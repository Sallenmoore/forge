# src/forge/release_notes.py
"""Client-side stand-in for GitHub's release-notes generation.

Forgejo (checked on 14.0.5) has no generate-notes endpoint, so
`release create --generate-notes` builds the body here. The rule mirrors
GitHub's: a PR belongs to a release when its merge commit lies in the
release's commit range — not when it merged by some date, which misfiles
PRs merged into other branches.

Pure functions; the CLI does the fetching.
"""


def select_prs(prs: list[dict], commit_shas: set[str]) -> list[dict]:
    """Merged PRs whose merge commit is in `commit_shas`, oldest merge first."""
    picked = [p for p in prs
              if p.get("merged") and p.get("merge_commit_sha") in commit_shas]
    return sorted(picked, key=lambda p: p["merged_at"])


def format_notes(prs: list[dict], *, changelog_url: str) -> str:
    """Render in gh's layout: a "What's Changed" list, then the changelog link."""
    lines = []
    if prs:
        lines.append("## What's Changed")
        lines += [f"* {p['title']} by @{p['user']['login']} in {p['html_url']}"
                  for p in prs]
        lines.append("")
    lines.append(f"**Full Changelog**: {changelog_url}")
    return "\n".join(lines)
