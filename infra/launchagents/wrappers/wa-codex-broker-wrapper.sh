#!/bin/sh
# wa-codex-broker-wrapper.sh — launchd payload for com.balizero.wa-codex-broker.
#
# Runs as the login-less user `zantara-codex` on Pro (spec §4.1,
# research/operations/2026-08-19-bot-chatgpt-provider-broker-spec.md). The
# LIVE copy is /usr/local/libexec/wa-codex-broker-wrapper.sh — ROOT-OWNED,
# outside any user-writable $HOME, per the declared-pairs charter for
# system-domain LaunchDaemon payloads (fw-guard precedent 2026-08-14): the
# process runs AS zantara-codex, so a compromised zantara-codex identity
# gains no privilege by editing a home-dir wrapper, but a root-owned payload
# denies it PERSISTENCE — it cannot rewrite what launchd will execute at
# the next restart. Same for the runtime tree in /usr/local/lib. Placed by
# scripts/provision_zantara_codex.sh; the pair is declared in
# infra/home-fork/declared-pairs.json (superscar #1 — re-run provisioning
# after changing this file, the merge alone leaves the live copy stale).
#
# Shape notes (scar-family antidotes, load-bearing):
# - `exec` into the daemon's REAL blocking loop under KeepAlive (family #7:
#   launchd monitors the python process itself, no restart cycling).
# - Guarded env-file source — never a bare `. file || true` under errexit
#   (W108: sh treats a failed `.` as a special-builtin exit; the guard
#   must come BEFORE the source, as an if).
# - Absolute interpreter path (W108: a PATH-resolved python is the failure
#   mode the daemon would then have to report on).
# - The env file carries WA_BROKER_KEY: 0600, never echoed, never on argv
#   (family #4 / W115).
# - Dedicated-binary pin (scripts/install_wa_codex_pinned.sh, spec v3, D5):
#   parsed BEFORE the daemon env is sourced, using ONLY shell builtins
#   (`read`, `case`, `[`, parameter expansion — no `expr`, no PATH lookup),
#   so nothing the env file could set (a redirected PATH, a shadowed
#   `expr`, an alias) can reach the pin validators. #7340's wrapper parsed
#   the pin AFTER sourcing and validated with `expr`, which is itself
#   PATH-resolved (F5, SUSPENDED PR #7340: `PATH=/opt/homebrew/bin:/usr/bin`
#   in the env makes macOS resolve `expr` to `/bin/expr` — verified, not
#   the bug — but any env-supplied PATH is untrusted input to a validator
#   that runs pre-privilege-boundary). The pinned binary PATH is DERIVED
#   from a literal root constant (PINNED_CODEX_ROOT), never read from the
#   pin file itself, so there is no path string to validate and so no path
#   validator to get wrong. A present-but-invalid pin fails closed (exit
#   78); legacy (env-supplied WA_CODEX_BIN) applies ONLY when the pin file
#   is absent. This closes the stale-or-wrong-DATA class, not a hostile
#   zantara-codex sourcing its own env (spec §8 #2) — that boundary is the
#   root-owned, non-writable pinned tree (installer, D1/D3), not this file.
#
# pin-protocol: wa-codex-pin/1

set -u

HOME_DIR="/Users/zantara-codex"
RUNTIME_DIR="/usr/local/lib/wa-codex-broker"
ENV_FILE="$HOME_DIR/.wa-codex-broker.env"
VENV_PY="$RUNTIME_DIR/.venv/bin/python3"
TAG="wa-codex-broker-wrapper"
ORGAN_ID="pro.wa_codex_broker"
SIDECAR_DIR="$HOME_DIR/.organism/last_seen"

