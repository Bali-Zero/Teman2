---
date: 2026-06-04
domain: compliance
client_case: false
session: WhatsApp → CRM corpus-miner — design completo (6 round + pilota empirico)
status: DRAFT v7 design, pronto per prova-di-fuoco poi implementazione
sources:
  - spec: docs/superpowers/specs/2026-06-03-wa-corpus-miner-local-rebuild-design.md
  - memory: discovery_wa_corpus_miner_built_then_removed_2026_06_03.md
---

# Session Report — WhatsApp Corpus-Miner (2026-06-03/04)

## Da dove è partito

"wa mirror, puoi preparare nuovo qr code per sahirta?" → rigenerati QR per Sahira + Ari
(entrambe connesse, verificato). Poi "come lavoriamo i msg wa-mirror" → indagine sul
collegamento chat WhatsApp del team → CRM.

## Stato del sistema (verificato live)

- **wa-mirror**: 7/7 account team connessi, scrive Postgres LOCALE Pro (`localhost:5432/nuzantara_dev`,
  tabella `whatsapp_message_context`, ~24k msg, flusso vivo). NON su Fly (cutover 24 mag, Law 2).
- Attribuzione per team member: **flusso live 100% attribuito** (i 14.847 NULL sono import storico 13-gen già lavorato).
- Chat raggruppabili per coppia `(team_member_phone, counterpart_phone)`; conversazioni multi-giorno
  si uniscono automaticamente (stesso counterpart = stessa conversazione). NO `conversation_id` nel DB.
- **321 coppie** distinte team↔counterpart. **85% clienti parla con 1 solo membro**, 15% (37) multi-membro.

## Il problema centrale (perché è difficile)

Esisteva un miner CRM (`c7c07b650`, 27 mag) mai mergiato, poi rimosso da #1018. Scrisse 3848
fatti su Fly. Ricostruirlo = problema duro: **estrarre fatti affidabili da chat multilingue
(bahasa+inglese misti) e scriverli nel CRM senza allucinare.**

## Percorso di design (6 round, tutti istruttivi)

1. **v1-v2** (estrazione fatti gemma/parser locali): REJECT — dedupe rotto, watermark fragile, conversation_id fantasma.
2. **v3** (append-only + finestra + gate): REJECT — conflict laundering, error accumulation, gate-placebo.
3. **v4** (due strati deterministico+LLM): REJECT — "sposta il rischio, non lo elimina", recall <30% su IT/ID misto.
4. **v5** (MVP umile read-only): scelto, poi superato dall'idea NLM.
5. **SVOLTA — v6 NotebookLM grounded** (idea Antonello): non estrarre fatti, caricare chat intere
   in NLM e interrogare a read-time. NLM cita verbatim (cited_text), non allucina.
   **PILOTA-1 (chat Sahira 1-a-1) superato**: verbatim ✅, 6 fatti immigration estratti ✅, upsert drive in-place ✅.
   MA v6 → REJECT 3/3 red-team: "1 chat curata inganna".
6. **v7** (corrente): NB-per-membro validato dai dati + mercato 2026. Bloccanti v6 ridimensionati.
   **PILOTA-2 (chat lunga reale 275 msg)**: ha rivelato il vero problema → vedi sotto.

## LA SCOPERTA CHIAVE (pilota-2)

L'assunto "1 counterpart_phone = 1 cliente" è **FALSO**. Esistono 3 categorie:

- **cliente 1-a-1** → carica, recap valido
- **team interno** → escludi (no profilo cliente)
- **partner/collega multi-cliente** → escludi v1 (genera recap che fonde 30 clienti)

**Fonte di verità per classificare = `whatsapp_contacts.contact_type`** (`team`/`client`).
Es: `+628563785797` non era nel roster mirrorato ma contact_type='team' name='Adit Bali Zero'
= secondo numero di Adit. Il prompt-master su quel numero produsse un recap-fuso (30 persone).
→ v1 DEVE avere un classificatore counterpart pre-caricamento basato su contact_type.

## BONUS: il CRM ha già i campi

`clients.strategic_recap` / `ai_summary` / `*_updated_at` / `*_source` esistono già nello schema.
Il recap grounded ha già destinazione. Niente nuove colonne.

