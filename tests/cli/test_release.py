import json

import httpx
from click.testing import CliRunner

from forge.cli.main import cli

HOST = "https://forgejo.example.com"
REPO = "/api/v1/repos/o/r"


def _patch_client(monkeypatch, mock_transport):
    from forge import client as client_mod
    orig = client_mod.ForgejoClient.__init__
    def patched(self, *, host, token, transport=None, timeout=10.0, debug=False):
        orig(self, host=host, token=token,
             transport=mock_transport.transport(), timeout=timeout, debug=debug)
    monkeypatch.setattr(client_mod.ForgejoClient, "__init__", patched)
    monkeypatch.setenv("FORGEJO_TOKEN", "tok")
    monkeypatch.setenv("FORGEJO_HOST", HOST)


def _pr(number, sha, merged_at="2026-09-29T00:00:00Z"):
    return {
        "number": number, "title": f"PR {number}", "merged": True,
        "merge_commit_sha": sha, "merged_at": merged_at,
        "user": {"login": "samoore"},
        "html_url": f"{HOST}/o/r/pulls/{number}",
    }


def _paged(pages, request):
    """Serve `pages` (a list of row lists) by the request's `page` param."""
    page = int(request.url.params.get("page", "1"))
    return httpx.Response(200, json=pages[page - 1] if page <= len(pages) else [])


class _Forgejo:
    """Routes the handful of endpoints `release create` touches; records the POST."""

    def __init__(self, *, releases=(), tags=("v0.2.0",), commits=(),
                 pulls=(), default_branch="main"):
        self.releases = list(releases)
        self.tags = set(tags)
        self.commits = [list(p) for p in commits]
        self.pulls = [list(p) for p in pulls]
        self.default_branch = default_branch
        self.posted = None
        self.seen = []

    def __call__(self, r: httpx.Request) -> httpx.Response:
        path = r.url.path
        self.seen.append((r.method, path, dict(r.url.params)))
        if r.method == "POST" and path == f"{REPO}/releases":
            self.posted = json.loads(r.content)
            return httpx.Response(201, json={
                "html_url": f"{HOST}/o/r/releases/tag/{self.posted['tag_name']}"})
        if path == f"{REPO}/releases":
            return httpx.Response(200, json=self.releases)
        if path.startswith(f"{REPO}/tags/"):
            tag = path.rsplit("/", 1)[1]
            if tag in self.tags:
                return httpx.Response(200, json={"name": tag})
            return httpx.Response(404, json={"message": "tag not found"})
        if path.startswith(f"{REPO}/compare/"):
            # What an Actions job token gets from compare on Forgejo 14.0.5,
            # even though it can read /pulls and /commits.
            return httpx.Response(404, json={
                "message": "Can't read pulls or can't read UnitTypeCode"})
        if path == f"{REPO}/commits":
            return _paged([[{"sha": s} for s in p] for p in self.commits], r)
        if path == f"{REPO}/pulls":
            return _paged(self.pulls, r)
        if path == REPO:
            return httpx.Response(200, json={"default_branch": self.default_branch})
        return httpx.Response(404, json={"message": f"unrouted {r.method} {path}"})


def _run(*args):
    return CliRunner().invoke(cli, ["release", "create", "-R", "o/r", *args])


def test_create_posts_minimal_payload_titled_by_tag(mock_transport, monkeypatch):
    _patch_client(monkeypatch, mock_transport)
    fj = mock_transport.handler = _Forgejo()
    result = _run("v0.2.0")
    assert result.exit_code == 0, result.output
    assert fj.posted == {"tag_name": "v0.2.0", "name": "v0.2.0", "body": "",
                         "draft": False, "prerelease": False}
    assert result.output.strip() == f"{HOST}/o/r/releases/tag/v0.2.0"


def test_create_maps_gh_flags_onto_forgejo_fields(mock_transport, monkeypatch):
    _patch_client(monkeypatch, mock_transport)
    fj = mock_transport.handler = _Forgejo()
    result = _run("v0.2.0", "--title", "Two", "--notes", "hi",
                  "--draft", "--prerelease", "--target", "abc123")
    assert result.exit_code == 0, result.output
    assert fj.posted == {"tag_name": "v0.2.0", "name": "Two", "body": "hi",
                         "draft": True, "prerelease": True,
                         "target_commitish": "abc123"}


