---
spec_id: T-1
title: Pre-execution global backup — single rollback point before Wave 1
tier: pre-execution
priority: P0 (MUST BE FIRST)
effort_estimate: 10 min
status: DRAFT
basis: DeepSeek V4 Pro panel review 2026-05-21 — High concern "no pre-execution global backup"
---

# T-1 — Pre-execution global backup

## Problem

Plan ha 23 spec con rollback individuali, ma nessun snapshot full environment PRIMA di iniziare Wave 1. Disaster recovery weak: se Wave 1+2 introduce regressioni interdipendenti, devo eseguire 23 rollback singoli in ordine inverso. DS panel: critical missing.

## Context

Stato a backup:

- `~/.claude/settings.json` (hook config attivo)
- `~/.claude/hooks/` (all hook scripts)
- `~/.claude/scripts/` (utility scripts)
- `~/.claude/skills/` (custom skills incl future karpathy-discipline)
- `~/.claude/commands/` (slash commands)
- `~/.claude/agents/` (subagent definitions)
- `~/.claude/state/` (Mnemos handoff files se exist)
- `~/.claude/memory.db` (MOS SQLite 10.9MB)
- `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/*.md` (memory files)
- `~/Desktop/nuzantara/CLAUDE.md` (project root)
- `~/Desktop/nuzantara/.mcp.json` (project MCP config)
- `~/Desktop/nuzantara/apps/backend-rag/CLAUDE.md` (app-level)
- `~/Desktop/nuzantara/.claude/rules/cicatrix-scars.md`

Git commit tag opzionale come secondary anchor.

## Acceptance criteria

- [ ] `~/backups/pre-orchestration-fix-${DATE}.tar.gz` exists, size > 1MB (DATE = timestamp at exec; e.g. `20260521-220000`)
- [ ] DATE value captured to `~/.claude/state/last-backup-id.txt` for use by G3 (GPT-5.5 code-review fix)
- [ ] tar verify (`tar -tzf` no error)
- [ ] Manifest file lista contenuto + SHA256 hash di ogni file critico
- [ ] External inventory file `~/backups/external-inventory-${DATE}.txt` exists with Keychain/MCP/LaunchAgents/npm state
- [ ] SQLite snapshot `~/.claude/memory.db.snapshot-${DATE}` passes `PRAGMA integrity_check` (GPT-5.5 B1 fix)
- [ ] Git commit tag `pre-orchestration-fix-${DATE}` created on main branch
- [ ] Restore test: tar extract a `/tmp/restore-test-${DATE}/` + diff vs source = clean (or expected diff documented)
- [ ] `set -euo pipefail` active throughout script (GPT-5.5 code-review fix)

## Implementation steps

### Step 1 — Create backup dir

```bash
mkdir -p ~/backups
cd ~/backups
DATE=$(date +%Y%m%d-%H%M%S)
BACKUP="pre-orchestration-fix-${DATE}.tar.gz"
echo "Target: ~/backups/$BACKUP"
```

### Step 2 — Generate manifest with hashes

```bash
cat > ~/backups/manifest-${DATE}.txt << EOF
=== Pre-orchestration-fix backup manifest ===
Date: $(date)
Machine: $(whoami)@$(hostname)
Git HEAD: $(cd ~/Desktop/nuzantara && git rev-parse HEAD)
Git branch: $(cd ~/Desktop/nuzantara && git rev-parse --abbrev-ref HEAD)
Git status: $(cd ~/Desktop/nuzantara && git status --short | wc -l) files modified

=== File hashes ===
EOF

# Hash key files
for f in \
  ~/.claude/settings.json \
  ~/.claude/memory.db \
  ~/Desktop/nuzantara/CLAUDE.md \
  ~/Desktop/nuzantara/.mcp.json \
  ~/Desktop/nuzantara/apps/backend-rag/CLAUDE.md \
  ~/Desktop/nuzantara/.claude/rules/cicatrix-scars.md
do
  [ -f "$f" ] && echo "$(shasum -a 256 "$f")" >> ~/backups/manifest-${DATE}.txt
done

# Memory file count
echo "" >> ~/backups/manifest-${DATE}.txt
echo "Memory files count: $(find ~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/ -name '*.md' 2>/dev/null | wc -l)" >> ~/backups/manifest-${DATE}.txt

# Hook count
echo "Hook scripts count: $(find ~/.claude/hooks/ -type f 2>/dev/null | wc -l)" >> ~/backups/manifest-${DATE}.txt

# Skills count
echo "Skills count: $(find ~/.claude/skills/ -name 'SKILL.md' 2>/dev/null | wc -l)" >> ~/backups/manifest-${DATE}.txt

cat ~/backups/manifest-${DATE}.txt
```

### Step 2.5 — SQLite quiesce (GPT-5.5 B1 fix)

