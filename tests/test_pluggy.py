from decimal import Decimal

import pytest

import arcter.pluggy as pluggy


def _tx(
    amount: str,
    transaction_type: str,
    category: str | None,
    *,
    currency_code: str = "BRL",
) -> pluggy.TransactionRow:
    return pluggy.TransactionRow(
        date="2026-02-01",
        description="Transaction",
        amount=Decimal(amount),
        currency_code=currency_code,
        type=transaction_type,
        status="POSTED",
        category=category,
        account_name="Checking",
        account_type="BANK",
    )


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
    monkeypatch.setattr(pluggy, "_load_config_item_id", lambda: "")

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
    monkeypatch.setattr(pluggy, "_load_config_item_id", lambda: "")

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


def test_list_item_accounts_filters_bank_and_credit(monkeypatch) -> None:
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
        observed["operation"] = operation
        observed["json_payload"] = json_payload
        observed["params"] = params
        return {
            "results": [
                {"id": "bank-1", "name": "Checking", "type": "BANK"},
                {"id": "credit-1", "name": "Visa", "type": "CREDIT"},
                {"id": "loan-1", "name": "Loan", "type": "LOAN"},
                {"id": "bank-without-id", "name": "No Id", "type": "BANK"},
            ]
        }

    monkeypatch.setattr(pluggy, "_request_json", fake_request_json)

    rows = pluggy.list_item_accounts(item_id="item-id", api_key="api-key")

    assert observed["method"] == "GET"
    assert observed["path"] == "/accounts"
    assert observed["operation"] == "accounts list"
    assert observed["json_payload"] is None
    assert observed["params"] == {"itemId": "item-id"}
    assert rows == [
        {"id": "bank-1", "name": "Checking", "type": "BANK"},
        {"id": "credit-1", "name": "Visa", "type": "CREDIT"},
        {"id": "bank-without-id", "name": "No Id", "type": "BANK"},
    ]


def test_list_account_transactions_passes_date_params(monkeypatch) -> None:
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
        observed["operation"] = operation
        observed["json_payload"] = json_payload
        observed["params"] = params
        return {"totalPages": 1, "page": 1, "results": [{"id": "tx-1"}]}

    monkeypatch.setattr(pluggy, "_request_json", fake_request_json)

    rows = pluggy.list_account_transactions(
        account_id="account-id",
        api_key="api-key",
        date_from="2026-01-01",
        date_to="2026-01-31",
    )

    assert observed["method"] == "GET"
    assert observed["path"] == "/transactions"
    assert observed["operation"] == "transactions list"
    assert observed["json_payload"] is None
    assert observed["params"] == {
        "accountId": "account-id",
        "from": "2026-01-01",
        "to": "2026-01-31",
        "pageSize": 500,
        "page": 1,
    }
    assert rows == [{"id": "tx-1"}]


def test_list_account_transactions_handles_pagination(monkeypatch) -> None:
    observed_pages: list[int] = []

    def fake_request_json(
        method: str,
        path: str,
        headers: dict[str, str],
        operation: str,
        json_payload: dict[str, object] | None = None,
        params: dict[str, object] | None = None,
    ) -> object:
        assert method == "GET"
        assert path == "/transactions"
        assert operation == "transactions list"
        assert params is not None

        page = int(params.get("page", 1))
        observed_pages.append(page)
        if page == 1:
            return {
                "totalPages": 2,
                "page": 1,
                "results": [{"id": "tx-1"}, {"id": "tx-2"}],
            }
        return {"totalPages": 2, "page": 2, "results": [{"id": "tx-3"}]}

    monkeypatch.setattr(pluggy, "_request_json", fake_request_json)

    rows = pluggy.list_account_transactions(account_id="account-id", api_key="api-key")

    assert observed_pages == [1, 2]
    assert rows == [{"id": "tx-1"}, {"id": "tx-2"}, {"id": "tx-3"}]


def test_parse_transactions_extracts_fields() -> None:
    raw_transactions = [
        {
            "id": "tx-1",
            "description": " Grocery ",
            "amount": "150.5",
            "date": "2026-01-14T03:00:00.000Z",
            "currencyCode": "brl",
            "type": "debit",
            "status": "posted",
            "category": "Food",
        }
    ]

    rows = pluggy._parse_transactions(
        raw_transactions,
        account_name="Checking",
        account_type="BANK",
    )

    assert rows == [
        pluggy.TransactionRow(
            date="2026-01-14",
            description="Grocery",
            amount=Decimal("150.5"),
            currency_code="BRL",
            type="DEBIT",
            status="POSTED",
            category="Food",
            account_name="Checking",
            account_type="BANK",
        )
    ]


