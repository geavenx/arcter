import datetime
from decimal import Decimal
from pathlib import Path

from typer.testing import CliRunner

from arcter.cli import app
from arcter.config import Config, ConfigError
from arcter.pluggy import BalanceRow, CreditCardRow, PluggyError, TransactionRow

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


def test_account_update_fails_when_credentials_are_missing(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("arcter.cli.pluggy.credentials.load_credentials", lambda: None)

    result = runner.invoke(
        app,
        ["account", "update", "item-id"],
        env=_env(tmp_path),
    )
    output = f"{result.stdout}{result.stderr}"

    assert result.exit_code == 1
    assert "Missing Pluggy credentials:" in output
    assert "PLUGGY_CLIENT_ID" in output
    assert "PLUGGY_CLIENT_SECRET" in output
    assert "arcter account login" in output


def test_account_update_fails_when_item_id_is_missing(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("arcter.cli.pluggy._load_config_item_id", lambda: "")

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
    assert "arcter config set pluggy.item_id" in output


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


def test_account_balance_succeeds_with_table_and_currency_totals(
    tmp_path: Path, monkeypatch
) -> None:
    observed: dict[str, str | None] = {}

    def fake_list_item_balances_with_env(item_id: str | None) -> list[BalanceRow]:
        observed["item_id"] = item_id
        return [
            BalanceRow(
                type="BANK",
                name="Checking",
                balance=Decimal("100.25"),
                currency_code="BRL",
            ),
            BalanceRow(
                type="CREDIT",
                name="Visa Platinum",
                balance=Decimal("20.00"),
                currency_code="BRL",
            ),
            BalanceRow(
                type="CREDIT",
                name="Travel Card",
                balance=Decimal("10"),
                currency_code="USD",
            ),
            BalanceRow(
                type="BANK",
                name="No Balance",
                balance=None,
                currency_code="BRL",
            ),
        ]

    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_balances_with_env",
        fake_list_item_balances_with_env,
    )

    result = runner.invoke(
        app, ["account", "balance", "item-from-arg"], env=_env(tmp_path)
    )

    assert result.exit_code == 0
    assert observed["item_id"] == "item-from-arg"
    assert "Type" in result.stdout
    assert "Checking" in result.stdout
    assert "Visa Platinum" in result.stdout
    assert "No Balance" in result.stdout
    assert "N/A" in result.stdout
    assert "Totals by currency:" in result.stdout
    assert "- BRL: 120.25" in result.stdout
    assert "- USD: 10.00" in result.stdout


def test_account_balance_handles_no_eligible_accounts(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_list_item_balances_with_env(_: str | None) -> list[BalanceRow]:
        return []

    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_balances_with_env",
        fake_list_item_balances_with_env,
    )

    result = runner.invoke(app, ["account", "balance"], env=_env(tmp_path))

    assert result.exit_code == 0
    assert (
        "No BANK or CREDIT accounts were found for this Pluggy item." in result.stdout
    )


def test_account_balance_fails_when_credentials_are_missing(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("arcter.cli.pluggy.credentials.load_credentials", lambda: None)

    result = runner.invoke(
        app,
        ["account", "balance", "item-id"],
        env=_env(tmp_path),
    )
    output = f"{result.stdout}{result.stderr}"

    assert result.exit_code == 1
    assert "Missing Pluggy credentials:" in output
    assert "PLUGGY_CLIENT_ID" in output
    assert "PLUGGY_CLIENT_SECRET" in output
    assert "arcter account login" in output


def test_account_balance_fails_when_item_id_is_missing(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("arcter.cli.pluggy._load_config_item_id", lambda: "")

    result = runner.invoke(
        app,
        ["account", "balance"],
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
    assert "arcter config set pluggy.item_id" in output


def test_account_balance_fails_when_fetch_returns_error(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_list_item_balances_with_env(_: str | None) -> list[BalanceRow]:
        raise PluggyError("Pluggy accounts list failed with status 401: Unauthorized")

    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_balances_with_env",
        fake_list_item_balances_with_env,
    )

    result = runner.invoke(
        app,
        ["account", "balance", "item-id"],
        env=_env(tmp_path),
    )
    output = f"{result.stdout}{result.stderr}"

    assert result.exit_code == 1
    assert "Pluggy accounts list failed with status 401: Unauthorized" in output


def test_account_goal_reports_progress_when_goal_not_reached(
    tmp_path: Path, monkeypatch
) -> None:
    observed: dict[str, str | None] = {}

    def fake_load_config() -> Config:
        return Config(
            currency="BRL",
            salary=Decimal("200.00"),
            savings_goal=Decimal("500.00"),
        )

    def fake_list_item_balances_with_env(item_id: str | None) -> list[BalanceRow]:
        observed["item_id"] = item_id
        return [
            BalanceRow(
                type="BANK",
                name="Main",
                balance=Decimal("200.00"),
                currency_code="BRL",
            ),
            BalanceRow(
                type="BANK",
                name="Emergency",
                balance=Decimal("150.00"),
                currency_code="BRL",
            ),
            BalanceRow(
                type="BANK",
                name="Pending",
                balance=None,
                currency_code="BRL",
            ),
            BalanceRow(
                type="CREDIT",
                name="Card",
                balance=Decimal("999.99"),
                currency_code="BRL",
            ),
        ]

    monkeypatch.setattr("arcter.cli.load_config", fake_load_config)
    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_balances_with_env",
        fake_list_item_balances_with_env,
    )

    result = runner.invoke(
        app, ["account", "goal", "item-from-arg"], env=_env(tmp_path)
    )

    assert result.exit_code == 0
    assert observed["item_id"] == "item-from-arg"
    assert "Savings goal progress (BRL):" in result.stdout
    assert "Goal:       BRL 500.00" in result.stdout
    assert "Current:    BRL 350.00  (70.0%)" in result.stdout
    assert "Remaining:  BRL 150.00" in result.stdout
    assert "Monthly salary: BRL 200.00" in result.stdout
    assert "Estimated:  ~0.8 months to reach goal" in result.stdout


def test_account_goal_reports_surplus_when_goal_exceeded(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_load_config() -> Config:
        return Config(
            currency="BRL",
            salary=Decimal("200.00"),
            savings_goal=Decimal("500.00"),
        )

    def fake_list_item_balances_with_env(_: str | None) -> list[BalanceRow]:
        return [
            BalanceRow(
                type="BANK",
                name="Main",
                balance=Decimal("600.00"),
                currency_code="BRL",
            )
        ]

    monkeypatch.setattr("arcter.cli.load_config", fake_load_config)
    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_balances_with_env",
        fake_list_item_balances_with_env,
    )

    result = runner.invoke(app, ["account", "goal"], env=_env(tmp_path))

    assert result.exit_code == 0
    assert "Current:    BRL 600.00  (120.0%)" in result.stdout
    assert "Surplus:    BRL 100.00" in result.stdout
    assert "Goal reached!" in result.stdout


def test_account_goal_reports_exact_goal_as_reached(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_load_config() -> Config:
        return Config(
            currency="BRL",
            salary=Decimal("200.00"),
            savings_goal=Decimal("500.00"),
        )

    def fake_list_item_balances_with_env(_: str | None) -> list[BalanceRow]:
        return [
            BalanceRow(
                type="BANK",
                name="Main",
                balance=Decimal("500.00"),
                currency_code="BRL",
            )
        ]

    monkeypatch.setattr("arcter.cli.load_config", fake_load_config)
    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_balances_with_env",
        fake_list_item_balances_with_env,
    )

    result = runner.invoke(app, ["account", "goal"], env=_env(tmp_path))

    assert result.exit_code == 0
    assert "Current:    BRL 500.00  (100.0%)" in result.stdout
    assert "Goal reached!" in result.stdout


def test_account_goal_reports_when_no_bank_accounts_in_currency(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_load_config() -> Config:
        return Config(
            currency="BRL",
            salary=Decimal("200.00"),
            savings_goal=Decimal("500.00"),
        )

    def fake_list_item_balances_with_env(_: str | None) -> list[BalanceRow]:
        return [
            BalanceRow(
                type="BANK",
                name="USD Account",
                balance=Decimal("100.00"),
                currency_code="USD",
            ),
            BalanceRow(
                type="CREDIT",
                name="Card",
                balance=Decimal("50.00"),
                currency_code="BRL",
            ),
        ]

    monkeypatch.setattr("arcter.cli.load_config", fake_load_config)
    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_balances_with_env",
        fake_list_item_balances_with_env,
    )

    result = runner.invoke(app, ["account", "goal"], env=_env(tmp_path))

    assert result.exit_code == 0
    assert "No BANK accounts found in BRL for this Pluggy item." in result.stdout


def test_account_goal_reports_when_all_bank_balances_are_none(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_load_config() -> Config:
        return Config(
            currency="BRL",
            salary=Decimal("200.00"),
            savings_goal=Decimal("500.00"),
        )

    def fake_list_item_balances_with_env(_: str | None) -> list[BalanceRow]:
        return [
            BalanceRow(type="BANK", name="A", balance=None, currency_code="BRL"),
            BalanceRow(type="BANK", name="B", balance=None, currency_code="BRL"),
        ]

    monkeypatch.setattr("arcter.cli.load_config", fake_load_config)
    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_balances_with_env",
        fake_list_item_balances_with_env,
    )

    result = runner.invoke(app, ["account", "goal"], env=_env(tmp_path))

    assert result.exit_code == 0
    assert "No numeric balances available for BANK accounts in BRL." in result.stdout


def test_account_goal_respects_custom_currency_filter(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_load_config() -> Config:
        return Config(
            currency="BRL",
            salary=Decimal("200.00"),
            savings_goal=Decimal("500.00"),
        )

    def fake_list_item_balances_with_env(_: str | None) -> list[BalanceRow]:
        return [
            BalanceRow(
                type="BANK",
                name="BRL Account",
                balance=Decimal("100.00"),
                currency_code="BRL",
            ),
            BalanceRow(
                type="BANK",
                name="USD Account",
                balance=Decimal("50.00"),
                currency_code="USD",
            ),
        ]

    monkeypatch.setattr("arcter.cli.load_config", fake_load_config)
    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_balances_with_env",
        fake_list_item_balances_with_env,
    )

    result = runner.invoke(
        app, ["account", "goal", "--currency", "usd"], env=_env(tmp_path)
    )

    assert result.exit_code == 0
    assert "Savings goal progress (USD):" in result.stdout
    assert "Current:    USD 50.00  (10.0%)" in result.stdout


def test_account_goal_omits_estimated_line_when_salary_is_zero(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_load_config() -> Config:
        return Config(
            currency="BRL",
            salary=Decimal("0.00"),
            savings_goal=Decimal("500.00"),
        )

    def fake_list_item_balances_with_env(_: str | None) -> list[BalanceRow]:
        return [
            BalanceRow(
                type="BANK",
                name="Main",
                balance=Decimal("100.00"),
                currency_code="BRL",
            )
        ]

    monkeypatch.setattr("arcter.cli.load_config", fake_load_config)
    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_balances_with_env",
        fake_list_item_balances_with_env,
    )

    result = runner.invoke(app, ["account", "goal"], env=_env(tmp_path))

    assert result.exit_code == 0
    assert "Monthly salary: BRL 0.00" in result.stdout
    assert "Estimated:" not in result.stdout


def test_account_goal_propagates_pluggy_error(tmp_path: Path, monkeypatch) -> None:
    def fake_load_config() -> Config:
        return Config(
            currency="BRL",
            salary=Decimal("200.00"),
            savings_goal=Decimal("500.00"),
        )

    def fake_list_item_balances_with_env(_: str | None) -> list[BalanceRow]:
        raise PluggyError("Pluggy accounts list failed with status 500: Internal Error")

    monkeypatch.setattr("arcter.cli.load_config", fake_load_config)
    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_balances_with_env",
        fake_list_item_balances_with_env,
    )

    result = runner.invoke(app, ["account", "goal"], env=_env(tmp_path))
    output = f"{result.stdout}{result.stderr}"

    assert result.exit_code == 1
    assert "Pluggy accounts list failed with status 500: Internal Error" in output


def test_account_goal_propagates_config_error(tmp_path: Path, monkeypatch) -> None:
    def fake_load_config() -> Config:
        raise ConfigError("Config file is not valid TOML")

    monkeypatch.setattr("arcter.cli.load_config", fake_load_config)

    result = runner.invoke(app, ["account", "goal"], env=_env(tmp_path))
    output = f"{result.stdout}{result.stderr}"

    assert result.exit_code == 1
    assert "Config file is not valid TOML" in output


def test_account_credit_shows_detailed_credit_card_output(
    tmp_path: Path, monkeypatch
) -> None:
    observed: dict[str, str | None] = {}

    def fake_list_item_credit_cards_with_env(
        item_id: str | None,
    ) -> list[CreditCardRow]:
        observed["item_id"] = item_id
        return [
            CreditCardRow(
                name="Itau Uniclass 2.0 Mastercard Platinum",
                number="1234",
                balance=Decimal("142.41"),
                currency_code="BRL",
                credit_limit=Decimal("51800"),
                available_credit_limit=Decimal("51300"),
                balance_due_date="2020-07-17",
                minimum_payment=Decimal("100"),
                brand="MASTERCARD",
                level="PLATINUM",
                status="ACTIVE",
                holder_type="MAIN",
            )
        ]

    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_credit_cards_with_env",
        fake_list_item_credit_cards_with_env,
    )

    result = runner.invoke(
        app, ["account", "credit", "item-from-arg"], env=_env(tmp_path)
    )

    assert result.exit_code == 0
    assert observed["item_id"] == "item-from-arg"
    assert "Itau Uniclass 2.0 Mastercard Platinum (****1234)" in result.stdout
    assert "Brand:      MASTERCARD PLATINUM" in result.stdout
    assert "Status:     ACTIVE (MAIN)" in result.stdout
    assert "Balance:    BRL 142.41  (due: 2020-07-17)" in result.stdout
    assert "Min. payment: BRL 100.00" in result.stdout
    assert "Credit limit: BRL 51,800.00  (available: BRL 51,300.00)" in result.stdout


def test_account_credit_shows_blank_line_between_multiple_cards(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_list_item_credit_cards_with_env(_: str | None) -> list[CreditCardRow]:
        return [
            CreditCardRow(
                name="Card One",
                number="1234",
                balance=Decimal("10"),
                currency_code="BRL",
                credit_limit=None,
                available_credit_limit=None,
                balance_due_date=None,
                minimum_payment=None,
                brand="VISA",
                level=None,
                status="ACTIVE",
                holder_type="MAIN",
            ),
            CreditCardRow(
                name="Card Two",
                number="5678",
                balance=Decimal("20"),
                currency_code="BRL",
                credit_limit=None,
                available_credit_limit=None,
                balance_due_date=None,
                minimum_payment=None,
                brand="MASTERCARD",
                level=None,
                status="ACTIVE",
                holder_type="MAIN",
            ),
        ]

    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_credit_cards_with_env",
        fake_list_item_credit_cards_with_env,
    )

    result = runner.invoke(app, ["account", "credit"], env=_env(tmp_path))

    assert result.exit_code == 0
    assert "Card One (****1234)" in result.stdout
    assert "Card Two (****5678)" in result.stdout
    assert "\n\nCard Two (****5678)\n" in result.stdout


def test_account_credit_handles_no_credit_cards(tmp_path: Path, monkeypatch) -> None:
    def fake_list_item_credit_cards_with_env(_: str | None) -> list[CreditCardRow]:
        return []

    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_credit_cards_with_env",
        fake_list_item_credit_cards_with_env,
    )

    result = runner.invoke(app, ["account", "credit"], env=_env(tmp_path))

    assert result.exit_code == 0
    assert "No credit card accounts found for this Pluggy item." in result.stdout


