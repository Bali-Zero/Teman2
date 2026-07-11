---
date: 2026-06-05
domain: operations
client_case: none
sources:
  - cc-setup-self-audit workflow (18 agents, 147 inventory items, 12 verified recs) — run wf_bbaf62f1-f80
  - Empirical re-verification (git check-ignore, lsof :5432, wc -c MEMORY.md, launchctl plist count)
  - anthropics/claude-plugins-official — claude-code-setup plugin (read-only recommender, baseline)
  - .claude/rules/cicatrix-scars.md (W64, W65, 2026-04-29 plist-secret, 2026-06-02 503 split-brain)
---

# Claude Code setup — self-audit (replica del plugin `claude-code-setup`, calibrato anti-duplicato)

## Contesto

Il plugin ufficiale Anthropic `claude-code-setup@claude-plugins-official` è un **raccomandatore read-only**:
scansiona il repo e suggerisce hook/skill/MCP/subagent/command/automazioni mancanti. È già installato dal
2026-03-02 ma **non abilitato**. Per un setup vanilla è utile; per Nuzantara (setup iper-avanzato: 147 item già
esistenti) il valore sta tutto nell'**anti-duplicato**. Questo audit lo replica con un workflow multi-agente:
6 scanner inventory in parallelo → gap-scan per categoria → verify adversariale (refute) per categoria → sintesi.

## Inventory baseline (cosa esiste GIÀ — 147 item)

| Categoria      | #     | Coverage                                                                                                                                                                                                                                            |
| -------------- | ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| hooks          | 36    | Eccezionalmente profonda. Lifecycle completo + guardrails daemon fail-closed + worktree-isolation + stop_verify. **Trap**: `.git/hooks/` legacy INERTI (core.hooksPath→.husky); `.pre-commit-config.yaml` non wired. Rischio = sprawl, non assenza. |
| mcp-servers    | 17    | Molto ricca (6 first-party + postgres-ro + github + ga4 + ocr). Overlap (github MCP vs gh, ocr-tesseract vs qwen2.5vl). Cloud connectors = superficie egress Law 2.                                                                                 |
| subagents      | 43    | Matura (WR2=8, WR3=13, ops cluster, reviewer). Tutti **user-scoped** (`.claude/agents/` di progetto VUOTO).                                                                                                                                         |
| skills         | 29    | 15 custom + 250+ da plugin. Sbilanciata: archivi `_archive-*` hanno ritirato db-migration/crm/vector-search senza rimpiazzo.                                                                                                                        |
| slash-commands | 13    | 6 custom (/verify /scar /resume /dispatch-stat /subhi /codex-second-opinion) + 7 da plugin. Tarati sui pain noti.                                                                                                                                   |
| automations    | 9→213 | Dominante. **217 plist live vs 77 tracked** in git. AUTOMATIONS_REFERENCE = 213 job, 25 failed, 10 TERMINAL, 10 DLQ. Gap = HEALTH non assenza.                                                                                                      |

## 12 raccomandazioni verificate → 6 bisogni distinti

**Insight dell'orchestratore (non visibile ai sub-agent per-categoria)**: 3 categorie hanno proposto lo STESSO
bisogno in forma diversa. I 12 finding collassano in **6 bisogni**, 2 dei quali con 3 forme alternative
(scegline UNA, non implementarle tutte).

### 🔴 CLUSTER A — Law 2 / OSINT enforcement (FINDING #1: hard-rule top-line con ZERO backstop oggi)

La sovranità OSINT (Law 2) è una hard-constraint top-line **senza alcun hook che la enforci**. L'unica
consapevolezza è `mos_capture_post_tool.py` che LABELS ma non blocca. Due superfici **complementari**:

- **A1 — hook MCP cloud-egress block** (estende `guardrails-static.py`): BLOCK (exit 2) quando un cloud-write
  MCP tool (`google-workspace docs/gmail/drive`, `claude_ai Canva/Drive/Gmail`, `notebooklm source_add`,
  `github push`) riceve payload che matcha SENSITIVE_PATHS/PII già definiti. Riusa plumbing esistente. **P1, effort medium.**
