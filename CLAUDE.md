# forge — conventions

## Dependency direction (load-bearing)

`src/forge/cli/*.py` may import from `client.py`, `translate.py`, `repo.py`, `errors.py`. **The reverse is forbidden.**

This is the seam that lets `forgejo_client/` be extracted as a separate library later without code changes. When/if a second consumer (e.g., agent-runner, storyteller) needs programmatic access to Forgejo, the extraction is mechanical: move the four files to a new package, update one import line in each `cli/*.py` module.

## Translation tables

Each resource (PR, issue) has a `<RESOURCE>_FIELDS: dict[str, str | Callable]` table in `translate.py`. String values are dot-paths into Forgejo's JSON. Callable values receive the full Forgejo dict and return the gh-shape value. To add a field:

1. Extend the table
2. Update the fixtures (forgejo + gh sides)
3. Snapshot test catches drift automatically

Never special-case at the call site.

## Forgejo API quirks (don't be surprised by these)

- **PR merge:** `{"Do": "merge"}` — capital D. Forgejo-specific.
- **Issues endpoint:** `/repos/o/r/issues` returns issues AND PRs unless `&type=issues` is passed. `forge issue list` always passes the filter.
- **Issue create labels:** must be integer IDs, not names. `forge issue create --label bug` resolves names client-side via `GET /repos/o/r/labels` first.
- **PR comments:** posted to `/issues/{N}/comments` (the issues endpoint), not `/pulls/{N}/comments`. Same as gh.

## Error classes

Six typed exceptions in `errors.py`, each with a static `code` class attribute mapping to exit codes 1-6:

- `ForgeError` (base, code=1, generic error)
- `UsageError` (code=2)
- `NotFoundError` (code=3)
- `AuthError` (code=4)
- `ServerError` (code=5)
- `ValidationError` (code=6)

To add a new error category, inherit directly from `ForgeError`, never from a sibling. Assign a new code; don't reuse. Update `_ERROR_LABELS` in `cli/main.py` for the user-facing label.

## Tests

Three rings: pure unit (no HTTP), mocked HTTP (`httpx.MockTransport` via the `mock_transport` fixture in `conftest.py`), opt-in live tests (`tests/live/`, gated by `FORGE_LIVE_TESTS=1`). CI runs the first two. The fixture-capture script is deferred to v0.2.

The `env_no_token` fixture strips token-related env vars AND redirects `DEFAULT_SECRETS_PATH` to a non-existent tmp path, ensuring negative tests are hermetic.

## Per-file CLI helpers

`cli/pr.py` and `cli/issue.py` each have their own copies of `_build_client`, `_resolve`, and `_filter_json`. This duplication is intentional for v0.1 — extraction to `cli/_common.py` happens when divergence pressure justifies it (likely v0.2). Tests monkeypatch by module path (`forge.cli.pr._build_client`), so per-file copies are part of the test contract.