def test_account_credit_handles_missing_optional_fields(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_list_item_credit_cards_with_env(_: str | None) -> list[CreditCardRow]:
        return [
            CreditCardRow(
                name="Simple Card",
                number="",
                balance=Decimal("55"),
                currency_code="USD",
                credit_limit=None,
                available_credit_limit=None,
                balance_due_date=None,
                minimum_payment=None,
                brand=None,
                level=None,
                status=None,
                holder_type=None,
            )
        ]

    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_credit_cards_with_env",
        fake_list_item_credit_cards_with_env,
    )

    result = runner.invoke(app, ["account", "credit"], env=_env(tmp_path))

    assert result.exit_code == 0
    assert "Simple Card" in result.stdout
    assert "Simple Card (****" not in result.stdout
    assert "Brand:      N/A" in result.stdout
    assert "Status:     N/A" in result.stdout
    assert "Balance:    USD 55.00" in result.stdout
    assert "Min. payment:" not in result.stdout
    assert "Credit limit:" not in result.stdout


def test_account_credit_propagates_pluggy_error(tmp_path: Path, monkeypatch) -> None:
    def fake_list_item_credit_cards_with_env(_: str | None) -> list[CreditCardRow]:
        raise PluggyError("Pluggy accounts list failed with status 500: Internal Error")

    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_credit_cards_with_env",
        fake_list_item_credit_cards_with_env,
    )

    result = runner.invoke(app, ["account", "credit"], env=_env(tmp_path))
    output = f"{result.stdout}{result.stderr}"

    assert result.exit_code == 1
    assert "Pluggy accounts list failed with status 500: Internal Error" in output


