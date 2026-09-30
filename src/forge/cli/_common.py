# src/forge/cli/_common.py
"""Client construction and repo resolution shared by the subcommand modules.

Extracted from cli/issue.py and cli/pr.py, which carried byte-identical
copies. The copies drifted: _build_client consulted FORGEJO_HOST while
_resolve did not, so the API client and the origin-host check could target
different instances. One definition removes the class of bug.

Imports only from the library layer (client/repo/errors/translate), preserving the
dependency direction that keeps that layer extractable.
"""
import os

from forge.client import DEFAULT_HOST, ForgejoClient, discover_token
from forge.errors import UsageError
from forge.repo import resolve_repo
from forge.translate import JSON_FIELD_NAMES


def resolved_host(host: str | None) -> str:
    """Which Forgejo instance this invocation targets.

    Every caller must agree, so there is exactly one of these.
    """
    return host or os.environ.get("FORGEJO_HOST") or DEFAULT_HOST


def build_client(token: str | None, host: str | None, debug: bool = False) -> ForgejoClient:
    return ForgejoClient(
        host=resolved_host(host),
        token=discover_token(explicit=token, secrets_path=None),
        debug=debug,
    )


def resolve_spec(ctx, repo_override: str | None = None):
    """Return the RepoSpec for a subcommand's click context, without a client."""
    return resolve_repo(
        r_flag=repo_override or ctx.obj.get("repo"),
        host=resolved_host(ctx.obj.get("host")),
        cwd=os.getcwd(),
        env_default=os.environ.get("FORGEJO_DEFAULT_REPO"),
    )


def resolve(ctx, repo_override: str | None = None):
    """Return (client, RepoSpec) for a subcommand's click context."""
    spec = resolve_spec(ctx, repo_override)
    client = build_client(
        ctx.obj.get("token"), ctx.obj.get("host"), debug=ctx.obj.get("debug", False)
    )
    return client, spec


def requested_fields(fields_str: str) -> list[str]:
    """Split a `--json a,b,c` argument into field names."""
    return [f.strip() for f in fields_str.split(",") if f.strip()]


def filter_json(rows: list[dict], fields_str: str, registry: str) -> list[dict]:
    """Project gh-shape rows onto the requested `--json` fields.

    `registry` names the JSON_FIELD_NAMES entry that says which fields are legal.
    """
    requested = requested_fields(fields_str)
    known = JSON_FIELD_NAMES[registry]
    for f in requested:
        if f not in known:
            raise UsageError(f"unknown field: {f} — available: {','.join(known)}")
    return [{f: row[f] for f in requested} for row in rows]
