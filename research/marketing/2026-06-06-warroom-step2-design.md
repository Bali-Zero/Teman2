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

- **Claude quota MAX via SDK `auth_token`** (mai `api_key`) per la fusione. Token dal Keychain CLI
  (`Claude Code-credentials`, `claudeAiOauth.accessToken`, auto-refresh) — fallback env
  `CLAUDE_CODE_OAUTH_TOKEN`. ⚠️ **CONFLITTO DA RICONCILIARE**: il `CLAUDE.md` di progetto §5 dice
  ancora «Anthropic SDK BANNED. Never `from anthropic import Anthropic`». Antonello ha corretto la
  regola in questa sessione (2026-06-06): l'SDK con `auth_token` consuma la quota MAX (HTTP
  `Authorization: Bearer`, verificato in `_client.py` `auth_headers()`), distinto dal path
  `api_key`/`ANTHROPIC_API_KEY` = pay-as-you-go, **quello sì bandito**. Il global `~/.claude/CLAUDE.md`
  già riflette il dual-auth; il CLAUDE.md di progetto **va aggiornato** prima/insieme al merge di
  questo codice, altrimenti un agente che legge il repo crede l'import vietato. Code-review pre-merge
  obbligatoria anti-scambio `auth_token`↔`api_key`.
- **Law 2**: la fusione tocca news pubbliche + ground-truth NB (conoscenza operativa, non PII cliente) → cloud OK.
- **Legge 5**: lo Step 2 scrive un draft 'briefed', NON pubblica. Il drafter+review-gate restano a valle.
- **Anti-allucinazione**: conflitto news/NB → NON inventare la sintesi; status `needs_review_conflict` + riporta entrambi.
- **Idempotenza**: dedup `canonical_url` any-date, MA re-brief UPSERT se `content_hash`/`published_at` mutano (§8.5).
- **Retrocompat**: NON rinominare/cambiare-tipo i campi che il drafter legge (enrichment dict, article_summary str, live_news_reasons list).

---

## 7. Verdetto panel 4-LLM (2026-06-06) — RISOLTO

Panel girato su **Claude (subagent) + Gemini (agy) + DeepSeek V4 Pro + Codex GPT-5.5**, tutti
su M5 (Pro+Mini fleet OFFLINE quel giorno). Output verbatim:
`/tmp/step2_panel_{codex,deepseek,gemini}_m5.out`.

| Q                  | Verdetto                                                                                                                                                                               | Voti                                                               |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| Q1 granularità     | **Ibrido**: LLM scrive SOLO la prosa narrativa; provenienza/conflitto/freschezza + campi-safety (taboo/lexicon/citations/numbers) = **codice deterministico** che copia verbatim da NB | 4/4 unanime                                                        |
| Q2 staleness NB    | News = correttore sistematico dello stato corrente; **NON** bloccare sull'NB; emetti segnale staleness (`nb_snapshot_date`/`nb_staleness_days`) per cura out-of-band                   | 4/4 unanime                                                        |
| Q3 conflitto       | Flag NON basta: status separato **`needs_review_conflict`** che ESCLUDE l'item dal pickup del drafter                                                                                  | 3/4 (DeepSeek: basta flag)                                         |
| Q4 quota           | **1-by-1**, mai batch, cap esplicito 3-5/giorno, **stop pulito** su quota (output parziale utile), cache NB grounding per `canonical_url+notebook_version`                             | 4/4 unanime                                                        |
| Q5 idempotenza     | Dedup `canonical_url` **any-date** MA re-brief (UPSERT) se `content_hash`/`published_at` cambiano materialmente                                                                        | 3/4 (Gemini+DeepSeek: dedup secco — ma perdono il caso PP 20/2026) |
| Q6 quando scrivere | Separare "brief esiste" da "pronto per drafter"; gate umano dove protegge la quota                                                                                                     | convergenza (vedi §8)                                              |

**IL DIFETTO PIÙ GRAVE — trovato da 3 LLM su 4 in modo indipendente, stessa crepa da 3 lati:**

