# tests/test_repo_resolution.py
import pytest

from forge.errors import UsageError
from forge.repo import RepoSpec, resolve_repo


def test_explicit_R_flag_returns_owner_repo():
    spec = resolve_repo(r_flag="samoore/forge", host="https://git.stevenamoore.dev",
                        cwd="/nonexistent", env_default=None)
    assert spec == RepoSpec(owner="samoore", repo="forge")


def test_explicit_R_flag_malformed_raises_usage_error():
    with pytest.raises(UsageError, match="must be owner/repo"):
        resolve_repo(r_flag="just-name", host="https://git.stevenamoore.dev",
                     cwd="/nonexistent", env_default=None)