# Dedicated codex pin (D5). Both literals, never built from $RUNTIME_DIR or
# any other name the sourced daemon env could reassign — the pin parse
# below runs BEFORE that source point, but keeping these as their own
# top-level constants (rather than string-concatenated from RUNTIME_DIR)
# keeps the two independently patchable in tests and independently
# reviewable on disk.
CODEX_PIN_FILE="/usr/local/lib/wa-codex-broker/codex-pin.env"
PINNED_CODEX_ROOT="/usr/local/lib/wa-codex-broker/codex"

# G2_heartbeat — sidecar at start and on every refusal exit. The RUNNING
# daemon's liveness ground truth is the SERVER-side claim-poll gauge
# (BROKER_ABSENT within DEFAULT_ABSENT_AFTER_S), not this file — the
# registry entry carries expected_hb_seconds=0 accordingly; this sidecar
# exists so a refusal exit is distinguishable from never-having-run.
heartbeat() { # $1 status, $2 note
    mkdir -p "$SIDECAR_DIR" 2>/dev/null || return 0
    printf '{"ts":"%s","status":"%s","note":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" > "$SIDECAR_DIR/$ORGAN_ID.json"
}

# --- pin-file version validator (builtins only — no `expr`, no PATH lookup) ---
# Marker-wrapped (N6, gate 2026-09-26) so PR-2's installer test
# (test_semver_validators_agree) can extract this exact predicate text
# instead of re-typing a copy.
# >>> _is_semver
_is_semver() {
    case $1 in
        *[!0-9.]*|.*|*.|*..*|*.*.*.*) return 1 ;;
        *.*.*) return 0 ;;
    esac
    return 1
}
# <<< _is_semver

if [ ! -f "$ENV_FILE" ]; then
    echo "$TAG: env file missing: $ENV_FILE - refusing to start (run provisioning)" >&2
    heartbeat "refused" "env file missing"
    exit 78 # EX_CONFIG
fi
if grep -q "__FILL_ME__" "$ENV_FILE"; then
    echo "$TAG: env file still carries __FILL_ME__ placeholders - refusing to start" >&2
    heartbeat "refused" "env placeholders unfilled"
    exit 78
fi

# Pin parse — BEFORE the daemon env exists in this shell (D5). A symlinked
# or otherwise non-regular pin file (directory, device, FIFO) is PRESENT-
# BUT-INVALID, never treated as absent: `[ -L ]` (lstat) is checked ahead
# of `[ -e ]` (stat, follows symlinks) so a symlink can never pass as a
# plain file, and `[ -e ]` (path exists at all) is checked separately from
# `[ -f ]` (regular file) so a directory or /dev/null at this path fails
# closed instead of silently reading as "no pin here" (spalla review
# 2026-09-26: the original `-L`/`-f`/else fell through non-regular,
# non-symlink paths straight into the legacy `else` branch). Fail-closed on
# any violation; legacy applies ONLY when nothing exists at this path.
#
# The two resolved values are carried across the `. "$ENV_FILE"` below as
# POSITIONAL PARAMETERS ($1/$2, set via `set --` right before the source),
# never as named shell variables — a `KEY=value` line in the daemon env
# file (spalla review 2026-09-26: reproduced with a plain assignment, no
# alias or function needed) can redefine ANY named variable once `set -a`
# exports it, but it cannot touch $1/$2 without the env file literally
# invoking the `set --` command, which no env file in this wrapper's actual
# `KEY=value` format ever does. A daemon env file deliberately rewritten to
# run shell commands is full code execution as zantara-codex regardless
# (spec §8 #2, out of scope by design) — this closes the DATA-only,
# accidental-or-stale-value class, which is F5's actual scope.
# RUNTIME_DIR not searchable (gate 2026-09-26): `[ -e "$CODEX_PIN_FILE" ]`
# cannot traverse an unsearchable ancestor, so a pin file that genuinely
# exists behind a broken directory mode is indistinguishable, at that test
# alone, from a pin file that was never installed — and the latter is the
# ONLY case legacy is allowed to cover. RUNTIME_DIR existing-but-not-
# searchable is a broken/obstructed state, never legitimate absence, so it
# fails closed here, BEFORE the daemon env (which could itself claim a
# different RUNTIME_DIR) is ever sourced. A RUNTIME_DIR that does not exist
# at all is the genuine "nothing installed yet" case and falls through to
# legacy exactly as before.
if [ -d "$RUNTIME_DIR" ] && [ ! -x "$RUNTIME_DIR" ]; then
    echo "$TAG: pin directory not searchable: $RUNTIME_DIR - refusing (cannot verify pin absence)" >&2
    heartbeat "refused" "pin invalid"
    exit 78
