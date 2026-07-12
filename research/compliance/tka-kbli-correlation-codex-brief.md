---
date: 2026-06-30
domain: compliance
client_case: none
project: TKA↔KBLI authoritative correlation dataset
status: brief-for-codex-multiagent
sources:
  - PP 34/2021 (Penggunaan Tenaga Kerja Asing) — data/source_documents/t0_regulations/pp_34_2021_penggunaan_tka.pdf
  - research/content/articles/17-tka-can-you-hire-or-be-the-foreign-worker.md
  - KBLI 2025 dataset — data/source_documents/KBLI_2025_FINAL_CLEAN.json (1559 codes)
---

# Codex Multi-Agent Brief — Authoritative KBLI ↔ TKA Position Correlation

> **Paste everything below the line into Codex** (`codex exec --sandbox workspace-write
> --skip-git-repo-check`), or run it as a multi-agent orchestration. It is written to be
> self-contained: it states the goal, the ground-truth sources, the regulatory model, the
> exact deliverable schema, the agent decomposition, the verification gates, and the hard
> constraints. Do NOT let any agent fabricate a jabatan list — every permitted/forbidden
> position must trace to a named Kemnaker instrument.

---

## ROLE

You are a multi-agent research+engineering orchestrator. Build an **authoritative, source-traceable
dataset that maps each Indonesian KBLI 2025 business code to the foreign-worker (TKA) positions that
are PERMITTED and FORBIDDEN for that activity**, grounded in the official Indonesian manpower regime —
NOT in ISCO/ILO proxies. The previous attempt used ISCO groups as a proxy and is being discarded; do
not reuse it as ground truth (you may use it only as a cross-check hint).

## WHY THIS MATTERS (the failure we are fixing)

A PT PMA can register a KBLI code and still be unable to operate, because **who may work in it** is a
separate regime (RPTKA + permitted jabatan). Founders assume "I own it, I can staff it" — false. The
manpower rules: (a) foreigners may hold only **certain positions**; (b) some positions are **closed to
foreigners by design** (notably HR/personalia); (c) every foreign role needs an approved **RPTKA**
(Rencana Penggunaan Tenaga Kerja Asing) with Indonesian counterparts + skill-transfer. A KBLI tool
that lists "eligible TKA positions" from an ISCO proxy is authoritative-looking but unverified — worse
than nothing. The fix: build it from the **official Kemnaker positive-list of jabatan per sector**.

## GROUND-TRUTH SOURCES (read these FIRST; do not skip to generation)

1. **PP 34/2021** "Penggunaan Tenaga Kerja Asing" — local copy:
   `data/source_documents/t0_regulations/pp_34_2021_penggunaan_tka.pdf`. The umbrella regulation:
   RPTKA, DKPTKA, permitted-positions principle, exemptions (directors/commissioners not managing
   personalia), skill-transfer + local-counterpart obligation.
2. **The Kemnaker positive-list instruments** — the actual per-sector jabatan lists. These are
   **Keputusan Menteri Ketenagakerjaan (Kepmenaker)** "tentang Jabatan Tertentu yang Dapat Diduduki
   oleh Tenaga Kerja Asing" issued per sector (Kepmenaker numbers vary by KBLI category — e.g.
   construction, accommodation/F&B, education, ICT, real estate each have their own decree). YOU MUST
   FIND THE CURRENT (2025/2026) ONES. They list, per sector, the exact **jabatan (Bahasa)** a foreigner
   may hold, often with required experience/qualification and the local-counterpart rule. This is the
   real source — not ISCO.
3. **The forbidden-position rule** — the jabatan **closed** to TKA. At minimum HR/personalia
   (Permenaker historically lists specific closed HR jabatan: e.g. Direktur Personalia, Manajer HRD,
   Manajer Personalia, Kepala Bagian Administrasi Kepegawaian, etc.). Find the current closed-list
   instrument verbatim.
