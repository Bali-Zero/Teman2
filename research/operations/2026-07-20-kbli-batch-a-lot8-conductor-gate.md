---
date: 2026-07-20
domain: compliance
client_case: null
sources:
  - PP 28/2025 Lampiran corpus (peraturan.bpk.go.id, download ids 394930-394950)
  - BPS Tabel Konversi KBLI 2020-2025 Volume 2 (Lampiran 5 + 10)
  - data/source_documents/KBLI_2025_FINAL_CLEAN.json (canonical, sha256 03e3116a5d6bddd30d1d154842a30024396512c81b9ccfe28e0a0f813047fc02)
  - infra/workflows/kbli-batch-a-lot.js (runnerBlobSha256 45e3951fb0d52f1d2c1687c12895a38cdc050a62c8486e3cbcaef967f3d4b01d)
---

# GARUDA-FILIERA Batch A — Lot 8 (A-L8) conductor gate

> Members (13): 91425, 93111, 93112, 93113, 93114, 93115, 93119, 93121, 93122, 93123, 93124,
> 93125, 93126 (the "kawasan konservasi" neighbor 91425 + the full 931xx sport-facility/klub
> cluster). Innocence controls (2): 63101, 73100.

## 0. Incident note (evidence-loss + re-pull — load-bearing for how to read this gate)

