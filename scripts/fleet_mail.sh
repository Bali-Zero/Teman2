#!/bin/bash
# fleet_mail.sh — cross-machine "fleet mailbox" sender + live-session lister.
# Companion to infra/claude-hooks/mailbox_inject.py (the reader half).
#
# Usage:
#   fleet_mail.sh <host> --list
#   fleet_mail.sh <host> <session_id> [--key <k>] [--ttl <hours>] "<message text>"
#   fleet_mail.sh <host> broadcast --to <target> [--to <target> ...] --from <label> \
#       [--key <k>] [--ttl <hours>] [--urgent] "<message text>"
#   fleet_mail.sh <host> <session_id|broadcast> [flags] -   # message on stdin
#   fleet_mail.sh <host> retract --key <k>
#   <target> is host:<name> | lane:<name> | session:<id> | all
#   --from <label> (or FLEET_MAIL_FROM=<label>) is REQUIRED for `broadcast` —
#   direct mail keeps the old "fleet-watch" default. Label charset
#   [A-Za-z0-9._:@-]{1,64}. A sender is capped at FLEET_MAIL_MAX_PER_HOUR
#   (default 6) live broadcasts/hour; --urgent bypasses the cap for one send.
#
# retract (2026-09-02): sender-side cleanup — renames every LIVE broadcast
# matching --key to `.retracted-<ts>` (same self-cleaning pattern
# mailbox_inject.py already uses for `.superseded-`/`.expired-`/
# `.delivered-`, so a retracted file drops out of every future scan for
# every session, immediately, not just after --ttl expires). Broadcast-only
# by design: measured 2026-09-02 (34 live broadcasts on Pro sampled against
# `gh pr view`), 33/34 (97%) were stale `queue_unstick:<PR#>` pages for PRs
# already MERGED/CLOSED/no-longer-DIRTY — direct/session mail was not part
# of the measured disease. Best-effort + fail-open: a key that matches
# nothing (already delivered/expired/never sent) is a silent no-op, not an
# error — the caller (queue_unstick.py) must never let a cleanup step wall
# its actual work.
#
# <host> is local|pro|mini|air. local runs directly; the rest go via
# `ssh -o BatchMode=yes <host>`. Exits non-zero with a one-line reason on
# any failure. Honors NUZ_MAILBOX_DIR (mailbox root override) for tests.
#
# --key/--ttl (S3, 2026-08-27): write `key:`/`expires:` front-matter lines
# that infra/claude-hooks/mailbox_inject.py's collector reads to keep only
# the newest message per key and drop anything past its TTL. --ttl is
# integer hours, default 48. A broadcast sent without --key gets one
# derived automatically as sha1(first line of the message) — this is what
# lets a repeated page (e.g. queue_unstick's DIRTY-PR notices) supersede its
# own predecessor instead of piling up forever; a direct message without
# --key stays keyless (never deduped against another). Flags may appear
# anywhere after <session_id|broadcast>.
#
# --to <target> (ADDRESSED BROADCAST, 2026-09-18, Zero's order): a plain
# `broadcast` used to reach EVERY session on every machine — "una follia".
# --to is REPEATABLE and REQUIRED for `broadcast` (missing it dies with a
# usage line, exit 2); each value is `host:<name>` (short lowercase
# hostname), `lane:<name>`, `session:<id>`, or `all`. All values are joined
# with a comma into ONE `to:` front-matter line right after `from:` — the
# reader (mailbox_inject.py's `_collect_broadcast`) delivers only when a
# target matches it. Direct (session-dir) mail is unchanged: --to is
# accepted but has no effect there (already addressed by its directory).
#
# `air` is M5. The fleet has been three nodes since 2026-05-31, and this
# allowlist was still two — so no Pro or Mini session could reach M5 with the
# fleet tool at all, and the one that needed to on 2026-08-24 hand-delivered
# over raw ssh instead. The name is `air` and not `m5` deliberately: measured
# from both peers this turn, `ssh air` resolves to Air-M5 from Pro AND from
# Mini, while `ssh m5` resolves only from Pro and dies on Mini with "could not
# resolve hostname". An alias that works from one peer and not the other is a
# lane that fails on exactly one machine — the shape this repo already has a
# scar family for.
#
# CORRECTION 2026-08-26: the paragraph above records a measurement that has
# since DECAYED. `ssh air` points at `Air-M5.local` (mDNS) and from Pro it now
# dies with "Could not resolve hostname air-m5.local" — so `fleet_mail.sh air`
# was dead from Pro, silently, while its own comment asserted the opposite.
# mDNS does not survive a peer moving off the LAN, and this repo already
# documents that exact shape for Mini ("LAN/mDNS Mini-Pro2.local often
# NXDOMAIN; this alias is the verified-working Tailscale path" — the
# `mini-remote` stanza in ~/.ssh/config). The cure is not a new hardcoded
# hostname: it is to stop trusting ONE route. ssh_target() below probes the
# primary alias and falls back to the Tailscale one, so the tool works from
# whichever side of the network the peer happens to be on.
set -uo pipefail
die() { echo "fleet_mail.sh: $*" >&2; exit 1; }
HOST="${1:-}"
case "$HOST" in
    local|pro|mini|air) ;;
    *) die "unknown host '$HOST' (want local|pro|mini|air)" ;;
