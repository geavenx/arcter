# Repository Guidelines

## Project Structure & Module Organization
- `src/arcter/cli.py`: Typer CLI entrypoint, exposed via the `arcter` console script.
- `src/arcter/config.py`: configuration loading, merge precedence, and Pydantic validation.
- `src/arcter/__init__.py`: package module marker.
- `dist/`: generated build artifacts (wheel/sdist); treat as output, not source.
- `tests/` is not present yet. Add tests there, mirroring the package layout (for example, `tests/test_config.py`).

## Build, Test, and Development Commands
- `uv sync`: install and lock project dependencies into the local environment.
- `uv run arcter --help`: run the CLI entrypoint locally.
- `uv run arcter config list`: quick sanity check for config loading and command wiring.
- `uv build`: build distribution artifacts into `dist/`.
- `uv run python -m arcter.cli`: run the CLI module directly during debugging.

## Coding Style & Naming Conventions
- Target Python `>=3.12`; use 4-space indentation and follow PEP 8.
- Prefer explicit type hints for public functions and config-related code paths.
- Naming: modules/functions/variables in `snake_case`, classes in `PascalCase`, constants in `UPPER_SNAKE_CASE`.
- Keep environment variable names under the `ARCTER_` prefix (for example, `ARCTER_SALARY`, `ARCTER_CURRENCY`).

## Testing Guidelines
- Current status: no committed test suite or coverage gate.
- Standardize on `pytest` for new tests and place them under `tests/` with names like `test_<behavior>.py`.
- Focus first on config precedence, validation failures, and CLI command behavior (`add`, `delete`, `list`).
- Run tests with `uv run pytest` once `pytest` is added to development dependencies.

## Commit & Pull Request Guidelines
- Repository currently has no commit history, so no existing convention to inherit.
- Use Conventional Commits going forward, for example:
  - `feat(cli): add config export command`
  - `fix(config): validate currency code before write`
- PRs should include: purpose, key changes, verification commands run, and any user-visible CLI output changes.
