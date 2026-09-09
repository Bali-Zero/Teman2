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
Everything else — including a bare `Bash`/`Write`/`Edit`/`Agent` that is not
one of the above — is DENIED (exit 2), in Italian, naming the exact percent,
threshold, handoff path and the `claude --model ... ` + `/resume` sequence.

Fail-open (exit 0), same discipline as every sibling gate in this
directory: unparseable payload, unreadable transcript, missing/unreadable
estimator, fewer than GRACE_TURNS assistant turns. This is an economy/
discipline guard, not a security boundary — a broken copy of it must never
paralyze the harness (cicatrix scar #2, Esiste!=Armato, cuts both ways: a
gate that blocks everything when it is itself broken teaches the kill
switch, same lesson `orchestrate_gate.py`'s DISARM AUDIBILITY note already
draws).
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import os
import re
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

ALLOWED_TOOLS_UNCONDITIONAL = {"SendMessage", "TaskStop"}

ASSISTANT_TYPE_RE = re.compile(r'"type"\s*:\s*"assistant"')


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


def _window_size(tail_text: str) -> int:
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
    return DEFAULT_WINDOW


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


def _write_handoff(payload: dict):
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


def _is_allowed_call(tool_name: str, tool_input: dict, handoff_path: Path) -> bool:
    if tool_name in ALLOWED_TOOLS_UNCONDITIONAL:
        return True
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

    window = _window_size(tail_text)
    pct = (tokens / window) if window else 0.0
    role, threshold = _role_and_threshold()

    if pct < threshold:
        _gc_record("context_window_guard", "allow", payload)
        return 0

    session_id = str(payload.get("session_id") or "unknown")
    handoff_path = _handoff_path(session_id)
    if _should_write_handoff(session_id):
        _write_handoff(payload)

    if _is_allowed_call(tool_name, tool_input, handoff_path):
        _gc_record("context_window_guard", "allow", payload)
        return 0

    model = os.environ.get("CONTEXT_GUARD_MODEL") or _last_assistant_model(tail_text) or "sonnet"
    pct_i = int(round(pct * 100))
    threshold_i = int(round(threshold * 100))
    tokens_k = tokens // 1000
    msg = (
        f"[context_window_guard] Contesto ≈{tokens_k}K token = {pct_i}% della finestra "
        f"(soglia {role} {threshold_i}%). Handoff scritto in {handoff_path if handoff_path.exists() else 'NON scritto (errore)'}. "
        f"Apri una finestra nuova: claude --model {model} e scrivi /resume. "
        "Kill switch: CONTEXT_GUARD_OFF=1."
    )
    print(msg, file=sys.stderr)
    _gc_record("context_window_guard", "deny", payload)
    return 2


if __name__ == "__main__":
    sys.exit(main())
