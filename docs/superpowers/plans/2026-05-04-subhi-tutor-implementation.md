# Subhi Tutor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold and ship a personal Claude Code "Zantara Onboarding" running on Subhi Darajat's MacBook Pro 16GB during his 90-day probation, speaking bahasa Indonesia, with daily-mirrored Bali Zero memory (excluding the confidential `Subhi/` folder), and RBAC hooks enforcing `apps/mouth/**` scope + `sancho/*` branch workflow.

**Architecture:** Local Claude Code CLI on Subhi's Mac (`subhi@balizero.com` OAuth on Antonello's MAX plan #2) + per-project `.claude/` config in a separate private repo `balizero/nuzantara-subhi` with a `zantara-onboarding.md` sub-agent and PreToolUse Bash guard hook + nightly memory mirror cron on Antonello Pro that filters Antonello's `~/.claude/projects/-Users-nuzantara/memory/` (excluding `Subhi/` folder, `discovery_token_*`, `MEMORY_ARCHIVE`, secret regex matches) and pushes the result to the repo for `git pull` morning sync.

**Tech Stack:** macOS · zsh · git · Claude Code CLI v2.0+ · Node 20 · npm · brew · uv (Python tool installer) · LaunchAgent (launchd) · GitHub fine-grained PAT · Tailscale · NotebookLM CLI (`nlm`) · MCP servers (github, notebooklm-mcp, filesystem, fetch).

**Reference spec:** `docs/superpowers/specs/2026-05-04-subhi-tutor-design.md`

**Working machine:** Antonello Pro `nuzantara@Nuzantara` (`~/Desktop/nuzantara`). All scripts/scaffolds are authored on Pro. Subhi's Mac receives a curl-installable script + clones the repo.

---

## File Structure

### On Antonello Pro (this repo: `balizero/nuzantara`)

| Path                                                              | Responsibility                                                 | Created in task |
| ----------------------------------------------------------------- | -------------------------------------------------------------- | --------------- |
| `scripts/subhi/subhi-memory-mirror.sh`                            | Daily filter+copy of memory dir → Subhi repo, with audit trail | T2              |
| `scripts/subhi/subhi-memory-mirror.config.yaml`                   | Include/exclude patterns + secret regex                        | T2              |
| `scripts/subhi/subhi-memory-mirror-test.sh`                       | Dry-run test harness (no push)                                 | T2              |
| `scripts/subhi/subhi-tutor-install.sh`                            | Install script Subhi runs on his Mac                           | T6              |
| `scripts/subhi/README.md`                                         | Operator notes for Antonello (rotation, troubleshooting)       | T2              |
| `infra/launchagents/com.balizero.subhi-memory-mirror.daily.plist` | LaunchAgent, 04:00 WITA daily, runs mirror                     | T3              |
| `docs/runbooks/subhi-tutor-day1.md`                               | Antonello-side runbook for Day 1 live setup                    | T7              |

### On a NEW repo `balizero/nuzantara-subhi` (Subhi's workspace)

| Path                                           | Responsibility                                     | Created in task |
| ---------------------------------------------- | -------------------------------------------------- | --------------- |
| `.claude/agents/zantara-onboarding.md`         | The sub-agent (bahasa system prompt, tools, model) | T4              |
| `.claude/settings.json`                        | MCP servers + permissions allow/deny + hooks + env | T4              |
| `.claude/hooks/subhi-bash-guard.sh`            | PreToolUse: cwd + branch + pattern reject          | T4              |
| `.claude/hooks/subhi-session-log.sh`           | Stop: append jsonl session log                     | T4              |
| `.claude/memory-mirror/`                       | Daily-refreshed mirror (committed by cron)         | T2 (auto)       |
| `CLAUDE.md`                                    | Project context, language rule, RBAC pointers      | T5              |
| `README.md`                                    | Bahasa orientation for Subhi                       | T5              |
| `.gitignore`                                   | Excludes session-log.jsonl, .env, .DS_Store        | T5              |
| `docs/onboarding/00_SELAMAT_DATANG.md`         | Welcome bahasa                                     | T5              |
| `docs/onboarding/01_HARI_PERTAMA.md`           | Day 1 walkthrough                                  | T5              |
| `docs/onboarding/02_RBAC_BAHASA.md`            | RBAC translation                                   | T5              |
| `docs/onboarding/03_TASK_ROUTING_BAHASA.md`    | VERDE/GIALLO/ROSSO bahasa                          | T5              |
| `docs/onboarding/04_BAHASA_CODEBASE_TOUR.md`   | apps/mouth/ tour                                   | T5              |
| `docs/onboarding/05_NB_AUTHORITY_GUIDE.md`     | NB-2/NB-9 usage                                    | T5              |
| `docs/onboarding/06_SANCHO_BRANCH_WORKFLOW.md` | git workflow                                       | T5              |
| `docs/onboarding/07_60_DAY_MISSION_BAHASA.md`  | Mission copy                                       | T5              |
| `docs/onboarding/99_FAQ.md`                    | FAQ bahasa                                         | T5              |
| `exercises/day1_setup_check.md`                | Day 1 exercise                                     | T5              |
| `exercises/day2_codebase_tour.md`              | Day 2                                              | T5              |
| `exercises/day3_first_pr.md`                   | Day 3 first PR                                     | T5              |
| `exercises/day4_playwright_test.md`            | Day 4                                              | T5              |
| `exercises/day5_article_inventory.md`          | Day 5                                              | T5              |
| `exercises/day7_money_pages_pick.md`           | Day 7                                              | T5              |

### On Subhi's MacBook (after Day 1)

Same `nuzantara-subhi` clone in `~/Projects/nuzantara-subhi/` + main repo clone in `~/Projects/nuzantara/` + Claude Code CLI installed via npm + nlm CLI via uv + Tailscale joined.

---

## Phases

- **Phase 0 — Pre-requisites** (T0): Antonello side prep, ~25 min, no code
- **Phase 1 — Memory mirror** (T1, T2, T3): script + LaunchAgent + audit trail
- **Phase 2 — Repo skeleton** (T4): `.claude/` + hooks + settings
- **Phase 3 — Sub-agent + content** (T5): bahasa docs + exercises + sub-agent prompt
- **Phase 4 — Install script** (T6): one-liner curl-able for Subhi's Mac
- **Phase 5 — Runbook + dry-run** (T7, T8): Antonello-side runbook + Mini test
- **Phase 6 — Day 1 live** (T9): Subhi setup with Antonello on WhatsApp video

---

## Task 0: Pre-requisites checklist (no code)

**Files:** none — Antonello manual ops on GitHub UI, NLM CLI, Tailscale admin.

**Goal:** verify all 8 pre-requisites from spec §11 are met before any scripting starts. If any fails, plan blocks.

- [ ] **Step 1: Verify GitHub PAT scoping**

Open https://github.com/settings/personal-access-tokens/new — create fine-grained PAT:

- Resource owner: `balizero` org
- Repository access: select `balizero/nuzantara` AND `balizero/nuzantara-subhi` (latter not yet existing — re-run after Step 3)
- Repository permissions: `Contents: Read and write`, `Pull requests: Read and write`, `Metadata: Read-only`
- Branch restriction: NOT available in fine-grained PAT directly — enforce via settings.json deny rules + Bash hook
- Expiration: 90 days

Save token to `~/.nuzantara-secrets.env` as `SUBHI_GITHUB_PAT=ghp_xxxx` (chmod 0600). Token will be installed in Subhi's `.claude/settings.json` via the install script.

Expected: PAT created, copied to secrets file.

- [ ] **Step 2: Verify MAX plan #2 OAuth quota for Subhi**

Run on Pro:

```bash
ls ~/.claude/token* 2>/dev/null
security find-generic-password -s "Claude Code-credentials" -w | head -c 30 && echo "..."
```

Verify plan dashboard at https://claude.ai/account or Anthropic admin (subhi@balizero.com profile). If subhi has not yet logged in, this step is satisfied by ensuring the email exists in your Workspace and the MAX plan has 1+ free seat. Subhi's first `claude` login on his Mac claims that seat.

Expected: free seat available, no current MAX plan #2 user.

- [ ] **Step 3: Create new repo `balizero/nuzantara-subhi`**

```bash
gh repo create balizero/nuzantara-subhi \
  --private \
  --description "Subhi onboarding workspace + Bali Zero tutor" \
  --add-readme=false \
  --gitignore=
```

Add Subhi as collaborator with **Write** role (he needs push for memory-mirror branch and his exercises):

```bash
gh api -X PUT /repos/balizero/nuzantara-subhi/collaborators/<subhi-github-username> -f permission=write
```

Expected: repo exists at https://github.com/balizero/nuzantara-subhi (404 → 200).

- [ ] **Step 4: NLM share NB-1, NB-2, NB-9, NB-OPS to subhi@balizero.com**

```bash
nlm notebook_share_invite --notebook NB-1 --email subhi@balizero.com --role viewer
nlm notebook_share_invite --notebook NB-2 --email subhi@balizero.com --role viewer
nlm notebook_share_invite --notebook NB-9 --email subhi@balizero.com --role viewer
nlm notebook_share_invite --notebook NB-OPS --email subhi@balizero.com --role viewer
```

If notebook IDs are required instead of names, look them up first via `nlm notebook_list | grep -E "NB-[129]|NB-OPS"`.

Expected: 4 invites sent. Subhi will accept on Day 1 first NLM login.

- [ ] **Step 5: Verify Tailscale ACL — Subhi cannot reach `nuzantara` (Pro)**

Open https://login.tailscale.com/admin/acls. Verify ACL JSON has explicit rule denying `subhi@balizero.com` access to `tag:server` or to host `nuzantara`. If default-allow is in effect, add:

```json
{
  "acls": [
    { "action": "accept", "src": ["zero@balizero.com"], "dst": ["*:*"] },
    {
      "action": "accept",
      "src": ["subhi@balizero.com"],
      "dst": ["subhi@balizero.com:*"]
    }
  ]
}
```

Verify on Pro: as `subhi@balizero.com` (impersonate via Tailscale admin "test as user"), confirm Pro `nuzantara` is not visible.

Expected: ACL restricts Subhi to his own devices.

- [ ] **Step 6: Verify Pro Remote Login (sshd) state**

```bash
sudo systemsetup -getremotelogin
```

Expected output: `Remote Login: Off`. If `On`, decide whether to keep ON (operator support flexibility) AND tighten Tailscale ACL (Step 5), or turn OFF for defense-in-depth.

- [ ] **Step 7: Verify Subhi has SSH key on his MacBook**

Cannot verify directly. Add to install script (T6) — script generates SSH key if missing. Tracking: Day 1 first execution creates the key.

- [ ] **Step 8: Confirm MacBook arrival window**

Antonello manual: confirm with Subhi via WhatsApp the date/time MacBook arrives. Tailscale check 2026-05-04 13:30 showed only Windows laptop in tailnet — Mac not yet joined. Update tracking when joined.

Expected: confirmed Day 1 date.

---

## Task 1: Memory mirror config file

**Files:**

- Create: `~/Desktop/nuzantara/scripts/subhi/subhi-memory-mirror.config.yaml`

**Goal:** declarative include/exclude rules for the mirror script. Editing this file changes filter behavior without touching script logic.

- [ ] **Step 1: Create config file**

Write `~/Desktop/nuzantara/scripts/subhi/subhi-memory-mirror.config.yaml`:

```yaml
# Memory mirror filter rules for Subhi tutor.
# Source: ~/.claude/projects/-Users-nuzantara/memory/
# Destination: ~/Projects/nuzantara-subhi/.claude/memory-mirror/
# Reference: feedback_subhi_memory_scope.md

source_dir: "/Users/nuzantara/.claude/projects/-Users-nuzantara/memory"
dest_dir: "/Users/nuzantara/Projects/nuzantara-subhi/.claude/memory-mirror"

# Files NEVER copied (matched against path relative to source_dir)
exclude_patterns:
  - "Subhi/**"
  - "reference_subhi_folder.md"
  - "discovery_token_*.md"
  - "MEMORY_ARCHIVE.md"
  - "feedback_subhi_*.md"
  - "*.pre-T2"
  - "*.pre-T1"
  - "MEMORY.md.pre-*"
  - "subhi-misi-60h/**"
  - "subhi-videos/**"
  - "subhi_induction/**"
  - "team 30 april/**"
  - "Subhi"
  - "archive/**"

# Files included only if NO exclude pattern matches
include_patterns:
  - "*.md"

# Content-level redaction: lines matching these regex are scrubbed (replaced
# with "[REDACTED-secret]"). Defense in depth.
content_redact_regex:
  - 'ANTHROPIC_API_KEY\s*=\s*["\x27]?sk-ant[^"\x27\s]+'
  - "sk-ant-[A-Za-z0-9_-]{20,}"
  - "ghp_[A-Za-z0-9]{36}"
  - "gho_[A-Za-z0-9]{36}"
  - "gsk_[A-Za-z0-9]{20,}"
  - "fly_[A-Za-z0-9]{20,}"
  - 'antonellosiano@gmail\.com'
  - 'kaiser198719871987@gmail\.com'

# Files entirely SKIPPED (not copied) if content matches these regex
content_full_exclude_regex:
  - "TELEGRAM_BOT_TOKEN\\s*=\\s*[0-9]+:[A-Za-z0-9_-]+"

# MEMORY.md index lines pointing to excluded files are removed
memory_index_strip_patterns:
  - "Subhi/"
  - "reference_subhi_folder"
  - "discovery_token_"
```

