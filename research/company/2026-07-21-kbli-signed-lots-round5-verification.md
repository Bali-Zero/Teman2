---
date: 2026-07-21
domain: company
dossier: company-kbli-signed-lots (CHATKB dossier 11, 20 Q&A)
round: 5 (ground-truth sweep after team-review round 4)
adversarial_review: done (Kimi-subagent seat; Codex MCP+CLI unavailable — see §Adversarial review)
---

# Dossier 11 (company-kbli-signed-lots) — round-5 verification of team review

## Inputs

- Team review docx: `~/Downloads/11-company-kbli-signed-lots-REVIEW.docx`
  (20 Q&A, correction boxes filled by the team reviewer).
- Live file: `apps/backend-rag/data/curated_qa/company-kbli-signed-lots.jsonl`
  (gitignored local state; Qdrant-committed twice — manifests
  `company-5436e4a5e36e` 2026-07-19 and `company-16462b054787` 2026-07-21T09:46Z;
  `faq_committed: false` in both — grounding path only).
- Canonical ground truth: `data/source_documents/KBLI_2025_FINAL_CLEAN.json`
  (v10.0-L2-oss-risk; `l4_bali` field injected 2026-06-19 from schema-v2 =
  OSS L0 + Perpres L2 + Bali moratorium 13/5/26 L4).

## What round 4 already did (same day, before this pass)

A session earlier on 2026-07-21 had already applied part of this same team
review directly to the live file (no research capture found — provenance is
only in the rows' `law_refs` as "Team-review round 4 (2026-07-21)"):

- Row 6: reviewer's staffing note applied (70100 ≠ 78109, dual-KBLI point).
- Row 9: reviewer's positive-list caveat applied (75002 is "Kode/Cakupan
  Baru"; Perpres 10/2021 list is KBLI-2020-keyed → 100% reading
  cross-vintage-pending). The reviewer's underlying point was validated,
  with the correct legal framing: under Perpres 10/2021 the positive-list
  rule is that all fields are open EXCEPT those expressly closed/restricted
  (BPK summary of Perpres 10/2021, peraturan.bpk.go.id/Details/161806) — so
  absence-from-list IS the mechanism of openness, but for new 2025 codes the
  2020-keying makes the mapping itself the weak link, which is exactly what
  the amended answer now says.
- Row 11: ownership caveat for 80190 (historic 49% cap under repealed
  Perpres 44/2016, current cap not established; POLRI BUJP regime) — beyond
  the docx note ("oke"), from a cross-family regulatory check.
- Row 16: "ownership settled" narrowed to the general case.
- Re-harvested to Qdrant at 09:46Z (manifest `company-16462b054787`).

## Round-5 findings (this pass) — what round 4 did NOT catch

Checked all 11 dossier codes' `l4_bali` records against the dossier's
ownership claims. Three rows still ground live RAG answers with claims the
canonical dataset contradicts or materially qualifies:

### 1. KBLI 70100 (Q5, Q6) — structurally NOT registrable by a PT PMA

Dataset record for 70100 `l4_bali`:
`status: CHIUSO_PMA_NO_BESAR, blocked: true, confidence: HIGH,
needs_review: false`, reason: *"OSS has no Usaha Besar scale row -> reserved
for UMKM; a PT PMA (Usaha Besar by law) cannot register. [structural]"*.
Raw `per_skala_disputed_pp28_collision` confirms the only scale row is
`(Mikro, Kecil, Menengah) → Rendah` — no Besar row at all.

The Q5 answer (pre-round-5) said "open to full foreign ownership (TERBUKA,
100%)" and advised registering under 70100 for active-management structures;
Q6 said "nothing stops you from proceeding with company incorporation". Both
are wrong **in practice**: nationally the code is not on the restricted list
(paper TERBUKA), but OSS cannot register a PMA under it. This is the same
error class as the villa-rental round-2 finding (offering a blocked route as
compliant) — the single most dangerous correction type in this KB.

**Fix applied (rows 5, 6):** ownership claim reframed as "paper TERBUKA,
not PMA-registrable"; Q6 sequencing corrected to "classification first,
incorporation after"; scoping guidance corrected to KBLI **64210** (see
§Adversarial review — the draft originally repeated the dossier's
KBLI-2020-vintage "64200", which does not exist in KBLI 2025); new
`law_refs` entry cites the l4_bali record with its provenance caveats.

