#!/usr/bin/env python3
"""WR2 Reflexion-style weekly synthesis — distill recent carousel runs into ≤10 verbal lessons.

PORTED INTO THE REPO 2026-06-24 (self-loop, superscar #1 HOME-fork cure): this was a HOME-only
file `~/.claude/skills/bali-zero-brand/_reflexion-synthesis.py` (80MB unversioned skill, 0 repo
source) — the running copy on Pro had NO Delta Gate, only a green/return-0 exit on an empty week
(the W74 "green cron != working" disease it should defend against). This repo version is the
faithful port of the PRO running copy + the Delta Gate cabled to the unified core, so the weekly
synthesis can no longer silently exit 0 on a no-delta week, and the code is versioned + CI-gated.

Inspired by Reflexion (Shinn et al., NeurIPS 2023): after each task, reflect on what worked and
what didn't, store as natural-language lesson, retrievable for future tasks.

For Bali Zero: weekly cron reads last 7 days of:
- carousel_runs.designer_override_diff (gold-standard signal)
- slide_states.critic_hard_failures + critic_soft_failures
- queue rejections with reason_tag

Synthesis is delegated to claude -p (Opus, OAuth — never pay-per-token) via subprocess. Lessons
are written to reflective_lessons table + appended to voice/on-tone-examples.md or
off-tone-examples.md, proposed as constitution amendments in _proposed-amendments/, or — for
lessons the synthesis itself classifies category="layout" with a
"layouts/_proposed/<name>.md" destination — routed as a proposal file into the repo-canonical
layout library's `_proposed/` dir (LAYOUTS_PROPOSED_DIR, see `_write_layout_proposal`; audit
2026-07-14 Wave-4 item 16 — the write logic did not exist before this routing was added).

THE DELTA GATE (cabled to scripts/lib/reflexion.record_run): every run appends an auditable
record to _reflexion-state.json with {run_at, signals_found, lessons_written, status, ...}.
A week with no data is NOT a silent return 0 — it records status NO_SIGNAL, so an operator can
SEE "12 weeks, all NO_SIGNAL" instead of mistaking green telemetry for learning. The on-disk
audit label keeps WR2's native vocabulary (SYNTHESIZED/THIN_SIGNAL/NO_INPUT/LLM_FAILED) via the
core's loop_status param; the canonical enum drives is_tautological.

Run: weekly LaunchAgent Sunday 02:30 WITA (after Voyager curriculum at 02:00).
Cost: 1 claude -p call per week (1 Opus invocation). ~52/year. Within OAuth MAX quota.

Paths are env-overridable (WR2_DB_PATH / WR2_SKILL_DIR / WR2_QUEUE_PATH /
WR2_LAYOUTS_PROPOSED_DIR) for tests + deploy.
"""

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---- Cabling to the unified A3 reflexion core (scripts/lib/reflexion.py) -----
# Loaded by path off __file__ so this standalone cron loads the core even from a
# deploy-worktree where scripts/lib is not an importable package.
_REFLEXION_LIB = Path(__file__).resolve().parent / "lib" / "reflexion.py"
_spec = importlib.util.spec_from_file_location("reflexion_core", str(_REFLEXION_LIB))
reflexion_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reflexion_core)

# WR2 native status vocabulary -> core enum. Core REJECTS unknown statuses (anti-typo).
_WR2_STATUS_TO_CORE = {
    "SYNTHESIZED": reflexion_core.LEARNED,    # lessons written
    "THIN_SIGNAL": reflexion_core.NO_SIGNAL,  # ran, data present, nothing worth a lesson
    "NO_INPUT": reflexion_core.NO_SIGNAL,     # ran honestly, no data in window
    "LLM_FAILED": reflexion_core.LLM_FAILED,  # claude -p synthesis failed with data present
}

# ---- Paths (env-overridable for tests / deploy-worktree) --------------------

def _db_path() -> Path:
    env = os.environ.get("WR2_DB_PATH")
    return Path(env) if env else (Path.home() / ".claude/projects/-Users-nuzantara/memory/wr2-episodic.db")


def _skill_dir() -> Path:
    env = os.environ.get("WR2_SKILL_DIR")
    return Path(env) if env else (Path.home() / ".claude/skills/bali-zero-brand")


