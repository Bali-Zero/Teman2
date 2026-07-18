---
date: 2026-07-18
domain: operations
client_case: none (GARUDA-FILIERA Batch A — LANE-E1 lot report)
adversarial_review: none (D5 blind refutation in-pipeline; conductor D6 gate pending)
sources:
  - "plan: research/operations/2026-07-18-kbli-batch-a-plan.md (pre-registration, §3 A1-A6, §5 m1-m5)"
  - "workflow: research/operations/2026-07-16-kbli-garuda-filiera-workflow.md (D0-D6)"
  - "calibration: data/kbli-filiera/batch-reports/batchA-calibration.md (SIGNED, conductor f5892d39)"
  - "pinned canonical: git 45bbc1f4 (blob 3cfe8134d) · manifest sha256 e7d25a37 · membership sha256 aa0a0a69"
---

# GARUDA-FILIERA Batch A — LANE-E1 lot 01 (division 01) report

> Lane E1 owns D0-D4. This report is the lane's measured output for lot 01; the conductor signs
> lot reports and runs D6. Quarantines are PROPOSED here, never adjudicated (mandate).

## Scope + grounding (pinned)

- **Codes** (taxonomy division 01, 2 members of the 114-code Wave A-serving): `01287`, `01700`.
- **Canonical** pinned at git `45bbc1f42a0c74d12c3021f56a54565a747a01c7` — verified the pinned commit
  carries canonical blob `3cfe8134d` (the stable content on main from #2618/e7152ad9c → HEAD).
- **Manifest** `vault-manifest-batch0-2026-07-18.json` sha256 `e7d25a37…` — matches the calibration pin.
- **Membership** `batch-a-members.json` sha256 `aa0a0a69…` — matches the calibration pin; the 114-code
  wave was re-derived byte-exact from the §1 predicate on the pinned canonical.
- **Vault** mirrored Mini→Pro (508 MB, 4960 files); a 31-item sha256 sample (incl. the BPS Vol.2 PDF,
  PP28 lampiran, and both lot codes' OSS dirs) verified 0 mismatch / 0 missing against the pinned manifest.
- **Leases**: `agent_lock:kbli-dossier:{01287,01700}` acquired before touch, released after assembly (P3).

## Per-code verdicts (D1 crosswalk → D5 blind refute → D2 conditional)

| Code | D1 mapping | needs_quar | licensing_inherits | D5 verdict | D5 refuted | Outcome |
| --- | --- | --- | --- | --- | --- | --- |
| 01287 | ONE_TO_ONE (01287→01287) | false | false | certified | false | **CERTIFIED CLEAN** |
| 01700 | MERGE 6→1 (01711/01712/01713/01714/01715/01719 → 01700) | **true** | false | certified | false | **QUARANTINE (proposed)** |

- **01287** (Pertanian Tanaman Narkotika dan Tanaman Obat Terlarang, TERTUTUP): genuine code-preserving
  1:1 continuation, bidirectional crosswalk confirmed image-grade (Lampiran 5 p.132 + Lampiran 10 p.326);
  licensing is OSS-RBA-2025-native (`_l1_source=OSS_RBA_2025`), NOT PP28-vintage → nothing to inherit,
  D2 correctly skipped. D5 independently re-derived and agreed (noted one non-substantive clerical
  off-by-one in D1's notes: "7 files" vs the actual 8 evidence-index entries — does not touch the verdict).
- **01700** (Perburuan, Penangkapan, dan Kegiatan Jasa Terkait, TERBUKA): a 6-way MERGE — six 2020
  hunting/trapping subclasses (primates/mammals/reptiles/birds/… 01711-01719) consolidated into one 2025
  code. Same class as pilot A1's 20111 quarantine: licensing cannot cleanly inherit from any single source,
  it must aggregate across all six — which the current single-source fill does not do. D1 self-flagged
  `needs_quarantine=true`; D5 agreed the MAPPING (refuted=false) but the code stays quarantined by the D1 flag.

## D4 discrepancy scan (observational, deterministic — provenance is D1's verdict, not this scan's)

Both codes carry a **declared_pp28_source_not_in_vault** observation: the canonical `pp28_sources`
pointer is not corroborated in the pinned PP28 corpus (21 files / 11,208 pages scanned, image-grade
fuzzy-code search, verdict ABSENT):
- `01287`: declares `pp28_sources=[01287]` → ABSENT. D1 ruled licensing_inherits=false (OSS-native), so
  the pointer is **vestigial**, not licensing-bearing.
- `01700`: declares `pp28_sources=[01711]` → ABSENT (and it is only 1 of the 6 merged 2020 ancestors).

## Measurements (extends the calibration baseline)

| Metric | Lot 01 | Calibration limit | Status |
| --- | --- | --- | --- |
| m1 extractor/refuter blind-concordance | 2/2 = 1.00 | floor 0.75 | ✅ |
| m2 certification rate (certified_clean / adjudicated) | 1/2 = 0.50 | [0.20, 0.85] | ✅ |
| m3 refutation categories seen | none new (01700 = merge-aggregation, in-registry) | closed list | ✅ |
| m4 tokens / code | 201,944 (403,889 / 2) | ceiling 400,000 | ✅ |
| m5 gold-set hit rate | n/a (conductor-injected, not in this wave) | 1.00 | — |

D0 evidence pull: ~18.75 s/code on Pro (BPS crosswalk render-scan + 21-lampiran PP28 scan dominate).
Extraction: 4 Sonnet seats (D1+D5 ×2; no D2 — neither code inherits), 330 s wall, 0 errors.

## Deliverables

- `data/kbli-filiera/dossiers/01287.jsonl` — 4 hash-chained events (D0→D1→D5→D4), chain verified.
- `data/kbli-filiera/dossiers/01700.jsonl` — 4 hash-chained events, chain verified.
- Compiler-mediated writes only (`dossier_assemble.py`, op_id recomputed deterministically); no hand-edits.

## Open items for the conductor (proposed, not adjudicated)

1. **01700 quarantine** — 6-way merge, licensing-aggregation not single-inherit. Honest-gap detach is the
   likely cure (per_skala → [] + disputed-key + honest-gap), but the canonical write is the conductor's
   at D6/emit, not this lane's.
2. **Canonical pin W88 (still open)** — calibration/membership pin `45bbc1f4` is a PR-head not reachable
   from main; the §4 emit-time fencing re-check will fail on it. Content is stable (blob 3cfe8134d);
   recommend re-pin to a main-reachable commit before any canonical emit.
3. **D5 family** — D5 ran Sonnet (matches pilot/calibration baseline). If Batch A wants a different-family
   refuter (plan seat table), that's a conductor tightening applied before D6; GLM unprobed, DeepSeek
   BALANCE_DEAD at last check.
4. Both codes' vestigial `pp28_sources` pointers (D4) — cosmetic cleanup candidate, conductor's call.

## Next

Lot 02 = division 02 (`02201`, `02402`, `02409`). Same D0→D5+D4 pipeline; lane continues absent a
control-limit breach (calibration §5 pause/resume).
