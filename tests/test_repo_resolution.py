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


def test_ssh_alias_is_expanded_via_ssh_minus_G(tmp_path, monkeypatch):
    """SCP-form remote with an SSH alias resolves via `ssh -G <alias>`."""
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text(
        '[remote "origin"]\n'
        '\turl = mooregit:samoore/storyteller.git\n'
    )

    # Stub subprocess.run to fake `ssh -G mooregit` output
    def fake_run(cmd, **kwargs):
        import subprocess
        if cmd[:2] == ["ssh", "-G"] and cmd[2] == "mooregit":
            return subprocess.CompletedProcess(
                cmd, 0,
                stdout=(
                    "user git\n"
                    "hostname git.stevenamoore.dev\n"
                    "port 22\n"
                ),
                stderr="",
            )
        raise RuntimeError(f"unexpected subprocess call: {cmd}")

    monkeypatch.setattr("subprocess.run", fake_run)

    spec = resolve_repo(r_flag=None, host="https://git.stevenamoore.dev",
                        cwd=str(tmp_path), env_default=None)
    assert spec == RepoSpec(owner="samoore", repo="storyteller")


def test_ssh_alias_with_real_hostname_mismatch_still_raises(tmp_path, monkeypatch):
    """If `ssh -G` reveals the alias points at a DIFFERENT host, still raise."""
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text(
        '[remote "origin"]\n'
        '\turl = somealias:samoore/storyteller.git\n'
    )

    def fake_run(cmd, **kwargs):
        import subprocess
        return subprocess.CompletedProcess(
            cmd, 0,
            stdout="hostname github.com\n",
            stderr="",
        )

    monkeypatch.setattr("subprocess.run", fake_run)

    with pytest.raises(UsageError, match=r"github\.com, not the configured Forgejo"):
        resolve_repo(r_flag=None, host="https://git.stevenamoore.dev",
                     cwd=str(tmp_path), env_default=None)


def test_ssh_command_failure_falls_back_to_literal_host(tmp_path, monkeypatch):
    """If `ssh -G` fails (no ssh binary, command error), fall back to the literal host.

    The original behavior remains for backward compat: if the literal host
    matches, fine; if it doesn't, raise (as before).
    """
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text(
        '[remote "origin"]\n'
        '\turl = git.stevenamoore.dev:samoore/storyteller.git\n'  # already-correct host
    )

    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("ssh not found")

    monkeypatch.setattr("subprocess.run", fake_run)

    # Even though ssh -G failed, the literal host matches, so resolution works.
    spec = resolve_repo(r_flag=None, host="https://git.stevenamoore.dev",
                        cwd=str(tmp_path), env_default=None)
    assert spec == RepoSpec(owner="samoore", repo="storyteller")


def test_https_url_does_NOT_invoke_ssh_minus_G(tmp_path, monkeypatch):
    """HTTPS URLs already have a real hostname; ssh -G should not be invoked."""
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text(
        '[remote "origin"]\n'
        '\turl = https://git.stevenamoore.dev/samoore/storyteller.git\n'
    )

    called = []
    def fake_run(cmd, **kwargs):
        called.append(cmd)
        import subprocess
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)

    spec = resolve_repo(r_flag=None, host="https://git.stevenamoore.dev",
                        cwd=str(tmp_path), env_default=None)
    assert spec == RepoSpec(owner="samoore", repo="storyteller")
    assert called == []  # ssh -G must not have been called
