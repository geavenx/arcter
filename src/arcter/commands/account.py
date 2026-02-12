from decimal import Decimal
from enum import Enum
from typing import NoReturn

import typer

from arcter import credentials, formatters, pluggy, validators
from arcter.config import Config, ConfigError, load_config, set_user_config

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


def _salary_filter_parts(config: Config) -> tuple[str, list[str]]:
    category_filter = config.account.salary_filters.category.strip()
    amount_filters = list(config.account.salary_filters.amount)
    return category_filter, amount_filters


def _salary_filters_configured(config: Config) -> bool:
    category_filter, amount_filters = _salary_filter_parts(config)
    return bool(category_filter) or bool(amount_filters)


def _filter_salary_transactions(
    rows: list[pluggy.TransactionRow],
    config: Config,
) -> list[pluggy.TransactionRow]:
    category_filter, amount_filters = _salary_filter_parts(config)
    normalized_category_filter = category_filter.casefold()

    filtered_rows: list[pluggy.TransactionRow] = []
    for row in rows:
        row_category = (
            row.category.strip().casefold()
            if isinstance(row.category, str) and row.category.strip()
            else ""
        )
        if normalized_category_filter and row_category != normalized_category_filter:
            continue

        if amount_filters and not all(
            validators.matches_salary_amount_filter(row.amount, expression)
            for expression in amount_filters
        ):
            continue

        filtered_rows.append(row)

    return filtered_rows


def _set_salary_from_transaction(
    transaction: pluggy.TransactionRow,
    announce: bool = True,
) -> str:
    normalized_amount = abs(transaction.amount).quantize(Decimal("0.01"))
    _, rendered_salary = set_user_config("salary", str(normalized_amount))
    if announce:
        typer.echo(f"Set salary = {rendered_salary}")
    return rendered_salary


def _print_salary_transaction_options(rows: list[pluggy.TransactionRow]) -> None:
    for index, row in enumerate(rows, start=1):
        amount_label = formatters.format_currency_amount_grouped(
            row.currency_code, abs(row.amount)
        )
        category_label = row.category if row.category else "Uncategorized"
        typer.echo(
            f"{index}. {row.date} | {amount_label} | {row.account_name} | "
            f"{category_label} | {row.description}"
        )


def _prompt_salary_transaction_choice(
    rows: list[pluggy.TransactionRow],
    title: str,
) -> pluggy.TransactionRow | None:
    typer.echo(title)
    typer.echo("")
    _print_salary_transaction_options(rows)
    typer.echo("")
    typer.echo("Type the transaction number to set salary, or press Enter to cancel.")

    while True:
        selected = typer.prompt("Selection", default="", show_default=False).strip()
        if not selected:
            return None

        try:
            selected_index = int(selected)
        except ValueError:
            typer.secho(
                "Invalid selection. Enter a number from the list, or press Enter to cancel.",
                fg=typer.colors.YELLOW,
            )
            continue

        if 1 <= selected_index <= len(rows):
            return rows[selected_index - 1]

        typer.secho(
            "Invalid selection. Enter a number from the list, or press Enter to cancel.",
            fg=typer.colors.YELLOW,
        )


def _print_salary_filter_debug_tips(config: Config) -> None:
    category_filter, amount_filters = _salary_filter_parts(config)

    typer.secho(
        "No transaction matched the configured salary filters.",
        fg=typer.colors.YELLOW,
    )
    typer.echo("Configured filters:")
    typer.echo(f"- account.salary_filters.category: {category_filter or '<not set>'}")
    typer.echo(
        f"- account.salary_filters.amount: {amount_filters if amount_filters else '<not set>'}"
    )
    typer.echo("")
    typer.echo("Tips:")
    typer.echo(
        '- Use `arcter config set account.salary_filters.category "Transfer"` '
        "to match one category."
    )
    typer.echo(
        '- Add amount filters like `arcter config set account.salary_filters.amount ">=4300"` '
        'and `arcter config set account.salary_filters.amount "<=4380"`.'
    )
    typer.echo(
        "- You can inspect this period with `arcter account transactions --output json`."
    )


