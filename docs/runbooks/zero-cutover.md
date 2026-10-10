# zero cutover — from the public Teman2 to the private FastLabsNet/zero

> Owner decision (2026-10-09/10): `Bali-Zero/Teman2` is PUBLIC and exposes clients in its
> history, so it is deleted together with that history. The products live on GitHub in the
> private `FastLabsNet/zero` (product-only, no history); the organism and the full history
> live in the local canonical repository (LOCALCI phase F's mirror on Pro). This runbook is
> the ordered list of what stands between today and the deletion, and who owns each step.

## State on 2026-10-10

| Piece                   | State                                                                                                                                                                               |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `FastLabsNet/zero`      | product-only snapshot of canonical `60c2a5c245` (single commit) + its own CI                                                                                                        |
| zero CI                 | `.github/workflows/ci.yml` on the self-hosted runner `mini-zero-1` (Linux container in Colima on Mini, LAN/tailnet/host blocked); 0 GitHub-hosted jobs                              |
| zero perimeter          | zero's `.slim/keep_paths.txt`, `cut_paths.txt`, `local_paths.txt`; `.github/` and `.slim/` are zero-owned                                                                           |
| canonical → zero sync   | `scripts/zero_sync/` + organ `mini.zero_sync` (every 30 min, fast-forward only, refuses to revert a direct zero change)                                                             |
| deploys                 | still from Teman2: `fly-deploy.yml` (backend), Vercel git integration + `mini.vercel_autopromote` (mouth)                                                                           |
| zero's deploy workflows | present, disabled through the API (`fly-deploy`, `garuda-arm`, `frontend-live-sentinel`, `lighthouse`, `tests`, `frontend-typecheck`); no secrets uploaded                          |
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
| 1   | LOCALCI READY and phase F armed (`docs/specs/localci-sovereign-2026-10-07.md` §2, phase D window ≥ 50 compared merges over ≥ 14 days, counting from 2026-10-09)                                                                                                                                                                                                                    | LOCALCI lead                                                                | the merger advances the mirror's `refs/merger/base`, then pushes it as Teman2's `main` |
| 2   | ~~zero recreated clean~~ — waived by the owner on 2026-10-10 (zero is private; see the section above)                                                                                                                                                                                                                                                                              | —                                                                           | —                                                                                      |
| 3   | sync source moves to the mirror: `ZERO_SYNC_CANONICAL_URL=ssh://<pro>/…/merger/repo.git` in the plist environment, plus the ref `refs/merger/base` (a code change first: Dry runs below); Mini reaches Pro over Tailscale SSH                                                                                                                                                      | session                                                                     | `mini.zero_sync` heartbeat `ok` with the new source                                    |
| 4   | roster outside git: `fly secrets set TEAM_MEMBERS_JSON` from the canonical file **through stdin** (never on the command line, never echoed) — only at the moment zero becomes the deploy source, because from then on the secret is the roster's SSOT                                                                                                                              | session (credential: operator)                                              | `/health` green and the backend logs `team roster ... source=env:TEAM_MEMBERS_JSON`    |
| 5   | backend deploys from zero: `fly-deploy.yml` on `[self-hosted, zero]` with `superfly/flyctl-actions/setup-flyctl`, secrets `FLY_API_TOKEN` (scoped to `nuzantara-rag`) and `SMOKE_TEST_API_KEY` uploaded; **Teman2's `fly-deploy.yml` disabled in the same step** — two deploy sources race (superscar #10)                                                                         | session                                                                     | one zero merge touching `apps/backend-rag/**` deploys and proves live                  |
| 6   | mouth deploys from zero: either the Vercel GitHub app installed on FastLabsNet (org owner, GUI) and the project re-linked to zero, or `vercel deploy --prod` from the runner with a `VERCEL_TOKEN` secret; `mini.vercel_autopromote` keeps promoting staged builds                                                                                                                 | org owner or session                                                        | one zero merge touching `apps/mouth/**` is live on balizero.com                        |
| 7   | remotes and slugs: `origin` on M5, Pro and Mini points at the mirror; the 65 code files that name `Bali-Zero/Teman2` (mostly GitHub merge-queue tooling that phase F retires) are retired or repointed; `localci_merger_tick.sh` stops pushing to Teman2                                                                                                                           | session                                                                     | `git grep -c "Bali-Zero/Teman2" -- scripts infra .github` is 0 outside archaeology     |
| 8   | export: Zero runs `gh auth refresh -h github.com -s admin:org,delete_repo` (interactive); `POST /orgs/Bali-Zero/migrations` with `repositories: ["Teman2"]` (issues, PRs, reviews, comments, releases, wiki); download the archive, check PR/issue counts against the API, store it on Mini (`0700` directory, never in git) together with `git bundle create --all` of the mirror | Zero (scope) + session                                                      | archive and bundle verified (`git bundle verify`), counts match                        |
| 9   | delete `Bali-Zero/Teman2`                                                                                                                                                                                                                                                                                                                                                          | **Zero's explicit go at that moment** — no standing authorization covers it | `gh api repos/Bali-Zero/Teman2` returns 404                                            |

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
  - The wrapper passes no arguments, the payload takes only the URL from the environment, and
    `--canonical-ref` defaults to `main`. Pointing the URL alone at the mirror would read the 2026-10-07
    tree as canonical.
  - So gate 3 also sets the ref, and neither way of doing it exists today. A PR lands first, either:
    - a `ZERO_SYNC_CANONICAL_REF` fallback for `--canonical-ref` in `zero_sync.py`, after which the plist sets it;
    - or the wrapper passing `--canonical-ref refs/merger/base`, after which the wrapper is reinstalled on Mini.
- **Just before the flip**, re-run the dry run above and check that `refs/merger/base` equals Teman2's `main`
  (`git ls-remote` on both). The base moves once per merger tick (about 10 minutes), so if it trails by a
  merge, wait for the next tick.
- **Rollback:** restore the plist and the wrapper from git and re-bootstrap the job. The source returns to
  Teman2.

## Never

- Upload `FLY_API_TOKEN` to zero before gate 5: `fly-deploy.yml` would deploy production from
  a tree without the roster, racing Teman2's deploys.
- Merge product changes directly on zero while the sync runs: the sync refuses until the same
  change lands in canonical. Port the change to canonical (one PR) and let the sync carry it.
- Privatize Teman2 as a "temporary" step: the owner ruled it out; the exposure is in the
  history, and privatizing keeps that history alive.
