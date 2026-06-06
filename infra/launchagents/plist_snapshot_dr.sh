#!/bin/bash
# plist_snapshot_dr.sh — daily disaster-recovery snapshot of live LaunchAgent plists.
#
# WHY (cicatrix lineage):
#   - 2026-04-29 "Unknown agent overwrites loaded LaunchAgent plist files" P0:
#     51/54 plist truncated on disk; only launchd's cached boot config saved us.
#     A reboot would have lost 51 services. We had NO git copy to restore from.
#   - 2026-04-29 "53 LaunchAgents, only 13% KeepAlive" + secrets leaked 0644.
#   - W65 (2026-06-02): a hardening backup leaked a 64-hex API key world-readable.
#   This script keeps a REDACTED, git-tracked mirror of every loaded plist so a
#   future corruption/loss event is recoverable from version control — WITHOUT
#   ever committing a live secret (Symbiosis Law 2 + the no-secret-in-git rule).
#
# WHAT IT DOES:
#   1. Copies every loaded com.{nuzantara,balizero,cell,matagaruda}.* plist from
#      ~/Library/LaunchAgents into infra/launchagents/_snapshot-live/.
#   2. BEFORE writing each, REDACTS secret values: any <key> whose name matches
#      the secret pattern has its following <string>VALUE</string> replaced with
#      <string>REDACTED</string>. Done structurally (plistlib) AND textually
#      (line scan) — defense in depth.
#   3. Validates every output file with `plutil -lint`.
#   4. HARD-VERIFIES the snapshot: an independent grep over _snapshot-live/ that
#      ABORTS the commit if any secret-shaped value survived redaction. No secret
#      may ever reach git. (Anti-hallucination rule #2: verify with a second,
#      independent pass — never trust the redactor's own report.)
#   5. git add + commit on a dedicated branch (this script runs as cron later).
#   6. Emits a Telegram delta line per plist that differs from the previous
#      snapshot, reusing the repo's _telegram() pattern (wr2_plist_watchdog.sh).
#
# Designed to be invoked from com.nuzantara.plist-snapshot.daily.plist, OR
# manually. Idempotent. Safe to run unconditionally.
#
#   Kill switch:  PLIST_SNAPSHOT_ENABLED=false (env or `launchctl setenv`)
#   Dry run:      PLIST_SNAPSHOT_DRY_RUN=true   (redact + lint + verify, NO git)
#
# Usage:
#   bash infra/launchagents/plist_snapshot_dr.sh
#   PLIST_SNAPSHOT_DRY_RUN=true bash infra/launchagents/plist_snapshot_dr.sh

set -uo pipefail

# ── Kill switch ────────────────────────────────────────────────────────────
if [[ "${PLIST_SNAPSHOT_ENABLED:-true}" == "false" ]]; then
    echo "[plist-snapshot] disabled via PLIST_SNAPSHOT_ENABLED=false — exit 0"
    exit 0
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC_DIR="${HOME}/Library/LaunchAgents"
SNAP_DIR="${REPO_ROOT}/infra/launchagents/_snapshot-live"
LOG_DIR="${HOME}/logs"
SECRETS_FILE="${HOME}/.nuzantara-secrets.env"
BRANCH="chore/plist-snapshot-dr"
DRY_RUN="${PLIST_SNAPSHOT_DRY_RUN:-false}"

# Secret-key regex (anchored, case-insensitive). A <key> name matching this →
# its following <string> value is replaced with REDACTED.
SECRET_KEY_RE='(^|.*_)(API_KEY|TOKEN|KEY|SECRET|PASSWORD)$|^TELEGRAM_.*|^FLY_API_TOKEN$'

mkdir -p "${SNAP_DIR}" "${LOG_DIR}"

# Pull TELEGRAM_BOT_TOKEN / chat id from the secrets file (not committed).
if [[ -f "${SECRETS_FILE}" ]]; then
    # shellcheck disable=SC1090
    set -a
    source "${SECRETS_FILE}"
    set +a
fi

# ── Telegram helper (reused from wr2_plist_watchdog.sh) ──────────────────────
_telegram() {
    local text="$1"
    local token="${TELEGRAM_BOT_TOKEN:-}"
    local chat="${TELEGRAM_OWNER_CHAT_ID:-1125336968}"
    if [[ -z "${token}" ]]; then
        return 0
    fi
    curl -fsS -m 10 \
        --data-urlencode "chat_id=${chat}" \
        --data-urlencode "text=${text}" \
        "https://api.telegram.org/bot${token}/sendMessage" \
        >/dev/null 2>&1 || true
}

NOW_ISO="$(date -u +%FT%TZ)"
echo "[plist-snapshot] ${NOW_ISO} start (repo=${REPO_ROOT})"

