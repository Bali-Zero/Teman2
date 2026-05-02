# OpenClaw `claude-code` 3rd agent investigation — Sprint 0 Track A5 (part 1)

**Date:** 2026-05-02 · **Author:** Sprint 0 Air session (Claude Opus 4.7 1M)
**Reference:** brainstorm 2026-05-02 round 2 § "Documentare/rimuovere `claude-code` 3rd agent"

## Background

`docs/audits/2026-05-02-cell-openclaw-brainstorm/06_openclaw_ecosystem_audit.md`
flags that OpenClaw on Pro has **3 agents**, not 2 as round 1 documented.

The third agent name is **`claude-code`**. It is undocumented anywhere in
the Nuzantara codebase, in the OpenClaw release notes, or in
`~/.openclaw/openclaw.json` comments. It surfaced only via direct
introspection of the agents list during the round 1 audit.

## What's empirically known

From audit (2026-05-02 13:00 WITA, Pro):

```
Gateway port: 18789 (loopback-only)
Agents (3):
  1. main       — sandbox=off, Telegram-bound, primary multi-LLM routing chain
  2. coder      — sandbox=off, isolated workspace, web tools denied (no web_search/web_fetch/browser)
  3. claude-code — undocumented
```

This Sprint 0 Air session was unable to fetch live `claude-code` config from
Pro because Pro is unreachable via SSH at audit time
(`ping nuzantara.local: Host is down`). The investigation thus relies on
the round 1 audit transcript + grep across the local repo.

## Hypotheses

1. **Wrapper for the `claude` CLI subprocess.** The Federation Orchestrator
   (`scripts/federation_orchestrator.py`) and the AI Dispatch System
   (`scripts/ai-dispatch.sh`) both invoke `claude` as a subprocess. If
   somebody added `claude-code` to OpenClaw's agents list to expose that
   subprocess as a tool callable from Lobster workflows, this is benign —
   it would be on a config-only level (no extra running process).
2. **Trace/Audit shim.** OpenClaw's gateway logs every tool call with the
   agent that invoked it. If a `claude-code` agent name was added to map
   external Claude Code sessions onto a single OpenClaw audit lane,
   that's also benign.
3. **Stale config artifact.** Someone tested `claude-code` as an agent
   profile in March/April and forgot to remove it. No active workflows
   reference it.

`grep -r "claude-code" ~/.openclaw/workspace/workflows/` is the conclusive
test: if no Lobster workflow references `--agent claude-code`, hypothesis
3 is correct (stale config).

## Recommended action: read-only audit, then either document or remove

### Step 1 — read-only audit (MUST be done on Pro)

```bash
# Owner: Antonello, on Pro, ~5 min:
ssh pro 'python3 -c "
import json
d = json.load(open(\"$HOME/.openclaw/openclaw.json\"))
agents = d.get(\"agents\", {}).get(\"list\", [])
for a in agents:
    print(json.dumps(a, indent=2))
"'

# Confirm whether any Lobster workflow references it:
ssh pro 'grep -lr "claude-code" ~/.openclaw/workspace/workflows/ 2>/dev/null || \
  echo "no workflows reference claude-code"'

# Confirm whether gateway.log records any invocations:
ssh pro 'grep -E "agent[\"=]\\s*\"?claude-code" ~/.openclaw/logs/gateway.log 2>/dev/null \
  | tail -10 || echo "no log entries for agent=claude-code"'
```

### Step 2 — decide based on Step 1 outputs

| Outcome | Decision | Action |
|---|---|---|
| Lobster workflow references it AND gateway.log shows recent calls | **document** | Add a Markdown block in `docs/openclaw/agents.md` describing model routing + tool surface |
| Lobster workflow references it AND gateway.log silent | **document + add smoke test** | Same as above, plus add a CI smoke that invokes the agent monthly |
| No Lobster workflow references it AND gateway.log shows NO calls in 90d | **remove** | Edit `~/.openclaw/openclaw.json` to delete the entry (with backup) |
| No Lobster workflow references it BUT gateway.log shows old calls | **document + monitor** | Likely an external integration (Federation Orchestrator); document and review next sprint |

The default fallback when in doubt is **document, don't remove** — removal
without understanding the original intent is the kind of change that
Symbiosis Law 5 ("Zero come ultima istanza") gates: if Antonello created
the agent for a reason, removing it is a structural decision, not a
janitorial one.

### Step 3 — if remove (only if Step 2 verdict is "remove")

```bash
# Backup first:
ssh pro 'cp ~/.openclaw/openclaw.json ~/.openclaw/openclaw.json.pre-claude-code-removal-2026-05-02'

# Edit (jq):
ssh pro 'jq ".agents.list = (.agents.list | map(select(.name != \"claude-code\")))" \
  ~/.openclaw/openclaw.json.pre-claude-code-removal-2026-05-02 \
  > ~/.openclaw/openclaw.json'

# Hot-reload the gateway:
ssh pro 'launchctl kickstart -k gui/501/ai.openclaw.gateway'

# Verify:
ssh pro 'python3 -c "
import json
d = json.load(open(\"$HOME/.openclaw/openclaw.json\"))
print([a[\"name\"] for a in d.get(\"agents\", {}).get(\"list\", [])])
"'
```

Expected: `["main", "coder"]`.

## Out-of-scope today

- Writing `docs/openclaw/agents.md` proactively. That's a sprint-1
  hand-off if Step 2 verdict is "document".
- Investigating whether `claude-code` is connected to the Federation
  Orchestrator or any external CLI subprocess. That requires Pro's live
  filesystem.

## References

- `docs/audits/2026-05-02-cell-openclaw-brainstorm/06_openclaw_ecosystem_audit.md` § 1
- `docs/audits/2026-05-02-cell-openclaw-brainstorm/07_openclaw_deep_research.md` § A
- `~/.openclaw/openclaw.json` `agents.list[]`
- `~/.openclaw/workspace/workflows/*.lobster`