4. **Our committed domain understanding** — `research/content/articles/17-tka-can-you-hire-or-be-the-foreign-worker.md`
   (verified published-draft). Use it for the regulatory model, not for jabatan data.
5. **The KBLI universe** — `data/source_documents/KBLI_2025_FINAL_CLEAN.json` (1559 codes, fields:
   `kode_kbli_2025`, `judul`, `uraian`, `sektor_id`, `per_skala[].kategori_risiko`). The thing each
   row must be correlated to.

## THE REGULATORY MODEL (so agents don't invent one)

- TKA permission is **per jabatan (position), scoped by sector/KBLI**, NOT per individual.
- The mapping is: **KBLI → sector → Kepmenaker positive-list of permitted jabatan for that sector**.
- Orthogonally: a **cross-sector forbidden list** (HR/personalia etc.) applies regardless of sector.
- Directors/Commissioners who do NOT manage personalia are exempt from being listed in the jabatan
  (they can work without an RPTKA jabatan slot) — encode this as a flag, not a position.
- RPTKA is the company-level licence; the individual KITAS work permit flows from it. The dataset
  describes POSITIONS + their basis, not individual permits.

## DELIVERABLE (exact schema — every record must validate)

Write `data/source_documents/tka_kbli_positions.json`: an object keyed by KBLI code. Each value:

```json
{
  "kode_kbli_2025": "55203",
  "sector_tka": "Akomodasi & Makan-Minum",
  "kepmenaker_basis": "Kepmenaker No. <NN>/<YYYY> tentang Jabatan Tertentu ... Sektor Pariwisata",
  "permitted_positions": [
    {
      "jabatan_id": "Manajer Hotel",
      "jabatan_en": "Hotel Manager",
      "basis": "Kepmenaker <NN>/<YYYY> Lampiran, row <k>",
      "requirements": "min. 5 yr experience / relevant degree (verbatim if stated, else null)",
      "local_counterpart_required": true
    }
  ],
  "forbidden_positions": [
    { "jabatan_id": "Manajer Personalia", "jabatan_en": "HR Manager",
      "basis": "Permenaker <...> (closed-list), verbatim" }
  ],
  "director_commissioner_exempt": true,
  "rptka_required": true,
  "confidence": "HIGH | MEDIUM | LOW",
  "provenance": "exact instrument + lampiran row(s) the permitted/forbidden lists came from",
  "verified": "<date> via <source>",
  "notes": "edge cases, sector-ambiguity, what is asserted vs inferred"
}
```

HARD RULE: a `permitted_positions` / `forbidden_positions` entry exists **only if** `basis` names a
real instrument + location (lampiran row / pasal). No basis → it does not go in the list; instead log
it to `unmapped_log` with the reason. `confidence=LOW` for any sector where the Kepmenaker list could
not be located — and SAY SO, do not pad with plausible jabatan.

## AGENT DECOMPOSITION (orchestrate; do not do it all in one pass)

**Phase 0 — Ground (1 agent).** Read PP 34/2021 + article 17 + the KBLI sektor_id taxonomy. Produce a
map of the ~9-22 KBLI sectors → their likely Kepmenaker positive-list decree title to hunt for. Output
`tka_sector_map.json`. No jabatan yet.

**Phase 1 — Source hunt (N agents, one per sector, parallel).** For each sector, FIND the current
(2025/2026) Kepmenaker "jabatan tertentu untuk TKA" decree + the cross-sector closed-list. Search:
peraturan.go.id, jdih.kemnaker.go.id, kemnaker.go.id, hukumonline, official PDFs. Download the PDF.
Each agent returns: instrument number+year+title, the PDF path (save under `data/kb_sources/tka/`),
and whether it's the in-force version. If a sector's decree cannot be found → report it, do not invent.

