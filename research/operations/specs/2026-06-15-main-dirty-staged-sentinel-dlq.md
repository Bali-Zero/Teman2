# Main Dirty Staged Sentinel/DLQ Triage - 2026-06-15

Date: 2026-06-15
Dispatch key: `main-dirty-staged-sentinel-dlq`
Source report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260615_063108.md`
Runtime branch: `codex-overnight/spark-alarm-20260615_063311-spark-dispatch-20260615_063108-scout-main-dirty-staged-sentinel-dlq-20260615_063312`
Shared checkout under investigation: `/Users/nuzantara/Desktop/nuzantara`

## Scope

Resolve the Spark-dispatched signal without rewriting the shared main checkout
from an unrelated overnight worktree.

The confirmed root-cause cluster is checkout hygiene: `/Users/nuzantara/Desktop/nuzantara`
is stale relative to `origin/main`, has two local article commits, has staged
operational script edits, and has a broad unstaged/untracked research/generated
surface. Spark/Codex LaunchAgent lifecycle is not the actionable fault.

## Live Evidence

- Machine: Pro, `nuzantara@Nuzantara`; peer `mini` was unreachable during the
  session-start check, so cross-machine git sync was not verified.
- Runtime worktree is on the required overnight branch and started clean.
- Only root `AGENTS.md` exists in this worktree; no path-specific `AGENTS.md`
  files were found under `scripts/`, `apps/backend-rag/`, or
  `apps/backend-rag/backend/llm/`.
- Spark lifecycle is healthy by the provided lifecycle semantics:
  - `com.nuzantara.codex-spark-loop`: `state = running`, active PID `1212`.
  - `com.nuzantara.codex-spark-alarm`: timer job, `state = not running`,
    `last exit code = 0`, `run interval = 120 seconds`.
  - `com.nuzantara.codex-spark-harvester`: timer job, `state = not running`,
    `last exit code = 0`, `run interval = 180 seconds`.
- Overnight runner was active during this intervention:
  `com.nuzantara.codex-overnight-runner` had active PID `32217`.
- Decision state files under `/Users/nuzantara/.agent/decisions/state` were
  fresh around the Spark window, including `spark_alarm.last.json` and
  `spark_completion_harvester.last.json` at 2026-06-15 06:33 WITA.
- Shared checkout status:
  - branch: `main`
  - relation: `ahead 2, behind 176`
  - local ahead commits:
    - `e2b355f45 feat(articles): add translations for indonesia-eyes-visa-free-access-for-aussie-and-kiwi-tourists`
    - `c6d6b85fe feat(articles): add translations for ojk-puts-8-online-lenders-on-watchlist-license-revocation-looms`
- Staged operational diff:
  - `scripts/dlq_autopilot.py`
  - `scripts/nuzantara-sentinel.py`
  - staged stat: 205 insertions, 2 deletions.
- Current `origin/main` already contains the staged operational behavior:
  - `scripts/dlq_autopilot.py` has `requeue_terminal(...)`.
  - `scripts/nuzantara-sentinel.py` has `_enrich_last_error_from_cron_log(...)`,
    recovered-TERMINAL resurrection, and `_check_blind_heal_loop(...)`.
  - Relevant history on the current branch includes:
    - `849a4a213 fix(ops): re-arm blind heal-loop (W70) ... (#1344)`
    - `6938d3883 fix(sentinel): close the blind heal-loop ... (#1413)`
    - `c454afb3d fix(sentinel): bound enrich tail (OOM) ... (#1418)`
- Unstaged tracked surface spans 22 files, including cicatrix docs, backend
  requirements, NLM pipeline code/config, automation docs, curiosity loop, and
  `shared/escalations_pro.jsonl`.
- Untracked top-level buckets:
  - `.claude`: 1 entry
  - `apps`: 11 entries
  - `outputs`: 51 entries
  - `research`: 855 entries
  - `scripts`: 3 entries

## Root-Cause Classification

Primary cluster: stale, broad, dirty shared checkout with staged operational
changes that have already landed upstream.

The staged `scripts/dlq_autopilot.py` and `scripts/nuzantara-sentinel.py` edits
should not be forward-ported from the shared checkout. The current branch already
contains the same W70 recovery behavior, with later follow-up hardening. Applying
the stale staged patch again would risk regressing the newer upstream versions.

Spark lifecycle is a non-issue in this event. Alarm and harvester are idle timer
jobs with exit 0; the loop is running.

## File Plan

| Path or bucket | Current shared-checkout state | Classification | Safe plan |
| --- | --- | --- | --- |
| `scripts/dlq_autopilot.py` | Staged modification | Stale duplicate of upstream W70 behavior | Do not commit from the shared checkout. After preserving a safety patch, owner can unstage/drop because `origin/main` already has `requeue_terminal(...)`. |
| `scripts/nuzantara-sentinel.py` | Staged modification | Stale duplicate of upstream W70 behavior with later upstream hardening | Do not commit from the shared checkout. After preserving a safety patch, owner can unstage/drop because `origin/main` already has cron-log enrichment, TERMINAL resurrection, and blind-loop alerting. |
| Local ahead article commits | Two commits ahead of `origin/main` | Separate content lane | Reconcile separately from automation cleanup. Cherry-pick or PR only if the articles are still intended and not already represented by newer article work. |
| NLM pipeline tracked edits | Unstaged tracked modifications | Separate executable lane | Do not mix with sentinel/DLQ cleanup. Needs owner review and focused NLM validation. |
| Docs/cicatrix tracked edits | Unstaged tracked modifications | Separate docs lane | Review separately; do not batch with operational scripts. |
| `shared/escalations_pro.jsonl` | Unstaged tracked append | Runtime/generated evidence | Do not commit unless an ops report explicitly requires this exact excerpt. |
| `outputs/` and `research/` untracked bulk | 906 combined untracked entries | Generated/research output | Inventory by owner; keep only curated reports, ignore/archive generated scratch output. |
| `scripts/nb_export_corpus.py`, `scripts/nb_generate_inventory.py`, `scripts/scar_query.py` | Untracked scripts | Possible tooling lane | Review and test independently before any commit. |

## Recommended Operator Cleanup

Do not run destructive cleanup automatically from an overnight worktree.

Suggested owner-safe sequence in the shared checkout:

```bash
cd /Users/nuzantara/Desktop/nuzantara
git diff --cached > /tmp/main-staged-sentinel-dlq-20260615.patch
git diff > /tmp/main-unstaged-20260615.patch
git ls-files --others --exclude-standard > /tmp/main-untracked-20260615.txt
git status --short --branch
```

Then decide lane by lane:

1. Preserve or PR the two local article commits if still wanted.
2. Drop the staged sentinel/DLQ script copies only after confirming the safety
   patches above exist and `origin/main` remains at or beyond the W70 fixes.
3. Move NLM/code changes into an isolated worktree/branch before validation.
4. Archive or ignore generated `outputs/` and uncurated research bulk.

## Non-Goals

- Do not reset, clean, checkout, or stash the shared checkout automatically.
- Do not restart or rewrite Spark/Codex LaunchAgents.
- Do not deploy.
- Do not modify `backend/prompts/zantara_core.py`, `fly.toml`, `.env*`, or
  secrets.

## Acceptance Criteria

- Spark lifecycle remains classified as healthy/idle, not failed.
- Staged sentinel/DLQ changes are recognized as stale duplicates of current
  upstream behavior.
- Shared checkout cleanup is left to the checkout owner with explicit safety
  patch commands and lane separation.
- This triage PR contains only the decision record; it does not mutate runtime
  state or the shared main checkout.
