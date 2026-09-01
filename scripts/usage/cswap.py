#!/usr/bin/env python3
"""cswap.py — Claude-profile rotation across the Anthropic MAX/Team seats.

Swaps `CLAUDE_CONFIG_DIR` between the local Claude profile directories mapped in
`seat_map.json` (A1/A2/A3/AZ + the orphan/legacy entries flagged there).
Lane-affine per the harness-flotta dossier (2026-08-09 §1): A1
interactive/architect, A2 subagents/build, A3 cron/batch (donor), AZ = the
Team Premium gate-primary seat.

HONESTY CONSTRAINT (W106, cicatrix-superscar.md family #9 — "the proxy
lies"): Anthropic exposes NO API for a seat's *remaining* 5h/7d quota. Every
number this tool prints or ranks by is *local consumption* — tokens already
spent, parsed from `~/.claude*/projects/**/*.jsonl` via
`seat_usage_collector.collect_claude()` — never remaining headroom. Two
concrete ways this proxy misleads, stated rather than hidden:

  1. A seat driven from ANOTHER machine (Pro/Mini) looks idle here — this
     tool only ever sees the LOCAL filesystem's transcripts.
  2. The "5h" and "7d" windows below are NOT a precise rolling-window sum.
     `collect_claude(profile_dir, since)` gates by FILE mtime, not by each
     JSONL line's own timestamp — a transcript file touched within the
     window contributes ALL of its lines, including ones written well
     before the window started. Treat both numbers as "how much recent
     activity has this profile's transcripts accumulated", not as an
     audited token count for that exact interval.

`cswap auto`'s 90%-of-observed-max threshold is therefore a proxy for "this
seat looks closer to its ceiling than the others", not a measurement of the
ceiling itself — there is no ceiling to measure.

PRIVACY: `seat_map.json` is tracked in a PUBLIC repo (Bali-Zero/Teman2) and
holds ONLY profile-dir -> seat-id mapping. `cswap fingerprint`'s output —
real personal identities (emails) — is written to a LOCAL file only
(~/.config/cswap/fingerprints.json, 0600) and this tool never writes
anything back into seat_map.json. Same scar class as the committed-team-PINs
incident: a value that reaches a tracked path is exposed the moment it's
pushed, not just if someone later reads it wrong.

Commands:
  cswap list                          show seats + fingerprint identity + 5h/7d consumption
  cswap fingerprint                   ARM: run `claude auth status` per profile, record identity LOCALLY
  cswap run <seat-or-dir> [-- cmd...]  exec a command (default: interactive `claude`) under that seat
  cswap auto [--print] [--activate] [--exclude SEAT ...]
                                       pick the least-loaded eligible seat (hysteresis + lock)

Composable: `CLAUDE_CONFIG_DIR=$(python3 scripts/usage/cswap.py auto --print) claude`

No symlinks in $HOME, no shell-rc edits (cicatrix-superscar.md family #1,
HOME-fork drift) — state lives only under `~/.config/cswap/`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Optional

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from seat_usage_collector import WITA, collect_claude  # noqa: E402  (path setup above)

LOCK_TIMEOUT_RC = 75  # EX_TEMPFAIL — same convention as scripts/prepush_suite_lock.sh
HYSTERESIS_THRESHOLD = 0.9
HYSTERESIS_WINDOW = timedelta(minutes=30)

_INELIGIBLE_MARKERS = ("orphan", "legacy")

# Defensive redaction (cicatrix-superscar.md family #4 — secret in the
# clear): applied to the raw-first-line fallback in fingerprinting, so a
# `claude auth status` output that fails to parse as the expected JSON shape
# can never land a token/secret-shaped string in seat_map.json.
_TOKEN_WORD_RE = re.compile(r"(?i)\b(token|secret|api[_-]?key|bearer|password)\b")
_LONG_OPAQUE_RE = re.compile(r"[A-Za-z0-9_\-]{24,}")


def emit(msg: str) -> None:
    print(msg)


def emit_err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _now() -> datetime:
    return datetime.now(WITA)


def _now_iso() -> str:
    return _now().isoformat(timespec="seconds")


# --------------------------------------------------------------- seat map


def _default_seat_map_path() -> Path:
    return _THIS_DIR / "seat_map.json"


def load_seat_map(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        raise SystemExit(f"[cswap] seat map not found: {path}")
    except json.JSONDecodeError as e:
        raise SystemExit(f"[cswap] seat map unreadable ({e}): {path}")


# cswap NEVER writes to seat_map.json. That file is tracked in a PUBLIC repo
# (Bali-Zero/Teman2) and holds only profile-dir -> seat-id mapping; fingerprint
# IDENTITIES (real personal emails) go to a LOCAL, gitignored-by-construction
# file instead (see _write_json_local / cmd_fingerprint below) — same scar
# class as the committed-team-PINs incident (2026-07-27): a secret/PII value
# that reaches a tracked path is exposed the moment it's pushed, not just if
# someone later reads it wrong.
def _write_json_local(path: Path, data: dict[str, Any]) -> None:
    """Writer for cswap's OWN local state (~/.config/cswap/*.json) — never
    for seat_map.json. ensure_ascii=False preserves literal UTF-8 (an
    orgName, an em-dash) instead of \\u-escaping it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # best-effort permission tightening; not the primary guard


