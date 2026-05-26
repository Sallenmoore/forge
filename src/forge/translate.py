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
