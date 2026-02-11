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
from arcter import pluggy

app = typer.Typer(name=APP_NAME)
config_app = typer.Typer(help="Manage CLI configuration values.")
account_app = typer.Typer(help="Manage external account integrations.")
app.add_typer(config_app, name="config")
app.add_typer(account_app, name="account")


class OutputFormat(str, Enum):
    table = "table"
    json = "json"
    toml = "toml"


def _exit_with_error(exc: Exception) -> None:
    typer.secho(str(exc), fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)


def _print_table(values: dict[str, str], sources: dict[str, str]) -> None:
    rows = [
        ("currency", values["currency"], sources["currency"]),
        ("salary", values["salary"], sources["salary"]),
        ("savings_goal", values["savings_goal"], sources["savings_goal"]),
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


def _format_currency_amount_grouped(currency_code: str, value: Decimal) -> str:
    quantized = value.quantize(Decimal("0.01"))
    return f"{currency_code} {quantized:,.2f}"


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
