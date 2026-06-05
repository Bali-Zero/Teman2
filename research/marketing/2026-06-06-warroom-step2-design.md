---
date: 2026-06-06
domain: marketing
client_case: war-room-rebuild
sources:
  - research/marketing/2026-06-06-warroom-step2-brief-poor-vs-rich.md (confronto reale)
  - scripts/wr2_draft_generator.py (consumer brief_json — contratto verificato)
  - ~/.claude/agents/wr2-brief-interpreter.md (schema brief ricco + NB ground-truth)
  - scripts/warroom_step1_reader.py (Step 1 — produce la shortlist input)
---

# War Room — Step 2: shortlist → draft briefato (B-FUSIONE)

> Decisione Antonello: **B-fusione** — il brief fonde la NEWS FRESCA (item shortlist, fatti
> aggiornati es. PP 20/2026) col GROUNDING NB VERBATIM (brief-interpreter: citazioni, numeri,
> taboo). Risolve la discrepanza stale-vs-fresco vista sul dato reale.
> **Stato: DESIGN (no codice). Gate: panel 4-LLM prima dell'implementazione.**

---

## 0. Cosa fa lo Step 2 (una frase)

Prende un item dalla shortlist dello Step 1, lo arricchisce fondendo i fatti freschi della news
con il ground-truth verbatim di NotebookLM (via brief-interpreter), e scrive un `brief_json`
in `war_room_drafts` (status='briefed') — retrocompatibile col drafter esistente + con i campi
ricchi nuovi per il futuro.

---

## 1. Il contratto verificato (cosa lo Step 2 DEVE rispettare)

Il consumer `wr2_draft_generator.py` legge `brief_json` solo via `.get()` (verificato: zero
schema-validation, zero extra=forbid). Set chiuso che legge:

**Top-level (5)**: `article_summary` (str), `source_url` (str), `enrichment` (dict),
`live_news_reasons` (list), `live_news_score` (solo log).
**Dentro `enrichment` (6)**: `thirty_second_brief{what,why_it_matters,who,risk_level}`,
`the_facts` (str), `bali_zero_take` (str), `in_practice` (str), `next_steps` (str),
`faq` (list[{question,answer}], max 6).

**Contratto minimo non-rompere**: `article_summary` non vuoto + `enrichment` resta dict +
`live_news_reasons` resta list. **Tutto il resto è additivo e sicuro** (i campi ricchi nuovi
sono invisibili al vecchio consumer).

→ **Strategia**: lo Step 2 popola SIA `enrichment` (il drafter funziona subito) SIA i campi
ricchi nuovi (persistiti per il futuro). Doppio binario, zero rottura.

---

## 2. Architettura B-fusione (4 stadi)

```
shortlist Step 1 (item: title, canonical_url, summary, source_domain, llm.service_line)
      │  prende 1 item (top relevance non ancora briefato) — idempotenza su canonical_url
      ▼
[STADIO 1] FATTI FRESCHI: estrai dal news-item
      │  title + summary completo (dal DB intel_items, non il summary troncato shortlist)
      │  → i fatti AGGIORNATI (es. "PP 20/2026 emanata", numeri citati nell'articolo)
      ▼
[STADIO 2] GROUNDING NB: invoca wr2-brief-interpreter
      │  input: topic + domain_hint (= service_line dallo Step 1)
      │  output ricco: key_facts[], regulatory_citations_verbatim[], key_numbers[],
      │    bilingual_lexicon[], taboo_check[], archetype, tone_register, hook_angle
      │  (ground-truth da NB-4/1/5 — profondità normativa)
      ▼
[STADIO 3] FUSIONE: riconcilia fresco (news) + profondo (NB)  ← LLM (Claude MAX SDK auth_token)
      │  - i FATTI freschi della news sovrascrivono/aggiornano i fatti NB stale
      │    (es. news dice PP 20/2026 emanata > NB dice "in attesa firma")
      │  - le CITAZIONI verbatim NB restano (la news non le ha)
      │  - flag esplicito quando news e NB confliggono → "freshness_override" nel brief
      │  - genera enrichment{the_facts, bali_zero_take, next_steps, faq, thirty_second_brief}
      │    DAL materiale fuso (non solo dalla news, non solo da NB)
      ▼
[STADIO 4] PERSISTI brief_json in war_room_drafts (status='briefed')
      │  enrichment{...}        ← il drafter esistente lo legge (carosello subito)
      │  + key_facts/regulatory_citations/key_numbers/bilingual_lexicon/taboo/archetype  ← campi ricchi nuovi
      │  + article_summary/source_url/live_news_reasons  ← contratto minimo
      │  + fusion_meta{nb_sources, freshness_overrides, generated_at}  ← provenienza
      ▼  (INSERT war_room_drafts — è l'unica WRITE. Idempotenza: skip se canonical_url già briefato)
```

