---
date: 2026-05-22
domain: operations
topic: cursor-3-5-nuzantara-integration
sources: 7
panel: gemini-3.1-pro + deepseek-v4-pro + gpt-5.5-codex + 5x webfetch
---

# Cursor 3.5.17 — analisi feature + integrazione Nuzantara

**Versione**: Cursor 3.5.17 (scaricato 22-mag-2026, `~/Downloads/Cursor-darwin-arm64.dmg` 246MB, sha256 `ecf391fbda6f793751f56631d3f39d80e845f324e4899c21ce0d232847d6adfb`, installato in `/Applications/Cursor.app`).

**Metodo**: 4-LLM panel + 5 WebFetch sources ufficiali (cursor.com/changelog, /changelog/1-0, /changelog/3-0, /docs/context/mcp, /docs/context/rules, /pricing).

---

## 1. Timeline release fino a 22-mag-2026 (verificato cursor.com/changelog)

| Versione                    | Data         | Headline                                                                                                                                                                                                                         |
| --------------------------- | ------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **3.0**                     | 2-apr-2026   | Agent-first interface. Agents Window (`Cmd+Shift+P → Agents Window`). Parallel agents locali/worktree/cloud/SSH. Agent Tabs (grid view). PR Review nativo. `/worktree`, `/best-of-n` slash cmd. Design Mode (annota UI browser). |
| **1.0** (rebrand parallelo) | mag-2026     | Bugbot GA, Background Agent GA, one-click MCP install.                                                                                                                                                                           |
| **3.3**                     | 7-mag-2026   | Async sub-agents paralleli. "Build in Parallel". Redesigned PR workflow (Reviews/Commits/Changes tabs).                                                                                                                          |
| Bugbot effort levels        | 11-mag-2026  | Default/High/Custom. Usage-based billing per Teams+Individual.                                                                                                                                                                   |
| **3.4**                     | 13-mag-2026  | Full-screen Tabs (`Cmd+Shift+M`), Compact Chat (Compact/Balanced/Detailed). Dev Environments for Cloud Agents (Dockerfile, 70% faster cached builds, secrets+egress).                                                            |
| **3.5**                     | 20-mag-2026  | Automations dentro Agents Window. Multi-repo automations. No-repo automations (monitor signals). 5 marketplace templates.                                                                                                        |
| 3.5.17 patch                | ~22-mag-2026 | Bugfix point release.                                                                                                                                                                                                            |

---

## 2. Feature set Cursor 3.5 — convergenza 4 fonti

### Editing core

| Feature                    | Convergenza | Note                                                                                                                   |
| -------------------------- | ----------- | ---------------------------------------------------------------------------------------------------------------------- |
| Composer / Agent (`Cmd+I`) | 4/4         | Multi-file, plan→act→verify loop, rollback su errore lint/compile, YOLO mode opzionale                                 |
| Tab completion             | 4/4         | Latenza p95 ~85ms (DeepSeek), proprietary model                                                                        |
| Cmd+K inline edit          | 4/4         | Semantic block, preserva indentazione                                                                                  |
| Cmd+L chat                 | 4/4         | Model picker + Auto mode                                                                                               |
| @-mentions                 | 4/4         | `@Files`, `@Folders`, `@Code`, `@Docs`, `@Web`, `@Git`, `@Recent Changes`, `@Lint Errors`, `@Definitions`, `@Codebase` |

### Agent platform (Cursor 3.x signature)

| Feature                   | Status                       | Note                                                                                     |
| ------------------------- | ---------------------------- | ---------------------------------------------------------------------------------------- |
| Agents Window             | GA 3.0                       | Run many agents in parallel: local / worktree / cloud / remote SSH                       |
| Agent Tabs                | GA 3.0                       | Side-by-side / grid view                                                                 |
| Background Agents (cloud) | GA 1.0/3.x                   | Cloud-based, Dockerfile-configured env, secrets+egress controls (3.4)                    |
| Build in Parallel         | GA 3.3                       | Identifica step indipendenti del piano, lancia async sub-agents                          |
| Automations               | GA 3.5                       | Multi-repo, no-repo, marketplace templates (Slack digest, FAQ, finance, customer health) |
| Bugbot                    | GA 1.0, effort levels mag-11 | PR review automatico GitHub. Default 0.7 bug/review, High 0.95, Custom                   |

