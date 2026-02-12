from decimal import Decimal
from pathlib import Path

import pytest

from arcter.config import Config
from arcter.pluggy import TransactionRow


@pytest.fixture
def default_config() -> Config:
    """Standard Config used by most account CLI tests."""
    return Config(
        currency="BRL",
        salary=Decimal("200.00"),
        savings_goal=Decimal("500.00"),
    )


@pytest.fixture
def env(tmp_path: Path):
    """Factory for CLI test environment dicts with XDG_CONFIG_HOME isolation."""

    def _env(extra: dict[str, str] | None = None) -> dict[str, str]:
        result = {"XDG_CONFIG_HOME": str(tmp_path)}
        if extra:
            result.update(extra)
        return result

    return _env


@pytest.fixture
def stub_transactions(monkeypatch):
    """Factory that stubs list_item_transactions_with_env and returns the observed dict."""

    def _stub(transactions: list[TransactionRow]) -> dict[str, object]:
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
            return transactions

        monkeypatch.setattr(
            "arcter.commands.account.pluggy.list_item_transactions_with_env",
            fake_list_item_transactions_with_env,
        )
        return observed

    return _stub
