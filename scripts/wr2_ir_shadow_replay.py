#!/usr/bin/env python3
"""wr2_ir_shadow_replay.py — Phase 1 shadow-replay harness for the typed
Carousel IR (wr2_carousel_ir.py) against historical WR2 decks.

ADDITIVE / SHADOW ONLY. This script never writes to `war_room_drafts` (the
`--fetch` mode issues SELECT only) and never touches
`wr2_draft_generator.py` / `scripts/wr2_html_renderer/composer.py` at
runtime beyond IMPORTING their pure helper functions for reuse — it does not
modify either file, and neither is wired to call anything in this module or
in `wr2_carousel_ir.py`. Implements spec §3 rollout step 1's shadow-mode gate:
"misurare il fail-rate della validazione stretta sul replay PRIMA del
cutover" — this harness produces that measurement, it does not act on it.

Two modes:

  --fetch --out <fixture.json> [--limit N]
      Read-only query against Postgres (asyncpg, DSN from env DATABASE_URL —
      the same convention wr2_draft_generator.py:2064 uses) selecting
      historical decks with a usable brief_json. Dumps them to a local JSON
      fixture. NEVER writes to the DB.

      Population note (verified empirically via mcp__postgres-nuzantara__
      query this session, NOT trusted from the build mandate's stated "~34"):
      `SELECT status, count(*) FROM war_room_drafts GROUP BY status` shows
      status='rendered' at 63 rows, of which 61 have a non-null brief_json.
      "~34" does not match any status/filter combination found on the live
      table — this harness selects on the verified filter
      (status='rendered' AND brief_json IS NOT NULL, 61 rows) rather than
      the unverified number.

  --replay --fixture <fixture.json> --out <metrics.json> [--limit N]
      For each deck, builds the typed composition prompt by REUSING
      production's own prompt assembly (wr2_draft_generator._build_draft_prompt
      — system instructions + brief context + liveness/tone steer, imported
      directly, not reimplemented) with ONE swapped section: the trailing
      output-format directive is replaced with the typed-JSON-schema
      instructions (_TYPED_SCHEMA_DIRECTIVE below). Calls the SAME model
      production uses for composition (wr2_draft_generator.claude_compose_
      slides pins model="claude-opus-4-7", wr2_draft_generator.py:1091) via
      the sanctioned OAuth CLI path (backend.llm.claude_oauth_client.
      complete_async — never the banned Anthropic SDK). Runs
      wr2_carousel_ir.generate_slides_typed's validate-and-retry loop, then
      resolves every slide's family via the REAL composer.map_slide_to_family
      (imported, not reimplemented) and checks it matches the kind's
      intended family. Writes per-deck results + aggregate metrics to the
      --out path, incrementally (resumable — a deck already present in an
      existing --out file is skipped on re-run).

Rate-limit friendly by design: sequential calls only (never concurrent), a
configurable --sleep between decks, and a per-deck try/except so one bad
deck (timeout, malformed brief, OAuth hiccup) never kills the whole run.

This script does NOT run the full historical replay itself — quota spend at
that scale is the orchestrator's call, per the build mandate. It DOES
support `--replay --limit 1` as an end-to-end smoke test when the `claude`
CLI/OAuth is available in the calling environment.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
_BACKEND_RAG = _REPO_ROOT / "apps" / "backend-rag"
if str(_BACKEND_RAG) not in sys.path:
    sys.path.insert(0, str(_BACKEND_RAG))

import wr2_carousel_ir as ir  # noqa: E402
import wr2_draft_generator as wr2dg  # noqa: E402  (prompt-assembly REUSE only — see module docstring)
from wr2_html_renderer.composer import map_slide_to_family  # noqa: E402

logger = logging.getLogger("wr2.ir_shadow_replay")

# SAME model wr2_draft_generator.claude_compose_slides pins for slide
# composition (wr2_draft_generator.py:1091) — the shadow replay must measure
# the model production would actually use, not a cheaper substitute.
_COMPOSE_MODEL = "claude-opus-4-7"

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_ID_PHONE_RE = re.compile(r"\+?62[\s-]?8\d{2}[\s-]?\d{3,4}[\s-]?\d{3,4}")


# ─────────────────────────────────────────────────────────────────────────
# --fetch: read-only historical-deck pull
# ─────────────────────────────────────────────────────────────────────────


def _scrub_pii(obj: Any) -> Any:
    """Defensive regex scrub over the fetched brief_json before it lands in
    a local fixture file. `war_room_drafts` has NO client_id / FK into the
    clients table (verified via information_schema.columns this session)
    and every brief_json sampled is public regulatory/tourism-news content
    (a real row was read this session — Bali tourism-levy story, zero PII).
    This is belt-and-suspenders, not a load-bearing filter — any hit is
    logged so a human can audit, and this function makes NO completeness
    promise. SYMBIOSIS Law 2 / UU PDP boundary."""
    text = json.dumps(obj, ensure_ascii=False)
    hits = len(_EMAIL_RE.findall(text)) + len(_ID_PHONE_RE.findall(text))
    if hits:
        logger.warning("PII-shaped pattern found (%d hits) — redacting before fixture write", hits)
        text = _EMAIL_RE.sub("[EMAIL-REDACTED]", text)
        text = _ID_PHONE_RE.sub("[PHONE-REDACTED]", text)
        return json.loads(text)
    return obj


async def _fetch_decks(out_path: Path, limit: int | None) -> int:
    import asyncpg  # local import: --replay mode must not require asyncpg to be installed

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit(
            "DATABASE_URL not set (read-only fetch — see scripts/pg.sh for the "
            "canonical proxy DSN, or export DATABASE_URL directly)"
        )
    conn = await asyncpg.connect(dsn=dsn)
    try:
        # Verified filter (this session, mcp__postgres-nuzantara__query,
        # read-only role): status='rendered' AND brief_json IS NOT NULL =
        # 61 rows. NEVER a write — SELECT only.
        sql = (
            "SELECT id, topic, register, brief_json, created_at "
            "FROM war_room_drafts "
            "WHERE status = 'rendered' AND brief_json IS NOT NULL "
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
        brief = r["brief_json"]
        if isinstance(brief, str):
            brief = json.loads(brief)
        brief = _scrub_pii(brief)
        decks.append({
            "id": str(r["id"]),
            "topic": r["topic"],
            "register": r["register"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "brief_json": brief,
        })

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(decks, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Fetched %d decks -> %s", len(decks), out_path)
    return len(decks)


# ─────────────────────────────────────────────────────────────────────────
# --replay: typed-prompt composition + validate + family-resolution check
# ─────────────────────────────────────────────────────────────────────────

_TYPED_SCHEMA_DIRECTIVE = """OUTPUT FORMAT — TYPED CAROUSEL IR (Phase-1 shadow replay; NOT the production flat schema)

