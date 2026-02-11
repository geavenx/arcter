# Repository Guidelines

## Tooling — uv (mandatory)
- **Always** load the `uv-package-manager` skill before performing any package, dependency, environment, or project management operation.
- Use `uv` for **all** Python-related operations: dependency installation, virtual environment management, running scripts/commands, building, locking, and publishing.
- Never fall back to `pip`, `pip-tools`, `venv`, `poetry`, `pipenv`, or any other package/environment manager. `uv` is the single source of truth for this project.

## Project Structure & Module Organization
- `src/arcter/__init__.py`: empty package marker (no exports or `__version__`).
- `src/arcter/cli.py`: Typer CLI entrypoint (894 lines), exposed via the `arcter` console script. Defines the root `app`, `config_app` subgroup, and `account_app` subgroup. Contains helper functions for table rendering, date validation, invoice cycle calculation, transaction formatting, and spending summary rendering.
- `src/arcter/config.py`: configuration loading (417 lines) with three-layer merge precedence, Pydantic validation, TOML read/write, key normalization, nested config support (`CreditCardsConfig`, `PluggyConfig`), and error handling.
- `src/arcter/constants.py`: app-level constants (`APP_NAME`, `APP_AUTHOR`) used for CLI naming and `platformdirs` config paths.
- `src/arcter/credentials.py`: thin `keyring` wrapper for Pluggy API credential storage (store, load, delete).
- `src/arcter/pluggy.py`: Pluggy API integration (686 lines) — authentication, item updates, balance retrieval, credit card details, account listing, transaction history, and category aggregation helpers. Includes credential/item resolution with environment, keyring, and config fallbacks. All HTTP calls go through a central `_request_json` helper with unified timeout/error handling and pagination support.
- `tests/test_config_cli.py`: integration tests for config CLI commands (12 tests using `typer.testing.CliRunner`). Covers set/list round-trip, unknown key rejection, corrupt TOML handling, env-var override source tracking, JSON/TOML output formats, help text, and credit_cards nested config.
- `tests/test_account_cli.py`: integration tests for account CLI commands (60 tests). Uses `monkeypatch` to stub `arcter.cli.pluggy.*` and `arcter.cli.credentials.*` functions. Covers login/logout, update, balance, goal, credit, transactions, and spending commands.
- `tests/test_credentials.py`: unit tests for the credentials module (8 tests). Uses `monkeypatch` to stub `keyring` API calls and error handling.
- `tests/test_pluggy.py`: unit tests for the Pluggy module (29 tests). Uses `monkeypatch` to stub `_request_json`. Covers balance filtering/parsing, credit card parsing, account listing, transaction pagination/parsing, category aggregation, env-based orchestrators, and credential/item-id fallback resolution.
- `prompts/`: feature specification documents used during development:
  - `01-savings-goal-progress.md`: spec for `arcter account goal` (implemented).
  - `02-credit-card-details.md`: spec for `arcter account credit` (implemented).
  - `03-transaction-history.md`: spec for `arcter account transactions` (implemented).
  - `04-spending-summary.md`: spec for `arcter account spending` (implemented).
  - `05-credential-storage.md`: spec for `arcter account login/logout` (implemented).
- `example_pluggy_integration.py`: standalone prototype script that predates the integrated `pluggy.py` module; uses `requests` + `python-dotenv`. Kept for reference only.
- `dist/`: generated build artifacts (wheel/sdist); treat as output, not source. Currently outdated (v0.1.0, predates most features).
- `build/`: stale build artifacts from a previous `python -m build` invocation. Out of date (predates `savings_goal`, Pluggy, credit cards, and transactions features). Safe to delete.
- `.github/workflows/ci.yml`: CI pipeline (see CI/CD section below).
- `.pre-commit-config.yaml`: pre-commit hooks for `uv-lock` and `ruff` (see Pre-commit Hooks section below).

