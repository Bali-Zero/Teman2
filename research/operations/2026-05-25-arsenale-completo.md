---
date: 2026-05-25
domain: operations
client_case: null
sources:
  - /tmp/arsenale-audit-2026-05-24/00-EXECUTIVE-SUMMARY.md
  - /tmp/arsenale-audit-2026-05-24/01-llm-arsenal.md
  - /tmp/arsenale-audit-2026-05-24/02-mcp-servers.md
  - /tmp/arsenale-audit-2026-05-24/03-notebooklm-arsenal.md
  - /tmp/arsenale-audit-2026-05-24/04-subagent-fleet.md
  - empirical audit 4-lane parallel (2026-05-24)
  - commit 751f6c4f5 (deepseek migration)
  - ~/logs/nb-migration-mapping.json (UUID switch antonellosiano@→zero@)
---

# Arsenale Bali Zero / Nuzantara — Snapshot Completo 2026-05-25

Snapshot post-audit 4-lane (LLM external + Ollama + MCP + NotebookLM + Subagent fleet) eseguito 2026-05-24 sera con apply ed empirical fixes. Tutti i numeri sono empiricamente verificati.

---

## 1. Cloud LLMs

### 1.1 Claude OAuth MAX (Anthropic) — 2 slot claim

| Slot | Account                                              | Status 2026-05-25                              | Invocation                                     |
| ---- | ---------------------------------------------------- | ---------------------------------------------- | ---------------------------------------------- |
| 1    | `kaiser198719871987@gmail.com` (era antonellosiano@) | ✓ healthy                                      | `claude` (default config dir `~/.claude/`)     |
| 2    | TBD (era antonellosiano@?)                           | ⚠ `email: null, orgId: null` — re-OAuth needed | `CLAUDE_CONFIG_DIR=$HOME/.claude-acct2 claude` |

**Wrapper alias `claude-acct2`**: NOT installed di default. Per attivare aggiungere a `~/.zshrc`:

```bash
alias claude-acct2='CLAUDE_CONFIG_DIR=$HOME/.claude-acct2 claude'
```

**Hard rule**: mai SDK Python `anthropic.Anthropic(...)`, mai `ANTHROPIC_API_KEY`. Solo CLI con `CLAUDE_CODE_OAUTH_TOKEN`. Reference: `apps/backend-rag/backend/llm/claude_oauth_client.py`.

**Health-check**: `bash -lc 'unset ANTHROPIC_API_KEY; claude auth status'`.

### 1.2 Antigravity (agy) CLI — Gemini 3.1 Pro (Google)

| Field         | Value                                                                 |
| ------------- | --------------------------------------------------------------------- |
| Binary        | `/Users/nuzantara/.local/bin/agy`                                     |
| Version       | **v1.0.2** (era v1.0.0 in doc)                                        |
| Subscription  | Google AI Ultra (rinnovata 2026-05-21, 10k Flow cr/mese + 2500 AI cr) |
| Model default | `gemini-3.1-pro-preview`                                              |
| Context       | 1M tokens                                                             |

**Invocation**:

```bash
agy -p "prompt qui"
cat prompt.txt | agy -p --print-timeout 5m
```

**Legacy `gemini` CLI** v0.42.0 ancora on disk at `/opt/homebrew/bin/gemini`. **DEPRECATED 2026-05-21** (quota exhaust nei tri-LLM panel). Non invocare.

### 1.3 Codex CLI — GPT-5.5 (OpenAI)

| Field        | Value                                                               |
| ------------ | ------------------------------------------------------------------- |
| Binary       | `/opt/homebrew/bin/codex`                                           |
| Version      | **v0.133.0** (era v0.128 in doc cicatrix)                           |
| Subscription | ChatGPT Pro $200/mo (illimitato)                                    |
| Models       | gpt-5.5 + gpt-5.1-codex-mini (low-cost) + gpt-image-2 (`$imagegen`) |

**Invocation**:

```bash
codex exec --sandbox workspace-write --skip-git-repo-check "prompt"
codex exec --sandbox read-only --skip-git-repo-check "read-only prompt"
```

