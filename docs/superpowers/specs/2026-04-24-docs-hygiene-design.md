# Docs Hygiene & Automated Inventory — Design

**Status:** Approved (brainstorm 2026-04-24)
**Date:** 2026-04-24
**Author:** Zero + Claude Opus 4.7 (1M context)
**Scope:** Fase 1 of 2 (this spec). Fase 2 (apps/*/README.md, ~/.claude/memory/, research/*) will be a separate spec later.
**Duration estimate:** 2.5–4 hours wall-clock, 4 atomic PRs.

---

## 0. Problem

`~/Desktop/nuzantara/docs/` contains ~150 markdown files and ~30 subdirs. From inspection:

- **Visible duplicates by filename:** 4 versions of `AUTOMATION_AUTONOMY_*`, 3 overlapping automations catalogs (`AUTOMATIONS_REFERENCE.md`, `ACTIVE_AUTOMATIONS.md`, `AUTOMATION_MODEL_MAP.md`), 4 system-map variants (`LIVING_ARCHITECTURE`, `SYSTEM_MAP_4D`, `SYSTEM_OVERVIEW`, `CODEBASE_THEMATIC_AREAS`), 2 versions of `SYSTEM_AUDIT_2026-04-03`.
- **No inventory:** there is no single source of truth for "which docs are alive, which drifted, which are orphans."
- **No automated guard:** `scripts/docs_sync.py` syncs DOCSYNC markers in a few canonical files but does not audit the 150-file landscape. Drift and duplicates accumulate silently.
- **The Sacred Books spec from 2026-04-15** (`2026-04-15-libri-sacri-canonici-design.md`) proposed creating 3 new books (ANATOMIA/FISIOLOGIA/STORIA-CLINICA) + auto-update scripts; it was superseded by a lean implementation that stopped at `INDEX.md` + `docs_sync.py`. The remaining 3 books were never built.

Consequence: every session spends tokens grepping through overlapping docs, and the assistant occasionally cites superseded versions.

## 1. Objective

Build a **documentation hygiene system** that:

1. Produces a single, regenerable inventory (`docs/DOCS_INVENTORY.md`) classifying every `docs/**/*.md` file as **LIVE**, **STALE**, or **ARCHIVED**.
2. Performs the known-duplicate cleanup (4 clusters) explicitly.
3. Archives orphan candidates (mtime >90d AND zero inbound refs) into `docs/archive/`.
4. Runs automatically: weekly cron with Telegram alert on new drift/orphans/broken links; CI check on PRs touching `docs/**`.
5. Adds zero new "sacred books." The existing four (SYMBIOSIS, VADEMECUM, CLAUDE, INDEX) remain canonical.

### Non-goals (decided during brainstorm)

- **No biological lifecycle (embrione→…→morte) on docs.** Decided the 7-phase model from `cell-core/lifecycle.py` does not map usefully to documents. A doc is correct or incorrect; forcing phases is cosmetic overhead.
- **No new sacred books.** ANATOMIA/FISIOLOGIA/STORIA-CLINICA evaluated and rejected: they duplicate existing artifacts (`LIVING_ARCHITECTURE.md` auto-generated, `git log`, `mem query`, NotebookLM NB-14).
- **No taxonomy restructure** of the 30 existing subdirs. That is a Fase 2/L3 concern if ever needed after cleanup.
- **No scope creep** to `apps/*/README.md`, `~/.claude/memory/`, `research/*`. Those have different rules and live in a Fase 2 spec.

## 2. Architecture

### 2.1 Files introduced / modified

```
~/Desktop/nuzantara/
├── docs/
│   ├── DOCS_INVENTORY.md              (NEW — auto-generated, source of truth)
│   ├── archive/                       (existing — destination for archived files)
│   │   ├── autonomy-history/          (NEW subdir, target for superseded AUTOMATION_AUTONOMY_* versions)
│   │   └── system-map-history/        (NEW subdir, target for superseded system-map variants)
│   ├── AUTOMATIONS.md                 (NEW — merged from 3 sources in Fase B)
│   └── ...                            (remaining files, some archived)
│
├── scripts/
│   ├── docs_sync.py                   (existing — unchanged)
│   ├── docs_audit.py                  (NEW — generates DOCS_INVENTORY.md)
│   └── docs_guardian.sh               (NEW — cron wrapper)
│
├── scripts/automation_catalog.json    (MODIFIED — add docs-guardian entry)
│
└── .github/workflows/
    └── docs-guardian.yml              (NEW — CI check on PRs touching docs/**)
```

### 2.2 Responsibilities

| Component | Responsibility | Trigger |
|---|---|---|
| `docs_audit.py` | Walk `docs/**/*.md`, compute mtime / refs_in / broken_links / drift / cluster membership; classify each file LIVE/STALE/ARCHIVED; rewrite `DOCS_INVENTORY.md`. | Weekly cron + CI + on-demand |
| `docs_guardian.sh` | Wrapper: runs `docs_sync.py` then `docs_audit.py`; sends Telegram alert if delta > 0. | Cron Sun 05:00 WITA |
| `DOCS_INVENTORY.md` | Single-source-of-truth markdown table of all doc status. | Rewritten each run |
| `docs-guardian.yml` | CI workflow running `docs_audit.py --check` on PRs touching `docs/**`. Fails if committed inventory diverges from computed one. | Every PR touching `docs/**` |

### 2.3 Why two scripts, not one

`docs_sync.py` currently does a narrow job: sync `<!-- DOCSYNC:KEY -->` markers inside CLAUDE.md/INDEX.md/AI_ONBOARDING.md. Mixing 150-file-wide auditing into it would bloat a focused tool. Two scripts, one responsibility each, orchestrated by `docs_guardian.sh`.

## 3. Classification rules

Each file receives exactly one status. Rules are evaluated top-to-bottom; first match wins.

### Rule 1 — ARCHIVED (already archived)

```
path.startswith("docs/archive/")
```

No other checks. If it is already there, it stays there.

### Rule 2 — ARCHIVED (orphan candidate)

```
mtime > 90 days ago
  AND refs_in == 0
  AND path NOT IN WHITELIST
```

- **refs_in** = number of other `.md` files in the repo containing the basename of this file. Computed via `fgrep -l -F "<basename>.md"` over `{docs/**.md, CLAUDE.md, INDEX.md, SYMBIOSIS.md, VADEMECUM.md, AGENTS.md, GEMINI.md, AUTONOMOUS_OPS.md, apps/**/README.md}` excluding `.git/` and the file itself. If two docs happen to share a basename (rare — `docs/` filenames are currently unique), both get counted together; the audit emits a warning in this case and the user resolves by renaming one.
- **WHITELIST**:
  - `docs/ARCHITECTURE_DECISION_RECORDS.md`
  - `docs/API_REFERENCE.md`
  - `AUTONOMOUS_OPS.md` (root, referenced by name from CLAUDE.md §2)
  - `docs/PRO_AIR_CONNECTION.md`

When matched → `action` column in inventory becomes `archive: orphan, mtime=Nd, refs=0`. The audit tool **does not move files automatically**. Moves happen when the user runs `docs_audit.py --apply` or manually.

### Rule 3 — STALE (active problem)

A file is STALE if at least one of:

- `broken_links > 0` — markdown `[...](path-or-url)` pointing to nonexistent relative paths or anchor refs that do not exist in the target.
- `drift_docsync == true` — file contains `<!-- DOCSYNC:KEY_START -->`/`<!-- DOCSYNC:KEY_END -->` markers and the enclosed value does not match what `docs_sync.py` would produce.
- `duplicate_cluster != null` — file belongs to one of the 4 known clusters (see §3.1).

### Rule 4 — LIVE (default)

Everything else.

### 3.1 Known duplicate clusters

| Cluster key | Members | Canonical | Action for non-canonical |
|---|---|---|---|
| `automation-autonomy` | `AUTOMATION_AUTONOMY_PLAN_v3_1.md`, `AUTOMATION_AUTONOMY_SYSTEM_V3_2.md`, `AUTOMATION_AUTONOMY_SYSTEM_V3_3.md`, `AUTOMATION_AUTONOMY_NB1_SUBMISSION.md` | `_SYSTEM_V3_3.md` | `git mv` to `docs/archive/autonomy-history/` |
| `automations-catalog` | `AUTOMATIONS_REFERENCE.md`, `ACTIVE_AUTOMATIONS.md`, `AUTOMATION_MODEL_MAP.md` | `AUTOMATIONS.md` (NEW, to be created by manual merge) | After merge, archive sources in `docs/archive/` |
| `system-map` | `LIVING_ARCHITECTURE.md`, `SYSTEM_MAP_4D.md`, `SYSTEM_OVERVIEW.md`, `CODEBASE_THEMATIC_AREAS.md` | `LIVING_ARCHITECTURE.md` (auto-generated by The Scribe) | `git mv` to `docs/archive/system-map-history/` |
| `system-audit` | `SYSTEM_AUDIT_2026-04-03.md`, `SYSTEM_AUDIT_FINAL_2026-04-03.md` | `_FINAL.md` | `git mv SYSTEM_AUDIT_2026-04-03.md docs/archive/` |

The audit tool **flags** cluster membership but **does not merge** the `automations-catalog` cluster: that one requires manual content merge and is handled in Fase B.7 of the build plan.

### 3.2 What does NOT make a file STALE

To avoid false-positive churn:

- **Age alone**: an old file that is still referenced and not drifted is LIVE. `SYMBIOSIS.md` does not age.
- **Low `refs_in` alone**: must also satisfy `mtime > 90d`. A recent audit may not yet be referenced.
- **Absence of DOCSYNC markers**: most docs don't have them and that's fine. Only a present marker drifting away from current value triggers STALE.

## 4. `DOCS_INVENTORY.md` schema

```markdown
# Documentation Inventory

