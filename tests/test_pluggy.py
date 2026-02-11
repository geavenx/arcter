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