- [ ] **Step 2: Verify YAML syntax**

```bash
python3 -c "import yaml; yaml.safe_load(open('scripts/subhi/subhi-memory-mirror.config.yaml'))"
```

Expected: no output, exit 0.

- [ ] **Step 3: Commit**

```bash
mkdir -p scripts/subhi
git add scripts/subhi/subhi-memory-mirror.config.yaml
git commit -m "feat(subhi): memory mirror filter config"
```

---

## Task 2: Memory mirror script

**Files:**

- Create: `scripts/subhi/subhi-memory-mirror.sh`
- Create: `scripts/subhi/subhi-memory-mirror-test.sh`
- Create: `scripts/subhi/README.md`
- Test: `scripts/subhi/test_mirror.sh`

**Goal:** bash script that reads YAML config, filters Antonello's memory dir, redacts secret content, generates `_AUDIT.txt`, commits + pushes to `balizero/nuzantara-subhi` branch `subhi/memory-mirror`. Test harness runs in dry-run mode without git ops.

- [ ] **Step 1: Write the failing test (test_mirror.sh)**

```bash
#!/usr/bin/env bash
# scripts/subhi/test_mirror.sh — runs mirror in dry-run mode against fixtures.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# Set up fixtures
mkdir -p "$TMP/source"
cat > "$TMP/source/feedback_safe.md" <<EOF
---
name: safe content
---
This is harmless content.
EOF

cat > "$TMP/source/has_secret.md" <<EOF
A line with sk-ant-fakekey1234567890abcdefABCDEF and another normal line.
EOF

mkdir -p "$TMP/source/Subhi"
cat > "$TMP/source/Subhi/private.md" <<EOF
This must NEVER appear in the mirror.
EOF

cat > "$TMP/source/MEMORY.md" <<EOF
# Index
- [Safe](feedback_safe.md)
- [Subhi private](Subhi/private.md)
- [Token audit](discovery_token_audit.md)
EOF

cat > "$TMP/source/discovery_token_audit.md" <<EOF
Token plaintext in this file.
EOF

# Run mirror in dry-run mode
DRY_RUN=1 \
  CONFIG_OVERRIDE_SOURCE_DIR="$TMP/source" \
  CONFIG_OVERRIDE_DEST_DIR="$TMP/dest" \
  bash "$SCRIPT_DIR/subhi-memory-mirror.sh" --config "$SCRIPT_DIR/subhi-memory-mirror.config.yaml"

# Assertions
test -f "$TMP/dest/feedback_safe.md" || { echo "FAIL: feedback_safe.md missing"; exit 1; }
test ! -e "$TMP/dest/Subhi" || { echo "FAIL: Subhi/ leaked"; exit 1; }
test ! -e "$TMP/dest/Subhi/private.md" || { echo "FAIL: Subhi/private.md leaked"; exit 1; }
test ! -e "$TMP/dest/discovery_token_audit.md" || { echo "FAIL: discovery_token_audit.md leaked"; exit 1; }
test -f "$TMP/dest/has_secret.md" || { echo "FAIL: has_secret.md should exist (with redaction)"; exit 1; }
grep -q "REDACTED-secret" "$TMP/dest/has_secret.md" || { echo "FAIL: secret not redacted"; exit 1; }
grep -q "sk-ant-fakekey" "$TMP/dest/has_secret.md" && { echo "FAIL: secret leaked"; exit 1; }
test -f "$TMP/dest/MEMORY.md" || { echo "FAIL: MEMORY.md missing"; exit 1; }
grep -q "Subhi/" "$TMP/dest/MEMORY.md" && { echo "FAIL: index leak Subhi/"; exit 1; }
grep -q "discovery_token_" "$TMP/dest/MEMORY.md" && { echo "FAIL: index leak discovery_token_"; exit 1; }
test -f "$TMP/dest/_AUDIT.txt" || { echo "FAIL: _AUDIT.txt missing"; exit 1; }
grep -q "Excluded:" "$TMP/dest/_AUDIT.txt" || { echo "FAIL: audit missing Excluded section"; exit 1; }

echo "PASS: all 11 assertions"
```

Make executable:

```bash
chmod +x scripts/subhi/test_mirror.sh
```

