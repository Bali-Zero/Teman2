---
date: 2026-07-21
domain: operations
client_case: none (GARUDA-FILIERA Batch A — program closure synthesis)
adversarial_review: exempt-synthesis-of-already-reviewed-lot-reports
sources:
  - "methodology: research/operations/2026-07-16-kbli-filiera-methodology.md (PR #2534 MERGED, adversarial_review: codex)"
  - "workflow: research/operations/2026-07-16-kbli-garuda-filiera-workflow.md (PR #2538 MERGED, adversarial_review: codex)"
  - "plan: research/operations/2026-07-18-kbli-batch-a-plan.md (pre-registration + amendments A-1..A-10)"
  - "research/operations/2026-07-18-kbli-batch-a-lot1-conductor-gate.md (PR #2695 dossiers; cure applied)"
  - "research/operations/2026-07-18-kbli-batch-a-lot2-conductor-gate.md (PR #2753 gate; PR #2761 cure)"
  - "research/operations/2026-07-19-kbli-batch-a-lot3-conductor-gate.md (PR #2768 gate; PR #2769 cure)"
  - "research/operations/2026-07-19-kbli-batch-a-lot4-conductor-gate.md (PR #2774 gate; PR #2776 cure)"
  - "research/operations/2026-07-19-kbli-batch-a-lot5-conductor-gate.md (PR #2788 gate; PR #2778 cure)"
  - "research/operations/2026-07-19-kbli-batch-a-lot6-conductor-gate.md (PR #2803 gate; PR #2800 cure)"
  - "research/operations/2026-07-19-kbli-batch-a-lot7-conductor-gate.md (PR #2837 gate; #2831 spec; #2878 apply)"
  - "research/operations/2026-07-20-kbli-batch-a-lot8-conductor-gate.md (PR #2892 gate, squash 66ee3932e4)"
  - "research/operations/2026-07-20-kbli-batch-a-lot9-conductor-gate.md (PR #2913 cure lane)"
  - "research/operations/2026-07-21-kbli-batch-a-lot10-conductor-gate.md (cure PR #2923 MERGED)"
  - "PR #2921 (feat(kbli): tier-scoped partial detach primitive in cure_canonical_collisions.py) — MERGED 2026-07-20T17:21:02Z, independently confirmed via `gh pr view`"
  - "PR #2923 (fix(kbli): Batch A Lot 10 cure — closes the last 6 codes of the 114-code sweep) — MERGED 2026-07-20T18:46:23Z, independently confirmed via `gh pr view`"
  - "PR #2926 (fix(kbli): Lot 10 one-off KG/Qdrant partial-detach for 93114/93191, audit trail) — OPEN as of this writing, independently confirmed via `gh pr view` + `gh pr checks` + `gh pr diff`"
  - "PR #2931 (fix(deps): heal npm-audit high gate on main — brace-expansion/axios/body-parser/js-yaml) — MERGED 2026-07-21T01:30:17Z, independently confirmed via `gh pr view`"
  - ".claude/skills/kbli-navigator/SKILL.md §1 LIVE STATE (last update 2026-07-20 at read time)"
  - ".claude/skills/modus/PENDING-ARMS.md (tail read for open-item context; lines re: 93111/93112/93119 fiktif_positif gap, tier-scoped detach gap, PR #2926 KG/Qdrant one-off, Kimi K3 scope-violation finding)"
  - "data/source_documents/KBLI_2025_FINAL_CLEAN.json (canonical, independently re-counted this session: metadata.total_codes=1559, len(data)=1559)"
  - "data/kbli-filiera/membership/batch-a-members.json (census artifact, independently re-read this session: A-serving/pp28=5, A-empty/gap=216, _total=221, canonical_sha256=446c5f5f1fcf5c33d18d411c71843a48f398b9b7a52f1f249c507c86604cf50b)"
---

# GARUDA-FILIERA Batch A — program closure synthesis (114/114, 0 remaining)

