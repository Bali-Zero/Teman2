#!/usr/bin/env python3
"""wr2_editorial_pregate.py — deterministic, zero-LLM editorial pre-gate
(WR2 editorial-intelligence Phase 2).

ADDITIVE ONLY. Nothing in `wr2_draft_generator.py`, `wr2_carousel_ir.py`, or
`scripts/wr2_html_renderer/composer.py` is modified or imports this module —
this is a standalone check library exercised by tests and by
`wr2_pregate_shadow.py` against historical decks. Wiring it into the live
pipeline (gating a draft before it reaches the human review queue) is a
future step, itself gated the same way Phase 1/3 are (4-LLM panel, CLAUDE.md
§6) — not this PR.

Implements the ratified spec's "Il Critico — SDOPPIATO" strato-1
(`.claude/skills/wr2/_research/2026-07-21-editorial-intelligence-design.md`
§2), the deterministic pre-gate ahead of the (expensive, slow) `wr2-critic`
LLM judge — ported in SHAPE (not code) from
`Maazsiddiqui01/linkedin-carousel-generator`'s `run_overseer_checks.js`
(Jaccard duplicate-detection :41-52, bullet-count/ceiling :118-132, coverage
:221-237 — see `.claude/skills/wr2/_research/2026-07-21-oss-code-reading-
statemachine-gptnewspaper.md` §4 for the mapping table).

SCAR #3 DISCIPLINE (cicatrix-superscar.md — guard over/under-match, the most
recursive disease in this codebase, 8+ prior instances: W68/W72/W73/W82/W83/
W84/W85/W91/W92/W94/W95/W99). Every check below is built to the antidote:
  - Jaccard similarity normalizes AWAY Indonesian legal boilerplate (Pasal/
    ayat/berdasarkan/…) BEFORE comparing, so two DIFFERENT regulatory slides
    that merely cite similar law-citation scaffolding never false-positive
    as duplicates (innocence).
  - "closer echoes spine" is a fact-key/entity match (numbers, regulation
    codes, acronyms, content-words), NEVER a bare substring test.
  - Count-word matching (bullet-promise) is WORD-BOUNDARY, never substring
    ("TAKEAWAY FOR SELLERS" containing "TAKE" must never fire a kicker-
    collision, mirroring wr2_draft_generator._kicker_collision's own
    discipline).
  - The caps-wall check exempts by FIELD ROLE (heading vs body), never by
    string-sniffing content — a statement-bomb closer that is legitimately
    all-caps is exempt because of WHAT FIELD it is, not because of a regex
    escape hatch on its text.
Every check has a registered guilt+innocence corpus in
`scripts/tests/test_wr2_editorial_pregate.py`, itself registered in
`infra/guard-conformance/registry.json` under a dedicated `wr2_editorial_
pregate` surface (see `check_wr2_editorial_pregate_surface` in
`infra/guard-conformance/check_guard_conformance.py`) — enforced in CI.

DESIGN — two entry points, one internal representation (spec §2's own
prescription): `pregate_typed(deck, spine=None)` accepts a validated
`wr2_carousel_ir.SlideDeck` (Phase 1's 11-kind discriminated union);
`pregate_flat(slides, spine=None)` accepts the flat production dict shape
`wr2_draft_generator._normalise_slides` actually emits today
(`{slide_number, slide_type, is_cover, is_hero_image, headline, subhead,
body, image_prompt, tonal_palette, image_mode, image_url}` — verified
against wr2_draft_generator.py:1441-1453 this session). Both entry points
project their input into `_CanonSlide` — a single normalized shape the 7
`check_*` functions operate on uniformly, so there is exactly ONE
implementation per check, not a typed/flat fork per check (less surface for
the #3 family to grow a new head on).

Pure functions only. Zero LLM calls, zero network, zero DB, zero filesystem
I/O at import time or call time — every function here is a plain
str/dict/pydantic-object -> CheckResult transform, so the test suite runs
instantly and deterministically, and `wr2_pregate_shadow.py` can run this
against hundreds of decks in well under a second of wall-clock.
"""
from __future__ import annotations

