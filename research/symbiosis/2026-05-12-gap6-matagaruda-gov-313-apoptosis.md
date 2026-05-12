---
date: 2026-05-12
domain: symbiosis
client_case: SYMBIOSIS gap-closure loop · Gap 6 (MISSING FROM ORIGINAL LOOP, surfaced by NB-1 review)
sources: 2
status: follow-up
loop_branch: feat/symbiosis-loop-2026-05-12
discovered_by: NB-1 overall review 2026-05-12 04:15 WITA
---

# Gap 6 — MATA GARUDA Gov 313 sources cancro cognitivo (follow-up spec)

**Generated**: 2026-05-12 04:35 WITA · Gap surfaced by NB-1 review of PR #588 · NOT in original 5-gap loop.

## NB-1 verdict

> 3. MATA GARUDA Gov (313 sources)
>    Verdetto entrambi LLM convergente: 🔴 CARICO MORTO / CANCRO COGNITIVO.
>
> DeepSeek: "È un carico morto. Non esegue nessuna delle 6 funzioni di distillazione. Se non re-ingegnerizzato entro la prossima sprint, va rimosso dal ciclo NB e archiviato offline."
>
> Gemini: "313 fonti governative buttate in un singolo NB non sono Intelligence, sono un segnalibro glorificato. APOPTOSI IMMEDIATA (Death by Obesity)."
>
> Pipeline state attuale: zero. `cross_notebook_correlator`, `kg_linker`, `contradiction_worker`, `claim_extractor` non leggono da MATA GARUDA perché non superano filtro `source_type: government` (mancano i tags). `normalizer` + `dedup_worker` mai configurati per queste fonti (PDF non testualizzati).
>
> Consumer attuali: nessuno. Né RAG, né dispatch, né Consiglio.

## Decision tree (from NB-1)

- **Opzione A** (1 sprint, T-shirt M): far girare `normalizer → dedup → scorer → kg_linker → claim_extractor → contradiction_worker → gap_scanner` su 313 sources. Risultato: potenzialmente la più ricca fonte di entità per KG del sistema.
- **Opzione B** (1 ora): export tutte 313 in Google Drive bucket + delete da NLM. Recupera quota.

**Voto LLM convergente**: B se non c'è budget sprint, A se c'è.

## Why this gap was missed

The original 5-gap loop focused on runtime organism components (cell observatory, HGT, Consiglio, matagaruda dup). It did not survey NotebookLM content state — that surface was assumed to be operator-curated. NB-1's overall review surfaced this as a CRITICAL audit finding from 2026-05-04 that has been idle 26+ days.

## Action items (for separate PR)

1. **Decision required from Zero**: Opzione A (1-sprint revival) or Opzione B (1-hour apoptosis)
2. If Opzione B: scripted export `nlm source list <NB-MATAGARUDA-GOV>` → Drive bucket `/nuzantara-osint-archive/matagaruda-gov-313-archived-YYYY-MM-DD/` → `nlm source delete` per source
3. If Opzione A: tag enrichment pipeline `normalizer → dedup → scorer → kg_linker → claim_extractor → contradiction_worker → gap_scanner`. Effort ~5-7 person-days.

**This loop NO action**: doc-only follow-up spec, decision deferred to Zero in a separate PR.

## Refusals enforced

1. NO autonomous Opzione B execution (would delete 313 sources irreversibly)
2. NO autonomous Opzione A pipeline start (would invoke 7 workers at scale)

## Sources

1. NB-1 query response 2026-05-12 04:15 WITA (`/tmp/symbiosis-nlm-review-2026-05-12/06_overall_review.md`)
2. NB-1 reference cited_text `c8325997-2898-4958-a483-c0cf46c116ac` (MATA GARUDA Gov audit 2026-05-04)
