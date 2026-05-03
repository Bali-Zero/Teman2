# docs-guardian L1+L2 Autofix — Design

**Status:** Approved (in-session brainstorm 2026-04-24)
**Date:** 2026-04-24
**Author:** Zero + Claude Opus 4.7 (1M context)
**Parent spec:** `docs/superpowers/specs/2026-04-24-docs-hygiene-design.md`
**Duration:** ~1h, single PR.

---

## 0. Problem

After Fase A-D of docs-hygiene (PRs #230, #233, #234, #235, #236), the weekly guardian is **L0 only** — it regenerates `DOCS_INVENTORY.md` and sends a Telegram alert on delta. Nothing acts on the delta. Orphans accumulate. Broken links accumulate. Human must notice the alert and manually open a PR.

Zero's question: "Un tool che sa misurare lo stato... vengono lanciati quando serve in automatico e il loro output raccolto e che crea azioni concrete?"

Answer was: **L0 yes, L1+ no.** This spec closes the gap.

## 1. Objective

Upgrade `scripts/docs_guardian.sh` from passive monitor to semi-autonomous agent:

- **L1 — orphan auto-archive**: when `docs_audit.py` flags orphans (`mtime>90d AND refs_in=0 AND not-whitelist`), run `--apply`, commit to a feature branch, open PR. Auto-merge enabled if no other issues pending.
- **L2 — broken-link triage PR**: when broken links detected, open PR with per-file checklist. No automatic fix (requires human judgment). Auto-merge NOT enabled.

Explicitly deferred:
- Fully LLM-driven cleanup (L3) — over-engineering for current load.
- Auto-fixing broken links via heuristics (remove link syntax, guess new path) — too error-prone, breaks prose.

## 2. Non-goals

- **No direct push to `main`**. All actions go through PR review.
- **No modification of `docs_audit.py`**. Its `--apply` already does the move; guardian just wires it into a git+gh workflow.
- **No new cron**. Reuses the existing Sun 05:00 WITA slot.

## 3. Architecture

### 3.1 Flow (new guardian)

```
cron Sun 05:00 WITA on Pro
 → docs_sync.py --quiet        (DOCSYNC markers, best-effort)
 → docs_audit.py --json --quiet (capture STATS)
 → docs_audit.py --quiet        (write DOCS_INVENTORY.md)
 → read STALE, BROKEN, ORPHANS from STATS
 │
 ├ if ORPHANS=0 AND BROKEN=0:
 │    discard inventory drift, silent exit (STALE keepers are irreducible)
 │
 ├ else (preconditions: gh authed, working tree clean):
 │    git fetch origin main
 │    git checkout -B docs-guardian/weekly-YYYY-MM-DD origin/main
 │    if ORPHANS>0:
 │       docs_audit.py --apply  (git mv orphans → archive/YYYY-MM-orphans/)
 │       docs_audit.py           (refresh inventory post-move)
 │       git add -A docs/
 │       git commit -m "chore(docs): auto-archive N orphan docs"
 │    git push origin <branch> --force-with-lease
 │    gh pr create ...
 │    if BROKEN=0:
 │       gh pr merge --auto --squash  (pure L1 → auto-mergeable)
 │    git checkout main
 │    notify Telegram with PR URL
```

### 3.2 Cluster args = single source of truth

The guardian hardcodes cluster+whitelist args identical to `.github/workflows/docs-guardian.yml`. This is the existing drift-prone pattern documented in PR #236 lesson. Follow-up refactor (not in this spec): extract to JSON config loaded by both. In-scope: ensure guardian's args match workflow's exactly.

### 3.3 Safety gates

| Gate | Action if failed |
|---|---|
| `gh auth status` | Skip auto-PR, Telegram-only fallback |
| Working tree dirty (excluding inventory) | Skip auto-PR, Telegram notify |
| `git fetch origin main` fails | Skip auto-PR, exit 1 |
| `docs_audit.py --apply` fails | Telegram notify with "manual cleanup required", exit 1 |
| `git push` fails | Telegram notify, exit 1 |

No gate for "main diverged during run" — rare race, worst case is PR opens from slightly-old base. Reviewer catches.

## 4. PR behavior

### 4.1 Pure L1 (orphans only, no broken)

- Title: `docs-guardian: weekly report (N orphans, 0 broken-link file(s))`
- Body: summary + orphan list + rollback instructions
- Commits: 1 auto-commit with the `git mv` + inventory refresh
- **Auto-merge enabled** (`--auto --squash`)
- Zero should expect silent merges on Sunday mornings when orphans exist

### 4.2 Pure L2 (broken only, no orphans)

- Title: `docs-guardian: weekly report (0 orphans, M broken-link file(s))`
- Body: per-file broken-link list + instructions (update path / remove link / fix anchor)
- Commits: none automatic (branch is `origin/main` + refreshed inventory)
- **Auto-merge NOT enabled** — human fixes links, then merges manually

### 4.3 Mixed (L1 + L2)

- Title: `docs-guardian: weekly report (N orphans, M broken-link file(s))`
- Body: both sections
- Commits: L1 auto-commit present
- **Auto-merge NOT enabled** — human must fix broken links first

## 5. Bug discovered & fixed during implementation

`STATS=$(python ... 2>/dev/null || echo '{}')` swallows the JSON when `docs_audit.py` exits 1 (delta detected — expected). Result: `STALE=0, BROKEN=0, ORPHANS=0` even when real orphans exist. Fixed by preserving stdout on exit 1, using `|| true` + explicit empty-check fallback. Commit `bc6a8cd15`.

## 6. Test coverage

No new unit tests (bash script, integration-testable only). Manual E2E attempted:
- ✓ `--dry-run` reports correct stale=4 / broken=0 / orphans=0 on clean main
- ✓ Synthetic orphan (backdated commit) makes dry-run report orphans=1
- ✓ Safety gate: guardian on non-main branch + dirty tree exits silently
- Not tested (would create real PR on GitHub): full L1 auto-PR flow. Relying on CI check `Docs Guardian` on THIS PR to validate the guardian's output shape.

## 7. Rollback

If guardian creates bad PRs in production:
1. `crontab -l | grep -v docs-guardian | crontab -` (disable)
2. Close any offending PRs without merging
3. `git revert <commit>` if bad auto-merge slipped through
4. Debug + re-enable

## 8. Success criteria

- Within 1-2 weekly runs after merge: if any orphan exists in the repo, a PR is auto-opened and (if no broken links pending) auto-merged.
- If broken links exist: PR opens awaiting review, Telegram alert with PR URL.
- Zero false-positive auto-archives (monitored via the alerts — orphans incorrectly archived are reversible with 1 `git mv`).

## 9. Out of scope (future work)

- **Single-source cluster config**: extract cluster+whitelist args to a JSON file loaded by both workflow and guardian.
- **L3 agent**: LLM reads inventory, decides per-file actions, opens PR with reasoning. Not justified at current velocity.
- **Broken-link auto-fix heuristics**: risky. Keep human-in-loop.
- **Multi-host coordination**: guardian only runs on Pro. Air does not touch docs/**.