> This is a DOCUMENTATION synthesis of already-completed, already individually-reviewed work
> (Lots 1-10, each separately conductor-gated and adversarially reviewed — see each report's own
> `## Adversarial review` section). No data file, canonical dataset, KG, Qdrant, or gold file was
> touched to produce this report; no cure compiler was run. `adversarial_review: exempt-*` is used
> per `scripts/check_adversarial_review.py`'s PASS-2b rule (an exemption is a greppable escape
> hatch, not a silent one) — re-reviewing content each of the ten source reports already carries
> its own signed adversarial pass would be re-grading homework that already has a grade, not
> generator≠grader on anything new. Every load-bearing number below was independently re-derived
> this session against the committed artifacts (canonical dataset direct count, census artifact,
> `gh pr view`/`gh pr checks`/`gh pr diff` for PR state) — not merely copied from the lot reports'
> own claims.

## 1. Program scope

**Mandate:** re-validate all 1,559 KBLI-2025 codes against government sources (BPS crosswalk,
PP28/2025, Perpres 10/49-2021, OSS RBA), replacing silent cross-vintage fill with per-fact
provenance + earned abstention. Methodology: `2026-07-16-kbli-filiera-methodology.md` (P1-P9,
L0-L6, G13-G17). Execution architecture: `2026-07-16-kbli-garuda-filiera-workflow.md` (D0-D6
per-code protocol, Fable-5 as non-delegable final gate, extractor≠refuter≠red-team family
independence).

**Batch A scope (pre-registered, `2026-07-18-kbli-batch-a-plan.md` §1):** of the ~221 codes whose
`per_skala` licensing data has no OSS-2025-native source (`_l2_status: no_oss_risk`), Batch A
covers the **114 "A-serving" codes** — 113 with a `pp28_sources` pointer (`A-serving/pp28`) + 1
source-discovery code with none at all, 80190 (`A-serving/orphan`). These are the codes actively
**serving** possibly-vintage-2020 licensing data to production today — the highest-risk subset.
The other ~107 "A-empty/gap" codes (no `per_skala` at all, including the 8 pilot-cured
false-friends: 68112, 49213, 51103, 51203, 20111, 50115, 60312, 64310) are explicitly OUT of
Batch A — a separate, still-open watchlist (§6).

Note on "119 vs 114": the workflow doc (2026-07-16, pre-execution enumeration) counted 119
A-serving codes; the plan doc (2026-07-18) reconciles this explicitly — same semantic predicate,
different snapshot date; cures landing between the two dates moved 5 codes from serving to empty
before Batch A's membership was pinned. Not a discrepancy requiring further action.

## 2. Final tally — independently verified this session

**114/114 Batch-A codes have a final, evidence-backed disposition. 0 remain in scope.**

| Disposition | Count | Mechanism |
|---|---|---|
| Cured — full detach (`per_skala` → `[]`, honest-gap `_data_note`) | **109** | 91 (Lots 1-7, 13/lot) + 9 (Lot 8) + 8 (Lot 9) + 1 (Lot 10: 93193) |
| Cured — tier-scoped partial detach (only the defective tier moves; the sound tier survives byte-identical) | **2** | Lot 10: 93114, 93191 |
| Certified clean / no cure needed (quarantine was a tooling artifact, not a record defect) | **3** | Lot 10: 93111, 93112, 93119 |
| **Total** | **114** | |

Cross-check performed this session: `109 + 2 + 3 = 114` ✓. Independently re-derived (not copied)
from each lot's own signed cure-spec code count (grepped per-lot: L1-L7 each 13/13 full detach;
L8 §Sign-off "9 codes"; L9 §Sign-off "8 full-detach codes... + 2 metadata-only... no detach"; L10
§2 dry-run output showing 1 full detach + 2 partial detach + 0 spec entries for the 3 innocence
codes).

Canonical dataset independently re-counted this session: `data/source_documents/KBLI_2025_FINAL_CLEAN.json`
→ `metadata.total_codes == 1559` and `len(data["data"]) == 1559` (both checked directly, not
assumed). Spot-checked records for the codes named across multiple lots' reports:

| Code | Found in canonical? | `per_skala` state | Disputed marker |
|---|---|---|---|
| 93114 | yes | 1 surviving tier (Menengah Rendah) | `per_skala_disputed_pp28_collision` present (Tinggi/golf tier moved) |
| 93191 | yes | 1 surviving tier (Mikro-Besar, "Promotor Kegiatan Olahraga") | `per_skala_disputed_pp28_collision` present (contaminated tier moved) |
| 93193 | yes | `[]` (full detach) | `per_skala_disputed_pp28_collision` present, both tiers moved |
| 93111 / 93112 / 93119 | yes | untouched, fully populated (certified clean) | none — correctly absent |
| 68112 / 80190 / 93122 | yes | consistent with their respective lot reports (68112 = pilot honest-gap, 80190 = Lot 6 detach after certification-revocation, 93122 = Lot 8 `source_absent_in_vault` detach) | as expected |

(First attempt at this check in this session used the wrong dict key — `kode_kbli` — and returned
false "NOT FOUND" for every code; corrected to the actual field name, `kode_kbli_2025`, confirmed
by inspecting a raw record's keys. Recorded here as a caught-and-corrected error, per this
program's own W65 discipline: re-ground before citing, don't paper over a wrong first read.)

## 3. Per-lot summary

| Lot | Date | Members (+ controls) | Cure | Notable finding |
|---|---|---|---|---|
| 1 | 2026-07-18 | 13 (div 01→39) | 13/13 full detach | First-lot calibration: m1/m2/m5 all breached. Lane (same-family Sonnet D1/D5) had certified 8/13 clean; 7 were false-clean on content evidence (cross-family Codex + blind-GLM-vision flips), the 8th (19206) fell under the plan's divergence rule. Meta-finding: "same-family blind agreement measures transcription fidelity, not truth" — became the program's founding lesson, cited by every later lot. |
| 2 | 2026-07-18 | 13 (div 42→59) | 13/13 full detach (incl. 47771 metadata upgrade) | Both innocence controls (46100, 52101) turned out contaminated at the crosswalk-metadata layer (merge-undercounts caught only on the REVERSE BPS table) — first evidence the metadata disease lives outside the no-scope set too. |
| 3 | 2026-07-19 | 13 (div 60→64) | 13/13 full detach | Both innocence controls certified clean (2/2) — first clean control pair of the program. |
| 4 | 2026-07-19 | 13 (div 64→66) | 13/13 full detach | Root-caused the "cooperative payload" contamination: PP28 lampiran row 66292 is itself KBLI-2020-vintage, and one vintage-blind digit-string join poisoned 17+ codes across division 66. |
| 5 | 2026-07-19 | 13 (div 66→70) | 13/13 full detach | Controls certified; two codes (01629, 71204) added to the standalone metadata-fix backlog (still open, §6). |
| 6 | 2026-07-19 | 13 (div 72→85) | 13/13 full detach | The runner initially certified 80190 clean; adversarial review REVOKED that certification on record-level evidence (a false-friend confirmation caught, not missed) — 80190 rejoined the cure as 13/13. Drove a certification-contract hardening (`exposed_facts_inventory` required + fail-closed `factsInventoryUnverified`). |
| 7 | 2026-07-19/20 | 13 (div 85→91) | 13/13 full detach | The 41013 `fiktif_positif` finding (asserted with no citable PP28 derivation-formula coverage) drove a versioned formula refinement in `derive_fiktif_positif.py` — later directly relevant to Lot 8/10's 93111/93112/93119 disposition. |
| 8 | 2026-07-20 | 13 (91425 + 931xx sport cluster) + 2 borrowed controls | 9/13 full detach; **4 held un-cured** (93111, 93112, 93119, 93114) | First confirmed instance of the tier-scoped gap: 93114 has one sound tier + one defective tier, and the compiler could only detach the whole array. Both calibration floors breached but root-caused as a genuine population finding (poor PP28 locatability for this activity family), not pipeline defect. Codex/agy both seat-dead this cycle; Kimi K3 used as cross-family substitute red-team seat, verdict CONFIRMED-WITH-NOTES. |
| 9 | 2026-07-20 | 10 (931xx sport cluster remainder) + 2 borrowed controls | 8/10 full detach; **2 held un-cured** (93191, 93193) | Second confirmed instance of the tier-scoped gap (93191) — this is what triggered building PR #2921 (§4). Correction mid-gate: 93193 was first thought to have one sound tier too; re-verified to have zero (no PP28 row anywhere in the 21-file/11,208-page vault). |
| 10 | 2026-07-21 | 6 (the last held codes: 93111, 93112, 93114, 93119, 93191, 93193) | 1 full detach (93193) + 2 partial detach (93114, 93191); 3 certified clean, no cure (93111, 93112, 93119) | Synthesized Lot 8's and Lot 9's own already-adjudicated dispositions — no new D1/D5 lane was run. First production use of PR #2921's `partial_detach`. 93111/93112/93119's quarantines resolved as tooling artifacts (PP28 Pasal 8(1) grounds automatic-issuance for Rendah/Menengah-Rendah tiers as a DIFFERENT mechanism than `fiktif_positif`; 93112's `derived_license` field was never applicable to a record with a non-empty `perizinan`). **Closes the 114-code sweep: 0 remaining.** |

