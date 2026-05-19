---
date: 2026-05-19
domain: operations
client_case: Claude Code best configuration May 2026 for Nuzantara-class stack
sources: 14
---

# Claude Code best configuration — Maggio 2026

**Trigger**: post-diagnosi regression Nuzantara (2026-05-19). Antonello chiede ricerca cross-source su miglior config Claude Code per stack come il nostro (monorepo 24 apps, multi-LLM cascade, Pro+Mini, 60+ MCP tool, autonomous L2).

**Sintesi 1 frase**: Anthropic ha rilasciato strumenti progressive-disclosure (Tool Search 2.1.7, Skill-3-layer loading, hierarchical CLAUDE.md, ENABLE_TOOL_SEARCH=auto) che risolvono in modo strutturale i 3 problemi della nostra config attuale — context saturation, MEMORY.md truncation silenziosa, tool schema bloat — ma vanno adottati esplicitamente, non sono default per setup legacy come il nostro.

---

## 1. Stato 2026 — feature critiche da adottare (verified cross-source)

### A. ENABLE_TOOL_SEARCH (Claude Code ≥2.1.7) — **PRIORITÀ MASSIMA**

| Cosa                       | Quote source                                                                                                                                                                                                                                             |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Default behaviour          | "Tool search keeps MCP context usage low by deferring tool definitions until Claude needs them. Only tool names load at session start, so adding more MCP servers has minimal impact on your context window." ([Anthropic docs via NB-AGENTS source 33]) |
| Modes                      | `true` (defer all), `auto` (defer overflow only, threshold 10% context), `false` (legacy load all) ([NB-AGENTS source 34])                                                                                                                               |
| Vincolo                    | "Requires Sonnet 4 and later, or Opus 4 and later. Haiku models do not support tool search."                                                                                                                                                             |
| Esonero per server critici | `alwaysLoad: true` nella `.mcp.json` di un server espone tutti i suoi tool upfront ([NB-AGENTS source 35])                                                                                                                                               |

**Nostra config attuale** (`settings.json`): `ENABLE_TOOL_SEARCH=auto:5` — già attivo con override soglia 5%. **Verifica che funzioni davvero** è da fare empiricamente, perché this session ho visto `~100+ deferred tools listed` (positivo, indica deferral attivo) MA anche `7 system-reminder` con full MCP server descriptions (segno che `alwaysLoad` o legacy load è ancora attivo da qualche parte).

### B. Hierarchical CLAUDE.md — pattern monorepo (verified Anthropic docs + Medium + GitHub bestpractice)

Anthropic supporta **stratificazione automatica** di CLAUDE.md:

```
~/.claude/CLAUDE.md                          # user-level (sempre caricato)
<repo-root>/CLAUDE.md                         # project root (caricato in repo)
<repo-root>/.claude/CLAUDE.md                 # alternative project location
<repo-root>/apps/<app-name>/.claude/CLAUDE.md # nested app-specific (lazy)
```

Quote: "Project skills load from `.claude/skills/` in your starting directory and in every parent directory up to the repository root, supporting monorepo setups where packages have their own skills. When you work with files in subdirectories below your starting directory, Claude Code also discovers skills from nested `.claude/skills/` directories on demand."

**Implicazione per Nuzantara**: `apps/backend-rag/CLAUDE.md`, `apps/mouth/CLAUDE.md`, `apps/wa-mirror/CLAUDE.md` esistono e dovrebbero essere lazy-loaded SOLO quando lavoro in quei subtree. Verifica: il nostro CLAUDE.md root 29.6KB potrebbe scendere a ~15KB delegando 50% a CLAUDE.md per-app.

**Limit confermato**: "Only the first 200 lines or 25 KB of auto memory are loaded into each conversation" ([Anthropic docs via MindStudio + DEV community]). **Stesso identico limit** che colpisce MEMORY.md.

### C. Skill 3-layer progressive disclosure (Anthropic docs verbatim)

| Layer                                                  | Cosa carica          | Quando                            |
| ------------------------------------------------------ | -------------------- | --------------------------------- |
| 1 — Metadata (name + description)                      | ~100 token/skill     | Sempre, SessionStart              |
| 2 — SKILL.md body                                      | < 5.000 token target | Solo quando skill viene triggered |
| 3 — Bundled resources (references/, scripts/, assets/) | Unlimited            | On demand quando Claude le chiede |

Anti-pattern documentati:

- "Keep SKILL.md lean: Target 1,500-2,000 words for the body" ([NB-AGENTS source 30])
- "Move detailed content to references/" — patterns, advanced techniques, migration guides, API references
- "Avoid duplication: Information should live in either SKILL.md or references files, not both"

**Implicazione**: il nostro `bali-zero-brand/constitution.md` è **41.352 byte** (vs target ≤3.000 token = ~12KB). Dovrebbe essere spezzato — articles core in `SKILL.md`, articles dettagliati in `references/constitution-detail.md`.

### D. Subagent isolation pattern — orchestrator dispatch

| Pattern                                                                                                                             | Source                  | Implicazione                                                                                                                                         |
| ----------------------------------------------------------------------------------------------------------------------------------- | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| "Sub-agents are isolated from each other. Each sub-agent only knows what the orchestrator passes to it in its initial instructions" | Anthropic docs          | I nostri agent definitions (wr2-_, wr3-_, regulatory-watcher) NON ereditano MEMORY.md/CLAUDE.md context — solo prompt iniziale + skill esplicite     |
| "Sub-agents prevent context bloat by isolating exploration in clean context windows, returning only summaries"                      | DataCamp + claudefa.st  | Pattern corretto: spawn subagent per ogni esplorazione codebase, non eseguirla nell'orchestrator                                                     |
| Pitfall: "Zero-Shot Verifier Isolation Trap"                                                                                        | NB-AGENTS Voyager paper | Quando spawni subagent verifier, **deve essere isolato dalla parent's CLAUDE.md** altrimenti eredita la bias. Pilot 2026-05-13 math-auditor leakato. |

### E. Hooks: SessionStart vs PreToolUse vs PostToolUse

Quote verificate ([NB-AGENTS source 36-41]):

| Hook                   | Use case ✅                                                                    | Anti-pattern ❌                                                 |
| ---------------------- | ------------------------------------------------------------------------------ | --------------------------------------------------------------- |
| **SessionStart**       | "Loading development context like existing issues or recent changes"           | "Don't load heavy scripts here, as they delay every CLI launch" |
| **SessionStart**       | Persistere env var via `$CLAUDE_ENV_FILE` per Bash subseguenti                 | Dumping di tutto upfront — "use selective output"               |
| **PreToolUse**         | Security policy enforcement (block `rm -rf /`), prompt-based con LLM reasoning | —                                                               |
| **PostToolUse**        | Sanitize/format tool outputs, additionalContext per inject feedback a Claude   | —                                                               |
| **Per static context** | "Use CLAUDE.md instead" (Anthropic docs)                                       | Non duplicare in hook ciò che già sta in CLAUDE.md              |

**Nostra config attuale ha 11 hook SessionStart**. Quote sopra dice "keep these hooks fast". 11 è troppo. Consolidare.

### F. MEMORY.md / Auto Memory — limiti reali Maggio 2026

3 source convergenti:

| Source                     | Quote                                                                                                                                        |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Anthropic docs (NB-AGENTS) | "Impose a strict 200-line hard limit on MEMORY.md file. Overgrown memory files slow down reasoning; older entries must be actively archived" |
| Milvus Blog                | "4 Layers, 5 Limits" — sistema cap 200 righe / 25KB, grep-only no semantic search                                                            |
| MindStudio                 | "Only the first 200 lines or 25 KB of auto memory are loaded into each conversation"                                                         |
| Issue Anthropic #40614     | "Hierarchical memory features to prevent silent loss at 200-line limit" — feature request riconosciuta, **non risolta**                      |

**Sintesi verità 2026**: limit è **hard-coded**, non c'è override. Solo workaround: hierarchical structure (entry pointer → file dedicato), aggressive archiving.

### G. Multi-machine pattern (Pro+Mini) — verified NB-AGENTS

Quote ([NB-AGENTS source 7-9]):

- "Cross-machine SSH execution utilizes a resilient fallback pattern. If the Mini is unreachable via LAN (mDNS), scripts should automatically fall back to the Tailscale data-plane IP"
- "Always use absolute paths for remote CLI tools via `ssh -t`, as non-interactive SSH sessions do not source `~/.zshrc`"
- Memory `memory-sync-bidirectional.sh` patchato 2026-05-06: prova prima alias SSH `mini` (LAN/mDNS), poi `mini-remote` (Tailscale 100.93.236.6)

