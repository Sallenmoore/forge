# src/forge/cli/run.py
import json as json_module
import os

import click

from forge.client import DEFAULT_HOST, ForgejoClient, discover_token
from forge.errors import UsageError
from forge.repo import resolve_repo
from forge.translate import JSON_FIELD_NAMES, run_to_gh

LIMIT_MAX = 50
LIMIT_DEFAULT = 20


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
    known = JSON_FIELD_NAMES["run"]
    for f in requested:
        if f not in known:
            raise UsageError(f"unknown field: {f} — available: {','.join(known)}")
    return [{f: row[f] for f in requested} for row in rows]


@click.group()
def run():
    """Workflow run subcommands."""


@run.command("list")
@click.option("-R", "repo", default=None, help="owner/repo override")
@click.option("--branch", default=None, help="Filter by head branch")
@click.option("--status", default=None,
              help="Filter by status (success|failure|cancelled|...)")
@click.option("--workflow", default=None,
              help="Filter by workflow file (e.g. test.yml)")
@click.option("--limit", type=int, default=LIMIT_DEFAULT,
              help=f"Max runs to fetch (capped at {LIMIT_MAX})")
@click.option("--json", "json_fields", default=None,
              help="Comma-separated fields to emit as JSON")
@click.pass_context
def run_list(ctx, repo, branch, status, workflow, limit, json_fields):
    """List recent workflow runs."""
    limit = max(1, min(limit, LIMIT_MAX))
    client, spec = _resolve(ctx, repo_override=repo)
    try:
        raw = client.get(
            f"/repos/{spec.owner}/{spec.repo}/actions/tasks",
            params={"limit": limit},
        )
    finally:
        client.close()
    runs = raw.get("workflow_runs", []) if isinstance(raw, dict) else []
    if branch is not None:
        runs = [r for r in runs if r.get("head_branch") == branch]
    if status is not None:
        runs = [r for r in runs if r.get("status") == status]
    if workflow is not None:
        runs = [r for r in runs if r.get("workflow_id") == workflow]
    rows = [run_to_gh(r) for r in runs]
    if json_fields:
        click.echo(json_module.dumps(_filter_json(rows, json_fields)))
        return
    # Table output: ID, RUN, STATUS, WORKFLOW, BRANCH, EVENT, TITLE
    for r in rows:
        click.echo("\t".join([
            str(r["id"]), str(r["runNumber"]), r["status"],
            r["workflowId"], r["headBranch"], r["event"],
            r["displayTitle"],
        ]))


@run.command("log")
@click.argument("task_id", type=int, metavar="RUN-ID")
@click.option("-R", "repo", default=None, help="owner/repo override")
@click.option("--container", default=None,
              help="Forgejo container name (or set FORGEJO_CONTAINER)")
@click.pass_context
def run_log(ctx, task_id, repo, container):
    """Dump the on-disk log for a workflow run by its task ID.

    Requires --container or FORGEJO_CONTAINER because Forgejo 11 exposes no
    log API. Only failed runs retain logs on disk.
    """
    from forge import logs as _logs
    container = container or os.environ.get("FORGEJO_CONTAINER")
    spec = resolve_repo(
        r_flag=repo or ctx.obj.get("repo"),
        host=ctx.obj.get("host") or DEFAULT_HOST,
        cwd=os.getcwd(),
        env_default=os.environ.get("FORGEJO_DEFAULT_REPO"),
    )
    text = _logs.fetch_log(
        container=container,
        owner=spec.owner,
        repo=spec.repo,
        task_id=task_id,
    )
    click.echo(text, nl=False)
