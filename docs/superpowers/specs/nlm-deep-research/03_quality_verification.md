# Step 3: Quality Verification — NB-2 Deep Research Pipeline

> Synthesis: Gemini + Codex GPT-5.4 + DeepSeek R1 (2026-03-28)
> Status: Brainstorm complete

---

## 1. Source Authority Hierarchy

### Consensus: 6-7 tier system with local government as first-class tier (3/3)

All 3 AI agree: local government sources (Bali) are NOT low-tier noise — they are **critical operational intelligence** that often signals changes before national sources.

### Merged Tier System

| Tier   | Name                     | Examples                                                                                                        | Authority Score | Use For                                                                      |
| ------ | ------------------------ | --------------------------------------------------------------------------------------------------------------- | --------------- | ---------------------------------------------------------------------------- |
| **T0** | National Primary Law     | UU, PP, Perpres, Permenkumham, Gazette (JDIH)                                                                   | 1.00            | Eligibility, rights, obligations, penalties, deadlines                       |
| **T1** | National Implementation  | Ditjen Imigrasi site, Surat Edaran, official circulars, evisa/molina portals                                    | 0.90            | Process flow, portal changes, official interpretations                       |
| **T2** | Regional/Local Authority | Kanwil Kemenkumham Bali, Kantor Imigrasi Ngurah Rai, Pemprov Bali, DPMPTSP Bali, Perda/Pergub/Perbup, Bali JDIH | 0.80            | Local procedures, operating hours, local regulations, regional enforcement   |
| **T3** | Local Enforcement        | Tim Pora Bali, Satpol PP Badung/Denpasar, joint operation reports                                               | 0.70            | Raids, inspections, enforcement focus, compliance intensity                  |
| **T4** | Official Social Media    | Instagram @kanaboraingurahrai, @ditaborasi, @kanwilkemenkumhambali, @pemprovbali                                | 0.60            | Announcements, operational disruptions, real-time alerts                     |
| **T5** | Reputable Press          | Bali Post, NusaBali, Tribun Bali, Kompas, Tempo, Jakarta Post                                                   | 0.45            | Early signals, enforcement reporting, interviews. Never alone for compliance |
| **T6** | Community/Unverified     | Blogs, forums, expat groups, individual social media, travel sites                                              | 0.20            | Signal only. Never in daily brief standalone                                 |

### Key Principle: Two-Axis Authority (Codex insight)

- **Legal authority axis**: T0 > T1 > T2 > T3 (for what the LAW says)
- **Operational authority axis**: T2/T3/T4 can OUTRANK T0/T1 on what actually HAPPENS at local offices

### Local-National Contradiction Rules (all 3 agree)

| Scenario                                                                                      | How to handle                                                                                                 |
| --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| **Local adds requirements** beyond national (e.g., Bali tourist levy)                         | Both correct. Tag `geographic_scope: bali_specific`. Local regulation is legally valid                        |
| **Local practice diverges** from written national law (e.g., 15-day processing vs 5-day rule) | Both factually correct. Tag `enforcement_divergence: true`. For client advisory: local practice prevails      |
| **Local contradicts** national regulation directly                                            | National prevails legally. Local gets flagged as `operational_alert`. NEVER silently discard the local source |
| **Local social media** vs local website conflict                                              | Prefer website unless social is newer and clearly operational/time-sensitive                                  |
| **Bali practice extrapolated** to Indonesia-wide                                              | NEVER generalize without national corroboration                                                               |

### Instagram as First-Class Source (Gemini + Codex agree)

In Indonesia, government offices routinely announce operational changes on Instagram 3-7 days BEFORE updating websites. Official government Instagram accounts are T4 (not T5/T6) because they are institutional, not personal.

---

## 2. Confidence Scoring Formula

### Merged Formula

```
Confidence = max(0, min(1.0,
    W_auth * S_auth + W_type * S_type + W_recency * S_recency
  + W_corr * S_corr + W_spec * S_spec + W_geo * S_geo - Penalty
))
```

### Weights (consensus across 3 AI)