**Nostra config attuale** (SessionStart hook verificato verbatim):

```bash
HN=$(hostname); ...
if [ "$HN" = "Nuzantara" ]; then OTHER=mini-pro2.local; ...
ssh -o ConnectTimeout=2 -o BatchMode=yes "$OTHER" 'echo "Peer: $(whoami)@$(hostname)"'
```

**Bug**: usa solo mDNS `mini-pro2.local`, no fallback Tailscale. Quando mDNS rompe (oggi) → "UNREACHABLE" persistente. Fix è già documentato in memory `memory-sync-bidirectional.sh`.

### H. Topology multi-agent — Kim et al. 2025 + Voyager + Reflexion

Quote ([NB-AGENTS source 10-11, 45-49]):

| Topology                          | Error amplification vs single-agent baseline | Quando usarla                                         |
| --------------------------------- | -------------------------------------------- | ----------------------------------------------------- |
| Single-agent (SAS)                | 1×                                           | Sequential pipelines (39-70% migliore di multi-agent) |
| Centralized (orchestrator-led)    | 4.4×                                         | Parallelizable tasks (+80.9% vs single-agent)         |
| Hybrid                            | intermediate                                 | Caso ibrido                                           |
| Decentralized                     | high                                         | Evitare                                               |
| **Independent (no coordination)** | **17.2×**                                    | **MAI**                                               |

Translation per Nuzantara:

- WR2 pipeline (brief → storyboard → layout → critic chain) = **single-agent** (catena sequenziale)
- Deep research (4-LLM panel review) = **centralized** parallelizable, +80.9% gain
- Mai spawnare 3 sessioni Claude parallele senza orchestrator coordinator (cicatrix `git stash` Branch Hijack ne è esempio: 17.2× pattern)

Voyager + Reflexion patterns ([NB-AGENTS source 45-49]):

- **Voyager**: skill library che cresce (`~/.claude/skills/<domain>/SKILL.md`) — ogni successo orchestrator → skill nuova. Bali Zero ha già `bali-zero-brand`, `wr2-*`, `wr3-*` agent definitions seguendo questo pattern.
- **Reflexion**: post-mortem settimanale su PR chiuse + run completati → verbal lessons in `~/.claude/skills/<domain>/_lessons/` come few-shot examples. Bali Zero ha `wr2-reflexion-synth` weekly cron Sun 02:30 e `wr3-reflexion-synth` — già implementato.

---

## 2. Cosa stiamo facendo BENE oggi (riconoscimento)

| Aspetto                                              | Stato Nuzantara                                                                              |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| ENABLE_TOOL_SEARCH=auto attivo                       | ✅ Verificato in settings.json                                                               |
| Hierarchical CLAUDE.md (app-level)                   | ✅ Esistono `apps/<x>/CLAUDE.md`, presunto lazy-load                                         |
| Skill agent-based (wr2-_, wr3-_, regulatory-watcher) | ✅ 60+ agent definitions con `model: opus/sonnet/haiku` routing                              |
| Multi-LLM cascade (Claude+Gemini+DeepSeek+Ollama)    | ✅ Documentato CLAUDE.md global §"Model routing"                                             |
| Voyager skill library                                | ✅ `~/.claude/skills/bali-zero-brand/` con constitution + tokens + voice + 64 past carousels |
| Reflexion weekly cron                                | ✅ wr2-reflexion-synth (domenica 02:30) + wr3                                                |
| Devils-advocate gate per high-stakes                 | ✅ Agent definition esiste, usato in deep-researcher + client-case-quote-generator           |
| Pre-brief sweep contro HEAD                          | ✅ Memory `feedback_brief_stale_premise_pre_brief_sweep.md` 2026-05-08                       |
| Anti-hallucination tool-output                       | ✅ Memory `lessons_hallucinating_tool_output_is_diabolical.md` 2026-05-13                    |
| 4-LLM panel review pre-approval                      | ✅ Memory `feedback_always_review_spec_with_4_llm.md` 2026-05-13                             |
| Plist live env paths = main checkout never worktree  | ✅ Memory dopo P1 incident supervisor 2026-05-08                                             |
| Local sovereignty (CRM via Ollama, no cloud PII)     | ✅ Memory `feedback_email_language.md` + yield-optimizer.md                                  |

## 3. Cosa NON stiamo facendo bene (gap chiusi della ricerca)

