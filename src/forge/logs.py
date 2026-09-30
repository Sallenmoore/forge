# src/forge/logs.py
"""On-disk log access for Forgejo runs.

The Forgejo 11.x API exposes no log endpoint; this module reads the on-disk
log file from inside the Forgejo container via `docker exec`. Path:

    /data/gitea/actions_log/{owner}/{repo}/{shard}/{task_id_decimal}.log.zst

where shard is `%02x` of task_id % 256 — the id's low byte, two lowercase hex
digits (292 → "24"). Verified against a live 14.0.5 instance, 2026-09-30.

Logs are kept for successful tasks as well as failed ones; a missing file
usually means the caller passed a run number, not a task id.
"""
import subprocess

import zstandard

from forge.errors import NotFoundError, ServerError, ValidationError

ISSUE_URL = "https://github.com/Sallenmoore/forge/issues/2"


def compute_log_path(owner: str, repo: str, task_id: int) -> str:
    """Path inside the Forgejo container for the given task's log file."""
    shard = f"{task_id % 256:02x}"
    return f"/data/gitea/actions_log/{owner}/{repo}/{shard}/{task_id}.log.zst"


def fetch_log(*, container: str | None, owner: str, repo: str, task_id: int,
              timeout: float = 15.0) -> str:
    """Fetch the decompressed log text for a single task.

    Raises:
        ValidationError: when `container` is None (user must opt into docker exec)
        NotFoundError:   when the log file doesn't exist on disk
        ServerError:     when `docker exec` itself fails (no container, etc.)
    """
    if container is None:
        raise ValidationError(
            "log access requires container exec on the Forgejo host. "
            "Forgejo has no log API; pass --container <name> or set "
            f"FORGEJO_CONTAINER. See {ISSUE_URL}"
        )
    path = compute_log_path(owner, repo, task_id)
    proc = subprocess.run(
        ["docker", "exec", container, "cat", path],
        capture_output=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace").strip()
        if "no such file" in stderr.lower():
            raise NotFoundError(
                f"no log on disk for task {task_id} — pass a task id (first "
                f"column of `forge run list`), not a run number; or it expired"
            )
        raise ServerError(f"docker exec failed: {stderr}")
    try:
        dctx = zstandard.ZstdDecompressor()
        decompressed = dctx.decompress(proc.stdout, max_output_size=200_000_000)
    except zstandard.ZstdError as e:
        raise ServerError(f"log decompression failed for run {task_id}: {e}") from e
    return decompressed.decode("utf-8", errors="replace")