import json
import logging
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("wr2.editorial_pregate")

# wr2_carousel_ir.py is a sibling script module (not a package), so it is
# only importable with scripts/ on sys.path — same convention
# wr2_ir_shadow_replay.py and scripts/tests/test_wr2_carousel_ir.py already
# use. wr2_carousel_ir itself is zero-I/O (its own docstring guarantees it),
# so this import adds no side effects.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from wr2_carousel_ir import (  # noqa: E402
    CitationSlide,
    CoverSlide,
    CtaSlide,
    FactStackSlide,
    ProseSlide,
    QaSlide,
    SlideDeck,
    StatementSlide,
    StatSlide,
    StatusListSlide,
    TimelineSlide,
    TriadSlide,
)

# ─────────────────────────────────────────────────────────────────────────
# Structured result
# ─────────────────────────────────────────────────────────────────────────

VALID_VERDICTS = ("PASS", "FAIL", "SKIP", "WARN")


@dataclass
class CheckResult:
    check: str
    verdict: str  # PASS | FAIL | SKIP | WARN
    reasons: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.verdict not in VALID_VERDICTS:
            raise ValueError(f"invalid verdict {self.verdict!r} (allowed: {VALID_VERDICTS})")

    def to_dict(self) -> dict[str, Any]:
        return {"check": self.check, "verdict": self.verdict, "reasons": list(self.reasons)}


@dataclass
class PregateReport:
    deck_kind: str  # "typed" | "flat"
    slide_count: int
    checks: list[CheckResult]
    verdict: str  # aggregate: FAIL > WARN > PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "deck_kind": self.deck_kind,
            "slide_count": self.slide_count,
            "verdict": self.verdict,
            "checks": [c.to_dict() for c in self.checks],
        }

    def to_json(self, **kwargs: Any) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, **kwargs)


def _aggregate_verdict(results: list[CheckResult]) -> str:
    verdicts = {r.verdict for r in results}
    if "FAIL" in verdicts:
        return "FAIL"
    if "WARN" in verdicts:
        return "WARN"
    return "PASS"


# ─────────────────────────────────────────────────────────────────────────
# Internal canonical representation — the "one internal representation"
# both entry points project into before any check runs.
# ─────────────────────────────────────────────────────────────────────────


@dataclass
class _CanonSlide:
    index: int  # 1-based
    is_cover: bool
    kind_or_type: str  # typed: pydantic discriminator ("cover", "prose", …); flat: slide_type verbatim
    typed_origin: bool  # True iff this canon list came from a validated typed SlideDeck
    reader_text: str  # every user-visible string on the slide, concatenated
    heading_texts: list[str]  # HEADING-ROLE text (headline/statement/heading/kicker-ish — MAY be caps)
    body_texts: list[str]  # BODY-ROLE text (prose/list-item content — must NEVER be a caps-wall)
    kicker_source: str  # the one text field a kicker would be extracted from
    count_heading_text: str  # text scanned for an announced item-count ("3 things", "TIGA syarat")
    list_count: int | None  # delivered item count, when this slide kind/body structurally carries one


# ─────────────────────────────────────────────────────────────────────────
# Shared low-level helpers
# ─────────────────────────────────────────────────────────────────────────

_ID_BOILERPLATE_TOKENS = frozenset({
    "pasal", "ayat", "berdasarkan", "peraturan", "menteri", "nomor",
    "tahun", "huruf", "jo", "juncto",
})


def _normalize_for_jaccard(text: str) -> set[str]:
    """Lowercase + strip punctuation via \\w+ tokenization, then drop
    digit-only tokens and Indonesian legal-boilerplate tokens BEFORE
    similarity is computed — so two DIFFERENT regulatory slides that merely
    share law-citation scaffolding ("Pasal 5 ayat 2 Peraturan Menteri Nomor
    ...") never false-positive as near-duplicates (spec §2, Kimi red-team
    objection #3)."""
    normalized = unicodedata.normalize("NFKC", text or "").lower()
    tokens = re.findall(r"\w+", normalized)
    return {
        t for t in tokens
        if not t.isdigit() and t not in _ID_BOILERPLATE_TOKENS
    }