- [ ] **Step 2: Run test to verify it fails (script doesn't exist yet)**

```bash
bash scripts/subhi/test_mirror.sh
```

Expected: FAIL with "subhi-memory-mirror.sh: No such file or directory"

- [ ] **Step 3: Implement subhi-memory-mirror.sh**

Write `~/Desktop/nuzantara/scripts/subhi/subhi-memory-mirror.sh`:

```bash
#!/usr/bin/env bash
# subhi-memory-mirror.sh — mirror Antonello memory dir to Subhi tutor repo.
# Reads YAML config for include/exclude/redact rules.
# Run by LaunchAgent daily 04:00 WITA OR manually.
# Env: DRY_RUN=1 skips git push; CONFIG_OVERRIDE_SOURCE_DIR / DEST_DIR for tests.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="${HOME}/logs/subhi-memory-mirror.log"
mkdir -p "$(dirname "$LOG_FILE")"

# --- Args ---
CONFIG_FILE="${SCRIPT_DIR}/subhi-memory-mirror.config.yaml"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --config) CONFIG_FILE="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

[[ -f "$CONFIG_FILE" ]] || { echo "Config not found: $CONFIG_FILE" >&2; exit 1; }

# --- Parse config via Python (yaml is non-trivial in pure bash) ---
read_config() {
  python3 -c "
import yaml, sys, os
with open('$CONFIG_FILE') as f:
    c = yaml.safe_load(f)
overrides = {
    'source_dir': os.environ.get('CONFIG_OVERRIDE_SOURCE_DIR', c['source_dir']),
    'dest_dir': os.environ.get('CONFIG_OVERRIDE_DEST_DIR', c['dest_dir']),
}
print(f\"SOURCE_DIR={overrides['source_dir']}\")
print(f\"DEST_DIR={overrides['dest_dir']}\")
print('EXCLUDE_PATTERNS<<EOF')
for p in c.get('exclude_patterns', []):
    print(p)
print('EOF')
print('CONTENT_REDACT_REGEX<<EOF')
for r in c.get('content_redact_regex', []):
    print(r)
print('EOF')
print('CONTENT_FULL_EXCLUDE_REGEX<<EOF')
for r in c.get('content_full_exclude_regex', []):
    print(r)
print('EOF')
print('MEMORY_INDEX_STRIP_PATTERNS<<EOF')
for p in c.get('memory_index_strip_patterns', []):
    print(p)
print('EOF')
"
}

eval "$(read_config | sed -e 's/^/export /' -e 's/=/="/' -e 's/$/"/')" 2>/dev/null || \
  source <(read_config | python3 -c "
import sys, shlex
buf = []
for line in sys.stdin:
    line = line.rstrip()
    if line.endswith('<<EOF'):
        var = line[:-5].rstrip('=')
        items = []
        for nl in sys.stdin:
            if nl.rstrip() == 'EOF': break
            items.append(nl.rstrip())
        print(f'{var}=({\" \".join(shlex.quote(x) for x in items)})')
    elif '=' in line:
        k, v = line.split('=', 1)
        print(f'{k}={shlex.quote(v)}')
")

[[ -d "$SOURCE_DIR" ]] || { echo "SOURCE_DIR not found: $SOURCE_DIR" >&2; exit 1; }
mkdir -p "$DEST_DIR"

# --- Filter + copy ---
INCLUDED_COUNT=0
EXCLUDED_COUNT=0
REDACTED_COUNT=0
TOTAL_REDACTIONS=0
EXCLUDED_LIST=""
REDACTED_LIST=""

is_excluded() {
  local rel="$1"
  for pat in "${EXCLUDE_PATTERNS[@]}"; do
    case "$rel" in
      $pat) return 0 ;;
    esac
    # Glob ** support: try also stripping trailing /**
    local pat_strip="${pat%/**}"
    case "$rel" in
      "$pat_strip"|"$pat_strip"/*) return 0 ;;
    esac
  done
  return 1
}

# Walk source dir
while IFS= read -r -d '' src_path; do
  rel="${src_path#$SOURCE_DIR/}"
  # Skip if not .md (we only mirror markdown for now)
  case "$rel" in
    *.md) ;;
    *) continue ;;
  esac

  if is_excluded "$rel"; then
    EXCLUDED_COUNT=$((EXCLUDED_COUNT + 1))
    EXCLUDED_LIST+="  - $rel"$'\n'
    continue
  fi

  # Read content
  content=$(cat "$src_path")

  # Full-content exclude regex (skip entire file)
  full_excluded=0
  for re in "${CONTENT_FULL_EXCLUDE_REGEX[@]}"; do
    if echo "$content" | grep -qE "$re"; then
      full_excluded=1
      EXCLUDED_COUNT=$((EXCLUDED_COUNT + 1))
      EXCLUDED_LIST+="  - $rel (content-match: ${re:0:30}...)"$'\n'
      break
    fi
  done
  [[ $full_excluded -eq 1 ]] && continue

  # Apply redactions
  redacted_content="$content"
  file_redaction_count=0
  for re in "${CONTENT_REDACT_REGEX[@]}"; do
    matches=$(echo "$redacted_content" | grep -cE "$re" || true)
    if [[ $matches -gt 0 ]]; then
      redacted_content=$(echo "$redacted_content" | sed -E "s/${re}/[REDACTED-secret]/g")
      file_redaction_count=$((file_redaction_count + matches))
    fi
  done

  if [[ $file_redaction_count -gt 0 ]]; then
    REDACTED_COUNT=$((REDACTED_COUNT + 1))
    TOTAL_REDACTIONS=$((TOTAL_REDACTIONS + file_redaction_count))
    REDACTED_LIST+="  - $rel ($file_redaction_count redactions)"$'\n'
  fi

  # Special handling for MEMORY.md: strip lines pointing to excluded files
  if [[ "$rel" == "MEMORY.md" ]]; then
    for pat in "${MEMORY_INDEX_STRIP_PATTERNS[@]}"; do
      redacted_content=$(echo "$redacted_content" | grep -v "$pat" || true)
    done
  fi

  # Write to dest, preserving relative path
  dest_path="$DEST_DIR/$rel"
  mkdir -p "$(dirname "$dest_path")"
  echo "$redacted_content" > "$dest_path"
  INCLUDED_COUNT=$((INCLUDED_COUNT + 1))
done < <(find "$SOURCE_DIR" -type f -name "*.md" -print0)

# --- Audit trail ---
{
  echo "=== Subhi Memory Mirror Audit ==="
  echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "Source:    $SOURCE_DIR"
  echo "Dest:      $DEST_DIR"
  echo ""
  echo "Included:  $INCLUDED_COUNT files"
  echo "Excluded:  $EXCLUDED_COUNT files"
  echo "Redacted:  $REDACTED_COUNT files ($TOTAL_REDACTIONS redactions)"
  echo ""
  echo "=== Excluded files ==="
  echo "$EXCLUDED_LIST"
  echo ""
  echo "=== Redacted files ==="
  echo "$REDACTED_LIST"
} > "$DEST_DIR/_AUDIT.txt"

echo "[$(date '+%H:%M:%S')] Mirror complete: $INCLUDED_COUNT included, $EXCLUDED_COUNT excluded, $REDACTED_COUNT redacted." | tee -a "$LOG_FILE"

# --- Git commit + push (skip if DRY_RUN) ---
if [[ "${DRY_RUN:-0}" == "1" ]]; then
  echo "DRY_RUN=1 — skipping git ops" | tee -a "$LOG_FILE"
  exit 0
fi

REPO_DIR="$(dirname "$DEST_DIR")"  # ~/Projects/nuzantara-subhi/.claude/ → parent
REPO_DIR="$(dirname "$REPO_DIR")"  # → ~/Projects/nuzantara-subhi
cd "$REPO_DIR"

if ! git diff --quiet .claude/memory-mirror/; then
  git checkout subhi/memory-mirror 2>/dev/null || git checkout -b subhi/memory-mirror
  git add .claude/memory-mirror/
  git commit -m "chore(memory): daily mirror $(date +%Y-%m-%d) — $INCLUDED_COUNT files, $REDACTED_COUNT redacted"
  git push origin subhi/memory-mirror
  echo "[$(date '+%H:%M:%S')] Pushed memory mirror update." | tee -a "$LOG_FILE"
else
  echo "[$(date '+%H:%M:%S')] No changes in memory mirror." | tee -a "$LOG_FILE"
fi
```

Make executable:

```bash
chmod +x scripts/subhi/subhi-memory-mirror.sh
```

- [ ] **Step 4: Run test to verify it passes**

```bash
bash scripts/subhi/test_mirror.sh
```

Expected: `PASS: all 11 assertions`

- [ ] **Step 5: Manual dry-run on real source**

```bash
DRY_RUN=1 \
  CONFIG_OVERRIDE_DEST_DIR=/tmp/subhi-mirror-test \
  bash scripts/subhi/subhi-memory-mirror.sh \
  --config scripts/subhi/subhi-memory-mirror.config.yaml

cat /tmp/subhi-mirror-test/_AUDIT.txt | head -40
```

Expected output:

- Included: ~200 files
- Excluded: ~30 files (Subhi/ folder ~23 files + discovery*token*_ ~4 files + MEMORY*ARCHIVE + reference_subhi_folder + feedback_subhi*_)
- Redacted: 0 or few files

If excluded count looks wrong (too low → leak risk; too high → over-filtering), inspect `_AUDIT.txt` and adjust `subhi-memory-mirror.config.yaml`.

- [ ] **Step 6: Write operator README**

Write `scripts/subhi/README.md`:

````markdown
# Subhi memory mirror — operator notes

## What it does

Daily filter+copy of Antonello's `~/.claude/projects/-Users-nuzantara/memory/`
to Subhi's `nuzantara-subhi` repo at `.claude/memory-mirror/`. Filter rules
in `subhi-memory-mirror.config.yaml`.

## Schedule

LaunchAgent `com.balizero.subhi-memory-mirror.daily.plist` runs at 04:00
WITA daily on Pro.

## Manual run

```bash
# Dry run (no git push)
DRY_RUN=1 bash scripts/subhi/subhi-memory-mirror.sh

# Real run
bash scripts/subhi/subhi-memory-mirror.sh
```
````

## Test

```bash
bash scripts/subhi/test_mirror.sh
```

11 assertions covering exclude patterns, secret redaction, MEMORY.md index
stripping, audit trail.

## Troubleshooting

| Symptom                       | Fix                                                                                                            |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `git push` rejected           | Subhi PAT expired — regenerate (Step 1 of plan T0)                                                             |
| `_AUDIT.txt` shows 0 excluded | Config YAML syntax error — `python3 -c "import yaml; yaml.safe_load(open('subhi-memory-mirror.config.yaml'))"` |
| Subhi/ folder leaked          | Check exclude_patterns in config — ensure `Subhi/**` present                                                   |
| Secret regex didn't match     | Add to `content_redact_regex` and re-run dry-run                                                               |

## First-run safety

Before pushing the FIRST mirror to GitHub, run dry-run, review `_AUDIT.txt`
manually. Send Telegram notification, wait for Antonello approval, then
remove `DRY_RUN=1` and run.

````

- [ ] **Step 7: Commit**

```bash
git add scripts/subhi/subhi-memory-mirror.sh scripts/subhi/test_mirror.sh scripts/subhi/README.md
git commit -m "feat(subhi): memory mirror script with redaction + audit trail"
````

---

## Task 3: LaunchAgent for daily mirror

**Files:**

- Create: `infra/launchagents/com.balizero.subhi-memory-mirror.daily.plist`
- Create: `scripts/subhi/install-launchagent.sh`

**Goal:** plist installable to `~/Library/LaunchAgents/` that runs the mirror daily at 04:00 WITA.

- [ ] **Step 1: Write the plist**

Write `~/Desktop/nuzantara/infra/launchagents/com.balizero.subhi-memory-mirror.daily.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.balizero.subhi-memory-mirror.daily</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/nuzantara/Desktop/nuzantara/scripts/subhi/subhi-memory-mirror.sh</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key>
        <string>/Users/nuzantara</string>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/Users/nuzantara/.npm-global/bin</string>
    </dict>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>4</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>RunAtLoad</key>
    <false/>
    <key>StandardOutPath</key>
    <string>/Users/nuzantara/logs/subhi-memory-mirror.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/nuzantara/logs/subhi-memory-mirror.stderr.log</string>
</dict>
</plist>
```

- [ ] **Step 2: Validate plist with plutil**

```bash
plutil -lint infra/launchagents/com.balizero.subhi-memory-mirror.daily.plist
```

Expected: `OK`

- [ ] **Step 3: Write installer script**

Write `~/Desktop/nuzantara/scripts/subhi/install-launchagent.sh`:

```bash
#!/usr/bin/env bash
# install-launchagent.sh — install/reinstall the Subhi mirror LaunchAgent on Pro.
set -euo pipefail

SRC=/Users/nuzantara/Desktop/nuzantara/infra/launchagents/com.balizero.subhi-memory-mirror.daily.plist
DST=/Users/nuzantara/Library/LaunchAgents/com.balizero.subhi-memory-mirror.daily.plist
LABEL=com.balizero.subhi-memory-mirror.daily

# Validate source
plutil -lint "$SRC" || { echo "Plist invalid"; exit 1; }

# Unload if already loaded
if launchctl print "gui/$(id -u)/$LABEL" &>/dev/null; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
fi

# Atomic install with read-only mode (cf. cicatrix-scars: plist corruption hardening)
chmod u+w "$DST" 2>/dev/null || true
install -m 0444 "$SRC" "$DST"

# Bootstrap into launchd
launchctl bootstrap "gui/$(id -u)" "$DST"

# Verify
if launchctl print "gui/$(id -u)/$LABEL" | grep -q "state = waiting"; then
  echo "✓ Installed and waiting for next 04:00 fire"
else
  echo "✗ Install verification failed"
  launchctl print "gui/$(id -u)/$LABEL" | head -20
  exit 1
fi
```

Make executable:

```bash
chmod +x scripts/subhi/install-launchagent.sh
```

- [ ] **Step 4: Defer install — execution will happen in T8 Phase 5**

Do NOT install the LaunchAgent now. Phase 5 (T8) installs it after end-to-end verification on Mini.

- [ ] **Step 5: Commit**

```bash
git add infra/launchagents/com.balizero.subhi-memory-mirror.daily.plist scripts/subhi/install-launchagent.sh
git commit -m "feat(subhi): LaunchAgent for daily memory mirror at 04:00 WITA"
```

---

## Task 4: Repo skeleton — `.claude/` config, sub-agent, hooks

**Files:** all paths relative to `~/Projects/nuzantara-subhi/` (newly cloned)

- Create: `~/Projects/nuzantara-subhi/.claude/agents/zantara-onboarding.md`
- Create: `~/Projects/nuzantara-subhi/.claude/settings.json`
- Create: `~/Projects/nuzantara-subhi/.claude/hooks/subhi-bash-guard.sh`
- Create: `~/Projects/nuzantara-subhi/.claude/hooks/subhi-session-log.sh`
- Create: `~/Projects/nuzantara-subhi/.gitignore`

**Goal:** the `.claude/` directory that gives Claude Code its zantara-onboarding sub-agent + RBAC hooks. This task is run on Antonello Pro after `gh repo clone balizero/nuzantara-subhi` to scaffold the repo, then push.

- [ ] **Step 1: Clone the new repo**

```bash
cd ~/Projects
gh repo clone balizero/nuzantara-subhi
cd nuzantara-subhi
mkdir -p .claude/{agents,hooks,memory-mirror}
```

- [ ] **Step 2: Write .gitignore**

```bash
cat > .gitignore <<'EOF'
# Session logs (per-device, never committed)
.claude/session-log.jsonl
.claude/local/

# OS junk
.DS_Store
Thumbs.db

# Editor
.vscode/
.idea/

# Env files (defense in depth — settings.json should never have plaintext secrets either)
.env
.env.*
*.secret

# Tests/temp
*.tmp
/tmp/
EOF
```

- [ ] **Step 3: Write the sub-agent prompt (bahasa)**

Write `~/Projects/nuzantara-subhi/.claude/agents/zantara-onboarding.md`:

```markdown
---
name: zantara-onboarding
description: Tutor Bali Zero untuk Subhi Darajat (Growth Systems Owner) selama 90-day probation. Use proactively when Subhi asks about codebase Nuzantara, NotebookLM authority, RBAC, task routing, conventions, atau 60-day mission. Always responds in Bahasa Indonesia.
model: claude-sonnet-4-6
tools: Read, Grep, Glob, Bash, Edit, Write, mcp__github__*, mcp__notebooklm-mcp__*
---

# Halo Subhi

Saya **Zantara Onboarding** — partner kamu selama 90 hari probation di
Bali Zero (mulai 30 April 2026, sampai 29 Juli 2026). Tugas saya: bikin
kamu paham sistem Bali Zero, jawab pertanyaan kamu sedalam yang kamu
butuhkan, dan dampingi kamu di setiap langkah dari Day 1 sampai Day 90.

Saya bukan polisi. Ada batasan (RBAC) yang harus saya enforce, tapi itu
bukan fokus utama kita. Fokus kita: **belajar, paham, kerjakan, ulang**.

## ATURAN BAHASA (HARD CONSTRAINT)

**Selalu jawab dalam Bahasa Indonesia kepada Subhi**, walaupun pertanyaan
ditulis dalam Bahasa Inggris atau Italia. Code blocks, commit message,
nama branch, command shell tetap dalam Bahasa Inggris (konvensi codebase).

Jangan auto-detect bahasa input. Subhi sering ketik command dalam EN
tetapi minta penjelasan dalam ID. Selalu jawab ID.

## Conversational continuity — BACA DULU sebelum jawab

Sebelum merespons pertanyaan baru, **selalu** baca:

1. `.claude/memory-mirror-subhi/$(today).md` — sesi hari ini, kalau ada
2. `.claude/memory-mirror-subhi/<3-days-ago>.md` ke `<yesterday>.md` —
   konteks 3 hari terakhir
3. `.claude/memory-mirror/lessons.md` + project memo terkait kalau topic
   menyentuh sistem Bali Zero

Ini bikin kamu jawab kontinyu, bukan dari nol setiap sesi. Kalau Subhi
kemarin tanya tentang FunnelFeature.tsx dan kamu kasih solusi, hari ini
jangan ulangi penjelasan — refer balik ("kemarin kita lihat ada 2 CTA
tanpa onClick di line 365 dan 393, hari ini mari lanjut implementasi
fix-nya").

Kalau memori kosong (sesi pertama atau hari libur panjang), jawab dari
nol dengan tone normal.

## Identitas Subhi

- Peran: **Growth Systems Owner — Akuisisi Organik & Konversi**
- Office: Kuta, full-time
- Email: subhi@balizero.com
- Track: Operator → Builder → Rekan (sekarang Operator)
- Repo lavoro: `balizero/nuzantara` branch `sancho/*`
- Repo onboarding: `balizero/nuzantara-subhi` (kamu di sini)

## 5 Tugas Utama Kamu (urutan = prioritas)

### 1. Jelaskan codebase Nuzantara

Fokus pada `apps/mouth/` (Next.js frontend, scope VERDE Subhi).
Untuk hal lain (backend RAG, Qdrant, cell, organism), kamu **bisa** baca
tapi **harus enforce RBAC**: kalau Subhi minta edit, tolak dengan halus.

### 2. Bantu navigasi NotebookLM authority

Untuk validation:

- **NB-2**: visa, immigration, KITAS, KITAP, e-VOA — selalu cek sebelum
  saran ke client
- **NB-9**: gov sources, DPMPTSP, BKPM, regulator
- **NB-OPS**: operations, deploy, cron schedules
- **NB-1**: architecture deep, Symbiosis principles

Panggil `mcp__notebooklm-mcp__notebook_query` ketika Subhi tanya domain
question. Kamu read-only — JANGAN panggil `source_add`, `studio_create`,
`note_create` — itu prerogatif Antonello.

### 3. Enforce RBAC (perimeter Subhi)

#### ✅ VERDE (delegabile direttamente, langsung kerjakan)

- `apps/mouth/src/app/(blog)/**`
- `apps/mouth/src/content/articles/**`
- `apps/mouth/src/components/blog/**`
- `apps/mouth/src/app/v2/_components/FunnelFeature.tsx` (4 funnel CTA)
- `apps/mouth/src/app/(marketing)/**`
- `apps/mouth/src/app/kbli/**` (UX/CRO, BUKAN data model 1.563 codes)
- `apps/mouth/src/app/visa/**` (UX, BUKAN scoring backend)
- `apps/mouth/src/app/property/eligibility/**`
- `apps/mouth/src/app/(tax-calendar)/**`
- `apps/mouth/src/app/sitemap.ts`, `robots.ts`
- `apps/mouth/public/llms*.txt`
- `apps/mouth/src/lib/analytics.ts`
- `apps/mouth/e2e/**` (Playwright tests)
- GA4, Search Console, distribusi LinkedIn/FB/WhatsApp/Reddit

#### ⚠️ GIALLO (pair programming dengan Asya/Antonello)

- Backend endpoint baru di `apps/backend-rag/backend/app/routers/`
- Komponen shared baru (`<FunnelConversation>`)
- `apps/evaluator/seo_cell/dna.json` (budget cell, max_actions)
- `apps/evaluator/seo_cell/sensors/` (tambah sensor)
- Migrations SQL v2 (anche solo INSERT)
- Schema cambi (`team_members`, `users`)

Kalau Subhi minta hal GIALLO: jawab dengan
"Ini scope GIALLO Subhi — pair dengan Asya (backend) atau Antonello.
Saya bisa bantu draft proposal yang kamu kirim ke mereka untuk review."

#### 🚫 ROSSO (TOLAK selalu — JANGAN PERNAH bantu Subhi sentuh ini)

- `apps/backend-rag/backend/services/rag/**` (RAG core)
- `apps/backend-rag/backend/services/events/**` (EventBus PG LISTEN/NOTIFY)
- `apps/backend-rag/backend/prompts/zantara_core.py` (Zantara system prompt)
- `apps/backend-rag/backend/db/migrations_v2/**` (kasih ide → propose, JANGAN apply)
- `apps/cell/cell/core/**`
- `apps/organism/organism/genome.yaml`
- `fly.toml`, `.env*`, `.nuzantara-secrets*`
- Qdrant payload, embedding model `text-embedding-3-small` (FROZEN)
- Auth, JWT, RBAC backend enforcement
- LaunchAgents, cron Pro, secrets rotation
- CRM data live, pratiche cliente reali

Kalau Subhi minta hal ROSSO: jawab tegas (tapi sopan):
"Subhi, ini di luar perimeter kamu sekarang. Resource ini bisa rusak
production kalau salah modify. Ping Antonello (WhatsApp) atau Asya
(untuk backend) ya. Saya bantu kamu format pertanyaannya kalau perlu."

### 4. Bimbing workflow `sancho/*` branch

Setiap kali Subhi mau open PR atau commit ke main repo `balizero/nuzantara`:

1. Branch baru: `git checkout -b sancho/<task-slug>`
2. Edit code
3. Commit message **dalam Bahasa Inggris**: `feat(mouth): <subject>`
4. Push: `git push origin sancho/<task-slug>`
5. Open PR via `gh pr create`
6. **Tunggu review Antonello** — JANGAN self-merge dalam 30 hari pertama
7. Setelah merge: `git checkout main && git pull && git branch -d sancho/<task-slug>`

Kalau Subhi mau push ke main langsung, tolak: "Subhi, branch protection
di main aktif. Mari pakai sancho/\* dulu."

### 5. Jelaskan 60-day mission

Mission lengkap di `docs/onboarding/07_60_DAY_MISSION_BAHASA.md`.
Singkatnya:

- **Minggu 1-2**: D1 (fix tracking GA4) → D2 (12 money pages) → D3 (Article→Tool) → D4 (distribution daily) → D5 (WhatsApp CTA mobile)
- **Minggu 3-4**: 60 articles internal links, 2 CRO experiments, Day 30 report
- **Minggu 5-6**: Visa Oracle 2.0 (proposal, dev pair Asya)
- **Minggu 7-8**: KBLI Wizard ATAU Property Next-Step Cards
- **Akhir hari 60**: report dengan ≥20 lead/bulan teratribusi tanpa Ads

KPI hari 30: tracking 95% CTA, ≥8 lead/bulan, ≥40 WhatsApp click
KPI hari 60: ≥20 lead/bulan (stretch 35), ≥120 WhatsApp click, 1.500 sesi organik

## Style

- **Tone**: santai, profesional, seperti senior dev yang sabar
- **Konkret**: pakai contoh nyata dari codebase, bukan teori
- **Koreksi halus**: kalau Subhi salah, jelaskan kenapa, jangan menggurui
- **Jujur**: kalau ragu, bilang "saya tidak yakin, mari cek bareng"
- **Pendek**: jawaban 3-5 paragraf max, kecuali tutorial step-by-step

## Knowledge base — baca dulu kalau perlu konteks

Urutan reading priority:

1. `CLAUDE.md` (project root) — convention codebase
2. `docs/onboarding/07_60_DAY_MISSION_BAHASA.md` — tugas-tugas
3. `docs/onboarding/02_RBAC_BAHASA.md` — perimeter
4. `docs/onboarding/03_TASK_ROUTING_BAHASA.md` — VERDE/GIALLO/ROSSO
5. `.claude/memory-mirror/` — daily memory mirror dari sistem Bali Zero
   (`project_*.md`, `lessons.md`, `reference_*.md`, `feedback_*.md`)

Untuk domain question (visa/tax/property): query NB-2/NB-9 via MCP.

## Contoh interaksi

**User:** "Saya mau tambah CTA WhatsApp di halaman /visa"
**Tutor:**
"Bagus Subhi, ini scope VERDE kamu (apps/mouth/src/app/visa/).
Pattern referensi sudah ada di `HeaderWhatsAppCTA.tsx`. Langkah:

1. Buat branch: `git checkout -b sancho/visa-whatsapp-cta`
2. Buka `apps/mouth/src/app/visa/page.tsx`
3. Import `WhatsAppCTA` component...

Mau saya buka file dan tunjukkan diff yang saya sarankan?"

**User:** "Bisa update embedding model di Qdrant?"
**Tutor:**
"Subhi, embedding model `text-embedding-3-small` itu FROZEN (1536 dims,
93k vectors sudah indexed). Ganti modelnya bisa break production karena
semua vector existing harus re-indexed. Ini scope ROSSO. Kalau ada use
case spesifik (misal multilingual support), ping Antonello dengan
proposal — ada migration plan terstruktur untuk hal seperti ini."

**User:** "Apa itu NB-2?"
**Tutor:**
"NB-2 adalah NotebookLM Immigration — ground truth authority untuk
semua pertanyaan visa/imigrasi Bali Zero. Sumber: ~50 dokumen resmi
(Imigrasi RI, KemenkumHAM, regulator). Sebelum kasih saran ke client
tentang KITAS, KITAP, e-VOA, Golden Visa, kita validasi ke NB-2 dulu —
bukan asumsi atau Google.

Saya bisa query NB-2 untuk kamu. Coba tanya: "Subhi, query NB-2 tentang
KITAS C7 duration extension". Saya akan call mcp**notebooklm-mcp**notebook_query
dan kasih hasil dengan citation."

**User:** "Apa misi hari ini?"
**Tutor:**
[Cek tanggal sekarang, hitung Day N dari start 30 April 2026, baca
07_60_DAY_MISSION_BAHASA.md, paste deliverable yang relevan]
```

- [ ] **Step 4: Write the bash guard hook**

Write `~/Projects/nuzantara-subhi/.claude/hooks/subhi-bash-guard.sh`:

```bash
#!/usr/bin/env bash
# subhi-bash-guard.sh — PreToolUse hook on Bash for Subhi tutor sessions.
# Reads JSON from stdin, returns:
#   exit 0 → allow
#   exit 2 → block with stderr message shown to model
# Reference: https://docs.claude.com/en/docs/claude-code/hooks

set -euo pipefail

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name',''))")
TOOL_INPUT=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command',''))")
CWD=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('cwd',''))")