**OAuth state**: token può andare in `401 token_revoked` silenziosamente. Re-login da terminale interactive:

```bash
codex login
```

**TRAP**: cron job che cascadano oltre Tier 1+2 (Claude+agy) verso Codex Tier 3 fail silenti se token revocato.

### 1.4 DeepSeek V4 Pro API (Chinese stack)

| Field        | Value                                                          |
| ------------ | -------------------------------------------------------------- |
| Endpoint     | `https://api.deepseek.com/chat/completions` (OpenAI-style)     |
| Key location | `~/.openclaw/workspace/.env.master` (NOT in default shell env) |
| Cost         | ~$0.01/query                                                   |

**Active models 2026-05-25**:
| Model | Use case | Params | Cost (per 1M tokens) |
|---|---|---|---|
| `deepseek-v4-pro` | Synthesis-grade reasoning, complex chains | 1.6T total, 49B activated, 1M ctx | input $0.435 / output $0.87 |
| `deepseek-v4-flash` | High-throughput, structured JSON | flash architecture | input $0.14 / output $0.28 |

**`reasoning_effort` modes** (v4-pro only): `low` / `high` / `max`.

**SILENT-ALIAS TRAP** (discovered 2026-05-24):

- `deepseek-reasoner` legacy alias → returns HTTP 200 BUT silently routes to `deepseek-v4-flash`
- `deepseek-chat` legacy alias → same silent downgrade
- Code expecting reasoning grade silently gets flash quality

**Migration shipped commit `751f6c4f5`** (3 production callsites):

- `scripts/ai-dispatch.sh:616`
- `scripts/nlm_shadow_extractor.py:147`
- `scripts/codex_tri_llm_review.py:443`

**Intentionally NOT migrated**:

- `apps/backend-rag/.../routers/article_composer.py` usa `deepseek-chat` deliberately per ~100x cost reduction (flash IS the right choice)
- `backend/llm/deepseek_client.py` già gestisce aliases correttamente nel pricing
- `scripts/deepseek_vs_gemini_blite.py` benchmark intenzionale

### 1.5 NotebookLM (Google) — Free, ground-truth authority

| Field    | Value                                                                             |
| -------- | --------------------------------------------------------------------------------- |
| Access   | MCP `mcp__notebooklm-mcp__*` (binary `~/.local/bin/notebooklm-mcp`)               |
| CLI      | `~/.local/bin/nlm` (Python uv-installed)                                          |
| Account  | `zero@balizero.com` (migrato da antonellosiano@ il 2026-05-18)                    |
| Snapshot | ~64 notebook attivi, ~3,618 source totali (delta vs 2026-05-03: +4 NB / +648 src) |

Vedi §4 NotebookLM stack per inventario completo.

---

## 2. Multi-LLM patterns

### 2.1 Tier cascade (autonomous agents)

Reference impl: `~/scripts/regulatory-watcher-run.sh`. Order:

| Tier | LLM                                                                   | Use when                                                              |
| ---- | --------------------------------------------------------------------- | --------------------------------------------------------------------- |
| 1    | `claude --print --model claude-sonnet-4-6` (or `-opus-4-7` synthesis) | Default. Quota-rich.                                                  |
| 2    | `agy -p --print-timeout 5m`                                           | Tier-1 quota-exhaust OR long-context (60-NB, 64 carousels, multi-PDF) |
| 3    | `codex exec --full-auto`                                              | Tier-1+2 exhaust OR code/reasoning                                    |
| 4    | `ollama run qwen3.5:9b`                                               | Tier-1+2+3 exhaust OR vision pre-filter / classifier (always-on, $0)  |

Cascade detection: grep stdout for `out of extra usage|usage limit|quota exceeded|rate.limit|429|exhausted`.

**Health-check before relying on Tier 3+4 in cron**:

```bash
codex exec --sandbox read-only "ping" || echo "codex 401, re-login needed"
ollama list | grep qwen3.5 || echo "qwen3.5 missing, pull needed"
```