## Architettura v7 (in sintesi)

- 1 NB per team member (NB-Surya, NB-Adit…), 1 file/cliente dentro (chat=Google Doc Workspace zero@).
- Sync drive in-place (`nlm source sync`, no delete).
- Query-runner schedulato → 1 prompt-master per cliente → recap EN → campo CRM.
- Cross-NB query per i 37 clienti multi-membro.
- Anti-allucinazione: grounding NLM (verbatim) + scope-limit + human-in-the-loop (recap read, umano decide).

## PROMPT-MASTER (testato, funziona)

1 query completa, 6 sezioni (DEADLINES / PAYMENTS / DOCUMENTS-CASES / PENDING ACTIONS /
RISKS-URGENCIES / RELATIONSHIP STATUS), ognuna con **citazione verbatim obbligatoria**,
"not mentioned" se assente, output ENGLISH, max 2000 char. Testo completo nella spec §4.

## GATE prima di costruire (prova-di-fuoco, ~2gg)

2 incognite tecniche da chiudere PRIMA del resto:

1. **Scrittura Doc**: MCP google-workspace docs ha BUG field-mask → il renderer deve usare Drive API diretta. MAI testato.
2. **Sync contenuto NUOVO**: `source sync` testato solo su Doc invariato. Verificare che propaghi modifiche reali.
   Se falliscono → rivalutare il motore (Claude CLI MAX + retrieval locale come fallback).

## Note tecniche nlm CLI

- profili: `default`=antonellosiano@gmail, `zero`=zero@balizero (Workspace interno).
- flag `-p zero` DOPO il subcomando (non globale). `source delete` serve `-y`.
- drive-sync mantiene stesso source ID; cross-NB query via `nlm cross`.

## TODO manuale Antonello

- Cestinare Google Doc di test: Drive (profilo zero) → `WA-Chat-Surya-6281246627424-PILOT`
  (id `1W7VcQu1c9NJvBlaIDLtSnI2BHE6P6WnEQODd8uEePz4`) — nessun MCP ha delete-Drive.

## Decisioni Antonello (Law 5) prese in sessione

- Recap output in INGLESE (va nel CRM auto).
- NB-per-membro (validato 85/15), non per-cliente.
- Law 2: NB su Workspace interno zero@ OK (non cloud pubblico). Goldset/estrazione locale abbandonati → nessuna deroga a regime.
- Gruppi (23% traffico) e UI review = fase 2.

## Ricerca mercato giugno 2026 (conferme)

- Recap-per-cliente sul timeline = standard CRM immigration 2026.
- Anti-allucinazione = RAG + scope-limit + HITL (non estrazione deterministica).
- ⚠️ Meta vieta AI chatbot general-purpose su WhatsApp Business API dal 15-gen-2026 — NON tocca
  questo uso interno né wa-mirror (Baileys), ma audit 4 canali operativi consigliato separatamente.

## NEXT SESSION — punto di ripresa

1. Eseguire la PROVA-DI-FUOCO (gate): Drive API scrive un Doc reale + `nlm source sync` propaga il contenuto nuovo.
2. Se gate PASS → writing-plans → worktree → renderer chat→Doc → classificatore counterpart (contact_type) → query-runner.
3. Se gate FAIL → rivalutare motore.

---

## AGGIORNAMENTO 2026-06-04 (sera) — GATE PASS + v1 COSTRUITO

### GATE (prova-di-fuoco) — ENTRAMBI PASS ✅

- **TEST 1 (Drive API diretta)**: Google Doc nativo creato nel Workspace zero@ via Service Account
  con Domain-Wide Delegation (`nuzantara-google-drive-sa@nuzantara.iam.gserviceaccount.com` impersona
  `zero@balizero.com`) + `files().create(media=text/markdown → google-apps.document)`. Round-trip
  export confermato. **Bypassa il MCP docs buggato.** 53 msg chat reale (Alexandre +33614653019).
- **TEST 2 (sync contenuto nuovo)**: query baseline negava un sentinella univoco → dopo
  `nlm source sync --source-ids <id> -y` la query lo cita **verbatim** con cited_text + source_id.
  Propagazione del contenuto nuovo provata end-to-end.

### 3 FINDING che CORREGGONO la spec v7