def _queue_path() -> Path:
    env = os.environ.get("WR2_QUEUE_PATH")
    return Path(env) if env else (Path.home() / "Desktop/nuzantara/apps/war-room/output/queue/human-review-queue.json")


def _layouts_proposed_dir() -> Path:
    """Repo-canonical layout-library `_proposed/` dir (audit 2026-07-14, Wave-4 item 16).

    Deliberately NOT rooted under SKILL_DIR (which defaults to `$HOME/.claude/skills/...`, an
    undeclared HOME-fork target per superscar #1 — `infra/home-fork/declared-pairs.json` does
    not cover this dir). Layout-scoped lessons are routed to the repo-tracked layout library
    that `wr2_html_renderer/composer.py` actually reads from (`skills/bali-zero-brand/layouts/`),
    resolved relative to this script's own location so it works from any worktree/deploy
    checkout without depending on `$HOME` state.
    """
    env = os.environ.get("WR2_LAYOUTS_PROPOSED_DIR")
    if env:
        return Path(env)
    repo_root = Path(__file__).resolve().parent.parent
    return repo_root / "skills" / "bali-zero-brand" / "layouts" / "_proposed"


DB_PATH = _db_path()
SKILL_DIR = _skill_dir()
PROPOSED_DIR = SKILL_DIR / "_proposed-amendments"
ON_TONE_PATH = SKILL_DIR / "voice/on-tone-examples.md"
OFF_TONE_PATH = SKILL_DIR / "voice/off-tone-examples.md"
LAYOUTS_PROPOSED_DIR = _layouts_proposed_dir()


def fetch_last_7_days():
    if not DB_PATH.exists():
        return {"runs": [], "rejections": [], "critic_failures": []}

    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    try:
        # Add ig_likes + ig_comment_count if columns exist (W3.1: outcome-aware Reflexion)
        existing_cols = [r[1] for r in conn.execute("PRAGMA table_info(carousel_runs)").fetchall()]
        ig_extra_cols = [c for c in ("ig_likes", "ig_comment_count", "ig_reach")
                         if c in existing_cols]
        ig_extra_select = ("," + ",".join(ig_extra_cols)) if ig_extra_cols else ""

        runs = conn.execute(f"""
            SELECT id, topic_slug, domain, audience_segment, designer_override_diff,
                   critic_overall_verdict, instagram_published_at, ig_save_count
                   {ig_extra_select}
              FROM carousel_runs
             WHERE completed_at >= ?
        """, (cutoff,)).fetchall()
        run_cols = ["id", "topic_slug", "domain", "audience_segment", "designer_override_diff",
                    "critic_overall_verdict", "instagram_published_at", "ig_save_count"] + ig_extra_cols

        critic_failures = conn.execute("""
            SELECT ss.run_id, ss.slide_index, ss.layout_family,
                   ss.critic_hard_failures, ss.critic_soft_failures,
                   cr.topic_slug, cr.domain
              FROM slide_states ss
              JOIN carousel_runs cr ON cr.id = ss.run_id
             WHERE cr.completed_at >= ?
               AND (ss.critic_hard_failures IS NOT NULL OR ss.critic_soft_failures IS NOT NULL)
        """, (cutoff,)).fetchall()
        cf_cols = ["run_id", "slide_index", "layout_family", "critic_hard_failures",
                   "critic_soft_failures", "topic_slug", "domain"]

        return {
            "runs": [dict(zip(run_cols, r)) for r in runs],
            "critic_failures": [dict(zip(cf_cols, r)) for r in critic_failures],
        }
    finally:
        conn.close()


def fetch_rejections_from_queue():
    queue_path = _queue_path()
    if not queue_path.exists():
        return []
    queue = json.loads(queue_path.read_text())
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    rejected = []
    for item in queue:
        if item.get("state") != "rejected":
            continue
        action_at = item.get("damar_action_at")
        if not action_at:
            continue
        ts = datetime.fromisoformat(action_at.replace("Z", "+00:00"))
        if ts >= cutoff:
            rejected.append({
                "id": item["id"],
                "topic_slug": item.get("topic_slug"),
                "reason_tag": next((h.get("reason_tag") for h in item.get("state_history", [])
                                    if h.get("state") == "rejected"), None),
                "notes": item.get("damar_notes"),
            })
    return rejected