| Factor             | Gemini | Codex | DeepSeek | **Adopted** | Rationale                                                    |
| ------------------ | ------ | ----- | -------- | ----------- | ------------------------------------------------------------ |
| Authority (A)      | 0.30   | 0.30  | 0.30     | **0.30**    | Unanimous                                                    |
| Corroboration (C)  | 0.25   | 0.20  | 0.25     | **0.25**    | Single-source claims are risky in ID regulatory space        |
| Specificity (S)    | 0.20   | 0.10  | 0.10     | **0.15**    | Claims with exact regulation numbers are far more verifiable |
| Source Type (T)    | 0.10   | 0.15  | 0.15     | **0.12**    | Independent signal beyond authority                          |
| Recency (R)        | 0.10   | 0.15  | 0.10     | **0.10**    | Regulations don't expire by being old                        |
| Geographic Fit (G) | 0.05   | 0.10  | 0.10     | **0.08**    | Scope alignment matters                                      |
| **Penalty (P)**    | —      | 0-35  | —        | **0-20**    | Contradictions, stale evidence, unclear jurisdiction         |

### Sub-Score Tables

**S_authority** (from tier):
| Tier | Score |
|------|-------|
| T0 (national law) | 1.00 |
| T1 (national implementation) | 0.90 |
| T2 (regional/local authority) | 0.80 |
| T3 (local enforcement) | 0.70 |
| T4 (official social media) | 0.60 |
| T5 (press) | 0.45 |
| T6 (community) | 0.20 |
Use highest available source when multiple exist.

**S_type** (document type):
| Type | Score |
|------|-------|
| Official gazette / JDIH regulation text | 1.00 |
| Official circular PDF (Surat Edaran) | 0.90 |
| Official portal notice / press release | 0.80 |
| Official webpage / FAQ | 0.70 |
| Government social media post | 0.60 |
| Named-source journalism | 0.50 |
| Legal firm analysis | 0.45 |
| Unattributed report | 0.20 |
| Forum / individual social | 0.10 |

**S_recency**:

- Regulations in force: **no decay** (score 1.0 regardless of age)
- Operational claims: exponential decay (half-life ~46 days)
  - Today: 1.00 | 7d: 0.90 | 30d: 0.64 | 90d: 0.26

**S_corroboration**:
| Sources | Score |
|---------|-------|
| 2+ from DIFFERENT tiers (cross-tier) | 1.00 |
| 3+ independent same tier | 0.90 |
| 2 independent sources | 0.65 |
| 1 source, T0-T2 | 0.50 |
| 1 source, T3-T6 | 0.25 |

**S_specificity**:
| Level | Score | Example |
|-------|-------|---------|
| Exact reg number + article + date | 1.00 | "Permenkumham 22/2023 Art. 47, effective 1 Jan 2024" |
| Reg number + general content | 0.80 | "New Permenkumham on Golden Visa published" |
| Named institution + action + date | 0.70 | "Ngurah Rai: KITAS extensions suspended 15-20 March" |
| Named institution + general statement | 0.50 | "Immigration tightening KITAS requirements" |
| Vague attribution | 0.25 | "Sources say visa rules may change" |

**S_geographic**:
| Alignment | Score |
|-----------|-------|
| Claim scope matches source scope exactly | 1.00 |
| National claim from national source | 1.00 |
| Bali claim from Bali source | 1.00 |
| National claim confirmed by local source | 0.80 |
| Bali claim from national media only | 0.60 |
| Geographic mismatch | 0.20 |

**Penalty (P)**:
| Condition | Penalty |
|-----------|---------|
| Direct contradiction with higher-tier source | -15 to -20 |
| Jurisdiction unclear | -5 to -10 |
| Source archived/deleted/screenshot only | -5 to -10 |
| Possibly superseded by newer document | -10 to -15 |

### Thresholds for Daily Brief

| Score     | Classification  | Action                                                         |
| --------- | --------------- | -------------------------------------------------------------- |
| >= 0.75   | **VERIFIED**    | Include in brief. Full detail                                  |
| 0.55-0.74 | **PROVISIONAL** | Include with explicit disclaimer. Trigger follow-up query      |
| 0.35-0.54 | **MONITORING**  | NOT in brief. Internal watch list. Escalate if unresolved >48h |
| < 0.35    | **UNVERIFIED**  | NOT in brief. Log for pattern analysis only                    |

