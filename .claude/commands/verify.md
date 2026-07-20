---
name: verify
description: Empirical verification — file exists / command exit / value present / process / URL. Anti-hallucination enforcement (2026-05-13).
---

> **CANON**: repo `.claude/` (vendored 2026-07-17, PR process-toolkit SSOT) — shadows the `~/.claude/` HOME copy. Edit HERE, never in `$HOME`. Pro/Mini shadow it on `git pull`.

# /verify $ARGUMENTS

Per-command contract (T3.4 panel amendment):

- **Side effects**: ZERO. Read-only. NO writes, NO state mutation.
- **Input schema**: free-form target. Infer type from shape (path / cmd / "X exists" / URL).
- **Failure mode**: report PARTIAL with reason, never fabricate.
- **Audit**: none required (no mutation).

## Steps

Esegui ADESSO la verifica empirica del target `$ARGUMENTS`. NOT da memoria/context.

Infer target type:

- File path (starts with `/` or `~`) → `ls -la <path>` + report size, perms, mtime
- Command verbatim (contains spaces + verbs) → execute + report exit code + first/last 10 lines stdout
- String/value lookup ("X in file Y") → grep
- Process name ("process X running") → `ps aux | grep -v grep | grep <name>` + count
- URL (starts with http) → `curl -sI -m 5 <url>` + HTTP status

## Output format

```
VERIFY <target>:
- Status: PASS | FAIL | PARTIAL
- Evidence: <command output verbatim, single line if possible>
- Anomalie: <list, empty if none>
```

## Anti-pattern (anti-hallucination 2026-05-13 rule 1)

NEVER cite output da context buffer. SOLO da tool call eseguito IN QUESTO turn. Se dubbio "ho letto o sto inventando" → re-eseguire tool.
