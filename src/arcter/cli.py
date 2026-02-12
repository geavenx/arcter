import calendar
import csv
import datetime
import json
import sys
from datetime import date
from decimal import Decimal
from enum import Enum

import typer

from arcter.config import (
    ConfigError,
    ConfigKey,
    get_config_value,
    list_config_as_json,
    list_config_as_toml,
    list_config_values,
    load_config,
    set_user_config,
    unset_user_config,
    user_config_path,
)
from arcter.constants import APP_NAME
from arcter import credentials, pluggy

app = typer.Typer(name=APP_NAME)
config_app = typer.Typer(help="Manage CLI configuration values.")
account_app = typer.Typer(help="Manage external account integrations.")
app.add_typer(config_app, name="config")
app.add_typer(account_app, name="account")


class OutputFormat(str, Enum):
    table = "table"
    json = "json"
    toml = "toml"


class TransactionOutputFormat(str, Enum):
    table = "table"
    csv = "csv"
    json = "json"


def _exit_with_error(exc: Exception) -> None:
    """
    Print an error message in red to stderr and terminate the application with exit code 1.

    Parameters:
        exc (Exception): The exception whose message will be printed.
    """
    typer.secho(str(exc), fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)


def _print_table(values: dict[str, str], sources: dict[str, str]) -> None:
    rows = [
        ("currency", values["currency"], sources["currency"]),
        ("salary", values["salary"], sources["salary"]),
        ("savings_goal", values["savings_goal"], sources["savings_goal"]),
        (
            "pluggy.item_id",
            values["pluggy.item_id"],
            sources["pluggy.item_id"],
        ),
        (
            "credit_cards.invoice_due_day",
            values["credit_cards.invoice_due_day"],
            sources["credit_cards.invoice_due_day"],
        ),
        (
            "credit_cards.excluded_categories",
            values["credit_cards.excluded_categories"],
            sources["credit_cards.excluded_categories"],
        ),
    ]
    headers = ("Key", "Value", "Source")
    widths = [len(column) for column in headers]

    for row in rows:
        widths = [
            max(current, len(value)) for current, value in zip(widths, row, strict=True)
        ]

    typer.echo(
        f"{headers[0]:<{widths[0]}}  {headers[1]:<{widths[1]}}  {headers[2]:<{widths[2]}}"
    )
    typer.echo(f"{'-' * widths[0]}  {'-' * widths[1]}  {'-' * widths[2]}")
    for key, value, source in rows:
        typer.echo(f"{key:<{widths[0]}}  {value:<{widths[1]}}  {source:<{widths[2]}}")


def _format_balance_value(value: Decimal | None) -> str:
    if value is None:
        return "N/A"
    return str(value.quantize(Decimal("0.01")))


def _format_currency_amount(currency_code: str, value: Decimal) -> str:
    return f"{currency_code} {value.quantize(Decimal('0.01'))}"


def _format_currency_amount_grouped(
    currency_code: str,
    value: Decimal,
    show_sign: bool = False,
) -> str:
    quantized = value.quantize(Decimal("0.01"))
    if show_sign:
        return f"{currency_code} {quantized:+,.2f}"
    return f"{currency_code} {quantized:,.2f}"


def _truncate_text(value: str, max_length: int = 20) -> str:
    if len(value) <= max_length:
        return value
    return f"{value[: max_length - 3]}..."


def _validate_iso_date(value: str | None, option_name: str) -> str | None:
    if value is None:
        return None

    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{option_name} must use YYYY-MM-DD format.")

    try:
        parsed = date.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{option_name} must use YYYY-MM-DD format.") from exc

    if parsed.isoformat() != normalized:
        raise ValueError(f"{option_name} must use YYYY-MM-DD format.")

    return normalized


