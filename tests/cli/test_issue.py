# tests/cli/test_issue.py
import json
from pathlib import Path

import httpx
from click.testing import CliRunner

from forge.cli.main import cli

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _patch_client(monkeypatch, mock_transport):
    from forge.client import ForgejoClient

    def fake_build(token, host):
        return ForgejoClient(host=host or "https://git.stevenamoore.dev",
                            token="t", transport=mock_transport.transport())
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
