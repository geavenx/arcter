from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from difflib import get_close_matches
from enum import Enum
import json
import os
from pathlib import Path
import tomllib
from typing import Any, Callable, Mapping

from platformdirs import user_config_dir
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from pydantic_extra_types.currency_code import ISO4217
import tomli_w

from arcter.constants import APP_AUTHOR, APP_NAME


class ConfigKey(str, Enum):
    currency = "currency"
    salary = "salary"
    savings_goal = "savings_goal"
    credit_cards_invoice_due_day = "credit_cards.invoice_due_day"
    credit_cards_excluded_categories = "credit_cards.excluded_categories"
    pluggy_item_id = "pluggy.item_id"


VALID_KEYS = tuple(key.value for key in ConfigKey)


class ConfigError(Exception):
    """Base exception for user-facing configuration errors."""


class ConfigFileError(ConfigError):
    """Raised when the TOML file cannot be loaded."""


class UnknownConfigKeyError(ConfigError):
    """Raised when a key is not in the allowed set."""

    def __init__(self, key: str) -> None:
        candidates = [*VALID_KEYS]
        suggestion = get_close_matches(key, candidates, n=1, cutoff=0.6)

        message = f"Unknown config key '{key}'. Valid keys: {', '.join(VALID_KEYS)}."
        if suggestion:
            message = f"{message} Did you mean '{suggestion[0]}'?"

        super().__init__(message)


class ConfigValidationError(ConfigError):
    """Raised when a config value fails schema validation."""


@dataclass(frozen=True, slots=True)
class _KeyDescriptor:
    serialize: Callable[[Any], Any]
    parse_cli: Callable[[str], Any]
    format_output: Callable[[Any], str]


def _parse_int(raw: str, key_name: str) -> int:
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigValidationError(
            f"Invalid value for '{key_name}'. Use an integer between 1 and 31."
        ) from exc


def _make_decimal_parser(key_name: str) -> Callable[[str], Decimal]:
    def parse(raw: str) -> Decimal:
        try:
            return Decimal(raw)
        except InvalidOperation as exc:
            raise ConfigValidationError(
                f"Invalid value for '{key_name}'. Use a numeric value, for example: 2500.00"
            ) from exc

    return parse


def _format_decimal(value: Any) -> str:
    decimal_value = Decimal(value).quantize(Decimal("0.01"))
    return str(decimal_value)


_KEY_REGISTRY: dict[str, _KeyDescriptor] = {
    "currency": _KeyDescriptor(
        serialize=str,
        parse_cli=lambda raw: raw.strip().upper(),
        format_output=str,
    ),
    "salary": _KeyDescriptor(
        serialize=lambda value: float(Decimal(value)),
        parse_cli=_make_decimal_parser("salary"),
        format_output=_format_decimal,
    ),
    "savings_goal": _KeyDescriptor(
        serialize=lambda value: float(Decimal(value)),
        parse_cli=_make_decimal_parser("savings_goal"),
        format_output=_format_decimal,
    ),
    "credit_cards.invoice_due_day": _KeyDescriptor(
        serialize=int,
        parse_cli=lambda raw: _parse_int(raw, "credit_cards.invoice_due_day"),
        format_output=lambda value: str(int(value)),
    ),
    "credit_cards.excluded_categories": _KeyDescriptor(
        serialize=lambda value: [str(entry) for entry in list(value)],
        parse_cli=lambda raw: [
            entry.strip() for entry in raw.split(",") if entry.strip()
        ],
        format_output=lambda value: json.dumps(list(value)),
    ),
    "pluggy.item_id": _KeyDescriptor(
        serialize=str,
        parse_cli=lambda raw: raw.strip(),
        format_output=lambda value: str(value) if value else "",
    ),
}


class CreditCardsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invoice_due_day: int = Field(default=30, ge=1, le=31)
    excluded_categories: list[str] = Field(default_factory=list)

    @field_validator("excluded_categories", mode="before")
    @classmethod
    def normalize_excluded_categories(cls, value: Any) -> Any:
        if value is None:
            return []

        if isinstance(value, str):
            candidates: list[Any] = value.split(",")
        elif isinstance(value, tuple):
            candidates = list(value)
        elif isinstance(value, list):
            candidates = value
        else:
            return value

        normalized: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            text = str(candidate).strip()
            if not text:
                continue

            dedupe_key = text.casefold()
            if dedupe_key in seen:
                continue

            seen.add(dedupe_key)
            normalized.append(text)

        return normalized


class PluggyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(default="")


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: ISO4217 = Field(default=ISO4217("BRL"))
    salary: Decimal = Field(default=Decimal("200.00"), decimal_places=2)
    savings_goal: Decimal = Field(default=Decimal("500.00"), decimal_places=2)
    credit_cards: CreditCardsConfig = Field(default_factory=CreditCardsConfig)
    pluggy: PluggyConfig = Field(default_factory=PluggyConfig)

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().upper()
        return value


def user_config_path() -> Path:
    config_dir = Path(user_config_dir(APP_NAME, APP_AUTHOR))
    return config_dir / "config.toml"


def _format_validation_error(exc: ValidationError) -> str:
    lines = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        lines.append(f"- {location}: {error['msg']}")

    return "Invalid configuration:\n" + "\n".join(lines)


def _normalize_key(key: str) -> str:
    return key.strip().lower()


def normalize_and_validate_key(key: str) -> str:
    normalized = _normalize_key(key)
    if normalized not in VALID_KEYS:
        raise UnknownConfigKeyError(key)
    return normalized


def _normalize_input_map(
    data: Mapping[str, Any],
    prefix: str = "",
) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for raw_key, value in data.items():
        key = _normalize_key(str(raw_key))
        full_key = f"{prefix}.{key}" if prefix else key

        if isinstance(value, Mapping):
            normalized.update(_normalize_input_map(value, prefix=full_key))
            continue

        normalized_key = normalize_and_validate_key(full_key)
        normalized[normalized_key] = value

    return normalized


def _flat_to_nested_map(data: Mapping[str, Any]) -> dict[str, Any]:
    nested: dict[str, Any] = {}

    for raw_key, value in data.items():
        key = normalize_and_validate_key(str(raw_key))
        path = key.split(".")
        current: dict[str, Any] = nested

        for part in path[:-1]:
            current_value = current.get(part)
            if isinstance(current_value, dict):
                current = current_value
                continue

            next_map: dict[str, Any] = {}
            current[part] = next_map
            current = next_map

        current[path[-1]] = value

    return nested


