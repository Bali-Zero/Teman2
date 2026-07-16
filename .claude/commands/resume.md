---
name: resume
description: Re-inject Mnemos handoff JSON post-compact. Reads precompact-handoff state files.
---

> **CANON**: repo `.claude/` (vendored 2026-07-17, PR process-toolkit SSOT) — shadows the `~/.claude/` HOME copy. Edit HERE, never in `$HOME`. Pro/Mini shadow it on `git pull`.

# /resume

Per-command contract (T3.4 panel amendment):

- **Side effects**: ZERO. Read-only — display only.
- **Input schema**: no args.
- **Failure mode**: if no handoff file found → state "no recent Mnemos handoff", do not fabricate.
- **Audit**: none.

## Steps

1. ALWAYS print the recent-sessions list first (operator preference 2026-05-30 — lista sessioni on every /resume):

```bash
python3 ~/.claude/scripts/resume-session-list.py 12
```

Display the output verbatim. If the operator replies with a `#`, resume THAT session's handoff; otherwise default to the most recent (continue with Step 2).

2. Find most recent handoff (or the one chosen above):

```bash
ls -t ~/.claude/state/precompact-handoff-*.json 2>/dev/null | head -1
```

3. If no file → output:

```
=== NO MNEMOS HANDOFF ===
No file found at ~/.claude/state/precompact-handoff-*.json.
Either: (a) session not yet compacted, (b) PreCompact hook (T2.5) not active, (c) handoff cleaned post-resume.
=== END ===
```

4. If file found → Read + display:

```
=== RESUME FROM COMPACT ===
Session ID: <id>
Timestamp: <ts>
Objective: <text>
Changed files: <list>
Verified commands: <list>
Risks: <list>
Next action: <text>
=== END RESUME ===
```

5. Confirm with user: "Continua su next action? (y/n)" — wait for explicit response before any action.

## Anti-pattern

- Read multiple handoff files and merge — ambiguous source of truth
- Auto-execute "next action" without explicit confirmation
- Delete handoff file (leave for next /resume)
