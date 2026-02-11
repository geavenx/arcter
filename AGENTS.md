# Repository Guidelines

## Tooling — uv (mandatory)
- **Always** load the `uv-package-manager` skill before performing any package, dependency, environment, or project management operation.
- Use `uv` for **all** Python-related operations: dependency installation, virtual environment management, running scripts/commands, building, locking, and publishing.
- Never fall back to `pip`, `pip-tools`, `venv`, `poetry`, `pipenv`, or any other package/environment manager. `uv` is the single source of truth for this project.

## Project Structure & Module Organization
- `src/arcter/__init__.py`: empty package marker (no exports or `__version__`).
- `src/arcter/cli.py`: Typer CLI entrypoint, exposed via the `arcter` console script.
- `src/arcter/config.py`: configuration loading with three-layer merge precedence, Pydantic validation, TOML read/write, key normalization, and error handling.
- `src/arcter/constants.py`: app-level constants (`APP_NAME`, `APP_AUTHOR`) used for CLI naming and `platformdirs` config paths.
- `tests/test_config_cli.py`: integration tests for config CLI commands (6 tests using `typer.testing.CliRunner`).
- `dist/`: generated build artifacts (wheel/sdist); treat as output, not source.
- `.github/workflows/ci.yml`: CI pipeline (see CI/CD section below).

## CLI Commands
The CLI is structured as `arcter config <subcommand>`:

| Command | Arguments / Options | Purpose |
|---|---|---|
| `arcter config set <key> <value>` | `key`: `ConfigKey` enum (`salary`, `currency`), `value`: string | Set a config key in the user config file |
| `arcter config get <key>` | `key`: `ConfigKey` enum | Show one config value and its source |
| `arcter config unset <key>` | `key`: `ConfigKey` enum | Remove a key from the user config file |
| `arcter config list` | `--format`/`-f` (`table`\|`json`\|`toml`, default: `table`) | List all config values with sources |
| `arcter config path` | (none) | Print the config file path |

The `key` argument uses the `ConfigKey` enum, so Typer validates keys at parse time (exit code 2 for invalid keys).

## Configuration System
- **Config file location:** `platformdirs.user_config_dir("arcter", "Vitor Cardoso")` — resolves to `~/.config/arcter/config.toml` on Linux.
- **Merge precedence** (lowest to highest): Pydantic defaults → user config file → environment variables → CLI overrides.
- **Config fields:**
  - `salary`: `Decimal` (default `200.00`, 2 decimal places)
  - `currency`: `ISO4217` (default `BRL`, auto-uppercased, validated against ISO 4217)
- **Environment variables:** `ARCTER_SALARY`, `ARCTER_CURRENCY` — override file values when set.
- **Atomic writes:** `_write_toml` uses a `.tmp` + `Path.replace()` pattern for safe file updates.
- **Error hierarchy:** `ConfigError` → `ConfigFileError`, `UnknownConfigKeyError` (with fuzzy "did you mean?" suggestions), `ConfigValidationError`.

## Build, Test, and Development Commands
- `uv sync`: install and lock project dependencies into the local environment.
- `uv run arcter --help`: run the CLI entrypoint locally.
- `uv run arcter config list`: quick sanity check for config loading and command wiring.
- `uv run pytest`: run the test suite.
- `uv build`: build distribution artifacts into `dist/`.
- `uvx ruff format --check .`: check code formatting.
- `uvx ruff check .`: run linter.

## CI/CD
The GitHub Actions workflow (`.github/workflows/ci.yml`) triggers on pushes to `master` and all pull requests:
1. Checkout + install uv (with caching) + set up Python from `.python-version`
2. `uv sync --all-groups --frozen` — install all deps including dev
3. `uv run pytest` — run tests
4. `uvx ruff format --check .` — check formatting
5. `uvx ruff check .` — lint

## Coding Style & Naming Conventions
- Target Python `>=3.12`; use 4-space indentation and follow PEP 8.
- Use **ruff** for formatting and linting (enforced in CI via `uvx ruff`).
- Prefer explicit type hints for public functions and config-related code paths.
- Naming: modules/functions/variables in `snake_case`, classes in `PascalCase`, constants in `UPPER_SNAKE_CASE`.
- Keep environment variable names under the `ARCTER_` prefix (for example, `ARCTER_SALARY`, `ARCTER_CURRENCY`).

## Testing Guidelines
- Framework: `pytest` (already in dev dependencies).
- Tests live under `tests/` with names like `test_<behavior>.py`.
- Current tests cover: config set/list round-trip, unknown key rejection, corrupt TOML handling, env-var override source tracking, JSON/TOML output formats, and help text.
- Tests use `tmp_path` fixture with `XDG_CONFIG_HOME` override for filesystem isolation.
- Expand coverage for: config precedence edge cases, validation failures, and additional CLI subcommands (`get`, `unset`, `path`).

## Dependencies
**Runtime:** `platformdirs`, `pydantic`, `pydantic-extra-types`, `tomli-w`, `typer`, `pycountry` (declared but currently unused in source).

**Dev:** `pytest`.

## Commit & Pull Request Guidelines
- Use Conventional Commits (already established in the repo), for example:
  - `feat(cli): add config export command`
  - `fix(config): validate currency code before write`
  - `tests: add config CLI tests`
  - `ci: add test-format-lint workflow`
- PRs should include: purpose, key changes, verification commands run, and any user-visible CLI output changes.