fi

_wcbw_pin_ver=""
_wcbw_pin_bin=""
if [ -L "$CODEX_PIN_FILE" ]; then
    echo "$TAG: pin file is a symlink, refusing: $CODEX_PIN_FILE" >&2
    heartbeat "refused" "pin invalid"
    exit 78
elif [ -e "$CODEX_PIN_FILE" ]; then
    if [ ! -f "$CODEX_PIN_FILE" ]; then
        echo "$TAG: pin file is not a regular file: $CODEX_PIN_FILE" >&2
        heartbeat "refused" "pin invalid"
        exit 78
    fi
    if [ ! -r "$CODEX_PIN_FILE" ]; then
        echo "$TAG: pin file is not readable: $CODEX_PIN_FILE" >&2
        heartbeat "refused" "pin invalid"
        exit 78
    fi
    # NUL-byte guard (spalla review 2026-09-26): a shell variable cannot
    # represent a NUL byte at all, so `read -r` alone silently truncates a
    # line AT its first NUL and the truncated remainder can slip past the
    # "exactly one line" count below as if it were never there. `read -d
    # ''` (NUL as the delimiter) is a BASH extension — dash rejects it
    # outright (`read: Illegal option -d`, gate 2026-09-26 correction of
    # this comment's prior claim that dash also supports it) — still a
    # shell BUILTIN, not an external tool, so "builtins only" still holds;
    # this wrapper's only two actual runtimes are macOS's own `/bin/sh`
    # (itself bash 3.2 in a POSIX-ish mode) and macos-latest CI's bash, so
    # the extension is always available where this file ever really runs.
    # Returns 0 when it DID find a delimiter before EOF and non-zero when
    # it read to EOF with none: a clean file always hits EOF first (rc !=
    # 0), so rc == 0 here can only mean the file contains at least one NUL.
    if IFS= read -r -d '' _pin_nul_probe < "$CODEX_PIN_FILE"; then
        echo "$TAG: pin file contains a NUL byte: $CODEX_PIN_FILE" >&2
        heartbeat "refused" "pin invalid"
        exit 78
    fi
    _pin_lines=0
    _pin_line=""
    while IFS= read -r _pin_row || [ -n "$_pin_row" ]; do
        _pin_lines=$((_pin_lines + 1))
        _pin_line="$_pin_row"
    done < "$CODEX_PIN_FILE"
    if [ "$_pin_lines" -ne 1 ]; then
        echo "$TAG: pin file must carry exactly one line: $CODEX_PIN_FILE" >&2
        heartbeat "refused" "pin invalid"
        exit 78
    fi
    case "$_pin_line" in
        WA_CODEX_CLI_VERSION_PIN=*)
            _wcbw_pin_ver="${_pin_line#WA_CODEX_CLI_VERSION_PIN=}"
            ;;
        *)
            echo "$TAG: pin file has an unrecognized line: $CODEX_PIN_FILE" >&2
            heartbeat "refused" "pin invalid"
            exit 78
            ;;
    esac
    if ! _is_semver "$_wcbw_pin_ver"; then
        echo "$TAG: pin version is not exact semver: $_wcbw_pin_ver" >&2
        heartbeat "refused" "pin invalid"
        exit 78
    fi
    _wcbw_pin_bin="$PINNED_CODEX_ROOT/$_wcbw_pin_ver/bin/codex"
    # `-x` alone is true for a directory too (a 0755 dir is "executable" in
    # the traverse sense) — gate 2026-09-26, reproduced: a directory planted
    # at this path was silently APPLIED. Require a regular file first.
    if [ ! -f "$_wcbw_pin_bin" ] || [ ! -x "$_wcbw_pin_bin" ]; then
        echo "$TAG: pinned binary missing, not a regular file, or not executable: $_wcbw_pin_bin" >&2
        heartbeat "refused" "pin invalid"
        exit 78
    fi
