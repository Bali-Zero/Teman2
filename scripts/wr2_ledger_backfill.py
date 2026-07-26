#!/usr/bin/env python3
"""WR2 Creative Ledger — historical BACKFILL (spec §Mossa-D "BACKFILL degli
assi nuovi", Sonnet red-team BLOCKER-2).

`arc` / `spine_gist` / `hook_type` did not exist as fields when the monolith
engine produced the ~60 decks now in `war_room_drafts`. Without them the
Creative Ledger's cooldown sees only the handful of post-cutover planner_writer
decks — a cold-start that lasts weeks. This one-shot pass reverse-engineers
those axes FROM THE FINISHED COPY (a fuzzy task with its own error rate — hence
`--sample-qa` for human spot-check, spec §Mossa-D "con QA a campione umano") and
writes them ADDITIVELY into the deck's existing `council_debate_json` under a
`backfill` sub-object. It NEVER touches a native planner_writer `arc` and never
overwrites a prior backfill unless `--force`.

DESIGN INVARIANTS (grounded 2026-07-25):
  - NO schema migration — writes into the existing `council_debate_json` jsonb
    (same column `_process_one_planner_writer` writes `arc` to). `wr2_creative_
    ledger._arc_from_council` reads `backfill.arc` as a fallback to native.
  - ADDITIVE + non-destructive: reads the current council blob, merges a
    `backfill` key, writes the WHOLE blob back (never a partial column update
    that could drop sibling keys — scar #9 state-schema drift).
  - Idempotent: a deck with a native `arc` OR an existing `backfill` is SKIPPED
    (unless `--force`). Re-running is a no-op.
  - `--dry-run` (DEFAULT) writes nothing — it prints what WOULD be labeled.
    `--apply` performs the UPDATEs. A backfill that mutates prod on import would
    be exactly the class of accident this project guards against.
  - LLM via the `claude` CLI subprocess (MAX-plan OAuth) — Anthropic SDK BANNED
    (Golden Rule #13). Mirrors `empirical_ig_analyzer.classify_hooks_batch`'s
    exact invocation (stdin=DEVNULL, JSON-on-last-line parse, best-effort).
  - PII: WR2 decks are Bali Zero's own editorial copy on PUBLIC regulation, not
    client PII — cloud-safe. No secrets ever enter the prompt.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("wr2_ledger_backfill")

# The 7 ratified arcs (spec §8, RATIFIED by Zero 2026-07-21) — MUST match
# wr2_carousel_ir.ARCS. Imported at runtime below to stay in one SSOT; this
# tuple is the fallback/validation set the labeler is constrained to.
RATIFIED_ARCS: tuple[str, ...] = (
    "news_alert",
    "deadline",
    "myth_buster",
    "worked_example",
    "comparison",
    "explainer",
    "status_roundup",
)

# hook_type vocabulary — reuse the SAME categories the empirical IG analyzer
# already uses (`empirical_ig_analyzer.HOOK_CATEGORIES`), so a backfilled
# hook_type is comparable to the ones the IG loop will eventually attach.
HOOK_CATEGORIES: tuple[str, ...] = ("question", "stat", "story", "contrarian", "list")

_CLAUDE_TIMEOUT_S = 240
_BACKFILL_MODEL = "claude-sonnet-5"  # implementer-tier labeling, not a final gate


@dataclass(frozen=True)
class DeckToLabel:
    draft_id: str
    topic: str
    copy_excerpt: str  # the finished slide copy, joined — what the LLM reads


@dataclass(frozen=True)
class BackfillLabel:
    arc: str
    spine_gist: str
    hook_type: str
    confidence: float


# ── pure helpers (unit-testable, zero I/O) ────────────────────────────────


def needs_backfill(council: dict[str, Any] | None, *, force: bool = False) -> bool:
    """True iff this deck should be (re)labeled. A native planner_writer `arc`
    means the deck already carries real axes — never overwrite it (force or
    not). An existing `backfill` sub-object means we already labeled it — skip
    unless `--force`. A monolith deck with neither is the target."""
    if not isinstance(council, dict):
        return True  # no council blob at all → label it (will create the blob)
    native = council.get("arc")
    if isinstance(native, str) and native.strip():
        return False  # native arc is authoritative, never touched
    has_backfill = isinstance(council.get("backfill"), dict)
    if has_backfill and not force:
        return False
    return True


def extract_copy_excerpt(slides_blob: Any, *, max_chars: int = 2000) -> str:
    """Flatten a deck's finished slide copy (headline + subhead + body) into a
    single excerpt for the labeler. Best-effort: odd shapes contribute nothing.
    Bounded to `max_chars` so a long deck can't bloat the prompt."""
    if isinstance(slides_blob, str):
        try:
            slides_blob = json.loads(slides_blob)
        except json.JSONDecodeError:
            return ""
    slides = slides_blob.get("slides") if isinstance(slides_blob, dict) else slides_blob
    if not isinstance(slides, list):
        return ""
    parts: list[str] = []
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        for key in ("headline", "subhead", "body", "take_label"):
            val = str(slide.get(key) or "").strip()
            if val:
                parts.append(val)
    excerpt = " / ".join(parts)
    return excerpt[:max_chars]


