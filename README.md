# Arcter

A personal finance CLI that connects to Brazilian bank accounts via the [Pluggy](https://pluggy.ai) API to track balances, credit cards, savings goals, and transactions.

[![CI](https://github.com/geavenx/arcter/actions/workflows/ci.yml/badge.svg)](https://github.com/geavenx/arcter/actions/workflows/ci.yml)

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
arcter config list
```

### Account commands

All `arcter account` commands accept an optional `ITEM_ID` argument. If omitted, Arcter reads `PLUGGY_ITEM_ID` from the environment.

You also need `PLUGGY_CLIENT_ID` and `PLUGGY_CLIENT_SECRET` set in your environment.

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

**Pluggy integration** authenticates with the Pluggy API, then fetches account data (balances, credit card details, transactions) through a central HTTP client with unified error handling. Transaction listing supports server-side pagination and client-side filtering by date range, transaction type, account type, and category exclusions. When no date range is given, Arcter derives one from the configured invoice cycle.

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