def _normalize_account_type_filter(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip().upper()
    if normalized not in ("BANK", "CREDIT"):
        raise ValueError("Option --account-type must be either 'bank' or 'credit'.")

    return normalized


def _normalize_transaction_type_filter(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip().upper()
    if normalized not in ("CREDIT", "DEBIT"):
        raise ValueError("Option --type must be either 'credit' or 'debit'.")

    return normalized


def _normalize_spending_direction(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in ("expense", "income", "all"):
        raise ValueError("Option --direction must be one of: expense, income, all.")
    return normalized


def _normalize_excluded_categories(
    config_categories: list[str],
    cli_categories: list[str],
) -> set[str]:
    normalized_categories: set[str] = set()

    for value in [*config_categories, *cli_categories]:
        normalized = value.strip()
        if normalized:
            normalized_categories.add(normalized.casefold())

    return normalized_categories


def _derive_invoice_cycle_date_range(
    invoice_due_day: int,
    reference_date: date | None = None,
) -> tuple[str, str]:
    current = reference_date or date.today()

    if current.month == 1:
        previous_year = current.year - 1
        previous_month = 12
    else:
        previous_year = current.year
        previous_month = current.month - 1

    previous_month_last_day = calendar.monthrange(previous_year, previous_month)[1]
    current_month_last_day = calendar.monthrange(current.year, current.month)[1]

    start_day = min(invoice_due_day, previous_month_last_day)
    end_day = min(invoice_due_day, current_month_last_day)

    start_date = date(previous_year, previous_month, start_day)
    end_date = date(current.year, current.month, end_day)

    return start_date.isoformat(), end_date.isoformat()


def _current_month_date_range(
    today: datetime.date | None = None,
) -> tuple[str, str]:
    current = today or datetime.date.today()
    return current.replace(day=1).isoformat(), current.isoformat()


def _format_transaction_amount(amount: Decimal, transaction_type: str) -> str:
    sign = "+" if transaction_type == "CREDIT" else "-"
    quantized = abs(amount).quantize(Decimal("0.01"))
    return f"{sign}{quantized:,.2f}"


def _signed_transaction_amount(amount: Decimal, transaction_type: str) -> Decimal:
    if transaction_type.strip().upper() == "CREDIT":
        return abs(amount)
    return -abs(amount)


def _format_total_amount(value: Decimal) -> str:
    sign = "+" if value >= 0 else "-"
    quantized = abs(value).quantize(Decimal("0.01"))
    return f"{sign}{quantized:,.2f}"


def _print_transaction_table(rows: list[pluggy.TransactionRow]) -> None:
    """
    Prints a formatted table of transaction rows to standard output.

    Parameters:
        rows (list[pluggy.TransactionRow]): Transaction rows to render. Each row is displayed as a table row with the columns: Date, Account, Type, Amount, Currency, Category, and Status.
    """
    table_rows = [
        (
            row.date,
            _truncate_text(row.account_name.strip() or "Unnamed account"),
            row.type,
            _format_transaction_amount(row.amount, row.type),
            row.currency_code,
            _truncate_text(row.category or ""),
            row.status,
        )
        for row in rows
    ]
    headers = ("Date", "Account", "Type", "Amount", "Currency", "Category", "Status")
    widths = [len(column) for column in headers]

    for row in table_rows:
        widths = [
            max(current, len(value)) for current, value in zip(widths, row, strict=True)
        ]

    typer.echo(
        f"{headers[0]:<{widths[0]}}  {headers[1]:<{widths[1]}}  {headers[2]:<{widths[2]}}  {headers[3]:<{widths[3]}}  {headers[4]:<{widths[4]}}  {headers[5]:<{widths[5]}}  {headers[6]:<{widths[6]}}"
    )
    typer.echo(
        f"{'-' * widths[0]}  {'-' * widths[1]}  {'-' * widths[2]}  {'-' * widths[3]}  {'-' * widths[4]}  {'-' * widths[5]}  {'-' * widths[6]}"
    )
    for row in table_rows:
        typer.echo(
            f"{row[0]:<{widths[0]}}  {row[1]:<{widths[1]}}  {row[2]:<{widths[2]}}  {row[3]:<{widths[3]}}  {row[4]:<{widths[4]}}  {row[5]:<{widths[5]}}  {row[6]:<{widths[6]}}"
        )


def _print_transaction_csv(rows: list[pluggy.TransactionRow]) -> None:
    """
    Write transaction rows to standard output as CSV using the header:
    Date, Account, Account Type, Type, Amount, Currency, Category, Status, Description.

    Parameters:
        rows (list[pluggy.TransactionRow]): Transactions to emit; each transaction becomes one CSV row.
        Amount values are formatted with two decimal places and missing categories are emitted as an empty string.
    """
    writer = csv.writer(sys.stdout)
    writer.writerow(
        [
            "Date",
            "Account",
            "Account Type",
            "Type",
            "Amount",
            "Currency",
            "Category",
            "Status",
            "Description",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row.date,
                row.account_name,
                row.account_type,
                row.type,
                str(row.amount.quantize(Decimal("0.01"))),
                row.currency_code,
                row.category or "",
                row.status,
                row.description,
            ]
        )


def _print_transaction_json(rows: list[pluggy.TransactionRow]) -> None:
    """
    Prints the given transaction rows as a formatted JSON array to standard output.

    Each transaction is serialized to an object with keys: `date`, `account`, `account_type`, `type`, `amount`, `currency`, `category`, `status`, and `description`. The `amount` value is formatted as a string with two decimal places.

    Parameters:
        rows (list[pluggy.TransactionRow]): Transaction rows to serialize and print.
    """
    data = [
        {
            "date": row.date,
            "account": row.account_name,
            "account_type": row.account_type,
            "type": row.type,
            "amount": str(row.amount.quantize(Decimal("0.01"))),
            "currency": row.currency_code,
            "category": row.category,
            "status": row.status,
            "description": row.description,
        }
        for row in rows
    ]
    typer.echo(json.dumps(data, indent=2, ensure_ascii=False))


def _print_spending_table(
    rows: list[pluggy.CategorySummary],
    currency_code: str,
    direction: str,
    top_n: int | None = None,
) -> tuple[Decimal, int]:
    """
    Render a spending-by-category table to standard output.

    Parameters:
        rows (list[pluggy.CategorySummary]): Aggregated category summaries; each item is expected to have
            `category`, `total` (Decimal), `count` (int), and `percentage` (Decimal) attributes.
        currency_code (str): Currency code used to format amounts (e.g., "USD", "EUR").
        direction (str): Spending direction that determines sign formatting; expected values include
            "expense", "income", or "all".
        top_n (int | None): If provided, limit the displayed rows to the first `top_n` categories.

    Returns:
        total_amount (Decimal): Sum of `total` across all provided rows.
        total_count (int): Sum of `count` across all provided rows.
    """
    display_rows = rows[:top_n] if top_n is not None else rows
    show_sign = direction == "all"

    table_rows = [
        (
            _truncate_text(row.category),
            _format_currency_amount_grouped(
                currency_code,
                row.total,
                show_sign=show_sign,
            ),
            str(row.count),
            f"{row.percentage.quantize(Decimal('0.1'))}%",
        )
        for row in display_rows
    ]
    headers = ("Category", "Amount", "Count", "% of total")
    widths = [len(column) for column in headers]

    for row in table_rows:
        widths = [
            max(current, len(value)) for current, value in zip(widths, row, strict=True)
        ]

    typer.echo(
        f"{headers[0]:<{widths[0]}}  {headers[1]:>{widths[1]}}  {headers[2]:>{widths[2]}}  {headers[3]:>{widths[3]}}"
    )
    typer.echo(
        f"{'-' * widths[0]}  {'-' * widths[1]}  {'-' * widths[2]}  {'-' * widths[3]}"
    )
    for row in table_rows:
        typer.echo(
            f"{row[0]:<{widths[0]}}  {row[1]:>{widths[1]}}  {row[2]:>{widths[2]}}  {row[3]:>{widths[3]}}"
        )

    if top_n is not None and len(rows) > top_n:
        typer.echo(f"... and {len(rows) - top_n} more categories")

    total_amount = sum((row.total for row in rows), Decimal("0"))
    total_count = sum(row.count for row in rows)
    return total_amount, total_count


def _print_balance_table(rows: list[pluggy.BalanceRow]) -> None:
    table_rows = [
        (row.type, row.name, _format_balance_value(row.balance), row.currency_code)
        for row in rows
    ]
    headers = ("Type", "Name", "Balance", "Currency")
    widths = [len(column) for column in headers]

    for row in table_rows:
        widths = [
            max(current, len(value)) for current, value in zip(widths, row, strict=True)
        ]

    typer.echo(
        f"{headers[0]:<{widths[0]}}  {headers[1]:<{widths[1]}}  {headers[2]:<{widths[2]}}  {headers[3]:<{widths[3]}}"
    )
    typer.echo(
        f"{'-' * widths[0]}  {'-' * widths[1]}  {'-' * widths[2]}  {'-' * widths[3]}"
    )
    for account_type, name, balance, currency in table_rows:
        typer.echo(
            f"{account_type:<{widths[0]}}  {name:<{widths[1]}}  {balance:<{widths[2]}}  {currency:<{widths[3]}}"
        )


def _print_balance_totals(rows: list[pluggy.BalanceRow]) -> None:
    totals_by_currency: dict[str, Decimal] = {}
    for row in rows:
        if row.balance is None:
            continue
        totals_by_currency[row.currency_code] = (
            totals_by_currency.get(row.currency_code, Decimal("0")) + row.balance
        )

    if not totals_by_currency:
        typer.echo("")
        typer.echo("Totals by currency: no numeric balances available.")
        return

    typer.echo("")
    typer.echo("Totals by currency:")
    for currency_code, total in sorted(totals_by_currency.items()):
        typer.echo(f"- {currency_code}: {_format_balance_value(total)}")


@config_app.command("set")
def config_set(key: ConfigKey, value: str) -> None:
    """
    Set a persisted user configuration value.
    """
    try:
        normalized_key, normalized_value = set_user_config(key.value, value)
    except ConfigError as exc:
        _exit_with_error(exc)

    typer.echo(
        f"Set {normalized_key} = {normalized_value} (file: {user_config_path()})"
    )


@config_app.command("get")
def config_get(key: ConfigKey) -> None:
    """
    Show one effective configuration value and where it came from.
    """
    try:
        normalized_key, value, source = get_config_value(key.value)
    except ConfigError as exc:
        _exit_with_error(exc)

    typer.echo(f"{normalized_key} = {value} (source: {source})")


@config_app.command("unset")
def config_unset(key: ConfigKey) -> None:
    """
    Remove a persisted key from the user config file.
    """
    try:
        removed = unset_user_config(key.value)
    except ConfigError as exc:
        _exit_with_error(exc)

    if removed:
        typer.echo(f"Unset {key.value} from {user_config_path()}")
    else:
        typer.echo(f"Key '{key.value}' was not set in {user_config_path()}")


@config_app.command("list")
def config_list(
    output_format: OutputFormat = typer.Option(
        OutputFormat.table,
        "--format",
        "-f",
        help="Output format: table, json, or toml.",
        case_sensitive=False,
    ),
) -> None:
    """
    List effective configuration values.
    """
    try:
        if output_format == OutputFormat.json:
            typer.echo(list_config_as_json())
            return
        if output_format == OutputFormat.toml:
            typer.echo(list_config_as_toml())
            return

        values, sources = list_config_values()
        _print_table(values, sources)
    except ConfigError as exc:
        _exit_with_error(exc)


@config_app.command("path")
def config_path() -> None:
    """
    Print the absolute user config file path.
    """
    typer.echo(user_config_path())


@account_app.command("login")
def account_login(
    client_id: str | None = typer.Option(
        None,
        "--client-id",
        help="Pluggy API client ID.",
    ),
    client_secret: str | None = typer.Option(
        None,
        "--client-secret",
        help="Pluggy API client secret.",
    ),
    item_id: str | None = typer.Option(
        None,
        "--item-id",
        help="Pluggy item ID to store in config.",
    ),
) -> None:
    """Store Pluggy API credentials in the system keyring."""
    try:
        if client_id is None:
            client_id = typer.prompt("Pluggy Client ID")
        if client_secret is None:
            client_secret = typer.prompt("Pluggy Client Secret", hide_input=True)

        client_id = client_id.strip()
        client_secret = client_secret.strip()

        if not client_id or not client_secret:
            typer.secho(
                "Client ID and Client Secret must not be empty.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)

        credentials.store_credentials(client_id, client_secret)
        typer.echo("Credentials stored in system keyring.")

        if item_id is not None:
            item_id = item_id.strip()
            if not item_id:
                typer.secho(
                    "Item ID must not be empty.",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(code=1)
            set_user_config("pluggy.item_id", item_id)
            typer.echo(f"Set pluggy.item_id = {item_id}")
    except credentials.CredentialError as exc:
        _exit_with_error(exc)
    except ConfigError as exc:
        _exit_with_error(exc)


@account_app.command("logout")
def account_logout() -> None:
    """Remove Pluggy API credentials from the system keyring."""
    try:
        removed = credentials.delete_credentials()
    except credentials.CredentialError as exc:
        _exit_with_error(exc)

    if removed:
        typer.echo("Credentials removed from system keyring.")
    else:
        typer.echo("No credentials found in system keyring.")


@account_app.command("update")
def account_update(
    item_id: str | None = typer.Argument(
        None,
        help="Pluggy item ID. Falls back to PLUGGY_ITEM_ID if omitted.",
    ),
) -> None:
    """
    Refresh a Pluggy item state.
    """
    try:
        resolved_item_id = pluggy.update_item_with_env(item_id)
    except pluggy.PluggyError as exc:
        _exit_with_error(exc)

    typer.echo(f"Updated Pluggy item {resolved_item_id}.")


@account_app.command("balance")
def account_balance(
    item_id: str | None = typer.Argument(
        None,
        help="Pluggy item ID. Falls back to PLUGGY_ITEM_ID if omitted.",
    ),
) -> None:
    """
    Show current balances for BANK and CREDIT accounts.
    """
    try:
        rows = pluggy.list_item_balances_with_env(item_id)
    except pluggy.PluggyError as exc:
        _exit_with_error(exc)

    if not rows:
        typer.echo("No BANK or CREDIT accounts were found for this Pluggy item.")
        return

    _print_balance_table(rows)
    _print_balance_totals(rows)


@account_app.command("credit")
def account_credit(
    item_id: str | None = typer.Argument(
        None,
        help="Pluggy item ID. Falls back to PLUGGY_ITEM_ID if omitted.",
    ),
) -> None:
    """
    Show credit card details for connected accounts.
    """
    try:
        rows = pluggy.list_item_credit_cards_with_env(item_id)
    except pluggy.PluggyError as exc:
        _exit_with_error(exc)

    if not rows:
        typer.echo("No credit card accounts found for this Pluggy item.")
        return

    for index, row in enumerate(rows):
        card_header = f"{row.name} (****{row.number})" if row.number else row.name
        typer.echo(card_header)

        brand_parts = [part for part in (row.brand, row.level) if part]
        brand_value = " ".join(brand_parts) if brand_parts else "N/A"
        typer.echo(f"  Brand:      {brand_value}")

        if row.status and row.holder_type:
            status_value = f"{row.status} ({row.holder_type})"
        elif row.status:
            status_value = row.status
        elif row.holder_type:
            status_value = row.holder_type
        else:
            status_value = "N/A"
        typer.echo(f"  Status:     {status_value}")

        balance_value = (
            _format_currency_amount_grouped(row.currency_code, row.balance)
            if row.balance is not None
            else "N/A"
        )
        due_suffix = f"  (due: {row.balance_due_date})" if row.balance_due_date else ""
        typer.echo(f"  Balance:    {balance_value}{due_suffix}")

        if row.minimum_payment is not None:
            typer.echo(
                f"  Min. payment: {_format_currency_amount_grouped(row.currency_code, row.minimum_payment)}"
            )

        if row.credit_limit is not None:
            credit_limit_line = (
                "  Credit limit: "
                f"{_format_currency_amount_grouped(row.currency_code, row.credit_limit)}"
            )
            if row.available_credit_limit is not None:
                credit_limit_line += (
                    "  (available: "
                    f"{_format_currency_amount_grouped(row.currency_code, row.available_credit_limit)})"
                )
            typer.echo(credit_limit_line)

        if index < len(rows) - 1:
            typer.echo("")


@account_app.command("goal")
def account_goal(
    item_id: str | None = typer.Argument(
        None,
        help="Pluggy item ID. Falls back to PLUGGY_ITEM_ID if omitted.",
    ),
    currency: str | None = typer.Option(
        None,
        "--currency",
        "-c",
        help="Currency code used to filter BANK balances. Defaults to configured currency.",
    ),
) -> None:
    """
    Show savings goal progress using BANK balances.
    """
    try:
        config = load_config()
        rows = pluggy.list_item_balances_with_env(item_id)
    except (ConfigError, pluggy.PluggyError) as exc:
        _exit_with_error(exc)

    target_currency = currency.strip().upper() if currency else str(config.currency)
    bank_rows = [
        row
        for row in rows
        if row.type == "BANK" and row.currency_code.upper() == target_currency
    ]

    if not bank_rows:
        typer.echo(f"No BANK accounts found in {target_currency} for this Pluggy item.")
        return

    numeric_balances = [row.balance for row in bank_rows if row.balance is not None]
    if not numeric_balances:
        typer.echo(
            f"No numeric balances available for BANK accounts in {target_currency}."
        )
        return

    current_total = sum(numeric_balances, Decimal("0"))
    goal = Decimal(config.savings_goal)
    salary = Decimal(config.salary)

    if goal == 0:
        percentage = Decimal("100.0") if current_total > 0 else Decimal("0.0")
    else:
        percentage = ((current_total / goal) * Decimal("100")).quantize(Decimal("0.1"))

    typer.echo(f"Savings goal progress ({target_currency}):")
    typer.echo("")
    typer.echo(f"  Goal:       {_format_currency_amount(target_currency, goal)}")
    typer.echo(
        f"  Current:    {_format_currency_amount(target_currency, current_total)}  ({percentage}%)"
    )

    if current_total >= goal:
        surplus = current_total - goal
        typer.echo(f"  Surplus:    {_format_currency_amount(target_currency, surplus)}")
        typer.echo("  Goal reached!")
        return

    remaining = goal - current_total
    typer.echo(f"  Remaining:  {_format_currency_amount(target_currency, remaining)}")
    typer.echo(f"  Monthly salary: {_format_currency_amount(target_currency, salary)}")

    if salary > 0:
        estimated_months = (remaining / salary).quantize(Decimal("0.1"))
        typer.echo(f"  Estimated:  ~{estimated_months} months to reach goal")


@account_app.command("transactions")
def account_transactions(
    item_id: str | None = typer.Argument(
        None,
        help="Pluggy item ID. Falls back to PLUGGY_ITEM_ID if omitted.",
    ),
    date_from: str | None = typer.Option(
        None,
        "--from",
        "-f",
        help="Start date (YYYY-MM-DD).",
    ),
    date_to: str | None = typer.Option(
        None,
        "--to",
        "-t",
        help="End date (YYYY-MM-DD).",
    ),
    transaction_type: str | None = typer.Option(
        None,
        "--type",
        help="Filter by transaction type: credit or debit.",
    ),
    account_type: str | None = typer.Option(
        None,
        "--account-type",
        help="Filter by account type: bank or credit.",
    ),
    excludes: list[str] | None = typer.Option(
        None,
        "--excludes",
        help="Exclude transactions by category. Repeat option to add multiple categories.",
    ),
    limit: int = typer.Option(
        50,
        "--limit",
        "-n",
        help="Maximum number of transactions to display.",
    ),
    output_format: TransactionOutputFormat = typer.Option(
        TransactionOutputFormat.table,
        "--output",
        "-o",
        help="Output format: table, csv, or json.",
        case_sensitive=False,
    ),
) -> None:
    """
    List recent transactions for the connected Pluggy item and render them in the chosen format.

    Retrieves transactions for the specified item and applies optional filters (date range, transaction type, account type, excluded categories), limits the number of displayed rows, and outputs results as a table, CSV, or JSON. If no date range is provided, a default invoice-cycle range is derived from configuration.

    Parameters:
        item_id (str | None): Pluggy item ID; falls back to the PLUGGY_ITEM_ID environment/config value when omitted.
        date_from (str | None): Start date in ISO format `YYYY-MM-DD`. If omitted, a cycle-based default may be used.
        date_to (str | None): End date in ISO format `YYYY-MM-DD`. If omitted, a cycle-based default or today may be used.
        transaction_type (str | None): Filter by transaction type; accepted values are `credit` or `debit`.
        account_type (str | None): Filter by account type; accepted values are `bank` or `credit`.
        excludes (list[str] | None): Categories to exclude (case-insensitive). Repeat option to add multiple categories; merged with config exclusions.
        limit (int): Maximum number of transactions to display; must be greater than zero.
        output_format (TransactionOutputFormat): Output renderer to use: `table`, `csv`, or `json`. CSV/JSON outputs emit an empty structure when no rows match the filters.
    """
    user_passed_date_filter = date_from is not None or date_to is not None

    try:
        config = load_config()
        normalized_from = _validate_iso_date(date_from, "--from")
        normalized_to = _validate_iso_date(date_to, "--to")
        normalized_transaction_type = _normalize_transaction_type_filter(
            transaction_type
        )
        normalized_account_type = _normalize_account_type_filter(account_type)
        excluded_categories = _normalize_excluded_categories(
            list(config.credit_cards.excluded_categories),
            excludes or [],
        )
        if limit <= 0:
            raise ValueError("Option --limit must be a positive integer.")

        if normalized_from is None or normalized_to is None:
            cycle_from, cycle_to = _derive_invoice_cycle_date_range(
                int(config.credit_cards.invoice_due_day)
            )
            if normalized_from is None:
                normalized_from = cycle_from
            if normalized_to is None:
                normalized_to = cycle_to
    except (ConfigError, ValueError) as exc:
        _exit_with_error(exc)

    try:
        rows = pluggy.list_item_transactions_with_env(
            item_id,
            date_from=normalized_from,
            date_to=normalized_to,
            account_type_filter=normalized_account_type,
        )
    except pluggy.PluggyError as exc:
        _exit_with_error(exc)

    if normalized_transaction_type is not None:
        rows = [
            row
            for row in rows
            if row.type.strip().upper() == normalized_transaction_type
        ]

    if excluded_categories:
        rows = [
            row
            for row in rows
            if row.category is None
            or row.category.strip().casefold() not in excluded_categories
        ]

    if not rows:
        if output_format == TransactionOutputFormat.csv:
            _print_transaction_csv([])
            return
        if output_format == TransactionOutputFormat.json:
            _print_transaction_json([])
            return
        if user_passed_date_filter:
            from_label = normalized_from or "start"
            to_label = normalized_to or "today"
            typer.echo(f"No transactions found between {from_label} and {to_label}.")
        else:
            typer.echo("No transactions found for this Pluggy item.")
        return

    displayed_rows = rows[:limit]
    if output_format == TransactionOutputFormat.csv:
        _print_transaction_csv(displayed_rows)
        return
    if output_format == TransactionOutputFormat.json:
        _print_transaction_json(displayed_rows)
        return

    _print_transaction_table(displayed_rows)
    total_value = sum(
        (_signed_transaction_amount(row.amount, row.type) for row in displayed_rows),
        Decimal("0"),
    )
    typer.echo("")
    typer.echo(f"Showing {len(displayed_rows)} of {len(rows)} transactions.")
    if len(displayed_rows) < len(rows):
        typer.echo("Use --limit to show more.")
    typer.echo(f"TOTAL: {_format_total_amount(total_value)}")


@account_app.command("spending")
def account_spending(
    item_id: str | None = typer.Argument(
        None,
        help="Pluggy item ID. Falls back to PLUGGY_ITEM_ID if omitted.",
    ),
    date_from: str | None = typer.Option(
        None,
        "--from",
        "-f",
        help="Start date (YYYY-MM-DD). Defaults to first day of current month.",
    ),
    date_to: str | None = typer.Option(
        None,
        "--to",
        "-t",
        help="End date (YYYY-MM-DD). Defaults to today.",
    ),
    direction: str = typer.Option(
        "expense",
        "--direction",
        "-d",
        help="Filter direction: expense, income, or all.",
    ),
    account_type: str | None = typer.Option(
        None,
        "--type",
        help="Filter by account type: bank or credit.",
    ),
    top_n: int | None = typer.Option(
        None,
        "--top",
        help="Show only top N categories.",
    ),
) -> None:
    """Show spending breakdown by category."""
    try:
        config = load_config()
        normalized_from = _validate_iso_date(date_from, "--from")
        normalized_to = _validate_iso_date(date_to, "--to")
        normalized_direction = _normalize_spending_direction(direction)
        normalized_account_type = (
            account_type.strip().upper() if isinstance(account_type, str) else None
        )
        if normalized_account_type not in (None, "BANK", "CREDIT"):
            raise ValueError("Option --type must be either 'bank' or 'credit'.")
        if top_n is not None and top_n <= 0:
            raise ValueError("Option --top must be a positive integer.")

        default_from, default_to = _current_month_date_range()
        if normalized_from is None:
            normalized_from = default_from
        if normalized_to is None:
            normalized_to = default_to
    except (ConfigError, ValueError) as exc:
        _exit_with_error(exc)

    try:
        rows = pluggy.list_item_transactions_with_env(
            item_id,
            date_from=normalized_from,
            date_to=normalized_to,
            account_type_filter=normalized_account_type,
        )
    except pluggy.PluggyError as exc:
        _exit_with_error(exc)

    currency_code = str(config.currency)
    rows = [row for row in rows if row.currency_code.upper() == currency_code]
    if not rows:
        typer.echo("No transactions found for this period.")
        return

    summaries = pluggy.aggregate_by_category(rows, direction=normalized_direction)
    if not summaries:
        if normalized_direction == "expense":
            typer.echo("No expense transactions found for this period.")
        elif normalized_direction == "income":
            typer.echo("No income transactions found for this period.")
        else:
            typer.echo("No transactions found for this period.")
        return

    typer.echo(f"Spending summary ({normalized_from} to {normalized_to})")
    if normalized_direction == "expense":
        typer.echo("Direction: expenses")
    elif normalized_direction == "income":
        typer.echo("Direction: income")
    else:
        typer.echo("Direction: all (expenses negative, income positive)")
    typer.echo("")

    grand_total, total_count = _print_spending_table(
        summaries,
        currency_code=currency_code,
        direction=normalized_direction,
        top_n=top_n,
    )

    typer.echo("")
    typer.echo(
        "Total: "
        f"{_format_currency_amount_grouped(currency_code, grand_total, show_sign=normalized_direction == 'all')} "
        f"across {total_count} transactions"
    )
