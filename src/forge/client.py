# src/forge/client.py
import os
import re
from pathlib import Path

import httpx

from forge.errors import AuthError

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
