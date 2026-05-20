#!/usr/bin/env python3
"""WR3 Veo Tier 1 prompt normalizer — deterministic safety net.

Empirical 2026-05-20 (panel synthesis + discriminator probe):
Veo 3.1 Fast Tier 1 portrait silently rejects upstream on:
  - Style modifiers ("editorial documentary", "cinematic", "journalistic")
  - Sensitive content ("passport", "visa stamp")
  - Compound long prompts (>25w + style + location)

This module runs AS A LAST GATE before any Veo POST, even if the
shot-director + pre-render-gatekeeper agent contracts drift.

Public API:
  normalize_prompt(text) -> NormalizedPrompt
  enforce_tier1_safety(text) -> str (raises Tier1RejectError on hard-block)

Reference:
  research/operations/2026-05-20-wr3-veo-panel-synthesis.md
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

BANNED_STYLE_MODIFIERS = [
    r"\beditorial\s+documentary\b",
    r"\bdocumentary\b",
    r"\bcinematic\b",
    r"\beditorial\s+photography\s+aesthetic\b",
    r"\bjournalistic\b",
    r"\bpress\s+photography\b",
    r"\baward-winning\b",
    r"\bmagazine\s+cover\b",
    r"\bNational\s+Geographic\b",
]

CONTENT_REPLACEMENTS = [
    (re.compile(r"\bpassport\s+stamp\b", re.IGNORECASE), "seal on paper"),
    (re.compile(r"\bvisa\s+stamp\b", re.IGNORECASE), "seal on paper"),
    (re.compile(r"\bpassport\s+pages?\b", re.IGNORECASE), "official document pages"),
    (re.compile(r"\bpassport\b", re.IGNORECASE), "official document"),
    (re.compile(r"\bvisa\s+document\b", re.IGNORECASE), "official paperwork"),
    (re.compile(r"\bstamp\s+page\b", re.IGNORECASE), "paper page"),
    (re.compile(r"\bJakarta\b", re.IGNORECASE), "modern Southeast Asian"),
    (re.compile(r"\bDenpasar\b", re.IGNORECASE), "modern Southeast Asian"),
    (re.compile(r"\bSurabaya\b", re.IGNORECASE), "modern Southeast Asian"),
    (re.compile(r"\bMedan\b", re.IGNORECASE), "modern Southeast Asian"),
]

STYLE_PATTERN = re.compile("|".join(BANNED_STYLE_MODIFIERS), re.IGNORECASE)
WORD_CAP = 25


class Tier1RejectError(Exception):
    """Raised when a prompt cannot be made Tier 1 safe by normalization alone."""


@dataclass
class NormalizedPrompt:
    original: str
    normalized: str
    style_stripped: list[str] = field(default_factory=list)
    content_replaced: list[tuple[str, str]] = field(default_factory=list)
    word_count_original: int = 0
    word_count_normalized: int = 0
    needs_human_rewrite: bool = False
    reason: str | None = None


def _strip_style_modifiers(text: str) -> tuple[str, list[str]]:
    matches = [m.group(0) for m in STYLE_PATTERN.finditer(text)]
    cleaned = STYLE_PATTERN.sub("", text)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s*,\s*,", ",", cleaned)
    cleaned = re.sub(r"^[,\s]+|[,\s]+$", "", cleaned)
    return cleaned.strip(), matches


def _apply_content_replacements(text: str) -> tuple[str, list[tuple[str, str]]]:
    replacements: list[tuple[str, str]] = []
    out = text
    for pattern, replacement in CONTENT_REPLACEMENTS:
        new = pattern.sub(replacement, out)
        if new != out:
            replacements.append((pattern.pattern, replacement))
            out = new
    # Dedup consecutive duplicate adjectives ("modern modern Southeast Asian")
    out = re.sub(r"\b(\w+)(\s+\1\b)+", r"\1", out, flags=re.IGNORECASE)
    return out, replacements


def normalize_prompt(text: str) -> NormalizedPrompt:
    """Return a NormalizedPrompt. Does NOT raise — caller decides on `needs_human_rewrite`."""
    original = text
    wc_orig = len(text.split())

    stripped, style_matches = _strip_style_modifiers(text)
    replaced, content_replacements = _apply_content_replacements(stripped)
    wc_norm = len(replaced.split())

    needs_rewrite = False
    reason = None
    if wc_norm > WORD_CAP:
        needs_rewrite = True
        reason = f"word_count {wc_norm} > {WORD_CAP} after stripping (truncation would break grammar)"

    return NormalizedPrompt(
        original=original,
        normalized=replaced,
        style_stripped=style_matches,
        content_replaced=content_replacements,
        word_count_original=wc_orig,
        word_count_normalized=wc_norm,
        needs_human_rewrite=needs_rewrite,
        reason=reason,
    )


def enforce_tier1_safety(text: str) -> str:
    """Normalize + raise if not salvageable. Use this in clip-renderer pre-submit."""
    result = normalize_prompt(text)
    if result.needs_human_rewrite:
        raise Tier1RejectError(
            f"prompt cannot be auto-normalized: {result.reason}. "
            f"Original ({result.word_count_original}w): {result.original[:120]}..."
        )
    return result.normalized


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: wr3_prompt_normalizer.py '<prompt>'", file=sys.stderr)
        sys.exit(2)

    text = sys.argv[1]
    result = normalize_prompt(text)
    print(json.dumps({
        "original": result.original,
        "normalized": result.normalized,
        "style_stripped": result.style_stripped,
        "content_replaced": result.content_replaced,
        "word_count_original": result.word_count_original,
        "word_count_normalized": result.word_count_normalized,
        "needs_human_rewrite": result.needs_human_rewrite,
        "reason": result.reason,
    }, indent=2))