def is_eligible(seat_id: str) -> bool:
    """False for the orphan (`~/.claude-acct4`, no seat exists) and legacy
    (`~/.claude-zero-team`, AZ duplicate) entries — matched on seat_map's own
    `_doc`-declared markers, not a hardcoded profile-dir list, so a future
    seat_map edit that retires/adds an entry doesn't need this file touched."""
    lowered = seat_id.lower()
    return not any(marker in lowered for marker in _INELIGIBLE_MARKERS)


def resolve_seat_dir(seat_map: dict[str, Any], token: str) -> Path:
    """Resolve a seat id (e.g. "A2") or a literal directory path to an
    existing profile directory. Refuses unknown seat ids and the
    orphan/legacy ones — never falls through to a directory guess for those,
    so a typo'd seat id cannot silently run against an unintended profile.

    The orphan/legacy refusal is checked on the ENTITY (the resolved
    directory), not just the seat-id TOKEN — cicatrix-superscar.md family #3
    (guard-over/under-match): a check keyed only on the token "A4" would be
    bypassable by simply naming the same directory literally
    (`cswap run ~/.claude-acct4`), which is the directory the refusal exists
    to protect in the first place."""
    profiles = seat_map.get("claude_profiles") or {}
    for pdir_str, seat_id in profiles.items():
        if seat_id == token:
            if not is_eligible(seat_id):
                raise ValueError(
                    f"seat '{token}' is excluded (orphan/legacy) — refusing to run against it"
                )
            pdir = Path(os.path.expanduser(pdir_str))
            if not pdir.is_dir():
                raise ValueError(f"seat '{token}' maps to '{pdir_str}', which does not exist")
            return pdir

    candidate = Path(os.path.expanduser(token))
    for pdir_str, seat_id in profiles.items():
        if is_eligible(seat_id):
            continue
        mapped = Path(os.path.expanduser(pdir_str))
        try:
            same = candidate.exists() and mapped.exists() and candidate.samefile(mapped)
        except OSError:
            same = False
        if same or candidate == mapped:
            raise ValueError(
                f"'{token}' resolves to the excluded seat '{seat_id}' ({pdir_str}) — refusing"
            )

    if candidate.is_dir():
        return candidate
    raise ValueError(f"unknown seat or directory: '{token}'")


# --------------------------------------------------------------- consumption


