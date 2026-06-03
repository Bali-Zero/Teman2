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

### TODO manuale Antonello (nessun MCP delete-Drive)

Cestinare su Drive (profilo zero) + cancellare 2 NB di test:

- NB `WA-CORPUS-GATE-TEST-20260604` (id `f4dcb203-c6cf-45b1-b6a9-dd5e14bb4663`)
- NB `WA-CORPUS-PILOT-CLEAN-20260604` (id `7e4665c3-1c78-4648-9e49-2415a099abee`)
- Doc `WA-GATE-TEST1-+33614653019-...` (id `1YsU-X-4nyhpXEjhfo1phv47WWYtwfw5ie-OQsu67al4`)
- Doc `WA-+33614653019-...` del pilot (id `17TDAELRcd6U2It-nRqo23QZi-k_yBAS1HAfLA47mMsA`)
  (`nlm notebook delete <id> -p zero` cancella i NB; i Doc Drive vanno dal cestino Drive di zero@.)

### FASE 2 (non in v1, da spec §7)

gruppi (23% traffico), rename auto da CRM, cross-NB per i 37 clienti multi-membro, quota/retry batch
hardening, persistenza recap in `clients.strategic_recap`/`ai_summary` (campi già esistenti). Plus:
calibrazione fine soglie classificatore su un campione più ampio (la coppia REVIEW va validata a mano).
