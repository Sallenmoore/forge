# src/forge/cli/pr.py
import json as json_module
import os

import click

from forge.cli._common import filter_json
from forge.cli._common import resolve as _resolve
from forge.errors import UsageError
from forge.translate import pr_to_gh


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
        click.echo(json_module.dumps(filter_json(rows, json_fields, "pr")))
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
        click.echo(json_module.dumps(filter_json([translated], json_fields, "pr")[0]))
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
    # Click 8.3 does not honor default=True across a group of options that
    # share one name: --squash comes first in .params with an UNSET default
    # and wins, so an invocation with no method flag arrives here as None and
    # would POST {"Do": null}. Normalize rather than reshape the CLI surface.
    method = method or "merge"
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


@pr.command("edit")
@click.argument("number", type=int)
@click.option("-R", "repo", default=None, help="owner/repo override")
@click.option("--title", default=None, help="New title")
@click.option("--body", default=None, help="New body (markdown)")
@click.option("--base", default=None, help="Retarget the base branch")
@click.pass_context
def pr_edit(ctx, number, repo, title, body, base):
    """Edit a PR's title, body, or base branch."""
    payload = {}
    if title is not None:
        payload["title"] = title
    if body is not None:
        payload["body"] = body
    if base is not None:
        payload["base"] = base
    if not payload:
        raise UsageError("pr edit: at least one of --title, --body, --base is required")
    client, spec = _resolve(ctx, repo_override=repo)
    try:
        client.patch(
            f"/repos/{spec.owner}/{spec.repo}/pulls/{number}",
            json=payload,
        )
    finally:
        client.close()
    fields = ", ".join(sorted(payload.keys()))
    click.echo(f"Edited PR #{number} ({fields})")


@pr.command("log")
@click.argument("number", type=int)
@click.option("-R", "repo", default=None, help="owner/repo override")
@click.option("--container", default=None,
              help="Forgejo container name (or set FORGEJO_CONTAINER)")
@click.option("--failed-only/--no-failed-only", default=True,
              help="Only fetch logs for failed runs (default true)")
@click.pass_context
def pr_log(ctx, number, repo, container, failed_only):
    """Concatenated CI logs for the PR's head commit's runs.

    Default: only failed runs (the common agentic-debug case). Use
    --no-failed-only to include successful runs.
    """
    from forge import logs as _logs
    from forge.errors import NotFoundError
    container = container or os.environ.get("FORGEJO_CONTAINER")
    client, spec = _resolve(ctx, repo_override=repo)
    try:
        pr_data = client.get(f"/repos/{spec.owner}/{spec.repo}/pulls/{number}")
        head_sha = pr_data["head"]["sha"]
        raw = client.get(
            f"/repos/{spec.owner}/{spec.repo}/actions/tasks",
            params={"limit": 50},
        )
    finally:
        client.close()
    all_runs = raw.get("workflow_runs", []) if isinstance(raw, dict) else []
    matching = [r for r in all_runs if r.get("head_sha") == head_sha]
    if failed_only:
        matching = [r for r in matching if r.get("status") == "failure"]
    if not matching:
        click.echo(
            f"no matching runs for PR #{number} head {head_sha[:7]}",
            err=True,
        )
        return
    for r in matching:
        click.echo(
            f"===== run #{r['run_number']} \"{r['name']}\" "
            f"(id={r['id']}) status={r['status']} ====="
        )
        try:
            text = _logs.fetch_log(
                container=container,
                owner=spec.owner,
                repo=spec.repo,
                task_id=r["id"],
            )
            click.echo(text, nl=False)
        except NotFoundError as e:
            click.echo(str(e))
