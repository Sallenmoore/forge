# tests/cli/test_pr.py
import json
from pathlib import Path

import httpx
from click.testing import CliRunner

from forge.cli.main import cli

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _patch_client(monkeypatch, mock_transport):
    from forge.client import ForgejoClient

    def fake_build(token, host, debug=False):
        return ForgejoClient(host=host or "https://git.stevenamoore.dev",
                            token="t", transport=mock_transport.transport(),
                            debug=debug)
    monkeypatch.setattr("forge.cli.pr._build_client", fake_build)
    monkeypatch.setenv("FORGEJO_TOKEN", "t")


def test_pr_list_default_output_is_tab_separated(mock_transport, monkeypatch):
    _patch_client(monkeypatch, mock_transport)
    forgejo_pr = json.loads((FIXTURES / "forgejo" / "pr.json").read_text())
    mock_transport.handler = lambda r: httpx.Response(200, json=[forgejo_pr])
    result = CliRunner().invoke(cli, ["pr", "list", "-R", "samoore/forge"])
    assert result.exit_code == 0
    cols = result.output.strip().split("\t")
    assert cols[0] == "7"            # number
    assert "Add forge CLI" in cols[1]
    assert "feat/forge" in cols[2]   # head ref
    assert "OPEN" in cols[3]         # state