def _collect_window(profile_dir_str: str, since: datetime) -> dict[str, Any]:
    """Reuses seat_usage_collector.collect_claude — see its own docstring
    plus the honesty-constraint note at the top of this file for what the
    resulting numbers do and don't mean."""
    result = collect_claude(os.path.expanduser(profile_dir_str), since)
    days = result.get("days") or {}
    totals = {"in": 0, "out": 0, "cache_r": 0, "cache_w": 0}
    for bucket in days.values():
        for k in totals:
            totals[k] += bucket.get(k, 0) or 0
    totals["total"] = sum(totals.values())
    totals["status"] = result.get("status", "unknown")
    return totals


def _fmt_tokens(d: dict[str, Any]) -> str:
    return f"{d['total']:,}tok(in={d['in']:,}/out={d['out']:,}/status={d['status']})"


# --------------------------------------------------------------- fingerprint


def _redact_if_secretlike(text: str) -> str:
    if _TOKEN_WORD_RE.search(text) or _LONG_OPAQUE_RE.search(text):
        return "[REDACTED — output matched a secret-shaped pattern]"
    return text


def _run_auth_status(profile_dir: Path, *, timeout: float = 20.0) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    # Same defensive strip as scripts/arsenal_probe.py::probe_claude — a
    # stray ambient credential must not shadow the profile dir under test.
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL",
              "CLAUDE_CODE_OAUTH_TOKEN"):
        env.pop(k, None)
    env["CLAUDE_CONFIG_DIR"] = str(profile_dir)
    try:
        return subprocess.run(["claude", "auth", "status"], capture_output=True,
                               text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args=["claude", "auth", "status"], returncode=124,
                                            stdout="", stderr=f"timed out after {timeout}s")
    except FileNotFoundError:
        return subprocess.CompletedProcess(args=["claude"], returncode=127,
                                            stdout="", stderr="claude binary not found")


AuthStatusRunner = Callable[[Path], "subprocess.CompletedProcess"]


def fingerprint_one(profile_dir: Path, runner: AuthStatusRunner = _run_auth_status) -> dict[str, Any]:
    """Judge `claude auth status` output DEFENSIVELY (W104 — judge the
    reply, never the bare rc): parse the documented JSON shape
    (`{"loggedIn": bool, "email": ..., "subscriptionType": ..., ...}`,
    verified live 2026-08-11) first; only fall back to the raw first line,
    redacted, when that parse fails."""
    proc = runner(profile_dir)
    stdout = proc.stdout or ""
    parsed: Any = None
    try:
        parsed = json.loads(stdout)
    except (ValueError, TypeError):
        parsed = None

    if isinstance(parsed, dict) and "loggedIn" in parsed:
        if parsed.get("loggedIn"):
            bits = []
            if parsed.get("email"):
                bits.append(str(parsed["email"]))
            if parsed.get("subscriptionType"):
                bits.append(f"({parsed['subscriptionType']})")
            if parsed.get("orgName"):
                bits.append(f"org={parsed['orgName']}")
            identity = " ".join(bits) if bits else "logged in (no identity fields in response)"
        else:
            identity = f"not logged in (authMethod={parsed.get('authMethod', 'none')})"
        parse_status = "ok"
    else:
        first_line = next((ln.strip() for ln in stdout.splitlines() if ln.strip()), "")
        if not first_line:
            stderr = proc.stderr or ""
            first_line = next((ln.strip() for ln in stderr.splitlines() if ln.strip()), "")
        identity = first_line or "(no output)"
        parse_status = "unparsed"

    identity = _redact_if_secretlike(identity)
    return {
        "identity": identity,
        "checked_at": _now_iso(),
        "rc": proc.returncode,
        "parse_status": parse_status,
    }


def _default_fingerprints_path() -> Path:
    return _state_dir() / "fingerprints.json"


