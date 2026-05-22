---
date: 2026-05-23
domain: operations
client_case: internal — Bali Zero chat-data intelligence (WhatsApp corpus → CRM/RAG/forecasting)
status: APPROVE_WITH_AMENDMENTS (4-LLM gate 2026-05-23) — amendments incorporated, pre Antonello approval
sources: 4-LLM panel (Gemini 3.1 Pro + Codex GPT-5.5 + DeepSeek V4 Pro + NB-6 ground-truth) + WebSearch (Gong/RAG/privacy 2026) + on-disk corpus census
supersedes_partial: research/marketing/2026-05-16-whatsapp-conversation-intelligence.md (industry pattern + UU PDP base)
complements: research/operations/2026-05-23-wa-mirror-dashboard-discovery.md (UI layer, different scope)
---

# Chat-Data Intelligence per Nuzantara — Prima Spec

## 0. Domanda

Come può Bali Zero sfruttare la potenza dei dati delle proprie chat di business (conversazioni
collaboratori↔clienti/lead **+** chat interne team↔team) per creare valore corporate durabile,
sul sistema Nuzantara attuale, dentro i vincoli UU PDP 27/2022 e Symbiosis Law 2 (OSINT/dati locali)?

## 1. TL;DR

- **L'asset esiste già su disco e non è sfruttato**: **109 conversazioni** WhatsApp esportate, ~13.540
  immagini, ~11.275 PDF, ~7.721 vCard, ~5.3 GB, span 2023-08 → 2026-05 (~3 anni). È _dark data_ —
  il bridge live `wa-mirror` per design NON fa backfill di questo storico (README riga 119).
- **Convergenza 4/4 LLM sul "wedge"**: il primo move a più alto ROI è un **historical ingestion
  pipeline offline** che trasforma quel dark data in record CRM ricchi + memoria RAG interrogabile,
  girando **interamente in locale** (Ollama su Mini-Pro2) per soddisfare UU PDP.
- **Il valore non è un chatbot**: è (a) **memoria corporate unificata** — quando un cliente scrive
  ad Adit che non l'ha mai sentito, il sistema gli mostra un dossier 3-bullet della storia con
  Bali Zero; (b) un **case ledger** (aide accuracy-checked, NON sostituto della raw chat come
  evidenza) — cosa è stato richiesto/inviato/promesso/prezzato/mancante per ogni pratica;
  (c) forecasting da promesse di pagamento (fragile, da validare) + geo-temporal EXIF (da verificare,
  WhatsApp strippa EXIF — vedi §11 panel P1).
- **Vincolo legale duro (NB-6 ground-truth)**: AI su dati specifici (passaporti, bank) larga scala
  attiva **DPIA + DPO + ROPA** non opzionali. Retention a **2 tier** (NB-6, nessuna contraddizione):
  Customer 5y assoluto / Lead cancellazione a scopo esaurito (~12 mesi). Sanzioni: admin 2% fatturato
  - penale fino 6 anni / IDR 500jt + NIB freeze via OSS flag. **Caveat panel**: la redazione regex
    NON copre le immagini → serve pipeline OCR-FIRST (§4 SILVER); tutto locale.

## 2. Censimento del corpus reale (on-disk, 2026-05-23)

| Asset                        | Volume      | Note                                                            |
| ---------------------------- | ----------- | --------------------------------------------------------------- |
| Conversazioni `_chat.txt`    | **109**     | client-facing (Ari visa, Surya company), 1:1 + gruppi familiari |
| Immagini (jpg/webp/png/heic) | ~13.540     | passaporti, selfie, foto ville/proprietà, screenshot bonifici   |
| PDF                          | ~11.275     | akta PT PMA, invoice, bank statement, e-visa, LKPM              |
| vCard (vcf)                  | ~7.721      | grafo contatti/referral (asset di rete sottovalutato)           |
| Audio voice (opus)           | 88          | note vocali — trascrivibili (whisper local)                     |
| Excel/Word                   | ~40         | tax/LKPM, materiale interno team                                |
| **Totale**                   | **~5.3 GB** | span 2023-08 → 2026-05                                          |

Fonti (4 batch `chat_history/` + 362MB batch + standalone):

