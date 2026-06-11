# Runbook — Review-gate (Pro-side tri-LLM review-only)

> **What it is.** An H24 Pro LaunchAgent that posts an automated 3-LLM review
> **comment** on every open `agent/*` PR whose head SHA is new. It is the
> review half of the meta-dev-loop review gate.
>
> **What it is NOT.** It never labels, approves, or merges. Merge stays the
> operator's decision (Legge 5). Auto-merge is a separate, **deferred** phase
> (GitHub App check-run — see the deferred spec, task #3).

## Components

| Artifact                                             | Role                                                                                                                                   |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `scripts/review_gate_run.sh`                         | Sweep wrapper: enumerate open `agent/*` PRs, review the ones with a new head SHA, post a comment. flock + idempotency + per-sweep cap. |
| `scripts/codex_tri_llm_review.py --pr N --comment`   | The 3-LLM panel (Codex GPT-5.5 · Claude Opus · DeepSeek V4-Pro). Posts the verdict comment.                                            |
| `infra/launchagents/com.nuzantara.review-gate.plist` | StartInterval 600s, KeepAlive false, **no secrets in plist**, runtime home = deploy worktree.                                          |
| `infra/launchagents/install_fase0_governance.sh`     | Installer (the review-gate is folded into the FASE-0 governance installer).                                                            |
| `~/.agent/decisions/state/review_gate_seen.json`     | Per-PR last-reviewed head SHA (idempotency).                                                                                           |

## Trust model (review-only)

The comment is **informational**. It carries no merge authority — a `repo:status`
token, a hand-applied label, or a re-pushed SHA cannot turn a comment into a
merge. The footer says so verbatim. This is why review-only ships now with zero
new attack surface, while auto-merge waits for the unforgeable App check-run.

## Safety properties (falsifiable)

| Gate              | How it holds                                                                                           | How to falsify                                                          |
| ----------------- | ------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------- |
| **G-comment**     | posts a 3-LLM verdict comment on a real `agent/*` PR                                                   | comment appears on the PR                                               |
| **G-idempotent**  | per-`(pr, head_sha)` state file; unchanged head → skip                                                 | run the sweep twice on an unchanged PR → exactly one comment            |
| **G-fail-closed** | a truncated diff → `diff_complete=False` → forced `inconclusive`, comment says "treat as NOT reviewed" | review a PR whose diff > `--max-diff-chars` → comment is not a green    |
| **G-flock**       | `fcntl.flock(LOCK_EX\|LOCK_NB)`; busy lock → exit 0                                                    | hold the lock, run a 2nd sweep → "lock held — skipping"                 |
| **G-no-secrets**  | nothing secret in the plist; `gh` uses its own auth                                                    | `grep -i 'token\|key\|secret' com.nuzantara.review-gate.plist` → 0 hits |
| **G-air-gap**     | diff via `gh pr diff` only; the untrusted branch is never checked out                                  | no `git checkout <branch>` in `review_gate_run.sh`                      |

## Robust quorum (W64)

`compute_outcome` decides ONLY over reviewers that actually ran (`error is None`):

- `< 2` live reviewers → `inconclusive` (an env-down reviewer is **never** counted
  as a non-green vote over a fixed denominator — that would be W64 theater);
- any live `red` → `red`; all live `green` → `green`; otherwise `yellow`.

## Operate

```bash
# Install (on the Pro — runtime home is the deploy worktree):
bash infra/launchagents/install_fase0_governance.sh
bash infra/launchagents/install_fase0_governance.sh --verify
bash infra/launchagents/install_fase0_governance.sh --uninstall   # remove

# Manual sweep (dry-run — logs, never comments):
REVIEW_GATE_DRY_RUN=1 bash scripts/review_gate_run.sh

# Manual sweep (real — posts comments, capped per sweep):
REVIEW_GATE_MAX_PER_SWEEP=3 bash scripts/review_gate_run.sh

# Force-review a single PR (bypasses the wrapper / idempotency):
python3 scripts/codex_tri_llm_review.py --pr <N> --comment
```

Tunables (env): `REVIEW_GATE_MAX_PER_SWEEP` (default 3, 0=unlimited),
`REVIEW_GATE_DRY_RUN` (1=log-only). Logs: `~/logs/review-gate.{out,err}.log`.

## Cold start

The first armed sweep sees the full open-`agent/*` backlog. The per-sweep cap
(default 3) processes 3/tick (≈ 9 LLM calls / 10 min), the rest next tick —
no quota stampede. Steady-state has ~0–1 new SHAs per sweep.

## Gotchas

- **Must run on the Pro.** The reviewers are OAuth-CLI (Codex/Claude) + the
  DeepSeek key — no CI access. The plist hardcodes `/Users/nuzantara`; it is a
  Pro-runtime artifact (it will NOT run on M5).
- **macOS bash 3.2** has no GNU `flock` and no `declare -A` — the wrapper uses a
  Python `fcntl.flock` re-exec, and the installer uses a `case()` function.
- **Idempotency is head-SHA-keyed**, not time-keyed: re-running a sweep on an
  unchanged PR does NOT re-comment; a new push (new head SHA) does.
- The state file marks a SHA "seen" even on `inconclusive`/`red` — we already
  posted a comment for that SHA; re-posting the same adds nothing. The next
  PUSH re-triggers; the next SWEEP won't.

## Family

- Modeled on the FASE-0 governance LaunchAgents (`cost-breaker-deadman`,
  `verify-the-verifiers`, `mcp-integrity`) — same conventions.
- W64 (`esistere ≠ armato`): the wrapper refuses to no-op — it errors if the
  review script is absent, rather than silently doing nothing.
- 2026-04-29 plist-secret scar: zero secrets in the plist.
- The deferred auto-merge phase: spec v3 (GitHub App check-run), task #3.
