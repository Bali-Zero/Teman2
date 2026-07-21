"""SPEC v2 D3 (F1b): scripts/curated_qa_convert_e33.py

Three converter modes, all emitting the shared curated_qa JSONL schema
(apps/backend-rag/data/curated_qa/README.md):

1. Default: parses the "E33 DEFINITIVE CHATKB" markdown format (per-question
   blocks: ### Q<N>. <question> / **FINAL (client-facing):** / **CONFIDENCE:**
   / **INTERNAL:** / **CONFIRM IN WRITING:** / **LAW REFS (source-cited,
   unverified):**). The FIXTURE below is a SYNTHETIC 3-question snippet
   authored in the same format as the real
   ~/Desktop/E33-SecondHome/E33-DEFINITIVE-CHATKB-2026-07-15.md file — it is
   NOT copied real content (per build scope: the real file must not land in
   the repo in this build).
2. --golden-yaml: converts scripts/golden_answers_questions.yaml. That file
   is QUESTION-ONLY (no answer field) — golden answers live in Postgres, out
   of scope here — so every row gets answer=null.
3. --prewarm: converts the PREWARM_QUESTIONS dict imported from
   scripts/nlm_cache_prewarm.py. Also QUESTION-ONLY (answers come from a
   live NLM query, not a static corpus) — answer=null.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts import curated_qa_convert_e33 as converter

# ── Synthetic E33-format fixture (NOT copied real content) ─────────────────

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
- Permenkumham 22/2023, Pasal 56 (property-evidence provision)

## Section L. Questions for an Agent or Service Provider

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


# ── Default (E33 markdown) mode ─────────────────────────────────────────────


def test_parses_all_questions_in_the_fixture(synthetic_e33_file: Path) -> None:
    rows, counts = converter.parse_e33_markdown_file(
        synthetic_e33_file,
        domain="visa",
        lang="en",
        source_priority=80,
    )

    assert len(rows) == 3
    assert [r["question"] for r in rows] == [
        "Why choose the E33 visa over an investor KITAS?",
        "Is there a minimum age requirement?",
        "Will you provide written reminders for deadlines?",
    ]


def test_extracts_final_client_facing_answer_only(synthetic_e33_file: Path) -> None:
    rows, _ = converter.parse_e33_markdown_file(
        synthetic_e33_file,
        domain="visa",
        lang="en",
        source_priority=80,
    )

    q1 = rows[0]
    assert "simplest route for a long stay" in q1["answer"]
    # INTERNAL reasoning must NEVER leak into the client-facing answer field.
    assert "primary regulator source" not in q1["answer"]
    assert "Banned phrasing" not in q1["answer"]


def test_extracts_confidence_class_per_question(synthetic_e33_file: Path) -> None:
    rows, _ = converter.parse_e33_markdown_file(
        synthetic_e33_file,
        domain="visa",
        lang="en",
        source_priority=80,
    )

    assert [r["confidence_class"] for r in rows] == [
        "BERSYARAT",
        "BELUM_DIATUR_PUBLIK",
        "KEBIJAKAN_PENYEDIA",
    ]


def test_emits_per_class_count_summary(synthetic_e33_file: Path) -> None:
    _, counts = converter.parse_e33_markdown_file(
        synthetic_e33_file,
        domain="visa",
        lang="en",
        source_priority=80,
    )

    assert counts == {"BERSYARAT": 1, "BELUM_DIATUR_PUBLIK": 1, "KEBIJAKAN_PENYEDIA": 1}


# ── Compound CONFIDENCE tag degrade (Fable gate, 2026-07-19, Wave-3) ────────
# RULING: a compound CONFIDENCE tag (naming MORE THAN ONE of the 5 known
# classes) must DEGRADE to the least-promotable class at harvest — the
# verbatim-promotion gate only auto-serves pure JELAS. The original tag is
# preserved in `confidence_class_raw`, emitted ONLY when normalization
# actually changed the value (i.e. the degraded class differs from the
# FIRST class token listed in the tag).


def _confidence_fixture(tmp_path: Path, confidence_line: str) -> Path:
    path = tmp_path / "compound.md"
    path.write_text(
        "### Q1. Some question?\n\n"
        "**FINAL (client-facing):**\nSome answer.\n\n"
        f"**CONFIDENCE:** {confidence_line}\n\n"
        "**LAW REFS (source-cited, unverified):**\n- some ref\n",
        encoding="utf-8",
    )
    return path


def test_compound_confidence_tag_degrades_to_least_promotable_class(
    tmp_path: Path,
) -> None:
    path = _confidence_fixture(tmp_path, "JELAS (mechanics); BERSYARAT (eligibility)")

    rows, _ = converter.parse_e33_markdown_file(
        path, domain="visa", lang="en", source_priority=80, source_date_override="2026-07-19",
    )

    assert rows[0]["confidence_class"] == "BERSYARAT"
    assert rows[0]["confidence_class_raw"] == "JELAS (mechanics); BERSYARAT (eligibility)"


def test_slash_separated_compound_confidence_tag_degrades(tmp_path: Path) -> None:
    path = _confidence_fixture(tmp_path, "JELAS/BERSYARAT split")

    rows, _ = converter.parse_e33_markdown_file(
        path, domain="visa", lang="en", source_priority=80, source_date_override="2026-07-19",
    )

    assert rows[0]["confidence_class"] == "BERSYARAT"
    assert rows[0]["confidence_class_raw"] == "JELAS/BERSYARAT split"


def test_compound_confidence_tag_degrades_across_three_classes_to_lowest_rank(
    tmp_path: Path,
) -> None:
    path = _confidence_fixture(tmp_path, "BERSYARAT; BELUM_DIATUR_PUBLIK")

    rows, _ = converter.parse_e33_markdown_file(
        path, domain="visa", lang="en", source_priority=80, source_date_override="2026-07-19",
    )

    assert rows[0]["confidence_class"] == "BELUM_DIATUR_PUBLIK"
    assert rows[0]["confidence_class_raw"] == "BERSYARAT; BELUM_DIATUR_PUBLIK"


def test_pure_jelas_confidence_tag_stays_jelas_with_no_raw_field(tmp_path: Path) -> None:
    path = _confidence_fixture(tmp_path, "JELAS")

    rows, _ = converter.parse_e33_markdown_file(
        path, domain="visa", lang="en", source_priority=80, source_date_override="2026-07-19",
    )

    assert rows[0]["confidence_class"] == "JELAS"
    assert "confidence_class_raw" not in rows[0]


def test_pure_belum_diatur_publik_confidence_tag_unchanged(tmp_path: Path) -> None:
    path = _confidence_fixture(tmp_path, "BELUM_DIATUR_PUBLIK")

    rows, _ = converter.parse_e33_markdown_file(
        path, domain="visa", lang="en", source_priority=80, source_date_override="2026-07-19",
    )

    assert rows[0]["confidence_class"] == "BELUM_DIATUR_PUBLIK"
    assert "confidence_class_raw" not in rows[0]


def test_class_token_inside_prose_parentheses_around_same_leading_tag_does_not_emit_raw(
    tmp_path: Path,
) -> None:
    """A class token can appear a SECOND time inside descriptive prose
    around the SAME leading tag (e.g. explaining a condition under which a
    different class would apply). The scan finds both tokens, but the
    min-rank class already equals the leading/first-listed tag — nothing
    actually degraded, so confidence_class_raw must NOT be emitted even
    though 2 distinct tokens were found."""
    path = _confidence_fixture(tmp_path, "BERSYARAT (JELAS only after OSS confirmation)")

    rows, _ = converter.parse_e33_markdown_file(
        path, domain="visa", lang="en", source_priority=80, source_date_override="2026-07-19",
    )

    assert rows[0]["confidence_class"] == "BERSYARAT"
    assert "confidence_class_raw" not in rows[0]


def test_unrecognized_compound_looking_tag_falls_back_to_first_token_verbatim(
    tmp_path: Path,
) -> None:
    """0 known class tokens found (P7 principle, pre-existing behavior):
    the raw first whitespace-delimited token is kept verbatim, unchanged
    by the compound-degrade logic."""
    path = _confidence_fixture(tmp_path, "SOME_NEW_CLASS maybe-also-other")

    rows, _ = converter.parse_e33_markdown_file(
        path, domain="visa", lang="en", source_priority=80, source_date_override="2026-07-19",
    )

    assert rows[0]["confidence_class"] == "SOME_NEW_CLASS"
    assert "confidence_class_raw" not in rows[0]


def test_confidence_class_count_summary_counts_the_normalized_class(tmp_path: Path) -> None:
    """The per-class count summary must reflect the value that actually
    lands in confidence_class (i.e. the DEGRADED class) — the summary
    exists to catch anomalies in what gets harvested, not to audit raw
    dossier tags class-by-class."""
    path = _confidence_fixture(tmp_path, "JELAS (mechanics); BERSYARAT (eligibility)")

    _, counts = converter.parse_e33_markdown_file(
        path, domain="visa", lang="en", source_priority=80, source_date_override="2026-07-19",
    )

    assert counts == {"BERSYARAT": 1}


# ── Interaction: #2810 verbatim_eligible x #2856 compound-degrade ──────────
# These two Phase-0 rails were built on branches that diverged BEFORE either
# landed on main (PR #2810 cache-phase0-rails vs PR #2856 confidence-degrade)
# and were merged together 2026-07-20. The merge composes them (normalize
# runs first inside parse_e33_markdown_file, then the row-builder derives
# verbatim_eligible from the resulting `confidence_class` local) — this test
# pins that composition so a future refactor can't silently split them apart
# (e.g. by reading the un-normalized first-listed token instead).


def test_compound_confidence_tag_verbatim_eligible_uses_normalized_class(
    tmp_path: Path,
) -> None:
    """A compound tag "JELAS; BERSYARAT" degrades confidence_class to the
    lower-rank BERSYARAT (Wave-3 ruling). verbatim_eligible MUST reflect
    that NORMALIZED class — i.e. False, per the #2810 FATAL-3 rule that only
    pure JELAS rows are converter-side eligible — never True as it would be
    if verbatim_eligible were (incorrectly) derived from the raw tag's
    first-listed token (JELAS) instead of the post-degrade class."""
    path = _confidence_fixture(tmp_path, "JELAS; BERSYARAT")

    rows, _ = converter.parse_e33_markdown_file(
        path, domain="visa", lang="en", source_priority=80, source_date_override="2026-07-19",
    )

    assert rows[0]["confidence_class"] == "BERSYARAT"
    assert rows[0]["confidence_class_raw"] == "JELAS; BERSYARAT"
    assert rows[0]["verbatim_eligible"] is False
    assert rows[0]["client_specific"] is False


def test_extracts_law_refs_as_flat_string_list(synthetic_e33_file: Path) -> None:
    rows, _ = converter.parse_e33_markdown_file(
        synthetic_e33_file,
        domain="visa",
        lang="en",
        source_priority=80,
    )

    assert len(rows[0]["law_refs"]) == 2
    assert all(isinstance(ref, str) for ref in rows[0]["law_refs"])
    assert "E33 Visa Rumah Kedua" in rows[0]["law_refs"][0]
    assert rows[1]["law_refs"] == ["Permenkumham 22/2023, Pasal 56 (property-evidence provision)"]


def test_source_ref_anchors_to_filename_and_question_number(synthetic_e33_file: Path) -> None:
    rows, _ = converter.parse_e33_markdown_file(
        synthetic_e33_file,
        domain="visa",
        lang="en",
        source_priority=80,
    )

    assert rows[0]["source_ref"] == "E33-DEFINITIVE-CHATKB-2026-07-15.md#Q1"
    assert rows[1]["source_ref"] == "E33-DEFINITIVE-CHATKB-2026-07-15.md#Q2"
    assert rows[2]["source_ref"] == "E33-DEFINITIVE-CHATKB-2026-07-15.md#Q3"


def test_source_date_extracted_from_generated_header(synthetic_e33_file: Path) -> None:
    rows, _ = converter.parse_e33_markdown_file(
        synthetic_e33_file,
        domain="visa",
        lang="en",
        source_priority=80,
    )

    assert all(r["source_date"] == "2026-07-15" for r in rows)


def test_every_row_matches_the_shared_curated_qa_schema(synthetic_e33_file: Path) -> None:
    rows, _ = converter.parse_e33_markdown_file(
        synthetic_e33_file,
        domain="visa",
        lang="en",
        source_priority=80,
    )

    for row in rows:
        assert set(row.keys()) == {
            "question",
            "answer",
            "domain",
            "lang",
            "source_ref",
            "source_date",
            "confidence_class",
            "law_refs",
            "source_priority",
            "verbatim_eligible",
            "client_specific",
        }
        assert row["domain"] == "visa"
        assert row["lang"] == "en"
        assert row["source_priority"] == 80
        assert isinstance(row["answer"], str) and row["answer"]


def test_verbatim_eligible_true_only_for_jelas_class(synthetic_e33_file: Path) -> None:
    """The synthetic fixture has BERSYARAT/BELUM_DIATUR_PUBLIK/KEBIJAKAN_PENYEDIA
    rows — none JELAS — so verbatim_eligible must be False on all three (this
    is the converter's own best-effort value; the harvester re-derives it
    independently and never trusts this one)."""
    rows, _ = converter.parse_e33_markdown_file(
        synthetic_e33_file,
        domain="visa",
        lang="en",
        source_priority=80,
    )

    assert all(r["verbatim_eligible"] is False for r in rows)
    assert all(r["client_specific"] is False for r in rows)


def test_verbatim_eligible_true_for_jelas_row(tmp_path: Path) -> None:
    path = tmp_path / "jelas.md"
    path.write_text(
        "### Q1. Some settled question?\n\n"
        "**FINAL (client-facing):**\nA settled answer.\n\n"
        "**CONFIDENCE:** JELAS\n\n"
        "**LAW REFS (source-cited, unverified):**\n- ref\n",
        encoding="utf-8",
    )

    rows, _ = converter.parse_e33_markdown_file(
        path,
        domain="visa",
        lang="en",
        source_priority=80,
        source_date_override="2026-07-15",
    )

    assert rows[0]["verbatim_eligible"] is True
    assert rows[0]["client_specific"] is False


def test_unrecognized_confidence_class_is_kept_not_skipped(tmp_path: Path) -> None:
    """P7 principle applied here too: never silently drop a row — an
    unrecognized CONFIDENCE token must still produce a row, just counted
    under its own (unexpected) key so the summary surfaces the anomaly."""
    path = tmp_path / "weird.md"
    path.write_text(
        "### Q1. Some question?\n\n"
        "**FINAL (client-facing):**\nSome answer.\n\n"
        "**CONFIDENCE:** SOME_NEW_CLASS\n\n"
        "**INTERNAL:**\nreasoning\n\n"
        "**LAW REFS (source-cited, unverified):**\n- some ref\n",
        encoding="utf-8",
    )

    rows, counts = converter.parse_e33_markdown_file(
        path,
        domain="visa",
        lang="en",
        source_priority=80,
        source_date_override="2026-07-15",
    )

    assert len(rows) == 1
    assert rows[0]["confidence_class"] == "SOME_NEW_CLASS"
    assert counts == {"SOME_NEW_CLASS": 1}


def test_inline_final_answer_on_same_line_as_label_is_captured(tmp_path: Path) -> None:
    """Curated-cache cantiere postmortem (2026-07-19, Wave 1/2 dossiers):
    8 of 14 real dossiers write the answer INLINE, right after the label
    on the same physical line, rather than starting on the next line —
    e.g. `**FINAL (client-facing):** The standard rate is 22%...`. The
    original regex silently produced answer="" for every such row
    (162/272 rows across the cantiere) instead of raising — a quiet
    data-loss bug caught only downstream in curated_qa_review_pack.py's
    generated packs. This must never regress."""
    path = tmp_path / "inline.md"
    path.write_text(
        "### Q1. What corporate income tax rate applies?\n\n"
        "**FINAL (client-facing):** The standard rate is 22% of net taxable "
        "income, with two narrow carve-outs described below.\n\n"
        "**CONFIDENCE:** JELAS\n\n"
        "**INTERNAL:**\nSourced from DJP article, fetched 2026-07-19.\n\n"
        "**LAW REFS (source-cited, unverified):**\n- pajak.go.id/en/node/94054\n",
        encoding="utf-8",
    )

    rows, _ = converter.parse_e33_markdown_file(
        path, domain="tax", lang="en", source_priority=80, source_date_override="2026-07-19",
    )

    assert rows[0]["answer"] == (
        "The standard rate is 22% of net taxable income, with two narrow "
        "carve-outs described below."
    )


def test_bare_law_refs_label_without_qualifier_is_captured(tmp_path: Path) -> None:
    """Same postmortem: 9 of 14 real dossiers write `**LAW REFS:**` (no
    "(source-cited, unverified)" qualifier). The original regex required
    the qualifier literally, so every such row silently got law_refs=[]
    instead of the refs the dossier actually cited."""
    path = tmp_path / "bare-law-refs.md"
    path.write_text(
        "### Q1. Some question?\n\n"
        "**FINAL (client-facing):**\nSome answer.\n\n"
        "**CONFIDENCE:** JELAS\n\n"
        "**LAW REFS:**\n- UU PPh No. 36/2008 Pasal 17\n- Permenkumham 22/2023\n",
        encoding="utf-8",
    )

    rows, _ = converter.parse_e33_markdown_file(
        path, domain="tax", lang="en", source_priority=80, source_date_override="2026-07-19",
    )

    assert rows[0]["law_refs"] == [
        "UU PPh No. 36/2008 Pasal 17",
        "Permenkumham 22/2023",
    ]


def test_inline_final_and_bare_law_refs_combined_matches_real_dossier_shape(
    tmp_path: Path,
) -> None:
    """Both variants together — the actual shape of e.g.
    tax-corporate/FINAL-v2.md and company-compliance/FINAL.md in the
    curated-cache cantiere. Two questions to also confirm the LAW REFS
    block boundary (`(?=\\n### Q\\d+\\.|...)`) still stops at the next
    question header rather than swallowing it."""
    path = tmp_path / "real-shape.md"
    path.write_text(
        "### Q1. First question?\n\n"
        "**FINAL (client-facing):** Inline answer for Q1.\n\n"
        "**CONFIDENCE:** JELAS\n\n"
        "**LAW REFS:**\n- ref-for-q1\n\n"
        "---\n\n"
        "### Q2. Second question?\n\n"
        "**FINAL (client-facing):** Inline answer for Q2.\n\n"
        "**CONFIDENCE:** BERSYARAT\n\n"
        "**LAW REFS:**\n- ref-for-q2\n",
        encoding="utf-8",
    )

    rows, _ = converter.parse_e33_markdown_file(
        path, domain="tax", lang="en", source_priority=80, source_date_override="2026-07-19",
    )

    assert len(rows) == 2
    assert rows[0]["answer"] == "Inline answer for Q1."
    assert rows[0]["law_refs"] == ["ref-for-q1"]
    assert rows[1]["answer"] == "Inline answer for Q2."
    assert rows[1]["law_refs"] == ["ref-for-q2"]


def test_horizontal_rule_separator_is_not_mistaken_for_a_dash_bullet(
    tmp_path: Path,
) -> None:
    """A bare `---` markdown horizontal rule between Q blocks is common
    real-dossier formatting (visual separator before the next `### Q`).
    Confirmed live on all 5 originally-clean Wave 1/2 dossiers
    (visa-golden-investor, visa-business-multientry, visa-student,
    company-kbli-signed-lots — near-100% of rows; tax-pmk37 uses no `---`
    convention): the old per-line scan treated `stripped.startswith("-")`
    as a bullet, so `---` became a bogus `"--"` entry appended to almost
    every row's law_refs. Must be filtered, never emitted as a ref."""
    path = tmp_path / "hr-separator.md"
    path.write_text(
        "### Q1. Some question?\n\n"
        "**FINAL (client-facing):**\nSome answer.\n\n"
        "**CONFIDENCE:** JELAS\n\n"
        "**LAW REFS (source-cited, unverified):**\n"
        "- a real ref\n"
        "- another real ref\n\n"
        "---\n\n"
        "### Q2. Trailing question just to anchor the boundary?\n\n"
        "**FINAL (client-facing):**\nAnother answer.\n\n"
        "**CONFIDENCE:** JELAS\n\n"
        "**LAW REFS (source-cited, unverified):**\n- ref-2\n",
        encoding="utf-8",
    )

    rows, _ = converter.parse_e33_markdown_file(
        path, domain="visa", lang="en", source_priority=80, source_date_override="2026-07-19",
    )

    assert rows[0]["law_refs"] == ["a real ref", "another real ref"]
    assert "--" not in rows[0]["law_refs"]


