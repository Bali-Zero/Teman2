# NB Lifecycle Round 1 — Senescent decommission design

**Date:** 2026-05-07
**Author:** Claude Opus 4.7 (1M context) + Zero
**Branch:** `feat/nb-senescent-decomm-2026-05-07`
**Worktree:** `/Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent`
**Status:** Design — pending Zero spec review

---

## 1. Problem statement

The NotebookLM (NLM) arsenal currently lists 60 active notebooks (snapshot 2026-05-03, `reference_notebooklm_arsenal_full.md`). Round 1 lifecycle audit classified **36 candidates** as `SENESCENT` or eligible for `APOPTOSIS` — placeholder, playbook artifacts, orphans, research aggregators with low signal, Subhi merge candidates, and zero-value orphans.

Two structural issues compound the cleanup:

1. **R6 anti-pattern** — UUIDs are scattered as hardcoded literals across at least 4 consumer files (`config.py` itself plus `sentinel_actor.py`, `nlm_feeder.py`, `nlm_expander_agent.py`, `health_tools.py`), totalling ~9 references. There is no Single Source of Truth (SSOT). Any rename, status change, or future migration risks drift between consumers.
2. **No registry of intent** — the snapshot YAML in memory is read-only documentation, not a queryable runtime artifact. Lifecycle stages (`SENESCENT`, `KILL_PENDING`, `EXPORT_PENDING`, `APOPTOSIS_DONE`, `ORPHAN_REVIEW`) cannot be expressed in code, which makes idempotent cleanup runs and crash-safe recovery impossible.

**Goal of this PR:** introduce the SSOT (`notebook_registry.py`), audit the 36 candidates against live NLM state, execute APOPTOSIS for the 17 univoci (3 placeholder + 14 playbook), and produce a decision matrix doc for the 19 ambigui (8 orphan + 5 research + 4 Subhi + 2 zero_value), without breaking any of the 4 existing consumer files.

**Out of scope (deferred):**
- Migration of 4 consumer files (`sentinel_actor.py`, `nlm_feeder.py`, `nlm_expander_agent.py`, `health_tools.py`) to the new registry API. This PR keeps them on the `NLM_NOTEBOOKS` shim — see §5 Follow-up.
- Final decision/action on the 19 ambigui — Zero will review the decision matrix doc separately.
- Round 2 (skill graduation) and beyond — out of scope for this design.

---

## 2. Constraints

| # | Constraint | Source |
|---|------------|--------|
| C1 | Compat shim must be byte-identical to current `NLM_NOTEBOOKS` literal for the 6 active NB | Zero req |
| C2 | NEVER delete via MCP/UI without Zero approval (rename `[ARCHIVED-...]` only) | SYMBIOSIS Law 5 |
| C3 | Audit trail append-only (`research/nb-archive/audit_log.md`) | Zero req |
| C4 | TDD obbligatorio (red → green) | CLAUDE.md root |
| C5 | Branch hijack antibody: verify branch matches `feat/nb-senescent-decomm-2026-05-07` before each Edit/Write | Zero req (revised) |
| C6 | WIP commit cadence 30-45 min (down from 90) for 6 parallel sessions wave | Zero req (revised) |
| C7 | Atomic compound `git add && git commit && git push` | scar STRUCTURAL 2026-04-29 |
| C8 | Tri-LLM review relaxed 2/3 acceptable in capacity exhaustion | scar 2026-04-29 |
| C9 | NO API HTTP, CLI-only for LLM (mata-garuda inviolable) | mata-garuda CLAUDE.md §1 |
| C10 | Stack minimale runtime: only `pydantic`, `pytest` | mata-garuda CLAUDE.md §1 |
| C11 | T2 best-effort failure tolerance: cookie refresh proactive, 1 retry+5s backoff, hard cap 50% | Zero req |
| C12 | Persistence after each transition (crash-safe) | Zero req |
| C13 | Dry-run gate Zero approval between C1 and C2 commits | D3 hybrid req |

---

## 3. Architecture

### 3.1 New module — `mata_garuda.notebook_registry`

Single Source of Truth for all NB metadata. Public API.

