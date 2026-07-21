---
date: 2026-07-20
domain: compliance
client_case: null
adversarial_review: kimi-k3
adversarial_review_detail: "DONE (kimi-code/k3, read-only over the gate report + canonical JSON + cure compiler + raw workflow result JSON + evidence root, cross-family substitute seat — Codex quota-exhausted until 2026-08-19, GLM keychain-unavailable in this background session). Verdict: CONFIRMED-WITH-NOTES — no cure/no-cure disposition refuted. 1 MEDIUM finding actioned in this SECOND SIGNING (F1: status_mapping mislabel on 3 codes, curable with existing tooling) + 1 MEDIUM reframing accepted (F2: 93193 has zero fully-sound tiers, not one) + 2 LOW precision notes (F3 mechanism wording, F4 a listing omission in §2.3) + 1 informational NOTE (F5)."
sources:
  - PP 28/2025 Lampiran corpus (peraturan.bpk.go.id, download ids 394930-394950)
  - BPS Tabel Konversi KBLI 2020-2025 Volume 2 (Lampiran 5 + 10)
  - data/source_documents/KBLI_2025_FINAL_CLEAN.json (canonical, sha256 dcda285b00e129ba905ae4b9d958663f1e5132bb708d6d72d878591320401979 at gate time — Lot 9's own 12 codes independently content-verified byte-identical to the D0 evidence snapshot pulled at the older sha 873f8fb4f9b5…, per W88 discipline: content-check, not sha-proxy)
  - infra/workflows/kbli-batch-a-lot.js (runnerBlobSha256 45e3951fb0d52f1d2c1687c12895a38cdc050a62c8486e3cbcaef967f3d4b01d, unchanged since Lot 8)
---

# GARUDA-FILIERA Batch A — Lot 9 (A-L9) conductor gate

> Members (10): 93127, 93128, 93129, 93191, 93192, 93193, 93194, 93195, 93197, 93199 — the
> remainder of the division-93 sport-facility/klub/activity split not covered by Lot 8 (which took
> 93111-93126 + the 91425 neighbor). Innocence controls (2): 46201 (division 46, wholesale grain
> trade), 96300 (division 96, funeral activities) — both chosen from divisions never touched by
> any prior Batch-A lot (see `/tmp/kbli-conductor-a1-0718/lot9-prelaunch-pins.md` §3 for the full
> exclusion-set construction).

## 0. Launch note

D0 evidence pulled cleanly in one pass (~99s, vault/PDF cache warm from Lot 8) — no incident, no
re-pull needed (contrast Lot 8's §0). Membership gate: all 10 real members independently confirmed
`in_scope: true` in `data/kbli-filiera/membership/batch-a-members.json` before launch (the file's
own `canonical_sha256` pin is separately known-stale relative to `main` HEAD post-Lot-8-cure — see
PENDING-ARMS — but that staleness affects the CENSUS TOTAL only, not the in-scope flag on codes
neither Lot 8 nor any earlier lot ever touched; verified directly). Launcher built the
byte-exact membership injection programmatically (JSON file read → JS launcher source, never
hand-transcribed — W88 discipline) and reused Lot 8's runner file unmodified
(`runnerBlobSha256` identical). Workflow `wf_8d2d246d-f8f`, 24 agent invocations (12 codes × D1+D5),
0 errors.

## 1. Outcome

Lot A-L9: **12/12 codes flagged "quarantined" by the raw runner output — but this figure is
misleading and must NOT be read at face value (see §3.3).** Of the 10 real members, ALL 10 have a
genuine, conductor-confirmed finding (not a tooling artifact) — 8 `source_absent_in_vault` (full
detach, same disease as Lot 8's majority bucket) + 2 `payload_cross_contamination` (93191↔93193, a
NEW tier-scoped variant, held un-cured — §3.2). Of the 2 innocence controls, BOTH are
**substantively clean** (D1 `needs_quarantine=false` AND D5 `problem_found=false` on both,
high-confidence bidirectional image-verified crosswalks with real cited PP28/OSS locators) — their
"quarantined" label is driven ENTIRELY by the already-known `derive_fiktif_positif.py`
tier-coverage gap (PENDING-ARMS, opened at Lot 8's gate), not a real defect. **m1 blind-concordance
0.300** (3/10 concordant among real members) **< floor 0.75**; **m2 certification rate 0.000**
outside **[0.2, 0.85]** — both breached, consistent with Lot 8's breach and now confirming this is
a property of the WHOLE division-93 sport family, not one lot's bad luck (§5, meta-pattern).

## 2. Conductor spot verification (by-eye, THIS session — direct canonical-data + PNG comparison)

Given the scale of a second consecutive 100%-flagged lot, this gate leaned on **direct canonical
JSON comparison across codes** (not just seat prose) as the primary verification tool, backed by
PNG renders for the crosswalk/PP28 claims — a stronger, more precise check than image-reading alone
for the tier-contamination finding (§2.1), because it caught something the seats' own evidence
citations got imprecise about.

### 2.1 93191 ↔ 93193 — confirmed tier-scoped symmetric contamination (the lot's sharpest finding)

D5 flagged both codes `payload_cross_contamination` but cited an IMPRECISE locator for 93191
(`pp28/394946_p186-186.png`, row 51) — I viewed that image directly: **row 51 IS 93191's own
legitimate PP28 row** (Kode KBLI 93191, Judul "Promotor Kegiatan Olahraga", Menengah
Rendah/NIB+Sertifikat Standar/Bupati-Walikota), not a contamination source. D5's cited evidence was
imprecise, but its underlying VERDICT was correct — I found the real defect by comparing the two
codes' canonical `per_skala` arrays directly, side by side:

- **93191** ("Penyelenggaraan Kegiatan Olahraga", sports-event organizing) has 2 tiers. Tier 1
  (Mikro/Kecil/Menengah/Besar) kewajiban correctly says "...Standar usaha **Promotor Kegiatan
  Olahraga**..." — 93191's own activity name, matching the PP28 row 51 I viewed. **Tier 2**
  (Kecil/Menengah/Besar) kewajiban says "...Standar usaha **Aktivitas Perburuan**..." — "Hunting
  Activities," an activity 93191 has nothing to do with.
- **93193** ("Aktivitas Perburuan di Kawasan Buru", hunting-reserve activities) ALSO has 2 tiers.
  **Tier 1** (Mikro/Kecil/Menengah/Besar) kewajiban says "...Standar usaha **Promotor Kegiatan
  Olahraga**..." — 93191's activity name, not 93193's own. Tier 2 (Kecil/Menengah/Besar) correctly
  says "...Standar usaha **Aktivitas Perburuan**..." — 93193's own activity.
- The two codes' WRONG tiers are not just "similar" — they are **verbatim byte-identical** to each
  other's corresponding CORRECT tier (confirmed via direct JSON diff, not eyeballing prose). **Kimi
  red-team refinement (F3):** the FULL two-tier `per_skala` array is byte-identical between the two
  codes (`json.dumps(sort_keys=True)` equality across every field of both tiers), not a piecemeal
  one-tier-only borrow — better described as one shared block cloned onto both codes than as two
  independent tier swaps; the bottom-line defect (each code carries exactly one foreign-activity
  tier) is unchanged. Not a foreign/unrelated-code borrow either way (contrast Lot 8's 91425←91025,
  which pulled from a wholly different, non-member 2020 activity) — 93191/93193 are both this lot's
  own members. Both codes' `pp28_sources` are correctly self-referential (`["93191"]`,
  `["93193"]`) — that field is fine; only the CONTENT leaked across the boundary. The
  "extraction-time row-adjacency" mechanism (rows 51/52 physically adjacent) is speculation the
  red-team could not confirm — 93193 has no PP28 row anywhere in the vault (see below), so the
  actual extraction path stays an open question.
- **CORRECTED by the Kimi red-team (F2) — the claim below originally overclaimed both tiers as
  sound:** only **93191's Tier 1** is actually source-verified (PP28 row 51, image-confirmed
  field-for-field — §2.1 below). **93193 has NO PP28 row anywhere in the 21-file vault**
  (`pp28/ABSENT.json`, 11,208 pages scanned) and no OSS endpoints either. So while 93193's Tier 2
  correctly NAMES its own activity ("Aktivitas Perburuan", corroborated by the crosswalk MERGE from
  91037 "Kawasan Buru"), that tier's licensing VALUES have no citable locator at all — the same
  `source_absent_in_vault` disease as the 8 detached codes below. The crosswalk corroborates the
  code's existence/title, not its tier content's provenance. **Net: 93191 has exactly 1 genuinely
  sound tier; 93193 has 0.** When the tier-scoped primitive below eventually lands, 93193's likely
  end-state is full detach (both tiers unconfirmable), not a partial cure — this gate holds it
  un-cured today for the SAME reason as 93191 (no selector exists to act at tier granularity), not
  because its untouched tier is known-good. Whole-array detach today would still destroy 93191's
  one genuinely-sound tier — exactly the disease Lot 8's PENDING-ARMS entry (§3.4/§5.1b, code
  93114) already flagged as un-curable with today's tooling ("no per-entry tier/index/skala_usaha
  selector exists"). **This is the SECOND confirmed instance of that exact gap** — strengthens the
  case for building the tier-scoped detach primitive before Batch-B, not after.