def test_inline_semicolon_separated_law_refs_prose_is_split_into_discrete_refs(
    tmp_path: Path,
) -> None:
    """The tax-corporate/FINAL-v2.md real shape: `**LAW REFS:**` followed
    immediately by ONE prose sentence with semicolon-separated citations,
    no bullets at all. Must split into per-citation entries, matching the
    granularity the bulleted convention gives, not collapse to []."""
    path = tmp_path / "prose-law-refs.md"
    path.write_text(
        "### Q1. Some question?\n\n"
        "**FINAL (client-facing):** Some answer.\n\n"
        "**CONFIDENCE:** JELAS\n\n"
        "**LAW REFS:** UU PPh No. 36/2008 Pasal 17(1)(b); Pasal 17(2b) "
        "(19% public-company rate); Pasal 31E (small-turnover discount). "
        "Source: pajak.go.id/en/node/94054 (fetched 2026-07-19).\n",
        encoding="utf-8",
    )

    rows, _ = converter.parse_e33_markdown_file(
        path, domain="tax", lang="en", source_priority=80, source_date_override="2026-07-19",
    )

    assert rows[0]["law_refs"] == [
        "UU PPh No. 36/2008 Pasal 17(1)(b)",
        "Pasal 17(2b) (19% public-company rate)",
        "Pasal 31E (small-turnover discount). Source: pajak.go.id/en/node/94054 "
        "(fetched 2026-07-19).",
    ]