## CLI Commands
The CLI is structured as `arcter <subgroup> <subcommand>`:

### `arcter config` subgroup

| Command | Arguments / Options | Purpose |
|---|---|---|
| `arcter config set <key> <value>` | `key`: `ConfigKey` enum, `value`: string | Set a config key in the user config file |
| `arcter config get <key>` | `key`: `ConfigKey` enum | Show one config value and its source |
| `arcter config unset <key>` | `key`: `ConfigKey` enum | Remove a key from the user config file |
| `arcter config list` | `--format`/`-f` (`table`\|`json`\|`toml`, default: `table`) | List all config values with sources |
| `arcter config path` | (none) | Print the config file path |

The `key` argument uses the `ConfigKey` enum (`salary`, `currency`, `savings_goal`, `credit_cards.invoice_due_day`, `credit_cards.excluded_categories`, `pluggy.item_id`), so Typer validates keys at parse time (exit code 2 for invalid keys).

### `arcter account` subgroup

| Command | Arguments / Options | Purpose |
|---|---|---|
| `arcter account update [ITEM_ID]` | `item_id`: optional string (falls back to `PLUGGY_ITEM_ID` env var) | Refresh a Pluggy item (triggers bank data sync) |
| `arcter account balance [ITEM_ID]` | `item_id`: optional string (falls back to `PLUGGY_ITEM_ID` env var) | Show BANK and CREDIT account balances with currency totals |
| `arcter account login` | `--client-id`: optional, `--client-secret`: optional, `--item-id`: optional | Store Pluggy API credentials in system keyring and optionally persist `pluggy.item_id` |
| `arcter account logout` | (none) | Remove Pluggy API credentials from system keyring |
| `arcter account credit [ITEM_ID]` | `item_id`: optional string (falls back to `PLUGGY_ITEM_ID` env var) | Show detailed credit card information (limits, due dates, minimum payments) |
| `arcter account goal [ITEM_ID]` | `item_id`: optional, `--currency`/`-c`: optional (defaults to config `currency`) | Show savings goal progress against BANK balances, with estimated months to reach the goal |
| `arcter account transactions [ITEM_ID]` | `item_id`: optional, `--from`/`-f` and `--to`/`-t`: YYYY-MM-DD dates, `--type`: CREDIT\|DEBIT, `--account-type`: BANK\|CREDIT, `--excludes`: category names (repeatable), `--limit`/`-n`: max rows | Show transaction history across accounts with filtering and category exclusion |
| `arcter account spending [ITEM_ID]` | `item_id`: optional, `--from`/`-f` and `--to`/`-t`: YYYY-MM-DD dates, `--direction`/`-d`: expense\|income\|all, `--type`: BANK\|CREDIT, `--top`: top N categories | Show category spending/income summary for the selected period |

## Configuration System
- **Config file location:** `platformdirs.user_config_dir("arcter", "Vitor Cardoso")` — resolves to `~/.config/arcter/config.toml` on Linux.
- **Merge precedence** (lowest to highest): Pydantic defaults -> user config file -> environment variables -> CLI overrides.
- **Config fields:**
  - `salary`: `Decimal` (default `200.00`, 2 decimal places)
  - `currency`: `ISO4217` (default `BRL`, auto-uppercased, validated against ISO 4217)
  - `savings_goal`: `Decimal` (default `500.00`, 2 decimal places)
  - `credit_cards`: nested `CreditCardsConfig` model:
    - `invoice_due_day`: `int` (default `30`, must be 1-31)
    - `excluded_categories`: `list[str]` (default `[]`, normalized via `casefold` for case-insensitive comparison)
  - `pluggy`: nested `PluggyConfig` model:
    - `item_id`: `str` (default `""`), the Pluggy item connection identifier
