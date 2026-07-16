---
date: 2026-07-16
domain: operations
client_case: none (product/data architecture)
sources:
  - "Operazione Garuda 1559 — KBLI Navigator Design and Quality Specification (GPT-5.6 Sol, 2026-07-14, ~/Desktop/garuda 1559.rtf)"
  - "KBLI Navigator Production Audit Report v2.0 (Subhi, 2026-07-09)"
  - "BPS Tabel Konversi KBLI 2020–KBLI 2025 (publication 2026-04-22, https://www.bps.go.id/id/publication/2026/04/22/909d503355d2b7664e43dea8/tabel-konversi-kbli-2020-kbli-2025.html)"
  - "Permen Investasi dan Hilirisasi/BKPM No. 5/2025 (in force 2025-10-02, revokes BKPM 3/2021, 4/2021, 5/2021 — https://peraturan.bpk.go.id/Details/332573/permeninvesbkpm-no-5-tahun-2025)"
  - "memory: discovery_kbli_68112_code_collision_pp28_vs_bps_2026_07_16, discovery_kbli_noscope_codes_per_skala_not_from_oss_2026_07_16, discovery_kg_perizinan_name_dedup_disease_2026_07_16, lesson_kbli_remap_gate_context_beats_title_2026_07_16"
  - "adversarial panel 2026-07-16: Codex GPT-5.6-sol red-team (15 findings, 5 FATAL; CLI default gpt-5.6-sol, effort medium) + Gemini 3.1 Pro costruttivo (12 suggestions)"
adversarial_review: codex
---

# Filiera KBLI — corpus methodology (assessment + rebuild plan)

> Mandate: "GPT Sol worked on the KBLI navigator and we realized we may have built all the KBLI
> inappropriately — if we were superficial, design the definitive methodology: government-source
> faithful, and beyond OSS in usefulness." This document is the answer: Part 1 the verdict,
> Part 2 the methodology, Part 3 phasing, §Meta-pattern, §Solo-operatore.

## Part 1 — Verdict: did we build the corpus wrong?

**Not wholesale — but yes, superficial on one specific axis, and the Garuda spec alone does not
cure it.**