- **F1**: l'account NLM (profilo `zero` e default) è **`antonellosiano@gmail.com`**, NON zero@.
  I Doc creati dalla SA (owned zero@) vanno **condivisi** con antonellosiano@ (writer, no-notify) o
  `nlm source add` fallisce "Could not add drive source". Il renderer lo fa automaticamente al create.
- **F2**: `nlm source stale` NON rileva una modifica reale (ha detto "all up to date" dopo un update
  con modifiedTime cambiato). Produzione: watermark proprio + sync esplicito su source-id, mai `stale`.
- **F3** (data-driven): `contact_type` reale = contact 8242 / linked 166 / group 81 / team 42 /
  client_visa 11 / partner 6 / client 2. Solo 13 righe client/client_visa. → classificatore
  **exclusion-first** (escludi team/partner/group), NON inclusion-only su `contact_type='client'`.

### v1 COSTRUITO (worktree `ops-wacorpus-gate-firetest-20260604`, branch agent/...)

Package `scripts/wa_corpus/` — 7 moduli, **18 unit test PASS + 1 live skipped**, TDD:

- `classifier.py` — exclusion-first, 4 verdetti (CLIENT/INTERNAL/MULTI_CLIENT/REVIEW). Verificato sui
  dati: il numero-trappola §7bis `+628563785797` (contact_type=team) → **INTERNAL escluso**; Alexandre → CLIENT.
- `db.py` — accesso Postgres read-only; `count_distinct_names` con stoplist EN/ID/brand (Alexandre 13→2 nomi).
- `renderer.py` — chat→Doc nativo via Drive API + auto-share (F1).
- `query_runner.py` — wrapper nlm CLI, sync esplicito (F2), enforcement cited-text.
- `prompt_master.py` — prompt 6 sezioni grounded + validator.
- `pilot.py` — driver end-to-end. **Pilot live PASS**: recap 6 sezioni, 4 citazioni verbatim,
  semanticamente reale (LKPM/OSS, PT AUM, cliente frustrato), read-only (HITL, non scrive CRM).

### AGGIORNAMENTO 2026-06-04 (notte) — SCALA 10 chat + classificatore a 3 categorie