def test_account_credit_fails_when_credentials_are_missing(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("arcter.cli.pluggy.credentials.load_credentials", lambda: None)

    result = runner.invoke(
        app,
        ["account", "credit", "item-id"],
        env=_env(tmp_path),
    )
    output = f"{result.stdout}{result.stderr}"

    assert result.exit_code == 1
    assert "Missing Pluggy credentials:" in output
    assert "PLUGGY_CLIENT_ID" in output
    assert "PLUGGY_CLIENT_SECRET" in output
    assert "arcter account login" in output


def test_account_credit_fails_when_item_id_is_missing(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("arcter.cli.pluggy._load_config_item_id", lambda: "")

    result = runner.invoke(
        app,
        ["account", "credit"],
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
    assert "arcter config set pluggy.item_id" in output


def test_account_transactions_happy_path_shows_table(
    tmp_path: Path, monkeypatch
) -> None:
    observed: dict[str, object] = {"due_day": None}

    def fake_load_config() -> Config:
        return Config(
            currency="BRL",
            salary=Decimal("200.00"),
            savings_goal=Decimal("500.00"),
            credit_cards={"invoice_due_day": 30},
        )

    def fake_derive_invoice_cycle_date_range(
        invoice_due_day: int,
        reference_date: object | None = None,
    ) -> tuple[str, str]:
        observed["due_day"] = invoice_due_day
        return ("2026-01-30", "2026-02-28")

    def fake_list_item_transactions_with_env(
        item_id: str | None,
        date_from: str | None = None,
        date_to: str | None = None,
        account_type_filter: str | None = None,
        env: dict[str, str] | None = None,
    ) -> list[TransactionRow]:
        observed["item_id"] = item_id
        observed["date_from"] = date_from
        observed["date_to"] = date_to
        observed["account_type_filter"] = account_type_filter
        observed["env"] = env
        return [
            TransactionRow(
                date="2026-01-15",
                description="Salary",
                amount=Decimal("1500.00"),
                currency_code="BRL",
                type="CREDIT",
                status="POSTED",
                category="Transfer",
                account_name="Checking",
                account_type="BANK",
            ),
            TransactionRow(
                date="2026-01-14",
                description="Groceries",
                amount=Decimal("200.00"),
                currency_code="BRL",
                type="DEBIT",
                status="POSTED",
                category="Food",
                account_name="Checking",
                account_type="BANK",
            ),
            TransactionRow(
                date="2026-01-14",
                description="Pending txn",
                amount=Decimal("50"),
                currency_code="BRL",
                type="DEBIT",
                status="PENDING",
                category=None,
                account_name="Visa Platinum",
                account_type="CREDIT",
            ),
        ]

    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_transactions_with_env",
        fake_list_item_transactions_with_env,
    )
    monkeypatch.setattr("arcter.cli.load_config", fake_load_config)
    monkeypatch.setattr(
        "arcter.cli._derive_invoice_cycle_date_range",
        fake_derive_invoice_cycle_date_range,
    )

    result = runner.invoke(
        app, ["account", "transactions", "item-from-arg"], env=_env(tmp_path)
    )

    assert result.exit_code == 0
    assert observed["item_id"] == "item-from-arg"
    assert observed["due_day"] == 30
    assert observed["date_from"] == "2026-01-30"
    assert observed["date_to"] == "2026-02-28"
    assert observed["account_type_filter"] is None
    assert observed["env"] is None
    assert "Date" in result.stdout
    assert "Account" in result.stdout
    assert "Type" in result.stdout
    assert "Amount" in result.stdout
    assert "Currency" in result.stdout
    assert "Category" in result.stdout
    assert "Status" in result.stdout
    assert "+1,500.00" in result.stdout
    assert "-200.00" in result.stdout
    assert "PENDING" in result.stdout
    assert "Showing 3 of 3 transactions." in result.stdout
    assert "TOTAL: +1,250.00" in result.stdout


def test_account_transactions_passes_date_filter_options(
    tmp_path: Path, monkeypatch
) -> None:
    observed: dict[str, object] = {}

    def fake_list_item_transactions_with_env(
        item_id: str | None,
        date_from: str | None = None,
        date_to: str | None = None,
        account_type_filter: str | None = None,
        env: dict[str, str] | None = None,
    ) -> list[TransactionRow]:
        observed["item_id"] = item_id
        observed["date_from"] = date_from
        observed["date_to"] = date_to
        observed["account_type_filter"] = account_type_filter
        observed["env"] = env
        return []

    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_transactions_with_env",
        fake_list_item_transactions_with_env,
    )

    def fake_load_config() -> Config:
        observed["load_config_called"] = True
        return Config(
            currency="BRL",
            salary=Decimal("200.00"),
            savings_goal=Decimal("500.00"),
            credit_cards={"invoice_due_day": 30, "excluded_categories": ["Transfer"]},
        )

    def fail_derive_invoice_cycle_date_range(
        invoice_due_day: int,
        reference_date: object | None = None,
    ) -> tuple[str, str]:
        raise AssertionError(
            "Invoice cycle should not be derived when explicit dates are provided."
        )

    monkeypatch.setattr("arcter.cli.load_config", fake_load_config)
    monkeypatch.setattr(
        "arcter.cli._derive_invoice_cycle_date_range",
        fail_derive_invoice_cycle_date_range,
    )

    result = runner.invoke(
        app,
        [
            "account",
            "transactions",
            "--from",
            "2026-01-01",
            "--to",
            "2026-01-31",
        ],
        env=_env(tmp_path),
    )

    assert result.exit_code == 0
    assert observed["item_id"] is None
    assert observed["date_from"] == "2026-01-01"
    assert observed["date_to"] == "2026-01-31"
    assert observed["account_type_filter"] is None
    assert observed["env"] is None
    assert observed["load_config_called"] is True
    assert "No transactions found between 2026-01-01 and 2026-01-31." in result.stdout


def test_account_transactions_passes_account_type_filter(
    tmp_path: Path, monkeypatch
) -> None:
    observed: dict[str, object] = {"due_day": None}

    def fake_load_config() -> Config:
        return Config(
            currency="BRL",
            salary=Decimal("200.00"),
            savings_goal=Decimal("500.00"),
            credit_cards={"invoice_due_day": 25},
        )

    def fake_derive_invoice_cycle_date_range(
        invoice_due_day: int,
        reference_date: object | None = None,
    ) -> tuple[str, str]:
        observed["due_day"] = invoice_due_day
        return ("2026-01-25", "2026-02-25")

    def fake_list_item_transactions_with_env(
        item_id: str | None,
        date_from: str | None = None,
        date_to: str | None = None,
        account_type_filter: str | None = None,
        env: dict[str, str] | None = None,
    ) -> list[TransactionRow]:
        observed["item_id"] = item_id
        observed["date_from"] = date_from
        observed["date_to"] = date_to
        observed["account_type_filter"] = account_type_filter
        observed["env"] = env
        return []

    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_transactions_with_env",
        fake_list_item_transactions_with_env,
    )
    monkeypatch.setattr("arcter.cli.load_config", fake_load_config)
    monkeypatch.setattr(
        "arcter.cli._derive_invoice_cycle_date_range",
        fake_derive_invoice_cycle_date_range,
    )

    result = runner.invoke(
        app,
        ["account", "transactions", "--account-type", "bank"],
        env=_env(tmp_path),
    )

    assert result.exit_code == 0
    assert observed["item_id"] is None
    assert observed["due_day"] == 25
    assert observed["account_type_filter"] == "BANK"
    assert observed["date_from"] == "2026-01-25"
    assert observed["date_to"] == "2026-02-25"
    assert observed["env"] is None


