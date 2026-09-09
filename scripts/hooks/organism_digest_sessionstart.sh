#!/usr/bin/env bash
# organism_digest_sessionstart.sh — session-boot receptor for the organism digest.
#
# Third sibling of escalations_alert_sessionstart.sh / proprioception_sessionstart.sh.
# Renders "what changed in the organism in the last 24h" (regulatory deltas, dead AI
# seats, silent organs, overdue armings, main landings) INTO the session — the one
# channel Zero actually reads daily. Born 2026-07-06 from the mandate "Telegram non lo
# leggo: resoconti compatti al canale giusto".
#
# ANTI-CALM-LIAR CONTRACT: never silent — all-quiet prints a one-line heartbeat.
# Budget: the python receptor self-limits via SIGALRM (6s). Always exit 0.
# Kill switch: ORGANISM_DIGEST_ENABLED=false.
#
# D4 freshness (docs/mandates/2026-08-22-arsenal-routing-mandate.md): when the
# arsenal probe report is missing or >24h stale, kick a re-probe in the
# BACKGROUND and read the PREVIOUS report THIS boot regardless — the probe
# takes ~60-90s wall clock (measured 2026-08-22), far past this hook's budget.
# Never uses timeout/gtimeout: neither exists on this fleet (measured
# 2026-08-22 — `command -v timeout` found nothing, and a `timeout 240 …` call
# exited 0 having run nothing). Kill switch mirrors ORGANISM_DIGEST_ENABLED's
# own style: ORGANISM_ARSENAL_REFRESH_ENABLED=false.

set -o pipefail
[[ "${ORGANISM_DIGEST_ENABLED:-true}" == "false" ]] && exit 0

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)"
REPO_ROOT="$(cd "$HOOK_DIR/../.." 2>/dev/null && pwd)"

if [[ "${ORGANISM_ARSENAL_REFRESH_ENABLED:-true}" != "false" ]]; then
  ARSENAL_DIR="$HOME/.organism/arsenal"
  ARSENAL_REPORT="$ARSENAL_DIR/last.json"
  ARSENAL_LOCK="$ARSENAL_DIR/.refresh.lock"   # mkdir-lock: atomic, portable, no flock dependency
  STALE_SECS=$((24 * 3600))
  LOCK_STALE_SECS=$((15 * 60))                # a wedged/dead holder must not lock this out forever

  need_refresh=0
  if [[ ! -f "$ARSENAL_REPORT" ]]; then
    need_refresh=1
  else
    report_mtime="$(stat -f %m "$ARSENAL_REPORT" 2>/dev/null || echo 0)"
    now_ts="$(date +%s)"
    if (( now_ts - report_mtime > STALE_SECS )); then
      need_refresh=1
    fi
  fi

  if [[ "$need_refresh" == "1" ]]; then
    mkdir -p "$ARSENAL_DIR" "$HOME/logs" 2>/dev/null
    if [[ -d "$ARSENAL_LOCK" ]]; then
      lock_mtime="$(stat -f %m "$ARSENAL_LOCK" 2>/dev/null || echo 0)"
      now_ts="$(date +%s)"
      if (( now_ts - lock_mtime > LOCK_STALE_SECS )); then
        rmdir "$ARSENAL_LOCK" 2>/dev/null
      fi
    fi
    # mkdir is atomic: exactly one concurrent hook invocation wins the lock.
    if mkdir "$ARSENAL_LOCK" 2>/dev/null; then
      (
        nohup python3 "$REPO_ROOT/scripts/arsenal_probe.py" \
          >> "$HOME/logs/arsenal_probe_bg.log" 2>&1 < /dev/null
        rmdir "$ARSENAL_LOCK" 2>/dev/null
      ) &
      disown 2>/dev/null || true
    fi
  fi
fi

OUT="$(python3 "$REPO_ROOT/scripts/organism_digest.py" 2>/dev/null)"
RC=$?
if [[ -n "$OUT" ]]; then
  # Output cap (2026-09-04): reshape + cap WITHOUT touching organism_digest.py
  # (768 lines, its own selftest asserts exact arsenal_card shape) — this is a
  # post-filter over the already-rendered text. Two rules, always applied:
  #   (a) the arsenal card's per-seat rollup line + provider "doors:" line
  #       collapse into ONE line naming only the NOT-ok seats — the doors map
  #       is reference material (the report has it in full), the all-seats
  #       rollup is the single biggest line in a HEALTHY digest and names
  #       nothing an operator acts on.
  #   (b) if still over budget: drop low/unknown-severity regulatory lines,
  #       then the main-landing line, then pending-arms detail lines, before
  #       ever touching a red item (seat TIMEOUT/dead, silent organ,
  #       medium+/high regulatory) — and if that alone is not enough, hard
  #       line-boundary truncate with a trailer naming the real full command.
  MAX_BYTES="${SESSIONSTART_HOOK_MAX_BYTES:-1500}"
  CAPPED="$(python3 - "$OUT" "$MAX_BYTES" <<'PYEOF' 2>/dev/null
import sys

text, max_bytes = sys.argv[1], int(sys.argv[2])
lines = text.split("\n")

out = []
i = 0
while i < len(lines):
    ln = lines[i]
    if ln.lstrip().startswith("🔌 arsenal (probe"):
        out.append(ln)
        rollup = lines[i + 1] if i + 1 < len(lines) else ""
        if "no seats" in rollup:
            out.append("  (report has no seats)")
        else:
            not_ok = [tok for tok in rollup.split() if "✗" in tok]
            out.append("  not ok: " + " ".join(not_ok) if not_ok else "  all seats ok")
        i += 3  # skip the original rollup + doors lines — always collapsed
        continue
    out.append(ln)
    i += 1


def _bytes(ls: list[str]) -> int:
    return len("\n".join(ls).encode("utf-8"))


if _bytes(out) > max_bytes:
    def _priority(ln: str):
        s = ln.strip()
        if s.startswith("⚖️") and ("[low]" in s or "[?]" in s):
            return 1  # lowest severity regulatory: drop first
        if s.startswith("⬆️") or s.startswith("🕰️"):
            return 2  # main-landing / pending-arms detail: droppable second
        return None  # never droppable here: seats, organs, high/medium reg, errors

    trimmed = list(out)
    while _bytes(trimmed) > max_bytes:
        candidates = [(idx, _priority(ln)) for idx, ln in enumerate(trimmed)]
        candidates = [(idx, p) for idx, p in candidates if p is not None]
        if not candidates:
            break
        candidates.sort(key=lambda t: (-t[1], -t[0]))  # least-important, latest first
        del trimmed[candidates[0][0]]

    if _bytes(trimmed) > max_bytes:
        kept, total, reserve = [], 0, 100
        for ln in trimmed:
            b = len((ln + "\n").encode("utf-8"))
            if total + b > max_bytes - reserve:
                break
            kept.append(ln)
            total += b
        hidden = len(trimmed) - len(kept)
        if hidden > 0:
            kept.append(f"… (+{hidden} lines, run: python3 scripts/organism_digest.py)")
        trimmed = kept
    out = trimmed

sys.stdout.write("\n".join(out))
PYEOF
)"
  [[ -n "$CAPPED" ]] && OUT="$CAPPED"
  echo "$OUT"
elif [[ $RC -ne 0 ]]; then
  echo "📰 organismo: receptor error (digest exit $RC) — run: python3 scripts/organism_digest.py"
else
  # Empty output with rc=0 should be impossible (anti-calm-liar) — make THAT visible too.
  echo "📰 organismo: receptor emitted nothing (contract breach) — check scripts/organism_digest.py"
fi
exit 0