_Auto-generated by `scripts/docs_audit.py`. Last run: YYYY-MM-DD HH:MM WITA_

## Summary

| Status    | Count | % |
|-----------|-------|---|
| LIVE      | N     | X% |
| STALE     | N     | X% |
| ARCHIVED  | N     | X% |

**Drift:** N files · **Broken links:** N · **Orphans (candidate archive):** N

## Files

| File | Status | mtime_days | refs_in | broken | drift | cluster | action |
|------|--------|-----------:|--------:|-------:|-------|---------|--------|
| <path> | LIVE/STALE/ARCHIVED | N | N | N | yes/no | <cluster>/— | <action-or-—> |
| ... (one row per file, alphabetically by path) |

## STALE details

### <cluster-key> cluster
Canonical: `<path>`
Archive candidates: `<path>`, ...
Manual action: <one-line shell command or description>

### Broken links
- `<file>:<line>` → `<target>` (<reason>)

### Orphans (candidate archive, mtime>90d AND refs_in==0)
- `<path>` (last touched YYYY-MM-DD, zero inbound refs)
```

### Properties of the generated file

- **Stable**: same input → same output. Only the header has a timestamp; body rows are sorted alphabetically.
- **Idempotent**: full rewrite every run; no merge logic.
- **Diff-friendly**: meaningful diffs between runs show only real changes.

## 5. Automation

### 5.1 `docs_audit.py` specification

- **Input:** repo root.
- **Output:** `docs/DOCS_INVENTORY.md` (rewritten) + exit code.
- **Exit codes:**
  - `0` — run clean, no STALE/orphan/broken-link delta vs prior `DOCS_INVENTORY.md`.
  - `1` — delta detected (used by `--check` and by the cron to decide whether to alert).
  - `2` — unexpected failure.
- **Flags:**
  - `--apply` — physically move files flagged `archive:*` to `docs/archive/…/` via `git mv`. Default off.
  - `--check` — exit 1 if the regenerated inventory differs from the committed one. For CI. Does not write.
  - `--quiet` — suppress stdout on success.
  - `--json` — emit stats JSON on stdout for shell consumption.
- **Dependencies:** Python stdlib only. No `pip install`.
- **Performance target:** <5 seconds on 150 files. No LLM calls.
- **Algorithm (single pass):**
  1. Walk `docs/**/*.md`.
  2. For each: compute mtime; extract links via regex `\[.*?\]\((.*?)\)`; detect `<!-- DOCSYNC:KEY_START -->...<!-- DOCSYNC:KEY_END -->` blocks and compare enclosed value to `docs_sync.py --json` output.
  3. Compute `refs_in` via a single `fgrep -l -F` scan over tracked files; filter out `.git/`.
  4. Apply Rule 1→4.
  5. Write `DOCS_INVENTORY.md`.

### 5.2 `docs_guardian.sh`

```bash
#!/bin/bash
# Weekly docs guardian — Sun 05:00 WITA (Sat 21:00 UTC)
set -euo pipefail
cd "$HOME/Desktop/nuzantara"
python scripts/docs_sync.py --quiet || true
if ! python scripts/docs_audit.py --quiet; then
  SUMMARY=$(python scripts/docs_audit.py --json | jq -r '"\(.stale) stale, \(.broken) broken, \(.orphans) orphans"')
  "$HOME/.claude/scripts/hotfix-notify.sh" "docs-guardian" "Delta: ${SUMMARY}. See docs/DOCS_INVENTORY.md"
