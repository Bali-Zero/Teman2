# NLM Deep Research Pipeline — Mega Synthesis (Gemini + Codex + DeepSeek R1)

> Generated: 2026-03-28
> Context: Brainstorm for automated NLM Deep Research pipeline on NB-2 (Immigration & Visa Indonesia)

## Vision

- NB-2 must be a curated immigration intelligence notebook, not a dump of search results
- Scraper = fast sensor (what happened?), NLM = slow analyst (what does it mean?)
- Value is temporal intelligence tracking: WHAT → SO WHAT → WHAT'S NEXT

## Query Design (4 levels)

| Level            | Purpose                                    | Frequency       |
| ---------------- | ------------------------------------------ | --------------- |
| L1: Monitoring   | What changed?                              | Daily           |
| L2: Comparative  | How does this compare?                     | 2-3x/week       |
| L3: Predictive   | What trends are emerging?                  | Weekly          |
| L4: Cross-domain | How does visa affect tax/property/company? | Daily or weekly |

## Sequencing

- 2-3 queries/day optimal, sequential not parallel
- Order: L1 → L1b (confirm) → L2 → L4 → L3 (weekly only)
- Later queries build on earlier results

## Quality Verification

- Source tiers: .go.id (T1) > Law firms (T2) > News (T3) > Blogs (T4)
- Confidence = Authority×0.4 + Recency×0.3 + Corroboration×0.3
- ≥0.75 auto-import, 0.60-0.75 review, <0.60 discard
- Claim extraction: verify atomic claims, not whole articles

## Source Management

- Target: 40-70 active sources (25-40 canonical + 10-20 working + 5-10 master digests)
- 4 Master Documents: Change Log, Operations Status, Cross-Domain Impacts, Open Questions
- Lifecycle: INGEST → QUARANTINE → TRIAGE → ACTIVE → CONSOLIDATE → ARCHIVE
- Cadence: daily triage, weekly dedup, monthly master brief, quarterly audit

## Intel Scraper Integration

> **ARCHITETTURA RIBALTATA (decisione 2026-03-28):**
> NLM Deep Research e' UPSTREAM dell'intel scraper, NON downstream.
>
> NLM (01:00-02:20) → verified report → Intel Scraper (03:00) → War Room

- NLM gira PRIMA (01:00-02:20) e produce un brief con temi verificati + confidence scores
- Lo scraper gira DOPO (03:00) e fa il suo lavoro AUTONOMO come sempre
- Il brief NLM e' un ARRICCHIMENTO opzionale, NON una dipendenza:
  lo scraper funziona identicamente anche senza il brief
- Lo scraper puo' usare il brief per cross-validare o dare priorita' editoriale
- Il team riceve due output complementari: brief NLM + articoli scraper
- La War Room puo' scegliere temi NLM come topic giornalieri per articoli

## Failure Modes

1. Source bloat (>50, dedup >25%)
2. Old info as new (publication vs effective date)
3. Hallucination (claim vs cited text)
4. Feedback loop scraper↔NLM
5. Rate limits (budget 2-3/day)

## Testing Protocol (8 phases)

1. Baseline inventory (40 sources)
2. First L1 query + verify
3. Claim extraction + confidence scoring
4. Second L2 query
5. Third L4 query (cross-domain)
6. Optional L3 query (predictive)
7. Source lifecycle trial
8. Scraper comparison

## Source AI Contributions

### Gemini (Il Consigliere)

- Best on: sequencing strategy, source lifecycle model, scraper integration architecture
- Unique: "breaking news override" — if L1 detects major change, bump afternoon to deep dive
- Testing: detailed 8-phase protocol with acceptance criteria

### Codex GPT-5.4 (Il Soldato)

- Best on: query precision, claim extraction pipeline, source management philosophy
- Unique: "reduce uncertainty in layers" framing, 4 master documents concept
- Core principle: "raw items are temporary, master digests are durable"

### DeepSeek R1 (Il Pensatore)

- Best on: confidence scoring formula, failure mode taxonomy, success metrics
- Unique: quantified thresholds (30% duplication = stop, >85% verification accuracy)
- Critical insight: "temporal intelligence tracking" framing