### 2.2 Per-agent LLM choice

| Agent                                                  | Tier 1                                                         | Rationale                                   |
| ------------------------------------------------------ | -------------------------------------------------------------- | ------------------------------------------- |
| wr2-design-architect                                   | Opus 4.7                                                       | Orchestration + brand judgment              |
| wr2-critic                                             | Opus 4.7                                                       | Vision + nuanced rubric scoring             |
| wr2-brief-interpreter / storyboarder / layout-composer | Sonnet 4.6                                                     | Structured I/O                              |
| wr3-design-architect                                   | Opus 4.7                                                       | Video orchestration                         |
| wr3-shot-director                                      | Opus 4.7                                                       | Largest hallucination surface (Veo prompts) |
| wr3-critic                                             | Opus 4.7                                                       | 4-lane vision + brand + legal review        |
| wr3 specialists                                        | Sonnet 4.6 / Haiku VLM                                         | Structured I/O, cost optimization           |
| regulatory-watcher                                     | Sonnet 4.6                                                     | Daily classification + delta extraction     |
| deep-researcher                                        | Opus 4.7 (synthesis) + Gemini (long-context) + DeepSeek (math) | Tri-panel by design                         |
| devils-advocate                                        | Sonnet 4.6 orchestrator + DeepSeek V4 Pro reasoner             | Multi-LLM pattern                           |
| wr2-ig-metrics-analyst                                 | Gemini 3.1 Pro                                                 | 1M context for full corpus pass             |
| wr3-yt-metrics-analyst                                 | Gemini 3.1 Pro                                                 | Stesso (corpus engagement metrics)          |
| nb-curator                                             | Sonnet 4.6 (Mode A) / Gemini (Mode B health)                   | Different tool surface per mode             |
| client-case-quote-generator                            | Opus + DeepSeek                                                | Hybrid synthesis + math                     |
| competitor-monitor                                     | Sonnet + qwen2.5vl local                                       | Pre-filter saves cloud calls                |
| email-template-builder                                 | Sonnet 4.6                                                     | Mechanical brand-compliant templating       |
| hr-companion                                           | Sonnet 4.6                                                     | Bilingual ID/IT routing                     |
| yield-optimizer                                        | Sonnet 4.6 (orchestrator) + local Ollama Qwen 3.5              | CRM data privacy (UU PDP scope)             |

### 2.3 Deliberation patterns

- **Wave-orchestrator**: parallel agents on independent tasks (fan-out via Agent tool)
- **Tri-LLM panel review**: Claude + Gemini + DeepSeek on PR critical (mandatory pre-approval per spec architetturali, quote cliente, pre-deploy critical path)
- **4-LLM panel**: + NB-1 4° panelist quando UUID known per regulatory/domain ground-truth
- **Bipolar verifier**: 1 LLM main + 1 NB ground-truth (NOT 4-LLM council — bipolar è il default)
- **Ad-hoc cross-LLM brainstorm**: on demand, NOT scheduled

---

## 3. Ollama local arsenal — VERIFY PER MACHINE

**Pro snapshot 2026-05-25** (post re-pull 2026-05-24):

| Model              | Size    | Status Pro             | Use case                                             |
| ------------------ | ------- | ---------------------- | ---------------------------------------------------- |
| `qwen3.5:9b`       | 6.6 GB  | ✓ installed 2026-05-24 | classifier fast, regulatory-watcher Tier 4           |
| `qwen2.5vl:7b`     | 6.0 GB  | ✓ installed 2026-05-24 | **vision OCR — CRITICAL for CRM-Guardian Phase 1.5** |
| `bge-m3:latest`    | 1.2 GB  | ✓ installed 2026-05-24 | embed multilingual                                   |
| `deepseek-r1:32b`  | ~19 GB  | ✗ NOT pulled           | reasoning offline                                    |
| `gemma4:26b`       | ~16 GB  | ✗ NOT pulled           | translation cron                                     |
| `qwen3:8b`         | ~5 GB   | ✗ NOT pulled           | general                                              |
| `nomic-embed-text` | ~270 MB | ✗ NOT pulled           | embed                                                |