---

## 3. La fusione (il cuore — come riconciliare fresco vs profondo)

Il problema reale visto su PPh UMKM: news dice "PP 20/2026 emanata, Pasal 57"; NB dice "in attesa
firma Prabowo". **Regola di fusione** (LLM-guidata, esplicita nel prompt):

1. **Fatti datati/procedurali** (status di una norma, numeri, scadenze) → **la NEWS vince** se più
   recente (ha una data di pubblicazione fresca). Flag `freshness_override` per audit.
2. **Citazioni normative verbatim + numeri strutturali** (testo di legge, aliquote storiche,
   durate) → **NB vince** (ground-truth, la news non le ha verbatim).
3. **Conflitto irriducibile** (news e NB dicono cose opposte su un fatto sostanziale) → **NON
   inventare la sintesi**: riporta entrambi con flag `conflict` + privilegia la news fresca ma
   segnala. (Anti-allucinazione: meglio un brief che dice "fonti discordi" che uno che sceglie a caso.)
4. **Taboo + lexicon + archetype** → sempre da NB (non li ha la news).

---

## 4. Contratto I/O dello Step 2

**Input**: la shortlist dello Step 1 (`shortlist-YYYY-MM-DD.json`) — oppure `--item-id <uuid>`
per forzare un item, `--dry-run` (non scrive war_room_drafts), `--top N` (processa i top-N).

**Output**: righe `war_room_drafts` (status='briefed') con `brief_json` esteso:

```json
{
  "article_title": "...", "article_summary": "...(completo dal DB)...", "source_url": "...",
  "staging_id": "<intel_items.id>", "staging_type": "tax",
  "live_news_reasons": [...], "live_news_score": 0,
  "enrichment": {
    "thirty_second_brief": {"what": "...", "why_it_matters": "...", "who": "...", "risk_level": "..."},
    "the_facts": "...(fuso news+NB)...", "bali_zero_take": "...", "in_practice": "...",
    "next_steps": "...", "faq": [{"question": "...", "answer": "..."}]
  },
  "key_facts": ["...con provenienza NB-4 source ..."],
  "key_numbers": ["0.5%", "Rp 4.8 mld", ...],
  "regulatory_citations_verbatim": ["PP 55/2022 ...", "UU HPP 7/2021 Pasal ..."],
  "bilingual_lexicon": [{"id_term": "omzet", "english_assist": "gross revenue", "always_untranslated": false}],
  "taboo_check": ["no 'loophole' — la riforma lo chiude", "no 'PT PMA can use UMKM' = misinfo"],
  "archetype": "regulatory-explainer", "tone_register": "analitico/militante",
  "fusion_meta": {"nb_sources": ["NB-4 d4b2..."], "freshness_overrides": ["status norma: news PP 20/2026 > NB 'in attesa'"], "generated_at": "..."}
}
```

Il drafter legge `enrichment` + `article_summary` → carosello. I campi ricchi restano per Step 3/drafter-v2.

---

## 5. Reuse-first

