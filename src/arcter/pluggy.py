from collections.abc import Mapping
import json
import os
from typing import Any

import httpx

BASE_URL = "https://api.pluggy.ai"
DEFAULT_TIMEOUT_SECONDS = 15.0


class PluggyError(Exception):
    """Raised when Pluggy integration operations fail."""


def _sanitize(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip()


def resolve_item_id(
    item_id: str | None,
    env: Mapping[str, str] | None = None,
) -> str:
    env_vars = env or os.environ
    resolved_item_id = _sanitize(item_id) or _sanitize(env_vars.get("PLUGGY_ITEM_ID"))

    if not resolved_item_id:
        raise PluggyError(
            "Missing Pluggy item ID. Provide ITEM_ID argument or set PLUGGY_ITEM_ID."
        )

    return resolved_item_id


def resolve_credentials(
    env: Mapping[str, str] | None = None,
) -> tuple[str, str]:
    env_vars = env or os.environ
    client_id = _sanitize(env_vars.get("PLUGGY_CLIENT_ID"))
    client_secret = _sanitize(env_vars.get("PLUGGY_CLIENT_SECRET"))

    missing: list[str] = []
    if not client_id:
        missing.append("PLUGGY_CLIENT_ID")
    if not client_secret:
        missing.append("PLUGGY_CLIENT_SECRET")

    if missing:
        raise PluggyError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    return client_id, client_secret


def _format_http_error(operation: str, response: httpx.Response) -> str:
    detail = ""

    try:
        response_payload: Any = response.json()
    except ValueError:
        response_payload = response.text

    if isinstance(response_payload, dict):
        for candidate in ("message", "error", "detail", "title"):
            if candidate in response_payload and response_payload[candidate]:
                detail = str(response_payload[candidate])
                break

        if not detail:
            detail = json.dumps(response_payload)
    else:
        detail = str(response_payload).strip()

    if detail:
        return f"Pluggy {operation} failed with status {response.status_code}: {detail}"

    return f"Pluggy {operation} failed with status {response.status_code}."


def _request_json(
    method: str,
    path: str,
    headers: Mapping[str, str],
    operation: str,
    json_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_path = path if path.startswith("/") else f"/{path}"
    url = f"{BASE_URL}{normalized_path}"

    request_kwargs: dict[str, Any] = {
        "headers": dict(headers),
        "timeout": DEFAULT_TIMEOUT_SECONDS,
    }
    if json_payload is not None:
        request_kwargs["json"] = json_payload

    try:
        response = httpx.request(method, url, **request_kwargs)
    except httpx.TimeoutException as exc:
        raise PluggyError(
            f"Pluggy {operation} request timed out. Please try again."
        ) from exc
    except httpx.HTTPError as exc:
        raise PluggyError(f"Pluggy {operation} request failed: {exc}") from exc

    if not response.is_success:
        raise PluggyError(_format_http_error(operation, response))

    if response.status_code == 204 or not response.content:
        return {}

    try:
        return response.json()
    except ValueError as exc:
        raise PluggyError(
            f"Pluggy {operation} returned an invalid JSON response."
        ) from exc


def authenticate(client_id: str, client_secret: str) -> str:
    response_payload = _request_json(
        method="POST",
        path="/auth",
        headers={"accept": "application/json", "content-type": "application/json"},
        operation="auth",
        json_payload={"clientId": client_id, "clientSecret": client_secret},
    )

    api_key = response_payload.get("apiKey")
    if not isinstance(api_key, str) or not api_key.strip():
        raise PluggyError("Pluggy auth returned an invalid response: missing apiKey.")

    return api_key


def update_item(item_id: str, api_key: str) -> None:
    _request_json(
        method="PATCH",
        path=f"/items/{item_id}",
        headers={
            "accept": "application/json",
            "content-type": "application/json",
            "X-API-KEY": api_key,
        },
        operation="item update",
    )


def update_item_with_env(
    item_id: str | None,
    env: Mapping[str, str] | None = None,
) -> str:
    resolved_item_id = resolve_item_id(item_id, env=env)
    client_id, client_secret = resolve_credentials(env=env)
    api_key = authenticate(client_id, client_secret)
    update_item(resolved_item_id, api_key)
    return resolved_item_id
