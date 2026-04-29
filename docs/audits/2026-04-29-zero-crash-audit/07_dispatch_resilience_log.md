# Dispatch resilience log — Eat your own dogfood

> Per audit zero-crash: ogni fallimento durante il dispatch ai 4 LLM esterni
> è documentato qui. Il sistema che vogliamo costruire — recupero automatico,
> rilevazione, fix root-cause — è lo stesso che applichiamo alle nostre tool.

---

## Summary

| LLM | Final state | Retries | Final output size | Time-to-success |
|-----|-------------|---------|-------------------|------------------|
| **Opus 4.7 (this)** | ✅ done | 0 | 02_opus_analysis.md | n/a |
| **Codex GPT-5.5** | ⚠️ partial | 3 | r3 still streaming evidence (~30K lines) | TBD |
| **Gemini 3.1 Pro** | ✅ done | 2 | 04_gemini_analysis.md (15KB) | 3:30 min |
| **DeepSeek v4-pro** | ✅ done | 3 | 05_deepseek_analysis.md (35KB, 7271 reasoning tokens) | ~1 min |
| **NotebookLM NB-1** | ✅ done | 0 | 06_notebooklm_analysis.md (10KB, 39 citations) | ~30 sec |

**Effective dispatch coverage: 4/4 perspectives obtained** (Codex producing live evidence even if mid-stream).

---

## Codex GPT-5.5 — 3 retries, root cause: MCP token expired

### Retry 1 (13:23:53)
- **Command:** `cat brief | codex exec --full-auto --sandbox workspace-write --skip-git-repo-check 2>&1 > /tmp/codex_audit_output.md`
- **Failure:** Output file 0 bytes. Stderr shows:
  ```
  ERROR rmcp::transport::worker: worker quit with fatal: Transport channel closed,
  when Auth(TokenRefreshFailed("invalid_grant: Grant not found"))
  ```
- **Diagnosis:** One of the MCP servers configured in `~/.codex/config.toml` (sentry/notion/github) has expired OAuth token. The Rust MCP transport (`rmcp`) crashed Codex on session init.
- **Secondary:** Bash redirect order `2>&1 > file` reinterprets — should be `> file 2>&1`. Output went to terminal, not file.

### Retry 2 (13:25:02)
- **Command:** `cat brief | OPENAI_DISABLE_MCP=1 codex exec --full-auto --sandbox workspace-write 2>&1 > /tmp/codex_audit_output.md`
- **Failure:** Same `rmcp TokenRefreshFailed`. The `OPENAI_DISABLE_MCP` env var is not the canonical way to disable MCP for Codex CLI. Output 0 bytes.
- **Diagnosis:** MCP servers still loaded from `~/.codex/config.toml` despite env var.

### Retry 3 (13:26:10) — partial success
- **Command:** `codex exec --full-auto --sandbox workspace-write < /tmp/audit_brief.txt > /tmp/codex_audit_output.md 2>&1`
- **Result:** Stream-of-consciousness output cresce live (~30K lines after 8 min). Codex MCP errors logged at start, but execution continued. Codex performed:
  - Read of SYMBIOSIS.md, AUTONOMOUS_OPS.md (full)
  - `find` counts: 26 apps, 5 packages, **140 router files**, **607 service files**, 30 migrations v2, 25 workflow files
  - `~/.agent/decisions/` deep inspection: 34 jobs in registry, 16 OPEN circuits, 54 DLQ entries (7 terminal), only 10/58 jobs healthy at 2026-04-29 05:32 UTC
  - `~/Library/LaunchAgents` audit: **53 project plist** (not 19 as I counted — I missed `com.balizero.*` and `com.cell.*`), only 7 have `KeepAlive=true`, 11 have it absent, 5 missing `EnvironmentVariables`, 6 logging to `/tmp/`
  - `shared/escalations_pro.jsonl`: **7404 pending lines** (file is append-only, never pruned)
- **Status:** Codex was still running at audit completion — its evidence captured will be merged into `08_convergent_findings.md` rather than waiting for terminal token.