```python
# apps/mata-garuda/mata_garuda/notebook_registry.py
from dataclasses import dataclass
from typing import Literal, Final
from mata_garuda._registry_data import REGISTRY_DATA

NotebookStatus = Literal[
    "ACTIVE", "TAC", "SENESCENT", "KILL_PENDING",
    "EXPORT_PENDING", "APOPTOSIS_DONE", "ORPHAN_REVIEW",
]
NotebookCluster = Literal[
    "placeholder_empty", "playbook_artifact", "orphan_unclear",
    "research_heavy", "subhi_merge", "zero_value_orphan",
]

@dataclass(frozen=True)
class NotebookEntry:
    uuid: str
    name: str
    family: str | None
    legacy_key: str | None
    status: NotebookStatus
    cluster: NotebookCluster | None
    created_at: str | None
    last_audited: str
    action_pending: str | None
    peer_uuids: list[str]

NOTEBOOK_REGISTRY: Final[dict[str, NotebookEntry]] = {
    uuid: NotebookEntry(uuid=uuid, **data)
    for uuid, data in REGISTRY_DATA.items()
}

def get_legacy_notebooks_dict() -> dict[str, str]:
    """Backward-compat: returns NLM_NOTEBOOKS as it was — 6 active UUIDs only."""
    return {
        e.legacy_key: e.uuid
        for e in NOTEBOOK_REGISTRY.values()
        if e.status == "ACTIVE" and e.legacy_key
    }

def get_by_status(status: NotebookStatus) -> list[NotebookEntry]:
    return [e for e in NOTEBOOK_REGISTRY.values() if e.status == status]

def get_by_cluster(cluster: NotebookCluster) -> list[NotebookEntry]:
    return [e for e in NOTEBOOK_REGISTRY.values() if e.cluster == cluster]

def get_notebook(uuid: str) -> NotebookEntry | None:
    return NOTEBOOK_REGISTRY.get(uuid)
```

### 3.2 Auto-generated data — `mata_garuda._registry_data`

Pure-Python literal. Built by `scripts/build_registry_from_manifest.py` from the YAML manifest. Regenerated **after each transition** to ensure crash-safety (C12).

```python
# apps/mata-garuda/mata_garuda/_registry_data.py
# AUTO-GENERATED — DO NOT EDIT MANUALLY
# Source: apps/mata-garuda/data/nb_round1_candidates_2026-05-07.yaml
# Regenerator: apps/mata-garuda/scripts/build_registry_from_manifest.py
# Last regenerated: 2026-05-07 HH:MM:SS UTC

from typing import Final

REGISTRY_DATA: Final[dict[str, dict]] = {
    "dc5d01cd-e99f-4c8f-aae4-75060b43d0de": {
        "name": "NB-INTEL-AIResearch",
        "family": "NB-INTEL",
        "legacy_key": "ai_research",
        "status": "ACTIVE",
        "cluster": None,
        "created_at": None,
        "last_audited": "2026-05-07",
        "action_pending": None,
        "peer_uuids": [],
    },
    # ... 6 active + 36 Round 1 candidates = 42 entries
}
```

### 3.3 Compat shim — `mata_garuda.config`

Minimal modification. The `NLM_NOTEBOOKS` literal is replaced by a function call. The 4 consumer files keep importing `from mata_garuda.config import NLM_NOTEBOOKS` and see a byte-identical dict.

```python
# apps/mata-garuda/mata_garuda/config.py
# NLM_NOTEBOOKS is a backward-compat shim.
# Source of truth: notebook_registry.NOTEBOOK_REGISTRY (status=ACTIVE).
from mata_garuda.notebook_registry import get_legacy_notebooks_dict
NLM_NOTEBOOKS = get_legacy_notebooks_dict()

# NLM_DOMAIN_ROUTING unchanged — still references legacy keys.
NLM_DOMAIN_ROUTING = {
    "immigration_visa": "immigration",
    # ... unchanged
}
```

### 3.4 Bootstrap manifest — `data/nb_round1_candidates_2026-05-07.yaml`

Audit-time artifact. Lists the 36 Round 1 candidates with their classification, peer UUIDs, drift status, and proposed action.

