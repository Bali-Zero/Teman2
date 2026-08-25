#!/usr/bin/env python3
"""cukup_jelas_signal — the campaign's §6 damage signal, as a reusable predicate.

Damage signal (MANDATE.md §6, measured 2026-08-25 by lane P): a point whose
`section` is not `penjelasan` AND whose text contains "Cukup jelas" —
elucidation/commentary sitting in an article slot.

This module holds ONLY the classification logic (no Qdrant import, no I/O), so
it can be imported by both the live measurement script
(`scripts/kb/cukup_jelas_sample.py`) and the CI regression test
(`apps/backend-rag/backend/tests/unit/kb/test_cukup_jelas_damage_signal.py`)
without either one restating the definition — a signal defined twice is a
signal that can quietly diverge from what it claims to measure.

Measured false-positive rate (lane P, 2026-08-25): 0/45 on a stratified sample
spanning 34 distinct documents (round-robin, not "first N found", seed
20260825) — see kb/inventory/_cukup_jelas_sample.json and
research/legal/2026-08-25-cukup-jelas-false-positive-rate.md for the full method
and the read-through of every sample. Every one of the 45 was genuinely
elucidation-style text (a bare "Cukup jelas." boilerplate note, a fuller
Penjelasan Pasal Demi Pasal explanation, or a "Tidak diberikan penjelasan,
karena cukup jelas" statement) — none was an innocent occurrence (a citation,
an unrelated preamble, ordinary prose using the words non-idiomatically). The
2,019-fragment / 34-document count this signal reports is NOT a fiction.
"""
from __future__ import annotations

import re
from typing import Any

CUKUP_JELAS = re.compile(r"cukup\s+jelas", re.IGNORECASE)


def get_section(payload: dict[str, Any]) -> str | None:
    """Top-level `section` wins; falls back to `metadata.section` (legacy shape)."""
    if payload.get("section"):
        return payload["section"]
    meta = payload.get("metadata")
    if isinstance(meta, dict) and meta.get("section"):
        return meta["section"]
    return None


def get_document_id(payload: dict[str, Any]) -> str:
    if payload.get("document_id"):
        return payload["document_id"]
    meta = payload.get("metadata")
    if isinstance(meta, dict) and meta.get("document_id"):
        return meta["document_id"]
    return "<none>"


def get_text(payload: dict[str, Any]) -> str:
    meta = payload.get("metadata")
    meta = meta if isinstance(meta, dict) else {}
    return payload.get("text") or payload.get("content") or meta.get("text") or ""


def is_unmarked_penjelasan_fragment(payload: dict[str, Any]) -> bool:
    """True iff this point is the §6 damage signal: contains "Cukup jelas" AND
    is not explicitly tagged `section: penjelasan`.

    This is deliberately a bare substring test (case-insensitive, whitespace-
    tolerant between the two words) — it is NOT smart about context. The
    2026-08-25 sampling measured that this crudeness does not cost precision
    in practice (0/45 false positives): in this corpus "cukup jelas" is used
    almost exclusively as elucidation boilerplate, not as ordinary prose.
    """
    if not CUKUP_JELAS.search(get_text(payload)):
        return False
    return get_section(payload) != "penjelasan"