def test_generate_notes_lists_prs_merged_since_previous_release(mock_transport, monkeypatch):
    _patch_client(monkeypatch, mock_transport)
    fj = mock_transport.handler = _Forgejo(
        # Newest first, as Forgejo returns them; the tag being released is skipped.
        releases=[{"tag_name": "v0.2.0"}, {"tag_name": "v0.1.0"}],
        commits=[["m8", "c1"]],
        pulls=[[_pr(8, "m8"), _pr(3, "old")]],
    )
    result = _run("v0.2.0", "--generate-notes")
    assert result.exit_code == 0, result.output
    commit_queries = [q for m, path, q in fj.seen if path == f"{REPO}/commits"]
    assert commit_queries[0]["sha"] == "v0.2.0"
    assert commit_queries[0]["not"] == "v0.1.0"
    release_queries = [q for m, path, q in fj.seen
                       if m == "GET" and path == f"{REPO}/releases"]
    assert release_queries and release_queries[0]["draft"] == "false"
    assert fj.posted["body"] == (
        "## What's Changed\n"
        f"* PR 8 by @samoore in {HOST}/o/r/pulls/8\n"
        "\n"
        f"**Full Changelog**: {HOST}/o/r/compare/v0.1.0...v0.2.0"
    )


def test_generate_notes_first_release_walks_all_history(mock_transport, monkeypatch):
    _patch_client(monkeypatch, mock_transport)
    fj = mock_transport.handler = _Forgejo(
        tags={"v0.1.0"},
        commits=[["m7", "c2"], ["c1"]],
        pulls=[[_pr(7, "m7")]],
    )
    result = _run("v0.1.0", "--generate-notes")
    assert result.exit_code == 0, result.output
    commit_pages = [p for m, path, p in fj.seen if path == f"{REPO}/commits"]
    assert all(p["sha"] == "v0.1.0" and "not" not in p for p in commit_pages)
    assert f"* PR 7 by @samoore in {HOST}/o/r/pulls/7" in fj.posted["body"]
    assert fj.posted["body"].endswith(
        f"**Full Changelog**: {HOST}/o/r/commits/tag/v0.1.0")


def test_generate_notes_reads_every_page_even_when_server_caps_page_size(
        mock_transport, monkeypatch):
    """A server whose max page size is below our `limit` must not truncate notes."""
    _patch_client(monkeypatch, mock_transport)
    fj = mock_transport.handler = _Forgejo(
        releases=[{"tag_name": "v0.1.0"}],
        commits=[["a", "b", "c"]],
        pulls=[[_pr(1, "a"), _pr(2, "b")], [_pr(3, "c")]],
    )
    result = _run("v0.2.0", "--generate-notes")
    assert result.exit_code == 0, result.output
    for n in (1, 2, 3):
        assert f"PR {n} by" in fj.posted["body"]


def test_generate_notes_for_a_new_tag_ranges_to_the_default_branch(
        mock_transport, monkeypatch):
    _patch_client(monkeypatch, mock_transport)
    fj = mock_transport.handler = _Forgejo(
        releases=[{"tag_name": "v0.1.0"}], tags=(), default_branch="trunk")
    result = _run("v0.2.0", "--generate-notes")
    assert result.exit_code == 0, result.output
    commit_queries = [q for m, path, q in fj.seen if path == f"{REPO}/commits"]
    assert commit_queries[0]["sha"] == "trunk"
    assert commit_queries[0]["not"] == "v0.1.0"


def test_notes_are_prepended_to_generated_notes(mock_transport, monkeypatch):
    _patch_client(monkeypatch, mock_transport)
    fj = mock_transport.handler = _Forgejo(releases=[{"tag_name": "v0.1.0"}])
    result = _run("v0.2.0", "--notes", "Intro.", "--generate-notes")
    assert result.exit_code == 0, result.output
    assert fj.posted["body"] == (
        "Intro.\n\n"
        f"**Full Changelog**: {HOST}/o/r/compare/v0.1.0...v0.2.0"
    )