def build_backfill_prompt(deck: DeckToLabel) -> str:
    """One deck → one labeling prompt. Constrains arc to the 7-slate and
    hook_type to the shared vocab; asks for a one-line spine_gist reverse-
    engineered from the copy, plus a confidence the QA pass can triage on."""
    arcs = "|".join(RATIFIED_ARCS)
    hooks = "|".join(HOOK_CATEGORIES)
    return (
        "You are labeling a FINISHED Instagram carousel (Bali Zero editorial, "
        "Indonesian immigration/tax/company regulation) to recover its editorial "
        "structure. Read the slide copy and emit ONLY a single JSON object on the "
        "last line — no prose, no markdown fences.\n"
        f'Schema: {{"arc":"{arcs}","spine_gist":"<one sentence: the ONE guiding '
        'idea the deck is built around, reverse-engineered from the copy>",'
        f'"hook_type":"{hooks}","confidence":<0.0-1.0>}}\n'
        f"arc = the narrative shape that best fits (news_alert=breaking change; "
        "deadline=a date/expiry to act on; myth_buster=corrects a false belief; "
        "worked_example=one concrete case step-by-step; comparison=A vs B verdict; "
        "explainer=teaches a concept/forces; status_roundup=list of statuses).\n"
        f"hook_type = the opening slide's device.\n\n"
        f"TOPIC: {deck.topic}\n"
        f"SLIDE COPY: {deck.copy_excerpt}"
    )


def parse_backfill_response(stdout: str) -> BackfillLabel | None:
    """Parse the labeler's JSON-on-last-line (mirrors empirical_ig_analyzer's
    reversed-scan). Returns None on any unparseable/out-of-vocab/missing-field
    output — the caller counts it as a failed label, never guesses."""
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            return None
        arc = str(parsed.get("arc") or "").strip()
        spine = str(parsed.get("spine_gist") or "").strip()
        hook = str(parsed.get("hook_type") or "").strip()
        if arc not in RATIFIED_ARCS or hook not in HOOK_CATEGORIES or not spine:
            return None
        try:
            conf = float(parsed.get("confidence"))
        except (TypeError, ValueError):
            conf = 0.0
        conf = max(0.0, min(1.0, conf))
        return BackfillLabel(arc=arc, spine_gist=spine, hook_type=hook, confidence=conf)
    return None


def merge_backfill(council: dict[str, Any] | None, label: BackfillLabel) -> dict[str, Any]:
    """Return a NEW council dict with the `backfill` sub-object merged in,
    preserving every existing key (scar #9: never drop sibling keys). Marks
    `backfilled:true` + the model + a monotone label version so a future reader
    can tell a recovered axis from a native one."""
    out = dict(council) if isinstance(council, dict) else {}
    out["backfill"] = {
        "arc": label.arc,
        "spine_gist": label.spine_gist,
        "hook_type": label.hook_type,
        "confidence": label.confidence,
        "backfilled": True,
        "model": _BACKFILL_MODEL,
        "schema_version": 1,
    }
    return out


# ── LLM call (thin subprocess wrapper, mirrors empirical_ig_analyzer) ──────