```yaml
schema_version: 1
generated_at: "2026-05-07T12:34:56Z"
generator: scripts/build_manifest.py
source_inventory_snapshot: "2026-05-03"
candidates_count: 36
clusters_summary:
  placeholder_empty: 3
  playbook_artifact: 14
  orphan_unclear: 8
  research_heavy: 5
  subhi_merge: 4
  zero_value_orphan: 2
candidates:
  - uuid: "<uuid>"
    name_snapshot: "<title from 2026-05-03 inventory>"
    name_live: "<title from nlm list at audit time, or null if unreachable>"
    cluster: "placeholder_empty"
    source_count_snapshot: 0
    source_count_live: 0
    drift_status: "consistent"  # consistent | drifted | unknown_via_mcp_failure
    proposed_action: "KILL"     # KILL | EXPORT | ORPHAN_REVIEW
    match_status: "exact"       # exact | fuzzy | not_found
    match_evidence: ""
    peer_uuids: []
    notes: ""
```

### 3.5 Scripts

All idempotent, all support `--dry-run`. Located in `apps/mata-garuda/scripts/`.

| Script | Purpose |
|--------|---------|
| `build_manifest.py` | Run `nlm list notebooks` (CLI subprocess), classify 36 candidates, write YAML manifest |
| `build_registry_from_manifest.py` | Read YAML manifest, render `_registry_data.py` Python literal |
| `audit_nb_live.py` | Use `mcp__notebooklm-mcp__notebook_query` to inspect each candidate, compare with snapshot, write JSON audit, set `*_PENDING` status in registry |
| `execute_apoptosis.py` | Run APOPTOSIS for 17 univoci, supports `--dry-run` and `--apply`, generates decision matrix doc, regenerates registry after each transition |

---

## 4. Data flow

```
[2026-05-03 snapshot]                    [Round 1 classification]
  reference_notebooklm_arsenal_full.md     R1-R5 rules + 36 candidates
                  │                                 │
                  └──────────────┬──────────────────┘
                                 ↓
                       scripts/build_manifest.py
                                 │
                                 ↓
              data/nb_round1_candidates_2026-05-07.yaml
                                 │
                                 ↓
              scripts/build_registry_from_manifest.py
                                 │
                                 ↓
                  mata_garuda/_registry_data.py
                                 │
                                 ↓
                mata_garuda/notebook_registry.py
                       (NOTEBOOK_REGISTRY)
                                 │
                  ┌──────────────┴──────────────┐
                  ↓                              ↓
   mata_garuda/config.py                scripts/audit_nb_live.py
  (NLM_NOTEBOOKS shim)                            │
              │                                   ↓ (mutates registry: SENESCENT → *_PENDING)
              ↓                                   │
   4 consumer files unchanged                     ↓
                                  scripts/execute_apoptosis.py
                                                  │
                                  ┌───────────────┴───────────────┐
                                  ↓                                ↓
                         --dry-run preview              --apply transitions
                          (manual review)              (NLM rename + export)
                                                                  │
                                                                  ↓
                                          regenerate _registry_data.py
                                          (after EACH transition; status: *_PENDING → APOPTOSIS_DONE)
                                                                  │
                                                                  ↓
                                          docs/nb-lifecycle/round1-19-ambiguous-decisions-2026-05-07.md
                                          research/nb-archive/audit_log.md (append)
                                          research/nb-archive/<uuid>-<slug>-2026-05-07.md (× 14 exports)
```

---

## 5. Decision matrix doc — 19 ambigui

**Path:** `docs/nb-lifecycle/round1-19-ambiguous-decisions-2026-05-07.md`

**Purpose:** document the 19 NB classified `ORPHAN_REVIEW` (8 orphan_unclear + 5 research_heavy + 4 subhi_merge + 2 zero_value_orphan) so Zero can decide each separately. This PR does NOT execute action on these 19; the doc only stages decisions.

**Schema:**
- Summary table with 4 cluster rows + count + cluster description
- Per-cluster sections explaining classification rules used
- Per-NB matrix: title, UUID, source_count_live, peer_uuids, snapshot drift, recommended action, **`Zero decision (YYYY-MM-DD):`** placeholder line for human resolution
- Final §Follow-up section listing the 4 consumer files with `NLM_NOTEBOOKS` callsites needing migration in a future PR

**Generation:** `scripts/execute_apoptosis.py::generate_decision_matrix()` reads `NOTEBOOK_REGISTRY`, filters `status == "ORPHAN_REVIEW"`, groups by `cluster`, renders markdown.

**Follow-up section content:**

