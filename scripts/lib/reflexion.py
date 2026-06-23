#!/usr/bin/env python3
"""reflexion.py — A3 of the self-loop: reflexion-che-impara, the reusable core.

Self-loop plan Anello 3 (research/operations/2026-06-23-self-loop-implementation-plan.md),
designed from the verified deep-study (research/operations/2026-06-23-a2-a3-*.md):
the TAC found A3 already exists TWICE, divergently — scripts/wr3_reflexion_synthesis.py
has the Delta Gate (record_run) but no heartbeat; the WR2 skill copy has heartbeat but
NO Delta Gate. Each has half. Per superscar #1 (HOME-fork drift), the cure is NOT a third
copy — it's lifting the shared core HERE so both can import one Delta Gate + one MOS bridge.

WHAT REFLEXION IS (Shinn et al, NeurIPS 2023, arXiv 2303.11366): after a task/batch, on a
sparse binary success/fail signal, reflect on what went wrong and store a natural-language
lesson retrieved IN-CONTEXT next run. No weight updates (consistent with the Anthropic-SDK
ban / CLI-only constraint). Gains are pure prompt-level. Anthropic's managed-agents framing
adds a second trigger: lessons also fire on OPERATOR OVERRIDE / grader correction.

THE FOUR HOW-LESSONS (verified-sourced in the study), all enforced below:
  1. TRIGGER on the binary verdict (LLM_FAILED / NOOP) AND on operator override.
  2. BOUND lesson-noise: Reflexion hard-caps long-term memory to Ω=1-3 lessons; we keep a
     small hot-window + the MOS 200-line/25KB inject cap that Nuzantara already runs.
  3. CONSOLIDATE ("dreaming"): a periodic dedup/merge/evict pass keeps the store high-signal.
  4. PROMOTE-GATE against phantom lessons: a lesson enters the durable MOS store only via a
     caller-supplied verdict (the refuter / Outcomes panel) — superscar #6.

THE DELTA GATE (lifted verbatim from wr3_reflexion_synthesis.record_run, generalized):
  every run appends {run_at, window_days, signals_found, lessons_written, status, notes} to
  a capped JSON history. A zero-work tick writes status=NO_SIGNAL, NOT a silent sys.exit(0)
  — so an operator SEES "12 weeks, all NO_SIGNAL" instead of mistaking green for learning.
  This is "Omeostasi Tautologica" defeated — AND it is A2 (Heartbeat Semantico) applied to
  the reflexion loop itself: the loop refuses to claim a green exit for a no-delta tick.

HARD REUSE CONSTRAINTS (verified on disk 2026-06-23):
  - MOS CHECK constraint: type IN (decision,discovery,fact,pattern,unresolved). 'lesson' is
    REJECTED (`mem save lesson` -> "Invalid type"). We save lessons as type='pattern'.
  - FTS5 strips '-' (mem query): retrieval keys must avoid hyphens.

Pure stdlib. No network. The MOS save shells out to the `mem` CLI (the sanctioned path).
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Loop-neutral status enum (widened from WR3's {SYNTHESIZED,THIN_SIGNAL,NO_INPUT,LLM_FAILED}).
LEARNED = "LEARNED"        # signals present, lesson(s) written
NO_SIGNAL = "NO_SIGNAL"    # ran honestly, nothing to learn from (NOT a silent exit)
NOOP = "NOOP"              # ran but produced byte-identical output to last tick (tautology!)
LLM_FAILED = "LLM_FAILED"  # the synthesis LLM cascade failed with signals present (alert-worthy)
_VALID_STATUS = {LEARNED, NO_SIGNAL, NOOP, LLM_FAILED}

# Reflexion Ω: hot-window of lessons kept inline (Shinn et al cap = 1-3).
HOT_WINDOW = 3
# Delta-gate history cap (matches wr3 record_run history[-200:]).
HISTORY_CAP = 200
# MOS type that survives the CHECK constraint AND auto-loads at SessionStart (importance>=7).
MOS_TYPE = "pattern"

_MEM_CLI = Path.home() / ".claude" / "scripts" / "mem"


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _sanitize_key(loop_name: str) -> str:
    """FTS5 strips '-'; loop keys used for `mem query` must avoid hyphens (verified mem:36/38)."""
    return loop_name.replace("-", "_")


# ---- The Delta Gate (the heart — generalized record_run) ---------------------

def record_run(state_dir: Path, *, loop: str, window_days: int = 0,
               signals_found: int, lessons_written: int, status: str,
               notes: str = "", loop_status: str | None = None) -> Path:
    """Append an auditable run record. THIS kills green-cron-theater: a NO_SIGNAL run is
    visible on disk, not a silent sys.exit(0). Lifted from wr3_reflexion_synthesis (L310).

    Two-vocabulary contract (separates VALIDATION from AUDIT, so a cabled caller keeps its
    own on-disk vocabulary — superscar #9, the WR3-cabling fix 2026-06-24):
      - `status`  : the CANONICAL enum value, validated against _VALID_STATUS (anti-typo gate).
      - `loop_status` (optional): the caller's NATIVE audit label (e.g. WR3's 'NO_INPUT').
    The on-disk `status` field is the native label when `loop_status` is given (what an
    operator reading the file expects), else the canonical value. The canonical value is
    ALWAYS persisted under `canonical_status` so machine consumers (is_tautological) stay
    correct regardless of the audit vocabulary. Readers of old records (no canonical_status)
    fall back to `status` — backward compatible."""
    if status not in _VALID_STATUS:
        raise ValueError(f"invalid reflexion status {status!r}; use one of {sorted(_VALID_STATUS)}")
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / "_reflexion-state.json"
    history = _load_json(state_path)
    if not isinstance(history, list):
        history = []
    history.append({
        "run_at": datetime.now(timezone.utc).isoformat(),
        "loop": loop,
        "window_days": window_days,
        "signals_found": signals_found,
        "lessons_written": lessons_written,
        "status": loop_status if loop_status is not None else status,
        "canonical_status": status,
        "notes": notes,
    })
    state_path.write_text(json.dumps(history[-HISTORY_CAP:], indent=2))
    return state_path


def is_tautological(state_dir: Path, *, last_n: int = HOT_WINDOW) -> bool:
    """A2 applied to the reflexion loop: True if the last `last_n` runs were ALL NO_SIGNAL/NOOP
    (zero learning despite green exits) — the Omeostasi-Tautologica alarm an operator should see."""
    state_path = state_dir / "_reflexion-state.json"
    history = _load_json(state_path)
    if not isinstance(history, list) or len(history) < last_n:
        return False
    tail = history[-last_n:]
    # Read the CANONICAL status (machine vocabulary), falling back to `status` for old
    # records written before the two-vocabulary split — so a cabled caller's native audit
    # label (e.g. WR3 'NO_INPUT') never confuses the machine alarm.
    return all((r.get("canonical_status") or r.get("status")) in (NO_SIGNAL, NOOP) for r in tail)


# ---- Lesson store: file (hot-window) + MOS (cross-session) -------------------

def write_lesson_file(lessons_dir: Path, *, loop: str, lesson: str) -> Path:
    """Append a lesson to the per-loop lessons.md, keeping only the last HOT_WINDOW (Ω cap).
    File-path retrieval is what skill-coupled loops already do (wr3 write_lessons L279)."""
    lessons_dir.mkdir(parents=True, exist_ok=True)
    path = lessons_dir / f"{_sanitize_key(loop)}.lessons.md"
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    bullets = [ln for ln in existing if ln.strip().startswith("- ")]
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    bullets.append(f"- [{stamp}] {lesson.strip()}")
    bullets = bullets[-HOT_WINDOW:]  # bound noise (Reflexion Ω)
    path.write_text(f"# Reflexion lessons — {loop}\n\n" + "\n".join(bullets) + "\n")
    return path


def save_lesson_mos(loop: str, lesson: str, *, importance: int = 7,
                    promoted: bool = False, mem_cli: Path = _MEM_CLI) -> bool:
    """Save a lesson to MOS as type='pattern' (the 'lesson' type is rejected by the CHECK
    constraint). importance>=7 makes SessionStart auto-load it — the cross-session retrieval
    half of A3, for free. PROMOTE-GATE (constraint #4 / superscar #6): only a lesson the caller
    has VERIFIED (promoted=True, e.g. via refuter/Outcomes) enters the durable store — a
    hallucinated lesson must never auto-persist."""
    if not promoted:
        return False
    text = f"[reflexion:{_sanitize_key(loop)}] {lesson.strip()}"
    try:
        r = subprocess.run([str(mem_cli), "save", MOS_TYPE, text, str(importance)],
                           capture_output=True, text=True, timeout=30)
        return r.returncode == 0
    except Exception:
        return False


def retrieve_lessons(loop: str, *, lessons_dir: Path | None = None,
                     mem_cli: Path = _MEM_CLI) -> list[str]:
    """Pull this loop's prior lessons at run start (the 'retrieve next run' half of A3).
    Path A: per-loop lessons.md (hot-window). Path B: MOS FTS query (cross-session)."""
    out: list[str] = []
    if lessons_dir is not None:
        p = lessons_dir / f"{_sanitize_key(loop)}.lessons.md"
        if p.exists():
            out += [ln[2:].strip() for ln in p.read_text(encoding="utf-8").splitlines()
                    if ln.strip().startswith("- ")]
    try:
        r = subprocess.run([str(mem_cli), "query", f"reflexion {_sanitize_key(loop)}"],
                           capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and r.stdout:
            out += [ln.strip() for ln in r.stdout.splitlines()
                    if "reflexion" in ln.lower() and ln.strip()]
    except Exception:
        pass
    # dedup preserving order, bound to a sane retrieval size
    seen, uniq = set(), []
    for x in out:
        k = x.lower()[:80]
        if k not in seen:
            seen.add(k); uniq.append(x)
    return uniq[: HOT_WINDOW * 2]


# ---- Consolidation ("dreaming") --------------------------------------------

def consolidate_lessons(lessons_dir: Path, *, loop: str) -> int:
    """Periodic dedup/merge/evict pass (Anthropic 'DREAMING' — managed-agents) so the file
    store stays high-signal under the HOT_WINDOW cap. Returns how many bullets were dropped.
    Conservative: dedup-by-prefix + keep newest HOT_WINDOW. Semantic merge is the caller's job
    (an LLM pass) — this is the deterministic floor."""
    path = lessons_dir / f"{_sanitize_key(loop)}.lessons.md"
    if not path.exists():
        return 0
    bullets = [ln for ln in path.read_text(encoding="utf-8").splitlines()
               if ln.strip().startswith("- ")]
    seen, kept = set(), []
    for b in bullets:
        key = b.split("] ", 1)[-1].lower()[:60]  # ignore the date stamp for dedup
        if key not in seen:
            seen.add(key); kept.append(b)
    dropped = len(bullets) - len(kept)
    kept = kept[-HOT_WINDOW:]
    dropped += max(0, len(seen) - HOT_WINDOW)
    path.write_text(f"# Reflexion lessons — {loop}\n\n" + "\n".join(kept) + "\n")
    return dropped