def _annotate_with_engagement_buckets(runs):
    """W3.1 outcome-aware: tag each run as 'top20', 'bottom20', or 'mid60' by engagement.

    Engagement metric priority: ig_likes > ig_save_count > ig_reach. Runs without
    any IG metric are tagged 'unmeasured'.
    Tagging only meaningful when N>=10 measured runs (else 'insufficient_data').
    """
    measured = []
    for r in runs:
        score = r.get("ig_likes") or r.get("ig_save_count") or r.get("ig_reach")
        if score is not None and score > 0:
            r["_engagement_score"] = score
            measured.append(r)
        else:
            r["_engagement_bucket"] = "unmeasured"

    if len(measured) < 10:
        for r in measured:
            r["_engagement_bucket"] = "insufficient_data"
        return runs

    measured.sort(key=lambda x: x["_engagement_score"], reverse=True)
    n = len(measured)
    top_cut = max(1, n // 5)  # top 20%
    bot_cut = n - max(1, n // 5)  # bottom 20%

    for i, r in enumerate(measured):
        if i < top_cut:
            r["_engagement_bucket"] = "top20"
        elif i >= bot_cut:
            r["_engagement_bucket"] = "bottom20"
        else:
            r["_engagement_bucket"] = "mid60"
    return runs


def build_synthesis_prompt(data):
    """Build the prompt for claude -p Reflexion synthesis."""
    iso_week = datetime.now(timezone.utc).strftime("%Y-W%V")
    # W3.1: tag runs with engagement buckets before sending to LLM
    data["runs"] = _annotate_with_engagement_buckets(data["runs"])
    n_runs = len(data["runs"])
    n_critic = len(data["critic_failures"])
    n_rej = len(data["rejections"])
    n_top = sum(1 for r in data["runs"] if r.get("_engagement_bucket") == "top20")
    n_bot = sum(1 for r in data["runs"] if r.get("_engagement_bucket") == "bottom20")

    return f"""You are doing the weekly Reflexion synthesis for Bali Zero WR2 carousel agent.

Week: {iso_week}.
Last 7 days: {n_runs} carousel runs, {n_critic} critic failures, {n_rej} rejections.
**Outcome-aware (W3.1)**: {n_top} runs tagged top20 (high IG engagement), {n_bot} tagged bottom20. Each run carries `_engagement_bucket` field. Use this signal to weigh lessons — patterns that correlate with top20 are HIGH-VALUE, patterns that correlate with bottom20 are HIGH-RISK.

Below is the structured data. Your job: extract ≤10 verbal lessons. NO MORE THAN 10. Each
lesson must be a single sentence, actionable, citable to specific runs/slides.

For each lesson, classify:
- category: voice | layout | image | copy | regulatory
- confidence: low (N≤2 motivating runs), medium (3-5), high (6+)
- proposes_amendment: true if lesson should change constitution.md (rare); false otherwise
- suggested_destination: voice/on-tone-examples.md | voice/off-tone-examples.md | constitution.md | layouts/_proposed/<name>.md

CRITICAL: do NOT invent lessons. If signal is too thin to draw conclusions, return fewer than
10 lessons. Self-justification noise is the failure mode to avoid.

Data:

```json
{json.dumps(data, indent=2)}
```

Output format (JSON):

```json
{{
  "week": "{iso_week}",
  "lessons": [
    {{
      "lesson_text": "When body uses UPPERCASE in tax-domain carousels, drop word count to ≤30 (not 35) — 5/5 tax runs this week had Damar shorten body in published_with_edits.",
      "category": "voice",
      "confidence": "medium",
      "motivating_run_ids": [42, 43, 44, 45, 46],
      "proposes_amendment": false,
      "suggested_destination": "voice/on-tone-examples.md",
      "suggested_addition": "<exact text to append to the destination>"
    }}
  ],
  "synthesis_notes": "Brief 1-paragraph summary of what the agent learned this week."
}}
```

Return ONLY the JSON object. No prose preamble. No markdown fences around the JSON."""


def call_claude_synthesis(prompt):
    """Invoke claude -p with the synthesis prompt. Returns parsed JSON or None on failure."""
    env = os.environ.copy()
    # Defense-in-depth: never pay-per-token
    env.pop("ANTHROPIC_API_KEY", None)

    try:
        result = subprocess.run(
            ["claude", "-p", "--model", "claude-opus-4-8"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=600,
            env=env,
        )
        if result.returncode != 0:
            print(f"claude -p exit {result.returncode}: {result.stderr[:500]}", file=sys.stderr)
            return None
        out = result.stdout.strip()
        # Strip code fences if present
        if out.startswith("```"):
            out = out.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            if out.startswith("json\n"):
                out = out[5:]
        return json.loads(out)
    except subprocess.TimeoutExpired:
        print("claude -p timed out after 600s", file=sys.stderr)
        return None
    except json.JSONDecodeError as e:
        print(f"JSON parse failed: {e}", file=sys.stderr)
        print(f"Output was: {out[:1000]}", file=sys.stderr)
        return None


def write_lessons(synthesis):
    if not synthesis or not synthesis.get("lessons"):
        return 0

    week = synthesis["week"]
    lessons = synthesis["lessons"]

    # Write to DB
    if DB_PATH.exists():
        conn = sqlite3.connect(DB_PATH)
        try:
            for lesson in lessons:
                proposed_path = None
                if lesson.get("proposes_amendment"):
                    PROPOSED_DIR.mkdir(parents=True, exist_ok=True)
                    slug = lesson["lesson_text"][:50].lower().replace(" ", "-").replace(",", "")
                    proposed_path = PROPOSED_DIR / f"{week}-{slug}.md"
                    proposed_path.write_text(
                        f"# Proposed amendment {week}\n\n"
                        f"**Lesson**: {lesson['lesson_text']}\n\n"
                        f"**Category**: {lesson['category']}\n\n"
                        f"**Confidence**: {lesson['confidence']}\n\n"
                        f"**Motivating runs**: {lesson.get('motivating_run_ids')}\n\n"
                        f"**Suggested addition**:\n\n{lesson.get('suggested_addition', 'TBD by Antonello')}\n\n"
                        f"---\n\n*Generated by Reflexion synthesis on {datetime.now(timezone.utc).isoformat()}*"
                    )

                conn.execute("""
                    INSERT INTO reflective_lessons
                    (week_synthesized, lesson_text, motivating_run_ids, lesson_category,
                     confidence, proposed_amendment_path)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    week,
                    lesson["lesson_text"],
                    json.dumps(lesson.get("motivating_run_ids", [])),
                    lesson["category"],
                    lesson["confidence"],
                    str(proposed_path) if proposed_path else None,
                ))
            conn.commit()
        finally:
            conn.close()

    # Route layout-scoped lessons to the layout library's _proposed/ dir (audit 2026-07-14,
    # Wave-4 item 16). Requires BOTH structured signals to agree (category AND destination
    # prefix) — never a bare substring match on lesson_text (cicatrix scar #3 guard-over-match).
    for lesson in lessons:
        dest = lesson.get("suggested_destination", "")
        if lesson.get("category") == "layout" and dest.startswith("layouts/_proposed/"):
            _write_layout_proposal(lesson, week)

    # Append voice lessons to on-tone/off-tone
    for lesson in lessons:
        dest = lesson.get("suggested_destination", "")
        addition = lesson.get("suggested_addition")
        if not addition:
            continue
        if "on-tone-examples.md" in dest and ON_TONE_PATH.exists():
            with ON_TONE_PATH.open("a") as f:
                f.write(f"\n\n---\n\n*Reflexion {week}*: {addition}\n")
        elif "off-tone-examples.md" in dest and OFF_TONE_PATH.exists():
            with OFF_TONE_PATH.open("a") as f:
                f.write(f"\n\n---\n\n*Reflexion {week}*: {addition}\n")

    return len(lessons)


def _write_layout_proposal(lesson, week) -> Path:
    """Write one layout-scoped lesson as a proposal file in LAYOUTS_PROPOSED_DIR.

    Filename prefers the `<name>` the synthesis put in `suggested_destination`
    ("layouts/_proposed/<name>.md"); falls back to a slug of the lesson text if the LLM left
    the literal placeholder or an empty tail. Lifecycle (proposed -> operator review -> merged
    into the library or discarded) is documented in LAYOUTS_PROPOSED_DIR/README.md.
    """
    dest = lesson.get("suggested_destination", "")
    LAYOUTS_PROPOSED_DIR.mkdir(parents=True, exist_ok=True)

    name_part = dest.rsplit("/", 1)[-1] if "/" in dest else ""
    if not name_part or name_part == "<name>.md":
        slug = lesson["lesson_text"][:50].lower().replace(" ", "-").replace(",", "")
        name_part = f"{slug}.md"
    if not name_part.endswith(".md"):
        name_part += ".md"

    proposal_path = LAYOUTS_PROPOSED_DIR / f"{week}-{name_part}"
    proposal_path.write_text(
        f"# Layout proposal {week}\n\n"
        f"**Lesson**: {lesson['lesson_text']}\n\n"
        f"**Confidence**: {lesson.get('confidence', 'unknown')}\n\n"
        f"**Motivating runs**: {lesson.get('motivating_run_ids')}\n\n"
        f"**Suggested addition**:\n\n{lesson.get('suggested_addition', 'TBD by Antonello')}\n\n"
        f"---\n\n*Generated by Reflexion synthesis on {datetime.now(timezone.utc).isoformat()}*\n\n"
        f"> Lifecycle: proposed -> operator review -> merged into "
        f"`skills/bali-zero-brand/layouts/` or discarded. See this directory's README.md.\n"
    )
    return proposal_path


def _record(status, *, signals_found, lessons_written, notes=""):
    """Delta Gate: append an auditable run record via the unified core. Native WR2 status
    persisted on disk (operator vocabulary), canonical enum drives is_tautological."""
    core_status = _WR2_STATUS_TO_CORE.get(status)
    if core_status is None:
        raise ValueError(f"unknown WR2 reflexion status {status!r}; "
                         f"expected one of {sorted(_WR2_STATUS_TO_CORE)}")
    reflexion_core.record_run(
        SKILL_DIR, loop="wr2", window_days=7,
        signals_found=signals_found, lessons_written=lessons_written,
        status=core_status, loop_status=status, notes=notes,
    )


def _warn_if_tautological():
    """Surface the Omeostasi-Tautologica alarm: last HOT_WINDOW runs all no-learning."""
    try:
        if reflexion_core.is_tautological(SKILL_DIR):
            print(f"[wr2-reflexion] ⚠ TAUTOLOGY ALARM: last {reflexion_core.HOT_WINDOW} runs "
                  f"all no-learning — green cron, zero state-delta. Investigate whether carousel "
                  f"runs are actually being produced.", file=sys.stderr)
    except Exception:
        pass


def main():
    data = fetch_last_7_days()
    data["rejections"] = fetch_rejections_from_queue()

    if not data["runs"] and not data["rejections"]:
        # Delta Gate: NOT a silent return 0 — an empty week is recorded as NO_INPUT.
        _record("NO_INPUT", signals_found=0, lessons_written=0,
                notes="no carousel runs / rejections in last 7d")
        print("No data in last 7 days; recorded NO_INPUT (honest empty run, NOT theater).")
        _warn_if_tautological()
        return 0

    n_signals = len(data["runs"]) + len(data["rejections"])
    prompt = build_synthesis_prompt(data)
    synthesis = call_claude_synthesis(prompt)
    if not synthesis:
        _record("LLM_FAILED", signals_found=n_signals, lessons_written=0,
                notes="claude -p synthesis failed with data present")
        print("Synthesis failed; no lessons written.", file=sys.stderr)
        return 1  # real failure with input present — worth alerting

    n_written = write_lessons(synthesis)
    status = "SYNTHESIZED" if n_written > 0 else "THIN_SIGNAL"
    _record(status, signals_found=n_signals, lessons_written=n_written,
            notes=synthesis.get("synthesis_notes", "")[:500])
    print(f"Synthesized {n_written} lessons for week {synthesis.get('week')}.")
    if synthesis.get("synthesis_notes"):
        print(f"Notes: {synthesis['synthesis_notes']}")
    if status == "THIN_SIGNAL":
        _warn_if_tautological()
    return 0


if __name__ == "__main__":
    sys.exit(main())
