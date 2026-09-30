# src/forge/cli/release.py
from urllib.parse import quote

import click

from forge.cli._common import resolve as _resolve
from forge.cli._common import resolved_host
from forge.errors import NotFoundError
from forge.release_notes import format_notes, select_prs


@click.group()
def release():
    """Release subcommands."""


@release.command("create")
@click.argument("tag")
@click.option("-R", "repo", default=None, help="owner/repo override")
@click.option("-t", "--title", default=None, help="Release title (default: the tag)")
@click.option("-n", "--notes", default="", help="Release notes (markdown)")
@click.option("--generate-notes", is_flag=True,
              help="List PRs merged since the previous release, as gh does")
@click.option("--target", default=None,
              help="Branch or commit to tag if TAG doesn't exist yet")
@click.option("-d", "--draft", is_flag=True, help="Save as a draft")
@click.option("-p", "--prerelease", is_flag=True, help="Mark as a prerelease")
@click.pass_context
def release_create(ctx, tag, repo, title, notes, generate_notes, target, draft, prerelease):
    """Create a release for TAG (created from --target if it doesn't exist)."""
    client, spec = _resolve(ctx, repo_override=repo)
    base = f"/repos/{spec.owner}/{spec.repo}"
    web = f"{resolved_host(ctx.obj.get('host')).rstrip('/')}/{spec.owner}/{spec.repo}"
    try:
        body = notes
        if generate_notes:
            generated = _generate_notes(client, base, web, tag, target)
            body = f"{notes}\n\n{generated}" if notes else generated
        payload = {"tag_name": tag, "name": title or tag, "body": body,
                   "draft": draft, "prerelease": prerelease}
        if target:
            payload["target_commitish"] = target
        resp = client.post(f"{base}/releases", json=payload)
    finally:
        client.close()
    click.echo(resp["html_url"])


def _generate_notes(client, base: str, web: str, tag: str, target: str | None) -> str:
    """Notes for the commits between the previous release and TAG.

    Forgejo has no generate-notes endpoint; see forge.release_notes.
    """
    head = tag if _tag_exists(client, base, tag) else (
        target or client.get(base)["default_branch"])
    prev = _previous_release_tag(client, base, tag)
    if prev:
        compare = client.get(f"{base}/compare/{prev}...{head}")
        shas = {c["sha"] for c in compare["commits"]}
        changelog = f"{web}/compare/{prev}...{tag}"
    else:
        shas = {c["sha"] for c in client.paginate(
            f"{base}/commits", {"sha": head, "stat": "false", "files": "false"})}
        changelog = f"{web}/commits/tag/{tag}"
    prs = list(client.paginate(f"{base}/pulls", {"state": "closed"}))
    return format_notes(select_prs(prs, shas), changelog_url=changelog)


def _tag_exists(client, base: str, tag: str) -> bool:
    try:
        client.get(f"{base}/tags/{quote(tag, safe='')}")
    except NotFoundError:
        return False
    return True


def _previous_release_tag(client, base: str, tag: str) -> str | None:
    """The newest published release other than TAG itself (Forgejo lists newest first)."""
    releases = client.get(f"{base}/releases", params={"draft": "false", "limit": 50})
    return next((r["tag_name"] for r in releases if r["tag_name"] != tag), None)
