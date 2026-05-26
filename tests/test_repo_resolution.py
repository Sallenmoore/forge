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


def test_git_remote_origin_matches_host(tmp_path):
    # Simulate a git repo with origin pointing at the configured host
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text(
        '[remote "origin"]\n'
        '\turl = https://git.stevenamoore.dev/samoore/storyteller.git\n'
    )
    spec = resolve_repo(r_flag=None, host="https://git.stevenamoore.dev",
                        cwd=str(tmp_path), env_default=None)
    assert spec == RepoSpec(owner="samoore", repo="storyteller")


def test_git_remote_host_mismatch_raises(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text(
        '[remote "origin"]\n'
        '\turl = https://github.com/samoore/storyteller.git\n'
    )
    with pytest.raises(UsageError, match=r"github\.com, not the configured Forgejo"):
        resolve_repo(r_flag=None, host="https://git.stevenamoore.dev",
                     cwd=str(tmp_path), env_default=None)


def test_git_remote_ssh_scp_form(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text(
        '[remote "origin"]\n'
        '\turl = git@git.stevenamoore.dev:samoore/forge.git\n'
    )
    spec = resolve_repo(r_flag=None, host="https://git.stevenamoore.dev",
                        cwd=str(tmp_path), env_default=None)
    assert spec == RepoSpec(owner="samoore", repo="forge")


def test_git_remote_ssh_host_mismatch_raises(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text(
        '[remote "origin"]\n'
        '\turl = git@github.com:samoore/storyteller.git\n'
    )
    with pytest.raises(UsageError, match=r"github\.com, not the configured Forgejo"):
        resolve_repo(r_flag=None, host="https://git.stevenamoore.dev",
                     cwd=str(tmp_path), env_default=None)


def test_env_default_used_when_no_r_no_remote(tmp_path):
    spec = resolve_repo(r_flag=None, host="https://git.stevenamoore.dev",
                        cwd=str(tmp_path), env_default="samoore/forge")
    assert spec == RepoSpec(owner="samoore", repo="forge")


def test_env_default_used_only_when_r_absent(tmp_path):
    spec = resolve_repo(r_flag="other/repo", host="https://git.stevenamoore.dev",
                        cwd=str(tmp_path), env_default="samoore/forge")
    assert spec == RepoSpec(owner="other", repo="repo")


def test_git_remote_resolves_from_subdir(tmp_path):
    """Running forge from a subdir of a git repo should still resolve via origin."""
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text(
        '[remote "origin"]\n'
        '\turl = https://git.stevenamoore.dev/samoore/storyteller.git\n'
    )
    subdir = tmp_path / "src" / "deep" / "nested"
    subdir.mkdir(parents=True)
    spec = resolve_repo(r_flag=None, host="https://git.stevenamoore.dev",
                        cwd=str(subdir), env_default=None)
    assert spec == RepoSpec(owner="samoore", repo="storyteller")


def test_git_remote_returns_none_outside_any_repo(tmp_path):
    """When no parent has .git/config, _from_git_remote returns None (falls through)."""
    spec = resolve_repo(r_flag=None, host="https://git.stevenamoore.dev",
                        cwd=str(tmp_path), env_default="fallback/repo")
    assert spec == RepoSpec(owner="fallback", repo="repo")
