#!/usr/bin/env python3
"""wr2_carousel_ir.py — typed Carousel IR (WR2 editorial-intelligence Phase 1).

ADDITIVE / SHADOW ONLY. Nothing in `wr2_draft_generator.py` or
`scripts/wr2_html_renderer/composer.py` imports this module, and this PR does
not modify either file — production behavior is byte-identical before/after.
This module exists to be exercised by `wr2_ir_shadow_replay.py` against
historical decks. Wiring it into the live autonomous pipeline is Phase 3,
itself gated by the 4-LLM panel per CLAUDE.md §6 — not this PR.

Implements Mossa A of the ratified spec:
    .claude/skills/wr2/_research/2026-07-21-editorial-intelligence-design.md
    §2 "Carousel IR: la grammatica tipizzata delle slide" + §3 rollout step 1.

Design (spec §2, "VALIDAZIONE LENIENT-FIRST", red-team BLOCKER-1):
  - A pydantic v2 discriminated union `Slide` over 11 kinds: cover, prose,
    statement, fact_stack, status_list, timeline, triad, qa, stat, citation,
    cta. Discriminator = `kind` (a `Literal`).
  - STRICT validation is scoped to exactly two things: the `kind` tag itself
    (pydantic raises `union_tag_invalid` on an unknown tag), and the
    per-kind structurally-required field(s) — e.g. `fact_stack.facts` must
    be a non-empty list (an empty list is not "a fact stack"); `qa.pairs`
    needs >=2 entries (qa-dialogue is a fixed 2-voice layout downstream).
  - EVERY other scalar (headline/subhead/body/…) is LENIENT: coerced to
    `str`, truncated, defaulted — mirroring the tolerances
    `wr2_draft_generator._normalise_slides` already applies today
    (headline[:80], body[:500], subhead via a `_cap_subhead`-style
    word/char cap; see `_lenient_str`/`_cap_len`/`_cap_subhead` below,
    ported/mirrored from wr2_draft_generator.py:1386-1414,1441-1453). A
    strict union on every scalar risks a regen-spike that burns MAX-plan
    quota at shakeout for zero real gain — the *shape* (kind) is what must
    be right, not every character budget.
  - Kind-preservation is a HARD design rule (spec §2, Kimi red-team
    objection #3): at retry-exhaustion `IRValidationExhausted` is raised —
    the CALLER decides park, never this module. There is no fallback here
    that silently coerces a richly-shaped slide down to prose/statement
    just because validation failed; that would re-collapse onto the same 4
    auto-reachable layouts (spec §0.2) the whole design exists to escape.

`to_composer_dict()` projects a validated Slide into the EXACT dict shape
`scripts/wr2_html_renderer/composer.py` consumes for that layout family.
Field names were VERIFIED against the real skeleton `.md` files under
`skills/bali-zero-brand/layouts/` + composer.py's `_fill_placeholders` /
`_expand_each_blocks` / `_qa_dialogue_fields` (this session, 2026-07-21) —
NOT guessed from the spec's summary table, which uses simplified field
names ("label,value" for fact_stack; "q,a" for qa; "date,event,current" for
timeline) that do not match the real composer contract for several kinds.
See the per-branch comments in `to_composer_dict` for the corrections, with
composer.py line citations and two DISCOVERED GAPS (source-citation's
`{{title}}` and elegant-close's `trust_marker`/`reach`/`invite`/… are never
substituted by `_fill_placeholders` at all — verified by grep, zero hits).
"""
from __future__ import annotations

import json
import logging
import warnings
from typing import Annotated, Any, Callable, Literal, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
)

logger = logging.getLogger("wr2.carousel_ir")

# pydantic's ModelMetaclass inherits from abc.ABCMeta, which defines a
# `.register()` classmethod (virtual-subclass registration) — a field
# LITERALLY named "register" shadows it, and pydantic emits a class-
# definition-time UserWarning about it. Harmless (verified: the field
# validates/serializes correctly either way) and unavoidable here since
# "register" is the production JSON key (wr2_draft_generator._normalise_
# slides reads `parsed.get("register")` — the IR wrapper must match it
# verbatim). Scoped narrowly to SlideDeck's class body only.
warnings.filterwarnings(
    "ignore",
    message='Field name "register" in "SlideDeck" shadows an attribute',
    category=UserWarning,
)

# ─────────────────────────────────────────────────────────────────────────
# Lenient scalar helpers — mirror wr2_draft_generator._normalise_slides
# (wr2_draft_generator.py:1441-1453) and _cap_subhead (:1386-1414).
# Duplicated (not imported) on purpose: this module must stay importable
# standalone with ZERO I/O/DB/CLI side effects, so unit tests never need a
# database, a subprocess, or the wr2_draft_generator module's own import
# surface. wr2_ir_shadow_replay.py is the one place that DOES import
# wr2_draft_generator, for its prompt-assembly helpers.
# ─────────────────────────────────────────────────────────────────────────

