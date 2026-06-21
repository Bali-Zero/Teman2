---
date: 2026-06-21
domain: compliance
client_case: adit-intake-review-load
sources:
  - apps/backend-rag/backend/services/intake/routing.py (decision matrix C4, commit_gate)
  - apps/backend-rag/backend/services/intake/classify.py (doc_type + OCR)
  - apps/backend-rag/backend/app/routers/intake_review.py (reader /api/intake/review/queue)
  - apps/mouth/src/app/(workspace)/review/page.tsx (frontend pre-seed candidato)
  - DB nuzantara_dev: document_routing_proposal + intake_queue + clients (live, 2026-06-21)
---

# Ridurre la fase di review umana dell'intake — analisi profonda

## Mandato (Zero, 2026-06-20)
"Pensa a come diminuire la fase di review umana." Focus: adit, ma il funnel è team-wide.

## Anatomia del lavoro umano (dati live, whatsapp, ~1372 proposal storiche)
- **rejected 24.3%** (333) — di cui **222 erano `unknown`** (66%): rumore (screenshot/foto/meme/illeggibili) guardato e rifiutato a mano.
- **routed 5.6%** (77) — approvati→CRM. **ZERO AUTO_ATTACH committati** (tutti LINK_CANDIDATE/AMBIGUOUS/NO_MATCH confermati a mano).
- review_pending 40% / superseded 30%.

Dei ~534 review_pending whatsapp, per telefono mittente:
- **214 LINK_CANDIDATE** con telefono = 1 cliente CRM esatto.
- **38 AMBIGUOUS** con telefono = 2+ clienti (condiviso, 51 gruppi live).
- **277 NO_MATCH** con telefono NON in CRM (mittente sconosciuto → lead).
- 5 LINK_CANDIDATE per nome fuzzy.
→ **92% ha il destino già determinato dal telefono a monte.**

## SCOPERTA: il matching a monte ESISTE GIÀ (non è il collo)
Tracciato l'intero flusso:
1. `routing._match_sender_phone` normalizza (`0→62`,`8→62`, dual `+`) e match-a `clients.phone_normalized`.
2. Il candidato finisce in `entity_resolution.candidates`.
3. Il reader `/api/intake/review/queue` li carica (`_load_candidate_clients`) → `entity_candidates`.
4. **Il frontend pre-seleziona** `entity_candidates[0]` (`review/page.tsx:427-433`) + inferisce destinazione dal doc_type + pre-compila i campi estratti (`prefillFromExtractedFields`).

→ Per i 214 LINK_CANDIDATE adit trova GIÀ cliente pre-selezionato + tipo + campi. Il "ri-cercare il cliente" ipotizzato in gran parte NON c'è. Costruire "pre-aggancio a monte" sarebbe ri-fare l'esistente.

## I 3 costi REALI del tempo umano
- **A. Volume di tap**: centinaia di doc, ognuno 1-tap, ma il volume è il costo.
- **B. 277 NO_MATCH**: telefono sconosciuto → adit crea lead a mano / scarta. (auto-promote esiste ma è cron 5min soglia-3, non immediato → molti restano appesi.)
- **C. ~222 unknown-rumore**: guardare e rifiutare uno a uno.

## DUE LEVE scelte da Zero (2026-06-21)

### LEVA 1 — Pre-filtro rumore → quarantena (taglia ~40% volume, costo C)
Doc `classify.doc_type='unknown'` + OCR < soglia char (illeggibile) → NON in `/review` principale: flag `quarantine`, tab separato, auto-archive dopo N giorni se non aperto. Rischio basso: quarantena consultabile (no delete). Mitiga il falso-negativo (doc vero mal-classificato → recuperabile dal tab).
- Punto d'innesto: route stage (`routing.py` commit_gate) calcola un flag `quarantine_eligible`; reader esclude quarantine dalla queue default + endpoint `/review/quarantine` per consultarli.

### LEVA 2 — Auto-attach doppio-concorde (taglia il tap sui sicuri, costo A) — "ESISTE≠ARMATO"
**Il sistema lo calcola già ma non lo arma**: `routing.py` produce `commit_gate.auto_attach_eligible = (decision==AUTO_ATTACH AND client_id risolto)`, ma scrive SEMPRE `status='review_pending'` e NESSUNO consuma il flag per committare. Superscar #2 (costruito non attivato).
- AUTO_ATTACH scatta quando 1 identificatore FORTE estratto (passaporto/NPWP/NIB/akta) → 1 cliente univoco. Il telefono concorde lo rafforza (mittente=soggetto confermato → risolve mittente≠soggetto).
- **Armamento**: quando `auto_attach_eligible` AND telefono concorde → invece di review_pending, eseguire il COMMIT reale:
  1. collocare il documento nel posto preciso (cartella CRM corretta via `routing.client_id` + categoria doc_type→folder),
  2. notifica al lead/cliente in **kita** (canale notifiche kita),
  3. audit-log + **undo 48h** (reversibile),
  4. proposal status nuovo `auto_routed` (distinto da `routed`-umano per audit).
- Solo questo caso bypassa l'umano. Tutto il resto invariato. Zero rischio mittente≠soggetto (doppio segnale concorde).

### Doppio-concorde — definizione operativa stretta (anti-falso-positivo)
Auto-attach SOLO se TUTTE:
1. `decision == AUTO_ATTACH` (1 identificatore forte estratto → 1 cliente).
2. `target.client_id` risolto e NON nullo.
3. Telefono mittente normalizzato matcha lo STESSO `client_id` (concordanza forte-id ↔ telefono).
4. Telefono NON in un gruppo condiviso (51 gruppi) — se condiviso → resta review.
5. Killswitch globale `INTAKE_AUTO_ATTACH_ENABLED` (default false fino a GO Zero).

## Stato implementazione
- 2026-06-21: analisi completata + design. Implementazione LEVA 1 + LEVA 2 in worktree backend-rag-intake-review-levers.
- Recupero 319 adit in corso in parallelo (monitor bijfgmgca), indipendente.

## Invarianti da non violare
- `enqueue.py` resta ZERO-CRM-write (Law 2): il lookup cliente NON va lì, sta nel route stage.
- mittente≠soggetto: l'auto-attach SOLO su doppio segnale concorde, MAI su telefono solo.
- Telefono condiviso (51 gruppi) → resta AMBIGUOUS, mai auto.
- Undo 48h obbligatorio su ogni auto-commit (reversibilità).
- Killswitch default-OFF: nessuna scrittura CRM autonoma prima del GO di Zero.
