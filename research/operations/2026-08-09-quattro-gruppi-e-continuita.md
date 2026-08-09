---
date: 2026-08-09
adversarial_review: exempt-historical-input-consolidated-and-corrected-by-2026-08-10-fleet-order-spec
---

# I Quattro Gruppi e l'Architettura di Continuità

> Data: 2026-08-09 · Compagno di: Harness v2 + Roster Flotta (stesso giorno)
> Mandato Zero: (1) Conduttore = ruolo, non modello; (2) fallback fluidi su account E modelli — nessuna linea si ferma mai; (3) studio dei 4 gruppi; (4) config al massimo potenziale.
> Esiti operativi: `FLEET_TOPOLOGY.json` (nuovo SSOT cloud) · AGENTS.md §17 · codex.md §7 · GEMINI.md §Conduttore · `kimi.md` + `qwen.md` (nuovi).

---

## 1. Anthropic — 4 account (governo, mani, gate)

**Cosa possediamo:** 4 account (slot A1–A4 in FLEET_TOPOLOGY — Zero mappa le email reali). Modelli: Fable 5, Opus 5, Sonnet 5, Haiku 4.5 via CLI/OAuth (SDK bannato da costituzione).

**Meccanica quote:** finestre 5h + cap settimanali per account; Fable con allowance settimanale dedicata sul seat che la include.

**Rotazione:** i profili OAuth si scambiano (pattern claude-swap/cswap): backup credenziali in Keychain, `cswap auto` ruota proattivamente al 90% della finestra verso l'account con più quota residua, con lock anti-collisione e isteresi anti flip-flop; `cswap run` consente sessioni parallele su account diversi. **PENDING-ARMS: installazione+test su Pro e Air-M5** (va provato dal Mac, non da qui).

**Strategia d'uso (lane-affine, NON round-robin):** A1 interattiva+gate · A2 subagenti/build · A3 cron/batch · **A4 riserva strategica: backup del gate PRIMA di tutto**. Ratio: il round-robin brucia tutte le finestre in parallelo e ti lascia senza gate proprio nei picchi; la riserva vergine garantisce che il Giudice abbia sempre benzina. Con 4 account, "window dead → SUSPEND" del gate diventa "TUTTE E QUATTRO dead → SUSPEND": stessa invariante, 4× la pista.

## 2. OpenAI — 2 account (spada avversaria)

**Cosa possediamo:** 2 abbonamenti ChatGPT (O1, O2) con Codex CLI (Sol = refuter, Terra/Luna = builder).

**Meccanica rotazione:** `CODEX_HOME` separati (`~/.codex` = O1, `~/.codex-o2` = O2), ciascuno con il proprio `auth.json`; alias `codex-o1`/`codex-o2`. **Attenzione:** `--profile` cambia modello/settings, NON identità. Nessun failover automatico nativo → è il Conduttore che ruota esplicitamente. Due abbonamenti propri con propri metodi di pagamento = uso conforme ai ToS; è la condivisione di credenziali con terzi ad essere vietata.

**Lane:** O1 = refuter primario (Sol xhigh/max — il Pubblico Ministero non deve mai restare a secco); O2 = builder Terra/Luna + backup Sol. Sandbox obbligatoria invariata (`read-only`/`workspace-write`).

## 3. Google — AI Ultra (sensi, esplorazione, red team)

**Fatto nuovo rilevante:** Gemini CLI è **deprecato dal 2026-06-18** → la porta è **Antigravity/agy** (il repo era già posizionato bene). ⚠ `MODEL_TOPOLOGY.json` ha ancora `cloud_fallback: google-gemini-cli/...` → da riconciliare in v3.

**Meccanica quote AI Ultra:** quota più alta dei tier, **refresh ogni 5 ore** + cap settimanali; il consumo è pesato sulla complessità del lavoro, non sul conteggio prompt; overage acquistabile a crediti → per noi è spesa per-token: **richiede GO** (spend order §17.4).

**Lane:** agy explore/normative-search/redteam pre-deploy (fence candidate-only invariata) · NotebookLM Oracolo · Antigravity braccio recintato (4 NO) · Jules resta CANDIDATE non armato.

## 4. Alibaba — Token Plan (l'ala cinese unificata)

**Cosa possediamo (da ieri):** Token Plan su Model Studio, regione Singapore — un solo seat con API key che copre Qwen 3.8 Max/3.7, GLM 5.2, MiniMax 2.5, Kimi, DeepSeek (seat RETIRED — disponibilità ≠ riarmo), Wan. Crediti mensili (tier $30/$100/$200), endpoint OpenAI-compatible E Anthropic-compatible.