**Mini-Pro2 snapshot**: verifica con `ssh mini 'ollama list'`. Probable full mirror (server H24 role).

**Models NOT auto-replicated cross-machine.** Sempre `ollama list` prima di assumere presenza.

**Regola**: Ollama **non** in path critico decisionale (latency 30-120s). Solo cron batch + hook async.

**API caveat**: `backend/llm/ollama_client.py` richiede `think: false` per Qwen 3.5. Vision API: `"images": [base64]`, qwen2.5vl:7b ONLY (qwen3.5 Q4_K_M strips vision weights).

---

## 4. NotebookLM stack — UUID switch 2026-05-18

### 4.1 Account migration

Branch `chore/nlm-migrate-zero-account-2026-05-18` ha migrato 28 NB del core stack da `antonellosiano@gmail.com` → `zero@balizero.com` (Google Workspace) il 2026-05-18 00:14-01:14 WITA.

**Le UUID vecchie sono ancora vive** ma NON più consumate dalla pipeline. Le 353 sources "perse" dal `nb-intel-delta-watcher` sono safe sull'account antonellosiano@, semplicemente non più pollate.

UUID mapping completo: `~/logs/nb-migration-mapping.json` (28 entry).

### 4.2 UUID mapping principali

| NB                              | Old UUID (antonellosiano@, dormant)    | New UUID (zero@, active)               |
| ------------------------------- | -------------------------------------- | -------------------------------------- |
| NB-0 Meta-NLM                   | `9a70162a-db99-496a-8e3d-237982249f9c` | `cdc7ef67-8adf-4878-b007-d2fa4a5362fb` |
| NB-0 Zantara Cognitive Identity | `f03b5c70-b3a2-445f-acb0-ff0c96885fd5` | `ff6a3ee3-8cbe-4b6e-ba1f-46242ba88893` |
| NB-1 Codebase                   | `f6ecd115-dd89-4c9b-b3dd-071e0e2f1876` | `bfd6f360-05ed-43f1-a909-6beba07df018` |
| NB-2 Visa                       | `cff93ab0-813a-42f2-a8de-36987e724271` | `271c7159-0c32-49a1-bda8-803c8e0993a6` |
| NB-3 Company                    | `933509f9-1561-403d-bd44-4a7a67a36df2` | `045f3cdb-ef62-488c-90ba-82594928b671` |
| NB-5 Property                   | `d9438180-5e63-4e2a-a473-6061101f6a8d` | `93314ad3-177e-4d2f-956b-fe4be3e47697` |
| NB-6 Operations                 | `85207af3-352f-4554-8d2a-18f42cc541ba` | `7fbf37ed-e290-491a-98f5-677d6371ad62` |
| NB-7 Editorial                  | `f51ab8a0-50d0-49f1-a64f-ebc131fed7b8` | `42687fcb-87fc-40b1-8af8-8a2ff91f9c4c` |
| NB-8 Expat Life                 | `4fd8cd0f-93f1-4e43-9c9e-86c0d581852c` | `aa9ac5d7-5090-46c7-9d09-89cec4ba13de` |
| NB-INTEL-Press                  | `9d262101-abeb-4e15-af9c-c38e028c62fe` | `caec5b82-287c-464f-844f-02e2c8f04c21` |
| NB-AGENTS                       | `6d449787-04e3-430e-acbe-d6fc38d379a9` | `ac78736d-5c96-4b8f-aea1-72157bdfbb2d` |
| NB-HARARI                       | `077fd5cc-fc83-433f-a40d-b4ad5bb17a5d` | `78658a0f-ac50-4356-9ff3-13d09ebed54b` |

### 4.3 NB-INTEL family post-switch (5 NB)

| NB          | New UUID                               | Sources @ 2026-05-25          | Pre-switch (antonellosiano@) |
| ----------- | -------------------------------------- | ----------------------------- | ---------------------------- |
| AIResearch  | (verify via `nlm list`)                | ~600 (stable, dedupe pending) | 585                          |
| Press       | `caec5b82-287c-464f-844f-02e2c8f04c21` | 47                            | 215                          |
| Immigration | (verify)                               | 7                             | 80                           |
| Regulation  | (verify)                               | 3                             | 41                           |
| Tax         | (verify)                               | 10                            | 17                           |