_HEADLINE_MAX = 80
_BODY_MAX = 500
_IMAGE_PROMPT_MAX = 600
_SUBHEAD_MAX_WORDS = 6
_SUBHEAD_MAX_CHARS = 32

_VALID_TONES = frozenset({
    "rituale", "analitico", "ironico", "militante", "pedagogico", "poetico", "tecnico",
})

_VALID_STATUS_TOKENS = frozenset({"neutral", "critical", "positive"})


def _lenient_str(v: Any) -> str:
    """Coerce anything to a stripped str. Never raises."""
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    return str(v).strip()


def _cap_len(s: str, n: int) -> str:
    return s[:n]


def _cap_subhead(text: str, max_words: int = _SUBHEAD_MAX_WORDS, max_chars: int = _SUBHEAD_MAX_CHARS) -> str:
    """Port of wr2_draft_generator._cap_subhead (wr2_draft_generator.py:1386-1414):
    hard-cap to 1-6 words, then trim to a word boundary under max_chars. No
    ellipsis — a clean shorter kicker beats a truncated one."""
    words = text.strip().split()
    if not words:
        return ""
    capped = " ".join(words[:max_words])
    if len(capped) <= max_chars:
        return capped
    trimmed: list[str] = []
    length = 0
    for w in capped.split():
        extra = len(w) + (1 if trimmed else 0)
        if length + extra > max_chars:
            break
        trimmed.append(w)
        length += extra
    if not trimmed:
        trimmed = [capped.split()[0]]
    return " ".join(trimmed)


def _require_nonempty(v: str, field_name: str) -> str:
    """Post-coercion guard for fields this module treats as structurally
    required content (not just structurally-present keys): an empty string
    after lenient coercion is still a real content failure worth a retry,
    not a silently-accepted blank slide."""
    if not v:
        raise ValueError(f"{field_name} must be non-empty after coercion")
    return v


# ─────────────────────────────────────────────────────────────────────────
# 1. Slide kinds — discriminated union over 11 shapes
# ─────────────────────────────────────────────────────────────────────────


class CoverSlide(BaseModel):
    """→ cover-photo. Composer fields: headline, subhead(ing), optional
    regulation_code (constitution Art 9.3 hard rule — always slide 1)."""

    model_config = ConfigDict(extra="ignore")

    kind: Literal["cover"]
    headline: str
    subhead: str = ""
    regulation_code: str = ""
    image_prompt: str = ""

    @field_validator("headline", mode="before")
    @classmethod
    def _v_headline(cls, v: Any) -> str:
        return _require_nonempty(_cap_len(_lenient_str(v), _HEADLINE_MAX), "headline")

    @field_validator("subhead", mode="before")
    @classmethod
    def _v_subhead(cls, v: Any) -> str:
        return _cap_subhead(_lenient_str(v))

    @field_validator("regulation_code", mode="before")
    @classmethod
    def _v_regulation_code(cls, v: Any) -> str:
        return _lenient_str(v)

    @field_validator("image_prompt", mode="before")
    @classmethod
    def _v_image_prompt(cls, v: Any) -> str:
        # Mirrors wr2_draft_generator._normalise_slides' image_prompt[:600]
        # cap (wr2_draft_generator.py:1449).
        return _cap_len(_lenient_str(v), _IMAGE_PROMPT_MAX)


class ProseSlide(BaseModel):
    """→ editorial-text. Composer fields: headline, subhead(ing), body."""

    model_config = ConfigDict(extra="ignore")

    kind: Literal["prose"]
    headline: str
    body: str
    subhead: str = ""

    @field_validator("headline", mode="before")
    @classmethod
    def _v_headline(cls, v: Any) -> str:
        return _require_nonempty(_cap_len(_lenient_str(v), _HEADLINE_MAX), "headline")

    @field_validator("body", mode="before")
    @classmethod
    def _v_body(cls, v: Any) -> str:
        return _require_nonempty(_cap_len(_lenient_str(v), _BODY_MAX), "body")

    @field_validator("subhead", mode="before")
    @classmethod
    def _v_subhead(cls, v: Any) -> str:
        return _cap_subhead(_lenient_str(v))


class StatementSlide(BaseModel):
    """→ statement-bomb. Composer field: statement (falls back to
    headline/body if absent, but this kind IS the statement — required)."""

    model_config = ConfigDict(extra="ignore")

    kind: Literal["statement"]
    statement: str

    @field_validator("statement", mode="before")
    @classmethod
    def _v_statement(cls, v: Any) -> str:
        return _require_nonempty(_cap_len(_lenient_str(v), _HEADLINE_MAX), "statement")