**Test di scala (chiude bloccante v6 + incognita #3 cross-source contamination)** ✅

- `multi_chat_pilot.py`: 10 chat REALI di Surya (`team_member_email=surya@balizero.com`,
  linea `+628133946856`) caricate nello **stesso NB**, sync esplicito, 1 query per source con
  `--source-ids`. **Risultato: 0 cross-source leak su 10** (ogni citazione proviene dal source giusto).
  Il bloccante v6 "1 chat curata inganna" è superato: 10 chat diverse gestite correttamente.
  Selezione automatica via classificatore: scelti solo i 10 CLIENT, saltati i counterpart INTERNAL.

**Classificatore robusto a 3 categorie + gruppi** (richiesta Antonello) ✅

- Gerarchia precedenza (ordine conta): **GROUP** (chat_type=group) > **INTERNAL** (team — `contact_type=team`
  OR è una linea `team_member_phone`; team BATTE client) > **MULTI_CLIENT** (alto volume + molti nomi) >
  **CLIENT** (già in `clients` via phone/whatsapp) > **PROSPECT** (esterno NON in CRM, volume normale) > **REVIEW**.
- `Verdict.loadable` = CLIENT|PROSPECT (entrambi ricevono Doc+recap; CLIENT→profilo cliente, PROSPECT→lead).
  team/group/multi-client esclusi in v1.
- Nuovi segnali in `db.py`: `is_team_member` (roster + linea team) e `is_in_crm` (match `clients`).
- **Verificato sui counterpart reali di Surya (top 20)**: 6 internal / 12 client / 1 prospect / 1 review.
  Lia (team=True E in CRM) → INTERNAL corretto (precedenza). Screenshot conferma Surya=+628133946856.
- 23 unit test green (era 18; +5 per group/team-beats-client/prospect/loadable).

### AGGIORNAMENTO 2026-06-04 (notte 2) — naming OBBLIGATORIO + query perfezionata

**Naming Doc — OBBLIGO Antonello** ✅

- Il nome del Doc è **o il nome cliente CRM, o il numero telefono** (che diventerà cliente CRM).
  Il numero è SEMPRE la chiave stabile nel title (per ricerca/rename alla conversione lead→client).
- `db.crm_name(phone)` (full_name||company_name da `clients`) + `renderer.doc_title(phone, crm_name)`:
  in CRM → `WA · <nome> · <numero>`; non in CRM → `WA · <numero>`.
- Verificato: Alexandre/Johanna → con nome; `+6281358196299` → solo numero.

**Query perfezionata — recap multi-prospettiva + punti specifici (MOLTI test)** ✅

- `query_lab.py` + `prompt_variants.py`: iterati 5 prompt (v1-v5) su 3 chat reali di Surya
  (Alexandre/Johanna/Fabio) con scoring ground-truth (recall fatti / allucinazioni / citazioni / char).
- **Vincitore v5** (ora `prompt_master.PROMPT_MASTER`): struttura a **2 livelli** — `HEADLINE` (1 frase) +
  `GENERAL RECAP` da 4 punti di vista (Operational / Relationship / Commercial / Risk) +
  `SPECIFIC POINTS` (7 punti: company / service / deadlines / amounts / documents / next-action / last-contact).
  Tutto grounded con quote verbatim, ENGLISH, <2000 char.
- Risultati v5: Alexandre 5/5 fatti, Fabio cattura `17.8 mill`+date+`war in Iran`, 0 allucinazioni,
  0 cross-source leak su tutte e 3. E2E produzione su Fabio: 6 citazioni, struttura valida, 1934 char.
- **LAB FINDING (importante)**: NLM è **non-deterministico** nel popolare le `references` strutturate —
  stesso prompt+source → 0 citazioni una run, 8 la successiva. Il `query_runner.run_prompt_master`
  ora **ritenta (max 3)** finché le citazioni sono vuote; se ancora vuote, il chiamante flagga il recap
  come "unverified" (gate HITL — un recap senza citazioni tracciabili non passa l'anti-allucinazione).
- 32 unit test green (era 23; +4 prompt-master nuova struttura + retry, +5 doc-title già contati sopra).

### AGGIORNAMENTO 2026-06-04 (notte 3) — FLUSSO AGENTICO (riconciliazione di stato)

Antonello: "devi essere più strutturato e creare il flusso agentico" — non basta creare il Doc una
volta, serve gestire le **transizioni di stato** ad ogni passata (es. prospect→client → il file va
rinominato numero → nome+numero). Decisioni Antonello: rename (non archive/cancel), cron giornaliero
subito, recap scritto **diretto** in `clients.strategic_recap`.

**Stato CRM verificato** (anti-allucinazione, NON assunto): `strategic_recap` era VUOTO su tutte le
11446 righe (mai scritto). Migration 189 → CHECK constraint `strategic_recap_source IN
('manual','ollama_local','wa_auto','human_curated')`. Scrivo con `source='wa_auto'`; un edit umano
successivo lo passa a `manual` via il router CRM (riga 972). Chiave = `clients.id` da phone.

**Decision logic agentica PURA** (`reconcile.decide_action`, 10 test): matrice transizioni
CREATE / RENAME / UPDATE / SKIP / ARCHIVE. Gerarchia: nuovo+loadable→CREATE; non-più-loadable→ARCHIVE
(rename `ARCHIVED · …`, NON cancella); title cambiato→RENAME (prospect→client, nome CRM nuovo);
nuovi msg→UPDATE; invariato→SKIP. RENAME ha precedenza su UPDATE. Numero SEMPRE preservato.

**State store** `wa_corpus_docs` (tabella locale nuzantara_dev): per `(team_email, counterpart_phone)`
traccia file_id/source_id/nb_id/last_title/last_verdict/last_msg_at/last_recap_at. Upsert idempotente.

**Reconciler I/O** (`reconciler.py`): per membro itera i counterpart, calcola stato desiderato,
`decide_action`, esegue (rename_doc Drive / update+sync / recap+CRM write), persiste, accumula digest.
Recap scritto in CRM SOLO se in `clients` AND ha citazioni (retry garantisce o flag unverified).

**VERIFICATO LIVE** (Surya, NB reconcile-test `a10ea479-6e88-4010-8201-6d21720b57a5`):

- run1: `create=2 recap_written=2` → Brandi+Johanna in `clients.strategic_recap` source=wa_auto
  (verificato sul DB: 1560 e 1942 char con HEADLINE grounded).
- run2 (stessi parametri): `skip=3` → **idempotente**, zero spreco.
- run3 (simulato prospect→client falsificando last_title a solo-numero): **`rename=1`** → Doc
  rinominato su Drive E nello state store a `WA · Johanna · +46737002611` (numero preservato). ✅
  **Questo è esattamente il caso che Antonello chiedeva.**

**Cron giornaliero** (`run_all_members.py` + `wa_corpus_daily_run.sh` + plist example 05:00 WITA):
legge `wa_corpus_members.json` (email/team_phone/nb_id per i 7 membri con chat), reconcile per membro,
digest Telegram (solo TOTAL+righe membro, mai contenuto chat). **NON installato** — l'operatore prima
crea 1 NB per membro + riempie nb_id + token, poi `launchctl bootstrap`. Membri senza nb_id → skip con
warning. Verificato: bash -n OK, plutil -lint OK, dry-run all-members OK. 52 unit test green totali.

### TODO manuale Antonello (nessun MCP delete-Drive)

Cestinare su Drive (profilo zero) + cancellare 4 NB di test (`nlm notebook delete <id> -p zero`):

- NB `WA-CORPUS-GATE-TEST-20260604` (`f4dcb203-c6cf-45b1-b6a9-dd5e14bb4663`)
- NB `WA-CORPUS-PILOT-CLEAN-20260604` (`7e4665c3-1c78-4648-9e49-2415a099abee`)
- NB `WA-CORPUS-SCALE-SURYA-20260604` (`9c82e1db-1cf5-4048-b9f2-5bc8e0c8f26c`) — 10 Doc WA-MULTI-\*
- NB `WA-CORPUS-RECONCILE-TEST-20260604` (`a10ea479-6e88-4010-8201-6d21720b57a5`) — 2 Doc reconcile-test
- Doc `WA-GATE-TEST1-+33614653019-...` (`1YsU-X-4nyhpXEjhfo1phv47WWYtwfw5ie-OQsu67al4`)
- Doc `WA-+33614653019-...` del pilot (`17TDAELRcd6U2It-nRqo23QZi-k_yBAS1HAfLA47mMsA`)
- 10 Doc `WA-MULTI-*` + 2 Doc reconcile (`WA · Brandi…`, `WA · Johanna…`) dal cestino Drive di zero@
- ⚠️ **2 righe `clients.strategic_recap` scritte dal test** (Brandi id 5730, Johanna id 6087, source=wa_auto)
  — sono recap reali corretti; lasciarli o resettarli a piacere (`UPDATE clients SET strategic_recap=NULL,
strategic_recap_source=NULL WHERE id IN (5730,6087)`).

### PER ANDARE IN PRODUZIONE (operatore)

1. Crea 1 NB per membro: `nlm notebook create "NB-Surya" -p zero` (×7), copia gli id.
2. `cp infra/launchagents/wa_corpus_members.example.json ~/.config/nuzantara/wa_corpus_members.json`,
   riempi gli `nb_id`.
3. `cp infra/launchagents/com.nuzantara.wa-corpus.daily.plist.example ~/Library/LaunchAgents/…plist`,
   metti `TELEGRAM_BOT_TOKEN`, `chmod 0400`, `launchctl bootstrap gui/$(id -u) …`.
4. Primo giro consigliato con `WA_CORPUS_DRY_RUN=1` per vedere il digest senza scritture.

### FASE 2 (non in v1, da spec §7)

gruppi (23% traffico — il classificatore già li riconosce come GROUP, manca solo il rendering
multi-party), rename auto da CRM, cross-NB per i 37 clienti multi-membro, quota/retry batch
hardening, persistenza recap in `clients.strategic_recap`/`ai_summary` (campi già esistenti). Plus:
validare a mano i counterpart REVIEW; raffinare la soglia volume per separare i numeri-team
non ancora marcati (es. `+628213454728` classificato PROSPECT ma forse linea team — il roster
`whatsapp_contacts.contact_type` va completato).