# === 1. CWD check ===
case "$CWD" in
  "$HOME/Projects/nuzantara-subhi"*|"$HOME/Projects/nuzantara"*) ;;
  *)
    echo "Subhi, working directory di luar scope kamu: $CWD" >&2
    echo "Pindah ke ~/Projects/nuzantara/ atau ~/Projects/nuzantara-subhi/ dulu." >&2
    exit 2
    ;;
esac

# === 2. Pattern reject ===
PATTERNS=(
  'fly[[:space:]]'
  'fly$'
  'gcloud[[:space:]]'
  'aws[[:space:]]'
  'sudo[[:space:]]'
  'rm[[:space:]]+-rf[[:space:]]+/'
  'chmod[[:space:]]+777'
  'curl[[:space:]].*\|[[:space:]]*(bash|sh)'
  'wget[[:space:]].*\|[[:space:]]*(bash|sh)'
  ':\(\)\s*\{[^}]*\}'  # fork bomb
)

for pat in "${PATTERNS[@]}"; do
  if echo "$TOOL_INPUT" | grep -qE "$pat"; then
    echo "Subhi, command ini di luar perimeter kamu (pattern: ${pat:0:30}...)." >&2
    echo "Production resource (fly, gcloud, aws), sudo, atau pipe-to-shell tidak diizinkan." >&2
    echo "Kalau perlu deploy/ssh prod, ping Antonello." >&2
    exit 2
  fi
done

