from pathlib import Path

from typer.testing import CliRunner

from arcter.cli import app

runner = CliRunner()


def test_root_command_without_args_shows_help() -> None:
    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "Usage:" in result.stdout
    assert "config" in result.stdout
    assert "account" in result.stdout


def test_config_command_without_args_shows_help() -> None:
    result = runner.invoke(app, ["config"])

    assert result.exit_code == 0
    assert "Usage:" in result.stdout
    assert "set" in result.stdout
    assert "get" in result.stdout
    assert "list" in result.stdout


def test_set_currency_writes_valid_toml_and_list_is_readable(
    tmp_path: Path, env
) -> None:
    set_result = runner.invoke(app, ["config", "set", "currency", "usd"], env=env())
    assert set_result.exit_code == 0
    assert "Set currency = USD" in set_result.stdout

    config_file = tmp_path / "arcter" / "config.toml"
    assert config_file.exists()
    assert 'currency = "USD"' in config_file.read_text(encoding="utf-8")

    list_result = runner.invoke(app, ["config", "list"], env=env())
    assert list_result.exit_code == 0
    assert "currency" in list_result.stdout
    assert "USD" in list_result.stdout
    assert "file" in list_result.stdout


def test_unknown_key_is_rejected_at_parse_time(tmp_path: Path, env) -> None:
    result = runner.invoke(app, ["config", "set", "currncy", "USD"], env=env())
    output = f"{result.stdout}{result.stderr}"

    assert result.exit_code == 2
    lowered_output = output.lower()
    assert "invalid value for" in lowered_output
    assert "currncy" in output
    assert "salary" in lowered_output
    assert "currency" in lowered_output
    assert "savings_goal" in lowered_output
    assert "credit_cards.invoice_due_day" in lowered_output
    assert "credit_cards.excluded_categories" in lowered_output
    assert "pluggy.item_id" in lowered_output


def test_invalid_toml_file_returns_actionable_error(tmp_path: Path, env) -> None:
    config_file = tmp_path / "arcter" / "config.toml"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("currency = USD\n", encoding="utf-8")

    result = runner.invoke(app, ["config", "list"], env=env())
    output = f"{result.stdout}{result.stderr}"

    assert result.exit_code == 1
    assert "Config file is not valid TOML" in output
    assert "Fix the syntax and run the command again." in output
    assert "Traceback" not in output


def test_get_reports_env_source_when_env_overrides_file(tmp_path: Path, env) -> None:
    config_file = tmp_path / "arcter" / "config.toml"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text('currency = "USD"\n', encoding="utf-8")

    result = runner.invoke(
        app,
        ["config", "get", "currency"],
        env=env({"ARCTER_CURRENCY": "EUR"}),
    )

    assert result.exit_code == 0
    assert "currency = EUR" in result.stdout
    assert "(source: env)" in result.stdout


def test_list_supports_json_and_toml_formats(tmp_path: Path, env) -> None:
    runner.invoke(app, ["config", "set", "salary", "123.45"], env=env())

    json_result = runner.invoke(app, ["config", "list", "--format", "json"], env=env())
    toml_result = runner.invoke(app, ["config", "list", "--format", "toml"], env=env())

    assert json_result.exit_code == 0
    assert '"salary"' in json_result.stdout
    assert '"source"' in json_result.stdout

    assert toml_result.exit_code == 0
    assert "salary = 123.45" in toml_result.stdout
    assert "[credit_cards]" in toml_result.stdout
    assert "invoice_due_day = 30" in toml_result.stdout
    assert "excluded_categories = []" in toml_result.stdout


def test_set_and_unset_help_include_valid_keys() -> None:
    set_help = runner.invoke(app, ["config", "set", "--help"])
    unset_help = runner.invoke(app, ["config", "unset", "--help"])

    assert set_help.exit_code == 0
    assert "salary" in set_help.stdout.lower()
    assert "currency" in set_help.stdout.lower()
    assert "savings_goal" in set_help.stdout.lower()
    assert "invoice_due_day" in set_help.stdout.lower()
    assert "excluded_categorie" in set_help.stdout.lower()
    assert "pluggy.item_id" in set_help.stdout.lower()

    assert unset_help.exit_code == 0
    assert "salary" in unset_help.stdout.lower()
    assert "currency" in unset_help.stdout.lower()
    assert "savings_goal" in unset_help.stdout.lower()
    assert "invoice_due_day" in unset_help.stdout.lower()
    assert "excluded_categorie" in unset_help.stdout.lower()
    assert "pluggy.item_id" in unset_help.stdout.lower()