if [[ ! -d "${SRC_DIR}" ]]; then
    echo "[plist-snapshot] FATAL: source dir missing: ${SRC_DIR}" >&2
    exit 1
fi

# ── 1+2+3: copy + redact + lint each loaded plist ────────────────────────────
# The heavy lifting (XML-aware redaction + lint + delta) is done in Python:
# bash regex over plist XML is fragile and the W65 scar is precisely a botched
# redaction. Python returns a machine-readable summary on stdout.
REDACT_SUMMARY="$(
SECRET_KEY_RE="${SECRET_KEY_RE}" SRC_DIR="${SRC_DIR}" SNAP_DIR="${SNAP_DIR}" \
python3 - <<'PY'
import os, re, glob, plistlib, subprocess, sys

SRC_DIR  = os.environ["SRC_DIR"]
SNAP_DIR = os.environ["SNAP_DIR"]
SECRET_RE = re.compile(os.environ["SECRET_KEY_RE"], re.IGNORECASE)
REDACTED = "REDACTED"

# Value-based redaction (defense layer 2): a VALUE that looks like a secret is
# redacted regardless of its key name. Closes the gap where keys like
# WA_DASHBOARD_DATABASE_URL / *_REDIS_URL (end in URL, not TOKEN/KEY) carry an
# inline password (postgres://u:pass@h). Specific shapes only — NOT bare hex  # pragma: allowlist secret
# (would over-redact git shas). Sub-redacts only the secret span, preserving the
# rest (host/command) for DR usefulness.
VALUE_SECRET_RE = re.compile(
    r"://[^:/\s]+:[^@\s]{3,}@"                 # user:password@ in any URI
    r"|\b[0-9]{6,}:[A-Za-z0-9_-]{30,}\b"      # telegram bot token
    r"|\bghp_[A-Za-z0-9]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{30,}\b"  # GitHub PAT
    r"|FlyV1\s+[A-Za-z0-9_=-]{10,}|\bfm2_[A-Za-z0-9_=-]{10,}\b"    # Fly tokens
    r"|\bxox[baprs]-[A-Za-z0-9-]{10,}\b"      # Slack
    r"|\bsk-[A-Za-z0-9]{20,}\b"               # OpenAI-style
    r"|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}",  # JWT
)

PREFIXES = ("com.nuzantara.", "com.balizero.", "com.cell.", "com.matagaruda.")

def is_loaded(label: str) -> bool:
    # Only snapshot plists launchd actually knows about (the 2026-04-29 producer
    # only touched loaded services; an unloaded canary on disk is noise).
    uid = os.getuid()
    r = subprocess.run(
        ["launchctl", "print", f"gui/{uid}/{label}"],
        capture_output=True,
    )
    return r.returncode == 0

