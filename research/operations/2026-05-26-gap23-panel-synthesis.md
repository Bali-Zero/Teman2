---
date: 2026-05-26
domain: operations
client_case: none
sources:
  - /tmp/gap23-panel/brief.md (input)
  - /tmp/gap23-panel/gemini.md (Gemini 3.1 Pro raw output, 5.3KB)
  - /tmp/gap23-panel/codex.md (Codex GPT-5.5 xhigh + web search raw output, 51KB)
  - /tmp/gap23-panel/deepseek.md (DeepSeek V4 Pro reasoning_effort=high raw output, 7KB)
  - research/operations/2026-05-25-sota-workflow-gap-analysis-and-l5-spec.md (parent)
  - research/operations/specs/L5.1-agent-worktree-enforcement-2026-05-25.md (parent, draft)
  - research/operations/specs/L5.1-panel-synthesis-2026-05-25.md (parent panel)
  - sessione Claude `026f2cd1-5f18-40d3-806b-dbf7938a4c30` (2026-05-26 02:54-04:55 WITA) — origine 3 gap
---

# Panel 4-LLM Synthesis — Gap #2 + #3 Workflow Discipline (2026-05-26)

**Panel**: Gemini 3.1 Pro (agy CLI) + Codex GPT-5.5 (xhigh, with web search GitHub docs + Husky docs) + DeepSeek V4 Pro (reasoning_effort=high)
**Date**: 2026-05-26 ~14:20 WITA (wall ~5 min parallel dispatch)
**Brief**: `/tmp/gap23-panel/brief.md` (54 righe)

## Verdetto globale: **APPROVE_WITH_AMENDMENTS** (3/3 convergent)

I 2 gap originali ("require admin review" + "Telegram audit HUSKY=0") sono **reali ma mal-formulati**. Il panel converge:

- Detect HUSKY=0 lato client = **tecnicamente impossibile**.
- `required_approving_review_count=1` universale = **cargo cult** per single-dev.
- Vero rischio non mappato nel brief originale: **Claude bot admin con merge rights** su `main`.

La soluzione corretta sposta enforcement da client hook → CI server-side.

## Convergenze (3/3 unanime)

| #   | Convergenza                                                                                                                                                                              | Implicazione                                                                                                                                                             |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| C1  | **Client hook ≠ security boundary**. Husky/`HUSKY=0` non è catturabile in modo affidabile lato client.                                                                                   | Spostare enforcement reale a CI server-side. Client hooks restano ergonomia/early warning.                                                                               |
| C2  | **"Detect HUSKY=0" è obiettivo sbagliato**. La cosa corretta è "nessun PR entra in main senza che i controlli equivalenti ai hook siano rieseguiti server-side sul diff finale" (Codex). | Non scrivere wrapper husky/.zshrc per intercettare HUSKY=0. Scrivere required GitHub Action che replica lease-check + lint-launchagents server-side.                     |
| C3  | **`required_approving_review_count=1` universale = cargo cult**. (Gemini "CARGO_CULT_WITH_EXCEPTIONS", Codex "throughput tax senza sicurezza", DeepSeek "REJECT lato umano").            | Solo per PR Dependabot/bot non umani + hot-zone.                                                                                                                         |
| C4  | **CODEOWNERS auto-referenziale = no-op**. Cancellazione in commit `b8df2f996` corretta IF assenza di team reale.                                                                         | Ripristinare SOLO se mappa owner indipendenti per hot-zone.                                                                                                              |
| C5  | **Telegram alert real-time = solo eventi hot-zone**, digest periodico per il resto. Alert fatigue è il rischio principale.                                                               | Real-time per: direct push main, modifica branch protection/workflows/hook, hot-zone PR senza review, bot+admin merge same actor. Digest per HUSKY=0/--no-verify locale. |
| C6  | **L5.1 panel-pending fix > Gap #2 > Gap #3** in priorità.                                                                                                                                | Chiudere L5.1 4 difetti PRIMA di aprire spec nuove.                                                                                                                      |

## Divergenze

| #   | Divergenza                | Posizioni                                                                                                                                                                                                                         |
| --- | ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | **CODEOWNERS ripristino** | Gemini: NO (rumore). Codex: SÌ se mappa owner reali/indipendenti. DeepSeek: SÌ con scope ristretto (migrations, auth, workflows) per PR bot.                                                                                      |
| D2  | **Codex bot-reviewer**    | Codex: OK come required status check `LLM review passed` (NON come PR approval) + bot NON admin. Gemini: rischio "sindrome compiacenza LLM" — ok come segnale non-bloccante. DeepSeek: rischio "doppie allucinazioni", marginale. |
| D3  | **Priorità Gap #3**       | Gemini: P1 (CI fallback). Codex: P2 (telegram audit). DeepSeek: P1 (W34 dimostra abuse).                                                                                                                                          |

## Difetti tecnici del brief originale (caught by panel)

| #   | Quello che dicevo nel brief                                    | Difetto                                                                                                                                                   |
| --- | -------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| F1  | `.git/hooks/pre-commit` minimal che gira sempre                | **Falso**: se `core.hooksPath` punta altrove, git non chiama `.git/hooks/`. (Codex)                                                                       |
| F2  | `core.hooksPath` puntato a dir diversa che gira PRIMA di husky | **Falso**: git usa UN solo hooks path, non chain. Wrapper globale SOSTITUISCE husky, non lo precede. (Codex)                                              |
| F3  | Audit lato husky di HUSKY=0                                    | **Impossibile**: husky stesso non esegue niente quando HUSKY=0. Nessun hook husky può catturarlo. (3/3)                                                   |
| F4  | Server-side post-push detection                                | **Insufficiente**: per direct push a main, il danno è già in history. Serve required PRE-merge check. (Codex)                                             |
| F5  | "Gap #2 fa pensare a review umana"                             | **Riformulare**: vero gap è `bot admin con merge rights su main`. Soluzione: ridurre privilegi bot, non aggiungere review. (Codex amendment obbligatorio) |