Feeder rate post-switch ~0-10/day, troppo lento per ricostituire i pre-switch volumes via natural ingest. Bulk re-ingest necessario se serve tornare ai livelli precedenti.

### 4.4 Inventory by family

- **Core stack NB-0..NB-14**: 15 NB (status GREEN)
- **NB-INTEL family**: 5 NB (status YELLOW — recovering)
- **MATA GARUDA**: 5 documentati, 4 live (1 permanently deleted: "Indonesia Gov Data Sources" 313 src — P2 rebuild candidate)
- **Specialized**: Subhi, CRM, Research, HARARI (10 fonti, 144k parole), AGENTS (157 src, era 86 — +71 espansione 2026-05-19), nb-curator artifacts
- **New since 2026-05-17**: 12 nuovi NB creati (7 con sources, 5 empty scaffolds)

### 4.5 nb-intel-delta-watcher

| Field    | Value                                                                                            |
| -------- | ------------------------------------------------------------------------------------------------ |
| Script   | `~/scripts/nb-intel-delta-watcher.sh`                                                            |
| Schedule | `~/Library/LaunchAgents/com.nuzantara.nb-intel-delta-watcher.hourly.plist` — StartInterval 3600s |
| Profile  | `nlm list notebooks --profile zero` (già migrato)                                                |
| Log      | `~/logs/nb-intel-delta-watcher.log`                                                              |
| State    | `~/.agent/decisions/state/nb_intel_delta_state.json`                                             |
| Alert    | Telegram via `TELEGRAM_BOT_TOKEN` + `TELEGRAM_OWNER_CHAT_ID=1125336968` quando empty >24h        |

### 4.6 Pattern d'uso

- **Bipolar verifier** (default): 1 LLM main + 1 NB ground-truth specialistico
- **Decision matrix domain→NB**: vedi memory `reference_notebooklm_arsenal_full.md`
- **Authority**: NotebookLM è la ground-truth per regulatory/legal/visa/property/tax. Non inventare, citare verbatim.

---

## 5. MCP servers inventory — empirical 2026-05-25

### 5.1 Stale-signal pattern (cicatrix 2026-05-22)

`claude mcp list` Status è point-in-time at SessionStart, **NOT live**. `✗ Failed to connect` è false-positive nel 60%+ dei casi. Verifica empiricamente con tool call prima di escalare a P0.

### 5.2 Inventory table

| Categoria            | Server                                             | Transport                                   | Auth                                   | Status verify                   | Note                                                     |
| -------------------- | -------------------------------------------------- | ------------------------------------------- | -------------------------------------- | ------------------------------- | -------------------------------------------------------- |
| **Internal CRM/RAG** | `nuzantara-mcp`                                    | stdio (Python)                              | API key                                | ✓ (115+ tools)                  | Primario — CRM, portal, KBLI, comms, Drive               |
| **Internal ops**     | `nuzantara-mcp-advanced`                           | stdio                                       | API key                                | ✓                               | Fly.io diagnostics, codebase search, tests               |
| **Browser**          | `nuzantara-browser`                                | stdio (Playwright stealth)                  | none                                   | ✓                               | Default browser. Mai `mcp__playwright__*` unless ordered |
| **Postgres RO**      | `postgres-nuzantara`                               | npx `@modelcontextprotocol/server-postgres` | Keychain `nuzantara-postgres-readonly` | ✓ (despite `✗` stale)           | T3.2 (2026-05-23), 255 SELECT grants, 0 mutations        |
| **NB ground-truth**  | `notebooklm-mcp`                                   | stdio                                       | OAuth (Chrome profile)                 | ✓ (symlink ricreato 2026-05-24) | Binary `~/.local/bin/notebooklm-mcp`                     |
| **Analytics**        | `ga4-analytics`                                    | stdio                                       | GA4 service account                    | ✓                               | GA4 property 505466833                                   |
| **OCR**              | `ocr-tesseract`                                    | stdio                                       | none (local tesseract)                 | ✗ stale-PATH                    | PATH truncation fix needed                               |
| **Remote OAuth**     | `claude.ai Canva`                                  | HTTP                                        | OAuth dynamic registration (RFC 7591)  | ✓                               | UI-asset edits                                           |
| **Remote OAuth**     | `claude.ai Gmail`                                  | HTTP                                        | OAuth                                  | ✓                               | Email drafts                                             |
| **Remote OAuth**     | `claude.ai Google Drive`                           | HTTP                                        | OAuth                                  | ✓                               | Drive read                                               |
| **Failed (config)**  | `github`                                           | npx                                         | missing `GITHUB_PERSONAL_ACCESS_TOKEN` | ✗ genuine                       | Workaround: `gh` CLI                                     |
| **Failed (stale)**   | `nuzantara-fetch`, `playwright`, `plugin:context7` | uvx/npx                                     | PATH truncation                        | ✗ stale-PATH                    | Fix below                                                |