_DUPLICATE_JACCARD_THRESHOLD = 0.80
_DUPLICATE_MIN_TOKENS = 6


_COUNT_WORDS: dict[str, int] = {
    "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "dua": 2, "tiga": 3, "empat": 4, "lima": 5, "enam": 6, "tujuh": 7, "delapan": 8, "sembilan": 9,
}
_COUNT_PATTERN = re.compile(
    r"\b(?:[2-9]|" + "|".join(sorted(_COUNT_WORDS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def _extract_announced_count(text: str) -> int | None:
    """First word-boundary count token in `text` (digit 2-9, or an EN/ID
    count word). Never a substring match — `\\b...\\b` on the WHOLE token,
    so e.g. "2025" never matches (no boundary between its digits) and
    "istiga..." never matches "tiga". Returns None when no count is
    announced (callers SKIP, never guess)."""
    m = _COUNT_PATTERN.search(text or "")
    if not m:
        return None
    tok = m.group(0)
    if tok.isdigit():
        return int(tok)
    return _COUNT_WORDS.get(tok.lower())


_NEWLINE_BULLET_RE = re.compile(r"(?:^|\n)\s*[-*•‣◦]\s+", re.MULTILINE)
_INLINE_NUMBERED_RE = re.compile(r"(?<!\d)([1-9]\d?)[.)]\s+")


def _flat_body_bullet_count(body: str) -> int | None:
    """Delivered item count for a FLAT slide's `body` text, or None when the
    body has no structurally-verifiable list shape (plain prose — the
    overwhelming majority of today's production bodies, verified this
    session: 3/557 historical slides have any bullet/numbered structure at
    all). Returning None here is a SKIP signal, not a violation — a prose
    paragraph that happens to mention a number in its heading is not
    (structurally) a broken bullet-promise; it simply has nothing this
    check can verify (innocence: prose stays silent, never penalized for
    not being a list it never claimed via structure to be)."""
    body = body or ""
    newline_bullets = _NEWLINE_BULLET_RE.findall(body)
    if newline_bullets:
        return len(newline_bullets)
    nums = _INLINE_NUMBERED_RE.findall(body)
    if len(nums) < 2:
        return None
    try:
        seq = [int(n) for n in nums]
    except ValueError:
        return None
    if seq[0] != 1:
        return None
    if not all(b - a in (0, 1) for a, b in zip(seq, seq[1:])):
        return None
    return len(nums)


_CAPS_WALL_MIN_LEN = 15
_CAPS_WALL_RATIO = 0.85
_CAPS_ACRONYM_TOLERANCE = 4  # ignore tokens <=4 letters when computing the ratio


def _is_caps_wall(text: str) -> bool:
    """RATIFIED brand rule (spec §8 item 2, ratified by Zero 2026-07-21):
    'caps only on headings, never on bodies'. A body/list-item text is a
    caps-wall when it is >=15 chars AND >=85% uppercase letters, ignoring
    short (<=4 letter) tokens so acronyms (KITAS, NPWP, PMA, KTP) embedded
    in otherwise normal-case prose never tip the ratio on their own —
    they're outnumbered by the surrounding lowercase prose in any real
    sentence, so this check flags genuine caps-walls, not acronym-bearing
    prose."""
    stripped = (text or "").strip()
    if len(stripped) < _CAPS_WALL_MIN_LEN:
        return False
    letters: list[str] = []
    for tok in stripped.split():
        core = "".join(ch for ch in tok if ch.isalpha())
        if len(core) <= _CAPS_ACRONYM_TOLERANCE:
            continue
        letters.extend(core)
    if not letters:
        return False
    upper = sum(1 for ch in letters if ch.isupper())
    return (upper / len(letters)) >= _CAPS_WALL_RATIO


def _extract_kicker(headline: str) -> str | None:
    """Port of wr2_draft_generator._extract_take_kicker (wr2_draft_generator.py
    :629-665) — duplicated rather than imported, mirroring wr2_carousel_ir.py's
    own precedent (its docstring: 'Duplicated (not imported) on purpose: this
    module must stay importable standalone with ZERO I/O ... side effects').
    'KICKER: rest of the sentence' -> 'KICKER' (2-5 words before the colon);
    a colon-less headline is treated as a kicker only if itself 1-5 words."""
    headline = (headline or "").strip()
    if not headline:
        return None
    normalized_headline = unicodedata.normalize("NFKC", headline)
    prefix, sep, _rest = normalized_headline.partition(":")
    if sep:
        prefix = prefix.strip()
        if prefix and 2 <= len(prefix.split()) <= 5:
            return prefix
        return None
    if 1 <= len(normalized_headline.split()) <= 5:
        return normalized_headline
    return None


def _normalize_kicker_text(text: str) -> str:
    """Port of wr2_draft_generator._normalize_kicker (wr2_draft_generator.py
    :609-626) — whole-STRING normalization, never used for substring
    matching (scar family #3): NFKC fold, whitespace collapse, terminal-
    punctuation strip, casefold."""
    normalized = unicodedata.normalize("NFKC", text)
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = normalized.strip(" \t\r\n:;,.-–—")
    return normalized.casefold()


_STOPWORDS_EN = frozenset({
    "the", "and", "for", "with", "from", "that", "this", "these", "those",
    "have", "has", "will", "are", "was", "were", "been", "into", "onto",
    "over", "under", "about", "after", "before", "during", "which", "what",
    "when", "where", "while", "their", "there", "here", "your", "you",
    "our", "its", "than", "then", "also", "still", "each", "every",
})
_STOPWORDS_ID = frozenset({
    "yang", "dengan", "dari", "untuk", "pada", "dalam", "adalah", "akan",
    "atau", "dan", "ini", "itu", "para", "oleh", "telah", "dapat", "tidak",
    "juga", "sudah", "masih", "harus", "bagi", "sebagai", "karena",
})

_REGCODE_RE = re.compile(r"\b\d{1,4}/\d{4}\b")  # "37/2025", "5/2025" — a regulation-code number pair
_ACRONYM_RE = re.compile(r"\b[A-Z]{2,}\b")
_NUMBER_RE = re.compile(r"\b\d{2,}\b")
_WORD5_RE = re.compile(r"[A-Za-z]{5,}")


def _fact_key_tokens(text: str) -> set[str]:
    """Entity/fact-key tokens for the spine-echo check — NEVER a bare
    substring test (spec §2 hard rule: 'l'echo si misura su chiave-fatto/
    entità condivisa, non su sotto-stringa letterale'). Four independent
    signals, unioned: regulation-code number pairs ('37/2025'), uppercase
    acronyms (KITAS, PMA — lowercased for matching), bare 2+-digit numbers
    (catches a shared year/threshold even without a full code), and
    content-words >=5 chars minus EN/ID stopwords."""
    text = text or ""
    tokens: set[str] = set()
    tokens |= {m.group(0) for m in _REGCODE_RE.finditer(text)}
    tokens |= {m.group(0).lower() for m in _ACRONYM_RE.finditer(text)}
    tokens |= {m.group(0) for m in _NUMBER_RE.finditer(text)}
    for w in _WORD5_RE.findall(text):
        wl = w.lower()
        if wl in _STOPWORDS_EN or wl in _STOPWORDS_ID:
            continue
        tokens.add(wl)
    return tokens


# ─────────────────────────────────────────────────────────────────────────
# Typed-deck projection (wr2_carousel_ir.SlideDeck -> _CanonSlide)
# ─────────────────────────────────────────────────────────────────────────

# Kinds with a spec-scoped "list field" for the bullet-promise check
# (spec §2: "fact_stack/status_list/triad/qa/timeline" — NOT stat/citation).
_BULLET_PROMISE_KINDS = frozenset({"fact_stack", "status_list", "triad", "timeline", "qa"})


def _typed_slide_fields(slide: Any) -> tuple[str, list[str], list[str], str, str, int | None]:
    """(kind, heading_texts, body_texts, kicker_source, count_heading_text,
    list_count) for one validated typed Slide. Field-ROLE assignment is the
    caps-policy exemption mechanism (spec §8 item 2): heading_texts MAY be
    caps (kicker/punch convention), body_texts must NEVER be a caps-wall."""
    if isinstance(slide, CoverSlide):
        return ("cover", [slide.headline, slide.subhead], [], slide.headline, "", None)
    if isinstance(slide, ProseSlide):
        return ("prose", [slide.headline, slide.subhead], [slide.body], slide.headline, "", None)
    if isinstance(slide, StatementSlide):
        return ("statement", [slide.statement], [], slide.statement, "", None)
    if isinstance(slide, FactStackSlide):
        heading = [slide.heading] + ([slide.take_label] if slide.take_label else [])
        body = list(slide.facts) + ([slide.take_line] if slide.take_line else [])
        return ("fact_stack", heading, body, slide.heading, slide.heading, len(slide.facts))
    if isinstance(slide, StatusListSlide):
        body = [t for it in slide.items for t in (it.label, it.value) if t]
        return ("status_list", [slide.heading], body, slide.heading, slide.heading, len(slide.items))
    if isinstance(slide, TimelineSlide):
        body = [st.label for st in slide.steps if st.label]
        return ("timeline", [slide.heading], body, slide.heading, slide.heading, len(slide.steps))
    if isinstance(slide, TriadSlide):
        body = [t for it in slide.items for t in (it.title, it.desc) if t]
        return ("triad", [slide.heading], body, slide.heading, slide.heading, len(slide.items))
    if isinstance(slide, QaSlide):
        heading = [p.voice for p in slide.pairs if p.voice]  # speaker labels are kicker-like, not prose
        body = [p.line for p in slide.pairs if p.line]
        return ("qa", heading, body, "", "", len(slide.pairs))
    if isinstance(slide, StatSlide):
        heading = [t for t in (slide.value, slide.unit, slide.label) if t]
        body = [slide.context] if slide.context else []
        return ("stat", heading, body, slide.value, "", None)
    if isinstance(slide, CitationSlide):
        heading = [slide.claim] + [s.code for s in slide.sources if s.code]
        body = [s.note for s in slide.sources if s.note]
        return ("citation", heading, body, slide.claim, "", None)
    if isinstance(slide, CtaSlide):
        # The CTA line is a closer PUNCH (same register as statement-bomb),
        # not a prose body — treated as heading-role (spec: closer slots are
        # short/punchy by design, not a paragraph the caps rule targets).
        heading = [t for t in (slide.invite, slide.trust_marker, slide.reach) if t]
        return ("cta", heading, [], slide.invite, "", None)
    raise TypeError(f"_typed_slide_fields: unhandled slide kind {type(slide)!r}")  # pragma: no cover


def _canon_from_typed(deck: SlideDeck) -> list[_CanonSlide]:
    out: list[_CanonSlide] = []
    for i, s in enumerate(deck.slides, start=1):
        kind, heading_texts, body_texts, kicker_src, count_text, list_count = _typed_slide_fields(s)
        heading_texts = [t for t in heading_texts if t]
        body_texts = [t for t in body_texts if t]
        reader_text = " ".join(heading_texts + body_texts)
        if kind in _BULLET_PROMISE_KINDS:
            promise_count = list_count
        else:
            promise_count = None
        out.append(_CanonSlide(
            index=i,
            is_cover=(kind == "cover"),
            kind_or_type=kind,
            typed_origin=True,
            reader_text=reader_text,
            heading_texts=heading_texts,
            body_texts=body_texts,
            kicker_source=kicker_src or "",
            count_heading_text=count_text or "",
            list_count=promise_count,
        ))
    return out


# ─────────────────────────────────────────────────────────────────────────
# Flat-deck projection (production dict shape -> _CanonSlide)
# ─────────────────────────────────────────────────────────────────────────


def _canon_from_flat(slides: list[dict[str, Any]]) -> list[_CanonSlide]:
    out: list[_CanonSlide] = []
    for i, s in enumerate(slides, start=1):
        headline = str(s.get("headline") or "").strip()
        subhead = str(s.get("subhead") or "").strip()
        body = str(s.get("body") or "").strip()
        slide_type = str(s.get("slide_type") or "").strip().lower()
        is_cover = bool(s.get("is_cover")) or i == 1
        heading_texts = [t for t in (headline, subhead) if t]
        body_texts = [body] if body else []
        reader_text = " ".join(heading_texts + body_texts)
        out.append(_CanonSlide(
            index=i,
            is_cover=is_cover,
            kind_or_type=slide_type,
            typed_origin=False,
            reader_text=reader_text,
            heading_texts=heading_texts,
            body_texts=body_texts,
            kicker_source=headline,
            count_heading_text=" ".join(t for t in (headline, subhead) if t),
            list_count=_flat_body_bullet_count(body),
        ))
    return out


# ─────────────────────────────────────────────────────────────────────────
# The 7 checks — each a pure list[_CanonSlide] -> CheckResult transform.
# ─────────────────────────────────────────────────────────────────────────


def check_duplicate_slides(canon: list[_CanonSlide]) -> CheckResult:
    """Pairwise Jaccard on normalized reader-text (boilerplate-stripped
    FIRST). Slides with <6 content tokens after normalization are excluded
    from comparison (too short to judge either way — SKIP, not PASS/FAIL,
    for that slide)."""
    eligible: list[tuple[int, set[str]]] = []
    for c in canon:
        toks = _normalize_for_jaccard(c.reader_text)
        if len(toks) >= _DUPLICATE_MIN_TOKENS:
            eligible.append((c.index, toks))
    if len(eligible) < 2:
        return CheckResult(
            "check_duplicate_slides", "SKIP",
            ["fewer than 2 slides have >=6 content tokens after boilerplate-stripped normalization"],
        )
    reasons: list[str] = []
    verdict = "PASS"
    for a in range(len(eligible)):
        for b in range(a + 1, len(eligible)):
            i, ta = eligible[a]
            j, tb = eligible[b]
            union = ta | tb
            if not union:
                continue
            jacc = len(ta & tb) / len(union)
            if jacc >= _DUPLICATE_JACCARD_THRESHOLD:
                verdict = "FAIL"
                reasons.append(f"slide {i} vs slide {j}: jaccard={jacc:.2f} (>= {_DUPLICATE_JACCARD_THRESHOLD})")
    if not reasons:
        reasons = ["no near-duplicate slide pair found"]
    return CheckResult("check_duplicate_slides", verdict, reasons)


def check_bullet_promise(canon: list[_CanonSlide]) -> CheckResult:
    """If a heading/subhead announces a count (word-boundary digit 2-9 or
    EN/ID count word), the slide's list-bearing field must deliver exactly
    N items. Typed: fact_stack/status_list/triad/qa/timeline kinds. Flat:
    bodies with a verifiable bullet/numbered-line structure. SKIPs (per
    slide) when no count is announced OR the slide has no verifiable
    delivered-count signal — never guesses, never penalizes prose for not
    being a list it never structurally claimed to be."""
    reasons: list[str] = []
    any_judged = False
    verdict = "PASS"
    for c in canon:
        if c.list_count is None:
            continue
        n = _extract_announced_count(c.count_heading_text)
        if n is None:
            continue
        any_judged = True
        if c.list_count != n:
            verdict = "FAIL"
            reasons.append(
                f"slide {c.index} ({c.kind_or_type}): heading announces {n}, delivers {c.list_count} items"
            )
    if not any_judged:
        return CheckResult(
            "check_bullet_promise", "SKIP",
            ["no slide had both an announced count and a structurally-verifiable item list"],
        )
    if not reasons:
        reasons = ["every announced count matched its delivered item count"]
    return CheckResult("check_bullet_promise", verdict, reasons)


def check_caps_policy(canon: list[_CanonSlide]) -> CheckResult:
    """RATIFIED (spec §8 item 2): caps only on headings, never on bodies.
    Exemption is by FIELD ROLE (a slide's body_texts vs heading_texts,
    assigned at projection time per-kind/per-flat-field) — never by
    string-sniffing the text itself."""
    reasons: list[str] = []
    any_checked = False
    verdict = "PASS"
    for c in canon:
        for t in c.body_texts:
            any_checked = True
            if _is_caps_wall(t):
                verdict = "FAIL"
                reasons.append(f"slide {c.index} ({c.kind_or_type}): body-role text is a caps-wall: {t[:60]!r}")
    if not any_checked:
        return CheckResult("check_caps_policy", "SKIP", ["deck has no body-role text to evaluate"])
    if not reasons:
        reasons = ["no caps-wall found in any body-role field"]
    return CheckResult("check_caps_policy", verdict, reasons)


def check_cta_presence(canon: list[_CanonSlide]) -> CheckResult:
    """Deck has >=1 closing slide. Typed decks have a real kind
    discriminator, so the rule is precise: a cta-kind slide anywhere, OR
    the closer is kind=statement. Flat decks carry `slide_type` as a free
    string (production histogram: 76+ distinct values on 557 slides — not a
    reliable discriminator), so the only structurally-honest signal is the
    one production itself relies on (composer.map_slide_to_family's
    index==total branch: the LAST slide is ALWAYS the closer regardless of
    its label, Art 9.5 hard rule) — verify it simply carries content."""
    if not canon:
        return CheckResult("check_cta_presence", "SKIP", ["empty deck"])
    last = canon[-1]
    if canon[0].typed_origin:
        has_cta_anywhere = any(c.kind_or_type == "cta" for c in canon)
        last_is_statement = last.kind_or_type == "statement"
        if has_cta_anywhere or last_is_statement:
            reason = "cta-kind slide present" if has_cta_anywhere else f"closer (slide {last.index}) is kind=statement"
            return CheckResult("check_cta_presence", "PASS", [reason])
        return CheckResult(
            "check_cta_presence", "FAIL",
            [f"no cta-kind slide anywhere and closer (slide {last.index}, kind={last.kind_or_type}) is not a statement"],
        )
    if last.reader_text.strip():
        return CheckResult("check_cta_presence", "PASS", [f"closing slide {last.index} has content"])
    return CheckResult("check_cta_presence", "FAIL", [f"closing slide {last.index} has no text content"])


def check_kicker_unique(canon: list[_CanonSlide]) -> CheckResult:
    """No two slides in THIS deck share a normalized kicker (within-deck —
    distinct from production's cross-deck `_kicker_collision`, which checks
    against recent history; this catches a disco-rotto deck repeating its
    own kicker on two slides). Whole-string comparison only, mirroring
    `_normalize_kicker`'s own discipline — never substring."""
    seen: dict[str, int] = {}
    reasons: list[str] = []
    verdict = "PASS"
    extracted = 0
    for c in canon:
        kicker = _extract_kicker(c.kicker_source)
        if kicker is None:
            continue
        extracted += 1
        norm = _normalize_kicker_text(kicker)
        if norm in seen:
            verdict = "FAIL"
            reasons.append(f"slide {seen[norm]} and slide {c.index} share kicker {kicker!r}")
        else:
            seen[norm] = c.index
    if extracted < 2:
        return CheckResult("check_kicker_unique", "SKIP", ["fewer than 2 slides yielded an extractable kicker"])
    if not reasons:
        reasons = ["all extracted kickers are unique within this deck"]
    return CheckResult("check_kicker_unique", verdict, reasons)


_PROSE_LIKE_TYPES = frozenset({"prose", "body"})
_DEGENERACY_WARN_FRACTION = 0.70


def check_kind_coverage(canon: list[_CanonSlide]) -> CheckResult:
    """Typed decks: every slide has a valid kind — trivially true after
    pydantic validation (a cheap tripwire, per spec: 'nessuna struttura
    tipizzata... trivially true post-validation'). Flat decks: every slide
    has a non-empty slide_type. Both also WARN (never FAIL) when >70% of
    non-cover slides are prose/body-shaped — the degeneracy tripwire this
    whole program exists to surface (spec §0.1's own diagnosis)."""
    if not canon:
        return CheckResult("check_kind_coverage", "SKIP", ["empty deck"])
    missing = [c.index for c in canon if not c.kind_or_type]
    verdict = "PASS"
    reasons: list[str] = []
    if missing:
        verdict = "FAIL"
        reasons.append(f"slides missing kind/slide_type: {missing}")
    non_cover = [c for c in canon if not c.is_cover]
    if non_cover:
        prose_like = sum(1 for c in non_cover if c.kind_or_type in _PROSE_LIKE_TYPES)
        frac = prose_like / len(non_cover)
        if frac > _DEGENERACY_WARN_FRACTION:
            if verdict == "PASS":
                verdict = "WARN"
            reasons.append(
                f"{prose_like}/{len(non_cover)} ({frac:.0%}) non-cover slides are prose/body-shaped "
                f"— degeneracy tripwire (> {_DEGENERACY_WARN_FRACTION:.0%})"
            )
    if not reasons:
        reasons = ["every slide has a kind/slide_type; below the prose/body degeneracy threshold"]
    return CheckResult("check_kind_coverage", verdict, reasons)


def check_spine_echo(canon: list[_CanonSlide], spine: str | None) -> CheckResult:
    """When a `spine` (the deck's chosen guiding idea, spec §2 Mossa C) is
    supplied, the closer must echo it via a shared fact-key/entity token —
    NEVER a bare substring test. SKIP (honest N/A) when no spine is given:
    this function never guesses one from the copy."""
    if spine is None:
        return CheckResult("check_spine_echo", "SKIP", ["no spine provided — never guessed from the copy"])
    spine_tokens = _fact_key_tokens(spine)
    if not spine_tokens:
        return CheckResult("check_spine_echo", "SKIP", ["spine text yielded no extractable fact-key tokens"])
    if not canon:
        return CheckResult("check_spine_echo", "SKIP", ["empty deck"])
    closer = canon[-1]
    closer_tokens = _fact_key_tokens(closer.reader_text)
    shared = spine_tokens & closer_tokens
    if shared:
        return CheckResult(
            "check_spine_echo", "PASS",
            [f"closer (slide {closer.index}) shares fact-key token(s): {sorted(shared)[:5]}"],
        )
    return CheckResult(
        "check_spine_echo", "FAIL",
        [f"closer (slide {closer.index}) shares zero fact-key tokens with the spine"],
    )


_STRUCTURAL_CHECKS: tuple[Callable[[list[_CanonSlide]], CheckResult], ...] = (
    check_duplicate_slides,
    check_bullet_promise,
    check_caps_policy,
    check_cta_presence,
    check_kicker_unique,
    check_kind_coverage,
)


# ─────────────────────────────────────────────────────────────────────────
# Public entry points
# ─────────────────────────────────────────────────────────────────────────


def pregate_typed(deck: SlideDeck, spine: str | None = None) -> PregateReport:
    """Run the full pre-gate over a validated typed `wr2_carousel_ir.SlideDeck`."""
    canon = _canon_from_typed(deck)
    results = [fn(canon) for fn in _STRUCTURAL_CHECKS]
    results.append(check_spine_echo(canon, spine))
    return PregateReport(
        deck_kind="typed", slide_count=len(canon), checks=results, verdict=_aggregate_verdict(results),
    )


def pregate_flat(slides: list[dict[str, Any]], spine: str | None = None) -> PregateReport:
    """Run the full pre-gate over the flat production slide-dict shape
    (`wr2_draft_generator._normalise_slides`'s own output shape) — this is
    what gives immediate value on today's live corpus, no Phase-1/3 cutover
    required."""
    canon = _canon_from_flat(slides)
    results = [fn(canon) for fn in _STRUCTURAL_CHECKS]
    results.append(check_spine_echo(canon, spine))
    return PregateReport(
        deck_kind="flat", slide_count=len(canon), checks=results, verdict=_aggregate_verdict(results),
    )
