from decimal import Decimal
from enum import Enum
from typing import NoReturn

import typer

from arcter import credentials, formatters, pluggy, validators
from arcter.config import ConfigError, load_config, set_user_config

account_app = typer.Typer(
    help="Manage external account integrations.",
    invoke_without_command=True,
)


@account_app.callback()
def account_callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(code=0)


class TransactionOutputFormat(str, Enum):
    table = "table"
    csv = "csv"
    json = "json"


def _exit_with_error(exc: Exception) -> NoReturn:
    typer.secho(str(exc), fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)


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

        assert client_id is not None
        assert client_secret is not None

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

    formatters.print_balance_table(rows)
    formatters.print_balance_totals(rows)


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
            formatters.format_currency_amount_grouped(row.currency_code, row.balance)
            if row.balance is not None
            else "N/A"
        )
        due_suffix = f"  (due: {row.balance_due_date})" if row.balance_due_date else ""
        typer.echo(f"  Balance:    {balance_value}{due_suffix}")

        if row.minimum_payment is not None:
            typer.echo(
                f"  Min. payment: {formatters.format_currency_amount_grouped(row.currency_code, row.minimum_payment)}"
            )

        if row.credit_limit is not None:
            credit_limit_line = (
                "  Credit limit: "
                f"{formatters.format_currency_amount_grouped(row.currency_code, row.credit_limit)}"
            )
            if row.available_credit_limit is not None:
                credit_limit_line += (
                    "  (available: "
                    f"{formatters.format_currency_amount_grouped(row.currency_code, row.available_credit_limit)})"
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
    typer.echo(
        f"  Goal:       {formatters.format_currency_amount(target_currency, goal)}"
    )
    typer.echo(
        f"  Current:    {formatters.format_currency_amount(target_currency, current_total)}  ({percentage}%)"
    )

    if current_total >= goal:
        surplus = current_total - goal
        typer.echo(
            f"  Surplus:    {formatters.format_currency_amount(target_currency, surplus)}"
        )
        typer.echo("  Goal reached!")
        return

    remaining = goal - current_total
    typer.echo(
        f"  Remaining:  {formatters.format_currency_amount(target_currency, remaining)}"
    )
    typer.echo(
        f"  Monthly salary: {formatters.format_currency_amount(target_currency, salary)}"
    )

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
    List recent transactions for connected accounts.
    """
    user_passed_date_filter = date_from is not None or date_to is not None

    try:
        config = load_config()
        normalized_from = validators.validate_iso_date(date_from, "--from")
        normalized_to = validators.validate_iso_date(date_to, "--to")
        normalized_transaction_type = validators.normalize_transaction_type_filter(
            transaction_type
        )
        normalized_account_type = validators.normalize_account_type_filter(account_type)
        excluded_categories = validators.normalize_excluded_categories(
            list(config.credit_cards.excluded_categories),
            excludes or [],
        )
        if limit <= 0:
            raise ValueError("Option --limit must be a positive integer.")

        if normalized_from is None or normalized_to is None:
            cycle_from, cycle_to = validators.derive_invoice_cycle_date_range(
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
            formatters.print_transaction_csv([])
            return
        if output_format == TransactionOutputFormat.json:
            formatters.print_transaction_json([])
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
        formatters.print_transaction_csv(displayed_rows)
        return
    if output_format == TransactionOutputFormat.json:
        formatters.print_transaction_json(displayed_rows)
        return

    formatters.print_transaction_table(displayed_rows)
    total_value = sum(
        (
            formatters.signed_transaction_amount(row.amount, row.type)
            for row in displayed_rows
        ),
        Decimal("0"),
    )
    typer.echo("")
    typer.echo(f"Showing {len(displayed_rows)} of {len(rows)} transactions.")
    if len(displayed_rows) < len(rows):
        typer.echo("Use --limit to show more.")
    typer.echo(f"TOTAL: {formatters.format_total_amount(total_value)}")


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
        normalized_from = validators.validate_iso_date(date_from, "--from")
        normalized_to = validators.validate_iso_date(date_to, "--to")
        normalized_direction = validators.normalize_spending_direction(direction)
        normalized_account_type = (
            account_type.strip().upper() if isinstance(account_type, str) else None
        )
        if normalized_account_type not in (None, "BANK", "CREDIT"):
            raise ValueError("Option --type must be either 'bank' or 'credit'.")
        if top_n is not None and top_n <= 0:
            raise ValueError("Option --top must be a positive integer.")

        default_from, default_to = validators.current_month_date_range()
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

    grand_total, total_count = formatters.print_spending_table(
        summaries,
        currency_code=currency_code,
        direction=normalized_direction,
        top_n=top_n,
    )

    typer.echo("")
    typer.echo(
        "Total: "
        f"{formatters.format_currency_amount_grouped(currency_code, grand_total, show_sign=normalized_direction == 'all')} "
        f"across {total_count} transactions"
    )