### Hard Gates (override score)

- T6-only source (forums) → NEVER reaches brief regardless of score
- LEGAL_CHANGE without JDIH/official confirmation → capped at PROVISIONAL
- ENFORCEMENT_ACTION from single news source → capped at PROVISIONAL
- Visa eligibility/fee/deadline claim → must have T0-T2 source for VERIFIED

---

## 3. Claim Extraction Pipeline

### Atomic Claim Definition

Single, independently verifiable assertion with: one predicate, temporal bound, geographic bound, actor specified.

### Claim Categories

| Category                 | What it is                         | Example                                                       |
| ------------------------ | ---------------------------------- | ------------------------------------------------------------- |
| **LEGAL_CHANGE**         | New/amended regulation             | "Permenkumham X/2026 changes B211A max stay to 120 days"      |
| **OPERATIONAL_CHANGE**   | Same law, different practice       | "Ngurah Rai now requires original degree certs for ITAS"      |
| **ENFORCEMENT_ACTION**   | Specific event                     | "Tim Pora swept 30 businesses in Canggu, 12 deportation recs" |
| **ENFORCEMENT_PATTERN**  | Repeated trend                     | "Third report this week of KITAS delays at Ngurah Rai"        |
| **POLICY_SIGNAL**        | Forward-looking official statement | "Dirjen says E33G regs being finalized for Q3"                |
| **PROCEDURAL_UPDATE**    | Forms/systems/fees change          | "E-visa portal now requires biometric page upload"            |
| **LOCAL_REGULATION**     | Perda/Pergub affecting compliance  | "Pergub Bali new foreign worker supervision rules"            |
| **DOCUMENT_REQUIREMENT** | Docs added/removed/changed         | "Additional company docs for investor KITAS renewals"         |
| **FEE_CHANGE**           | Official tariff changes            | "PNBP fee increase for KITAS extension"                       |
| **UNCLASSIFIED_SIGNAL**  | Watch bucket                       | "Vague reports of processing changes"                         |

### Partially Verifiable Claims

1. Decompose into atomic sub-assertions
2. Score each independently
3. Overall confidence = **minimum** of sub-assertions (conservative: weakest link)
4. Tag which parts verified, which not

### Claim Metadata — CANONICAL SCHEMA (merged from all 3)

> **CANONICAL CLAIM SCHEMA (review fix 2026-03-28):**
> This is the single source of truth for claim structure. All other files (04 source_registry,
> 05 handoff, 06 recovery, 07 tests) MUST use these field names:
>
> - `source_ids` (array of source IDs, NOT `source_id` singular)
> - `regulation_ref` (string|null — regulation number if applicable)
> - `assertion_direction` (string — controlled vocabulary: requirement_added, requirement_removed,
>   fee_increased, fee_decreased, deadline_extended, deadline_shortened, scope_expanded, scope_narrowed,
>   process_changed, enforcement_increased, enforcement_decreased, status_changed)

```json
{
  "claim_id": "NB2-2026-03-28-001",
  "claim_text": "...",
  "claim_text_id": "... (Bahasa)",
  "category": "OPERATIONAL_CHANGE",
  "confidence_score": 0.72,
  "confidence_class": "PROVISIONAL",
  "geographic_scope": "LOCAL_OFFICE: Ngurah Rai",
  "affected_visa_types": ["KITAS_RPTKA"],
  "affected_services": ["work_permit", "visa_extension"],
  "effective_date": "2026-03-20",
  "announcement_date": "2026-03-25",
  "extraction_date": "2026-03-28T01:52:00+08:00",
  "source_chain": [
    {
      "name": "Instagram @kanaboraingurahrai",
      "tier": 4,
      "type": "gov_social",
      "url": "...",
      "quote": "..."
    },
    {
      "name": "NusaBali",
      "tier": 5,
      "type": "news",
      "url": "...",
      "quote": "..."
    }
  ],
  "sub_scores": {
    "authority": 0.6,
    "type": 0.6,
    "recency": 0.9,
    "corroboration": 1.0,
    "specificity": 0.7,
    "geographic": 1.0
  },
  "source_ids": ["src_abc123", "src_def456"],
  "regulation_ref": "Permenkumham 22/2023",
  "assertion_direction": "requirement_added",
  "verification_gaps": [
    "No backing Surat Edaran found",
    "Other Bali offices not confirmed"
  ],
  "enforcement_divergence": true,
  "urgency": "THIS_WEEK",
  "action_recommendation": "Advise KITAS clients at Ngurah Rai to bring originals",
  "follow_up": "Query JDIH for backing document next session",
  "expires": "2026-04-04"
}
```