def test_hard_wrapped_multiline_law_refs_prose_is_rejoined_before_splitting(
    tmp_path: Path,
) -> None:
    """The visa-kitap/FINAL-v2.md real shape: inline prose LAW REFS whose
    physical lines are hard-wrapped (editor line width), not one bullet
    per line. Must rejoin wrapped lines into a continuous sentence before
    semicolon-splitting, not leave a stray line-break embedded mid-ref."""
    path = tmp_path / "wrapped-law-refs.md"
    path.write_text(
        "### Q1. Some question?\n\n"
        "**FINAL (client-facing):** Some answer.\n\n"
        "**CONFIDENCE:** JELAS\n\n"
        "**LAW REFS:** UU 6/2011 jo. UU 63/2024, Pasal 59 "
        "(https://www.imigrasi.go.id/uu_imigrasi/bab-5,\n"
        "fetched 2026-07-19); Permenkumham 22/2023 Pasal 184-185 (Golden "
        "Visa/investment).\n",
        encoding="utf-8",
    )

    rows, _ = converter.parse_e33_markdown_file(
        path, domain="visa", lang="en", source_priority=80, source_date_override="2026-07-19",
    )

    assert rows[0]["law_refs"] == [
        "UU 6/2011 jo. UU 63/2024, Pasal 59 "
        "(https://www.imigrasi.go.id/uu_imigrasi/bab-5, fetched 2026-07-19)",
        "Permenkumham 22/2023 Pasal 184-185 (Golden Visa/investment).",
    ]


