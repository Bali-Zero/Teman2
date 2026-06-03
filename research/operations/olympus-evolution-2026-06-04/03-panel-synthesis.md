---
date: 2026-06-04
domain: operations
client_case: none (internal infra)
component: Olympus DB Guardian — multi-LLM panel synthesis
sources:
  - DeepSeek V4 Pro (reasoning_effort=high) — full red-team, /tmp/panel_deepseek.txt
  - Codex GPT-5.5 (sota-architecture-loop skill) — full red-team, /tmp/panel_codex2.txt
  - Gemini 3.1 Pro (agy) — FAILED (OAuth token expired, interactive re-login needed)
  - gemma3:27b local (Pro Ollama) — slow, not collected in time (non-blocking)
  - brief: /tmp/olympus_panel_brief.md (49 lines, gaps + thesis)
author: Claude Opus 4.8 (M5 session)
status: STEP 3 of 5 — panel synthesis complete (2 strong independent voices, converged)
---

# 03 — Panel Synthesis: red-team della tesi Olympus

> Quarto report. Ho sottoposto gap-analysis + tesi a un panel multi-LLM eterogeneo.
> Raccolti **3 voci indipendentemente convergenti**: DeepSeek V4 Pro + Codex GPT-5.5 + gemma3:27b
> locale (Pro Ollama). Gemini fallito (OAuth scaduto, non-bloccante).
> **3/3 convergono sul punto #1: il rischio architetturale in-process/superuser viene PRIMA
> dell'osservabilità.** Gemma: "proposed order is subtly dangerous and misses a fundamental risk →
> SAFETY FIRST; in-process is a massive risk → separate process." (unica divergenza: Gemma mette
> "rollback infra" come mossa-2-settimane, ma DeepSeek l'ha già confutato — rollback per DROP è
> impossibile → si tiene il Safety Envelope). La convergenza 3/3 di modelli con prior diversi è
> il segnale più forte possibile.

---

## 1. Il verdetto convergente (entrambi, indipendentemente)

> **La mia tesi era giusta nella direzione ("vedi e consuma prima di agire") ma SBAGLIATA
> nell'ordine: manca il primo cancello — il CONTENIMENTO.**

Entrambi i modelli, senza essersi parlati, hanno spostato il problema #1 da "pg_stat_statements
assente" a **"un servizio in-process con ruolo superuser fa manutenzione autonoma su prod"**.

- **Codex**: _"The biggest smell is not pg_stat_statements. It is this: an in-process app service
  with a superuser DB role is running autonomous maintenance on production. That is a blast-radius
  problem before it is an observability problem."_
- **DeepSeek**: _"Olympus runs in-process on a single 2GB Fly machine. Any memory leak, runaway
  VACUUM, or pool exhaustion from the guardian can crash the main application. This is the plan's
  largest hidden risk ... it dwarfs the gaps related to insight duplication."_

**Ho sottopesato questo. Loro hanno ragione.** Health=98 è una metrica che maschera: non misura
lock pressure, query load, crescita tabelle, né il delta prima/dopo le azioni.

---

## 2. Punti dove il panel ha CORRETTO la mia tesi

| #   | Mia tesi                                               | Correzione panel                                                                                                                                   | Chi              |
| --- | ------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------- |
| 1   | pgss primo (osservabilità prima)                       | **Contenimento primo**; pgss non riduce il rischio operativo attuale, lo fa il contenimento                                                        | Codex + DeepSeek |
| 2   | "rollback versionato → DROP unused index" come step L3 | **Fantasia**: non puoi rollback-are un DROP INDEX; e senza pgss non puoi provare che un indice sia inutilizzato                                    | DeepSeek         |
| 3   | confidence loop = feedback sano                        | **"Zero regole degradate dopo 20.504 azioni è sospetto"** — il modello confidence è probabilmente _cerimoniale_ (failure detection troppo stretta) | Codex            |
| 4   | pgstattuple = quick win osservabilità                  | **Attenzione**: pgstattuple scansiona l'intera tabella → spike I/O in-process. Va fatto con cautela/budget                                         | DeepSeek         |
| 5   | gap #8 robustezza loop = trasversale minore            | Merita un **circuit breaker**, non solo logging. Il rischio pool/InterfaceError è "sharp"                                                          | Codex + DeepSeek |

---

## 3. Punti dove il panel CONFERMA la mia analisi

- "Observability + consume before more actions" è **direzionalmente giusto** (entrambi).
- I quick-win zero-infra (digest insight + dedup + self-retention) sono **il miglior ROI immediato** (entrambi, esplicitamente).
- txid wraparound, matview failures, hypopg-absence sono **sovrappesati** — confermano le mie correzioni empiriche del report 02. Codex: _"Txid: verified low risk now. Track it, but do not center the roadmap."_
- NON saltare a L4/full-auto. Nessuna azione L3 finché in-process + superuser.

