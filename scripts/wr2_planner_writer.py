#!/usr/bin/env python3
"""wr2_planner_writer.py — Planner/Writer split (WR2 editorial-intelligence
Phase 3, Mossa B — "il cuore anti-disco-rotto").

ADDITIVE / SHADOW ONLY. Nothing in `wr2_draft_generator.py` or
`scripts/wr2_html_renderer/composer.py` imports this module, and this PR
does not modify either file — production behavior is byte-identical
before/after. This module is exercised by `wr2_pw_shadow.py` against
historical decks. Wiring it into the live autonomous pipeline is a later,
separately-gated cutover (spec §3 rollout step 3: "Planner/Writer dual-run
(B) — shadow accanto al monolite, poi cutover"), not this PR.

Implements Mossa B of the ratified spec:
    .claude/skills/wr2/_research/2026-07-21-editorial-intelligence-design.md
    §2 "Planner -> Writer: separare DECIDERE da SCRIVERE".

Design (spec §2 Mossa B, as corrected by the two independent red-team
grades recorded in §7 of that spec):

  - The monolith becomes TWO stages, the STORM/gpt-researcher shape:
    `plan_deck` (the "editor") emits a zero-prose `wr2_carousel_ir.DeckPlan`
    — spine, arc, one role+kind+heading_intent per slot, nothing more.
    `write_slot` (the "redattore") fills ONE slot's actual copy from that
    locked plan.

  - CHI PROPONE != CHI DISPONE (red-team correction, Kimi objection #1):
    `build_arc_priors` is CODE — it only PROPOSES soft weights (a cooldown
    penalty for recently-used arcs + a mild liveness-tier boost). It NEVER
    zeroes a weight (no hard mask on arc is a non-negotiable ratified design
    rule) and it never picks the arc itself. The planner-LLM DISPOSES —
    chooses the arc FROM THE CONTENT within those soft priors, and a
    content-justified repeat is logged via `DeckPlan.arc_reason`, not
    blocked. Hard masks are legitimate only on SURFACE axes (palette,
    kicker, subhead-pattern, register) — never on arc; this module does not
    implement surface-axis masking (out of scope for Mossa B itself, that
    is Mossa D's Creative Ledger), it only refuses to let arc selection be
    coded as a hard choice.

  - Voice continuity without a full rewrite hazard (red-team correction,
    Kimi objection #2): a STORM-strict slot-blind writer ("nessuno possiede
    la continuità di voce") reads monotone even with varied layouts.
    `write_slot` receives the SIBLING slots' `heading_intent`s (never their
    copy) so the writer has enough to build ritmo/callback/escalation
    without the hazard of rewriting a sister slide it never validated
    against its own retry loop.

  - Kind-preservation is a HARD rule, mirroring `wr2_carousel_ir.py`'s own
    precedent (`IRValidationExhausted`'s docstring: "There is no fallback
    here that silently coerces ... that would re-collapse onto the same 4
    auto-reachable layouts"): a writer response whose `kind` disagrees with
    the plan's locked `SlotPlan.kind` is a retry-worthy failure, NEVER
    silently accepted or silently coerced. `SlotWriteExhausted` is raised at
    retry-exhaustion — same shape as `wr2_carousel_ir.IRValidationExhausted`
    (last_raw_text/last_error), plus `slot_id` for per-slot diagnosis.

Pure logic + an injected `call_fn` per stage (`planner_fn`/`writer_fn`),
mirroring `wr2_carousel_ir.generate_slides_typed`'s own discipline: this
module never itself shells out to the `claude` CLI or touches the network —
zero I/O/DB/network side effects at import time or call time, so the unit
tests need nothing but a plain Python fake for each `call_fn`. The actual
OAuth-CLI wiring (which model per stage, `DEFAULT_PLANNER_MODEL` /
`DEFAULT_WRITER_MODEL` below) lives in the caller — `wr2_pw_shadow.py`
wraps `backend.llm.claude_oauth_client.complete_async`, the same sanctioned
path `wr2_ir_shadow_replay.py` already uses (never the banned Anthropic
SDK).
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Callable

from pydantic import ValidationError

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import wr2_carousel_ir as ir  # noqa: E402

logger = logging.getLogger("wr2.planner_writer")

# The 9x-cost mitigation (spec §5 sizing): the planner needs JUDGMENT (arc
# selection FROM content, spine authorship) — pin it to the SAME model
# production's single monolithic call already uses
# (wr2_draft_generator.claude_compose_slides, wr2_draft_generator.py:1091).
# Writers fill STRUCTURE against an already-locked plan — a materially
# cheaper/faster model is sufficient there. Named constants only; this
# module makes no network call itself — the caller (wr2_pw_shadow.py) reads
# these to build its `planner_fn`/`writer_fn` closures, exactly how
# `wr2_ir_shadow_replay._COMPOSE_MODEL` is consumed by that script's own
# `_make_call_fn`.
DEFAULT_PLANNER_MODEL = "claude-opus-4-7"
DEFAULT_WRITER_MODEL = "claude-sonnet-5"

# ─────────────────────────────────────────────────────────────────────────
# Exceptions — same shape as wr2_carousel_ir.IRValidationExhausted
# (last_raw_text/last_error), so a caller's try/except can handle all three
# retry-exhaustion classes (IR / plan / slot) uniformly if it wants to.
# ─────────────────────────────────────────────────────────────────────────


class PlanValidationExhausted(RuntimeError):
    """Raised when `plan_deck` exhausts max_retries without a valid
    DeckPlan. The CALLER decides what happens next (park the whole deck —
    there is no partial-plan fallback, a deck cannot be half-planned)."""

    def __init__(self, message: str, *, last_raw_text: str, last_error: str):
        super().__init__(message)
        self.last_raw_text = last_raw_text
        self.last_error = last_error


class SlotWriteExhausted(RuntimeError):
    """Raised when `write_slot` exhausts max_retries without a valid,
    kind-matching Slide for its slot. Carries `slot_id` (in addition to the
    IRValidationExhausted-shaped last_raw_text/last_error) so a caller
    driving multiple slots can report exactly which one failed. The CALLER
    decides what happens next — this module has NO kind-collapsing fallback
    (spec §2 hard rule, mirrored from wr2_carousel_ir.py's own precedent)."""

    def __init__(self, message: str, *, slot_id: int, last_raw_text: str, last_error: str):
        super().__init__(message)
        self.slot_id = slot_id
        self.last_raw_text = last_raw_text
        self.last_error = last_error


# ─────────────────────────────────────────────────────────────────────────
# build_arc_priors — CODE PROPOSES, planner-LLM DISPOSES (spec §2, Kimi #1)
# ─────────────────────────────────────────────────────────────────────────

# Only the 3 most-recently-used arcs carry a cooldown penalty; older history
# is treated as fully cooled off. Decaying by recency (most recent = harshest
# penalty) rather than a flat penalty per occurrence — a slate used 3 decks
# ago should weigh less against reselection than one used yesterday.
_COOLDOWN_PENALTY_BY_RECENCY: tuple[float, ...] = (0.55, 0.35, 0.20)
_BASE_WEIGHT = 1.0
# NEVER zero — spec §2 hard rule: "Maschere HARD solo sugli assi di
# SUPERFICIE ... Mai una maschera hard che forzi un arco sbagliato". A floor
# well above zero keeps a recently-used arc SELECTABLE (soft-discouraged,
# never forbidden) even after a full 3-slot cooldown stack.
_MIN_WEIGHT = 0.15
_TIER_BOOST = 0.35

# Mild tier-appropriate boost (spec §Mossa-E: "Breaking -> arco stretto 5-6;
# evergreen -> arco ricco 9. È QUESTO che fa 'adattare al momento e al
# tema'"). `developing` and unknown/"" tiers get no boost — deliberately
# neutral rather than guessing a preference the spec never states.
_TIER_PREFERRED_ARCS: dict[str, tuple[str, ...]] = {
    "breaking": ("news_alert", "deadline"),
    "evergreen": ("worked_example", "explainer"),
}


def build_arc_priors(recent_arcs: list[str], liveness_tier: str | None) -> dict[str, float]:
    """Soft weights over the 7 ratified arcs (`wr2_carousel_ir.ARCS`, spec
    §8) — a cooldown PENALTY (never a mask) for recently-used arcs, plus a
    mild tier-appropriate boost. `recent_arcs` is read newest-first (index 0
    = most recently used), matching the Creative Ledger's own lookback
    ordering (spec §Mossa-D). Cold-start (`recent_arcs == []`) with no tier
    boost in play returns an EXACTLY uniform dict — no history, no
    preference. A weight never reaches 0.0: this function only proposes: the
    planner-LLM disposes the arc from the content (spec §2, Kimi red-team
    objection #1 — CHI PROPONE != CHI DISPONE)."""
    weights: dict[str, float] = {arc: _BASE_WEIGHT for arc in ir.ARCS}

    seen: set[str] = set()
    for i, arc in enumerate(recent_arcs):
        if arc not in weights or arc in seen:
            continue  # unknown arc string, or an older repeat of one already penalized
        seen.add(arc)
        idx = i if i < len(_COOLDOWN_PENALTY_BY_RECENCY) else len(_COOLDOWN_PENALTY_BY_RECENCY) - 1
        penalty = _COOLDOWN_PENALTY_BY_RECENCY[idx]
        weights[arc] = max(_MIN_WEIGHT, weights[arc] - penalty)

    tier = (liveness_tier or "").strip().lower()
    for arc in _TIER_PREFERRED_ARCS.get(tier, ()):
        if arc in weights:
            weights[arc] += _TIER_BOOST

    return weights


# ─────────────────────────────────────────────────────────────────────────
# Shared retry-context helper (reask pattern, ported from
# wr2_carousel_ir.generate_slides_typed's own retry loop — see that
# function's docstring for the instructor provenance) — used by both
# plan_deck and write_slot below so the two retry loops build their next
# attempt's context identically.
# ─────────────────────────────────────────────────────────────────────────


def _retry_ctx(prompt: str, err: Exception, raw: str) -> str:
    return (
        f"{prompt}\n\n"
        "Your previous attempt failed validation.\n"
        f"Validation errors found:\n{err}\n"
        "Recall the schema and fix the errors found in the following attempt:\n"
        f"{raw}"
    )


# ─────────────────────────────────────────────────────────────────────────
# plan_deck
# ─────────────────────────────────────────────────────────────────────────

_PLANNER_SLIDE_COUNT_GUIDANCE: dict[str, str] = {
    "breaking": "5-6 slides total (tight — this is breaking news)",
    "developing": "6-8 slides total",
    "evergreen": "8-9 slides total (rich — this is evergreen reference material)",
}
_DEFAULT_SLIDE_COUNT_GUIDANCE = "6-8 slides total"

_PLANNER_KIND_LIST = ", ".join(f"{k}" for k in ir.SLIDE_KIND_TO_FAMILY)


def _render_arc_library(priors: dict[str, float]) -> str:
    lines = []
    for arc_id, roles in ir.ARCS.items():
        weight = priors.get(arc_id, _BASE_WEIGHT)
        lines.append(f"  - {arc_id}  (soft prior weight {weight:.2f}): {' -> '.join(roles)}")
    return "\n".join(lines)


def _render_cooldown_guidance(recent_arcs: list[str]) -> str:
    recent_valid = [a for a in recent_arcs if a in ir.ARCS]
    if not recent_valid:
        return (
            "COOLDOWN — no recent-arc history yet (cold start): all 7 arcs above carry the same "
            "soft prior weight. Pick freely on content merit alone."
        )
    recent_str = ", ".join(recent_valid[:3])
    return (
        f"COOLDOWN — recently used (most recent first): {recent_str}. Their soft prior weight "
        "above is already lower for this reason (never zero — you are never FORBIDDEN from "
        "picking one). Prefer a DIFFERENT arc UNLESS the content genuinely demands one of these. "
        "A content-justified repeat is allowed: if you pick a recently-used arc anyway, say "
        "EXACTLY why in `arc_reason` (e.g. a genuinely breaking week — a PMK/Omnibus cascade — can "
        "justify news_alert two days running; that is a JUSTIFIED repeat, logged as such, not a "
        "violation)."
    )


def _build_planner_prompt(
    brief_ctx: str,
    liveness_tier: str | None,
    recent_arcs: list[str],
    priors: dict[str, float],
) -> str:
    tier = (liveness_tier or "").strip().lower()
    count_guidance = _PLANNER_SLIDE_COUNT_GUIDANCE.get(tier, _DEFAULT_SLIDE_COUNT_GUIDANCE)
    arc_library = _render_arc_library(priors)
    cooldown = _render_cooldown_guidance(recent_arcs)

    return f"""You are the PLANNER for a Bali Zero Instagram carousel — the editor, not the writer.

Your ONLY job is to decide the deck's SHAPE. ZERO PROSE: every field below is a plan, not copy —
a separate writer stage fills the actual words afterward, one slot at a time, from your plan.

BRIEF:
{brief_ctx}

LIVENESS TIER: {tier or "unknown"} -> target {count_guidance}

ARC LIBRARY — the 7 ratified arcs (spec §8), each a sequence of slide ROLES:
{arc_library}

{cooldown}

CHI PROPONE != CHI DISPONE: the soft prior weights above come from code — YOU choose the arc FROM
THE CONTENT, within them. A high-prior arc that does not fit this story is still the wrong choice;
a low-prior arc the content genuinely demands is still the right one. The weights nudge, they never
decide for you.

OUTPUT — ONE JSON object, exactly these fields, nothing else:
{{
  "spine": "<the ONE guiding idea for the whole deck — a sentence, not a headline; the closer will
            later be checked for echoing it>",
  "arc": "<exactly one of: {', '.join(ir.ARCS)}>",
  "arc_reason": "<one line: why THIS arc for THIS content — mandatory even when the arc has the
                 highest prior weight; if this is a content-justified REPEAT of a recently-used
                 arc, say so explicitly here>",
  "slides": [
    {{"slot_id": <int, 1-based, sequential>, "role": "<a role from the chosen arc's sequence
      above>", "kind": "<one of: {_PLANNER_KIND_LIST}>", "heading_intent": "<one line — the
      EDITORIAL DIRECTION for this slide's heading; NEVER the heading text itself, that is the
      writer's job>", "bullet_promise_n": <int or null — if this kind structurally delivers N
      items (fact_stack/status_list/triad/timeline/qa), the N it will deliver; null otherwise>,
      "hero": <bool>, "body": null}},
    ...
  ]
}}

HARD RULES:
  - `body` is ALWAYS null on every slide of the plan. ZERO PROSE — you are the editor, not the
    writer; slide copy is written later, per-slot, from this plan.
  - slot_id 1 is ALWAYS kind="cover", hero=true, role is the chosen arc's FIRST role (its hook).
  - The LAST slot is ALWAYS the closer (role "close"); its heading_intent should invoke
    "{ir.CLOSER_FRANCHISE_LABEL}" — the recurring closer slot-franchise (spec §8 item 3) — and
    should be positioned to echo the `spine` above.
  - Slide count matches the liveness guidance above.
  - No text outside the JSON object. No prose commentary. JSON only.

Produce the DeckPlan JSON NOW.
"""


def plan_deck(
    brief_ctx: str,
    liveness_tier: str | None,
    recent_arcs: list[str],
    call_fn: Callable[[str], str],
    max_retries: int = 3,
) -> ir.DeckPlan:
    """Run the planner stage: build the priors + prompt, validate-and-retry
    against `wr2_carousel_ir.DeckPlan` (reusing `extract_json_from_codeblock`,
    same instructor-derived reask pattern `generate_slides_typed` uses).
    Raises `PlanValidationExhausted` after `max_retries` failed attempts —
    the caller decides what happens next (there is no partial-plan
    fallback)."""
    priors = build_arc_priors(recent_arcs, liveness_tier)
    prompt = _build_planner_prompt(brief_ctx, liveness_tier, recent_arcs, priors)

    ctx = prompt
    last_raw = ""
    last_err: Exception | None = None
    for attempt in range(1, max_retries + 1):
        raw = call_fn(ctx)
        last_raw = raw
        json_str = ir.extract_json_from_codeblock(raw)
        try:
            plan = ir.DeckPlan.model_validate_json(json_str)
        except (ValidationError, json.JSONDecodeError) as e:
            last_err = e
            logger.warning("DeckPlan validation failed (attempt %d/%d): %s", attempt, max_retries, e)
            if attempt == max_retries:
                break
            ctx = _retry_ctx(prompt, e, raw)
            continue
        if attempt > 1:
            logger.info("DeckPlan validated on retry %d/%d", attempt, max_retries)
        return plan

    raise PlanValidationExhausted(
        f"DeckPlan validation exhausted after {max_retries} attempts: {last_err}",
        last_raw_text=last_raw,
        last_error=str(last_err) if last_err else "unknown",
    )


# ─────────────────────────────────────────────────────────────────────────
# write_slot
# ─────────────────────────────────────────────────────────────────────────

# kind -> the ONE typed model that kind validates against. Deliberately kept
# HERE (not in wr2_carousel_ir.py, whose kind->target mapping,
# SLIDE_KIND_TO_FAMILY, is kind->composer FAMILY, a different axis) — this
# module is the one place kind->CLASS matters, for write_slot's
# kind-preservation check + final validation.
_KIND_TO_MODEL: dict[str, type] = {
    "cover": ir.CoverSlide,
    "prose": ir.ProseSlide,
    "statement": ir.StatementSlide,
    "fact_stack": ir.FactStackSlide,
    "status_list": ir.StatusListSlide,
    "timeline": ir.TimelineSlide,
    "triad": ir.TriadSlide,
    "qa": ir.QaSlide,
    "stat": ir.StatSlide,
    "citation": ir.CitationSlide,
    "cta": ir.CtaSlide,
}
assert set(_KIND_TO_MODEL) == set(ir.SLIDE_KIND_TO_FAMILY), (
    "_KIND_TO_MODEL has drifted from wr2_carousel_ir.SLIDE_KIND_TO_FAMILY's keys"
)

# Per-kind field schema, ONE line each — duplicated (not imported) from the
# shape wr2_ir_shadow_replay._TYPED_SCHEMA_DIRECTIVE already documents,
# mirroring wr2_carousel_ir.py's own stated precedent for this module family
# ("Duplicated (not imported) on purpose: this module must stay importable
# standalone with ZERO I/O ... side effects" — wr2_carousel_ir.py's own
# docstring). Importing wr2_ir_shadow_replay here would pull in its asyncpg/
# backend.llm import surface at module load time, which this module's own
# zero-I/O discipline (stated in this file's module docstring) forbids.
_KIND_FIELD_SCHEMA: dict[str, str] = {
    "cover": 'headline (str, required), subhead (str), regulation_code (str), image_prompt (str)',
    "prose": 'headline (str, required), body (str, required), subhead (str)',
    "statement": 'statement (str, required) — a 3-15 word punch line, never a paragraph',
    "fact_stack": (
        'heading (str, required), facts (list[str], required, >=1 — each item is ONE fact line), '
        'take_label (str), take_line (str)'
    ),
    "status_list": (
        'heading (str, required), items (list[{label, value, status: "neutral"|"critical"|'
        '"positive"}], required, >=1)'
    ),
    "timeline": 'heading (str, required), steps (list[{date, label, current: bool}], required, >=1)',
    "triad": (
        'heading (str, required), items (list[{title, desc}], required, 2-6 items — e.g. '
        '"3 forces behind the rise")'
    ),
    "qa": 'pairs (list[{voice, line}], required, >=2 — first two entries are the two voices in the exchange)',
    "stat": 'value (str, required), unit (str), label (str), context (str)',
    "citation": 'claim (str, required), sources (list[{code, issuer, date, url, note}], required, >=1)',
    "cta": 'invite (str, required), trust_marker (str), reach (str)',
}
assert set(_KIND_FIELD_SCHEMA) == set(_KIND_TO_MODEL), (
    "_KIND_FIELD_SCHEMA has drifted from _KIND_TO_MODEL's keys"
)


def _build_writer_prompt(
    brief_ctx: str,
    plan: ir.DeckPlan,
    slot: ir.SlotPlan,
    sibling_intents: list[str],
) -> str:
    schema_line = _KIND_FIELD_SCHEMA[slot.kind]
    if sibling_intents:
        siblings_block = "\n".join(f"  - {intent}" for intent in sibling_intents)
    else:
        siblings_block = "  (none — this is the only slide in the deck)"

    bullet_line = ""
    if slot.bullet_promise_n is not None:
        bullet_line = (
            f"\n  bullet_promise_n: {slot.bullet_promise_n}  <- deliver EXACTLY this many items in "
            "this slide's list-bearing field; the planner already locked this count against the "
            "heading"
        )

    return f"""You are the WRITER for ONE slide of a Bali Zero Instagram carousel — the redattore,
not the editor. The plan below is LOCKED: fill the copy, never re-plan.

BRIEF:
{brief_ctx}

DECK SPINE (the guiding idea for the whole deck — your copy should serve it; the closer slide will
be checked for echoing it, so if YOU are the closer, echo it explicitly):
{plan.spine}

DECK ARC: {plan.arc}  (chosen because: {plan.arc_reason})

YOUR SLOT — LOCKED, do not change any of these:
  slot_id: {slot.slot_id}
  role: {slot.role}
  kind: {slot.kind}   <- your JSON response MUST have "kind": "{slot.kind}" — exactly this, never
                          a different kind
  heading_intent (the EDITORIAL DIRECTION for this slide's heading — write TO this, do not just
                   restate it verbatim as the heading): {slot.heading_intent}
  hero: {slot.hero}{bullet_line}

SIBLING SLIDES' heading_intent ONLY (for voice continuity — ritmo, callback, escalation across the
deck). You do NOT see their copy and must NEVER rewrite them, only play off the editorial direction
they represent:
{siblings_block}

OUTPUT — this kind's fields ONLY (plus "kind"):
  {schema_line}

Output ONE JSON object: {{"kind": "{slot.kind}", ...that kind's fields above, filled with real
content grounded in the brief above}}. No text outside the JSON object. No prose commentary.

Produce the slide JSON NOW.
"""


def write_slot(
    brief_ctx: str,
    plan: ir.DeckPlan,
    slot: ir.SlotPlan,
    sibling_intents: list[str],
    call_fn: Callable[[str], str],
    max_retries: int = 3,
) -> ir.Slide:
    """Run the writer stage for ONE slot: brief + locked plan frame (spine,
    arc, this slot's role/kind/heading_intent/bullet_promise_n) + sibling
    slots' heading_intents ONLY (never their copy) + the field schema for
    THIS kind only. Validates against the single kind-matching model
    (`_KIND_TO_MODEL[slot.kind]`) — a writer response whose own "kind" field
    disagrees with `slot.kind` is a retry-worthy failure, NEVER silently
    accepted as a different kind (kind-preserving hard rule, spec §2).
    Raises `SlotWriteExhausted` after `max_retries` failed attempts (bad
    JSON, wrong kind, or a schema-validation failure for the right kind)."""
    model_cls = _KIND_TO_MODEL.get(slot.kind)
    if model_cls is None:  # pragma: no cover — SlotPlan.kind is itself a Literal over these keys
        raise ValueError(f"write_slot: unknown plan kind {slot.kind!r}")

    prompt = _build_writer_prompt(brief_ctx, plan, slot, sibling_intents)

    ctx = prompt
    last_raw = ""
    last_err: Exception | None = None
    for attempt in range(1, max_retries + 1):
        raw = call_fn(ctx)
        last_raw = raw
        json_str = ir.extract_json_from_codeblock(raw)
        try:
            parsed = json.loads(json_str)
        except json.JSONDecodeError as e:
            last_err = e
            logger.warning(
                "write_slot(slot_id=%d) JSON parse failed (attempt %d/%d): %s",
                slot.slot_id, attempt, max_retries, e,
            )
            if attempt == max_retries:
                break
            ctx = _retry_ctx(prompt, e, raw)
            continue

        returned_kind = parsed.get("kind") if isinstance(parsed, dict) else None
        if returned_kind != slot.kind:
            last_err = ValueError(
                f"writer returned kind={returned_kind!r}, plan locked slot {slot.slot_id} to "
                f"kind={slot.kind!r} — kind-preserving hard rule (spec §2): never accept a "
                "different kind than planned"
            )
            logger.warning(
                "write_slot(slot_id=%d) kind mismatch (attempt %d/%d): %s",
                slot.slot_id, attempt, max_retries, last_err,
            )
            if attempt == max_retries:
                break
            ctx = _retry_ctx(prompt, last_err, raw)
            continue

        try:
            slide = model_cls.model_validate(parsed)
        except ValidationError as e:
            last_err = e
            logger.warning(
                "write_slot(slot_id=%d) schema validation failed (attempt %d/%d): %s",
                slot.slot_id, attempt, max_retries, e,
            )
            if attempt == max_retries:
                break
            ctx = _retry_ctx(prompt, e, raw)
            continue

        if attempt > 1:
            logger.info("write_slot(slot_id=%d) validated on retry %d/%d", slot.slot_id, attempt, max_retries)
        return slide

    raise SlotWriteExhausted(
        f"write_slot(slot_id={slot.slot_id}, kind={slot.kind}) exhausted after {max_retries} "
        f"attempts: {last_err}",
        slot_id=slot.slot_id,
        last_raw_text=last_raw,
        last_error=str(last_err) if last_err else "unknown",
    )


# ─────────────────────────────────────────────────────────────────────────
# produce_deck
# ─────────────────────────────────────────────────────────────────────────


def produce_deck(
    brief_ctx: str,
    register: str,
    liveness_tier: str | None,
    recent_arcs: list[str],
    planner_fn: Callable[[str], str],
    writer_fn: Callable[[str], str],
    max_retries: int = 3,
) -> ir.SlideDeck:
    """plan -> write each slot (sequential; parallelization is a caller
    concern per spec §2 — "Parallelizzabile per-slot" describes an option,
    not a requirement this function imposes) -> assemble a
    `wr2_carousel_ir.SlideDeck` with `spine`/`arc` set from the plan.

    `register` is passed straight through, NOT decided here: `DeckPlan`
    (spec §2) is exactly {spine, arc, arc_reason, slides} — zero-prose, no
    voice-register field — so register comes from the same upstream source
    production already resolves it from today (the deck's own
    `war_room_drafts.register` / the historical brief's own `register`, per
    the `ir_replay_fixture.json` shape `wr2_pw_shadow.py` reads).

    `planner_fn` is used for `plan_deck` (typically pinned to
    `DEFAULT_PLANNER_MODEL`); `writer_fn` is used for every `write_slot`
    call (typically pinned to `DEFAULT_WRITER_MODEL`) — the two-model split
    is the caller's wiring (see this module's docstring, "9x-cost
    mitigation"), not enforced here structurally beyond accepting two
    distinct callables.
    """
    plan = plan_deck(brief_ctx, liveness_tier, recent_arcs, planner_fn, max_retries=max_retries)

    ordered_slots = sorted(plan.slides, key=lambda s: s.slot_id)
    slides: list[ir.Slide] = []
    for slot in ordered_slots:
        sibling_intents = [s.heading_intent for s in ordered_slots if s.slot_id != slot.slot_id]
        slide = write_slot(brief_ctx, plan, slot, sibling_intents, writer_fn, max_retries=max_retries)
        slides.append(slide)

    return ir.SlideDeck(register=register, slides=slides, spine=plan.spine, arc=plan.arc)