def load_local_fingerprints(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def cmd_fingerprint(seat_map_path: Path, fingerprints_path: Optional[Path] = None,
                     runner: AuthStatusRunner = _run_auth_status) -> int:
    """ARMING command. Writes identities to a LOCAL file
    (~/.config/cswap/fingerprints.json, 0600) — NEVER into seat_map.json.
    That file is tracked in a public repo (Bali-Zero/Teman2); a real personal
    email must never land there (same scar class as the committed-team-PINs
    incident). seat_map.json is only ever READ here, never written."""
    seat_map = load_seat_map(seat_map_path)
    profiles = seat_map.get("claude_profiles") or {}
    fp_path = fingerprints_path or _default_fingerprints_path()
    fingerprints = load_local_fingerprints(fp_path)
    checked = 0
    for pdir_str, seat_id in profiles.items():
        pdir = Path(os.path.expanduser(pdir_str))
        if not pdir.is_dir():
            emit(f"[cswap fingerprint] SKIP {seat_id} ({pdir_str}) — directory missing")
            continue
        result = fingerprint_one(pdir, runner)
        fingerprints[pdir_str] = result
        checked += 1
        emit(f"[cswap fingerprint] {seat_id:24s} {pdir_str:22s} -> {result['identity']}")
    _write_json_local(fp_path, fingerprints)
    emit(f"[cswap fingerprint] {checked}/{len(profiles)} profiles fingerprinted "
         f"-> {fp_path} (local only, never committed)")
    return 0


# --------------------------------------------------------------- list


def cmd_list(seat_map_path: Path, fingerprints_path: Optional[Path] = None) -> int:
    seat_map = load_seat_map(seat_map_path)
    profiles = seat_map.get("claude_profiles") or {}
    fingerprints = load_local_fingerprints(fingerprints_path or _default_fingerprints_path())
    now = _now()
    for pdir_str, seat_id in profiles.items():
        pdir = Path(os.path.expanduser(pdir_str))
        exists = pdir.is_dir()
        fp = fingerprints.get(pdir_str, {})
        identity = fp.get("identity", "(not fingerprinted — run `cswap fingerprint`)")
        if not is_eligible(seat_id):
            status = "present" if exists else "MISSING"
            emit(f"[cswap list] WARN excluded seat={seat_id} dir={pdir_str} "
                 f"status={status} identity={identity}")
            continue
        if not exists:
            emit(f"{seat_id:6s} {pdir_str:22s} MISSING")
            continue
        m5h = _collect_window(pdir_str, now - timedelta(hours=5))
        m7d = _collect_window(pdir_str, now - timedelta(days=7))
        emit(f"{seat_id:6s} {pdir_str:22s} identity={identity} "
             f"5h={_fmt_tokens(m5h)} 7d={_fmt_tokens(m7d)}")
    return 0


# --------------------------------------------------------------- auto (rank + hysteresis + lock)


def _state_dir() -> Path:
    return Path.home() / ".config" / "cswap"


def _state_path() -> Path:
    return _state_dir() / "state.json"


def _lock_dir_path() -> Path:
    return _state_dir() / "auto.lock"


def load_state(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(path: Path, state: dict[str, Any]) -> None:
    _write_json_local(path, state)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, we just can't signal it — still alive
    except OSError:
        return False
    return True


def acquire_lock(lock_dir: Path) -> bool:
    """mkdir-atomic lock with stale-holder reclaim via `kill -0` — same
    primitive choice as scripts/prepush_suite_lock.sh (mkdir is
    POSIX-guaranteed atomic; no TOCTOU window). Unlike that wrapper this is
    a SINGLE-ATTEMPT trylock, not a poll-and-wait loop: `cswap auto` is meant
    to run instantly (a cron tick or an interactive `$(cswap auto --print)`),
    so a held lock means "another rotation decision is in flight right now"
    and the correct answer is "come back later", never a silent wait."""
    lock_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock_dir.mkdir()
    except FileExistsError:
        pid_file = lock_dir / "pid"
        holder_pid: Optional[int] = None
        try:
            holder_pid = int(pid_file.read_text().strip())
        except (FileNotFoundError, ValueError):
            holder_pid = None
        if holder_pid is not None and _pid_alive(holder_pid):
            return False  # genuinely held
        shutil.rmtree(lock_dir, ignore_errors=True)
        try:
            lock_dir.mkdir()
        except FileExistsError:
            return False  # lost the reclaim race to another waiter
    (lock_dir / "pid").write_text(str(os.getpid()))
    return True


def release_lock(lock_dir: Path) -> None:
    shutil.rmtree(lock_dir, ignore_errors=True)


def collect_candidates(seat_map: dict[str, Any], now: datetime,
                        exclude: set[str]) -> list[dict[str, Any]]:
    """Impure: touches real profile dirs + calls collect_claude. Kept
    separate from choose_seat() (pure) so the hysteresis/ranking logic is
    unit-testable without real transcript files on disk."""
    candidates = []
    for pdir_str, seat_id in (seat_map.get("claude_profiles") or {}).items():
        if not is_eligible(seat_id) or seat_id in exclude:
            continue
        pdir = Path(os.path.expanduser(pdir_str))
        if not pdir.is_dir():
            continue
        m5h = _collect_window(pdir_str, now - timedelta(hours=5))
        m7d = _collect_window(pdir_str, now - timedelta(days=7))
        candidates.append({"seat": seat_id, "dir": pdir_str, "path": pdir,
                            "t5": m5h["total"], "t7": m7d["total"]})
    return candidates


def choose_seat(candidates: list[dict[str, Any]], state: dict[str, Any], now: datetime,
                 threshold: float = HYSTERESIS_THRESHOLD,
                 window: timedelta = HYSTERESIS_WINDOW) -> dict[str, Any]:
    """Pure ranking + hysteresis — no I/O, fully unit-testable.

    Rank ascending by 5h consumption (tie-break 7d): the least-loaded
    eligible seat is the default choice. Then KEEP the currently-active seat
    if EITHER holds: (a) its 5h consumption is under `threshold` (90%) of
    the max observed among candidates — it isn't near the ceiling proxy yet
    — or (b) the last switch was less than `window` (30min) ago — anti
    flip-flop. Only when BOTH conditions fail does auto actually rotate."""
    if not candidates:
        raise ValueError("no eligible candidates")

    ranked = sorted(candidates, key=lambda c: (c["t5"], c["t7"]))
    chosen = ranked[0]

    active_dir = state.get("active_dir")
    if active_dir:
        current = next((c for c in candidates if c["dir"] == active_dir), None)
        if current is not None:
            max_t5 = max(c["t5"] for c in candidates)
            under_threshold = max_t5 <= 0 or current["t5"] < threshold * max_t5
            recent_switch = False
            last_switch = state.get("last_switch_ts")
            if last_switch:
                try:
                    recent_switch = (now - datetime.fromisoformat(last_switch)) < window
                except ValueError:
                    recent_switch = False
            if under_threshold or recent_switch:
                chosen = current
    return chosen


def cmd_auto(seat_map_path: Path, *, do_print: bool, do_activate: bool,
             exclude: list[str]) -> int:
    lock_dir = _lock_dir_path()
    if not acquire_lock(lock_dir):
        emit_err("[cswap auto] another `cswap auto` is running right now "
                 f"(lock: {lock_dir}) — this is the queue working, not a fault. Retry shortly.")
        return LOCK_TIMEOUT_RC
    try:
        seat_map = load_seat_map(seat_map_path)
        now = _now()
        candidates = collect_candidates(seat_map, now, set(exclude))
        if not candidates:
            emit_err("[cswap auto] no eligible seats available (all excluded, missing, "
                     "or orphan/legacy)")
            return 3

        state_path = _state_path()
        state = load_state(state_path)
        chosen = choose_seat(candidates, state, now)

        if do_print:
            print(str(chosen["path"]))
        else:
            emit(f"[cswap auto] chosen seat={chosen['seat']} dir={chosen['dir']} "
                 f"(5h_total={chosen['t5']}, 7d_total={chosen['t7']})")

        if do_activate:
            switched = state.get("active_dir") != chosen["dir"]
            new_state = {
                "active_dir": chosen["dir"],
                "active_seat": chosen["seat"],
                "last_switch_ts": _now_iso() if switched else state.get("last_switch_ts", _now_iso()),
            }
            save_state(state_path, new_state)
        return 0
    finally:
        release_lock(lock_dir)


# --------------------------------------------------------------- run


def _strip_leading_separator(cmd: list[str]) -> list[str]:
    if cmd and cmd[0] == "--":
        return cmd[1:]
    return cmd


def cmd_run(seat_map_path: Path, seat_or_dir: str, cmd: list[str]) -> int:
    seat_map = load_seat_map(seat_map_path)
    try:
        resolved = resolve_seat_dir(seat_map, seat_or_dir)
    except ValueError as e:
        emit_err(f"[cswap run] {e}")
        return 2

    argv = _strip_leading_separator(cmd) or ["claude"]
    env = dict(os.environ)
    env["CLAUDE_CONFIG_DIR"] = str(resolved)
    binp = shutil.which(argv[0]) or argv[0]
    emit(f"[cswap run] CLAUDE_CONFIG_DIR={resolved} exec: {' '.join(argv)}")
    os.execvpe(binp, argv, env)  # never returns on success
    return 1  # pragma: no cover — unreachable unless execvpe itself fails


# --------------------------------------------------------------- CLI


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cswap",
        description="Rotate CLAUDE_CONFIG_DIR across the Anthropic MAX/Team seats mapped in seat_map.json.",
    )
    p.add_argument("--seat-map", default=str(_default_seat_map_path()),
                    help="path to seat_map.json (default: alongside this script; mapping ONLY, "
                         "never touched by this tool — no identity is ever written here)")
    p.add_argument("--fingerprints", default=None,
                    help="path to the LOCAL fingerprints file (default: ~/.config/cswap/fingerprints.json)")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="show seats, fingerprint identity, 5h/7d local consumption")
    sub.add_parser("fingerprint",
                    help="ARM: run `claude auth status` per mapped profile, record identities "
                         "LOCALLY (never into the tracked seat_map.json)")

    p_run = sub.add_parser("run", help="exec a command with CLAUDE_CONFIG_DIR set to the resolved seat")
    p_run.add_argument("seat_or_dir", help="seat id (A1/A2/A3/AZ) or a literal profile directory")
    p_run.add_argument("cmd", nargs="*", help="command to exec (default: interactive `claude`)")

    p_auto = sub.add_parser("auto", help="pick the least-loaded eligible seat (hysteresis + lock)")
    p_auto.add_argument("--print", dest="do_print", action="store_true",
                         help="print only the chosen profile dir (composable)")
    p_auto.add_argument("--activate", dest="do_activate", action="store_true",
                         help="also record the choice as active in the state file")
    p_auto.add_argument("--exclude", nargs="*", default=[], metavar="SEAT",
                         help="seat ids to exclude from ranking this run")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    seat_map_path = Path(args.seat_map)
    fingerprints_path = Path(args.fingerprints) if args.fingerprints else None

    if args.command == "list":
        return cmd_list(seat_map_path, fingerprints_path)
    if args.command == "fingerprint":
        return cmd_fingerprint(seat_map_path, fingerprints_path)
    if args.command == "run":
        return cmd_run(seat_map_path, args.seat_or_dir, args.cmd)
    if args.command == "auto":
        return cmd_auto(seat_map_path, do_print=args.do_print, do_activate=args.do_activate,
                         exclude=args.exclude)
    parser.error("unknown command")  # pragma: no cover — argparse enforces `required=True`
    return 2


if __name__ == "__main__":
    sys.exit(main())
