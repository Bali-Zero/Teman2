#!/bin/bash
# fleet_mail.sh — cross-machine "fleet mailbox" sender + live-session lister.
# Companion to infra/claude-hooks/mailbox_inject.py (the reader half).
#
# Usage:
#   fleet_mail.sh <host> --list
#   fleet_mail.sh <host> <session_id|broadcast> "<message text>"
#   fleet_mail.sh <host> <session_id|broadcast> -        # message on stdin
#
# <host> is local|pro|mini. local runs directly; pro/mini go via
# `ssh -o BatchMode=yes <host>`. Exits non-zero with a one-line reason on
# any failure. Honors NUZ_MAILBOX_DIR (mailbox root override) for tests.
set -uo pipefail
die() { echo "fleet_mail.sh: $*" >&2; exit 1; }
HOST="${1:-}"
case "$HOST" in
    local|pro|mini) ;;
    *) die "unknown host '$HOST' (want local|pro|mini)" ;;
esac
shift || die "missing <host>"
SESSION_ID_RE='^([A-Za-z0-9_-]{8,80}|broadcast)$'
# ---- read-only session lister (executes on the target, local or remote) ----
read -r -d '' LIST_SCRIPT <<'REMOTE' || true
python3 - <<'PY'
import glob, json, os, time
now = time.time()
rows = []
for path in glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl")):
    try:
        st = os.stat(path)
    except OSError:
        continue
    if now - st.st_mtime > 360 * 60:
        continue
    sid = os.path.splitext(os.path.basename(path))[0]
    mtime = time.strftime("%H:%M", time.localtime(st.st_mtime))
    prompt, mandate = "", ""
    try:
        with open(path, "r", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i >= 40:
                    break
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("type") != "user":
                    continue
                content = rec.get("message", {}).get("content", rec.get("content"))
                text = None
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text")
                            break
                if not text:
                    continue
                if not prompt:
                    prompt = text
                if "MANDATE" in text and not mandate:
                    mandate = text
    except Exception:
        pass
    snippet = (mandate or prompt)[:100].replace("\n", " ")
    rows.append((sid, mtime, snippet))
rows.sort(key=lambda r: r[1])
for sid, mtime, snippet in rows:
    print(f"{sid} {mtime} {snippet}")
PY
REMOTE
if [ "${1:-}" = "--list" ]; then
    if [ "$HOST" = "local" ]; then
        bash -c "$LIST_SCRIPT" || die "local list failed"
    else
        ssh -o BatchMode=yes -o ConnectTimeout=8 "$HOST" bash -s <<< "$LIST_SCRIPT" \
            || die "ssh list on $HOST failed"
    fi
    exit 0
fi
# ---- send ----
SESSION="${1:-}"
[ -n "$SESSION" ] || die "missing <session_id|broadcast>"
[[ "$SESSION" =~ $SESSION_ID_RE ]] || die "invalid session id '$SESSION'"
shift
MSG_ARG="${1:-}"
[ -n "$MSG_ARG" ] || die "missing <message> (or '-' for stdin)"
if [ "$MSG_ARG" = "-" ]; then
    BODY="$(cat)"
else
    BODY="$MSG_ARG"
fi
# Sanitize FROM label to a safe charset before it is embedded in remote command text.
RAW_FROM="$(hostname -s 2>/dev/null || echo unknown):${FLEET_MAIL_FROM:-fleet-watch}"
FROM_LABEL="$(printf '%s' "$RAW_FROM" | tr -cd 'A-Za-z0-9:_.-')"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
FILENAME="${TS}-$(printf '%04x' $((RANDOM % 65536))).md"
# Literal (quoted heredoc): FM_SESSION/FM_FILENAME/FM_FROM are env vars set by
# the caller below, never string-interpolated into this text.
read -r -d '' SEND_SCRIPT <<'REMOTE_SEND' || true
set -uo pipefail
ROOT="${NUZ_MAILBOX_DIR:-$HOME/.nuzantara-mailbox}"
if [ "$FM_SESSION" = "broadcast" ]; then TARGET="$ROOT/broadcast"; else TARGET="$ROOT/$FM_SESSION"; fi
mkdir -p "$TARGET" || exit 1
chmod 700 "$TARGET" 2>/dev/null || true
TMP="$ROOT/.tmp-$FM_FILENAME.$$"
{ printf 'from: %s\n\n' "$FM_FROM"; cat; } > "$TMP" || exit 1
mv "$TMP" "$TARGET/$FM_FILENAME" || exit 1
REMOTE_SEND
if [ "$HOST" = "local" ]; then
    printf '%s' "$BODY" | FM_SESSION="$SESSION" FM_FILENAME="$FILENAME" FM_FROM="$FROM_LABEL" \
        bash -c "$SEND_SCRIPT" || die "local delivery to $SESSION failed"
else
    { printf '%s\n' "$SEND_SCRIPT"; printf '%s' "$BODY"; } | \
        ssh -o BatchMode=yes -o ConnectTimeout=8 "$HOST" \
            "FM_SESSION='$SESSION' FM_FILENAME='$FILENAME' FM_FROM='$FROM_LABEL' bash -s" \
        || die "ssh delivery to $HOST:$SESSION failed"
fi
echo "delivered to $HOST:$SESSION ($FILENAME)"