*Provenance caveat on the HIGH mark (surfaced by adversarial review):* the
record's underlying scale row sits in `per_skala_disputed_pp28_collision`
(`_l2_status='no_oss_risk'`, Lot-5 gate `source_absent_in_vault`), and the
l4 verdict (2026-06-28) predates the detachment — the same detached-basis
situation is marked LOW/needs_review on 66123/68126, so the HIGH here is
inherited, not re-derived. The record's own `intel_2026.baliContext`
contradicts the block (claims holdings "fit within the Medium scale") —
legally incoherent for a PMA (Usaha Besar by law, Perka BKPM 5/2025) but
logged here so the next reviewer doesn't rediscover the conflict. The
substance is externally corroborated: public OSS mirrors list 70100 as
Risiko Rendah / NIB-only with no Besar row, and Perka BKPM 5/2025 classes
PMA as Usaha Besar. Client text was accordingly re-attributed from "we
checked OSS" to "our canonical KBLI/OSS verification dataset records…".

### 2. KBLI 66123 (Q13) — Bali moratorium flag, LOW confidence

Dataset record: `status: CHIUSO_MORATORIA_BALI, blocked: true,
confidence: LOW, needs_review: true` — the Besar-scale risk reading
("Menengah Rendah") that would trigger the 13-May-2026 Bali PMA moratorium
(Gubernur letter B.27.000/642/PM/DPMPTSP) was itself detached to
`per_skala_disputed_pp28_collision`; verdict pending re-derivation
(GARUDA-FILIERA).

**Fix applied (row 13):** hedged Bali caveat added — "would place it in the
blocked group", confidence explicitly low, Bali registrability unresolved
pending re-derivation. NOT asserted as settled (mirrors the dataset's own
LOW/needs_review state). OJK-overlay content unchanged (reviewer confirmed:
"But need make license with OJK" — already covered).

### 3. KBLI 68129 (Q4) — investigated, NOT changed

`l4_bali: CHIUSO_BALI_PROPOSTO, blocked: false, confidence: HIGH` — a
*proposed* Bali PMA closure for real estate, not in effect. The Q4 answer's
TERBUKA 100% claim stands as of today. (Adversarial review struck an
earlier supporting argument here — "the disputed Besar-scale row reads
Menengah Tinggi, would survive the moratorium" — because that row is the
same detached, contaminated property-brokerage payload the Lot-5 gate
quarantined; the no-change call rests solely on `blocked: false` +
proposal-not-effective. A one-line hedged Bali-proposal caveat on row 4
would be defensible for symmetry with row 13 but is not required — the
question is nationally framed and nothing is currently blocked.)
Documented here so the next reviewer doesn't re-investigate.

## Team-review notes disposition (all 20 boxes)