### 5.3 ROOT CAUSE — PATH truncation per 5/7 ✗

Claude Code spawna MCP server children con PATH truncato:

```
PATH=/usr/bin:/bin:/usr/sbin:/sbin:~/.local/bin
```

**`/opt/homebrew/bin/` ESCLUSO** → ogni server registrato con bare `npx`, `uvx`, `tesseract` fail.

**Fix (proposed, NOT YET applied)**: aggiungere a `.mcp.json` env block dei server affetti:

```json
"env": {
  "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
}
```

### 5.4 Stale-signal rule (operational)

**MAI escalare `✗ Failed to connect` a P0 senza tool call empirico**. Workflow:

1. `claude mcp list` mostra `✗`
2. Tenta 1 tool call leggero (es. `mcp__nuzantara-mcp__check_health`)
3. Se ritorna 200 → status era stale, MCP healthy
4. Se errore → leggi `~/Library/Logs/Claude/mcp-*.log` per child stderr

---

## 6. Subagent fleet inventory (34 user-global + plugin)

### 6.1 WR2 carousel pipeline (8 agents) — skill `bali-zero-brand`

- `wr2-design-architect` (opus, orchestrator) → fan-out via Agent tool
- Specialists: `wr2-brief-interpreter`, `wr2-storyboarder`, `wr2-layout-composer`, `wr2-image-prompt-author`, `wr2-critic`
- Scheduled: `wr2-ig-metrics-analyst` (weekly), `wr2-external-bench` (monthly)

### 6.2 WR3 video episode pipeline (13 agents) — skill `bali-zero-brand/wr3/`, `contract_version: 1.0.0`

- `wr3-design-architect` (opus, orchestrator) → fan-out
- Specialists: `wr3-brief-interpreter`, `wr3-script-editor`, `wr3-shot-director` (opus), `wr3-pre-render-gatekeeper`, `wr3-clip-renderer`, `wr3-audio-asset-producer`, `wr3-b-roll-curator` (fallback), `wr3-post-assembler`, `wr3-critic` (opus)
- Scheduled: `wr3-editorial-bench` (monthly), `wr3-yt-metrics-analyst` (weekly), `wr3-reflexion-synth` (weekly)

### 6.3 Cross-cutting (9 agents)

| Agent                         | Purpose                                             | Schedule                        |
| ----------------------------- | --------------------------------------------------- | ------------------------------- |
| `deep-researcher`             | Multi-LLM client cases + policy                     | on demand                       |
| `regulatory-watcher`          | Daily reg watch (Permenkumham/PMK/PP/Perpres)       | daily cron 07:00 WITA           |
| `devils-advocate`             | Red-team adversarial review                         | pre-publish gate                |
| `client-case-quote-generator` | Bali Zero PDF quote                                 | on demand                       |
| `email-template-builder`      | Brevo HTML compliant brand                          | on demand                       |
| `hr-companion`                | HR handbook + bilingual ID/IT                       | on demand                       |
| `yield-optimizer`             | Weekly CRM scanner (local Ollama for privacy)       | weekly Sun 04:00 WITA           |
| `competitor-monitor`          | Monthly competitor digest (Lets Move/Emerhub/Flado) | monthly                         |
| `nb-curator`                  | NB inventory + curation                             | weekly health, monthly curation |

