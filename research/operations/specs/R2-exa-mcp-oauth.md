---
spec_id: R2
title: Exa MCP OAuth — semantic search web for research
tier: research
priority: P3
effort_estimate: 10 min
status: DRAFT
basis: 2026-05-21-arming-arsenal Part 6 + deferred tool list empirical
empirical_today:
  - `mcp__claude_ai_Exa__authenticate` deferred tool present
  - OAuth flow ready via Claude marketplace
---

# R2 — Exa MCP OAuth

## Problem

Deep research workflow Nuzantara (deep-researcher agent, /research command) usa:

- WebSearch (Claude built-in) — limit context
- WebFetch (specific URL)
- NotebookLM domain queries

Mancante: **semantic web search** che cluster source by topic + return summary. Exa MCP fa esattamente questo, OAuth-gated via claude.ai marketplace.

## Context

Exa = semantic search engine via embeddings. MCP server (`mcp__claude_ai_Exa__*`) ha:

- `complete_authentication` flow OAuth
- Web search + semantic ranking
- Summarization built-in

Today empirical: `mcp__claude_ai_Exa__authenticate` already deferred tool, just needs OAuth click.

## Acceptance criteria

- [ ] OAuth completato Antonello → Exa account
- [ ] Tool list include `mcp__claude_ai_Exa__search` (or similar)
- [ ] Test query: returns 5-10 semantic results
- [ ] Memory entry doc usage

## Implementation steps

### Step 1 — Initiate OAuth

In Claude session:

```
mcp__claude_ai_Exa__authenticate
```

Returns URL for Antonello to visit.

### Step 2 — Antonello completes OAuth

Browser → Exa auth grant → claude.ai backend persists token.

### Step 3 — Verify in Claude

```
mcp__claude_ai_Exa__complete_authentication
```

Returns: authenticated=true.

### Step 4 — Test semantic query

```
mcp__claude_ai_Exa__search query="Indonesian KITAS visa best practices 2026"
```

Expected: 5-10 results with semantic ranking.

### Step 5 — Update deep-researcher agent

Add Exa as 5th LLM panel member (Codex + Gemini + DeepSeek + NotebookLM + Exa):

```
~/.claude/agents/deep-researcher.md update:
  - Exa: `mcp__claude_ai_Exa__search` for fresh web semantic
```

### Step 6 — Memory documentation

```bash
cat > ~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/reference_exa_mcp_2026_05_21.md << 'EOF'
---
name: exa-mcp
description: Exa semantic web search via MCP OAuth — 5th panelist deep-researcher
metadata:
  type: reference
---

# Exa MCP (R2 2026-05-21)

OAuth via claude.ai. Tool: `mcp__claude_ai_Exa__search`.

## Use per
- Fresh web semantic search (vs WebSearch limited)
- Topic clustering with summary
- Deep research multi-source 5th panelist

## Anti-pattern
- Mai per regulatory verbatim (use NotebookLM NB-INTEL family)
- Mai sostituire ground truth NB
EOF
```

## Verification

### Test 1 — Authenticated

```
mcp__claude_ai_Exa__complete_authentication
# Expected: success
```

### Test 2 — Search empirical

```
mcp__claude_ai_Exa__search query="KBLI 47749 retail apparel Indonesia"
```

Expected: results with KBLI 47749 mentions.

### Test 3 — Multi-panel integration

In /research command, verify Exa called alongside Gemini + DeepSeek.

## Rollback

```bash
# Revoke OAuth via https://claude.ai/settings/integrations
```

## Open questions

1. **Free tier limit**: Exa OAuth grants quanto query/day? Verify pricing.
2. **HTTP transport OK**: same as Vercel MCP. claude.ai cloud-mediated, not local. Acceptable per non-OSINT data.
3. **Source attribution**: Exa returns URLs. Compose research files cita Exa source verbatim? Yes (provenance).

## Estimated breakdown

| Step                  | Tempo      |
| --------------------- | ---------- |
| OAuth flow            | 3 min      |
| Test 1-3              | 4 min      |
| Memory + update agent | 3 min      |
| **Total**             | **10 min** |