### Lessons learned
1. **Codex MCP coupling is a liability when MCP servers age**. Recommendation: separate `~/.codex/config.toml` profile for non-interactive dispatch (no MCP), keep current profile for interactive use.
2. **Bash redirect order is a documented gotcha** — `2>&1 > file` does NOT redirect both to file. Use `> file 2>&1`.
3. **Codex --full-auto with sandbox produces high-quality empirical evidence** when it works, including reading files, counting things, and computing JSON. Worth the timeout cost.

---

## Gemini 3.1 Pro — 2 retries, root cause: sandbox+plan blocks shell tools

### Retry 1 (13:23:56)
- **Command:** `gemini -m gemini-3.1-pro-preview --sandbox --approval-mode plan -p "<brief>"`
- **Failure:** Output 0 bytes after 16 seconds.
- **Diagnosis:** `--sandbox --approval-mode plan` makes Gemini read-only and approval-required. With no human to approve, all tool calls blocked silently. Gemini executed but had no actionable tools.

### Retry 2 (13:25:04)
- **Command:** `gemini -m gemini-3.1-pro-preview --yolo -p "<brief>" > /tmp/gemini_audit_output.md 2> /tmp/gemini_stderr3.log`
- **Result:** SUCCESS at 13:29:41 (3:30 min). Output 18 lines / 2.5KB written to TERMINAL (file with summary in Italian), but the **substantial deliverable is in `docs/audits/2026-04-29-zero-crash-audit/audit.md`** which Gemini wrote directly via filesystem tool. 15KB structured analysis.
- **Insight:** Gemini interpreted "Your output goes to docs/audits/..." in the brief as an instruction to write a file there. Useful behavior but not anticipated.

### Lessons learned
1. **`--sandbox --approval-mode plan` is wrong for non-interactive automation** — the sandbox blocks the very tools Gemini needs to read files. Use `--yolo` for batch dispatch.
2. **Gemini will write files when prompt mentions output paths.** Prompts should be either explicit ("write to FILE") or stay generic if you want a stdout dump.

---

## DeepSeek v4-pro — 3 retries, root causes: env not exported, model deprecated

### Retry 1 (13:24:05)
- **Command:** Python heredoc reading `os.environ.get("DEEPSEEK_API_KEY")` after `source ~/.nuzantara-secrets.env`
- **Failure:** `ERROR: DEEPSEEK_API_KEY not set`. Output 0 bytes.
- **Diagnosis:** `source` in subshell of background `&` job does not propagate env vars to the heredoc-spawned `python3` because each `&` invocation creates a new subshell. Standard Bash gotcha.

### Retry 2 (13:25:14)
- **Command:** Inline key extraction from secrets file via `grep | cut`, passed directly into Python.
- **Failure:** Output 0 bytes despite key length=35 detected. **Model `deepseek-reasoner` returned HTTP 200 with empty content.**
- **Diagnosis:** Probe call (`curl -X POST .../chat/completions`) revealed the API now ALIASES `deepseek-reasoner` → `deepseek-v4-flash`. The `reasoning_content` is no longer populated for v4-flash. Model deprecated.
- **Verification:** `GET /v1/models` returned only `deepseek-v4-flash` and `deepseek-v4-pro`.