- `~/Downloads/chat_history/drive-download-...142735` → 20 conv
- `~/Downloads/chat_history/drive-download-...142751` → 29 conv
- `~/Downloads/chat_history/drive-download-...142807` → **51 conv** (era zip-of-zips, estratto in `_extracted/`)
- `~/Downloads/chat_history/drive-download-...142858` → **2 conv** (idem)
- `~/Downloads/wa-corpus-extracted/` (362MB batch) → 4 conv
- Susiane + YOPO standalone → 3 conv
- `~/Desktop/WhatsApp Chat - INVOICE BALI ZERO` (4.3 GB allegati, manca `_chat.txt`)
- `~/Downloads/TAX DEPARTMENT...` (workspace interno per-membro: Angel/Dea/Veronika/Kadek/Dewa Ayu + LKPM)

Due nature di dato distinte:

- **Client-facing** (chat con clienti/lead): valore = memoria + ledger + forecasting. PDP-scope alto.
- **Internal team** (TAX DEPARTMENT, gruppi interni): valore = distillazione SOP, tribal knowledge di
  Ari/Surya, process mining. PDP-scope su dipendenti (legitimate interest + Peraturan Perusahaan).

## 3. Sintesi 4-LLM panel (convergente / divergente)

| Tema             | Gemini                                | Codex                                                    | DeepSeek                                           | NB-6 (legge)                 | Verdetto                              |
| ---------------- | ------------------------------------- | -------------------------------------------------------- | -------------------------------------------------- | ---------------------------- | ------------------------------------- |
| **Wedge**        | offline backfill locale               | offline dossier builder read-only                        | bulk ingest → CRM+RAG                              | —                            | **4/4 identico**                      |
| **Architettura** | Shadow CRM + intel lake + ghost draft | medallion bronze/silver/gold + GraphRAG + process mining | knowledge graph + lead scoring + compliance shield | —                            | medallion + estrazione locale + graph |
| **PII**          | Ollama local, no PII in Qdrant        | Presidio redaction + audit                               | redazione **deterministica PRE-LLM**               | DPIA+DPO+ROPA obbligatori    | redact prima dell'LLM, tutto locale   |
| **Angle unico**  | "Omniscient Handoff Dossier"          | "case ledger difendibile"                                | cash-flow da promesse + EXIF journey               | —                            | complementari → tutti in spec         |
| **Anti-pattern** | RAG poisoning pricing stale           | hallucination → citation+confidence+human review         | schema validation + hash dedup                     | objection automated decision | tag legacy + ground-truth separato    |

## 4. Architettura proposta — medallion locale + funnel su organi Nuzantara

```
BRONZE (immutable raw, local Pro/Mini, encrypted-at-rest)
  109 _chat.txt + 13.5k img + 11k pdf + 7.7k vcf
    → archivio immutabile con SHA-256 per file (dedup + provenienza + anti-tamper)
    → NESSUN LLM tocca questo layer

SILVER (extraction, 100% LOCALE — Symbiosis Law 2)
  parser deterministico WA (timestamp/sender/attachment refs)
    TESTO:
    → redaction DETERMINISTICA (regex passport/NIK/IBAN/phone → token) PRIMA dell'LLM testo
    → testo redatto → Ollama qwen3.5:9b → JSON {client, service, quote, deadline, doc_ref}
    IMMAGINI (vision PII paradox fix — panel P1):
    → la redaction-regex NON si applica a un'immagine; serve pipeline OCR-FIRST:
       qwen2.5vl:7b (o tesseract local) OCR → testo grezzo → redaction regex → poi estrazione campi
    → l'output del vision model (MRZ/IBAN estratti) è SUBITO tokenizzato, mai persistito raw in chiaro
    → log esplicito di cosa il vision model riceve (DPIA audit trail)
    VOICE:
    → opus → whisper local → transcript → redaction → estrazione
    → bge-m3 (local) re-embed per RAG locale
  Tabelle PG nuove: chat_events, chat_entities, chat_attachments, chat_commitments, chat_case_timeline
    → ogni fact ha source_span (file + riga) + confidence + needs_review flag
    → match phone/vcf → clients.id SOLO con (phone E.164 normalizzato + name match) + threshold;
      mai phone-only (numeri riciclati/condivisi → false-positive merge di ledger distinti — panel P2)
    → NULL = prospect (NON scartare)

GOLD (surfaces, valore consegnato — realismo flaggato post-panel)
  1. Omniscient Handoff Dossier  → CRM UI: 3-bullet client recap on inbound (continuità) [REALE]
  2. Case Ledger                 → per practice: requested/sent/promised/priced/delayed/MISSING
       [REALE ma è aide accuracy-checked, NON court-ready record — la raw chat resta l'evidenza]
  3. Missing-doc queue + stale-promise alerts → EventBus → Telegram [REALE]
  4. Lead-stage classifier + scoring → client_scoring (da 3 anni outcome storici) [REALE]
  5. Cash-flow forecast da payment-intent ("trasferisco 50jt lunedì") → expected_close
       [FRAGILE — false-positive (ironia/tentativo) gonfiano il forecast; serve reliability
        weighting + reconciliation core-banking; NON presentare come proiezione finanziaria live]
  6. SOP candidates da chat interne → human approval → RAG team (tribal knowledge) [REALE]
  7. Geo-temporal journey da EXIF → site-visits→deposit funnel
       [❌ DECLASSATO 2026-05-23 — verifica empirica su 250 img campionate del corpus (PIL):
        1/250 ha EXIF (0%), 0/250 GPS, 0/250 DateTimeOriginal. WhatsApp strippa i metadati.
        Surface MORTA: nessun moat geo-temporale dal corpus. Timestamp utilizzabile = solo
        quello del messaggio WA (riga _chat.txt), non EXIF foto.]
```

