---
date: 2026-10-06
domain: operations
client_case: none
adversarial_review: human-zero
sources:
  - data/source_documents/KBLI_2025_FINAL_CLEAN.json
  - apps/mouth/data/kbli-gold-all.json
  - infra/claude-hooks/data-plane-registry.json
  - .github/workflows/kbli-filiera-vault-compilers.yml
---

# KBLI corpus health audit — Batch B (2026-10-06)

Read-only health audit of the KBLI corpus per the `/kbli-navigator` skill map, run by an
external-builder seat (Kimi K3, Air-M5) in worktree `.worktrees/docs-kbli-corpus-audit-1006`,
branch `agent/air-m5/docs/kbli-corpus-audit-1006`, base `origin/main @ 83237f8f93` (2026-10-05/06).
**Zero data changes** — every measurement below is a read of `origin/main` content.
All commands are quoted in the appendix; probes were one-off stdlib-Python scripts (also
quoted), not committed.

## Corpus inventory (what "the corpus" is)

| file | role | bytes |
|---|---|---|
| `data/source_documents/KBLI_2025_FINAL_CLEAN.json` | canonical dataset (1,559 KBLI-2025 codes) | 38,653,373 |
| `source_documents/` → `data/source_documents/` | tracked symlink to the same | — |
| `apps/mouth/data/KBLI_2025_FINAL_CLEAN.json` | mouth consumer copy | 38,653,373 |
| `apps/kbli-navigator/data/kbli-2025.json` | navigator-app fork | 38,653,373 |
| `apps/mouth/data/kbli-gold-all.json` | gold editorial layer (428 records) | 1,989,151 |
| `apps/mouth/data/kbli-dataset-version.json` | sidecar (git-date + sha256) | 577 |

**Copy parity: PASS.** `shasum -a 256` of all three dataset copies returns the identical digest
`c29d6e6aea7a4fdbda5e9794224e22db207bd777329de83f15fc951deaee3450`, which also equals the
`datasetSha256` recorded in the sidecar. The two gitignored RAG runtime copies inside
`apps/backend-rag` are rebuilt in-container and were not audited (not on disk in a checkout).

## Invariant 1 — FLAT payloads

**Verdict: PASS where the invariant is defined (the Qdrant payload boundary); the on-disk
canonical file is NOT flat and was never meant to be.**