| Q | Note (gist) | Disposition |
|---|---|---|
| 1 | "no PMA detail / scope / risk in system" | Matches dataset state (risk tiers quarantined to `per_skala_disputed_pp28_collision` pending GARUDA-FILIERA re-derivation). Answer's honest-gap stance is the correct behaviour. No change. |
| 2 | "double check with Menteri Pariwisata" | Pointer noted; sea-transport licensing is primarily Kemenhub-domain, tourism standards Kemenpar — both in the re-verification queue. Answer asserts no licensing detail, so nothing to retract. No change. |
| 3 | same as Q1 + "check dinas perhubungan" | Dishub pointer NOT supported for warehousing: warehouse registration is TDG under PP 29/2021 (Penyelenggaraan Bidang Perdagangan — trade/Kemendag lineage) via OSS ([PP 29/2021 Pasal 1(43)](https://peraturan.bpk.go.id/Details/173630/pp-no-29-tahun-2021), practitioner confirmations [1](https://prolegal.id/catat-begini-syarat-dan-prosedur-pengajuan-tanda-daftar-gudang/) [2](https://firmahukum.id/pengurusan-tanda-daftar-gudang-tdg-melalui-oss-panduan-lengkap-sesuai-aturan-terbaru-2025/)). Queued as a lead for the 68126 re-verification, not an answer change. |
| 4 | same note as Q3 | Dishub not relevant to real-estate leasing; 68129 ownership claim verified standing (finding 3 above). No change. |
| 5 | "no scope detail" | Vague; but verification found the real defect (finding 1). Fixed. |
| 6 | 70100+78109 dual-KBLI note + scope | Staffing note already applied in round 4; structural block fixed in round 5. |
| 7 | "ok" | No change. |
| 8 | confirms 78109 ≠ LPK + "no scope detail" | Reviewer agrees with answer. No change. |
| 9 | positive-list/2020-keying caveat | Validated and already applied in round 4 with correct legal framing (see above). |
| 10 | confirms 85321 government-only | Reviewer agrees. No change. |
| 11 | "oke" | Round 4 nonetheless added a warranted ownership caveat (historic 49% cap lineage). Kept. |
| 12 | "ok — possible, like Grab" | Reviewer agrees. No change. |
| 13 | "Ok — but need OJK license" | Already covered; Bali moratorium caveat added in round 5 (finding 2). |
| 14 | "ok" | No change. |
| 15 | rewording of "pending regulation" | Semantically identical to the answer's own definition. No change. |
| 16 | "ok" | Round 4 narrowing kept. No change. |
| 17 | paraphrase of KBLI-2025 crosswalk issues | Agrees with answer. No change. |
| 18–20 | "Ok" | No change. |

## Files

- Corrected full JSONL (20 rows; rows 5, 6, 13 amended — all
  non-`verbatim_eligible`, so only Qdrant grounding is affected):
  `research/curated-qa-corrections-2026-07-21/company-kbli-signed-lots.jsonl`
- Apply + re-harvest: operator-gated, same procedure as the morning package —
  see `research/curated-qa-corrections-2026-07-21/README.md`.

## Adversarial review (round 5, same day) — FIX-THEN-SHIP, fixes applied

Per the repo's R1 gate (generator≠grader), the draft above went to an
independent seat. The cross-model seat was unavailable (Codex MCP timed out
twice; `codex exec` CLI hung 25 min with zero output, task log
`bash-m17eew2w`), so the review ran on a fresh Kimi subagent with a refuter
brief — same generator≠grader separation, weaker model diversity; flagged
here for transparency. Verdict **FIX-THEN-SHIP**; all three required fixes
applied in place (the content above already reflects them):

1. **Real error caught — "KBLI 64200" does not exist in KBLI 2025.** The
   dossier (round-0 text, which round 5 had repeated) pointed clients to
   64200 for holding activity; the KBLI 2025 code is **64210 'Aktivitas
   Perusahaan Induk'**, recorded TERBUKA 100 in the canonical dataset —
   verified independently against `KBLI_2025_FINAL_CLEAN.json` (64200
   absent; 70100's BPS uraian points to "subgolongan 6421"). Rows 5/6, the
   row-5 law_refs attribution, and this capture fixed; the "verify 64200"
   open lead replaced by a 64210-registrability lead.
2. **Confidence calibration on 70100** — see the provenance caveat added to
   finding 1 (HIGH inherited pre-detachment; intel_2026 contradiction;
   client text re-attributed to the dataset rather than a live OSS check).
3. **68129 justification** — the "would survive the moratorium anyway"
   argument rested on the detached contaminated payload; struck, no-change
   call re-grounded (finding 3).

Also verified-and-rejected: the seat's own hint that warehousing might
involve Kemenhub PM 49/2021 — that regulation covers ship-equipment
certification, not pergudangan; the TDG/PP 29-2021 finding stands
("even the refuter hallucinates" pattern — checked, not blindly applied).

## Open leads (not blocking)

- 70100: identify the operative alternative code for active group-management
  PMAs (the record's own `intel_2026.youllAlsoNeed` suggests the
  management-consultancy family — 70203 etc.) and verify **64210**'s OSS
  registrability for a PMA (ownership already recorded TERBUKA 100).
  Feeds Q5/Q6's "we will confirm the workable classification" promise.
- 66123: GARUDA-FILIERA risk-tier re-derivation → settle the Bali-moratorium
  verdict (currently LOW confidence).
- 70100 l4 verdict: re-derive post-detachment and reconcile the HIGH mark
  with the LOW/needs_review treatment given to 66123/68126 in the same
  detached-basis situation (consistency debt flagged by adversarial review).
- 68126: confirm TDG track under PP 29/2021 in the re-verification queue.
- 80190 (round-4 addition): establish the *current* foreign-ownership
  ceiling against the live positive list; POLRI BUJP regime under PP 28/2025.
