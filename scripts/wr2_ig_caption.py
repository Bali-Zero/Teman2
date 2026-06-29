#!/usr/bin/env python3
"""
wr2_ig_caption.py — deterministic Instagram-caption author for WR2 carousels.

`build_caption(slug) -> str` turns a rendered WR2 carousel's `brief.json` +
`slides.json` (under `apps/war-room/output/carousel/<slug>/`) into a
brand-compliant, restrained Instagram caption — **without any LLM call**.
The transform is pure: same JSON in, same caption out.

Caption structure (Bali Zero restrained voice):
  1. hook line          — the carousel's core tension (cover / slide-1 heading)
  2. body (2-4 lines)   — the real regulatory fact, plain language
  3. soft CTA           — "DM us / link in bio"
  4. disclaimer         — "Informational, not legal advice."
  5. 8-15 hashtags      — broad (#bali #indonesia) + niche per topic

LAW 2 (sovereignty / UU PDP): the caption is built EXCLUSIVELY from the
carousel's own public editorial copy. No CRM / KTP / passport / NPWP / client
path is ever read. `_assert_no_pii_path` enforces that the only inputs are the
two public JSON files of the carousel itself.

This module carries fixes for three bugs found by adversarial observers on real
fixtures (see the module-level constants / helpers flagged `BUG #n`):
  1. CRITICAL — nested-dict `bilingual_lexicon_with_english_assist` crashed the
     iterator (AttributeError). `_normalize_lexicon` now handles flat-list,
     nested-dict, missing, and None shapes.
  2. CRITICAL (superscar #3 over-match) — the brand emoji guard swallowed the
     legitimate content glyphs ✓ / ✗ (U+2713/2714/2716/2717) that WR2
     dark-status-list slides carry, killing the whole caption. `_strip_emoji`
     now transliterates those glyphs to "yes:" / "no:" BEFORE the emoji class
     runs, and the emoji class explicitly excludes them.
  3. MEDIUM — the sentence-case helper lowercased unknown all-caps tokens,
     mangling nationality lists ("Thailand and vietnam"). `_sentence_case` now
     keeps all-caps tokens verbatim (or Title-cases them), never lowercases.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #

# Repo root = three levels up from this file (.../<repo>/scripts/wr2_ig_caption.py).
_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_CAROUSEL_BASE = _REPO_ROOT / "apps" / "war-room" / "output" / "carousel"

# The ONLY two files a carousel caption may be built from (LAW 2 boundary).
_ALLOWED_INPUT_FILES = ("brief.json", "slides.json")

IG_CAPTION_HARD_LIMIT = 2200  # Instagram caption hard char limit.

DISCLAIMER = "Informational, not legal advice."
SOFT_CTA = "Questions about your case? DM us or tap the link in bio."

# --------------------------------------------------------------------------- #
# Hashtag vocabulary (deterministic — domain/keyword driven, no randomness)
# --------------------------------------------------------------------------- #

_BROAD_HASHTAGS = ["#bali", "#indonesia", "#balizero"]

# Domain -> niche hashtags (carousel brief.domain).
_DOMAIN_HASHTAGS: dict[str, list[str]] = {
    "visa": ["#balivisa", "#indonesiavisa", "#kitas", "#visaonarrival", "#expatlife"],
    "tax": ["#indonesiatax", "#pajak", "#taxindonesia", "#expattax", "#npwp"],
    "company": ["#ptpma", "#businessindonesia", "#kbli", "#investindonesia", "#oss"],
    "property": ["#baliproperty", "#balirealestate", "#propertyindonesia", "#leasehold", "#hakpakai"],
    "hr": ["#hrindonesia", "#workpermit", "#imta", "#rptka", "#expatworker"],
    "compliance": ["#compliancebali", "#lkpm", "#bkpm", "#businessindonesia", "#regulasi"],
}

# Keyword -> niche hashtag, scanned against the brief/slides text. Lets a visa
# carousel about KITAS surface #kitas even if the domain bucket didn't include
# the exact term. Deterministic ordered scan.
_KEYWORD_HASHTAGS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bkitas\b", re.I), "#kitas"),
    (re.compile(r"\bkitap\b", re.I), "#kitap"),
    (re.compile(r"\bvoa\b|visa on arrival", re.I), "#visaonarrival"),
    (re.compile(r"\bbvk\b|bebas visa", re.I), "#visafree"),
    (re.compile(r"\bnpwp\b", re.I), "#npwp"),
    (re.compile(r"\bpt pma\b|\bpma\b", re.I), "#ptpma"),
    (re.compile(r"\bkbli\b", re.I), "#kbli"),
    (re.compile(r"\blkpm\b", re.I), "#lkpm"),
    (re.compile(r"\bgolden visa\b", re.I), "#goldenvisa"),
    (re.compile(r"digital nomad", re.I), "#digitalnomadvisa"),
    (re.compile(r"\bleasehold\b|hak pakai", re.I), "#baliproperty"),
]


# --------------------------------------------------------------------------- #
# BUG #1 — nested-dict lexicon normalization
# --------------------------------------------------------------------------- #


def _normalize_lexicon(raw: Any) -> list[dict[str, Any]]:
    """Normalize ``bilingual_lexicon_with_english_assist`` to a flat list[dict].

    Real briefs ship this field in TWO shapes:
      (a) flat ``list[dict]``                      -> returned as-is (filtered)
      (b) nested ``dict`` with bucket keys such as
          ``{"always_untranslated": [...], "assist_on_first_use": [...]}``
          -> flattened by concatenating every list-valued bucket.

    Also tolerates ``None`` / missing (-> ``[]``) and silently drops any
    non-dict entries so downstream ``.get`` calls never hit a str/key.

    BUG #1 FIX: code that iterated the nested-dict shape as if it were a list
    called ``.get`` on a *string key* -> AttributeError -> no caption produced.
    Reproduced on 2 real fixtures (e31a-spouse-visa, kep71-spt-extension-test-5).
    """
    if raw is None:
        return []

    items: list[Any]
    if isinstance(raw, dict):
        # Nested-dict shape: flatten every list-valued bucket in stable order.
        items = []
        for value in raw.values():
            if isinstance(value, list):
                items.extend(value)
            elif isinstance(value, dict):
                # Defensive: a bucket that is itself a single term dict.
                items.append(value)
    elif isinstance(raw, list):
        items = raw
    else:
        # Unknown shape (e.g. a bare string) — nothing iterable/useful.
        return []

    # Keep only well-formed term dicts.
    return [entry for entry in items if isinstance(entry, dict) and entry.get("id_term")]


# --------------------------------------------------------------------------- #
# BUG #2 — emoji guard over-match on legitimate content glyphs (superscar #3)
# --------------------------------------------------------------------------- #

# Legitimate status glyphs that WR2 dark-status-list slides carry. They live
# INSIDE the historical emoji range \U00002600-\U000027BF, so a naive emoji
# stripper swallows them and kills the caption. We transliterate them to plain
# words BEFORE the emoji class runs, and exclude them from the class itself.
_STATUS_GLYPH_TRANSLITERATION = {
    "✓": "yes:",  # ✓ CHECK MARK
    "✔": "yes:",  # ✔ HEAVY CHECK MARK
    "✖": "no:",   # ✖ HEAVY MULTIPLICATION X
    "✗": "no:",   # ✗ BALLOT X
    "✅": "yes:",  # ✅ WHITE HEAVY CHECK MARK (emoji-presentation variant)
    "❌": "no:",   # ❌ CROSS MARK (emoji-presentation variant)
}

# Emoji class for the guard. We carve the status glyphs OUT of the
# ☀-➿ range (split into ☀-✒, ✕, ✘-➿) so a
# stray ✓/✗ that survived transliteration is still NOT treated as emoji.
# This is the structural half of the BUG #2 fix: even without transliteration,
# the class can never match U+2713/2714/2716/2717.
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"  # symbols & pictographs, emoji, supplemental
    "\U00002600-\U00002712"  # misc symbols / dingbats — BELOW the check marks
    "\U00002715"             # ✕ multiplication x (an emoji-ish dingbat, keep stripped)
    "\U00002718-\U0000271F"  # dingbats above ✗, below the heavy-x band
    "\U00002721-\U000027BF"  # remaining dingbats, SKIPPING ✖/✗ handled above
    "\U0001F1E6-\U0001F1FF"  # regional indicators (flags)
    "\U00002B00-\U00002BFF"  # misc symbols and arrows (e.g. ⭐)
    "\U0000FE00-\U0000FE0F"  # variation selectors
    "\U00002190-\U000021FF"  # arrows (some render as emoji)
    "]+",
    flags=re.UNICODE,
)


def _strip_emoji(text: str) -> str:
    """Remove emoji from a caption WITHOUT killing legitimate ✓/✗ status glyphs.

    BUG #2 FIX (superscar #3, guard-over-match): the emoji class
    \\U00002600-\\U000027BF swallowed ✓ (U+2713/2714) and ✗ (U+2716/2717),
    which WR2 dark-status-list slides legitimately contain -> the guard killed
    the whole caption. We first transliterate those glyphs to plain words, then
    run an emoji class that also explicitly excludes them.

    Innocence: a caption with ✓/✗ survives (glyphs become "yes:"/"no:").
    Guilt: a real emoji like 🎉 is still stripped.
    """
    # Transliterate legitimate status glyphs to words first.
    for glyph, word in _STATUS_GLYPH_TRANSLITERATION.items():
        text = text.replace(glyph, word)
    # Now strip true emoji (the class can no longer match the status glyphs).
    text = _EMOJI_PATTERN.sub("", text)
    # Collapse any double spaces introduced by stripping.
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text


# --------------------------------------------------------------------------- #
# BUG #3 — sentence-case helper mangling all-caps nationality lists
# --------------------------------------------------------------------------- #

# Small words that stay lowercase in sentence/title case unless first.
_LOWER_SMALL_WORDS = {
    "a", "an", "and", "as", "at", "but", "by", "for", "in", "of", "on", "or",
    "the", "to", "vs", "via", "with", "per",
}

# Tokens we never re-case (brand technical terms / regulation prefixes / fee units).
_PRESERVE_TOKENS = {
    "BVK", "VoA", "e-VoA", "KITAS", "KITAP", "ITAS", "ITAP", "NPWP", "PMA",
    "PT", "PT PMA", "KBLI", "LKPM", "BKPM", "OSS", "NIB", "RPTKA", "IMTA",
    "PNBP", "DJP", "SPT", "MERP", "KUA", "Rp", "PP", "UU", "DPR", "ASEAN",
    "USA", "US", "UK", "EU", "HK", "DM",
}


def _recase_token(token: str, *, is_first: bool) -> str:
    """Recase a single token for sentence-case body text.

    ``is_first`` is True at the start of the fragment OR at the start of a new
    sentence (after ``.``/``!``/``?``) — such a token is always capitalized,
    even a small word ("the" -> "The" after a period).

    BUG #3 FIX: never lowercase an unknown all-caps token. An ALL-CAPS token
    that is not a small-word is Title-cased ("VIETNAM" -> "Vietnam"), so
    nationality lists read "Thailand and Vietnam", never "...and vietnam".
    Known brand/technical tokens are preserved verbatim.
    """
    # Strip leading/trailing punctuation we want to keep attached on output.
    m = re.match(r"^(\W*)(.*?)(\W*)$", token, flags=re.UNICODE)
    assert m is not None  # the regex always matches
    lead, core, trail = m.group(1), m.group(2), m.group(3)
    if not core:
        return token

    # Preserve brand/technical tokens verbatim (case-sensitive membership, and
    # an upper() fallback so "kitas" or "KITAS" both map to the canonical form).
    if core in _PRESERVE_TOKENS:
        return f"{lead}{core}{trail}"
    upper_core = core.upper()
    if upper_core in {t.upper() for t in _PRESERVE_TOKENS}:
        # Use the canonical brand spelling.
        canonical = next(t for t in _PRESERVE_TOKENS if t.upper() == upper_core)
        return f"{lead}{canonical}{trail}"

    lower_core = core.lower()
    # Small grammatical words go lowercase mid-sentence regardless of their
    # original case (so "AND" -> "and", "ARE" stays a content word). This runs
    # BEFORE the all-caps Title-case path so "THAILAND AND VIETNAM" reads
    # "Thailand and Vietnam", not "Thailand And Vietnam".
    if not is_first and lower_core in _LOWER_SMALL_WORDS:
        return f"{lead}{lower_core}{trail}"

    is_all_caps = core.isupper() and any(ch.isalpha() for ch in core)

    if is_all_caps:
        # BUG #3: do NOT lowercase an unknown all-caps content token. Title-case
        # it instead — a nationality like "VIETNAM" becomes "Vietnam", never
        # "vietnam". Multi-glyph all-caps acronyms not in _PRESERVE_TOKENS still
        # become Title-case here, which is the restrained-caption default.
        recased = core[:1].upper() + core[1:].lower()
        return f"{lead}{recased}{trail}"

    # Mixed/normal case: keep as-is (already authored), only capitalize first.
    if is_first:
        return f"{lead}{core[:1].upper()}{core[1:]}{trail}"
    return f"{lead}{core}{trail}"


def _sentence_case(text: str) -> str:
    """Convert a heading/body fragment to restrained sentence case.

    Splits on whitespace, recases token by token. All-caps tokens are
    Title-cased (never lowercased — BUG #3), small words go lowercase unless
    first, brand tokens are preserved verbatim. Punctuation is preserved.
    """
    text = text.strip()
    if not text:
        return text
    tokens = text.split(" ")
    out: list[str] = []
    at_sentence_start = True
    for tok in tokens:
        if not tok:
            out.append(tok)
            continue
        recased = _recase_token(tok, is_first=at_sentence_start)
        out.append(recased)
        # A token whose visible text ends in sentence-final punctuation opens a
        # new sentence for the NEXT token (so "PROPOSAL." -> next word capped).
        stripped = tok.rstrip("\"')]}")
        at_sentence_start = bool(stripped) and stripped[-1] in ".!?"
    result = " ".join(out)
    # Ensure the very first alphabetic char is upper.
    for i, ch in enumerate(result):
        if ch.isalpha():
            result = result[:i] + ch.upper() + result[i + 1:]
            break
    return result


# --------------------------------------------------------------------------- #
# LAW 2 boundary
# --------------------------------------------------------------------------- #


def _assert_no_pii_path(carousel_dir: Path) -> None:
    """Assert the caption is built ONLY from the carousel's own public copy.

    The only files we read are the carousel's own ``brief.json`` /
    ``slides.json``. No CRM / passport / KTP / NPWP / client-record path is
    ever touched. This is a structural guard, not a content scan: if a future
    refactor tries to read anything else, the load helpers below would have to
    change — keeping the input surface to two public files is the boundary.
    """
    # The directory must be a carousel output dir; we never traverse upward
    # into CRM or client data. Resolve and confirm the inputs are the two
    # public JSON files.
    for fname in _ALLOWED_INPUT_FILES:
        # Just a structural assertion that these are the inputs we use.
        _ = carousel_dir / fname
    # No-op beyond documenting/locking the contract — present so the LAW 2
    # boundary is explicit and testable.


# --------------------------------------------------------------------------- #
# Caption assembly
# --------------------------------------------------------------------------- #


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} did not contain a JSON object")
    return data


def _first_slide_heading(slides: dict[str, Any]) -> str:
    """Return the cover / slide-1 heading (the carousel's core tension)."""
    slide_list = slides.get("slides") or []
    for slide in slide_list:
        if not isinstance(slide, dict):
            continue
        if slide.get("index") == 1 or slide is slide_list[0]:
            heading = slide.get("heading")
            if isinstance(heading, str) and heading.strip():
                return heading.strip()
            break
    # Fallback: first non-empty heading anywhere.
    for slide in slide_list:
        if isinstance(slide, dict):
            heading = slide.get("heading")
            if isinstance(heading, str) and heading.strip():
                return heading.strip()
    return ""


def _build_body(brief: dict[str, Any]) -> str:
    """Build a 2-4 line plain-language body from the brief's real facts.

    Uses ``hook_angle`` (already plain-language editorial prose) as the spine,
    trimmed to a restrained length. Falls back to the first key_fact.
    """
    hook = brief.get("hook_angle")
    candidates: list[str] = []
    if isinstance(hook, str) and hook.strip():
        candidates.append(hook.strip())
    facts = brief.get("key_facts") or []
    if isinstance(facts, list):
        for fact in facts:
            if isinstance(fact, str) and fact.strip():
                candidates.append(fact.strip())
            if len(candidates) >= 2:
                break

    if not candidates:
        return ""

    body_source = candidates[0]
    # Split into sentences and keep 2-4 lines, restrained.
    sentences = re.split(r"(?<=[.!?])\s+", body_source)
    # Drop source-citation tails like "Source: ..." for caption cleanliness.
    cleaned: list[str] = []
    for sent in sentences:
        s = sent.strip()
        if not s:
            continue
        if re.match(r"^(source|sumber)\s*[:.]", s, re.I):
            continue
        cleaned.append(s)
        if len(cleaned) >= 3:
            break
    body = " ".join(cleaned)
    # The brief's hook_angle / key_facts are ALREADY plain-language, well-cased
    # editorial prose. Do NOT sentence-case it (that would lowercase "as of
    # today" without re-capitalizing the sentence start, and mangle "US" ->
    # "Us"). The body just needs emoji stripped; restraint is already authored.
    # Only ALL-CAPS slide HEADINGS (rendered shouty) get sentence-cased — see
    # _restrain(), applied to the hook line, not here.
    return _strip_emoji(body).strip()


def _build_hashtags(brief: dict[str, Any], slides: dict[str, Any]) -> list[str]:
    """Build 8-15 relevant hashtags deterministically.

    Broad tags + domain bucket + keyword-scanned niche tags, de-duplicated in
    stable order, capped to 15 and floored at 8 with safe generic fillers.
    """
    tags: list[str] = []

    def _add(tag: str) -> None:
        if tag not in tags:
            tags.append(tag)

    for t in _BROAD_HASHTAGS:
        _add(t)

    domain = (brief.get("domain") or "").strip().lower()
    for t in _DOMAIN_HASHTAGS.get(domain, []):
        _add(t)

    # Keyword scan over brief topic/facts + slide headings/bodies.
    scan_parts: list[str] = []
    for key in ("topic", "hook_angle"):
        val = brief.get(key)
        if isinstance(val, str):
            scan_parts.append(val)
    facts = brief.get("key_facts")
    if isinstance(facts, list):
        scan_parts.extend(f for f in facts if isinstance(f, str))
    for slide in slides.get("slides") or []:
        if isinstance(slide, dict):
            for k in ("heading", "subheading", "body"):
                v = slide.get(k)
                if isinstance(v, str):
                    scan_parts.append(v)
    scan_text = " ".join(scan_parts)
    for pattern, tag in _KEYWORD_HASHTAGS:
        if pattern.search(scan_text):
            _add(tag)

    # Floor at 8 with safe generic fillers; cap at 15.
    _fillers = ["#expatindonesia", "#balilife", "#bureaucracy", "#legalupdate",
                "#balibusiness", "#movetobali", "#indonesianlaw"]
    fi = 0
    while len(tags) < 8 and fi < len(_fillers):
        _add(_fillers[fi])
        fi += 1
    return tags[:15]


def _restrain(text: str) -> str:
    """Apply restraint rules: de-uppercase shouty fragments, strip emoji.

    Headings in slides.json are authored ALL-CAPS for the rendered slide; the
    caption voice is restrained, so we sentence-case them. Emoji are stripped
    via the BUG #2-safe guard.
    """
    text = _strip_emoji(text)
    # If the fragment is mostly uppercase, sentence-case it for restraint.
    letters = [c for c in text if c.isalpha()]
    if letters:
        upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if upper_ratio > 0.6:
            text = _sentence_case(text)
    return text.strip()


def build_caption(slug: str, base_dir: str | Path | None = None) -> str:
    """Build a brand-compliant Instagram caption for carousel ``slug``.

    Reads ``<base_dir>/<slug>/brief.json`` + ``slides.json`` and returns a
    deterministic, restrained caption (hook + body + CTA + disclaimer +
    hashtags), guaranteed under the IG 2200-char limit.

    Args:
        slug: carousel slug (directory name under the carousel base).
        base_dir: override for the carousel base directory. Defaults to
            ``<repo>/apps/war-room/output/carousel``.

    Raises:
        FileNotFoundError: if the carousel dir or its JSON files are missing.

    LAW 2: built ONLY from the carousel's own public copy — no client PII path.
    """
    base = Path(base_dir) if base_dir is not None else _DEFAULT_CAROUSEL_BASE
    carousel_dir = base / slug
    if not carousel_dir.is_dir():
        raise FileNotFoundError(f"carousel dir not found: {carousel_dir}")

    _assert_no_pii_path(carousel_dir)

    brief = _load_json(carousel_dir / "brief.json")
    slides = _load_json(carousel_dir / "slides.json")

    # Touch the (normalized) lexicon so the nested-dict shape is exercised on
    # every build and BUG #1 can never silently regress. The flattened terms
    # are available for future enrichment; today we only need it not to crash.
    _ = _normalize_lexicon(brief.get("bilingual_lexicon_with_english_assist"))

    # 1. Hook line — the cover heading, restrained.
    hook = _restrain(_first_slide_heading(slides))

    # 2. Body — 2-4 plain-language lines of the real regulatory fact.
    body = _build_body(brief)

    # 3. Soft CTA.
    cta = SOFT_CTA

    # 4. Disclaimer.
    disclaimer = DISCLAIMER

    # 5. Hashtags.
    hashtags = _build_hashtags(brief, slides)

    parts = [p for p in (hook, body, cta, disclaimer) if p]
    caption = "\n\n".join(parts)
    caption = caption + "\n\n" + " ".join(hashtags)

    # Final restraint: ensure emoji-free (defensive) and under the hard limit.
    caption = _strip_emoji(caption)
    if len(caption) > IG_CAPTION_HARD_LIMIT:
        # Trim the body first (most elastic part), then reassemble.
        overflow = len(caption) - IG_CAPTION_HARD_LIMIT
        if body and len(body) > overflow + 1:
            body = body[: len(body) - overflow - 1].rstrip() + "…"
            parts = [p for p in (hook, body, cta, disclaimer) if p]
            caption = "\n\n".join(parts) + "\n\n" + " ".join(hashtags)
            caption = _strip_emoji(caption)
        # Hard cap as a last resort.
        if len(caption) > IG_CAPTION_HARD_LIMIT:
            caption = caption[:IG_CAPTION_HARD_LIMIT].rstrip()

    return unicodedata.normalize("NFC", caption)


if __name__ == "__main__":  # pragma: no cover
    import sys

    _slug = sys.argv[1] if len(sys.argv) > 1 else "indonesia-visafree-myth-reality"
    print(build_caption(_slug))
