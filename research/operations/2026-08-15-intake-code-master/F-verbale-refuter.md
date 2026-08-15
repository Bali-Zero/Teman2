---
title: "Intake Code Master — F: adversarial verbale (Codex GPT-5.6 + Kimi K3)"
date: 2026-08-15
domain: operations
client_case: none (intake system audit, aggregate counts only, PII-redacted; no client names/phones/ids beyond client_id/proposal_id integers)
author: Claude Fable 5 interactive session (Pro) — candidacy dossier, READ-ONLY mandate
sources:
  - worktree .worktrees/docs-intake-code-master-0815 @ f6dfda994 (code read file:line in-turn; svc/rt/rd path conventions in README)
  - local nuzantara_dev Postgres 127.0.0.1:5432 (SELECT-only, default_transaction_read_only=on; W87 — never the prod MCP)
  - one prod read via scripts/pg.sh (readonly role) for the `companies` count
  - live process/plist/log state on Pro (launchctl print, ps, lsof, stat) — measured 2026-08-15
  - research/operations/doc-intake-unified/* + 2026-06-27/28, 2026-07-18 intake reports + modus PENDING-ARMS + /intake SKILL
  - external SOTA (D): URLs listed per axis, WebSearch 2026-08-15
adversarial_review: kimi-k3
---

# F — Verbale del passaggio avversariale (generator ≠ grader)

## Adversarial review

Seat: `kimi-k3` (Moonshot Kimi K3) + `codex` (GPT-5.6 terra) — entrambi di famiglia diversa dall'autore (Claude Fable 5). Sollevati: 15+5 WEAKENED, 5 difetti nuovi, 0 FALLS. Sopravvissuti dopo ri-verifica su disco: tutti i 31 finding; 8 corretti nel testo; le obiezioni respinte sono elencate in §6 «Disaccordi mantenuti». Il resto di questo file È il verbale.

Dossier generato da Claude Fable 5 (questa sessione). Refuter di famiglia DIVERSA, entrambi con ordine esplicito di DISTRUGGERE il dossier (prompt in `refuter-prompt.txt`, scratchpad di sessione: attaccare ogni file:line di C, le 6 risposte A.8, ≥10 anchor di B, cercare PII, marcare UNVERIFIABLE i numeri senza DB), lanciati sul worktree in sola lettura, senza accesso al DB, senza accesso a `docs/mandates/`:

| Seat | Comando | Esito |
|---|---|---|
| **Codex GPT-5.6 terra** (OpenAI, `model_reasoning_effort=high`, `--sandbox read-only`) | `codex exec -m gpt-5.6-terra … "$(cat refuter-prompt.txt)"` | 163.989 token, tabella su 29 C + 6 A.8 + 13 B; **0 FALLS**, 15 WEAKENED (di cui 9 solo «UNVERIFIABLE-BY-ME» sui numeri) |
| **Kimi K3** (Moonshot, `kimi -m kimi-code/k3 -p`) | idem, swarm di 8 sub-agenti per cluster | tabella su 29 C + 6 A.8 + 20 B; **0 FALLS**, 5 WEAKENED, **5 difetti nuovi** |
| Sonnet 5 (Explore, stessa famiglia — solo anchor-sweep meccanico, non giudizio) | 40 anchor di B non coperti dai due sopra | 37 OK · 3 OFFSET · **0 PHANTOM** |
| Sonnet 5 (Explore, verifica indipendente delle 6 correzioni post-Kimi) | 6 claim nuovi | 5 TRUE · 1 PARTLY (`rag_proxy.py` 207-209 → 207-210) |

Regola applicata: **il refuter può sbagliare (W65)** — ogni FALLS/WEAKENED è stato ri-verificato su disco in questo turno prima di toccare il dossier; ogni frase correttiva è un claim nuovo ed è stata ri-derivata dalla fonte (W113).

## 1. Caduti

Nessuno. Su 31 finding, 6 risposte A.8 e 27 pattern B, nessun refuter ha trovato una citazione fantasma o una logica falsa. Il peggior anchor: `intake_review_reader_liveness.sh:80` (era `:139`, riusato in C-13 e B19) — un errore di riga, non di sostanza; corretto e la prova è stata ESEGUITA (stub 500 in un HOME finto ⇒ `OK: reader ALIVE (http 500)`).

## 2. Indeboliti → corretti (con l'evidenza ri-letta)

| ID | Obiezione (chi) | Verifica mia | Correzione nel dossier |
|---|---|---|---|
| C-13 / B19 | riga `:80` sbagliata (Kimi, Codex); «`python -m http.server` non ritorna 500» (Codex) | `grep -n '\[1-5\]'` → `:139`; stub `BaseHTTPRequestHandler` 500 eseguito | `:139` + prova eseguita nel testo |
| C-08 | somma stati = 308 ≠ denominatore 304; «65 pushed non dà 241» (Codex) | `intake_commit_audit committed` = 308 righe/308 `doc_id`; `documents.intake_proposal_id` = 304 (4 `doc_id` spariti, 2 con `rolled_back`); `file_id` = 63 = `pushed` presenti | i due denominatori dichiarati; 241 = 304 − 63 (da `file_id`, non da `pushed`) |
| C-07 / A.8-4 | «il sentinel riporta separatamente le zero-proposal» (Codex); «grep = 0 è falso: snapshot + plist disabilitato» + 932 vs 951 (Kimi) | `COUNT_SQL :57-77` conta due classi; `launchctl print` → «Could not find service»; ledger `:181`; LEFT JOIN → 951 WA / 22.979 Drive | titolo «tripwire ARMATO»; evidenza di attivazione corretta; 951; e ho ESEGUITO il `COUNT_SQL` del sentinel: 28.199 orfani di cui 28.068 falsi |
| C-20 | roster telefoni non è import-time puro: `_internal_phone_config()` è UNIONE snapshot+env (Kimi; Codex l'aveva confuso col sweeper) | `auto_attach.py:111-117` `frozenset((*INTERNAL_PHONE_NUMBERS, *env_numbers))`, unico caller `:125` per messaggio | il difetto è ribaltato: le AGGIUNTE passano, le RIMOZIONI no; titolo e categoria aggiornati |
| C-24 | «11 gruppi = soppressione voluta» contraddetto dal docstring `:15` e dal loop (Kimi) | `sweeper.py:15` «Group media is intentionally still enqueued», loop `:590-604` accoda tutti | i 29 sono tutti da spiegare; candidato causale C-31 |
| C-16 | il canone 6–12 proposto confligge con `validate` 6–9 (Codex, Kimi) | `validate_rules.py:39` `{6,9}` vs `extract.py:922` `{6,12}`; `_match_person_strong` → `_normalize_passport` (`:300-306`) senza lunghezza | i DUE canoni sono ora il cuore del finding; la cura chiede UNA scelta |
| A.8-2 / A.8-4 | cross-ref C-05→C-03, C-14→C-07 (Kimi, Codex) | testo | corretti |
| A.8-5 | «intenzionale» vs C-04/C-27 «difetto» (Codex) | — | precisato: la restrizione è scelta di default; la CONSEGUENZA è il difetto |
| C-10 | «il codice non dice che Qdrant è cloud» (Codex) | host dell'env del clone: `…gcp.cloud.qdrant.io` (solo host) | comando aggiunto |
| C-11 | «repo pubblico non provato» (Codex) | `gh repo view --json visibility` → `PUBLIC` | comando + output aggiunti |
| C-23 | «impatto non dimostrato» (Codex) | — | dichiarato NON misurato; resta P3 |
| C-18, C-28, B10, B4 | riga `:428→:430`, `:199→:207-210`, `:98→:97`, «abortisce» troppo forte | letti | corretti (`skipped: strong_id_stale`, `strong_id_lock_busy :768-780`) |
| B20 / B23 | path `backend/tests/…` senza prefisso `apps/backend-rag/` (Sonnet sweep) | — | convenzione dichiarata nel README |

## 3. Difetti nuovi portati dai refuter (Kimi K3) — verificati e assorbiti

| # | Difetto | Verifica | Dove |
|---|---|---|---|
| 1 | Sweeper: `break` senza avanzare il watermark su eccezione per-riga permanente | `sweeper.py:579-588, :604-609` vs `:563/:568` che avanzano; watermark `:616-617`; oggi non fermo (153.245 = max id) | **C-31** (nuovo) |
| 2 | Rimozione dal roster telefoni non propaga fino al restart | `auto_attach.py:111-117` | C-20 (riscritto) |
| 3 | Quarantine/duplicate senza superficie UI (`page.tsx` non chiama mai `status=quarantine|duplicate` né `/recover`) | grep `page.tsx` → 0 hit; API `:366-371`, `/recover :919` | C-25 |
| 4 | Due canoni passaporto 6–9 vs 6–12 | `validate_rules.py:39` / `extract.py:922` | C-16 |
| 5 | Nessun monitor per lo zombie C-05 (`review_claimed AND lease_expires_at IS NULL`) | grep sentinel/report → assente | C-05 (cura) |

Codex: «New defects: none». Sonnet (anchor-sweep): nessuno per mandato.

## 4. Trovato DURANTE la verifica (non dai refuter)

**C-30 (P0 LIVE)**: misurando l'innocenza di C-31 (watermark = `max(id)` media) è emerso che il `max(id)` è fermo al **13/8 13:03**: `whatsapp_message_context` non riceve righe da 48 ore, i 6 bridge del WA mirror sono in crash-loop su `ERR_MODULE_NOT_FOUND 'pino'` (`node_modules` del main checkout svuotata il 13/8 04:26), e nessun guardiano ha suonato. Inviato UN P0 via `tg_notify.py` (dedup `wa-mirror:all-bridges-dead:err-module-not-found`); nessuna riparazione (mandato read-only). È l'esempio più netto di ciò che il refuter NON poteva vedere: entrambi i seat hanno marcato «UNVERIFIABLE-BY-ME» tutto ciò che vive nel DB e nei processi — la metà del dossier — ed è lì che stava il P0.

## 5. Ciò che i refuter NON hanno potuto verificare (dichiarato)

Tutti i conteggi su `nuzantara_dev`, lo stato dei processi (`lsof`, `launchctl`, `ps`), i digest Fly, i file HOME. Per ognuno il dossier porta il comando accanto al numero; gli output stanno nel transcript di questa sessione. Chi legge può ri-eseguirli: sono tutti `SELECT`/`ls`/`stat`/`launchctl print`.

## 6. Bilancio

- Anchor verificati da terzi: ~120 (C) + 40 (B, Sonnet) + 20 (B, Kimi) + 13 (B, Codex) + 6 (correzioni) ⇒ **1 riga sbagliata riusata 2 volte, 5 offset di 1–4 righe, 0 fantasmi**.
- Sostanza: **0 finding caduti**; 8 corretti nel testo; 2 nuovi (C-30, C-31); 3 assorbiti in finding esistenti.
- Disaccordi mantenuti: C-27 resta un finding (POLICY/SPEC) anche se «scelta di default» — la scelta è documentata, la sua conseguenza (18.902 documenti invisibili a ogni umano e a ogni parametro API) no. C-03 resta P1 anche se «unverifiable from source»: è misura di processo, riportata col comando.
