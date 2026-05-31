# forge — conventions

## Known v0.2 limitations

- No `forge run rerun` — Forgejo 11 exposes no rerun API. (Workaround: push an empty commit to retrigger.)
- No `forge workflow run` (workflow_dispatch trigger). Deferred to v0.3.
- No single-run view (`forge run view <id>`). Forgejo has no GET single-run endpoint; only the bulk `/actions/tasks` list works.
- No `pr edit --add-label/--add-assignee/--milestone`. v0.2 supports only `--title/--body/--base`.
- `--no-retry` flag and `Retry-After` header handling not implemented (deferred to v0.3; self-hosted Forgejo rarely rate-limits).
- Per-file `_build_client` / `_resolve` duplication in cli/{auth,issue,pr,run}.py. Lift to cli/_common.py when divergence pressure justifies it.
- Live fixture-capture script (`tests/fixtures/capture.py`) deferred to v0.3; current fixtures are hand-crafted from Forgejo's documented response shapes.
- `forge pr log` always exits 0 once at least one matching run exists, even if every single log fetch raises NotFoundError. (Edge case unlikely in practice — Forgejo retains all failed-run logs.)

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

## Repo resolution gotchas

When the origin remote uses an SSH `Host` alias from `~/.ssh/config`
(e.g. `mooregit:owner/repo.git`), forge expands the alias via `ssh -G`
to get the effective hostname before checking against the configured
Forgejo host. This delegates to ssh's own config parser, handling
Match blocks, Include directives, etc.

If `ssh -G` fails (no ssh binary, no matching config), forge falls
back to the literal alias name. The host-mismatch error still fires
if the resolved name doesn't match the configured host.

## Log access (v0.2)

Forgejo 11.0.14 / Gitea-1.22 exposes no log endpoint in its REST API. `forge`
reads logs from disk by `docker exec`-ing into the Forgejo container and
catting `/data/gitea/actions_log/{owner}/{repo}/{id_hex}/{id}.log.zst`.

- Requires `--container <name>` flag or `FORGEJO_CONTAINER` env var
- Only failed runs retain logs (Forgejo cleans up successful ones on completion)
- `id_hex = format(task_id, 'x')` — full lowercase hex of the task ID
- See `src/forge/logs.py` for the path/decompression code

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
