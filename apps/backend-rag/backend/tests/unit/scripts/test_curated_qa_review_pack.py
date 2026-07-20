"""Curated-cache cantiere: scripts/curated_qa_review_pack.py

The review-pack generator splits a CHATKB dossier (same E33 markdown shape
the GARUDA visa corpus ships in) into simple per-reviewer .md/.html files
for non-technical Bali Zero staff to vet before promotion to the bot's
verbatim FAQ cache.

Coverage:
1. Parsing fidelity — the module reuses (never reimplements)
   scripts.curated_qa_convert_e33.parse_e33_markdown_file.
2. Batch-slug derivation from filename.
3. Round-robin assignment balance (overlap=1 and overlap>1).
4. INTERNAL-stripping guilt (never leaks) + innocence (FINAL text passes
   through byte-faithful).
5. Bahasa Indonesia (default lang=id) template rendering.
6. Manifest correctness.
7. PII/provenance rail (--source override gate).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import curated_qa_convert_e33 as converter
from scripts import curated_qa_review_pack as review_pack

# ── Synthetic E33-format fixture (NOT copied real content) ─────────────────
# Deliberately includes INTERNAL / banned-phrasing / confirm-in-writing
# content so the guilt test has something real to catch, and one question
# with an empty LAW REFS block so the "no refs" fallback text is exercised.

SYNTHETIC_E33_MARKDOWN = """# E33 Second Home Visa — Chat-LLM Knowledge Base

> **E33 Second Home Visa** · Bali Zero · generated 2026-07-15
> Full record for the chat-handling LLM.

---

## Section A. Eligibility & Suitability

### Q1. Why choose the E33 visa over an investor KITAS?

**FINAL (client-facing):**
E33 is the simplest route for a long stay without a company sponsoring you.
It requires a qualifying deposit and grants a long, renewable stay.

**CONFIDENCE:** BERSYARAT

**INTERNAL:**
Confidence: BERSYARAT — the core comparison is confirmed against the
primary regulator source, but some execution details remain open.

**Banned phrasing for this topic:** "approval guaranteed."
**Safe phrasing:** "eligible, subject to Imigrasi discretion."

**CONFIRM IN WRITING:**
- Whether splitting the deposit across two banks is permitted.
- The exact reporting procedure after arrival.

**LAW REFS (source-cited, unverified):**
- imigrasi.go.id — E33 Visa Rumah Kedua (https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E33)
- imigrasi.go.id — E28A Visa Investor (https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E28A)

### Q2. Is there a minimum age requirement?

**FINAL (client-facing):**
No specific minimum age is codified for the standard E33 visa. In practice
the applicant needs to be a legal adult to hold the qualifying deposit.

**CONFIDENCE:** BELUM_DIATUR_PUBLIK

**INTERNAL:**
No numeric min/max age is codified for the generic E33 in the regulation.

**CONFIRM IN WRITING:**
- Whether Imigrasi permits a minor as the principal applicant.

**LAW REFS (source-cited, unverified):**

### Q3. Will you provide written reminders for deadlines?

**FINAL (client-facing):**
Yes — Bali Zero sends milestone-based written reminders ahead of the
90-day deadline and extension windows, as a value-added service.

**CONFIDENCE:** KEBIJAKAN_PENYEDIA

**INTERNAL:**
Confidence: KEBIJAKAN_PENYEDIA — this is a service commitment, not a
government-mandated system.

**CONFIRM IN WRITING:**
- Exact reminder cadence and channels per the written engagement agreement.

