from decimal import Decimal

import pytest

import arcter.pluggy as pluggy


def test_list_item_balances_filters_and_parses_accounts(monkeypatch) -> None:
    observed: dict[str, object] = {}

    def fake_request_json(
        method: str,
        path: str,
        headers: dict[str, str],
        operation: str,
        json_payload: dict[str, object] | None = None,
        params: dict[str, object] | None = None,
    ) -> object:
        observed["method"] = method
        observed["path"] = path
        observed["headers"] = headers
        observed["operation"] = operation
        observed["json_payload"] = json_payload
        observed["params"] = params
        return {
            "results": [
                {
                    "type": "BANK",
                    "name": "Main account",
                    "currencyCode": "BRL",
                    "balance": "100.25",
                },
                {
                    "type": "CREDIT",
                    "name": "Travel card",
                    "currencyCode": "usd",
                    "balance": -20,
                },
                {
                    "type": "LOAN",
                    "name": "Loan account",
                    "currencyCode": "BRL",
                    "balance": "1000.00",
                },
                {
                    "type": "BANK",
                    "name": "",
                    "currencyCode": "",
                    "balance": "not-a-number",
                },
            ]
        }

    monkeypatch.setattr(pluggy, "_request_json", fake_request_json)

    rows = pluggy.list_item_balances(item_id="item-id", api_key="api-key")

    assert observed["method"] == "GET"
    assert observed["path"] == "/accounts"
    assert observed["operation"] == "accounts list"
    assert observed["json_payload"] is None
    assert observed["params"] == {"itemId": "item-id"}

    headers = observed["headers"]
    assert isinstance(headers, dict)
    assert headers["X-API-KEY"] == "api-key"
    assert headers["accept"] == "application/json"

    assert rows == [
        pluggy.BalanceRow(
            type="BANK",
            name="Main account",
            balance=Decimal("100.25"),
            currency_code="BRL",
        ),
        pluggy.BalanceRow(
            type="CREDIT",
            name="Travel card",
            balance=Decimal("-20"),
            currency_code="USD",
        ),
        pluggy.BalanceRow(
            type="BANK",
            name="Unnamed account",
            balance=None,
            currency_code="N/A",
        ),
    ]


def test_list_item_balances_raises_on_invalid_payload(monkeypatch) -> None:
    def fake_request_json(
        method: str,
        path: str,
        headers: dict[str, str],
        operation: str,
        json_payload: dict[str, object] | None = None,
        params: dict[str, object] | None = None,
    ) -> object:
        return {"results": "invalid"}

    monkeypatch.setattr(pluggy, "_request_json", fake_request_json)

    with pytest.raises(pluggy.PluggyError, match="invalid payload format"):
        pluggy.list_item_balances(item_id="item-id", api_key="api-key")


def test_list_item_balances_with_env_uses_env_item_id(monkeypatch) -> None:
    observed: dict[str, str] = {}

    def fake_authenticate(client_id: str, client_secret: str) -> str:
        observed["client_id"] = client_id
        observed["client_secret"] = client_secret
        return "api-key"

    def fake_list_item_balances(item_id: str, api_key: str) -> list[pluggy.BalanceRow]:
        observed["item_id"] = item_id
        observed["api_key"] = api_key
        return []

    monkeypatch.setattr(pluggy, "authenticate", fake_authenticate)
    monkeypatch.setattr(pluggy, "list_item_balances", fake_list_item_balances)

    rows = pluggy.list_item_balances_with_env(
        item_id=None,
        env={
            "PLUGGY_CLIENT_ID": "client-id",
            "PLUGGY_CLIENT_SECRET": "client-secret",
            "PLUGGY_ITEM_ID": "item-from-env",
        },
    )

    assert rows == []
    assert observed == {
        "client_id": "client-id",
        "client_secret": "client-secret",
        "item_id": "item-from-env",
        "api_key": "api-key",
    }


def test_list_item_balances_with_env_prefers_arg_item_id(monkeypatch) -> None:
    observed: dict[str, str] = {}

    def fake_authenticate(client_id: str, client_secret: str) -> str:
        return "api-key"

    def fake_list_item_balances(item_id: str, api_key: str) -> list[pluggy.BalanceRow]:
        observed["item_id"] = item_id
        observed["api_key"] = api_key
        return []

    monkeypatch.setattr(pluggy, "authenticate", fake_authenticate)
    monkeypatch.setattr(pluggy, "list_item_balances", fake_list_item_balances)

    rows = pluggy.list_item_balances_with_env(
        item_id="item-from-arg",
        env={
            "PLUGGY_CLIENT_ID": "client-id",
            "PLUGGY_CLIENT_SECRET": "client-secret",
            "PLUGGY_ITEM_ID": "item-from-env",
        },
    )

    assert rows == []
    assert observed["item_id"] == "item-from-arg"