def test_account_transactions_filters_by_transaction_type(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_load_config() -> Config:
        return Config(
            currency="BRL",
            salary=Decimal("200.00"),
            savings_goal=Decimal("500.00"),
            credit_cards={"invoice_due_day": 30},
        )

    def fake_derive_invoice_cycle_date_range(
        invoice_due_day: int,
        reference_date: object | None = None,
    ) -> tuple[str, str]:
        return ("2026-01-30", "2026-02-28")

    def fake_list_item_transactions_with_env(
        item_id: str | None,
        date_from: str | None = None,
        date_to: str | None = None,
        account_type_filter: str | None = None,
        env: dict[str, str] | None = None,
    ) -> list[TransactionRow]:
        return [
            TransactionRow(
                date="2026-01-15",
                description="Salary",
                amount=Decimal("1500.00"),
                currency_code="BRL",
                type="CREDIT",
                status="POSTED",
                category="Transfer",
                account_name="Checking",
                account_type="BANK",
            ),
            TransactionRow(
                date="2026-01-14",
                description="Groceries",
                amount=Decimal("200.00"),
                currency_code="BRL",
                type="DEBIT",
                status="POSTED",
                category="Food",
                account_name="Checking",
                account_type="BANK",
            ),
        ]

    monkeypatch.setattr("arcter.cli.load_config", fake_load_config)
    monkeypatch.setattr(
        "arcter.cli._derive_invoice_cycle_date_range",
        fake_derive_invoice_cycle_date_range,
    )
    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_transactions_with_env",
        fake_list_item_transactions_with_env,
    )

    result = runner.invoke(
        app, ["account", "transactions", "--type", "credit"], env=_env(tmp_path)
    )

    assert result.exit_code == 0
    assert "+1,500.00" in result.stdout
    assert "-200.00" not in result.stdout
    assert "Showing 1 of 1 transactions." in result.stdout
    assert "TOTAL: +1,500.00" in result.stdout


