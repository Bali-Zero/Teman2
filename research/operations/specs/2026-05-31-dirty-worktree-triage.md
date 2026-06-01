# Dirty Worktree Triage - 2026-05-31

Date: 2026-05-31
Dispatch key: `dirty-worktree-audit-2026-05-31`
Source report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260531_033604.md`
Owner: Ops/audit branch owner for `chore/audit-rag-truth-2026-05-31`
Decision deadline: 2026-05-31 12:00 WITA

## Scope

Resolve the dirty/stalled checkout signal in `/Users/nuzantara/Desktop/nuzantara`
without touching Spark LaunchAgents or production systems.

This triage spec is deliberately decision-only. The shared checkout contains
staged and untracked work owned by another audit flow, so the safe remediation is
to define the keep/drop/commit plan and leave the files intact.

## Live Evidence

- Machine check: Pro, `nuzantara@Nuzantara`; Mini reachable as `nuzantara@mini-pro2`;
  local and peer HEAD both `44f793840`.
- Isolated overnight branch:
  `codex-overnight/spark-alarm-20260531_033715-spark-dispatch-20260531_033604-scout-dirty-worktree-audit-2026-05-31-20260531_033715`.
- Shared checkout `/Users/nuzantara/Desktop/nuzantara` is on
  `chore/audit-rag-truth-2026-05-31` at `44f793840` with:
  - `A  research/operations/2026-05-31-empirical-audit.md`
  - `A  research/operations/audits/FROZEN-2026-05-31.json`
  - `M  scripts/openclaw_whatsapp_eval.py`
  - `?? research/audits/`
- `research/audits/` currently contains only
  `research/audits/2026-05-31-rag-truth/.checkpoint.txt`.
- Spark lifecycle is not actionable:
  - `com.nuzantara.codex-spark-loop`: `state = running`, `pid = 1018`,
    `last exit code = (never exited)`.
  - `com.nuzantara.codex-spark-alarm`: timer job, `state = not running`,
    `last exit code = 0`, `run interval = 120 seconds`.
  - `com.nuzantara.codex-spark-harvester`: timer job, `state = not running`,
    `last exit code = 0`, `run interval = 180 seconds`.
- Spark state files under `/Users/nuzantara/.agent/decisions/state` were updated
  around 03:36-03:37 WITA, so the Spark state signal is fresh.

## Root-Cause Classification

Primary cluster: shared-checkout audit deliverables left staged/untracked.

The LaunchAgent evidence does not support a Spark repair. The only confirmed
actionable signal is that an audit branch in the shared checkout has staged
deliverables plus one staged eval-script behavior change and one untracked
checkpoint directory.

## File Plan

| Path | Current state | Plan | Owner | Acceptance criteria |
| --- | --- | --- | --- | --- |
| `research/operations/2026-05-31-empirical-audit.md` | Staged add | Keep and commit with the FROZEN JSON as an audit-docs commit on `chore/audit-rag-truth-2026-05-31`. | Ops/audit branch owner | Report is reviewed for factual consistency with the captured evidence and references PR numbers/commit IDs without claiming merged status unless verified live. |
| `research/operations/audits/FROZEN-2026-05-31.json` | Staged add | Keep and commit atomically with the empirical audit report. | Ops/audit branch owner | JSON is valid, contains no secrets, and matches the report's frozen values. |
| `scripts/openclaw_whatsapp_eval.py` | Staged modification | Keep only after focused eval validation; commit separately from the audit docs because it changes scoring semantics. | OpenClaw eval owner | Run the smallest relevant `openclaw_whatsapp_eval` validation or focused tests proving controlled KBLI 404 lookups are ignored only for `kbli_kb` cases after `search_kbli` was called. If validation is not available by the deadline, unstage and park behind a follow-up spec. |
| `research/audits/` | Untracked directory | Drop before merge unless the checkpoint is explicitly needed for operator handoff. | Ops/audit branch owner | If retained, fold the branch/head checkpoint into the audit report. Otherwise remove the untracked checkpoint so it cannot be accidentally committed. |

## Commit Order

1. Audit docs commit:
   `docs(ops): add 2026-05-31 empirical audit`
2. Eval behavior commit, only after validation:
   `fix(openclaw): ignore controlled obsolete-kbli lookup misses`
3. Cleanup:
   remove or fold `research/audits/2026-05-31-rag-truth/.checkpoint.txt`.

Do not mix these into one commit. The docs are a historical audit deliverable; the
eval change is executable behavior and needs its own validation trail.

## Non-Goals

- Do not restart, unload, or rewrite `com.nuzantara.codex-spark-*` LaunchAgents.
- Do not deploy.
- Do not change `backend/prompts/zantara_core.py`, `fly.toml`, `.env*`, or secrets.
- Do not clean the shared checkout from an unrelated isolated worktree.
- Do not use `--no-verify`, force push, or reset the shared checkout.

## Next Step

The branch owner should decide by 2026-05-31 12:00 WITA whether to commit the
audit docs and validate the eval-script change. If no owner has acted by the
deadline, preserve the staged diff with a normal stash or isolated branch before
any branch switch in the shared checkout.
