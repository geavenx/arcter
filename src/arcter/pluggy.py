from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
import os
from typing import Any

import httpx

from arcter import credentials

BASE_URL = "https://api.pluggy.ai"
DEFAULT_TIMEOUT_SECONDS = 15.0


class PluggyError(Exception):
    """Raised when Pluggy integration operations fail."""


@dataclass(frozen=True, slots=True)
class BalanceRow:
    type: str
    name: str
    balance: Decimal | None
    currency_code: str


@dataclass(frozen=True, slots=True)
class CreditCardRow:
    name: str
    number: str
    balance: Decimal | None
    currency_code: str
    credit_limit: Decimal | None
    available_credit_limit: Decimal | None
    balance_due_date: str | None
    minimum_payment: Decimal | None
    brand: str | None
    level: str | None
    status: str | None
    holder_type: str | None


@dataclass(frozen=True, slots=True)
class TransactionRow:
    date: str
    description: str
    amount: Decimal
    currency_code: str
    type: str
    status: str
    category: str | None
    account_name: str
    account_type: str


@dataclass(frozen=True, slots=True)
class CategorySummary:
    category: str
    total: Decimal
    count: int
    percentage: Decimal


def _sanitize(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip()


def _load_config_item_id() -> str:
    """Load pluggy.item_id from config, returning empty string on any failure."""
    try:
        from arcter.config import load_config

        config = load_config()
        return config.pluggy.item_id
    except Exception:
        return ""


def resolve_item_id(
    item_id: str | None,
    env: Mapping[str, str] | None = None,
    config_item_id: str | None = None,
) -> str:
    env_vars = env or os.environ
    resolved_item_id = (
        _sanitize(item_id)
        or _sanitize(env_vars.get("PLUGGY_ITEM_ID"))
        or _sanitize(config_item_id)
    )

    if not resolved_item_id:
        raise PluggyError(
            "Missing Pluggy item ID. "
            "Provide ITEM_ID argument, set PLUGGY_ITEM_ID, "
            "or run 'arcter config set pluggy.item_id <id>'."
        )

    return resolved_item_id


def resolve_credentials(
    env: Mapping[str, str] | None = None,
) -> tuple[str, str]:
    env_vars = env or os.environ
    client_id = _sanitize(env_vars.get("PLUGGY_CLIENT_ID"))
    client_secret = _sanitize(env_vars.get("PLUGGY_CLIENT_SECRET"))

    if not client_id or not client_secret:
        stored = credentials.load_credentials()
        if stored is not None:
            stored_id, stored_secret = stored
            if not client_id:
                client_id = stored_id
            if not client_secret:
                client_secret = stored_secret

    missing: list[str] = []
    if not client_id:
        missing.append("PLUGGY_CLIENT_ID")
    if not client_secret:
        missing.append("PLUGGY_CLIENT_SECRET")

    if missing:
        raise PluggyError(
            f"Missing Pluggy credentials: {', '.join(missing)}. "
            "Set environment variables or run 'arcter account login'."
        )

    return client_id, client_secret


def _format_http_error(operation: str, response: httpx.Response) -> str:
    detail = ""

    try:
        response_payload: Any = response.json()
    except ValueError:
        response_payload = response.text

    if isinstance(response_payload, dict):
        for candidate in ("message", "error", "detail", "title"):
            if candidate in response_payload and response_payload[candidate]:
                detail = str(response_payload[candidate])
                break

        if not detail:
            detail = json.dumps(response_payload)
    else:
        detail = str(response_payload).strip()

    if detail:
        return f"Pluggy {operation} failed with status {response.status_code}: {detail}"

    return f"Pluggy {operation} failed with status {response.status_code}."


def _request_json(
    method: str,
    path: str,
    headers: Mapping[str, str],
    operation: str,
    json_payload: Mapping[str, Any] | None = None,
    params: Mapping[str, Any] | None = None,
) -> Any:
    normalized_path = path if path.startswith("/") else f"/{path}"
    url = f"{BASE_URL}{normalized_path}"

    request_kwargs: dict[str, Any] = {
        "headers": dict(headers),
        "timeout": DEFAULT_TIMEOUT_SECONDS,
    }
    if json_payload is not None:
        request_kwargs["json"] = json_payload
    if params is not None:
        request_kwargs["params"] = dict(params)

    try:
        response = httpx.request(method, url, **request_kwargs)
    except httpx.TimeoutException as exc:
        raise PluggyError(
            f"Pluggy {operation} request timed out. Please try again."
        ) from exc
    except httpx.HTTPError as exc:
        raise PluggyError(f"Pluggy {operation} request failed: {exc}") from exc

    if not response.is_success:
        raise PluggyError(_format_http_error(operation, response))

    if response.status_code == 204 or not response.content:
        return {}

    try:
        return response.json()
    except ValueError as exc:
        raise PluggyError(
            f"Pluggy {operation} returned an invalid JSON response."
        ) from exc


def authenticate(client_id: str, client_secret: str) -> str:
    response_payload = _request_json(
        method="POST",
        path="/auth",
        headers={"accept": "application/json", "content-type": "application/json"},
        operation="auth",
        json_payload={"clientId": client_id, "clientSecret": client_secret},
    )

    api_key = response_payload.get("apiKey")
    if not isinstance(api_key, str) or not api_key.strip():
        raise PluggyError("Pluggy auth returned an invalid response: missing apiKey.")

    return api_key


def update_item(item_id: str, api_key: str) -> None:
    _request_json(
        method="PATCH",
        path=f"/items/{item_id}",
        headers={
            "accept": "application/json",
            "content-type": "application/json",
            "X-API-KEY": api_key,
        },
        operation="item update",
    )


def _extract_account_entries(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        if not all(isinstance(entry, Mapping) for entry in payload):
            raise PluggyError(
                "Pluggy accounts list returned malformed account entries."
            )
        return [entry for entry in payload if isinstance(entry, Mapping)]

    if isinstance(payload, Mapping):
        for key in ("results", "items", "data"):
            if key in payload:
                entries = payload[key]
                if not isinstance(entries, list):
                    raise PluggyError(
                        "Pluggy accounts list returned an invalid payload format."
                    )
                if not all(isinstance(entry, Mapping) for entry in entries):
                    raise PluggyError(
                        "Pluggy accounts list returned malformed account entries."
                    )
                return [entry for entry in entries if isinstance(entry, Mapping)]

    raise PluggyError("Pluggy accounts list returned an invalid payload format.")


def _parse_balance(value: Any) -> Decimal | None:
    if value is None:
        return None

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _parse_optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None

    normalized = value.strip()
    if not normalized:
        return None

    return normalized


def list_item_balances(item_id: str, api_key: str) -> list[BalanceRow]:
    payload = _request_json(
        method="GET",
        path="/accounts",
        headers={"accept": "application/json", "X-API-KEY": api_key},
        operation="accounts list",
        params={"itemId": item_id},
    )
    accounts = _extract_account_entries(payload)

    rows: list[BalanceRow] = []
    for account in accounts:
        account_type_raw = account.get("type")
        account_type = (
            account_type_raw.strip().upper()
            if isinstance(account_type_raw, str)
            else str(account_type_raw or "").strip().upper()
        )
        if account_type not in ("BANK", "CREDIT"):
            continue

        name_raw = account.get("name")
        name = name_raw.strip() if isinstance(name_raw, str) else ""
        if not name:
            name = "Unnamed account"

        currency_raw = account.get("currencyCode")
        currency_code = (
            currency_raw.strip().upper() if isinstance(currency_raw, str) else ""
        )
        if not currency_code:
            currency_code = "N/A"

        rows.append(
            BalanceRow(
                type=account_type,
                name=name,
                balance=_parse_balance(account.get("balance")),
                currency_code=currency_code,
            )
        )

    return rows


def list_item_credit_cards(item_id: str, api_key: str) -> list[CreditCardRow]:
    payload = _request_json(
        method="GET",
        path="/accounts",
        headers={"accept": "application/json", "X-API-KEY": api_key},
        operation="accounts list",
        params={"itemId": item_id},
    )
    accounts = _extract_account_entries(payload)

    rows: list[CreditCardRow] = []
    for account in accounts:
        account_type_raw = account.get("type")
        account_type = (
            account_type_raw.strip().upper()
            if isinstance(account_type_raw, str)
            else str(account_type_raw or "").strip().upper()
        )
        if account_type != "CREDIT":
            continue

        name_raw = account.get("name")
        name = name_raw.strip() if isinstance(name_raw, str) else ""
        if not name:
            name = "Unnamed account"

        number = ""
        number_raw = account.get("number")
        if isinstance(number_raw, str):
            digits = "".join(char for char in number_raw if char.isdigit())
            if digits:
                number = digits[-4:]

        currency_raw = account.get("currencyCode")
        currency_code = (
            currency_raw.strip().upper() if isinstance(currency_raw, str) else ""
        )
        if not currency_code:
            currency_code = "N/A"

        credit_data_raw = account.get("creditData")
        credit_data = credit_data_raw if isinstance(credit_data_raw, Mapping) else {}

        rows.append(
            CreditCardRow(
                name=name,
                number=number,
                balance=_parse_balance(account.get("balance")),
                currency_code=currency_code,
                credit_limit=_parse_balance(credit_data.get("creditLimit")),
                available_credit_limit=_parse_balance(
                    credit_data.get("availableCreditLimit")
                ),
                balance_due_date=_parse_optional_text(
                    credit_data.get("balanceDueDate")
                ),
                minimum_payment=_parse_balance(credit_data.get("minimumPayment")),
                brand=_parse_optional_text(credit_data.get("brand")),
                level=_parse_optional_text(credit_data.get("level")),
                status=_parse_optional_text(credit_data.get("status")),
                holder_type=_parse_optional_text(credit_data.get("holderType")),
            )
        )

    return rows


def list_item_accounts(item_id: str, api_key: str) -> list[dict[str, str]]:
    payload = _request_json(
        method="GET",
        path="/accounts",
        headers={"accept": "application/json", "X-API-KEY": api_key},
        operation="accounts list",
        params={"itemId": item_id},
    )
    accounts = _extract_account_entries(payload)

    rows: list[dict[str, str]] = []
    for account in accounts:
        account_type_raw = account.get("type")
        account_type = (
            account_type_raw.strip().upper()
            if isinstance(account_type_raw, str)
            else str(account_type_raw or "").strip().upper()
        )
        if account_type not in ("BANK", "CREDIT"):
            continue

        account_id_raw = account.get("id")
        account_id = account_id_raw.strip() if isinstance(account_id_raw, str) else ""
        if not account_id:
            continue

        name_raw = account.get("name")
        name = name_raw.strip() if isinstance(name_raw, str) else ""
        if not name:
            name = "Unnamed account"

        rows.append({"id": account_id, "name": name, "type": account_type})

    return rows


def _extract_transaction_entries(payload: Any) -> tuple[list[Mapping[str, Any]], int]:
    if not isinstance(payload, Mapping):
        raise PluggyError(
            "Pluggy transactions list returned an invalid payload format."
        )

    entries = payload.get("results")
    if not isinstance(entries, list):
        raise PluggyError(
            "Pluggy transactions list returned an invalid payload format."
        )
    if not all(isinstance(entry, Mapping) for entry in entries):
        raise PluggyError("Pluggy transactions list returned malformed entries.")

    total_pages_raw = payload.get("totalPages", 1)
    try:
        total_pages = int(total_pages_raw)
    except (TypeError, ValueError):
        total_pages = 1
    if total_pages < 1:
        total_pages = 1

    return [entry for entry in entries if isinstance(entry, Mapping)], total_pages


def list_account_transactions(
    account_id: str,
    api_key: str,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    base_params: dict[str, Any] = {"accountId": account_id, "pageSize": 500}
    if date_from:
        base_params["from"] = date_from
    if date_to:
        base_params["to"] = date_to

    rows: list[dict[str, Any]] = []
    page = 1
    while True:
        params = {**base_params, "page": page}
        payload = _request_json(
            method="GET",
            path="/transactions",
            headers={"accept": "application/json", "X-API-KEY": api_key},
            operation="transactions list",
            params=params,
        )
        entries, total_pages = _extract_transaction_entries(payload)
        rows.extend(dict(entry) for entry in entries)

        if page >= total_pages:
            break
        page += 1

    return rows


def _parse_transactions(
    raw_transactions: list[dict[str, Any]],
    account_name: str,
    account_type: str,
) -> list[TransactionRow]:
    normalized_account_name = account_name.strip() or "Unnamed account"
    normalized_account_type = account_type.strip().upper() or "BANK"

    rows: list[TransactionRow] = []
    for transaction in raw_transactions:
        raw_date = transaction.get("date")
        if isinstance(raw_date, str) and raw_date.strip():
            date = raw_date.strip().split("T", maxsplit=1)[0]
        else:
            date = "Unknown"

        raw_description = transaction.get("description")
        description = (
            raw_description.strip() if isinstance(raw_description, str) else ""
        )
        if not description:
            description = "No description"

        amount = _parse_balance(transaction.get("amount"))
        if amount is None:
            continue

        raw_currency = transaction.get("currencyCode")
        currency_code = (
            raw_currency.strip().upper() if isinstance(raw_currency, str) else ""
        )
        if not currency_code:
            currency_code = "N/A"

        raw_type = transaction.get("type")
        transaction_type = raw_type.strip().upper() if isinstance(raw_type, str) else ""
        if not transaction_type:
            transaction_type = "DEBIT"

        raw_status = transaction.get("status")
        status = raw_status.strip().upper() if isinstance(raw_status, str) else ""
        if not status:
            status = "POSTED"

        raw_category = transaction.get("category")
        category = raw_category.strip() if isinstance(raw_category, str) else None
        if category == "":
            category = None

        rows.append(
            TransactionRow(
                date=date,
                description=description,
                amount=amount,
                currency_code=currency_code,
                type=transaction_type,
                status=status,
                category=category,
                account_name=normalized_account_name,
                account_type=normalized_account_type,
            )
        )

    return rows


def aggregate_by_category(
    transactions: list[TransactionRow],
    direction: str = "expense",
) -> list[CategorySummary]:
    normalized_direction = direction.strip().lower()
    if normalized_direction not in ("expense", "income", "all"):
        raise ValueError("direction must be one of: expense, income, all.")

    totals_by_category: dict[str, Decimal] = {}
    counts_by_category: dict[str, int] = {}
    grand_total = Decimal("0")

    for transaction in transactions:
        transaction_type = transaction.type.strip().upper()
        if normalized_direction == "expense" and transaction_type != "DEBIT":
            continue
        if normalized_direction == "income" and transaction_type != "CREDIT":
            continue

        category = (
            transaction.category.strip()
            if isinstance(transaction.category, str) and transaction.category.strip()
            else "Uncategorized"
        )
        absolute_amount = abs(transaction.amount)

        if normalized_direction == "expense":
            normalized_amount = absolute_amount
        elif normalized_direction == "income":
            normalized_amount = absolute_amount
        else:
            normalized_amount = (
                absolute_amount if transaction_type == "CREDIT" else -absolute_amount
            )

        totals_by_category[category] = (
            totals_by_category.get(category, Decimal("0")) + normalized_amount
        )
        counts_by_category[category] = counts_by_category.get(category, 0) + 1
        grand_total += absolute_amount

    if not totals_by_category:
        return []

    summaries = [
        CategorySummary(
            category=category,
            total=total,
            count=counts_by_category[category],
            percentage=(
                ((total / grand_total) * Decimal("100")).quantize(Decimal("0.1"))
                if grand_total != 0
                else Decimal("0.0")
            ),
        )
        for category, total in totals_by_category.items()
    ]
    summaries.sort(key=lambda row: row.total, reverse=True)
    return summaries


def update_item_with_env(
    item_id: str | None,
    env: Mapping[str, str] | None = None,
) -> str:
    config_item_id = _load_config_item_id()
    resolved_item_id = resolve_item_id(item_id, env=env, config_item_id=config_item_id)
    client_id, client_secret = resolve_credentials(env=env)
    api_key = authenticate(client_id, client_secret)
    update_item(resolved_item_id, api_key)
    return resolved_item_id


def list_item_balances_with_env(
    item_id: str | None,
    env: Mapping[str, str] | None = None,
) -> list[BalanceRow]:
    config_item_id = _load_config_item_id()
    resolved_item_id = resolve_item_id(item_id, env=env, config_item_id=config_item_id)
    client_id, client_secret = resolve_credentials(env=env)
    api_key = authenticate(client_id, client_secret)
    return list_item_balances(resolved_item_id, api_key)


def list_item_credit_cards_with_env(
    item_id: str | None,
    env: Mapping[str, str] | None = None,
) -> list[CreditCardRow]:
    config_item_id = _load_config_item_id()
    resolved_item_id = resolve_item_id(item_id, env=env, config_item_id=config_item_id)
    client_id, client_secret = resolve_credentials(env=env)
    api_key = authenticate(client_id, client_secret)
    return list_item_credit_cards(resolved_item_id, api_key)


def list_item_transactions_with_env(
    item_id: str | None,
    date_from: str | None = None,
    date_to: str | None = None,
    account_type_filter: str | None = None,
    env: Mapping[str, str] | None = None,
) -> list[TransactionRow]:
    config_item_id = _load_config_item_id()
    resolved_item_id = resolve_item_id(item_id, env=env, config_item_id=config_item_id)
    client_id, client_secret = resolve_credentials(env=env)
    api_key = authenticate(client_id, client_secret)

    accounts = list_item_accounts(resolved_item_id, api_key)
    normalized_filter = (
        account_type_filter.strip().upper()
        if isinstance(account_type_filter, str)
        else None
    )
    if normalized_filter:
        accounts = [row for row in accounts if row["type"] == normalized_filter]

    transactions: list[TransactionRow] = []
    for account in accounts:
        raw_transactions = list_account_transactions(
            account["id"],
            api_key,
            date_from=date_from,
            date_to=date_to,
        )
        transactions.extend(
            _parse_transactions(
                raw_transactions,
                account_name=account["name"],
                account_type=account["type"],
            )
        )

    transactions.sort(
        key=lambda row: (row.date != "Unknown", row.date),
        reverse=True,
    )
    return transactions