| Mattone                       | Esiste?                                                                   | Esito                                                      |
| ----------------------------- | ------------------------------------------------------------------------- | ---------------------------------------------------------- |
| Schema brief ricco + query NB | ✅ `wr2-brief-interpreter` agente                                         | **[INVOCA]** — lo Step 2 lo chiama via Agent tool          |
| Forma `brief_json` + INSERT   | ✅ `wr2_topic_selector.py:637` (template) + `WarRoomDraftCreate` Pydantic | **[FORKA-E-ADATTA]** il template, estendi coi campi ricchi |
| Consumer (drafter)            | ✅ `wr2_draft_generator.py` (tollera campi extra)                         | **[NON TOCCARE]** — retrocompat, legge enrichment          |
| Lettura shortlist + DB        | ✅ `warroom_step1_reader.py` (pattern asyncpg+proxy+token)                | **[RIUSA]** il pattern connessione/token                   |
| LLM fusione                   | ✅ SDK `anthropic` auth_token (Step 1)                                    | **[RIUSA]** stesso client raw MAX                          |

Lo Step 2 è ~collante: invoca brief-interpreter + fonde via LLM + INSERT. Poco codice nuovo.

---

## 6. Vincoli (hard)

- **Claude quota MAX** (SDK auth_token, mai api_key) per la fusione. Token dal Keychain CLI (fallback env).
- **Law 2**: la fusione tocca news pubbliche + ground-truth NB (conoscenza operativa, non PII cliente) → cloud OK.
- **Legge 5**: lo Step 2 scrive un draft 'briefed', NON pubblica. Il drafter+review-gate restano a valle.
- **Anti-allucinazione**: conflitto news/NB → riporta entrambi con flag, MAI inventare la sintesi.
- **Idempotenza**: skip item con canonical_url già 'briefed' (no doppio draft). INSERT è l'unica WRITE.
- **Retrocompat**: NON rinominare/cambiare-tipo i campi che il drafter legge (enrichment dict, article_summary str, live_news_reasons list).

---

## 7. Domande aperte per il panel 4-LLM

1. **Granularità fusione**: fondere a livello di `the_facts` (un blocco) o campo-per-campo? Quanto LLM-guidata vs regola deterministica?
2. **brief-interpreter è stale**: NB-4 aveva fatti di nov 2025. Se ogni Step 2 invoca brief-interpreter, paghiamo la staleness NB ogni volta. Meglio: la news fresca come "correttore" sistematico? O aggiornare prima NB-4 (fuori scope Step 2)?
3. **Conflitto irriducibile**: il flag `conflict`/`freshness_override` è sufficiente, o serve human-in-loop quando news e NB confliggono su un fatto sostanziale (es. una norma è emanata o no)?
4. **Costo/quota**: ogni item = 1 invocazione brief-interpreter (query NB multiple) + 1 fusione LLM. Per N item della shortlist, quanto carica la rolling-window MAX 5h? Batch o 1-a-1?
5. **Idempotenza cross-day**: un topic in shortlist per 3 giorni → ri-briefato ogni giorno? Dedup su canonical_url 'briefed' in qualsiasi data, o solo oggi?
6. **Quando scrivere war_room_drafts**: lo Step 2 scrive subito (status='briefed' → il drafter cron lo prende) o aspetta un OK umano sulla shortlist? (Legge 5 è a valle, ma il draft consuma quota drafter.)

---

## 8. Decisione chiusa / da chiudere

- **Forma**: nuovo `scripts/warroom_step2_briefer.py`. Riusa pattern connessione/token Step 1.
- **Fusione**: LLM-guidata (Claude MAX) con regole esplicite §3. brief-interpreter via Agent.
- **Persistenza**: brief_json esteso (enrichment + campi ricchi + fusion_meta), INSERT 'briefed'.
- **DA DECIDERE col panel**: granularità fusione (§7.1), gestione staleness NB (§7.2), human-gate su conflitto (§7.3), batch vs 1-a-1 (§7.4), quando scrivere (§7.6).

> Prossimo: panel 4-LLM su questo design → implementazione in worktree (codice + collaudo su
> 1 item reale della shortlist, INSERT in dry-run/staging) → poi Step 3 (draft → slide, che però
> esiste già come wr2_draft_generator: lo Step 3 sarà più "verifica+migliora l'esistente").
