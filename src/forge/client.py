# src/forge/client.py
import os
import re
import time
from pathlib import Path

import httpx

from forge.errors import AuthError, ForgeError, NotFoundError, ServerError, ValidationError

DEFAULT_HOST = "https://git.stevenamoore.dev"
DEFAULT_SECRETS_PATH = Path.home() / ".secrets" / "forgejo.env"


def discover_token(*, explicit: str | None, secrets_path: Path | None) -> str:
    if explicit is not None:
        return explicit
    env = os.environ.get("FORGEJO_TOKEN")
    if env:
        return env
    path = secrets_path if secrets_path is not None else DEFAULT_SECRETS_PATH
    if path.is_file():
        for line in path.read_text().splitlines():
            m = re.match(r"\s*FORGEJO_API_KEY\s*=\s*(\S+)", line)
            if m:
                return m.group(1).strip("'\"")
    raise AuthError(
        "no token found — pass --token, set FORGEJO_TOKEN, "
        "or put FORGEJO_API_KEY in ~/.secrets/forgejo.env"
    )


def _raise_for_response(resp: httpx.Response) -> None:
    if resp.is_success:
        return
    try:
        body = resp.json()
        msg = body.get("message", "")
        if "errors" in body:
            msg = f"{msg}: {'; '.join(body['errors'])}".strip(": ")
    except Exception:
        msg = resp.text.strip() or f"HTTP {resp.status_code}"
    code = resp.status_code
    if code == 404:
        raise NotFoundError(msg)
    if code in (401, 403):
        raise AuthError(msg)
    if code == 422:
        raise ValidationError(msg)
    if 500 <= code < 600:
        raise ServerError(f"{msg} (HTTP {code})")
    raise ForgeError(f"{msg} (HTTP {code})")


class ForgejoClient:
    def __init__(
        self,
        *,
        host: str = DEFAULT_HOST,
        token: str,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 10.0,
    ):
        self._host = host.rstrip("/")
        self._http = httpx.Client(
            base_url=f"{self._host}/api/v1",
            headers={"Authorization": f"token {token}",
                     "Accept": "application/json"},
            timeout=timeout,
            transport=transport,
        )

    def close(self) -> None:
        self._http.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
        retry_backoff: float = 1.0,
    ) -> dict | list | None:
        try:
            resp = self._http.request(method, path, json=json, params=params)
        except httpx.TimeoutException as e:
            if retry_backoff > 0:
                time.sleep(retry_backoff)
                resp = self._http.request(method, path, json=json, params=params)
            else:
                raise ServerError(f"timeout: {e}") from e
        if 500 <= resp.status_code < 600 and retry_backoff > 0:
            time.sleep(retry_backoff)
            resp = self._http.request(method, path, json=json, params=params)
        _raise_for_response(resp)
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    def get(self, path: str, **kwargs) -> dict | list | None:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, json: dict | None = None, **kwargs) -> dict | list | None:
        return self._request("POST", path, json=json, **kwargs)

    def patch(self, path: str, json: dict | None = None, **kwargs) -> dict | list | None:
        return self._request("PATCH", path, json=json, **kwargs)