| Gap                                                         | Fix concreto                                                                                                                     | Source convergente                                            |
| ----------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| **MEMORY.md silent truncation 60.6KB**                      | Compaction immediata + hierarchical pointer (entry 1 riga → file dedicato)                                                       | 4/4 LLM panel + 3 web source + NB-AGENTS                      |
| **lessons.md hook inietta solo last-2**                     | Sostituire con date-based (last 14d)                                                                                             | Gemini + DeepSeek esplicito                                   |
| **SessionStart 11 hook**                                    | Consolidare a 3-4 (machine check + memory load + symbiosis core + autonomous ops), gli altri spostare in PostCompact o eliminare | Anthropic docs "keep these hooks fast"                        |
| **mDNS-only SSH peer check**                                | Aggiungere fallback Tailscale `mini-remote`                                                                                      | Memory `memory-sync-bidirectional.sh` 2026-05-06              |
| **cicatrix-scars-archive.md 27KB auto-loaded**              | Verificare matcher glob in `additionalContext` di settings.json, escludere `*-archive.md`                                        | Header file dice "not auto-loaded" — VIOLATO                  |
| **bali-zero-brand/constitution.md 41KB**                    | Split: articles core in SKILL.md (~12KB), dettagli in `references/constitution-detail.md`                                        | Anthropic skill docs "target 1500-2000 words"                 |
| **Mini PATH non-interactive non funziona**                  | Sostituire `.zshrc` con `.zshenv` per PATH Claude/Gemini/Codex                                                                   | Memory `feedback_ssh_non_interactive_path_trap.md` 2026-05-04 |
| **alzheimer-diagnose 8gg silenziato**                       | Patch script → Telegram alert su soglia 25KB                                                                                     | DeepSeek esplicito                                            |
| **Pro/Mini Claude Code version drift** (2.1.144 vs 2.1.140) | Allineare entrambi a 2.1.144 (Pro current) o decidere master                                                                     | Claude Code release notes (52 changes between)                |

## 4. Configurazione target — Nuzantara post-fix (sintesi 1-page)

### `~/.claude/CLAUDE.md` (user-level, ≤ 12KB attuale) — **mantieni**

### `<repo-root>/CLAUDE.md` (project, 29.6KB → target 15KB)

- Sezioni core (machine ID, project overview, autonomous ops, MOS, golden rules, deploy) **stay**
- Sezione "Domain-Specific Knowledge" → migra a `apps/backend-rag/CLAUDE.md` (delega)
- Sezione "AI Dispatch System" → migra a `docs/AI_DISPATCH_REFERENCE.md` (già reference esiste)
- Sezione "CRITICAL OPERATIONAL RULES" → delega a `apps/<app>/CLAUDE.md` nested
- Sezione "Cron Air" → archive (Air decommissioned 2026-05-05)

### `<repo-root>/.claude/rules/cicatrix-scars.md` (25.8KB) — **stay** (struttura ok, contenuto valido)

### `<repo-root>/.claude/rules/cicatrix-scars-archive.md` (27.3KB) — **NON deve auto-load**

Verifica `settings.json` per matcher `additionalContext` o equivalente che lo trascina.

### `<repo-root>/SYMBIOSIS.md` 24.5KB — **stay** (caricato da hook esplicito, non glob)

### `<repo-root>/VADEMECUM.md` 21KB — **valuta delega a `docs/`**

Quote Anthropic: "For static context that does not require a script, use CLAUDE.md instead". VADEMECUM = static checklist, CLAUDE.md riga 1 lo referenzia. Potrebbe non auto-load se non chiamato esplicitamente.

### `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/MEMORY.md` — target **18-20KB**

- 17 Research Captures → split in `MEMORY_RESEARCH_CAPTURES.md` (referenced 1-liner pointer in MEMORY.md)
- Entry restanti compatte ≤150 char (regola CLAUDE.md §3 violata, da riapplicare)

### `~/.claude/projects/-Users-nuzantara/memory/lessons.md` — target **2 entry recenti 2026-05-13**

- Migra `feedback_always_review_spec_with_4_llm.md` come `### 2026-05-13 — 4-LLM panel review prima di approval`
- Migra `lessons_hallucinating_tool_output_is_diabolical.md` come `### 2026-05-13 — Hallucinating tool output is diabolical`
- Fix hook in `settings.json`: da `L=$(count-2)` a date-based filter ultimi 14gg

### `~/.claude/settings.json` SessionStart — consolida 11 → 4 hook

