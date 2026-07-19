---
date: 2026-07-19
domain: operations
client_case: none (GARUDA-FILIERA Batch A — Lot 7 conductor D6 gate)
adversarial_review: codex
adversarial_review_detail: "DONE (sol xhigh read-only, full-output capture per W97 — /tmp/kbli-conductor-a1-0718/lot7-redteam.txt, verdict at lines 9641-9679, 549,576 tokens). Verdict: FIX-FIRST — 1 BLOCKER (41013 absolved prematurely and on a WRONG legal base: MT→Pasal 225(1) not 230; fail-closed was CORRECT) + 2 MAJOR (20232 'concordant' contradicts the runner tuple; 'RANDOM'/disease-rate unsupported) + 3 MINOR. ALL cured in this SECOND SIGNING. Checks (a)(b)(c)(e)(f)(g)(h) PASS with exact independent recomputation — the objective adjudications of 85330/91222/20232 STAND."
sources:
  - "plan: research/operations/2026-07-18-kbli-batch-a-plan.md"
  - "runner: /tmp/kbli-conductor-a1-0718/lot7-runner.js sha256 9bb3870fe5bae3c977c8e1ab5895d098e7be86a604d54c0c9f4a6be6a103a609 = git blob a3e27f7fd2c7036a3183b466eb82960524ac57a1 @ origin/main 06b26c4639c2 — FIRST LOT under the patched certification contract (#2800 + OSS-native amendment bcd60e026e)"
  - "lane run: wf_f557bfcc-249 (30 seats, 0 errors, 0 empty), launcher sha256 95aa49ee6fbeede8c51b85024ea322a2e237f244f9a01b4c325ced99a9331125"
  - "prior gates: #2753 (L2), #2768 (L3), #2774 (L4), #2788 (L5), #2803 (L6 second-signed, 80190 revocation)"
  - "pre-launch pins: /tmp/kbli-conductor-a1-0718/lot7-prelaunch-pins.md (W88 15/15 per-record fence proof, canonical f2a90dfa…)"
---

# GARUDA-FILIERA Batch A — Lot 7 (A-L7) conductor gate

> D6 adjudication of the seventh lot: 13 in-scope codes (divisions 85→91: 85330,
> 85401, 85403, 85404, 86102, 86109, 86201, 86202, 86203, 90111, 91212, 91222, 91424
> — post-secondary/higher education, health facilities, literary creation, private
> museums/heritage, nature parks) + 2 innocence controls — **the program's FIRST
> FRESH controls** (20232 cosmetics mfg, 41013 industrial-building construction;
> 59140/59201 retired after 4 reuses; 62110 deliberately excluded by the conductor:
> division adjacent to the 58219 SUSPECT with judgment-ambiguous PSE-gaming scope).
> **FIRST LOT RUN UNDER THE PATCHED CERTIFICATION CONTRACT** (per-field
> exposed_facts_inventory + OSS-native locator clause + factsInventoryUnverified
> demote-only gate).

## 1. Outcome

**13/13 in-scope QUARANTINED — evidence-driven, five categories.** Both controls
were ALSO quarantined, for two very different reasons that are the twin headlines of
this lot (§3.4/§3.5): 20232 carries a REAL, conductor-eye-verified metadata falsity
(the "verified" OSS-native set disease again — an additional observed defect from a
fresh SELECTED control); 41013 is seat-clean on the problem bits and was quarantined
by the facts-inventory gate on `fiktif_positif` — a **CORRECT fail-closed under the
current contract** (post-adversarial correction: the record genuinely asserts the
fact ×5 with no cited provenance; the absolution to "contract artifact" is
CONDITIONAL on the derived-provenance refinement landing and 41013's seats being
re-run under it — §3.5).

Final category census (runner assignment, 6/4/1/1/1 = 13):