def test_account_transactions_excludes_categories_from_config(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_load_config() -> Config:
        return Config(
            currency="BRL",
            salary=Decimal("200.00"),
            savings_goal=Decimal("500.00"),
            credit_cards={
                "invoice_due_day": 30,
                "excluded_categories": ["food", "Transfer"],
            },
        )

    def fake_derive_invoice_cycle_date_range(
        invoice_due_day: int,
        reference_date: object | None = None,
    ) -> tuple[str, str]:
        return ("2026-01-30", "2026-02-28")

    def fake_list_item_transactions_with_env(
        item_id: str | None,
        date_from: str | None = None,
        date_to: str | None = None,
        account_type_filter: str | None = None,
        env: dict[str, str] | None = None,
    ) -> list[TransactionRow]:
        return [
            TransactionRow(
                date="2026-01-15",
                description="Salary",
                amount=Decimal("1500.00"),
                currency_code="BRL",
                type="CREDIT",
                status="POSTED",
                category="Transfer",
                account_name="Checking",
                account_type="BANK",
            ),
            TransactionRow(
                date="2026-01-14",
                description="Groceries",
                amount=Decimal("200.00"),
                currency_code="BRL",
                type="DEBIT",
                status="POSTED",
                category="Food",
                account_name="Checking",
                account_type="BANK",
            ),
            TransactionRow(
                date="2026-01-14",
                description="Pending txn",
                amount=Decimal("50"),
                currency_code="BRL",
                type="DEBIT",
                status="PENDING",
                category=None,
                account_name="Visa Platinum",
                account_type="CREDIT",
            ),
        ]

    monkeypatch.setattr("arcter.cli.load_config", fake_load_config)
    monkeypatch.setattr(
        "arcter.cli._derive_invoice_cycle_date_range",
        fake_derive_invoice_cycle_date_range,
    )
    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_transactions_with_env",
        fake_list_item_transactions_with_env,
    )

    result = runner.invoke(app, ["account", "transactions"], env=_env(tmp_path))

    assert result.exit_code == 0
    assert "Transfer" not in result.stdout
    assert "Food" not in result.stdout
    assert "PENDING" in result.stdout
    assert "Showing 1 of 1 transactions." in result.stdout
    assert "TOTAL: -50.00" in result.stdout


def test_account_transactions_excludes_categories_from_cli_option(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_load_config() -> Config:
        return Config(
            currency="BRL",
            salary=Decimal("200.00"),
            savings_goal=Decimal("500.00"),
            credit_cards={"invoice_due_day": 30, "excluded_categories": []},
        )

    def fake_derive_invoice_cycle_date_range(
        invoice_due_day: int,
        reference_date: object | None = None,
    ) -> tuple[str, str]:
        return ("2026-01-30", "2026-02-28")

    def fake_list_item_transactions_with_env(
        item_id: str | None,
        date_from: str | None = None,
        date_to: str | None = None,
        account_type_filter: str | None = None,
        env: dict[str, str] | None = None,
    ) -> list[TransactionRow]:
        return [
            TransactionRow(
                date="2026-01-15",
                description="Salary",
                amount=Decimal("1500.00"),
                currency_code="BRL",
                type="CREDIT",
                status="POSTED",
                category="Transfer",
                account_name="Checking",
                account_type="BANK",
            ),
            TransactionRow(
                date="2026-01-14",
                description="Groceries",
                amount=Decimal("200.00"),
                currency_code="BRL",
                type="DEBIT",
                status="POSTED",
                category="Food",
                account_name="Checking",
                account_type="BANK",
            ),
        ]

    monkeypatch.setattr("arcter.cli.load_config", fake_load_config)
    monkeypatch.setattr(
        "arcter.cli._derive_invoice_cycle_date_range",
        fake_derive_invoice_cycle_date_range,
    )
    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_transactions_with_env",
        fake_list_item_transactions_with_env,
    )

    result = runner.invoke(
        app,
        ["account", "transactions", "--excludes", "transfer"],
        env=_env(tmp_path),
    )

    assert result.exit_code == 0
    assert "+1,500.00" not in result.stdout
    assert "-200.00" in result.stdout
    assert "Showing 1 of 1 transactions." in result.stdout
    assert "TOTAL: -200.00" in result.stdout


def test_account_transactions_combines_config_and_cli_excluded_categories(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_load_config() -> Config:
        return Config(
            currency="BRL",
            salary=Decimal("200.00"),
            savings_goal=Decimal("500.00"),
            credit_cards={"invoice_due_day": 30, "excluded_categories": ["Food"]},
        )

    def fake_derive_invoice_cycle_date_range(
        invoice_due_day: int,
        reference_date: object | None = None,
    ) -> tuple[str, str]:
        return ("2026-01-30", "2026-02-28")

    def fake_list_item_transactions_with_env(
        item_id: str | None,
        date_from: str | None = None,
        date_to: str | None = None,
        account_type_filter: str | None = None,
        env: dict[str, str] | None = None,
    ) -> list[TransactionRow]:
        return [
            TransactionRow(
                date="2026-01-15",
                description="Salary",
                amount=Decimal("1500.00"),
                currency_code="BRL",
                type="CREDIT",
                status="POSTED",
                category="Transfer",
                account_name="Checking",
                account_type="BANK",
            ),
            TransactionRow(
                date="2026-01-14",
                description="Groceries",
                amount=Decimal("200.00"),
                currency_code="BRL",
                type="DEBIT",
                status="POSTED",
                category="Food",
                account_name="Checking",
                account_type="BANK",
            ),
        ]

    monkeypatch.setattr("arcter.cli.load_config", fake_load_config)
    monkeypatch.setattr(
        "arcter.cli._derive_invoice_cycle_date_range",
        fake_derive_invoice_cycle_date_range,
    )
    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_transactions_with_env",
        fake_list_item_transactions_with_env,
    )

    result = runner.invoke(
        app,
        ["account", "transactions", "--excludes", "transfer"],
        env=_env(tmp_path),
    )

    assert result.exit_code == 0
    assert "No transactions found for this Pluggy item." in result.stdout


def test_account_transactions_respects_limit_option(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_list_item_transactions_with_env(
        item_id: str | None,
        date_from: str | None = None,
        date_to: str | None = None,
        account_type_filter: str | None = None,
        env: dict[str, str] | None = None,
    ) -> list[TransactionRow]:
        return [
            TransactionRow(
                date=f"2026-01-{day:02d}",
                description=f"Tx {day}",
                amount=Decimal("10.00"),
                currency_code="BRL",
                type="DEBIT",
                status="POSTED",
                category="Misc",
                account_name="Checking",
                account_type="BANK",
            )
            for day in range(1, 11)
        ]

    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_transactions_with_env",
        fake_list_item_transactions_with_env,
    )

    result = runner.invoke(
        app, ["account", "transactions", "--limit", "5"], env=_env(tmp_path)
    )

    assert result.exit_code == 0
    assert "Showing 5 of 10 transactions." in result.stdout
    assert "Use --limit to show more." in result.stdout
    assert "TOTAL: -50.00" in result.stdout