### Context system

| Feature                            | Convergenza              | Note                                                                                                                                                                         |
| ---------------------------------- | ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cursor Rules `.cursor/rules/*.mdc` | 4/4                      | Sostituisce `.cursorrules` (ancora letto). Frontmatter `description` + `globs` + `alwaysApply`. Precedence: Team → Project → User. **NON** influenza Tab/Inline, solo Agent. |
| AGENTS.md                          | confermato docs          | Alternativa markdown a Project Rules, nested directory                                                                                                                       |
| User Rules globali                 | confermato docs          | Settings → Rules                                                                                                                                                             |
| Memory                             | confermato docs+DeepSeek | Sostituisce Notepads (deprecati). Long-term context.                                                                                                                         |
| MCP `.cursor/mcp.json`             | 4/4                      | Project + global `~/.cursor/mcp.json`. Transport: stdio / SSE / Streamable HTTP. One-click install dal Marketplace.                                                          |
| `.cursorignore`                    | 3/4                      | Esclude path da indexing. **NON è una sandbox** (Codex caveat): MCP/terminale possono ancora accedere.                                                                       |

### Modelli (3.5 al 22-mag-2026)

| Modello              | Disponibilità               | Note                                              |
| -------------------- | --------------------------- | ------------------------------------------------- |
| Claude Sonnet 4.6    | Pro/Pro+/Ultra              | Default bilanciato                                |
| Claude Opus 4.7      | Pro+ con limiti, Ultra full | Max mode primary                                  |
| GPT-5.5              | Tutti i piani paid          | Refactor, reasoning                               |
| Gemini 3.1 Pro       | Tutti i piani               | 1M+ ctx                                           |
| DeepSeek V4 (Pro)    | Tutti i piani               | Costo ridotto, logic                              |
| Custom OpenAI-compat | Business+/Ultra             | Endpoint arbitrari (vLLM, Ollama localhost:11434) |

### Max mode (verificato docs+DeepSeek)

- Contesto esteso fino a **2M token** (Opus 4.7 + GPT-5.5)
- Chain-of-thought multi-pass + tool use parallelo
- **2x crediti** vs standard, illimitato su Ultra
- Trigger manuale o auto > 200k ctx

### Privacy + compliance

- Privacy mode: no training, no retention (SOC 2 Type II Q1-2026)
- Data retention default: 30 giorni
- Audit logs (Business+), SSO/SAML/OIDC (Business+), SCIM (Enterprise)

---

## 3. Pricing al 22-mag-2026 (cursor.com/pricing confirmed)

| Piano          | Prezzo      | Credit pool                                                             | Uso target                             |
| -------------- | ----------- | ----------------------------------------------------------------------- | -------------------------------------- |
| **Hobby**      | $0          | Limitato (~2K completions, 50 agent steps/mese)                         | Demo                                   |
| **Pro**        | $20/mo      | $20 credit pool. Frontier models, MCP, cloud agents, Bugbot usage-based | Solo dev intensivo                     |
| **Pro+**       | $60/mo      | 3x usage Pro                                                            | Daily heavy user (raccomandato Cursor) |
| **Ultra**      | $200/mo     | 20x usage + priority new features + Max mode quasi-illimitato           | Power user, multi-agent fleet          |
| **Teams**      | $40/user/mo | Pro features + shared chats/rules, SSO, audit, plugin marketplace       | Team collab                            |
| **Enterprise** | custom      | Pooled usage, SCIM, audit, AI code tracking API                         | Org >50                                |

**Cambio modello giugno 2025**: abolite request cap, ora **usage-based billing** in $ del credit pool. Auto mode unlimited. Max mode brucia più credito. Premium model selection consuma pool.

---

## 4. Cursor vs Claude Code CLI — analisi ortogonale

