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

# Delivery logic as a Python program (never a shell script read via `bash -s`
# from stdin): a script sourced from stdin and a `cat` reading MORE stdin
# inside that same script cannot safely share one ssh channel — bash buffers
# ahead when parsing a piped script and silently eats bytes meant for the
# later `cat` (found by refuter round 1: only `.tmp-*` ever landed, `mv`
# never ran). Passing this program via `-c` (argv, not stdin) keeps stdin
# free end-to-end for the message BODY, identically for local and remote.
read -r -d '' PY_SEND <<'PYEOF' || true
import os, sys
root = os.environ.get("NUZ_MAILBOX_DIR") or os.path.expanduser("~/.nuzantara-mailbox")
session, filename, from_label = sys.argv[1], sys.argv[2], sys.argv[3]
target = os.path.join(root, "broadcast") if session == "broadcast" else os.path.join(root, session)
os.makedirs(target, exist_ok=True)
try:
    os.chmod(target, 0o700)
except OSError:
    pass
body = sys.stdin.buffer.read()
tmp = os.path.join(root, ".tmp-" + filename + "." + str(os.getpid()))
with open(tmp, "wb") as fh:
    fh.write(("from: " + from_label + "\n\n").encode())
    fh.write(body)
os.replace(tmp, os.path.join(target, filename))
PYEOF

if [ "$HOST" = "local" ]; then
    printf '%s' "$BODY" | python3 -c "$PY_SEND" "$SESSION" "$FILENAME" "$FROM_LABEL" \
        || die "local delivery to $SESSION failed"
else
    # Remote command is built as ONE argv string for ssh (never `-s`/stdin),
    # so the remote shell's stdin stays untouched and forwards straight to
    # python's sys.stdin — this is what fixes the CRITICAL bug above. The
    # program is base64-embedded to sidestep quoting entirely (session/
    # filename/from-label are already charset-validated, so single-quoting
    # them is safe — none can contain a single quote).
    B64="$(printf '%s' "$PY_SEND" | base64 | tr -d '\n')"
    POP_AND_EXEC='import base64,sys;b=sys.argv.pop(1);exec(base64.b64decode(b).decode())'
    REMOTE_CMD="python3 -c \"$POP_AND_EXEC\" '$B64' '$SESSION' '$FILENAME' '$FROM_LABEL'"
    printf '%s' "$BODY" | ssh -o BatchMode=yes -o ConnectTimeout=8 "$HOST" "$REMOTE_CMD" \
        || die "ssh delivery to $HOST:$SESSION failed"
fi
echo "delivered to $HOST:$SESSION ($FILENAME)"