**Phase 2 — Extract (N agents, parallel, one per decree).** OCR/parse each decree's lampiran into the
permitted-jabatan table (jabatan_id, requirements, counterpart rule) + extract the closed-list
verbatim. Use `qwen2.5vl:7b` LOCAL for scanned PDFs (per repo rules: vision = qwen2.5vl only). Output
structured per-sector position tables with provenance to lampiran rows.

**Phase 3 — Correlate (1 agent).** Join: for each of 1559 KBLI codes, resolve its sector → attach that
sector's permitted list + the global forbidden list. Codes whose sector has no located decree →
`confidence=LOW`, empty permitted list, logged. Emit `tka_kbli_positions.json`.

**Phase 4 — Adversarial verify (independent agent, MUST be a different agent than Phase 2/3).** For a
stratified sample (≥2 codes per sector + all HIGH-confidence claims): re-open the cited lampiran row
and confirm the jabatan text matches verbatim. Refute any position whose basis does not actually
contain it. Apply the cicatrix anti-hallucination rule: a `file:line`/`lampiran row` cited by Phase 3
is a LEAD until re-read in THIS pass. Downgrade confidence on anything that fails. Produce a verdict
report `tka_kbli_verification.md` (claims confirmed / refuted / downgraded, with counts).

**Phase 5 — Cross-check vs the discarded ISCO proxy (1 agent, low priority).** Diff the new authoritative
list against the old `intel_2026.tkaInfo` to surface where the proxy was right/wrong — purely as a
sanity signal, never as a source. Note systematic divergences.

## HARD CONSTRAINTS (repo rules — non-negotiable)

- **No paid API keys.** Free-first: local Ollama (qwen2.5vl:7b for vision OCR), OAuth subscriptions,
  free web. DeepSeek V4 Pro ($0.01/q) is pre-authorized for non-PII reasoning only. NO Anthropic paid
  endpoint. If a step seems to need a paid key, STOP and surface it.
- **No PII.** This is all public regulation — keep it that way. No client data anywhere.
- **Sandbox.** `--sandbox workspace-write` only, never `--dangerously-bypass`.
- **Worktree discipline.** Do all work in a dedicated git worktree (`python scripts/agent_start.py
  --lane tka --task-id kbli-tka-correlation`), never the main checkout.
- **Anti-hallucination (load-bearing).** Errare è umano, allucinare è diabolico. Never cite a lampiran
  row/decree you did not actually open in the current step. A position with no traceable basis is
  EXCLUDED, not guessed. The verifier (Phase 4) must be a different agent than the extractor/correlator.
- **Honesty over coverage.** It is correct and expected that many sectors end at `confidence=LOW` if
  their Kepmenaker decree can't be located. Report the gap loudly in `tka_kbli_verification.md`; do not
  pad the dataset to look complete.

## DEFINITION OF DONE

1. `data/source_documents/tka_kbli_positions.json` validates against the schema for all 1559 codes
   (LOW-confidence + empty lists allowed and labelled).
2. Every non-empty permitted/forbidden entry has a `basis` pointing to a real, downloaded instrument
   (PDFs under `data/kb_sources/tka/`).
3. `tka_kbli_verification.md` reports the adversarial-verify outcome with confirmed/refuted/downgraded
   counts and the list of sectors that remained LOW (decree not found).
4. A short `tka_kbli_README.md` states: what's authoritative, what's LOW-confidence, the forbidden-list
   coverage, and the exact next step to close remaining gaps.
5. NOTHING is auto-promoted into the KBLI Navigator. The Navigator re-integration is a separate,
   later decision once this dataset is HIGH-confidence — the app code path was already removed
   (commit 37b6259, KBLIRegistryView.swift referenceDrawer).

## NOTE FOR THE ORCHESTRATOR

When you finish, write a 1-paragraph summary to stdout: how many codes ended HIGH/MEDIUM/LOW, how many
sectors had a located decree vs not, and the single most important gap to close next. Do not claim the
dataset is production-ready unless ≥80% of codes are HIGH/MEDIUM with traceable basis — otherwise label
it "research-grade, gaps documented".