**Ruoli:** da roster — Qwen Max = Terzo Polo · GLM 5.2 = Contro-Costruttore · MiniMax 2.5 = Macinatore. Dettagli operativi e divieti in `qwen.md`. **PROBATION fino a PROBE-1** (key, modelli visibili, burn-rate).

**Moonshot a parte:** Kimi resta armato via piano Allegro flat + CLI (`kimi.md` nuovo, con fence zero-trust motivata dall'incidente AISI).

---

## 5. Architettura di Continuità — "nessuna linea si ferma mai"

**La scala (in ordine, ogni salto loggato nell'evidence del task):**

1. **Rotazione account, stesso modello** — perdita di qualità zero. È il gradino che il piano v1 non aveva: con 4+2 account, la maggior parte degli esaurimenti si risolve qui.
2. **Sostituzione di modello nello stesso ruolo** — catene per-ruolo in `FLEET_TOPOLOGY.json` (builder: sonnet→codex→glm · refuter: sol→k3→gemini · grunt: haiku→locale→minimax).
3. **Fallback cross-famiglia** — consentito ma marchiato `degraded_execution: true` nel pack: il gate DEVE vedere che il task ha viaggiato degradato.
4. **Coda, mai stop silenzioso** — catena morta → PENDING-ARMS con motivo e timestamp. Un task fermo dichiarato è sano; una linea ferma zitta è la malattia.

**Le tre eccezioni senza scala:**
- **Gate finale:** solo Fable — rotazione tra A1→A4→A2→A3 sì, sostituzione MAI, pagamento MAI. Tutte le finestre morte → SUSPEND.
- **PII:** solo locale (SEA-LION & flotta MODEL_TOPOLOGY) → coda. Mai cloud, nemmeno degradato.
- **Client-facing:** solo sessione Anthropic interattiva.

**Regola di diversità nel fallback refuter:** il quorum Gear 3 richiede 2 famiglie diverse — la rotazione non deve mai collassare la refutazione su una famiglia sola (se succede → degraded, il gate lo vede).

**Conduttore-come-ruolo (punto 1 di Zero):** qualsiasi orchestratore di frontiera può condurre la sessione (claude/codex/agy/kimi). La legge non cambia col conducente perché lo ship è **meccanico**: PR → required checks (CI + AI-review + check `harness/fable-gate` sui Gear 3) → auto-merge armato → deploy via CI. Il potere del Conduttore è orchestrare; il potere di shippare sta nei check. Una legge, molte porte: CLAUDE.md (claude) · codex.md (codex) · GEMINI.md (agy) · kimi.md (kimi) · qwen.md (ala Token Plan) — tutti puntano ad AGENTS.md §17 e a FLEET_TOPOLOGY.json.

---

## 6. Pending & Probe (in ordine di leva)

| # | Azione | Dove | Note |
|---|---|---|---|
| 1 | Zero mappa le email reali su A1–A4 / O1–O2 | FLEET_TOPOLOGY.json | 2 minuti, sblocca tutto |
| 2 | cswap (o equivalente) installato+testato | Pro + Air-M5 | sessione Mac; poi `cswap auto` con soglia 90% |
| 3 | `~/.codex-o2` login + alias | Air-M5/Pro | 5 minuti |
| 4 | PROBE-1 Token Plan: key, tier, modelli, burn-rate 3 task campione, Qoder? | Model Studio | sblocca GLM/Qwen/MiniMax load-bearing |
| 5 | PROBE-2/3/4 (K3 refuter multimodale · via CLI Qwen · lotto MiniMax) | — | da roster |
| 6 | `scripts/seat_dispatch.py` legge FLEET_TOPOLOGY e sceglie seat+account | repo | serve test live CLI → sessione Mac |
| 7 | MODEL_TOPOLOGY v3: `cloud_fallback` (gemini-cli morto) + `aider_fix` (deepseek RETIRED) | repo | toccare con cautela: i cron lo leggono |
| 8 | AGENTS.md §15 refresh completo era-5-family | repo | oggi solo flaggato in §17.4 |

**Fonti:** report flotta 2026-08-09 · docs Alibaba Token Plan · claude-swap (GitHub realiti4) · ProxyLLM su CODEX_HOME multi-account · Antigravity plans/blog (deprecazione Gemini CLI, quota Ultra) · AGENTS.md/codex.md/GEMINI.md/MODEL_TOPOLOGY.json del repo.