---

## 4. Cross-Reference Verification (4 stages)

| Stage                    | Source                                    | What to check                      | Action                                                  |
| ------------------------ | ----------------------------------------- | ---------------------------------- | ------------------------------------------------------- |
| **1. NB-2 Internal**     | Existing 40 sources                       | Consistency with known regulations | Confirm/contradict/silent                               |
| **2. Scraper Archive**   | Intel scraper history (PostgreSQL/Qdrant) | Previously reported?               | If yes: not new intelligence. Tag `previously_reported` |
| **3. Government Portal** | JDIH, imigrasi.go.id, oss.go.id           | Can we find the actual document?   | Best-effort, max 5 checks/run. Not blocking             |
| **4. Local Source**      | Bali local feeds, Instagram, local news   | Corroboration from local ground    | Cross-reference Tim Pora, Ngurah Rai social             |

### Minimum Standards for Brief Inclusion

| Classification               | Minimum Source Requirement                                                            |
| ---------------------------- | ------------------------------------------------------------------------------------- |
| VERIFIED                     | 2+ independent sources, at least one T0-T2. OR: single T0 source (gazette)            |
| PROVISIONAL                  | 1 source T0-T4 with specific details. Max 2 verification gaps. Must trigger follow-up |
| Any compliance-affecting rec | MUST have T0-T2 evidence                                                              |
| T6-only source               | NEVER in brief                                                                        |

---

## 5. Local Source Monitoring Strategy (Bali)

### Priority 1 — Check every pipeline run (daily)

| Source                     | Platform                      | What to monitor                                  |
| -------------------------- | ----------------------------- | ------------------------------------------------ |
| Kantor Imigrasi Ngurah Rai | Instagram @kanaboraingurahrai | Operational changes, schedules, new requirements |
| Ditjen Imigrasi            | Instagram @ditaborasi         | National announcements affecting Bali            |
| Kanwil Kemenkumham Bali    | Website + social media        | Regional directives, enforcement                 |
| DPMPTSP Bali               | dpmptsp.baliprov.go.id        | Licensing changes, OSS local requirements        |

### Priority 2 — 2-3 times/week

| Source                   | Platform                 | What to monitor                       |
| ------------------------ | ------------------------ | ------------------------------------- |
| Pemprov Bali             | baliprov.go.id           | Pergub, Perda, governor statements    |
| Kantor Imigrasi Denpasar | Social media             | Separate jurisdiction from Ngurah Rai |
| Dinas Tenaga Kerja Bali  | disnaker.baliprov.go.id  | RPTKA/IMTA enforcement                |
| Tim Pora Bali            | Via Kanwil or local news | Joint enforcement operations          |

### Priority 3 — Weekly

| Source                    | Platform                                          |
| ------------------------- | ------------------------------------------------- |
| Kantor Imigrasi Singaraja | Social media (North Bali)                         |
| Satpol PP Badung/Denpasar | Social media / news (Canggu/Seminyak enforcement) |
| DPRD Bali                 | baliprov.go.id/dprd (pending legislation)         |

### Local News Outlets (ranked)

| Outlet             | Reliability | Immigration Relevance                              |
| ------------------ | ----------- | -------------------------------------------------- |
| Bali Post          | High        | High — oldest Bali newspaper                       |
| NusaBali           | High        | High — strong govt/enforcement reporting           |
| Tribun Bali        | Medium      | Medium-high — large network, sometimes sensational |
| Radar Bali         | Medium      | Medium — business/investment                       |
| Antara Bali bureau | Medium      | Medium — official wire service                     |