### What is solid (keep)
- **Taxonomy layer**: 1,559 KBLI-2025 codes; judul/uraian realigned against the OSS RBA snapshot
  (`_l1_source: OSS_RBA_2025_id_version_fff4053d`; judul_fixed 1,559, uraian_fixed 1,550; PR #2118).
- **1,338/1,559 codes** carry OSS-native `ruang_lingkup` + per-scope licensing — KBLI-2025 vintage,
  structurally safe from cross-vintage contamination.
- **PMA layer** has a real legal basis (Perpres 10/2021 default-open + 49/2021 lists) with dated
  audit trails (pma_gov_fix_2026_06_27, terbatas_cap_audit_2026_06_27).
- **Bali overlay** dated and sourced (Gubernur letter B.27.000/642/PM/DPMPTSP), complete on 1,559.
- Record-level provenance fields exist (`_source`, `_l1_source`, `_l2_source`, `pma_source`,
  `pp28_sources`).

### The disease cluster (all surfaced July 2026)
1. **Cross-vintage weak-key joins** — PP 28/2025 lampiran numbers rows on **KBLI 2020**; BPS 7/2025
   renumbered codes. Our merge stitched PP28 rows onto KBLI-2025 codes by bare 5-digit equality.
   68112 proved the failure mode: MICE-venue licensing on a residential-leasing code (fixed #2508).
2. **Silent fallback-fill instead of abstention** — ~221 no-scope codes (OSS ruang-lingkup 404) got
   per_skala from PP28/curatela without row-level provenance; consumers read it as OSS truth.
3. **Non-reproducible generators** — the backend KG catalog has no generator left in the repo; the
   canonical is a palimpsest of one-off fix scripts. KG name-dedup (978 codes → one agriculture
   kewajiban node; ~68% of catalog wrong via inspect_kbli) is curable only at generator level.
4. **Editorial unbound from code identity** — 56303 café served discotheque copy; 128 cross-tagged
   tkaInfo purged (#2164); 63 phantom rows in kbli_gold_remap_table.json.
5. **Verification asymmetry** — PMA evidence: 13 explicit_official vs 1,542 status_derived; Bali
   evidence: 0 verified. (status_derived is legally *correct* — default-open by absence from the
   Perpres negative list IS the rule — but per-code linkage to annex rows was never systematic.)

**Red-team extension (Codex, confirmed):** the vintage defect is NOT confined to PP28. The
Perpres 10/2021 + 49/2021 investment annexes ALSO predate KBLI 2025, so every per-code PMA
conclusion needs the same cross-vintage treatment. Kepmenaker 228/2019 (TKA jabatan) is older
still. **Any source published before Dec 2025 that names KBLI codes is 2020-vintage (or older) and
must pass the crosswalk.**

**Live proof the refresh loop is not optional:** Permen Investasi/Hilirisasi-BKPM **5/2025**
(in force 2025-10-02) revoked BKPM 3/2021, 4/2021, 5/2021 and (per first reads) lowered the PMA
minimum paid-up capital from Rp 10 mld to Rp 2.5 mld. Our own operating references still cited
BKPM 4/2021. A corpus without change-detection decays silently — ours already had.

### Verdict on the Garuda spec (GPT-5.6 Sol, 2026-07-14)
**Adopt it — it is the right product-hardening harness** (source hierarchy, two-plane
facts/editorial, fail-closed quarantine, digest pinning, exact censuses, BE1/BE2 governance).
Its structural limit: **it certifies internal consistency of current bytes, not external truth
against sources.** Its own censuses make the unverified mass visible (1,542 status_derived; 0 Bali
verified; 221 scope-less; 19 quarantined rows) but freezing bytes does not re-derive them. The
68112-class survives Garuda certification for any PP28/Perpres-derived row that doesn't carry a
`dati_inferiti` marker. Garuda §13 "no regeneration" is right for the product phase and wrong as a
permanent corpus doctrine: the corpus needs a **reproducible filiera**, not a one-off regen.

## §Meta-pattern (malattia-delle-malattie)

All five diseases are ONE defect: **facts joined across sources by weak keys (code digits across
vintages, license names, titles) with silent substitution on source-silence, inside pipelines that
cannot be re-run.** The cure is not more auditing; it is a supply chain where every fact carries
its evidence, every join is vintage-aware, silence abstains, and every artifact is a build product.
(Scar-family alignment: #9 state-schema/data-drift + #6 phantom + W88 "verify by content".)

## Part 2 — The methodology: Filiera KBLI

### Principles P1–P9
- **P1 Per-fact provenance + temporal validity.** Every fact carries
  `(source_id, source_vintage, locator, retrieved_at, evidence_digest)` **and validity intervals**
  (promulgated / effective / transitional-until / repealed-by). A rule can be historically valid and
  currently inapplicable; the model must express both. Record-level `_source` is not enough.
- **P2 Vintage-aware identity.** `KBLI2020:68112 ≠ KBLI2025:68112`. Cross-vintage joins go through
  the official **BPS Tabel Konversi KBLI 2020–2025** (published 2026-04-22, Vol.2 May 2026; three
  patterns: 1-to-1, 1-to-many, many-to-1). The crosswalk is **necessary but NOT sufficient**: for
  1-to-many splits, regulatory inheritance requires activity-level adjudication (uraian semantics,
  lampiran row read, image-verified) with curator sign-off — never title-similarity ("context beats
  title", gold-remap lesson 2026-07-16). Bare-digit cross-vintage joins are forbidden by CI lint.
- **P3 Silence → corroborated abstention.** A single 404 is NOT regulatory absence (it may be UUID
  drift, deployment lag, WAF). `ABSENT` requires corroboration: ≥3 retries spread over ≥72h +
  portal-UI cross-check + stable aggregate counts. Confirmed absence yields `ABSENT(reason,dates)`;
  it is NEVER filled from a sibling code, another vintage, or an LLM. Cross-vintage proxying exists
  only as an explicit curatela row (crosswalk proof + semantic adjudication + curator + date +
  basis), rendered as "regulatory basis (PP28, KBLI-2020 numbering, crosswalked)" — never as OSS.
- **P4 Raw-evidence vault (L0).** Every scrape/PDF/API response stored content-addressed (sha256) with
  URL + fetch date. OCR-hostile PDFs stored WITH 300-dpi image renders (the "681t2" lesson:
  pdftotext corrupted digits; only the image read true). All layers re-derivable offline from vault.
- **P5 Deterministic compilers.** Canonical, KG catalog, search index, Garuda public-facts bundle,
  Navigator app JSON are ALL build artifacts from vault + curatela, regenerated by one command each.
  Hand-patches (like #2508) are emergency medicine, folded into curatela within the same week.
- **P6 Two-plane discipline** (Garuda §5 adopted as-is). Deterministic facts vs generated copy; the
  LLM never manufactures a fact; generator≠grader certification for editorial (Garuda §9).
- **P7 Multi-source change detection.** Not just OSS polling: JDIH watchers (BPS, BKPM, sectoral
  ministries, peraturan.bpk.go.id "dicabut/diubah" status flips) feed the same delta queue as the
  existing daily regulatory-watcher cron. Diff vs vault → alert → targeted Garuda §5.4.3
  recertification. First standing job: the 221 no-scope watchlist — when OSS publishes their scopes
  (SEB transition, national deadline was 2026-06-18), ingest and retire the PP28 proxy.
- **P8 Durable identity in KG and rows.** No entity dedup by name (the 68%-disease). Row identity =
  `(source_snapshot_digest, canonical row locator)` PLUS a semantic content-hash fingerprint so
  source reordering/insertion is detected as lineage, not silently absorbed. License/obligation
  nodes keyed per-code per-row; shared text is a rendering concern, not an identity.
- **P9 Quarantine as a state machine, corpus-wide.** Extend Garuda's editorial states to every layer:
  `certified | quarantined(reason, owner) | abstained(reason)` per fact; quarantine guarantees
  downstream exclusion (compiler-enforced), invalidates dependents, blocks release unless an
  explicit named exception exists, and has formal resolution criteria.

### Layers
| Layer | Content | Source of record | Vintage handling |
|---|---|---|---|
| L0 | Raw evidence vault | BPS PDF+web; OSS RBA API; PP28 lampiran PDFs (+image renders); Perpres 10/2021+49/2021 (+lampiran); Permen Investasi/BKPM 5/2025; BKPM SEB; Bali instruments; Kepmenaker 228/2019; sectoral Permen | recorded per item |
| L1 | Taxonomy: code, judul, uraian, hierarchy, 22 categories, **crosswalk 2020↔2025 as first-class dataset** | **BPS 7/2025 is the taxonomy authority**; OSS detail endpoint is a check — divergences are recorded discrepancies (and a product feature), never silent overwrites | 2025 native |
| L2 | Licensing: ruang_lingkup, per_skala (risk, licenses, requirements, obligations, authority, time), PB-UMKU | OSS RBA per-code snapshots (1,338); PP28 lampiran ONLY via crosswalk curatela for no-scope codes | 2025 (OSS) / 2020→crosswalked (PP28) |
| L2b | Sectoral standards behind the licenses | Sector-ministry Permen referenced by PP28 (Kemenpar, PUPR, Kemenperin, ESDM…) | per-reg validity intervals |
| L3 | PMA: open/conditional/closed, caps, conditions, partnership requirements | Perpres 10/2021 default rule (citable evidence) + 49/2021 annexes **per-code via crosswalk + semantic adjudication**; default-open check specified as an algorithm (annex-I closed, annex-II conditional, partnership lists), result recorded per code | 2020→crosswalked |
| L4 | Local overlays (Bali moratorium…) | dated instruments **with legal-force classification** (pergub vs surat edaran vs letter → binding vs administrative-practice signal, reflected in confidence language) | n/a |
| L5 | Investor cross-refs: capital rules (**Permen Investasi/BKPM 5/2025**, NOT 4/2021 — revoked), TKA jabatan (Kepmenaker 228/2019, crosswalk-flagged), related codes, sector ministry, **ISIC Rev.4 mapping**, **grandfathering/NIB-amendment flags** for split/merged codes | respective regs | per-reg |
| L6 | Editorial (grounded LLM), certified per Garuda §9, bound to (code, vintage) identity | Garuda pipeline | 2025 |

### OSS extraction contract (P7 prerequisite, red-team #11)
One page in the repo documenting: endpoints (`gw.oss.go.id/v2/portal/kbli/{uuid}`, `/ruang-lingkup`,
`/umku`, `/relasi`), auth (static app user_key — note it can rotate), rate budget (throttled,
Mini-hosted, night-window), retry/backoff, schema-drift detector (field census per snapshot vs
previous), and a permitted-use note (public portal data, no PII, snapshot-for-verification use).

### Gates (extends Garuda G1–G12)
- **G13 vintage-join gate**: zero cross-vintage joins outside the crosswalk; every PP28/Perpres-derived
  row references its crosswalk entry + adjudication record. CI lint on the canonical.
- **G14 source-silence gate**: every ABSENT carries corroboration evidence; per_skala rows without an
  L0 evidence pointer hard-fail the build.
- **G15 freshness gate**: per-code snapshot age tracked; stale > threshold → visible in trust panel
  ("last checked"), never hidden.
- **G16 reproducibility gate**: CI rebuilds canonical + KG catalog from vault and diffs against the
  committed artifacts — byte-identical or fail (anti-palimpsest).
- **G17 temporal-validity gate**: no fact rendered as current if its source is repealed/expired
  (validity intervals from P1 enforced at compile time).

### Beyond OSS — why ours becomes MORE useful than oss.go.id
1. **Multi-geography verdict**: national PMA + Bali overlay + per-scope licensing in one view — OSS
   answers none of "can a foreigner do this, in Bali, at this scale?".
2. **PMA aggregate burden precalc**: ownership cap + minimum capital (5/2025 rules) + partnership
   obligations + TKA positions, computed per code through the foreign-investor lens.
3. **Crosswalk navigation**: "your old code became X; here's what changed; does your NIB need
   amending?" — OSS auto-converted permits but offers zero exploration or grandfathering guidance.
4. **Change alerts**: "requirements for your code changed on <date>" — OSS has no changelog at all.
   Our vault diffs ARE the changelog.
5. **Honest discrepancy surfacing**: 68112-class collisions, PP28-vs-OSS and BPS-vs-OSS divergences
   shown with citations — nobody else does this, including the government.
6. **Search that works**: exact-code fast path + semantic + hierarchy browse (fixes Subhi F-03),
   clean snippets (F-02), synced grounded chat with abstain (F-04).
7. **Per-fact citations with dates** (Garuda §6 trust panel) — OSS shows conclusions; we show evidence.
8. **Bilingual EN/ID** with validated terminology + ISIC Rev.4 bridge for parent-company reporting.

### Verification doctrine
- Image-verify OCR-hostile lampiran (render; never trust extracted digits).
- Generator≠grader on all LLM output; deterministic validators are final authority (Garuda).
- NLM as bipolar verifier only with source-date vs resolution-date freshness check (W90).
- Permanent sentinel codes as regression fixtures: 68112, 56303, 70209, 47111, 47221, 79110, 01122,
  80190 + licensing-collision quartet 01287/38122/61909/85401. Every audit's negative findings
  become new sentinels.

## Part 3 — Phasing

- **Phase 0 — Garuda lands, with one amendment (red-team FATAL #5).** BE1/BE2 proceed (recertify
  post-#2508 pins per §5.4.3), BUT every PP28/Perpres-derived row is interim-labeled in the trust
  panel as "regulatory basis pending crosswalk audit" until Phase 1 clears it. Garuda may not
  certify externally-unaudited cross-vintage rows as more than that.
- **Phase 1 — Collision sweep (bounded, deterministic).** Ingest the official BPS conversion table
  (both volumes) into L0/L1. Enumerate all records whose per_skala derives from PP28
  (`pp28_sources` present / `_l2_source` null) AND all per-code PMA rows sourced from Perpres
  annexes. For each: crosswalk-adjudicate (1-to-1 fast lane; splits/merges get semantic
  adjudication with image-verified lampiran reads). Reassigned-meaning codes → quarantine +
  re-derive via the correct 2020 ancestor. Output: zero unaudited cross-vintage rows; the 63
  phantom gold-remap rows re-adjudicated through the same machinery.
- **Phase 2 — Reproducible compilers.** Canonical builder (vault + curatela → canonical vNext with
  per-row provenance + validity intervals) and KG catalog generator (per-code nodes, P8) — cures
  the 68% KG disease at the root instead of spot-deleting edges. G16 goes live.
- **Phase 3 — Refresh loop.** OSS re-snapshot cron (Mini, rate-budgeted) + JDIH watchers integrated
  with the existing regulatory-watcher; no-scope watchlist; deltas trigger Garuda §5.4.3
  recertification. L5 capital rules re-derived from Permen 5/2025 (first concrete workload).
- **Phase 4 — Editorial recertification.** Garuda §9 full-corpus run on the post-Phase-1 corpus.

## §Solo-operatore (Zero decides — Legge 5)
1. **GO on the phasing** (Phase 1 is the highest-value/lowest-regret; Phases 2-3 are engineering
   investments; Phase 4 rides on Garuda).
2. **Business call**: is "honest discrepancy surfacing" (collisions, gov-source divergences) a
   PUBLIC product feature or internal-only? It is a differentiator AND a potential irritant to
   authorities — business judgment.
3. **Permen 5/2025 capital-rule verification** feeds client-facing pricing/advice (PT PMA setup) —
   tax/setup team should verify the Rp 2.5 mld modal-disetor reading on the primary source before
   any client communication.
4. Consent for the standing OSS snapshot cron (new daemon on Mini — W81/W84 lessons apply; it ships
   with liveness receptors, not just KeepAlive).

## Adversarial review (generator≠grader panel record)
- Codex GPT-5.6-sol red-team (CLI default, effort medium): 15 findings (5 FATAL, 10 MAJOR) — all incorporated above; the two
  factual FATALs (Perpres annexes are 2020-vintage; BKPM 4/2021 revoked by 5/2025) independently
  verified this session (web, primary-source links in frontmatter).
- Gemini 3.1 Pro costruttivo: 12 suggestions — incorporated: L2b sectoral layer, PB-UMKU, capital
  rules refresh, ISIC mapping, grandfathering flags, temporal model, multi-frequency layer
  separation, synthetic OSS polling, PMA-centric precalc.
- DeepSeek seat: dead (BALANCE_DEAD per organism report) — 2-seat heterogeneous council, declared.
