#!/usr/bin/env python3
"""WR3 Reflexion synthesis — weekly cron Sunday 02:30 WITA.

Replaces the S7.3 PLACEHOLDER stub (816 bytes, `sys.exit(0)`) that synthesized
nothing for 12+ Sundays (cicatrix F21 / W74 "green cron != working").

Faithful port of the real WR2 reflexion synthesizer
(`~/.claude/skills/bali-zero-brand/_reflexion-synthesis.py`, 314 lines) adapted
from WR2's SQLite source to WR3's FILE-based episode artifacts.

Reflexion (Shinn et al., NeurIPS 2023): after a batch of tasks, reflect on what
worked / what didn't, store as natural-language lessons retrievable for future
tasks. For WR3, weekly cron reads the last 7 days of episodes + designer
overrides and distils <=10 verbal lessons per agent.

Reads (per the wr3-reflexion-synth contract, docs/wr3/contracts/reflexion-synth.yaml):
- apps/war-room/output/episode/<modified in last N days>/{episode_manifest.json,
  legal_claim_gate_verdict.json, gate-verdict.json, identity-report.json,
  render-report.json, brief.json}
- apps/war-room/output/queue/wr3-human-review-queue.json (designer overrides; OPTIONAL —
  the contract marks it required but it is frequently absent; absence is tolerated)

Writes:
- ~/.claude/skills/bali-zero-brand/wr3/<agent>/lessons.md (append, max 10/week)
- ~/.claude/skills/bali-zero-brand/wr3/_proposed/<iso-week>-<slug>.md (skill drafts)
- ~/.claude/skills/bali-zero-brand/wr3/_reflexion-state.json (THE DELTA GATE — see below)

THE DELTA GATE (Mythos meta-pattern counter-measure, 2026-06-14):
  The disease this file was born from is "Omeostasi Tautologica" — a green cron
  that exits 0 while producing zero state-delta, indistinguishable from a healthy
  converged loop. The cure: EVERY run appends an auditable record to
  `_reflexion-state.json` with {run_at, window_days, episodes_found, lessons_written,
  status}. A run with no episodes is NOT a silent `sys.exit(0)`; it writes
  status="NO_INPUT" so an operator can SEE "12 weeks, all NO_INPUT" instead of
  mistaking green telemetry for learning. status in {SYNTHESIZED, THIN_SIGNAL,
  NO_INPUT, LLM_FAILED}.

Multi-LLM cascade per CLAUDE.md: Tier 1 Sonnet 5 (claude -p), Tier 2 Gemini 3.x
(agy) on quota-exhaust. Cost ceiling $0.15/run (contract).

Exit codes: 0 = ran (incl. honest NO_INPUT), 1 = LLM cascade fully failed with
episodes present (a real failure worth alerting, NOT silent).
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---- Cabling to the unified A3 reflexion core (scripts/lib/reflexion.py) -----
# A3 self-loop (research/operations/2026-06-23-self-loop-implementation-plan.md):
# the Delta Gate + tautology alarm live in ONE place now (superscar #1 HOME-fork
# cure — no third copy). This standalone cron may run from a deploy-worktree where
# scripts/lib is not importable as a package, so load it by path off __file__.
_REFLEXION_LIB = Path(__file__).resolve().parent / "lib" / "reflexion.py"
_spec = importlib.util.spec_from_file_location("reflexion_core", str(_REFLEXION_LIB))
reflexion_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reflexion_core)

# WR3 status vocabulary -> the core's loop-neutral enum. The core REJECTS unknown
# statuses (ValueError) — defends against silently logging a typo as a valid run.
_WR3_STATUS_TO_CORE = {
    "SYNTHESIZED": reflexion_core.LEARNED,      # lessons written
    "THIN_SIGNAL": reflexion_core.NO_SIGNAL,    # ran, nothing worth a lesson
    "NO_INPUT": reflexion_core.NO_SIGNAL,       # ran honestly, no episodes
    "LLM_FAILED": reflexion_core.LLM_FAILED,    # cascade failed with input present
}

# ---- Paths (override via env for tests / deploy-worktree) --------------------

def _repo_root() -> Path:
    env = os.environ.get("WR3_REPO_ROOT")
    if env:
        return Path(env)
    # scripts/wr3_reflexion_synthesis.py -> repo root is parent of scripts/
    return Path(__file__).resolve().parent.parent


def _skill_dir() -> Path:
    env = os.environ.get("WR3_SKILL_DIR")
    if env:
        return Path(env)
    return Path.home() / ".claude/skills/bali-zero-brand/wr3"


WINDOW_DAYS = int(os.environ.get("WR3_REFLEXION_WINDOW_DAYS", "7"))
MAX_LESSONS = int(os.environ.get("WR3_REFLEXION_MAX_LESSONS", "10"))
LLM_TIMEOUT_S = int(os.environ.get("WR3_REFLEXION_LLM_TIMEOUT", "600"))

# Episode artifacts to harvest as reflexion signal (filename -> short label)
_SIGNAL_FILES = {
    "episode_manifest.json": "manifest",
    "legal_claim_gate_verdict.json": "legal_gate",
    "gate-verdict.json": "prerender_gate",
    "identity-report.json": "identity",
    "render-report.json": "render",
    "brief.json": "brief",
}


# ---- Harvest ----------------------------------------------------------------

def _load_json(path: Path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def fetch_recent_episodes(repo_root: Path, window_days: int = WINDOW_DAYS) -> list[dict]:
    """Collect episodes whose dir mtime is within the window, with their signal files."""
    episode_root = repo_root / "apps/war-room/output/episode"
    if not episode_root.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    episodes: list[dict] = []
    for ep_dir in sorted(episode_root.iterdir()):
        if not ep_dir.is_dir() or ep_dir.name.startswith((".", "_")):
            continue
        try:
            mtime = datetime.fromtimestamp(ep_dir.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if mtime < cutoff:
            continue
        signals: dict = {"episode_id": ep_dir.name, "dir_mtime": mtime.isoformat()}
        for fname, label in _SIGNAL_FILES.items():
            data = _load_json(ep_dir / fname)
            if data is not None:
                signals[label] = _compact_signal(label, data)
        episodes.append(signals)
    return episodes


def _compact_signal(label: str, data: dict):
    """Keep only the reflexion-relevant fields per artifact (avoid sending 16KB briefs)."""
    if not isinstance(data, dict):
        return data
    keep = {
        "manifest": ("critic_verdict", "degradation_flags", "variants_failed",
                     "vo_lufs", "render_cost_cr", "identity_gate", "clips_count"),
        "legal_gate": ("verdict", "claims_drifted", "claims_unbound",
                       "taboo_violations", "number_attribution_ok", "retry_reasons"),
        "prerender_gate": ("verdict", "shots_to_reroll", "retry_reasons", "note"),
        "identity": ("overall_cosine_avg", "overall_cosine_min", "hard_fail_triggered",
                     "clips_failed", "mock_mode"),
        "render": ("failed", "rerender", "total_cost_cr"),
        "brief": ("domain", "archetype", "audience_segment", "topic",
                  "number_attribution_flag", "degrade_loud"),
    }.get(label)
    if keep is None:
        return data
    return {k: data[k] for k in keep if k in data}


def fetch_override_diffs(repo_root: Path, window_days: int = WINDOW_DAYS) -> list[dict]:
    """Designer overrides from the WR3 human-review queue. Absent file => []."""
    queue_path = repo_root / "apps/war-room/output/queue/wr3-human-review-queue.json"
    if not queue_path.exists():
        return []
    queue = _load_json(queue_path)
    if not isinstance(queue, list):
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    out: list[dict] = []
    for item in queue:
        if not isinstance(item, dict):
            continue
        action_at = item.get("action_at") or item.get("damar_action_at")
        if not action_at:
            continue
        try:
            ts = datetime.fromisoformat(str(action_at).replace("Z", "+00:00"))
        except ValueError:
            continue
        if ts >= cutoff:
            out.append({
                "episode_id": item.get("episode_id") or item.get("id"),
                "state": item.get("state"),
                "reason_tag": item.get("reason_tag"),
                "notes": item.get("notes") or item.get("damar_notes"),
            })
    return out


# ---- Synthesis (LLM cascade) ------------------------------------------------

def build_synthesis_prompt(episodes: list[dict], overrides: list[dict]) -> str:
    iso_week = datetime.now(timezone.utc).strftime("%Y-W%V")
    data = {"week": iso_week, "episodes": episodes, "designer_overrides": overrides}
    return f"""You are doing the weekly Reflexion synthesis for the Bali Zero WR3 video-episode room.