class FactStackSlide(BaseModel):
    """→ evidence-carved. `facts` is a non-empty list of fact lines (spec §2
    code block: `facts: List[str]` — matches the REAL each-loop contract,
    `{{#each facts}}...{{this}}...{{/each}}`, verified against
    skills/bali-zero-brand/layouts/evidence-carved.md:115-120 +
    scripts/wr2_html_renderer/tests/test_each_block_render.py's own guilt
    case `{"facts": ["FACT ONE", "FACT TWO"]}`)."""

    model_config = ConfigDict(extra="ignore")

    kind: Literal["fact_stack"]
    heading: str
    facts: list[str] = Field(min_length=1)
    take_label: str = ""
    take_line: str = ""

    @field_validator("heading", mode="before")
    @classmethod
    def _v_heading(cls, v: Any) -> str:
        return _require_nonempty(_cap_len(_lenient_str(v), _HEADLINE_MAX), "heading")

    @field_validator("facts", mode="before")
    @classmethod
    def _v_facts(cls, v: Any) -> Any:
        if not isinstance(v, list):
            return v  # let pydantic raise its own type error
        return [_cap_len(_lenient_str(x), _BODY_MAX) for x in v]

    @field_validator("take_label", "take_line", mode="before")
    @classmethod
    def _v_take(cls, v: Any) -> str:
        return _lenient_str(v)


class StatusItem(BaseModel):
    """Row shape for dark-status-list's {{#each items}} — label/value/status,
    verified against layouts/dark-status-list.md:67-72. `status` drives the
    CSS class `status-{{status}}`; only 3 tokens have real styling."""

    model_config = ConfigDict(extra="ignore")

    label: str
    value: str
    status: Literal["neutral", "critical", "positive"] = "neutral"

    @field_validator("label", "value", mode="before")
    @classmethod
    def _v_scalars(cls, v: Any) -> str:
        return _lenient_str(v)

    @field_validator("status", mode="before")
    @classmethod
    def _v_status(cls, v: Any) -> str:
        s = _lenient_str(v).lower() or "neutral"
        if s not in _VALID_STATUS_TOKENS:
            logger.warning("StatusItem.status=%r not in %s — defaulting to 'neutral'", s, sorted(_VALID_STATUS_TOKENS))
            return "neutral"
        return s


class StatusListSlide(BaseModel):
    """→ dark-status-list. `items` non-empty (a status list with zero rows
    is not a status list)."""

    model_config = ConfigDict(extra="ignore")

    kind: Literal["status_list"]
    heading: str
    items: list[StatusItem] = Field(min_length=1)

    @field_validator("heading", mode="before")
    @classmethod
    def _v_heading(cls, v: Any) -> str:
        return _require_nonempty(_cap_len(_lenient_str(v), _HEADLINE_MAX), "heading")


class TimelineStep(BaseModel):
    """Row shape for timeline-pinboard's {{#each events}} — date/label(+accent),
    verified against layouts/timeline-pinboard.md:59-66. `current` is an
    IR-level editorial concept ("this is where we are now"); the projection
    derives the composer's `accent` token from it — see to_composer_dict."""

    model_config = ConfigDict(extra="ignore")

    date: str
    label: str
    current: bool = False

    @field_validator("date", "label", mode="before")
    @classmethod
    def _v_scalars(cls, v: Any) -> str:
        return _lenient_str(v)

    @field_validator("current", mode="before")
    @classmethod
    def _v_current(cls, v: Any) -> bool:
        if isinstance(v, str):
            return v.strip().lower() in {"true", "yes", "1", "current"}
        return bool(v)


class TimelineSlide(BaseModel):
    """→ timeline-pinboard. `steps` non-empty."""

    model_config = ConfigDict(extra="ignore")

    kind: Literal["timeline"]
    heading: str
    steps: list[TimelineStep] = Field(min_length=1)

    @field_validator("heading", mode="before")
    @classmethod
    def _v_heading(cls, v: Any) -> str:
        return _require_nonempty(_cap_len(_lenient_str(v), _HEADLINE_MAX), "heading")


class TriadItem(BaseModel):
    """Row shape for numbered-forces-list's {{#each items}} — label/value,
    verified against layouts/numbered-forces-list.md:68-76."""

    model_config = ConfigDict(extra="ignore")

    title: str
    desc: str

    @field_validator("title", mode="before")
    @classmethod
    def _v_title(cls, v: Any) -> str:
        return _lenient_str(v)

    @field_validator("desc", mode="before")
    @classmethod
    def _v_desc(cls, v: Any) -> str:
        return _cap_len(_lenient_str(v), _BODY_MAX)


