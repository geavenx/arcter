import calendar
import datetime
from datetime import date
from decimal import Decimal, InvalidOperation
import re


def validate_iso_date(value: str | None, option_name: str) -> str | None:
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


def normalize_account_type_filter(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip().upper()
    if normalized not in ("BANK", "CREDIT"):
        raise ValueError("Option --account-type must be either 'bank' or 'credit'.")

    return normalized


def normalize_transaction_type_filter(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip().upper()
    if normalized not in ("CREDIT", "DEBIT"):
        raise ValueError("Option --type must be either 'credit' or 'debit'.")

    return normalized


def normalize_spending_direction(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in ("expense", "income", "all"):
        raise ValueError("Option --direction must be one of: expense, income, all.")
    return normalized


def normalize_excluded_categories(
    config_categories: list[str],
    cli_categories: list[str],
) -> set[str]:
    normalized_categories: set[str] = set()

    for value in [*config_categories, *cli_categories]:
        normalized = value.strip()
        if normalized:
            normalized_categories.add(normalized.casefold())

    return normalized_categories


def derive_invoice_cycle_date_range(
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


def current_month_date_range(
    today: datetime.date | None = None,
) -> tuple[str, str]:
    current = today or datetime.date.today()
    return current.replace(day=1).isoformat(), current.isoformat()


_SALARY_AMOUNT_FILTER_PATTERN = re.compile(
    r"^(?:(>=|<=|>|<|=)\s*)?([+-]?\d+(?:\.\d+)?)$"
)


def parse_salary_amount_filter_expression(expression: str) -> tuple[str, Decimal, bool]:
    normalized = expression.strip()
    if not normalized:
        raise ValueError("Salary amount filter expression cannot be empty.")

    match = _SALARY_AMOUNT_FILTER_PATTERN.match(normalized)
    if match is None:
        raise ValueError(
            "Invalid salary amount filter expression. "
            "Use one of: >=4300, <=4380, =4322.50, or 4322."
        )

    operator = match.group(1) or ""
    raw_amount = match.group(2)
    try:
        amount = Decimal(raw_amount)
    except InvalidOperation as exc:
        raise ValueError(
            "Invalid salary amount filter expression. "
            "Use one of: >=4300, <=4380, =4322.50, or 4322."
        ) from exc

    return operator, amount, operator == ""


def _format_decimal_compact(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in {"", "-0"}:
        return "0"
    return text


def normalize_salary_amount_filter_expression(expression: str) -> str:
    operator, amount, is_plain = parse_salary_amount_filter_expression(expression)
    compact_amount = _format_decimal_compact(amount)
    if is_plain:
        return compact_amount
    return f"{operator}{compact_amount}"


def matches_salary_amount_filter(amount: Decimal, expression: str) -> bool:
    operator, target, is_plain = parse_salary_amount_filter_expression(expression)
    normalized_amount = abs(amount)
    normalized_target = abs(target)

    if operator == ">=":
        return normalized_amount >= normalized_target
    if operator == "<=":
        return normalized_amount <= normalized_target
    if operator == ">":
        return normalized_amount > normalized_target
    if operator == "<":
        return normalized_amount < normalized_target
    if operator == "=":
        return normalized_amount == normalized_target

    if is_plain and normalized_target == normalized_target.to_integral_value():
        return normalized_target <= normalized_amount < normalized_target + Decimal("1")

    return normalized_amount == normalized_target