esac
shift || die "missing <host>"

# Extract optional --key/--ttl/--to anywhere in the remaining args (order-
# independent, all take a value; --to is repeatable) BEFORE any positional
# parsing below, so `--list`, <session_id|broadcast> and <message> parsing
# are unaffected.
MSG_KEY=""
MSG_TTL_HOURS="48"
TO_TARGETS=()
FROM_ARG=""
URGENT=0
_rest=()
while [ $# -gt 0 ]; do
    case "$1" in
        --key) MSG_KEY="${2:-}"; shift 2 || die "--key needs a value" ;;
        --ttl) MSG_TTL_HOURS="${2:-}"; shift 2 || die "--ttl needs a value" ;;
        --to) TO_TARGETS+=("${2:-}"); shift 2 || die "--to needs a value" ;;
        --from) FROM_ARG="${2:-}"; shift 2 || die "--from needs a value" ;;
        --urgent) URGENT=1; shift ;;
        *) _rest+=("$1"); shift ;;
    esac
done
set -- "${_rest[@]}"
# IDENTITY + RATE CAP (2026-09-18, Zero's order): a plain `broadcast` with no
# sender label used to write `from: <host>:fleet-watch` for EVERY anonymous
# session on a machine (measured 2026-09-18: 368/416 live broadcasts on M5
# carried exactly that label) -- indistinguishable senders, so nobody could
# tell who to mute. `--from <label>` (or FLEET_MAIL_FROM env) is now REQUIRED
# for `broadcast` (checked below, after the --to check); direct (session-dir)
# mail is UNCHANGED and keeps the `fleet-watch` default. FLEET_MAIL_MAX_PER_HOUR
# (default 6) caps how many LIVE broadcasts one label may have sent in the
# last hour -- see PY_SEND below for the count + refusal (exit 3), overridable
# per-send with --urgent.
FLEET_MAIL_MAX_PER_HOUR="${FLEET_MAIL_MAX_PER_HOUR:-6}"
[[ "$FLEET_MAIL_MAX_PER_HOUR" =~ ^[0-9]+$ ]] || die "invalid FLEET_MAIL_MAX_PER_HOUR '$FLEET_MAIL_MAX_PER_HOUR' (want integer)"

# Resolve <host> to an ssh target that actually answers. The primary alias may
# be mDNS-backed and unresolvable when the peer is off-LAN (see CORRECTION
# above); each host therefore declares a Tailscale-backed fallback alias that
# already exists in ~/.ssh/config. Probing costs one cheap `true` round-trip
# and ONLY on the primary — the fallback is tried only after the primary fails,
# so the common (on-LAN) path is unchanged. Judged by the probe's RETURN CODE,
# never by its output: a resolver failure prints to stderr and would otherwise
# look like success to a stdout-reading caller.
ssh_fallback_for() {
    case "$1" in
        air)  echo "air-ts" ;;
        mini) echo "mini-remote" ;;
        *)    echo "" ;;
    esac
}
ssh_target() {
    local host="$1" fb
    if ssh -o BatchMode=yes -o ConnectTimeout=6 "$host" true 2>/dev/null; then
        echo "$host"; return 0
    fi
    fb="$(ssh_fallback_for "$host")"
    if [ -n "$fb" ] && ssh -o BatchMode=yes -o ConnectTimeout=6 "$fb" true 2>/dev/null; then
        echo "$fb"; return 0
    fi
    return 1
}
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
        SSH_HOST="$(ssh_target "$HOST")" \
            || die "no reachable ssh route for '$HOST' (tried '$HOST' and '$(ssh_fallback_for "$HOST")')"
        ssh -o BatchMode=yes -o ConnectTimeout=8 "$SSH_HOST" bash -s <<< "$LIST_SCRIPT" \
            || die "ssh list on $HOST (via $SSH_HOST) failed"
    fi
    exit 0