def test_parse_transactions_skips_unparseable_amounts() -> None:
    raw_transactions = [
        {
            "description": "Transfer",
            "amount": "not-a-number",
            "date": "2026-01-14T03:00:00.000Z",
            "currencyCode": "BRL",
            "type": "DEBIT",
            "status": "POSTED",
        },
        {
            "description": "Salary",
            "amount": "2000.00",
            "date": "2026-01-15T03:00:00.000Z",
            "currencyCode": "BRL",
            "type": "CREDIT",
            "status": "POSTED",
        },
    ]

    rows = pluggy._parse_transactions(
        raw_transactions,
        account_name="Checking",
        account_type="BANK",
    )

    assert len(rows) == 1
    assert rows[0].description == "Salary"
    assert rows[0].amount == Decimal("2000.00")


def test_parse_transactions_handles_missing_fields() -> None:
    raw_transactions = [
        {
            "amount": "99.90",
            "date": "",
            "currencyCode": "",
            "category": None,
            "description": "  ",
        }
    ]

    rows = pluggy._parse_transactions(
        raw_transactions,
        account_name="",
        account_type="",
    )

    assert rows == [
        pluggy.TransactionRow(
            date="Unknown",
            description="No description",
            amount=Decimal("99.90"),
            currency_code="N/A",
            type="DEBIT",
            status="POSTED",
            category=None,
            account_name="Unnamed account",
            account_type="BANK",
        )
    ]


def test_aggregate_by_category_groups_expenses() -> None:
    rows = [
        _tx("100.00", "DEBIT", "Food"),
        _tx("40.00", "DEBIT", "Food"),
        _tx("50.00", "DEBIT", "Transportation"),
        _tx("300.00", "CREDIT", "Salary"),
    ]

    summaries = pluggy.aggregate_by_category(rows, direction="expense")

    assert summaries == [
        pluggy.CategorySummary(
            category="Food",
            total=Decimal("140.00"),
            count=2,
            percentage=Decimal("73.7"),
        ),
        pluggy.CategorySummary(
            category="Transportation",
            total=Decimal("50.00"),
            count=1,
            percentage=Decimal("26.3"),
        ),
    ]


def test_aggregate_by_category_handles_uncategorized() -> None:
    rows = [
        _tx("30.00", "DEBIT", None),
        _tx("10.00", "DEBIT", " "),
    ]

    summaries = pluggy.aggregate_by_category(rows, direction="expense")

    assert summaries == [
        pluggy.CategorySummary(
            category="Uncategorized",
            total=Decimal("40.00"),
            count=2,
            percentage=Decimal("100.0"),
        )
    ]


def test_aggregate_by_category_filters_income() -> None:
    rows = [
        _tx("1000.00", "CREDIT", "Salary"),
        _tx("200.00", "DEBIT", "Food"),
        _tx("150.00", "CREDIT", "Side income"),
    ]

    summaries = pluggy.aggregate_by_category(rows, direction="income")

    assert summaries == [
        pluggy.CategorySummary(
            category="Salary",
            total=Decimal("1000.00"),
            count=1,
            percentage=Decimal("87.0"),
        ),
        pluggy.CategorySummary(
            category="Side income",
            total=Decimal("150.00"),
            count=1,
            percentage=Decimal("13.0"),
        ),
    ]


def test_aggregate_by_category_all_direction() -> None:
    rows = [
        _tx("100.00", "CREDIT", "Salary"),
        _tx("40.00", "DEBIT", "Food"),
        _tx("20.00", "DEBIT", "Transportation"),
    ]

    summaries = pluggy.aggregate_by_category(rows, direction="all")

    assert summaries == [
        pluggy.CategorySummary(
            category="Salary",
            total=Decimal("100.00"),
            count=1,
            percentage=Decimal("62.5"),
        ),
        pluggy.CategorySummary(
            category="Transportation",
            total=Decimal("-20.00"),
            count=1,
            percentage=Decimal("-12.5"),
        ),
        pluggy.CategorySummary(
            category="Food",
            total=Decimal("-40.00"),
            count=1,
            percentage=Decimal("-25.0"),
        ),
    ]


def test_aggregate_by_category_empty_transactions() -> None:
    assert pluggy.aggregate_by_category([], direction="expense") == []


def test_aggregate_by_category_single_category() -> None:
    rows = [
        _tx("10.00", "DEBIT", "Food"),
        _tx("20.00", "DEBIT", "Food"),
        _tx("5.00", "CREDIT", "Salary"),
    ]

    summaries = pluggy.aggregate_by_category(rows, direction="expense")

    assert summaries == [
        pluggy.CategorySummary(
            category="Food",
            total=Decimal("30.00"),
            count=2,
            percentage=Decimal("100.0"),
        )
    ]


def test_aggregate_by_category_percentages_sum_to_100() -> None:
    rows = [
        _tx("1.00", "DEBIT", "One"),
        _tx("1.00", "DEBIT", "Two"),
        _tx("1.00", "DEBIT", "Three"),
    ]

    summaries = pluggy.aggregate_by_category(rows, direction="expense")
    percentages_total = sum((summary.percentage for summary in summaries), Decimal("0"))

    assert abs(percentages_total - Decimal("100")) <= Decimal("0.2")


