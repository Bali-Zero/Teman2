# 02 — Dispatch resilience log: 4 LLM, retry chain, root causes

**Data**: 2026-04-29 21:30-21:45 WITA
**Orchestratore**: Claude Opus 4.7 max effort, sessione Track C3 Innervation
**Lesson principle (cita SYMBIOSIS Legge 4)**: graceful degradation — se un LLM cade, il dispatch ai 3 restanti continua. Loggo qui tutti gli errori + riparazioni in modo che la prossima sessione non rifaccia gli stessi tentativi.

---

## 1. Dispatch round 1 (parallelo)

| LLM | Comando lanciato | Esito |
|---|---|---|
| Gemini 3.1 Pro | `gemini -m gemini-3.1-pro-preview --sandbox --approval-mode plan -p "<brief>"` | ❌ HTTP 429 — `MODEL_CAPACITY_EXHAUSTED` "No capacity available for model gemini-3.1-pro-preview on the server" |
| Codex GPT-5.5 | `codex exec --sandbox read-only --model gpt-5.5 --output-last-message <out> "<brief>"` | ⏳ Still running (>2 minuti, normale) |
| DeepSeek v4 Reasoner | Python via `backend.llm.deepseek_client.DeepSeekClient` | ❌ ImportError: classe DeepSeekClient non esiste |
| NotebookLM | `nlm cross-notebook-query --notebooks NB-1,NB-14 ...` | ❌ Sintassi inesistente: nessun subcommand `cross-notebook-query` né `notebook_query` |

## 2. Triage + retry round 2

### 2.1 Gemini — retry rimandato

429 capacity exhausted è **server-side** Google: non riprovo subito (rispetto rate limit), riproverò più tardi. Memory check: brainstorm capacity exhaustion è già pattern documentato (vedi `lessons.md` 2026-04-29 wave 2 pro: "Codex usage limit + Gemini 3.1 Pro 429 + NotebookLM API errors simultanei"). Lesson: aspetto 5-10min, oppure procedo 3/4 senza Gemini se gli altri 3 sono solidi.

**Fallback secondario** (non eseguito ancora): `gemini -m gemini-2.5-flash` (free tier diverso).

### 2.2 DeepSeek — fix API signature

API reale: `complete_async(prompt, *, model, system, max_tokens, temperature, ...)` — singolo `prompt` string, NON OpenAI-style `messages` list.

Retry chain:
1. Prova 1: `messages=[{"role": "user", "content": ...}]` → `TypeError: complete_async() got unexpected kwarg 'messages'`
2. Prova 2: `prompt=<brief>` → `DeepSeekAuthError: DEEPSEEK_API_KEY env var is not set`
3. Prova 3: `set -a && source ~/.nuzantara-secrets.env && set +a` poi `prompt=<brief>` → in flight (PID rilanciato 21:38)

**Lesson per future agent sessions**: il client `backend.llm.deepseek_client` espone funzione `complete_async`, NON una classe `DeepSeekClient`. Signature single-prompt, non chat-completion list. La env key DEEPSEEK_API_KEY vive in `~/.nuzantara-secrets.env`.

### 2.3 NotebookLM — sintassi giusta

Vera sintassi: `nlm notebook query <NOTEBOOK_ID> "<question>" [--timeout 180]`. NON c'è batch cross-notebook nativo.

Fix: 2 query separate, una per NB-1 e una per NB-14, in parallelo.

NB IDs trovati via `nlm notebook list`:
- NB-1: `f6ecd115-dd89-4c9b-b3dd-071e0e2f1876` ("NB-1: Nuzantara Codebase & Architecture")
- NB-14: `1e5f9b04-9485-4620-a775-801b7e6b0395` ("NB-14: Claude Code Session Memory")

**Lesson per future agent sessions**: `nlm notebook query <UUID> "<text>"` è il comando canonico. Non esistono subcommand `notebook_query` o `cross-notebook-query`. NB IDs vanno risolti via `nlm notebook list` (output JSON parsabile).

### 2.4 Codex — wait

Codex con `--sandbox read-only` su un brief denso (3KB) richiede 3-10 minuti. Non interrompo, lascio finire. PID 46280 attivo.

---

## 3. Stato finale FASE 1 dispatch (aggiornato a runtime)

| LLM | Output file | Word count | Verdict |
|---|---|---:|---|
| Gemini 3.1 Pro | `docs/innervation-2026-04-29/03_gemini_dependency_graph.md` | TBD | TBD |
| Codex GPT-5.5 | `docs/innervation-2026-04-29/04_codex_existing_signals.md` | TBD | TBD |
| DeepSeek v4 | `docs/innervation-2026-04-29/05_deepseek_minimum_contract.md` | TBD | TBD |
| NotebookLM | `docs/innervation-2026-04-29/06_notebooklm_history.md` | TBD | TBD |