### Funnel su organi esistenti

| Organo Nuzantara                          | Ruolo nella pipeline                                                                                      |
| ----------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `apps/wa-mirror`                          | live capture (già attivo) — la pipeline storica è un importer SEPARATO, non lo tocca                      |
| PG `whatsapp_message_context`             | append rows live; nuove tabelle silver affiancate                                                         |
| Qdrant (93k vec, embed FROZEN)            | **NON** mescolare PII chat nel corpus 1536d esistente → nuova collection locale `chat_history` con bge-m3 |
| Ollama (qwen3.5:9b, qwen2.5vl:7b, bge-m3) | TUTTA l'estrazione — zero cloud LLM su dati CRM/PDP                                                       |
| PricingTool                               | **validator** dei prezzi estratti dalle chat (non source) — anti-poisoning                                |
| EventBus PG NOTIFY                        | alert missing-doc / stale-promise / lead-score                                                            |
| intel lake                                | pattern aggregati NON-PII (mai dati cliente)                                                              |
| NB-2/3/4/6                                | ground-truth attuale per generation (separato dallo storico legacy)                                       |

## 5. Il wedge (primo move) — Historical Ingestion Pipeline, read-only

Perché: sfrutta l'asset che `wa-mirror` non può backfillare, gira in locale, e crea il
test-set per ogni automazione futura. **Wall-time NON è "ore"**: ~13.5k immagini × vision model
su Mini-Pro2 24GB = realisticamente **giorni**, non ore (panel P2). Serve batching + queue +
memory guardrail + benchmark before/after su campione. Sequenza:

1. Bronze: copia immutabile + SHA-256 di ogni file (no LLM).
2. Parser deterministico dei 56 `_chat.txt` (sender/timestamp/attachment refs).
3. Redazione PII deterministica (regex) PRIMA di qualsiasi LLM.
4. Estrazione locale (qwen3.5:9b testo, qwen2.5vl:7b immagini) con `source_span` + `confidence`.
5. Match a CRM via phone/vcf; prospect se NULL.
6. Output: timeline per-persona/per-pratica + needs-review queue. **Read-only** — nessun auto-write
   distruttivo su CRM, ogni fact passa human-review prima di promozione a campo CRM autoritativo.

Outcome immediato: CRM passa da sparso a ricco di 3 anni di contesto, prospect backlog recuperato,
training corpus per scoring/forecasting, "what did we promise this client?" risolto.

## 6. Compliance UU PDP 27/2022 (NB-6 ground-truth) — gating

