# src/forge/cli/main.py
import os
import sys
import traceback

import click

from forge import __version__
from forge.errors import ForgeError

_ERROR_LABELS = {
    "ForgeError":      "error",
    "UsageError":      "usage error",
    "NotFoundError":   "not found",
    "AuthError":       "auth failed",
    "ServerError":     "server error",
    "ValidationError": "validation error",
}


def _error_label(exc_type_name: str) -> str:
    return _ERROR_LABELS.get(exc_type_name, exc_type_name.replace("Error", "").lower() or "error")


class _ForgeGroup(click.Group):
    """A click.Group that converts ForgeError into a click Exit with the
    error's `.code` after printing the standard `forge: <label> (N): <msg>`
    line on stderr. This makes both `main()` and CliRunner-driven invocations
    surface the same exit code without each subcommand re-implementing it."""

    def invoke(self, ctx):
        try:
            return super().invoke(ctx)
        except ForgeError as e:
            click.echo(
                f"forge: {_error_label(type(e).__name__)} ({e.code}): {e}",
                err=True,
            )
            ctx.exit(e.code)


@click.group(cls=_ForgeGroup, invoke_without_command=True)
@click.version_option(
    version=__version__,
    prog_name="forge",
    message="%(prog)s, version %(version)s",
)
@click.option("--token", default=None, help="API token (overrides env and ~/.secrets)")
@click.option("--host", default=None, help="Forgejo instance URL")
@click.option("-R", "repo", default=None, help="owner/repo")
@click.option("--debug", is_flag=True, default=False,
              help=("Enable Python tracebacks on internal errors "
                    "(HTTP request logging coming in v0.2)"))
@click.pass_context
def cli(ctx, token, host, repo, debug):
    """gh-compatible CLI for self-hosted Forgejo."""
    ctx.ensure_object(dict)
    ctx.obj["token"] = token
    ctx.obj["host"] = host
    ctx.obj["repo"] = repo
    ctx.obj["debug"] = debug or os.environ.get("FORGE_DEBUG") == "1"
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# Deferred imports: subcommand modules don't import main.py, but main.py
# imports them. Keeping registration here makes main.py the single source of
# truth for "what subcommands does cli have", at the cost of non-top-of-file
# imports.
from forge.cli.auth import auth as _auth_group  # noqa: E402
from forge.cli.issue import issue as _issue_group  # noqa: E402
from forge.cli.pr import pr as _pr_group  # noqa: E402

cli.add_command(_auth_group)
cli.add_command(_pr_group)
cli.add_command(_issue_group)


def main() -> int:
    try:
        rv = cli(standalone_mode=False)
        # _ForgeGroup.invoke calls ctx.exit(code) for ForgeError, which click
        # translates into a return value (the exit code) in non-standalone
        # mode. Pass that through so the OS sees the right code.
        return rv if isinstance(rv, int) else 0
    except click.UsageError as e:
        click.echo(f"forge: usage error (2): {e.format_message()}", err=True)
        return 2
    except click.exceptions.Exit as e:
        return e.exit_code
    except ForgeError as e:
        click.echo(f"forge: {_error_label(type(e).__name__)} ({e.code}): {e}", err=True)
        return e.code
    except Exception as e:
        if os.environ.get("FORGE_DEBUG") == "1" or "--debug" in sys.argv:
            traceback.print_exc()
        click.echo(
            f"forge: internal error (1): {type(e).__name__}: {e} "
            f"— set FORGE_DEBUG=1 or pass --debug for traceback",
            err=True,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
