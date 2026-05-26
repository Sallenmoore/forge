# tests/test_translate.py
import json
from pathlib import Path

from forge.translate import JSON_FIELD_NAMES, PR_FIELDS, pr_to_gh

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