| Category | Codes |
| --- | --- |
| source_absent_in_vault (6) | 85403, 85404, 86109, 86201, 86202, 86203 |
| payload_cross_contamination (4) | 85330 **(aviation flight-school payload on an education code — §3.2)**, 85401, 86102, 91212 |
| code_collision (1) | 90111 |
| illegitimate_inheritance (1) | 91222 — **first Batch-A sighting of this category** |
| unresolvable_source_pointer (1) | 91424 |

All in the v2 closed registry (m3 ✅, 5 of 7 categories). Census is the runner's
single-final-category assignment, NOT an exhaustive defect census.

**Lease disclosure (standing):** LEASE-GUARD SKIPPED on all 15 dossiers — same infra
state, same compensating isolation.

## 2. Conductor spot verification (by-eye, THIS session — two fresh renders)

- **`20232/crosswalk/lampiran5_p156-156.png` (printed p.142):** TWO consecutive rows
  for 2020-code 20232 "Industri Kosmetik Untuk Manusia, Termasuk Pasta Gigi":
  `→ 2025-20232 "Industri Kosmetik untuk Manusia, Cairan Lensa Kontak"` AND
  `→ 2025-20235 "Industri Parfum Sesuai Pesanan"`. A genuine SPLIT with visible
  scope change (pasta gigi dropped from the title, contact-lens fluid added, bespoke
  perfume hived off). The control's canonical `status_mapping='MATCH_LANGSUNG'` +
  "Direct 1:1 match — code and scope unchanged" is **contradicted by government
  ink**. Both seats INDEPENDENTLY found SPLIT + `mapping_metadata_false`; the full
  runner tuple is nonetheless DIVERGENT on `licensing_inherits` (D1 false, D5 true —
  compiled `divergent=true`), so this is a both-sick divergence, not a concordance
  *(adversarial MAJOR cured: the first signing wrote "concordant finding")*.
- **`85330/crosswalk/lampiran10_p431-431.png` (printed p.417):** single row
  `85330 ← 85220 "Pendidikan Menengah/Aliyah Swasta"` — the canonical's claimed
  source 85499 is refuted; three rows below, `85530 "Kegiatan Sekolah Mengemudi" ←
  85499 "Pendidikan Lainnya Swasta"` shows where 85499 actually goes. Same page,
  same conductor eyes: **the 51108 residual bucket ("Angkutan Udara Bukan Niaga")
  feeds 85401, 85402 AND 85530** — the division-crossing fan (L5/L6 meta-pattern)
  now proven to reach the EDUCATION division; and `85404 ← {85332, 85340}` is a
  2-parent merge (canonical records only 85332 — the vet-trio incomplete
  single-parent shape).
- 90111's collision truth was image-verified at D0 by the pull agent (lampiran
  394946 printed p.498, label I.P.8: 90011 row 10 AND 90021 row 12, both
  Rendah/NIB/Bupati-Walikota; methodology + false-positive purge documented in
  `evid-lot7/90111/pp28/MANUAL_HUNT_90021_NOTE.json`) — cited here as agent-verified
  with method note, not conductor-eye (red-team may re-render).

## 3. Adjudications

1. **Seat agreement:** problem-bit agreement **9/13 = 0.692** (9 both-sick + 0
   both-clean among members); 4 true D1-clean-vs-D5-problem divergences (86102,
   86201, 86202, 86203 — the whole practice-of-medicine block) quarantined by the
   preregistered divergence rule. Runner same-family tuple-concordance **0.231** —
   declared runner-proxy breach (standing artifact, unchanged interpretation:
   structured-label instability, never a concordance key).
2. **85330 — payload_cross_contamination with a NEW mechanism (page-bleed
   row-boundary error):** canonical carries aviation flight-school licensing (DGCA
   Form 141-01, aircraft operating certificates, `sektor_id='I.I'` = Transportasi)
   on a post-secondary education code. Both seats traced the content: canonical's
   kewajiban items match VERBATIM the continuation text at the top of PP28 render
   p.232 belonging to the row PRECEDING row 65 (an aviation/flight-training code
   whose row starts on unretrieved p.231) — the fill pipeline read a row across a
   page boundary and attributed the previous entity's payload. On top of a false
   crosswalk pointer (85499 claimed; true parent 85220 SPLIT {85316, 85317, 85330},
   forward table p.235 + reverse p.431, conductor-eye on the reverse). This is a
   new contamination signature for the program record: **pagination row-bleed**.
