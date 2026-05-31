# tests/test_translate.py
import json
from pathlib import Path

from forge.translate import ISSUE_FIELDS, JSON_FIELD_NAMES, PR_FIELDS, issue_to_gh, pr_to_gh

FIXTURES = Path(__file__).parent / "fixtures"


def test_pr_translation_matches_gh_fixture():
    forgejo_pr = json.loads((FIXTURES / "forgejo" / "pr.json").read_text())
    expected = json.loads((FIXTURES / "gh" / "pr.json").read_text())
    assert pr_to_gh(forgejo_pr) == expected


def test_merged_pr_state_is_MERGED():
    forgejo_pr = {
        "state": "closed", "merged": True,
        "user": {"login": "x"},
        "head": {"ref": "a", "sha": "1"}, "base": {"ref": "b", "sha": "2"},
        "number": 1, "title": "t", "draft": False,
        "created_at": "2026-01-01T00:00:00Z", "html_url": "", "labels": [],
    }
    assert pr_to_gh(forgejo_pr)["state"] == "MERGED"


def test_json_field_names_returns_known_pr_fields():
    names = JSON_FIELD_NAMES["pr"]
    assert "number" in names
    assert "headRefName" in names
    assert "author" in names
    assert names == tuple(PR_FIELDS.keys())


def test_issue_translation_matches_gh_fixture():
    forgejo_issue = json.loads((FIXTURES / "forgejo" / "issue.json").read_text())
    expected = json.loads((FIXTURES / "gh" / "issue.json").read_text())
    assert issue_to_gh(forgejo_issue) == expected


def test_json_field_names_returns_known_issue_fields():
    names = JSON_FIELD_NAMES["issue"]
    assert "number" in names
    assert "body" in names
    assert names == tuple(ISSUE_FIELDS.keys())   # registry coupling, matches T7 pattern


def test_run_to_gh_maps_all_run_fields():
    from forge.translate import JSON_FIELD_NAMES, run_to_gh

    forgejo_run = {
        "id": 161,
        "run_number": 17,
        "name": "test (3.13)",
        "display_title": "release: bump version to 0.1.1",
        "head_branch": "v0.1.1",
        "head_sha": "7637ea61f2877477a77330a91f3f5915532e3fca",
        "status": "success",
        "event": "push",
        "url": "https://git.stevenamoore.dev/samoore/forge/actions/runs/17",
        "created_at": "2026-05-26T18:48:21-04:00",
        "run_started_at": "2026-05-26T18:48:21-04:00",
        "updated_at": "2026-05-26T18:49:05-04:00",
        "workflow_id": "test.yml",
    }
    out = run_to_gh(forgejo_run)
    assert out == {
        "id": 161,
        "runNumber": 17,
        "name": "test (3.13)",
        "displayTitle": "release: bump version to 0.1.1",
        "headBranch": "v0.1.1",
        "headSha": "7637ea61f2877477a77330a91f3f5915532e3fca",
        "status": "success",
        "event": "push",
        "url": "https://git.stevenamoore.dev/samoore/forge/actions/runs/17",
        "createdAt": "2026-05-26T18:48:21-04:00",
        "startedAt": "2026-05-26T18:48:21-04:00",
        "updatedAt": "2026-05-26T18:49:05-04:00",
        "workflowId": "test.yml",
    }
    assert "run" in JSON_FIELD_NAMES
    assert "runNumber" in JSON_FIELD_NAMES["run"]