class TriadSlide(BaseModel):
    """→ numbered-forces-list. `items` min 2 (a "forces" list of 1 is not a
    list) — NOT hard-locked to exactly 3 despite the name: the renderer's
    numeral-extraction (regex on the headline's leading integer) generalizes
    to any N, so an editorially-justified 2 or 4 is not a structural error.
    Capped at 6 (a sane display ceiling for this layout's numeral+item grid,
    not a hard composer limit)."""

    model_config = ConfigDict(extra="ignore")

    kind: Literal["triad"]
    heading: str
    items: list[TriadItem] = Field(min_length=2, max_length=6)

    @field_validator("heading", mode="before")
    @classmethod
    def _v_heading(cls, v: Any) -> str:
        return _require_nonempty(_cap_len(_lenient_str(v), _HEADLINE_MAX), "heading")


class QaPair(BaseModel):
    """Row shape for qa-dialogue — voice/line, verified against the pinned
    regression test scripts/wr2_html_renderer/tests/test_each_block_render.py
    (`{"voice": "INVESTOR", "line": "IS JAPAN VISA-FREE?"}`) and
    composer._qa_dialogue_fields (composer.py:1057-1074). NOT the spec
    table's simplified "q,a" field names."""

    model_config = ConfigDict(extra="ignore")

    voice: str
    line: str

    @field_validator("voice", mode="before")
    @classmethod
    def _v_voice(cls, v: Any) -> str:
        return _lenient_str(v)

    @field_validator("line", mode="before")
    @classmethod
    def _v_line(cls, v: Any) -> str:
        return _cap_len(_lenient_str(v), _BODY_MAX)


class QaSlide(BaseModel):
    """→ qa-dialogue. `pairs` min 2 (composer._qa_dialogue_fields only ever
    renders the first two, `for idx, key in ((0,"a"),(1,"b"))` —
    composer.py:1069 — a fixed 2-voice layout, not an N-turn dialogue; fewer
    than 2 pairs cannot fill both voices)."""

    model_config = ConfigDict(extra="ignore")

    kind: Literal["qa"]
    pairs: list[QaPair] = Field(min_length=2)


class StatSlide(BaseModel):
    """→ stat-card-hero. `value` required; `unit`/`label`/`context` lenient.
    Composer fields: heading (supports a "UNIT / VALUE" split,
    composer.py:1564-1566), subheading (label above), body (caption below
    the optional chart)."""

    model_config = ConfigDict(extra="ignore")

    kind: Literal["stat"]
    value: str
    unit: str = ""
    label: str = ""
    context: str = ""

    @field_validator("value", mode="before")
    @classmethod
    def _v_value(cls, v: Any) -> str:
        return _require_nonempty(_cap_len(_lenient_str(v), _HEADLINE_MAX), "value")

    @field_validator("unit", "label", mode="before")
    @classmethod
    def _v_short(cls, v: Any) -> str:
        return _cap_subhead(_lenient_str(v))

    @field_validator("context", mode="before")
    @classmethod
    def _v_context(cls, v: Any) -> str:
        return _cap_len(_lenient_str(v), _BODY_MAX)


class CitationSource(BaseModel):
    """Row shape for source-citation's {{#each citations}} — body(=code)/
    issuer/date/url/note, verified against layouts/source-citation.md:31-36.
    NOTE: the row's `body` key is the citation CODE text — unrelated to the
    slide-level `{{body}}` placeholder used by other families."""

    model_config = ConfigDict(extra="ignore")

    code: str
    issuer: str = ""
    date: str = ""
    url: str = ""
    note: str = ""

    @field_validator("code", mode="before")
    @classmethod
    def _v_code(cls, v: Any) -> str:
        return _lenient_str(v)

    @field_validator("issuer", "date", "url", "note", mode="before")
    @classmethod
    def _v_scalars(cls, v: Any) -> str:
        return _lenient_str(v)


class CitationSlide(BaseModel):
    """→ source-citation. `sources` non-empty. `claim` is required content
    (projects to the skeleton's top-level `{{title}}` — see the DISCOVERED
    GAP note in to_composer_dict: composer never actually substitutes
    {{title}}, verified by grep)."""

    model_config = ConfigDict(extra="ignore")

    kind: Literal["citation"]
    claim: str
    sources: list[CitationSource] = Field(min_length=1)

    @field_validator("claim", mode="before")
    @classmethod
    def _v_claim(cls, v: Any) -> str:
        return _require_nonempty(_cap_len(_lenient_str(v), _HEADLINE_MAX), "claim")


class CtaSlide(BaseModel):
    """→ elegant-close. `invite` required content (the core call-to-action
    line). See the DISCOVERED GAP note in to_composer_dict: NONE of this
    family's top-level fields (trust_marker/reach/invite/…) are ever
    substituted by composer._fill_placeholders today — verified by grep,
    zero hits for all of them."""

    model_config = ConfigDict(extra="ignore")

    kind: Literal["cta"]
    invite: str
    trust_marker: str = ""
    reach: str = ""

    @field_validator("invite", mode="before")
    @classmethod
    def _v_invite(cls, v: Any) -> str:
        return _require_nonempty(_cap_len(_lenient_str(v), _BODY_MAX), "invite")

    @field_validator("trust_marker", "reach", mode="before")
    @classmethod
    def _v_scalars(cls, v: Any) -> str:
        return _cap_subhead(_lenient_str(v))


