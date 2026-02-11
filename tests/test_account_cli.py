from pathlib import Path

from typer.testing import CliRunner

from arcter.cli import app
from arcter.pluggy import PluggyError

runner = CliRunner()


def _env(tmp_path: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {"XDG_CONFIG_HOME": str(tmp_path)}
    if extra:
        env.update(extra)
    return env


def test_account_update_succeeds_with_item_id_argument(
    tmp_path: Path, monkeypatch
) -> None:
    observed: dict[str, str] = {}

    def fake_authenticate(client_id: str, client_secret: str) -> str:
        observed["client_id"] = client_id
        observed["client_secret"] = client_secret
        return "api-key"

    def fake_update_item(item_id: str, api_key: str) -> None:
        observed["item_id"] = item_id
        observed["api_key"] = api_key

    monkeypatch.setattr("arcter.cli.pluggy.authenticate", fake_authenticate)
    monkeypatch.setattr("arcter.cli.pluggy.update_item", fake_update_item)

    result = runner.invoke(
        app,
        ["account", "update", "item-from-arg"],
        env=_env(
            tmp_path,
            {
                "PLUGGY_CLIENT_ID": "client-id",
                "PLUGGY_CLIENT_SECRET": "client-secret",
            },
        ),
    )

    assert result.exit_code == 0
    assert "Updated Pluggy item item-from-arg." in result.stdout
    assert observed == {
        "client_id": "client-id",
        "client_secret": "client-secret",
        "item_id": "item-from-arg",
        "api_key": "api-key",
    }


def test_account_update_reads_item_id_from_environment_when_arg_is_missing(
    tmp_path: Path, monkeypatch
) -> None:
    observed: dict[str, str] = {}

    def fake_authenticate(client_id: str, client_secret: str) -> str:
        observed["client_id"] = client_id
        observed["client_secret"] = client_secret
        return "api-key"

    def fake_update_item(item_id: str, api_key: str) -> None:
        observed["item_id"] = item_id
        observed["api_key"] = api_key

    monkeypatch.setattr("arcter.cli.pluggy.authenticate", fake_authenticate)
    monkeypatch.setattr("arcter.cli.pluggy.update_item", fake_update_item)

    result = runner.invoke(
        app,
        ["account", "update"],
        env=_env(
            tmp_path,
            {
                "PLUGGY_CLIENT_ID": "client-id",
                "PLUGGY_CLIENT_SECRET": "client-secret",
                "PLUGGY_ITEM_ID": "item-from-env",
            },
        ),
    )

    assert result.exit_code == 0
    assert "Updated Pluggy item item-from-env." in result.stdout
    assert observed["item_id"] == "item-from-env"


def test_account_update_prefers_argument_item_id_over_environment(
    tmp_path: Path, monkeypatch
) -> None:
    observed: dict[str, str] = {}

    def fake_authenticate(_: str, __: str) -> str:
        return "api-key"

    def fake_update_item(item_id: str, _: str) -> None:
        observed["item_id"] = item_id

    monkeypatch.setattr("arcter.cli.pluggy.authenticate", fake_authenticate)
    monkeypatch.setattr("arcter.cli.pluggy.update_item", fake_update_item)

    result = runner.invoke(
        app,
        ["account", "update", "item-from-arg"],
        env=_env(
            tmp_path,
            {
                "PLUGGY_CLIENT_ID": "client-id",
                "PLUGGY_CLIENT_SECRET": "client-secret",
                "PLUGGY_ITEM_ID": "item-from-env",
            },
        ),
    )

    assert result.exit_code == 0
    assert observed["item_id"] == "item-from-arg"


def test_account_update_fails_when_credentials_are_missing(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["account", "update", "item-id"],
        env=_env(tmp_path),
    )
    output = f"{result.stdout}{result.stderr}"

    assert result.exit_code == 1
    assert "Missing required environment variables:" in output
    assert "PLUGGY_CLIENT_ID" in output
    assert "PLUGGY_CLIENT_SECRET" in output


def test_account_update_fails_when_item_id_is_missing(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["account", "update"],
        env=_env(
            tmp_path,
            {
                "PLUGGY_CLIENT_ID": "client-id",
                "PLUGGY_CLIENT_SECRET": "client-secret",
            },
        ),
    )
    output = f"{result.stdout}{result.stderr}"

    assert result.exit_code == 1
    assert "Missing Pluggy item ID." in output
    assert "PLUGGY_ITEM_ID" in output


def test_account_update_fails_when_auth_returns_error(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_authenticate(_: str, __: str) -> str:
        raise PluggyError("Pluggy auth failed with status 401: Unauthorized")

    monkeypatch.setattr("arcter.cli.pluggy.authenticate", fake_authenticate)

    result = runner.invoke(
        app,
        ["account", "update", "item-id"],
        env=_env(
            tmp_path,
            {
                "PLUGGY_CLIENT_ID": "client-id",
                "PLUGGY_CLIENT_SECRET": "client-secret",
            },
        ),
    )
    output = f"{result.stdout}{result.stderr}"

    assert result.exit_code == 1
    assert "Pluggy auth failed with status 401: Unauthorized" in output


def test_account_update_fails_when_update_returns_error(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_authenticate(_: str, __: str) -> str:
        return "api-key"

    def fake_update_item(_: str, __: str) -> None:
        raise PluggyError("Pluggy item update failed with status 400: invalid item")

    monkeypatch.setattr("arcter.cli.pluggy.authenticate", fake_authenticate)
    monkeypatch.setattr("arcter.cli.pluggy.update_item", fake_update_item)

    result = runner.invoke(
        app,
        ["account", "update", "item-id"],
        env=_env(
            tmp_path,
            {
                "PLUGGY_CLIENT_ID": "client-id",
                "PLUGGY_CLIENT_SECRET": "client-secret",
            },
        ),
    )
    output = f"{result.stdout}{result.stderr}"

    assert result.exit_code == 1
    assert "Pluggy item update failed with status 400: invalid item" in output


def test_account_update_surfaces_timeout_error_message(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_authenticate(_: str, __: str) -> str:
        raise PluggyError("Pluggy auth request timed out. Please try again.")

    monkeypatch.setattr("arcter.cli.pluggy.authenticate", fake_authenticate)

    result = runner.invoke(
        app,
        ["account", "update", "item-id"],
        env=_env(
            tmp_path,
            {
                "PLUGGY_CLIENT_ID": "client-id",
                "PLUGGY_CLIENT_SECRET": "client-secret",
            },
        ),
    )
    output = f"{result.stdout}{result.stderr}"

    assert result.exit_code == 1
    assert "Pluggy auth request timed out. Please try again." in output