fi
# ---- retract (sender-side cleanup, broadcast dir only — see header) ----
if [ "${1:-}" = "retract" ]; then
    MSG_KEY="$(printf '%s' "$MSG_KEY" | tr -cd 'A-Za-z0-9:_./-')"
    [ -n "$MSG_KEY" ] || die "retract needs --key <k>"
    read -r -d '' PY_RETRACT <<'PYEOF' || true
import glob, os, sys, time
root = os.environ.get("NUZ_MAILBOX_DIR") or os.path.expanduser("~/.nuzantara-mailbox")
key = sys.argv[1]
bdir = os.path.join(root, "broadcast")
ts = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
n = 0
for path in sorted(glob.glob(os.path.join(bdir, "*.md"))):
    if os.path.islink(path):  # containment: never follow a symlinked message
        continue
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            head = fh.read(2048)  # front matter only, never the full body
    except OSError:
        continue
    found_key = ""
    for line in head.split("\n", 10)[:10]:
        if not line.strip() or ":" not in line:
            break
        k, _, v = line.partition(":")
        if k.strip().lower() == "key":
            found_key = v.strip()
            break
    if found_key != key:
        continue
    try:
        os.rename(path, path + ".retracted-" + ts)
        n += 1
    except OSError:
        pass  # best-effort: a rename failure leaves the file live, re-tried by --ttl instead
print(n)
PYEOF
    if [ "$HOST" = "local" ]; then
        N="$(python3 -c "$PY_RETRACT" "$MSG_KEY")" || die "local retract failed"
    else
        B64="$(printf '%s' "$PY_RETRACT" | base64 | tr -d '\n')"
        POP_AND_EXEC='import base64,sys;b=sys.argv.pop(1);exec(base64.b64decode(b).decode())'
        REMOTE_CMD="python3 -c \"$POP_AND_EXEC\" '$B64' '$MSG_KEY'"
        SSH_HOST="$(ssh_target "$HOST")" \
            || die "no reachable ssh route for '$HOST' (tried '$HOST' and '$(ssh_fallback_for "$HOST")')"
        N="$(ssh -o BatchMode=yes -o ConnectTimeout=8 "$SSH_HOST" "$REMOTE_CMD")" \
            || die "ssh retract on $HOST (via $SSH_HOST) failed"
    fi
    echo "retracted $N message(s) matching key '$MSG_KEY' on $HOST${SSH_HOST:+ via $SSH_HOST}"
    exit 0