Slide = Annotated[
    Union[
        CoverSlide,
        ProseSlide,
        StatementSlide,
        FactStackSlide,
        StatusListSlide,
        TimelineSlide,
        TriadSlide,
        QaSlide,
        StatSlide,
        CitationSlide,
        CtaSlide,
    ],
    Field(discriminator="kind"),
]

SlideListAdapter: TypeAdapter[list[Slide]] = TypeAdapter(list[Slide])

# kind (string) -> composer layout_family (string). All 11 targets are in
# composer.RENDERABLE_FAMILIES (composer.py:51-67) — verified this session.
SLIDE_KIND_TO_FAMILY: dict[str, str] = {
    "cover": "cover-photo",
    "prose": "editorial-text",
    "statement": "statement-bomb",
    "fact_stack": "evidence-carved",
    "status_list": "dark-status-list",
    "timeline": "timeline-pinboard",
    "triad": "numbered-forces-list",
    "qa": "qa-dialogue",
    "stat": "stat-card-hero",
    "citation": "source-citation",
    "cta": "elegant-close",
}


class SlideDeck(BaseModel):
    """Top-level wrapper — mirrors the production JSON shape
    `{"register": ..., "slides": [...]}` (wr2_draft_generator._normalise_slides
    reads `parsed.get("register")` / `parsed.get("slides")`)."""

    model_config = ConfigDict(extra="ignore")

    register: str
    slides: list[Slide]

    @field_validator("register", mode="before")
    @classmethod
    def _v_register(cls, v: Any) -> str:
        # Deliberately STRICT — the one deck-level field this module does NOT
        # treat leniently, mirroring wr2_draft_generator._normalise_slides'
        # own choice (wr2_draft_generator.py:1418-1422, hard ValueError on an
        # invalid register). register drives voice/tone for the WHOLE deck;
        # silently defaulting it risks a content/voice mismatch, which is a
        # worse failure mode than one extra retry.
        s = _lenient_str(v).lower()
        if s not in _VALID_TONES:
            raise ValueError(f"invalid register={s!r} (allowed: {sorted(_VALID_TONES)})")
        return s


# ─────────────────────────────────────────────────────────────────────────
# 2. extract_json_from_codeblock — ported VERBATIM from instructor v2
#    (instructor/v2/core/json.py, MIT license, github.com/567-labs/instructor)
#    via .claude/skills/wr2/_research/2026-07-21-oss-code-reading-typed-
#    pydantic-instructor.md §5 (this session re-verified the port against
#    that evidence file's own copy, byte-for-byte identical algorithm).
#    Balanced-brace/bracket scanner: walks the text, tracks string/escape
#    state so braces INSIDE quoted strings don't confuse the stack, and
#    returns the LAST valid top-level JSON span found (a model's raw stdout
#    often has prose before/after the JSON, or a fenced ```json block).
# ─────────────────────────────────────────────────────────────────────────


def extract_json_from_codeblock(content: str) -> str:
    candidates: list[str] = []
    search_index = 0
    while search_index < len(content):
        start_index = next(
            (i for i in range(search_index, len(content)) if content[i] in "{["), None
        )
        if start_index is None:
            break
        start_char = content[start_index]
        end_stack = ["}" if start_char == "{" else "]"]
        in_string = False
        escape_next = False
        candidate_found = False
        for end_index in range(start_index + 1, len(content)):
            char = content[end_index]
            if escape_next:
                escape_next = False
            elif char == "\\" and in_string:
                escape_next = True
            elif char == '"':
                in_string = not in_string
            if in_string:
                continue
            if char in "{[":
                end_stack.append("}" if char == "{" else "]")
                continue
            if end_stack and char == end_stack[-1]:
                end_stack.pop()
                if not end_stack:
                    candidate = content[start_index : end_index + 1]
                    try:
                        json.loads(candidate)
                    except Exception:
                        break
                    candidates.append(candidate)
                    search_index = end_index + 1
                    candidate_found = True
                    break
        if not candidate_found:
            search_index = start_index + 1
    return candidates[-1] if candidates else content


# ─────────────────────────────────────────────────────────────────────────
# 3. validate + retry loop
# ─────────────────────────────────────────────────────────────────────────


class IRValidationExhausted(RuntimeError):
    """Raised when max_retries is exhausted without a valid SlideDeck.

    The CALLER decides what to do next (park the deck, fall back to a
    kind-preserving fill, …) — this module never silently coerces a failed
    validation into a simpler kind (spec §2, Kimi objection #3: "i
    kind-fallback sono sempre i semplici -> ri-collasso sui 4 layout")."""

    def __init__(self, message: str, *, last_raw_text: str, last_error: str):
        super().__init__(message)
        self.last_raw_text = last_raw_text
        self.last_error = last_error