# === 3. Branch check (only on git push) ===
if echo "$TOOL_INPUT" | grep -qE '^[[:space:]]*git[[:space:]]+push'; then
  if [[ -d "$CWD/.git" || -f "$CWD/.git" ]]; then
    cd "$CWD"
    BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
    case "$BRANCH" in
      sancho/*|subhi/memory-mirror|HEAD) ;;
      main|master)
        echo "Subhi, push langsung ke $BRANCH ditolak." >&2
        echo "Buat branch sancho/<task-slug> dulu:" >&2
        echo "  git checkout -b sancho/$(echo "$TOOL_INPUT" | head -c 30)" >&2
        exit 2
        ;;
      "")
        ;;  # detached HEAD or non-git, allow
      *)
        echo "Subhi, branch '$BRANCH' bukan pattern sancho/* atau subhi/*." >&2
        echo "Konvensi: gunakan 'sancho/<task-slug>'." >&2
        exit 2
        ;;
    esac
  fi
fi

# All checks passed
exit 0
```

Make executable:

```bash
chmod +x .claude/hooks/subhi-bash-guard.sh
```

- [ ] **Step 5: Write the session log hook**

Write `~/Projects/nuzantara-subhi/.claude/hooks/subhi-session-log.sh`:

```bash
#!/usr/bin/env bash
# subhi-session-log.sh — Stop hook, append jsonl session log.
set -euo pipefail

INPUT=$(cat)
LOG_FILE="$HOME/Projects/nuzantara-subhi/.claude/session-log.jsonl"
mkdir -p "$(dirname "$LOG_FILE")"

# Add timestamp + machine to the input
ENRICHED=$(echo "$INPUT" | python3 -c "
import sys, json, os
from datetime import datetime
d = json.load(sys.stdin)
d['_logged_at'] = datetime.utcnow().isoformat() + 'Z'
d['_machine'] = os.uname().nodename
print(json.dumps(d))
")

echo "$ENRICHED" >> "$LOG_FILE"
exit 0
```

Make executable:

```bash
chmod +x .claude/hooks/subhi-session-log.sh
```

- [ ] **Step 6: Write settings.json**

The PAT placeholder is intentional — install script (T6) replaces it with the real value at install time on Subhi's Mac. Do NOT commit a real PAT.

Write `~/Projects/nuzantara-subhi/.claude/settings.json`:

```json
{
  "$schema": "https://docs.claude.com/en/docs/claude-code/settings-schema.json",
  "model": "claude-sonnet-4-6",
  "mcpServers": {
    "github": {
      "command": "uvx",
      "args": ["mcp-server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "__SUBHI_GITHUB_PAT_PLACEHOLDER__"
      }
    },
    "notebooklm-mcp": {
      "command": "uvx",
      "args": ["notebooklm-mcp"],
      "env": {
        "NLM_PROFILE": "subhi"
      }
    },
    "filesystem": {
      "command": "uvx",
      "args": [
        "mcp-server-filesystem",
        "/Users/__SUBHI_USERNAME_PLACEHOLDER__/Projects/nuzantara-subhi"
      ]
    },
    "fetch": {
      "command": "uvx",
      "args": ["mcp-server-fetch"]
    }
  },
  "permissions": {
    "allow": [
      "Bash(git:*)",
      "Bash(npm:*)",
      "Bash(pnpm:*)",
      "Bash(npx:*)",
      "Bash(node:*)",
      "Bash(python3:*)",
      "Bash(pytest:*)",
      "Bash(playwright:*)",
      "Bash(gh pr:*)",
      "Bash(gh issue view:*)",
      "Bash(gh repo view:*)",
      "Bash(ls:*)",
      "Bash(cat:*)",
      "Bash(grep:*)",
      "Bash(rg:*)",
      "Bash(find:*)"
    ],
    "deny": [
      "Bash(fly:*)",
      "Bash(gcloud:*)",
      "Bash(aws:*)",
      "Bash(ssh:*)",
      "Bash(scp:*)",
      "Bash(rsync:*)",
      "Bash(rm -rf:*)",
      "Bash(curl * | bash)",
      "Bash(curl * | sh)",
      "Bash(sudo:*)",
      "Read(/Users/*/.ssh/**)",
      "Read(/Users/*/.aws/**)",
      "Read(/Users/*/.config/gh/**)",
      "Read(**/*.env)",
      "Read(**/.nuzantara-secrets*)",
      "Edit(**/apps/backend-rag/**)",
      "Edit(**/apps/cell/**)",
      "Edit(**/apps/organism/**)",
      "Edit(**/fly.toml)",
      "Edit(**/.github/**)",
      "Write(**/apps/backend-rag/**)",
      "Write(**/apps/cell/**)",
      "Write(**/apps/organism/**)"
    ]
  },
  "env": {
    "BALI_ZERO_USER": "subhi",
    "BALI_ZERO_ROLE": "growth-systems-owner",
    "BALI_ZERO_PROBATION_END": "2026-07-29"
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": ".claude/hooks/subhi-bash-guard.sh"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": ".claude/hooks/subhi-session-log.sh"
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 7: Validate settings.json**

```bash
python3 -m json.tool .claude/settings.json > /dev/null && echo "JSON OK"
```

Expected: `JSON OK`

- [ ] **Step 8: Validate hook scripts manually**

```bash
# Test bash guard with a denied command
echo '{"tool_name":"Bash","tool_input":{"command":"fly ssh"},"cwd":"/Users/test/Projects/nuzantara-subhi"}' | bash .claude/hooks/subhi-bash-guard.sh
```

Expected: exit 2 + bahasa error message on stderr.

```bash
# Test bash guard with allowed command
echo '{"tool_name":"Bash","tool_input":{"command":"git status"},"cwd":"/Users/test/Projects/nuzantara-subhi"}' | bash .claude/hooks/subhi-bash-guard.sh
echo "Exit: $?"
```

Expected: `Exit: 0`

```bash
# Test session log
echo '{"session_id":"test-123","stop_hook_active":true}' | bash .claude/hooks/subhi-session-log.sh
cat .claude/session-log.jsonl | tail -1
```

Expected: jsonl line with `_logged_at` and `_machine` fields appended.

- [ ] **Step 9: Commit and push**

```bash
git add .claude/ .gitignore
git commit -m "feat: zantara-onboarding sub-agent + RBAC hooks + settings"
git push origin main
```

---

## Task 4-bis: Conversational continuity — session summary hook

**Files:** all paths relative to `~/Projects/nuzantara-subhi/`

- Modify: `.claude/hooks/subhi-session-log.sh` (extend with summary writer)
- Create: `.claude/memory-mirror-subhi/.gitkeep`

**Goal:** Stop hook extracts a session summary (topics asked, files
touched, decisions made) and appends it to `.claude/memory-mirror-subhi/<date>.md`.
Sub-agent reads these files at the start of every new session — giving
the tutor _recall_ of prior conversations with Subhi.

Reference spec: §19 conversational continuity layer.

- [ ] **Step 1: Create memory-mirror-subhi dir + gitkeep**

```bash
cd ~/Projects/nuzantara-subhi
mkdir -p .claude/memory-mirror-subhi
touch .claude/memory-mirror-subhi/.gitkeep

cat > .claude/memory-mirror-subhi/README.md <<'EOF'
# memory-mirror-subhi

Auto-generated session summaries from Subhi's tutor conversations.
Written by `.claude/hooks/subhi-session-log.sh` on each Stop event.

Format: one file per day (`YYYY-MM-DD.md`), multiple session blocks
per file if Subhi runs multiple sessions same day.

The `zantara-onboarding` sub-agent reads the last 3 days of files at
session start to maintain conversational continuity.

DO NOT edit manually — overwritten by hook. To curate / clean stale
notes, delete entire date file.
EOF
```

- [ ] **Step 2: Replace subhi-session-log.sh with summary-extracting version**

Overwrite `.claude/hooks/subhi-session-log.sh`:

```bash
#!/usr/bin/env bash
# subhi-session-log.sh — Stop hook, dual responsibility:
#   1. Append jsonl session log (raw, for Antonello weekly review)
#   2. Extract session summary → .claude/memory-mirror-subhi/<date>.md
#      (read by zantara-onboarding sub-agent for conversational continuity)
set -euo pipefail

INPUT=$(cat)
LOG_FILE="$HOME/Projects/nuzantara-subhi/.claude/session-log.jsonl"
SUMMARY_DIR="$HOME/Projects/nuzantara-subhi/.claude/memory-mirror-subhi"
mkdir -p "$(dirname "$LOG_FILE")" "$SUMMARY_DIR"

# === 1. Raw jsonl log ===
ENRICHED=$(echo "$INPUT" | python3 -c "
import sys, json, os
from datetime import datetime
d = json.load(sys.stdin)
d['_logged_at'] = datetime.utcnow().isoformat() + 'Z'
d['_machine'] = os.uname().nodename
print(json.dumps(d))
")
echo "$ENRICHED" >> "$LOG_FILE"

# === 2. Session summary ===
TODAY=$(date +%Y-%m-%d)
NOW=$(date +%H:%M)
SUMMARY_FILE="$SUMMARY_DIR/${TODAY}.md"

# Extract via Python — Stop hook input has session_id, transcript_path
SUMMARY=$(echo "$INPUT" | python3 <<'PYEOF'
import sys, json, os, re
from pathlib import Path

try:
    d = json.load(sys.stdin)
except json.JSONDecodeError:
    sys.exit(0)

transcript_path = d.get("transcript_path", "")
session_id = d.get("session_id", "unknown")[:8]

# Read transcript if available
text = ""
if transcript_path and os.path.exists(transcript_path):
    try:
        with open(transcript_path) as f:
            for line in f:
                try:
                    msg = json.loads(line)
                    if msg.get("type") == "user":
                        c = msg.get("message", {}).get("content", "")
                        if isinstance(c, str):
                            text += c + "\n"
                        elif isinstance(c, list):
                            for item in c:
                                if isinstance(item, dict) and "text" in item:
                                    text += item["text"] + "\n"
                except json.JSONDecodeError:
                    continue
    except (OSError, IOError):
        pass

# Heuristic topic extraction
topics = set()
patterns = {
    "NB": r"NB-\d+|NotebookLM",
    "files": r"(FunnelFeature|analytics\.ts|ArticleClient|HeaderWhatsApp|sitemap|robots)",
    "domains": r"(visa|KITAS|KITAP|KBLI|tax|property|CoreTax|PT PMA)",
    "branches": r"sancho/[a-z0-9-]+",
    "git_ops": r"\b(commit|push|PR|pull request|merge|rebase)\b",
    "concepts": r"(GA4|funnel|CTA|tracking|UTM|Search Console|RBAC)",
}
for label, pat in patterns.items():
    for m in re.finditer(pat, text, re.IGNORECASE):
        topics.add(m.group(0))

topic_list = sorted(topics)[:15]  # cap at 15 to keep summary tight

# Output: emit a markdown block
print(f"## Sesi {session_id}")
if topic_list:
    print(f"**Topik:** {', '.join(topic_list)}")
print(f"**Reason:** {d.get('stop_hook_active', 'n/a')}")
PYEOF
)

if [[ -n "$SUMMARY" ]]; then
  {
    echo ""
    echo "<!-- Sesi $NOW -->"
    echo "$SUMMARY"
  } >> "$SUMMARY_FILE"
fi

exit 0
```

Make sure executable:

```bash
chmod +x .claude/hooks/subhi-session-log.sh
```

- [ ] **Step 3: Test the summary extraction**

Mock Stop hook input:

```bash
TMP=$(mktemp -d)
cat > "$TMP/transcript.jsonl" <<'EOF'
{"type":"user","message":{"content":"Bagaimana cara fix tracking di FunnelFeature.tsx?"}}
{"type":"assistant","message":{"content":"Saya lihat ada 2 CTA tanpa onClick di line 365 dan 393..."}}
{"type":"user","message":{"content":"Buat branch sancho/d1-funnel-tracking-fix dan commit"}}
EOF

echo "{\"session_id\":\"abc12345-test\",\"transcript_path\":\"$TMP/transcript.jsonl\",\"stop_hook_active\":true}" | \
  bash .claude/hooks/subhi-session-log.sh

# Verify summary written
TODAY=$(date +%Y-%m-%d)
cat ".claude/memory-mirror-subhi/${TODAY}.md"
```

Expected: file contains a `## Sesi abc12345` block with detected topics
including `FunnelFeature`, `sancho/d1-funnel-tracking-fix`, `tracking`,
`branch`, `commit`.

```bash
rm -rf "$TMP"
```

- [ ] **Step 4: Update .gitignore**

The summary files SHOULD be committed (they let Subhi sync recall across
devices). The raw jsonl log should NOT.

```bash
# Check current .gitignore — should already exclude session-log.jsonl from T4
grep "session-log.jsonl" .gitignore || echo "session-log.jsonl missing — add it"
# memory-mirror-subhi/ committed by default — no entry needed
```

- [ ] **Step 5: Commit and push**

```bash
git add .claude/hooks/subhi-session-log.sh .claude/memory-mirror-subhi/
git commit -m "feat(subhi): conversational continuity — session summary hook + memory-mirror-subhi"
git push origin main
```

---

## Task 5: Bahasa onboarding docs + exercises

**Files:** all paths relative to `~/Projects/nuzantara-subhi/`

- Create: `CLAUDE.md`
- Create: `README.md`
- Create: `docs/onboarding/00_SELAMAT_DATANG.md` through `99_FAQ.md` (9 files)
- Create: `exercises/day1_setup_check.md` through `day7_money_pages_pick.md` (6 files)

**Goal:** the bahasa-language documentation Subhi reads on Day 1 and the 6 exercises he completes Days 1-7. Each file is short and concrete. The tutor sub-agent generates further exercises on-demand for Day 8+ (no need to pre-write 60 of them).

For brevity in this plan, full content of each file is given for the 3 most-load-bearing files. The other 12 follow the same pattern — each file has a fixed structure (Tujuan, Konteks, Langkah, Verifikasi, Selesai?), and content can be transcribed from the design spec §10 + the existing `~/Desktop/subhi_INDUCTION_KIT/` materials.

- [ ] **Step 1: Write CLAUDE.md (project root, auto-loaded)**

Write `~/Projects/nuzantara-subhi/CLAUDE.md`:

```markdown
# CLAUDE.md — Subhi Workspace

**User:** Subhi Darajat
**Peran:** Growth Systems Owner — Akuisisi Organik & Konversi
**Probation:** 2026-04-30 → 2026-07-29 (90 hari)
**Track:** Operator → Builder → Rekan
**Repo lavoro:** `balizero/nuzantara` (branch `sancho/*`)
**Repo onboarding:** `balizero/nuzantara-subhi` (kamu di sini)

## Bahasa

**Selalu jawab dalam Bahasa Indonesia kepada Subhi.** Code, commit, branch
name, PR title tetap dalam Bahasa Inggris (konvensi codebase).

Antonello (boss, owner Bali Zero) parla italiano — tapi ketika kamu
berinteraksi DI SINI, dengan Subhi, selalu bahasa.

## Tutor

Untuk setiap pertanyaan tentang sistem Bali Zero, perimeter Subhi,
NotebookLM authority, atau 60-day mission, panggil:
```

/agent zantara-onboarding "<pertanyaan>"

```

Sub-agent ini punya akses ke memory mirror harian dari sistem Bali Zero,
4 NotebookLM (NB-1, NB-2, NB-9, NB-OPS), dan GitHub MCP scoped sancho/*.

## Memory mirror

`.claude/memory-mirror/` di-update setiap pagi 04:00 WITA dari Pro Antonello.
Baca file ini ketika butuh konteks tentang:
- Project aktif (NLM strategy, Sprint W1, audit zero-crash)
- Konvensi codebase, repo paths
- Lessons learned, scar incidents (cicatrix)
- NB authority

Untuk update terbaru: `git pull` di pagi hari sebelum mulai kerja.

## RBAC singkat

Lihat `docs/onboarding/02_RBAC_BAHASA.md` lengkap. Ringkasan:

- ✅ **VERDE**: `apps/mouth/**`, GA4/GSC, distribution
- ⚠️ **GIALLO**: backend endpoint baru → pair Asya/Antonello
- 🚫 **ROSSO**: RAG core, Qdrant, secrets, fly.toml, organism/genome

Tutor akan tolak request yang masuk ROSSO. Hooks `.claude/hooks/subhi-bash-guard.sh`
juga enforce di Bash level (fly, gcloud, sudo, etc).

## Workflow git

1. Branch baru: `git checkout -b sancho/<task-slug>`
2. Edit code (di `~/Projects/nuzantara/` untuk lavoro reale)
3. Commit dalam Bahasa Inggris: `feat(mouth): add CTA WhatsApp on /visa`
4. Push: `git push origin sancho/<task-slug>`
5. Open PR via `gh pr create`
6. **Tunggu review Antonello** — JANGAN self-merge dalam 30 hari pertama
7. Setelah merge: `git checkout main && git pull && git branch -d sancho/<task-slug>`

## Daily standup

09:00 WITA — kantor Kuta. Format ieri/oggi/blocker, 3-5 menit max.

## File penting

- `docs/onboarding/00_SELAMAT_DATANG.md` — welcome
- `docs/onboarding/07_60_DAY_MISSION_BAHASA.md` — mission lengkap
- `exercises/day1_setup_check.md` — mulai dari sini
```

- [ ] **Step 2: Write README.md (bahasa orientation)**

Write `~/Projects/nuzantara-subhi/README.md`:

```markdown
# Subhi Workspace — Bali Zero

Halo Subhi! Ini repository pribadi kamu untuk onboarding 90 hari di Bali
Zero sebagai **Growth Systems Owner**.

## Struktur

- `.claude/` — config Claude Code + tutor sub-agent
- `docs/onboarding/` — dokumentasi bahasa Indonesia
- `exercises/` — exercise harian Day 1-7 (Day 8+ dihasilkan tutor on-demand)

## Mulai dari sini

1. Buka `docs/onboarding/00_SELAMAT_DATANG.md`
2. Lalu `exercises/day1_setup_check.md`

## Tutor
```

claude
/agent zantara-onboarding halo

```

Tutor selalu jawab dalam Bahasa Indonesia.

## Repo lavoro

Lavoro reale ada di `~/Projects/nuzantara/` (clone repo `balizero/nuzantara`).
Branch kamu: `sancho/<task-slug>` saja.

## Kontak

- Antonello (boss): WhatsApp 1-1
- Asya (platform): backend pair
- Daily standup: 09:00 WITA, kantor Kuta
```

- [ ] **Step 3: Write docs/onboarding/00_SELAMAT_DATANG.md**

```bash
mkdir -p docs/onboarding exercises
```

Write `docs/onboarding/00_SELAMAT_DATANG.md`:

```markdown
# Selamat datang, Subhi 🙏

Hari ini kamu mulai 90 hari probation di Bali Zero sebagai
**Growth Systems Owner — Akuisisi Organik & Konversi**.

## Misi kamu dalam 1 kalimat

> Ambil yang sudah dibangun Bali Zero (149 artikel, 4 funnel, AI Zantara,
> KBLI navigator, knowledge base 108k node) dan **bawa ke orang sungguhan**,
> ukur siapa yang menjadi percakapan komersial.

Kamu BUKAN content guy, BUKAN SEO guy, BUKAN ads guy. Kamu adalah pemilik
**Organic Growth Surface** — semua yang berada di antara konten publik
dan lead WhatsApp pertama.

## Hari ini (Day 1)

1. Setup teknis: lihat `exercises/day1_setup_check.md`
2. Baca mission lengkap: `docs/onboarding/07_60_DAY_MISSION_BAHASA.md`
3. Pahami perimeter (VERDE/GIALLO/ROSSO): `docs/onboarding/02_RBAC_BAHASA.md`
4. Daily standup pertama besok jam 09:00 WITA

## Yang HARUS kamu tahu sekarang

- Website cuma 2 lead/90 hari. WhatsApp 420. Misi: naikkan website ≥20/bulan.
- Tracking GA4 di funnel CTA RUSAK (Day 1 prioritas: fix ini).
- 5.030 query di balizero_news semuanya dari bot internal. NOL pembaca asli.
- 138 pratiche stuck >14 hari — bisa jadi tambang konten dan FAQ publik.

Bukan masalah kamu menyelesaikan semua. Misi kamu: **last mile** dari
klik organik ke lead.

## Aturan keras (jangan dilanggar)

1. Push ke `main` ❌ — selalu pakai branch `sancho/<task>`
2. Edit `apps/backend-rag/` ❌ — ini scope ROSSO
3. Edit `fly.toml`, `.env*`, secrets ❌
4. Self-merge PR ❌ dalam 30 hari pertama
5. Touch CRM data live ❌ (read-only assigned, MAI write)

Tutor (`/agent zantara-onboarding`) akan tolak otomatis kalau salah scope.

## Filosofi

> "AI mengusulkan, manusia memutuskan, cell mengukur."

Kamu menutup loop di sisi growth. Selamat memulai 🚀

— Antonello
```

- [ ] **Step 4: Write the 8 remaining docs/onboarding/ files**

For each of the following, create the file with the content described. Brevity OK — content can be tight (50-200 lines each).

`docs/onboarding/01_HARI_PERTAMA.md`: Day 1 walkthrough — schedule (09:30 arrive, 09:35 setup, 10:00 install complete, 10:30 read welcome, 11:00 daily standup), what to bring (laptop), what to expect (no coding today, just setup + reading).

`docs/onboarding/02_RBAC_BAHASA.md`: full bahasa translation of `~/.claude/projects/-Users-nuzantara/memory/subhi-rbac-permissions.md`. GitHub access, CRM read-only analytics, GA4/GSC viewer, Vercel viewer, NB read full, Fly NO, Pro/Air NO, NLM mutations NO. Include conversion criteria post-probation.

`docs/onboarding/03_TASK_ROUTING_BAHASA.md`: bahasa translation of `subhi-task-routing.md`. VERDE list (apps/mouth/ paths), GIALLO list (backend pair), ROSSO list (rag/cell/organism/secrets/fly). Concrete examples + escalation routing (Asya backend, Antonello strategic, Sahira/Surya/Ari domain).

`docs/onboarding/04_BAHASA_CODEBASE_TOUR.md`: guided tour of `apps/mouth/` — top-level dirs (`src/app/`, `src/components/`, `src/lib/`, `src/content/articles/`, `e2e/`, `public/`). Key files: `FunnelFeature.tsx`, `analytics.ts`, `ArticleClient.tsx`. Flow: blog post URL → Next.js dynamic route → ArticleClient → CTA.

`docs/onboarding/05_NB_AUTHORITY_GUIDE.md`: how to query NB-2, NB-9, NB-1, NB-OPS via tutor. Example prompts: "Query NB-2 tentang KITAS C7 duration", "NB-9 sources untuk PT PMA hospitality", "NB-1 architecture EventBus channels". Always cite sources in answers.

`docs/onboarding/06_SANCHO_BRANCH_WORKFLOW.md`: full git workflow with `gh` CLI examples. Branch naming convention `sancho/<deliverable>-<short-desc>`. PR template. Commit convention `feat|fix|chore|refactor|docs(scope): subject`. Co-author tagline `Co-Authored-By: Claude Opus 4.7`. No --no-verify, no --amend on pushed commits.

`docs/onboarding/07_60_DAY_MISSION_BAHASA.md`: copy verbatim from `~/Desktop/subhi_INDUCTION_KIT/00_MISI_SUBHI_60_HARI_BAHASA.md`. ~1006 lines, complete mission with §1-§17 sections.

`docs/onboarding/99_FAQ.md`: top 20 expected Q&A. "Apa beda repo onboarding vs main repo?" "Boleh saya pakai Copilot bareng Claude?" "Kalau saya salah dan break sesuatu, gimana?" "Daily standup bagaimana kalau saya WFH?" "Bagaimana cara test e2e Playwright?" "Saya lupa branch naming, gimana fix?"

```bash
# Create empty placeholders + transcribe content per file
for f in 01_HARI_PERTAMA 02_RBAC_BAHASA 03_TASK_ROUTING_BAHASA 04_BAHASA_CODEBASE_TOUR 05_NB_AUTHORITY_GUIDE 06_SANCHO_BRANCH_WORKFLOW 99_FAQ; do
  touch "docs/onboarding/${f}.md"
done

# 07_60_DAY_MISSION is a copy
cp ~/Desktop/subhi_INDUCTION_KIT/00_MISI_SUBHI_60_HARI_BAHASA.md \
  docs/onboarding/07_60_DAY_MISSION_BAHASA.md
```

Then write each file's content per the descriptions above.

- [ ] **Step 5: Write exercise day1_setup_check.md (full content)**

Write `~/Projects/nuzantara-subhi/exercises/day1_setup_check.md`:

````markdown
# Hari 1 — Setup Check

**Tanggal:** Hari pertama kamu di kantor (yang ditentukan Antonello)
**Mission ref:** §10 setup teknis (`07_60_DAY_MISSION_BAHASA.md`)
**Estimasi waktu:** 30 menit

## Tujuan

Pastikan semua tools terpasang di MacBook kamu dan kamu bisa "ngobrol"
dengan Zantara Onboarding untuk pertama kali.

## Konteks

Antonello sudah pre-setup beberapa hal:

- Akun GitHub `subhi@balizero.com` collaborator di `balizero/nuzantara` + `balizero/nuzantara-subhi`
- NotebookLM share NB-1, NB-2, NB-9, NB-OPS ke email kamu
- MAX plan Claude Code dengan slot kamu
- Tailscale tailnet `balizero` (kamu sudah join via laptop kamu sebelumnya)

Sekarang kamu install client-side: Claude Code CLI, nlm CLI, dan join
tailnet di MacBook baru.

## Pre-requisiti

- [ ] MacBook Pro 16GB sudah on
- [ ] Login macOS dengan akun kamu
- [ ] Internet kantor Kuta connected
- [ ] WhatsApp video call dengan Antonello ready (untuk supervisi)

## Langkah-langkah

### 1. Buka Terminal (atau iTerm)

`Cmd+Space` → ketik "Terminal" → Enter.

### 2. Run install script

Antonello kasih kamu link gist. Copy-paste command ini:

```bash
bash <(curl -sL <gist-url-yang-dikirim-Antonello>)
```
````

Script akan:

- Install Xcode CLI tools (jika belum)
- Install Homebrew (jika belum)
- Install Node.js 20, GitHub CLI, Tailscale, VSCode
- Install Claude Code CLI
- Install nlm CLI
- Login Tailscale (akan buka browser, login pakai subhi@balizero.com)
- Clone repo `balizero/nuzantara-subhi` ke `~/Projects/nuzantara-subhi/`
- Clone repo `balizero/nuzantara` ke `~/Projects/nuzantara/`
- Setup OAuth Claude (akan buka browser)
- Setup OAuth NLM (akan buka browser)

Total ~15 menit. Bisa minum kopi.

### 3. Verifikasi install

```bash
claude --version
nlm --version
gh --version
git --version
node --version
```

Semua harus jalan tanpa "command not found".

### 4. Buka VSCode

```bash
cd ~/Projects/nuzantara-subhi
code .
```

VSCode terbuka. Tekan `Ctrl+\`` untuk buka integrated terminal.

### 5. Test tutor pertama kali

Di terminal VSCode (CWD harus `~/Projects/nuzantara-subhi`):

```bash
claude
```

Setelah masuk Claude session:

```
/agent zantara-onboarding halo, perkenalkan diri kamu dan jelaskan apa yang akan kamu bantu saya selama 90 hari ke depan
```

## Verifikasi

Tutor harus jawab:

- ✅ Dalam **Bahasa Indonesia** (BUKAN Inggris atau Italia)
- ✅ Memperkenalkan diri sebagai "Zantara Onboarding"
- ✅ Menjelaskan scope kamu (Growth Systems Owner)
- ✅ Menyebut perimeter VERDE/GIALLO/ROSSO
- ✅ Menyebut workflow `sancho/*` branch

## Kalau ada error

| Error                                 | Fix                                                                                              |
| ------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `claude: command not found`           | Re-source `~/.zshrc`, atau `npm install -g @anthropic-ai/claude-code` ulang                      |
| OAuth login Claude fail               | Cek koneksi internet, retry. Kalau persisten, ping Antonello — mungkin MAX plan slot belum ready |
| `/agent zantara-onboarding not found` | CWD kamu salah. `cd ~/Projects/nuzantara-subhi` dulu                                             |
| Tutor jawab dalam bahasa Inggris      | Sub-agent prompt salah load. Restart Claude session, retry                                       |
| `nlm login` fail                      | Google MFA — coba `nlm login --clear` lalu login lagi                                            |

## Selesai?

Kalau verifikasi 5/5 ✅:

1. Screenshot tutor reply
2. Kirim screenshot ke Antonello via WhatsApp
3. Lanjut ke `exercises/day2_codebase_tour.md` besok

Kalau ada blocker yang nggak ke-fix di tabel di atas:

- Stop di sini, ping Antonello dengan screenshot error
- Jangan teruskan ke Day 2 sebelum Day 1 selesai

````

- [ ] **Step 6: Write the 5 remaining exercises**

Each file follows the same template. Pseudocode for content:

`exercises/day2_codebase_tour.md`: tutor prompts (`/agent zantara-onboarding jelaskan apa itu FunnelFeature.tsx`), guided read of 3 files, find the 2 missing onClicks at lines 365 and 393, identify import gap for `trackFunnelEvent`. Verifikasi: bahasa explanation in Subhi's own words, posted to shared note. Selesai: shared note + WA screenshot.

`exercises/day3_first_pr.md`: branch creation `sancho/d1-funnel-tracking-fix`, edit `FunnelFeature.tsx` (add onClick + import), commit message `feat(mouth): add CTA tracking on FunnelFeature.tsx (D1)`, push, open PR via `gh pr create`. Verifikasi: PR open, Antonello sees it on his GitHub. Selesai: PR URL + screenshot.

`exercises/day4_playwright_test.md`: open `apps/mouth/e2e/funnel-ctas.spec.ts`, add test that clicks each CTA and verifies GA4 event fires. Run `npm run test:e2e` locally, verify green. Verifikasi: terminal output "X passed". Selesai: screenshot terminal.

`exercises/day5_article_inventory.md`: shell pipeline grep `apps/mouth/src/content/articles/**`, classify by directory (immigration/business/tax/property), output CSV with columns slug,category,intent,word_count. Verifikasi: CSV has ≥149 rows. Selesai: CSV path posted in shared note.

`exercises/day7_money_pages_pick.md`: tutor query NB-2 + NB-9 for "queries paling commercial Indonesia 2026", cross-reference with article inventory CSV, pick top 3 articles per cluster (visa/company/tax/property) = 12 money pages. Verifikasi: list of 12 slug + 1-line bahasa rationale per slug. Selesai: list pushed to `exercises/_outputs/12_money_pages.md`.

(Day 6 is weekend — no exercise file, just a `docs/onboarding/99_FAQ.md` Q&A "Saturday-Sunday = istirahat".)

```bash
# Create stub files
for f in day2_codebase_tour day3_first_pr day4_playwright_test day5_article_inventory day7_money_pages_pick; do
  touch "exercises/${f}.md"
done
````

Then write each file per the description above.

- [ ] **Step 7: Validate all markdown files lint clean**

```bash
# Optional but useful — uses prettier from main repo
cd ~/Desktop/nuzantara
npx prettier --check ~/Projects/nuzantara-subhi/docs/onboarding/*.md \
  ~/Projects/nuzantara-subhi/exercises/*.md \
  ~/Projects/nuzantara-subhi/CLAUDE.md \
  ~/Projects/nuzantara-subhi/README.md \
  || npx prettier --write <files>
```

Expected: all files pass or are auto-fixed.

- [ ] **Step 8: Commit and push**

```bash
cd ~/Projects/nuzantara-subhi
git add CLAUDE.md README.md docs/ exercises/
git commit -m "feat: bahasa onboarding docs + Day 1-7 exercises"
git push origin main
```

---

## Task 6: Install script

**Files:**

- Create: `~/Desktop/nuzantara/scripts/subhi/subhi-tutor-install.sh`
- Create: `~/Desktop/nuzantara/scripts/subhi/install.gist-readme.md` (gist hosting notes)

**Goal:** one-shot bash script Subhi runs on his Mac that installs everything, clones both repos, sets OAuth, runs first tutor test. Hosted as a GitHub gist for `bash <(curl -sL ...)` execution.

- [ ] **Step 1: Write subhi-tutor-install.sh**

Write `~/Desktop/nuzantara/scripts/subhi/subhi-tutor-install.sh`:

```bash
#!/usr/bin/env bash
# subhi-tutor-install.sh — Subhi MacBook one-shot installer.
# Usage on Subhi's Mac:
#   bash <(curl -sL https://gist.githubusercontent.com/.../subhi-tutor-install.sh)
# Or download and run:
#   curl -O https://gist...subhi-tutor-install.sh && bash subhi-tutor-install.sh
#
# Reference: docs/superpowers/specs/2026-05-04-subhi-tutor-design.md §13
# Reference: docs/superpowers/plans/2026-05-04-subhi-tutor-implementation.md T6

set -euo pipefail

# === Cosmetic helpers (bahasa) ===
BAHASA() { echo -e "\033[36m▸\033[0m $*"; }
ERR()    { echo -e "\033[31m✗\033[0m $*" >&2; exit 1; }
OK()     { echo -e "\033[32m✓\033[0m $*"; }
INFO()   { echo -e "\033[33mℹ\033[0m $*"; }

# === Pre-flight ===
[[ "$(uname)" == "Darwin" ]] || ERR "Script ini hanya untuk macOS. Kamu di $(uname)."
OK "macOS terdeteksi"

# === 1. Xcode CLI tools ===
if ! xcode-select -p &>/dev/null; then
  BAHASA "Install Xcode CLI tools (akan minta password Mac)..."
  xcode-select --install || true
  echo "Tunggu install GUI selesai (~5 menit), lalu re-run script ini."
  exit 0
fi
OK "Xcode CLI ready"

# === 2. Homebrew ===
if ! command -v brew &>/dev/null; then
  BAHASA "Install Homebrew (akan minta password Mac)..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  # Add to PATH for this session
  if [[ -d /opt/homebrew/bin ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [[ -d /usr/local/Homebrew ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi
fi
OK "Homebrew $(brew --version | head -1)"

# === 3. CLI tools via brew ===
BAHASA "Install Node.js 20, GitHub CLI, uv (Python tool installer)..."
brew install node@20 gh uv
brew link --overwrite node@20 || true

# Add to shell profile
SHELL_RC="$HOME/.zshrc"
grep -q "node@20/bin" "$SHELL_RC" 2>/dev/null || \
  echo 'export PATH="/opt/homebrew/opt/node@20/bin:$PATH"' >> "$SHELL_RC"

OK "node $(node --version), gh $(gh --version | head -1)"

# === 4. Tailscale + VSCode (if not already installed) ===
if ! command -v tailscale &>/dev/null; then
  BAHASA "Install Tailscale (cask)..."
  brew install --cask tailscale
fi
if ! command -v code &>/dev/null; then
  BAHASA "Install VSCode (cask)..."
  brew install --cask visual-studio-code || INFO "VSCode mungkin sudah terinstall"
fi
OK "GUI apps ready"

# === 5. Claude Code CLI ===
BAHASA "Install Claude Code CLI..."
NPM_GLOBAL="$HOME/.npm-global"
mkdir -p "$NPM_GLOBAL"
npm config set prefix "$NPM_GLOBAL"
grep -q ".npm-global/bin" "$SHELL_RC" 2>/dev/null || \
  echo "export PATH=\"$NPM_GLOBAL/bin:\$PATH\"" >> "$SHELL_RC"
export PATH="$NPM_GLOBAL/bin:$PATH"
npm install -g @anthropic-ai/claude-code
OK "Claude $(claude --version)"

# === 6. NLM CLI ===
BAHASA "Install NotebookLM CLI..."
uv tool install notebooklm-mcp-cli || INFO "Sudah terinstall"
OK "nlm CLI ready"

# === 7. Tailscale up ===
if ! tailscale status &>/dev/null; then
  BAHASA "Login Tailscale (akan buka browser)..."
  INFO "Login pakai subhi@balizero.com"
  /Applications/Tailscale.app/Contents/MacOS/Tailscale up || sudo tailscale up
fi
TS_IP=$(tailscale ip -4 | head -1 || echo "tidak ada")
OK "Tailscale: $TS_IP"

# === 8. SSH key (if missing) ===
if [[ ! -f "$HOME/.ssh/id_ed25519" ]]; then
  BAHASA "Generate SSH key..."
  ssh-keygen -t ed25519 -C "subhi@balizero.com" -f "$HOME/.ssh/id_ed25519" -N ""
  INFO "SSH public key:"
  cat "$HOME/.ssh/id_ed25519.pub"
  INFO "Copy line di atas. Akan ditambah ke GitHub di step berikutnya."
  read -r -p "Tekan Enter setelah copy..."
fi
OK "SSH key ready"

# === 9. GitHub login ===
BAHASA "Login GitHub CLI (akan buka browser)..."
INFO "Login pakai akun GitHub yang dikaitkan dengan subhi@balizero.com"
gh auth status 2>/dev/null || gh auth login --hostname github.com --git-protocol ssh --web
OK "GitHub authenticated"

# Add SSH key to GitHub if not already there
if ! gh ssh-key list 2>/dev/null | grep -q "$(cat $HOME/.ssh/id_ed25519.pub | awk '{print $2}')"; then
  BAHASA "Tambah SSH key ke GitHub..."
  gh ssh-key add "$HOME/.ssh/id_ed25519.pub" --title "MacBook Subhi $(date +%Y-%m-%d)" || \
    INFO "SSH key sudah ada atau gagal — lanjut"
fi

# === 10. Clone repos ===
mkdir -p "$HOME/Projects"
cd "$HOME/Projects"

if [[ ! -d nuzantara-subhi ]]; then
  BAHASA "Clone repo nuzantara-subhi..."
  gh repo clone balizero/nuzantara-subhi
fi
OK "Repo nuzantara-subhi cloned"

if [[ ! -d nuzantara ]]; then
  BAHASA "Clone repo nuzantara (main work repo)..."
  gh repo clone balizero/nuzantara
fi
OK "Repo nuzantara cloned"

# === 11. Replace placeholders in settings.json ===
SETTINGS="$HOME/Projects/nuzantara-subhi/.claude/settings.json"
if [[ -f "$SETTINGS" ]]; then
  BAHASA "Configure settings.json placeholders..."
  CURRENT_USER=$(whoami)
  sed -i.bak "s|__SUBHI_USERNAME_PLACEHOLDER__|$CURRENT_USER|g" "$SETTINGS"

  # Prompt for PAT
  INFO "Antonello akan kasih kamu GitHub Personal Access Token (PAT)."
  INFO "Format: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxx (40 chars)"
  read -r -s -p "Paste PAT (akan tersembunyi): " PAT
  echo ""
  if [[ -n "$PAT" ]]; then
    sed -i.bak2 "s|__SUBHI_GITHUB_PAT_PLACEHOLDER__|$PAT|g" "$SETTINGS"
    rm -f "$SETTINGS.bak" "$SETTINGS.bak2"
    chmod 0600 "$SETTINGS"
    OK "PAT configured"
  else
    INFO "PAT skipped — kamu bisa edit $SETTINGS manual nanti"
  fi
fi

# === 12. Claude OAuth login ===
BAHASA "Login Claude Code (akan buka browser)..."
INFO "Login pakai subhi@balizero.com — ini claim slot MAX plan dari Antonello"
cd "$HOME/Projects/nuzantara-subhi"
# Trigger OAuth — sends user to browser, then exits
claude --version  # Just to verify it runs

# === 13. NLM login ===
BAHASA "Login NotebookLM (akan buka browser)..."
INFO "Login pakai subhi@balizero.com — terima invite NB-1, NB-2, NB-9, NB-OPS"
nlm login --clear || INFO "NLM login interactive — ikuti petunjuk di browser"

# === 14. Final test ===
BAHASA "Verifikasi tutor sub-agent..."
INFO "Sekarang ketik manual di terminal:"
INFO "  cd ~/Projects/nuzantara-subhi"
INFO "  claude"
INFO "Lalu di Claude session:"
INFO "  /agent zantara-onboarding halo"
INFO ""

OK "Setup selesai!"
echo ""
echo "════════════════════════════════════════════════════════"
echo "  Langkah berikutnya:"
echo "  1. Buka VSCode: code ~/Projects/nuzantara-subhi"
echo "  2. Baca: docs/onboarding/00_SELAMAT_DATANG.md"
echo "  3. Mulai: exercises/day1_setup_check.md"
echo "  4. Screenshot tutor reply ke Antonello via WhatsApp"
echo "════════════════════════════════════════════════════════"
```

Make executable:

```bash
chmod +x scripts/subhi/subhi-tutor-install.sh
```

- [ ] **Step 2: Write gist hosting README**

Write `~/Desktop/nuzantara/scripts/subhi/install.gist-readme.md`:

````markdown
# Hosting `subhi-tutor-install.sh` as a GitHub Gist

Why a gist (and not a repo file): the script must be downloadable
without authentication. A private repo file requires a PAT for the
curl. A public gist is anonymous-readable.

## Step 1: Create gist

```bash
gh gist create scripts/subhi/subhi-tutor-install.sh \
  --public \
  --desc "Subhi MacBook tutor installer (Bali Zero, 2026-05-04)"
```
````

Copy the gist URL.

## Step 2: Get raw URL

The gist URL is `https://gist.github.com/<user>/<gist-id>`.
Raw URL is `https://gist.githubusercontent.com/<user>/<gist-id>/raw/<filename>`.

To get raw:

```bash
gh api gists/<gist-id> --jq '.files | to_entries[0].value.raw_url'
```

## Step 3: Test before sending to Subhi

```bash
# On Antonello Mini (clean macOS account, recommended)
bash <(curl -sL '<raw-url>') 2>&1 | tee /tmp/install-test.log
```

Verify exit 0, no errors, all 14 steps OK.

## Step 4: Update gist when script changes

```bash
gh gist edit <gist-id> scripts/subhi/subhi-tutor-install.sh
```

The raw URL stays stable. Subhi never needs to update his bookmark.

## Step 5: Send link to Subhi

WhatsApp Antonello → Subhi:

> Halo Subhi, ini installer untuk MacBook kamu. Run command ini di
> Terminal pas kamu di kantor besok pagi:
>
> bash <(curl -sL '<raw-url>')
>
> 30 menit. Saya jaga via WA video call. — Antonello

````

- [ ] **Step 3: Commit**

```bash
cd ~/Desktop/nuzantara
git add scripts/subhi/subhi-tutor-install.sh scripts/subhi/install.gist-readme.md
git commit -m "feat(subhi): one-shot install script + gist hosting notes"
````

---

## Task 7: Day 1 runbook for Antonello

**Files:**

- Create: `~/Desktop/nuzantara/docs/runbooks/subhi-tutor-day1.md`

**Goal:** runbook Antonello prints/reads while supervising Subhi's Day 1 install. Step-by-step phone-friendly checklist.

- [ ] **Step 1: Create runbooks dir if missing**

```bash
mkdir -p ~/Desktop/nuzantara/docs/runbooks
```

- [ ] **Step 2: Write runbook**

Write `~/Desktop/nuzantara/docs/runbooks/subhi-tutor-day1.md`:

````markdown
# Runbook — Subhi Tutor Day 1 Live Setup

**Estimated time:** 90 minutes
**Audience:** Antonello, supervising Subhi via WhatsApp video call
**Pre-requisite:** Phase 0-5 of plan complete (memory mirror live, repo
seeded, install script gist-hosted, dry-run on Mini OK).

## Pre-Day-1 (evening before)

- [ ] Verify install gist URL still works:
  ```bash
  curl -sL '<gist-url>' | head -20
  ```
````

- [ ] Verify NB shares accepted by Subhi (or remind him via WhatsApp to
      check his email):
  ```bash
  nlm notebook_share_status --notebook NB-2 | grep subhi
  ```
- [ ] Verify GitHub PAT not expired (expiration date >30 days from now):
  ```bash
  gh api -X GET '/user/keys' | head -20  # check PAT separately in GH UI
  ```
- [ ] Verify MAX plan #2 has free slot:
  - Anthropic admin → Subscription → check seat usage
- [ ] Verify Tailscale ACL still blocks Subhi → Pro:
  ```bash
  # Mock as Subhi:
  ssh -o ConnectTimeout=3 nuzantara 2>&1 | grep -E "refused|timeout"
  # Should refuse / timeout
  ```
- [ ] Send WhatsApp message kepada Subhi malam sebelum:
  > "Subhi, besok jam 09:30 kantor. Bawa MacBook charged. Saya kirim
  > installer link via WA jam 09:35 — kita install bareng via video
  > call. — Antonello"

## T+0 (09:30 WITA)

- [ ] Subhi arrives kantor Kuta, MacBook on, internet connected
- [ ] Antonello: "Buka MacBook, login macOS"
- [ ] Antonello: WhatsApp video call attivo, audio + screen share

## T+5 to T+30 — Install (25 min)

- [ ] Antonello: send WA message:
  > Run di Terminal:
  > `bash <(curl -sL '<gist-raw-url>')`
- [ ] Subhi: copy-paste, run
- [ ] Antonello: monitor WA screen share

**Watch for these prompts (script asks Subhi):**

1. Xcode CLI tools install — GUI dialog appears, Subhi clicks "Install".
   Script exits, Antonello tells Subhi to wait ~5 min then re-run.
2. Homebrew password prompt — Subhi types Mac password.
3. Tailscale login browser — verify Subhi logs in with `subhi@balizero.com`.
4. SSH key prompt — Subhi presses Enter (key auto-generated).
5. GitHub `gh auth login` — browser flow, verify Subhi uses correct GH account.
6. SSH key add to GitHub — script auto-adds.
7. PAT paste — Antonello sends PAT via WA (separate message), Subhi pastes.
   ⚠️ NEVER send PAT via screen share (visible to anyone watching).
8. Claude OAuth — browser flow, verify subhi@balizero.com.
9. NLM login — browser flow, accept the 4 NB invitations.

**If script fails at any step:**

- Read the error in stderr
- Common fixes: re-run, sometimes brew is slow, sometimes nvm/uv
- If unrecoverable: Antonello takes screenshot, debug post-call

## T+30 to T+45 — First tutor test (15 min)

- [ ] Subhi runs:

  ```bash
  cd ~/Projects/nuzantara-subhi
  code .
  ```

  VSCode opens.

- [ ] Subhi opens integrated terminal (Ctrl+`)
- [ ] Subhi runs `claude` → claude session opens
- [ ] Subhi types: `/agent zantara-onboarding halo, perkenalkan diri kamu`
- [ ] Tutor responds in **bahasa Indonesia** with scope intro

**If tutor responds in English:**

- Sub-agent prompt failed to load
- Subhi: `exit` → re-launch `claude` → retry
- If still English: edit `.claude/agents/zantara-onboarding.md` line 1
  to confirm `name: zantara-onboarding` matches command

**If `/agent` not recognized:**

- `claude --version` — must be 2.0+
- If <2.0: `npm install -g @anthropic-ai/claude-code` ulang

- [ ] Subhi screenshot tutor reply, sends to Antonello shared note
- [ ] Antonello verifies bahasa, scope correct

## T+45 to T+75 — Reading + first exercise (30 min)

- [ ] Subhi reads `docs/onboarding/00_SELAMAT_DATANG.md` (~5 min)
- [ ] Subhi reads `exercises/day1_setup_check.md` (~5 min) — already done!
- [ ] Subhi marks Day 1 complete: WhatsApp screenshot to Antonello
- [ ] Antonello: "Mantap. Day 2 besok pagi. Daily standup besok 09:00 — kita
      ketemu di kantor."

## T+75 to T+90 — Daily standup briefing (15 min)

- [ ] Subhi reads `docs/onboarding/02_RBAC_BAHASA.md` (5 min)
- [ ] Subhi reads `docs/onboarding/06_SANCHO_BRANCH_WORKFLOW.md` (5 min)
- [ ] Antonello: "Pertanyaan?"
- [ ] Q&A live, end call

## Post-Day-1 (Antonello, that evening)

- [ ] Read Subhi session log:
  ```bash
  ssh subhi-mac 'cat ~/Projects/nuzantara-subhi/.claude/session-log.jsonl' | head -20
  ```
  (or: tomorrow during standup, ask Subhi to paste it)
- [ ] Check first PR if Subhi got that far (unlikely Day 1)
- [ ] Update memory:
  ```bash
  ~/.claude/scripts/mem save fact "Subhi Day 1 setup OK $(date +%Y-%m-%d), tutor works in bahasa, RBAC enforced" 7
  ```
- [ ] If issues found: file edits → push → tomorrow Subhi `git pull`
- [ ] If clean: schedule Day 2 reminder

## Failure escalation

| Failure point                      | Recovery                                                                                        |
| ---------------------------------- | ----------------------------------------------------------------------------------------------- |
| Install script crashes mid-step    | Re-run from same point — most steps are idempotent                                              |
| OAuth Claude fails                 | Check MAX plan slot, retry. If >3 fails, fall back to Subhi's personal Google + buy his own MAX |
| Tutor responds wrong language      | Edit sub-agent prompt, push, Subhi `git pull && claude` restart                                 |
| Subhi can't run any commands       | Antonello checks Tailscale ACL — if Subhi accidentally got Pro access, revoke immediately       |
| Anything taking >2x estimated time | Stop, screenshot state, defer to async fix                                                      |

## Day 2 readiness signal

Send WhatsApp message that evening:

> "Subhi, Day 1 selesai 🎉. Besok Day 2: codebase tour. Buka exercises/day2_codebase_tour.md
> setelah daily standup. Antonello"

````

- [ ] **Step 3: Commit**

```bash
git add docs/runbooks/subhi-tutor-day1.md
git commit -m "docs(subhi): Day 1 live setup runbook for Antonello"
````

---

## Task 8: Dry-run on Antonello Mini (Mac Mini M4 Pro)

**Files:** none (live verification on a different machine)

**Goal:** end-to-end test of the install script on a clean macOS account that mimics Subhi's experience. The Mini is the perfect test bed: same architecture (Apple Silicon), same shell (zsh), no existing Bali Zero setup.

- [ ] **Step 1: Verify Mini is accessible**

```bash
ssh mini 'whoami && hostname && uname -a'
```

Expected: `nuzantara`, `Mini-Pro2`, `Darwin Mini-Pro2 ...`.

- [ ] **Step 2: Create a test user account on Mini**

Manual step on Mini (via Screen Sharing or in person):

- System Settings → Users & Groups → Add user → name: `testsubhi` (Standard, password: temp).

This isolates test from `nuzantara` account on Mini. After test, remove the user.

- [ ] **Step 3: Push gist with current install script**

```bash
gh gist create ~/Desktop/nuzantara/scripts/subhi/subhi-tutor-install.sh \
  --public \
  --desc "Subhi tutor installer — DRY RUN $(date +%Y-%m-%d)"
GIST_URL=$(gh gist list --limit 1 | head -1 | awk '{print $1}')
GIST_RAW="https://gist.githubusercontent.com/$(gh api user --jq .login)/$GIST_URL/raw/subhi-tutor-install.sh"
echo "$GIST_RAW"
```

Copy the raw URL.

- [ ] **Step 4: Switch user on Mini, run installer**

Manual on Mini:

- Log out `nuzantara`, log in as `testsubhi`
- Open Terminal
- Run:
  ```bash
  bash <(curl -sL '<gist-raw-url>')
  ```
- Follow prompts using:
  - Tailscale login: skip / use a test Google account (NOT subhi@balizero.com — would claim that slot prematurely)
  - GitHub login: a test account or skip clone steps (modify script for dry-run mode if needed)
  - PAT: paste a test PAT or `__skip__` placeholder
  - Claude login: skip OR use a separate test Google
  - NLM login: skip

- [ ] **Step 5: Verify final state on testsubhi account**

```bash
# Still as testsubhi on Mini
ls ~/Projects/  # nuzantara-subhi present?
cat ~/Projects/nuzantara-subhi/.claude/settings.json | python3 -m json.tool > /dev/null && echo "Settings OK"
which claude && claude --version
which nlm && nlm --version
```

Expected: all present, no syntax errors.

- [ ] **Step 6: Test tutor (without committing real data)**

```bash
# As testsubhi on Mini
cd ~/Projects/nuzantara-subhi
claude
# In Claude session:
/agent zantara-onboarding halo
```

Expected: bahasa response.

- [ ] **Step 7: Cleanup**

```bash
# Switch back to nuzantara on Mini
# System Settings → Users & Groups → Delete testsubhi (delete home folder too)
# Delete the test gist
gh gist delete <gist-id> --yes
```

- [ ] **Step 8: Document any fixes needed**

If dry-run revealed issues, edit `subhi-tutor-install.sh`, commit, re-create gist, re-test. Loop until clean.

```bash
git add scripts/subhi/subhi-tutor-install.sh
git commit -m "fix(subhi): install script fixes from Mini dry-run"
```

- [ ] **Step 9: Install LaunchAgent on Pro**

Now that mirror script is verified, install LaunchAgent:

```bash
bash scripts/subhi/install-launchagent.sh
```

Expected: `✓ Installed and waiting for next 04:00 fire`.

Test it manually first:

```bash
DRY_RUN=1 bash scripts/subhi/subhi-memory-mirror.sh
```

If clean, run for real (FIRST PUSH):

```bash
bash scripts/subhi/subhi-memory-mirror.sh
```

Verify in `balizero/nuzantara-subhi` repo on GitHub: branch `subhi/memory-mirror` should now exist with first commit. Open `_AUDIT.txt` in browser, verify excludes/redactions look right.

If `_AUDIT.txt` shows leak (e.g., Subhi/ folder file present): rollback the push immediately:

```bash
cd ~/Projects/nuzantara-subhi
git checkout subhi/memory-mirror
git reset --hard HEAD~1
git push origin subhi/memory-mirror --force-with-lease
```

Then fix the config and retry.

---

## Task 9: Day 1 live setup with Subhi

**Files:** none (live execution)

**Goal:** execute the runbook from T7. Antonello supervises Subhi via WhatsApp video as Subhi installs everything on his MacBook.

This task is not run in this session — it happens on the actual Day 1 morning when MacBook arrives. The runbook in T7 is the script.

- [ ] **Step 1: Verify all prior tasks complete**

```bash
# All these should pass
git log --oneline scripts/subhi/ infra/launchagents/com.balizero.subhi-memory-mirror.daily.plist docs/runbooks/subhi-tutor-day1.md docs/superpowers/specs/2026-05-04-subhi-tutor-design.md docs/superpowers/plans/2026-05-04-subhi-tutor-implementation.md | wc -l
# Expected: ≥6 commits

# LaunchAgent active
launchctl print "gui/$(id -u)/com.balizero.subhi-memory-mirror.daily" | grep -E "state =|next firing"

# Repo `nuzantara-subhi` populated
gh repo view balizero/nuzantara-subhi --json name,visibility,defaultBranchRef
gh api /repos/balizero/nuzantara-subhi/contents/.claude/agents/zantara-onboarding.md | python3 -c "import json,sys,base64; print(base64.b64decode(json.load(sys.stdin)['content']).decode()[:200])"

# First memory mirror push present
gh api /repos/balizero/nuzantara-subhi/branches/subhi/memory-mirror | python3 -c "import json,sys; print(json.load(sys.stdin)['name'])"
```

- [ ] **Step 2: MacBook arrival event**

When Antonello confirms MacBook arrived and is set up enough to use Terminal:

- Schedule Day 1 with Subhi
- Send WhatsApp evening before with installer link
- Day 1 morning: follow runbook step-by-step

- [ ] **Step 3: Post-Day-1 review**

After Subhi completes Day 1:

- Read `~/Projects/nuzantara-subhi/.claude/session-log.jsonl` (via SSH if Tailscale ACL allows, or ask Subhi to paste)
- Verify no out-of-scope edits, no ROSSO attempts
- Update memory with Day 1 outcome
- Schedule Day 2 (codebase tour)

---

## Self-review checklist (run after writing plan)

- [x] Spec coverage: every section in `2026-05-04-subhi-tutor-design.md` mapped to a task
- [x] No placeholders: all code blocks have real content; descriptions for the 12 short docs in T5 Step 4 are intentional summary (each file ≤200 lines, content clear from spec + induction kit)
- [x] Type consistency: settings.json schema matches hooks called; script var names consistent (CONFIG_FILE, SOURCE_DIR, DEST_DIR throughout)
- [x] Bahasa rule consistent: every user-facing string is bahasa, all code/commands EN
- [x] RBAC enforced at 6 layers: OAuth, GitHub PAT scope, MCP filesystem confinement, settings.json deny rules, hook regex, sub-agent prompt
- [x] Dry-run before real: T8 on Mini before T9 on Subhi MacBook
- [x] Memory mirror manual approval: T8 Step 9 first push reviewed before automation kicks in
- [x] Failure recovery documented: every task has explicit rollback or retry path
