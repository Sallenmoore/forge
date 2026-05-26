# src/forge/repo.py
from dataclasses import dataclass

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
    raise UsageError(
        "repo: no -R flag, git remote, or FORGEJO_DEFAULT_REPO available"
    )


def _parse_owner_repo(value: str) -> RepoSpec:
    parts = value.split("/")
    if len(parts) != 2 or not all(parts):
        raise UsageError(f"repo: '{value}' must be owner/repo")
    return RepoSpec(owner=parts[0], repo=parts[1])