### 2.2 93192 / 93197 — genuine SPLIT, generic boilerplate, no foreign-activity contamination

Crosswalk (both D1 and D5, image-verified `lampiran10_p242-242.png` + `p438/p439-439.png`): 2020
code 93192 "Olahragawan, Juri dan Wasit Profesional" genuinely SPLITS into 93192(2025) "Aktivitas
Juri dan Wasit Profesional" (judges/referees) AND 93197(2025) "Aktivitas Olaharagawan/Atlet
Independen" (independent athletes) — both directions (forward p.242, reverse p.438/439) show the
same 2020 source feeding both 2025 targets, no ambiguity. Canonical: 93197's `pp28_sources=["93192"]`
correctly cites its split-parent (not self-referential — honest about the split), `status_mapping =
CODICE_RINUMERATO`. Both codes' `per_skala` is a SINGLE generic tier (Rendah/NIB/"submit periodic
activity reports" only) — bland but NOT wrong in the sense of naming a foreign activity; a
plausible shared low-risk regime for two similarly low-touch activities. Both `pp28/ABSENT.json`
(vault hunt absent) AND `oss/ABSENT.json` (OSS endpoints also absent) — no citable primary source
for either, genuinely unconfirmable. **Disposition: genuine `source_absent_in_vault`, standard full
detach** — the split itself is sound, only the licensing payload lacks any locator.