def label_deck(deck: DeckToLabel) -> BackfillLabel | None:
    """One `claude -p` call per deck. Best-effort: FileNotFound/timeout/non-zero
    exit/unparseable → None (a failed label, logged, never a fabricated arc)."""
    prompt = build_backfill_prompt(deck)
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--model", _BACKFILL_MODEL],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=_CLAUDE_TIMEOUT_S,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("claude CLI failed for deck %s: %s", deck.draft_id, exc)
        return None
    if result.returncode != 0:
        logger.warning("claude -p exited %s for deck %s", result.returncode, deck.draft_id)
        return None
    return parse_backfill_response(result.stdout)


# ── DB I/O (thin) ─────────────────────────────────────────────────────────

_SELECT_DECKS_SQL = """
    SELECT id, topic, slides_json, council_debate_json
      FROM war_room_drafts
     WHERE status IN ('rendered', 'published')
       AND slides_json IS NOT NULL
     ORDER BY created_at DESC
"""

_UPDATE_COUNCIL_SQL = """
    UPDATE war_room_drafts
       SET council_debate_json = $2::jsonb,
           updated_at = NOW()
     WHERE id = $1
"""


def _coerce(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return None
    return raw if isinstance(raw, dict) else None


async def run_backfill(
    conn: Any,
    *,
    apply: bool,
    force: bool,
    sample_qa: int,
    limit: int | None,
) -> dict[str, Any]:
    """Select candidate decks, label the ones that `needs_backfill`, and (if
    `apply`) write the merged council blob back. Returns a summary dict.
    `sample_qa` random labelings are collected for human spot-check (spec
    §Mossa-D). Deterministic sampling (first-N of the processed order — no
    Math.random, forbidden in this codebase's scripting sandbox and avoided
    here for reproducibility of the QA set)."""
    rows = await conn.fetch(_SELECT_DECKS_SQL)
    considered = labeled = skipped = failed = written = 0
    qa_samples: list[dict[str, Any]] = []

    for row in rows:
        if limit is not None and considered >= limit:
            break
        considered += 1
        council = _coerce(row["council_debate_json"])
        if not needs_backfill(council, force=force):
            skipped += 1
            continue

        excerpt = extract_copy_excerpt(row["slides_json"])
        if not excerpt:
            failed += 1
            logger.warning("deck %s has no usable copy — skipped", row["id"])
            continue

        deck = DeckToLabel(draft_id=str(row["id"]), topic=str(row["topic"] or ""), copy_excerpt=excerpt)
        label = label_deck(deck)
        if label is None:
            failed += 1
            continue
        labeled += 1

        if len(qa_samples) < sample_qa:
            qa_samples.append({
                "draft_id": deck.draft_id,
                "topic": deck.topic,
                "excerpt": excerpt[:300],
                "arc": label.arc,
                "spine_gist": label.spine_gist,
                "hook_type": label.hook_type,
                "confidence": label.confidence,
            })

        if apply:
            merged = merge_backfill(council, label)
            await conn.execute(_UPDATE_COUNCIL_SQL, uuid.UUID(deck.draft_id), json.dumps(merged))
            written += 1

    return {
        "considered": considered,
        "labeled": labeled,
        "skipped_native_or_done": skipped,
        "failed": failed,
        "written": written,
        "apply": apply,
        "qa_samples": qa_samples,
    }


async def _amain(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="WR2 Creative Ledger historical backfill (Move D)")
    parser.add_argument("--apply", action="store_true", help="perform DB writes (default: dry-run, writes nothing)")
    parser.add_argument("--force", action="store_true", help="re-label decks that already have a backfill (never touches a NATIVE arc)")
    parser.add_argument("--sample-qa", type=int, default=5, metavar="N", help="collect N labelings for human QA (default 5)")
    parser.add_argument("--limit", type=int, default=None, help="cap decks considered (default: all)")
    args = parser.parse_args(argv)

    import asyncpg  # local import: keep module import side-effect-free/testable

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL not set")
        return 2

    conn = await asyncpg.connect(dsn)
    try:
        summary = await run_backfill(
            conn, apply=args.apply, force=args.force, sample_qa=args.sample_qa, limit=args.limit,
        )
    finally:
        await conn.close()

    mode = "APPLY" if args.apply else "DRY-RUN (no writes)"
    logger.info(
        "[%s] considered=%d labeled=%d skipped(native/done)=%d failed=%d written=%d",
        mode, summary["considered"], summary["labeled"],
        summary["skipped_native_or_done"], summary["failed"], summary["written"],
    )
    print(json.dumps(summary, indent=2, default=str))
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    return asyncio.run(_amain(sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