## Failure modes mappati dal panel (mancanti nel brief originale)

1. **Same trust domain** (Codex): Antonello + Claude + Codex sono "attori diversi" su GitHub ma stessa workstation, stessi token, stesso keychain. Non è indipendenza forte.
2. **LLM review prompt injection** (Codex): PR description/comments possono istruire reviewer bot. Reviewer deve leggere diff via API, non eseguire branch.
3. **Approval stale race** (Codex): approval prima di push successivo. Serve `dismiss stale approvals` o `require approval of most recent reviewable push`.
4. **CI spoofing** (Codex): write users possono creare commit statuses. Required check con `expected source app` riduce spoofing.
5. **Required workflow skip-trap** (Codex): path filters / commit-message skip / conditional jobs / `job neutral` producono falso verde. Required wrapper deve girare SEMPRE e decidere internamente.
6. **Workflow self-modification** (Codex): PR che modifica `.github/workflows` non deve poter cambiare il proprio judge. Required check controllato da workflow protetto/base o GitHub App esterna.
7. **`pull_request_target` trap** (Codex): pericoloso se checkout codice PR con segreti.
8. **Lease stale/race** (Codex): lease al commit time ≠ merge time. Serve ricalcolo su latest base SHA, idealmente merge queue.
9. **Redis fail-open vs fail-closed** (Codex): hot-zone deve fail-CLOSED se Redis down. Non hot-zone può degradare con warning.
10. **`git commit --amend` bypass** (DeepSeek): pre-commit non scatta se amend non modifica staging area.
11. **Rename file critical** (DeepSeek): lease basato su path fallisce se `migration.sql` → `migration_backup.sql`. Lease basato su hash oggetto / pattern dinamici.
12. **HUSKY_SKIP_INSTALL / HUSKY_SKIP_HOOKS / CI=true** (DeepSeek): equivalenti funzionali di HUSKY=0 da neutralizzare.
13. **Attestation forgeability** (Codex): trailer `Hook-Verified: yes` inutile. HMAC locale solo poco meglio. Meglio re-run server-side.
14. **Alert blind spot** (Codex): Telegram bot token rotto/muted/rate-limit. Serve audit append-only in GitHub issues/log artifact + alert best-effort.
15. **Break-glass abuse** (Codex): "admin can bypass" senza audit = backdoor permanente. Richiede label/reason/issue link/TTL/actor allowlist/alert immediato.

## Proposta riformulata (post-panel) — priority-ordered

### P0 (urgente, prima di L5.1)

- **P0.1** Audit + downgrade privilegi Claude bot. Se admin, deve essere ridotto a `write` senza merge rights su main. Bot reviewer = no admin.
- **P0.2** Required server-side hot-zone check via GitHub Action che replica lease-check + lint-launchagents su diff finale al merge. Fail-CLOSED su Redis down (graceful degrade solo per file non-hot-zone). Required `source app expected` (anti-spoofing CI status). Workflow self-modification protetto.
- **P0.3** Required check deve girare SEMPRE (no path filter skip-success trap). Wrapper required decide internamente.

### P1 (dopo L5.1 chiuso)

- **P1.1** Branch protection main: `required_approving_review_count=1` SOLO per PR Dependabot + bot + hot-zone (CODEOWNERS scope-ristretto a migrations / auth / billing / pricing / .github/workflows). `dismiss stale approvals` ON. `require approval of the most recent reviewable push` ON.
- **P1.2** Audit append-only in GitHub issues per bypass events (HUSKY=0, --no-verify, direct push main). Telegram alert SOLO per hot-zone events. Canary periodico Telegram pipeline.

### P2 (nice-to-have)

- **P2.1** Best-effort wrapper `.zshrc` git alias che logga HUSKY=0/--no-verify localmente (Gemini dissent: nudge psicologico + metriche frequency).
- **P2.2** Digest settimanale Telegram con statistiche bypass.

### Reject (NON implementare)

- ~~Detect HUSKY=0 lato husky~~ (impossibile)
- ~~`.git/hooks/pre-commit` parallelo a husky~~ (falso assunto, single hooksPath)
- ~~CODEOWNERS auto-referenziale~~ (no-op semantico)
- ~~Telegram alert real-time per OGNI HUSKY=0~~ (alert fatigue)

## Cosa cambia rispetto al brief originale (sessione 026f2cd1)

| Brief originale                 | Riformulato post-panel                                                                                                            |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Gap #2 "require admin review"   | P0.1 + P1.1 — ridurre privilegi bot + review only PR-bot/hot-zone con anti-race                                                   |
| Gap #3 "Telegram audit HUSKY=0" | P0.2 + P1.2 — server-side replay + audit append-only GitHub + Telegram solo hot-zone                                              |
| (assenti)                       | 15 failure mode nuovi, in particolare: same trust domain, workflow self-modification, attestation forgeability, break-glass abuse |
| Priorità implicita "subito"     | L5.1 panel-pending fix > nuove spec                                                                                               |

## Next step

Spec P0 dedicata in `research/operations/specs/L5.2-server-side-enforcement-2026-05-26.md` (status: `draft`). 4-LLM review iter-2 pending prima rollout.