- **Environment variables (config):** `ARCTER_SALARY`, `ARCTER_CURRENCY`, `ARCTER_SAVINGS_GOAL`, `ARCTER_INVOICE_DUE_DAY`, `PLUGGY_ITEM_ID` — override file values when set.
- **Atomic writes:** `_write_toml` uses a `.tmp` + `Path.replace()` pattern for safe file updates.
- **Error hierarchy:** `ConfigError` -> `ConfigFileError`, `UnknownConfigKeyError` (with fuzzy "did you mean?" suggestions), `ConfigValidationError`.

## Pluggy Integration
- **Module:** `src/arcter/pluggy.py` — communicates with the Pluggy API (`https://api.pluggy.ai`).
- **Credential storage and resolution:**
  - `PLUGGY_CLIENT_ID` / `PLUGGY_CLIENT_SECRET` env vars (highest priority)
  - OS keyring (`src/arcter/credentials.py`) fallback
  - Missing credentials raise `PluggyError` with guidance to run `arcter account login`
- **Item ID resolution:** CLI arg -> `PLUGGY_ITEM_ID` env var -> `pluggy.item_id` in config -> error.
- **Data models** (all `frozen=True, slots=True` dataclasses):
  - `BalanceRow`: `type`, `name`, `balance` (`Decimal | None`), `currency_code`.
  - `CreditCardRow`: `name`, `number`, `balance`, `currency_code`, `credit_limit`, `available_credit_limit`, `balance_due_date`, `minimum_payment`, `brand`, `level`, `status`, `holder_type` (12 fields).
  - `TransactionRow`: `date`, `description`, `amount`, `currency_code`, `type`, `status`, `category`, `account_name`, `account_type` (9 fields).
  - `CategorySummary`: `category`, `total`, `count`, `percentage` (4 fields) for spending reports.
- **Error handling:** `PluggyError` exception for all API failures (auth, HTTP errors, timeouts, malformed responses).
- **HTTP client:** `httpx` with a configurable timeout (`DEFAULT_TIMEOUT_SECONDS = 15.0`).
- **Key functions:**
  - `authenticate()`, `update_item()` — auth and item refresh.
  - `list_item_balances()` — GET /accounts, filters BANK+CREDIT types.
  - `list_item_credit_cards()` — GET /accounts, filters CREDIT, parses `creditData`.
  - `list_item_accounts()` — GET /accounts, returns id/name/type dicts.
  - `list_account_transactions()` — GET /transactions with pagination support.
  - `_parse_transactions()` — converts raw API dicts to `TransactionRow` objects.
  - `aggregate_by_category()` — pure in-memory grouping/filtering helper for spending summaries.
  - Orchestrators: `update_item_with_env()`, `list_item_balances_with_env()`, `list_item_credit_cards_with_env()`, `list_item_transactions_with_env()` — handle credential resolution and auth in one call.

## Build, Test, and Development Commands
- `uv sync`: install and lock project dependencies into the local environment.
- `uv run arcter --help`: run the CLI entrypoint locally.
- `uv run arcter config list`: quick sanity check for config loading and command wiring.
- `uv run arcter account balance`: quick sanity check for Pluggy integration (requires `.env` credentials).
- `uv run pytest`: run the test suite (109 tests across 4 files).
- `uv build`: build distribution artifacts into `dist/`.
- `uvx ruff format --check .`: check code formatting.
- `uvx ruff check .`: run linter.

## Pre-commit Hooks
Configured in `.pre-commit-config.yaml`:
- `uv-lock` (astral-sh/uv-pre-commit v0.10.2) — ensures the lockfile stays in sync with `pyproject.toml`.
- `ruff-check --fix` + `ruff-format` (astral-sh/ruff-pre-commit v0.15.0) — auto-fixes lint issues and formats code on commit.

## CI/CD
The GitHub Actions workflow (`.github/workflows/ci.yml`) triggers on pushes to `master` and all pull requests:
1. Checkout + install uv (with caching) + set up Python from `.python-version`
2. `uv sync --all-groups --frozen` — install all deps including dev
3. `uv run pytest` — run tests
4. `uvx ruff format --check .` — check formatting
5. `uvx ruff check .` — lint