### Divergence Detection Rules

Flag automatically when:

- Local office states requirement NOT in national rule → `local_additional_requirement`
- Local enforcement stricter than written guidance → `enforcement_divergence`
- Local social announces change not on portal → `communication_lag`
- Local regulation affects business while immigration status unchanged → `local_regulation`
- Possible overreach by local office → `possible_overreach` (manual review only)

---

## 6. Verified Claim Output Format

### Daily Brief Structure (Codex insight)

Separate into 3 sections: **LAW** | **OFFICE OPERATIONS** | **ENFORCEMENT SIGNALS**
Most verification failures happen when these are mixed.

### Claim Record Format

```
══════════════════════════════════════════════════
CLAIM: [claim_id]
══════════════════════════════════════════════════
STATUS:     [VERIFIED | PROVISIONAL]  CONFIDENCE: [0.XX] ████████░░
CATEGORY:   [LEGAL_CHANGE | OPERATIONAL_CHANGE | ...]
URGENCY:    [IMMEDIATE | THIS_WEEK | MONITOR]
GEOGRAPHIC: [NATIONAL | BALI | LOCAL_OFFICE: name]

CLAIM (EN): [text]
CLAIM (ID): [text]

AFFECTED: Visa types: [...] | Services: [...] | Effective: [date]

SOURCE CHAIN:
  1. [Tier X] [type] — [name] (URL, accessed date)
     Quote: "..."
  2. [Tier Y] [type] — [name] (URL, accessed date)

SCORE: Auth [0.XX] | Type [0.XX] | Recency [0.XX] | Corr [0.XX] | Spec [0.XX] | Geo [0.XX]

GAPS: [what's missing for full verification]
DIVERGENCE: [YES/NO — if local practice differs from national]
ACTION: [specific recommendation for Bali Zero]
FOLLOW-UP: [next verification step]
EXPIRES: [date]
══════════════════════════════════════════════════
```

### 3 Examples at Different Confidence Levels

**Example 1: VERIFIED (0.91) — National Legal Change**

- Permenkumham 3/2026 reduces B211A max stay from 180→120 days, effective April 15
- Sources: JDIH gazette (T0) + Kemenkumham press release (T1) + Jakarta Post (T5)
- Action: Notify all B211A clients, update Zantara knowledge base

**Example 2: PROVISIONAL (0.63) — Local Operational Change**

- Ngurah Rai now requires original degree certificates for ITAS-RPTKA extensions
- Sources: Instagram @kanaboraingurahrai (T4) + NusaBali article (T5)
- No backing Surat Edaran found. Possible enforcement divergence
- Action: Advise KITAS clients at Ngurah Rai to bring originals. Do NOT update general knowledge base

**Example 3: PROVISIONAL (0.57) — Enforcement Action**

- Tim Pora swept 30 businesses in Canggu, March 22-24, deportation proceedings
- Sources: Tribun Bali (T5) + Bali Post (T5). No official Tim Pora press release
- Action: Alert Canggu/Berawa clients to ensure compliance docs current. Watchlist only

---

## Source AI Contributions

### Gemini — Best on architecture + examples

- 6-tier hierarchy with explicit local government tiers
- Full confidence formula with exponential recency decay
- 3 detailed worked examples (verified, provisional, enforcement)
- Claim metadata schema with 25+ fields
- Instagram as first-class source justification

### Codex — Best on discipline + separation

- 7-tier system (T0-T6) with clearest tier boundaries
- Penalty system (-P) for contradictions/stale evidence
- "Separate law / operations / enforcement in brief" insight
- 10 claim categories (most granular)
- Hard gate: compliance claims need T0-T2, period
- Divergence classification: operational, documentation, enforcement, communication lag, overreach

### DeepSeek — Best on formulas + simplicity

- Cleanest formula: same weights, simplest sub-scores
- R = max(0.1, 1 - days/30) for operational claims
- C = min(1, sources/3) — elegant simplicity
- Social media T4 must be followed by formal publication within 48h for high-confidence
- Geographic scope scoring most explicit