memory.db è SQLite WAL mode attivo. Raw tar copy può catturare WAL/SHM inconsistente. Use proper backup:

```bash
# Verify integrity BEFORE backup
sqlite3 ~/.claude/memory.db "PRAGMA integrity_check;" | head -3
# Expected: "ok"

# Atomic snapshot via SQLite .backup (safe even if writers active)
sqlite3 ~/.claude/memory.db ".backup ~/.claude/memory.db.snapshot-${DATE}"

# Verify snapshot integrity
sqlite3 ~/.claude/memory.db.snapshot-${DATE} "PRAGMA integrity_check;" | head -3
# Expected: "ok"
```

### Step 3 — Create tar.gz (extended scope per GPT-5.5 B2)

```bash
set -euo pipefail   # GPT-5.5 code-review fix: was implicit, now explicit

# Manifest inventory of EXTERNAL state (Keychain, MCP registry, LaunchAgents, npm)
# ⚠️ THIS BLOCK IS SUPERSEDED BY "FIX 1 — Names-only external inventory" BELOW
# (iteration-2 devils-advocate CRITICAL: this `security dump-keychain | grep` line
# writes Keychain metadata to an unencrypted flat file — anti-pattern. The FIX 1
# replacement at the bottom of this spec is the authoritative inventory block.)
EXTERNAL_INVENTORY=~/backups/external-inventory-${DATE}.txt
{
    echo "=== Claude MCP registry ==="
    claude mcp list 2>/dev/null || echo "(no MCP listed)"
    echo ""
    echo "=== Keychain Bali Zero items ==="
    security dump-keychain 2>/dev/null | grep -E "PG_PASSWORD|GITHUB_PAT|TELEGRAM_BOT|GDRIVE_|OPENAI" | head -30 || true  # ⚠️ DO NOT USE — see FIX 1 below
    echo ""
    echo "=== LaunchAgents loaded ==="
    launchctl list | grep -E "com.balizero|com.nuzantara|com.cell" || true
    echo ""
    echo "=== npm globals ==="
    npm ls -g --depth=0 2>/dev/null || true
    echo ""
    echo "=== Active claude processes ==="
    ps aux | grep -E "claude\b" | grep -v grep || true
} > "$EXTERNAL_INVENTORY"
echo "External inventory: $EXTERNAL_INVENTORY"

# Tarball — extended scope (GPT-5.5 B2 fix)
# set -o pipefail ensures tar errors propagate (was hidden by tail before)
cd ~
tar -czf ~/backups/$BACKUP \
    .claude/settings.json \
    .claude/hooks/ \
    .claude/scripts/ \
    .claude/skills/ \
    .claude/commands/ \
    .claude/agents/ \
    .claude/state/ \
    .claude/memory.db.snapshot-${DATE} \
    .claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/ \
    Library/LaunchAgents/com.balizero.*.plist \
    Library/LaunchAgents/com.nuzantara.*.plist \
    scripts/ \
    .zshenv \
    .config/nuzantara/ \
    Desktop/nuzantara/CLAUDE.md \
    Desktop/nuzantara/.mcp.json \
    Desktop/nuzantara/apps/backend-rag/CLAUDE.md \
    Desktop/nuzantara/.claude/rules/cicatrix-scars.md
TAR_EXIT=$?
echo "tar exit: $TAR_EXIT"
if [ $TAR_EXIT -ne 0 ]; then
    echo "❌ tar failed — abort backup"
    exit 1
fi
```

Note: `.claude/state/` può non esistere ancora (creato da T2.5). Tar continua su missing — verify warning. Some scripts may not exist yet (created by other specs). Use `-h` or skip-missing if needed.

**External state NOT in tarball** (per GPT-5.5 B2):

- Keychain items (just inventory in `external-inventory-*.txt`)
- npm globals (inventory only)
- claude mcp registry (inventory only)
- Postgres role `nuzantara_readonly` (created by T3.2, must be teardown via G0)
- Vercel/Fly remote config (must be teardown via G0)

### Step 4 — Verify tar integrity

```bash
ls -la ~/backups/$BACKUP
# Expected: size > 1MB (memory.db è 10.9MB già, total likely 15-25MB)

tar -tzf ~/backups/$BACKUP | wc -l
# Expected: > 50 file

tar -tzf ~/backups/$BACKUP | head -20
# Sanity check: vede paths attesi

# Test extract a tmp + diff
mkdir -p /tmp/restore-test-${DATE}
tar -xzf ~/backups/$BACKUP -C /tmp/restore-test-${DATE}/
ls /tmp/restore-test-${DATE}/
# Verify: ~.claude/, Desktop/ structure preserved
diff -rq ~/.claude/settings.json /tmp/restore-test-${DATE}/.claude/settings.json
# Expected: no output (identical)
```

### Step 4.5 — Save backup_id for G3 (GPT-5.5 code-review fix)