def test_last_question_law_refs_do_not_swallow_trailing_document_sections(
    tmp_path: Path,
) -> None:
    """Real bug found live on 7 of 14 curated-cache cantiere Wave 1/2
    dossiers (company-compliance/FINAL.md Q20 being the clearest case):
    the LAST question's `block` runs to EOF, and real dossiers append
    document-level trailing sections after the last question — e.g.
    "## Self-check pass", "## Arbiter verification pass" — which are NOT
    spelled "## Section" (the only trailing-boundary spelling the old
    regex recognized). Before the fix, the last question's LAW REFS block
    engulfed those trailing sections whole, including any "- " bulleted
    line inside them — leaking INTERNAL-adjacent reviewer-facing text into
    curated_qa_review_pack.py packs. Any "## " heading must stop the
    capture, not just ones literally starting with "## Section"."""
    path = tmp_path / "trailing-sections.md"
    path.write_text(
        "### Q1. Last question in the file?\n\n"
        "**FINAL (client-facing):** Some answer.\n\n"
        "**CONFIDENCE:** JELAS\n\n"
        "**LAW REFS:** N/A (see other rows).\n\n"
        "---\n\n"
        "## Self-check pass\n\n"
        "- **Some internal note**: this must never appear in law_refs.\n"
        "- **Another internal note**: neither must this.\n\n"
        "## Arbiter verification pass (2026-07-19)\n\n"
        "More internal-only commentary that must not leak.\n",
        encoding="utf-8",
    )

    rows, _ = converter.parse_e33_markdown_file(
        path, domain="visa", lang="en", source_priority=80, source_date_override="2026-07-19",
    )

    assert len(rows) == 1
    assert rows[0]["law_refs"] == ["N/A (see other rows)."]
    joined = "; ".join(rows[0]["law_refs"])
    assert "internal note" not in joined
    assert "Arbiter verification" not in joined


