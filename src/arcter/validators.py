import calendar
import datetime
from datetime import date


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
