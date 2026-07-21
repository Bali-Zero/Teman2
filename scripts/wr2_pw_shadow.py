#!/usr/bin/env python3
"""wr2_pw_shadow.py — Phase 3 shadow-measurement harness for the
planner/writer split (wr2_planner_writer.py) against historical WR2 briefs.

ADDITIVE / SHADOW ONLY. This script never writes to `war_room_drafts` and
never touches `wr2_draft_generator.py` / `scripts/wr2_html_renderer/
composer.py` at runtime beyond IMPORTING their pure helper functions for
reuse (`wr2_draft_generator._build_enriched_brief`, `wr2_draft_generator.
_normalise_liveness_tier`, `composer.map_slide_to_family`, and — --render-
one only — `composer.compose_carousel`) — it does not modify any of them,
and none of them import `wr2_planner_writer.py` or this module. Implements
the Phase-3 build mandate's deliverable: run the planner/writer split (spec
§2 Mossa B) against real historical briefs and measure whether the arc
selection actually VARIES (the anti-disco-rotto claim the whole design
exists to prove), plus the deterministic pre-gate (Phase 2,
`wr2_editorial_pregate.pregate_typed`) getting its first REAL spine
(`check_spine_echo` has been SKIP-only on every prior shadow run — Phase 1's
replay never produced a spine, Phase 2's own shadow harness passes
`spine=None` explicitly; this is the first harness that has one to give it).

Fixture shape: SAME as `wr2_ir_shadow_replay.py --fetch`'s output —
`[{id, topic, register, created_at, brief_json}]` — reused rather than
duplicating a second `--fetch` mode: that script's read-only Postgres query
(`status='rendered' AND brief_json IS NOT NULL`, verified 61 rows this
session) is exactly the population this harness also wants (a brief to plan
from, not an already-drafted slide copy — that is `wr2_pregate_shadow.py`'s
different fixture shape, `slides_json`-based, which this harness does NOT
use). Run `python scripts/wr2_ir_shadow_replay.py --fetch --out
<fixture.json>` first if a fresh fixture is needed.

Two modes:

  --shadow --fixture <fixture.json> --out <report.json> [--limit N]
      For each of `limit` (default 12) sampled decks — stratified across
      domains IF the fixture carries a `domain`/`vertical`/`topic_domain`
      field (none of the 61 rows fetched this session carry one — verified
      by inspecting every row's brief_json key-set; see `_infer_domain`'s
      own docstring for the honest fallback this harness uses instead) —
      runs `wr2_planner_writer.plan_deck` + `write_slot` per slot, then
      `wr2_editorial_pregate.pregate_typed(deck, spine=plan.spine)`, then
      resolves every produced slide's layout family via the REAL
      `composer.map_slide_to_family` (imported, not reimplemented) and
      compares it to the kind's intended family
      (`wr2_carousel_ir.SLIDE_KIND_TO_FAMILY`). Writes per-deck results +
      aggregate metrics to --out, incrementally (resumable — a deck already
      present in an existing --out file is skipped on re-run). A lightweight
      in-run `recent_arcs` (newest-first, capped at 5) feeds
      `build_arc_priors` across the run — a stand-in for the not-yet-built
      Creative Ledger (spec §Mossa-D), explicitly NOT that ledger: this
      harness's own memory resets between runs, an honest limitation of a
      shadow tool, not the real thing.

  --render-one <deck_id> --fixture <fixture.json> --out <dir>
      Best-effort render of ONE produced deck to PNGs via the REAL renderer
      path (`wr2_html_renderer.composer.compose_carousel`, imported — same
      Playwright pipeline production uses). If Playwright/the composer
      module are unavailable in this environment, this FAILS HONESTLY
      (returns/prints a `status: unavailable` reason) rather than faking a
      result. Hero slides will show a download/placement failure in the
      result's `failures` list — this harness generates zero images
      (image_prompt -> image_url is out of scope, spec §2 Mossa B does not
      cover image generation), so that failure is EXPECTED, not a render
      bug; documented in the result, not hidden.

Rate-limit friendly by design: sequential calls only (never concurrent), a
configurable --sleep between decks, and a per-deck try/except so one bad
deck (timeout, malformed brief, plan/slot retry-exhaustion) never kills the
whole run.

This script does NOT run the full historical shadow itself — quota spend at
that scale is the orchestrator's call, per the build mandate. It DOES
support `--shadow --limit 1` as an end-to-end smoke test when the `claude`
CLI/OAuth is available in the calling environment.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from collections import Counter
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
import wr2_draft_generator as wr2dg  # noqa: E402  (enrichment-formatting + liveness-tier REUSE only)
import wr2_editorial_pregate as pg  # noqa: E402
import wr2_planner_writer as pw  # noqa: E402
from wr2_html_renderer.composer import map_slide_to_family  # noqa: E402

logger = logging.getLogger("wr2.pw_shadow")


# ─────────────────────────────────────────────────────────────────────────
# Domain inference + stratified sampling
# ─────────────────────────────────────────────────────────────────────────

_DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "immigration": ("visa", "kitas", "kitap", "immigration", "imigrasi", "deport", "passport", "overstay"),
    "tax": ("tax", "pajak", "coretax", "pph", "ppn", "npwp", "levy"),
    "company": ("pma", "pt ", "kbli", "oss", "nib", "company", "investor", "investment"),
    "property": ("villa", "property", "leasehold", "freehold", "land", "hgb"),
}


def _infer_domain(deck: dict[str, Any]) -> str:
    """Best-effort domain proxy for stratified sampling. `ir_replay_
    fixture.json` (this harness's own fixture, verified this session, all
    61 rows) carries NO `domain`/`vertical`/`topic_domain` field anywhere —
    at the row level or inside brief_json. Per the build mandate
    ("stratified across domains IF the fixture carries a domain field —
    read it"): a real field, when present, is read and trusted outright
    (the loop below checks for one first); only in its ABSENCE — today's
    reality for the delivered fixture — does this keyword heuristic over
    topic/article_title kick in. An honestly-labeled proxy, never presented
    as ground truth."""
    for key in ("domain", "vertical", "topic_domain"):
        val = deck.get(key) or (deck.get("brief_json") or {}).get(key)
        if val:
            return str(val).lower()
    text = " ".join([
        str(deck.get("topic") or ""),
        str((deck.get("brief_json") or {}).get("article_title") or ""),
    ]).lower()
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return domain
    return "other"


def _stratified_sample(decks: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Round-robin across inferred domain buckets (biggest bucket first,
    deterministic) so `limit` decks span the corpus's topical variety
    rather than clustering on whichever domain happens to dominate the
    front of the (created_at ASC-ordered) fixture."""
    if limit <= 0 or limit >= len(decks):
        return list(decks)
    buckets: dict[str, list[dict[str, Any]]] = {}
    for deck in decks:
        buckets.setdefault(_infer_domain(deck), []).append(deck)
    order = sorted(buckets, key=lambda k: -len(buckets[k]))
    idx_per_bucket = dict.fromkeys(order, 0)
    sampled: list[dict[str, Any]] = []
    while len(sampled) < limit:
        progressed = False
        for domain in order:
            if len(sampled) >= limit:
                break
            i = idx_per_bucket[domain]
            bucket = buckets[domain]
            if i < len(bucket):
                sampled.append(bucket[i])
                idx_per_bucket[domain] = i + 1
                progressed = True
        if not progressed:
            break
    return sampled


# ─────────────────────────────────────────────────────────────────────────
# Brief assembly — reuse wr2_draft_generator's pure formatting helper,
# NOT its monolith-specific system-instructions/steer wrapper (the
# planner/writer split has its own per-stage instructions).
# ─────────────────────────────────────────────────────────────────────────


def _build_brief_ctx(deck: dict[str, Any]) -> str:
    """Facts-first brief content block, mirroring wr2_draft_generator.
    _build_draft_prompt's own `body` assembly (wr2_draft_generator.py:
    920-934) — via `wr2_draft_generator._build_enriched_brief` (a pure
    formatting helper, zero side effects, safe to import) — WITHOUT that
    function's system-instructions/steer wrapper, which is specific to the
    single monolithic composition call this whole program exists to
    replace."""
    brief = deck.get("brief_json") or {}
    topic = deck.get("topic") or brief.get("article_title") or ""
    summary = brief.get("article_summary") or ""
    source_url = brief.get("source_url") or ""
    enrichment = brief.get("enrichment")
    live_reasons = brief.get("live_news_reasons")

    enriched_body = ""
    if enrichment:
        enriched_body = wr2dg._build_enriched_brief(enrichment, live_reasons)

    if summary.strip() and enriched_body:
        body = (
            "### Source article (the real event)\n"
            f"{summary[:3500]}\n\n"
            "### Supporting brief (citations, editorial take, practice notes)\n"
            f"{enriched_body}"
        )
    elif enriched_body:
        body = enriched_body
    else:
        body = summary[:3500]

    return f"Title: {topic}\n\nSource: {source_url or 'n/a'}\n\nContent:\n{body}"


def _liveness_tier_of(deck: dict[str, Any]) -> str:
    return wr2dg._normalise_liveness_tier((deck.get("brief_json") or {}).get("liveness_tier"))


def _register_of(deck: dict[str, Any]) -> str:
    return deck.get("register") or "analitico"


# ─────────────────────────────────────────────────────────────────────────
# call_fn factories — sanctioned OAuth CLI path only (never the banned
# Anthropic SDK), same pattern wr2_ir_shadow_replay._make_call_fn uses,
# parametrized by model so planner/writer get their own pin
# (wr2_planner_writer.DEFAULT_PLANNER_MODEL / DEFAULT_WRITER_MODEL).
# ─────────────────────────────────────────────────────────────────────────


def _make_call_fn(model: str, endpoint_suffix: str) -> tuple[Callable[[str], str], dict[str, int]]:
    from backend.llm.claude_oauth_client import complete_async

    counter = {"n": 0}

    def call_fn(prompt: str) -> str:
        counter["n"] += 1

        async def _call() -> str:
            resp = await complete_async(
                prompt,
                model=model,
                timeout_s=300,
                endpoint=f"wr2_pw_shadow_{endpoint_suffix}",
            )
            return resp.text

        return asyncio.run(_call())

    return call_fn, counter


# ─────────────────────────────────────────────────────────────────────────
# --shadow: plan + write + pregate + family-resolution per deck
# ─────────────────────────────────────────────────────────────────────────


def _run_one(deck: dict[str, Any], *, recent_arcs: list[str], max_retries: int) -> dict[str, Any]:
    deck_id = deck.get("id")
    result: dict[str, Any] = {"id": deck_id, "topic": deck.get("topic")}

    try:
        brief_ctx = _build_brief_ctx(deck)
    except Exception as e:  # a malformed brief must not kill the run
        result.update({"status": "error", "error": f"brief-build failed: {e!r}"})
        return result

    liveness_tier = _liveness_tier_of(deck)
    register = _register_of(deck)

    planner_fn, planner_calls = _make_call_fn(pw.DEFAULT_PLANNER_MODEL, "planner")
    writer_fn, writer_calls = _make_call_fn(pw.DEFAULT_WRITER_MODEL, "writer")

    t0 = time.perf_counter()
    try:
        plan = pw.plan_deck(brief_ctx, liveness_tier, recent_arcs, planner_fn, max_retries=max_retries)
    except pw.PlanValidationExhausted as e:
        result.update({
            "status": "plan_exhausted",
            "error": str(e),
            "last_raw_text_head": e.last_raw_text[:2000],
            "calls_used": {"planner": planner_calls["n"], "writer": writer_calls["n"]},
            "wall_s": round(time.perf_counter() - t0, 1),
        })
        return result
    except Exception as e:  # per-deck try/except: one bad deck never kills the run
        result.update({
            "status": "error", "error": repr(e),
            "calls_used": {"planner": planner_calls["n"], "writer": writer_calls["n"]},
            "wall_s": round(time.perf_counter() - t0, 1),
        })
        return result

    ordered_slots = sorted(plan.slides, key=lambda s: s.slot_id)
    slides: list[ir.Slide] = []
    try:
        for slot in ordered_slots:
            siblings = [s.heading_intent for s in ordered_slots if s.slot_id != slot.slot_id]
            slide = pw.write_slot(brief_ctx, plan, slot, siblings, writer_fn, max_retries=max_retries)
            slides.append(slide)
    except pw.SlotWriteExhausted as e:
        result.update({
            "status": "slot_exhausted",
            "slot_id": e.slot_id,
            "error": str(e),
            "last_raw_text_head": e.last_raw_text[:2000],
            "plan": {"arc": plan.arc, "arc_reason": plan.arc_reason, "spine": plan.spine},
            "calls_used": {"planner": planner_calls["n"], "writer": writer_calls["n"]},
            "wall_s": round(time.perf_counter() - t0, 1),
        })
        return result
    except Exception as e:
        result.update({
            "status": "error", "error": repr(e),
            "plan": {"arc": plan.arc, "arc_reason": plan.arc_reason, "spine": plan.spine},
            "calls_used": {"planner": planner_calls["n"], "writer": writer_calls["n"]},
            "wall_s": round(time.perf_counter() - t0, 1),
        })
        return result

    try:
        deck_obj = ir.SlideDeck(register=register, slides=slides, spine=plan.spine, arc=plan.arc)
    except Exception as e:
        result.update({
            "status": "error", "error": f"SlideDeck assembly failed: {e!r}",
            "plan": {"arc": plan.arc, "arc_reason": plan.arc_reason, "spine": plan.spine},
            "calls_used": {"planner": planner_calls["n"], "writer": writer_calls["n"]},
            "wall_s": round(time.perf_counter() - t0, 1),
        })
        return result

    wall_s = round(time.perf_counter() - t0, 1)
    report = pg.pregate_typed(deck_obj, spine=deck_obj.spine)

    total = len(deck_obj.slides)
    resolved_ok = True
    for i, s in enumerate(deck_obj.slides, start=1):
        cdict = ir.to_composer_dict(s, index=i, total=total)
        resolved = map_slide_to_family(cdict, i, total)
        expected = ir.SLIDE_KIND_TO_FAMILY[s.kind]
        if resolved != expected:
            resolved_ok = False

    result.update({
        "status": "ok",
        "plan": {
            "arc": plan.arc,
            "arc_reason": plan.arc_reason,
            "spine": plan.spine,
            "slot_kinds": [s.kind for s in deck_obj.slides],
        },
        "register": deck_obj.register,
        "slide_count": total,
        "pregate_verdict": report.verdict,
        "pregate_checks": [c.to_dict() for c in report.checks],
        "family_resolution_ok": resolved_ok,
        "calls_used": {
            "planner": planner_calls["n"], "writer": writer_calls["n"],
            "total": planner_calls["n"] + writer_calls["n"],
        },
        "wall_s": wall_s,
    })
    return result


def _aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(results)
    ok = [r for r in results if r.get("status") == "ok"]

    arc_distribution = Counter(r["plan"]["arc"] for r in ok)
    kind_histogram: Counter = Counter()
    for r in ok:
        kind_histogram.update(r["plan"]["slot_kinds"])

    spine_echo_judged = 0
    spine_echo_pass = 0
    pregate_pass = 0
    for r in ok:
        if r.get("pregate_verdict") == "PASS":
            pregate_pass += 1
        for c in r.get("pregate_checks", []):
            if c["check"] == "check_spine_echo" and c["verdict"] != "SKIP":
                spine_echo_judged += 1
                if c["verdict"] == "PASS":
                    spine_echo_pass += 1

    total_calls = sum(r["calls_used"]["total"] for r in ok)
    total_wall = sum(r["wall_s"] for r in ok)
    family_resolution_ok_count = sum(1 for r in ok if r.get("family_resolution_ok"))

    return {
        "n_decks": n,
        "n_ok": len(ok),
        "n_failed": n - len(ok),
        "arc_distribution": dict(arc_distribution),
        "kind_histogram": dict(kind_histogram),
        "spine_echo_pass_rate": round(spine_echo_pass / spine_echo_judged, 3) if spine_echo_judged else None,
        "pregate_pass_rate": round(pregate_pass / len(ok), 3) if ok else None,
        "family_resolution_ok_rate": round(family_resolution_ok_count / len(ok), 3) if ok else None,
        "avg_calls_per_deck": round(total_calls / len(ok), 2) if ok else None,
        "avg_wall_secs": round(total_wall / len(ok), 2) if ok else None,
        "per_deck": results,
    }


def _write_metrics(out_path: Path, results: list[dict[str, Any]]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(_aggregate(results), indent=2, ensure_ascii=False), encoding="utf-8")


def _run_shadow(fixture_path: Path, out_path: Path, *, limit: int, sleep_s: float, max_retries: int) -> None:
    decks: list[dict[str, Any]] = json.loads(fixture_path.read_text(encoding="utf-8"))
    sampled = _stratified_sample(decks, limit)

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

    # In-run recent-arcs, newest-first, capped at 5 — an honest stand-in for
    # the not-yet-built Creative Ledger (spec §Mossa-D): this harness's own
    # memory resets between invocations, unlike a real Postgres-backed
    # ledger would.
    recent_arcs: list[str] = []
    for r in reversed(results):
        if r.get("status") == "ok":
            recent_arcs.append(r["plan"]["arc"])
        if len(recent_arcs) >= 5:
            break

    for i, deck in enumerate(sampled):
        if deck.get("id") in done_ids:
            continue
        logger.info(
            "[%d/%d] planner/writer for deck %s (%s) [domain=%s]",
            i + 1, len(sampled), deck.get("id"), str(deck.get("topic", ""))[:60], _infer_domain(deck),
        )
        try:
            r = _run_one(deck, recent_arcs=recent_arcs, max_retries=max_retries)
        except Exception as e:  # belt-and-suspenders at the outer loop too
            r = {"id": deck.get("id"), "topic": deck.get("topic"), "status": "error", "error": repr(e)}
        results.append(r)
        if r.get("status") == "ok":
            recent_arcs = [r["plan"]["arc"]] + recent_arcs[:4]
        _write_metrics(out_path, results)
        if i < len(sampled) - 1:
            time.sleep(sleep_s)

    _write_metrics(out_path, results)
    logger.info("Shadow run complete: %d decks -> %s", len(results), out_path)


# ─────────────────────────────────────────────────────────────────────────
# --render-one: best-effort render of ONE produced deck via the REAL
# renderer path — fails honestly if Playwright/the composer aren't usable.
# ─────────────────────────────────────────────────────────────────────────


def _render_one(fixture_path: Path, deck_id: str, out_dir: Path, *, max_retries: int) -> dict[str, Any]:
    decks: list[dict[str, Any]] = json.loads(fixture_path.read_text(encoding="utf-8"))
    deck = next(
        (d for d in decks if d.get("id") == deck_id or str(d.get("id", "")).startswith(deck_id)), None,
    )
    if deck is None:
        return {"status": "unavailable", "reason": f"deck_id {deck_id!r} not found in {fixture_path}"}

    try:
        from wr2_html_renderer.composer import compose_carousel
    except Exception as e:
        return {"status": "unavailable", "reason": f"composer.compose_carousel import failed: {e!r}"}

    try:
        import playwright.async_api  # noqa: F401
    except Exception as e:
        return {"status": "unavailable", "reason": f"playwright not importable: {e!r}"}

    brief_ctx = _build_brief_ctx(deck)
    liveness_tier = _liveness_tier_of(deck)
    register = _register_of(deck)

    planner_fn, _ = _make_call_fn(pw.DEFAULT_PLANNER_MODEL, "planner")
    writer_fn, _ = _make_call_fn(pw.DEFAULT_WRITER_MODEL, "writer")

    try:
        plan = pw.plan_deck(brief_ctx, liveness_tier, [], planner_fn, max_retries=max_retries)
        ordered_slots = sorted(plan.slides, key=lambda s: s.slot_id)
        slides: list[ir.Slide] = []
        for slot in ordered_slots:
            siblings = [s.heading_intent for s in ordered_slots if s.slot_id != slot.slot_id]
            slides.append(pw.write_slot(brief_ctx, plan, slot, siblings, writer_fn, max_retries=max_retries))
        deck_obj = ir.SlideDeck(register=register, slides=slides, spine=plan.spine, arc=plan.arc)
    except (pw.PlanValidationExhausted, pw.SlotWriteExhausted) as e:
        return {"status": "produce_failed", "reason": str(e)}

    total = len(deck_obj.slides)
    composer_slides = [ir.to_composer_dict(s, index=i, total=total) for i, s in enumerate(deck_obj.slides, start=1)]

    async def _do_render() -> Any:
        return await compose_carousel(composer_slides, out_dir, topic=deck.get("topic") or "")

    try:
        render_result = asyncio.run(_do_render())
    except Exception as e:
        return {"status": "render_failed", "reason": repr(e)}

    return {
        "status": "ok",
        "deck_id": deck["id"],
        "arc": deck_obj.arc,
        "spine": deck_obj.spine,
        "slides_rendered": render_result.slides_rendered,
        "heroes_expected": render_result.heroes_expected,
        "heroes_placed": render_result.heroes_placed,
        "failures": render_result.failures,
        "png_paths": [str(p) for p in render_result.png_paths],
        "note": (
            "best-effort: this harness generates zero images (image_prompt -> image_url is out of "
            "scope), so hero slides are EXPECTED to show a download/placement failure above — that "
            "is not a render-pipeline bug."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--shadow", action="store_true", help="Run the planner/writer split over sampled historical briefs")
    mode.add_argument("--render-one", metavar="DECK_ID", help="Best-effort render ONE produced deck to PNGs")
    parser.add_argument("--fixture", type=Path, help="Input fixture JSON (id/topic/register/brief_json shape)")
    parser.add_argument("--out", type=Path, help="Output path (--shadow: metrics JSON; --render-one: PNG output dir)")
    parser.add_argument("--limit", type=int, default=12, help="Decks to sample, stratified by (inferred) domain (--shadow only)")
    parser.add_argument("--sleep", type=float, default=1.0, help="Seconds between decks in --shadow")
    parser.add_argument("--max-retries", type=int, default=3, help="Validate-and-retry attempts per planner/writer call")
    args = parser.parse_args()

    if args.shadow:
        if not args.fixture:
            parser.error("--shadow requires --fixture <fixture.json>")
        if not args.out:
            parser.error("--shadow requires --out <report.json>")
        _run_shadow(args.fixture, args.out, limit=args.limit, sleep_s=args.sleep, max_retries=args.max_retries)
        return 0

    if not args.fixture:
        parser.error("--render-one requires --fixture <fixture.json>")
    if not args.out:
        parser.error("--render-one requires --out <output dir>")
    result = _render_one(args.fixture, args.render_one, args.out, max_retries=args.max_retries)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