```markdown
## §Follow-up — `NLM_NOTEBOOKS` callsites pending migration

This PR keeps these consumers on the compat shim. Future PR should migrate them
to `notebook_registry.NOTEBOOK_REGISTRY` directly:

- `apps/mata-garuda/mata_garuda/agents/sentinel_actor.py`
- `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py`
- `apps/mata-garuda/mata_garuda/agents/nlm_expander_agent.py`
- `apps/backend-rag/backend/tools/health_tools.py`

Total references: ~9. Migration is a pure refactor (no behavior change required).
```

---

## 6. Test plan

All tests live under `apps/mata-garuda/tests/`. TDD strictly: red → green per file.

### 6.1 `test_notebook_registry.py`
- `test_registry_loads_without_error`
- `test_notebook_entry_is_frozen_dataclass`
- `test_get_legacy_notebooks_dict_returns_6_uuids`
- `test_get_legacy_notebooks_dict_only_active`
- `test_get_notebook_returns_none_for_unknown_uuid`
- `test_get_by_status_returns_correct_subset`
- `test_get_by_cluster_returns_correct_subset`
- `test_registry_uuid_format` — all UUIDs match v4 regex
- `test_registry_no_duplicate_legacy_keys`

### 6.2 `test_compat_shim.py`
- `test_legacy_dict_matches_registry`
- `test_legacy_dict_byte_identical_to_pre_pr_snapshot` — hardcoded 6-UUID frozen snapshot
- `test_legacy_dict_keys_match_expected_set`
- `test_legacy_dict_uuid_format`

### 6.3 `test_no_circular_import.py`
- `test_notebook_registry_imports_alone` — uses `sys.modules` introspection
- `test_config_imports_after_registry`
- `test_registry_data_imports_alone`

### 6.4 `test_manifest_schema.py`
- `test_manifest_yaml_loads_valid`
- `test_manifest_has_required_top_level_fields`
- `test_candidates_count_matches_list_length`
- `test_each_candidate_has_required_fields`
- `test_each_candidate_uuid_format`
- `test_cluster_values_are_in_enum`
- `test_match_status_values_are_in_enum`
- `test_clusters_summary_matches_actual_counts`

### 6.5 `test_idempotent_re_run.py`
- `test_run_1_partial_failure_persists_done_state` — 17 NB *_PENDING → mock 10 success + 7 fail → registry: 10 DONE + 7 PENDING
- `test_run_2_resumes_from_pending` — initial: 10 DONE + 7 PENDING → mock all success → final: 17 DONE
- `test_run_3_no_op_when_all_done` — initial: 17 DONE → asserts ZERO mcp calls made
- `test_apoptosis_idempotent_skips_already_renamed_nb` — NLM-side: NB name already starts with `[ARCHIVED-...]` → script returns success without re-rename
- `test_persistence_after_simulated_sigkill` — process N transitions, simulate SIGKILL mid-loop, restart process, verify N transitions persisted to `_registry_data.py`

### 6.6 `test_audit_pipeline.py`
- `test_drift_detection_consistent` — delta ±1 → consistent
- `test_drift_detection_drifted` — delta >5 → drifted, force ORPHAN_REVIEW
- `test_drift_detection_unknown` — current==null → unknown_via_mcp_failure
- `test_t2a_cookie_refresh_proactive` — mock `nlm whoami` to fail, assert `nlm login --clear` invoked
- `test_t2b_retry_with_backoff` — first call raises TransientMCPError, second succeeds → returns success after sleep
- `test_t2c_hard_cap_aborts_phase` — 9/17 mock failures (>50%) → assert telegram_alert called + `sys.exit(2)`
- `test_audit_log_append_only` — entries appear chronologically, format conforms

### 6.7 `test_apoptosis_dry_run.py`
- `test_dry_run_makes_no_mcp_calls` — spy on `mcp_rename`, assert `call_count == 0`
- `test_dry_run_writes_preview_to_tmp`
- `test_dry_run_preview_lists_all_pending_nb`
- `test_dry_run_preview_mentions_apply_command`

### 6.8 `test_export_format.py`
- `test_slugify_strips_non_ascii`
- `test_slugify_handles_empty_input_with_fallback_untitled`
- `test_slugify_truncates_at_80`
- `test_export_filename_format` — `<uuid_short>-<slug>-2026-05-07.md`
- `test_export_frontmatter_fields_complete`
- `test_export_includes_summary_500w`
- `test_export_includes_reimport_command_for_url_sources`
- `test_export_omits_reimport_for_text_sources`

