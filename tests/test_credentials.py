import pytest

from arcter import credentials


def test_store_credentials_calls_keyring(monkeypatch) -> None:
    """Verify store_credentials writes both keys to keyring."""
    observed: list[tuple[str, str, str]] = []

    def fake_set_password(service: str, key: str, value: str) -> None:
        observed.append((service, key, value))

    monkeypatch.setattr("keyring.set_password", fake_set_password)

    credentials.store_credentials("my-client-id", "my-client-secret")

    assert len(observed) == 2
    assert (
        credentials.SERVICE_NAME,
        credentials._KEY_CLIENT_ID,
        "my-client-id",
    ) in observed
    assert (
        credentials.SERVICE_NAME,
        credentials._KEY_CLIENT_SECRET,
        "my-client-secret",
    ) in observed


def test_load_credentials_returns_tuple_when_both_found(monkeypatch) -> None:
    """When both keys exist in keyring, return (client_id, client_secret)."""
    store = {
        credentials._KEY_CLIENT_ID: "cid",
        credentials._KEY_CLIENT_SECRET: "csecret",
    }

    def fake_get_password(service: str, key: str) -> str | None:
        return store.get(key)

    monkeypatch.setattr("keyring.get_password", fake_get_password)

    result = credentials.load_credentials()
    assert result == ("cid", "csecret")


def test_load_credentials_returns_none_when_missing(monkeypatch) -> None:
    """When one or both keys are missing, return None."""

    def fake_get_password(service: str, key: str) -> str | None:
        return None

    monkeypatch.setattr("keyring.get_password", fake_get_password)

    result = credentials.load_credentials()
    assert result is None


def test_load_credentials_returns_none_on_keyring_error(monkeypatch) -> None:
    """On KeyringError, return None (graceful degradation)."""
    from keyring.errors import KeyringError

    def fake_get_password(service: str, key: str) -> str | None:
        raise KeyringError("backend unavailable")

    monkeypatch.setattr("keyring.get_password", fake_get_password)

    result = credentials.load_credentials()
    assert result is None


def test_load_credentials_returns_none_when_values_are_empty(monkeypatch) -> None:
    """When keyring returns empty strings, treat as missing."""

    def fake_get_password(service: str, key: str) -> str | None:
        return "  "

    monkeypatch.setattr("keyring.get_password", fake_get_password)

    result = credentials.load_credentials()
    assert result is None


def test_delete_credentials_returns_true_when_deleted(monkeypatch) -> None:
    """When keys exist and are deleted, return True."""
    deleted: list[str] = []

    def fake_delete_password(service: str, key: str) -> None:
        deleted.append(key)

    monkeypatch.setattr("keyring.delete_password", fake_delete_password)

    result = credentials.delete_credentials()
    assert result is True
    assert credentials._KEY_CLIENT_ID in deleted
    assert credentials._KEY_CLIENT_SECRET in deleted


def test_delete_credentials_returns_false_when_not_found(monkeypatch) -> None:
    """When neither key exists, return False."""
    from keyring.errors import PasswordDeleteError

    def fake_delete_password(service: str, key: str) -> None:
        raise PasswordDeleteError(f"No password for {key}")

    monkeypatch.setattr("keyring.delete_password", fake_delete_password)

    result = credentials.delete_credentials()
    assert result is False


def test_store_credentials_wraps_keyring_error(monkeypatch) -> None:
    """KeyringError during store is wrapped in CredentialError."""
    from keyring.errors import KeyringError

    def fake_set_password(service: str, key: str, value: str) -> None:
        raise KeyringError("locked keyring")

    monkeypatch.setattr("keyring.set_password", fake_set_password)

    with pytest.raises(
        credentials.CredentialError, match="Failed to store credentials"
    ):
        credentials.store_credentials("id", "secret")
