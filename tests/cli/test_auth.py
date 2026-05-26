# tests/cli/test_auth.py
import httpx
from click.testing import CliRunner

from forge.cli.main import cli


def _stub_client(mock_transport, host):
    """Build a ForgejoClient with the mock transport injected."""
    from forge.client import ForgejoClient
    return ForgejoClient(host=host or "https://git.stevenamoore.dev",
                        token="t", transport=mock_transport.transport())


def test_auth_status_success(mock_transport, monkeypatch):
    monkeypatch.setenv("FORGEJO_TOKEN", "t")
    monkeypatch.setattr(
        "forge.cli.auth._build_client",
        lambda token, host: _stub_client(mock_transport, host)
    )
    def handler(r):
        assert r.url.path == "/api/v1/user"
        return httpx.Response(200, json={"login": "samoore"})
    mock_transport.handler = handler
    result = CliRunner().invoke(cli, ["auth", "status"])
    assert result.exit_code == 0
    assert "samoore" in result.output
    assert "git.stevenamoore.dev" in result.output


def test_auth_status_401_exits_4(mock_transport, monkeypatch):
    monkeypatch.setenv("FORGEJO_TOKEN", "bad")
    monkeypatch.setattr(
        "forge.cli.auth._build_client",
        lambda token, host: _stub_client(mock_transport, host)
    )
    mock_transport.handler = lambda r: httpx.Response(401, json={"message": "token rejected"})
    result = CliRunner().invoke(cli, ["auth", "status"])
    assert result.exit_code == 4
    assert "auth failed" in result.output  # _ERROR_LABELS["AuthError"] == "auth failed"
    assert "(4)" in result.output
    assert "token rejected" in result.output  # message from server propagates


def test_token_source_label_with_explicit_flag():
    """_token_source_label returns '--token flag' when ctx.obj['token'] is truthy."""
    from typing import ClassVar

    from forge.cli.auth import _token_source_label

    class FakeCtx:
        obj: ClassVar[dict] = {"token": "t-from-cli"}

    assert _token_source_label(FakeCtx()) == "--token flag"


def test_token_source_label_with_env_var(monkeypatch):
    """_token_source_label returns 'FORGEJO_TOKEN env var' when env is set and no flag."""
    from typing import ClassVar

    from forge.cli.auth import _token_source_label

    monkeypatch.setenv("FORGEJO_TOKEN", "t-from-env")

    class FakeCtx:
        obj: ClassVar[dict] = {"token": None}

    assert _token_source_label(FakeCtx()) == "FORGEJO_TOKEN env var"


def test_token_source_label_falls_back_to_secrets_file(env_no_token):
    """_token_source_label returns '~/.secrets/forgejo.env' when no flag and no env."""
    from typing import ClassVar

    from forge.cli.auth import _token_source_label

    class FakeCtx:
        obj: ClassVar[dict] = {"token": None}

    assert _token_source_label(FakeCtx()) == "~/.secrets/forgejo.env"


def test_build_client_with_env_token(env_no_token, monkeypatch):
    """_build_client end-to-end: env token + host parameter -> a ForgejoClient."""
    from forge.cli.auth import _build_client
    from forge.client import ForgejoClient

    monkeypatch.setenv("FORGEJO_TOKEN", "t-from-env")
    client = _build_client(token=None, host="https://example.test")
    try:
        assert isinstance(client, ForgejoClient)
        assert client._host == "https://example.test"
    finally:
        client.close()


def test_build_client_uses_FORGEJO_HOST_env(env_no_token, monkeypatch):
    """_build_client uses FORGEJO_HOST env when --host flag is absent."""
    from forge.cli.auth import _build_client
    monkeypatch.setenv("FORGEJO_HOST", "https://other.example")
    monkeypatch.setenv("FORGEJO_TOKEN", "t")
    client = _build_client(token=None, host=None)
    try:
        assert client._host == "https://other.example"
    finally:
        client.close()


def test_build_client_no_token_raises_auth_error(env_no_token):
    """_build_client surfaces discover_token's AuthError when no token sources available."""
    import pytest

    from forge.cli.auth import _build_client
    from forge.errors import AuthError

    with pytest.raises(AuthError, match="no token"):
        _build_client(token=None, host=None)


def test_auth_git_credential_get_prints_protocol(mock_transport, monkeypatch):
    monkeypatch.setenv("FORGEJO_TOKEN", "t-from-env")
    monkeypatch.setattr(
        "forge.cli.auth._build_client",
        lambda token, host: _stub_client(mock_transport, host)
    )
    mock_transport.handler = lambda r: httpx.Response(200, json={"login": "samoore"})
    result = CliRunner().invoke(
        cli, ["auth", "git-credential", "get"],
        input="host=git.stevenamoore.dev\nprotocol=https\n\n",
    )
    assert result.exit_code == 0
    assert "username=samoore" in result.output
    assert "password=t-from-env" in result.output


def test_auth_git_credential_store_is_noop(monkeypatch):
    monkeypatch.setenv("FORGEJO_TOKEN", "t")
    result = CliRunner().invoke(cli, ["auth", "git-credential", "store"],
                                input="host=git.stevenamoore.dev\nprotocol=https\n\n")
    assert result.exit_code == 0
    assert result.output == ""


def test_git_credential_get_no_token_exits_0_empty(env_no_token):
    """If no token is discoverable, exit 0 with empty stdout so git can fall through."""
    result = CliRunner().invoke(
        cli, ["auth", "git-credential", "get"],
        input="host=git.stevenamoore.dev\nprotocol=https\n\n",
    )
    assert result.exit_code == 0
    assert result.output == ""