def _sync_salary_silently_if_single_match(
    rows: list[pluggy.TransactionRow],
    config: Config,
) -> None:
    if not _salary_filters_configured(config):
        return

    candidates = _filter_salary_transactions(rows, config)
    if len(candidates) != 1:
        return

    _set_salary_from_transaction(candidates[0], announce=False)


def _sync_salary_with_filters(item_id: str | None, config: Config) -> None:
    current_month_from, current_month_to = validators.current_month_date_range()
    current_rows = pluggy.list_item_transactions_with_env(
        item_id,
        date_from=current_month_from,
        date_to=current_month_to,
    )

    current_candidates = _filter_salary_transactions(current_rows, config)
    if len(current_candidates) == 1:
        _set_salary_from_transaction(current_candidates[0], announce=True)
        return

    if len(current_candidates) > 1:
        selected = _prompt_salary_transaction_choice(
            current_candidates,
            "Multiple transactions matched salary filters. Choose one:",
        )
        if selected is None:
            typer.echo("Salary sync cancelled.")
            return

        _set_salary_from_transaction(selected, announce=True)
        return

    previous_month_from, previous_month_to = validators.previous_month_date_range()
    previous_rows = pluggy.list_item_transactions_with_env(
        item_id,
        date_from=previous_month_from,
        date_to=previous_month_to,
    )
    previous_candidates = _filter_salary_transactions(previous_rows, config)
    if len(previous_candidates) == 1:
        typer.echo(
            f"No salary match found for {current_month_from} to {current_month_to}. "
            f"Using last month match ({previous_month_from} to {previous_month_to})."
        )
        _set_salary_from_transaction(previous_candidates[0], announce=True)
        return

    if len(previous_candidates) > 1:
        selected = _prompt_salary_transaction_choice(
            previous_candidates,
            "No current-month salary match. Multiple last-month matches found. Choose one:",
        )
        if selected is None:
            typer.echo("Salary sync cancelled.")
            return

        _set_salary_from_transaction(selected, announce=True)
        return

    _print_salary_filter_debug_tips(config)
    typer.echo("")

    if not current_rows:
        if previous_rows:
            fallback_selection = _prompt_salary_transaction_choice(
                previous_rows,
                "No transactions found in the current month. Select one from last month to set salary:",
            )
            if fallback_selection is None:
                typer.echo("Salary sync cancelled.")
                return

            _set_salary_from_transaction(fallback_selection, announce=True)
            return

        typer.echo("No transactions found in the current month or last month.")
        return

    fallback_selection = _prompt_salary_transaction_choice(
        current_rows,
        "Select a transaction from the current month to set salary:",
    )
    if fallback_selection is None:
        typer.echo("Salary sync cancelled.")
        return

    _set_salary_from_transaction(fallback_selection, announce=True)


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


@account_app.command("salary")
def account_salary(
    item_id: str | None = typer.Argument(
        None,
        help="Pluggy item ID. Falls back to PLUGGY_ITEM_ID if omitted.",
    ),
    sync: bool = typer.Option(
        False,
        "--sync",
        help="Sync salary from Pluggy transactions using configured salary filters.",
    ),
    set_amount: str | None = typer.Option(
        None,
        "--set",
        help="Set salary manually.",
    ),
) -> None:
    """Manage salary configuration."""
    if sync and set_amount is not None:
        typer.secho(
            "Options --sync and --set are mutually exclusive.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    if not sync and set_amount is None:
        typer.secho(
            "Provide one of --sync or --set.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    if set_amount is not None:
        try:
            _normalized_key, rendered_salary = set_user_config("salary", set_amount)
        except ConfigError as exc:
            _exit_with_error(exc)

        typer.echo(f"Set salary = {rendered_salary}")
        return

    try:
        config = load_config()
        _sync_salary_with_filters(item_id, config)
    except (ConfigError, pluggy.PluggyError) as exc:
        _exit_with_error(exc)


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

    try:
        _sync_salary_silently_if_single_match(rows, config)
    except (ConfigError, ValueError):
        pass

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