```bash
mkdir -p ~/.claude/state
echo "$DATE" > ~/.claude/state/last-backup-id.txt
echo "Backup ID saved: $DATE → ~/.claude/state/last-backup-id.txt"
# G3 will read this to know which backup_id to roll back to
```

### Step 5 — Git tag

```bash
cd ~/Desktop/nuzantara
git tag -a "pre-orchestration-fix-${DATE}" -m "Snapshot before orchestration regression fix Wave 1-4

Plan: research/operations/specs/00-INDEX.md
Backup tarball: ~/backups/pre-orchestration-fix-${DATE}.tar.gz
Manifest: ~/backups/manifest-${DATE}.txt

DeepSeek panel verdict: APPROVE_WITH_FIXES (2026-05-21)
"
git tag -l "pre-orchestration-fix-*"
# Expected: tag listed

# Push tag to remote (autonomous L2 OK)
git push origin "pre-orchestration-fix-${DATE}"
```

### Step 6 — Update memory

```bash
cat > ~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/reference_orchestration_fix_backup_2026_05_21.md << EOF
---
name: orchestration-fix-backup-20260521
description: Pre-Wave-1 backup snapshot — single rollback point for orchestration regression fix
metadata:
  type: reference
---

# Orchestration regression fix backup (T-1 2026-05-21)

## Backup location
~/backups/pre-orchestration-fix-${DATE}.tar.gz (size: $(du -h ~/backups/$BACKUP | cut -f1))

## Manifest
~/backups/manifest-${DATE}.txt

## Git tag
\`pre-orchestration-fix-${DATE}\` on main branch

## To rollback (full)
\`\`\`bash
# Stop Claude Code session first
cd ~ && tar -xzf ~/backups/pre-orchestration-fix-${DATE}.tar.gz
cd ~/Desktop/nuzantara && git reset --hard pre-orchestration-fix-${DATE}
\`\`\`

## See also
- G3-global-rollback.md (orchestrated rollback procedure)
- 00-INDEX.md (full plan)
EOF
```

## Verification

### Test 1 — backup exists + size

```bash
ls -la ~/backups/pre-orchestration-fix-*.tar.gz
# Expected: ≥1 file, size > 1MB
```

### Test 2 — manifest readable

```bash
cat ~/backups/manifest-*.txt | head
# Expected: SHA256 hashes present
```

### Test 3 — extract dry-run

```bash
tar -tzf ~/backups/pre-orchestration-fix-*.tar.gz | wc -l
# Expected: > 50
```

### Test 4 — git tag pushed

```bash
git ls-remote --tags origin | grep pre-orchestration-fix
# Expected: tag on remote
```

## Rollback (of backup itself)

Solo se backup tarball corrotto:

```bash
rm ~/backups/pre-orchestration-fix-${DATE}.tar.gz
# Re-run T-1
```

NB: il backup tarball stesso è IL rollback per le altre 23 spec.

## Fix WAVE -1 (2026-05-21): tolerate missing paths + mkdir -p T3.4 commands dir

### Problem (DS NI-2 + GPT-5.5 second-pass blocker, empirically validated 2026-05-21 smoke test)

Step 3 used `tar -czf "$BACKUP" <explicit path list>` under `set -euo pipefail`. Multiple paths in that list MAY NOT exist on a given Pro machine — smoke test 2026-05-21 confirmed `~/.claude/commands/` is currently absent (will be created by T3.4). `tar` returns non-zero on missing paths → `pipefail` propagates → whole T-1 step aborts BEFORE Wave 0 → executor halts → operator blocked.

Also: T3.4 spec depends on `~/.claude/commands/` existing as a directory. If T-1 doesn't materialize it (or at minimum tolerate its absence), T3.4 will fail-open downstream.

### Fix — dynamic include-list builder + glob expansion guard

Replace the static path list in Step 3 with a manifest builder that:

1. Iterates each candidate path (literal or glob).
2. Performs existence check (`-e`) per resolution.
3. Filters glob patterns that resolve to the literal pattern (zero matches in bash without `nullglob`).
4. Emits only existing paths to a temp manifest passed to `tar -T`.
5. `mkdir -p` for any optional dir that downstream specs depend on (notably T3.4's commands dir).

```bash
set -euo pipefail   # unchanged

# Pre-create dirs that downstream specs (T3.4 et al.) expect to exist.
# Idempotent: mkdir -p does NOT fail on existing dirs.
mkdir -p "$HOME/.claude/commands"
mkdir -p "$HOME/.claude/state"

# Build include-list dynamically — tolerates missing paths + glob expansion
INCLUDE_FILE=$(mktemp -t t1-include.XXXXXX)
trap 'rm -f "$INCLUDE_FILE"' EXIT

# Candidate paths (literals + globs). Order: relative-to-HOME for tar consumption.
# tar runs from `cd ~`, so paths in manifest must be HOME-relative.
CANDIDATES=(
    ".claude/settings.json"
    ".claude/hooks/"
    ".claude/scripts/"
    ".claude/skills/"
    ".claude/commands/"
    ".claude/agents/"
    ".claude/state/"
    ".claude/memory.db.snapshot-${DATE}"
    ".claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/"
    "Library/LaunchAgents/com.balizero.*.plist"
    "Library/LaunchAgents/com.nuzantara.*.plist"
    "scripts/"
    ".zshenv"
    ".config/nuzantara/"
    "Desktop/nuzantara/CLAUDE.md"
    "Desktop/nuzantara/.mcp.json"
    "Desktop/nuzantara/apps/backend-rag/CLAUDE.md"
    "Desktop/nuzantara/.claude/rules/cicatrix-scars.md"
)

cd ~   # tar expects HOME-relative paths

for p in "${CANDIDATES[@]}"; do
    # Expand glob (if any). Without nullglob, an unmatched glob remains
    # literal — we filter by `-e` existence check below.
    # shellcheck disable=SC2206
    matches=($p)
    for m in "${matches[@]}"; do
        if [ -e "$m" ]; then
            echo "$m" >> "$INCLUDE_FILE"
        else
            echo "  ⓘ skip missing: $m" >&2
        fi
    done
done

# Guard: refuse to tar an empty manifest (would produce a 45-byte empty
# tarball that downstream verify Step 4 would NOT catch via size>1MB alone
# but easier to trap here).
if [ ! -s "$INCLUDE_FILE" ]; then
    echo "❌ INCLUDE_FILE is empty — no candidate paths exist. ABORT." >&2
    exit 1
fi

echo "📋 Backing up $(wc -l < "$INCLUDE_FILE") paths:"
cat "$INCLUDE_FILE" | sed 's/^/   /'

# Tar consumes manifest via -T (one path per line). NULL-delimited variant
# (-T - --null) avoids issues with paths containing newlines — none expected
# in this manifest, but if a future candidate has spaces it's already safe
# because tar -T reads one full line as one path.
tar -czf ~/backups/$BACKUP -T "$INCLUDE_FILE"
TAR_EXIT=$?
echo "tar exit: $TAR_EXIT"
if [ $TAR_EXIT -ne 0 ]; then
    echo "❌ tar failed — abort backup" >&2
    exit 1
fi
```

### Verification (dry-run with missing paths)

Smoke test on a Pro machine where `~/.claude/commands` was deleted:

```bash
# Simulate missing path
[ -d ~/.claude/commands ] && mv ~/.claude/commands ~/.claude/commands.bak

# Run Step 3 dynamic builder dry-run (no tar exec)
INCLUDE_FILE=$(mktemp)
CANDIDATES=(
    ".claude/settings.json"
    ".claude/commands/"
    "Library/LaunchAgents/com.balizero.*.plist"
    "Library/LaunchAgents/com.does-not-exist.*.plist"
)
cd ~
for p in "${CANDIDATES[@]}"; do
    matches=($p)
    for m in "${matches[@]}"; do
        [ -e "$m" ] && echo "$m" >> "$INCLUDE_FILE" || echo "skip: $m" >&2
    done
done

# Expected stderr:
#   skip: .claude/commands/                          (missing — was renamed)
#   skip: Library/LaunchAgents/com.does-not-exist.*.plist   (unexpanded glob)
# Expected INCLUDE_FILE content:
#   .claude/settings.json
#   Library/LaunchAgents/com.balizero.*.plist (one entry per real match)

cat $INCLUDE_FILE
rm -f $INCLUDE_FILE

# After mkdir -p (in the real Step 3):
mkdir -p ~/.claude/commands
ls -la ~/.claude/commands/   # exists, empty dir

# Restore (test cleanup)
[ -d ~/.claude/commands.bak ] && rmdir ~/.claude/commands && mv ~/.claude/commands.bak ~/.claude/commands
```

Expected results:

- Missing literal path (`~/.claude/commands/` when absent) → skipped, manifest does NOT contain entry, tar succeeds on the remaining real paths.
- Unmatched glob (`com.does-not-exist.*.plist`) → bash leaves literal pattern → `[ -e "<literal-pattern>" ]` returns false → skipped (no spurious entry).
- After `mkdir -p`, T3.4 downstream can assume the dir exists.

### Why this matters (WAVE -1 evidence)

DeepSeek V4 Pro second-pass NI-2 and GPT-5.5 second-pass blocker both flagged this. Empirical Pro filesystem state 2026-05-21 confirmed `~/.claude/commands` absent. Without the fix, the executor would halt at T-1 Step 3 before reaching Wave 0, blocking the entire 23-spec plan. This is the highest-leverage one-line semantic change in the WAVE -1 cumulative panel.

### Failure modes mitigated

| Failure                                                 | Old behavior                                                      | New behavior                                             |
| ------------------------------------------------------- | ----------------------------------------------------------------- | -------------------------------------------------------- |
| `~/.claude/commands/` missing                           | `tar` exit≠0 → pipefail → abort                                   | Skipped in manifest, T-1 proceeds                        |
| `~/.config/nuzantara/` missing                          | `tar` exit≠0 → pipefail → abort                                   | Skipped, no entry in manifest                            |
| Glob with zero matches (e.g. no `com.balizero.*.plist`) | bash leaves literal `com.balizero.*.plist` → `tar` warns or fails | `[ -e ]` check filters out the literal pattern → skipped |
| `.zshenv` absent (clean machine)                        | abort                                                             | skipped                                                  |
| All candidates missing                                  | empty INCLUDE_FILE → tar would emit empty tarball                 | Explicit `[ ! -s ]` guard aborts with clear message      |
| T3.4 depends on `~/.claude/commands`                    | T3.4 fails-open                                                   | `mkdir -p` in T-1 materializes the dir                   |

## Fix WAVE -1 Iteration 2 (2026-05-21)

This section integrates the iteration-2 devils-advocate findings on top of the iteration-1 fixes above. Two fixes apply to T-1:

- **FIX 1 (CRITICAL)** — Replace plaintext Keychain dump in external inventory with a names-only extraction (or, alternatively, GPG-encrypted snapshot).
- **FIX 3 (CROSS-CUTTING)** — Document daemon-bootout-before-`git reset` as the primary rollback recipe; T1.2 guardrails whitelist is a secondary belt-and-suspenders.

### FIX 1 — Names-only external inventory (CRITICAL)

#### Problem (iteration-2 devils-advocate, severity CRITICAL)

Iteration-1 Step 3 wrote the external inventory with this line:

```bash
security dump-keychain 2>/dev/null \
    | grep -E "PG_PASSWORD|GITHUB_PAT|TELEGRAM_BOT|GDRIVE_|OPENAI" | head -30 || true
```

`security dump-keychain` emits Keychain item metadata. While it does NOT dump the secret values themselves (those require an explicit unlock + `-w` flag per item), the dump still contains:

- `acct` (account name, often the user identifier or token label)
- `svce` (service name, including suffixes that hint at scope: `OPENAI_API_KEY`, `GITHUB_PAT_repo_scope`, etc.)
- `cdat`/`mdat` (creation/modification dates — useful for an attacker to correlate with leak timelines)
- `desc`, `gena`, `icmt` — free-form fields that operators sometimes use to stash hints, expiry notes, or even partial values

The output is then redirected into `~/backups/external-inventory-${DATE}.txt` — an unencrypted, world-readable-if-permissions-drift flat file under `~/backups/` (default mode `0644` for files created by `>` redirection in a default umask=022 zsh).

This is the EXACT anti-pattern cicatrix `2026-04-29 / Unknown agent overwrites loaded LaunchAgent plist files with JSON dump` documents: secrets-adjacent metadata persisted to disk in plain text, where a subsequent process (sibling AI agent, filesystem MCP, or a rogue `tar` of `~/backups/` to a cloud bucket) can exfiltrate it.

#### Fix — two acceptable patterns

##### Pattern A (RECOMMENDED) — names-only inventory, no values, no metadata

Strip the dump down to just the `svce` (service-name) field, sorted and de-duplicated. The inventory tells the operator WHICH Keychain entries existed at backup time (sufficient for restore checklist: "did `PG_PASSWORD_RO` exist? did `OPENAI_API_KEY` exist?") without exposing any password material, account hints, or temporal metadata.

```bash
# Names-only Keychain inventory (FIX 1, Pattern A)
# Extracts only svce (service-name) field, NO values, NO acct, NO dates.
NAMES_FILE=~/backups/external-inventory-${DATE}.names.txt
security dump-keychain 2>/dev/null \
    | awk '/^[[:space:]]*"svce"/ { gsub(/[<>]/,"",$NF); print $NF }' \
    | grep -E "PG_PASSWORD|GITHUB_PAT|TELEGRAM_BOT|GDRIVE_|OPENAI" \
    | sort -u \
    > "$NAMES_FILE"
chmod 0600 "$NAMES_FILE"

echo "Names-only Keychain inventory written: $NAMES_FILE"
echo "Entries captured: $(wc -l < "$NAMES_FILE")"
```

Properties:

- The `awk` extractor matches only lines of the form `"svce"<blob>="<service-name>"` from `security dump-keychain` text output and prints just the value.
- `grep -E` filters down to the Bali Zero / Nuzantara namespace prefixes (operator-controlled allowlist of prefixes).
- `sort -u` de-duplicates and removes ordering signal (timestamps, keychain-iteration order, etc.) that could otherwise be a side-channel.
- `chmod 0600` immediately after creation ensures the file is owner-read-only, defending against `~/backups/` permission drift.
- No password values, no account names, no dates.

Why this is sufficient for the restore checklist: at restore time, the operator does NOT need the value (Keychain values are retrieved live via `security find-generic-password -s <name> -w` against the restored Keychain DB or are re-generated). The operator needs to know WHICH names to look for. Names-only delivers exactly that.

##### Pattern B (advanced) — GPG-encrypted snapshot for value-restore capability

If the operator has a use case where value-restore from the inventory is genuinely required (e.g., a machine-loss disaster where the Keychain itself is gone), use a symmetrically encrypted snapshot with an operator-typed passphrase (NOT an env var, NOT a file, NOT a flag — passphrase must be ephemeral, in operator memory only).

```bash
# Pattern B — GPG-encrypted full inventory (only if value-restore needed)
# DANGER: operator must remember the passphrase for restore. No recovery path.
ENC_FILE=~/backups/external-inventory-${DATE}.txt.gpg
security dump-keychain 2>/dev/null \
    | grep -E "PG_PASSWORD|GITHUB_PAT|TELEGRAM_BOT|GDRIVE_|OPENAI" \
    | gpg --symmetric --cipher-algo AES256 --no-symkey-cache --output "$ENC_FILE"
# gpg prompts on tty for passphrase; operator types once, gpg does NOT cache.
chmod 0600 "$ENC_FILE"

echo "Encrypted inventory written: $ENC_FILE"
echo "Restore: gpg --decrypt $ENC_FILE  (will prompt for the passphrase)"
```

Trade-offs:

| Trade-off                 | Pattern A (names-only)                                  | Pattern B (GPG encrypted)                                                      |
| ------------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------ |
| Plaintext on disk         | None (only names)                                       | None (encrypted ciphertext)                                                    |
| Restore from inventory    | Possible for "did entry X exist?" — sufficient for T3.x | Possible to recover the actual metadata fields                                 |
| Passphrase management     | None required                                           | Operator MUST remember; no recovery if forgotten                               |
| Failure mode if drift     | File becomes 0644-readable → still leaks only names     | File becomes 0644-readable → still ciphertext, requires passphrase to exploit  |
| Coupling to GPG toolchain | No external deps                                        | Requires `gpg` (Homebrew `gnupg`) installed; macOS does not ship with it       |
| Recommended for           | Default — Bali Zero restore checklist                   | Only when value-recovery from inventory is genuinely required (rare scenarios) |

**Recommendation**: use Pattern A by default. Document Pattern B for operators who explicitly need value-restore capability.

#### Replace iteration-1 Step 3 inventory block with this

```bash
# Manifest inventory of EXTERNAL state — Pattern A (names-only Keychain, FIX 1)
EXTERNAL_INVENTORY=~/backups/external-inventory-${DATE}.txt
NAMES_FILE=~/backups/external-inventory-${DATE}.names.txt

{
    echo "=== Claude MCP registry ==="
    claude mcp list 2>/dev/null || echo "(no MCP listed)"
    echo ""
    echo "=== Keychain entries (names only, NO values, NO metadata) ==="
    echo "Inventory file: $NAMES_FILE (see for sorted list)"
    echo ""
    echo "=== LaunchAgents loaded ==="
    launchctl list | grep -E "com.balizero|com.nuzantara|com.cell" || true
    echo ""
    echo "=== npm globals ==="
    npm ls -g --depth=0 2>/dev/null || true
    echo ""
    echo "=== Active claude processes ==="
    ps aux | grep -E "claude\b" | grep -v grep || true
} > "$EXTERNAL_INVENTORY"
chmod 0600 "$EXTERNAL_INVENTORY"

# Names-only Keychain (FIX 1 Pattern A)
security dump-keychain 2>/dev/null \
    | awk '/^[[:space:]]*"svce"/ { gsub(/[<>]/,"",$NF); print $NF }' \
    | grep -E "PG_PASSWORD|GITHUB_PAT|TELEGRAM_BOT|GDRIVE_|OPENAI" \
    | sort -u \
    > "$NAMES_FILE"
chmod 0600 "$NAMES_FILE"

echo "External inventory: $EXTERNAL_INVENTORY"
echo "Names-only Keychain: $NAMES_FILE ($(wc -l < "$NAMES_FILE") entries)"
```

#### Acceptance criteria update for FIX 1

- [ ] `~/backups/external-inventory-${DATE}.txt` does NOT contain the substring `security dump-keychain` output rows (only the pointer line referencing the names file).
- [ ] `~/backups/external-inventory-${DATE}.names.txt` exists, mode `0600`, contains only service-name strings (one per line, sorted, no metadata).
- [ ] `grep -E "BEGIN|password|secret|api[-_]?key" ~/backups/external-inventory-${DATE}.names.txt` returns NO matches (sanity: only namespace-prefix names like `PG_PASSWORD_RO`, `OPENAI_API_KEY`, etc., not the values themselves).
- [ ] If Pattern B is selected: `file ~/backups/external-inventory-${DATE}.txt.gpg` returns `GPG symmetrically encrypted data`.

### FIX 3 — Daemon-bootout-before-`git reset` rollback recipe (CROSS-CUTTING)

#### Problem (iteration-2 devils-advocate, severity CROSS-CUTTING)

The iteration-1 documented rollback recipe (in Step 6 "Update memory" block) is:

```bash
cd ~ && tar -xzf ~/backups/pre-orchestration-fix-${DATE}.tar.gz
cd ~/Desktop/nuzantara && git reset --hard pre-orchestration-fix-${DATE}
```

T1.2 (Worker A2 scope) ships a guardrails daemon (`com.balizero.guardrails-daemon`) that monitors for dangerous git operations. The iteration-1 T1.2 design whitelists EXACTLY the tag pattern `pre-orchestration-fix-*` so `git reset --hard pre-orchestration-fix-<DATE>` is allowed.

However: if the guardrails daemon is itself **wedged** (deadlocked, OOM, stuck reading from a closed pipe — empirically observed in cicatrix `2026-05-13 daemon liveness probe`), the whitelist evaluation never completes. `git reset --hard` blocks waiting for daemon ack, the operator times out, and the rollback is half-applied — the WORST possible failure mode.

The whitelist is a NECESSARY but not SUFFICIENT condition for safe rollback. The SUFFICIENT condition is: ensure the daemon is not in the path of the rollback command at all.

#### Fix — primary rollback recipe with explicit daemon bootout

Document this as the PRIMARY rollback procedure. The T1.2 whitelist is documented as the SECONDARY belt-and-suspenders for when the operator forgets to bootout the daemon.

```bash
# Primary T-1 + G3 rollback recipe (FIX 3 — daemon-bootout-first)

# Variables — operator fills these in from ~/.claude/state/last-backup-id.txt
BACKUP_ID=$(cat ~/.claude/state/last-backup-id.txt 2>/dev/null || echo "MISSING")
if [ "$BACKUP_ID" = "MISSING" ]; then
    echo "❌ ~/.claude/state/last-backup-id.txt missing — cannot determine which backup to roll back to" >&2
    echo "   Inspect ~/backups/ manually and set BACKUP_ID=<YYYYMMDD-HHMMSS>" >&2
    exit 1
fi
echo "→ Rolling back to backup: $BACKUP_ID"

# Step 1 — shutdown guardrails daemon FIRST (out-of-path)
# This is non-negotiable: a wedged daemon will block git reset --hard
# regardless of the T1.2 whitelist. Bootout removes the daemon from the
# kernel's launchd registry, freeing the rollback command from any daemon
# interception path.
launchctl bootout gui/$(id -u)/com.balizero.guardrails-daemon 2>/dev/null || true
echo "  ✓ guardrails-daemon booted out (or was not loaded)"

# Step 2 — extract tarball (re-applies pre-Wave-1 file state)
cd ~ || exit 1
tar -xzf ~/backups/pre-orchestration-fix-${BACKUP_ID}.tar.gz
echo "  ✓ tarball extracted from ~/backups/pre-orchestration-fix-${BACKUP_ID}.tar.gz"

# Step 3 — git reset --hard, now unguarded (daemon is OUT)
cd ~/Desktop/nuzantara || exit 1
git reset --hard "pre-orchestration-fix-${BACKUP_ID}"
echo "  ✓ git reset --hard pre-orchestration-fix-${BACKUP_ID} succeeded"

# Step 4 — re-bootstrap guardrails daemon AFTER rollback completes
# Critical: do NOT skip this step. A rollback that leaves the guardrails
# daemon unloaded means subsequent post-rollback git operations (including
# the operator's NEXT session) have no protection.
if [ -f ~/Library/LaunchAgents/com.balizero.guardrails-daemon.plist ]; then
    launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.guardrails-daemon.plist
    echo "  ✓ guardrails-daemon re-bootstrapped"
else
    echo "  ⚠ ~/Library/LaunchAgents/com.balizero.guardrails-daemon.plist not found"
    echo "    (rollback may have removed it — check T1.2 spec for re-install)"
fi

# Step 5 — verify rollback succeeded
cd ~/Desktop/nuzantara
git log -1 --oneline
git status --short
echo "→ Rollback complete. Verify HEAD matches the tag commit."
```

#### Why this order is correct

1. **Daemon bootout BEFORE tar extract**: the tar might include / overwrite the daemon plist. If the daemon is loaded during overwrite, launchd may hold the file open and the new plist content won't take effect. Booting out first releases any open file handle.
2. **Daemon bootout BEFORE git reset**: a wedged daemon's `PreCommit`/`PreRef` hook (or sibling monitoring path) can block `git reset --hard` indefinitely. Booting out removes that interception.
3. **Daemon re-bootstrap AFTER everything**: leaving the daemon unloaded post-rollback is a SECURITY REGRESSION — the next git operation in any session has no guardrail. Always re-bootstrap.

#### Secondary recipe (when operator forgets daemon bootout)

If the operator runs `git reset --hard pre-orchestration-fix-${BACKUP_ID}` without booting out the daemon first, the T1.2 whitelist is supposed to allow it. This is the BELT-AND-SUSPENDERS layer:

- T1.2 whitelist matches `^pre-orchestration-fix-[0-9]{8}-[0-9]{6}$` tag pattern → allowed.
- If the daemon is HEALTHY, the whitelist evaluates in <100ms and the rollback proceeds.
- If the daemon is WEDGED, the whitelist NEVER evaluates → rollback hangs → operator must Ctrl-C + bootout manually (and may have partially-applied state).

For this reason, the PRIMARY recipe above is the recommended path. The T1.2 whitelist is documented in T1.2 itself; it is NOT a substitute for the primary recipe.

#### Acceptance criteria update for FIX 3

- [ ] The memory file written in Step 6 (`reference_orchestration_fix_backup_2026_05_21.md`) embeds the PRIMARY recipe above (with `launchctl bootout` as Step 1) — NOT the iteration-1 simplified `tar -xzf && git reset --hard` block.
- [ ] The memory file documents that the T1.2 whitelist is the SECONDARY layer, not a replacement for daemon bootout.
- [ ] A smoke-test rollback against a sacrificial branch verifies that the recipe runs to completion without the operator needing to re-bootstrap the daemon manually (Step 4 re-bootstrap is in the recipe).

### Update to Step 6 — Memory entry

Replace the `## To rollback (full)` block in the iteration-1 Step 6 heredoc with the FIX 3 recipe above. The new memory file contents:

```bash
cat > ~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/reference_orchestration_fix_backup_2026_05_21.md << EOF
---
name: orchestration-fix-backup-20260521
description: Pre-Wave-1 backup snapshot — single rollback point for orchestration regression fix
metadata:
  type: reference
---

# Orchestration regression fix backup (T-1 2026-05-21)

## Backup location
~/backups/pre-orchestration-fix-${DATE}.tar.gz (size: $(du -h ~/backups/$BACKUP | cut -f1))
Names-only Keychain inventory: ~/backups/external-inventory-${DATE}.names.txt

## Manifest
~/backups/manifest-${DATE}.txt

## Git tag
\`pre-orchestration-fix-${DATE}\` on main branch

## To rollback (PRIMARY recipe — daemon-bootout-first, FIX 3)
\`\`\`bash
BACKUP_ID="${DATE}"
# Step 1: shutdown guardrails daemon (out-of-path)
launchctl bootout gui/\$(id -u)/com.balizero.guardrails-daemon 2>/dev/null || true
# Step 2: extract tarball
cd ~ && tar -xzf ~/backups/pre-orchestration-fix-\${BACKUP_ID}.tar.gz
# Step 3: git reset --hard (unguarded)
cd ~/Desktop/nuzantara && git reset --hard "pre-orchestration-fix-\${BACKUP_ID}"
# Step 4: re-bootstrap daemon
launchctl bootstrap gui/\$(id -u) ~/Library/LaunchAgents/com.balizero.guardrails-daemon.plist
\`\`\`

## Secondary recipe (belt-and-suspenders)
If operator forgets Step 1 daemon-bootout, T1.2 guardrails whitelist matches
\`^pre-orchestration-fix-[0-9]{8}-[0-9]{6}$\` and allows the reset. Only safe
if daemon is HEALTHY; if WEDGED, rollback will hang — Ctrl-C and use primary recipe.

## See also
- G3-global-rollback.md (orchestrated rollback procedure)
- T1.2 (guardrails whitelist for pre-orchestration-fix-* tag pattern)
- 00-INDEX.md (full plan)
EOF
```

## Open questions

1. **Backup encryption**: tarball contiene `memory.db` con potenziali secret + cicatrix-scars con incident metadata. Vale la pena `gpg` encryption? Default = no, ~/backups/ è già 0700 dir presumibilmente.
2. **Remote backup**: tarball solo locale. Worth push a Tigris S3 / Drive? Default = no per ora, ~/backups/ è Mac Pro SSD reliable abbastanza.
3. **Auto-rotate**: future backup (e.g., monthly) overwrite questo? Default = manual cleanup dopo 3 mesi.
4. **`.codex/` / `.litellm/` etc**: altri tool config da includere? Audit step 1 verify.

## Estimated breakdown

| Step         | Tempo      |
| ------------ | ---------- |
| Create dir   | <1 min     |
| Manifest     | 2 min      |
| tar.gz       | 2 min      |
| Verify       | 2 min      |
| Git tag      | 1 min      |
| Memory entry | 2 min      |
| **Total**    | **10 min** |
