from decimal import Decimal
import os
import tomllib


from pathlib import Path
from typing import Any, Dict

from platformdirs import user_config_dir
from pydantic import BaseModel, Field, ValidationError
from pydantic_extra_types.currency_code import ISO4217

from arcter import cli


class Config(BaseModel):
    salary: Decimal = Field(default=Decimal(200.00), decimal_places=2)
    currecy: ISO4217 = Field(default=ISO4217("BRL"))


DEFAULT_CONFIG: Dict[str, Any] = {"salary": "", "currency": "BRL"}


def _load_toml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)

def _format_toml_value(value: Any) -> str:
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f"{escaped}"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    raise TypeError(f"Unsupported TOML type: {type(value)}")

def _write_toml(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for key in sorted(data.keys()):
        value = _format_toml_value(data[key])
        lines.append(f"{key} = {value}")

    content = "\n".join(lines) + "\n"

    tmp = path.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)

def user_config_path() -> Path:
    config_dir = Path(user_config_dir(cli.APP_NAME, cli.APP_AUTHOR))
    return config_dir / "config.toml"

def load_user_config() -> Dict[str, Any]:
    return _load_toml(user_config_path())


def load_env_config() -> Dict[str, Any]:
    config: Dict[str, Any] = {}

    if "ARCTER_SALARY" in os.environ:
        config["salary"] = os.environ["ARCTER_SALARY"]

    if "ARCTER_CURRENCY" in os.environ:
        config["currency"] = os.environ["ARCTER_CURRENCY"]

    return config


def merge_configs(*configs: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for cfg in configs:
        result.update(cfg)

    return result


def load_config(cli_overrides: Dict[str, Any] | None = None) -> Config:
    f"""
    Precedence of configuration:
    1. CLI args
    2. Environment variables
    3. User config (~/.config/{cli.APP_NAME})
    4. Defaults
    """
    cli_overrides = cli_overrides or {}

    merged = merge_configs(
        {},
        load_user_config(),
        load_env_config(),
        cli_overrides,
    )

    try:
        return Config(**merged)
    except ValidationError as e:
        raise SystemExit(f"Invalid configuration: \n{e}")


def add_user_config(key: str, value: Any) -> None:
    data = load_user_config()
    data[key] = value

    # Validation only
    Config(**merge_configs({}, data))

    _write_toml(user_config_path(), data)

def delete_user_config(key: str) -> None:
    data = load_user_config()
    if key in data:
        del data[key]
        _write_toml(user_config_path(), data)

def list_configs() -> Config:
    return load_config()
