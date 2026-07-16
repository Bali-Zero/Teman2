---
name: scar
description: Append cicatrix-scars.md entry strutturato (TRAUMA/ANTIBODY/GOTCHA). APPEND ONLY — no auto-commit.
---

> **CANON**: repo `.claude/` (vendored 2026-07-17, PR process-toolkit SSOT) — shadows the `~/.claude/` HOME copy. Edit HERE, never in `$HOME`. Pro/Mini shadow it on `git pull`.

# /scar $ARGUMENTS

Per-command contract (T3.4 panel amendment):

- **Side effects**: APPEND to `~/nuzantara/.claude/rules/cicatrix-scars.md` ONLY. NO git commit, NO push.
- **Input schema**: `<severity> <one-line description>`. Severity ∈ {P0, P1, P2, P3, RESOLVED, INFO}.
- **Failure mode**: if severity unrecognized or `$ARGUMENTS` empty → ABORT with format reminder.
- **Audit**: log timestamp + severity + description to `~/.claude/state/scar-audit.log`.

## Steps

1. Parse `$ARGUMENTS`: first token = severity, rest = description. Validate severity in allowed set.
2. Optionally ask user for: TRAUMA (one paragraph), ANTIBODY (proposed fix), GOTCHA (edge case), Reference (commit SHA / spec path / line). If `$ARGUMENTS` already contains structured content, skip.
3. Build entry:

```
### <icon> <severity>: <description> (YYYY-MM-DD)

_Discovered: YYYY-MM-DD HH:MM WITA · Severity: <severity> · Status: <derive from severity>_

**TRAUMA**: <user-supplied>

**ANTIBODY**: <user-supplied>

**GOTCHA**: <user-supplied>

**Reference**: <user-supplied>
```

Icon mapping: P0=🚨, P1=⚠️, P2=⚠️, P3=ℹ️, RESOLVED=✅, INFO=ℹ️.

4. Append via Bash heredoc (bypass Write hook for cicatrix path — appends are allowed, not destructive):

```bash
cat >> ~/nuzantara/.claude/rules/cicatrix-scars.md <<'SCAREOF'
<entry>
SCAREOF
```

5. Propagate to worktrees: `cp ~/nuzantara/.claude/rules/cicatrix-scars.md <worktree>/.claude/rules/cicatrix-scars.md` (inode-independent).

6. Append audit log:

```bash
echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ')|<severity>|<description>" >> ~/.claude/state/scar-audit.log
```

7. **NO git commit** — operator commits manually.

## Anti-pattern

- Inventare scar senza evidenza empirica (anti-hallucination)
- Auto-commit (rischio commit accidentale + cross-branch pollution)
- Skipping audit log (rende impossibile reconciliation post-fact)