def _resolve_config_value(config: Config, key: str) -> Any:
    resolved: Any = config
    for part in key.split("."):
        resolved = getattr(resolved, part)
    return resolved


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        with path.open("rb") as file_handle:
            raw = tomllib.load(file_handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigFileError(
            f"Config file is not valid TOML: {path}\n"
            f"Fix the syntax and run the command again.\n"
            f"Parser error: {exc}"
        ) from exc

    if not isinstance(raw, dict):
        raise ConfigFileError(
            f"Config file must contain key/value pairs at top-level: {path}"
        )

    return _normalize_input_map(raw)


def load_user_config() -> dict[str, Any]:
    return _load_toml(user_config_path())


def load_env_config() -> dict[str, Any]:
    config: dict[str, Any] = {}

    if "ARCTER_SALARY" in os.environ:
        config["salary"] = os.environ["ARCTER_SALARY"]

    if "ARCTER_CURRENCY" in os.environ:
        config["currency"] = os.environ["ARCTER_CURRENCY"]

    if "ARCTER_SAVINGS_GOAL" in os.environ:
        config["savings_goal"] = os.environ["ARCTER_SAVINGS_GOAL"]

    if "ARCTER_INVOICE_DUE_DAY" in os.environ:
        config["credit_cards.invoice_due_day"] = os.environ["ARCTER_INVOICE_DUE_DAY"]

    if "PLUGGY_ITEM_ID" in os.environ:
        config["pluggy.item_id"] = os.environ["PLUGGY_ITEM_ID"]

    return _normalize_input_map(config)


def _serialize_for_toml(key: str, value: Any) -> Any:
    descriptor = _KEY_REGISTRY.get(key)
    if descriptor is None:
        return value
    return descriptor.serialize(value)


def _write_toml(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sorted_data = dict(sorted(data.items()))

    tmp = path.with_suffix(".tmp")
    tmp.write_text(tomli_w.dumps(sorted_data), encoding="utf-8")
    tmp.replace(path)


def _validate_payload(payload: Mapping[str, Any]) -> Config:
    normalized_payload = _normalize_input_map(payload)
    nested_payload = _flat_to_nested_map(normalized_payload)

    try:
        return Config(**nested_payload)
    except ValidationError as exc:
        raise ConfigValidationError(_format_validation_error(exc)) from exc


def _normalize_cli_value(key: str, raw_value: str) -> Any:
    descriptor = _KEY_REGISTRY.get(key)
    if descriptor is None:
        return raw_value
    return descriptor.parse_cli(raw_value)


def load_config(cli_overrides: Mapping[str, Any] | None = None) -> Config:
    cli_overrides = _normalize_input_map(cli_overrides or {})
    merged = {**load_user_config(), **load_env_config(), **cli_overrides}
    return _validate_payload(merged)


def resolve_config_with_sources(
    cli_overrides: Mapping[str, Any] | None = None,
) -> tuple[Config, dict[str, str]]:
    cli_overrides = _normalize_input_map(cli_overrides or {})
    file_config = load_user_config()
    env_config = load_env_config()
    merged = {**file_config, **env_config, **cli_overrides}
    resolved = _validate_payload(merged)

    sources = {key: "default" for key in VALID_KEYS}
    for key in file_config:
        sources[key] = "file"
    for key in env_config:
        sources[key] = "env"
    for key in cli_overrides:
        sources[key] = "cli"

    return resolved, sources


def _value_for_output(key: str, value: Any) -> str:
    descriptor = _KEY_REGISTRY.get(key)
    if descriptor is None:
        return str(value)
    return descriptor.format_output(value)


def set_user_config(key: str, raw_value: str) -> tuple[str, str]:
    normalized_key = normalize_and_validate_key(key)
    normalized_value = _normalize_cli_value(normalized_key, raw_value)

    data = load_user_config()
    candidate = dict(data)
    candidate[normalized_key] = normalized_value
    validated = _validate_payload(candidate)
    validated_value = _resolve_config_value(validated, normalized_key)

    data[normalized_key] = _serialize_for_toml(normalized_key, validated_value)
    _write_toml(user_config_path(), _flat_to_nested_map(data))

    return normalized_key, _value_for_output(normalized_key, validated_value)


def unset_user_config(key: str) -> bool:
    normalized_key = normalize_and_validate_key(key)
    data = load_user_config()

    if normalized_key not in data:
        return False

    del data[normalized_key]
    _write_toml(user_config_path(), _flat_to_nested_map(data))
    return True


def get_config_value(key: str) -> tuple[str, str, str]:
    normalized_key = normalize_and_validate_key(key)
    config, sources = resolve_config_with_sources()
    value = _value_for_output(
        normalized_key, _resolve_config_value(config, normalized_key)
    )
    return normalized_key, value, sources[normalized_key]


def list_config_values() -> tuple[dict[str, str], dict[str, str]]:
    config, sources = resolve_config_with_sources()
    values = {
        key: _value_for_output(key, _resolve_config_value(config, key))
        for key in VALID_KEYS
    }
    return values, sources


def list_config_as_json() -> str:
    values, sources = list_config_values()
    payload = {
        key: {"value": values[key], "source": sources[key]} for key in VALID_KEYS
    }
    return json.dumps(payload, indent=2)


def list_config_as_toml() -> str:
    config = load_config()
    flat_payload = {
        key: _serialize_for_toml(key, _resolve_config_value(config, key))
        for key in VALID_KEYS
    }
    return tomli_w.dumps(_flat_to_nested_map(flat_payload))