1. Machine check (con fallback Tailscale)
2. MCP cleanup + memory load (combine)
3. Lessons recent (date-based)
4. Symbiosis core + autonomous ops + active context (combine, era 3 separati)

### `.mcp.json` `alwaysLoad` — **rivedi**

8 server attivi. Anthropic docs raccomanda `alwaysLoad: true` SOLO per server con tool che servono ogni turno. Per Nuzantara probabilmente: nessuno (deferred default va benissimo). Verifica config attuale.

### Subagent fresh context — patch quando spawni verifier

Quando dispatcho devils-advocate / panel-LLM / smoke-test agent, prompt deve includere:

```
You are a fresh subagent. Do NOT inherit parent's MEMORY.md or CLAUDE.md context.
Trust ONLY: (1) this prompt, (2) explicit file paths you Read, (3) tool outputs in this session.
If you find yourself citing facts you "know" without a Read tool call → STOP and Read first.
```

---

## 5. Tabella decisioni: priorità + tempo + rischio

| #   | Decisione                                               | Priorità | Tempo  | Rischio se non fatto                         |
| --- | ------------------------------------------------------- | -------- | ------ | -------------------------------------------- |
| 1   | MEMORY.md → 18-20KB (fix immediato)                     | P0       | 25 min | Regressione continua, alert silenziati       |
| 2   | lessons.md migrate 2 entry 2026-05-13 + hook date-based | P0       | 20 min | SessionStart inietta lessons vecchie         |
| 3   | alzheimer-diagnose → Telegram alert > 25KB              | P0       | 15 min | Cieco a future regressioni                   |
| 4   | SSH peer check fallback Tailscale                       | P1       | 5 min  | Falso allarme UNREACHABLE ogni session       |
| 5   | Mini PATH `.zshenv`                                     | P1       | 5 min  | Automation cross-host fragili                |
| 6   | Pro/Mini Claude version align                           | P1       | 10 min | Comportamento harness drift                  |
| 7   | cicatrix-scars-archive **non** auto-load                | P1       | 10 min | -27KB context fisso pre-turn (-13%)          |
| 8   | bali-zero-brand/constitution.md split                   | P2       | 30 min | Skill load 41KB ogni run wr2                 |
| 9   | SessionStart hook consolidate 11→4                      | P2       | 30 min | Hook latency, eccesso system-reminder        |
| 10  | CLAUDE.md project → 15KB delegando ad app-CLAUDE.md     | P2       | 45 min | -14KB context fisso                          |
| 11  | Subagent fresh-context prompt patch                     | P2       | 15 min | Bias inheritance, math-auditor pilot pattern |
| 12  | `.mcp.json` audit alwaysLoad per server                 | P3       | 10 min | Possibile overhead schema                    |

**Totale P0**: 60 min — recover ~60% effective memory + chiudere monitoring loop
**Totale P0+P1**: 1h 50 min — recover anche fallback infrastructure
**Totale P0+P1+P2**: 4h — config production-grade May 2026 SOTA

---

## 6. Caveat metodologici