### 6.4 Lane aggregators T3.3 (4 agents — read-only, `disallowedTools: [Edit, Write, MultiEdit, NotebookEdit]`)

- `backend-verifier` — pytest, Fly status, router audit
- `frontend-browser` — QA post-deploy via browser MCP
- `mcp-health` — diagnose MCP cluster failures
- `spalla-review` — code review co-pilot (alternative to devils-advocate)

### 6.5 Built-in Claude Code (no .md file)

- `general-purpose`, `Explore`, `Plan`, `claude`

### 6.6 Plugin-provided agents

- `feature-dev:code-architect`, `feature-dev:code-explorer`, `feature-dev:code-reviewer` (all sonnet)
- `code-simplifier:code-simplifier` (opus)
- `hookify:*`

### 6.7 Discipline rules

- **Read-only intent** → MUST have `disallowedTools` denylist (T3.3 lesson, cicatrix Wave 1 H5)
- **Brand-consuming** → load `bali-zero-brand` via `skills:` declaration
- **WR3 agents** → `contract_version` + `lifecycle_tier` (core/fallback/scheduled) per graceful retirement
- **Worktree isolation** quando dispatch multiplo su file condivisi (lesson 2026-05-24 arsenale audit)

---

## 7. Cost constraint — HARD RULE (Anthropic-specific ban)

### 7.1 Banned (Anthropic only)

Mai in nessun env (local, Fly secrets, CI, cron wrapper, Docker):

- `ANTHROPIC_API_KEY` (pay-as-you-go)
- `from anthropic import Anthropic` (SDK Python — no OAuth mode)
- `AWS_BEDROCK_*` / `VERTEX_AI_*` targeting Anthropic models
- `langchain-anthropic`, `litellm` con `anthropic/...` paid endpoint

**Sole sanctioned path**: shell out a `claude` CLI con `CLAUDE_CODE_OAUTH_TOKEN` (consuma MAX-plan quota). Reference: `apps/backend-rag/backend/llm/claude_oauth_client.py` (strippa `ANTHROPIC_API_KEY` da `os.environ` come defense-in-depth).

### 7.2 NON banned (other paid APIs OK)

La regola applica **solo** ad Anthropic perché Antonello ha 2 Claude MAX x20 = pagare per token duplicherebbe una flat subscription.

- **DeepSeek V4 Pro API** (~$0.01/query) → article_composer + tri-LLM panel gate-6
- **ChatGPT Pro $200/mo** → Codex CLI illimitato + `$imagegen`
- **Google AI Ultra** → agy CLI + NotebookLM free + Vertex Gemini OAuth free

### 7.3 Email sending rule (hardcoded)

**ALWAYS** `from=zantara@balizero.com` / `name=Zantara` (alias di `zero@balizero.com`) via Brevo endpoint `/api/notifications/send-email` + `X-API-Key: zantara-secret-2024`. Mai `notifications@`, `subhi@`, personal addresses.

---

## 8. Cicatrici recenti pertinenti all'arsenale (last 14d)

### 8.1 RESOLVED 2026-05-24 — Arsenale audit fixes

- **Codex token revoked**: re-login da terminale (Antonello fatto)
- **Ollama empty su Pro**: re-pulled qwen3.5:9b + qwen2.5vl:7b + bge-m3
- **notebooklm-mcp + nlm CLI symlinks cancellati**: ricreati in `~/.local/bin/`
- **NB-INTEL "mass purge" 2026-05-18**: era UUID switch, NON destructive event
- **DeepSeek silent-alias trap**: 3 production callsites migrati (commit `751f6c4f5`)
- **CLAUDE.md global** aggiornata (slot 1 kaiser, agy v1.0.2, codex v0.133, Ollama VERIFY PER MACHINE, cascade health-check warning)
- **Memory `reference_notebooklm_arsenal_full.md`** aggiornata con UUID mapping post-switch

