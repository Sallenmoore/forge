# src/forge/cli/issue.py
import json as json_module

import click

from forge.cli._common import filter_json, requested_fields
from forge.cli._common import resolve as _resolve
from forge.client import ForgejoClient
from forge.errors import UsageError
from forge.translate import comment_to_gh, issue_to_gh


@click.group()
def issue():
    """Issue subcommands."""


@issue.command("list")
@click.option("-R", "repo", default=None, help="owner/repo override")
@click.option("--state", type=click.Choice(["open", "closed", "all"]), default="open")
@click.option("--json", "json_fields", default=None,
              help="Comma-separated gh-shape fields to emit as JSON")
@click.pass_context
def issue_list(ctx, repo, state, json_fields):
    """List issues on the resolved repo. Filters out PRs via &type=issues."""
    client, spec = _resolve(ctx, repo_override=repo)
    try:
        raw = client.get(
            f"/repos/{spec.owner}/{spec.repo}/issues",
            params={"state": state, "type": "issues"},
        )
    finally:
        client.close()
    rows = [issue_to_gh(p) for p in raw]
    if json_fields:
        click.echo(json_module.dumps(filter_json(rows, json_fields, "issue")))
        return
    for r in rows:
        labels = ",".join(lbl["name"] for lbl in r.get("labels", []))
        click.echo("\t".join([str(r["number"]), r["title"], r["state"], labels]))


@issue.command("view")
@click.argument("number", type=int)
@click.option("-R", "repo", default=None, help="owner/repo override")
@click.option("--comments", "show_comments", is_flag=True,
              help="Append the comment thread (author, timestamp, body)")
@click.option("--json", "json_fields", default=None)
@click.pass_context
def issue_view(ctx, number, repo, show_comments, json_fields):
    """Show issue details."""
    want_comments = show_comments or (
        json_fields is not None and "comments" in requested_fields(json_fields)
    )
    client, spec = _resolve(ctx, repo_override=repo)
    try:
        path = f"/repos/{spec.owner}/{spec.repo}/issues/{number}"
        raw = client.get(path)
        raw_comments = client.get(f"{path}/comments") if want_comments else []
    finally:
        client.close()
    translated = issue_to_gh(raw)
    comments = [comment_to_gh(c) for c in raw_comments]
    if json_fields:
        row = {**translated, "comments": comments}
        click.echo(json_module.dumps(filter_json([row], json_fields, "issue_view")[0]))
        return
    click.echo(f"#{translated['number']} {translated['title']}")
    click.echo(f"State:  {translated['state']}")
    click.echo(f"Author: {translated['author']['login']}")
    click.echo(f"URL:    {translated['url']}")
    if translated.get("body"):
        click.echo("")
        click.echo(translated["body"])
    if show_comments:
        _echo_comments(comments)


def _echo_comments(comments: list[dict]) -> None:
    click.echo("")
    click.echo(f"--- {len(comments)} comment(s) ---")
    for c in comments:
        click.echo("")
        click.echo(f"{c['author']['login']} commented {c['createdAt']}")
        click.echo(c["body"])


@issue.command("create")
@click.option("-R", "repo", default=None, help="owner/repo override")
@click.option("--title", required=True)
@click.option("--body", default="")
@click.option("--label", "labels", multiple=True,
              help="Label name (repeatable); resolved to integer IDs")
@click.pass_context
def issue_create(ctx, repo, title, body, labels):
    """Open a new issue. Label names are resolved to Forgejo's integer IDs."""
    client, spec = _resolve(ctx, repo_override=repo)
    try:
        label_ids = _resolve_label_names(client, spec, labels) if labels else []
        resp = client.post(
            f"/repos/{spec.owner}/{spec.repo}/issues",
            json={"title": title, "body": body, "labels": label_ids},
        )
    finally:
        client.close()
    click.echo(resp.get("html_url", "issue created"))


def _resolve_label_names(client: ForgejoClient, spec, names: tuple[str, ...]) -> list[int]:
    all_labels = client.get(f"/repos/{spec.owner}/{spec.repo}/labels")
    by_name = {lbl["name"]: lbl["id"] for lbl in all_labels}
    ids = []
    for name in names:
        if name not in by_name:
            raise UsageError(f"label '{name}' not found in {spec}")
        ids.append(by_name[name])
    return ids


@issue.command("close")
@click.argument("number", type=int)
@click.option("-R", "repo", default=None, help="owner/repo override")
@click.pass_context
def issue_close(ctx, number, repo):
    """Close an open issue."""
    client, spec = _resolve(ctx, repo_override=repo)
    try:
        client.patch(
            f"/repos/{spec.owner}/{spec.repo}/issues/{number}",
            json={"state": "closed"},
        )
    finally:
        client.close()
    click.echo(f"Issue #{number} closed")


@issue.command("comment")
@click.argument("number", type=int)
@click.option("-R", "repo", default=None, help="owner/repo override")
@click.option("--body", required=True)
@click.pass_context
def issue_comment(ctx, number, repo, body):
    """Add a comment to an issue."""
    client, spec = _resolve(ctx, repo_override=repo)
    try:
        resp = client.post(
            f"/repos/{spec.owner}/{spec.repo}/issues/{number}/comments",
            json={"body": body},
        )
    finally:
        client.close()
    click.echo(resp.get("html_url", "comment added"))
