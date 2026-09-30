# src/forge/translate.py
from collections.abc import Callable
from typing import Any


def _path(p: dict, dotted: str) -> Any:
    cur: Any = p
    for part in dotted.split("."):
        cur = cur[part]
    return cur


def _pr_state(p: dict) -> str:
    if p.get("merged"):
        return "MERGED"
    return p["state"].upper()


PR_FIELDS: dict[str, str | Callable[[dict], Any]] = {
    "number":       "number",
    "title":        "title",
    "state":        _pr_state,
    "isDraft":      "draft",
    "author":       lambda p: {"login": p["user"]["login"]},
    "headRefName":  "head.ref",
    "headRefOid":   "head.sha",
    "baseRefName":  "base.ref",
    "createdAt":    "created_at",
    "url":          "html_url",
    "labels":       lambda p: [{"name": lbl["name"], "color": lbl["color"]}
                                for lbl in p.get("labels", [])],
}


def _translate(forgejo: dict, table: dict[str, str | Callable]) -> dict:
    out = {}
    for gh_name, resolver in table.items():
        if callable(resolver):
            out[gh_name] = resolver(forgejo)
        else:
            out[gh_name] = _path(forgejo, resolver)
    return out


def pr_to_gh(forgejo_pr: dict) -> dict:
    return _translate(forgejo_pr, PR_FIELDS)


JSON_FIELD_NAMES = {
    "pr": tuple(PR_FIELDS.keys()),
}


ISSUE_FIELDS: dict[str, str | Callable[[dict], Any]] = {
    "number":     "number",
    "title":      "title",
    "body":       "body",
    "state":      lambda p: p["state"].upper(),
    "author":     lambda p: {"login": p["user"]["login"]},
    "createdAt":  "created_at",
    "url":        "html_url",
    "labels":     lambda p: [{"name": lbl["name"], "color": lbl["color"]}
                              for lbl in p.get("labels", [])],
}


def issue_to_gh(forgejo_issue: dict) -> dict:
    return _translate(forgejo_issue, ISSUE_FIELDS)


JSON_FIELD_NAMES["issue"] = tuple(ISSUE_FIELDS.keys())


COMMENT_FIELDS: dict[str, str | Callable[[dict], Any]] = {
    "author":     lambda c: {"login": c["user"]["login"]},
    "body":       "body",
    "createdAt":  "created_at",
    "url":        "html_url",
}


def comment_to_gh(forgejo_comment: dict) -> dict:
    return _translate(forgejo_comment, COMMENT_FIELDS)


# `comments` is served by a second endpoint (/issues/{n}/comments), so only
# `issue view` — which makes that call on demand — can emit it.
JSON_FIELD_NAMES["issue_view"] = (*JSON_FIELD_NAMES["issue"], "comments")


RUN_FIELDS: dict[str, str | Callable[[dict], Any]] = {
    "id":           "id",
    "runNumber":    "run_number",
    "name":         "name",
    "displayTitle": "display_title",
    "headBranch":   "head_branch",
    "headSha":      "head_sha",
    "status":       "status",
    "event":        "event",
    "url":          "url",
    "createdAt":    "created_at",
    "startedAt":    "run_started_at",
    "updatedAt":    "updated_at",
    "workflowId":   "workflow_id",
}


def run_to_gh(forgejo_run: dict) -> dict:
    return _translate(forgejo_run, RUN_FIELDS)


JSON_FIELD_NAMES["run"] = tuple(RUN_FIELDS.keys())


# A single run from /actions/runs, which is a different object from the
# /actions/tasks rows RUN_FIELDS covers: `id` here is the global run id, and
# `runNumber` is the per-repo index shown in web URLs (a task's `run_number`).
ACTION_RUN_FIELDS: dict[str, str | Callable[[dict], Any]] = {
    "id":           "id",
    "runNumber":    "index_in_repo",
    "displayTitle": "title",
    "workflowId":   "workflow_id",
    "headBranch":   "prettyref",
    "headSha":      "commit_sha",
    "status":       "status",
    "event":        "trigger_event",
    "triggeredBy":  lambda r: {"login": r["trigger_user"]["login"]},
    "url":          "html_url",
    "createdAt":    "created",
    "startedAt":    "started",
    "stoppedAt":    "stopped",
}


def action_run_to_gh(forgejo_run: dict) -> dict:
    return _translate(forgejo_run, ACTION_RUN_FIELDS)


JSON_FIELD_NAMES["action_run"] = tuple(ACTION_RUN_FIELDS.keys())