### 8.2 OPEN — pending Antonello decisions

- **Claude slot 2** re-OAuth da terminale: `CLAUDE_CONFIG_DIR=$HOME/.claude-acct2 claude /login`
- **MATA GARUDA Indonesia Gov Data Sources (313 src)** rebuild
- **MCP PATH truncation fix** in `.mcp.json` env blocks (5 server stale-PATH)
- **NB-INTEL re-populate** opzionale: Press +168, Immigration +73, Regulation +38, Tax +7
- **Re-decide fate antonellosiano@ NBs** dormant: archive Drive, re-ingest priority, o leave dormant
- **Ollama complete pull**: deepseek-r1:32b + gemma4:26b + qwen3:8b + nomic-embed-text (optional, ~40GB total)

---

## 9. Health-check rapidi (run quando si dubita)

```bash
# 1. Claude OAuth slot 1
bash -lc 'unset ANTHROPIC_API_KEY; claude auth status'

# 2. Claude OAuth slot 2
bash -lc 'unset ANTHROPIC_API_KEY; CLAUDE_CONFIG_DIR=~/.claude-acct2 claude auth status'

# 3. agy
echo "ping" | timeout 30 agy -p --print-timeout 20s

# 4. Codex
codex exec --sandbox read-only --skip-git-repo-check "say ok"

# 5. DeepSeek V4 Pro (5 tokens cap = ~$0.0003)
curl -s --max-time 15 https://api.deepseek.com/chat/completions \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v4-pro","messages":[{"role":"user","content":"ping"}],"max_tokens":5}'

# 6. Ollama
ollama list
ollama ps  # active models

# 7. MCP
claude mcp list

# 8. NotebookLM CLI
nlm login --check --profile zero
nlm list notebooks --profile zero 2>&1 | head -5

# 9. notebooklm-mcp binary
~/.local/bin/notebooklm-mcp --help | head -5

# 10. Mini-Pro2 mirror (when needed)
ssh mini 'ollama list && ollama ps'
```

---

## 10. File touchpoints

| Touchpoint                    | Path                                                                                                | Purpose                             |
| ----------------------------- | --------------------------------------------------------------------------------------------------- | ----------------------------------- |
| User-global CLAUDE.md         | `~/.claude/CLAUDE.md`                                                                               | Arsenale + machine config + cascade |
| Project CLAUDE.md (Nuzantara) | `/Users/nuzantara/Desktop/nuzantara/CLAUDE.md`                                                      | Project invariants + golden rules   |
| Backend RAG CLAUDE.md         | `apps/backend-rag/CLAUDE.md`                                                                        | RAG-specific gotchas                |
| NB arsenal reference          | `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/reference_notebooklm_arsenal_full.md` | NB inventory + UUID mapping         |
| UUID migration log            | `~/logs/nb-migration-mapping.json`                                                                  | 28 entry old→new                    |
| DeepSeek key                  | `~/.openclaw/workspace/.env.master`                                                                 | NOT in shell env                    |
| Cascade wrapper               | `~/scripts/regulatory-watcher-run.sh`                                                               | Reference impl Tier 1→4             |
| Delta-watcher                 | `~/scripts/nb-intel-delta-watcher.sh`                                                               | Hourly NB-INTEL monitor             |
| Postgres MCP Keychain         | `security find-generic-password -s nuzantara-postgres-readonly`                                     | T3.2 RO role                        |
| Audit reports raw             | `/tmp/arsenale-audit-2026-05-24/`                                                                   | 6 file, ~1200 righe                 |
| Last migration commit         | `751f6c4f5` su `origin/main`                                                                        | DeepSeek v4-pro migration           |

---

_Generato 2026-05-25 da arsenale audit consolidation. Snapshot empirico verificato 4-lane parallel (LLM external + MCP + NB + Subagent fleet)._