Return ONE JSON object: {"register": "<one of: rituale|analitico|ironico|militante|pedagogico|poetico|tecnico>", "slides": [...]}.

Every slide is a JSON object with a "kind" field (EXACTLY one of the 11 below) plus that kind's own fields. Slide 1 is ALWAYS kind="cover". Pick the kind that fits what THIS slide is actually doing — a list of facts is fact_stack, not prose; a back-and-forth is qa, not two statement slides; a step-by-step is timeline; a 2-4-way breakdown is triad; a single number is stat.

  kind="cover"       headline (str, required), subhead (str), regulation_code (str), image_prompt (str)
  kind="prose"       headline (str, required), body (str, required), subhead (str)
  kind="statement"   statement (str, required) — a 3-15 word punch line, never a paragraph
  kind="fact_stack"  heading (str, required), facts (list[str], required, >=1 — each item is ONE fact line), take_label (str), take_line (str)
  kind="status_list" heading (str, required), items (list[{label, value, status: "neutral"|"critical"|"positive"}], required, >=1)
  kind="timeline"    heading (str, required), steps (list[{date, label, current: bool}], required, >=1)
  kind="triad"       heading (str, required), items (list[{title, desc}], required, 2-6 items — e.g. "3 forces behind the rise")
  kind="qa"          pairs (list[{voice, line}], required, >=2 — first two entries are the two voices in the exchange)
  kind="stat"        value (str, required), unit (str), label (str), context (str)
  kind="citation"    claim (str, required), sources (list[{code, issuer, date, url, note}], required, >=1)
  kind="cta"         invite (str, required), trust_marker (str), reach (str)

Worked examples (illustrative SHAPE only — invent real content grounded in the article above, never reuse this text):

{"kind": "cover", "headline": "NEW LEVY RAISES RP 369 BILLION", "subhead": "TOURISM", "regulation_code": "", "image_prompt": "wide shot of a Bali beach at golden hour, editorial photography"}

{"kind": "fact_stack", "heading": "THE NUMBERS", "facts": ["7,050,314 foreign arrivals in 2025", "Rp369 billion collected via the tourist levy", "Only 34% compliance so far"], "take_label": "The Bali Zero read", "take_line": "Demand is not the problem here — enforcement is."}

{"kind": "qa", "pairs": [{"voice": "INVESTOR", "line": "IS THE LEVY NEW?"}, {"voice": "BALI ZERO", "line": "NO. ENFORCEMENT IS."}]}