def test_account_transactions_handles_no_transactions(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_list_item_transactions_with_env(
        item_id: str | None,
        date_from: str | None = None,
        date_to: str | None = None,
        account_type_filter: str | None = None,
        env: dict[str, str] | None = None,
    ) -> list[TransactionRow]:
        return []

    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_transactions_with_env",
        fake_list_item_transactions_with_env,
    )

    result = runner.invoke(app, ["account", "transactions"], env=_env(tmp_path))

    assert result.exit_code == 0
    assert "No transactions found for this Pluggy item." in result.stdout


def test_account_transactions_rejects_invalid_date_format(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["account", "transactions", "--from", "2026/01/01"],
        env=_env(tmp_path),
    )
    output = f"{result.stdout}{result.stderr}"

    assert result.exit_code == 1
    assert "--from must use YYYY-MM-DD format." in output


def test_account_transactions_rejects_invalid_transaction_type(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["account", "transactions", "--type", "bank"],
        env=_env(tmp_path),
    )
    output = f"{result.stdout}{result.stderr}"

    assert result.exit_code == 1
    assert "Option --type must be either 'credit' or 'debit'." in output


def test_account_transactions_propagates_pluggy_error(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_list_item_transactions_with_env(
        item_id: str | None,
        date_from: str | None = None,
        date_to: str | None = None,
        account_type_filter: str | None = None,
        env: dict[str, str] | None = None,
    ) -> list[TransactionRow]:
        raise PluggyError(
            "Pluggy transactions list failed with status 500: Internal Error"
        )

    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_transactions_with_env",
        fake_list_item_transactions_with_env,
    )

    result = runner.invoke(app, ["account", "transactions"], env=_env(tmp_path))
    output = f"{result.stdout}{result.stderr}"

    assert result.exit_code == 1
    assert "Pluggy transactions list failed with status 500: Internal Error" in output


def test_account_transactions_fails_when_credentials_are_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr("arcter.cli.pluggy.credentials.load_credentials", lambda: None)

    result = runner.invoke(
        app,
        ["account", "transactions", "item-id"],
        env=_env(tmp_path),
    )
    output = f"{result.stdout}{result.stderr}"

    assert result.exit_code == 1
    assert "Missing Pluggy credentials:" in output
    assert "PLUGGY_CLIENT_ID" in output
    assert "PLUGGY_CLIENT_SECRET" in output
    assert "arcter account login" in output


def test_account_transactions_propagates_config_error(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_load_config() -> Config:
        raise ConfigError("Config file is not valid TOML")

    monkeypatch.setattr("arcter.cli.load_config", fake_load_config)

    result = runner.invoke(app, ["account", "transactions"], env=_env(tmp_path))
    output = f"{result.stdout}{result.stderr}"

    assert result.exit_code == 1
    assert "Config file is not valid TOML" in output


def test_account_spending_happy_path_shows_summary_table(
    tmp_path: Path, monkeypatch
) -> None:
    observed: dict[str, object] = {}

    def fake_load_config() -> Config:
        return Config(
            currency="BRL",
            salary=Decimal("200.00"),
            savings_goal=Decimal("500.00"),
        )

    def fake_list_item_transactions_with_env(
        item_id: str | None,
        date_from: str | None = None,
        date_to: str | None = None,
        account_type_filter: str | None = None,
        env: dict[str, str] | None = None,
    ) -> list[TransactionRow]:
        observed["item_id"] = item_id
        observed["date_from"] = date_from
        observed["date_to"] = date_to
        observed["account_type_filter"] = account_type_filter
        observed["env"] = env
        return [
            TransactionRow(
                date="2026-02-10",
                description="Lunch",
                amount=Decimal("100.00"),
                currency_code="BRL",
                type="DEBIT",
                status="POSTED",
                category="Food and drinks",
                account_name="Checking",
                account_type="BANK",
            ),
            TransactionRow(
                date="2026-02-09",
                description="Dinner",
                amount=Decimal("20.00"),
                currency_code="BRL",
                type="DEBIT",
                status="POSTED",
                category="Food and drinks",
                account_name="Checking",
                account_type="BANK",
            ),
            TransactionRow(
                date="2026-02-08",
                description="Online order",
                amount=Decimal("50.00"),
                currency_code="BRL",
                type="DEBIT",
                status="POSTED",
                category="Shopping",
                account_name="Checking",
                account_type="BANK",
            ),
            TransactionRow(
                date="2026-02-01",
                description="Salary",
                amount=Decimal("1000.00"),
                currency_code="BRL",
                type="CREDIT",
                status="POSTED",
                category="Salary",
                account_name="Checking",
                account_type="BANK",
            ),
        ]

    monkeypatch.setattr("arcter.cli.load_config", fake_load_config)
    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_transactions_with_env",
        fake_list_item_transactions_with_env,
    )

    result = runner.invoke(
        app,
        [
            "account",
            "spending",
            "item-from-arg",
            "--from",
            "2026-02-01",
            "--to",
            "2026-02-11",
        ],
        env=_env(tmp_path),
    )

    assert result.exit_code == 0
    assert observed["item_id"] == "item-from-arg"
    assert observed["date_from"] == "2026-02-01"
    assert observed["date_to"] == "2026-02-11"
    assert observed["account_type_filter"] is None
    assert observed["env"] is None
    assert "Spending summary (2026-02-01 to 2026-02-11)" in result.stdout
    assert "Direction: expenses" in result.stdout
    assert "Food and drinks" in result.stdout
    assert "Shopping" in result.stdout
    assert "BRL 120.00" in result.stdout
    assert "BRL 50.00" in result.stdout
    assert "Total: BRL 170.00 across 3 transactions" in result.stdout


def test_account_spending_defaults_to_first_day_of_month_and_today(
    tmp_path: Path, monkeypatch
) -> None:
    observed: dict[str, object] = {}

    class FixedDate(datetime.date):
        @classmethod
        def today(cls) -> "FixedDate":
            return cls(2026, 2, 11)

    def fake_load_config() -> Config:
        return Config(
            currency="BRL",
            salary=Decimal("200.00"),
            savings_goal=Decimal("500.00"),
        )

    def fake_list_item_transactions_with_env(
        item_id: str | None,
        date_from: str | None = None,
        date_to: str | None = None,
        account_type_filter: str | None = None,
        env: dict[str, str] | None = None,
    ) -> list[TransactionRow]:
        observed["date_from"] = date_from
        observed["date_to"] = date_to
        return []

    monkeypatch.setattr("arcter.cli.datetime.date", FixedDate)
    monkeypatch.setattr("arcter.cli.load_config", fake_load_config)
    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_transactions_with_env",
        fake_list_item_transactions_with_env,
    )

    result = runner.invoke(app, ["account", "spending"], env=_env(tmp_path))

    assert result.exit_code == 0
    assert observed["date_from"] == "2026-02-01"
    assert observed["date_to"] == "2026-02-11"
    assert "No transactions found for this period." in result.stdout


