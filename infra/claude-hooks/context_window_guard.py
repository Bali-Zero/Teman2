#!/usr/bin/env python3
"""context_window_guard.py — PreToolUse hard-gate: short windows per role.

MANDATE (Zero, 2026-09-09): "sopra il 40% di contesto il modello si
indebolisce; forzarlo ad aprire una nuova finestra, incollare il mandato e
proseguire lì". This hook ENFORCES that: once a session's estimated context
crosses its role's percent-of-window threshold, every tool call is DENIED
except the handful needed to hand off cleanly (save memory, write the
handoff artifact, delegate via SendMessage/TaskStop) — the same discipline
`orchestrate_gate.py` already applies to "stop doing everything yourself",
here applied to "stop working in a window that is already too big".

REUSE, NOT REINVENTION (repo doctrine — cicatrix scar family, "never build a
second estimator"):
  - Token estimate: `last_context_tokens()` in
    `~/.tokenaudit/hooks/context_hygiene.py` (S1, the same function whose
    "[tokenaudit] Context ~NNNK tokens" nudge every session has already
    seen). Loaded by file path via `importlib` — that hook lives in HOME,
    detached from this repo's venv, exactly like `model_routing_gate.py`
    already does for `scripts/evidence_pack_lint.py`'s HOTZONE_PATTERNS (see
    that file's "HOTZONE_PATTERNS sourcing" docstring section). Never
    reimplemented here: if the HOME file is missing or unreadable, the
    token estimate is UNVERIFIABLE and this gate fails open (cannot-verify
    is not a verdict — cicatrix scar #6 discipline already used by every
    other PreToolUse gate in this directory).
  - Handoff artifact: `parse_transcript_jsonl()` in
    `~/.claude/hooks/precompact-mnemos.py` (the PreCompact hook, registered
    in `~/.claude/settings.json` hooks.PreCompact) writes
    `~/.claude/state/precompact-handoff-<session_id>.json` — the EXACT file
    the `/resume` skill reads (`~/.claude/commands/resume.md` step 2:
    `ls -t ~/.claude/state/precompact-handoff-*.json`). This hook produces
    the SAME artifact, at the SAME path, via the SAME parser, so a fresh
    window that runs `/resume` after being forced open by this gate sees the
    handoff exactly as if the harness itself had compacted — that is the
    whole point of "open a new window, paste the mandate, continue there".

THRESHOLD BY ROLE (env `CONTEXT_GUARD_ROLE`, case-insensitive):
  imperator                       -> 20 %  (matches
                                     docs/architecture/dual-consul/army-map.md
                                     §4's own "short window" language for
                                     that rank)
  general | dux | builder | (any
  other value, including unset)   -> 40 %  (the mandate's own number)
  `CONTEXT_GUARD_PCT` overrides either default (a value > 1 is read as a
  percentage, e.g. "35"; a value <= 1 is read as a fraction, e.g. "0.35").

WINDOW SIZE: `CONTEXT_WINDOW_TOKENS` env overrides everything. Otherwise
1,000,000 if the session's model string ends with `[1m]` or contains "1m"
(the fleet's own suffix convention — see e.g. `claude-opus-5[1m]` in
`research/design/2026-08-31-web-design-sixteen-lane-corpus/reports/L04-price.md`
and `docs/architecture/dual-consul/army-map.md` §5), read from the last
assistant transcript record's `message.model` field (same record
`last_context_tokens()` itself scans), with `CONTEXT_GUARD_MODEL` as an env
fallback for a transcript that has no assistant record yet. Otherwise
200,000 (the harness default).

GRACE: never fires before `GRACE_TURNS` (30) assistant turns — a session
that just started cannot possibly be "too big", and the estimator's own
tail-read can be noisy on a very short transcript.

Kill switch: `CONTEXT_GUARD_OFF=1` — same escape-hatch pattern as
`ORCHESTRATE_GATE_OFF`/`ROUTING_FLOOR_OK`, checked first, unconditionally.

ALLOW-LIST once at/above threshold (the only things a hand-off needs):
  - any Bash command containing "mem save" (`~/.claude/scripts/mem save ...`)
  - a Write/Edit whose `file_path` IS this session's own handoff file (so a
    session that wants to enrich the handoff by hand still can)
  - `SendMessage`, `TaskStop` (delegate to a peer / end the turn cleanly)
  - `ToolSearch`, but ONLY for a query naming one of those two: in a harness
    that defers tool schemas they are names with no parameters until their
    definition is fetched, so denying the fetch denied the hand-off this guard
    is telling the session to make. An unrelated search stays denied.
Everything else — including a bare `Bash`/`Write`/`Edit`/`Agent` that is not
one of the above — is DENIED (exit 2), in Italian, naming the exact percent,
threshold, handoff path, the evidence for the window it computed, and the
three SELF-CURE routes below (`/resume`, the `! python3` env fix, the kill
switch).

Fail-open (exit 0), same discipline as every sibling gate in this
directory: unparseable payload, unreadable transcript, missing/unreadable
estimator, fewer than GRACE_TURNS assistant turns. This is an economy/
discipline guard, not a security boundary — a broken copy of it must never
paralyze the harness (cicatrix scar #2, Esiste!=Armato, cuts both ways: a
gate that blocks everything when it is itself broken teaches the kill
switch, same lesson `orchestrate_gate.py`'s DISARM AUDIBILITY note already
draws).

SELF-CURE (Zero, 2026-09-09 — the bug this section documents): a session
denied at 85K tokens because `~/.claude/settings.json` env lacked
`CONTEXT_WINDOW_TOKENS=1000000` could not cure it — editing that file is
itself a tool call, and the guard denies tool calls. The deny message
below now states its own evidence (model string seen, window assumed and
WHY, threshold role) and three routes, IN ORDER:
  1. `/resume` in a brand-new window (`claude --model <model>` then
     `/resume`) — the intended, cheap fix.
  2. If the WINDOW ITSELF is wrong on this machine (this bug's actual
     cause): the owner types the fix in the Claude Code PROMPT BAR with a
     `!` prefix (`! python3 -c "..."`, see `ESCAPE_ONE_LINER` below) — a
     `!`-prefixed line runs in the session's own shell and does NOT pass
     through PreToolUse hooks, so it is not itself denied. It rewrites
     `~/.claude/settings.json`'s `env` block (backing up to `.json.bak`
     first) and the harness hot-reloads it — verified live 2026-09-09.
  3. `CONTEXT_GUARD_OFF=1` — last resort, same kill switch as always.
Route 2 is the fix for a WRONG window, not a substitute for route 1: a
session whose window is already correct and is simply over threshold
should still open a fresh window.
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from gate_coverage import record as _gc_record
except Exception:
    def _gc_record(hook_name, decision, payload=None):
        pass

GRACE_TURNS = 30
DEFAULT_WINDOW = 200_000
LARGE_WINDOW = 1_000_000
DEFAULT_THRESHOLD = 0.40
ROLE_THRESHOLDS = {"imperator": 0.20}
HANDOFF_RATE_LIMIT_S = 600
TAIL_BYTES = 400_000  # same tail size context_hygiene.py's own estimator reads

REPORTING_TOOLS = ("SendMessage", "TaskStop")
ALLOWED_TOOLS_UNCONDITIONAL = set(REPORTING_TOOLS)

ASSISTANT_TYPE_RE = re.compile(r'"type"\s*:\s*"assistant"')

# The self-cure one-liner printed verbatim in the deny message (see module
# docstring's SELF-CURE section, route 2): typed with a `!` prefix at the
# Claude Code prompt bar, it runs in the session's own shell — NOT through
# PreToolUse hooks — so it is not itself denied by this same guard. It backs
# up ~/.claude/settings.json to .json.bak before writing, then sets
# CONTEXT_WINDOW_TOKENS=1000000 in the env block; the harness hot-reloads
# that file (verified live on M5, 2026-09-09).
ESCAPE_ONE_LINER = (
    'python3 -c "import json,pathlib as p;'
    "h=p.Path.home()/'.claude/settings.json';"
    "h.with_suffix('.json.bak').write_text(h.read_text());"
    "d=json.load(open(h));"
    "d.setdefault('env',{})['CONTEXT_WINDOW_TOKENS']='1000000';"
    "json.dump(d,open(h,'w'),indent=2)\""
)


def _home() -> Path:
    # pathlib.Path.home() re-reads $HOME at call time, not at import time —
    # required for tests to isolate via env HOME=<tmp>, same convention
    # test_model_routing_gate_floor.py already uses for this directory's
    # other PreToolUse gates.
    return Path.home()


def _estimator_path() -> Path:
    return _home() / ".tokenaudit" / "hooks" / "context_hygiene.py"


def _precompact_hook_path() -> Path:
    return _home() / ".claude" / "hooks" / "precompact-mnemos.py"


def _state_dir() -> Path:
    return _home() / ".claude" / "state"


def _guard_state_dir() -> Path:
    return _home() / ".claude" / "state" / "context-window-guard"


def _handoff_path(session_id: str) -> Path:
    return _state_dir() / f"precompact-handoff-{session_id}.json"


# ---------------------------------------------------------------------------
# WINDOW JUMP (Ruling Zero 2026-09-09, research/operations/2026-09-09-window-
# jump-automatic-handoff-it.md): the first trip of this gate must not end with
# "apri una finestra nuova" addressed to a human. It writes pending-jump.json
# and — on a Ghostty interactive seat — spawns window_jump.sh (⌘N, `nz-jump`,
# then `/exit` into the old window once the new session reports in). Headless
# seats get only the file: the cascade wrapper re-invokes `claude -p` on it.
# The new session's SessionStart hook (context_jump_resume.py) injects the
# handoff and stamps `to_session`. Cap: JUMP_MAX_HOPS per chain — a mandate
# that never converges must stop and escalate, not hop forever.
# Kill switch: CONTEXT_JUMP_OFF=1 (the deny itself stays: that is Rule 1).
# ---------------------------------------------------------------------------
JUMP_MAX_HOPS = 3
JUMP_MAX_GESTURES = 3   # window gestures per session before it is a human problem
JUMP_STALE_S = 60       # a jump file this old with no to_session never landed
MANDATE_MAX_CHARS = 6000


def _jump_dir() -> Path:
    return _home() / ".organism" / "context-guard"


def _pending_jump_path(from_session: str) -> Path:
    # One file PER SESSION: two windows tripping at once must never overwrite
    # each other's jump (cicatrix #5, sibling race on shared state).
    return _jump_dir() / f"pending-jump-{from_session}.json"


def _chain_link(from_session: str) -> dict | None:
    """The jump that PRODUCED this session (to_session == from_session), if any:
    it carries the chain's hop count and the ORIGINAL mandate — hop 2's own
    transcript starts with nz-jump's stub, not with the mandate."""
    try:
        for f in _jump_dir().glob("pending-jump-*.json"):
            try:
                j = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(j, dict) and j.get("to_session") == from_session:
                return j
    except OSError:
        pass
    return None


