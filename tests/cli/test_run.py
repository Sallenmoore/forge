import json as _json

import httpx
from click.testing import CliRunner

from forge.cli.main import cli


def _patch_client_with(monkeypatch, mock_transport):
    from forge import client as client_mod
    orig = client_mod.ForgejoClient.__init__
    def patched(self, *, host, token, transport=None, timeout=10.0, debug=False):
        orig(self, host=host, token=token,
             transport=mock_transport.transport(), timeout=timeout, debug=debug)
    monkeypatch.setattr(client_mod.ForgejoClient, "__init__", patched)


SAMPLE = {
    "workflow_runs": [
        {
            "id": 161, "run_number": 17, "name": "test (3.13)",
            "display_title": "release 0.1.1", "head_branch": "v0.1.1",
            "head_sha": "7637ea6", "status": "success", "event": "push",
            "url": "https://x/runs/17", "created_at": "2026-05-26T18:48:21-04:00",
            "run_started_at": "2026-05-26T18:48:21-04:00",
            "updated_at": "2026-05-26T18:49:05-04:00", "workflow_id": "test.yml",
        },
        {
            "id": 120, "run_number": 7, "name": "test (3.12)",
            "display_title": "docs", "head_branch": "main",
            "head_sha": "7bae1f9", "status": "failure", "event": "push",
            "url": "https://x/runs/7", "created_at": "2026-05-26T17:00:00-04:00",
            "run_started_at": "2026-05-26T17:00:00-04:00",
            "updated_at": "2026-05-26T17:01:00-04:00", "workflow_id": "test.yml",
        },
    ],
    "total_count": 2,
}


def test_run_list_table_default(monkeypatch, mock_transport):
    mock_transport.handler = lambda request: httpx.Response(200, json=SAMPLE)
    _patch_client_with(monkeypatch, mock_transport)
    monkeypatch.setenv("FORGEJO_TOKEN", "tok")

    result = CliRunner().invoke(cli, ["run", "list", "-R", "o/r"])
    assert result.exit_code == 0, result.output
    out = result.output
    assert "161" in out and "17" in out and "success" in out
    assert "120" in out and "7" in out and "failure" in out


def test_run_list_filter_by_status(monkeypatch, mock_transport):
    mock_transport.handler = lambda request: httpx.Response(200, json=SAMPLE)
    _patch_client_with(monkeypatch, mock_transport)
    monkeypatch.setenv("FORGEJO_TOKEN", "tok")

    result = CliRunner().invoke(
        cli, ["run", "list", "-R", "o/r", "--status", "failure"])
    assert result.exit_code == 0, result.output
    assert "120" in result.output
    assert "161" not in result.output


def test_run_list_filter_by_branch(monkeypatch, mock_transport):
    mock_transport.handler = lambda request: httpx.Response(200, json=SAMPLE)
    _patch_client_with(monkeypatch, mock_transport)
    monkeypatch.setenv("FORGEJO_TOKEN", "tok")

    result = CliRunner().invoke(
        cli, ["run", "list", "-R", "o/r", "--branch", "main"])
    assert result.exit_code == 0
    assert "120" in result.output
    assert "161" not in result.output


def test_run_list_json_emits_camelcase(monkeypatch, mock_transport):
    mock_transport.handler = lambda request: httpx.Response(200, json=SAMPLE)
    _patch_client_with(monkeypatch, mock_transport)
    monkeypatch.setenv("FORGEJO_TOKEN", "tok")

    result = CliRunner().invoke(
        cli, ["run", "list", "-R", "o/r", "--json", "id,status,headBranch", "--limit", "5"])
    assert result.exit_code == 0, result.output
    rows = _json.loads(result.output)
    assert isinstance(rows, list)
    assert {r["id"] for r in rows} == {161, 120}
    for r in rows:
        assert set(r.keys()) == {"id", "status", "headBranch"}


def test_run_list_unknown_json_field_exits_2(monkeypatch, mock_transport):
    mock_transport.handler = lambda request: httpx.Response(200, json=SAMPLE)
    _patch_client_with(monkeypatch, mock_transport)
    monkeypatch.setenv("FORGEJO_TOKEN", "tok")

    result = CliRunner().invoke(
        cli, ["run", "list", "-R", "o/r", "--json", "nope"])
    assert result.exit_code == 2
    assert "unknown field" in result.output.lower()


def test_run_list_limit_caps_at_50(monkeypatch, mock_transport):
    seen = {}
    def handler(request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=SAMPLE)
    mock_transport.handler = handler
    _patch_client_with(monkeypatch, mock_transport)
    monkeypatch.setenv("FORGEJO_TOKEN", "tok")

    result = CliRunner().invoke(
        cli, ["run", "list", "-R", "o/r", "--limit", "100"])
    assert result.exit_code == 0
    assert seen["params"]["limit"] == "50"


def test_run_log_dumps_decompressed_log(monkeypatch):
    """run log <id> --container forgejo prints decompressed log text."""
    from click.testing import CliRunner

    from forge import logs
    from forge.cli.main import cli

    sample = "ts1 line 1\nts2 line 2\n"
    monkeypatch.setattr(logs, "fetch_log",
                        lambda *, container, owner, repo, task_id, **kwargs: sample)
    monkeypatch.setenv("FORGEJO_TOKEN", "tok")

    result = CliRunner().invoke(
        cli, ["run", "log", "120", "-R", "o/r", "--container", "forgejo"])
    assert result.exit_code == 0, result.output
    assert result.output == sample


def test_run_log_no_container_exits_6(monkeypatch):
    from click.testing import CliRunner

    from forge.cli.main import cli
    monkeypatch.delenv("FORGEJO_CONTAINER", raising=False)
    monkeypatch.setenv("FORGEJO_TOKEN", "tok")

    result = CliRunner().invoke(
        cli, ["run", "log", "120", "-R", "o/r"])
    assert result.exit_code == 6
    assert "container exec" in result.output.lower()


def test_run_log_env_var_picked_up(monkeypatch):
    from click.testing import CliRunner

    from forge import logs
    from forge.cli.main import cli

    seen = {}
    def fake_fetch_log(*, container, owner, repo, task_id, **kwargs):
        seen["container"] = container
        return "ok\n"
    monkeypatch.setattr(logs, "fetch_log", fake_fetch_log)
    monkeypatch.setenv("FORGEJO_TOKEN", "tok")
    monkeypatch.setenv("FORGEJO_CONTAINER", "fj-env")

    result = CliRunner().invoke(
        cli, ["run", "log", "120", "-R", "o/r"])
    assert result.exit_code == 0, result.output
    assert seen["container"] == "fj-env"


def test_run_log_missing_file_exits_3(monkeypatch):
    from click.testing import CliRunner

    from forge import logs
    from forge.cli.main import cli
    from forge.errors import NotFoundError

    def raiser(*, container, owner, repo, task_id, **kwargs):
        raise NotFoundError(
            f"no log on disk for run {task_id} (probably succeeded — "
            f"Forgejo only retains failed-run logs)")
    monkeypatch.setattr(logs, "fetch_log", raiser)
    monkeypatch.setenv("FORGEJO_TOKEN", "tok")

    result = CliRunner().invoke(
        cli, ["run", "log", "161", "-R", "o/r", "--container", "forgejo"])
    assert result.exit_code == 3
    assert "no log on disk" in result.output