def test_list_table_uses_correct_source_for_savings_goal(tmp_path: Path, env) -> None:
    config_file = tmp_path / "arcter" / "config.toml"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("salary = 100.00\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["config", "list"],
        env=env({"ARCTER_SAVINGS_GOAL": "900.00"}),
    )

    assert result.exit_code == 0
    savings_goal_lines = [
        line
        for line in result.stdout.splitlines()
        if line.strip().startswith("savings_goal")
    ]
    assert savings_goal_lines
    assert "env" in savings_goal_lines[0]


def test_set_invoice_due_day_writes_nested_credit_cards_table(
    tmp_path: Path, env
) -> None:
    set_result = runner.invoke(
        app,
        ["config", "set", "credit_cards.invoice_due_day", "25"],
        env=env(),
    )

    assert set_result.exit_code == 0
    assert "Set credit_cards.invoice_due_day = 25" in set_result.stdout

    config_file = tmp_path / "arcter" / "config.toml"
    content = config_file.read_text(encoding="utf-8")
    assert "[credit_cards]" in content
    assert "invoice_due_day = 25" in content

    get_result = runner.invoke(
        app, ["config", "get", "credit_cards.invoice_due_day"], env=env()
    )
    assert get_result.exit_code == 0
    assert "credit_cards.invoice_due_day = 25 (source: file)" in get_result.stdout


def test_set_invoice_due_day_rejects_invalid_value(tmp_path: Path, env) -> None:
    result = runner.invoke(
        app,
        ["config", "set", "credit_cards.invoice_due_day", "99"],
        env=env(),
    )
    output = f"{result.stdout}{result.stderr}"

    assert result.exit_code == 1
    assert "invoice_due_day" in output
    assert "less than or equal to 31" in output


def test_set_excluded_categories_writes_nested_credit_cards_table(
    tmp_path: Path,
    env,
) -> None:
    set_result = runner.invoke(
        app,
        ["config", "set", "credit_cards.excluded_categories", "Transfer, Shopping"],
        env=env(),
    )

    assert set_result.exit_code == 0
    assert (
        'Set credit_cards.excluded_categories = ["Transfer", "Shopping"]'
        in set_result.stdout
    )

    config_file = tmp_path / "arcter" / "config.toml"
    content = config_file.read_text(encoding="utf-8")
    assert "[credit_cards]" in content
    assert "excluded_categories" in content
    assert '"Transfer"' in content
    assert '"Shopping"' in content

    get_result = runner.invoke(
        app,
        ["config", "get", "credit_cards.excluded_categories"],
        env=env(),
    )
    assert get_result.exit_code == 0
    assert (
        'credit_cards.excluded_categories = ["Transfer", "Shopping"] '
        "(source: file)" in get_result.stdout
    )


def test_list_shows_default_invoice_due_day(tmp_path: Path, env) -> None:
    result = runner.invoke(app, ["config", "list"], env=env())

    assert result.exit_code == 0
    invoice_lines = [
        line
        for line in result.stdout.splitlines()
        if line.strip().startswith("credit_cards.invoice_due_day")
    ]
    assert invoice_lines
    assert "30" in invoice_lines[0]
    assert "default" in invoice_lines[0]

    pluggy_lines = [
        line
        for line in result.stdout.splitlines()
        if line.strip().startswith("pluggy.item_id")
    ]
    assert pluggy_lines
    assert "default" in pluggy_lines[0]


def test_list_shows_default_excluded_categories(tmp_path: Path, env) -> None:
    result = runner.invoke(app, ["config", "list"], env=env())

    assert result.exit_code == 0
    excluded_lines = [
        line
        for line in result.stdout.splitlines()
        if line.strip().startswith("credit_cards.excluded_categories")
    ]
    assert excluded_lines
    assert "[]" in excluded_lines[0]
    assert "default" in excluded_lines[0]