def validate_slides(json_str: str) -> SlideDeck:
    """Validate a raw JSON string against SlideDeck. Raises ValidationError /
    json.JSONDecodeError on failure — callers wanting the retry loop should
    use generate_slides_typed instead of calling this directly."""
    return SlideDeck.model_validate_json(json_str)


def generate_slides_typed(
    prompt: str,
    call_fn: Callable[[str], str],
    max_retries: int = 3,
) -> SlideDeck:
    """Validate-and-retry loop against `call_fn` (sync text-in/text-out).

    `call_fn` is INJECTED so this module never itself shells out to the
    `claude` CLI or touches the network — that responsibility stays with the
    caller (wr2_ir_shadow_replay.py wraps backend.llm.claude_oauth_client.
    complete_async). This keeps wr2_carousel_ir.py import-safe with zero
    I/O/DB/network side effects: a plain Python fake for `call_fn` is all
    the retry-loop unit test needs.

    Reask pattern ported from instructor's AnthropicJSONHandler.handle_reask
    (see the OSS evidence file §2c / §5), adapted to plain text: on failure
    the next prompt = original prompt + the validation errors + the failed
    raw output, so the model can see exactly what it got wrong.

    Raises IRValidationExhausted after `max_retries` failed attempts.
    """
    ctx = prompt
    last_raw = ""
    last_err: Exception | None = None
    for attempt in range(1, max_retries + 1):
        raw = call_fn(ctx)
        last_raw = raw
        json_str = extract_json_from_codeblock(raw)
        try:
            deck = validate_slides(json_str)
        except (ValidationError, json.JSONDecodeError) as e:
            last_err = e
            logger.warning(
                "Carousel IR validation failed (attempt %d/%d): %s", attempt, max_retries, e,
            )
            if attempt == max_retries:
                break
            ctx = (
                f"{prompt}\n\n"
                "Your previous attempt failed validation.\n"
                f"Validation errors found:\n{e}\n"
                "Recall the schema and fix the errors found in the following attempt:\n"
                f"{raw}"
            )
            continue
        if attempt > 1:
            logger.info("Carousel IR validated on retry %d/%d", attempt, max_retries)
        return deck
    raise IRValidationExhausted(
        f"Carousel IR validation exhausted after {max_retries} attempts: {last_err}",
        last_raw_text=last_raw,
        last_error=str(last_err) if last_err else "unknown",
    )


# ─────────────────────────────────────────────────────────────────────────
# 4. to_composer_dict — projection to the composer-compatible dict shape
# ─────────────────────────────────────────────────────────────────────────


