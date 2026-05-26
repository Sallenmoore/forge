# src/forge/cli/main.py
import os
import sys
import traceback

import click

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


@click.group(invoke_without_command=True)
@click.option("--token", default=None, help="API token (overrides env and ~/.secrets)")
@click.option("--host", default=None, help="Forgejo instance URL")
@click.option("-R", "repo", default=None, help="owner/repo")
@click.option("--debug", is_flag=True, default=False,
              help="Print tracebacks + log HTTP requests to stderr")
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


def main() -> int:
    try:
        cli(standalone_mode=False)
        return 0
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
