# tests/cli/test_pr.py
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
