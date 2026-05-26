# tests/test_client.py
import pytest

from forge.client import discover_token
from forge.errors import AuthError


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