### 6.9 `test_decision_matrix.py`
- `test_decision_matrix_groups_by_cluster`
- `test_decision_matrix_lists_all_19_orphan_review`
- `test_decision_matrix_includes_callsite_followup_section`
- `test_decision_matrix_zero_decision_marker_present_per_nb`

### 6.10 Integration runbook (manual, not pytest)
`tests/integration/test_e2e_apoptosis.md`:
1. Cleanup test branch + worktree
2. Create worktree fresh from `origin/main`
3. Run `scripts/build_manifest.py` → assert YAML created with 36 entries
4. Run `scripts/audit_nb_live.py` → assert JSON created, registry has `*_PENDING`
5. Run `scripts/execute_apoptosis.py --dry-run` → assert `/tmp` preview
6. Manual review preview
7. Run `scripts/execute_apoptosis.py --apply` → assert 17 renamed in NLM
8. Verify decision matrix doc generated
9. Run `pytest` → all green
10. Verify worker workers ancora funzionanti (mata-garuda nlm-feeder cron)

### Coverage target
- Unit tests: ≥90% line coverage on `notebook_registry.py`, `_registry_data.py`, `build_manifest.py`, `audit_nb_live.py`, `execute_apoptosis.py`
- Integration: manual runbook executed + verified pre-merge

---

## 7. Commit / PR cadence

### 7.1 Branch & worktree
- Branch: `feat/nb-senescent-decomm-2026-05-07` from `origin/main`
- Worktree: `/Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent`
- Created via `git worktree add -b ... origin/main`

### 7.2 Branch hijack antibody (revised, C5)
Before each `Edit` / `Write` in the implementation phase:

```bash
test "$(git -C /Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent rev-parse --abbrev-ref HEAD)" \
  = "feat/nb-senescent-decomm-2026-05-07" || exit 1
```

If branch differs (sibling session checked out something else in this worktree, or the worktree was redirected), abort the operation. The blanket `ps aux | grep -c claude > 2` precondition is dropped — Zero confirms 6 sessions are intentional in this wave.

### 7.3 WIP commit cadence (revised, C6)
Every 30-45 min during audit/APOPTOSIS phase, run atomic compound:

```bash
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent && \
  git add apps/mata-garuda/ research/nb-archive/ docs/nb-lifecycle/ scripts/data/ && \
  git commit -m "WIP(nb-lifecycle): checkpoint $(date +%H:%M) — work in progress" && \
  git push origin feat/nb-senescent-decomm-2026-05-07
```

Single shell pipeline. No interleaved Read/Write/Bash between `commit` and `push`. Skip if working tree is clean.

### 7.4 Logical commits (D3 hybrid + dry-run gate)

**C1 — Foundation + audit + registry `*_PENDING`**

Title: `feat(nb-lifecycle): registry SSOT + Round 1 candidates audit (Phase 0+0.5)`

Files committed:
- `apps/mata-garuda/mata_garuda/notebook_registry.py` (new)
- `apps/mata-garuda/mata_garuda/_registry_data.py` (new, populated)
- `apps/mata-garuda/mata_garuda/config.py` (S1 shim)
- `apps/mata-garuda/data/nb_round1_candidates_2026-05-07.yaml`
- `apps/mata-garuda/scripts/build_manifest.py`
- `apps/mata-garuda/scripts/build_registry_from_manifest.py`
- `apps/mata-garuda/scripts/audit_nb_live.py`
- Test files §6.1–6.4, 6.6
- `scripts/data/nb_decomm_audit_2026-05-07.json`
- `research/nb-archive/audit_log.md` (initial entries)
- `research/nb-archive/fuzzy_match_log_2026-05-07.md`

Pre-commit gates:
- `pytest apps/mata-garuda/tests/` → green
- `python -c "from mata_garuda import config; from mata_garuda.notebook_registry import NOTEBOOK_REGISTRY"` → no error
- `python -c "from mata_garuda.config import NLM_NOTEBOOKS; assert len(NLM_NOTEBOOKS) == 6"` → success