### 2.3 The remaining 6 simple ONE_TO_ONE/MERGE codes (93127, 93128, 93129, 93194, 93195, 93199)

Each spot-checked directly against canonical `per_skala` kewajiban text: all generic boilerplate
("submit periodic reports" / standard tourism-business-certificate language), self-referential
`pp28_sources`, **zero foreign activity-name mentions** — no hidden tier-swap like §2.1. Each has
an exhaustive `pp28/ABSENT.json` (21/21 files, 11,208 pages). 93127 additionally carries the
program-wide `_source_relabeled` annotation (2026-06-27, "PP28_2024->PP28_2025, label-only... no
content change") that D1 read as reconciling the PP28 absence — but D5's `exposed_facts_inventory`
correctly shows `kategori_risiko`/`jangka_waktu`/`fiktif_positif` all `status: absent` with **no
citable locator anywhere in this dossier**, i.e. the relabel note reconciles the LABEL only, not
the actual per-tier risk-value provenance. **Conductor tie-break sides with D5 on all 6 divergent
codes in this bucket** (93127, 93128, 93129, 93195, **93197**, 93199 — corrected list, a code was
dropped from this parenthetical in the FIRST SIGNING, caught by the Kimi red-team F4 — the count
"6" was always right, the naming wasn't; D1's occasional leniency on seeing the `_source_relabeled`
note is a miscalibration, not a real reconciliation — see §6). 93199's MERGE
source 51106 "Angkutan Udara untuk Olahraga" (air transport for sports) was checked for a
Lot-8-91425-style foreign-code borrow: NOT found — 93199's kewajiban is the same generic
boilerplate as its siblings, no transport-specific content leaked in. **Disposition: genuine
`source_absent_in_vault`, standard full detach**, same bucket as §2.2.

### 2.4 Innocence controls — genuinely clean, "quarantined" label is a tooling artifact only

**46201** (wholesale grain trade): D1 `needs_quarantine=false`, D5 `problem_found=false`. Crosswalk
bidirectionally image-verified (`lampiran5_p176-176.png` printed p.162 forward, `lampiran10_p370-370.png`
printed p.356 reverse) — clean ONE_TO_ONE, digit-for-digit read off the PNG pixels. PP28 licensing
source image-verified (`pp28/394943_p309-309.png`, row 283, Kode KBLI 46201) — risk/jangka-waktu/
scope ALL `status: verified` with exact page+row locators, matching canonical verbatim. Only
`fiktif_positif` (4 tiers) shows `status: absent` — the known formula-coverage gap (Rendah tier).
**96300** (funeral activities): D1 `needs_quarantine=false`, D5 `problem_found=false`. Crosswalk
image-verified both directions (p.244/p.441), correctly ONE_TO_ONE with an explicit contrast check
against neighboring rows that DO split/merge (96111, 95230/95240/etc.) to rule out a missed
split/merge. `pp28_sources=[]` + `pp28/NOT_APPLICABLE.json` correctly documents no PP28 layer
applies; licensing sourced from `oss/ruang_lingkup.json` directly (risk/scope `verified` with exact
OSS record locators). Only `jangka_waktu`/`fiktif_positif`/`derived_license` show `absent` — again
the same known gap, now on an OSS-native (not even PP28-adjacent) code, confirming the gap is
**generic to `derive_fiktif_positif.py`'s Rendah-tier coverage, not specific to division 93 or to
PP28-sourced codes at all**. **Both controls pass the pipeline's real sanity check — nothing here
is a Lot 9 finding, and neither should be cured.**

## 3. Adjudications

### 3.1 Genuine `source_absent_in_vault` — full detach (8 codes)

**93127, 93128, 93129, 93192, 93194, 93195, 93197, 93199**. Each: clean/plausible crosswalk (own-code
or honestly-cited split-parent), self-consistent generic boilerplate licensing content with no
foreign-activity contamination, but an exhaustive PP28 vault hunt (21/21 files) plus (where
independently probed by D5) OSS endpoints both come up absent — no citable primary source for the
asserted risk tier/timeframe/authority. Same disease class as Lot 8's 6-code majority bucket
(93113/93115/93122/93123/93125/93126). **Cure: detach `per_skala`, preserve under the disputed key,
honest `whatYouNeed`** — identical mechanism to Lots 5-8. **Plus (added at SECOND SIGNING, Kimi
red-team F1): 93199 also gets a `status_mapping_correction`** — see §3.4.

### 3.2 Genuine `payload_cross_contamination` — tier-scoped, HELD un-cured (2 codes)

**93191, 93193** (§2.1). Confirmed by direct canonical-JSON comparison: each code's one WRONG tier
is verbatim identical to the OTHER code's corresponding correct tier, each explicitly naming the
wrong code's own activity. **Corrected at SECOND SIGNING (Kimi red-team F2 — see the boxed
correction in §2.1): only 93191's Tier 1 is actually genuinely sound; 93193 has zero
source-verified tiers** (its "own-activity-named" Tier 2 has no citable PP28/OSS locator either).
**Not cured this lot regardless** — `cure_canonical_collisions.py` can only detach a code's ENTIRE
`per_skala` array, no per-tier selector exists yet (Lot 8 PENDING-ARMS §3.4/§5.1b already flagged
this gap on code 93114; this is the gap's second, sharper confirmed instance). Forcing a
whole-array detach today would destroy 93191's one genuinely-sound tier — real data left untouched
rather than destroyed, per program discipline. **Logged as a PENDING-ARMS strengthening, not a new
line** (§6). **Both codes DO get a `status_mapping_correction` this signing** (§3.4) — that field is
independently curable with existing tooling and doesn't touch `per_skala`.

### 3.4 NEW at SECOND SIGNING — `status_mapping` mislabel, 3 codes (Kimi red-team F1)

**93191, 93193, 93199** are each genuine 2-parent crosswalk merges (93191 ← 93191 + 82302 "Jasa
Penyelenggara Event Khusus"; 93193 ← 93193 + 91037 "Kawasan Buru"; 93199 ← 93199 + 51106 "Angkutan
Udara untuk Olahraga" — all three already cited in §2.1/§2.3 above for other reasons, the label
conflict itself was missed in the FIRST SIGNING) but all three carry `status_mapping:
MATCH_LANGSUNG`, the label for a clean 1:1 match. This contradicts the program's own established
convention: the 47771/46100 metadata-fix precedent (PENDING-ARMS line 344) and same-table siblings
93210/93291/93294/93299 (which genuinely ARE `MATCH_CON_AGGREGAZIONE` in canonical) both establish
that a multi-parent merge gets `MATCH_CON_AGGREGAZIONE`, with parents recorded in `_data_note`.
**Cure: `status_mapping_correction: "MATCH_CON_AGGREGAZIONE"` for all three** — curable with the
EXISTING compiler action (no new tooling needed, unlike §3.2's tier problem). For 93199 this rides
along with its full per_skala detach (§3.1). For 93191/93193 this is applied via `action:
"metadata_only"` (per_skala stays untouched, matching Lot 8's precedent for codes that need a
metadata fix without a detach).

### 3.3 Innocence controls — NOT cured, "quarantined" label explicitly overridden by conductor

**46201, 96300** (§2.4). Both are substantively clean per D1 AND D5 independently. The raw runner
verdict of "quarantined" for both is driven exclusively by `facts_inventory_failed=true` (the
`derive_fiktif_positif.py` Rendah-tier formula-coverage gap — PENDING-ARMS, Lot 8). **Conductor
ruling: these do not represent a Lot 9 finding and are excluded from the cure spec and from the
"12/12 quarantined" headline's substantive reading** — the substantive count for this lot is **10
real findings among 10 real members (100%), 0 false alarms among 2 controls**, not "12/12."

## 4. Meta-pattern (the malattia-delle-malattie)

**The entire KBLI division 93 (sport facilities and activities) — all 23 codes now covered across
Lots 8 and 9 — has a systematically unconfirmable PP28-vintage per_skala.** Lot 8: 13/13 real
members quarantined (100%), m1=0.615, m2=0.000. Lot 9: 10/10 real members quarantined (100%),
m1=0.300, m2=0.000. Two consecutive lots, same division, same headline outcome — this is not one
lot's bad luck, it is a property of how division 93's data was populated at some point upstream
(most codes carry a `_source_relabeled` annotation dated 2026-06-27 claiming OSS-RBA-2025
provenance, but the underlying risk/timeframe VALUES have no citable locator in either the PP28
vault or the OSS risk endpoints for the majority of codes checked). **Recommendation for Batch-B
planning**: treat "whole KBLI division has no verifiable per-code PP28 backing" as a first-class
lot-sizing signal — a future division showing this pattern on its first few codes should be
suspected wholesale rather than adjudicated code-by-code from scratch.

Second, smaller meta-note: this lot is the **second consecutive occurrence** of the
`derive_fiktif_positif.py` Rendah/Menengah-Rendah tier-coverage gap hitting codes that are
otherwise completely clean (Lot 8's 93111/93112/93119; Lot 9's both innocence controls PLUS most
real members) — this gap is not a division-93 quirk either, it hits an OSS-native code from
division 96 just as readily. It is the dominant SOURCE of "false-quarantine noise" across both
lots and deserves fixing before Batch-B for exactly that reason (PENDING-ARMS, opened Lot 8, still
open).

## 5. Open before the Lot 9 cure ships

- **Tier-scoped detach primitive** (§3.2): 93191/93193 held un-cured pending the compiler
  enhancement already flagged in PENDING-ARMS from Lot 8 (§3.4/§5.1b). This lot's finding is
  additional evidence strengthening that line's priority, not a new open item.
- **`derive_fiktif_positif.py` tier-coverage gap** (§4): already open in PENDING-ARMS from Lot 8;
  this lot's both innocence controls + several real members reconfirm it, no new line needed.
- **D1's occasional leniency on `_source_relabeled`-annotated codes** (§2.3): a real, if minor,
  calibration note about the D1 seat's own prompt/rubric — worth a prompt tweak before Batch-B so
  D1 doesn't accept a label-only reconciliation note as resolving a content-provenance gap. Filed
  as a fresh PENDING-ARMS line (§6), since it's a new, distinct observation not covered by an
  existing entry.
- **Adversarial review**: NOT yet run (this is FIRST SIGNING). Kimi K3 next (Codex quota-exhausted
  until 2026-08-19; GLM keychain-unavailable in this background session — same cascade as Lot 8).

## 6. New PENDING-ARMS candidate (to file alongside the cure PR)

D1's extraction rubric treats a `_source_relabeled` annotation (present program-wide, dated
2026-06-27, "label-only... no content change") as sufficient grounds to call
`needs_quarantine=false`, even when the annotation only reconciles the SOURCE LABEL
(PP28_2024→PP28_2025) and says nothing about whether the actual risk/timeframe VALUES have a
citable locator. On 6 of this lot's 8 genuine `source_absent_in_vault` codes, D1 read this
annotation as a clean bill of health while D5 (checking the `exposed_facts_inventory` locator
fields directly) correctly found no citable source for the same values — a real, repeatable D1
miscalibration, not caught by Lot 8 because Lot 8's own 6-code `source_absent_in_vault` bucket
happened not to carry this specific annotation. Needs: a small D1 prompt/schema clarification (the
annotation reconciles a LABEL, never substitutes for a locator) before Batch-B, where this
annotation is expected to recur widely (`_source_relabeled` appears to be a program-wide 2026-06-27
backfill, not division-93-specific — spot-checked on both innocence controls too).

## 7. Artifact manifest

- Evidence root: `/tmp/kbli-conductor-a1-0718/evid-lot9/` (12 code dossiers, dossier_pull.py,
  ~99s wall time, warm vault cache).
- Workflow run: `wf_8d2d246d-f8f`, 24 agent invocations, 0 errors, 195 tool calls,
  ~2.5M subagent tokens. Full journal: `.../subagents/workflows/wf_8d2d246d-f8f/journal.jsonl`.
  Full structured result: `/private/tmp/claude-501/-Users-nuzantara-nuzantara/680a67f6-91b1-43d6-af44-292ef7788f04/tasks/wxrn3oiey.output`.
- Launcher: `/tmp/kbli-conductor-a1-0718/lot9-launcher.js` (built programmatically from
  `data/kbli-filiera/membership/batch-a-members.json`, never hand-transcribed).
- Runner (reused unmodified from Lot 8): `/tmp/kbli-conductor-a1-0718/lot8-runner.js`,
  sha256 `45e3951fb0d52f1d2c1687c12895a38cdc050a62c8486e3cbcaef967f3d4b01d`.
- Canonical pin at gate time: sha256 `dcda285b00e129ba905ae4b9d958663f1e5132bb708d6d72d878591320401979`
  (post-Lot-8-cure, pre-Lot-9-cure); Lot 9's own 12 codes independently content-verified
  byte-identical against the D0 evidence snapshot (W88 discipline — content check, not sha proxy).

## Adversarial review — VERDICT AND CURES

Seat: **kimi-k3** (Moonshot Kimi K3, `kimi -m kimi-code/k3`), read-only over this gate report + the
canonical dataset + the raw workflow result JSON (parsed directly, not just report prose) + the
cure compiler source + 5 evidence PNGs viewed directly (`93191/pp28/394946_p186-186.png`,
`93192`/`93197`/`93193`'s crosswalk pages). Full transcript:
`/tmp/kbli-conductor-a1-0718/kimi-redteam-lot9-output.log` (1283 lines). Overall verdict:
**CONFIRMED-WITH-NOTES** — every load-bearing claim independently re-derived from primary evidence
held; no cure/no-cure disposition was refuted.

| # | Severity | Finding | Cure in this signing |
|---|----------|---------|----------------------|
| F1 | MEDIUM | `status_mapping=MATCH_LANGSUNG` on 93191/93193/93199 contradicts the program's own 2-parent-merge convention (PENDING-ARMS line 344 precedent + same-table siblings 93210/93291/93294/93299, which correctly use `MATCH_CON_AGGREGAZIONE`) | New §3.4 added; 3 `status_mapping_correction` entries in the cure spec (93199 rides its full detach, 93191/93193 via `metadata_only`) |
| F2 | MEDIUM | §2.1/§3.2 originally claimed BOTH codes' untouched tier was "genuinely sound" — wrong: 93193 has NO PP28 row anywhere in the vault, so its own-activity-named Tier 2 has no citable locator either | §2.1 and §3.2 corrected: 93191 has 1 sound tier, 93193 has 0; disposition (hold both un-cured) unchanged, reasoning corrected |
| F3 | LOW | Mechanism description overstated ("piecemeal tier borrow" + "rows 51/52 adjacency" speculation) vs. the more precise "whole per_skala block cloned onto both codes," and the adjacency explanation is unconfirmable since 93193 has no PP28 row at all | §2.1 wording corrected, adjacency explanation now flagged as open, not settled |
| F4 | LOW | §2.3 named only 5 of the 6 "divergent, source_absent_in_vault" codes in a parenthetical (93197 dropped from the list although the count "6" was already correct) | §2.3 list corrected to include 93197 |
| F5 | NOTE | PP28 row 51's Judul "Promotor Kegiatan Olahraga" vs. canonical's "Penyelenggaraan Kegiatan Olahraga" is the crosswalk-documented 2020→2025 rename, not a legitimacy problem | No action needed, noted for completeness |

What Kimi could NOT verify (declared, not silently skipped): the runner's own sha pin and the 24
D1/D5 seat journals (verdicts were taken from the parsed structured result JSON, not report prose);
the crosswalk/PP28/OSS PNGs for the 6 simple codes + both controls were not re-viewed pixel-by-pixel
(their verdicts rest on canonical-content checks + ABSENT.json files + the facts-inventory
locators the raw D1/D5 records already cite); whether `MATCH_LANGSUNG` on a 2-parent merge is
*always* wrong program-wide rests on precedent + sibling labels, not a written labeling spec (no
schema doc defining the enum was found).

## Sign-off

**SECOND SIGNING — conductor gate complete, cure scope determined (§3), adversarial review COMPLETE
(Kimi K3 cross-family substitute, adversarial review section above). Ready to cure.** Cure scope:
**8 full-detach codes** (93127, 93128, 93129, 93192, 93194, 93195, 93197, 93199, one of which —
93199 — also carries a `status_mapping_correction`) **+ 2 metadata-only corrections, no detach**
(93191, 93193 — `status_mapping_correction` only, per_skala left untouched pending the tier-scoped
primitive) **+ 2 controls informational only** (46201, 96300 — genuinely clean, not Batch-A
members, no spec entry). The red-team pass found 2 MEDIUM (1 actioned — F1 — + 1 reasoning
correction — F2 — both cured in THIS signing) + 2 LOW (both corrected) + 1 NOTE, and refuted NONE
of the 12 dispositions. Next: cure spec, compiler run, registry tests, gate PR, cure PR,
data-apply PR, surfaces, Appendix A screen.
