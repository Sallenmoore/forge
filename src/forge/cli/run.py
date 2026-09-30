# src/forge/cli/run.py
import json as json_module
import os

import click

from forge.cli._common import filter_json, resolve_spec, resolved_host
from forge.cli._common import resolve as _resolve
from forge.errors import ForgeError, NotFoundError
from forge.translate import action_run_to_gh, run_to_gh

LIMIT_MAX = 50
LIMIT_DEFAULT = 20


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
        click.echo(json_module.dumps(filter_json(rows, json_fields, "run")))
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
    spec = resolve_spec(ctx, repo)
    text = _logs.fetch_log(
        container=container,
        owner=spec.owner,
        repo=spec.repo,
        task_id=task_id,
    )
    click.echo(text, nl=False)


@run.command("view")
@click.argument("run_number", type=int, metavar="RUN-NUMBER")
@click.option("-R", "repo", default=None, help="owner/repo override")
@click.option("--json", "json_fields", default=None,
              help="Comma-separated fields to emit as JSON")
@click.pass_context
def run_view(ctx, run_number, repo, json_fields):
    """Show one workflow run by its run number (as in the web URL).

    /actions/runs/{id} wants Forgejo's global run id, which nothing user-facing
    shows, so this filters the run list by run number instead.
    """
    client, spec = _resolve(ctx, repo_override=repo)
    try:
        raw = client.get(
            f"/repos/{spec.owner}/{spec.repo}/actions/runs",
            params={"run_number": run_number},
        )
    finally:
        client.close()
    runs = raw.get("workflow_runs") or []
    if not runs:
        raise NotFoundError(f"no run #{run_number} in {spec}")
    r = action_run_to_gh(runs[0])
    if json_fields:
        click.echo(json_module.dumps(filter_json([r], json_fields, "action_run")[0]))
        return
    click.echo(f"#{r['runNumber']} {r['displayTitle']}")
    click.echo(f"Status:   {r['status']}")
    click.echo(f"Workflow: {r['workflowId']}")
    click.echo(f"Ref:      {r['headBranch']} @ {r['headSha'][:7]}")
    click.echo(f"Event:    {r['event']} by {r['triggeredBy']['login']}")
    click.echo(f"Started:  {r['startedAt']}")
    click.echo(f"Stopped:  {r['stoppedAt']}")
    click.echo(f"URL:      {r['url']}")


def _web_only(ctx, verb: str, run_number: int, repo: str | None):
    spec = resolve_spec(ctx, repo)
    url = f"{resolved_host(ctx.obj.get('host'))}/{spec.owner}/{spec.repo}/actions/runs/{run_number}"
    raise ForgeError(
        f"Forgejo has no REST API to {verb} a run "
        f"(https://github.com/Sallenmoore/forge/issues/3); "
        f"use the {verb} button at {url}"
    )


@run.command("cancel")
@click.argument("run_number", type=int, metavar="RUN-NUMBER")
@click.option("-R", "repo", default=None, help="owner/repo override")
@click.pass_context
def run_cancel(ctx, run_number, repo):
    """Cancel a run. Not possible via Forgejo's API; points at the web UI."""
    _web_only(ctx, "cancel", run_number, repo)


@run.command("rerun")
@click.argument("run_number", type=int, metavar="RUN-NUMBER")
@click.option("-R", "repo", default=None, help="owner/repo override")
@click.pass_context
def run_rerun(ctx, run_number, repo):
    """Re-run a run. Not possible via Forgejo's API; points at the web UI."""
    _web_only(ctx, "rerun", run_number, repo)
