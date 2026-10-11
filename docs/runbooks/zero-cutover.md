# zero cutover — from the public Teman2 to the private FastLabsNet/zero

> Owner decision (2026-10-09/10): `Bali-Zero/Teman2` is PUBLIC and exposes clients in its
> history, so it is deleted together with that history. The products live on GitHub in the
> private `FastLabsNet/zero` (product-only, no history); the organism and the full history
> live in the local canonical repository (LOCALCI phase F's mirror on Pro). This runbook is
> the ordered list of what stands between today and the deletion, and who owns each step.

## State on 2026-10-11

| Piece                   | State                                                                                                                                                                               |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `FastLabsNet/zero`      | product-only snapshot of canonical `60c2a5c245` (single commit) + its own CI                                                                                                        |
| zero CI                 | `.github/workflows/ci.yml` on the self-hosted runner `mini-zero-1` (Linux container in Colima on Mini, LAN/tailnet/host blocked); 0 GitHub-hosted jobs                              |
| zero perimeter          | zero's `.slim/keep_paths.txt`, `cut_paths.txt`, `local_paths.txt`; `.github/` and `.slim/` are zero-owned                                                                           |
| canonical → zero sync   | `scripts/zero_sync/` + organ `mini.zero_sync` (every 5 min, fast-forward only, refuses to revert a direct zero change)                                                              |
| deploys                 | backend from zero since 2026-10-11 (gates 4–5, below); mouth still from Teman2 (`vercel_prod_deploy.py` gitSource + `mini.vercel_autopromote`)                                      |
| zero's deploy workflows | `fly-deploy` active (secret `FLY_API_TOKEN`, an app-scoped deploy token); `garuda-arm`, `frontend-live-sentinel`, `lighthouse`, `tests`, `frontend-typecheck` disabled              |
| staff roster            | `backend/core/team_roster.py` reads `TEAM_MEMBERS_JSON` → `TEAM_MEMBERS_FILE` → the package file; zero carries only `team_members.synthetic.json` (invented people, used by its CI) |

## Accepted exposure on zero (owner decision 2026-10-10)

zero still makes two things reachable to anyone with read access to it:

- the old Teman2 history, through 34 `refs/pull/*` refs left by the first migration;
- staff personal data in zero's first commit (the stale `backend/data/team_members.py`, emptied on the tip by the
  roster loader and the first sync).

The owner accepted both: zero is private, so it is **not** recreated. Do not raise it again as an ask. Only a
change of fact reopens it, for example zero turning public or someone outside the owner's control getting read
access.

## Ordered gates to the deletion