Threshold accettazione: **3/4 con output sostanziale (>1000 words ognuno)**. Sotto questo, FASE 2 design diventa unilaterale Opus → rischio bias single-LLM (vedi cicatrix Wave 3 2026-04-22 "scar: parser test passava unit, falliva e2e").

---

## 4. Strategia decisione FASE 2 (in caso di output incompleto)

Se 1 LLM manca:
- Gemini manca → vado con Codex (signals) + DeepSeek (3 proposte) + NLM (storia). Mancherà la dependency graph cross-organ — la costruisco io leggendo il codice (slow ma fattibile).
- Codex manca → vado con Gemini (deps) + DeepSeek (proposte) + NLM. Mancherà il catalog signals — uso ripgrep manualmente.
- DeepSeek manca → **HARD STOP**: senza le 3 proposte, FASE 2 protocol decision diventa improvvisazione. Aspetto retry indefinito.
- NLM manca → vado con i 3 senza storia. Rischio: ripetere errori passati. Mitigazione: leggo manualmente `cicatrix-scars.md` + git log degli ultimi 30gg.

---

## 5. Cosa NON ho fatto e perché

- **NON** ho usato API HTTP Anthropic (Golden Rule #13).
- **NON** ho duplicato il dispatch su Claude OAuth `claude` CLI come "5° opinion" — sarei io stesso, conflitto di interesse + violazione spirito del red-team multi-LLM.
- **NON** ho aspettato Gemini retry sincrono — se 429 persiste ho già 3 LLM con prospettive distinte (signals/contract/storia) sufficienti per decision in FASE 2.

---

## 6. CICATRICE auto-pull file loss (2026-04-29 ~21:42 WITA)

**Trauma**: durante il dispatch parallelo dei 4 LLM, è arrivato un **`git pull origin main --ff-only` automatico da nuz-sync watchdog** (LaunchAgent `com.nuzantara.nuz-sync.plist`). Reflog evidence:
```
HEAD@{0}: merge origin/main: Fast-forward
HEAD@{1}: reset: moving to origin/main
HEAD@{2}: checkout: moving from feature/innervation-2026-04-29 to main
```

Effetti collaterali:
1. `git checkout` da feature branch → main, autostash di file modificati tracciati (CLAUDE.md, lint, escalations) in `stash@{0}` etichettato `feature-innervation-temp-2026-04-29`.
2. **File untracked NON vanno in stash**. I miei `00_design_intent.md` e `01_innervation_matrix.md` (creati con Write tool, mai `git add`) sono finiti **sovrascritti dal pull merge** (la directory `docs/innervation-2026-04-29/` non esisteva nel branch main, quindi il merge l'ha lasciata stata ma il subsequent reset ha cancellato file untracked).
3. Sopravvissuti solo i file 02-06 perché creati DOPO il merge auto.
4. `git fsck --unreachable` non ritrova i 2 file persi → mai indexati come blob.

**Antibody applicato**:
- **Recovery**: ricostruito `00_design_intent.md` e `01_innervation_matrix.md` integralmente dal context di sessione orchestrator (Claude Opus 4.7 1M ctx — i file erano ancora completamente in conversation memory).
- **Switch back**: `git checkout feature/innervation-2026-04-29` per tornare sul branch corretto.
- **Commit immediato**: dopo restore, `git add docs/innervation-2026-04-29/ && git commit` per indexare i file come blob — qualsiasi auto-pull successivo non li toccherà più.

**Lesson per future agent sessions**:
1. **`git add` IMMEDIATAMENTE dopo Write tool** sui file in repo, non aspettare la fine fase. Costo: 0. Beneficio: protezione da auto-pull/auto-stash.
2. **nuz-sync watchdog è invisibile ma molto attivo**. LaunchAgent `com.nuzantara.nuz-sync.plist` può intervenire in qualsiasi momento. Considera una sessione long-running con file untracked come transient state vulnerabile.
3. **Branch awareness**: dopo ogni `git` interaction, verifica `git rev-parse --abbrev-ref HEAD` — un auto-pull può cambiare branch sotto i piedi.
4. **Backup orchestrator context**: per file critici (>5KB di lavoro intellettuale), considera `cp` parallel a `/tmp/<file>.bak` come second-line protection.

**Cicatrice da aggiungere a `.claude/rules/cicatrix-scars.md`** (proposta in FASE 4 doc finale): "Untracked files in long-running session vulnerable to auto-pull / auto-stash from nuz-sync watchdog. Mitigation: `git add` immediately after Write tool".

**Costo recupero**: ~10 minuti orchestrator, 0 token LLM (ricostruzione da context, no re-dispatch).
