#!/usr/bin/env python3
"""
fleet_sessions — GEAR 2, builder = Codex

DISEASE KILLED: phantom organ death — sessions that declare a long-running loop
(e.g. "loop 4h") but silently die after a few minutes with no alarm, as measured
on Mini 2026-08-23.  The classic scar is superscar #2 "Esiste != Armato": session
f9dd23da-8d36-4b7b-957d-077091090fec, first_ts → last_ts = 6m31s, declared 240m.

TRAPS ENCODED (so the next reader does not rediscover them):
  - `ls` is eza on this fleet; never shell out to `ls`.
  - `ps | grep claude-code/bin/claude` misses main sessions on Pro and Mini.
  - `lsof … .jsonl` finds nothing — live sessions do not hold transcripts open.
  - Subagents carry `--parent-session-id`, giving an exact alive mapping.
  - `until` is an ordinary English word; it must be narrowed to loop contexts.
  - A run that probed nothing must NOT report clean (blind-scan guard, exit 2).
  - Transcripts never leave the host that owns them.
  - Hard boundaries: never read settings, env, plists; never print full bodies.
"""

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Optional, Tuple, List, Dict, Set

# ---------------------------------------------------------------------------
# status / verdict constants — mirror arsenal_probe.py
# ---------------------------------------------------------------------------
ALIVE = "ALIVE"
NO_PROCESS = "NO-PROCESS"
UNMAPPED = "UNMAPPED"
UNREACHABLE = "UNREACHABLE"

PRODUCING = "PRODUCING"
QUIET = "QUIET"
STALE = "STALE"
DEAD_BUT_DECLARED_LONG = "DEAD-BUT-DECLARED-LONG"

# argv[0] basenames that ARE a Claude Code session (case-sensitive on purpose:
# `Claude` with a capital C is the Electron desktop app, not a session).
SESSION_BINARY_BASENAMES = frozenset({"claude", "claude.exe"})

# Defense-in-depth only — the basename test above is the real discriminator.
NON_SESSION_MARKERS = (
    "/applications/claude.app/",
    "claude-science",
)

# ---------------------------------------------------------------------------
# pure helpers — unit-testable without ssh / subprocess
# ---------------------------------------------------------------------------

def encode_project_dir(cwd: str) -> str:
    """Return the encoded form of an absolute cwd, as used in ~/.claude/projects/."""
    return cwd.replace("/", "-").replace(".", "-")


def is_session_process(command: str) -> bool:
    """Return True if `command` is a Claude Code SESSION process.

    Narrowed at the EXECUTABLE IDENTITY, not at a substring of the whole command
    line. A bare `"claude" in command` test is an over-match that swallows
    `not-claude`, `claude-science`, `tmux -L claude-swarm-...`, `grep -i claude`
    and every tool shell whose argv merely mentions a path under `~/.claude/`
    (superscar #3, guard-over-match). Chasing those with a growing exclusion list
    is a race you lose: the ONE thing every real session shares is that argv[0]'s
    basename is the claude binary itself.

    Measured live on the fleet 2026-08-23 — all four session shapes differ, and a
    naive `ps | grep claude-code/bin/claude` false-negatives on the first two:
        `claude`                                           (Mini main session)
        `claude interactive`                               (Pro main session)
        `/opt/homebrew/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe --agent-id ...`
        `/Users/balizero/.local/share/mise/installs/node/22/.../bin/claude.exe`
    Case is load-bearing: the desktop app's binary is `/Applications/Claude.app/
    Contents/MacOS/Claude` — capital C, and NOT a session. The explicit exclusions
    below are kept as defense-in-depth, not as the primary discriminator.
    """
    if not command or not command.strip():
        return False

    first = command.split()[0]
    base = first.rsplit("/", 1)[-1]
    if base not in SESSION_BINARY_BASENAMES:
        return False

    cmd_lower = command.lower()
    for excl in NON_SESSION_MARKERS:
        if excl in cmd_lower:
            return False

    return True