fi
```

- `set -euo pipefail` — fail loudly.
- `docs_sync.py || true` — sync failure does not block audit.
- Alert only on `docs_audit.py` exit != 0 → no weekly noise.
- Reuses `hotfix-notify.sh` (existing Telegram integration).

### 5.3 Cron installation

`crontab -e` on Pro:

```
0 5 * * 0 /Users/nuzantara/Desktop/nuzantara/scripts/docs_guardian.sh >> $HOME/logs/docs-guardian.log 2>&1
```

### 5.4 Automation catalog registration

Append to `scripts/automation_catalog.json`:

```json
{
  "name": "docs-guardian",
  "schedule": "0 5 * * 0",
  "script": "scripts/docs_guardian.sh",
  "owner": "pro",
  "purpose": "Weekly docs inventory + drift/orphan/broken-link detection",
  "alert_channel": "telegram"
}
```

### 5.5 CI hook

`.github/workflows/docs-guardian.yml`:

- Triggers on pull_request touching `docs/**`.
- Runs `python scripts/docs_audit.py --check`.
- Fails if committed `DOCS_INVENTORY.md` differs from computed. Forces contributor to regenerate.

## 6. Build plan (4 PRs, sequential)

### PR #1 — Fase A: Bootstrap audit tool (30–45 min)

1. Write `scripts/docs_audit.py`.
2. Write `scripts/docs_guardian.sh`.
3. First run → generate initial `docs/DOCS_INVENTORY.md`.
4. Manual review of inventory: verify LIVE/STALE/ARCHIVED classifications are sane, the 4 clusters are flagged correctly, no obvious false positives on whitelist files.
5. Commit: `feat(docs): docs_audit tool + initial inventory`.

**Definition of done:** `docs/DOCS_INVENTORY.md` exists, rows for all ~150 files, the 4 duplicate clusters visible in the `cluster` column, whitelist files are LIVE.

### PR #2 — Fase B: Cleanup actions (1–2 hours)

Execute in order, **atomic commits**:

1. `git mv` the 3 superseded `AUTOMATION_AUTONOMY_*` → `docs/archive/autonomy-history/`. Commit.
2. `git mv` the 3 superseded system-map files → `docs/archive/system-map-history/`. Commit.
3. `git mv SYSTEM_AUDIT_2026-04-03.md docs/archive/`. Commit.
4. Orphans flagged in inventory: review one by one, archive or keep with a note. Commit grouped.
5. Fix broken links inline. Commit.
6. **Manual merge**: write new `docs/AUTOMATIONS.md` consolidating `AUTOMATIONS_REFERENCE.md` + `ACTIVE_AUTOMATIONS.md` + `AUTOMATION_MODEL_MAP.md`. After merge, `git mv` the 3 sources to `docs/archive/`. Commit.
7. Rerun `docs_audit.py`. Verify STALE count dropped to near-zero. Commit `chore(docs): refresh inventory post-cleanup`.

**Definition of done:** ~15–20 files moved to archive, `AUTOMATIONS.md` exists, `DOCS_INVENTORY.md` STALE ≈ 0.

**Stop-and-ask gates:**
- Before archiving any orphan **not** in a known cluster — requires user ok per file.
- Before committing `AUTOMATIONS.md` — user reviews the merged content.

### PR #3 — Fase C: Active automation (20–30 min)

1. Install cron entry on Pro.
2. Append `docs-guardian` entry to `scripts/automation_catalog.json`.
3. Add `.github/workflows/docs-guardian.yml`.
4. End-to-end test: modify a doc without refreshing inventory, open a throwaway branch, verify CI `--check` fails; refresh and verify it passes.
5. Commit: `feat(ci): docs-guardian cron + CI check`.

**Definition of done:** `crontab -l` shows the line; CI green on a test PR.

### PR #4 — Fase D: Integration with sacred books (15–20 min)

1. Update `INDEX.md` — add an entry pointing to `docs/DOCS_INVENTORY.md` under the "Cosa cerchi?" table.
2. Update `VADEMECUM.md` — "Creating a new doc" section: regola "when you add a new doc, either regenerate inventory or let the weekly cron do it."
3. Remove references to archived files from CLAUDE.md / INDEX.md (grep check).
4. Commit: `docs(sacred): point to DOCS_INVENTORY from INDEX + VADEMECUM`.

**Definition of done:** `grep -r "AUTOMATION_AUTONOMY_V3_2\|SYSTEM_MAP_4D\|SYSTEM_OVERVIEW.md" CLAUDE.md INDEX.md VADEMECUM.md SYMBIOSIS.md` returns 0.

## 7. Success criteria

**Measurable:**

1. `docs/*` file count drops from ~150 to ~100–120 LIVE + archive.
2. `DOCS_INVENTORY.md` STALE count < 5 after Fase B (residual legitimate drift only).
3. Weekly cron runs without manual intervention; alert fires only on genuine delta.
4. CI check blocks PRs that add docs without refreshing inventory.

**Qualitative:**

- A new session can learn the doc landscape by reading `DOCS_INVENTORY.md` alone.
- The 4 duplicate clusters are resolved; no surviving `V3_2` / `SYSTEM_OVERVIEW` / etc. in LIVE.
- Additional sacred books were not needed to achieve this.

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| `docs_audit.py` false-positive archives a LIVE file | Default is report-only; `--apply` is explicit; PR #2 commits are atomic and reviewable. |
| Cluster canonical choice (e.g., `_V3_3` over `_V3_2`) is wrong | User-reviewed in PR #2. Archive is reversible (`git mv` back). |
| `refs_in` misses references in code (e.g., Python strings) | Acceptable: docs should not be referenced from code paths. If it happens, whitelist. |
| Weekly alert noise | Alert only on exit-code != 0 (real delta). No delta → silent. |
| CI `--check` blocks legitimate PRs that happen to touch a doc | The fix is one command: `python scripts/docs_audit.py`. Documented in VADEMECUM. |
| `docs_sync.py` extension accidentally breaks the existing marker sync | Keep `docs_sync.py` unchanged; `docs_audit.py` is a separate script. |

## 9. Dependencies

All prerequisites already exist:

- `crontab -l` accessible on Pro (yes).
- `scripts/hotfix-notify.sh` (Telegram alert helper) — yes, present.
- `scripts/docs_sync.py` — yes, existing.
- `scripts/automation_catalog.json` — yes, existing.
- GitHub Actions — yes, multiple workflows already present.
- Python 3.11+ stdlib — yes.

No new external dependency.

## 10. References

- `docs/superpowers/specs/2026-04-15-libri-sacri-canonici-design.md` — the superseded spec that tried 3 new sacred books. Kept for context; this design deliberately does not resurrect ANATOMIA/FISIOLOGIA/STORIA-CLINICA.
- `scripts/docs_sync.py` — reused unchanged for DOCSYNC marker sync.
- `docs/archive/` — existing archive destination.
- `CLAUDE.md` root — contains `<!-- DOCSYNC:LIVING_ORGANS_START -->` and similar markers maintained by `docs_sync.py`.
- `INDEX.md` — the canonical atlas, will gain one new entry pointing to `DOCS_INVENTORY.md`.

## 11. Out of scope for this spec (Fase 2)

Explicitly deferred to a separate future spec:

- `apps/*/README.md` inventory (21 apps).
- `~/.claude/memory/` MEMORY.md hygiene (currently at the 200-line hardcoded limit).
- `research/*` capture audit (already has its own rules in CLAUDE.md §16).
- Semantic re-clustering of the 30 existing `docs/` subdirs (would be L3, not needed until L2 is stable).
- Cross-repo docs consolidation (Pro vs Air vs sota-social-research).

---

**End of spec.** Next: writing-plans skill to produce the implementation plan.