def to_composer_dict(slide: Slide, *, index: int, total: int) -> dict[str, Any]:
    """Project a validated typed Slide into the exact dict shape
    `scripts/wr2_html_renderer/composer.py` consumes for its layout family.

    Sets `layout_family` EXPLICITLY — composer.map_slide_to_family honours
    an explicit pin before any auto-routing heuristic (composer.py:143-145,
    `explicit = (slide.get("layout_family") or "").strip(); if explicit in
    RENDERABLE_FAMILIES: return explicit`), so this projection is immune to
    the auto-router's 4-family collapse (spec §0.2) regardless of what the
    IR's `kind` maps to.
    """
    base: dict[str, Any] = {
        "slide_number": index,
        "is_cover": False,
        "is_hero_image": False,
    }

    if isinstance(slide, CoverSlide):
        base.update({
            "layout_family": "cover-photo",
            "is_cover": True,
            "is_hero_image": True,
            "headline": slide.headline,
            "subhead": slide.subhead,
            "image_prompt": slide.image_prompt,
        })
        if slide.regulation_code:
            base["regulation_code"] = slide.regulation_code
        return base

    if isinstance(slide, ProseSlide):
        base.update({
            "layout_family": "editorial-text",
            "headline": slide.headline,
            "subhead": slide.subhead,
            "body": slide.body,
        })
        return base

    if isinstance(slide, StatementSlide):
        base.update({
            "layout_family": "statement-bomb",
            "statement": slide.statement,
        })
        return base

    if isinstance(slide, FactStackSlide):
        # evidence-carved's {{#each facts}} wants §-numbered rows: dict rows
        # {"idx": N, "this": text} render "§N  text" (verified against
        # skills/bali-zero-brand/layouts/evidence-carved.md:115-120 +
        # composer._expand_each_blocks's dict-row branch). A plain
        # scalar-string row ALSO binds {{this}}, but leaves the §-marker
        # BLANK — {{idx}} is only ever populated from a dict-row key, never
        # auto-enumerated by the composer itself — so this projection
        # upgrades to the numbered dict-row shape rather than the bare
        # strings the pinned regression test exercises.
        base.update({
            "layout_family": "evidence-carved",
            "headline": slide.heading,
            "facts": [{"idx": i, "this": f} for i, f in enumerate(slide.facts, start=1)],
        })
        if slide.take_label:
            base["take_label"] = slide.take_label
        if slide.take_line:
            base["take_line"] = slide.take_line
        return base

    if isinstance(slide, StatusListSlide):
        base.update({
            "layout_family": "dark-status-list",
            "headline": slide.heading,
            "list_items": [
                {"label": it.label, "value": it.value, "status": it.status}
                for it in slide.items
            ],
        })
        return base

    if isinstance(slide, TimelineSlide):
        # timeline-pinboard's each-row fields are accent/date/label (verified
        # against layouts/timeline-pinboard.md:59-66) — NOT the spec table's
        # simplified "date,event,current". `current` is an IR-level editorial
        # concept; the projection derives the composer's `accent` token from
        # it (yellow = "we are here", white = past/future) rather than
        # exposing "current" to the skeleton directly.
        base.update({
            "layout_family": "timeline-pinboard",
            "headline": slide.heading,
            "events": [
                {"date": s.date, "label": s.label, "accent": "yellow" if s.current else "white"}
                for s in slide.steps
            ],
        })
        return base

    if isinstance(slide, TriadSlide):
        # numbered-forces-list's {{numeral}} is NOT a settable field —
        # composer extracts it by REGEX from a leading integer in the
        # headline itself (`_fill_placeholders`, composer.py:1528-1534:
        # `^(\d+)\s+(.*)$`), so the projection formats headline as
        # "<N> <heading>" to trigger it. Each-row fields are label/value
        # (layouts/numbered-forces-list.md:68-76), fed via the "items"
        # each-alias (composer.py:998-1003).
        base.update({
            "layout_family": "numbered-forces-list",
            "headline": f"{len(slide.items)} {slide.heading}".strip(),
            "items": [{"label": it.title, "value": it.desc} for it in slide.items],
        })
        return base

    if isinstance(slide, QaSlide):
        # qa-dialogue only ever renders the FIRST TWO pairs (composer.
        # _qa_dialogue_fields, composer.py:1069, `for idx, key in
        # ((0,"a"),(1,"b"))`) — a fixed 2-voice layout, not an N-turn
        # dialogue. Row keys are voice/line (matching the storyboarder
        # contract + the pinned regression test
        # scripts/wr2_html_renderer/tests/test_each_block_render.py), NOT
        # the spec table's simplified "q,a".
        base.update({
            "layout_family": "qa-dialogue",
            "qa_pairs": [{"voice": p.voice, "line": p.line} for p in slide.pairs],
        })
        return base

    if isinstance(slide, StatSlide):
        # stat-card-hero: `heading` supports a "UNIT / VALUE" split into a
        # small unit line + big accent value (composer.py:1564-1566, the
        # family == "stat-card-hero" special-case); `subheading` is the
        # label above; `body` is the caption below the (optional) chart. No
        # `chart` is emitted for a single-stat IR slide — the
        # {{#each chart_rows}} block cleanly drops itself when absent
        # (verified: test_each_block_render.py "absent-array: block dropped").
        headline = f"{slide.unit} / {slide.value}" if slide.unit else slide.value
        base.update({
            "layout_family": "stat-card-hero",
            "headline": headline,
            "subhead": slide.label,  # _fill_placeholders fills {{subheading}} from "subhead"/"subheading"
            "body": slide.context,
        })
        return base

    if isinstance(slide, CitationSlide):
        # DISCOVERED GAP (verified this session, grep composer.py for
        # "title" = zero hits): source-citation's top-level {{title}}
        # placeholder is NEVER substituted anywhere in _fill_placeholders.
        # We still emit the field the skeleton textually names ("title"),
        # per the mandate to match the real skeleton contract rather than
        # invent a workaround field name composer doesn't look for either —
        # see the PR description / final report for the Phase-3 composer.py
        # follow-up this implies. Per-citation row fields are
        # body/issuer/date/url/note (layouts/source-citation.md:31-36) —
        # "body" here is the row's citation CODE text, unrelated to the
        # top-level {{body}} placeholder other families use.
        base.update({
            "layout_family": "source-citation",
            "title": slide.claim,
            "citations": [
                {
                    "body": s.code,
                    "issuer": s.issuer,
                    "date": s.date,
                    "url": s.url,
                    **({"note": s.note} if s.note else {}),
                }
                for s in slide.sources
            ],
        })
        return base

    if isinstance(slide, CtaSlide):
        # DISCOVERED GAP (verified this session, grep composer.py for
        # "trust_marker"/"reach"/"invite"/"primary_source_url"/"qr_caption" =
        # zero hits for all of them): elegant-close's top-level content
        # fields are ALSO never substituted by _fill_placeholders — this
        # family appears effectively unwired end-to-end today, consistent
        # with the spec's diagnosis that most of the 11 non-auto-reachable
        # families are underbaked. Emitted verbatim per the skeleton's own
        # field names; see final report for the Phase-3 follow-up.
        base.update({
            "layout_family": "elegant-close",
            "trust_marker": slide.trust_marker,
            "reach": slide.reach,
            "invite": slide.invite,
        })
        return base

    raise TypeError(f"to_composer_dict: unhandled slide kind {type(slide)!r}")


