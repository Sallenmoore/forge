# src/forge/repo.py
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from forge.errors import UsageError


@dataclass(frozen=True)
class RepoSpec:
    owner: str
    repo: str

    def __str__(self) -> str:
        return f"{self.owner}/{self.repo}"


def resolve_repo(
    *,
    r_flag: str | None,
    host: str,
    cwd: str,
    env_default: str | None,
) -> RepoSpec:
    if r_flag is not None:
        return _parse_owner_repo(r_flag)
    from_remote = _from_git_remote(Path(cwd), host)
    if from_remote is not None:
        return from_remote
    if env_default:
        return _parse_owner_repo(env_default)
    raise UsageError(
        "repo: no -R flag, git remote, or FORGEJO_DEFAULT_REPO available"
    )


def _from_git_remote(cwd: Path, host: str) -> RepoSpec | None:
    git_root = _find_git_root(cwd)
    if git_root is None:
        return None
    config_path = git_root / ".git" / "config"
    text = config_path.read_text()
    m = re.search(r'\[remote\s+"origin"\][^\[]*?url\s*=\s*(\S+)', text, re.DOTALL)
    if not m:
        return None
    remote_url = m.group(1)
    remote_host, remote_path = _parse_remote_url(remote_url)
    configured_host = urlparse(host).hostname or ""
    if remote_host != configured_host:
        raise UsageError(
            f"repo: remote 'origin' points at {remote_host}, "
            f"not the configured Forgejo at {configured_host} — "
            f"pass -R explicitly or set FORGEJO_DEFAULT_REPO"
        )
    path = remote_path.removesuffix(".git")
    return _parse_owner_repo(path)


def _find_git_root(cwd: Path) -> Path | None:
    """Walk up from cwd looking for a directory containing .git/config."""
    for d in [cwd, *cwd.parents]:
        if (d / ".git" / "config").is_file():
            return d
    return None


def _parse_remote_url(remote_url: str) -> tuple[str, str]:
    """Return (host, path) from either an http(s)/ssh URL or an SCP-style remote.

    SCP-style: git@host:owner/repo[.git]  (no scheme, single colon before path)
    URL-style: https://host/owner/repo[.git] or ssh://user@host/owner/repo[.git]
    """
    if "://" in remote_url:
        parsed = urlparse(remote_url)
        return (parsed.hostname or "", parsed.path.lstrip("/"))
    # SCP form: [user@]host:path  (no scheme, single colon, path has no leading slash)
    scp_match = re.match(r"^(?:[^@]+@)?([^:/]+):(.+)$", remote_url)
    if scp_match:
        return (scp_match.group(1), scp_match.group(2))
    return ("", remote_url)


def _parse_owner_repo(value: str) -> RepoSpec:
    parts = value.split("/")
    if len(parts) != 2 or not all(parts):
        raise UsageError(f"repo: '{value}' must be owner/repo")
    return RepoSpec(owner=parts[0], repo=parts[1])
