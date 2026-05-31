import pytest
import zstandard

from forge import logs
from forge.errors import NotFoundError, ServerError, ValidationError


def test_compute_log_path_uses_lowercase_hex_dir():
    """task_id 161 → dir 'a1', file '161.log.zst'."""
    p = logs.compute_log_path("samoore", "forge", 161)
    assert p == "/data/gitea/actions_log/samoore/forge/a1/161.log.zst"


def test_compute_log_path_small_ids_no_pad():
    assert logs.compute_log_path("o", "r", 1) == "/data/gitea/actions_log/o/r/1/1.log.zst"
    assert logs.compute_log_path("o", "r", 15) == "/data/gitea/actions_log/o/r/f/15.log.zst"
    assert logs.compute_log_path("o", "r", 120) == "/data/gitea/actions_log/o/r/78/120.log.zst"
    assert logs.compute_log_path("o", "r", 309) == "/data/gitea/actions_log/o/r/135/309.log.zst"


def test_fetch_log_via_container_decompresses_zstd(monkeypatch):
    """fetch_log shells out to docker exec, decompresses, returns text."""
    sample_text = "2026-05-25T23:46:32.0086151Z line 1\n2026-05-25T23:47:09.8830993Z line 2\n"
    cctx = zstandard.ZstdCompressor()
    compressed = cctx.compress(sample_text.encode("utf-8"))

    seen = {}
    class FakeCompleted:
        returncode = 0
        stdout = compressed
        stderr = b""

    def fake_run(cmd, capture_output, timeout):
        seen["cmd"] = cmd
        seen["capture_output"] = capture_output
        return FakeCompleted()

    monkeypatch.setattr(logs.subprocess, "run", fake_run)
    out = logs.fetch_log(container="forgejo", owner="samoore", repo="forge", task_id=120)
    assert out == sample_text
    assert seen["cmd"][:4] == ["docker", "exec", "forgejo", "cat"]
    assert seen["cmd"][4] == "/data/gitea/actions_log/samoore/forge/78/120.log.zst"


def test_fetch_log_missing_file_raises_not_found(monkeypatch):
    class FakeCompleted:
        returncode = 1
        stdout = b""
        stderr = b"cat: /data/gitea/actions_log/o/r/a1/161.log.zst: No such file or directory\n"

    monkeypatch.setattr(logs.subprocess, "run",
                        lambda cmd, capture_output, timeout: FakeCompleted())

    with pytest.raises(NotFoundError) as exc_info:
        logs.fetch_log(container="forgejo", owner="o", repo="r", task_id=161)
    msg = str(exc_info.value).lower()
    assert "no log on disk" in msg
    assert "161" in msg
    assert "forgejo only retains failed-run logs" in msg


def test_fetch_log_docker_error_raises_server_error(monkeypatch):
    class FakeCompleted:
        returncode = 1
        stdout = b""
        stderr = b"Error response from daemon: No such container: foo\n"

    monkeypatch.setattr(logs.subprocess, "run",
                        lambda cmd, capture_output, timeout: FakeCompleted())

    with pytest.raises(ServerError) as exc_info:
        logs.fetch_log(container="foo", owner="o", repo="r", task_id=1)
    assert "no such container" in str(exc_info.value).lower()


def test_fetch_log_no_container_raises_validation_error():
    with pytest.raises(ValidationError) as exc_info:
        logs.fetch_log(container=None, owner="o", repo="r", task_id=1)
    msg = str(exc_info.value).lower()
    assert "container exec" in msg
    assert "forgejo_container" in msg
    assert "issues/3" in msg
