#!/usr/bin/env python3
"""WR2 topic-type derivation helpers (pure, defensive, no I/O).

These functions turn a carousel's `topic` text and `slides_json` into the
columns of `topic_type_log` (migration 206). They are consumed by:
  - wr2_canva_desktop_apply._log_topic_type  (write at status='rendered')
  - wr2_draft_generator.fetch_recent_same_domain / the anti-sameness steer

Design contract (constitution Art 5.7 domain, Art 5.8 image-mode, Art 10.6
anti-sameness):
  * derive_domain(topic)            -> str          (never raises; "unknown" fallback)
  * derive_dominant_mode(slides)    -> str          (never raises; "unknown" fallback)
  * derive_layout_family(slides)    -> str | None   (never raises)
  * extract_archetype(slides)       -> str | None   (never raises)

EVERY function is defensive: it accepts a dict OR a JSON string OR garbage and
NEVER raises. A logging table must never break the render path (best-effort
write per plan §3.3). When in doubt the answer is "unknown" / None.
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from typing import Any

logger = logging.getLogger("wr2.topic_type")

# ── Domain keyword map (constitution Art 5.7: visa, tax, property, regulatory,
# health, brand). Case-insensitive, Indonesian + English keywords. Order does
# not matter for correctness — first-match-wins on the iteration below, but the
# buckets are disjoint enough in practice that ordering is not load-bearing. ──
#
# A coarse keyword classifier by design (plan risk #5): a misclassification only
# weakens the anti-monotony steer, it never corrupts data. A real classifier is
# a documented v2 follow-up.
#
# ORDER IS LOAD-BEARING: derive_domain returns the FIRST bucket whose keyword
# hits, so more-specific buckets must precede the ones with broad/ambiguous
# tokens. In particular `health` is checked BEFORE `regulatory` because
# "BPJS Kesehatan" (a health topic) would otherwise be claimed by a bare "bpjs"
# regulatory token — so regulatory carries only the labor-specific
# "bpjs ketenagakerjaan", never bare "bpjs". (Verified empirically: without
# this ordering "BPJS Kesehatan for expats" misclassified as regulatory.)
_DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "visa": (
        "visa", "visto", "kitas", "kitap", "e28a", "e28b", "e33g", "voa",
        "b211", "c312", "c313", "c314", "c316", "c317", "c318", "c319", "c320",
        "permit", "stay permit", "izin tinggal", "rkptka", "imta", "dkptka",
        "second home", "golden visa", "retirement visa", "digital nomad",
    ),
    "tax": (
        "tax", "pajak", "ppn", "pph", "npwp", "vat", "fiscal", "fiskal",
        "spt", "coretax", "withholding", "income tax", "bea", "djp",
        "tax amnesty", "transfer pricing", " pbb",
    ),
    "property": (
        "property", "properti", "tanah", "rumah", "villa", "land",
        "hak pakai", "hak guna", "hgb", "shm", "sertifikat", "nominee",
        "leasehold", "freehold", "real estate", "zoning", "imb", "pbg",
        "right to use", "right of use",
    ),
    "health": (
        "health", "kesehatan", "bpjs kesehatan", "medical", "rumah sakit",
        "hospital", "clinic", "klinik", "insurance health", "asuransi kesehatan",
        "vaccine", "vaksin", "puskesmas",
    ),
    "regulatory": (
        "permenaker", "permenkumham", "labor", "tenaga kerja",
        "bpjs ketenagakerjaan", "regulasi", "regulation", "peraturan",
        "omnibus", "oss", "nib", "kbli", "compliance", "lkpm", "bkpm",
        "pp ", "pp no", "permen", "uu ", "perppu", "decree", "ministerial",
        "license", "izin usaha", "company", "pt pma", "perusahaan",
        "incorporation",
    ),
    "brand": (
        "bali zero", "balizero", "our story", "behind the scenes", "team",
        "anniversary", "we built", "manifesto",
    ),
}

# The image-mode taxonomy (constitution Art 5.8, 9 modes). We do NOT invent
# modes — derive_dominant_mode only counts what the slides actually carry, and
# this set is informational (lets callers sanity-check / future-validate).
VALID_IMAGE_MODES: frozenset[str] = frozenset(
    {
        "desk-document",
        "event-photo",
        "architecture-or-texture",
        "provocation-photo",
        "human-silhouette",
        "object-comparison",
        "calendar-photo",
        "data-visualization",
        "cultural-photo",
    }
)

UNKNOWN = "unknown"


def _coerce_to_dict(slides_json: Any) -> dict[str, Any] | list[Any] | None:
    """Best-effort coerce slides_json into a dict/list. Never raises.

    Accepts:
      * a dict (already parsed) -> returned as-is
      * a list (the bare slides array) -> returned as-is
      * a JSON string -> parsed; returns the result or None on failure
      * anything else / malformed -> None
    """
    if slides_json is None:
        return None
    if isinstance(slides_json, (dict, list)):
        return slides_json
    if isinstance(slides_json, (str, bytes, bytearray)):
        try:
            parsed = json.loads(slides_json)
        except (ValueError, TypeError):
            return None
        if isinstance(parsed, (dict, list)):
            return parsed
        return None
    return None


def _extract_slide_list(slides_json: Any) -> list[dict[str, Any]]:
    """Return the list of per-slide dicts from any slides_json shape. Never raises.

    Handles the canonical {"slides": [...]} envelope as well as a bare [...]
    list. Non-dict slide entries are dropped (defensive).
    """
    data = _coerce_to_dict(slides_json)
    if data is None:
        return []
    if isinstance(data, dict):
        slides = data.get("slides")
    else:  # already a list
        slides = data
    if not isinstance(slides, list):
        return []
    return [s for s in slides if isinstance(s, dict)]


def derive_domain(topic: str | None) -> str:
    """Map a topic string to a domain bucket via keyword match. Never raises.

    Case-insensitive, matches Indonesian + English keywords. Returns the first
    domain whose keyword set hits; "unknown" if nothing matches or topic is
    empty/None/non-string.
    """
    if not isinstance(topic, str) or not topic.strip():
        return UNKNOWN
    haystack = topic.lower()
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if kw in haystack:
                return domain
    return UNKNOWN


def _slide_mode(slide: dict[str, Any]) -> str | None:
    """Read a slide's image-mode from whichever field it carries. Never raises.

    Tolerates both `image_mode` (the field §3.0 adds) and the alt name
    `image_style_mode`. Returns a normalised lowercase string, or None when the
    slide has no usable mode.
    """
    for key in ("image_mode", "image_style_mode"):
        val = slide.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip().lower()
    return None


def derive_dominant_mode(slides_json: Any) -> str:
    """Most-frequent per-slide image-mode across the carousel. Never raises.

    Counts only what the slides carry (we do not invent modes). Returns:
      * the single most-frequent mode when there is a unique winner
      * "unknown" on a tie, on an empty/absent set, or on malformed input
    """
    slides = _extract_slide_list(slides_json)
    if not slides:
        return UNKNOWN
    modes = [m for m in (_slide_mode(s) for s in slides) if m]
    if not modes:
        return UNKNOWN
    counts = Counter(modes)
    most_common = counts.most_common()
    # Tie at the top -> ambiguous -> unknown (do not pick arbitrarily).
    if len(most_common) > 1 and most_common[0][1] == most_common[1][1]:
        return UNKNOWN
    return most_common[0][0]


def distinct_mode_count(slides_json: Any) -> int:
    """Number of distinct image-modes present in the carousel. Never raises.

    Used by the intra-carousel >=3-distinct-modes WARN (plan §3.5).
    """
    slides = _extract_slide_list(slides_json)
    modes = {m for m in (_slide_mode(s) for s in slides) if m}
    return len(modes)


def derive_layout_family(slides_json: Any) -> str | None:
    """Most-frequent per-slide layout field, else top-level archetype, else None.

    Never raises. Reads a per-slide `layout_family` / `layout` field if the
    slides carry one; falls back to the top-level archetype; else None.
    """
    slides = _extract_slide_list(slides_json)
    layouts: list[str] = []
    for s in slides:
        for key in ("layout_family", "layout"):
            val = s.get(key)
            if isinstance(val, str) and val.strip():
                layouts.append(val.strip().lower())
                break
    if layouts:
        counts = Counter(layouts)
        return counts.most_common(1)[0][0]
    return extract_archetype(slides_json)


def extract_archetype(slides_json: Any) -> str | None:
    """Top-level `archetype` from slides_json if present, else None. Never raises."""
    data = _coerce_to_dict(slides_json)
    if isinstance(data, dict):
        val = data.get("archetype")
        if isinstance(val, str) and val.strip():
            return val.strip().lower()
    return None


def is_same_combo(
    register_a: str | None,
    mode_a: str | None,
    register_b: str | None,
    mode_b: str | None,
) -> bool:
    """True when two (register, image-mode) combos count as "the same" per Art 10.6.

    The anti-sameness rule (plan §3.5, panel-corrected): a new carousel is
    allowed if it DIFFERS IN EITHER register OR image-mode. So two combos are
    "the same" (a collision worth rejecting) only when they match in BOTH
    register AND mode.

    Mode comparison is SKIPPED when dominant_mode is "unknown" on EITHER side
    (until §3.0 fills modes, this degrades to register-only). When mode is
    skipped, a collision requires only the registers to match.
    """
    reg_a = (register_a or "").strip().lower() or None
    reg_b = (register_b or "").strip().lower() or None
    md_a = (mode_a or "").strip().lower() or None
    md_b = (mode_b or "").strip().lower() or None

    # Registers must match for any collision.
    if reg_a is None or reg_b is None or reg_a != reg_b:
        return False

    # Registers match. Now the mode axis.
    mode_known = (
        md_a is not None
        and md_b is not None
        and md_a != UNKNOWN
        and md_b != UNKNOWN
    )
    if not mode_known:
        # Mode unknown on at least one side -> register-only comparison.
        # Registers already matched -> collision.
        return True
    # Both modes known: collision only if modes ALSO match (differ-in-either rule).
    return md_a == md_b


def collides_with_recent(
    register: str | None,
    dominant_mode: str | None,
    recent: list[dict[str, Any]],
) -> bool:
    """True if (register, mode) collides with EITHER of the recent same-domain rows.

    `recent` is the output of fetch_recent_same_domain: a list of dicts with
    keys `register` and `dominant_mode`. Empty list -> no collision (cold-start
    safe). Never raises.
    """
    if not recent:
        return False
    for row in recent:
        try:
            r_reg = row.get("register")
            r_mode = row.get("dominant_mode")
        except AttributeError:
            continue
        if is_same_combo(register, dominant_mode, r_reg, r_mode):
            return True
    return False
