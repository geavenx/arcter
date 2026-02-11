# Arcter

A personal finance CLI that connects to Brazilian bank accounts via the [Pluggy](https://pluggy.ai) API to track balances, credit cards, savings goals, transactions, and spending summaries by category.

[![CI](https://github.com/geavenx/arcter/actions/workflows/ci.yml/badge.svg)](https://github.com/geavenx/arcter/actions/workflows/ci.yml)

## Features

- Configuration with layered precedence (defaults -> file -> env -> CLI)
- Pluggy account sync (`update`) and unified balance view (`balance`)
- Credit card details (`credit`) and savings goal tracking (`goal`)
- Transaction listing with date/account/type/category filters (`transactions`)
- Spending breakdown by category with direction/date/top filters (`spending`)
- Secure Pluggy credential storage via OS keyring (`login` / `logout`)

## Installation

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/geavenx/arcter.git
cd arcter
uv sync
```

## Usage

### Configuration

Arcter stores settings in `~/.config/arcter/config.toml`. Manage them with `arcter config`:

```bash
arcter config set salary 5000
arcter config set currency BRL
arcter config set savings_goal 25000
arcter config set pluggy.item_id your-item-id
arcter config list
```

### Pluggy credentials and item ID

Store credentials securely in your system keyring:

```bash
arcter account login --client-id your-client-id --client-secret your-client-secret
arcter account login --item-id your-item-id  # optional: also persists pluggy.item_id
```

Or remove stored credentials:

```bash
arcter account logout
```

Resolution precedence:

| Value | Highest -> Lowest |
|---|---|
| Item ID | CLI argument -> `PLUGGY_ITEM_ID` env var -> `pluggy.item_id` in config |
| Client ID / Secret | `PLUGGY_CLIENT_ID`/`PLUGGY_CLIENT_SECRET` env vars -> OS keyring |

Environment variables always override stored values.

### Account commands

```bash
# Refresh bank data
arcter account update

# Show balances across BANK and CREDIT accounts
arcter account balance

# Show credit card details (limits, due dates, minimum payments)
arcter account credit

# Track savings goal progress
arcter account goal

# List recent transactions with filtering
arcter account transactions --from 2025-01-01 --to 2025-01-31
arcter account transactions --type debit --account-type bank
arcter account transactions --excludes "Transfer" --limit 20

# Summarize spending by category
arcter account spending --from 2025-01-01 --to 2025-01-31
arcter account spending --direction income
arcter account spending --type credit --top 5
```

## How It Works

Arcter has two core subsystems:

**Configuration** merges values from four layers (lowest to highest priority): Arcter defaults, the TOML config file, environment variables (`ARCTER_*`), and CLI flags. This lets you set once and override per-session without editing files.

Default values:

| Key | Default | Environment variable |
|-----|---------|----------------------|
| `currency` | `BRL` | `ARCTER_CURRENCY` |
| `salary` | `200.00` | `ARCTER_SALARY` |
| `savings_goal` | `500.00` | `ARCTER_SAVINGS_GOAL` |
| `credit_cards.invoice_due_day` | `30` | `ARCTER_INVOICE_DUE_DAY` |
| `credit_cards.excluded_categories` | `[]` | — |
| `pluggy.item_id` | `""` | `PLUGGY_ITEM_ID` |

**Pluggy integration** authenticates with the Pluggy API, then fetches account data (balances, credit card details, transactions) through a central HTTP client with unified error handling. Transaction listing supports server-side pagination and client-side filtering by date range, transaction type, account type, and category exclusions. Spending summaries reuse the same transaction layer and aggregate totals by Pluggy category (`expense`, `income`, or `all`) with optional top-N output. When no date range is given, spending defaults to first day of the current month through today, while transaction listing derives dates from the configured invoice cycle.

## Contributing

```bash
git clone https://github.com/geavenx/arcter.git
cd arcter
uv sync
```

Run the test suite:

```bash
uv run pytest
```

Check formatting and lint:

```bash
uvx ruff format --check .
uvx ruff check .
```

The CI pipeline runs all three on every push and pull request.

Last reviewed: 2026-02-11