Week: {iso_week}.
Last {WINDOW_DAYS} days: {len(episodes)} episodes, {len(overrides)} designer overrides.

Each episode carries per-agent quality signals: critic_verdict + degradation_flags
(post-assembler/critic), legal_gate verdict + claims_drifted/taboo (brief-interpreter/
script-editor), prerender_gate verdict + shots_to_reroll (shot-director/gatekeeper),
identity cosine + hard_fail (clip-renderer), render failures/cost (clip-renderer).

Your job: extract <={MAX_LESSONS} verbal lessons. NO MORE THAN {MAX_LESSONS}. Each lesson is a
single actionable sentence, citable to specific episode_ids, attributed to the WR3 agent it
should teach (brief-interpreter | script-editor | shot-director | pre-render-gatekeeper |
clip-renderer | audio-asset-producer | post-assembler | critic | design-architect).

CRITICAL: do NOT invent lessons. If signal is too thin to draw conclusions, return FEWER than
{MAX_LESSONS} (even zero). Self-justification noise is the failure mode to avoid — an empty,
honest synthesis beats fabricated lessons.

Data:

```json
{json.dumps(data, indent=2)}
```

Output format — return ONLY this JSON object, no prose, no markdown fences:

{{
  "week": "{iso_week}",
  "lessons": [
    {{
      "lesson_text": "<single actionable sentence>",
      "agent": "<one of the WR3 agent names above>",
      "category": "regulatory|identity|render|audio|pacing|brand|orchestration",
      "confidence": "low|medium|high",
      "motivating_episode_ids": ["<id>"],
      "proposes_skill_draft": false,
      "suggested_addition": "<exact text to append to the agent's lessons.md>"
    }}
  ],
  "synthesis_notes": "1-paragraph summary of what WR3 learned this week."
}}"""


def _strip_fences(out: str) -> str:
    out = out.strip()
    if out.startswith("```"):
        out = out.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        if out.startswith("json\n"):
            out = out[5:]
    return out


def call_llm_synthesis(prompt: str) -> dict | None:
    """Tier-1 claude -p (Sonnet), Tier-2 agy (Gemini) on cascade. Returns parsed JSON or None."""
    for tier in ("claude", "gemini"):
        out = _run_tier(tier, prompt)
        if out is None:
            continue
        try:
            return json.loads(_strip_fences(out))
        except json.JSONDecodeError as e:
            print(f"[wr3-reflexion] {tier} JSON parse failed: {e}", file=sys.stderr)
            continue
    return None


def _run_tier(tier: str, prompt: str) -> str | None:
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)  # defense-in-depth: never pay-per-token (CLAUDE.md)
    if tier == "claude":
        cmd = ["claude", "-p", "--model", "claude-sonnet-5"]
    else:
        cmd = ["agy", "-p", "--print-timeout", "5m"]
    try:
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                           timeout=LLM_TIMEOUT_S, env=env)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"[wr3-reflexion] tier {tier} unavailable: {e}", file=sys.stderr)
        return None
    if r.returncode != 0:
        low = (r.stdout + r.stderr).lower()
        if any(s in low for s in ("out of extra usage", "usage limit", "quota",
                                  "rate limit", "429", "exhausted")):
            print(f"[wr3-reflexion] tier {tier} quota-exhausted, cascading", file=sys.stderr)
        else:
            print(f"[wr3-reflexion] tier {tier} exit {r.returncode}: {r.stderr[:300]}",
                  file=sys.stderr)
        return None
    return r.stdout


# ---- Write lessons + skill drafts -------------------------------------------

def write_lessons(synthesis: dict, skill_dir: Path) -> int:
    lessons = (synthesis or {}).get("lessons") or []
    if not lessons:
        return 0
    week = synthesis.get("week", datetime.now(timezone.utc).strftime("%Y-W%V"))
    lessons = lessons[:MAX_LESSONS]
    stamp = datetime.now(timezone.utc).isoformat()
    for lesson in lessons:
        agent = (lesson.get("agent") or "design-architect").strip()
        # agent dir names use the SKILL.md subdir convention (e.g. brief-interpreter/)
        agent_dir = skill_dir / agent
        agent_dir.mkdir(parents=True, exist_ok=True)
        lessons_md = agent_dir / "lessons.md"
        addition = lesson.get("suggested_addition") or lesson.get("lesson_text", "")
        cite = ", ".join(lesson.get("motivating_episode_ids", []) or [])
        with lessons_md.open("a") as f:
            f.write(
                f"\n- *Reflexion {week}* [{lesson.get('confidence','?')}/"
                f"{lesson.get('category','?')}]: {addition}"
                + (f"  (ep: {cite})" if cite else "")
                + "\n"
            )
        if lesson.get("proposes_skill_draft"):
            proposed_dir = skill_dir / "_proposed"
            proposed_dir.mkdir(parents=True, exist_ok=True)
            slug = "".join(c if c.isalnum() else "-" for c in
                           lesson.get("lesson_text", "")[:40].lower()).strip("-")
            (proposed_dir / f"{week}-{slug}.md").write_text(
                f"# WR3 skill draft {week}\n\n"
                f"**Agent**: {agent}\n\n**Lesson**: {lesson.get('lesson_text')}\n\n"
                f"**Category**: {lesson.get('category')}\n\n"
                f"**Confidence**: {lesson.get('confidence')}\n\n"
                f"**Motivating episodes**: {cite}\n\n"
                f"**Suggested addition**:\n\n{addition}\n\n"
                f"---\n\n*Generated by WR3 Reflexion synthesis {stamp}*\n"
            )
    return len(lessons)


# ---- The Delta Gate ---------------------------------------------------------

def record_run(skill_dir: Path, *, window_days: int, episodes_found: int,
               lessons_written: int, status: str, notes: str = "") -> Path:
    """Append an auditable run record. THIS is what kills the green-cron-theater:
    a NO_INPUT run is visible on disk, not a silent sys.exit(0).

    CABLED (A3, 2026-06-24): delegates to the unified core Delta Gate
    (reflexion_core.record_run) instead of a private copy. Two-vocabulary contract: the WR3
    NATIVE status (NO_INPUT/SYNTHESIZED/...) is persisted on disk verbatim via `loop_status`
    (what an operator reading _reflexion-state.json expects — unchanged from the pre-cabling
    file), while the CANONICAL enum value drives the core's machine logic (is_tautological).
    `episodes_found` is carried as the generic `signals_found` (no reader consumes the count
    by name). An unmapped status raises (no silent typo). Superscar #9: the on-disk audit
    vocabulary is preserved across the cabling — only the storage backend changed."""
    core_status = _WR3_STATUS_TO_CORE.get(status)
    if core_status is None:
        raise ValueError(f"unknown WR3 reflexion status {status!r}; "
                         f"expected one of {sorted(_WR3_STATUS_TO_CORE)}")
    return reflexion_core.record_run(
        skill_dir, loop="wr3", window_days=window_days,
        signals_found=episodes_found, lessons_written=lessons_written,
        status=core_status, loop_status=status, notes=notes,
    )


# ---- Main -------------------------------------------------------------------

def _warn_if_tautological(skill_dir: Path) -> None:
    """A3 cabling value-add: surface the Omeostasi-Tautologica alarm WR3 lacked.
    If the last HOT_WINDOW runs were ALL no-learning (NO_SIGNAL/NOOP), an operator
    should SEE 'N weeks, zero lessons' instead of mistaking a green cron for a
    converged loop. Advisory only (never changes the exit code)."""
    try:
        if reflexion_core.is_tautological(skill_dir):
            print(f"[wr3-reflexion] ⚠ TAUTOLOGY ALARM: last {reflexion_core.HOT_WINDOW} "
                  f"runs all no-learning — green cron, zero state-delta. Investigate "
                  f"whether episodes are actually being produced.", file=sys.stderr)
    except Exception:
        pass  # alarm is best-effort; never break the run


def main() -> int:
    repo_root = _repo_root()
    skill_dir = _skill_dir()
    episodes = fetch_recent_episodes(repo_root)
    overrides = fetch_override_diffs(repo_root)

    if not episodes and not overrides:
        record_run(skill_dir, window_days=WINDOW_DAYS, episodes_found=0,
                   lessons_written=0, status="NO_INPUT",
                   notes=f"no episodes/overrides in last {WINDOW_DAYS}d under {repo_root}")
        print(f"[wr3-reflexion] NO_INPUT — 0 episodes in last {WINDOW_DAYS}d. "
              f"Honest empty run (NOT theater); recorded to _reflexion-state.json.")
        _warn_if_tautological(skill_dir)
        return 0

    prompt = build_synthesis_prompt(episodes, overrides)
    synthesis = call_llm_synthesis(prompt)
    if synthesis is None:
        record_run(skill_dir, window_days=WINDOW_DAYS, episodes_found=len(episodes),
                   lessons_written=0, status="LLM_FAILED",
                   notes="claude+gemini cascade both failed")
        print("[wr3-reflexion] LLM cascade failed; no lessons written.", file=sys.stderr)
        return 1  # real failure with input present — worth alerting

    n = write_lessons(synthesis, skill_dir)
    status = "SYNTHESIZED" if n > 0 else "THIN_SIGNAL"
    record_run(skill_dir, window_days=WINDOW_DAYS, episodes_found=len(episodes),
               lessons_written=n, status=status,
               notes=synthesis.get("synthesis_notes", "")[:500])
    print(f"[wr3-reflexion] {status}: {n} lessons from {len(episodes)} episodes "
          f"(week {synthesis.get('week')}).")
    if status == "THIN_SIGNAL":
        _warn_if_tautological(skill_dir)  # had input but learned nothing — watch the trend
    return 0


if __name__ == "__main__":
    sys.exit(main())