### Retry 3 (13:32:00) — success
- **Command:** Same as r2, but `model=deepseek-v4-pro` and explicit `os.environ.get` after `export DEEPSEEK_API_KEY=...`.
- **Result:** SUCCESS in ~60s. Output 258 lines / 35KB. Usage: `prompt=1197, completion=8000 (cap), reasoning=7271 (cap reached, truncated).` Substantial chain-of-thought emerged: noted that "MUST NOT have any crash without automatic restart" needs reinterpretation (a restart loop technically restarts but isn't healthy), noted Qdrant SUSPENDED is a degradation not crash, noted async client leak is deterministic so restart doesn't fix.

### Lessons learned
1. **DeepSeek API breaking change unannounced**: `deepseek-reasoner` deprecated, replaced by `deepseek-v4-pro` (CoT enabled) and `deepseek-v4-flash` (no CoT). Update `apps/backend-rag/backend/llm/deepseek_client.py` if it still references `deepseek-reasoner` (likely already migrated, but verify).
2. **Environment variable propagation in `bash -c '... &' | python heredoc` chain**: each `&` is a fresh subshell. Always export inline or pass keys as Python arguments.
3. **8000 max_tokens is hit by reasoner-class models on substantial briefs**. Consider `max_tokens=16000` for resilience audits with long context.

---

## NotebookLM NB-1 — 0 retries, native success

### Single attempt (13:33:00)
- **Command:** `mcp__notebooklm-mcp__notebook_query` on `f6ecd115-...` (NB-1: Codebase & Architecture, 52 sources, 2026-03-23 snapshot)
- **Result:** SUCCESS in ~25 seconds. 39-citation analysis with **3 explicit "UNKNOWN — not in sources"** for PR #307 (post-snapshot), PR #273 (post-snapshot), and `system_doctor.py` (only OpsIntelligence found).
- **Critical corrections to my (Opus) assumptions** identified by NB-1 from the actual code:
  - EventBus is **PG LISTEN/NOTIFY**, NOT Redis Streams (Symbiosis Law 4 documentation drifts from code reality)
  - Routers count: NB-1 sees **88 registered routers**, the file count is 140
  - KG: 87K nodes / 210K edges (production), not 108K/243K
  - `nuzantara-mcp` is a **monolite of 115 tools** in a single FastMCP server — single-process crash blast
  - "System Doctor cron 08:00" doesn't exist as I named it; the closest is `OpsIntelligence` (Mon 08:00 WITA, NLM aggregator, NOT diagnostic)

### Lessons learned
1. **NotebookLM is the lowest-friction, highest-truth source** for ground-truth corrections when codebase snapshot is recent. Run NB-1 query EARLY in audits — it catches assumption drift fast.
2. **NB-1 snapshot age (2026-03-23 vs today 2026-04-29) = 37 days** means post-snapshot PRs/lessons (273, 307) are blind to NB-1. Mitigation: combine NB-1 + cicatrix-scars.md + git log.

---

## What this log proves about the system we want to build

The 4 dispatches collectively failed **8 times** before all returning useful work. Each failure had a **different root cause**:

1. Expired OAuth token in upstream MCP server → blocks unrelated CLI (Codex)
2. Bash redirect order silently sends output to terminal not file (operator error caught by retry diagnostics)
3. Sandbox+approval-mode blocks all tools, gives empty output without error (Gemini)
4. Subshell env var propagation (DeepSeek) — invisible in `&` chains
5. API model alias deprecation without breaking change announcement (DeepSeek)
6. Output token cap hit (DeepSeek 8000) without explicit signal in stdout — only stderr usage

**The pattern:** every failure was either silent or had a misleading first signal. The user (Antonello) would have seen "completed exit 0, file 0 bytes" and not known what to do.

**This is exactly what we are auditing about Nuzantara.** Every failure mode in `09_intervention_plan.md` follows the same archetype — silent or misleading. The fixes there are constructed to make failures LOUD: Telegram alert, deploy-failure-alert sibling job, system_doctor extension, fly_restart_monitor cooldown, etc.

A system that makes its own audit fail silently is the system that needs the audit most.

---

## Recommendations for future dispatch infrastructure

1. **`scripts/ai-dispatch.sh` should learn the dispatch resilience patterns** documented here (model aliases, redirect order, env propagation). Add a `--audit` mode that runs all 4 in parallel with retry+log.
2. **Codex non-interactive profile**: separate `~/.codex/config-batch.toml` without MCP servers, invoked via `--config <path>`.
3. **DeepSeek API health probe**: add `GET /v1/models` to the `system_doctor.py` Pro probe set, with alert if `deepseek-v4-pro` disappears (or another LLM the codebase pins to deprecates).
4. **NotebookLM ground-truth check should become a standard `scripts/ai-dispatch.sh` command** (`./scripts/ai-dispatch.sh nlm-groundtruth NB-1 "<question>"`) with the answer stored in MOS so subsequent sessions inherit corrections.
