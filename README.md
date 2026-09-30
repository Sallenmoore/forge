# forge

`gh`-compatible CLI for the self-hosted Forgejo.

## Install

```bash
pipx install -e /opt/projects/forge
pipx ensurepath
```

(Or `pip install --user -e /opt/projects/forge` if you prefer pip over pipx.)

## Quickstart

```bash
forge auth status
forge pr list -R user/repo
forge issue create -R user/repo --title "..." --body "..." --label bug
```

## Config

**Token precedence:**

1. `--token <value>` CLI flag
2. `FORGEJO_TOKEN` env var
3. `FORGEJO_API_KEY` line in `~/.secrets/forgejo.env`

**Instance URL:** `--host <url>` → `FORGEJO_HOST` env → default.

**Repo resolution:** `-R owner/repo` → `git remote -v` (origin must point at the configured Forgejo) → `FORGEJO_DEFAULT_REPO` env.

## Subcommands (v0.2)

| Noun | Subcommands |
|---|---|
| `auth` | `status`, `git-credential` |
| `pr` | `list`, `view`, `create`, `merge`, `checks`, `comment`, `close`, `reopen`, `edit`, `log` |
| `issue` | `list`, `view`, `create`, `close`, `comment` |
| `run` | `list`, `log`, `view` (`cancel`/`rerun` point at the web UI) |
| `release` | `create` (with gh's `--generate-notes`, built client-side) |

See [.github_compat_table.md](./.github_compat_table.md) for the full `gh` → `forge` mapping.

## Design + plan

The v0.2 design + plan are at [`docs/specs/2026-05-31-v0.2-design.md`](./docs/specs/2026-05-31-v0.2-design.md) and [`docs/plans/2026-05-31-v0.2-implementation.md`](./docs/plans/2026-05-31-v0.2-implementation.md). The original v0.1 design is at [`docs/specs/2026-05-26-design.md`](./docs/specs/2026-05-26-design.md) and the v0.1 plan at [`docs/plans/2026-05-26-v0.1-implementation.md`](./docs/plans/2026-05-26-v0.1-implementation.md).
