from forge import release_notes


def _pr(number, sha, merged_at, merged=True, login="samoore"):
    return {
        "number": number, "title": f"PR {number}", "merged": merged,
        "merge_commit_sha": sha, "merged_at": merged_at,
        "user": {"login": login},
        "html_url": f"https://f/o/r/pulls/{number}",
    }


def test_select_prs_keeps_only_merges_inside_the_range():
    prs = [
        _pr(1, "aaa", "2026-01-01T00:00:00Z"),
        _pr(2, "bbb", "2026-01-02T00:00:00Z"),               # before the range
        _pr(3, "ccc", "2026-01-03T00:00:00Z", merged=False),  # closed unmerged
    ]
    picked = release_notes.select_prs(prs, {"aaa", "ccc"})
    assert [p["number"] for p in picked] == [1]


def test_select_prs_orders_oldest_merge_first():
    prs = [
        _pr(9, "b", "2026-02-01T00:00:00Z"),
        _pr(4, "a", "2026-01-01T00:00:00Z"),
    ]
    assert [p["number"] for p in release_notes.select_prs(prs, {"a", "b"})] == [4, 9]


def test_format_notes_matches_gh_layout():
    notes = release_notes.format_notes(
        [_pr(7, "x", "2026-09-29T00:00:00Z")],
        changelog_url="https://f/o/r/compare/v0.1.0...v0.2.0",
    )
    assert notes == (
        "## What's Changed\n"
        "* PR 7 by @samoore in https://f/o/r/pulls/7\n"
        "\n"
        "**Full Changelog**: https://f/o/r/compare/v0.1.0...v0.2.0"
    )


def test_format_notes_without_prs_is_just_the_changelog_link():
    notes = release_notes.format_notes([], changelog_url="https://f/o/r/commits/tag/v1")
    assert notes == "**Full Changelog**: https://f/o/r/commits/tag/v1"
