---
spec_id: OPS-DIRTY-MAIN-2026-05-30
title: Dirty Main Checkout Triage After Spark Scout
date: 2026-05-30
domain: operations
status: draft
priority: P1
source_report: /Users/nuzantara/codex-spark-loop/reports/scout-20260530_035903.md
dispatch_key: dirty-worktree-nuzantara-main
---

# Dirty Main Checkout Triage After Spark Scout

## Decision

The actionable signal is the dirty shared checkout at `/Users/nuzantara/Desktop/nuzantara`, not the Spark LaunchAgent lifecycle.

Do not discard or commit those dirty files directly from the shared checkout. Preserve them by replaying the exact patch into a dedicated operations worktree, validating the content there, then committing through a normal branch and PR.

## Live Evidence Verified

Verified from the overnight worktree on 2026-05-30 WITA:

| Surface | Result |
| --- | --- |
| Machine | `nuzantara@Nuzantara` |
| Peer | `nuzantara@mini-pro2`, reachable |
| Pro/Mini sync | Out of sync: local `9bc201436`; Mini `3a9011c19` |
| Overnight branch | `codex-overnight/spark-alarm-20260530_035936-spark-dispatch-20260530_035903-scout-dirty-worktree-nuzantara-main-20260530_035937` |
| Overnight worktree | Clean before this spec |
| Shared main checkout | Dirty on `work-main-2026-05-29...origin/main` |
| Spark loop | `com.nuzantara.codex-spark-loop` running with PID `28682`, last exit `0` |
| Spark alarm/harvester | Idle between interval ticks, last exit `0` |
| Overnight runner | Running with PID `62342`, last exit `0` |
| Path-specific `AGENTS.md` | None under `apps/backend-rag/`, `scripts/`, or `apps/backend-rag/backend/llm/` |

Dirty shared-main status:

```text
 M .claude/rules/cicatrix-scars.md
 M docs/AI_ONBOARDING.md
?? research/operations/2026-05-30-sota-ai-architecture-methodology.md
```

## File Disposition

| Path | Disposition | Evidence | Safe handling |
| --- | --- | --- | --- |
| `.claude/rules/cicatrix-scars.md` | `keep/commit` | Adds an evidence-rich WR3 render scar and updates the W62 worktree-GC scar from reported to resolved/enforcing. The content is operational memory, not throwaway debug output. | Replay the patch into a dedicated `ops` worktree. Stage only this path if the scar references are still valid. |
| `docs/AI_ONBOARDING.md` | `move-to-worktree` | One-line docsync count change from `970 tests` to `971 tests`. This is plausible, but it should be verified against the current docsync/test inventory before commit. | Replay into the same or a separate worktree. Commit only after regenerating or otherwise verifying the quick-number source. |
| `research/operations/2026-05-30-sota-ai-architecture-methodology.md` | `keep/commit` | New research artifact with frontmatter, source list, caveats, and an explicit operations methodology. It is untracked, so it is at highest risk of sibling-process loss. | Copy the exact file into a dedicated worktree before any cleanup. Keep the current path unless a reviewer explicitly asks to move it under `research/operations/specs/`. |

No file currently has enough evidence for `discard`.

## Cleanup Runbook

Run these steps from a controlled shell. They are intentionally patch-based so the shared checkout is not mutated until the work is preserved elsewhere.

1. Capture the shared-main evidence:

```bash
git -C /Users/nuzantara/Desktop/nuzantara status --short --branch
git -C /Users/nuzantara/Desktop/nuzantara diff -- .claude/rules/cicatrix-scars.md docs/AI_ONBOARDING.md > /tmp/dirty-main-20260530-docs.patch
cp /Users/nuzantara/Desktop/nuzantara/research/operations/2026-05-30-sota-ai-architecture-methodology.md /tmp/dirty-main-20260530-sota-ai-architecture-methodology.md
```

2. Create a dedicated worktree:

```bash
cd /Users/nuzantara/Desktop/nuzantara
WT=$(python scripts/agent_start.py --lane ops --task-id dirty-main-cleanup-20260530 | tail -1)
cd "$WT"
```

3. Replay the dirty changes into the worktree:

```bash
git apply --check /tmp/dirty-main-20260530-docs.patch
git apply /tmp/dirty-main-20260530-docs.patch
cp /tmp/dirty-main-20260530-sota-ai-architecture-methodology.md research/operations/2026-05-30-sota-ai-architecture-methodology.md
```

4. Validate before committing:

```bash
git status --short
git diff --check
rg -n "API_KEY|sk-[A-Za-z0-9]{20,}" -- .claude/rules/cicatrix-scars.md docs/AI_ONBOARDING.md research/operations/2026-05-30-sota-ai-architecture-methodology.md
```

The secret-marker check should return no matches. If it returns matches, inspect before staging.

5. Commit with partial staging only:

```bash
git add .claude/rules/cicatrix-scars.md docs/AI_ONBOARDING.md research/operations/2026-05-30-sota-ai-architecture-methodology.md
git commit -m "docs(ops): preserve dirty-main operational notes"
git push -u origin HEAD
```

6. Open a PR and wait for normal review/merge.

7. Clean the shared main checkout only after the content is preserved in a branch or merged. Before any destructive cleanup, keep `/tmp/dirty-main-20260530-docs.patch` and `/tmp/dirty-main-20260530-sota-ai-architecture-methodology.md` until the cleanup is verified.

## Stop Conditions

Stop and write a blocked status instead of cleaning the shared checkout if any of these are true:

- The shared-main dirty files changed after this spec was generated.
- `git apply --check` fails in the dedicated worktree.
- The untracked research artifact no longer exists in shared main and no backup copy exists.
- A path contains secrets or API keys.
- Mini sync is required for the cleanup decision.

## Acceptance Criteria For Resolution

- A dedicated worktree branch contains the preserved operational changes.
- The branch passes `git diff --check` and targeted content checks.
- The shared main checkout is either clean or has a documented, current reason to remain dirty.
- No production deploy is performed.
- No `--no-verify`, force push, broad `git add -A`, or destructive cleanup is used.