def _window_jump_script() -> Path:
    return _home() / ".claude" / "hooks" / "window_jump.sh"


def _first_user_mandate(transcript_path: str) -> str:
    """The FIRST real user prompt of the transcript, in full (capped). The
    handoff's `objective` (precompact-mnemos) keeps only prompts under 500
    chars — measured 2026-09-09: a structured mandate came out as [] — so
    the jump carries the mandate itself. Head-read, not tail-read: the first
    prompt of a long session lives outside the 400K tail."""
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="ignore") as fh:
            # The first prompt is within the first few records; past 400 lines
            # (hook/system injections come first) give up and return "" rather
            # than scan a multi-MB transcript on every denied call.
            for _ in range(400):
                line = fh.readline()
                if not line:
                    break
                if '"user"' not in line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                msg = rec.get("message") if isinstance(rec.get("message"), dict) else {}
                is_user = rec.get("type") == "user" or msg.get("role") == "user"
                if not is_user:
                    continue
                content = msg.get("content", rec.get("content"))
                text = ""
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    text = "\n".join(str(b.get("text", "")) for b in content
                                     if isinstance(b, dict) and b.get("type") == "text")
                text = text.strip()
                if len(text) < 20 or text.startswith("<") or "tool_result" in line[:200]:
                    continue
                return text[:MANDATE_MAX_CHARS]
    except OSError:
        pass
    return ""