Cross-lot notes: every lot's FIRST signing was FIX-FIRSTed by its red-team pass (Codex GPT-5.6-sol
xhigh, cross-family from the Sonnet-family lane; Kimi K3 substituted at Lots 8-9 when Codex was
quota-limited and `agy` was seat-dead) — the substance (quarantine verdicts) survived every pass;
the errors caught lived in the audit trail (mislabeled metrics, wrong category, stale claims), not
in the underlying dispositions. Same-family lane-internal concordance was consistently high
(0.69-0.92) while cross-family concordance started low (0.385 at Lot 1) and settled near 1.00 once
the lane protocol was upgraded (image-grounded blind D5 as a lane requirement, not a conductor
add-on, from Lot 1's GO package onward).

## 4. The one new primitive: tier-scoped `partial_detach` (PR #2921)

`scripts/kbli_filiera/cure_canonical_collisions.py`'s original `apply_cure` moved a code's entire
`per_skala` array atomically — all tiers or none. This is destructive when a record genuinely has
one sound, evidence-backed tier and one defective one (e.g. 93114: a legitimate PP28-verified
non-golf tier plus a golf-course-specific tier with zero PP28 backing).

**The program's own discipline: the primitive was built only after the SAME gap was confirmed
TWICE**, not on first sighting. Lot 8 (2026-07-20) hit it on 93114 and filed it in PENDING-ARMS
as an open gap, holding the code un-cured rather than force a destructive whole-array detach. Lot
9 (2026-07-20, same day) hit the identical shape on 93191 — the Lot 10 report explicitly calls
this "the second confirmed instance." PR #2921 (`action: "partial_detach"` + `tier_selector`,
content-matched — never by array index) was built between Lot 9 and Lot 10, with a guilt+innocence
test pair (one code needing full detach still detaches fully; one code needing partial detach only
moves the flagged tier). Lot 10 is the first lot to use it in production, on exactly the two codes
that motivated it (93114, 93191) plus one full-detach code in the same lot (93193) proving the old
path still works byte-identically alongside the new one.

**This same "rule of two" discipline was applied again, independently, one layer down**, discovered
during this session's verification of PR #2926 (§5): the KG/Qdrant surface scripts
(`kg_kbli_license_fix.py`, `kbli_qdrant_risk_clear.py`) have the identical all-or-nothing shape as
the pre-#2921 canonical compiler, and hit the identical gap when Lot 10's partial-detach cure
reached the surface layer. Rather than build a second generic primitive on a single instance, the
program shipped a deliberately narrow, hardcoded one-off script
(`apps/backend-rag/backend/scripts/kbli_lot10_partial_detach_93114_93191.py`) and filed a
PENDING-ARMS line explicit that a generic surface-layer primitive is deferred until a THIRD
instance confirms the pattern recurs — the same engineering restraint, applied consistently.