| #   | Gate                                                                                                                                                                                                                                                                                                                                                                               | Owner                                                                       | Done when                                                                              |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| 1   | LOCALCI READY and phase F armed (`docs/specs/localci-sovereign-2026-10-07.md` §2, phase D window ≥ 50 compared merges over ≥ 14 days, counting from 2026-10-09)                                                                                                                                                                                                                    | LOCALCI lead                                                                | the merger pushes Teman2's `main`, then advances the mirror's `refs/merger/base` to it |
| 2   | ~~zero recreated clean~~ — waived by the owner on 2026-10-10 (zero is private; see the section above)                                                                                                                                                                                                                                                                              | —                                                                           | —                                                                                      |
| 3   | sync source moves to the mirror: `ZERO_SYNC_CANONICAL_URL=ssh://<pro>/…/merger/repo.git` in the plist environment, plus `ZERO_SYNC_CANONICAL_REF=refs/merger/base` (Dry runs below); Mini reaches Pro over Tailscale SSH                                                                                                                                                           | session                                                                     | `mini.zero_sync` heartbeat `ok` with the new source                                    |
| 4   | roster outside git: `fly secrets set TEAM_MEMBERS_JSON` from the canonical file **through stdin** (never on the command line, never echoed) — only at the moment zero becomes the deploy source, because from then on the secret is the roster's SSOT                                                                                                                              | session (credential: operator)                                              | `/health` green and the backend logs `team roster ... source=env:TEAM_MEMBERS_JSON`    |
| 5   | backend deploys from zero: `fly-deploy.yml` on `[self-hosted, zero]` with `superfly/flyctl-actions/setup-flyctl`, secrets `FLY_API_TOKEN` (scoped to `nuzantara-rag`) and `SMOKE_TEST_API_KEY` uploaded; **Teman2's `fly-deploy.yml` disabled in the same step** — two deploy sources race (superscar #10)                                                                         | session                                                                     | one zero merge touching `apps/backend-rag/**` deploys and proves live                  |
| 6   | mouth deploys from zero: either the Vercel GitHub app installed on FastLabsNet (org owner, GUI) and the project re-linked to zero, or `vercel deploy --prod` from the runner with a `VERCEL_TOKEN` secret; `mini.vercel_autopromote` keeps promoting staged builds                                                                                                                 | org owner or session                                                        | one zero merge touching `apps/mouth/**` is live on balizero.com                        |
| 7   | remotes and slugs: `origin` on M5, Pro and Mini points at the mirror; the 65 code files that name `Bali-Zero/Teman2` (mostly GitHub merge-queue tooling that phase F retires) are retired or repointed; `localci_merger_tick.sh` stops pushing to Teman2                                                                                                                           | session                                                                     | `git grep -c "Bali-Zero/Teman2" -- scripts infra .github` is 0 outside archaeology     |
| 8   | export: Zero runs `gh auth refresh -h github.com -s admin:org,delete_repo` (interactive); `POST /orgs/Bali-Zero/migrations` with `repositories: ["Teman2"]` (issues, PRs, reviews, comments, releases, wiki); download the archive, check PR/issue counts against the API, store it on Mini (`0700` directory, never in git) together with `git bundle create --all` of the mirror | Zero (scope) + session                                                      | archive and bundle verified (`git bundle verify`), counts match                        |
| 9   | delete `Bali-Zero/Teman2`                                                                                                                                                                                                                                                                                                                                                          | **Zero's explicit go at that moment** — no standing authorization covers it | `gh api repos/Bali-Zero/Teman2` returns 404                                            |

## Progress on 2026-10-11

- **Gate 4: done.** `TEAM_MEMBERS_JSON` was staged with `fly secrets import --stage`, the canonical file compacted and piped through stdin (19 entries, never printed), and it was applied by the first zero deploy. Live, the loader reads `env:TEAM_MEMBERS_JSON 19` (`team_roster_source()` over `fly ssh console`). From now on, a roster edit in canonical reaches production only when the secret is re-imported the same way.
- **Gate 5: done.**
  - Zero #54 moved the 7 jobs to `[self-hosted, zero]`, replaced the ghcr Postgres sidecar with the local recipe from `ci.yml`, and set `GIT_SHA` from the newest `Zero-Sync-Canonical` trailer, refusing to deploy without one.
  - Zero #55 removed the pip cache, because its save step hung for more than 18 minutes on the runner.
  - Teman2's `fly-deploy.yml` was disabled (`disabled_manually`) and zero's enabled.
  - The first run, 38124509097, was green on every job. `/health` reported `build_sha` `033772cbdc`, the canonical sha.
  - Rollback: `gh workflow enable fly-deploy.yml -R Bali-Zero/Teman2` and disable zero's copy.
  - `scripts/post-deploy-verify.sh` follows a merge into the zero run that contains it.
- **Gate 6 (mouth), open.** `vercel_prod_deploy.py` creates deployments with `gitSource` on Teman2, and that source disappears at gate 9. The route without GitHub is a CLI upload from a tree built at the canonical sha.
  - That tree is the root manifests plus `apps/mouth` and `packages`: 8,675 tracked files, 780 MB, of which `public/` is 683 MB. Vercel uploads by content, so after the first deploy only changed files travel.
  - The upload carries `BUILD_COMMIT_SHA` as build and runtime env, and `apps/mouth/src/app/api/health/route.ts` falls back to it after `VERCEL_GIT_COMMIT_SHA`.
  - With the Vercel GitHub app on FastLabsNet instead (org owner, GUI), the commit would be zero's sha, so the same fallback would be needed anyway.