# ─────────────────────────────────────────────────────────────────────────
# 5. Inert brand constants (Phase 1 — NOT consumed by production; a future
#    Phase 3, itself gated by the 4-LLM panel, is the only place these would
#    ever get wired into a live render).
#
#    ⚠️ PROVENANCE CAVEAT (verified 2026-07-21, this session): the ratified
#    spec (.claude/skills/wr2/_research/2026-07-21-editorial-intelligence-
#    design.md §8) lists the arc slate, the caps-only-on-headings rule, "The
#    Bali Zero read" closer slot, and the palette-per-domain map as
#    "Decisioni Zero-gated (Legge 5) ... la sessione NON le prende" — i.e.
#    NOT YET ratified on disk as of this session (re-read verbatim this
#    turn; §8 is a REQUEST for ratification, not a ratification record; no
#    later commit/PR closes it — `gh pr list --search "editorial-
#    intelligence"` returns only the spec PR #2936 itself). The build
#    mandate that produced this module described these as "ratified" — that
#    claim does not hold up against the spec file's own text on disk, so
#    everything below is a DRAFT/PROPOSED shape only, pending Zero's actual
#    §8 ratification, NOT a record of a decision that happened. Shipping
#    this draft carries zero live-behavior risk (Phase 1 is shadow-only,
#    nothing here is read by production) — but do not let its mere presence
#    in a merged PR be mistaken for ratification-by-commit.
# ─────────────────────────────────────────────────────────────────────────

CAPS_POLICY = "headings_only"  # PROPOSED, spec §8 item 2 (Zero-gated, UNRATIFIED)

# PROPOSED 7-arc slate with role sequences (spec §8 item 1, UNRATIFIED — the
# spec itself only names the count/examples "quali 6-8, e le loro sequenze
# di ruoli — è voce editoriale/brand", it does not specify the sequences).
# Role vocabulary follows the spec's own Mossa-B planner JSON example (§2:
# roles "hook"/"discovery") extended with the obvious siblings a slide-role
# grammar needs. Sequence length follows §Mossa-E ("breaking -> arco stretto
# 5-6; evergreen -> arco ricco 9") — this is a STARTING shape for Zero to
# react to/amend, not a claim of institutional voice.
ARCS: dict[str, list[str]] = {
    "news_alert": ["hook", "context", "fact_stack", "impact", "close"],
    "deadline": ["hook", "deadline_fact", "consequence", "action", "close"],
    "myth_buster": ["hook", "myth", "reality", "evidence", "close"],
    "worked_example": ["hook", "scenario", "steps", "outcome", "close"],
    "comparison": ["hook", "option_a", "option_b", "verdict", "close"],
    "explainer": ["hook", "context", "mechanism", "implication", "close"],
    "status_roundup": ["hook", "item", "item", "item", "close"],
}

# PROPOSED palette-per-domain (spec §8 item 4, UNRATIFIED). immigration/tax/
# company use REAL brand tokens (skills/bali-zero-brand/tokens.json +
# constitution.md "Palette" table): antracite #373D42, accent yellow
# #F4C430, status red #C8102E, bg.black #000000. property's "paper/cream"
# has NO existing token (tokens.json has no cream/paper entry) — its hex
# here is an INVENTED placeholder, flagged accordingly; a real value needs a
# tokens.json addition + Zero sign-off, not this module.
PALETTE_BY_DOMAIN: dict[str, dict[str, str]] = {
    "immigration": {"primary": "#373D42", "accent": "#F4C430"},
    "tax": {"primary": "#373D42", "accent": "#C8102E"},
    "company": {"primary": "#000000", "accent": "#F4C430"},
    # "#F5F0E6" is an INVENTED placeholder — no cream/paper brand token exists yet.
    "property": {"primary": "#F5F0E6", "accent": "#373D42"},
    "breaking": {"primary": "#C8102E", "accent": "#000000"},
}

# PROPOSED recurring role slot (spec §8 item 3, UNRATIFIED): "The Bali Zero
# read" as the standing name for the closer's take/point-of-view role. A
# future Phase 3 would use it as e.g. the default take_label on a
# fact_stack's closing take.
CLOSER_FRANCHISE_LABEL = "The Bali Zero read"
