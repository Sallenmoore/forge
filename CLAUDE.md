# forge — conventions

## Known v0.2 limitations

- `forge run cancel` / `forge run rerun` only explain themselves: Forgejo's REST API has neither (checked against the 14.0.5 swagger; they are web-UI routes needing a session cookie + CSRF). They exit 1 with the run's web URL. Revisit if upstream adds the endpoints.
- No `forge workflow run` (workflow_dispatch trigger). Deferred to v0.3.
- No `pr edit --add-label/--add-assignee/--milestone`. v0.2 supports only `--title/--body/--base`.
- `--no-retry` flag and `Retry-After` header handling not implemented (deferred to v0.3; self-hosted Forgejo rarely rate-limits).
- Live fixture-capture script (`tests/fixtures/capture.py`) deferred to v0.3; current fixtures are hand-crafted from Forgejo's documented response shapes.
- `forge pr log` always exits 0 once at least one matching run exists, even if every single log fetch raises NotFoundError. (Edge case unlikely in practice — Forgejo retains task logs.)

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
- **Three run numbers.** `/actions/tasks` rows (what `run list` shows) have a task `id` and a `run_number`; the `run_number` is the per-repo index in web URLs (`/actions/runs/153`). `/actions/runs/{id}` wants a *third* number, the global run id, that nothing user-facing shows. `forge run view N` therefore queries `/actions/runs?run_number=N`, never `/actions/runs/N`, which silently returns a different run.
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

Precedence is `-R` > `FORGEJO_DEFAULT_REPO` > origin remote, mirroring
gh's `-R` > `GH_REPO` > remote. The env var must outrank the remote:
the remote check *raises* on a host mismatch, so ranking it first made
the mismatch error's own "or set FORGEJO_DEFAULT_REPO" advice
unreachable. Consequence worth knowing — exporting
`FORGEJO_DEFAULT_REPO` in a shell profile pins every invocation in
every checkout, exactly as `GH_REPO` does.

## Log access (v0.2)

Forgejo's REST API has no log endpoint (11.0.14, and still none in 14.0.5). `forge`
reads logs from disk by `docker exec`-ing into the Forgejo container and
catting `/data/gitea/actions_log/{owner}/{repo}/{shard}/{id}.log.zst`.

- Requires `--container <name>` flag or `FORGEJO_CONTAINER` env var
- `shard = f"{task_id % 256:02x}"` — the task id's low byte, zero-padded (292 → `24`).
  Through v0.2.0 this was `format(task_id, 'x')`, the full hex, which happens to agree
  for ids 16–255 only; every task from 256 up reported "not found". Verified against all
  196 log files on the 14.0.5 instance, 2026-09-30.
- Logs are kept for **successful** tasks too — the earlier "only failed runs retain logs"
  note was a misreading of the path bug above. A miss usually means a run number was
  passed where a task id belongs (`run list`'s first column is the task id).
- Re-check the path after a Forgejo major upgrade
- See `src/forge/logs.py` for the path/decompression code

## Release notes

`release create --generate-notes` has no Forgejo endpoint to call (none through 14.0.5),
so `release_notes.py` rebuilds GitHub's rule client-side: a PR is in a release when its
`merge_commit_sha` lies in the release's commit range — `commits?sha={tag}&not={prev}`,
or the whole history under the tag for a first release. **Not the compare endpoint:**
an Actions job token gets a 404 from `/compare` ("Can't read pulls or can't read
UnitTypeCode") on 14.0.5 while reading `/commits` and `/pulls` fine — measured from
inside a job, 2026-10-01. That one release job is `release create`'s main caller. Not by merge date: that misfiles PRs
merged into other branches. The previous release is the newest published one other than
the tag being created. Only PRs appear; commits pushed straight to the branch don't.

`ForgejoClient.paginate` stops on the first *empty* page, not the first short one, so a
server whose max page size is below the requested `limit` can't silently truncate.

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

Three rings: pure unit (no HTTP), mocked HTTP (`httpx.MockTransport` via the `mock_transport` fixture in `conftest.py`), opt-in live tests (`tests/live/`, gated by `FORGE_LIVE_TESTS=1`). CI runs the first two. The fixture-capture script is deferred to v0.3.

The `env_no_token` fixture strips token-related env vars AND redirects `DEFAULT_SECRETS_PATH` to a non-existent tmp path, ensuring negative tests are hermetic.

## Shared CLI helpers

`resolved_host`, `build_client`, `resolve_spec` and `resolve` live in `cli/_common.py`,
imported by `cli/pr.py`, `cli/issue.py` and `cli/run.py`. They were per-file copies through v0.1.0; the copies
drifted (`_build_client` consulted `FORGEJO_HOST`, `_resolve` did not), so the API
client and the origin-host check could target different instances. One definition
removes the class of bug — keep it that way.

Tests monkeypatch `forge.cli._common.build_client`, not a per-module name.

`filter_json` / `requested_fields` joined them in v0.2, when `cli/run.py` became the
third consumer. `feat/v0.2` was written before the v0.1.2 extraction and carried fresh
per-file copies of all three helpers into `run.py` — including the original
`FORGEJO_HOST` drift bug in `run log`. When landing an old branch, grep it for
`resolve_repo(` and `DEFAULT_HOST` outside `_common.py`.

`cli/auth.py` keeps its own `_build_client`: it has no repo-resolution half to drift
against, and its tests patch it by that name.
