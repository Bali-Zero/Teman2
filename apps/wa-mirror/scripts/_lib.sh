#!/usr/bin/env bash
# Shared helpers for wa-mirror single-account-per-process launcher.

set -eo pipefail

WA_MIRROR_DIR="$HOME/Desktop/nuzantara/apps/wa-mirror"
ACCOUNTS_JSON="$HOME/.wa-mirror.accounts.json"
LOG_DIR="/tmp/wa-mirror-logs"
PID_DIR="/tmp/wa-mirror-pids"
mkdir -p "$LOG_DIR" "$PID_DIR"

# Returns E.164 for a given employee name (lowercase), or empty if not found.
get_e164() {
    local name="$1"
    python3 -c "
import json, sys
data = json.load(open('$ACCOUNTS_JSON'))
for a in data['accounts']:
    if a['name'].lower() == '$name'.lower():
        print(a['e164']); break
" 2>/dev/null || true
}

# Returns "label name e164 role" rows for all accounts.
list_accounts() {
    python3 -c "
import json
data = json.load(open('$ACCOUNTS_JSON'))
for a in data['accounts']:
    print(f\"{a['name']:10} {a['e164']:20} {a['label']:10} {a['role']}\")
" 2>/dev/null
}

# Returns JSON object {e164: name} for ACCOUNT_NAMES env.
get_account_names_for() {
    local e164="$1"
    local name="$2"
    python3 -c "import json; print(json.dumps({'$e164': '$name'}))"
}

# Returns JSON object {e164: email} for ACCOUNT_EMAILS env (FIX 4 2026-05-26).
# Empty if no email set for that account.
get_account_email_for() {
    local e164="$1"
    python3 -c "
import json
data = json.load(open('$ACCOUNTS_JSON'))
for a in data['accounts']:
    if a['e164'] == '$e164':
        email = a.get('email', '').strip().lower()
        if email:
            print(json.dumps({'$e164': email}))
        break
" 2>/dev/null || true
}

# Validate employee name against roster.
validate_name() {
    local name="$1"
    local e164
    e164=$(get_e164 "$name")
    if [ -z "$e164" ]; then
        echo "❌ Employee '$name' not found in $ACCOUNTS_JSON"
        echo "Valid names:"
        list_accounts | awk '{print "  - " $1}'
        return 1
    fi
    echo "$e164"
}

# W77 (2026-06-14): per-account lifecycle gate. Reads optional fields from the
# roster so the supervisor knows a session's INTENDED state instead of deducing
# it from "is there a session dir / is the process alive". Closes the W77
# meta-pattern (antibodies need a declarative source of truth, not inference):
#   expected_status: ACTIVE (default) | STANDBY | DECOMMISSIONED
#   assigned_node:   hostname this account should run on (default: any)
# The roster ($ACCOUNTS_JSON) stays HOME-only (PII: e164+email) — only the
# READING logic lives in git. See accounts.example.json for the schema.
get_expected_status() {
    local name="$1"
    python3 -c "
import json
data = json.load(open('$ACCOUNTS_JSON'))
for a in data['accounts']:
    if a['name'].lower() == '$name'.lower():
        print((a.get('expected_status') or 'ACTIVE').upper()); break
else:
    print('ACTIVE')
" 2>/dev/null || echo ACTIVE
}

get_assigned_node() {
    local name="$1"
    python3 -c "
import json
data = json.load(open('$ACCOUNTS_JSON'))
for a in data['accounts']:
    if a['name'].lower() == '$name'.lower():
        print(a.get('assigned_node') or ''); break
" 2>/dev/null || true
}

pid_file()      { echo "$PID_DIR/$1.pid"; }
log_file()      { echo "$LOG_DIR/$1.log"; }
session_dir()   { echo "$WA_MIRROR_DIR/sessions/$1"; }
