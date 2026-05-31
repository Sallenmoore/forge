# tests/cli/test_main.py
import sys

from click.testing import CliRunner

from forge.cli.main import cli
from forge.cli.main import main as cli_main
from forge.errors import NotFoundError


def test_forge_no_args_prints_help_exits_0():
    result = CliRunner().invoke(cli, [])
    assert result.exit_code == 0
    assert "forge" in result.output.lower()


def test_forge_help_flag():
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Usage" in result.output


def test_forge_version_flag():
    from forge import __version__

    result = CliRunner().invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "forge" in result.output
    assert __version__ in result.output


def test_unknown_subcommand_exits_2():
    result = CliRunner().invoke(cli, ["wat"])
    assert result.exit_code == 2


def test_main_handles_forge_error_with_label_and_exit_code(monkeypatch, capsys):
    # Inject a fake command that raises NotFoundError
    from forge.cli.main import cli as cli_group

    @cli_group.command("_boom")
    def _boom():
        raise NotFoundError("fake")

    try:
        monkeypatch.setattr(sys, "argv", ["forge", "_boom"])
        exit_code = cli_main()
        assert exit_code == 3   # NotFoundError.code
        captured = capsys.readouterr()
        assert "not found" in captured.err
        assert "(3)" in captured.err
        assert "fake" in captured.err
    finally:
        # Clean up so the _boom command doesn't leak to other tests
        del cli_group.commands["_boom"]


def test_debug_flag_threads_through_to_client(capsys, monkeypatch):
    """--debug at top level surfaces in client HTTP logging."""
    import httpx
    from click.testing import CliRunner
    from forge.cli.main import cli

    captured_clients = []

    def fake_transport_factory():
        def dispatch(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "number": 1, "title": "x", "state": "open", "merged": False,
                "draft": False, "user": {"login": "u"},
                "head": {"ref": "h", "sha": "s"}, "base": {"ref": "b"},
                "created_at": "t", "html_url": "u", "labels": [],
            })
        return httpx.MockTransport(dispatch)

    from forge import client as client_mod
    orig = client_mod.ForgejoClient.__init__
    def patched(self, *, host, token, transport=None, timeout=10.0, debug=False):
        captured_clients.append(debug)
        orig(self, host=host, token=token,
             transport=fake_transport_factory(), timeout=timeout, debug=debug)
    monkeypatch.setattr(client_mod.ForgejoClient, "__init__", patched)
    monkeypatch.setenv("FORGEJO_TOKEN", "test-token")

    runner = CliRunner()
    result = runner.invoke(cli, ["--debug", "pr", "view", "1", "-R", "o/r"])
    assert result.exit_code == 0, result.output
    assert captured_clients == [True]