fi
# ---- send ----
SESSION="${1:-}"
[ -n "$SESSION" ] || die "missing <session_id|broadcast>"
[[ "$SESSION" =~ $SESSION_ID_RE ]] || die "invalid session id '$SESSION'"
if [ "$SESSION" = "broadcast" ] && [ ${#TO_TARGETS[@]} -eq 0 ]; then
    echo "fleet_mail.sh: broadcast requires --to <target> (host:<name>|lane:<name>|session:<id>|all) — a broadcast with no address reaches EVERY session on every machine" >&2
    exit 2
fi
if [ "$SESSION" = "broadcast" ] && [ -z "$FROM_ARG" ] && [ -z "${FLEET_MAIL_FROM:-}" ]; then
    echo "fleet_mail.sh: broadcast requires --from <label> or FLEET_MAIL_FROM=<label> — every broadcast must say who is sending it" >&2
    exit 2
fi
shift
MSG_ARG="${1:-}"
[ -n "$MSG_ARG" ] || die "missing <message> (or '-' for stdin)"
if [ "$MSG_ARG" = "-" ]; then
    BODY="$(cat)"
else
    BODY="$MSG_ARG"
fi
# Sender label (2026-09-18): --from wins over FLEET_MAIL_FROM wins over the
# old "fleet-watch" default (broadcast can never reach here with neither set
# -- see the exit-2 check above). Sanitized to the SAME charset
# infra/claude-hooks/mailbox_inject.py's SENDER_UNSAFE_RE enforces on read
# ([^A-Za-z0-9._:@-]) and capped at its MAX_SENDER_LEN(64) -- stripped, never
# rejected outright, matching the existing --key/--to sanitization posture.
SENDER_LABEL="${FROM_ARG:-${FLEET_MAIL_FROM:-fleet-watch}}"
SENDER_LABEL="$(printf '%s' "$SENDER_LABEL" | tr -cd 'A-Za-z0-9._:@-' | cut -c1-64)"
RAW_FROM="$(hostname -s 2>/dev/null || echo unknown):${SENDER_LABEL}"
FROM_LABEL="$(printf '%s' "$RAW_FROM" | tr -cd 'A-Za-z0-9:_.@-')"

# Join repeatable --to values into ONE comma-separated `to:` front-matter
# value; sanitized to the same safe charset as MSG_KEY/FROM_LABEL for the
# same reason (embedded unquoted in the remote command text below).
TO_JOINED=""
if [ ${#TO_TARGETS[@]} -gt 0 ]; then
    _to_csv="$(IFS=,; echo "${TO_TARGETS[*]}")"
    TO_JOINED="$(printf '%s' "$_to_csv" | tr -cd 'A-Za-z0-9:_.,-')"
fi

# S3 state-keyed front matter: a broadcast with no explicit --key gets one
# derived from its own content (sha1 of the first line) so a repeated page
# about the same subject (e.g. queue_unstick's "PR #N is DIRTY") supersedes
# its predecessor instead of piling up; a direct message stays keyless
# unless --key was given. Sanitized to a safe charset for the same reason
# FROM_LABEL is — it is embedded unquoted in the remote command text below.
if [ -z "$MSG_KEY" ] && [ "$SESSION" = "broadcast" ]; then
    FIRST_LINE="${BODY%%$'\n'*}"
    MSG_KEY="$(printf '%s' "$FIRST_LINE" | shasum -a 1 | awk '{print $1}')"
fi
MSG_KEY="$(printf '%s' "$MSG_KEY" | tr -cd 'A-Za-z0-9:_./-')"
[[ "$MSG_TTL_HOURS" =~ ^[0-9]+$ ]] || die "invalid --ttl '$MSG_TTL_HOURS' (want integer hours)"
MSG_EXPIRES="$(date -u -v+"${MSG_TTL_HOURS}"H +%Y-%m-%dT%H:%M:%SZ)"

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
import glob, os, sys, time
root = os.environ.get("NUZ_MAILBOX_DIR") or os.path.expanduser("~/.nuzantara-mailbox")
session, filename, from_label = sys.argv[1], sys.argv[2], sys.argv[3]
msg_key = sys.argv[4] if len(sys.argv) > 4 else ""
msg_expires = sys.argv[5] if len(sys.argv) > 5 else ""
to_targets = sys.argv[6] if len(sys.argv) > 6 else ""
max_per_hour = int(sys.argv[7]) if len(sys.argv) > 7 and sys.argv[7] else 0
urgent = (sys.argv[8] if len(sys.argv) > 8 else "0") == "1"
# Owner-only root is the whole security story (messages become assistant-
# visible context) -- create it 0700, and re-tighten it if some earlier
# run left it wider (os.makedirs' mode is not honored on every platform).
os.makedirs(root, mode=0o700, exist_ok=True)
try:
    os.chmod(root, 0o700)
except OSError:
    pass
target = os.path.join(root, "broadcast") if session == "broadcast" else os.path.join(root, session)
os.makedirs(target, exist_ok=True)
for d in (root, target):  # owner-only: the root dir IS the security boundary
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass
# Body is read BEFORE the rate-cap decision (never after) so a refused send
# still drains stdin -- a piped-but-unread body risks SIGPIPE on the sender
# side once this process exits, on local AND remote (the message is on the
# wire either way).
body = sys.stdin.buffer.read()
# RATE CAP (2026-09-18): count LIVE broadcasts (bare *.md -- a retracted/
# expired/superseded/muted/unaddressed/skipped file already carries a
# suffix AFTER .md and so never matches this glob) from THIS label in the
# last hour. Front matter only (<=2048 bytes), same bounded-read posture as
# retract's own key scan above -- a message body is never read here.
if session == "broadcast" and max_per_hour > 0 and not urgent:
    cutoff = time.time() - 3600
    count = 0
    for path in glob.glob(os.path.join(target, "*.md")):
        if os.path.islink(path):  # containment, same posture as retract
            continue
        try:
            st = os.stat(path)
        except OSError:
            continue
        if st.st_mtime < cutoff:
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                head = fh.read(2048)
        except OSError:
            continue
        sender = ""
        for line in head.split("\n", 10)[:10]:
            if not line.strip() or ":" not in line:
                break
            k, _, v = line.partition(":")
            if k.strip().lower() == "from":
                sender = v.strip()
                break
        if sender == from_label:
            count += 1
    if count >= max_per_hour:
        print(
            "fleet_mail.sh: sender '" + from_label + "' already sent " + str(count) +
            " broadcast(s) in the last hour (cap " + str(max_per_hour) +
            "); refusing (use --urgent to override)",
            file=sys.stderr,
        )
        sys.exit(3)
tmp = os.path.join(root, ".tmp-" + filename + "." + str(os.getpid()))
header = "from: " + from_label + "\n"
if to_targets:
    header += "to: " + to_targets + "\n"
if msg_key:
    header += "key: " + msg_key + "\n"
if msg_expires:
    header += "expires: " + msg_expires + "\n"
if urgent:
    header += "urgent: true\n"
header += "\n"
with open(tmp, "wb") as fh:
    fh.write(header.encode())
    fh.write(body)
os.replace(tmp, os.path.join(target, filename))
PYEOF

if [ "$HOST" = "local" ]; then
    printf '%s' "$BODY" | python3 -c "$PY_SEND" "$SESSION" "$FILENAME" "$FROM_LABEL" "$MSG_KEY" "$MSG_EXPIRES" "$TO_JOINED" "$FLEET_MAIL_MAX_PER_HOUR" "$URGENT"
    SEND_RC=$?
else
    # Remote command is built as ONE argv string for ssh (never `-s`/stdin),
    # so the remote shell's stdin stays untouched and forwards straight to
    # python's sys.stdin — this is what fixes the CRITICAL bug above. The
    # program is base64-embedded to sidestep quoting entirely (session/
    # filename/from-label are already charset-validated, so single-quoting
    # them is safe — none can contain a single quote).
    B64="$(printf '%s' "$PY_SEND" | base64 | tr -d '\n')"
    POP_AND_EXEC='import base64,sys;b=sys.argv.pop(1);exec(base64.b64decode(b).decode())'
    REMOTE_CMD="python3 -c \"$POP_AND_EXEC\" '$B64' '$SESSION' '$FILENAME' '$FROM_LABEL' '$MSG_KEY' '$MSG_EXPIRES' '$TO_JOINED' '$FLEET_MAIL_MAX_PER_HOUR' '$URGENT'"
    SSH_HOST="$(ssh_target "$HOST")" \
        || die "no reachable ssh route for '$HOST' (tried '$HOST' and '$(ssh_fallback_for "$HOST")')"
    printf '%s' "$BODY" | ssh -o BatchMode=yes -o ConnectTimeout=8 "$SSH_HOST" "$REMOTE_CMD"
    SEND_RC=$?
fi
# Exit 3 (rate-cap refusal, see PY_SEND) is distinct from a plain delivery
# failure and must propagate as-is, not collapse into die()'s exit 1 -- a
# caller checks specifically for 3 to distinguish "capped" from "broken".
if [ "$SEND_RC" -eq 3 ]; then
    exit 3
elif [ "$SEND_RC" -ne 0 ]; then
    die "delivery to $HOST:$SESSION failed (rc=$SEND_RC)${SSH_HOST:+ via $SSH_HOST}"
fi
echo "delivered to $HOST:$SESSION ($FILENAME)${SSH_HOST:+ via $SSH_HOST}"