def parse_ps_output(text: str) -> Tuple[Set[str], Dict[str, int], Set[str]]:
    """
    Parse `ps -eo pid= -o args=` output.
    Returns (alive_parent_sids, subagent_counts, session_pids).
    """
    alive_parent_sids: Set[str] = set()
    subagent_counts: Dict[str, int] = {}
    session_pids: Set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) < 2:
            continue
        pid_str, args = parts
        if not is_session_process(args):
            continue
        session_pids.add(pid_str)
        m = re.search(r"--parent-session-id\s+([\w-]+)", args)
        if m:
            sid = m.group(1)
            alive_parent_sids.add(sid)
            subagent_counts[sid] = subagent_counts.get(sid, 0) + 1
    return alive_parent_sids, subagent_counts, session_pids


def parse_lsof_cwd(text: str) -> Dict[int, str]:
    """Parse `lsof -c claude -a -d cwd -Fpn` output. Returns pid -> cwd."""
    pid_cwd: Dict[int, str] = {}
    current_pid = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("p"):
            try:
                current_pid = int(line[1:])
            except ValueError:
                current_pid = None
        elif line.startswith("n"):
            if current_pid is not None:
                pid_cwd[current_pid] = line[1:]
    return pid_cwd


def identity_slice(text: str) -> str:
    """First user message text, whitespace-collapsed, truncated to 90 chars."""
    collapsed = " ".join(text.split())
    return collapsed[:90]


def declared_long(text: str) -> Tuple[bool, Optional[int]]:
    """Does this session's FIRST message declare a long autonomous run, and how long?

    Returns (declared_long, declared_span_min).

    NARROWED AT THE FALSE POSITIVE, measured — not at the canonical form.
    The first draft accepted any run-ish word within 40 characters of any
    duration. Run live against the real fleet on 2026-08-23 that produced FIVE
    false accusations and the reason is the same every time: the words matched
    the mandate's SUBJECT MATTER, not the mandate's own shape.

        "crash-looped for 73.5 hours with every health indicator reading green"
        "log silenzioso 43h"   /   "~3512 restarts (~29 h) predate the upgrade"
        "inbound stale 3h during business hours -> P1 fires"
        "(2) non fermarti al primo verdetto verde"      (a quoted lesson)
        "iterate until GREEN"                           (an ordinary build step)

    Every one of those is a session TALKING ABOUT durations and loops, which is
    exactly what this fleet's sessions do all day. A detector that accuses them
    gets muted, and a muted detector is the disease this tool exists to cure.

    The two TRUE positives on the same run share one shape — the duration sits
    ADJACENT to the run word, because that is how a mandate declares its own
    span:
        "# HEALER-MANDATE - sessione autonoma di cura (Mini-Pro2, loop 4h)"
        "# HEALER-PRO-MANDATE - sessione autonoma di cura runtime (Pro, loop 6h)"

    So: a duration must be named AND adjacent to a run word (either order, at
    most a few separator characters between them). `H24` counts on its own — it
    IS a span. A run word with no measurable span is deliberately NOT enough:
    without a number there is nothing to compare the transcript against, and the
    verdict would degrade to "stale and vaguely autonomous", which is every
    finished session on the fleet.

    `loop` is additionally guarded against compounds (`crash-loop`,
    `restart-loop`, `heal-loop`): a hyphen before it means the text is naming a
    failure mode, not issuing an instruction.
    """
    if not text:
        return False, None

    spans: List[int] = []

    # H24 is a span by itself (24h), but only as a standalone token.
    if re.search(r"(?<![\w-])H24(?![\w-])", text, re.IGNORECASE):
        spans.append(1440)

    unit_min = {
        "h": 60, "hr": 60, "hrs": 60, "hour": 60, "hours": 60, "ora": 60, "ore": 60,
        "m": 1, "min": 1, "mins": 1, "minute": 1, "minutes": 1, "minuto": 1, "minuti": 1,
    }
    # A run word, NOT preceded by a hyphen (kills `crash-loop`).
    run_word = r"(?<!-)\b(?:loop|autonomous|autonomo|autonoma|non-?stop|nonstop|continuous(?:ly)?|h24)\b"
    duration = r"(\d{1,4})\s*(h|hrs?|hours?|ore|ora|m|mins?|minutes?|minuti|minuto)\b"
    # ADJACENCY, both orders: at most 3 separator chars ("loop 4h", "4h loop",
    # "loop: 4h", "loop - 6h"). Not a 40-char window.
    joiner = r"[\s:\-\u2013\u2014,]{0,3}"

    for pat in (run_word + joiner + duration, duration + joiner + run_word):
        for m in re.finditer(pat, text, re.IGNORECASE):
            num = int(m.group(1))
            unit = m.group(2).lower()
            mult = unit_min.get(unit)
            if mult is None:
                continue
            minutes = num * mult
            # Sanity floor/ceiling: under 10 minutes is not a "long run"
            # declaration, and over 7 days is a number that wandered in.
            if 10 <= minutes <= 7 * 24 * 60:
                spans.append(minutes)

    if not spans:
        return False, None
    return True, max(spans)


