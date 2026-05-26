# tests/test_client.py
import httpx
import pytest

from forge.client import ForgejoClient, discover_token
from forge.errors import AuthError, NotFoundError, ServerError, ValidationError


def test_token_from_explicit_arg(env_no_token):
    assert discover_token(explicit="t-from-cli", secrets_path=None) == "t-from-cli"


def test_token_from_env(env_no_token, monkeypatch):
    monkeypatch.setenv("FORGEJO_TOKEN", "t-from-env")
    assert discover_token(explicit=None, secrets_path=None) == "t-from-env"


def test_token_from_secrets_file(env_no_token, tmp_path):
    f = tmp_path / "forgejo.env"
    f.write_text("FORGEJO_API_KEY=t-from-file\nOTHER=ignored\n")
    assert discover_token(explicit=None, secrets_path=f) == "t-from-file"


def test_token_explicit_beats_env(env_no_token, monkeypatch):
    monkeypatch.setenv("FORGEJO_TOKEN", "t-from-env")
    assert discover_token(explicit="t-cli", secrets_path=None) == "t-cli"


def test_no_token_raises_auth_error(env_no_token):
    with pytest.raises(AuthError, match="no token"):
        discover_token(explicit=None, secrets_path=None)


def _client_with_handler(mock_transport, handler):
    mock_transport.handler = handler
    return ForgejoClient(host="https://example.test", token="t",
                        transport=mock_transport.transport())


def test_get_returns_parsed_json(mock_transport):
    def handler(request):
        assert request.url.path == "/api/v1/repos/o/r/pulls/1"
        return httpx.Response(200, json={"number": 1, "title": "x"})
    client = _client_with_handler(mock_transport, handler)
    result = client.get("/repos/o/r/pulls/1")
    assert result == {"number": 1, "title": "x"}


def test_404_raises_not_found(mock_transport):
    mock_transport.handler = lambda r: httpx.Response(404, json={"message": "Not Found"})
    client = ForgejoClient(host="https://example.test", token="t",
                          transport=mock_transport.transport())
    with pytest.raises(NotFoundError, match="Not Found"):
        client.get("/repos/o/r/pulls/999")


def test_422_raises_validation_error(mock_transport):
    mock_transport.handler = lambda r: httpx.Response(422, json={"message": "invalid base/head"})
    client = ForgejoClient(host="https://example.test", token="t",
                          transport=mock_transport.transport())
    with pytest.raises(ValidationError, match="invalid base/head"):
        client.post("/repos/o/r/pulls", json={"base": "main", "head": "main"})


def test_500_retried_once_then_raises_server_error(mock_transport, monkeypatch):
    monkeypatch.setattr("forge.client.time.sleep", lambda _: None)
    calls = []
    def handler(r):
        calls.append(r)
        return httpx.Response(500, json={"message": "boom"})
    client = _client_with_handler(mock_transport, handler)
    with pytest.raises(ServerError, match="boom"):
        client.get("/anything")  # uses default retry_backoff=1.0
    assert len(calls) == 2


def test_4xx_not_retried(mock_transport):
    calls = []
    def handler(r):
        calls.append(r)
        return httpx.Response(404, json={"message": "nope"})
    client = _client_with_handler(mock_transport, handler)
    with pytest.raises(NotFoundError):
        client.get("/anything")
    assert len(calls) == 1