- **A2 — pre-commit path-gate** (Husky): HARD-BLOCK commit di `research/*/clients/`, `*-case.md`, DOSSIER\_\*, contenuto PII. **P1, effort low.**
- ✅ **Mitigazione immediata GIÀ APPLICATA (2026-06-05)**: aggiunti pattern `research/*/clients/`, `research/**/*-case.md`,
  `*-guidance.{html,pdf}` a `.gitignore`. Verificato: `research/visa/clients/` (file Marc Buckner reale, untracked) ora IGNORED.
  Rischio era LATENTE (un `git add -A` dal cloud Vercel), non breach avvenuta.

### 🟠 CLUSTER B — MEMORY.md overflow (BROKEN ADESSO: 39.629 byte = 1.6x il limite 24.440, troncamento silenzioso)

Verificato live questa sessione (anche nel system-reminder di SessionStart). Il MOS carica un index TRONCATO →
memorie importance≥7 silenziosamente non caricate. `mem` CLI non ha trim/compact/archive. **3 forme proposte — scegline 1:**

- B-cmd — **/mem-trim** (command, on-demand, operator y/n) — _consigliato: più pragmatico_. P1.
- B-skill — memory-index-curator (skill). P1.
- B-agent — mos-curator (subagent, **declassato a P2**: `alzheimer-hook.sh` già alerta su >25600 byte; net-new = solo per-line >200char + orphan-detection tra 424 topic file).

### 🟠 CLUSTER C — Fly split-brain / deploy-desync (scar 2x in un giorno il 2026-06-02)

`/health=200` maschera un rag worker morto; un deploy CI non force-boota una macchina autostop crash-loopata.
`nuzantara-deploy` skill controlla solo `/health` → avrebbe PASSATO durante l'outage. **Bonus**: la skill ha pure
il build-context SBAGLIATO (`cd apps/backend-rag` invece di repo-root). **3 forme — scegline 1:**

- C-skill — **fly-split-brain-verify** (skill) — _consigliato: si innesta in nuzantara-deploy e corregge il bug build-context_. P1.
- C-cmd — /fly-desync (command, triage on-demand). P1.
- C-agent — deploy-desync-triage (subagent). P1.

### 🟡 CLUSTER D — Fleet health (2 complementari, entrambi P1 low)

- **D1 — plist snapshot DR**: LaunchAgent daily che esporta i 217 plist live in git (XML secret-redatto). Il P0 cicatrix
  2026-04-29 (51 plist truncati, recovery solo da `launchctl print` effimero) sarebbe stato "git checkout". 217 live vs 77 tracked.
- **D2 — chronic-failure digest**: digest settimanale "red-for-N-days" sui job. `audit-launchd-daily.sh` è DELTA-only
  → un job rosso da >1 giorno diventa invisibile (famiglia W55 suppression).

### 🟢 CLUSTER E — quick wins indipendenti (P1 low)

- **E1 — /escalations**: triage HIGH-first di `shared/escalations_pro.jsonl` (24 entry, tutte dlq NORMAL ripetute) +
  `~/.agent/decisions/claude_tasks/` (507 file, 4 HIGH). Ritual CLAUDE.md §2/§14 mandato ma non automatizzato.
- **E2 — postgres-nuzantara-local MCP**: read-only sul Postgres LOCALE `127.0.0.1:5432/nuzantara_dev` (corpus WhatsApp
  OSINT live, 26.755 righe). L'MCP esistente punta al Fly cloud frozen pre-cutover → il corpus live NON ha MCP surface oggi.

## Sequenza consigliata

1. ✅ `.gitignore` PII (fatto). 2. A2 pre-commit gate (low, chiude la stessa superficie permanentemente).
2. B-cmd /mem-trim (broken adesso). 4. C-skill fly-split-brain-verify. 5. E1+E2 quick wins. 6. D1+D2 fleet health.
3. A1 hook MCP-egress (effort medium, ma è l'enforcement vero di Law 2). mos-curator/forme duplicate: SKIP.

## Nota metodologica

0 raccomandazioni droppate su 12 NON è consenso cieco: i `verify_reason` contengono verifiche empiriche reali
(lettura `guardrails-static.py`, `git check-ignore`, `lsof :5432`, lettura `nuzantara-deploy/SKILL.md`), e il verifier
ha declassato mos-curator P1→P2. I gap-scanner hanno prodotto poche rec già molto mirate (con `not_duplicate_because`
forte), confermate dal verify. Finding di sicurezza ri-verificati indipendentemente dall'orchestratore (cicatrix W65 GOTCHA).
