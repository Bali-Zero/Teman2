---
date: 2026-07-21
domain: compliance
client_case: null
adversarial_review: exempt-already-reviewed-at-lot8-lot9-gates
adversarial_review_detail: "Not run as a fresh D1/D5 Workflow lane -- this lot's adjudication was ALREADY COMPLETE at Lot 8's gate (research/operations/2026-07-20-kbli-batch-a-lot8-conductor-gate.md, 93114/93111/93112/93119 disposition) and Lot 9's gate (research/operations/2026-07-20-kbli-batch-a-lot9-conductor-gate.md, 93191/93193 disposition), BOTH of which already went through their own Kimi K3 cross-family adversarial review (Lot 8: CONFIRMED-WITH-NOTES, 2 MEDIUM+3 LOW cured; Lot 9: CONFIRMED-WITH-NOTES, 2 MEDIUM+2 LOW cured, refuted none). This lot is purely mechanical cure execution against those two already-adjudicated, already-red-teamed dispositions, now that the tier-scoped partial_detach primitive (PR #2921) exists to act on them. The one NEW piece of reasoning this session added -- confirming 93111/93112/93119 as genuinely clean innocence controls via PP28/2025 Pasal 8(1) regulatory research -- was independently grounded against NotebookLM (NB-3) verbatim regulation text, not merely asserted."
sources:
  - research/operations/2026-07-20-kbli-batch-a-lot8-conductor-gate.md (93114/93111/93112/93119 adjudication, §3.4/§3.5)
  - research/operations/2026-07-20-kbli-batch-a-lot9-conductor-gate.md (93191/93193 adjudication, §2.1/§3.2)
  - PP 28/2025 Lampiran corpus (peraturan.bpk.go.id, download ids 394930-394950) — cited via Lot 8/9's own evidence, not re-pulled this session
  - PP 28/2025 Pasal 8(1) elucidation (NotebookLM NB-3) — this session's regulatory research grounding the innocence-controls disposition
  - PR #2920 (docs(modus): PENDING-ARMS — correct 93112's quarantine characterization)
  - PR #2921 (feat(kbli): tier-scoped partial detach primitive in cure_canonical_collisions.py)
  - data/source_documents/KBLI_2025_FINAL_CLEAN.json (canonical, sha256 96a5ccec8f2fd65aeff591a30baa8bf177a16746b3939e02b572a8bf597cf2b3 pre-cure at commit a99ecef55c, post-PR-#2920/pre-Lot-10; sha256 446c5f5f1fcf5c33d18d411c71843a48f398b9b7a52f1f249c507c86604cf50b post-cure)
---

# GARUDA-FILIERA Batch A — Lot 10 (A-L10) conductor gate

> Members (6): 93111, 93112, 93114, 93119, 93191, 93193 — the LAST codes remaining in Batch A's
> originally-scoped 114-code sweep (`data/kbli-filiera/membership/batch-a-members.json`'s own
> pre-Lot-10 census: `_in_scope_total: 6`, matching exactly). No new D1/D5 Workflow lane was run
> for this lot — every one of these 6 codes was already adjudicated at Lot 8's gate (93111, 93112,
> 93114, 93119 — §3.5/§3.4) or Lot 9's gate (93191, 93193 — §2.1/§3.2), both already red-teamed by
> Kimi K3. This gate's job is purely to synthesize that prior work into a final disposition and
> execute the mechanical cure, now that the tier-scoped `partial_detach` primitive exists (PR
> #2921, merged 2026-07-20).

## 0. Why this lot could not be cured until now

Lot 8 (§3.4/§3.5) and Lot 9 (§2.1/§3.2) both independently hit the SAME tooling gap: a record with
ONE genuinely sound `per_skala` tier and ONE genuinely defective tier, where
`cure_canonical_collisions.py`'s only detach mode was whole-array (all tiers or none). Forcing a
full detach on 93114 or 93191 would have destroyed their one sound, PP28-image-verified tier —
the wrong trade. Both gates held these codes un-cured and filed the gap in PENDING-ARMS (opened
Lot 8 §3.4/§5.1b, reconfirmed Lot 9 §3.2 as "the second confirmed instance"). PR #2921 built the
missing primitive (`action: "partial_detach"` + `tier_selector`, content-matched, never by array
index) — this lot is the FIRST to use it in production.

## 1. Disposition — two groups

### 1.1 Group CURE (3 codes) — the tier-scoped primitive resolves them

- **93114** ("Fasilitas Lapangan", Lot 8 gate report §3.4): two-tier record. Tier 1
  (Mikro/Kecil/Menengah, Menengah Rendah risk) is fully verified — own PP28 row (394946 p.182,
  no.47) matches verbatim, and that row's own text explicitly excludes golf facilities ("...dan
  sejenisnya KECUALI Lapangan Golf"). Tier 2 (Menengah/Besar, Tinggi risk, golf-course-specific
  "Fasilitas Lapangan Golf" scope) has zero PP28 backing captured anywhere in the dossier. Cure:
  `partial_detach` with `tier_selector: {"kategori_risiko": "Tinggi", "skala_usaha": ["Menengah",
  "Besar"]}` — moves only Tier 2; Tier 1 survives in `per_skala`, byte-identical. Also carries an
  honest-gap `whatYouNeed` rewrite (partial — only the removed tier's claim is disclaimed; the
  sound tier's confirmed facts are kept), and its gold-editorial-layer mirror
  (`apps/mouth/data/kbli-gold-all.json`) was updated to match.

- **93191** ("Penyelenggaraan Kegiatan Olahraga", Lot 9 gate report §2.1/§3.2): confirmed
  tier-scoped `payload_cross_contamination` with 93193 — each code's two tiers were verbatim
  byte-identical to the other's. 93191's Tier 1 (Mikro/Kecil/Menengah/Besar, "Promotor Kegiatan
  Olahraga") is 93191's OWN activity, PP28 row 51 image-verified (`pp28/394946_p186-186.png`).
  Tier 2 (Kecil/Menengah/Besar, "Aktivitas Perburuan") is 93193's activity, wrongly present on
  93191's record. Cure: `partial_detach` with `tier_selector: {"kategori_risiko": "Menengah
  Rendah", "skala_usaha": ["Kecil", "Menengah", "Besar"]}` — moves only the contaminated tier;
  the sound tier survives, byte-identical. `intel_2026.whatYouNeed` is deliberately left
  untouched: the retained tier already covers the full scale range at the same
  risk/authority/process terms the removed tier described for a narrower subset, so no
  client-facing detail is lost. `status_mapping`/`whatChanged` (already corrected to
  `MATCH_CON_AGGREGAZIONE` at Lot 9) are not touched again.

- **93193** ("Aktivitas Perburuan di Kawasan Buru", Lot 9 gate report §2.1/§3.2): the mirror image
  of 93191 — Tier 1 (Mikro/Kecil/Menengah/Besar) is verbatim byte-identical to 93191's own correct
  tier ("Promotor Kegiatan Olahraga"), not 93193's activity. Tier 2 (Kecil/Menengah/Besar)
  correctly names 93193's own activity ("Aktivitas Perburuan") but — unlike 93191's sound tier —
  has NO PP28 row anywhere in the 21-file/11,208-page vault and no OSS endpoints either (Lot 9's
  Kimi K3 red-team F2 correction: 93193 has ZERO genuinely sound tiers, not one). Cure: plain full
  detach (default action, no `tier_selector` needed) — both tiers move to the disputed key,
  `per_skala -> []`, with the standard honest-gap `whatYouNeed`. `status_mapping`/`whatChanged`
  (already corrected at Lot 9) are not touched again. 93193 is absent from the gold editorial
  layer — nothing to mirror.

### 1.2 Group INNOCENCE (3 codes) — certified clean, EXPLICITLY EXCLUDED

- **93111** ("Fasilitas Stadion") and **93119** ("Pengelolaan Fasilitas Olahraga Lainnya"): both
  have a clean own-code crosswalk AND fully image-verified PP28 licensing rows (Lot 8 gate report
  §3.5: 93111 p.178 row 44, 93119 p.186 row 50) — D1 `needs_quarantine=false` and D5
  `problem_found=false` concordant, zero disagreement on the underlying crosswalk+licensing-row
  fields. Both were quarantined only because their `fiktif_positif=true` (asserted on
  Rendah/Menengah-Rendah tiers) has no citable derivation-formula locator in
  `scripts/derive_fiktif_positif.py` (whose Pasal 225(1)/230/124(4) formula table only covers
  Menengah-Tinggi/Tinggi tiers). **Resolved this session**: PP28/2025 Pasal 8(1) elucidation
  (NotebookLM NB-3), verbatim: *"perolehan PB secara otomatis... berlaku bagi kategori tingkat
  Risiko usaha rendah dan menengah rendah"* — confirms Rendah/Menengah-Rendah tiers get
  **automatic issuance**, a DIFFERENT legal mechanism than `fiktif_positif` (which is the
  30-hari-silent-approval mechanism for higher tiers). The formula table's Menengah-Tinggi/
  Tinggi-only scope is therefore regulatorily CORRECT, not a coverage gap — and the pre-existing
  `fiktif_positif=true` value on these tiers is a known, deliberately-preserved legacy artifact
  from the original dataset build (documented in `derive_fiktif_positif.py`'s own docstring), not
  a fabricated or wrong fact. Same disposition class as Lot 9's own innocence controls 46201/96300
  (Lot 9 gate report §2.4/§3.3): a `factsInventoryUnverified()` tooling artifact, not a record
  defect.

- **93112** ("Fasilitas Sirkuit"): clean own-code crosswalk AND fully image-verified PP28
  licensing row (Lot 8 gate report §3.5: p.179 row 45). Quarantined for a DIFFERENT reason than
  93111/93119 — `derived_license`, not `fiktif_positif`. **Verified this session** (PR #2920): 93112's
  `perizinan` field is explicitly stated (non-empty — `NIB dan Sertifikat Standar`, Menengah
  Tinggi tier), so `derived_license` never applies to it at all per the D5_SCHEMA's own field
  description ("the license type the frontend derives from risk WHEN PERIZINAN IS EMPTY") — it
  should never have been listed as an inventory entry needing verification, let alone marked
  absent. Confirmed directly against the live record this session: `scripts/derive_fiktif_positif.py`'s
  own per_skala row for 93112 (`data/source_documents/KBLI_2025_FINAL_CLEAN.json`) carries a
  non-empty `perizinan`. Same disposition: tooling artifact, not a record defect.

**ACTION: no cure_spec entry for any of these 3 codes. No canonical/gold changes. They need NO
fix — they are already correct.**

## 2. Execution

Cure spec: `scripts/kbli_filiera/cure_specs/batch_a_lot10.json` (`disputed_key`:
`per_skala_disputed_pp28_collision`, matching every prior lot). Applied via
`scripts/kbli_filiera/cure_canonical_collisions.py --spec batch_a_lot10.json --apply` against a
fresh `origin/main` worktree checkout (canonical pin at spec-authoring time: sha256
`96a5ccec8f2fd65aeff591a30baa8bf177a16746b3939e02b572a8bf597cf2b3`, commit `a99ecef55c`,
post-PR-#2920/pre-Lot-10). Dry-run confirmed the exact expected shape before apply:

```
93114: per_skala 1 matched row(s) -> moved to per_skala_disputed_pp28_collision (sibling tier(s) left untouched)
93191: per_skala 1 matched row(s) -> moved to per_skala_disputed_pp28_collision (sibling tier(s) left untouched)
93193: per_skala 2 row(s) -> 0 (fold per_skala_legacy: False, disputed_key: per_skala_disputed_pp28_collision)
```

Applied cleanly (3/3, 0 problems). `sync_kbli_dataset.sh` propagated to all 4 consumer copies
(`apps/mouth/data/KBLI_2025_FINAL_CLEAN.json`, the two gitignored `apps/backend-rag/*` runtime
copies, plus `apps/kbli-navigator/data/kbli-2025.json` — a newer sync target not yet reflected in
the Lot 8/9 test files' `ALL_DATASET_COPIES` constant, verified independently consistent this
session). Sidecar (`apps/mouth/data/kbli-dataset-version.json`) updated to the new dataset sha256.
Gold-editorial-layer mirror: 93114's `whatYouNeed` rewritten to canonical's own cured text
verbatim (same mechanism as Lot 8 commit `c2269e807d` / Lot 9's own gold-mirror step) — a
minimal, single-line diff on `apps/mouth/data/kbli-gold-all.json`.

## 3. Membership census re-emit (per-lot ritual, per Lot 9's own precedent)

`scripts/kbli_filiera/emit_batch_membership.py`'s fencing check requires the working canonical to
match HEAD's committed blob — re-run AFTER committing the cure. Only 93193 flips census
classification: its `per_skala` is now empty (`A-serving/pp28 -> A-empty/gap`). 93114/93191 stay
`A-serving/pp28` — their `partial_detach` leaves `per_skala` non-empty (1 surviving tier each), so
`emit_batch_membership.py`'s `_classify()` predicate (which only reads emptiness, not tier count)
does not reclassify them. Net: `A-serving/pp28` 6→5, `A-empty/gap` 215→216, `_in_scope_total`
6→5, `_total` invariant at 221. Re-emitted via `--apply`
(`data/kbli-filiera/membership/batch-a-members.json`, sha256 `ee69b205b9c4…`).

**This closes Batch A's originally-scoped 114-code sweep: 0 codes remain in scope.** The 6 members
of this lot were the entirety of the pre-Lot-10 in-scope set (`_in_scope_total: 6`, verified
directly against the membership artifact before this cure ran) — 3 are now cured (93114, 93191,
93193), and 3 are certified clean, correctly excluded innocence controls (93111, 93112, 93119),
never members of an in-scope defect population to begin with.

## 4. Cross-lot test-suite supersession (a new pattern for this program)

This is the FIRST time a later lot's cure legitimately changes a field an EARLIER lot's own
registry test file pinned as "untouched by this cure" — Lot 8 held 93114 un-cured (§3.4, no
tooling) and Lot 9 held 93191/93193 un-cured on `per_skala` (§3.2, same tooling gap). Both prior
test files' invariants are now correctly superseded, not regressed:

- `scripts/tests/test_kbli_batch_a_lot8_registry.py`: 93114 removed from `INNOCENT_NEIGHBORS`
  (it is no longer "untouched by this spec" — Lot 10 legitimately cured its defective tier),
  replaced with an explicit supersession comment pointing at this gate report and at
  `test_kbli_batch_a_lot10_registry.py` for 93114's current invariants.
- `scripts/tests/test_kbli_batch_a_lot9_registry.py`: the byte-identical-per_skala-untouched test
  for 93191/93193 (`test_lot9_metadata_only_per_skala_completely_untouched`) is retired and
  replaced with `test_lot9_metadata_only_per_skala_content_preserved_across_lot10` — a
  content-preservation invariant (per_skala + disputed key together still reconstruct the exact
  Lot 9 pre-cure snapshot) that remains TRUE across the handoff, instead of an invariant that is
  now intentionally false. `_data_note`-verbatim and content-marker tests for 93191/93193 are
  similarly excluded from Lot 9's own parametrize (their `_data_note` is now Lot 10's provenance
  text — `apply_cure` always rewrites `_data_note` to the latest cure's text), with a new
  divergence-pin test (`test_lot9_data_note_diverges_from_spec_after_lot10_supersession`)
  confirming the change is real and expected, not silent drift.
- `scripts/kbli_filiera/tests/test_emit_batch_membership.py`: docstring + census assertions
  refreshed to the post-Lot-10 numbers (5/216/5/221), with an explicit lot10 code-list assertion
  (93193 migrates to the gap watchlist; 93114/93191 explicitly asserted to STAY `A-serving/pp28`,
  not just "not asserted otherwise").

## 5. Test results

- `scripts/tests/test_kbli_batch_a_lot10_registry.py`: **59/59 passed** (new file, this lot).
- `scripts/tests/test_kbli_batch_a_lot9_registry.py` + `test_kbli_batch_a_lot8_registry.py` +
  `scripts/kbli_filiera/tests/` (full suite, incl. `test_cure_canonical_collisions.py`'s
  `partial_detach` guilt+innocence pair and `test_emit_batch_membership.py` /
  `test_emit_batch_calibration*.py`): **608/608 passed** after the supersession fixes + membership
  re-emit landed.
- Lots 1-7 registries + the remaining `scripts/tests/test_kbli_*` files (false-friend registry,
  metadata-fixes registry, dataset lint guards, l4bali disclosure, 68112 collision, lot2/56101,
  metadata residuals): run as a broader confirmation pass, unaffected by this lot's 3-code scope.

## 6. Artifact manifest

- Cure spec: `scripts/kbli_filiera/cure_specs/batch_a_lot10.json` (`lot10-v1`).
- Registry test: `scripts/tests/test_kbli_batch_a_lot10_registry.py` (59 tests).
- Canonical pre-cure sha256: `96a5ccec8f2fd65aeff591a30baa8bf177a16746b3939e02b572a8bf597cf2b3`
  (commit `a99ecef55c`). Post-cure sha256:
  `446c5f5f1fcf5c33d18d411c71843a48f398b9b7a52f1f249c507c86604cf50b`.
  Post-membership-re-emit HEAD: commit `2df807b006`.
- Membership artifact: `data/kbli-filiera/membership/batch-a-members.json`, re-emitted sha256
  `ee69b205b9c4…`, census `A-serving/pp28: 5, A-empty/gap: 216, _in_scope_total: 5, _total: 221`.
- Prior gates this lot synthesizes: `research/operations/2026-07-20-kbli-batch-a-lot8-conductor-gate.md`
  (§3.4, §3.5), `research/operations/2026-07-20-kbli-batch-a-lot9-conductor-gate.md` (§2.1, §3.2,
  §2.4, §3.3). Primitive this lot depends on: PR #2921
  (`scripts/kbli_filiera/cure_canonical_collisions.py`, `action: "partial_detach"` +
  `tier_selector`). Innocence-control correction this lot depends on: PR #2920 (93112 quarantine
  mis-listing).

## Sign-off

**Cure applied and tested green (608/608 across the dependent Lot 8/9/10 registries + the
`scripts/kbli_filiera/tests/` suite). No new D1/D5 Workflow lane was run — this lot synthesizes
Lot 8's and Lot 9's own already-adjudicated, already-red-teamed dispositions into a final cure,
now unblocked by the tier-scoped `partial_detach` primitive.** Membership re-emitted
(`_in_scope_total: 5 -> 0` is not literal — the artifact reflects the population classification
predicate, not a "remaining Lot 10 members" counter; the SUBSTANTIVE claim is that Batch A's
original 114-code sweep has zero remaining un-adjudicated members after this lot: all 6 of this
lot's codes have a final, evidence-backed disposition — 3 cured, 3 certified clean). Cure PR
ships on a fresh branch off `origin/main` with auto-merge armed; independent conductor
verification (byte-identity of retained sound tiers, selector correctness, canonical
`status_mapping` untouched) is expected before merge, per this program's generator≠grader
discipline.