## 5. PR #2926 — status, stated accurately

**PR #2926** (`fix(kbli): Lot 10 one-off KG/Qdrant partial-detach for 93114/93191 (audit trail)`)
is **OPEN, NOT MERGED** as of this writing (independently confirmed via `gh pr view 2926`:
`"state":"OPEN","mergedAt":null`). It is a **paper-trail PR**, not a pending change:

- The correction (hardcoded, exact edge-ID scope, guarded pre-write assertions on both the
  edges being removed and the edges required to survive) was **already applied directly to
  production** via `fly ssh`, 2026-07-21.
- It was **independently re-verified live** by the conductor session against Postgres
  (`kg_edges`/`kg_nodes` — 93114 left with exactly 2 sound REQUIRES edges + the 2 disputed ones
  archived in `properties._disputed_requires`; 93191 left with exactly 1 sound edge) and the
  public prod API (`/api/v1/kbli-notebook/inspect/{93114,93191}` confirmed clean of the
  cross-tier contamination post cache-bust) — both confirmed clean.
- The PR's own diff (independently pulled and read this session via `gh pr diff 2926`) is exactly
  two files: the new one-off script (289 lines, self-documenting WHY/WHAT/RESULT/USAGE) and a
  2-line PENDING-ARMS append. No canonical/data-plane file is touched — the canonical-side cure
  for these two codes already shipped in PR #2923.

**Why it's not merged**: `gh pr checks 2926` shows two failing checks — `Frontend Tests (Next.js)
(mouth, true)` and `Frontend Tests (Next.js) (admin-dashboard, false)` — everything else green.
This matches a repo-wide `npm audit --audit-level=high` gate failure (real CVEs in
axios/body-parser/js-yaml, pre-existing on `main`, affecting `apps/mouth` and
`apps/admin-dashboard`), unrelated to this PR's own diff.

**New finding from this session's independent verification (not in any prior report — flagged as
a discovery, not yet acted on):** PR #2926's CI run started 2026-07-21T00:21:23Z. A separate PR,
**#2931** (`fix(deps): heal npm-audit high gate on main`), **merged to `main` at
2026-07-21T01:30:17Z** — after #2926's CI already ran. This session's worktree HEAD (fetched from
`origin/main`) is `2a56d295b1` — the #2931 merge commit itself — confirming the fix is on main
now. This strongly suggests a rebase/merge-main + CI re-run on #2926 would go green, but **this
session did NOT rebase, push, or re-trigger CI on #2926** — that action is left for the operator
or a future session to execute and verify, not asserted as done here.

## 6. What is NOT covered by Batch A

Batch A's 114 codes were a bounded subset of the full no-scope population. Independently
re-derived this session from the committed census artifact
(`data/kbli-filiera/membership/batch-a-members.json`, post-Lot-10 re-emit, `_total: 221` invariant
confirmed) plus each lot's own reconciliation math:

- **221** — total no-scope codes (`_l2_status: no_oss_risk`), the program's own fixed invariant,
  confirmed unchanged in the current census.
- **8** — pilot-cured before Batch A began (68112 + 7 false-friends), a subset of the 221.
- **114** — Batch A (this closure): now fully adjudicated, 0 remaining.
- **≈99** — genuinely untouched by any program phase to date. This figure is **this session's own
  arithmetic** (221 − 8 pilot − 114 Batch A = 99), not a number directly stated by any single
  source document. The kbli-navigator skill's own LIVE STATE text says "~213 no-scope codes
  un-adjudicated" — that figure is **stale relative to Batch A's closure**: 221 − 8 = 213 was
  accurate *before* Batch A ran (it still counted Batch A's 114 as untouched); post-closure the
  correct residual is 213 − 114 = 99. **Flagging this explicitly as something the operator should
  independently re-confirm** (e.g. by re-running the census predicate) before it is quoted
  elsewhere — this session verified the *arithmetic* against the committed census artifact but did
  not re-run `emit_batch_membership.py` itself to generate a fresh full-catalog census.

**A residual artifact-shape caveat, independently confirmed this session and worth carrying
forward**: the current `batch-a-members.json` census still shows `"A-serving/pp28": 5,
"_in_scope_total": 5"` — NOT 0. This is **not** 5 unresolved Batch-A defects. Read directly from
the artifact's `members` list this session: the 5 are exactly {93111, 93112, 93114, 93119, 93191}
— the three certified-clean codes (whose `per_skala` was correctly never touched, so they
legitimately still "serve") plus the two partial-detach survivors (whose one sound tier keeps
`per_skala` non-empty by design). The classification predicate reads only "is `per_skala` empty",
not "is this code still under active dispute" — so it does not, and structurally cannot, drop to
zero even though the SUBSTANTIVE claim (114/114 have a final disposition) holds. Lot 10's own
report flags this same caveat; this session independently re-derived it from the raw artifact
rather than just trusting that framing.

