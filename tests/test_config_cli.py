from pathlib import Path

from typer.testing import CliRunner

from arcter.cli import app

runner = CliRunner()


def _env(tmp_path: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {"XDG_CONFIG_HOME": str(tmp_path)}
    if extra:
        env.update(extra)
    return env


def test_set_currency_writes_valid_toml_and_list_is_readable(tmp_path: Path) -> None:
    set_result = runner.invoke(
        app, ["config", "set", "currency", "usd"], env=_env(tmp_path)
    )
    assert set_result.exit_code == 0
    assert "Set currency = USD" in set_result.stdout

    config_file = tmp_path / "arcter" / "config.toml"
    assert config_file.exists()
    assert 'currency = "USD"' in config_file.read_text(encoding="utf-8")

    list_result = runner.invoke(app, ["config", "list"], env=_env(tmp_path))
    assert list_result.exit_code == 0
    assert "currency" in list_result.stdout
    assert "USD" in list_result.stdout
    assert "file" in list_result.stdout


def test_unknown_key_is_rejected_at_parse_time(tmp_path: Path) -> None:
    result = runner.invoke(app, ["config", "set", "currncy", "USD"], env=_env(tmp_path))
    output = f"{result.stdout}{result.stderr}"

    assert result.exit_code == 2
    lowered_output = output.lower()
    assert "invalid value for" in lowered_output
    assert "currncy" in output
    assert "salary" in lowered_output
    assert "currency" in lowered_output


def test_invalid_toml_file_returns_actionable_error(tmp_path: Path) -> None:
    config_file = tmp_path / "arcter" / "config.toml"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("currency = USD\n", encoding="utf-8")

    result = runner.invoke(app, ["config", "list"], env=_env(tmp_path))
    output = f"{result.stdout}{result.stderr}"

    assert result.exit_code == 1
    assert "Config file is not valid TOML" in output
    assert "Fix the syntax and run the command again." in output
    assert "Traceback" not in output


def test_get_reports_env_source_when_env_overrides_file(tmp_path: Path) -> None:
    config_file = tmp_path / "arcter" / "config.toml"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text('currency = "USD"\n', encoding="utf-8")

    result = runner.invoke(
        app,
        ["config", "get", "currency"],
        env=_env(tmp_path, {"ARCTER_CURRENCY": "EUR"}),
    )

    assert result.exit_code == 0
    assert "currency = EUR" in result.stdout
    assert "(source: env)" in result.stdout


def test_list_supports_json_and_toml_formats(tmp_path: Path) -> None:
    runner.invoke(app, ["config", "set", "salary", "123.45"], env=_env(tmp_path))

    json_result = runner.invoke(
        app, ["config", "list", "--format", "json"], env=_env(tmp_path)
    )
    toml_result = runner.invoke(
        app, ["config", "list", "--format", "toml"], env=_env(tmp_path)
    )

    assert json_result.exit_code == 0
    assert '"salary"' in json_result.stdout
    assert '"source"' in json_result.stdout

    assert toml_result.exit_code == 0
    assert "salary = 123.45" in toml_result.stdout


def test_set_and_unset_help_include_valid_keys() -> None:
    set_help = runner.invoke(app, ["config", "set", "--help"])
    unset_help = runner.invoke(app, ["config", "unset", "--help"])

    assert set_help.exit_code == 0
    assert "salary" in set_help.stdout.lower()
    assert "currency" in set_help.stdout.lower()

    assert unset_help.exit_code == 0
    assert "salary" in unset_help.stdout.lower()
    assert "currency" in unset_help.stdout.lower()