**Gate Zero** (between C1 and C2):
1. `python apps/mata-garuda/scripts/execute_apoptosis.py --dry-run` → `/tmp/apoptosis-preview-2026-05-07.md`
2. Notify: "Dry-run preview at `/tmp/apoptosis-preview-2026-05-07.md`. Review please."
3. Wait for explicit `ok procedi` or `abort` from Zero.
4. If `abort`: PR ships with C1 only. Title updated to `feat(nb-lifecycle): registry SSOT + Round 1 audit (Phase 0+0.5, APOPTOSIS deferred)`.
5. If `ok procedi`: continue to C2.

**C2 — APOPTOSIS execution + decision matrix**

Title: `feat(nb-lifecycle): APOPTOSIS 17 univoci + decision matrix 19 review`

Files committed:
- `apps/mata-garuda/mata_garuda/_registry_data.py` (regenerated; 17 entries `APOPTOSIS_DONE`)
- `apps/mata-garuda/scripts/execute_apoptosis.py` (new)
- Test files §6.5, 6.7, 6.8, 6.9
- `research/nb-archive/<uuid_short>-<slug>-2026-05-07.md` × 14
- `research/nb-archive/audit_log.md` (appended APOPTOSIS phase)
- `docs/nb-lifecycle/round1-19-ambiguous-decisions-2026-05-07.md` (new)

Pre-commit gates:
- All tests green
- Audit log shows ≥1 `APOPTOSIS_DONE` transition per processed NB
- Registry consistency: `[e for e in registry if e.status in ("KILL_PENDING", "EXPORT_PENDING")]` reports residue (failed renames) — log non-fatal

### 7.5 Push within 30s
Every `git commit` in this branch is followed by `git push origin feat/nb-senescent-decomm-2026-05-07` within 30s, no interleaved tool calls.

### 7.6 PR

Title: `feat(nb-lifecycle): Phase 0+0.5 — registry SSOT + 17 APOPTOSIS_DONE + 19 review pending`