def test_account_spending_passes_custom_date_range(tmp_path: Path, monkeypatch) -> None:
    observed: dict[str, object] = {}

    def fake_load_config() -> Config:
        return Config(
            currency="BRL",
            salary=Decimal("200.00"),
            savings_goal=Decimal("500.00"),
        )

    def fake_list_item_transactions_with_env(
        item_id: str | None,
        date_from: str | None = None,
        date_to: str | None = None,
        account_type_filter: str | None = None,
        env: dict[str, str] | None = None,
    ) -> list[TransactionRow]:
        observed["date_from"] = date_from
        observed["date_to"] = date_to
        return []

    monkeypatch.setattr("arcter.cli.load_config", fake_load_config)
    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_transactions_with_env",
        fake_list_item_transactions_with_env,
    )

    result = runner.invoke(
        app,
        [
            "account",
            "spending",
            "--from",
            "2026-01-01",
            "--to",
            "2026-01-31",
        ],
        env=_env(tmp_path),
    )

    assert result.exit_code == 0
    assert observed["date_from"] == "2026-01-01"
    assert observed["date_to"] == "2026-01-31"


def test_account_spending_direction_income(tmp_path: Path, monkeypatch) -> None:
    def fake_load_config() -> Config:
        return Config(
            currency="BRL",
            salary=Decimal("200.00"),
            savings_goal=Decimal("500.00"),
        )

    def fake_list_item_transactions_with_env(
        item_id: str | None,
        date_from: str | None = None,
        date_to: str | None = None,
        account_type_filter: str | None = None,
        env: dict[str, str] | None = None,
    ) -> list[TransactionRow]:
        return [
            TransactionRow(
                date="2026-01-10",
                description="Salary",
                amount=Decimal("2000.00"),
                currency_code="BRL",
                type="CREDIT",
                status="POSTED",
                category="Salary",
                account_name="Checking",
                account_type="BANK",
            ),
            TransactionRow(
                date="2026-01-11",
                description="Cashback",
                amount=Decimal("50.00"),
                currency_code="BRL",
                type="CREDIT",
                status="POSTED",
                category="Benefits",
                account_name="Checking",
                account_type="BANK",
            ),
            TransactionRow(
                date="2026-01-12",
                description="Groceries",
                amount=Decimal("100.00"),
                currency_code="BRL",
                type="DEBIT",
                status="POSTED",
                category="Food",
                account_name="Checking",
                account_type="BANK",
            ),
        ]

    monkeypatch.setattr("arcter.cli.load_config", fake_load_config)
    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_transactions_with_env",
        fake_list_item_transactions_with_env,
    )

    result = runner.invoke(
        app,
        [
            "account",
            "spending",
            "--from",
            "2026-01-01",
            "--to",
            "2026-01-31",
            "--direction",
            "income",
        ],
        env=_env(tmp_path),
    )

    assert result.exit_code == 0
    assert "Direction: income" in result.stdout
    assert "Salary" in result.stdout
    assert "Benefits" in result.stdout
    assert "Food" not in result.stdout
    assert "Total: BRL 2,050.00 across 2 transactions" in result.stdout


def test_account_spending_top_n(tmp_path: Path, monkeypatch) -> None:
    def fake_load_config() -> Config:
        return Config(
            currency="BRL",
            salary=Decimal("200.00"),
            savings_goal=Decimal("500.00"),
        )

    def fake_list_item_transactions_with_env(
        item_id: str | None,
        date_from: str | None = None,
        date_to: str | None = None,
        account_type_filter: str | None = None,
        env: dict[str, str] | None = None,
    ) -> list[TransactionRow]:
        return [
            TransactionRow(
                date="2026-01-10",
                description="Food",
                amount=Decimal("500.00"),
                currency_code="BRL",
                type="DEBIT",
                status="POSTED",
                category="Food",
                account_name="Checking",
                account_type="BANK",
            ),
            TransactionRow(
                date="2026-01-11",
                description="Shopping",
                amount=Decimal("400.00"),
                currency_code="BRL",
                type="DEBIT",
                status="POSTED",
                category="Shopping",
                account_name="Checking",
                account_type="BANK",
            ),
            TransactionRow(
                date="2026-01-12",
                description="Transport",
                amount=Decimal("300.00"),
                currency_code="BRL",
                type="DEBIT",
                status="POSTED",
                category="Transportation",
                account_name="Checking",
                account_type="BANK",
            ),
            TransactionRow(
                date="2026-01-13",
                description="Bills",
                amount=Decimal("200.00"),
                currency_code="BRL",
                type="DEBIT",
                status="POSTED",
                category="Utilities",
                account_name="Checking",
                account_type="BANK",
            ),
            TransactionRow(
                date="2026-01-14",
                description="Health",
                amount=Decimal("100.00"),
                currency_code="BRL",
                type="DEBIT",
                status="POSTED",
                category="Healthcare",
                account_name="Checking",
                account_type="BANK",
            ),
        ]

    monkeypatch.setattr("arcter.cli.load_config", fake_load_config)
    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_transactions_with_env",
        fake_list_item_transactions_with_env,
    )

    result = runner.invoke(
        app,
        [
            "account",
            "spending",
            "--from",
            "2026-01-01",
            "--to",
            "2026-01-31",
            "--top",
            "3",
        ],
        env=_env(tmp_path),
    )

    assert result.exit_code == 0
    assert "Food" in result.stdout
    assert "Shopping" in result.stdout
    assert "Transportation" in result.stdout
    assert "... and 2 more categories" in result.stdout


def test_account_spending_passes_account_type_filter(
    tmp_path: Path, monkeypatch
) -> None:
    observed: dict[str, object] = {}

    def fake_load_config() -> Config:
        return Config(
            currency="BRL",
            salary=Decimal("200.00"),
            savings_goal=Decimal("500.00"),
        )

    def fake_list_item_transactions_with_env(
        item_id: str | None,
        date_from: str | None = None,
        date_to: str | None = None,
        account_type_filter: str | None = None,
        env: dict[str, str] | None = None,
    ) -> list[TransactionRow]:
        observed["account_type_filter"] = account_type_filter
        return []

    monkeypatch.setattr("arcter.cli.load_config", fake_load_config)
    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_transactions_with_env",
        fake_list_item_transactions_with_env,
    )

    result = runner.invoke(
        app,
        [
            "account",
            "spending",
            "--from",
            "2026-01-01",
            "--to",
            "2026-01-31",
            "--type",
            "bank",
        ],
        env=_env(tmp_path),
    )

    assert result.exit_code == 0
    assert observed["account_type_filter"] == "BANK"