def redact_obj(obj):
    """Walk parsed plist; redact a value whose KEY matches SECRET_RE (whole value)
    OR whose string content matches VALUE_SECRET_RE (secret span only). The latter
    also covers secrets sitting inline in a ProgramArguments list."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(k, str) and SECRET_RE.search(k) and isinstance(v, (str, int, float, bytes)):
                out[k] = REDACTED
            else:
                out[k] = redact_obj(v)
        return out
    if isinstance(obj, list):
        return [redact_obj(x) for x in obj]
    if isinstance(obj, str):
        return VALUE_SECRET_RE.sub(REDACTED, obj)
    return obj

def redact_text_fallback(xml: str) -> str:
    """Textual defense-in-depth: <key>SECRET</key>\\n<string>v</string> →
    <string>REDACTED</string>. Catches keys the structured pass can't reach
    (e.g. inside an inline shell <string> ProgramArguments block)."""
    def repl(m):
        keyname = m.group("k")
        if SECRET_RE.search(keyname):
            return f"<key>{m.group('k')}</key>{m.group('gap')}<string>{REDACTED}</string>"
        return m.group(0)
    pat = re.compile(
        r"<key>(?P<k>[^<]+)</key>(?P<gap>\s*)<string>(?P<v>.*?)</string>",
        re.DOTALL,
    )
    out = pat.sub(repl, xml)
    # Value-based layer: redact any secret-shaped span anywhere (covers inline
    # ProgramArguments secrets the key-adjacent pattern cannot reach).
    out = VALUE_SECRET_RE.sub(REDACTED, out)
    return out

results = []   # (label, status, changed_vs_prev)
errors  = []

candidates = []
for pref in PREFIXES:
    candidates.extend(glob.glob(os.path.join(SRC_DIR, pref + "*.plist")))
# Exclude .bak* and non-plist siblings; glob already restricts to *.plist.
candidates = sorted(set(candidates))

for src in candidates:
    base = os.path.basename(src)            # com.x.y.plist
    label = base[:-len(".plist")]
    if not is_loaded(label):
        results.append((label, "SKIP_UNLOADED", False))
        continue

    dest = os.path.join(SNAP_DIR, base)
    try:
        with open(src, "rb") as fh:
            raw = fh.read()
        parsed = plistlib.loads(raw)
        red = redact_obj(parsed)
        # Re-serialize from the redacted structure (canonical), then apply the
        # textual fallback to mop up any inline-script secrets.
        xml = plistlib.dumps(red, fmt=plistlib.FMT_XML).decode("utf-8")
        xml = redact_text_fallback(xml)
    except Exception as e:          # noqa: BLE001
        # Unparseable plist: fall back to pure-text redaction of the raw bytes
        # so a corrupt-but-readable file still gets a redacted snapshot.
        try:
            xml = redact_text_fallback(raw.decode("utf-8", "replace"))
            results_note = f"PARSE_FALLBACK({type(e).__name__})"
        except Exception as e2:      # noqa: BLE001
            errors.append(f"{label}: unreadable ({e2})")
            continue
    else:
        results_note = "OK"

    # delta vs previous snapshot (content compare, ignoring nothing — XML is
    # canonical from plistlib so formatting noise is stable across runs).
    changed = True
    if os.path.exists(dest):
        with open(dest, "r", encoding="utf-8") as fh:
            changed = (fh.read() != xml)

    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(xml)

    # plutil -lint the OUTPUT (must stay valid plist after redaction).
    lint = subprocess.run(["plutil", "-lint", dest], capture_output=True)
    if lint.returncode != 0:
        errors.append(f"{label}: plutil lint failed after redaction")
        continue

    results.append((label, results_note, changed))

# Emit machine-readable summary for the bash caller.
print("SNAPSHOTTED=" + str(sum(1 for _, s, _ in results if s in ("OK", "PARSE_FALLBACK") or s.startswith("PARSE_FALLBACK"))))
print("SKIPPED=" + str(sum(1 for _, s, _ in results if s == "SKIP_UNLOADED")))
print("CHANGED=" + str(sum(1 for _, _, c in results if c)))
for label, status, changed in results:
    if status == "SKIP_UNLOADED":
        continue
    mark = "Δ" if changed else "="
    print(f"DELTA\t{mark}\t{label}\t{status}")
for e in errors:
    print(f"ERROR\t{e}")
sys.exit(2 if errors else 0)
PY
)"
REDACT_RC=$?

echo "${REDACT_SUMMARY}"

if [[ ${REDACT_RC} -ne 0 ]]; then
    msg="🚨 plist-snapshot: redaction/lint ERRORS @ ${NOW_ISO}"$'\n'"$(echo "${REDACT_SUMMARY}" | grep '^ERROR' | head -20)"
    echo "${msg}" >&2
    _telegram "${msg}"
    # Do NOT commit a snapshot that failed lint — abort before git.
    exit 1
fi

# ── 4: HARD secret-leak verification (independent of the redactor) ───────────
# The redactor said it's clean. Trust nothing — re-scan the OUTPUT directory for
# any secret-shaped value that is NOT the literal REDACTED. If even one survives,
# ABORT before git. (W65 lesson: even an adversarial verifier hallucinates; the
# only safe check is your own independent grep.)
#
# Heuristic leak signatures: long hex (>=24), JWT-ish, AAAA: bot tokens,
# fly tokens (FlyV1/fm2_), GitHub PATs (ghp_/github_pat_), sk-/xoxb- style keys.
LEAK_HITS="$(
grep -rInaE '(<string>[A-Fa-f0-9]{24,}</string>)|(<string>[0-9]{6,}:[A-Za-z0-9_-]{30,}</string>)|(ghp_[A-Za-z0-9]{20,})|(github_pat_[A-Za-z0-9_]{30,})|(FlyV1 )|(fm2_)|(xox[baprs]-[A-Za-z0-9-]{10,})|(sk-[A-Za-z0-9]{20,})|(eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.)|(://[^:/<[:space:]]+:[^@<[:space:]]{3,}@)' \
    "${SNAP_DIR}" 2>/dev/null \
    | grep -vF '>REDACTED<' \
    || true
)"

if [[ -n "${LEAK_HITS}" ]]; then
    # Quarantine: do NOT commit. Wipe the freshly-written snapshot so a leak
    # can't sit on disk world-readable either (W65 residue pattern).
    msg="🚨🚨 plist-snapshot ABORTED: secret survived redaction @ ${NOW_ISO}"$'\n'"$(echo "${LEAK_HITS}" | sed -E 's#(<string>).*(</string>)#\1<LEAKED-VALUE-NOT-LOGGED>\2#g' | head -10)"
    echo "${msg}" >&2
    _telegram "🚨🚨 plist-snapshot ABORTED: secret survived redaction @ ${NOW_ISO} — see ${LOG_DIR}/plist-snapshot.error.log (value NOT logged)"
    exit 3
fi
echo "[plist-snapshot] secret-leak verification PASS (0 unredacted secrets in ${SNAP_DIR})"

# Tighten perms on the snapshot dir (defense in depth; redacted but still).
chmod 0644 "${SNAP_DIR}"/*.plist 2>/dev/null || true

CHANGED_N="$(echo "${REDACT_SUMMARY}" | sed -n 's/^CHANGED=//p')"
SNAP_N="$(echo "${REDACT_SUMMARY}" | sed -n 's/^SNAPSHOTTED=//p')"

if [[ "${DRY_RUN}" == "true" ]]; then
    echo "[plist-snapshot] DRY RUN — no git. snapshotted=${SNAP_N} changed=${CHANGED_N}"
    exit 0
fi

# ── 5: commit snapshot to a dedicated DR branch WITHOUT touching HEAD ─────────
# Anti sibling-race (cicatrix W50/W51/W52 + untracked-loss-on-branch-switch
# 2026-04-29): a cron MUST NOT `git checkout`/`git stash` on the shared worktree
# — that changes HEAD under a live operator session and can drop untracked files.
# We commit via a temp index + commit-tree + update-ref: HEAD and the working
# tree are NEVER touched; only refs/heads/${BRANCH} advances. Push left to operator.
cd "${REPO_ROOT}" || { echo "[plist-snapshot] FATAL: cannot cd ${REPO_ROOT}" >&2; exit 1; }

TMP_INDEX="$(mktemp "${TMPDIR:-/tmp}/plist-snap-index.XXXXXX")"
rm -f "${TMP_INDEX}"   # mktemp's empty 0-byte file is NOT a valid git index; let git create it fresh
trap 'rm -f "${TMP_INDEX}"' EXIT

if git show-ref --verify --quiet "refs/heads/${BRANCH}"; then
    PARENT="$(git rev-parse "refs/heads/${BRANCH}")"
    GIT_INDEX_FILE="${TMP_INDEX}" git read-tree "${PARENT}" 2>/dev/null || true
else
    PARENT=""
fi

# Stage ONLY the snapshot dir into the TEMP index (operator's index untouched).
# -f because _snapshot-live/ is gitignored on working branches (it belongs ONLY
# on the DR branch, force-added here).
GIT_INDEX_FILE="${TMP_INDEX}" git add -f -- "infra/launchagents/_snapshot-live/"
TREE="$(GIT_INDEX_FILE="${TMP_INDEX}" git write-tree)"

if [[ -n "${PARENT}" && "${TREE}" == "$(git rev-parse "${PARENT}^{tree}" 2>/dev/null)" ]]; then
    echo "[plist-snapshot] no plist changes since last snapshot — nothing to commit."
    exit 0
fi

COMMIT_MSG="chore(dr): plist live snapshot ${NOW_ISO} (${CHANGED_N} changed, redacted)

Daily disaster-recovery snapshot of loaded LaunchAgent plists, secrets redacted.
snapshotted=${SNAP_N} changed=${CHANGED_N}
Source: ~/Library/LaunchAgents/com.{nuzantara,balizero,cell,matagaruda}.*
Redaction + independent secret-leak verification PASSED before commit.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"

if [[ -n "${PARENT}" ]]; then
    COMMIT="$(printf '%s' "${COMMIT_MSG}" | git commit-tree "${TREE}" -p "${PARENT}")"
else
    COMMIT="$(printf '%s' "${COMMIT_MSG}" | git commit-tree "${TREE}")"
fi
if [[ -z "${COMMIT}" ]]; then
    echo "[plist-snapshot] FATAL: git commit-tree returned empty (tree=${TREE})" >&2
    exit 1
fi
git update-ref "refs/heads/${BRANCH}" "${COMMIT}" ${PARENT:+"${PARENT}"}
echo "[plist-snapshot] committed ${COMMIT:0:9} → ${BRANCH} (HEAD/working-tree untouched)"

# ── 6: Telegram delta line ───────────────────────────────────────────────────
if [[ -n "${CHANGED_N}" && "${CHANGED_N}" != "0" ]]; then
    DELTA_LINES="$(echo "${REDACT_SUMMARY}" | awk -F'\t' '$1=="DELTA" && $2=="Δ" {print "  • "$3}' | head -20)"
    msg="🗂 plist-snapshot DR @ ${NOW_ISO}"$'\n'"${CHANGED_N} plist changed vs yesterday (committed to ${BRANCH}):"$'\n'"${DELTA_LINES}"
    echo "${msg}"
    _telegram "${msg}"
else
    echo "[plist-snapshot] committed; 0 deltas vs previous snapshot (timestamp-only)."
fi

echo "[plist-snapshot] done @ $(date -u +%FT%TZ)"
exit 0
