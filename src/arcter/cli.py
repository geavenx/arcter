from enum import Enum

import typer

from arcter.config import (
    ConfigError,
    ConfigKey,
    get_config_value,
    list_config_as_json,
    list_config_as_toml,
    list_config_values,
    set_user_config,
    unset_user_config,
    user_config_path,
)
from arcter.constants import APP_NAME

app = typer.Typer(name=APP_NAME)
config_app = typer.Typer(help="Manage CLI configuration values.")
app.add_typer(config_app, name="config")


class OutputFormat(str, Enum):
    table = "table"
    json = "json"
    toml = "toml"


def _exit_with_error(exc: Exception) -> None:
    typer.secho(str(exc), fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)


def _print_table(values: dict[str, str], sources: dict[str, str]) -> None:
    rows = [
        ("salary", values["salary"], sources["salary"]),
        ("currency", values["currency"], sources["currency"]),
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


@config_app.command("set")
def config_set(key: ConfigKey, value: str) -> None:
    """
    Set a persisted user configuration value.
    """
    try:
        normalized_key, normalized_value = set_user_config(key.value, value)
    except ConfigError as exc:
        _exit_with_error(exc)

    typer.echo(
        f"Set {normalized_key} = {normalized_value} (file: {user_config_path()})"
    )


@config_app.command("get")
def config_get(key: ConfigKey) -> None:
    """
    Show one effective configuration value and where it came from.
    """
    try:
        normalized_key, value, source = get_config_value(key.value)
    except ConfigError as exc:
        _exit_with_error(exc)

    typer.echo(f"{normalized_key} = {value} (source: {source})")


@config_app.command("unset")
def config_unset(key: ConfigKey) -> None:
    """
    Remove a persisted key from the user config file.
    """
    try:
        removed = unset_user_config(key.value)
    except ConfigError as exc:
        _exit_with_error(exc)

    if removed:
        typer.echo(f"Unset {key.value} from {user_config_path()}")
    else:
        typer.echo(f"Key '{key.value}' was not set in {user_config_path()}")


@config_app.command("list")
def config_list(
    output_format: OutputFormat = typer.Option(
        OutputFormat.table,
        "--format",
        "-f",
        help="Output format: table, json, or toml.",
        case_sensitive=False,
    ),
) -> None:
    """
    List effective configuration values.
    """
    try:
        if output_format == OutputFormat.json:
            typer.echo(list_config_as_json())
            return
        if output_format == OutputFormat.toml:
            typer.echo(list_config_as_toml())
            return

        values, sources = list_config_values()
        _print_table(values, sources)
    except ConfigError as exc:
        _exit_with_error(exc)


@config_app.command("path")
def config_path() -> None:
    """
    Print the absolute user config file path.
    """
    typer.echo(user_config_path())