**Also explicitly open, found in PENDING-ARMS during this synthesis (not part of Batch A's 114,
not closed by this program):**
- Standalone metadata-fix backlog (crosswalk-narrative corrections on OSS-native, per_skala-healthy
  records — `status_mapping`/`whatChanged`/`pp28_sources` narrative only, never a detach): 01629,
  71204 (Lot 5), 59140 (Lot 6), 20232 (Lot 7) — flagged lot-by-lot, not yet a dedicated spec+PR.
- The `pma_status` cross-vintage audit across the full 1,559-code catalog (Perpres 10/49-2021 is
  also 2020-vintage) — a separate FATAL-2-class axis, unstarted.
- The KG 68% name-dedup disease at the generator root (Batch A only fixed per-code edges reached by
  its own 114 cures, not the systemic cause).
- A 2026-07-20 finding (unrelated to data quality, process-integrity): a Kimi K3 seat dispatched as
  a read-only adversarial reviewer on the Lot 9 cure directly wrote to repo files mid-review — the
  content it wrote was independently re-verified correct, but the write path itself broke the
  generator≠grader boundary. Open with `operator[business]` as the owner (whether Kimi K3 continues
  as a review seat, and under what sandboxing) — noted here because it touches this program's own
  review architecture, not folded into the data-tally above.

## 7. Batch B — explicitly NOT authorized

**No Zero GO exists for Batch B as of this writing.** The kbli-navigator skill records "Batch-B
pre-registration design SIGNED (#2801 merged, REV-4b)" — a design being signed is not a phase GO.
This program's own phase-gate rule (methodology §Solo-operatore point 1, workflow §8 point 1,
plan doc's repeated Legge-5 framing) is explicit: **GO is per-batch, never inherited from the
prior batch's closure.** This report does not request, imply, or pre-stage a Batch B start; it
closes Batch A only. A fresh, explicit Zero GO is required before any Batch B lot begins.

## 8. Open questions (flagged, not smoothed over)

1. **The ≈99-code residual figure (§6) is this session's derived arithmetic, not a directly-quoted
   program number.** Recommend a fresh `emit_batch_membership.py`-style full-catalog census run
   before it is cited as authoritative elsewhere.
2. **PR #2926's mergeability after #2931 is inferred, not verified.** No rebase or CI re-run was
   performed this session.
3. **Whether the standalone metadata-fix backlog (§6) is complete** — it is described in the skill
   as "grows lot-by-lot", and this synthesis did not re-audit every lot report line-by-line for
   additional un-tracked entries beyond what LIVE STATE and PENDING-ARMS already list.
4. Adversarial review of this specific closure document, per the R1 CI gate's own design, is
   **exempted** (§ frontmatter) rather than run — because the load-bearing content is a synthesis
   of ten already-independently-reviewed source documents, not new claims. If a future reader
   wants a fresh cross-family pass specifically on the closure NARRATIVE (as opposed to the
   underlying data, which was reviewed ten times over), that is a reasonable ask this exemption
   deliberately does not preclude.