def test_list_item_credit_cards_parses_credit_data(monkeypatch) -> None:
    observed: dict[str, object] = {}

    def fake_request_json(
        method: str,
        path: str,
        headers: dict[str, str],
        operation: str,
        json_payload: dict[str, object] | None = None,
        params: dict[str, object] | None = None,
    ) -> object:
        observed["method"] = method
        observed["path"] = path
        observed["headers"] = headers
        observed["operation"] = operation
        observed["json_payload"] = json_payload
        observed["params"] = params
        return {
            "results": [
                {
                    "type": "BANK",
                    "name": "Main account",
                    "currencyCode": "BRL",
                    "balance": "100.25",
                },
                {
                    "type": "CREDIT",
                    "name": "Itau Uniclass",
                    "number": "1234",
                    "balance": "142.41",
                    "currencyCode": "BRL",
                    "creditData": {
                        "level": "PLATINUM",
                        "brand": "MASTERCARD",
                        "balanceDueDate": "2020-07-17",
                        "availableCreditLimit": 51300,
                        "creditLimit": 51800,
                        "minimumPayment": 100,
                        "status": "ACTIVE",
                        "holderType": "MAIN",
                    },
                },
                {
                    "type": "CREDIT",
                    "name": "Travel card",
                    "number": "****9876",
                    "balance": -20,
                    "currencyCode": "usd",
                    "creditData": {
                        "level": "GOLD",
                        "brand": "VISA",
                        "balanceDueDate": "2025-01-01",
                        "availableCreditLimit": "700.25",
                        "creditLimit": "1000.50",
                        "minimumPayment": "10.1",
                        "status": "BLOCKED",
                        "holderType": "ADDITIONAL",
                    },
                },
            ]
        }

    monkeypatch.setattr(pluggy, "_request_json", fake_request_json)

    rows = pluggy.list_item_credit_cards(item_id="item-id", api_key="api-key")

    assert observed["method"] == "GET"
    assert observed["path"] == "/accounts"
    assert observed["operation"] == "accounts list"
    assert observed["json_payload"] is None
    assert observed["params"] == {"itemId": "item-id"}

    headers = observed["headers"]
    assert isinstance(headers, dict)
    assert headers["X-API-KEY"] == "api-key"
    assert headers["accept"] == "application/json"

    assert rows == [
        pluggy.CreditCardRow(
            name="Itau Uniclass",
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
        ),
        pluggy.CreditCardRow(
            name="Travel card",
            number="9876",
            balance=Decimal("-20"),
            currency_code="USD",
            credit_limit=Decimal("1000.50"),
            available_credit_limit=Decimal("700.25"),
            balance_due_date="2025-01-01",
            minimum_payment=Decimal("10.1"),
            brand="VISA",
            level="GOLD",
            status="BLOCKED",
            holder_type="ADDITIONAL",
        ),
    ]


def test_list_item_credit_cards_handles_missing_credit_data(monkeypatch) -> None:
    def fake_request_json(
        method: str,
        path: str,
        headers: dict[str, str],
        operation: str,
        json_payload: dict[str, object] | None = None,
        params: dict[str, object] | None = None,
    ) -> object:
        return {
            "results": [
                {
                    "type": "CREDIT",
                    "name": "No details card",
                    "number": "1234",
                    "balance": "10.00",
                    "currencyCode": "BRL",
                }
            ]
        }

    monkeypatch.setattr(pluggy, "_request_json", fake_request_json)

    rows = pluggy.list_item_credit_cards(item_id="item-id", api_key="api-key")

    assert rows == [
        pluggy.CreditCardRow(
            name="No details card",
            number="1234",
            balance=Decimal("10.00"),
            currency_code="BRL",
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


def test_list_item_credit_cards_handles_non_dict_credit_data(monkeypatch) -> None:
    def fake_request_json(
        method: str,
        path: str,
        headers: dict[str, str],
        operation: str,
        json_payload: dict[str, object] | None = None,
        params: dict[str, object] | None = None,
    ) -> object:
        return {
            "results": [
                {
                    "type": "CREDIT",
                    "name": "Weird card",
                    "number": "4321",
                    "balance": "12.34",
                    "currencyCode": "BRL",
                    "creditData": "not-a-dict",
                }
            ]
        }

    monkeypatch.setattr(pluggy, "_request_json", fake_request_json)

    rows = pluggy.list_item_credit_cards(item_id="item-id", api_key="api-key")

    assert rows[0].name == "Weird card"
    assert rows[0].credit_limit is None
    assert rows[0].available_credit_limit is None
    assert rows[0].balance_due_date is None
    assert rows[0].minimum_payment is None
    assert rows[0].brand is None
    assert rows[0].level is None
    assert rows[0].status is None
    assert rows[0].holder_type is None


def test_list_item_credit_cards_filters_non_credit_accounts(monkeypatch) -> None:
    def fake_request_json(
        method: str,
        path: str,
        headers: dict[str, str],
        operation: str,
        json_payload: dict[str, object] | None = None,
        params: dict[str, object] | None = None,
    ) -> object:
        return {
            "results": [
                {"type": "BANK", "name": "Bank account", "currencyCode": "BRL"},
                {"type": "LOAN", "name": "Loan account", "currencyCode": "BRL"},
                {"type": "INVESTMENT", "name": "Brokerage", "currencyCode": "BRL"},
                {
                    "type": "CREDIT",
                    "name": "Credit card",
                    "currencyCode": "BRL",
                    "balance": "1.00",
                },
            ]
        }

    monkeypatch.setattr(pluggy, "_request_json", fake_request_json)

    rows = pluggy.list_item_credit_cards(item_id="item-id", api_key="api-key")

    assert len(rows) == 1
    assert rows[0].name == "Credit card"