Produce the full slide-shaped JSON NOW as ONE JSON object matching the kinds above exactly (a ```json fence is fine, or bare JSON — both parse). No text outside the JSON object.
"""

_PROD_DIRECTIVE_MARKER = "Produce the full "


def _swap_output_format(base_prompt: str, typed_schema_block: str) -> str:
    """The ONE swapped section (mandate STEP 3): everything ABOVE the
    production directive — system instructions + brief context + liveness/
    tone steer — is kept verbatim (it came straight out of wr2_draft_
    generator._build_draft_prompt); only the trailing free-form-JSON
    instruction is replaced with the typed-schema directive. Falls back to
    APPENDING rather than crashing if production's prompt phrasing drifts —
    never silently drops the brief context."""
    idx = base_prompt.rfind(_PROD_DIRECTIVE_MARKER)
    if idx == -1:
        logger.warning(
            "typed-prompt swap marker %r not found in base prompt — appending "
            "typed schema after the full base prompt instead of swapping",
            _PROD_DIRECTIVE_MARKER,
        )
        return f"{base_prompt}\n\n{typed_schema_block}"
    return f"{base_prompt[:idx].rstrip()}\n\n{typed_schema_block}"


def _build_typed_prompt(deck: dict[str, Any]) -> str:
    brief = deck.get("brief_json") or {}
    topic = deck.get("topic") or brief.get("article_title") or ""
    summary = brief.get("article_summary") or ""
    source_url = brief.get("source_url") or ""
    enrichment = brief.get("enrichment")
    live_reasons = brief.get("live_news_reasons")
    liveness_tier = brief.get("liveness_tier") or ""

    base_prompt = wr2dg._build_draft_prompt(
        topic,
        summary,
        source_url,
        enrichment=enrichment,
        live_reasons=live_reasons,
        avoid_steer="",
        liveness_tier=liveness_tier,
        recent_kickers=None,
    )
    return _swap_output_format(base_prompt, _TYPED_SCHEMA_DIRECTIVE)


def _make_call_fn() -> Callable[[str], str]:
    """Sync text-in/text-out wrapper over the sanctioned OAuth CLI path
    (backend.llm.claude_oauth_client.complete_async — never the banned
    Anthropic SDK, never ANTHROPIC_API_KEY). generate_slides_typed's
    contract is a plain sync callable (mirrors the OSS evidence's
    subprocess.run-based call_claude_cli) — this closure bridges that to
    the repo's async client via a fresh asyncio.run() per call, which is
    safe here because the replay driver itself is plain sync/sequential
    (never inside a running event loop when this is invoked)."""
    from backend.llm.claude_oauth_client import complete_async

    def call_fn(prompt: str) -> str:
        async def _call() -> str:
            resp = await complete_async(
                prompt,
                model=_COMPOSE_MODEL,
                timeout_s=300,
                endpoint="wr2_ir_shadow_replay",
            )
            return resp.text

        return asyncio.run(_call())

    return call_fn


def _replay_one(deck: dict[str, Any], *, max_retries: int) -> dict[str, Any]:
    deck_id = deck["id"]
    result: dict[str, Any] = {"id": deck_id, "topic": deck.get("topic")}

    try:
        typed_prompt = _build_typed_prompt(deck)
    except Exception as e:  # a malformed brief must not kill the run
        result.update({"status": "error", "attempts": 0, "error": f"prompt-build failed: {e!r}"})
        return result

    call_fn = _make_call_fn()
    call_count = {"n": 0}

    def counting_call_fn(p: str) -> str:
        call_count["n"] += 1
        return call_fn(p)

    t0 = time.perf_counter()
    try:
        deck_obj = ir.generate_slides_typed(typed_prompt, counting_call_fn, max_retries=max_retries)
    except ir.IRValidationExhausted as e:
        result.update({
            "status": "fail_after_retries",
            "attempts": call_count["n"],
            "error": str(e),
            "last_raw_text_head": e.last_raw_text[:2000],
            "wall_s": round(time.perf_counter() - t0, 1),
        })
        return result
    except Exception as e:  # per-deck try/except: one bad deck never kills the run
        result.update({
            "status": "error",
            "attempts": call_count["n"],
            "error": repr(e),
            "wall_s": round(time.perf_counter() - t0, 1),
        })
        return result

    total = len(deck_obj.slides)
    kinds: list[str] = []
    families: list[dict[str, str]] = []
    resolved_ok = True
    for i, s in enumerate(deck_obj.slides, start=1):
        kinds.append(s.kind)
        cdict = ir.to_composer_dict(s, index=i, total=total)
        resolved = map_slide_to_family(cdict, i, total)
        expected = ir.SLIDE_KIND_TO_FAMILY[s.kind]
        families.append({"kind": s.kind, "expected_family": expected, "resolved_family": resolved})
        if resolved != expected:
            resolved_ok = False

    result.update({
        "status": "ok",
        "attempts": call_count["n"],
        "register": deck_obj.register,
        "slide_count": total,
        "kinds": kinds,
        "families": families,
        "family_resolution_ok": resolved_ok,
        "wall_s": round(time.perf_counter() - t0, 1),
    })
    return result


def _aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(results)
    ok = [r for r in results if r.get("status") == "ok"]
    first_try = [r for r in ok if r.get("attempts") == 1]
    within_1_retry = [r for r in ok if isinstance(r.get("attempts"), int) and r["attempts"] <= 2]
    failed = [r for r in results if r.get("status") in ("fail_after_retries", "error")]

    kind_histogram: dict[str, int] = {}
    family_counts: dict[str, int] = {}
    resolved_total = 0
    resolved_ok_total = 0
    for r in ok:
        for k in r.get("kinds", []):
            kind_histogram[k] = kind_histogram.get(k, 0) + 1
        for f in r.get("families", []):
            family_counts[f["resolved_family"]] = family_counts.get(f["resolved_family"], 0) + 1
            resolved_total += 1
            if f["resolved_family"] == f["expected_family"]:
                resolved_ok_total += 1

    return {
        "n_decks": n,
        "first_try_valid_rate": round(len(first_try) / n, 3) if n else None,
        "valid_within_1_retry_rate": round(len(within_1_retry) / n, 3) if n else None,
        "fail_after_3_rate": round(len(failed) / n, 3) if n else None,
        "kind_histogram": kind_histogram,
        "family_resolution": {
            "resolved_pct": round(resolved_ok_total / resolved_total, 3) if resolved_total else None,
            "per_family_counts": family_counts,
        },
        "per_deck": results,
    }


def _write_metrics(out_path: Path, results: list[dict[str, Any]]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(_aggregate(results), indent=2, ensure_ascii=False), encoding="utf-8")


def _run_replay(fixture_path: Path, out_path: Path, *, limit: int | None, sleep_s: float, max_retries: int) -> None:
    decks: list[dict[str, Any]] = json.loads(fixture_path.read_text(encoding="utf-8"))
    if limit:
        decks = decks[:limit]

    results: list[dict[str, Any]] = []
    done_ids: set[str] = set()
    if out_path.exists():
        try:
            prior = json.loads(out_path.read_text(encoding="utf-8"))
            results = prior.get("per_deck", [])
            done_ids = {r["id"] for r in results if "id" in r}
            if done_ids:
                logger.info("Resuming: %d decks already in %s", len(done_ids), out_path)
        except Exception:
            logger.warning("Could not parse existing %s as prior results — starting fresh", out_path)

    for i, deck in enumerate(decks):
        if deck["id"] in done_ids:
            continue
        logger.info("[%d/%d] replaying deck %s (%s)", i + 1, len(decks), deck["id"], str(deck.get("topic", ""))[:60])
        try:
            r = _replay_one(deck, max_retries=max_retries)
        except Exception as e:  # belt-and-suspenders at the outer loop too
            r = {"id": deck["id"], "status": "error", "error": repr(e)}
        results.append(r)
        _write_metrics(out_path, results)  # incremental — safe to Ctrl-C / resume
        if i < len(decks) - 1:
            time.sleep(sleep_s)

    _write_metrics(out_path, results)
    logger.info("Replay complete: %d decks -> %s", len(results), out_path)


# ─────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fetch", action="store_true", help="Read-only fetch of historical decks into a JSON fixture")
    mode.add_argument("--replay", action="store_true", help="Replay decks from a fixture through the typed IR")
    parser.add_argument("--out", type=Path, help="Output path (--fetch: fixture JSON; --replay: metrics JSON)")
    parser.add_argument("--fixture", type=Path, help="Input fixture JSON (--replay only)")
    parser.add_argument("--limit", type=int, default=None, help="Cap the number of decks processed")
    parser.add_argument("--sleep", type=float, default=3.0, help="Seconds between deck calls in --replay")
    parser.add_argument("--max-retries", type=int, default=3, help="Validate-and-retry attempts per deck")
    args = parser.parse_args()

    if args.fetch:
        if not args.out:
            parser.error("--fetch requires --out <fixture.json>")
        n = asyncio.run(_fetch_decks(args.out, args.limit))
        print(f"Fetched {n} decks -> {args.out}")
        return 0

    if not args.fixture:
        parser.error("--replay requires --fixture <fixture.json>")
    if not args.out:
        parser.error("--replay requires --out <metrics.json>")
    _run_replay(args.fixture, args.out, limit=args.limit, sleep_s=args.sleep, max_retries=args.max_retries)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