| Dimensione          | Cursor 3.5                         | Claude Code CLI                          | Vincitore Nuzantara                  |
| ------------------- | ---------------------------------- | ---------------------------------------- | ------------------------------------ |
| Interfaccia         | GUI fork VSCode                    | CLI headless                             | Cursor (editing umano)               |
| Tab completion      | <85ms ghost text                   | n/a                                      | Cursor                               |
| Multi-file refactor | Diff visuale step approval         | Autonomo apply                           | Cursor per QA, CC per bulk           |
| Background agents   | Cloud-based, Dockerfile env        | Locale subprocess, full subagent fan-out | CC per workflow autonomous L2        |
| Cron / event-driven | Automations (3.5, no-repo)         | Nativo (LaunchAgent, MCP)                | CC per produzione, Cursor per ad-hoc |
| MCP support         | ✅ stdio/SSE/HTTP + UI marketplace | ✅ full + custom skills                  | Pari                                 |
| Sessione lunga      | Saturazione contesto UI            | Compaction nativa                        | CC                                   |
| Costo               | $20-200/mo                         | OAuth MAX subscription già pagata        | CC = 0 marginale                     |

**Coesistenza**: ortogonali, non sostitutivi. Cursor = bisturi GUI, CC = sistema operativo agentico.

---

## 5. Integrazione Nuzantara — setup raccomandato

### 5.1 `.cursorignore` (mandatory pre-index)

```gitignore
# Heavy dirs
node_modules/
**/node_modules/
.venv/
**/.venv/
**/__pycache__/
.next/
**/.next/
dist/
**/dist/
build/
**/build/

# Vendor / build artifacts
.vercel/
.turbo/
target/

# Logs / cache / dumps
*.log
*.dump
**/logs/
.cache/
qdrant_storage/
redis_dump/

# Test fixtures massivi
apps/backend-rag/tests/fixtures/large/
apps/backend-rag/migrations/data/

# Sensitive (defense-in-depth — NON è sandbox)
.env
.env.*
**/.env
**/.env.*
*.pem
*.key
secrets/
shared/escalations.json

# OSINT (sovranità Law 2)
apps/mata-garuda/data/
research/intelligence/
~/.agent/

# Memory / sessions Claude Code
.claude/projects/
**/.claude-acct2/

# Generated
apps/mouth/.next/
apps/web/.next/
apps/kbli-navigator/.next/
```

**⚠️ Cursor caveat (Codex finding)**: `.cursorignore` esclude da indexing+UI, ma agent tool calls (`run_terminal`, MCP) possono ancora accedere ai path. Non è sandbox.

### 5.2 `.cursor/rules/*.mdc` (strategia: pointer NON duplicate)

```
.cursor/rules/
├── 00-monorepo.mdc        # alwaysApply: true — Symbiosis core + comandi base
├── 10-backend-rag.mdc     # globs: apps/backend-rag/**/*.py
├── 11-mouth.mdc           # globs: apps/mouth/**/*.{ts,tsx}
├── 12-mata-garuda.mdc     # globs: apps/mata-garuda/** — OSINT rules
├── 20-migrations.mdc      # globs: **/migrations_v2/*.sql — Squawk gate
└── 30-channels.mdc        # globs: apps/backend-rag/backend/channels/**
```

**Esempio `00-monorepo.mdc`**:

```markdown
---
description: Nuzantara monorepo global rules
alwaysApply: true
---

# Nuzantara contesto

Monorepo 24 apps + 5 packages. Stack: FastAPI/Python 3.11, Next.js 16, PostgreSQL+Qdrant+Redis, Fly.io+Vercel.

**Riferimenti autoritativi** (leggi sempre prima di operazioni architetturali):

- `@CLAUDE.md` — convenzioni codebase
- `@SYMBIOSIS.md` — 8 leggi inviolabili (CLI-only, OSINT blindato, event-driven, graceful degradation, Zero last word, sovranità locale, numeri prima)
- `@VADEMECUM.md` — checklist per element type
- `@.claude/rules/cicatrix-scars.md` — bug storici + antibody

**Hard rules**:

- Mai mock DB nei test integration (regression Q3 2025)
- Mai `httpx.AsyncClient()` in metodi/loop — sempre `_get_client` persistent
- Email always `from=zantara@balizero.com` via Brevo
- Mai paid Anthropic API key (OAuth MAX only)
- Flat Qdrant payloads (`kode_kbli`, `judul`, `content`)

**Quando uso Cursor vs Claude Code CLI**:

- Cursor = editing visuale, refactor file-by-file con review
- Claude Code CLI = autonomous ops L2, deploy, cron, subagent fan-out
- Mai 2 agenti su stesso file in parallelo (race condition WIP)
```

