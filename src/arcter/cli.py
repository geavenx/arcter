import typer

from arcter.commands.account import account_app
from arcter.commands.config import config_app
from arcter.constants import APP_NAME

app = typer.Typer(name=APP_NAME)
app.add_typer(config_app, name="config")
app.add_typer(account_app, name="account")