The first Lot 8 launch (`wf_3a28b22f-e6d`) fired against an `evidenceRoot`
(`/tmp/kbli-conductor-a1-0718/evid-lot8`) that turned out to be **empty** — no per-code dossiers
existed on disk at launch time, despite an earlier D0 pass in this session having reportedly
populated it. Root cause not conclusively pinned (candidates: a `/tmp` cleanup during the
session-compaction gap, or the D0 dossier-pull agent's own completion report never having been
independently re-verified by the conductor before the expensive lane was launched — the latter is
a genuine anti-hallucination-discipline gap on the conductor's part, logged in §5.4). **What
matters for calibration: every one of the ~15 independently-dispatched D1/D5 seats in that first run
correctly fail-closed** (`needs_quarantine=true`/`problem_found=true`, `problem_category` in
{`source_absent_in_vault`, `unresolvable_source_pointer`}, empty `mappings`) rather than
fabricating a crosswalk from memory or title-similarity — a clean, unanimous proof-point for the
anti-hallucination doctrine under a genuine infra failure, not a process defect to hide. The lane
was stopped before completion, evidence was re-pulled (`dossier_pull.py --out .../evid-lot8`,
independently verified this session: log shows `PULL COMPLETE 15 of 15 codes ok`, zero
errors/tracebacks, 127 files across 15 code directories, spot-checked non-empty
`canonical.json`+`oss/`+`crosswalk/`+`pp28/` for both a member (91425) and a control (63101)), and
the lane was **relaunched fresh** (`wf_d079f983-515`, NOT `resumeFromRunId` — a resume would have
replayed the empty-evidence quarantine results from cache, since `agent()` caches by `(prompt,
opts)` and the prompt text is unchanged even though the underlying evidence files changed).

## 1. Outcome

Lot A-L8: **15/15 codes adjudicated — 0 certified, 13 quarantined (100% of real members), 0
abstained, 2 innocence controls** (both also flagged, for reasons outside this lot's cure scope —
§3.4). **Both calibration floors breached**: m1 blind-concordance **0.615** (8/13 concordant among
members) **< floor 0.75**; m2 certification rate **0.000** outside **[0.2, 0.85]**. Root-caused
below (§3, §6) as a **genuine finding about this specific activity family's provenance quality**,
not a runner/process defect — confirmed by conductor by-eye verification on primary sources
(§2), not accepted from seat prose alone (W100 discipline).

## 2. Conductor spot verification (by-eye, THIS session — three fresh renders)

1. `crosswalk/lampiran10_p241-241.png` (91425's evidence): BPS Vol.2 Lampiran 10, row **"91033 |
   Taman Hutan Raya | 91425 | Taman Hutan Raya"** — clean, unambiguous, image-verified. Same page,
   separately: **"91025 | Taman Budaya | 90310 | Aktivitas Operasional Tempat dan Fasilitas
   Kesenian"** — confirms 91025 crosswalks to 90310, NOT to 91425.
2. `pp28/394946_p497-497.png` (391425's cited PP28 source, row 8): star-seal PP28 render, row **"8.
   91025 | Taman Budaya | Seluruh | Mikro/Kecil/Menengah/Besar | Rendah | NIB | - | Otomatis |
   Menyampaikan laporan kegiatan secara berkala | - | Seluruh | Bupati/Walikota"** — matches
   canonical.json's `per_skala` payload for 91425 **verbatim, field for field**. This is the wrong
   code's row (Taman Budaya/Cultural Park, not Taman Hutan Raya/Forest Park) — **confirms
   `payload_cross_contamination`** independently of D1/D5 prose.
3. `pp28/394938_p761-761.png` (93121's + 63101's cited PP28 source — same file, both codes):
   header **"I.F.2886"**, all identity columns (No/Kode KBLI/Judul KBLI/Ruang Lingkup/Skala
   Usaha/Tingkat Risiko/Perizinan/Persyaratan/Jangka Waktu) **blank** — a continuation row from a
   merged block, only the Kewajiban column visible, reading industrial quality-control/calibration
   obligations ("...bidang perindustrian", "kalibrasi peralatan quality control") with no
   relationship to 93121 ("Klub Sepak Bola") or 63101 ("Aktivitas Pengolahan Data"). **This is the
   SAME page already flagged in the Lot 8 D0 corner note as a "hot trap page" / fuzzy-matcher
   magnet — re-confirmed on this independent, freshly re-pulled evidence set, for the SAME two
   codes.** Second sighting, now empirically reproducible across two separate pulls: this is a
   genuine, persistent defect in `dossier_pull.py`'s PP28 hunt heuristic, not evidence noise.

## 3. Adjudications

Five distinct dispositions emerge, and separating them is the point of this gate — a flat "13/13
quarantined" reading would conflate genuinely different findings.

### 3.1 Genuine `payload_cross_contamination` (1 code)

- **91425**: crosswalk 91033↔91425 is clean ONE_TO_ONE (bidirectional, image-verified — §2.1); the
  record's own `pp28_sources=["91025"]` points at a wholly different KBLI-2020 activity ("Taman
  Budaya"/Cultural Park, crosswalks to 90310) whose PP28 row (§2.2) matches the record's
  `per_skala` verbatim — the licensing payload was borrowed from a code-proximity neighbor (91025
  sits 8 digits from the true parent 91033 in the same cluster), not from 91425's actual
  predecessor. D1 and D5 concordant (`category_mismatch=true` on label only —
  `payload_cross_contamination` vs `unresolvable_source_pointer`, same underlying finding, D1's
  label is the more precise one). **Cure: detach `per_skala`, preserve under
  `per_skala_disputed_pp28_wrong_code`, honest `_data_note`.**

### 3.2 Genuine `source_absent_in_vault` — full exhaustive-scan absence (6 codes)

- **93113, 93115, 93122, 93123, 93125, 93126**: each has a clean, bidirectionally-confirmed
  ONE_TO_ONE crosswalk (own-code, unchanged title, both Lampiran 10 directions p.242/p.438) — the
  mapping layer is sound. But each code's `pp28/ABSENT.json` records an **exhaustive hunt across
  all 21 pinned lampiran files (394930-394950), 11,208 pages scanned, verdict=absent** — the PP28
  row the record's own `pp28_sources` (self-referential, same code number) claims to cite cannot
  be located anywhere in the vault. D1 initially treated this as a non-blocking provenance note in
  most of these (needs_quarantine=false, "not quarantine-worthy for the mapping"); D5 correctly
  flagged `problem_found=true`/`source_absent_in_vault` on all six — this is exactly what the
  divergence rule is for (plan §3/A4: any D1/D5 disagreement quarantines, never averaged). **Cure:
  detach `per_skala`, preserve under `per_skala_disputed_pp28_absent`, honest `_data_note` citing
  the ABSENT.json full-scan proof.**

### 3.3 Genuine wrong-pointer via the hot-trap-page (1 code)

- **93121**: crosswalk clean (own-code ONE_TO_ONE, §2.3 confirms no split/merge). The single PP28
  render captured resolves to the blank-continuation-row trap page (§2.3) — content
  (industrial-QC obligations) bears no relation to a football club's licensing profile, and
  `sektor_id` on the record (`I.J-P`) doesn't even match the trap page's lampiran letter (`I.F`).
  D1 correctly diagnosed this as a fuzzy-match false positive, not evidence of anything about
  93121. **Cure: detach `per_skala`, preserve under `per_skala_disputed_pp28_wrong_page`, note
  should record the trap-page filename explicitly so a future re-hunt against the correct sector
  lampiran (I.J-P, not I.F) isn't fooled again.**

### 3.4 Partial/mixed evidence (2 codes)

- **93114**: two-tier record. Tier 1 (Mikro/Kecil/Menengah, Menengah Rendah risk) is **fully
  verified** — own PP28 row (p.182, no.47) matches verbatim, and that row's own text explicitly
  excludes golf facilities ("...dan sejenisnya KECUALI Lapangan Golf"). Tier 2 (Menengah/Besar,
  golf-course-specific, Tinggi risk / Menteri-Kepala-Badan authority) has **zero PP28 backing
  captured** in this dossier — a real, narrower gap than 3.2 (only one tier of two is affected).
  **Verified against the actual tooling (dedicated schema-inspection pass, this session):
  `cure_canonical_collisions.py` only supports whole-`per_skala`-array detach per code — there is
  no per-tier/per-index/`skala_usaha`-scoped partial detach in the compiler today** (`plan_cure`/
  `apply_cure` key everything by `code` only; the whole array moves to the disputed key atomically
  or not at all). Forcing a whole-array detach here would destroy tier 1's genuinely sourced,
  verified data purely for lack of tooling — the wrong trade. **Disposition: NOT cured this lot,
  folded into §3.5's open item** (needs a compiler enhancement — a per-entry tier selector — before
  it can be cured correctly; holding un-cured is safer than a destructive whole-detach).
- **93124**: both tiers (Menengah Rendah + Tinggi) show `pp28/ABSENT.json` full-scan absence —
  same disposition as §3.2, just carrying two tiers instead of one, and since BOTH tiers are
  unverified a whole-array detach here is correct (no partial-tier tooling gap applies — nothing
  sound is being destroyed). **Cure: detach both tiers (whole `per_skala` array).**

### 3.5 Contract-coverage / tooling-gap quarantine, NOT a record defect (4 codes)

- **93111, 93112, 93119**: crosswalk clean (own-code ONE_TO_ONE) AND primary licensing
  (`kategori_risiko`/`jangka_waktu`/`perizinan`) is **natively PP28-sourced and image-verified by
  BOTH seats with zero disagreement** (93111: p.178 row 44; 93112: p.179 row 45; 93119: p.186 row
  50 — all own-code rows, not borrowed). D1 `needs_quarantine=false` and D5 `problem_found=false`
  on ALL THREE — the underlying crosswalk+licensing data is genuinely sound. They were quarantined
  anyway because `factsInventoryUnverified()` (the post-Lot-6 fail-closed gate,
  `infra/workflows/kbli-batch-a-lot.js:739-746`) demotes any preliminarily-"certified" verdict the
  moment D5's `exposed_facts_inventory` contains ANY non-`"verified"` entry — and for these three,
  the synthetic derived field `fiktif_positif` (93111, 93119) and `derived_license` (93112, 93119)
  came back `"absent"` because **the current derivation-formula table
  (`scripts/derive_fiktif_positif.py`, Pasal 225(1)/230/124(4)) only covers Menengah Tinggi / Tinggi
  tiers** — it has no citable formula for the Rendah / Menengah Rendah tiers these three codes
  actually carry, and `derived_license` legitimately does not apply when `perizinan` is already
  stated directly (93112's own D5 rationale: "N/A — perizinan is explicitly stated..., the
  frontend's risk→license derivation rule never triggers"). **This is a genuine contract-coverage
  gap, not a data defect — detaching `per_skala` here would destroy sourced-and-verified
  provenance.**
- **93114** joins this group for a DIFFERENT reason (§3.4): its tier 1 is equally sound, but tier
  2's real gap can't be cured in isolation because the compiler has no per-tier detach primitive —
  a tooling gap, not a derivation-formula gap, but the same disposition (hold un-cured rather than
  destroy good data).

Gate holds all four UN-cured this lot (no detach). Two distinct open items follow from this group:
does PP28 legitimately grant `fiktif_positif` at Rendah/Menengah-Rendah tiers at all, and if not,
is canonical.json's own `fiktif_positif=true` assertion on those tiers itself a separate
over-assertion defect (93111/93112/93119, §5.1)? And: does the cure compiler need a per-tier
detach primitive before 93114 (and likely other multi-tier records) can be cured correctly
(§5.1b)? Lot 9's remaining 931xx members will very likely hit the identical gaps.

## 4. Innocence controls

- **63101** (`mapping_metadata_false`, non-concordant): both seats independently derive
  63111→63101 ("Aktivitas Pengolahan Data") as the crosswalk-legitimate ONE_TO_ONE predecessor
  (Lampiran 5 p.215 + Lampiran 10 p.411, both directions) — but the record's own
  `status_mapping="MATCH_CON_AGGREGAZIONE"` and `pp28_sources=["63121","63111"]` (a 2-parent
  aggregation claim) is **not supported by the same official crosswalk page**. A genuine finding —
  but 63101 is a borrowed innocence control, not a Batch-A Lot 8 member; noted for the corner as an
  already-burned-control discovery, not cured via this lot's spec.
- **73100**: `source_absent_in_vault` verdict, but its `pp28/` evidence rests on a **partial**
  vault hunt (dossier_pull.py's own log: "2 of 21 lampiran file(s) scanned, full_scan=False" — the
  pull tool does not apply `full_scan=True` to innocence controls the way it does to real lot
  members). A negative ("absent") finding from a 2/21-file partial scan is **not reliable** the way
  the members' 21/21 exhaustive scans are — flagged as a methodology gap (§5.3), not treated as a
  genuine defect.

## 5. Open before the Lot 8 cure ships

1. **`fiktif_positif`/`derived_license` derivation-formula tier-coverage gap** (§3.5, 93111/93112/
   93119): needs a dedicated look at whether `scripts/derive_fiktif_positif.py`'s Pasal-225(1)/230
   coverage should extend to Rendah/Menengah-Rendah tiers, or whether canonical.json's own
   `fiktif_positif=true` assertion on those tiers is itself an over-assertion (a legal-accuracy
   defect distinct from crosswalk/per_skala issues — client-facing risk if PP28 doesn't actually
   grant silent-approval status at those tiers). Lot 9's remaining 10 members are the same 931xx
   family and will very likely reproduce this exact gap — recommend resolving before Lot 9's D6
   gate, not after.
2. **Cure-compiler tier-scoped detach primitive missing** (§3.4/§3.5, 93114): a dedicated
   schema-inspection pass this session (`scripts/kbli_filiera/cure_canonical_collisions.py`,
   `plan_cure`/`apply_cure`) confirmed the compiler keys everything by `code` only — a detach moves
   the WHOLE `per_skala` array atomically or not at all, with no per-entry
   tier/index/`skala_usaha` selector. 93114 has one genuinely sound tier and one genuinely absent
   tier; today's tooling cannot cure the second without destroying the first. Recommend a compiler
   enhancement (a per-entry tier selector in the cure-spec schema + a filtering step in
   `apply_cure`) before Lot 9, where multi-tier partial-gap records are likely to recur.
3. **"Hot trap page" (`394938_p761-761.png`, header `I.F.2886`) — SECOND confirmed sighting**
   (93121 this lot, 63101 control both this lot and previously) — `dossier_pull.py`'s PP28
   fuzzy-matcher needs hardening against blank-identity-column continuation rows. Standing rule
   reconfirmed: any future `pp28_sources` hit landing on this exact page/file is presumptively a
   false positive pending independent image proof.
4. **Control partial-scan methodology gap**: 63101/73100 got 8/21 and 2/21 lampiran files scanned
   respectively vs. members' 21/21 (`full_scan=True`) — negative ("absent") control findings are
   unreliable until `dossier_pull.py` either applies `full_scan=True` to controls too, or the pull
   explicitly caveats partial-scan absences as weaker evidence.
5. **Evidence-loss incident (§0)**: root cause not conclusively pinned. Recommend future lot
   launches verify `evidenceRoot` population via an independent `ls`/`find` check **immediately
   before** the expensive Workflow launch — not trusting a D0 dossier-pull agent's own completion
   report alone. This closes a real gap in this session's own anti-hallucination discipline (the
   conductor launched the first, empty-evidence run without a fresh independent check).

## 6. Meta-pattern (the malattia-delle-malattie)

Two distinct disease classes converged in one lot, and conflating them would misread the
calibration signal in both directions:

**(a) An activity-family-level source-locatability gap.** The KBLI 931xx sport-facility/klub
family (plus its 91425 neighbor) has a genuinely poor PP28 primary-source-locatability rate — most
member codes' own-code lampiran rows simply cannot be found even under an exhaustive
21-file/11,208-page scan (§3.2/3.4), distinct in kind from the collision/contamination patterns
that dominated Lots 1-7. This is a real finding about THIS specific corner of the catalog, not
evidence of a broken pipeline.

**(b) The certification contract's own increasing strictness.** The post-Lot-6 fail-closed
`factsInventoryUnverified()` gate plus the Lot-7 derived-fact refinement mean "quarantined" this
lot conflates a genuine source gap (needs a data cure) with a contract-coverage gap on a synthetic
field the derivation-formula table doesn't yet reach (needs a contract/formula refinement, not a
data cure) — §3.5's three codes. **Every future lot's calibration read must separate these before
trusting the raw certification-rate number**: a rate this low can mean "this activity family is
badly sourced" OR "the bar just got stricter than its own formula coverage" — conflating them would
either wrongly detach genuinely sound data (destroying real provenance) or wrongly wave off a
genuine gap as "just a contract issue."

**W100 corollary, fourth generation this program:** a contract designed to fail closed on real gaps
can ALSO fail closed on its OWN incompleteness — "even the gate's own strictness can misclassify
blame." (Lineage: W65 "even the refuter hallucinates" → W90 "even the ground-truth invecchia" → the
L7 report's "even the accord lies — and even the signature" → here: even a correctly-designed
fail-closed gate can conflate two causes of failure if its own formula coverage hasn't caught up
to what it demands.)