3. **Health-facility family (86xxx) — 5 of 6 source_absent + 86102/86201-3
   divergences:** the D0 pull already showed corroborated PP28 ABSENT for
   86102/86109/86201/86202/86203 after full 21/21-file, 11,208-page scans. The
   lane's verdicts are consistent. Working hypothesis for D2 (NOT asserted as
   fact): health-facility licensing lives in sector instruments (Permenkes/OSS
   sector annexes) rather than the PP28 lampiran corpus — if true, this family's
   cure is honest-gap now, sector-instrument grounding later (a P1-v2-style wave
   for health instruments would be a Zero decision).
4. **20232 control — REAL finding (adjudicated TRUE-POSITIVE, conductor-eye §2):**
   `MATCH_LANGSUNG`/"scope unchanged" refuted by the SPLIT rows on p.142. Same
   class as the 59140 pp28-label nit but LOUDER (title/scope materially changed).
   Disposition: **no detach** (OSS-native, not a member; per_skala provenance sound
   by marker); joins the standalone metadata cure-list (with 01629, 71204, 59140
   pp28-label). **FATAL-4 corroboration, stated precisely (adversarial MAJOR
   cured):** 20232 is a fresh SELECTED control (conductor-screened for
   non-exposure, not a reproducible random draw — no sampling frame/seed was
   published), so this is **an additional observed defect in the "verified" 1,336
   set, NOT a rate estimate**. The qualitative pattern stands: every independent
   selection path into that set keeps surfacing defects (POS ledger 1 clean / 3
   contaminated; now a fresh control too). A defensible disease-RATE needs a
   published frame + algorithm + seed — that is exactly the FATAL-4 sweep decision
   pending with Zero. Burn-list grows: +20232.
5. **41013 control — CORRECT FAIL-CLOSED; absolution CONDITIONAL (adversarial
   BLOCKER accepted in full, adjudication rewritten):** seat problem bits clean
   (D1 `needs_quarantine=false`; D5 `problem_found=false` — the two seats' schemas
   carry DIFFERENT field names, stated precisely per the adversarial MINOR). D5's
   25-entry inventory has **20 verified through BOTH locator channels working as
   designed** (PP28 render p.23 row 5 for Mikro/Kecil/Menengah +
   `oss/ruang_lingkup.json` KbliResikos for Besar/BG003+GT003 — the OSS-native
   amendment proven live on its first exercise) and **5 absent — ALL
   `fiktif_positif`**. The record GENUINELY asserts `fiktif_positif=true` in all
   five scale entries (dossier canonical.json:10/30/56/82/110/140) with no citable
   provenance — so **the gate's fail-closed demotion is CORRECT under the current
   contract, and 41013 stays QUARANTINED as "derived provenance not yet
   certifiable"**. The first signing's "contract artifact, NOT a record defect"
   was PREMATURE (it absolved the record before the refined contract exists) and
   cited the WRONG legal base — corrected here: `fiktif_positif` is a rule-derived
   legal consequence codified by UU Cipta Kerja 6/2023, with **Pasal 225(1) PP
   28/2025 governing Menengah Tinggi** (Sertifikat Standar deemed verified on SLA
   miss — 41013's actual tier) and **Pasal 230 governing Tinggi** (Izin
   auto-issued); **Pasal 124(4) is the separate derived-LICENSE rule** the runner
   already encodes. The repo carries the versioned formula:
   `scripts/derive_fiktif_positif.py` (NB-3-verbatim boolean rule, incl. the
   external-regime exclusions). **Contract refinement #2 (cure deliverable,
   precondition for Lot 8): a DERIVED-class inventory entry is `verified` iff (a)
   its BASE facts (kategori_risiko, jangka_waktu) are verified with locators, (b)
   the derivation formula is cited versioned (script + instrument + article + 
   vintage: Pasal 225(1)/230 PP 28/2025), and (c) the formula's exclusions are
   checked. Guilt test: base facts absent ⇒ derived absent ⇒ no certification.
   Innocence test: base verified + formula cited ⇒ derived verified ⇒
   certification possible. THEN both 41013 seats are RE-RUN under the refined
   contract — only that re-run can convert this disposition to "contract
   artifact, not record defect".** Until then no absolution is on record.
   Burn-list: +41013 (conservative — fresh controls are cheap). Scope of the
   current limitation, stated precisely (adversarial MINOR cured): the present
   wording blocks certification of every NON-EMPTY record asserting
   `fiktif_positif` (an empty-per_skala record still certifies vacuously) — not
   "m2=0 forever".