Body:
```markdown
## Summary
- Created `notebook_registry.py` SSOT (R6 anti-pattern fix #1)
- Migrated 6 active NB UUIDs from `config.NLM_NOTEBOOKS` literal to registry
- Audited 36 Round 1 candidates against live NotebookLM state
- Renamed 17 NB in NotebookLM (3 placeholder → ARCHIVED, 14 playbook → EXPORTED)
- Generated decision matrix doc for 19 ambiguous NB pending Zero approval
- Compat shim preserves `NLM_NOTEBOOKS` byte-identical for 4 unchanged consumer files

## Out of scope (deferred to follow-up)
- NLM_NOTEBOOKS callsite migration (4 files, 9 references) — see decision matrix §Follow-up
- 19 ambiguous NB final action (orphan review/research consolidation/Subhi merge/zero-value)
- NLM_DOMAIN_ROUTING refactor

## Test plan
- [x] pytest green (apps/mata-garuda/tests/)
- [x] No circular import test passes
- [x] Compat shim byte-identical with pre-PR snapshot
- [x] Idempotent re-run test (3 scenarios)
- [x] Dry-run gate executed + Zero approved before C2
- [x] All 17 renames verified in NotebookLM (manual spot check)
- [x] Decision matrix doc generated with all 19 NB

## Audit artifacts
- `apps/mata-garuda/data/nb_round1_candidates_2026-05-07.yaml` (36 entries manifest)
- `scripts/data/nb_decomm_audit_2026-05-07.json` (live audit + drift)
- `research/nb-archive/audit_log.md` (append-only audit trail)
- `research/nb-archive/fuzzy_match_log_2026-05-07.md` (title fuzzy matches)

## Cicatrix scars referenced
- 2026-04-29 STRUCTURAL: untracked file loss (30-45min WIP commit pattern applied)
- 2026-04-29 STRUCTURAL: `_schema_versions` vs `schema_migrations` (no migrations in this PR)
- 2026-04-29 STRUCTURAL: branch hijack (per-Edit/Write branch verification)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

### 7.7 Tri-LLM review (relaxed 2/3, C8)
- DeepSeek Reasoner: review C1 architecture (registry stand-alone, compat shim semantics, no circular)
- Gemini 3.1 Pro: review C2 execution (dry-run gate, idempotency, T2.a/b/c integration)
- NotebookLM NB-1: ground-truth check on mata-garuda module structure invariants

If 2/3 green → merge. If ≥1 BLOCKER → fix + re-review. If capacity exhaustion (DeepSeek+Gemini both unhealthy): 1/3 (NB-1 only) sufficient + manual Zero review.

---

## 8. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Compat shim returns wrong dict (consumers break) | `test_legacy_dict_byte_identical_to_pre_pr_snapshot` with hardcoded frozen 6-UUID dict |
| Circular import `config ↔ notebook_registry` | `test_no_circular_import` + `_registry_data` is pure data (no imports beyond typing) |
| Crash mid-APOPTOSIS leaves NLM in inconsistent state | 2-stage state machine (`*_PENDING` → `APOPTOSIS_DONE`) + persistence after EACH transition + idempotent re-run |
| MCP cookies expire mid-run | T2.a proactive `nlm login --clear` refresh; T2.b 1 retry + 5s backoff |
| Cascade failure (>50%) | T2.c hard cap aborts with telegram alert + `sys.exit(2)` |
| Decision matrix 19 NB never get human review | §Follow-up explicit in PR body; doc has `Zero decision (YYYY-MM-DD):` placeholder per NB |
| Branch hijack (sibling session) | Per-Edit/Write branch verification (C5 revised); atomic compound commit (C7) |
| WIP commit churn | 30-45 min cadence (C6 revised); skip if tree clean |
| Manifest YAML drift from live NLM | Drift detection in audit script; `unknown_via_mcp_failure` for unreachable |
| Title fuzzy matching false-positive | Levenshtein ≤3 + log fuzzy matches to `fuzzy_match_log_2026-05-07.md` for review |
| Stack creep (new deps) | C10 inviolable; design uses only stdlib + `pydantic` already present |
| API HTTP slip | C9 inviolable; all NLM ops via `nlm` CLI subprocess + MCP tool calls (CLI-mediated) |

---

## 9. Decisions log

- **D3 hybrid + dry-run gate (chosen over D1 strict 5-commit, D2 atomic)** — balances reviewability with branch hijack mitigation; dry-run gate gives Zero veto before irreversible NLM rename.
- **S1 compat shim re-export literal (chosen over S2 inline import or S3 lazy property)** — zero magic, snapshot at import time, debuggable.
- **5c Python literal `_registry_data.py` (chosen over 5a JSON, 5b YAML at runtime)** — type-checkable, importable, no parsing cost.
- **6abc all 3 export modes** — playbook content as markdown body, URL sources as `reimport_command` field, text sources as inline summary.
- **T2 best-effort with 3 vincoli (T2.a cookie refresh, T2.b 1 retry+backoff, T2.c hard cap)** — pragmatic given MCP reliability profile (cookies 5min TTL, transient timeouts common).
- **Persistence after EACH transition (chosen over end-of-run only)** — crash-safety per Zero req; SIGKILL test added.
- **Approach A STRIP-DOWN (chosen over original week-long roadmap)** — fits 4-6h sprint, ships SSOT + 17 univoci + decision doc, defers callsite migration to follow-up PR.
- **Per-Edit/Write branch verification (revised antibody, replaces `ps aux > 2`)** — Zero confirms 6 sessions intentional; the real risk is sibling session checkout in shared worktree, not session count.
- **WIP cadence 30-45 min (revised from 90 min)** — Zero req given 6 parallel sessions wave + scar reproduced 3× already.

---

## 10. Open questions

None at design time. Pending Zero spec review.

---

## 11. References

- `mata-garuda/CLAUDE.md` §1 (vincoli inviolabili), §3 (struttura package)
- `~/.claude/projects/-Users-nuzantara/memory/project_nb_lifecycle_master_2026_05_04.md`
- `~/.claude/projects/-Users-nuzantara/memory/project_nb_lifecycle_round5_2026_05_04.md`
- `~/.claude/projects/-Users-nuzantara/memory/reference_notebooklm_arsenal_full.md`
- `.claude/rules/cicatrix-scars.md` (2026-04-29 STRUCTURAL: branch hijack, untracked loss)
- `apps/mata-garuda/mata_garuda/config.py` (current `NLM_NOTEBOOKS` literal)
- `SYMBIOSIS.md` (Law 5: Zero ultima istanza)