---

## 4. L'ordine CORRETTO (riscritto dal panel)

Mia proposta originale → ordine finale convergente:

| Fase | Mia v1                 | Panel-corrected (Codex order, DeepSeek concorda su 1-2)                                                                                                                                                                  |
| ---- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1    | pgss + metrics         | **CONTAIN**: demote role / narrow maintenance role; `statement_timeout` + `lock_timeout`; max azioni & max runtime per pulse; kill-switch operatore; write-action allowlist esplicita; circuit breaker su InterfaceError |
| 2    | digest+dedup+retention | **MAKE OUTPUT USEFUL**: retention olympus\_\*, dedup/supersede, weekly digest azionabile                                                                                                                                 |
| 3    | qualify                | **IMPROVE VISIBILITY**: pgss, pgstattuple (con budget I/O), lock/txid metrics                                                                                                                                            |
| 4    | rollback→L3            | **QUALIFY ACTIONS**: euristiche, replay window, misura before/after                                                                                                                                                      |
| 5    | —                      | **Solo allora**: prime azioni L3 gated                                                                                                                                                                                   |

**Differenza chiave**: il contenimento (privilegi, timeout, budget, kill-switch) viene PRIMA
dell'osservabilità. Perché: pgss migliora la _qualità_ degli insight ma non riduce il _rischio
operativo attuale_. Il contenimento sì.

---

## 5. La mossa a più alta leva per le prossime 2 settimane (consenso)

Entrambi convergono su un singolo deliverable. Codex lo nomina **"Olympus Safety Envelope"**:

1. **Demote** `backend_rag_v2` da superuser O split Olympus in un ruolo di manutenzione ristretto
   (interseca cicatrix W38 già speccato).
2. **Timeout**: `statement_timeout`, `lock_timeout` su ogni azione pulse.
3. **Budget**: max azioni per pulse, max runtime per pulse.
4. **Kill-switch** operatore esplicito (DB/env) — oltre a DISABLE_BACKGROUND_WORKERS.
5. **Self-retention** delle tabelle olympus\_\* (drop partizioni vecchie + prune actions/insights).
6. **Weekly digest** da insight dedup-ati → Telegram operatore.

Effetto (Codex): _"converts Olympus from 'trusted autonomous actor' into 'bounded operator with
auditable output'. It also prepares the system for pgss and later L3 actions."_

DeepSeek lo restringe ulteriormente per "2 settimane reali": _"Ship a weekly insight report to
Telegram and add a simple DELETE-based retention ... maybe 50 lines of code ... Every other
improvement is wasted until those insights are consumed."_ → cioè i punti 5-6 sono i più rapidi;
1-4 (envelope vero) sono il cuore ma più impegnativi.

---

## 6. Rischi che il panel ha aggiunto (non nella mia gap-analysis)

1. **Confidence cerimoniale** (Codex): 13 regole tutte a 1.0 dopo 20.504 azioni → o la failure
   detection è troppo stretta, o i success criteria troppo deboli. Il feedback loop forse non
   misura nulla di reale. **DA INDAGARE in spec.**
2. **In-process blast radius** (entrambi): bug del guardiano → latenza app + pool + memoria + stato
   DB simultaneamente. Estrazione in worker/machine separata = obiettivo a medio termine.
3. **Insight growth poisons decision quality** (Codex): non è solo storage; 8.242 righe duplicate
   degradano la qualità di qualsiasi futura decisione basata su di esse.
4. **pgstattuple I/O spike in-process** (DeepSeek): l'osservabilità "gratis" non è gratis se gira
   nel pool dell'app.

---

## 7. Sintesi per la spec (04)

La spec deve ribaltare l'ordine: **Safety Envelope PRIMA, osservabilità DOPO**. La struttura:

- **Phase 0 — Safety Envelope** (contenimento): timeout, budget, kill-switch, circuit breaker,
  retention, role-narrowing. Questo è il P0.
- **Phase 1 — Consume** (output utile): dedup/supersede insight, weekly digest. Quick win.
- **Phase 2 — See** (osservabilità): pgss (gestendo restart+W38), pgstattuple budget-ato, txid/lock.
- **Phase 3 — Qualify** (euristiche, before/after).
- **Phase 4 — Extract & L3** (worker separato + prime azioni gated). Lungo termine.

* una **investigazione** trasversale: il confidence loop misura davvero qualcosa? (Codex catch).

→ 04: scrivere la spec SDD con questa struttura, falsifiable success metrics per fase, rollout.