**LAW REFS (source-cited, unverified):**
- UU No. 6/2011 tentang Keimigrasian, Pasal 71 (reporting obligations)
"""


@pytest.fixture
def synthetic_e33_file(tmp_path: Path) -> Path:
    path = tmp_path / "E33-DEFINITIVE-CHATKB-2026-07-15.md"
    path.write_text(SYNTHETIC_E33_MARKDOWN, encoding="utf-8")
    return path


def _make_rows(n: int) -> list[dict]:
    """Minimal synthetic curated_qa-shaped rows for pure assignment tests
    (no need to go through the markdown parser for these)."""
    return [
        {
            "question": f"Question {i}?",
            "answer": f"Answer {i}.",
            "domain": "visa",
            "lang": "id",
            "source_ref": f"fixture.md#Q{i}",
            "source_date": "2026-07-15",
            "confidence_class": "JELAS",
            "law_refs": [],
            "source_priority": 0,
        }
        for i in range(1, n + 1)
    ]


# ── 1. Parsing fidelity vs the converter's contract ─────────────────────────


def test_load_batches_delegates_to_converter_parser(synthetic_e33_file: Path) -> None:
    """The review-pack generator must not reimplement a second parser
    dialect — its rows must be identical to calling the converter directly
    (same domain/lang/source_priority)."""
    expected_rows, expected_counts = converter.parse_e33_markdown_file(
        synthetic_e33_file, domain="e33-2026-07-15", lang="id", source_priority=0,
    )

    [batch] = review_pack.load_batches(
        [synthetic_e33_file], lang="id", source_override=True, allowed_dir=synthetic_e33_file.parent,
    )

    assert batch.rows == expected_rows
    assert batch.confidence_counts == expected_counts


def test_load_batches_raises_on_empty_dossier(tmp_path: Path) -> None:
    empty = tmp_path / "EMPTY-DEFINITIVE-CHATKB-2026-07-15.md"
    empty.write_text("> generated 2026-07-15\n\nNo questions here.\n", encoding="utf-8")

    with pytest.raises(ValueError, match="zero questions"):
        review_pack.load_batches([empty], lang="id", source_override=True, allowed_dir=tmp_path)


# ── 2. Batch-slug derivation ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("filename", "expected_slug", "expected_title"),
    [
        ("E33-DEFINITIVE-CHATKB-2026-07-15.md", "e33-2026-07-15", "E33"),
        ("GARUDA-VOA-DEFINITIVE-CHATKB-2026-07-18.md", "garuda-voa-2026-07-18", "GARUDA VOA"),
        ("some_other_file.md", "some-other-file", "some other file"),
    ],
)
def test_derive_batch(filename: str, expected_slug: str, expected_title: str) -> None:
    slug, title = review_pack.derive_batch(Path(f"/x/{filename}"))
    assert slug == expected_slug
    assert title == expected_title


# ── 3+4. Round-robin assignment: balance + overlap ──────────────────────────


def test_round_robin_overlap_1_is_a_partition() -> None:
    rows = _make_rows(13)
    reviewers = [f"Reviewer {i}" for i in range(1, 7)]

    assignment = review_pack.assign_round_robin(rows, reviewers, overlap=1)

    all_assigned = [row["source_ref"] for rows_ in assignment.values() for row in rows_]
    assert sorted(all_assigned) == sorted(row["source_ref"] for row in rows)
    assert len(all_assigned) == len(rows)  # each row appears exactly once


def test_round_robin_overlap_1_is_balanced() -> None:
    rows = _make_rows(13)
    reviewers = [f"Reviewer {i}" for i in range(1, 7)]

    assignment = review_pack.assign_round_robin(rows, reviewers, overlap=1)

    counts = [len(v) for v in assignment.values()]
    assert max(counts) - min(counts) <= 1
    assert sum(counts) == 13


@pytest.mark.parametrize(("n", "reviewer_count", "overlap"), [(13, 6, 2), (20, 5, 3), (7, 4, 4), (1, 3, 1)])
def test_round_robin_overlap_n_balanced_and_distinct(n: int, reviewer_count: int, overlap: int) -> None:
    rows = _make_rows(n)
    reviewers = [f"Reviewer {i}" for i in range(1, reviewer_count + 1)]

    assignment = review_pack.assign_round_robin(rows, reviewers, overlap=overlap)

    counts = [len(v) for v in assignment.values()]
    assert max(counts) - min(counts) <= 1
    assert sum(counts) == n * overlap

    # Every row assigned to `overlap` DISTINCT reviewers.
    reviewer_sets_per_row: dict[str, set[str]] = {row["source_ref"]: set() for row in rows}
    for reviewer_name, assigned_rows in assignment.items():
        for row in assigned_rows:
            reviewer_sets_per_row[row["source_ref"]].add(reviewer_name)
    assert all(len(s) == overlap for s in reviewer_sets_per_row.values())


def test_round_robin_overlap_exceeding_reviewer_count_raises() -> None:
    rows = _make_rows(5)
    reviewers = ["A", "B", "C"]
    with pytest.raises(ValueError, match="overlap"):
        review_pack.assign_round_robin(rows, reviewers, overlap=4)


def test_round_robin_zero_overlap_raises() -> None:
    with pytest.raises(ValueError, match="overlap"):
        review_pack.assign_round_robin(_make_rows(3), ["A"], overlap=0)


def test_round_robin_zero_reviewers_raises() -> None:
    with pytest.raises(ValueError, match="reviewer"):
        review_pack.assign_round_robin(_make_rows(3), [], overlap=1)


# ── 5. INTERNAL-stripping: guilt + innocence ────────────────────────────────


def _build_single_pack(synthetic_e33_file: Path, *, lang: str = "id") -> tuple[str, str, list]:
    """Helper: parse the fixture, build one reviewer's md+html pack
    containing ALL rows, return (markdown, html, items)."""
    [batch] = review_pack.load_batches(
        [synthetic_e33_file], lang=lang, source_override=True, allowed_dir=synthetic_e33_file.parent,
    )
    items = [review_pack.row_to_item(row) for row in batch.rows]
    md = review_pack.render_markdown_pack(
        batch_title=batch.title,
        reviewer_name="Reviewer 1",
        items=items,
        lang=lang,
        generated_date="2026-07-19",
        deadline_date="2026-07-22",
    )
    html = review_pack.render_html_pack(
        batch_title=batch.title,
        reviewer_name="Reviewer 1",
        items=items,
        lang=lang,
        generated_date="2026-07-19",
        deadline_date="2026-07-22",
    )
    return md, html, items


def test_guilt_internal_reasoning_never_leaks_into_markdown(synthetic_e33_file: Path) -> None:
    md, _html, _items = _build_single_pack(synthetic_e33_file)

    assert "INTERNAL" not in md
    assert "Banned phrasing" not in md
    assert "primary regulator source" not in md
    assert "CONFIRM IN WRITING" not in md
    assert "splitting the deposit across two banks" not in md  # confirm-in-writing bullet


def test_guilt_internal_reasoning_never_leaks_into_html(synthetic_e33_file: Path) -> None:
    _md, html, _items = _build_single_pack(synthetic_e33_file)

    assert "INTERNAL" not in html
    assert "Banned phrasing" not in html
    assert "primary regulator source" not in html
    assert "CONFIRM IN WRITING" not in html
    assert "splitting the deposit across two banks" not in html


def test_innocence_final_answer_passes_through_byte_faithful_in_markdown(synthetic_e33_file: Path) -> None:
    md, _html, items = _build_single_pack(synthetic_e33_file)

    q1 = next(item for item in items if item.number == "1")
    assert q1.answer in md  # verbatim substring, no mangling


def test_innocence_final_answer_passes_through_byte_faithful_in_html(synthetic_e33_file: Path) -> None:
    _md, html, items = _build_single_pack(synthetic_e33_file)

    q1 = next(item for item in items if item.number == "1")
    # HTML-escapes for safety and turns newlines into <br> (matching the
    # renderer's own transform) but must not otherwise alter the text.
    import html as html_lib

    expected = html_lib.escape(q1.answer, quote=False).replace("\n", "<br>")
    assert expected in html


def test_law_refs_empty_falls_back_to_placeholder_text(synthetic_e33_file: Path) -> None:
    md, html, items = _build_single_pack(synthetic_e33_file)

    q2 = next(item for item in items if item.number == "2")
    assert q2.law_refs == []
    assert "Tidak ada referensi hukum tercatat" in md
    assert "Tidak ada referensi hukum tercatat" in html


# ── 6. Bahasa Indonesia template rendering ──────────────────────────────────


def test_bahasa_indonesia_is_the_default_lang() -> None:
    args = review_pack.parse_args(
        ["--input", "x.md", "--reviewers", "1", "--out-dir", "/tmp/out"],
    )
    assert args.lang == "id"


def test_bahasa_markdown_contains_expected_instructions_and_checkboxes(synthetic_e33_file: Path) -> None:
    md, _html, _items = _build_single_pack(synthetic_e33_file, lang="id")

    assert "Paket Review" in md
    assert "✅ BENAR" in md
    assert "❌ SALAH" in md
    assert "⚠️ RAGU" in md
    assert "harga TIDAK boleh muncul" in md
    assert "- [ ] ✅ BENAR" in md
    assert "Ringkasan" in md
    assert "Jumlah pertanyaan: 3" in md
    assert "Target kembali: 2026-07-22" in md


def test_bahasa_html_contains_checkbox_inputs_and_big_font_css(synthetic_e33_file: Path) -> None:
    _md, html, _items = _build_single_pack(synthetic_e33_file, lang="id")

    assert html.count('<input type="checkbox">') == 3 * 3  # 3 questions x 3 verdict options
    assert "font-size: 18px" in html or "font-size:18px" in html
    assert "<!doctype html>" in html.lower()
    assert "Paket Review" in html


def test_confidence_badge_translated_for_known_class_and_passthrough_for_unknown() -> None:
    assert review_pack._confidence_label("id", "JELAS") == "Pasti"
    assert review_pack._confidence_label("id", "BERSYARAT") == "Bersyarat"
    assert review_pack._confidence_label("id", "SOME_NEW_CLASS") == "SOME_NEW_CLASS"


# ── 7. Manifest correctness ──────────────────────────────────────────────


def test_manifest_structure_and_files_written(synthetic_e33_file: Path, tmp_path: Path) -> None:
    batches = review_pack.load_batches(
        [synthetic_e33_file], lang="id", source_override=True, allowed_dir=synthetic_e33_file.parent,
    )
    out_dir = tmp_path / "packs"

    manifest = review_pack.build_review_packs(
        batches=batches,
        reviewer_names=["Reviewer 1", "Reviewer 2"],
        overlap=1,
        lang="id",
        out_dir=out_dir,
        generated_date="2026-07-19",
        deadline_date="2026-07-22",
    )

    assert manifest["lang"] == "id"
    assert manifest["overlap"] == 1
    assert manifest["reviewers"] == ["Reviewer 1", "Reviewer 2"]
    assert len(manifest["batches"]) == 1

    entry = manifest["batches"][0]
    assert entry["batch_id"] == "e33-2026-07-15"
    assert entry["source_file"] == "E33-DEFINITIVE-CHATKB-2026-07-15.md"
    assert entry["total_questions"] == 3

    # every row assigned exactly once across the two reviewers (overlap=1)
    all_assigned = [ref for refs in entry["assignments"].values() for ref in refs]
    assert sorted(all_assigned) == [
        "E33-DEFINITIVE-CHATKB-2026-07-15.md#Q1",
        "E33-DEFINITIVE-CHATKB-2026-07-15.md#Q2",
        "E33-DEFINITIVE-CHATKB-2026-07-15.md#Q3",
    ]

    # files listed in the manifest actually exist on disk
    for reviewer_name, file_map in entry["files"].items():
        assert (out_dir / file_map["md"]).exists()
        assert (out_dir / file_map["html"]).exists()
        assert reviewer_name in entry["assignments"]

    # manifest itself must be JSON-serializable (no stray Path/dataclass objects)
    json.dumps(manifest)


def test_manifest_overlap_2_each_question_in_exactly_two_reviewer_lists(
    synthetic_e33_file: Path, tmp_path: Path,
) -> None:
    batches = review_pack.load_batches(
        [synthetic_e33_file], lang="id", source_override=True, allowed_dir=synthetic_e33_file.parent,
    )
    out_dir = tmp_path / "packs"

    manifest = review_pack.build_review_packs(
        batches=batches,
        reviewer_names=["Reviewer 1", "Reviewer 2", "Reviewer 3"],
        overlap=2,
        lang="id",
        out_dir=out_dir,
        generated_date="2026-07-19",
        deadline_date="2026-07-22",
    )

    entry = manifest["batches"][0]
    all_assigned = [ref for refs in entry["assignments"].values() for ref in refs]
    assert len(all_assigned) == 3 * 2
    from collections import Counter

    counts = Counter(all_assigned)
    assert all(count == 2 for count in counts.values())


# ── PII / provenance rail ────────────────────────────────────────────────


def test_validate_input_path_allows_inside_allowed_dir(tmp_path: Path) -> None:
    allowed = tmp_path / "data" / "curated_qa"
    allowed.mkdir(parents=True)
    f = allowed / "some-dossier.md"
    f.write_text("x", encoding="utf-8")

    result = review_pack.validate_input_path(f, source_override=False, allowed_dir=allowed)
    assert result is None  # does not raise; explicit assert for the anti-reward-hacking lint


def test_validate_input_path_refuses_outside_without_source(tmp_path: Path) -> None:
    allowed = tmp_path / "data" / "curated_qa"
    allowed.mkdir(parents=True)
    outside = tmp_path / "Desktop" / "dossier.md"
    outside.parent.mkdir(parents=True)
    outside.write_text("x", encoding="utf-8")

    with pytest.raises(review_pack.ReviewPackSourceError):
        review_pack.validate_input_path(outside, source_override=False, allowed_dir=allowed)


def test_validate_input_path_allows_outside_with_source_override(tmp_path: Path) -> None:
    allowed = tmp_path / "data" / "curated_qa"
    allowed.mkdir(parents=True)
    outside = tmp_path / "Desktop" / "dossier.md"
    outside.parent.mkdir(parents=True)
    outside.write_text("x", encoding="utf-8")

    result = review_pack.validate_input_path(outside, source_override=True, allowed_dir=allowed)
    assert result is None  # does not raise; explicit assert for the anti-reward-hacking lint


def test_validate_input_path_missing_file_raises_regardless_of_override(tmp_path: Path) -> None:
    missing = tmp_path / "nope.md"
    with pytest.raises(FileNotFoundError):
        review_pack.validate_input_path(missing, source_override=True, allowed_dir=tmp_path)


# ── Reviewer-name resolution ─────────────────────────────────────────────


def test_resolve_reviewer_names_from_count() -> None:
    names = review_pack.resolve_reviewer_names(reviewers=3, reviewers_file=None)
    assert names == ["Reviewer 1", "Reviewer 2", "Reviewer 3"]


def test_resolve_reviewer_names_from_file(tmp_path: Path) -> None:
    f = tmp_path / "names.txt"
    f.write_text("Surya\nAri\n\nAsya\n", encoding="utf-8")
    names = review_pack.resolve_reviewer_names(reviewers=None, reviewers_file=f)
    assert names == ["Surya", "Ari", "Asya"]


def test_resolve_reviewer_names_empty_file_raises(tmp_path: Path) -> None:
    f = tmp_path / "names.txt"
    f.write_text("\n\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no reviewer names"):
        review_pack.resolve_reviewer_names(reviewers=None, reviewers_file=f)


def test_resolve_reviewer_names_neither_given_raises() -> None:
    with pytest.raises(ValueError, match="reviewers"):
        review_pack.resolve_reviewer_names(reviewers=None, reviewers_file=None)


def test_resolve_reviewer_names_zero_raises() -> None:
    with pytest.raises(ValueError, match=">= 1"):
        review_pack.resolve_reviewer_names(reviewers=0, reviewers_file=None)
