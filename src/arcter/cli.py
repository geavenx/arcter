import typer

from arcter.config import add_user_config, delete_user_config, list_configs

APP_NAME = "arcter"
APP_AUTHOR = "Vitor Cardoso"

app = typer.Typer(name=APP_NAME)
config_app = typer.Typer()
app.add_typer(config_app, name="config")

@config_app.command("add")
def config_add(
    key: str,
    value: str
):
    """
    Add or update a user config value.
    """

    add_user_config(key, value)
    typer.echo(f"Set {key} = {value}")

@config_app.command("delete")
def config_delete(key: str):
    """
    Delete a user config value.
    """
    delete_user_config(key)
    typer.echo(f"Deleted config: {key}")

@config_app.command("list")
def config_list():
    """
    List current arcter configuration.
    """
    config = list_configs()

    typer.echo("Current configuration:")
    typer.echo(f"Salary = {config.salary}")
    typer.echo(f"Currency = {config.currecy}")