def test_missing_generated_date_header_requires_explicit_source_date(tmp_path: Path) -> None:
    path = tmp_path / "no-header.md"
    path.write_text(
        "### Q1. Some question?\n\n"
        "**FINAL (client-facing):**\nSome answer.\n\n"
        "**CONFIDENCE:** JELAS\n\n"
        "**LAW REFS (source-cited, unverified):**\n- ref\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="source_date"):
        converter.parse_e33_markdown_file(path, domain="visa", lang="en", source_priority=80)


def test_explicit_source_date_overrides_missing_header(tmp_path: Path) -> None:
    path = tmp_path / "no-header.md"
    path.write_text(
        "### Q1. Some question?\n\n"
        "**FINAL (client-facing):**\nSome answer.\n\n"
        "**CONFIDENCE:** JELAS\n\n"
        "**LAW REFS (source-cited, unverified):**\n- ref\n",
        encoding="utf-8",
    )

    rows, _ = converter.parse_e33_markdown_file(
        path,
        domain="visa",
        lang="en",
        source_priority=80,
        source_date_override="2026-01-01",
    )

    assert rows[0]["source_date"] == "2026-01-01"


# ── --golden-yaml mode ───────────────────────────────────────────────────────


def test_golden_yaml_mode_produces_question_only_rows(tmp_path: Path) -> None:
    yaml_path = tmp_path / "golden_answers_questions.yaml"
    yaml_path.write_text(
        yaml.safe_dump(
            {
                "version": "1.0",
                "generated": "2026-04-06",
                "questions": [
                    {
                        "question": "What are the requirements for a B211A visa?",
                        "domain": "visa",
                        "nb_id": "abc-123",
                        "aliases": ["B211A requirements"],
                    },
                    {
                        "question": "What taxes apply to property transactions?",
                        "domain": "property",
                        "nb_id": "def-456",
                        "aliases": [],
                    },
                ],
            },
        ),
        encoding="utf-8",
    )

    rows = converter.convert_golden_yaml(yaml_path)

    assert len(rows) == 2
    assert rows[0]["question"] == "What are the requirements for a B211A visa?"
    assert rows[0]["domain"] == "visa"
    assert rows[1]["domain"] == "property"
    assert all(r["answer"] is None for r in rows)
    assert all(r["source_date"] == "2026-04-06" for r in rows)
    assert all(r["confidence_class"] == "UNSCORED" for r in rows)
    assert all(r["law_refs"] == [] for r in rows)
    assert all("golden_answers_questions.yaml" in r["source_ref"] for r in rows)
    assert all(r["verbatim_eligible"] is False for r in rows)  # no answer, never eligible
    assert all(r["client_specific"] is False for r in rows)


def test_golden_yaml_mode_matches_shared_schema(tmp_path: Path) -> None:
    yaml_path = tmp_path / "golden.yaml"
    yaml_path.write_text(
        yaml.safe_dump(
            {
                "generated": "2026-04-06",
                "questions": [{"question": "Q?", "domain": "tax", "nb_id": "x"}],
            },
        ),
        encoding="utf-8",
    )

    rows = converter.convert_golden_yaml(yaml_path)

    assert set(rows[0].keys()) == {
        "question",
        "answer",
        "domain",
        "lang",
        "source_ref",
        "source_date",
        "confidence_class",
        "law_refs",
        "source_priority",
        "verbatim_eligible",
        "client_specific",
    }


# ── --prewarm mode ───────────────────────────────────────────────────────────


def test_prewarm_mode_produces_question_only_rows() -> None:
    prewarm_questions = {
        "immigration": {
            "notebook_id": "84375bc3-12d0-4405-a774-9b89189d8c39",
            "questions": ["What are the KITAS requirements for 2026?", "How to renew a KITAS?"],
        },
        "property": {
            "notebook_id": "568ec624-ceb8-47d1-a2a2-5b2f793ea7ed",
            "questions": ["Can a foreigner buy property in Bali?"],
        },
    }

    rows = converter.convert_prewarm(prewarm_questions)

    assert len(rows) == 3
    assert all(r["answer"] is None for r in rows)
    assert all(r["confidence_class"] == "UNSCORED" for r in rows)
    assert all(r["verbatim_eligible"] is False for r in rows)  # no answer, never eligible
    assert all(r["client_specific"] is False for r in rows)
    assert {r["question"] for r in rows} == {
        "What are the KITAS requirements for 2026?",
        "How to renew a KITAS?",
        "Can a foreigner buy property in Bali?",
    }


def test_prewarm_mode_maps_immigration_domain_to_visa() -> None:
    prewarm_questions = {
        "immigration": {"notebook_id": "nb1", "questions": ["Q?"]},
    }

    rows = converter.convert_prewarm(prewarm_questions)

    assert rows[0]["domain"] == "visa"


def test_prewarm_mode_maps_company_domain_to_kbli() -> None:
    prewarm_questions = {"company": {"notebook_id": "nb1", "questions": ["Q?"]}}

    rows = converter.convert_prewarm(prewarm_questions)

    assert rows[0]["domain"] == "kbli"


def test_prewarm_mode_passes_through_tax_and_property_domains() -> None:
    prewarm_questions = {
        "tax": {"notebook_id": "nb1", "questions": ["Q1?"]},
        "property": {"notebook_id": "nb2", "questions": ["Q2?"]},
    }

    rows = converter.convert_prewarm(prewarm_questions)

    domains = {r["question"]: r["domain"] for r in rows}
    assert domains["Q1?"] == "tax"
    assert domains["Q2?"] == "property"


def test_prewarm_mode_maps_lifestyle_domain_to_default() -> None:
    prewarm_questions = {"lifestyle": {"notebook_id": "nb1", "questions": ["Q?"]}}

    rows = converter.convert_prewarm(prewarm_questions)

    assert rows[0]["domain"] == "default"


def test_prewarm_mode_matches_shared_schema() -> None:
    prewarm_questions = {"tax": {"notebook_id": "nb1", "questions": ["Q?"]}}

    rows = converter.convert_prewarm(prewarm_questions)

    assert set(rows[0].keys()) == {
        "question",
        "answer",
        "domain",
        "lang",
        "source_ref",
        "source_date",
        "confidence_class",
        "law_refs",
        "source_priority",
        "verbatim_eligible",
        "client_specific",
    }


def test_prewarm_mode_imports_real_prewarm_questions_dict() -> None:
    """Sanity check the module actually imports PREWARM_QUESTIONS from
    scripts/nlm_cache_prewarm.py per the spec (--prewarm mode 'imports it')."""
    from scripts.nlm_cache_prewarm import PREWARM_QUESTIONS

    rows = converter.convert_prewarm(PREWARM_QUESTIONS)

    assert len(rows) == sum(len(v["questions"]) for v in PREWARM_QUESTIONS.values())


# ── CLI wiring (I/O) ─────────────────────────────────────────────────────────


def test_write_jsonl_rows_produces_one_json_object_per_line(tmp_path: Path) -> None:
    rows = [
        {"question": "Q1", "answer": "A1"},
        {"question": "Q2", "answer": None},
    ]
    output = tmp_path / "out.jsonl"

    converter.write_jsonl_rows(rows, output)

    lines = output.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == rows[0]
    assert json.loads(lines[1]) == rows[1]