- **Codex**: «overloading `status='briefed'` to mean both "brief exists" AND "safe for drafter". Split storage from readiness.»
- **Claude**: «idempotency-key `canonical_url='briefed'` è backwards — congela la prima versione stale, salta la correzione» (= rompe il caso PP 20/2026 che motiva la fusione).
- **Gemini**: «il drafter è cieco ai rail — legge solo `enrichment`, ignora taboo_check/citations/key_numbers → slide che violano taboo / allucinano numeri».

Tradotto: lo Step 2 v1 (a) sovraccarica un solo stato con due significati, (b) persiste campi
ricchi che il drafter non legge né aggiorna. Il "dual-rail per il futuro" non protegge **oggi**.

---

## 8. Decisioni chiuse (panel + Antonello 2026-06-06)

7 decisioni, design v2:

1. **Fusione ibrida (Q1)**: l'LLM (Claude MAX, SDK `auth_token`) genera solo la prosa di
   `the_facts`/`bali_zero_take`/`thirty_second_brief`/`next_steps`/`faq`. Tutto il resto —
   provenienza, scelta news-vs-NB, freshness_override, e i campi-safety (taboo/lexicon/citations/
   numbers) — è **codice deterministico** che copia verbatim da NB. L'LLM non tocca mai una
   citazione o un numero strutturale.
2. **News-corrector (Q2)**: la news fresca corregge i fatti datati NB stale; mai bloccare; emetti
   `fusion_meta.nb_staleness_days` + `freshness_overrides[]`. NB-4 si aggiorna in un backlog separato.
3. **Conflitto → blocca (Q3)**: conflitto sostanziale (es. norma emanata sì/no) → status
   **`needs_review_conflict`**, il drafter lo salta. Solo i puliti vanno avanti.
4. **1-by-1 + cap + stop-pulito (Q4)**: processa in ordine di rilevanza, cap `WR2_BRIEF_MAX_PER_RUN`
   (default 3), check quota e stop pulito (mai mezza coda di brief falliti).
5. **Idempotenza con re-brief (Q5)**: skip se `canonical_url` già briefato in **qualsiasi** data,
   MA se ricompare con `content_hash`/`published_at` cambiato → re-brief UPSERT sulla stessa riga
   (bump `revision`). Risolve PP 20/2026.
6. **Step 2 applica i rail (Antonello)**: oltre a persistere i campi ricchi, lo Step 2 **inietta**
   taboo/citazioni/numeri DENTRO `enrichment` (il canale che il drafter già legge): `the_facts`
   incorpora le citazioni verbatim, una riga esplicita `NON usare: <taboo>`, i numeri chiave nel
   testo. **Zero modifiche al drafter** — la sicurezza arriva sul binario esistente (retrocompat).
7. **Gate umano PRIMA dello Step 2 (Antonello)**: la fusione costosa gira solo su shortlist
   **approvata**. Step 2 = on-demand su selezione umana, non automatico su tutta la shortlist.
   Protegge la quota fusione + drafter, non solo il publish (Legge 5 resta a valle).

**Stato schema (separazione storage/readiness)**: lo status `briefed` significa "pronto per il
drafter" SOLO se l'item ha passato i gate machine-readable (no conflitto bloccante, campi richiesti
presenti). Conflitto → `needs_review_conflict`. Il drafter cron consuma SOLO `briefed`.

- **Forma**: nuovo `scripts/warroom_step2_briefer.py`. Riusa pattern connessione/token Step 1.
- **Persistenza**: `brief_json` esteso (enrichment con rail iniettati + campi ricchi + fusion_meta).
- **Input**: shortlist Step 1 + flag `--approved <item_id...>` (gate umano) o `--item-id` singolo.

> Prossimo: implementazione in worktree (codice + collaudo su 1 item reale della shortlist,
> INSERT in `--dry-run`) → poi Step 3 (draft → slide, esiste già come wr2_draft_generator:
> sarà "verifica+migliora l'esistente").
