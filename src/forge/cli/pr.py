# src/forge/cli/pr.py
import json as json_module
import os

import click

from forge.client import DEFAULT_HOST, ForgejoClient, discover_token
from forge.errors import UsageError
from forge.repo import resolve_repo
from forge.translate import JSON_FIELD_NAMES, pr_to_gh


def _build_client(token: str | None, host: str | None) -> ForgejoClient:
    return ForgejoClient(
        host=host or DEFAULT_HOST,
        token=discover_token(explicit=token, secrets_path=None),
    )


def _resolve(ctx, repo_override: str | None = None):
    spec = resolve_repo(
        r_flag=repo_override or ctx.obj.get("repo"),
        host=ctx.obj.get("host") or DEFAULT_HOST,
        cwd=os.getcwd(),
        env_default=os.environ.get("FORGEJO_DEFAULT_REPO"),
    )
    return _build_client(ctx.obj.get("token"), ctx.obj.get("host")), spec


def _filter_json(rows: list[dict], fields_str: str) -> list[dict]:
    requested = [f.strip() for f in fields_str.split(",") if f.strip()]
    known = JSON_FIELD_NAMES["pr"]
    for f in requested:
        if f not in known:
            raise UsageError(f"unknown field: {f} — available: {','.join(known)}")
    return [{f: row[f] for f in requested} for row in rows]


@click.group()
def pr():
    """Pull request subcommands."""


@pr.command("list")
@click.option("-R", "repo", default=None, help="owner/repo")
@click.option("--state", type=click.Choice(["open", "closed", "all"]), default="open")
@click.option("--json", "json_fields", default=None,
              help="Comma-separated gh-shape fields to emit as JSON")
@click.pass_context
def pr_list(ctx, repo, state, json_fields):
    """List PRs on the resolved repo."""
    client, spec = _resolve(ctx, repo_override=repo)
    try:
        raw = client.get(f"/repos/{spec.owner}/{spec.repo}/pulls",
                          params={"state": state})
    finally:
        client.close()
    rows = [pr_to_gh(p) for p in raw]
    if json_fields:
        click.echo(json_module.dumps(_filter_json(rows, json_fields)))
        return
    for r in rows:
        click.echo("\t".join([
            str(r["number"]), r["title"], r["headRefName"], r["state"]
        ]))


@pr.command("view")
@click.argument("number", type=int)
@click.option("-R", "repo", default=None, help="owner/repo override")
@click.option("--json", "json_fields", default=None,
              help="Comma-separated gh-shape fields to emit as JSON")
@click.pass_context
def pr_view(ctx, number, repo, json_fields):
    """Show details of a single PR."""
    client, spec = _resolve(ctx, repo_override=repo)
    try:
        raw = client.get(f"/repos/{spec.owner}/{spec.repo}/pulls/{number}")
    finally:
        client.close()
    translated = pr_to_gh(raw)
    if json_fields:
        click.echo(json_module.dumps(_filter_json([translated], json_fields)[0]))
        return
    click.echo(f"#{translated['number']} {translated['title']}")
    click.echo(f"State:   {translated['state']}")
    click.echo(f"Branch:  {translated['headRefName']} -> {translated['baseRefName']}")
    click.echo(f"Author:  {translated['author']['login']}")
    click.echo(f"URL:     {translated['url']}")


@pr.command("create")
@click.option("-R", "repo", default=None, help="owner/repo override")
@click.option("--title", required=True)
@click.option("--body", default="")
@click.option("--base", required=True)
@click.option("--head", required=True)
@click.pass_context
def pr_create(ctx, repo, title, body, base, head):
    """Open a new PR."""
    client, spec = _resolve(ctx, repo_override=repo)
    try:
        resp = client.post(
            f"/repos/{spec.owner}/{spec.repo}/pulls",
            json={"title": title, "body": body, "base": base, "head": head},
        )
    finally:
        client.close()
    click.echo(resp["html_url"])
