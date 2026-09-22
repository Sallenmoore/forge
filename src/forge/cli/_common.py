# src/forge/cli/_common.py
"""Client construction and repo resolution shared by the subcommand modules.

Extracted from cli/issue.py and cli/pr.py, which carried byte-identical
copies. The copies drifted: _build_client consulted FORGEJO_HOST while
_resolve did not, so the API client and the origin-host check could target
different instances. One definition removes the class of bug.

Imports only from the library layer (client/repo/errors), preserving the
dependency direction that keeps that layer extractable.
"""
import os

from forge.client import DEFAULT_HOST, ForgejoClient, discover_token
from forge.repo import resolve_repo


def resolved_host(host: str | None) -> str:
    """Which Forgejo instance this invocation targets.

    Every caller must agree, so there is exactly one of these.
    """
    return host or os.environ.get("FORGEJO_HOST") or DEFAULT_HOST


def build_client(token: str | None, host: str | None) -> ForgejoClient:
    return ForgejoClient(
        host=resolved_host(host),
        token=discover_token(explicit=token, secrets_path=None),
    )


def resolve(ctx, repo_override: str | None = None):
    """Return (client, RepoSpec) for a subcommand's click context."""
    spec = resolve_repo(
        r_flag=repo_override or ctx.obj.get("repo"),
        host=resolved_host(ctx.obj.get("host")),
        cwd=os.getcwd(),
        env_default=os.environ.get("FORGEJO_DEFAULT_REPO"),
    )
    return build_client(ctx.obj.get("token"), ctx.obj.get("host")), spec