6. **91222 — illegitimate_inheritance (first sighting):** 2-parent merge
   {91024, 91029} per both crosswalk directions (p.241 + p.437, seat-cited);
   canonical claims `MATCH_LANGSUNG` + `pp28_sources=['91022']` — and 91022
   (private museums) crosswalks to 91212/91300, never to 91222: the record inherits
   licensing from a code that is not its parent in EITHER direction. Distinct from
   collision (no same-digit trap) and from metadata_false (the inheritance itself,
   not just the label, is illegitimate).

## 4. Calibration

| # | Metric | Lot 7 | Limit | Status |
| --- | --- | --- | --- | --- |
| m1 | cross-family | Runner same-family tuple-concordance **0.231** = declared runner-proxy breach (standing artifact); problem-bit agreement **9/13 = 0.692**. TRUE cross-family GLM pass ⏸ (§5). | ≥0.75 | ❌ proxy breach DECLARED · true cross-family ⏸ |
| m2 | certification rate | **0.000 (0/13)** emitted and valid — every member is defective per cited evidence; the only clean-seat code in the lot (control 41013, non-member) was blocked by the fiktif_positif contract artifact (§3.5). | [0.20, 0.85] | ❌ breach declared (object-level; the artifact makes the ceiling unreachable until refinement #2 lands — declared, not pausable) |
| m3 | categories | 5 seen, all closed-7 (illegitimate_inheritance first Batch-A sighting) | closed list | ✅ |
| m4 | tokens/dossier | **avg 204,494.92** (2,658,434 / 13 in-scope; controls' 256,031 + 225,985 excluded from numerator AND denominator) · **max 249,113 (85401)** · identity check: members + controls = 3,140,450 = workflow total, exact | ≤400k | ✅ |
| m5 | gold-set | not run in-lane | ==1.00 | ⏸ cross-family pass (§5) |

## 5. Open before the Lot 7 cure ships

1. Red-team pass (sol xhigh, full-output W97) on THIS signed report — cures
   appended, second signing before anything ships.
2. Cross-family GLM pass: m1 sample 5 codes (MUST include 85330 aviation-payload +
   91222 first-sighting; Call B primary, Call A supplementary-only per L6 Appendix
   A) + m5-NEG 3 fresh + m5-POS per the L6 pool discipline (burn-list now
   +20232, +41013).
3. Cure spec `batch_a_lot7.json`: 13/13 detach + `_data_note` provenance (85330 →
   true parent 85220 SPLIT + aviation page-bleed record; 85401 → multi-parent incl.
   51108 fan; 85404 → {85332, 85340}; 91222 → {91024, 91029} illegitimate
   inheritance; 90111 → p.498 I.P.8 truth + ISO-9001 matcher trap record) + F12
   everywhere.
4. **Contract refinement #2** (§3.5): derived-fact rule + regression tests
   (guilt + innocence) + **re-run of BOTH 41013 seats under the refined contract —
   this re-run is the VALIDATION gate of the cure PR** (only it can convert the
   §3.5 disposition to "contract artifact"); precondition for Lot 8.
5. Standalone metadata cure-list grows: +20232 (with 01629, 71204, 59140).
6. D0 matcher hardening (ISO-9001 boilerplate trap, `fuzzy_code_pattern` guilt+
   innocence corpus) — FILED for the filiera-compiler lane.
6b. **Journal provenance (adversarial MINOR, runner deliverable):** each seat's
   journal entry must carry its LABEL, the sha256 of the FULL prompt actually
   sent, the sha256 of the response schema, the runner blob sha, and
   `control_tag_applied_after: true` for controls — so a future audit can prove
   which prompt/schema produced which verdict without trusting neutral labels.
7. Surfaces: proven consumer-map 13 codes + NOTE: `kbli_documents` 4th surface
   apply (sibling lane owns the `--all-quarantined` prod apply; verify it covers
   the L7 13 at close-out or run it coordinated via ledger).

## 6. Meta-pattern (the malattia-delle-malattie, program record)

- **The 51108 residual-bucket fan reaches its THIRD division** (transport → L5/L6
  targets → now EDUCATION: 85401, 85402, 85530 rows conductor-eye-verified on
  p.417). Any 2020 residual bucket must be treated as a collision factory whose
  every child needs independent adjudication — no inheritance presumption survives
  contact with this fan.
- **NEW contamination mechanism: pagination row-bleed** (85330): the fill pipeline
  attributed the PRECEDING row's continuation text (an aviation code) across a page
  boundary. Detection signature: kewajiban/persyaratan lists that match the TOP of
  a lampiran page verbatim while the code's own row is elsewhere; sektor_id
  inconsistent with the code's division is the cheap tripwire (85330 carried 'I.I'
  Transportasi on an education code).
- **The certification contract's derived-fact axis (generation 3):** L6 exposed the
  missing per-field inventory; the first live run under the patch exposed that
  rule-derived facts (fiktif_positif) can never satisfy a locator requirement.
  Every hardening reveals the next layer — the honest ceiling for certification is
  "base facts verified + derivation rules cited", not "every field has a table
  cell". Refinement #2 encodes exactly that, nothing more.
- **The "verified" 1,336 set keeps yielding defects under every SELECTION path
  tried (adversarial MAJOR accepted — no rate is claimed):** POS picks 1 clean /
  3 contaminated; now a FRESH innocence control (20232), picked for expected
  cleanliness, carries a false MATCH_LANGSUNG. None of these paths was randomized
  or frame-defined, so they support NO defect-rate estimate — only the
  qualitative signal that independent selection paths keep finding defects. A
  formal rate needs a declared frame + seed: exactly the FATAL-4 verified-set
  sweep decision (Zero, Legge 5), riper with each lot.

## 7. Artifact manifest (immutable pins)

| Artifact | Pin |
| --- | --- |
| Lane run | `wf_f557bfcc-249` (task whbngdcvp; 30 seats, 0 errors, 0 empty; 686s wall) |
| Launcher | `/tmp/kbli-conductor-a1-0718/lot7-launcher.js` sha256 `95aa49ee6fbeede8c51b85024ea322a2e237f244f9a01b4c325ced99a9331125` |
| Runner | sha256 `9bb3870fe5bae3c977c8e1ab5895d098e7be86a604d54c0c9f4a6be6a103a609` = blob `a3e27f7fd2c7036a3183b466eb82960524ac57a1` @ main `06b26c4639c2` (patched contract) |
| Canonical fence | sha256 `f2a90dfa391782f857f592e5faeb12aa0ce38d09e979dde4ae6e864a912155dc` @ main `06b26c4639c2`; membership artifact byte-exact (its embedded pin predates lots' cures — re-pin proven by W88 per-record check, 15/15 lot-relevant records byte-identical) |
| Render p.142 (by-eye) | `evid-lot7/20232/crosswalk/lampiran5_p156-156.png` |
| Render p.417 (by-eye) | `evid-lot7/85330/crosswalk/lampiran10_p431-431.png` |
| 90111 truth | `evid-lot7/90111/pp28/MANUAL_HUNT_90021_NOTE.json` (agent-image-verified, 29 ISO-9001-trap false positives purged) |
| Pre-launch pins | `/tmp/kbli-conductor-a1-0718/lot7-prelaunch-pins.md` |
| Raw compiled result | task output `whbngdcvp` (JSON `.result`, 15 entries) + journal `wf_f557bfcc-249/journal.jsonl` (30 results) |

## Adversarial review — VERDICT AND CURES

Seat: **codex gpt-5.6-sol xhigh**, read-only over this file + compiled result +
journal + canonical + renders. FULL output captured per W97
(`/tmp/kbli-conductor-a1-0718/lot7-redteam.txt`, 9,679 lines / 549,576 tokens;
verdict verbatim at lines 9641–9679). Overall verdict: **FIX-FIRST**. The
objective adjudications (85330 aviation payload, 91222 illegitimate inheritance,
20232 SPLIT, census 6/4/1/1/1, m4 token identity) were independently recomputed
and STAND.

| # | Severity | Finding | Cure in this signing |
|---|----------|---------|----------------------|
| 1 | BLOCKER | 41013 absolved as "contract artifact" PREMATURELY and on a WRONG legal base (Pasal 230/124(4) cited for a Menengah Tinggi record; the rule is Pasal 225(1), already versioned in `scripts/derive_fiktif_positif.py`) | §3.5 rewritten: fail-closed CORRECT, record stays QUARANTINED, legal base corrected (225(1) MT / 230 Tinggi / 124(4) derived-license), absolution CONDITIONAL on refinement #2 implemented+tested+seats re-run (§5.4) |
| 2 | MAJOR | 20232 described as seat-"concordant" while the compiled runner tuple is DIVERGENT on `licensing_inherits` (D1 false / D5 true) | §2 corrected: both seats independently found SPLIT+mapping_metadata_false, tuple nonetheless DIVERGENT on licensing_inherits |
| 3 | MAJOR | "RANDOM" probe / disease-rate language unsupported (selections were not randomized nor frame-defined) | §3.4 ("fresh SELECTED control... NOT a rate estimate") + §6 bullet rewritten with explicit no-rate caveat |
| 4 | MINOR | "m2=0 forever" over-broad (empty-per_skala records certify vacuously) | §3.5 scoped: blocks every NON-EMPTY record asserting fiktif_positif |
| 5 | MINOR | Journal entries lack prompt/label/schema provenance (neutral labels) | §5.6b deliverable: label + full-prompt sha256 + schema sha256 + runner blob sha + control_tag_applied_after |
| 6 | MINOR | Seat problem bits conflated ("both problem_found=false" — the two schemas use different field names) | §3.5 stated precisely: D1 `needs_quarantine=false`; D5 `problem_found=false` |

## Sign-off

**Lot 7 conductor gate: SIGNED — SECOND SIGNING, adversarial pass DONE** (codex
sol xhigh FIX-FIRST verdict: 1 BLOCKER + 2 MAJOR + 3 MINOR, ALL cured above; the
objective adjudications stand as independently recomputed). Census verified
against runner output; 20232 SPLIT + 85330 true-parent/51108-fan
conductor-eye-verified; both control dispositions adjudicated (41013 QUARANTINED
pending refinement #2 re-run); m4 identity-checked to the token. Cure PR
authorized to ship: 13/13 detach spec + contract refinement #2 (with the 41013
seats re-run as its validation gate) + standalone 20232 + journal provenance —
auto-merge armed only after the conductor's gate on the diff. — Conductor
(Fable, MANDATO S2), 2026-07-19.