def classify_verdict(
    stale_min: float,
    alive: str,
    declared_long: bool,
    declared_span_min: Optional[int],
    transcript_span_min: Optional[float],
    quiet_min: int,
    stale_min_threshold: int,
) -> str:
    if stale_min < quiet_min:
        verdict = PRODUCING
    elif quiet_min <= stale_min < stale_min_threshold:
        verdict = QUIET
    else:
        verdict = STALE

    if (
        declared_long
        and alive != ALIVE
        and stale_min >= stale_min_threshold
        and (
            declared_span_min is None
            or (transcript_span_min is not None and transcript_span_min < declared_span_min)
        )
    ):
        verdict = DEAD_BUT_DECLARED_LONG

    return verdict


# ---------------------------------------------------------------------------
# remote execution support
# ---------------------------------------------------------------------------

_SCRIPT_SOURCE: Optional[str] = None


def _get_script_source() -> str:
    global _SCRIPT_SOURCE
    if _SCRIPT_SOURCE is None:
        with open(__file__, "r") as f:
            _SCRIPT_SOURCE = f.read()
    return _SCRIPT_SOURCE


def run_host_probe(host: str, argv: List[str], timeout: int) -> Tuple[int, str, str]:
    """
    Mock boundary for tests.  Ships this script's source over ssh to `host`.
    """
    source = _get_script_source()
    ssh_cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={min(timeout, 8)}",
        host,
        "python3",
        "-",
        *argv,
    ]
    # ONE RETRY, deliberately (superscar #8, network flap / proxy fragility).
    # Measured 2026-08-23: the very same probe to `pro` timed out once at 20s and
    # then completed in 1.6s, twice, unchanged. A single transient is a busy box,
    # not a dead one — reporting it UNREACHABLE would spend the healer's Telegram
    # ladder on a machine that is fine, and an alarm that cries wolf gets muted,
    # which is how coverage dies. Two consecutive failures ARE the signal.
    last_exc: Optional[BaseException] = None
    for attempt in (1, 2):
        try:
            proc = subprocess.run(
                ssh_cmd,
                input=source,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            last_exc = exc
            if attempt == 2:
                raise
            continue
        if proc.returncode == 0 or attempt == 2:
            return proc.returncode, proc.stdout, proc.stderr
    # unreachable in practice; keeps the type checker and the reader honest
    raise last_exc if last_exc else RuntimeError("run_host_probe: no attempt ran")


# ---------------------------------------------------------------------------
# local probe
# ---------------------------------------------------------------------------

def probe_local(
    lookback_min: int,
    quiet_min: int,
    stale_min: int,
) -> Dict[str, Any]:
    home = os.path.expanduser("~")
    hostname = platform.node()
    projects_dir = os.path.join(home, ".claude", "projects")
    if not os.path.isdir(projects_dir):
        return {"machine": hostname, "sessions": [], "status": "OK", "skipped_unreadable": 0}

    # gather process info
    try:
        ps_out = subprocess.check_output(
            ["ps", "-eo", "pid=", "-o", "args="], text=True, timeout=10
        )
    except Exception:
        ps_out = ""
    alive_parent_sids, subagent_counts, session_pids = parse_ps_output(ps_out)

    # ASK lsof ABOUT THE PIDs ps ALREADY FOUND — never `lsof -c claude`.
    # `-c` matches the process NAME, and MEASURED live 2026-08-23: on Pro the
    # session processes' comm does NOT contain "claude" (the binary lives under
    # ~/.local/share/claude/versions/...), so `lsof -c claude -a -d cwd` returns
    # ZERO rows there while four sessions are demonstrably running. That blind
    # mapping is what made every Pro row read NO-PROCESS — a claim the tool had
    # no evidence for, on a host where sessions had written 6 seconds earlier.
    # `lsof -p <pid-list> -a -d cwd -Fpn` on the pids ps already classified
    # works on BOTH machines and drops the name dependency entirely.
    lsof_out = ""
    if session_pids:
        try:
            lsof_out = subprocess.check_output(
                ["lsof", "-p", ",".join(sorted(session_pids)), "-a", "-d", "cwd", "-Fpn"],
                text=True,
                timeout=15,
            )
        except subprocess.CalledProcessError as exc:
            # lsof exits non-zero when SOME pid is gone; keep whatever it printed
            lsof_out = exc.output or ""
        except Exception:
            lsof_out = ""
    pid_cwd = parse_lsof_cwd(lsof_out)

    # Can we attribute processes to project dirs AT ALL on this host? If ps sees
    # live sessions but lsof gave us nothing, the honest answer for a session we
    # cannot place is UNMAPPED — never NO-PROCESS, which asserts an absence we
    # did not observe.
    mapping_available = bool(pid_cwd) or not session_pids

    # cwd → encoded mapping, only from session processes
    cwd_to_encoded: Dict[str, str] = {}
    for pid, cwd in pid_cwd.items():
        if str(pid) in session_pids:
            cwd_to_encoded.setdefault(encode_project_dir(cwd), cwd)

    now = time.time()
    lookback_sec = lookback_min * 60
    sessions: List[Dict[str, Any]] = []
    skipped_unreadable = 0

    # ONE TRANSCRIPT, MANY PATHS (measured live 2026-08-23). On Mini AND on M5,
    # ~/.claude/projects/-Users-<u>-nuzantara is a SYMLINK to
    # -Users-<u>-Desktop-nuzantara (because ~/Desktop/nuzantara is itself a
    # symlink to ~/nuzantara). os.listdir therefore walks the same real files
    # twice and the same session is reported twice — 29 rows for 17 sessions,
    # and every finding double-counted. Identity is the INODE, never the path:
    # dedup on (st_dev, st_ino). Measured proof: both paths to
    # 733cf2de-...jsonl report inode=53353008.
    seen_inodes = set()
    seen_sessions = {}

    for encoded_dir in os.listdir(projects_dir):
        dir_path = os.path.join(projects_dir, encoded_dir)
        if not os.path.isdir(dir_path):
            continue
        for fname in os.listdir(dir_path):
            if not fname.endswith(".jsonl"):
                continue
            session_id = fname[:-6]  # remove .jsonl
            fpath = os.path.join(dir_path, fname)
            try:
                st = os.stat(fpath)
                inode_key = (st.st_dev, st.st_ino)
                if inode_key in seen_inodes:
                    continue
                seen_inodes.add(inode_key)
                mtime = st.st_mtime
                size = st.st_size
                if now - mtime > lookback_sec:
                    continue

                # Read the transcript once
                with open(fpath, "r") as f:
                    lines = f.readlines()

                first_ts: Optional[datetime] = None
                last_ts: Optional[datetime] = None
                identity = None
                first_msg_text = ""
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(record, dict):
                        continue
                    ts_str = record.get("timestamp") or record.get("created_at") or record.get("ts")
                    if ts_str:
                        try:
                            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        except Exception:
                            dt = None
                        if dt:
                            if first_ts is None:
                                first_ts = dt
                            last_ts = dt
                    if record.get("isMeta"):
                        continue
                    if record.get("type") == "user" and identity is None:
                        message = record.get("message", {})
                        content = message.get("content")
                        if isinstance(content, str):
                            first_msg_text = content
                        elif isinstance(content, list):
                            texts = []
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text" and "text" in block:
                                    texts.append(block["text"])
                            first_msg_text = " ".join(texts)
                        identity = identity_slice(first_msg_text)
                if identity is None:
                    identity = ""

                transcript_span_min = None
                if first_ts and last_ts:
                    span = (last_ts - first_ts).total_seconds() / 60.0
                    transcript_span_min = round(span, 1)

                is_long, span_min = declared_long(first_msg_text)

                # alive determination — three honest states, never a guess
                if session_id in alive_parent_sids:
                    alive = ALIVE          # positive: a live subagent names it
                elif not mapping_available:
                    alive = UNMAPPED       # live sessions exist, unattributable
                else:
                    alive = NO_PROCESS     # positive: nothing runs in that dir
                    for cwd in cwd_to_encoded.values():
                        if encode_project_dir(cwd) == encoded_dir:
                            alive = UNMAPPED
                            break

                # cwd: prefer live process cwd, else fallback to encoded dir
                cwd = cwd_to_encoded.get(encoded_dir, encoded_dir)

                subagents = subagent_counts.get(session_id, 0)
                stale_min_val = (now - mtime) / 60.0
                verdict = classify_verdict(
                    stale_min=stale_min_val,
                    alive=alive,
                    declared_long=is_long,
                    declared_span_min=span_min,
                    transcript_span_min=transcript_span_min,
                    quiet_min=quiet_min,
                    stale_min_threshold=stale_min,
                )

                # A session id reached by two DISTINCT files (not the symlink
                # case above) is ambiguous: keep the FRESHEST, because a stale
                # leftover copy would flag a live lane as dead.
                prev = seen_sessions.get(session_id)
                if prev is not None and prev["mtime_epoch"] >= mtime:
                    continue
                if prev is not None:
                    sessions.remove(prev)

                row = dict(
                    {
                        "session_id": session_id,
                        "project_dir": encoded_dir,
                        "cwd": cwd,
                        "mtime_epoch": mtime,
                        "mtime_iso": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
                        "stale_min": round(stale_min_val, 1),
                        "size_bytes": size,
                        "identity": identity,
                        "declared_long": is_long,
                        "declared_span_min": span_min,
                        "transcript_span_min": transcript_span_min,
                        "subagents": subagents,
                        "alive": alive,
                        "verdict": verdict,
                    }
                )
                sessions.append(row)
                seen_sessions[session_id] = row
            except Exception:
                skipped_unreadable += 1
                continue

    return {"machine": hostname, "sessions": sessions, "status": "OK", "skipped_unreadable": skipped_unreadable}


# ---------------------------------------------------------------------------
# table rendering — arsenal_probe.py style
# ---------------------------------------------------------------------------

def render_fleet_table(results: List[Dict[str, Any]], hosts_list: List[str]) -> str:
    """Render a single table for the whole fleet run."""
    from_host = platform.node()
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    lines = [f"fleet_sessions — from {from_host} — {ts}"]
    header = (
        f"{'HOST':8} {'MACHINE':20} {'SESSION_ID':40} {'PROJECT':30} {'CWD':30} "
        f"{'MTIME':20} {'STALE':>6} {'ALIVE':12} {'SUB':>4} {'VERDICT':26} {'IDENTITY'}"
    )
    lines.append(header)
    lines.append("-" * 200)

    total_sessions = 0
    dead_but_declared = 0
    unreachable = 0
    ok_hosts = 0
    total_skipped = 0

    for r in results:
        host_token = r.get("host", "?")
        machine = r.get("machine", "?")
        status = r.get("status", "OK")
        if status == UNREACHABLE:
            reason = r.get("reason", "unknown")
            lines.append(
                f"{host_token:8} {machine:20} {'UNREACHABLE':40} {'':30} {'':30} "
                f"{'':20} {'':>6} {'':12} {'':4} {'':26} {reason}"
            )
            unreachable += 1
        else:
            ok_hosts += 1
            sessions = r.get("sessions", [])
            total_sessions += len(sessions)
            for s in sessions:
                if s["verdict"] == DEAD_BUT_DECLARED_LONG:
                    dead_but_declared += 1
                lines.append(
                    f"{host_token:8} {machine:20} {s['session_id']:40} {s['project_dir']:30} "
                    f"{s['cwd']:30} {s['mtime_iso']:20} {s['stale_min']:5.1f}m "
                    f"{s['alive']:12} {s['subagents']:4} "
                    f"{s['verdict']:26} {s['identity']}"
                )
            total_skipped += r.get("skipped_unreadable", 0)

    N = ok_hosts
    M = len(hosts_list)
    D = dead_but_declared
    U = unreachable
    S = total_sessions
    lines.append(f"{N} of {M} hosts probed — {S} sessions — {D} DEAD-BUT-DECLARED-LONG, {U} unreachable")
    if total_skipped > 0:
        lines.append(f"{total_skipped} transcripts skipped (unreadable)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# selftest — embedded guilt + innocence corpus
# ---------------------------------------------------------------------------

def _selftest() -> None:
    """Run embedded tests; exit 0 on success, 1 on failure."""
    errors = []

    # 1. encode_project_dir
    e = encode_project_dir("/Users/nuzantara/nuzantara/.worktrees/backend-rag-seq8")
    assert e == "-Users-nuzantara-nuzantara--worktrees-backend-rag-seq8", f"encode fail: {e}"
    e2 = encode_project_dir("/private/tmp")
    assert e2 == "-private-tmp", f"encode fail: {e2}"

    # 2. is_session_process
    assert is_session_process("claude") is True
    assert is_session_process("claude interactive") is True
    assert is_session_process("/opt/homebrew/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe --agent-id ...") is True
    assert is_session_process("/Applications/Claude.app/Contents/MacOS/Claude") is False
    assert is_session_process("chrome-native-host chrome-extension://...") is False
    assert is_session_process("/Users/balizero/.claude-science/bin/claude-science serve --app") is False
    assert is_session_process("tmux -L claude-swarm-42327 new-session ...") is False
    assert is_session_process("python /Users/nuzantara/.claude/daemons/guardrails.py") is False
    assert is_session_process("python /Users/nuzantara/.claude/skills/bali-zero-brand/_damar-queue-server.py") is False
    assert is_session_process("/bin/zsh -c source /Users/nuzantara/.claude/shell-snapshots/... && eval '...'") is False

    # 3. parse_ps_output (now returns session_pids as well)
    ps_txt = """\
1234 claude
1235 claude interactive
1236 /opt/homebrew/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe --agent-id X@session-c03d6208 --agent-name X --team-name session-c03d6208 --parent-session-id c03d6208-a9fa-4db2-a78a-638b4f5f8122 --agent-type ... --model sonnet
1237 /Applications/Claude.app/Contents/MacOS/Claude
"""
    parent_sids, counts, session_pids = parse_ps_output(ps_txt)
    assert "c03d6208-a9fa-4db2-a78a-638b4f5f8122" in parent_sids
    assert counts.get("c03d6208-a9fa-4db2-a78a-638b4f5f8122", 0) == 1
    assert session_pids == {"1234", "1235", "1236"}

    # 4. parse_lsof_cwd
    lsof_txt = """\
p1234
fcwd
n/Users/nuzantara/nuzantara/.worktrees/backend-rag-seq8
p1235
fcwd
n/private/tmp
"""
    pid_cwd = parse_lsof_cwd(lsof_txt)
    assert pid_cwd[1234] == "/Users/nuzantara/nuzantara/.worktrees/backend-rag-seq8"
    assert pid_cwd[1235] == "/private/tmp"

    # D10: UNMAPPED uses only session pids — filter pid_cwd by session_pids
    ps_txt2 = "1234 claude\n1235 not-claude"
    lsof_txt2 = "p1234\nfcwd\nn/proj\np1235\nfcwd\nn/other"
    _, _, session_pids2 = parse_ps_output(ps_txt2)
    pid_cwd2 = parse_lsof_cwd(lsof_txt2)
    cwd_to_encoded_test = {}
    for pid, cwd in pid_cwd2.items():
        if str(pid) in session_pids2:
            cwd_to_encoded_test.setdefault(encode_project_dir(cwd), cwd)
    assert len(cwd_to_encoded_test) == 1
    assert encode_project_dir("/proj") in cwd_to_encoded_test

    # 5. identity_slice
    long_msg = "This is a very long message that should be truncated to exactly the length limit"
    s = identity_slice(long_msg)
    assert len(s) <= 90
    assert "\n" not in s
    multi_line = "line1\nline2\nline3"
    s2 = identity_slice(multi_line)
    assert s2 == "line1 line2 line3"[:90]

    # 6. declared_long — guilt
    l, span = declared_long("loop 4h")
    assert l is True
    assert span == 240

    # 7. declared_long — innocence (short one-shot, no long-run phrase)
    l2, span2 = declared_long("wait until the tests pass")
    assert l2 is False

    # 8. classified verdict
    v = classify_verdict(
        stale_min=193.0,
        alive=NO_PROCESS,
        declared_long=True,
        declared_span_min=240,
        transcript_span_min=6.5,
        quiet_min=5,
        stale_min_threshold=45,
    )
    assert v == DEAD_BUT_DECLARED_LONG, f"expected DEAD_BUT_DECLARED_LONG, got {v}"

    v2 = classify_verdict(
        stale_min=1.0,
        alive=ALIVE,
        declared_long=True,
        declared_span_min=240,
        transcript_span_min=6.5,
        quiet_min=5,
        stale_min_threshold=45,
    )
    assert v2 == PRODUCING, f"expected PRODUCING, got {v2}"

    v3 = classify_verdict(
        stale_min=60.0,
        alive=NO_PROCESS,
        declared_long=False,
        declared_span_min=None,
        transcript_span_min=None,
        quiet_min=5,
        stale_min_threshold=45,
    )
    assert v3 == STALE, f"expected STALE, got {v3}"

    print("selftest PASSED")
    sys.exit(0)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fleet session auditor — detect phantom organ death",
        add_help=True,
    )
    parser.add_argument("--table", action="store_true", default=False, help="Output as table (default)")
    parser.add_argument("--json", action="store_true", default=False, help="Output as JSON")
    parser.add_argument(
        "--hosts",
        default="local,pro,air",
        help="Comma-separated list of hosts to probe (default: local,pro,air)",
    )
    parser.add_argument(
        "--lookback-min",
        type=int,
        default=360,
        help="Ignore transcripts older than this many minutes (default: 360)",
    )
    parser.add_argument(
        "--quiet-min",
        type=int,
        default=5,
        help="Age threshold for PRODUCING → QUIET (default: 5)",
    )
    parser.add_argument(
        "--stale-min",
        type=int,
        default=45,
        help="Age threshold for QUIET → STALE (default: 45)",
    )
    parser.add_argument(
        "--ssh-timeout",
        type=int,
        default=45,
        help="Wall-clock timeout per SSH probe attempt (default: 45; two attempts)",
    )
    parser.add_argument("--selftest", action="store_true", default=False, help="Run embedded tests")
    parser.add_argument("--__host-probe", dest="host_probe", action="store_true", help=argparse.SUPPRESS)

    args = parser.parse_args(argv)

    if args.selftest:
        _selftest()
        return 0  # unreachable

    if args.host_probe:
        # Hidden mode: run local probe and print JSON
        try:
            report = probe_local(
                lookback_min=args.lookback_min,
                quiet_min=args.quiet_min,
                stale_min=args.stale_min,
            )
            json.dump(report, sys.stdout, indent=2)
        except Exception as exc:
            json.dump(
                {"machine": platform.node(), "status": UNREACHABLE, "reason": f"{type(exc).__name__}: {str(exc)[:200]}"},
                sys.stdout,
                indent=2,
            )
        return 0

    hosts = [h.strip() for h in args.hosts.split(",") if h.strip()]
    results: List[Dict[str, Any]] = []
    any_successful_probe = False
    any_finding = False

    for host in hosts:
        if host == "local":
            try:
                report = probe_local(
                    lookback_min=args.lookback_min,
                    quiet_min=args.quiet_min,
                    stale_min=args.stale_min,
                )
                report["host"] = "local"
                results.append(report)
                any_successful_probe = True
                for s in report.get("sessions", []):
                    if s["verdict"] == DEAD_BUT_DECLARED_LONG:
                        any_finding = True
            except Exception as exc:
                results.append(
                    {
                        "host": "local",
                        "machine": None,
                        "status": UNREACHABLE,
                        "reason": f"{type(exc).__name__}: {str(exc)[:200]}",
                    }
                )
                any_finding = True
        else:
            remote_argv = [
                "--__host-probe",
                f"--lookback-min={args.lookback_min}",
                f"--quiet-min={args.quiet_min}",
                f"--stale-min={args.stale_min}",
            ]
            try:
                rc, stdout, stderr = run_host_probe(host, remote_argv, args.ssh_timeout)
                if rc == 0:
                    report = json.loads(stdout)
                    report["host"] = host
                    results.append(report)
                    any_successful_probe = True
                    for s in report.get("sessions", []):
                        if s["verdict"] == DEAD_BUT_DECLARED_LONG:
                            any_finding = True
                else:
                    results.append(
                        {
                            "host": host,
                            "machine": None,
                            "status": UNREACHABLE,
                            "reason": f"ssh exit {rc}: {stderr.strip()}",
                        }
                    )
                    any_finding = True
            except Exception as exc:
                results.append(
                    {"host": host, "machine": None, "status": UNREACHABLE, "reason": f"{type(exc).__name__}: {str(exc)[:200]}"}
                )
                any_finding = True

    # Blind-scan guard (superscar #2 — a run that probed nothing must never
    # report clean). Exit 2, but STILL EMIT THE REPORT below: "I know nothing,
    # and here is the evidence of why" is strictly more useful to a consumer
    # than an empty stdout, and the healer's own parse step should never have
    # to distinguish "no output" from "no findings".
    if not any_successful_probe:
        print("BLIND: no host produced a successful probe", file=sys.stderr)
        exit_code = 2
    else:
        exit_code = 1 if any_finding else 0

    if args.json:
        from_host = platform.node()
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        hosts_ok = sum(1 for r in results if r.get("status") != UNREACHABLE)
        hosts_unreachable = sum(1 for r in results if r.get("status") == UNREACHABLE)
        unreachable_hosts = [r["host"] for r in results if r.get("status") == UNREACHABLE]
        sessions_total = sum(len(r.get("sessions", [])) for r in results)
        producing = quiet = stale = dead_but_declared = 0
        findings = []
        for r in results:
            for s in r.get("sessions", []):
                verdict = s.get("verdict")
                if verdict == PRODUCING:
                    producing += 1
                elif verdict == QUIET:
                    quiet += 1
                elif verdict == STALE:
                    stale += 1
                elif verdict == DEAD_BUT_DECLARED_LONG:
                    dead_but_declared += 1
                if verdict == DEAD_BUT_DECLARED_LONG:
                    findings.append(
                        {
                            "host": r.get("host"),
                            "session_id": s["session_id"],
                            "identity": s["identity"],
                            "stale_min": s["stale_min"],
                            "declared_span_min": s["declared_span_min"],
                            "transcript_span_min": s["transcript_span_min"],
                        }
                    )
        summary = {
            "hosts_requested": len(hosts),
            "hosts_ok": hosts_ok,
            "hosts_unreachable": hosts_unreachable,
            "unreachable_hosts": unreachable_hosts,
            "sessions_total": sessions_total,
            "producing": producing,
            "quiet": quiet,
            "stale": stale,
            "dead_but_declared_long": dead_but_declared,
            "findings": findings,
        }
        output = {
            "schema_version": 1,
            "from_host": from_host,
            "ts": ts,
            "hosts": results,
            "summary": summary,
        }
        json.dump(output, sys.stdout, indent=2)
    else:
        # default table
        print(render_fleet_table(results, hosts))

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