**Esempio `10-backend-rag.mdc`**:

```markdown
---
description: FastAPI backend RAG rules
globs: apps/backend-rag/**/*.py
---

- Routers in `backend/app/routers/` (NON `backend/routers/`)
- Services in `backend/services/` (domain) + `backend/app/services/` (app-level)
- `dependencies.py` = SPOF, test before deploy: `python -c "from backend.app.dependencies import get_current_user"`
- Prompt SSOT: `backend/prompts/zantara_core.py` — never edit downstream consumers
- All prices from `PricingTool` — never hardcode
- Use `client.generate_structured()` for LLM JSON (Pydantic v2 retry — PR #311)
```

### 5.3 `.cursor/mcp.json` (porta MCP esistenti)

```json
{
  "mcpServers": {
    "nuzantara-mcp": {
      "command": "/Users/nuzantara/Desktop/nuzantara/apps/nuzantara-mcp/.venv/bin/python",
      "args": [
        "/Users/nuzantara/Desktop/nuzantara/apps/nuzantara-mcp/nuzantara_mcp/server.py"
      ],
      "env": {
        "NUZANTARA_API_KEY": "${NUZANTARA_API_KEY}",
        "NUZANTARA_API_URL": "https://nuzantara-rag.fly.dev"
      }
    },
    "notebooklm-mcp": {
      "command": "nlm",
      "args": ["mcp"]
    },
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp"]
    }
  }
}
```

**Strategia di portazione** (priorità):

- ✅ `nuzantara-mcp` (115 tools CRM/intel/content) — il valore unico
- ✅ `notebooklm-mcp` — ground truth 60 NB
- ✅ `context7` — docs librerie (cf. plugin già attivo in CC)
- ⚠️ `github` — preferisci gh CLI nei chat, evita doppione con CC
- ❌ `playwright` — tieni solo in CC (orchestration headless)
- ❌ `nuzantara-mcp-advanced` — solo Fly ops, lascia in CC
- ❌ OSINT/wa-mirror MCP — sovranità Law 2 (CC only)

### 5.4 Settings raccomandati Cursor

```jsonc
// ~/Library/Application Support/Cursor/User/settings.json
{
  // Modello default — Sonnet 4.6 per quotidiano
  "cursor.cpp.disabledLanguages": [],
  "cursor.composer.autoApplyOutsideContext": false, // safety
  "cursor.composer.shouldAllowAutoApply": false, // diff approval esplicita
  "cursor.cpp.enablePartialAccepts": true,

  // Indexing
  "cursor.general.disableHttpRequests": false,
  "cursor.preview.composerApplyVibe": true,

  // Performance
  "files.exclude": {
    "**/node_modules": true,
    "**/.venv": true,
    "**/__pycache__": true,
    "**/.next": true,
  },
  "search.exclude": {
    "**/node_modules": true,
    "**/.venv": true,
    "**/qdrant_storage": true,
  },
}
```

### 5.5 Bugbot — `.cursor/BUGBOT.md`