def test_pr_list_json_flag_returns_translated_shape(mock_transport, monkeypatch):
    _patch_client(monkeypatch, mock_transport)
    forgejo_pr = json.loads((FIXTURES / "forgejo" / "pr.json").read_text())
    mock_transport.handler = lambda r: httpx.Response(200, json=[forgejo_pr])
    result = CliRunner().invoke(cli, ["pr", "list", "-R", "samoore/forge",
                                       "--json", "number,title,state"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == [{"number": 7, "title": "Add forge CLI", "state": "OPEN"}]


def test_pr_list_unknown_json_field_exits_2(mock_transport, monkeypatch):
    _patch_client(monkeypatch, mock_transport)
    mock_transport.handler = lambda r: httpx.Response(200, json=[])
    result = CliRunner().invoke(cli, ["pr", "list", "-R", "samoore/forge",
                                       "--json", "nope"])
    assert result.exit_code == 2
    assert "unknown field: nope" in result.output


def test_pr_view_prints_details(mock_transport, monkeypatch):
    _patch_client(monkeypatch, mock_transport)
    forgejo_pr = json.loads((FIXTURES / "forgejo" / "pr.json").read_text())
    mock_transport.handler = lambda r: httpx.Response(200, json=forgejo_pr)
    result = CliRunner().invoke(cli, ["pr", "view", "7", "-R", "samoore/forge"])
    assert result.exit_code == 0
    assert "Add forge CLI" in result.output
    assert "OPEN" in result.output
    assert "feat/forge" in result.output


def test_pr_view_404_exits_3(mock_transport, monkeypatch):
    _patch_client(monkeypatch, mock_transport)
    mock_transport.handler = lambda r: httpx.Response(404, json={"message": "not found"})
    result = CliRunner().invoke(cli, ["pr", "view", "999", "-R", "samoore/forge"])
    assert result.exit_code == 3


def test_pr_create_posts_payload_and_returns_url(mock_transport, monkeypatch):
    _patch_client(monkeypatch, mock_transport)
    captured = {}
    def handler(r):
        captured["method"] = r.method
        captured["path"] = r.url.path
        captured["body"] = json.loads(r.content)
        return httpx.Response(201, json={
            "number": 8, "html_url": "https://git.stevenamoore.dev/o/r/pulls/8",
            "title": "x", "state": "open", "merged": False, "draft": False,
            "user": {"login": "samoore"},
            "head": {"ref": "feat/x", "sha": "1"}, "base": {"ref": "main", "sha": "2"},
            "created_at": "2026-05-26T14:00:00Z", "labels": [],
        })
    mock_transport.handler = handler
    result = CliRunner().invoke(cli, [
        "pr", "create", "-R", "samoore/forge",
        "--title", "x", "--body", "y", "--base", "main", "--head", "feat/x",
    ])
    assert result.exit_code == 0
    assert captured["method"] == "POST"
    assert captured["body"] == {"title": "x", "body": "y", "base": "main", "head": "feat/x"}
    assert "/pulls/8" in result.output


def test_pr_merge_sends_capital_Do_field(mock_transport, monkeypatch):
    _patch_client(monkeypatch, mock_transport)
    captured = {}
    def handler(r):
        captured["body"] = json.loads(r.content)
        return httpx.Response(200, json={"merged": True})
    mock_transport.handler = handler
    result = CliRunner().invoke(cli, ["pr", "merge", "7", "-R", "samoore/forge"])
    assert result.exit_code == 0
    assert captured["body"] == {"Do": "merge"}  # capital D — Forgejo quirk
    assert "merged" in result.output.lower()


def test_pr_merge_with_squash(mock_transport, monkeypatch):
    _patch_client(monkeypatch, mock_transport)
    captured = {}
    def handler(r):
        captured["body"] = json.loads(r.content)
        return httpx.Response(200, json={})
    mock_transport.handler = handler
    result = CliRunner().invoke(cli, ["pr", "merge", "7", "-R", "samoore/forge", "--squash"])
    assert result.exit_code == 0
    assert captured["body"] == {"Do": "squash"}


def test_pr_checks_lists_combined_status(mock_transport, monkeypatch):
    _patch_client(monkeypatch, mock_transport)
    calls = []
    def handler(r):
        calls.append(r.url.path)
        if "/pulls/" in r.url.path:
            return httpx.Response(200, json={"head": {"sha": "abc123"}})
        return httpx.Response(200, json={
            "state": "failure",
            "statuses": [
                {"context": "build (3.12)", "status": "failure"},
                {"context": "build (3.13)", "status": "success"},
            ],
        })
    mock_transport.handler = handler
    result = CliRunner().invoke(cli, ["pr", "checks", "7", "-R", "samoore/forge"])
    assert result.exit_code == 0
    assert "build (3.12)" in result.output
    assert "failure" in result.output
    assert "build (3.13)" in result.output


def test_pr_comment_posts_to_issues_endpoint(mock_transport, monkeypatch):
    _patch_client(monkeypatch, mock_transport)
    captured = {}
    def handler(r):
        captured["path"] = r.url.path
        captured["body"] = json.loads(r.content)
        return httpx.Response(201, json={"html_url": "https://x/comments/1"})
    mock_transport.handler = handler
    result = CliRunner().invoke(cli, [
        "pr", "comment", "7", "-R", "samoore/forge", "--body", "Looks good"
    ])
    assert result.exit_code == 0
    assert captured["path"] == "/api/v1/repos/samoore/forge/issues/7/comments"
    assert captured["body"] == {"body": "Looks good"}


def test_pr_close_patches_state_closed(monkeypatch, mock_transport):
    """pr close N → PATCH /repos/o/r/pulls/N {state: closed}."""
    import httpx, json as _json
    from click.testing import CliRunner
    from forge.cli.main import cli

    seen = {}
    def handler(request):
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = _json.loads(request.content) if request.content else None
        return httpx.Response(200, json={"number": 5, "state": "closed"})

    mock_transport.handler = handler
    from forge import client as client_mod
    orig = client_mod.ForgejoClient.__init__
    def patched(self, *, host, token, transport=None, timeout=10.0, debug=False):
        orig(self, host=host, token=token,
             transport=mock_transport.transport(), timeout=timeout, debug=debug)
    monkeypatch.setattr(client_mod.ForgejoClient, "__init__", patched)
    monkeypatch.setenv("FORGEJO_TOKEN", "tok")

    result = CliRunner().invoke(cli, ["pr", "close", "5", "-R", "o/r"])
    assert result.exit_code == 0, result.output
    assert seen == {
        "method": "PATCH",
        "path": "/api/v1/repos/o/r/pulls/5",
        "body": {"state": "closed"},
    }
    assert "Closed PR #5" in result.output


def test_pr_reopen_patches_state_open(monkeypatch, mock_transport):
    """pr reopen N → PATCH state=open."""
    import httpx, json as _json
    from click.testing import CliRunner
    from forge.cli.main import cli

    seen = {}
    def handler(request):
        seen["body"] = _json.loads(request.content) if request.content else None
        return httpx.Response(200, json={"number": 5, "state": "open"})

    mock_transport.handler = handler
    from forge import client as client_mod
    orig = client_mod.ForgejoClient.__init__
    def patched(self, *, host, token, transport=None, timeout=10.0, debug=False):
        orig(self, host=host, token=token,
             transport=mock_transport.transport(), timeout=timeout, debug=debug)
    monkeypatch.setattr(client_mod.ForgejoClient, "__init__", patched)
    monkeypatch.setenv("FORGEJO_TOKEN", "tok")

    result = CliRunner().invoke(cli, ["pr", "reopen", "5", "-R", "o/r"])
    assert result.exit_code == 0, result.output
    assert seen["body"] == {"state": "open"}
    assert "Reopened PR #5" in result.output


def test_pr_close_404_exits_3(monkeypatch, mock_transport):
    import httpx
    from click.testing import CliRunner
    from forge.cli.main import cli

    mock_transport.handler = lambda request: httpx.Response(404, json={"message": "not found"})
    from forge import client as client_mod
    orig = client_mod.ForgejoClient.__init__
    def patched(self, *, host, token, transport=None, timeout=10.0, debug=False):
        orig(self, host=host, token=token,
             transport=mock_transport.transport(), timeout=timeout, debug=debug)
    monkeypatch.setattr(client_mod.ForgejoClient, "__init__", patched)
    monkeypatch.setenv("FORGEJO_TOKEN", "tok")

    result = CliRunner().invoke(cli, ["pr", "close", "9999", "-R", "o/r"])
    assert result.exit_code == 3
    assert "not found" in result.output
