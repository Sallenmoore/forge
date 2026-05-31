# tests/cli/test_issue.py
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
    monkeypatch.setattr("forge.cli.issue._build_client", fake_build)
    monkeypatch.setenv("FORGEJO_TOKEN", "t")


def test_issue_list_passes_type_issues_param(mock_transport, monkeypatch):
    _patch_client(monkeypatch, mock_transport)
    captured = {}
    def handler(r):
        captured["params"] = dict(r.url.params)
        forgejo_issue = json.loads((FIXTURES / "forgejo" / "issue.json").read_text())
        return httpx.Response(200, json=[forgejo_issue])
    mock_transport.handler = handler
    result = CliRunner().invoke(cli, ["issue", "list", "-R", "samoore/storyteller"])
    assert result.exit_code == 0
    assert captured["params"].get("type") == "issues"
    assert "42" in result.output


def test_issue_list_json_field_validation(mock_transport, monkeypatch):
    _patch_client(monkeypatch, mock_transport)
    mock_transport.handler = lambda r: httpx.Response(200, json=[])
    result = CliRunner().invoke(cli, ["issue", "list", "-R", "samoore/storyteller",
                                       "--json", "nope"])
    assert result.exit_code == 2
    assert "unknown field: nope" in result.output


def test_issue_view_prints_details(mock_transport, monkeypatch):
    _patch_client(monkeypatch, mock_transport)
    forgejo_issue = json.loads((FIXTURES / "forgejo" / "issue.json").read_text())
    mock_transport.handler = lambda r: httpx.Response(200, json=forgejo_issue)
    result = CliRunner().invoke(cli, ["issue", "view", "42", "-R", "samoore/storyteller"])
    assert result.exit_code == 0
    assert "Something broke" in result.output
    assert "OPEN" in result.output
    assert "samoore" in result.output


def test_issue_create_resolves_label_names_to_ids(mock_transport, monkeypatch):
    _patch_client(monkeypatch, mock_transport)
    captured = {}
    def handler(r):
        if r.url.path.endswith("/labels"):
            return httpx.Response(200, json=[
                {"id": 1, "name": "bug"},
                {"id": 2, "name": "enhancement"},
            ])
        captured["body"] = json.loads(r.content)
        return httpx.Response(201, json={
            "number": 43,
            "html_url": "https://git.stevenamoore.dev/o/r/issues/43",
        })
    mock_transport.handler = handler
    result = CliRunner().invoke(cli, [
        "issue", "create", "-R", "samoore/storyteller",
        "--title", "x", "--body", "y", "--label", "bug", "--label", "enhancement",
    ])
    assert result.exit_code == 0
    assert captured["body"]["title"] == "x"
    assert captured["body"]["body"] == "y"
    assert sorted(captured["body"]["labels"]) == [1, 2]  # integer IDs
    assert "/issues/43" in result.output


def test_issue_create_unknown_label_exits_2(mock_transport, monkeypatch):
    _patch_client(monkeypatch, mock_transport)
    mock_transport.handler = lambda r: httpx.Response(200, json=[
        {"id": 1, "name": "bug"},
    ])
    result = CliRunner().invoke(cli, [
        "issue", "create", "-R", "samoore/storyteller",
        "--title", "x", "--label", "made-up",
    ])
    assert result.exit_code == 2
    assert "label 'made-up' not found" in result.output


def test_issue_close_patches_state(mock_transport, monkeypatch):
    _patch_client(monkeypatch, mock_transport)
    captured = {}
    def handler(r):
        captured["method"] = r.method
        captured["body"] = json.loads(r.content)
        return httpx.Response(200, json={"state": "closed"})
    mock_transport.handler = handler
    result = CliRunner().invoke(cli, ["issue", "close", "42", "-R", "samoore/storyteller"])
    assert result.exit_code == 0
    assert captured["method"] == "PATCH"
    assert captured["body"] == {"state": "closed"}
    assert "closed" in result.output.lower()


def test_issue_comment_posts_to_comments_endpoint(mock_transport, monkeypatch):
    _patch_client(monkeypatch, mock_transport)
    captured = {}
    def handler(r):
        captured["path"] = r.url.path
        captured["body"] = json.loads(r.content)
        return httpx.Response(201, json={"html_url": "https://x/comments/9"})
    mock_transport.handler = handler
    result = CliRunner().invoke(cli, [
        "issue", "comment", "42", "-R", "samoore/storyteller", "--body", "ack"
    ])
    assert result.exit_code == 0
    assert captured["path"] == "/api/v1/repos/samoore/storyteller/issues/42/comments"
    assert captured["body"] == {"body": "ack"}