def test_account_spending_handles_no_transactions(tmp_path: Path, monkeypatch) -> None:
    def fake_load_config() -> Config:
        return Config(
            currency="BRL",
            salary=Decimal("200.00"),
            savings_goal=Decimal("500.00"),
        )

    def fake_list_item_transactions_with_env(
        item_id: str | None,
        date_from: str | None = None,
        date_to: str | None = None,
        account_type_filter: str | None = None,
        env: dict[str, str] | None = None,
    ) -> list[TransactionRow]:
        return []

    monkeypatch.setattr("arcter.cli.load_config", fake_load_config)
    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_transactions_with_env",
        fake_list_item_transactions_with_env,
    )

    result = runner.invoke(
        app,
        [
            "account",
            "spending",
            "--from",
            "2026-01-01",
            "--to",
            "2026-01-31",
        ],
        env=_env(tmp_path),
    )

    assert result.exit_code == 0
    assert "No transactions found for this period." in result.stdout


def test_account_spending_rejects_invalid_direction(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["account", "spending", "--direction", "outflow"],
        env=_env(tmp_path),
    )
    output = f"{result.stdout}{result.stderr}"

    assert result.exit_code == 1
    assert "Option --direction must be one of: expense, income, all." in output


def test_account_spending_rejects_invalid_date(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["account", "spending", "--from", "2026/01/01"],
        env=_env(tmp_path),
    )
    output = f"{result.stdout}{result.stderr}"

    assert result.exit_code == 1
    assert "--from must use YYYY-MM-DD format." in output


def test_account_spending_propagates_pluggy_error(tmp_path: Path, monkeypatch) -> None:
    def fake_load_config() -> Config:
        return Config(
            currency="BRL",
            salary=Decimal("200.00"),
            savings_goal=Decimal("500.00"),
        )

    def fake_list_item_transactions_with_env(
        item_id: str | None,
        date_from: str | None = None,
        date_to: str | None = None,
        account_type_filter: str | None = None,
        env: dict[str, str] | None = None,
    ) -> list[TransactionRow]:
        raise PluggyError(
            "Pluggy transactions list failed with status 500: Internal Error"
        )

    monkeypatch.setattr("arcter.cli.load_config", fake_load_config)
    monkeypatch.setattr(
        "arcter.cli.pluggy.list_item_transactions_with_env",
        fake_list_item_transactions_with_env,
    )

    result = runner.invoke(app, ["account", "spending"], env=_env(tmp_path))
    output = f"{result.stdout}{result.stderr}"

    assert result.exit_code == 1
    assert "Pluggy transactions list failed with status 500: Internal Error" in output


def test_account_login_stores_credentials_with_flags(
    tmp_path: Path, monkeypatch
) -> None:
    """arcter account login --client-id X --client-secret Y stores in keyring."""
    observed: dict[str, str] = {}

    def fake_store_credentials(client_id: str, client_secret: str) -> None:
        observed["client_id"] = client_id
        observed["client_secret"] = client_secret

    monkeypatch.setattr(
        "arcter.cli.credentials.store_credentials", fake_store_credentials
    )

    result = runner.invoke(
        app,
        [
            "account",
            "login",
            "--client-id",
            "my-client-id",
            "--client-secret",
            "my-client-secret",
        ],
        env=_env(tmp_path),
    )

    assert result.exit_code == 0
    assert "Credentials stored in system keyring." in result.stdout
    assert observed["client_id"] == "my-client-id"
    assert observed["client_secret"] == "my-client-secret"


def test_account_login_stores_item_id_in_config(tmp_path: Path, monkeypatch) -> None:
    """arcter account login --item-id writes pluggy.item_id to config."""

    def fake_store_credentials(client_id: str, client_secret: str) -> None:
        pass

    monkeypatch.setattr(
        "arcter.cli.credentials.store_credentials", fake_store_credentials
    )

    result = runner.invoke(
        app,
        [
            "account",
            "login",
            "--client-id",
            "cid",
            "--client-secret",
            "csecret",
            "--item-id",
            "item-123",
        ],
        env=_env(tmp_path),
    )

    assert result.exit_code == 0
    assert "Credentials stored in system keyring." in result.stdout
    assert "Set pluggy.item_id = item-123" in result.stdout

    config_file = tmp_path / "arcter" / "config.toml"
    assert config_file.exists()
    content = config_file.read_text(encoding="utf-8")
    assert "item-123" in content


def test_account_login_prompts_interactively(tmp_path: Path, monkeypatch) -> None:
    """When flags are omitted, login prompts for credentials."""
    observed: dict[str, str] = {}

    def fake_store_credentials(client_id: str, client_secret: str) -> None:
        observed["client_id"] = client_id
        observed["client_secret"] = client_secret

    monkeypatch.setattr(
        "arcter.cli.credentials.store_credentials", fake_store_credentials
    )

    result = runner.invoke(
        app,
        ["account", "login"],
        input="prompted-id\nprompted-secret\n",
        env=_env(tmp_path),
    )

    assert result.exit_code == 0
    assert "Credentials stored in system keyring." in result.stdout
    assert observed["client_id"] == "prompted-id"
    assert observed["client_secret"] == "prompted-secret"


def test_account_login_rejects_empty_credentials(tmp_path: Path) -> None:
    """Empty client ID or secret causes exit code 1."""
    result = runner.invoke(
        app,
        [
            "account",
            "login",
            "--client-id",
            "  ",
            "--client-secret",
            "secret",
        ],
        env=_env(tmp_path),
    )
    output = f"{result.stdout}{result.stderr}"

    assert result.exit_code == 1
    assert "must not be empty" in output


def test_account_login_fails_on_keyring_error(tmp_path: Path, monkeypatch) -> None:
    """CredentialError during store causes exit code 1."""
    from arcter.credentials import CredentialError

    def fake_store_credentials(client_id: str, client_secret: str) -> None:
        raise CredentialError("Failed to store credentials in system keyring: locked")

    monkeypatch.setattr(
        "arcter.cli.credentials.store_credentials", fake_store_credentials
    )

    result = runner.invoke(
        app,
        [
            "account",
            "login",
            "--client-id",
            "cid",
            "--client-secret",
            "csecret",
        ],
        env=_env(tmp_path),
    )
    output = f"{result.stdout}{result.stderr}"

    assert result.exit_code == 1
    assert "Failed to store credentials" in output


def test_account_logout_clears_credentials(tmp_path: Path, monkeypatch) -> None:
    """arcter account logout calls delete_credentials and reports success."""

    def fake_delete_credentials() -> bool:
        return True

    monkeypatch.setattr(
        "arcter.cli.credentials.delete_credentials", fake_delete_credentials
    )

    result = runner.invoke(app, ["account", "logout"], env=_env(tmp_path))

    assert result.exit_code == 0
    assert "Credentials removed from system keyring." in result.stdout


def test_account_logout_reports_when_no_credentials_found(
    tmp_path: Path, monkeypatch
) -> None:
    """When no credentials exist, logout reports that."""

    def fake_delete_credentials() -> bool:
        return False

    monkeypatch.setattr(
        "arcter.cli.credentials.delete_credentials", fake_delete_credentials
    )

    result = runner.invoke(app, ["account", "logout"], env=_env(tmp_path))

    assert result.exit_code == 0
    assert "No credentials found in system keyring." in result.stdout
