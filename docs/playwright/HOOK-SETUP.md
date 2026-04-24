# Claude Code PreToolUse hook — enable auto-injection

The file `~/.claude/hooks/playwright-context-inject.sh` has been written but **not activated**. Claude Code safely refuses to self-modify its own hook configuration, so you activate it manually (one time).

## One-time setup

```bash
# Make the hook executable
chmod +x ~/.claude/hooks/playwright-context-inject.sh

# Verify it works standalone
echo '{"tool_name":"mcp__playwright__browser_navigate","tool_input":{"url":"https://www.canva.com/design/DAHE6lx1lf8/edit"}}' \
  | ~/.claude/hooks/playwright-context-inject.sh
# Expect: a <system-reminder> block with Canva playbook
```

Then wire it into `~/.claude/settings.json`. Add under `hooks`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "mcp__(playwright|claude-in-chrome)__.*",
        "hooks": [
          { "type": "command", "command": "~/.claude/hooks/playwright-context-inject.sh" }
        ]
      }
    ]
  }
}
```

If `PreToolUse` already exists, append the new entry to the array.

## Effect

Every time any Claude in Claude Code is about to call:
- `mcp__playwright__browser_navigate`
- `mcp__claude-in-chrome__navigate`

…the hook reads the URL, matches it against `docs/playwright/sites/*.yaml`, and if any site matches, injects the full playbook (selectors, gotchas, recovery) as a `<system-reminder>` **before** the tool executes.

The LLM sees the context without you or it having to remember to fetch it.

## How this helps cross-LLM too

Same `inject.py` is consumed by `tools/playwright-context/cross-llm-wrapper.sh`:

```bash
cross-llm-wrapper.sh gemini canva -- "edit template DAHE6lx1lf8 text on slide 3"
# Under the hood:
#   ctx=$(inject.py --site canva --format markdown)
#   gemini -m gemini-3.1-pro-preview -p "${ctx}\n\n---\n\nUser request: ..."
```

One YAML source → any LLM.

## Validation

```bash
# Simulate a URL match
python3 /Users/nuzantara/Desktop/nuzantara/tools/playwright-context/inject.py \
  --url "https://gemini.google.com/app" --format compact
# → [gemini] flows=['generate_image'], verified=2026-04-24

python3 /Users/nuzantara/Desktop/nuzantara/tools/playwright-context/inject.py \
  --site canva --action edit_template_text
# → full markdown of the edit-template flow
```

## Uninstall

If the hook is noisy or slow:
1. Remove from `~/.claude/settings.json`
2. `chmod -x ~/.claude/hooks/playwright-context-inject.sh`

Keeping the file around (just unwired) is fine — it can be re-enabled any time.
