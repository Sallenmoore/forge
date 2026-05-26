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
