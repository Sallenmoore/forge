# src/forge/cli/pr.py
import json as json_module
import os

import click

from forge.client import DEFAULT_HOST, ForgejoClient, discover_token
from forge.errors import UsageError
from forge.repo import resolve_repo
from forge.translate import JSON_FIELD_NAMES, pr_to_gh


def _build_client(token: str | None, host: str | None, debug: bool = False) -> ForgejoClient:
    resolved_host = host or os.environ.get("FORGEJO_HOST") or DEFAULT_HOST
    return ForgejoClient(
        host=resolved_host,
        token=discover_token(explicit=token, secrets_path=None),
        debug=debug,
    )


def _resolve(ctx, repo_override: str | None = None):
    spec = resolve_repo(
        r_flag=repo_override or ctx.obj.get("repo"),
        host=ctx.obj.get("host") or DEFAULT_HOST,
        cwd=os.getcwd(),
        env_default=os.environ.get("FORGEJO_DEFAULT_REPO"),
    )
    return _build_client(
        ctx.obj.get("token"),
        ctx.obj.get("host"),
        debug=ctx.obj.get("debug", False),
    ), spec


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


@pr.command("merge")
@click.argument("number", type=int)
@click.option("-R", "repo", default=None, help="owner/repo override")
@click.option("--squash", "method", flag_value="squash")
@click.option("--rebase", "method", flag_value="rebase")
@click.option("--merge", "method", flag_value="merge", default=True)
@click.pass_context
def pr_merge(ctx, number, repo, method):
    """Merge a PR (uses Forgejo's capital-D `Do` field)."""
    client, spec = _resolve(ctx, repo_override=repo)
    try:
        client.post(
            f"/repos/{spec.owner}/{spec.repo}/pulls/{number}/merge",
            json={"Do": method},
        )
    finally:
        client.close()
    click.echo(f"PR #{number} merged ({method})")


@pr.command("checks")
@click.argument("number", type=int)
@click.option("-R", "repo", default=None, help="owner/repo override")
@click.pass_context
def pr_checks(ctx, number, repo):
    """Show CI status for the PR's head commit."""
    client, spec = _resolve(ctx, repo_override=repo)
    try:
        pr_data = client.get(f"/repos/{spec.owner}/{spec.repo}/pulls/{number}")
        sha = pr_data["head"]["sha"]
        status = client.get(f"/repos/{spec.owner}/{spec.repo}/commits/{sha}/status")
    finally:
        client.close()
    click.echo(f"Combined: {status['state']}")
    for s in status.get("statuses", []):
        click.echo(f"  {s.get('context', '?')}: {s.get('status', '?')}")


@pr.command("comment")
@click.argument("number", type=int)
@click.option("-R", "repo", default=None, help="owner/repo override")
@click.option("--body", required=True)
@click.pass_context
def pr_comment(ctx, number, repo, body):
    """Add a comment to a PR (uses the /issues/{n}/comments endpoint)."""
    client, spec = _resolve(ctx, repo_override=repo)
    try:
        resp = client.post(
            f"/repos/{spec.owner}/{spec.repo}/issues/{number}/comments",
            json={"body": body},
        )
    finally:
        client.close()
    click.echo(resp.get("html_url", "comment added"))


@pr.command("close")
@click.argument("number", type=int)
@click.option("-R", "repo", default=None, help="owner/repo override")
@click.pass_context
def pr_close(ctx, number, repo):
    """Close a PR."""
    client, spec = _resolve(ctx, repo_override=repo)
    try:
        client.patch(
            f"/repos/{spec.owner}/{spec.repo}/pulls/{number}",
            json={"state": "closed"},
        )
    finally:
        client.close()
    click.echo(f"Closed PR #{number}")


@pr.command("reopen")
@click.argument("number", type=int)
@click.option("-R", "repo", default=None, help="owner/repo override")
@click.pass_context
def pr_reopen(ctx, number, repo):
    """Reopen a closed PR."""
    client, spec = _resolve(ctx, repo_override=repo)
    try:
        client.patch(
            f"/repos/{spec.owner}/{spec.repo}/pulls/{number}",
            json={"state": "open"},
        )
    finally:
        client.close()
    click.echo(f"Reopened PR #{number}")