| Caveat                                                                                                                                                                                                                                                         | Mitigazione                                                                                                                             |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| WebSearch ha citato issue Anthropic #40614 con conferma "200-line limit hard-coded" ma anche con riferimento a `claude-mem/CHANGELOG.md` che NON è Anthropic ufficiale. La distinzione "hard-coded vs configurable" va riverificata leggendo source Anthropic. | Leggere `code.claude.com/docs/en/memory` direttamente prima di committare fix #1                                                        |
| NB-AGENTS cita Kim et al. 2025 arxiv 2512.08296 — paper esiste, ma "17.2× error amplification" specifico non l'ho verificato leggendo paper originale                                                                                                          | Mitigazione: pattern già adottato da Nuzantara (centralized > independent), conferma rule corretta indipendentemente da numerica esatta |
| Tool Search "v2.1.7" citato come release introduce-feature; nostra Pro è 2.1.144 quindi feature presente; Mini 2.1.140 → **verifica empirica** che ENABLE_TOOL_SEARCH funzioni anche lì                                                                        | Allineare Mini a 2.1.144 (item P1 #6)                                                                                                   |
| 8 source web vs 49 source NotebookLM — confidenza alta perché tutte e 3 le sezioni più importanti (MEMORY.md limit, Tool Search, Skill 3-layer) sono confermate da ≥3 source convergenti                                                                       | Continua approccio 4/4 LLM panel per decisioni high-stakes                                                                              |

---

## 7. Cosa NON ho potuto verificare (open questions)

1. **Exa MCP** è in `.mcp.json` ma richiede OAuth manuale (`/mcp` da user). Avrei voluto eseguire deep-research Exa parallelo a NB-AGENTS+WebSearch. **Azione**: chiedere a Antonello di completare auth con `/mcp` → claude.ai Exa, poi ri-eseguire questa query con 4 source.
2. **Claude Code 2.1.144 vs 2.1.140 changelog differenze precise**. WebSearch ha confermato "52 changes 2.1.69→2.1.101 e poi 2.1.140-144 release" ma non differenze granulari su context-packing.
3. **Empirical test che ENABLE_TOOL_SEARCH=auto:5 effettivamente defer 8 MCP server di Nuzantara**. Misurabile: contare token system prompt prima/dopo settings change con stesso payload.

---

## 8. Sintesi 1 frase (per Telegram update Antonello)

Il sistema Claude Code di Nuzantara è 80% allineato a SOTA Maggio 2026 (skill library, multi-LLM cascade, devils-advocate, Reflexion cron, hierarchical CLAUDE.md), ma soffre 4 regressioni tecniche cumulative (MEMORY.md truncation, hook lessons stale, archive auto-load violato, SSH mDNS-only) che insieme fanno percepire "Claude non più di Nuzantara" — fix P0 in 60 minuti.

---

**Sources** (this research):

Web (verified URLs):

- [How Claude remembers your project (Anthropic docs)](https://code.claude.com/docs/en/memory)
- [Claude Code MCP Servers configuration (Anthropic docs)](https://code.claude.com/docs/en/mcp)
- [Hooks reference (Anthropic docs)](https://code.claude.com/docs/en/hooks)
- [Extend Claude with skills (Anthropic docs)](https://code.claude.com/docs/en/skills)
- [Create custom subagents (Anthropic docs)](https://code.claude.com/docs/en/sub-agents)
- [Claude Code Memory System Explained — Milvus Blog](https://milvus.io/blog/claude-code-memory-memsearch.md)
- [Claude Code memory: how to survive 200k context window — DEV.to](https://dev.to/subprime2010/claude-code-memory-how-to-survive-a-200k-context-window-filling-up-idk)
- [Stop Bloating Your CLAUDE.md: Progressive Disclosure — alexop.dev](https://alexop.dev/posts/stop-bloating-your-claude-md-progressive-disclosure-ai-coding-tools/)
- [Claude Code Memory Levels Explained: 6 Layers — MindStudio](https://www.mindstudio.ai/blog/claude-code-memory-levels-explained-6-layers-claude-md-cross-tool-shared-memory)
- [Claude Code Configuration Guide — ClaudeLog](https://claudelog.com/configuration/)
- [How to Use Session Start Hooks — MindStudio](https://www.mindstudio.ai/blog/session-start-hooks-claude-code-force-context)
- [Claude Code Split-and-Merge Sub-Agent Parallelism — MindStudio](https://www.mindstudio.ai/blog/what-is-claude-code-split-and-merge-pattern-sub-agents-parallel)
- [Claude Code as Autonomous Agent Advanced Workflows 2026 — SitePoint](https://www.sitepoint.com/claude-code-as-an-autonomous-agent-advanced-workflows-2026/)

NotebookLM NB-AGENTS query (49 citations, 22 source IDs):

- Sources verified internally — full citation list at `/tmp/nlm-citations-nb-agents-2026-05-19.txt` (this turn)
- Key paper anchors: Wang et al. 2023 (Voyager arXiv 2305.16291), Shinn et al. 2023 (Reflexion arXiv 2303.11366), Park et al. 2023 (Generative Agents UIST), Kim et al. 2025 (Multi-agent topology arXiv 2512.08296), arxiv 2512.20845 (MAR persona debate)

Empirical verification this session:

- `~/.claude/settings.json` SessionStart hook chain (verbatim read)
- `~/Desktop/nuzantara/research/operations/2026-05-19-claude-code-regression-fix.md` (companion spec)
- `head -c 25600 MEMORY.md \| wc -l = 45` (cutoff verified)

**Out of scope this turn**:

- Exa MCP query (require user OAuth)
- Direct paper read Kim et al. 2025 (would need WebFetch on arxiv.org full PDF)
