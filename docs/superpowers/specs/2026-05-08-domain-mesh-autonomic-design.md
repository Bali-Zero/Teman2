# Domain Mesh Autonomic — Design Doc (2026-05-08)

> **Brainstorming session output**: 6 domains × universal lifecycle (nasce → cresce → auto-correct → cosciente → canalizza)
> **Owner**: Antonello Siano (Bali Zero / Nuzantara)
> **Status**: design — pending Antonello approval, then writing-plans skill
> **Research base**: 7 SOTA reports (R1-R7) saved in `2026-05-08-domain-mesh-research/` subfolder, 5752 lines total

## 0. Executive summary

Antonello requested an autonomic system for 6 domains:

1. **Setup Team** (immigration/company KBLI/licenses/business/property/labor)
2. **Tax** (everything fiscal)
3. **Marketing** (news/trends/strategies)
4. **Antonello Lab** (AI research, code, frontier science, robotics)
5. **Bali Zero macro** (Indonesia macro: politics/economy/society/culture/geo)
6. **Nexus OSINT** (news + curiosities about authorities)

Each domain follows a **universal lifecycle**: born → grows → auto-corrects → conscious of choices → channels outputs into the system.

The design output is:

- **Meta-pattern** (lifecycle + trust tier + federation graph) shared across all 6 domains
- **Per-domain genesis manifests** (YAML) with feeders/scorers/owners
- **Stack OSS-first** ($4,800-7,500/yr total, zero new Anthropic API)
- **Phased roadmap** (4 phases, 12 months)
- **Anti-patterns** (12 explicit "do not")

---

## 1. Meta-pattern: lifecycle universale a 5 fasi

### 1.1 Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│   ① NASCITA          ② CRESCITA        ③ AUTO-CORRECT           │
│   ────────           ───────────       ─────────────             │
│   - Seed sources     - Auto-ingest     - Drift detection         │
│   - Schema iniziale  - Dedup           - Source quality decay    │
│   - Boundary         - Enrichment      - Cross-NB conflict       │
│   - Owner umano      - Promotion       - Self-rewrite            │
│        │                  │                   │                  │
│        └──────────────────┴───────────────────┘                  │
│                           │                                      │
│                           ▼                                      │
│   ④ COSCIENZA          ⑤ CANALIZZAZIONE                          │
│   ──────────           ────────────────                          │
│   - Telemetry          - Output → Mouth (content)                │
│   - "Perché ho preso   - Output → Telegram (alert)               │
│      questa decision?" - Output → CRM (cliente)                  │
│   - Audit trail        - Output → Dispatch (IG)                  │
│   - Mitochondrial      - Output → Skill graduation               │
│      value monitor     - Output → ADR (decision record)          │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 1.2 Phase 1 — NASCITA (Genesis layer)

A new domain (or sub-domain) requires 5 minimum ingredients:

1. **Seed sources** — 10-50 manually curated sources defining NB DNA
2. **Schema iniziale** — entity types, relation types, controlled vocabulary
3. **Boundary statement** — "NB responds to X, not to Y"
4. **Owner umano** — Antonello/Veronika/Adit/Krisna/Angel
5. **Trust tier** — AUTHORITY (curated, ground truth) vs INTEL (cron-fed, signal) vs WORKBENCH (research, draft)

**Hard rule**: no NB created without `genesis.yaml` manifest. Eliminates orphan-NB jungle.

Example manifest:

```yaml
# domains/setup-team/genesis.yaml
name: NB-3 Company Setup
trust_tier: AUTHORITY
owner: Adit
boundary:
  responds_to:
    ["PT PMA setup procedures", "KBLI classification", "OSS NIB workflow"]
  does_not_respond:
    ["Tax filing details (→ NB-4)", "Property ownership (→ NB-5)"]
seed_sources:
  - PP 28/2025 Risk-Based Approach
  - Permendag 26/2021
  - Permenkumham 17/2017 (KKL)
schema:
  entity_types: [KBLI, RegulatoryDoc, Procedure, Authority]
  relation_types: [REQUIRES, AMENDS, ENFORCED_BY]
review_cadence: weekly
ingestion_policy:
  auto_ingest: false
  promotion_from: [NB-INTEL-Regulation]
```

### 1.3 Phase 2 — CRESCITA (Auto-ingest layer)

Four growth modalities per domain:

| Modalità              | Source                             | Esempio                                     |
| --------------------- | ---------------------------------- | ------------------------------------------- |
| **A. Manual deposit** | Human uploads PDF/URL              | NB-2/3/4/5 today                            |
| **B. Cron stream**    | Scraper → scorer → router          | NB-INTEL-AIResearch                         |
| **C. Promotion**      | INTEL source promoted to AUTHORITY | NEW: NB-INTEL-Tax → NB-4 when PMK confirmed |
| **D. Federation**     | Source from other NB referenced    | NEW: NB-OSINT cites NB-3 KBLI taxonomy      |

Each NB declares which modalities it accepts in genesis. AUTHORITY: A+C only. INTEL: B only. WORKBENCH: A+B+D.

**Trust gating ad ingestion** — every source has 3 mandatory metadata:

- `source_authority_tier` (1=law, 2=gov-press, 3=tier-1-media, 4=blog, 5=social)
- `freshness_at_ingest` (timestamp)
- `confidence_score` (0..1, from scorer)

Only tier ≤ 2 can trigger promotion. Tier 4-5 stays in INTEL, never promoted.

### 1.4 Phase 3 — AUTO-CORRECT (Reflective layer)

Three drift types:

#### Source decay

PMK gets repealed. NB still has it. → **Drift detection job** re-fetches original, hash-compares, if `superseded_by` field present → flag as `STALE`, move to archive partition.

#### Cross-NB conflict

NB-2 says "C312 KITAS validity 1 year", NB-INTEL-Immigration cites recent decree saying 2 years. → **Conflict detector** nightly cross-queries between NBs on overlapping entities. If divergence > threshold → human owner alert, NO auto-resolve.

#### Self-coherence

Within same NB, contradictory sources. → **Internal consistency probe**: LLM reads entity card, asks "any contradictions?", logs.

**Auto-rewrite** allowed only for WORKBENCH tier. AUTHORITY (NB-2/3/4/5): never auto-rewrite. Only flag + draft proposal + human approval.

### 1.5 Phase 4 — COSCIENZA (Telemetry & explainability)

System must answer:

- "Why did you add this source to NB-3 yesterday?"
- "Which source generated this answer?"
- "Is this NB losing value? How many queries last 30 days?"
- "What autonomous decisions did you take in last 24h?"

Components:

**Mitochondrial Value Monitor** (PR #493 already live, extend to all NBs)
Per NB tracks: queries/day, sources/day, ratio query-per-source, days-since-last-query, days-since-last-source-add. If ratio < threshold for N days → flag SENESCENT.

**Decision log** (JSONL):

```jsonl
{
  "ts": "2026-05-08T10:23:11Z",
  "actor": "feeder.NB-INTEL-Regulation",
  "action": "source_add",
  "target_nb": "NB-INTEL-Regulation",
  "source_url": "https://djp.go.id/pmk-12-2026.pdf",
  "scorer_confidence": 0.92,
  "router_decision": "regulation",
  "reasoning": "matched pattern '/PMK \\d+/' AND domain='djp.go.id'",
  "policy_applied": "tier-2-government-direct"
}
```

**Explainability API**: `GET /nb/{id}/why?source={source_id}` → decision log entry.

**Weekly self-report** per domain — markdown auto-generated Sunday.

### 1.6 Phase 5 — CANALIZZAZIONE (Output layer)

6 sinks:

1. **Mouth** (content publishing) — NB-INTEL-Press + NB-7 → WR2 → Astro → IG/blog
2. **Telegram alerts** — domain-specific channels (#setup-team, #tax, #editorial, #antonello, #macro, #osint)
3. **CRM enrichment** — lead → NB-3/4/5 query → suggested quote/template
4. **Dispatch** — NB-7 + value monitor → carousel topic suggestion
5. **Skill graduation** (Round 2 future) — mature workbench → permanent Claude skill
6. **ADR** — autonomous critical decisions → `docs/adr/` markdown signed by system + human

### 1.7 Trust tier matrix consolidata

| Tier                                  | Auto-ingest                   | Auto-rewrite                     | Output authorized                                               | Promotion gate                  |
| ------------------------------------- | ----------------------------- | -------------------------------- | --------------------------------------------------------------- | ------------------------------- |
| **AUTHORITY** (NB-2/3/4/5/6/7 + new)  | NO (manual + promotion gated) | NEVER                            | Client answers, dispatches, quotes, SPT                         | Human approval (owner-specific) |
| **INTEL** (NB-INTEL-\*)               | YES (cron + scorer)           | NO (rewrite with human approval) | Telegram alerts, content seeds, promotion candidates, briefings | N/A                             |
| **WORKBENCH** (NB-9, NB-WORKBENCH-\*) | YES + manual                  | YES (for coherence)              | Skill graduation, ADR seed, internal use                        | Maturity check (3+ deep items)  |

---

## 2. Domain B1 — Setup Team

### 2.1 Genesis (R2-validated)

```yaml
domain_id: setup-team
description: "Immigration/company KBLI/licenses/business/property/labor"
authority_nbs:
  - NB-2 Visa & Imigrasi (97 src, owner Angel)
  - NB-3 Company Setup (183 src, owner Adit)
  - NB-5 Property & Real Estate (117 src, owner Krisna)
  - NB-6 Operations & Compliance (188 src, owner Adit)
intel_nbs:
  - NB-INTEL-Immigration (currently 0 src, BROKEN)
  - NB-INTEL-Regulation (currently 0 src, BROKEN)
  - NB-INTEL-Property [NEW]
  - NB-INTEL-Labor [NEW]
  - NB-INTEL-Regulation-Bali [NEW] (Provinsi+Badung+Gianyar+Denpasar)
workbench_nbs:
  - NB-WORKBENCH-CaseFiles (per-client research)
```

### 2.2 R2-validated feeder strategy

**Primary layer (Quick-wins R2)**:

- `mcp__pasal-id__search_laws` (40k regulations indexed, MCP ready) — **no need to re-scrape peraturan.go.id**
- `mcp__pasal-id__get_law_status` (status check superseded/active)
- JDIHN portal aggregator (1,212 JDIH sites integrated)

**Secondary scraping**:

- `setkab.go.id` (Perpres/PP signing announcements)
- `peraturan.bpk.go.id` (BPK has audit-friendly status field — supersession detection)

**Tertiary commercial**:

- Hukumonline tag scraping (fair use)
- Ortax DataCenter

**Health monitoring**:

- Fork `suryast/indonesia-gov-apis` (monthly check: 22 portals operational, 16 dead, 6 geo-blocked, 5 CF/bot-challenged)

### 2.3 R2 Discovery: Obligation engine (AscentAI bottom-up pattern)

> "AscentAI: patented bottom-up obligation extraction (critique of taxonomy-driven horizon scanning)"

Instead of "scrape news → match with client" (top-down taxonomy), pattern is "extract atomic obligations from regulation → match with active clients via obligation IDs".

```yaml
Obligation:
  id: auto
  text: verbatim from regulation article
  article_ref: "PMK 12/2026 Pasal 3 ayat 2"
  kbli_codes_affected: [list]
  obligation_type: [filing|reporting|payment|operational|registration]
  deadline_pattern: [recurring|one_time|conditional]
  sanction_if_missed: text
  effective_date: date
  human_validated: bool

Matching: client.kbli_codes ∩ obligation.kbli_codes_affected
→ alert client per new/changed obligations
```

### 2.4 Bali sub-stream (4 portals = 90% client coverage)

```yaml
NB-INTEL-Regulation-Bali:
  sub_streams:
    - jdih.baliprov.go.id (1,247 docs)
    - jdih.badungkab.go.id (already in PBG Kutuh case)
    - jdih.gianyarkab.go.id (Ubud heritage)
    - jdih.denpasarkota.go.id (Perwali Denpasar)
  scorer_fastpath:
    - bali_tourism: wisata|subak|krama|desa adat|akomodasi pariwisata
    - property: PBG|SLF|sempadan|zonasi|RTH
    - business: KBLI|izin usaha|UMKM
```

### 2.5 Long-term: Bali Zero LegalLLM blueprint

> "LexIndoLLM: Llama 3.2-1B fine-tuned on 393 Kutai Kartanegara local regulations + FAISS RAG (perplexity 9.13→1.74, ROUGE-L 0.21→0.44)"

Replicable for Bali Pergub/Perbup corpus (~1,500 docs). Local Ollama-runnable. Privacy-perfect. 3-6 months Phase 4 project.

### 2.6 5 sinks Setup Team

1. Telegram `#setup-team-alerts` (PMK/KEP affecting active clients)
2. CRM client enrichment (KBLI → tax obligations + property check + case-similar match)
3. Mouth content (immigration vertical articles)
4. IG carousel (regulation explained for expats)
5. Skill graduation candidate (NB-WORKBENCH-KBLI-Marina-7codes pattern)

### 2.7 Open question B1.a (per Antonello)

4 NB-INTEL del dominio — quanti?

- **A.** 4 distinti (Imm + Reg + Property + Labor) — max specialization
- **B.** 2 (Imm + Reg-all-in-one) — mid maintenance
- **C.** 1 NB-INTEL-Setup — min overhead, max noise

---

## 3. Domain B2 — Tax Engine

### 3.1 Genesis (R3-validated)

```yaml
domain_id: tax
description: "PPh/PPN/SPT/Coretax/BPJS adjacency"
authority_nbs:
  - NB-4 Tax & Fiscal Indonesia (118 src, owner Veronika)
intel_nbs:
  - NB-INTEL-Tax
  - NB-INTEL-Coretax [NEW DEDICATED — R3-justified]
workbench_nbs:
  - NB-WORKBENCH-Quote-Engine
```

### 3.2 R3 critical discovery: Zero Coretax public API

> "Non esiste developer portal pubblica con OpenAPI/Swagger. Integrazione passa per PJAP (Pajak Application Service Providers) licenziati: Pajakku, PajakExpress, OnlinePajak, Klikpajak, AlatPajak."

Architecture decision: **PJAP partner abstraction layer mandatory**.

```yaml
coretax_adapter:
  type: PJAP_partner
  primary: Pajakku (most mature multi-cliente)
  fallback: PajakExpress (only public pricing, easy contract)
  abstraction:
    interface: PJAPClient (faktur, e-bupot, e-Filing, SPT submit)
    retry_policy: exponential_backoff, max 5 attempts
    escalation: > 5 failures → Telegram Veronika + manual queue
```

Cost: ~Rp 1.5jt/mo (~€85) for PajakExpress business tier.

### 3.3 R3 Coretax instability is structural

> "Disruptions to the CTAS architecture are generally related to surges in API queue traffic on the central server. Server processing loads surge significantly because the Coretax system must verify Indonesian ID numbers (NIK) to the Dukcapil central database in real-time."

> "Bimo Wijayanto (DG Pajak): 3 of 21 issues resolved as of April 2026. 18 pending."

**NB-INTEL-Coretax dedicated is justified** (B2.a Opzione A recommended).

Top 12 incident taxonomy (R3-derived):

```yaml
CoretaxIncident_taxonomy:
  - login_fail_face_verif
  - save_invalid_faktur
  - error_404_mass
  - error_500_api_queue
  - period_spt_default_off
  - upload_attachment_fail
  - nik_validation_dukcapil_timeout
  - digital_cert_refresh_expired
  - pph_21_23_ebupot_xml_broken
  - faktur_xml_import_bug
  - approval_workflow_stuck
  - browser_specific_ui_break
```

### 3.4 R3 Workflow automation matrix (8/10 steps automatable)

| Step                             | Automatable        | Note                                                   |
| -------------------------------- | ------------------ | ------------------------------------------------------ |
| OCR fatture                      | 100%               | qwen2.5vl:7b already in stack                          |
| Tax code classification          | 90%                | Stanford NLP 461k row paper                            |
| Calcolo PPh 21/23/26/25          | 100%               | Rule-based                                             |
| Calcolo PPN                      | 95%                | Edge faktur invalid → human                            |
| Equalizzazione PPN↔SPT           | Semi               | Reconciliation + variance flag, **firma umana finale** |
| Generazione draft SPT            | 100%               | Template-driven                                        |
| Submit Coretax via PJAP API      | 80%                | 20% error recovery                                     |
| Tax planning interpretazione PER | Human + LLM-assist | Judgment Veronika                                      |
| Audit response DJP               | Human              | Stakes                                                 |
| Cliente sign-off final           | Human              | Veronika firma                                         |

### 3.5 R3 Indonesian tax-LLM gap = competitive opportunity

> "Indonesian tax-specific LLM: risultato negativo — non esiste pubblico al 2026-05. Opportunity gap chiaro per Bali Zero."

NB-4 + NB-INTEL-Tax + Coretax workaround library = **proto-IndoTax-LLM RAG**. Bali Zero potentially first to market with Indonesia-first tax LLM assistant for SMBs. Differentiator vs Pajakku/OnlinePajak (workflow automation, no semantic intelligence) AND vs Joki Coretax (grey-market brokers).

### 3.6 6 sinks Tax Engine

1. Telegram `#tax-alerts` (PMK/KEP/Coretax incidents)
2. CRM tax workflow trigger (KBLI → tax obligations derivation)
3. Quote engine grounding (NB-4 + NB-3 + workbench casi simili)
4. Mouth content (tax-vertical articles, Tax Calendar Indonesia 2026)
5. Coretax workaround library (searchable, Veronika quick-access during incidents)
6. **NEW**: IndoTax-LLM positioning (marketing differentiator)

### 3.7 Open questions per Antonello

- **B2.a**: NB-INTEL-Coretax dedicato? (R3 → Opzione A recommended)
- **B2.b**: Quote consistency detector (drift if quote out 0.7-1.5x market median)?
  - Sì attivo / Sì silent / No

---

## 4. Domain B3 — Marketing Pulse

### 4.1 Genesis (R4-validated)

```yaml
domain_id: marketing-pulse
description: "Trend detection + strategy + content ops"
audience: [expat_it, expat_ru, expat_en, investor, nomad]
authority_nbs:
  - NB-7 Editorial & Content Strategy (89 src, owner Antonello)
intel_nbs:
  - NB-INTEL-Press (broken, fix needed)
  - NB-INTEL-Trends [NEW]
  - NB-INTEL-Competitor [NEW, optional B3.a]
workbench_nbs:
  - NB-WORKBENCH-Editorial
```

### 4.2 R4 quick-wins zero-cost

- **HN Algolia API** (no auth, gratis) → cron Mini-Pro2 zero-cost trend detection
- **Brevo + MailerLite MCP servers** ready → close measure→idea loop
- **Wayback Machine CDX** → competitor cadence tracker (etically OK)
- **C2PA Content Credentials v2.2/v2.3** → AI authenticity differentiator EEAT 2026
- **Reddit organic mandatory** (March 2026 core update boost) — manual posts r/digitalnomad, r/IndoBali

### 4.3 R4 critical traps to avoid

- **Sora 2 deprecation 24 settembre 2026** — do NOT build content pipeline on Sora 2
- **Originality.ai 7.3% recall on GPT-5-mini** — useless as AI detector, use GPTZero (~99%)
- **Reddit 10k req/month + non-commercial** — defensive use only
- Trendpop $250+/min, Talkwalker enterprise-only — skip, Brand24 Individual $99 sufficient

### 4.4 R4 SEO 2026: GEO (Generative Engine Optimization)

> "AI Overviews 76.1% rule. Reddit boost (March 2026 core update). EEAT, CWV thresholds."

Mouth content must optimize for **LLM-citability** (ChatGPT/Perplexity citations), not only Google SERP.

### 4.5 Drone Emprit exploratory partnership

> "Drone Emprit (Ismail Fahmi, Media Kernels Indonesia): Indonesia native social listening authority. Partnership lead worth exploring for visa/immigration sentiment."

Spawn `NB-WORKBENCH-DroneEmprit-partnership` for exploration.

### 4.6 6 sinks Marketing

1. WR2 brief auto-generation (NB-INTEL-Press top relevance → brief → Codex draft → mouth)
2. IG carousel suggestion (NB-INTEL-Trends + NB-7 methodology)
3. Telegram `#editorial` (brief candidates daily)
4. Newsletter Brevo daily digest 7am WITA
5. Mouth dispatch trigger (article → IG + LinkedIn + newsletter orchestrated)
6. **NEW**: Reddit organic dispatch (manual, included in weekly editorial brief)

### 4.7 Open questions

- **B3.a**: NB-INTEL-Competitor (Emerhub/Cekindo/InvestinAsia)?
  - Sì full / Sì weekly digest only / No
- **B3.b**: WR2 auto-trigger autonomy?
  - A. Auto-brief → auto-WR2 → human review pre-publish (low risk, high latency)
  - B. Auto-brief → auto-WR2 → auto-publish QA gate (low latency, editorial risk)
  - C. Manual everything (safe but no automation gain)

---

## 5. Domain B4 — Antonello Lab

### 5.1 Genesis (R5-validated)

```yaml
domain_id: antonello-lab
description: "Personal: AI papers, code, frontier science, robotics"
authority_nbs:
  - NB-9 Research Lab (201 src, owner Antonello)
  - NB-HARARI (10 src, AI ethics)
intel_nbs:
  - NB-INTEL-AIResearch (339 src, LIVE)
  - NB-INTEL-Code [NEW]
  - NB-INTEL-Robotics [NEW]
  - NB-INTEL-FrontierScience [NEW]
workbench_nbs:
  - NB-WORKBENCH-Antonello-{topic} (spawn on-demand)
```

### 5.2 R5 stack consigliato (zero marginal cost)

```yaml
research_orchestration:
  primary: Claude Code subagents + Skills (3x Max plan)
  secondary: Gemini CLI 3.1 Pro (OAuth free)
  tertiary: gpt-researcher + gptr-mcp (DeepSeek/Ollama backed)

long_form_synthesis:
  framework: Stanford STORM (Knowledge Curation + Outline + Article + Polish)
  target: NB-9 Research Lab

personalization:
  tier_1: arxiv-sanity SVM-on-tfidf (zero LLM cost, self-host Mini-Pro2)
  tier_2: bge-m3 embeddings + qwen3.5:9b rerank (Ollama local)
  tier_3: Claude Skill `research-lab.md` (procedural memory)

long_term_memory:
  primary: Mem0 vector + KG (Mini-Pro2)
  secondary: Anthropic Memory MCP (Claude-native KG)
  tertiary: Markdown mirror in ~/Desktop/nuzantara/research/ (Git tracked)
```

### 5.3 R5 feeder updates

- **Remove**: Papers With Code (dead July 2025), Asimov Press (hiatus April 2026)
- **Add**: HF Papers Trending (PWC replacement), TLDR AI subscription (1.25M readers)
- **Robotics seed**: Helix 02 (Figure), π0/π0.5 (Physical Intelligence), Gemini Robotics On-Device, GR00T N1.7 (NVIDIA), OpenVLA, Tesla Optimus Gen 3

### 5.4 R5 GitHub trending 4-tier signal

Detect repos 2-7 days **before** GitHub Trending page:

1. HN submission >100 pts first 6h on `github.com/`
2. Mention TLDR AI / Latent Space / The Batch
3. Star History slope jump (5x daily growth)
4. Sourcegraph search hit cluster

Language priority 2026: TypeScript > Rust > Python (Octoverse 2025: TS overtook).

### 5.5 R5 Gwern "Nenex" reference

> "A Nenex system would interactively tailor itself to a user's writing style, knowledge, existing corpus, and enable semantic features unavailable in other systems, such as searching a personal wiki for pages that need updating given updates to other pages."

Literary reference for "cresce → cosciente" stage. Corpus actively requests updates when cross-cutting facts change.

### 5.6 5 sinks Antonello Lab

1. Morning briefing Telegram 7am WITA (top-5 papers, repos trending, robotics, science)
2. Deep-read trigger (mark paper → spawn workbench with PDF + related work map + code repo cloned + summary draft)
3. Research session orchestration (`/research <topic>` → multi-agent → consolidated report)
4. Cross-pollination Bali Zero (paper relevant to BZ → alert Veronika/team)
5. Long-term KG (Mem0 + Anthropic Memory MCP)

### 5.7 Open questions

- **B4.a**: 4 NB-INTEL Antonello Lab (AIResearch + Code + Robotics + FrontierScience)?
  - A. 4 distinti / B. 2 (AIRes+Code, Rob+Sci) / C. 1 unificato / D. priority Robotics+Sci first
- **B4.b**: Morning briefing Telegram?
  - A. Daily 7am / B. Weekly Sunday digest / C. On-demand `/research-pulse`

---

## 6. Domain B5 — Bali Zero Macro

### 6.1 Genesis (R6-validated)

```yaml
domain_id: bali-zero-macro
description: "Indonesia macro: politics, economy, society, culture, geo"
authority_nbs:
  - NB-8 Expat Life Bali (140 src, lifestyle)
  - NB-IndonesiaMacro [NEW DEDICATED] (CSIS/ISEAS/Lowy seed)
intel_nbs:
  - NB-INTEL-IndonesiaPolicy [NEW]
  - NB-INTEL-IndonesiaEconomy [NEW]
  - NB-INTEL-IndonesiaSocial [NEW]
workbench_nbs:
  - NB-WORKBENCH-Indonesia-Outlook-{quarter}
```

### 6.2 R6 lifecycle mapping (5 layers, adopt as-is)

```yaml
layer_0_raw_signal:
  cadence: 15min - daily
  feeders:
    - GDELT API (FIPS-2=ID, free, no auth)
    - ACLED API (free, registered)
    - Antara EN/ID RSS
    - BPS WebAPI (token-auth free)

layer_1_curated_press:
  cadence: daily
  feeders:
    - Tempo (investigasi tag)
    - Kompas.id (paywall, manual highlights)
    - Jakarta Post tag pages
    - Project Multatuli investigations
    - Tirto.id deep dive
    - NusaBali (multi-kabupaten Bali)

layer_2_thinktank:
  cadence: weekly
  feeders:
    [
      CSIS Indonesia,
      ISEAS Perspective,
      Lowy Interpreter,
      New Mandala,
      FULCRUM,
      Habibie,
      TII,
      FKP,
    ]

layer_3_social:
  cadence: weekly digest
  feeders:
    [
      Drone Emprit pers.droneemprit.id (free),
      Indonesia Indicator,
      X trends24,
      TikTok Indonesia,
      Reddit r/indonesia,
    ]

layer_4_business_quarterly:
  cadence: quarterly
  feeders:
    [
      World Bank API,
      IMF Article IV,
      ADB CPS,
      OJK SJK Public,
      BritCham/EuroCham/AmCham/IABC,
    ]
```

### 6.3 R6 Bali calendar (Saka/Pawukon)

```yaml
Bali_calendar_module:
  source: babadbali.com + peradnya/balinese-date-js-lib
  query_function: get_balinese_date(gregorian_date) → {saka_year, pawukon_day, ceremonies_today}
  next_dates_2026:
    galungan: 2026-06-17 Wed
    kuningan: 2026-06-27 Sat
  cross_domain_use:
    - B1: skip PBG/SLF appointments around Galungan ±3 days
    - B2: filing slow during Galungan/Kuningan window
    - B3: content "Galungan for expats" 1 week before
    - CRM: client comm "we are closed [DATE]" template auto-fill
```

### 6.4 R6 geopolitica timeline 2026 anchor events

| Date           | Event                                        |
| -------------- | -------------------------------------------- |
| 2026-01-07     | BRICS membership effective                   |
| 2026-01-21     | IMF Article IV publ. (CR 2026/010)           |
| 2026-02-19     | US-Indonesia ART signed $33B (Trump-Prabowo) |
| 2026-02-20     | SCOTUS shakes ART legal base                 |
| 2026-02 mid    | Jakarta Treaty (Australia)                   |
| 2026-04-15     | Prabowo Moscow + new US defense pact         |
| 2026-05-05     | CSIS "creeping militarization" warning       |
| **2026-06-17** | **Galungan**                                 |
| **2026-06-27** | **Kuningan**                                 |
| 2026 TBD       | IEU-CEPA ratification track (target 2027)    |

### 6.5 5 sinks Macro

1. Quarterly outlook PDF auto-draft (workbench → 8-page PDF → optional client newsletter premium)
2. Cross-domain alert dispatcher (Kemenkeu → tax, Kemenkumham → setup, Kemenparekraf → marketing)
3. Mouth long-form analysis (multi-month framework articles)
4. Telegram strategic alerts weekly (not daily — strategic, not breaking news)
5. NB cross-pollination

### 6.6 Open questions

- **B5.a**: NB-IndonesiaMacro nuova o estendere NB-8?
  - **R6 confirms Opzione A** (NB-IndonesiaMacro nuova, separata da NB-8 lifestyle)
- **B5.b**: 3 NB-INTEL Macro distinti o 1 unificato?
  - **R6 confirms Opzione A** (3 distinti: Policy + Economy + Social)

---

## 7. Domain B6 — Nexus OSINT

### 7.1 Genesis (R7-validated)

```yaml
domain_id: nexus-osint
description: "People-graph + entity tracking Indonesia authorities"
boundary: "OSINT only (open sources). No doxing. UU PDP 27/2022 compliant."
authority_nbs:
  - NB-Nexus-People [NEW] (50 seed entries, bootstrap via Wikidata SPARQL)
  - NB-Nexus-Organizations [NEW] (30 seed orgs)
intel_nbs:
  - NB-INTEL-Authorities [NEW]
  - NB-INTEL-Curiosities [NEW]
workbench_nbs:
  - NB-WORKBENCH-Nexus-{person_or_topic}
```

### 7.2 R7 stack zero-cost ($130/yr only Hunchly)

| Layer                | Tool                                           | Cost    |
| -------------------- | ---------------------------------------------- | ------- |
| Entity ontology      | Wikibase self-host + Wikidata seed             | FREE    |
| Sanctions            | OpenSanctions free + API                       | FREE    |
| People-graph         | Wikidata SPARQL + LittleSis API + LHKPN scrape | FREE    |
| Investigative search | OCCRP Aleph (request access journos)           | FREE    |
| Username pivots      | Maigret 3000+ sites                            | FREE    |
| Email pivots         | Holehe + Mosint                                | FREE    |
| NER pipeline         | cahya/bert-base-indonesian-NER                 | FREE    |
| Visualization        | Gephi + NetworkX                               | FREE    |
| Evidence custody     | Hunchly                                        | $130/yr |
| News surveillance    | Tempo/Tirto/Multatuli/Watchdoc RSS             | FREE    |

**Skip**: Maltego ($$$$), Sayari ($$$$$), World-Check ($$$$$+ false-pos lawsuits), Palantir (cost + ethics red flags).

### 7.3 R7 Palantir-pattern 3-layer architecture

```
domains/nexus-osint/
├── semantic/
│   └── entity_definition.yaml  (Person, Organization, Event, Sanction)
├── kinetic/
│   ├── lhkpn_scraper.py
│   ├── wikidata_sparql.py
│   ├── opensanctions_id_pull.py
│   ├── tempo_rss_ingest.py
│   ├── ner_extractor.py (cahya bert)
│   └── maigret_username.py
├── dynamic/
│   ├── privacy_guardrails.rego  (UU PDP enforcement)
│   ├── role_change_detection.py
│   └── publication_gate.py  (no address/NIK auto-redact)
└── compliance/
    └── compliance_stance.md  (10-point policy)
```

Imitate Palantir architecture, NOT product (per memory `palantir-anthropic-hybris`).

### 7.4 R7 e-LHKPN goldmine

> "LHKPN data accessible to the public without needing to log in. Echelon I/II officials, BUMN directors, prosecutors, DPR members, governors/mayors required to file."

URL: `https://elhkpn.kpk.go.id/`

NB-Nexus-People entity card includes `lhkpn_status` (filed/verified/late) + `wealth_trajectory` (multi-year trend). Bimo Wijayanto (DG Pajak) → LHKPN obligatory, scrape-able.

### 7.5 R7 OpenSanctions Indonesia datasets (free direct)

- `id_dttot` (Indonesian List of Suspected Terrorists, daily update)
- `id_regional_2018` (2018 Regional Head Election Results)

### 7.6 R7 Wikidata SPARQL bootstrap

```sparql
SELECT ?person ?personLabel ?roleLabel ?orgLabel ?dob WHERE {
  ?person p:P39 ?role_statement.
  ?role_statement ps:P39 ?role.
  ?role wdt:P31* wd:Q294414.  # public office Indonesia
  ?role wdt:P17 wd:Q252.      # country: Indonesia
  OPTIONAL { ?person wdt:P569 ?dob. }
  ?role pq:P108 ?org.
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
}
LIMIT 500
```

→ Bootstrap 200-500 Indonesian public officials with role + org + DOB. Effort: 4-6 hours. Quick-win.

### 7.7 R7 UU PDP 27/2022 red lines (legal)

| Activity                                       | Legal status                                |
| ---------------------------------------------- | ------------------------------------------- |
| Reading e-LHKPN public data                    | LEGAL                                       |
| Querying Daftar Caleg KPU                      | LEGAL                                       |
| Compiling internal dossier from public sources | LEGAL (internal)                            |
| Publishing pejabat home address                | **ILLEGAL — UU PDP Art. 67(2), 5y / Rp 5B** |
| Publishing pejabat NIK / KTP                   | **ILLEGAL — sensitive data UU PDP Art. 4**  |
| Cross-ref data breach DB                       | **ILLEGAL — UU PDP Art. 65**                |
| OSINT for KYC due diligence (internal)         | LEGAL — lawful interest, document           |

### 7.8 R7 Bali Zero Nexus Compliance Stance (10-point)

1. Internal-use only dossier policy
2. Source restriction: only public/official Indonesian (KPK/KPU/DPR/BPK/MA/Setkab) + sanctioned international (OpenSanctions free)
3. No data breach DB use
4. No address/NIK in dossier
5. Hunchly chain-of-custody
6. 24-month retention max
7. Privacy notice in client engagement letter
8. No automated mass scraping
9. EU clients: GDPR Art. 6(1)(b) + Art. 6(1)(f) balancing test documented
10. Bellingcat-style ethics review (Antonello + senior team) before any external output

→ First commit `domains/nexus-osint/compliance/compliance_stance.md`

### 7.9 7 sinks Nexus OSINT

1. `/whois <name>` CLI (instant card from NB-Nexus-People + recent NB-INTEL mentions)
2. Strategic intel briefing monthly
3. Editorial fodder (Curiosities NB → marketing brief candidates)
4. Cross-domain alert (Person change → relevant domain)
5. Network graph visualization (Gephi/D3)
6. **NEW**: Client Due Diligence Hunchly workflow (high-value client > €10k → Maigret + OpenSanctions + Wikidata + Hunchly capture)
7. **NEW**: OCCRP Aleph partnership exploration

### 7.10 Open questions

- **B6.a**: 2 NB-INTEL OSINT (Authorities + Curiosities) o 1 unificato?
- **B6.b**: Privacy line?
  - A. Strict open-source only (UU PDP max compliant, magri profiles)
  - B. Aggressive OSINT (LinkedIn scraping, social cross-ref) — **R7 says ILLEGAL**
  - **C. Strict + manual deep-dive on demand (R7 confirms RIGHT — UU PDP-compliant)**

---

## 8. Cross-domain federation (SYN)

### 8.1 Federation graph

```
                ┌──────────────────────────────────────────┐
                │ ORCHESTRATOR LAYER (Claude Code subagent) │
                │ Query decomposition + multi-NB routing    │
                │ Citation graph builder                    │
                └──────────────┬───────────────────────────┘
                               │
   ┌──────────────┬────────────┼────────────┬──────────────┬──────────────┐
   ▼              ▼            ▼            ▼              ▼              ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ B1       │ │ B2       │ │ B3       │ │ B4       │ │ B5       │ │ B6       │
│ Setup    │ │ Tax      │ │ Mktg     │ │ Antonello│ │ Bali     │ │ Nexus    │
│ Team     │ │ Engine   │ │ Pulse    │ │ Lab      │ │ Macro    │ │ OSINT    │
└────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
     │            │            │            │            │            │
     └────────────┴────────────┴────────────┴────────────┴────────────┘
                               │
                               ▼
                ┌──────────────────────────────────────────┐
                │ SHARED KG LAYER                           │
                │ Wikibase + Mem0 + Anthropic Memory MCP    │
                └──────────────────────────────────────────┘
                               │
                               ▼
                ┌──────────────────────────────────────────┐
                │ OBSERVABILITY: Langfuse + Phoenix         │
                │ self-hosted on Mini-Pro2                  │
                └──────────────────────────────────────────┘
```

### 8.2 Cross-domain entity overlap (federation key)

| Entity               | Owned by                            | Referenced by                                                                      |
| -------------------- | ----------------------------------- | ---------------------------------------------------------------------------------- |
| Person               | NB-Nexus-People (B6)                | B1 client profiles, B2 tax officials, B3 editorial mentions, B5 macro stakeholders |
| Organization         | NB-Nexus-Organizations (B6)         | B1, B2, B5                                                                         |
| KBLI                 | NB-3 (B1)                           | B2 tax obligations, B3 vertical content, B5 sector trends                          |
| RegulatoryDoc        | NB-3/4/5 + NB-INTEL-Regulation (B1) | B2 tax-specific subset, B5 policy events                                           |
| Property             | NB-5 (B1)                           | B2 PBB, B5 Bali real estate trends                                                 |
| ContentItem          | NB-INTEL-Press (B3)                 | B1 client briefing, B5 macro signal                                                |
| Trend                | NB-INTEL-Trends (B3)                | B1 KBLI emerging, B4 personal interest match                                       |
| Paper                | NB-INTEL-AIResearch (B4)            | B1 LegalLLM blueprint, B6 NER pipeline                                             |
| PolicyEvent          | NB-INTEL-IndonesiaPolicy (B5)       | B1, B2, B6 cabinet reshuffle                                                       |
| Obligation           | NB-3 + obligation engine (B1)       | B2 client tax deliverables                                                         |
| CoretaxIncident      | NB-INTEL-Coretax (B2)               | B1 client comm template trigger                                                    |
| CalendarBaliCeremony | NB-IndonesiaMacro (B5)              | B1, B2, B3                                                                         |

### 8.3 Stack tecnologico consolidato

```yaml
shared_infrastructure:
  llm_orchestration:
    primary: Claude OAuth (3x Max, $0 marginal)
    secondary: Gemini CLI 3.1 Pro (OAuth free)
    tertiary: Codex CLI (ChatGPT Plus)
    quaternary: DeepSeek Reasoner ($0.01/q)
    local: Ollama (qwen3.5:9b, deepseek-r1:32b, gemma4:26b, qwen2.5vl:7b, bge-m3, nomic-embed-text)

  knowledge_graph:
    backend: Wikibase self-host (Mini-Pro2)
    vector_store: Qdrant local (Pro container, R4-bis already setup)
    relational: PostgreSQL + SQLite per-machine outboxes
    federation: Wikidata SPARQL (free, federated query)

  research_agents:
    primary: gpt-researcher + gptr-mcp (LLM-agnostic, MCP-ready)
    long_form: Stanford STORM
    code_acting: smolagents (HF Open Deep Research)
    auto_research: Sakana AI Scientist v2

  memory_systems:
    procedural: Claude Skills (`.claude/skills/<domain>.md`)
    episodic: Anthropic Memory MCP
    semantic_fast: Mem0
    archival: Markdown mirror ~/Desktop/nuzantara/research/ (Git tracked)

  ingestion:
    coretax_adapter: PJAP partner (Pajakku primary, PajakExpress fallback)
    regulation_id: pasal.id MCP (40k regs) + JDIHN (1212 sites) + suryast/indonesia-gov-apis (health)
    macro_id: GDELT API (free) + ACLED + BPS WebAPI + BI + IMF + ADB
    osint_id: e-LHKPN scrape + OpenSanctions API + Wikidata SPARQL + Tempo RSS
    research: arXiv API (1/3s) + Semantic Scholar (1/s) + HN API (no limit) + HF Papers Trending
    marketing: HN Algolia API (free) + pytrends + Reddit API free tier + Wayback CDX

  observability:
    primary: Langfuse self-host (Mini-Pro2, MIT license)
    secondary: Phoenix Arize self-host
    sdk: OpenLLMetry (OTel)
    cost_routing: LiteLLM proxy

  ner_extraction:
    bahasa: cahya/bert-base-indonesian-NER (HF, free)
    custom_labels: spaCy fine-tune (Law, KBLI, KEP-PER, Money-IDR)

  scoring_personal:
    arxiv_sanity: SVM-on-tfidf (zero LLM cost)
    embeddings: bge-m3 Ollama (multilingual, local)
    rerank: qwen3.5:9b Ollama (local)
```

### 8.4 Cross-domain alert routing matrix

| Trigger                       | Source                        | Routes to                                      |
| ----------------------------- | ----------------------------- | ---------------------------------------------- |
| New PMK published             | B1 (NB-INTEL-Regulation)      | B2 (if tax), B3 (editorial brief), CRM         |
| New Coretax incident          | B2 (NB-INTEL-Coretax)         | B1 (clienti filing window), Workaround library |
| Cabinet reshuffle             | B5 (NB-INTEL-IndonesiaPolicy) | B1, B2, B6                                     |
| New tax-LLM paper             | B4 (NB-INTEL-AIResearch)      | B2 (Veronika tax stack consideration)          |
| Bali Perbup property          | B1 (NB-INTEL-Regulation-Bali) | B5, B3, CRM                                    |
| Drone Emprit sentiment spike  | B5 (NB-INTEL-Social)          | B3, B1                                         |
| GitHub trending repo          | B4 (NB-INTEL-Code)            | B4 only                                        |
| Galungan/Kuningan approaching | B5 (Bali calendar)            | B1, B2, B3                                     |
| Person controversy detected   | B6 (NB-INTEL-Authorities)     | B5, B1 (if regulator)                          |

### 8.5 Multi-LLM fallback strategy

```yaml
priority_order:
  1. Claude OAuth MAX (primary, never exhaust grazie a 3 plan)
  2. DeepSeek Reasoner ($0.01/q, sostenibile sempre)
  3. Gemini CLI (OAuth free, può 429)
  4. Codex CLI (ChatGPT Plus, può exhaust)
  5. Ollama local (async only, 30-120s latency)

graceful_degradation:
  - if Claude available → primary
  - elif DeepSeek available → use, log "Claude exhaust"
  - elif Gemini available → use, log "Claude+DS exhaust"
  - else → queue task + Telegram alert "All cloud LLM exhaust, manual review"

  Mai bloccare workflow > 30s su capacity exhaust singolo LLM.
```

### 8.6 Cost model totale

| Voce                    | Cost/anno  | Note                   |
| ----------------------- | ---------- | ---------------------- |
| Claude MAX 3x           | $3,600     | Already paid           |
| ChatGPT Plus            | $240       | Already paid (Codex)   |
| Gemini Advanced         | $0         | OAuth free CLI         |
| DeepSeek Reasoner       | ~$120      | $0.01/q × 12k queries  |
| Hunchly                 | $130       | OSINT chain-of-custody |
| Pajakku PJAP            | ~$1,200    | Rp 1.5jt/mo            |
| Brand24 (optional)      | $1,188     | Indonesia listening    |
| Exploding Topics (opt)  | $1,188     | Trends                 |
| Glimpse Pro (opt)       | $588       | Absolute search vol    |
| **TOTAL minimum**       | **$5,290** | ~€4,800/yr             |
| **TOTAL with optional** | **$8,254** | ~€7,500/yr             |

vs Anthropic API direct estimated: probably €30k+/yr for same volume → **HARD RULE compliance saves significant cost**.

---

## 9. Phased roadmap (12 months)

### Phase 0 (Week 1-2): foundations

- Fork `suryast/indonesia-gov-apis` + monthly health monitor
- pasal.id MCP integration
- OpenSanctions API setup
- Wikibase self-host on Mini-Pro2
- Langfuse + Phoenix self-host on Mini-Pro2
- OpenLLMetry SDK in 5 critical scripts
- cahya/bert-base-indonesian-NER deploy
- arxiv-sanity SVM service (Mini-Pro2)
- Bali calendar (peradnya/balinese-date-js-lib) integration

### Phase 1 (Week 3-6): per-domain genesis

- B1: NB-INTEL-Immigration + Regulation feeders LIVE (fix broken pipeline)
- B1: NB-INTEL-Regulation-Bali (4 portal)
- B1: Obligation engine (AscentAI bottom-up pattern)
- B2: NB-INTEL-Tax LIVE
- B2: NB-INTEL-Coretax LIVE (DEDICATED)
- B2: PJAP partner contract + abstraction layer
- B5: NB-IndonesiaMacro NEW + 3 NB-INTEL Macro LIVE
- B6: NB-Nexus-People bootstrap (Wikidata SPARQL → 200 entries)
- B6: compliance_stance.md commit

### Phase 2 (Week 7-12): research orchestration

- gpt-researcher + gptr-mcp install
- STORM pipeline test on NB-9 candidate topic
- B4: NB-INTEL-Code + Robotics + FrontierScience LIVE
- B4: morning Telegram digest 7am WITA
- Anthropic Memory MCP integration
- Mem0 vector + KG mirror
- B3: HN Algolia + pytrends + Reddit feeders
- B3: NB-INTEL-Trends + Competitor + Press LIVE
- C2PA Content Credentials su WR2 publish step

### Phase 3 (Week 13-24): auto-correct + cross-domain

- Drift detector all 6 domains
- Conflict detector cross-NB
- Self-coherence probe per AUTHORITY NB
- Mitochondrial value monitor extended (PR #493 → all NB)
- Decision log centralized
- Weekly self-report per dominio
- Cross-domain alert dispatcher
- Skill graduation pipeline

### Phase 4 (Month 7-12): SOTA differentiator

- LexIndoLLM blueprint per Bali Pergub/Perbup (Llama 3.2-1B fine-tune)
- Sakana AI Scientist v2 pattern per Antonello deep-dive
- Drone Emprit partnership exploratory (Ismail Fahmi)
- OCCRP Aleph access request
- IndoTax-LLM positioning (marketing differentiator)

---

## 10. Anti-patterns (12 explicit "do not")

1. **NON** fondere AUTHORITY con INTEL — distrugge signal-to-noise
2. **NON** auto-promote INTEL → AUTHORITY senza human gate (NLLP 2025: 50% auto-consolidation accuracy)
3. **NON** usare Anthropic API key in any new tool (HARD RULE CLAUDE.md)
4. **NON** scrappare aggressivamente Reddit (10k req/mo limit + non-commercial)
5. **NON** pubblicare home address/NIK pejabat (UU PDP Art. 67(2), 5y / Rp 5B)
6. **NON** costruire su Sora 2 (deprecation 24 settembre 2026)
7. **NON** usare Originality.ai per AI detection (7.3% recall su GPT-5-mini)
8. **NON** clonare Palantir come prodotto (etica) — solo architecture pattern
9. **NON** fare scraping LinkedIn massivo (TOS violation)
10. **NON** creare nuovo NB senza Genesis manifest YAML
11. **NON** lasciare cron senza warm-pin Ollama (cold model = 30s latency)
12. **NON** affidare auto-rewrite a AUTHORITY tier (sempre human approval)

---

## 11. Open questions per Antonello

Questions left open during brainstorming, awaiting decision before writing-plans skill:

| ID   | Question                                                   | Default if no answer                                                  |
| ---- | ---------------------------------------------------------- | --------------------------------------------------------------------- |
| B1.a | 4 NB-INTEL Setup (Imm+Reg+Property+Labor), 2, o 1?         | A (4 distinti)                                                        |
| B2.a | NB-INTEL-Coretax dedicated o sub-tag?                      | A (dedicated, R3 confirms)                                            |
| B2.b | Quote consistency detector (drift 0.7-1.5x market median)? | C (Sì silent, no alert)                                               |
| B3.a | NB-INTEL-Competitor (Emerhub/Cekindo/InvestinAsia)?        | B (weekly digest only)                                                |
| B3.b | WR2 auto-trigger autonomy?                                 | A (auto-brief + auto-WR2 + human review pre-publish)                  |
| B4.a | 4 NB-INTEL Antonello Lab tutti, 2, 1, o priority?          | D (priority Robotics+Science first)                                   |
| B4.b | Morning briefing daily, weekly, on-demand?                 | A (daily 7am WITA)                                                    |
| B5.a | NB-IndonesiaMacro nuova o estendere NB-8?                  | A (nuova, R6 confirms)                                                |
| B5.b | 3 NB-INTEL Macro distinti o 1 unificato?                   | A (3 distinti, R6 confirms)                                           |
| B6.a | 2 NB-INTEL Nexus o 1 unificato?                            | A (2 distinti)                                                        |
| B6.b | Privacy line strict, aggressive, on-demand?                | C (Strict + manual deep-dive on demand, R7 confirms UU PDP-compliant) |

---

## 12. Research references (5752 lines total)

Full SOTA reports in `2026-05-08-domain-mesh-research/` subfolder:

- **R1** (`r1-sota-agentic-ingestion-2026-05-08.md`, 1096 lines) — Agentic ingestion + KG + RAG + Memory + Self-improve + Multi-agent + Observability SOTA 2026
- **R2** (`r2-regulatory-monitoring-id-2026-05-08.md`, 650 lines) — Indonesian regulatory monitoring + legal AI + Bali-specific
- **R3** (`r3-djp-coretax-tax-tech-2026-05-08.md`, 674 lines) — DJP Coretax + tax-tech + IndoTax-LLM gap
- **R4** (`r4-marketing-intelligence-2026-05-08.md`, 899 lines) — Trend detection + competitor OSINT + content lifecycle 2026
- **R5** (`r5-research-agents-2026-05-08.md`, 1119 lines) — Deep research agents + OSS frameworks + GitHub intel + robotics SOTA
- **R6** (`r6-country-intelligence-id-2026-05-08.md`, 704 lines) — Country intelligence Indonesia + macro + Bali calendar + geopolitics
- **R7** (`r7-osint-entity-people-2026-05-08.md`, 610 lines) — OSINT entity tracking + people-graph + UU PDP compliance

Each report contains:

- ≥5 sources per section with URLs
- Verbatim quotes (no paraphrasing)
- "Useful for Bali Zero" 1-line assessment

---

## 13. Self-review (Spec self-review pass)

**Placeholder scan**: 11 open questions documented in §11 with defaults. No TBD/TODO unresolved.

**Internal consistency**: trust tier matrix (§1.7) referenced consistently in B1-B6 sections. Federation graph (§8.1) matches per-domain genesis statements.

**Scope check**: this is a **brainstorm output**, not implementation plan. Single document covers 6 domains because they share lifecycle pattern. Decomposition into 6 separate implementation plans happens in writing-plans skill (Phase 1+).

**Ambiguity check**: terms like "owner" defined per-domain (Antonello/Veronika/Adit/Krisna/Angel). "Authority tier" 1-5 defined in §1.3.

---

## 14. Next step

After Antonello reviews this spec:

1. If approved → invoke `superpowers:writing-plans` skill to create implementation plan for Phase 0 (foundations)
2. If changes requested → revise spec inline, re-run review loop
3. Phase 1+ each domain gets its own writing-plans → executing-plans cycle (sequential to avoid wave overload)

**Decisions still needed from Antonello**: 11 questions in §11 (defaults exist if no answer).

---

> Document end. Brainstorming session 2026-05-08 complete.
> Authored: Claude Opus 4.7 with input from R1-R7 SOTA research agents.
> Total session output: this design doc + 7 research reports = 6,500+ lines.