```markdown
# Bugbot review policy — Nuzantara

## High-risk paths (effort=high mandatory)

- `apps/backend-rag/backend/db/migrations_v2/**` → cf. Squawk lint, no DROP COLUMN without DEFAULT
- `apps/backend-rag/backend/prompts/zantara_core.py` → SSOT, breaking change → tutti i consumer
- `apps/backend-rag/fly.toml` → deploy-blocking
- `apps/backend-rag/backend/app/dependencies.py` → SPOF
- `apps/backend-rag/backend/app/setup/router_registration.py` → manifest parity

## Cross-cutting checks

- Async HTTP: nessun `httpx.AsyncClient()` in metodo/loop
- Qdrant payload: solo flat keys
- Cache invalidation: `invalidate_cache()` dopo ogni mutazione CRM
- Public endpoints: `/health` mai pubblico senza explicit allowlist

## Forbidden

- `ANTHROPIC_API_KEY` in qualsiasi config (Law: OAuth MAX only)
- Hardcoded password Postgres (cicatrix P0 2026-05-21)
- `git push --force` su main
```

---

## 6. Workflow ibrido Cursor ↔ Claude Code CLI

**Regola d'oro**: 1 agente per area di lavoro. Lock implicito via branch separati.

| Task                                                | Tool                          | Note                                                |
| --------------------------------------------------- | ----------------------------- | --------------------------------------------------- |
| Editing quotidiano `apps/mouth/` Next.js            | Cursor + Sonnet 4.6           | Subhi-friendly                                      |
| Refactor visivo cross-file `apps/backend-rag/`      | Cursor + Opus 4.7 (Max mode)  | Diff approval esplicita                             |
| Tab completion + cmd+K                              | Cursor                        | Latenza <85ms, irreplaceable                        |
| Bugbot review PR                                    | Cursor (GitHub integration)   | Pre-deploy gate before merge                        |
| Background refactor multi-app overnight             | Cursor Background Agent       | Su branch dedicato                                  |
| Deploy Fly.io (autonomous L2)                       | Claude Code CLI               | Cron `fly-deploy.yml`, AUTONOMOUS_OPS L2            |
| Subagent fan-out (10+ agents parallel)              | Claude Code CLI               | Wave orchestration                                  |
| Cron daily (regulatory watcher, indexing, sentinel) | Claude Code CLI + LaunchAgent | 30+ active jobs                                     |
| 4-LLM panel pre-deploy critical                     | Claude Code CLI               | gemini+codex+deepseek+NB-1                          |
| OSINT mata-garuda                                   | Claude Code CLI               | Sovranità Law 2                                     |
| War room WR2/WR3 production carouseli/video         | Claude Code CLI               | wr2-design-architect orchestrator + 7-step pipeline |

**Anti-conflict pattern**:

- Branch convention: Cursor lavora su `feat/cursor-*`, CC su `feat/cc-*`
- Mai 2 sessioni Auto Mode contemporanee sullo stesso file
- WIP commit ogni 10min (cicatrix 2026-04-29 untracked-lost)

---

## 7. Subhi (team non-dev) — Cursor primary IDE

Cursor è **drop-in fit** per Subhi (Growth Systems Owner, probation 2026-04-30 → 2026-07-29):

- GUI familiare (fork VSCode)
- Composer in linguaggio naturale (BI default)
- Perimetro: `apps/mouth/(blog|marketing|kbli|visa|property|tax-calendar)/**` — tutto editabile via Cursor
- @Codebase rispetta `.cursorignore` (no backend RAG, no Genoma, no secrets)
- Bugbot su PR Subhi = primo gate prima review umana Antonello

**Subhi Cursor setup** (separato da Antonello):

- Piano Pro $20/mo (no Background Agents heavy)
- `.cursor/rules/11-mouth.mdc` con tone Bali Zero brand
- Disabilita Auto-apply (sempre diff approval)
- Privacy mode ON (UU PDP scope client data eventuale)

---

## 8. Pitfall noti (convergenza 3/4 LLM)

| Pitfall                                               | Mitigazione                                                                        |
| ----------------------------------------------------- | ---------------------------------------------------------------------------------- |
| Context window saturation dopo 10+ iterazioni in chat | New Chat frequente; Composer per stato persistente                                 |
| Hallucination su file mai aperti                      | `@Definitions` / `@File` esplicito; mai fidarsi solo di `@Codebase`                |
| Infinite agent loop                                   | `maxSteps: 25-30` settings; verify ogni 5 step                                     |
| Cost spike Max mode + Background paralleli            | Dashboard usage check settimanale; budget alert                                    |
| Ollama localhost endpoint format mismatch             | Test prima di committare Custom endpoint config                                    |
| `.cursorignore` ≠ sandbox                             | Defense-in-depth (`.gitignore` + `.cursorignore` + `.env` chmod 600 + Bugbot rule) |
| 2 agenti su stesso file race                          | Branch separation rigida + WIP commit 10min                                        |
| Cursor Rules ignorate da Tab/Inline                   | Capire: rules influenzano SOLO Agent (Chat). Tab/Inline = base model               |

---

## 9. Verdetto operativo per Antonello

### Setup raccomandato

1. **Start**: Cursor **Pro $20/mo** (1 mese pilot).
2. Misura settimanalmente:
   - Credit pool consumption ($20 mese, frazione usata)
   - Background Agent runs count
   - Bugbot PR review volume
3. **Upgrade Pro+ $60/mo** se: credit pool esaurito in <3 settimane O Background Agents >5/settimana.
4. **Upgrade Ultra $200/mo** SOLO se: Max mode quotidiano + multi-agent automation continuo + refactor massivi >2x/settimana.
5. **Subhi**: Cursor Pro $20/mo separato (sub-account o Teams $40/seat se vuoi shared rules).

### Stack target Nuzantara

- **Cursor** (Antonello daily) = IDE primario editing + visual review + Bugbot PR
- **Claude Code CLI** (sempre) = autonomous L2, cron, deploy, multi-LLM panel, OSINT, wave orchestration
- **Cursor Background Agents** = refactor multi-app overnight su branch dedicato
- **Subhi Cursor** = Growth Systems editing `apps/mouth/`

### Cosa NON fare

- ❌ Non duplicare CLAUDE.md/SYMBIOSIS.md/VADEMECUM.md in `.cursor/rules/`. Usa `@Docs` reference.
- ❌ Non portare TUTTI gli MCP in Cursor. Solo nuzantara-mcp + notebooklm + context7. Resto resta in CC.
- ❌ Non lanciare Cursor Auto Mode + Claude Code subagent fan-out sullo stesso file simultaneamente.
- ❌ Non saltare `.cursorignore` (indexing su 24 apps = lento + costoso + hallucination amplified).
- ❌ Non upgradare Ultra "preventivamente" — Pro è sufficiente per Antonello workflow attuale (CC fa il pesante).

---

## 10. Roadmap pubblica (giugno-luglio 2026 secondo DeepSeek/Codex)

- **3.6 (luglio)**: Codebase Embedding locale persistente, MCP tool discovery via registry, terminal command gen da chat
- **Beta opt-in**:
  - Cursor Agents API (REST, Ultra-only)
  - Memory Sync cross-instance (team)
  - Voice-to-Agent (Composer)

---

## Sources

- [Cursor changelog (cursor.com)](https://cursor.com/changelog)
- [Cursor 3.0 release notes](https://cursor.com/changelog/3-0)
- [Cursor 1.0: Bugbot + Background Agents GA + one-click MCP](https://cursor.com/changelog/1-0)
- [Cursor MCP docs](https://docs.cursor.com/context/mcp)
- [Cursor Rules docs](https://docs.cursor.com/context/rules)
- [Cursor Pricing](https://cursor.com/pricing)
- [Cursor 3 announcement blog](https://cursor.com/blog/cursor-3)
- [Cursor 3.2 IDE as agent runtime — Futurum](https://futurumgroup.com/insights/cursor-3-2-reframes-the-ide-as-an-agent-execution-runtime/)
- [Bugbot effort levels announcement — startdebugging.net](https://startdebugging.net/2026/05/cursor-bugbot-effort-levels-pr-review/)
- [Cursor pricing 2026 analysis — aiproductivity.ai](https://aiproductivity.ai/blog/cursor-pricing/)

LLM panel outputs (local artifacts):

- `/Users/nuzantara/.gemini/antigravity-cli/brain/b5d26688-4b6c-4515-b5f3-baa3dfeddfdb/cursor_3_5_technical_report.md` (Gemini 3.1 Pro)
- `/tmp/cursor-deepseek.md` (DeepSeek V4 Pro, reasoning_effort=high, 19KB)
- `/tmp/cursor-codex.md` (GPT-5.5 Codex, xhigh, 7KB)
