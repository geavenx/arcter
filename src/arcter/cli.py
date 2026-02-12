import typer

from arcter.commands.account import account_app
from arcter.commands.config import config_app
from arcter.constants import APP_NAME

app = typer.Typer(name=APP_NAME, invoke_without_command=True)


@app.callback()
def root_callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(code=0)


app.add_typer(config_app, name="config")
app.add_typer(account_app, name="account")
