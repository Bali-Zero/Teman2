---
spec_id: R3
title: LiteLLM gateway test — KILLED by DS panel 2026-05-21
tier: research
priority: KILLED
effort_estimate: N/A
status: KILLED 2026-05-21 — HARD RULE Anthropic ban risk too high
basis: 2026-05-21-arming-arsenal Part 6 + ClaudeFa.st rank #3 + DS panel kill recommendation
---

# R3 — LiteLLM gateway test — ❌ KILLED 2026-05-21

## Kill rationale (DS panel verbatim)

> _"Given the HARD RULE against Anthropic API usage, the LiteLLM gateway carries inherent risk of accidental pay-per-token billing even with the prerequisite verification. The verification manual step can be misinterpreted or skipped. Unless an automated test can confirm OAuth quota retention with zero false positive possibility, this spec should be killed or downgraded to a DOCUMENT-ONLY evaluation of feasibility without any actual installation."_

## Outcome

**KILLED** 2026-05-21 per panel review outcome. Decision memory: `decision_litellm_killed_2026_05_21.md`.

## Why not "DOCUMENT-ONLY" instead

Considered DS alternative ("downgrade to feasibility paper"). Rejected because:

1. Effort 30+ min per write robust feasibility con automated OAuth quota test design
2. ROI low: anche se feasibility documenta sicurezza, prossimo "let's try LiteLLM" sessione potrebbe ignorare la review
3. Cleaner: kill = chiusura definitiva, file resta come archeology

## Alternative if multi-LLM cascade needed

Current cascade pattern works fine:

- Shell out `claude` CLI con `CLAUDE_CODE_OAUTH_TOKEN` (Tier 1)
- Fallback shell out `gemini` CLI free OAuth (Tier 2)
- Fallback `codex exec` ChatGPT Pro $200/mo subscription (Tier 3)
- Fallback Ollama local (Tier 4)

Reference impl: `~/scripts/regulatory-watcher-run.sh` per cascade pattern.

LiteLLM benefit (caching + cost tracking) NOT worth the HARD RULE risk.

## Historical content preserved below (for archeology only)

_Original spec body retained but DO NOT EXECUTE._

---

# (Historical) R3 — LiteLLM gateway test

## ⚠️ HARD RULE WARNING

Per CLAUDE.md global "Anthropic — specifically banned":

> _"The single sanctioned path: shell out to the `claude` CLI with `CLAUDE_CODE_OAUTH_TOKEN`, which consumes Max-plan quota."_

LiteLLM gateway (`ANTHROPIC_BASE_URL=http://localhost:4000`) potrebbe intercettare API calls e redirigerle. **Must verify**: does this break OAuth flow OR still consume MAX-plan quota?

If LiteLLM converts to pay-per-token → **VIOLATES HARD RULE**, abort.

## Problem (potential)

LiteLLM gateway offers:

- Multi-provider routing (Claude / Codex / Gemini / DeepSeek behind unified API)
- Cost tracking per-provider
- Caching layer (avoid duplicate calls)
- Fallback automatic on rate limit

Useful for multi-LLM agents (cascade fallback per CLAUDE.md).

## Acceptance criteria

- [ ] **PREREQUISITE 1**: Verify OAuth quota retained (no pay-per-token risk)
- [ ] Read LiteLLM docs su Claude integration mode
- [ ] If OAuth compatible, install LiteLLM in pilot
- [ ] If OAuth incompatible, document and ABORT

## Implementation steps

### Step 1 — PREREQUISITE VERIFICATION

```bash
# Read LiteLLM docs
# https://docs.litellm.ai/docs/providers/anthropic

# Specifically: does LiteLLM proxy support OAuth token?
# Or only API key?
```

Decision tree:

- If LiteLLM supports OAuth token via env var → PROCEED Step 2
- If LiteLLM only API key → **ABORT** + document

### Step 2 — Install pilot

```bash
pip install litellm
# Or via Docker
docker pull ghcr.io/berriai/litellm:main
```

### Step 3 — Configure with OAuth

```yaml
# config.yaml
model_list:
  - model_name: claude-opus-4-7
    litellm_params:
      model: anthropic/claude-opus-4-7
      api_key: os.environ/CLAUDE_CODE_OAUTH_TOKEN # OAuth not API key
```

### Step 4 — Test single call

```bash
litellm --config config.yaml --port 4000 &
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-opus-4-7",
    "messages": [{"role": "user", "content": "test"}],
    "max_tokens": 100
  }'
```

Verify:

- Response received
- Latency reasonable
- Claude MAX plan dashboard shows usage (NOT API key billing)

### Step 5 — Test quota retention

After 100 calls:

```bash
# Check MAX plan dashboard:
# https://claude.ai/settings/usage  (verifica URL)
# Expected: usage shows recent calls
# vs API key would show separate billing
```

If usage shows on MAX plan = OAuth retained ✅
If usage shows on API tier = VIOLATED HARD RULE ❌

### Step 6 — Decision

If verified safe:

- Memory entry adoption
- Use case: cron agents multi-LLM cascade

If verified unsafe:

- Memory entry "abort, reason: pay-per-token risk"
- Stay current cascade (shell out claude CLI per tier)

## Verification

### Test 1 — OAuth confirmed

Critical: usage tracked on MAX plan, NOT pay-per-token.

### Test 2 — Caching layer working

Repeat identical query, second call returns cached (faster + zero quota use).

### Test 3 — Fallback automatic

Simulate Claude rate limit (e.g., 100 burst calls), LiteLLM falls back to Gemini.

## Rollback

```bash
pkill -f litellm
# Restore direct CLI cascade in cron wrappers
```

## Open questions

1. **OAuth flow incompat**: Anthropic OAuth tokens are short-lived (refreshed by `claude` CLI). LiteLLM proxy would need refresh logic. Built-in? Verifica.
2. **Token expose**: LiteLLM running on localhost:4000 — token in memory. Other process on same machine could intercept. Risk?
3. **Multi-LLM cascade redundancy**: if cron agents already cascade via shell wrapper (`~/scripts/regulatory-watcher-run.sh`), LiteLLM è duplicato. Worth?
4. **Cost trade**: LiteLLM caching saves quota. But if OAuth has 5h rolling window unlimited, savings = zero. Worth only if pay-per-token.

→ **Conclusion**: R3 likely **NOT WORTH** if OAuth retained, **HARD STOP** if not.

## Estimated breakdown

| Step                            | Tempo      |
| ------------------------------- | ---------- |
| Read docs + verify OAuth compat | 30 min     |
| Install pilot (if compat)       | 15 min     |
| Test 1-3                        | 30 min     |
| Decision + memory               | 15 min     |
| **Total**                       | **90 min** |

**If OAuth incompat detected at Step 1 → ABORT, 30 min total.**
