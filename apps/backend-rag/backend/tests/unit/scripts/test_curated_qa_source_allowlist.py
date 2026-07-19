"""Phase-0 safety rail (FATAL 5): PII source allowlist for the curated_qa
converter + harvester.

Guilt: any raw-log-derived path (meta_inbox_messages) is hard-refused, even
WITH an attestation. Any non-allowlisted path with NO attestation is
refused.
Innocence: paths inside data/curated_qa/ always pass with no attestation
needed; a non-allowlisted path WITH an attestation is accepted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.curated_qa_source_allowlist import (
    ALLOWED_SOURCE_ROOT,
    SourceAllowlistViolation,
    check_source_allowlist,
)


def test_allowed_root_is_data_curated_qa() -> None:
    assert ALLOWED_SOURCE_ROOT.name == "curated_qa"
    assert ALLOWED_SOURCE_ROOT.parent.name == "data"


# ── Innocence ────────────────────────────────────────────────────────────────


def test_path_inside_curated_qa_passes_without_attestation() -> None:
    inside = ALLOWED_SOURCE_ROOT / "some-batch.jsonl"
    result = check_source_allowlist([inside])
    assert result is None  # no exception raised — the pass/fail signal


def test_outside_path_with_attestation_passes(tmp_path: Path) -> None:
    outside = tmp_path / "E33-DEFINITIVE-CHATKB-2026-07-15.md"
    outside.write_text("content", encoding="utf-8")

    result = check_source_allowlist(
        [outside],
        source_attestation="E33 Second Home dossier, reviewed by Ari 2026-07-15",
    )
    assert result is None  # no exception raised — the pass/fail signal


# ── Guilt ────────────────────────────────────────────────────────────────────


def test_outside_path_without_attestation_is_refused(tmp_path: Path) -> None:
    outside = tmp_path / "some-external-file.jsonl"
    outside.write_text("content", encoding="utf-8")

    with pytest.raises(SourceAllowlistViolation, match="outside the allowlisted"):
        check_source_allowlist([outside])


def test_meta_inbox_messages_path_refused_even_with_attestation(tmp_path: Path) -> None:
    forbidden = tmp_path / "meta_inbox_messages_export.jsonl"
    forbidden.write_text("content", encoding="utf-8")

    with pytest.raises(SourceAllowlistViolation, match="forbidden raw-log-derived source"):
        check_source_allowlist(
            [forbidden],
            source_attestation="I reviewed it, I promise",
        )


def test_meta_inbox_messages_marker_is_case_insensitive(tmp_path: Path) -> None:
    forbidden = tmp_path / "META_INBOX_MESSAGES_dump.jsonl"
    forbidden.write_text("content", encoding="utf-8")

    with pytest.raises(SourceAllowlistViolation, match="forbidden raw-log-derived source"):
        check_source_allowlist([forbidden])


def test_one_bad_path_among_several_still_refuses_the_whole_batch(tmp_path: Path) -> None:
    good = ALLOWED_SOURCE_ROOT / "some-batch.jsonl"
    bad = tmp_path / "unattested.jsonl"
    bad.write_text("content", encoding="utf-8")

    with pytest.raises(SourceAllowlistViolation):
        check_source_allowlist([good, bad])