The "KBLI flat-payload golden rule" is a rule about the **Qdrant point payload**, not the JSON
document: `apps/backend-rag/backend/scripts/reindex_kbli_2025_final.py` carries explicit
"flat payload (KBLI flat-payload golden rule)" comments, and
`backend/tests/unit/scripts/test_kbli_payload_contract.py::test_reindex_kbli_payload_is_flat`
pins `"metadata" not in payload` with scalar top-level fields. It exists because the gold
indexer was born writing a nested `metadata` block against the flat contract (#3832/#3839).

Measured programmatically by running **every** record through the real code
(`build_payload` from `reindex_kbli_2025_final.py` for all 1,559 canonical records, and
`build_payload` from `index_kbli_gold_content.py` for all 428 gold records), then asserting
no dict values, no list-of-non-scalar values and no `metadata` key on the emitted payloads:

- BPS/canonical payloads: **1,559 built, 0 non-flat** (39 fields each, all scalar or
  list-of-scalars).
- Gold payloads: **428 built, 0 non-flat** (29 fields each).

At file level the canonical document is a nested structure: a `{metadata, data}` envelope, and
per-record sub-objects (`per_skala` scale rows, `per_skala_legacy`, `intel_2026`, `l4_bali`,
`bps_2020_ancestors`, `ruang_lingkup`) — 18,881 nested-value sites by enumeration. Gold records
likewise carry nested `tkaInfo` (139 records) and `_l3_gap_disclosure` (39). This is by design;
any consumer assuming a flat on-disk record would be wrong, but no invariant claims flatness
there.

## Invariant 2 — CURATED (data-plane guard)

**Verdict: PASS — no hand-edited drift detectable in git history; two machine identities only,
every write PR-shaped, and every post-guard canonical write traceable to a compiler/spec.**

- The guard is real and registered: `infra/claude-hooks/data-plane-registry.json` entry
  `kbli-filiera` (compilers: `scripts/kbli_filiera/`) protects
  `data/source_documents/KBLI_2025_FINAL_CLEAN.json`, the OSS ground truth and the perpres
  sidecars; entry `kbli-gold-editorial` (registered 2026-07-25) protects the gold file. CI
  twin: `.github/workflows/kbli-filiera-vault-compilers.yml`, whose `paths:` deliberately
  includes the canonical dataset so a data-plane commit cannot dodge the gate.
- Provenance of the canonical file: **113 commits** (`git log --follow`), authors exactly two
  machine identities — 90 × `Bali Zero`, 23 × `Claude Opus`. **Zero human-authored commits,
  zero direct-to-main pattern visible** (every subject carries a PR number).
- Era split: `scripts/kbli_filiera/` was created 2026-07-17 (`d9b14a00fd`, #2556). Before that,
  canonical writes travel with batch-enrichment scripts (`scripts/kbli_enrich_write.py`,
  `scripts/kbli_audit_patcher.py` — both named as legacy one-shot writers in the gold registry
  entry) or with no script at all; after that date, canonical-touching commits carry a
  `scripts/kbli_filiera/` change in the same commit, **with exactly two exceptions**:
  - `d50d5f33ca` (#2896, 2026-07-20, Lot 8 apply) — applies `batch_a_lot8.json` (spec file)
    and pins `scripts/tests/test_kbli_batch_a_lot8_registry.py` in the same commit;
  - `04b93e3e16` (#2725, 2026-07-18, Lot 1 apply) — same shape: spec-apply commit with its
    registry test and the `kbli_qdrant_risk_clear.py` cure script.
  Both are spec-driven applies from the Batch-A program, not hand edits.
- Gold layer (`kbli-gold-all.json`): 36 commits, 30 × `Bali Zero` + 6 × `Claude Opus`, all
  PR-shaped. Per the skill, gold is deliberately *not* fully data-plane-guarded ("edit
  value-in-place + pin with a regression test") — its registry entry names six cure compilers
  plus three legacy one-shot writers.
- Known pre-guard weakness (state, not drift): the Feb–Jun 2026 enrichment era wrote the
  canonical directly with no compiler of record. Nothing in this audit re-derives those values;
  the Filiera program exists precisely to re-validate them against government ground truth
  (the north star, 1,559 codes). No drift *signature* (human author, non-PR subject, or
  script-less post-guard edit) was found.

## Invariant 3 — counts and coverage

Measured on the canonical file (all figures independently reproduced by the repo's own
`scripts/kbli_filiera/kbli_coverage_scoreboard.py`, which printed identical numbers — see
appendix):

**Totals: PASS**
- **1,559** KBLI-2025 records; **0 duplicate codes**; **0 non-5-digit code formats**; **0**
  key↔`kode_kbli_2025` mismatches; all 1,559 carry `judul`, `uraian`, `pma_status`,
  `pma_verification_status`, `_source`, `_l1_source`.
- 39 distinct top-level fields; the file self-declares `total_codes: 1559` in `metadata`.

**Axis coverage (complete vs partial field sets):**

| axis | complete | gap | what the gap is |
|---|---|---|---|
| licensing (`per_skala`) | 1,350/1,559 (86.6%) | 209 | all 209 carry `_l2_status: no_oss_risk` (OSS ruang-lingkup 404 class, declared gaps) |
| risk tiers (in `per_skala` rows) | 1,350/1,559 (86.6%) | 209 | same population as licensing — no scale rows ⇒ no risk rows |
| PMA (`pma_verification_status`) | 722 located (46.3%) | 837 declared_gap (53.7%) | Perpres axis; located set = adjudicated + Pasal 3(1)(d) residuals |
| 2020 crosswalk (`bps_2020_ancestors` non-empty) | 1,559/1,559 (100%) | 0 | mechanical-only, **0 adjudicated** (scoreboard) — honest, not a defect |

Cross-tab (licensing × pma × risk): **668** complete on all three, **682** licensing+risk
present but PMA `declared_gap`, **155** gap on all three, **54** licensing/risk gap but PMA
`located` (Perpres-located codes inside the no-scale class).

Row-level completeness inside the 8,930 `per_skala` rows: `skala_usaha`/`kategori_risiko`/
`jangka_waktu`/`perizinan`/`persyaratan`/`kewajiban`/`kewenangan` keys present on 8,930/8,930
(the field-trap documented in the skill: `perizinan` is **populated on only 2 codes** —
`43110`, `49213` — in the new-shape rows; permit names live on `per_skala_legacy`, populated
on 1,259 codes). Empty-value census: `perizinan` empty 8,915/8,930 (by design), `persyaratan`
empty 3,687, `kewajiban` empty 122, `kewenangan` empty 45, `jangka_waktu` empty 165.

**Schema-shape outliers found (all small, none silent):**
- `01122` — the Lot-0-created code: absent 7 near-universal fields
  (`_source_relabeled`, `pp28_sources`, `pma_kondisi`, `pma_max_asing`, `pma_nota`,
  `pma_prioritas`, `status_mapping`); by design (it is the honest S2 shape, #7017).
- `pma_max_asing` is the **string** `"special"` on `47221` (int elsewhere, null on `01122`) —
  deliberate (special-regime regime, `pma_cap_special` on 15 codes).
- `per_skala_disputed_pp28_collision` is a **dict on 2 records** (`20111`, `49213`) vs a list
  on the other 115 carriers — same field, two shapes.
- `43110` alone carries `parameter`/`pb_umku`/`sanksi_*` keys inside 3 `per_skala` rows, and
  its `perizinan` values are **strings** while `49213`'s are **lists** — intra-field type
  inconsistency on the one populated licensing field.
- Gold layer: exactly **8 gold codes with no canonical record** (`64921`, `85300`, `85491`,
  `85499`, `85600`, `86903`, `96120`, `96130`) — matches the skill's ledgered phantom list
  8/8; 1,139 canonical codes have no gold entry (428 gold pages of 1,559).

## Top gaps, ranked

1. **PMA basis: 837/1,559 (53.7%) still `declared_gap`** — the most-read client fact on the
   product has no per-code locator on the majority of codes. (Scoreboard-honest, but the
   dominant remaining exposure; the F2/Pasal 3(1)(d) lots have been closing it ~250–330 codes
   at a time.)
2. **209 no-scale codes (13.4%)** — no licensing rows, no risk tiers, no `ruang_lingkup`
   (221 empty there), `sektor_id` null on 217. All are the OSS-404 `no_oss_risk` class; the
   weekly OSS refresh loop proposes cures but **the applier compiler does not exist yet**
   (PENDING-ARMS `kbli-oss-refresh-proposals-have-no-applier`).
3. **0 adjudicated crosswalks** — 100% of pages render 2020 ancestry from a mechanical
   BPS crosswalk nobody has adjudicated per code (the north star's core remaining work).
4. **Licensing permit names effectively absent from the current-shape rows** (`perizinan`
   on 2/1,559 codes) — any consumer reading only `per_skala[].perizinan` sees an empty
   licensing layer; the real vocabulary sits in `per_skala_legacy[].pb_umku`/`perizinan`.
5. **Small schema-shape outliers** listed above — cheap to normalize in a compiler lane if
   anything ever keys on them; today nothing does (payload builders read defensively).

## Safe follow-up lanes

- **OSS-refresh applier compiler** — the blocked cure for gap #2; spec proposals already
  exist on disk from the weekly loop. Needs the compiler + its own gate (data-plane write).
- **Crosswalk adjudication batches** — gap #3; the D0–D6 protocol and vault exist; per-batch
  Opus final gate is the standing rule.
- **PMA residual lots** — gap #1 continues lot-by-lot exactly as Lots 1–2 shipped; the
  remaining `declared_gap` population is the queue.
- **Schema-normalization compiler** (optional, low value): unify `per_skala_disputed_*`
  shapes, the `43110`/`49213` `perizinan` string-vs-list, and `47221`'s string cap — only
  worth it if a future reader starts keying on those fields.
- **Payload-flatness CI probe** — the flat invariant is only pinned for `build_payload`
  units via tests; a corpus-level probe (all 1,559 + 428 payloads) could run in the
  existing vault-compilers workflow cheaply, reusing this audit's approach.

## What was NOT checked

- Runtime stores (Qdrant collections, `kg_nodes`, `kbli_documents`, inspect cache) — corpus
  audit only; the surface-conformance detector and the 2026-09-22 sync cover those, and the
  gitignored in-repo RAG copies are not in a checkout.
- Field-level *truth* of any value against government sources — this measures presence,
  shape, provenance and coverage, not correctness (that is the Filiera program).
- The `tka_kbli_positions.json` and `KBLI_2017_TO_2025_MAPPING.json` neighbours, and the
  navigator-app `gold/` directory.
- Pre-guard (pre-2026-07-17) canonical writes were inventoried by author/commit shape, not
  re-derived value by value.
- Live surfaces (`balizero.com/kbli/*`, `inspect_kbli`) — no network probes.

## Appendix — commands (run in the worktree at `origin/main @ 83237f8f93`)

```bash
# copy parity
shasum -a 256 data/source_documents/KBLI_2025_FINAL_CLEAN.json \
  apps/mouth/data/KBLI_2025_FINAL_CLEAN.json apps/kbli-navigator/data/kbli-2025.json
cat apps/mouth/data/kbli-dataset-version.json

# provenance
git log --follow --format='%h|%ad|%an|%s' --date=short -- data/source_documents/KBLI_2025_FINAL_CLEAN.json
git log --format='%h|%ad|%an|%s' --date=short -- apps/mouth/data/kbli-gold-all.json
git log --reverse --format='%h %ad %s' --date=short -- scripts/kbli_filiera/ | head -3
python3 -c "import json; [print(e['id'],'| compilers:',e['compilers'],'| protected:',len(e['protected'])) \
  for e in json.load(open('infra/claude-hooks/data-plane-registry.json'))['entries']]"

# counts / coverage (repo's own scoreboard — output reproduced verbatim in §Invariant 3)
python3 scripts/kbli_filiera/kbli_coverage_scoreboard.py

# flatness: run every record through the real payload builders and assert no nesting.
# One-off stdlib script (not committed): for each of the 1,559 canonical entries call
# backend.scripts.reindex_kbli_2025_final.build_payload(entry, build_embedding_text(entry, registry), registry)
# and for each of the 428 gold records backend.scripts.index_kbli_gold_content.build_payload(code, gold, base, text, registry);
# assert per payload: 'metadata' not in payload and no isinstance(v, dict) and no nested list items.
# Result: 1559/1559 and 428/428 flat (interpreter: apps/backend-rag/.venv/bin/python).

# file-level nesting census + schema/coverage profile: one-off stdlib script over
# data/source_documents/KBLI_2025_FINAL_CLEAN.json keyed by kode_kbli_2025
# (duplicate check, 5-digit format check, field-shape census, per_skala emptiness,
# cross-tab of licensing × pma × risk). Results quoted in §Invariant 3.
```

## Adversarial review

Author seat: Kimi K3 (external builder). Declared reviewer: the interactive Claude session that
verifies and merges this PR under the external-agent contract (generator ≠ grader; family
≠ author), recorded as `human-zero` per the R1 gate's `human-*` seat rule. Suggested refutation
targets, cheapest first: (1) re-run the two `shasum` and the scoreboard commands and compare
against §Invariant 3; (2) re-run the payload-flatness probe on a sample of 20 codes plus the
two known-populated `perizinan` codes; (3) verify the post-guard drift claim by listing
canonical-touching commits after `d9b14a00fd` without a `scripts/kbli_filiera/` change and
confirming both are the spec-apply commits named above; (4) confirm the 8 gold phantoms match
`scripts/kbli_gold_remap_table.json`. The verifier may annotate this section with its verdict.