## 7. Artifact manifest (immutable pins)

- `evidenceRoot`: `/tmp/kbli-conductor-a1-0718/evid-lot8` — 127 files across 15 code directories,
  re-pull log `/tmp/kbli-conductor-a1-0718/pull-lot8.log` (`PULL COMPLETE 15 of 15 codes ok`, zero
  errors), independently verified this session (not trusted from agent prose alone).
- Workflow run: `wf_d079f983-515` (task `woydoml5r`) — the completed, valid run. First launch
  `wf_3a28b22f-e6d` (task `wxiwbqi9f`) was stopped before completion — empty evidence, discarded,
  zero seat results from it are used anywhere in this report.
- `runnerBlobSha256`: `45e3951fb0d52f1d2c1687c12895a38cdc050a62c8486e3cbcaef967f3d4b01d` (unchanged
  since Lot 7 — same certification-contract generation, no runner edits this lot).
- `canonical_sha256` (pre-cure, this branch's checkout): `03e3116a5d6bddd30d1d154842a30024396512c81b9ccfe28e0a0f813047fc02`.
  **Note:** this worktree's branch (`kbli/lot7-lane`) was found 56 commits behind `origin/main`
  when this gate was written — merged current before the Lot 8 cure spec is authored, so the cure
  applies against the true current canonical, not a stale snapshot (W88 discipline).
- Membership: 23 in-scope codes total in the "sport cluster" split (13 Lot 8 + 10 Lot 9:
  93127,93128,93129,93191,93192,93193,93194,93195,93197,93199), per the D0 pre-launch census
  recorded in the kbli-navigator corner.

## 5b. Arsenal outage — red-team could not run this cycle (verified, not assumed)

Attempted the mandatory red-team pass (`gpt-5.6-sol` xhigh via the codex MCP tool, per W97 full
output capture) immediately after cure-spec authoring. **Both non-DeepSeek red-team-capable seats
are confirmed down right now**, independently verified (not inferred from a stale digest):

- **Codex**: `mcp__plugin_second-opinion_codex__codex` returned `"Your access token could not be
  refreshed because your refresh token was revoked. Please log out and sign in again."` — the
  documented OAuth-token-revocation scar (CLAUDE.md: "OAuth token può andare in stato 401
  token_revoked... Fix: terminal interactive `codex login`"). This is an interactive-login action
  only the operator can perform — not self-serviceable.
- **Gemini (`agy`)**: a direct health ping (`agy -p "ping" --print-timeout 25s`) hung indefinitely
  (killed after ~3 min, zero CPU time — not processing, not erroring, just stuck). A SECOND,
  independent `agy` invocation from an unrelated process (PID observed via `ps aux`, not mine, seen
  hung since 07:11) confirms this is a genuine seat-level outage right now, not a one-off fluke on
  my specific call.
- **DeepSeek**: explicitly forbidden for this program (standing constraint, not re-litigated here).

**Disposition: this gate stays at FIRST SIGNING, red-team PENDING** — not skipped, not faked. The
conductor's own by-eye verification (§2: three independently re-rendered/re-checked images,
compiler dry-run confirming 9/9 clean cure, cross-referenced D1/D5 concordance for every code in
§3) stands as the evidence base, but does NOT substitute for the mandatory adversarial pass this
program has run on every prior lot. Cure PR should NOT auto-merge until either (a) Codex OAuth is
re-authenticated (operator[credentials] action) and the red-team pass runs, or (b) Zero explicitly
authorizes proceeding without it for this lot given the outage. Flagging as its own PENDING-ARMS
line (operator[credentials]: `codex login` needed on whichever machine hosts this MCP session).

## Sign-off

**FIRST SIGNING — conductor gate complete, cure scope determined (§3), NOT yet cured, red-team
PENDING (arsenal outage, §5b).**
Cure scope: **9 full-detach codes** (91425, 93113, 93115, 93121, 93122, 93123, 93124, 93125,
93126) **+ 4 explicitly-not-cured** (93111, 93112, 93114, 93119 — contract-coverage/tooling gaps,
§3.5, real data left untouched rather than destroyed) **+ 2 controls informational only** (63101,
73100 — not Batch-A members, no spec entry). Next: red-team (blocked on arsenal outage — retry
when Codex/Gemini seats recover), cure spec authored (this session, dry-run clean 9/9), second
signing, cross-family GLM Appendix A, gate PR, cure PR, data-apply PR, surfaces.