def test_list_item_transactions_with_env_filters_by_account_type(
    monkeypatch,
) -> None:
    observed: dict[str, object] = {"account_ids": []}

    def fake_authenticate(client_id: str, client_secret: str) -> str:
        observed["client_id"] = client_id
        observed["client_secret"] = client_secret
        return "api-key"

    def fake_list_item_accounts(item_id: str, api_key: str) -> list[dict[str, str]]:
        observed["item_id"] = item_id
        observed["api_key"] = api_key
        return [
            {"id": "bank-1", "name": "Checking", "type": "BANK"},
            {"id": "credit-1", "name": "Card", "type": "CREDIT"},
        ]

    def fake_list_account_transactions(
        account_id: str,
        api_key: str,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, object]]:
        observed_account_ids = observed["account_ids"]
        assert isinstance(observed_account_ids, list)
        observed_account_ids.append(account_id)

        if account_id == "bank-1":
            return [
                {
                    "description": "Salary",
                    "amount": "1000",
                    "date": "2026-01-15T00:00:00.000Z",
                    "currencyCode": "BRL",
                    "type": "CREDIT",
                    "status": "POSTED",
                }
            ]
        return [
            {
                "description": "Card charge",
                "amount": "100",
                "date": "2026-01-14T00:00:00.000Z",
                "currencyCode": "BRL",
                "type": "DEBIT",
                "status": "POSTED",
            }
        ]

    monkeypatch.setattr(pluggy, "authenticate", fake_authenticate)
    monkeypatch.setattr(pluggy, "list_item_accounts", fake_list_item_accounts)
    monkeypatch.setattr(
        pluggy, "list_account_transactions", fake_list_account_transactions
    )
    monkeypatch.setattr(pluggy, "_load_config_item_id", lambda: "")

    rows = pluggy.list_item_transactions_with_env(
        item_id=None,
        account_type_filter="BANK",
        env={
            "PLUGGY_CLIENT_ID": "client-id",
            "PLUGGY_CLIENT_SECRET": "client-secret",
            "PLUGGY_ITEM_ID": "item-from-env",
        },
    )

    assert observed["client_id"] == "client-id"
    assert observed["client_secret"] == "client-secret"
    assert observed["item_id"] == "item-from-env"
    assert observed["api_key"] == "api-key"
    assert observed["account_ids"] == ["bank-1"]
    assert len(rows) == 1
    assert rows[0].account_name == "Checking"
    assert rows[0].account_type == "BANK"


def test_resolve_credentials_falls_back_to_keyring(monkeypatch) -> None:
    """When env vars are missing, credentials come from keyring."""
    monkeypatch.setattr(
        pluggy.credentials, "load_credentials", lambda: ("kr-id", "kr-secret")
    )

    client_id, client_secret = pluggy.resolve_credentials(env={})

    assert client_id == "kr-id"
    assert client_secret == "kr-secret"


def test_resolve_credentials_prefers_env_over_keyring(monkeypatch) -> None:
    """Env vars take priority over keyring values."""
    monkeypatch.setattr(
        pluggy.credentials, "load_credentials", lambda: ("kr-id", "kr-secret")
    )

    client_id, client_secret = pluggy.resolve_credentials(
        env={"PLUGGY_CLIENT_ID": "env-id", "PLUGGY_CLIENT_SECRET": "env-secret"}
    )

    assert client_id == "env-id"
    assert client_secret == "env-secret"


def test_resolve_credentials_partial_env_override(monkeypatch) -> None:
    """One value from env, the other from keyring."""
    monkeypatch.setattr(
        pluggy.credentials, "load_credentials", lambda: ("kr-id", "kr-secret")
    )

    client_id, client_secret = pluggy.resolve_credentials(
        env={"PLUGGY_CLIENT_ID": "env-id"}
    )

    assert client_id == "env-id"
    assert client_secret == "kr-secret"


def test_resolve_item_id_falls_back_to_config() -> None:
    """When no arg or env var, config_item_id is used."""
    result = pluggy.resolve_item_id(
        item_id=None, env={}, config_item_id="config-item-id"
    )
    assert result == "config-item-id"


def test_resolve_item_id_prefers_env_over_config() -> None:
    """Env var takes priority over config_item_id."""
    result = pluggy.resolve_item_id(
        item_id=None,
        env={"PLUGGY_ITEM_ID": "env-item-id"},
        config_item_id="config-item-id",
    )
    assert result == "env-item-id"


def test_resolve_item_id_prefers_arg_over_everything() -> None:
    """CLI argument takes priority over env and config."""
    result = pluggy.resolve_item_id(
        item_id="arg-item-id",
        env={"PLUGGY_ITEM_ID": "env-item-id"},
        config_item_id="config-item-id",
    )
    assert result == "arg-item-id"


def test_resolve_item_id_raises_when_all_sources_empty() -> None:
    """Error message mentions all three sources when nothing is found."""
    with pytest.raises(pluggy.PluggyError, match="arcter config set pluggy.item_id"):
        pluggy.resolve_item_id(item_id=None, env={}, config_item_id="")