| Item                            | Requisito                                                                                                | Azione spec                                                                                                                                                                                                                                                       |
| ------------------------------- | -------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Lawful basis clienti            | contractual obligation (Art 20(2)(b))                                                                    | clausola engagement letter + WA auto-reply 1×                                                                                                                                                                                                                     |
| Lawful basis prospect           | consent o legitimate interest (Art 20(2)(f))                                                             | LIA documentata 1×, riusabile                                                                                                                                                                                                                                     |
| Chat dipendenti                 | legitimate interest **+ Peraturan Perusahaan + notice**                                                  | clausola PKWT (già `apps/wa-mirror/docs/PKWT_CLAUSE.md`) + notice                                                                                                                                                                                                 |
| Specific personal data          | passaporti/bank = tier alto Art 4(2) — DeepSeek P1: forse serve CONSENT esplicito, non basta contractual | DPIA deve decidere se MRZ-extraction richiede consent; legal opinion prima di toccare immagini                                                                                                                                                                    |
| AI large-scale                  | **DPIA obbligatorio**                                                                                    | DPIA prima di attivare la pipeline                                                                                                                                                                                                                                |
| DPO                             | obbligatorio (systematic monitoring of specific data)                                                    | nominare DPO (Antonello o delega)                                                                                                                                                                                                                                 |
| ROPA                            | record processing activities                                                                             | template APPDI/APINDO, file `docs/compliance/`                                                                                                                                                                                                                    |
| **Retention (RISOLTO da NB-6)** | NESSUNA contraddizione — servono **2 tier separati**                                                     | **Customer Data**: min 5y assoluto (KYC/fiscale/LKPM settoriale). **Lead Data** (prospect non-convertiti): NO retention settoriale → vince storage limitation → **cancellare** quando scopo esaurito (es. 12 mesi). Tenere prospect 5y VIOLEREBBE minimizzazione. |
| Chat dipendenti storiche        | LIA retroattiva su 2023-25 = problema (Gemini P1)                                                        | F0 serve strategia legale specifica per lo STORICO interno, non solo clausola PKWT futura                                                                                                                                                                         |
| Diritti subject                 | objection ad automated decision                                                                          | nessun auto-write CRM senza human-in-loop                                                                                                                                                                                                                         |

## 7. Top 3 rischi + mitigazione

1. **Legale** — processare passaporti/bank con AI senza basi → penale fino 6 anni + NIB freeze.
   _Mit._: DPIA+DPO+ROPA prima; redazione PII deterministica pre-LLM; tutto locale (Law 2); RBAC + encrypt-at-rest.
2. **Tecnico** — hallucination estrazione + linkage stale (pricing 2023 spacciato per attuale).
   _Mit._: JSON-schema validation (regex passport/phone), hash dedup, confidence threshold + human-review
   queue, tag `legacy_data:true` + timestamp, PricingTool/NB come ground-truth attuale separato.
3. **Org** — cattura su numeri personali = percepita come sorveglianza → boicottaggio team.
   _Mit._: co-design con Ari/Krisna, opt-out su thread sensibili, ZERO auto-reply, dashboard aggregata
   non-PII, framing "memory aid" + prototipo handoff dossier che fa risparmiare 15 min/cliente.

## 8. Cosa gli altri mancano (angle unici da preservare)

- **Codex** — _case ledger legalmente difendibile_ > sales analytics. Per un'agenzia visa, prevenire
  UNA promessa sbagliata vale più di qualsiasi analytics di vendita. Questo è il vero core value.
- **Gemini** — _omniscient handoff dossier_: continuità percepita dal cliente indipendente dall'agente.
- **DeepSeek** — _cash-flow da promesse di pagamento_ + _geo-temporal journey da EXIF_ (moat fisico:
  quante site-visit prima del deposit, silenzio 14gg post-visita = churn signal). Nessun SaaS CRM lo cattura.

## 9. Roadmap (fasi, non stime orarie definitive)

| Fase | Contenuto                                                                   | Gate                                              |
| ---- | --------------------------------------------------------------------------- | ------------------------------------------------- |
| F0   | DPIA + DPO + ROPA + LIA + retention 2-tier + EXIF check + consent decision  | **legal gate — blocca SILVER/GOLD**               |
| F1   | Bronze immutable + SHA-256 + parser deterministico                          | no LLM/no PII → **può partire in parallelo a F0** |
| F2   | Silver: redazione PII + estrazione locale (testo+vision+voice) + tabelle PG | smoke su 5 conv pilota                            |
| F3   | Match CRM + prospect backlog + needs-review queue                           | human-review prima di promozione                  |
| F4   | Gold #1 Handoff Dossier + #2 Case Ledger (i due core value)                 | CRM UI                                            |
| F5   | Gold #3-7 (alerts, scoring, forecast, SOP, EXIF)                            | incrementale                                      |

## 10. Checklist azione

P1 bloccanti (panel) — risolvere PRIMA di scrivere codice:

- [ ] **F0 legal gate**: DPIA + nomina DPO + ROPA + LIA prospect + clausola engagement/PKWT.
- [ ] **Retention 2-tier** (NB-6): Customer Data 5y assoluto; Lead Data cancellazione a scopo
      esaurito (es. 12 mesi). Due policy distinte + pruning script prospect.
- [ ] **Consent per specific data**: DPIA decide se MRZ/bank-extraction richiede consent esplicito
      (DeepSeek P1) — legal opinion prima di toccare qualsiasi immagine passaporto.
- [ ] **Vision PII fix**: pipeline OCR-FIRST (qwen2.5vl/tesseract → testo → redact → estrazione),
      output tokenizzato subito, mai raw in chiaro, log DPIA di cosa il vision model riceve.
- [ ] **EXIF empirical check**: verificare su campione se le immagini conservano EXIF/GPS (WhatsApp
      le strippa). Se assenti → declassare Gold #7, non è un moat.
- [ ] **LIA storico dipendenti**: strategia legale per chat interne 2023-25 (no notice retroattivo).

P2/P3:

- [ ] Bronze importer + SHA-256 (read-only, no LLM) — può partire in parallelo a F0 (no PII processing).
- [ ] Batching + queue + memory guardrail Mini-Pro2; benchmark before/after (wall-time = giorni non ore).
- [ ] Phone match: E.164 normalize + name match + threshold, MAI phone-only.
- [ ] Schema PG silver: chat_events, chat_entities, chat_attachments, chat_commitments, chat_case_timeline.
- [ ] Qdrant collection locale `chat_history` con bge-m3 (MAI nel corpus 1536d frozen).
- [ ] PricingTool come validator dei prezzi estratti (anti-poisoning) + tag legacy_data.
- [ ] Gold #1 Handoff Dossier + #2 Case Ledger come primi deliverable (i due core value REALI).
- [ ] Cash-flow (#5): reliability weighting, NON proiezione finanziaria live.
- [ ] Case Ledger (#2): UI disclaimer — aide accuracy-checked, NON sostituto della raw chat come evidenza.

## 11. Panel review verdict (4-LLM gate, 2026-05-23)

Fan-out: Gemini 3.1 Pro + DeepSeek V4 Pro + NB-6 ground-truth. **Codex escluso** (OAuth ChatGPT Pro
token scaduto mid-run — non re-loggato per non bloccare il gate; 3 reviewer sostanziosi + ground-truth
sufficienti).

| Reviewer | Verdetto                                                                                |
| -------- | --------------------------------------------------------------------------------------- |
| Gemini   | **REJECT** (pesa i 2 bug fatali: vision PII paradox + EXIF fantasma)                    |
| DeepSeek | **APPROVE_WITH_AMENDMENTS** (architettura coerente, fix obbligatori pre-ingestion)      |
| NB-6     | conferma retention 2-tier, nessuna contraddizione; specific data forse richiede consent |

**Sintesi**: la DIREZIONE è approvata (local-first + medallion + wedge storico = corretti). La
FORMULAZIONE attuale aveva 5 P1: (1) vision PII paradox, (2) EXIF dati-fantasma, (3) retention
indifferenziata, (4) consent specific-data, (5) LIA retroattiva dipendenti. Tutti incorporati sopra.
**Verdetto consolidato: APPROVE_WITH_AMENDMENTS** — gli amendment sono in spec; F0 legal gate +
EXIF empirical check sono i due gate che decidono se il progetto procede come scritto.

## Sources

- 4-LLM panel: `/tmp/panel-{gemini,codex,deepseek}.txt` + NB-6 query (UUID 85207af3-352f-4554-8d2a-18f42cc541ba)
- NB-6 verbatim: UU PDP lawful basis (contractual/consent/legitimate interest), retention 5y,
  sanzioni admin 2% + penale 4-6y/IDR200-500jt, DPIA+DPO+ROPA per AI large-scale specific data.
- WebSearch 2026: Gong conversation intelligence (call/deal/portfolio layers), Uber Genie (70k Slack
  Q, 13k eng-hours saved), GraphRAG/agentic RAG, privacy (fine-tuning su PII = memorization risk →
  preferire RAG a fine-tuning), self-hosting per dati sensibili.
- Corpus census on-disk 2026-05-23.
- Prior: `research/marketing/2026-05-16-whatsapp-conversation-intelligence.md`,
  `research/operations/2026-05-23-wa-mirror-dashboard-discovery.md`, `apps/wa-mirror/README.md`.
