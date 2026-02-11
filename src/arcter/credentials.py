import keyring
from keyring.errors import KeyringError, PasswordDeleteError

SERVICE_NAME = "arcter"
_KEY_CLIENT_ID = "pluggy_client_id"
_KEY_CLIENT_SECRET = "pluggy_client_secret"


class CredentialError(Exception):
    """Raised when credential storage operations fail."""


def store_credentials(client_id: str, client_secret: str) -> None:
    try:
        keyring.set_password(SERVICE_NAME, _KEY_CLIENT_ID, client_id)
        keyring.set_password(SERVICE_NAME, _KEY_CLIENT_SECRET, client_secret)
    except KeyringError as exc:
        raise CredentialError(
            f"Failed to store credentials in system keyring: {exc}"
        ) from exc


def load_credentials() -> tuple[str, str] | None:
    try:
        client_id = keyring.get_password(SERVICE_NAME, _KEY_CLIENT_ID)
        client_secret = keyring.get_password(SERVICE_NAME, _KEY_CLIENT_SECRET)
    except KeyringError:
        return None

    normalized_client_id = client_id.strip() if isinstance(client_id, str) else ""
    normalized_client_secret = (
        client_secret.strip() if isinstance(client_secret, str) else ""
    )
    if normalized_client_id and normalized_client_secret:
        return normalized_client_id, normalized_client_secret

    return None


def delete_credentials() -> bool:
    removed = False

    try:
        keyring.delete_password(SERVICE_NAME, _KEY_CLIENT_ID)
        removed = True
    except PasswordDeleteError:
        pass
    except KeyringError as exc:
        raise CredentialError(
            f"Failed to delete credentials from system keyring: {exc}"
        ) from exc

    try:
        keyring.delete_password(SERVICE_NAME, _KEY_CLIENT_SECRET)
        removed = True
    except PasswordDeleteError:
        pass
    except KeyringError as exc:
        raise CredentialError(
            f"Failed to delete credentials from system keyring: {exc}"
        ) from exc

    return removed