else
    echo "$TAG: no pin file at $CODEX_PIN_FILE — codex from the daemon env (legacy)" >&2
fi

# Positional-parameter handoff (see the comment above the pin parse): the
# script itself takes no argv from launchd, so $1/$2 are free to carry the
# resolved pin, immune to whatever the sourced env assigns by name.
set -- "$_wcbw_pin_ver" "$_wcbw_pin_bin"

set -a
. "$ENV_FILE"
set +a

# N1 (gate 2026-09-26): re-assert every wrapper-private literal a `set -a`
# export could have let the daemon env clobber by plain DATA (no alias, no
# function — reproduced with RUNTIME_DIR/VENV_PY, and TAG governs the §6
# proof line below). These six names are NEVER meant to be env-
# configurable; ENV_FILE itself was already resolved from HOME_DIR's
# ORIGINAL value before the source above, so redefining HOME_DIR here does
# not retroactively change where the env file was read from.
HOME_DIR="/Users/zantara-codex"
RUNTIME_DIR="/usr/local/lib/wa-codex-broker"
VENV_PY="$RUNTIME_DIR/.venv/bin/python3"
TAG="wa-codex-broker-wrapper"
ORGAN_ID="pro.wa_codex_broker"
SIDECAR_DIR="$HOME_DIR/.organism/last_seen"

# G5_kill_switch — operator stop without uninstall (set in the env file or
# the plist). Clean exit 0 stays DOWN under KeepAlive.SuccessfulExit=false;
# the disabled heartbeat keeps a healer from resurrecting an intentional
# stop.
#
# PRECEDENCE (N3, fresh re-gate 2026-09-27): the pin parse above runs
# BEFORE `. "$ENV_FILE"`, so an invalid pin exits 78 — heartbeat
# refused/"pin invalid" — without this kill switch ever being read. The
# env-file kill switch therefore CANNOT stop the launchd relaunch loop a
# broken root-owned pin causes: root must repair or remove the pin file
# itself, or stop the job at the launchd level (`launchctl bootout` on the
# job's label), not via this env var. That is intentional fail-closed
# ordering, not a bug — see D5.
if [ "${WA_CODEX_BROKER_ENABLED:-true}" = "false" ]; then
    echo "$TAG: WA_CODEX_BROKER_ENABLED=false - kill switch active, exiting clean" >&2
    heartbeat "disabled" "kill switch"
    exit 0
fi

if [ ! -x "$VENV_PY" ]; then
    echo "$TAG: venv python missing or not executable: $VENV_PY - run provisioning" >&2
    heartbeat "refused" "venv python missing"
    exit 78
fi

cd "$RUNTIME_DIR" || { heartbeat "refused" "cd failed"; exit 78; }
export PYTHONPATH="$RUNTIME_DIR"

heartbeat "starting" "exec daemon"

if [ -n "$1" ]; then
    echo "$TAG: $(/bin/date -u +%Y-%m-%dT%H:%M:%SZ) pin applied: codex $1 at $2" >&2
    exec /usr/bin/env WA_CODEX_CLI_VERSION_PIN="$1" WA_CODEX_BIN="$2" "$VENV_PY" -m backend.services.integrations.wa_codex_daemon
fi

exec "$VENV_PY" -m backend.services.integrations.wa_codex_daemon