## Coding Style & Naming Conventions
- Target Python `>=3.12`; use 4-space indentation and follow PEP 8.
- Use **ruff** for formatting and linting (enforced in CI via `uvx ruff` and pre-commit hooks).
- Prefer explicit type hints for public functions and config-related code paths.
- Naming: modules/functions/variables in `snake_case`, classes in `PascalCase`, constants in `UPPER_SNAKE_CASE`.
- Keep environment variable names under the `ARCTER_` prefix for config (e.g., `ARCTER_SALARY`, `ARCTER_CURRENCY`, `ARCTER_SAVINGS_GOAL`, `ARCTER_INVOICE_DUE_DAY`) and `PLUGGY_` prefix for Pluggy API credentials.

## Testing Guidelines
- Framework: `pytest` (already in dev dependencies).
- Tests live under `tests/` with names like `test_<behavior>.py`.
- **`test_config_cli.py`** (12 tests): config set/list round-trip, unknown key rejection, corrupt TOML handling, env-var override source tracking, JSON/TOML output formats, help text, and credit_cards nested config (invoice_due_day, excluded_categories).
- **`test_account_cli.py`** (60 tests): account login/logout, update, balance, goal, credit, transactions, and spending commands — happy paths, env-var/keyring/config fallback behavior, credential/item-id validation errors, HTTP error propagation, timeout handling, date filtering/defaults, transaction type/account type filtering, category exclusion (config + CLI), top-N limits, and edge cases (no accounts, nil balances, zero salary).
- **`test_credentials.py`** (8 tests): keyring store/load/delete behavior, empty/missing value handling, and `CredentialError` wrapping.
- **`test_pluggy.py`** (29 tests): balance filtering/parsing, invalid payload handling, env/keyring credential resolution, arg/env/config item-id resolution, credit card data parsing (including missing/non-dict creditData), account listing, transaction pagination, transaction field extraction, category aggregation math, unparseable amounts, missing fields, and account-type filtering in orchestrators.
- Tests use `tmp_path` fixture with `XDG_CONFIG_HOME` override for filesystem isolation.
- Tests use `monkeypatch` to stub `arcter.cli.pluggy.*` functions (account tests) and `_request_json` (pluggy unit tests).

## Dependencies
**Runtime:** `httpx` (>=0.28.1), `keyring` (>=25.0.0), `platformdirs` (>=4.5.1), `pydantic` (>=2.12.5), `pydantic-extra-types` (>=2.11.0), `tomli-w` (>=1.2.0), `typer` (>=0.23.0), `pycountry` (>=24.6.1, declared but currently unused in source).

**Dev:** `pytest` (>=8.4.0).

## Known Issues
- **`pycountry` unused:** declared as a runtime dependency in `pyproject.toml` but not imported anywhere in the source code. Consider removing or using it.
- **Stale `build/` directory:** contains outdated code from before the `savings_goal`, Pluggy, credit cards, and transactions features. Safe to delete.
- **Stale `dist/` artifacts:** the wheel and sdist in `dist/` are v0.1.0 and predate most features. They will be regenerated on `uv build`.
- **Placeholder project description:** `pyproject.toml` still has `description = "Add your description here"`.
- **No `[build-system]` table:** `pyproject.toml` relies on uv defaults (`[tool.uv] package = true`) without an explicit `[build-system]` declaration.

## Commit & Pull Request Guidelines
- Use Conventional Commits (already established in the repo), for example:
  - `feat(cli): add config export command`
  - `feat(account): add balance command`
  - `fix(config): validate currency code before write`
  - `tests: add config CLI tests`
  - `ci: add test-format-lint workflow`
- PRs should include: purpose, key changes, verification commands run, and any user-visible CLI output changes.
