# tests/cli/test_label.py
import json
from pathlib import Path

import httpx
from click.testing import CliRunner

from forge.cli.main import cli
from tests.cli.test_issue import _label_page, _patch_client

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _serve_label(mock_transport):
    label = json.loads((FIXTURES / "forgejo" / "label.json").read_text())
    paths = []
    def handler(r):
        paths.append(r.url.path)
        return httpx.Response(200, json=_label_page(r, [label]))
    mock_transport.handler = handler
    return paths


def test_label_list_prints_name_description_color(mock_transport, monkeypatch):
    _patch_client(monkeypatch, mock_transport)
    paths = _serve_label(mock_transport)
    result = CliRunner().invoke(cli, ["label", "list", "-R", "samoore/storyteller"])
    assert result.exit_code == 0, result.output
    assert result.output == "bug\tSomething isn't working\t#d73a4a\n"
    assert paths[0] == "/api/v1/repos/samoore/storyteller/labels"


def test_label_list_json(mock_transport, monkeypatch):
    _patch_client(monkeypatch, mock_transport)
    _serve_label(mock_transport)
    result = CliRunner().invoke(cli, ["label", "list", "-R", "samoore/storyteller",
                                      "--json", "name,color"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == [{"name": "bug", "color": "d73a4a"}]


def test_label_list_rejects_unknown_json_field(mock_transport, monkeypatch):
    _patch_client(monkeypatch, mock_transport)
    _serve_label(mock_transport)
    result = CliRunner().invoke(cli, ["label", "list", "-R", "samoore/storyteller",
                                      "--json", "nope"])
    assert result.exit_code == 2
    assert "unknown field: nope" in result.output