- **Gate 7b (new): Teman2's scheduled workflows.** 29 of Teman2's 132 workflows run on `schedule:` (25 distinct ones ran on 2026-10-10). They are organs on GitHub Actions and they end with the repository. Each one moves to a Mini or Pro launchd job or to zero's runner, or is retired, before gate 9.
- **Gate 7: inventory.** The 72 files in `scripts`, `infra` and `.github` that name `Bali-Zero/Teman2` break down as follows:
  - 25 retire (merge-queue, PR and Actions tooling);
  - 5 are live organs calling the GitHub API (`queue-baseline`, `suite-growth-probe`, `queue_shepherd`, `regulatory-watcher-run`, `jules_dispatch`);
  - 5 repoint to the mirror (`localci_merger_tick.sh` and `zero_sync.py` first);
  - 1 repoints to zero (`vercel_prod_deploy.py`);
  - 36 are archaeology or test fixtures.
  - There are 121 more files outside those directories, not yet classified.
- **Intake without GitHub.** The merger needs a way to receive candidates once GitHub is gone. It is specified in `docs/specs/localci-sovereign-2026-10-07.md`, "Phase F intake without GitHub", status RULING PENDING, and gated by the LocalCI lane. Gate 1 cannot complete without it.
- **Residuals.**
  - Zero has a single runner, so a deploy queues behind zero CI: about +13 minutes, and worst case about 30 minutes from merge to live.
  - `SMOKE_TEST_API_KEY` is not set on zero; the RAG smoke test is `continue-on-error`.
  - `fly ssh console` from M5 fails with "no access token" while `fly auth whoami` succeeds, so use Pro.

## Dry runs already made

- **Gate 3, 2026-10-10, on Mini.** The dry run read the mirror over Tailscale SSH, passed the content
  identity checks and printed `zero-sync: up to date (canonical ed59bc4180)`, the same commit as Teman2's
  `main`. Its state directory was removed afterwards. The command:

  ```bash
  zero_sync.py --dry-run --state-dir <tmp> \
    --canonical-url ssh://pro/Users/nuzantara/.nuzantara-pilots/local-ci/merger/repo.git \
    --canonical-ref refs/merger/base
  ```

- **Gate 3 needs the ref as well as the URL.**
  - In the mirror, the merger writes only `refs/merger/base`, in shadow and in phase F alike (`merger.py`
    runs `update-ref refs/merger/base` after a fetch or after a push that landed).
  - The mirror's `refs/heads/main` is its seed, `56c6f70d86` from 2026-10-07, and it never moves.
  - So at gate 3 the sync's source ref is `refs/merger/base`, not `main`.
  - The wrapper passes no arguments and the ref defaults to `main`. Pointing the URL alone at the mirror
    would read the 2026-10-07 tree as canonical.
  - So gate 3 also sets `ZERO_SYNC_CANONICAL_REF=refs/merger/base` in the job env, next to the URL. The
    payload reads it as the default of `--canonical-ref`.
- **Just before the flip**, re-run the dry run above and check that `refs/merger/base` equals Teman2's `main`
  (`git ls-remote` on both). The base moves once per merger tick (about 10 minutes), so if it trails by a
  merge, wait for the next tick.
- **Rollback:** restore the plist and the wrapper from git and re-bootstrap the job. The source returns to
  Teman2.

## Never

- Re-enable Teman2's `fly-deploy.yml` while zero's is active: two deploy sources race (superscar #10).
  A rollback disables zero's copy in the same step.
- Merge product changes directly on zero while the sync runs: the sync refuses until the same
  change lands in canonical. Port the change to canonical (one PR) and let the sync carry it.
- Privatize Teman2 as a "temporary" step: the owner ruled it out; the exposure is in the
  history, and privatizing keeps that history alive.
