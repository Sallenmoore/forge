# src/forge/cli/auth.py
import os
import sys

import click

from forge.client import DEFAULT_HOST, ForgejoClient, discover_token
from forge.errors import AuthError


def _build_client(token: str | None, host: str | None, debug: bool = False) -> ForgejoClient:
    resolved_token = discover_token(explicit=token, secrets_path=None)
    resolved_host = host or os.environ.get("FORGEJO_HOST") or DEFAULT_HOST
    return ForgejoClient(host=resolved_host, token=resolved_token, debug=debug)


@click.group()
def auth():
    """Authentication subcommands."""


@auth.command("status")
@click.pass_context
def auth_status(ctx):
    """Show the active token, instance URL, and authenticated user."""
    client = _build_client(
        ctx.obj.get("token"),
        ctx.obj.get("host"),
        debug=ctx.obj.get("debug", False),
    )
    try:
        user = client.get("/user")
    finally:
        client.close()
    click.echo(f"Logged in to {client._host} as {user['login']}")
    click.echo(f"Token source: {_token_source_label(ctx)}")


def _token_source_label(ctx) -> str:
    if ctx.obj.get("token"):
        return "--token flag"
    if os.environ.get("FORGEJO_TOKEN"):
        return "FORGEJO_TOKEN env var"
    return "~/.secrets/forgejo.env"


@auth.command("git-credential")
@click.argument("op", type=click.Choice(["get", "store", "erase"]))
@click.pass_context
def auth_git_credential(ctx, op):
    """git credential helper protocol.

    Set up with:
        git config --global credential.https://git.stevenamoore.dev.helper \\
            '!forge auth git-credential'
    """
    _ = sys.stdin.read()  # drain stdin (git sends k=v lines)
    if op != "get":
        return  # store/erase are no-ops; tokens are out-of-band
    try:
        token = discover_token(explicit=ctx.obj.get("token"), secrets_path=None)
        client = _build_client(
            ctx.obj.get("token"),
            ctx.obj.get("host"),
            debug=ctx.obj.get("debug", False),
        )
        try:
            user = client.get("/user")
        finally:
            client.close()
    except AuthError:
        # git's credential helper protocol expects exit 0 with empty stdout
        # so git can fall through to the next helper or prompt.
        return
    click.echo(f"username={user['login']}")
    click.echo(f"password={token}")
