---
title: "Intake Code Master dossier — index, method, unknowns"
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

# Dossier — Candidatura Code Master INTAKE (2026-08-15)

Mandato: `~/Desktop/2026-08-15-intake-code-master-mandate.md` (copia non tracciata su M5). Sessione READ-ONLY sul Pro: nessuna scrittura su DB intake/CRM, Fly, plist, worker; nessun flag armato; nessuno script eseguito con `--apply`; la answer key interna (`docs/mandates/…-answer-key-INTERNAL.md`) NON è stata aperta.

| File | Fase | Peso |
|---|---|---|
| [A-padronanza.md](A-padronanza.md) | A — Padronanza (macchine a stati, chiavi, flag/env, leve, writer, `/review`, tre radici, 6 domande) | 20 |
| [B-punti-di-forza.md](B-punti-di-forza.md) | B — 27 pattern difensivi con file:line, incidente, cosa succede rimuovendoli | 10 |
| [C-problematiche-e-bug.md](C-problematiche-e-bug.md) | C — 31 finding (**C-30 P0 LIVE**: WA mirror morto dal 13/8; 5 P1, 8 P2, 17 P3) con causa root, blast radius, prova guilt+innocence, cura minima; correzioni post-refuter in coda al file | 30 |
| [D-deep-research.md](D-deep-research.md) | D — leve misurate morte + SOTA su 7 assi con verdetti | 15 |
| [E-redesign-intake-2g.md](E-redesign-intake-2g.md) | E — Intake 2G: architettura, strangler in 10 wave, rischi × 10 famiglie, costi, STOP, cosa NON costruirò | 25 |
| [F-verbale-refuter.md](F-verbale-refuter.md) | Passaggio avversariale cross-family (Codex GPT-5.6 terra + Kimi K3 + 2 verificatori Sonnet): 0 caduti, 8 indeboliti e corretti, 5 difetti nuovi assorbiti | — |

## Metodo (per la difesa)

- Codice letto sul worktree di questo dossier (`.worktrees/docs-intake-code-master-0815`, HEAD `f6dfda994`; le righe citate valgono per quel commit — durante la sessione `origin/main` è avanzato a `0e638a3a1`, 2 commit non-intake); worker vivo confrontato con il clone `~/nuzantara-deploy` (HEAD `9104b6584` → `79d1e42ce` auto-pull, processo del 13/8); plist vivi vs `infra/launchagents/`; env-file letti SOLO per nome-chiave (`cut -d= -f1`), mai per valore.
- Convenzioni di path nel dossier: `svc/` = `apps/backend-rag/backend/services/intake/`, `rt/` = `apps/backend-rag/backend/app/routers/`, `rd/` = `apps/backend-rag/backend/app/`, `backend/tests/…` = `apps/backend-rag/backend/tests/…`, migrazioni = `apps/backend-rag/backend/db/migrations_v2/`; tutto il resto è relativo alla root del repo.
- DB: `PGOPTIONS='-c default_transaction_read_only=on' psql -h 127.0.0.1 -U nuzantara -d nuzantara_dev` (PostgreSQL 17.8); una sola lettura su prod via `scripts/pg.sh` (ruolo read-only) per confrontare `companies`.
- Filesystem: `test -e` sui `blob_path`, `lsof`/`launchctl print` per il worker, `ls`/`stat` per i log.
- Test: 823 passed / 8 skipped (intake + router + scripts + proxy) e 8/8 guard repo-root, con la guardia W96 attiva (`nuzantara_test`).
- Ricerca esterna: WebSearch 2026-08-15, URL riportati per asse.
- Nessun numero è ricordato: ogni cifra nel dossier ha il comando accanto o nel paragrafo "Misura".

## Cosa NON so (e come lo scoprirei)

- Chi ha svuotato `~/nuzantara/apps/wa-mirror/node_modules` il 13/8 04:26 (C-30): `fs_usage`/log dei job attivi alle 04:2x (`mos-maintenance` 04:00, `coverage-trend` 04:30 in crontab), `git reflog` del main checkout attorno a quell'ora.

- Chi ha cancellato i log del worker (C-03): `find`/`newsyslog.d`/plist con `-delete` su `~/logs`.
- Il valore di `INTAKE_GATE_DISABLED` su Fly (C-04/C-28): richiede `fly ssh console` (fuori mandato) o l'output della UI gate con un JWT reale.
- Quante delle 831 quarantene all-empty sono davvero Ollama-down (C-02): serve il log (C-03) o un replay dal Cold Archive (E W2/W8).
- Perché `companies` locale è vuota (C-29): confrontare il dump del refresh (`scripts/nuz_db_refresh.sh`) con `\dt` post-restore.

## Adversarial review

Cross-family refuters (generator ≠ grader): **Codex GPT-5.6 terra** (`codex exec --sandbox read-only`) and **Kimi K3** (`kimi -m kimi-code/k3 -p`), both ordered to destroy the dossier on the worktree, plus two Sonnet anchor-verifiers. Result: 0 findings fell; the weakened items and their on-disk re-verification are recorded in [F-verbale-refuter.md](F-verbale-refuter.md). Refuter transcripts: session scratchpad `refuter-codex-terra.md`, `refuter-kimi-k3.md`.
