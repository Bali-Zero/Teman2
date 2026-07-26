#!/usr/bin/env python3
"""wr2_pregate_shadow.py — Phase 2 shadow-measurement harness for the
deterministic editorial pre-gate (wr2_editorial_pregate.py) against
historical WR2 decks.

ADDITIVE / SHADOW ONLY / ZERO LLM. This script never writes to
`war_room_drafts` (the `--fetch` mode issues SELECT only) and never touches
`wr2_draft_generator.py` / `scripts/wr2_html_renderer/composer.py` — it does
not modify either file, and neither imports `wr2_editorial_pregate.py`.
Implements the Phase-2 build mandate's deliverable metric: "the pre-gate
would have flagged X of N existing decks, breakdown by check" — computed in
well under a second because every check in wr2_editorial_pregate.py is a
pure function (no LLM call, no network, no DB write).

Two modes:

  --fetch --out <fixture.json> [--limit N]
      Read-only query against Postgres (asyncpg, DSN from env DATABASE_URL
      — same convention wr2_draft_generator.py:2064 / wr2_ir_shadow_replay.py
      already use) selecting historical decks with a rendered `slides_json`
      — the REAL production slide copy (headline/subhead/body/slide_type
      per slide, the `_normalise_slides` output shape), NOT `brief_json`
      (which only carries the source article, not what was actually
      drafted — insufficient for this harness). Dumps to a local JSON
      fixture: `[{id, topic, register, status, created_at, slides: [...]}]`.
      NEVER writes to the DB.

  --shadow --fixture <fixture.json> --out <report.json> [--limit N]
      Runs `wr2_editorial_pregate.pregate_flat` over every deck's `slides`,
      aggregates FAIL/WARN/SKIP counts per check across the corpus, and
      writes per-check totals + full per-deck detail to --out. No `spine`
      is passed (production does not carry one yet — Mossa C/spine-as-
      first-class-field is a later step in the ratified spec) so
      `check_spine_echo` SKIPs on every deck; this is expected and reported
      honestly in the totals, never hidden or backfilled with a guess.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import wr2_editorial_pregate as pg  # noqa: E402

logger = logging.getLogger("wr2.pregate_shadow")

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_ID_PHONE_RE = re.compile(r"\+?62[\s-]?8\d{2}[\s-]?\d{3,4}[\s-]?\d{3,4}")

_CHECK_NAMES: tuple[str, ...] = (
    "check_duplicate_slides",
    "check_bullet_promise",
    "check_caps_policy",
    "check_cta_presence",
    "check_kicker_unique",
    "check_kind_coverage",
    "check_spine_echo",
)


# ─────────────────────────────────────────────────────────────────────────
# --fetch: read-only historical-deck pull (production slide copy)
# ─────────────────────────────────────────────────────────────────────────


def _scrub_pii(obj: Any) -> Any:
    """Same belt-and-suspenders scrub as wr2_ir_shadow_replay._scrub_pii —
    `war_room_drafts` has no client_id/FK into the clients table (verified
    via information_schema.columns), and every slides_json sampled this
    session is public regulatory/tourism editorial copy (zero PII hits on
    the full 63-deck corpus, verified this session). This makes no
    completeness promise; any hit is logged for human audit. SYMBIOSIS Law
    2 / UU PDP boundary."""
    text = json.dumps(obj, ensure_ascii=False)
    hits = len(_EMAIL_RE.findall(text)) + len(_ID_PHONE_RE.findall(text))
    if hits:
        logger.warning("PII-shaped pattern found (%d hits) — redacting before fixture write", hits)
        text = _EMAIL_RE.sub("[EMAIL-REDACTED]", text)
        text = _ID_PHONE_RE.sub("[PHONE-REDACTED]", text)
        return json.loads(text)
    return obj


async def _fetch_decks(out_path: Path, limit: int | None) -> int:
    import asyncpg  # local import: --shadow mode must not require asyncpg to be installed

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit(
            "DATABASE_URL not set (read-only fetch — see scripts/pg.sh for the "
            "canonical proxy DSN, or export DATABASE_URL directly)"
        )
    conn = await asyncpg.connect(dsn=dsn)
    try:
        # Verified filter (this session, mcp__postgres-nuzantara__query /
        # scripts/pg.sh, read-only role): status='rendered' AND
        # slides_json IS NOT NULL = 63 rows, 557 slides total.
        sql = (
            "SELECT id, topic, register, status, created_at, slides_json->'slides' AS slides "
            "FROM war_room_drafts "
            "WHERE status = 'rendered' AND slides_json IS NOT NULL "
            "ORDER BY created_at ASC"
        )
        if limit:
            sql += " LIMIT $1"
            rows = await conn.fetch(sql, limit)
        else:
            rows = await conn.fetch(sql)
    finally:
        await conn.close()

    decks: list[dict[str, Any]] = []
    for r in rows:
        slides = r["slides"]
        if isinstance(slides, str):
            slides = json.loads(slides)
        deck = {
            "id": str(r["id"]),
            "topic": r["topic"],
            "register": r["register"],
            "status": r["status"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "slides": slides or [],
        }
        decks.append(_scrub_pii(deck))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(decks, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Fetched %d decks -> %s", len(decks), out_path)
    return len(decks)


# ─────────────────────────────────────────────────────────────────────────
# --shadow: run the deterministic pre-gate over the fixture
# ─────────────────────────────────────────────────────────────────────────


def _run_shadow(fixture_path: Path, out_path: Path, *, limit: int | None) -> dict[str, Any]:
    decks: list[dict[str, Any]] = json.loads(fixture_path.read_text(encoding="utf-8"))
    if limit:
        decks = decks[:limit]

    per_check_fail: dict[str, int] = dict.fromkeys(_CHECK_NAMES, 0)
    per_check_warn: dict[str, int] = dict.fromkeys(_CHECK_NAMES, 0)
    per_check_skip: dict[str, int] = dict.fromkeys(_CHECK_NAMES, 0)
    aggregate_verdicts: dict[str, int] = {"PASS": 0, "FAIL": 0, "WARN": 0}
    per_deck: list[dict[str, Any]] = []
    n_errors = 0

    for deck in decks:
        slides = deck.get("slides") or []
        try:
            report = pg.pregate_flat(slides, spine=None)
        except Exception as e:  # one malformed deck must never kill the run
            n_errors += 1
            per_deck.append({"id": deck.get("id"), "topic": deck.get("topic"), "error": repr(e)})
            continue
        aggregate_verdicts[report.verdict] = aggregate_verdicts.get(report.verdict, 0) + 1
        per_deck.append({
            "id": deck.get("id"),
            "topic": deck.get("topic"),
            "slide_count": report.slide_count,
            "verdict": report.verdict,
            "checks": [c.to_dict() for c in report.checks],
        })
        for c in report.checks:
            if c.verdict == "FAIL":
                per_check_fail[c.check] = per_check_fail.get(c.check, 0) + 1
            elif c.verdict == "WARN":
                per_check_warn[c.check] = per_check_warn.get(c.check, 0) + 1
            elif c.verdict == "SKIP":
                per_check_skip[c.check] = per_check_skip.get(c.check, 0) + 1

    result: dict[str, Any] = {
        "n_decks": len(decks),
        "n_errors": n_errors,
        "aggregate_verdicts": aggregate_verdicts,
        "decks_flagged_fail": aggregate_verdicts.get("FAIL", 0),
        "decks_flagged_warn": aggregate_verdicts.get("WARN", 0),
        "per_check_fail_count": per_check_fail,
        "per_check_warn_count": per_check_warn,
        "per_check_skip_count": per_check_skip,
        "per_deck": per_deck,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Shadow run complete: %d decks -> %s", len(decks), out_path)
    return result


# ─────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fetch", action="store_true", help="Read-only fetch of historical decks' production slides into a JSON fixture")
    mode.add_argument("--shadow", action="store_true", help="Run the pre-gate over a fixture and report per-check violation counts")
    parser.add_argument("--out", type=Path, help="Output path (--fetch: fixture JSON; --shadow: report JSON)")
    parser.add_argument("--fixture", type=Path, help="Input fixture JSON (--shadow only)")
    parser.add_argument("--limit", type=int, default=None, help="Cap the number of decks processed")
    args = parser.parse_args()

    if args.fetch:
        if not args.out:
            parser.error("--fetch requires --out <fixture.json>")
        n = asyncio.run(_fetch_decks(args.out, args.limit))
        print(f"Fetched {n} decks -> {args.out}")
        return 0

    if not args.fixture:
        parser.error("--shadow requires --fixture <fixture.json>")
    if not args.out:
        parser.error("--shadow requires --out <report.json>")
    result = _run_shadow(args.fixture, args.out, limit=args.limit)
    print(json.dumps({
        "n_decks": result["n_decks"],
        "n_errors": result["n_errors"],
        "aggregate_verdicts": result["aggregate_verdicts"],
        "per_check_fail_count": result["per_check_fail_count"],
        "per_check_warn_count": result["per_check_warn_count"],
        "per_check_skip_count": result["per_check_skip_count"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
