# src/forge/cli/auth.py
import os

import click

from forge.client import DEFAULT_HOST, ForgejoClient, discover_token


def _build_client(token: str | None, host: str | None) -> ForgejoClient:
    resolved_token = discover_token(explicit=token, secrets_path=None)
    return ForgejoClient(host=host or DEFAULT_HOST, token=resolved_token)


@click.group()
def auth():
    """Authentication subcommands."""


@auth.command("status")
@click.pass_context
def auth_status(ctx):
    """Show the active token, instance URL, and authenticated user."""
    client = _build_client(ctx.obj.get("token"), ctx.obj.get("host"))
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
