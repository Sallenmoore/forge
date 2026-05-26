# tests/conftest.py
import httpx
import pytest


@pytest.fixture
def mock_transport():
    """A handler-replaceable httpx.MockTransport. Tests register routes by
    assigning to `mock_transport.handler`."""
    class _MockTransportHolder:
        handler = None
        def transport(self):
            def dispatch(request: httpx.Request) -> httpx.Response:
                if self.handler is None:
                    raise RuntimeError("mock_transport.handler not set")
                return self.handler(request)
            return httpx.MockTransport(dispatch)
    return _MockTransportHolder()


@pytest.fixture
def env_no_token(monkeypatch):
    """Strip every forge-related env var so tests have a clean baseline.

    Includes the token sources (FORGEJO_TOKEN, FORGEJO_API_KEY) plus other
    forge-related vars (FORGEJO_HOST, FORGEJO_DEFAULT_REPO, FORGE_DEBUG)
    that downstream tests may want to control independently. The fixture
    name is kept narrow ('env_no_token') because callers most commonly
    use it to test auth precedence.
    """
    for var in ("FORGEJO_TOKEN", "FORGEJO_HOST", "FORGEJO_DEFAULT_REPO",
                "FORGEJO_API_KEY", "FORGE_DEBUG"):
        monkeypatch.delenv(var, raising=False)
