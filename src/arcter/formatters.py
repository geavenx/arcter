import csv
import json
import sys
from decimal import Decimal

import typer

from arcter.pluggy import BalanceRow, CategorySummary, TransactionRow


def print_table(values: dict[str, str], sources: dict[str, str]) -> None:
    rows = [
        ("currency", values["currency"], sources["currency"]),
        ("salary", values["salary"], sources["salary"]),
        ("savings_goal", values["savings_goal"], sources["savings_goal"]),
        (
            "account.salary_filters.category",
            values["account.salary_filters.category"],
            sources["account.salary_filters.category"],
        ),
        (
            "account.salary_filters.amount",
            values["account.salary_filters.amount"],
            sources["account.salary_filters.amount"],
        ),
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


def format_balance_value(value: Decimal | None) -> str:
    if value is None:
        return "N/A"
    return str(value.quantize(Decimal("0.01")))


def format_currency_amount(currency_code: str, value: Decimal) -> str:
    return f"{currency_code} {value.quantize(Decimal('0.01'))}"


def format_currency_amount_grouped(
    currency_code: str,
    value: Decimal,
    show_sign: bool = False,
) -> str:
    quantized = value.quantize(Decimal("0.01"))
    if show_sign:
        return f"{currency_code} {quantized:+,.2f}"
    return f"{currency_code} {quantized:,.2f}"


def truncate_text(value: str, max_length: int = 20) -> str:
    if len(value) <= max_length:
        return value
    return f"{value[: max_length - 3]}..."


def format_transaction_amount(amount: Decimal, transaction_type: str) -> str:
    sign = "+" if transaction_type == "CREDIT" else "-"
    quantized = abs(amount).quantize(Decimal("0.01"))
    return f"{sign}{quantized:,.2f}"


def signed_transaction_amount(amount: Decimal, transaction_type: str) -> Decimal:
    if transaction_type.strip().upper() == "CREDIT":
        return abs(amount)
    return -abs(amount)


def format_total_amount(value: Decimal) -> str:
    sign = "+" if value >= 0 else "-"
    quantized = abs(value).quantize(Decimal("0.01"))
    return f"{sign}{quantized:,.2f}"


def print_transaction_table(rows: list[TransactionRow]) -> None:
    table_rows = [
        (
            row.date,
            truncate_text(row.account_name.strip() or "Unnamed account"),
            row.type,
            format_transaction_amount(row.amount, row.type),
            row.currency_code,
            truncate_text(row.category or ""),
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


def print_transaction_csv(rows: list[TransactionRow]) -> None:
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


def print_transaction_json(rows: list[TransactionRow]) -> None:
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


def print_spending_table(
    rows: list[CategorySummary],
    currency_code: str,
    direction: str,
    top_n: int | None = None,
) -> tuple[Decimal, int]:
    display_rows = rows[:top_n] if top_n is not None else rows
    show_sign = direction == "all"

    table_rows = [
        (
            truncate_text(row.category),
            format_currency_amount_grouped(
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


def print_balance_table(rows: list[BalanceRow]) -> None:
    table_rows = [
        (row.type, row.name, format_balance_value(row.balance), row.currency_code)
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


def print_balance_totals(rows: list[BalanceRow]) -> None:
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
        typer.echo(f"- {currency_code}: {format_balance_value(total)}")