def _claude_pid() -> int:
    """The PID of the `claude` process this hook runs under.

    From a PreToolUse hook os.getppid() IS claude, and that is what the jump
    file has always carried. Invoked OUTSIDE the hook — a session curing its own
    guard from the prompt bar, a probe, a test harness — the parent is a shell,
    and window_jump.sh's SIGINT×2 fallback would then interrupt that SHELL while
    the old claude kept running (measured 2026-09-09, session a60e0124: from_pid
    was a shell). So walk UP the process chain and take the nearest ancestor
    whose executable is claude's; fall back to getppid(), which is already the
    right answer in the hook case.

    Entity, not substring (cicatrix #3): the match is on a whole path COMPONENT
    or the basename — the installed CLI runs as
    ~/.local/share/claude/versions/<ver>, whose basename is a version number.
    """
    fallback = os.getppid()
    cur, seen = fallback, set()
    for _ in range(12):
        if cur <= 1 or cur in seen:
            break
        seen.add(cur)
        try:
            out = subprocess.run(["ps", "-o", "ppid=,comm=", "-p", str(cur)],
                                 capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            break
        line = (out.stdout or "").strip()
        if not line:
            break
        parts = line.split(None, 1)
        comm = parts[1].strip() if len(parts) > 1 else ""
        segs = [seg for seg in comm.split("/") if seg]
        if segs and (segs[-1] == "claude" or "claude" in segs):
            return cur
        try:
            cur = int(parts[0])
        except ValueError:
            break
    return fallback


def _gesture_available(jump: dict) -> bool:
    """Can a window gesture be made AT ALL for this jump (seat, osascript,
    installed script, kill switch)? Separate from whether it SHOULD be made.

    The capability question is `osascript`, the same one window_jump.sh asks of
    itself — not sys.platform: a Mac with no GUI seat is darwin and cannot make
    the gesture, and the two must not disagree about who can."""
    return (jump.get("seat") == "ghostty" and bool(shutil.which("osascript"))
            and _window_jump_script().exists()
            and os.environ.get("CONTEXT_JUMP_NO_SPAWN") != "1")


def _spawn_gesture(from_session: str) -> int | None:
    """Spawn the detached gesture; return its PID (recorded in the jump file so
    a later trip can tell a FINISHED gesture from one still running)."""
    try:
        proc = subprocess.Popen(["bash", str(_window_jump_script()), from_session],
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, start_new_session=True)
        return proc.pid
    except OSError:
        return None


def _gesture_alive(jump: dict) -> bool:
    """Is the gesture spawned last time STILL running? osascript can hang for
    minutes on a busy window server, having logged only `old window:` — and a
    second gesture on top of a live one opens a SECOND window into which
    nothing will ever be typed. A running gesture is not a failed one."""
    try:
        pid = int(jump.get("gesture_pid") or 0)
    except (TypeError, ValueError):
        return False
    if pid <= 1:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True   # alive, just not ours to signal
    except OSError:
        return False


def _jump_log_last(from_session: str) -> str:
    """The last jump.log line about THIS session (the log is shared by all)."""
    try:
        lines = (_jump_dir() / "jump.log").read_text(
            encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return ""
    tag = f"[{from_session}]"
    for line in reversed(lines):
        if tag in line:
            return line
    return ""


def _stamp_gesture_attempt(path: Path, pid: int | None = None) -> int:
    """Increment gesture_attempts in the jump file, atomically, and record the
    gesture's PID. Returns the new count (0 = unwritable). ts and mandate are
    never touched: the file is the handoff, only the attempt counter moves."""
    try:
        jump = json.loads(path.read_text(encoding="utf-8"))
        n = int(jump.get("gesture_attempts") or 0) + 1
        jump["gesture_attempts"] = n
        jump["gesture_pid"] = pid
        jump["last_gesture_ts"] = time.time()
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(jump, indent=2), encoding="utf-8")
        tmp.replace(path)
        return n
    except (OSError, ValueError, TypeError):
        return 0


def _should_retry_gesture(jump: dict, from_session: str) -> bool:
    """The file exists — is the gesture OWED a second try?

    It is when the new session never reported, the previous gesture PROCESS has
    exited, AND (jump.log's last word on this session is a miss, or the file is
    older than JUMP_STALE_S and no line ever said the keystroke landed). It is
    NOT when a gesture was never made in the first place (headless seat / kill
    switch: gesture_attempts == 0), not while the previous gesture is still
    running (a hung osascript logs nothing and would be read as a miss), and not
    past the cap — three failed gestures are a human problem, not a fourth one.
    """
    if jump.get("to_session"):
        return False
    try:
        attempts = int(jump.get("gesture_attempts") or 0)
    except (TypeError, ValueError):
        return False
    if attempts < 1 or attempts >= JUMP_MAX_GESTURES:
        return False
    if _gesture_alive(jump):
        return False
    last = _jump_log_last(from_session)
    typed_ok = "opened, 'nz-jump" in last
    if "nothing typed" in last:
        return True
    try:
        age = time.time() - float(jump.get("last_gesture_ts") or jump.get("ts") or 0)
    except (TypeError, ValueError):
        return False
    return age > JUMP_STALE_S and not typed_ok


def _retry_gesture(path: Path, from_session: str):
    """Second trip of a session whose jump file already exists. The file used to
    BE the rate limit ("già in corso"), which is right when the gesture worked
    and wrong when it silently failed: measured 2026-09-09, the file existed,
    to_session was null, jump.log said "nothing typed", and every later trip
    answered "salto non avviato" — the session sat at the guard with no window
    and no retry until a human typed nz-jump by hand."""
    try:
        jump = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(jump, dict) or not _should_retry_gesture(jump, from_session):
        return None
    if not _gesture_available(jump):
        return None
    pid = _spawn_gesture(from_session)
    if pid is None:
        return None
    n = _stamp_gesture_attempt(path, pid)
    # An unwritable file means the counter did NOT move: say that, never
    # "gesto ritentato (0/3)", which would read as a cap that already ran out.
    return f"retried:{n}" if n else "retried-unrecorded"


def _write_pending_jump(payload: dict, model: str, handoff_path: Path, mandate: str):
    """Write pending-jump-<session>.json and, on a Ghostty seat, spawn
    window_jump.sh detached. Returns what was actually done, so the deny text
    can say it honestly: "spawned" (the window gesture was STARTED — its
    outcome is only in jump.log, the hook does not wait for it), "recorded"
    (file written, no gesture: headless seat or no script), "retried:<n>" (the
    file was already there but the gesture had missed, so it was made again —
    capped at JUMP_MAX_GESTURES), "retried-unrecorded" (made again, but the
    counter could not be written) or None (nothing raised). Measured 2026-09-09
    on M5 (session 461e7cb5) and Pro (e82f9c09): two of three gestures failed
    AFTER the hook had already printed AVVIATO, so the operator read "started"
    and waited for a window that never came."""
    if os.environ.get("CONTEXT_JUMP_OFF") == "1":
        return None
    from_session = str(payload.get("session_id") or "unknown")
    path = _pending_jump_path(from_session)
    if path.exists():
        # The file is the rate limit for the FILE, never for the GESTURE.
        return _retry_gesture(path, from_session)
    link = _chain_link(from_session)
    try:
        hops = int((link or {}).get("hops", 0)) + 1
    except (TypeError, ValueError):
        hops = 1
    if hops > JUMP_MAX_HOPS:
        return None
    jump = {
        "from_session": from_session,
        "from_pid": _claude_pid(),  # the claude process this hook runs under
        "to_session": None,
        "model": model,
        "permission_mode": payload.get("permission_mode") or "",
        "cwd": str(payload.get("cwd") or os.getcwd()),
        "handoff_path": str(handoff_path),
        "mandate": mandate,
        "hops": hops,
        "ts": time.time(),
        "seat": "ghostty" if os.environ.get("TERM_PROGRAM") == "ghostty" else "headless",
        "gesture_attempts": 0,
        "gesture_pid": None,
    }
    try:
        _jump_dir().mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(jump, indent=2), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        return None
    # The file must exist BEFORE the gesture: window_jump.sh reads it.
    if _gesture_available(jump):
        pid = _spawn_gesture(from_session)
        if pid is not None:
            _stamp_gesture_attempt(path, pid)
            return "spawned"
    return "recorded"


def _load_module_from_path(path: Path, name: str):
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read_tail(path: str, size: int = TAIL_BYTES):
    """Return the last `size` bytes of `path`, decoded, or None (cannot-verify)."""
    if not path:
        return None
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            total = f.tell()
            f.seek(max(0, total - size))
            return f.read().decode("utf-8", "ignore")
    except OSError:
        return None


def _count_assistant_turns(tail_text: str) -> int:
    return len(ASSISTANT_TYPE_RE.findall(tail_text))


def _last_assistant_model(tail_text: str):
    """Reversed-line scan mirroring last_context_tokens()'s own loop shape
    (same file, same tail) — extracts `message.model` from the last
    assistant record, not the token estimate itself (that stays imported,
    never reimplemented)."""
    for line in reversed(tail_text.splitlines()):
        if '"assistant"' not in line or '"model"' not in line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        msg = (r.get("message") or {}) if isinstance(r, dict) else {}
        model = msg.get("model")
        if model:
            return str(model)
    return None


def _estimate_tokens(transcript_path: str):
    """Returns int token estimate, or None (cannot-verify -> caller fails open).

    Imports and calls the REAL S1 estimator — see module docstring's REUSE
    section. Never reimplements the formula."""
    try:
        mod = _load_module_from_path(_estimator_path(), "_ctxguard_context_hygiene")
    except Exception:
        return None
    if mod is None or not hasattr(mod, "last_context_tokens"):
        return None
    try:
        return int(mod.last_context_tokens(transcript_path))
    except Exception:
        return None


def _window_size(tail_text: str, tokens: int | None = None) -> int:
    env_val = os.environ.get("CONTEXT_WINDOW_TOKENS")
    if env_val:
        try:
            return int(env_val)
        except ValueError:
            pass
    model = os.environ.get("CONTEXT_GUARD_MODEL") or _last_assistant_model(tail_text) or ""
    model_l = model.lower()
    if model_l.endswith("[1m]") or "1m" in model_l:
        return LARGE_WINDOW
    # EVIDENCE BEATS THE LABEL (measured 2026-09-09 on M5): the transcript's
    # `message.model` never carries the `[1m]` suffix — it is a CLI alias, not
    # a model id — so a 1M seat looked like 200K and a 458K-token session was
    # denied at "229%". A context that already holds more than the small window
    # cannot be running in it: treat it as the large one. (A 1M seat BELOW 200K
    # is indistinguishable from a 200K seat by the transcript alone: set
    # CONTEXT_WINDOW_TOKENS in that seat's settings.json env — the sanctioned
    # override above.)
    if tokens is not None and tokens > DEFAULT_WINDOW:
        return LARGE_WINDOW
    return DEFAULT_WINDOW


def _window_reason(tail_text: str, tokens: int | None) -> str:
    """Human-readable WHY for the window `_window_size()` computed — mirrors
    that function's branch order exactly but never feeds back into the
    decision (display-only, read-only): the window inference logic itself is
    untouched (see module docstring's SELF-CURE note)."""
    if os.environ.get("CONTEXT_WINDOW_TOKENS"):
        return "env override"
    model = os.environ.get("CONTEXT_GUARD_MODEL") or _last_assistant_model(tail_text) or ""
    model_l = model.lower()
    if model_l.endswith("[1m]") or "1m" in model_l:
        return "modello [1m]"
    if tokens is not None and tokens > DEFAULT_WINDOW:
        return ">200K evidenza"
    return "default"


def _role_and_threshold():
    role = (os.environ.get("CONTEXT_GUARD_ROLE") or "default").strip().lower()
    pct_env = os.environ.get("CONTEXT_GUARD_PCT")
    if pct_env:
        try:
            val = float(pct_env)
            return role, (val / 100.0 if val > 1 else val)
        except ValueError:
            pass
    return role, ROLE_THRESHOLDS.get(role, DEFAULT_THRESHOLD)


def _rate_limit_marker(session_id: str) -> Path:
    return _guard_state_dir() / f"{session_id}.last-handoff"


def _should_write_handoff(session_id: str) -> bool:
    marker = _rate_limit_marker(session_id)
    try:
        if marker.exists():
            last = float(marker.read_text().strip() or "0")
            if time.time() - last < HANDOFF_RATE_LIMIT_S:
                return False
    except (OSError, ValueError):
        pass
    return True


def _mark_handoff_written(session_id: str) -> None:
    try:
        _guard_state_dir().mkdir(parents=True, exist_ok=True)
        _rate_limit_marker(session_id).write_text(str(time.time()))
    except OSError:
        pass


def _write_handoff(payload: dict, mandate: str = ""):
    """Write the SAME artifact precompact-mnemos.py's PreCompact hook writes
    (see module docstring's REUSE section), rate-limited to once per
    HANDOFF_RATE_LIMIT_S per session. Returns the path written, or None."""
    session_id = str(payload.get("session_id") or "unknown")
    transcript_path = str(payload.get("transcript_path") or "")
    handoff_path = _handoff_path(session_id)

    def _via_import():
        mod = _load_module_from_path(_precompact_hook_path(), "_ctxguard_precompact_mnemos")
        if mod is None or not hasattr(mod, "parse_transcript_jsonl"):
            return False
        p = Path(transcript_path)
        if not p.exists():
            return False
        parsed = mod.parse_transcript_jsonl(p)
        handoff = {
            "session_id": session_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "transcript_path": transcript_path,
            "mandate": mandate,
            **parsed,
        }
        handoff_path.parent.mkdir(parents=True, exist_ok=True)
        handoff_path.write_text(json.dumps(handoff, indent=2))
        return True

    ok = False
    try:
        ok = _via_import()
    except Exception:
        ok = False

    if not ok:
        try:
            subprocess.run(
                [sys.executable, str(_precompact_hook_path())],
                input=json.dumps(payload), text=True, capture_output=True, timeout=10,
            )
            ok = handoff_path.exists()
        except Exception:
            ok = False

    if ok:
        _mark_handoff_written(session_id)
        return str(handoff_path)
    return None


def _reporting_search(tool_input: dict) -> bool:
    """Let a capped session reach the schema of the tools it is told to use.

    The parent had the same hole the child adapter had: `SendMessage` and
    `TaskStop` were exempt, `ToolSearch` was not, and in a harness that defers
    tool schemas a deferred `SendMessage` is a NAME with no parameters until
    `ToolSearch` fetches its definition. So the deny message named the hand-off
    route and blocked the one call that reaches it. Narrowed by the query: only
    a search naming one of the two passes. When there is no readable query --
    a payload shape this guard does not own -- `ToolSearch` is allowed as a
    whole rather than trapping the session; every other tool stays denied.
    """
    query = tool_input.get("query")
    if not isinstance(query, str) or not query.strip():
        return True
    return any(name.lower() in query.lower() for name in REPORTING_TOOLS)


def _is_allowed_call(tool_name: str, tool_input: dict, handoff_path: Path) -> bool:
    if tool_name in ALLOWED_TOOLS_UNCONDITIONAL:
        return True
    if tool_name == "ToolSearch":
        return _reporting_search(tool_input)
    if tool_name == "Bash":
        return "mem save" in (tool_input.get("command") or "")
    if tool_name in ("Write", "Edit"):
        fp = tool_input.get("file_path") or ""
        try:
            return bool(fp) and Path(fp).resolve() == handoff_path.resolve()
        except OSError:
            return fp == str(handoff_path)
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        _gc_record("context_window_guard", "exempt", None)
        return 0
    if not isinstance(payload, dict):
        _gc_record("context_window_guard", "exempt", payload)
        return 0

    if os.environ.get("CONTEXT_GUARD_OFF") == "1":
        _gc_record("context_window_guard", "exempt", payload)
        return 0

    tool_name = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    transcript_path = str(payload.get("transcript_path") or "")

    tail_text = _read_tail(transcript_path)
    if tail_text is None:
        _gc_record("context_window_guard", "exempt", payload)  # cannot-verify
        return 0

    if _count_assistant_turns(tail_text) < GRACE_TURNS:
        _gc_record("context_window_guard", "allow", payload)
        return 0

    tokens = _estimate_tokens(transcript_path)
    if tokens is None:
        _gc_record("context_window_guard", "exempt", payload)  # estimator unavailable
        return 0

    window = _window_size(tail_text, tokens)
    pct = (tokens / window) if window else 0.0
    role, threshold = _role_and_threshold()

    if pct < threshold:
        _gc_record("context_window_guard", "allow", payload)
        return 0

    session_id = str(payload.get("session_id") or "unknown")
    handoff_path = _handoff_path(session_id)
    model = os.environ.get("CONTEXT_GUARD_MODEL") or _last_assistant_model(tail_text) or "sonnet"
    link = _chain_link(session_id)
    mandate = (link or {}).get("mandate") or _first_user_mandate(transcript_path)
    if _should_write_handoff(session_id):
        _write_handoff(payload, mandate)
    jumped = _write_pending_jump(payload, model, handoff_path, mandate)

    if _is_allowed_call(tool_name, tool_input, handoff_path):
        _gc_record("context_window_guard", "allow", payload)
        return 0

    pct_i = int(round(pct * 100))
    threshold_i = int(round(threshold * 100))
    tokens_k = tokens // 1000
    window_k = window // 1000
    reason = _window_reason(tail_text, tokens)
    handoff_str = str(handoff_path) if handoff_path.exists() else "NON scritto (errore)"
    msg = (
        f"[context_window_guard] Contesto ≈{tokens_k}K token = {pct_i}% della finestra "
        f"(soglia {role} {threshold_i}%). Modello: {model}; finestra assunta {window_k}K ({reason}). "
        f"Handoff: {handoff_str}.\n"
        + (f"Salto di finestra TENTATO (window_jump.sh in background, esito SOLO in "
           f"{_jump_dir() / 'jump.log'}): se entro ~15s non compare una finestra nuova con il "
           f"mandato, aprine una tu e scrivi: nz-jump {session_id}. Chiudi il turno.\n"
           if jumped == "spawned" else
           f"Salto: gesto ritentato ({str(jumped).split(':')[1]}/{JUMP_MAX_GESTURES}) — la finestra "
           f"precedente non era arrivata (window_jump.sh in background, esito SOLO in "
           f"{_jump_dir() / 'jump.log'}): se non compare, aprine una tu e scrivi: "
           f"nz-jump {session_id}. Chiudi il turno.\n"
           if str(jumped).startswith("retried:") else
           f"Salto: gesto ritentato, ma il contatore NON è stato scritto (file salto non "
           f"scrivibile: il cap di {JUMP_MAX_GESTURES} gesti non avanza). Esito in "
           f"{_jump_dir() / 'jump.log'}; a mano: nz-jump {session_id}. Chiudi il turno.\n"
           if jumped == "retried-unrecorded" else
           f"Salto REGISTRATO ({_pending_jump_path(session_id).name}), nessun gesto di finestra "
           f"(seat headless: il wrapper claude-cascade fa l'hop; a mano: nz-jump {session_id}). "
           "Chiudi il turno.\n"
           if jumped == "recorded" else
           f"Salto non avviato (kill switch, cap salti o già in corso: esito in {_jump_dir() / 'jump.log'}).\n")
        + f"1) Finestra nuova: claude --model {model} poi /resume.\n"
        f"2) Finestra sbagliata su QUESTA macchina? Dal prompt bar (bypassa i tool-hook): "
        f"! {ESCAPE_ONE_LINER}\n"
        "3) Ultima risorsa: CONTEXT_GUARD_OFF=1 (gate), CONTEXT_JUMP_OFF=1 (salto)."
    )
    print(msg, file=sys.stderr)
    _gc_record("context_window_guard", "deny", payload)
    return 2


if __name__ == "__main__":
    sys.exit(main())
