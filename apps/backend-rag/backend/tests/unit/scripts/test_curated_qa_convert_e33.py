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
        synthetic_e33_file, domain="visa", lang="en", source_priority=80,
    )

    q1 = rows[0]
    assert "simplest route for a long stay" in q1["answer"]
    # INTERNAL reasoning must NEVER leak into the client-facing answer field.
    assert "primary regulator source" not in q1["answer"]
    assert "Banned phrasing" not in q1["answer"]


def test_extracts_confidence_class_per_question(synthetic_e33_file: Path) -> None:
    rows, _ = converter.parse_e33_markdown_file(
        synthetic_e33_file, domain="visa", lang="en", source_priority=80,
    )

    assert [r["confidence_class"] for r in rows] == [
        "BERSYARAT",
        "BELUM_DIATUR_PUBLIK",
        "KEBIJAKAN_PENYEDIA",
    ]


def test_emits_per_class_count_summary(synthetic_e33_file: Path) -> None:
    _, counts = converter.parse_e33_markdown_file(
        synthetic_e33_file, domain="visa", lang="en", source_priority=80,
    )

    assert counts == {"BERSYARAT": 1, "BELUM_DIATUR_PUBLIK": 1, "KEBIJAKAN_PENYEDIA": 1}


def test_extracts_law_refs_as_flat_string_list(synthetic_e33_file: Path) -> None:
    rows, _ = converter.parse_e33_markdown_file(
        synthetic_e33_file, domain="visa", lang="en", source_priority=80,
    )

    assert len(rows[0]["law_refs"]) == 2
    assert all(isinstance(ref, str) for ref in rows[0]["law_refs"])
    assert "E33 Visa Rumah Kedua" in rows[0]["law_refs"][0]
    assert rows[1]["law_refs"] == ["Permenkumham 22/2023, Pasal 56 (property-evidence provision)"]


def test_source_ref_anchors_to_filename_and_question_number(synthetic_e33_file: Path) -> None:
    rows, _ = converter.parse_e33_markdown_file(
        synthetic_e33_file, domain="visa", lang="en", source_priority=80,
    )

    assert rows[0]["source_ref"] == "E33-DEFINITIVE-CHATKB-2026-07-15.md#Q1"
    assert rows[1]["source_ref"] == "E33-DEFINITIVE-CHATKB-2026-07-15.md#Q2"
    assert rows[2]["source_ref"] == "E33-DEFINITIVE-CHATKB-2026-07-15.md#Q3"


def test_source_date_extracted_from_generated_header(synthetic_e33_file: Path) -> None:
    rows, _ = converter.parse_e33_markdown_file(
        synthetic_e33_file, domain="visa", lang="en", source_priority=80,
    )

    assert all(r["source_date"] == "2026-07-15" for r in rows)


def test_every_row_matches_the_shared_curated_qa_schema(synthetic_e33_file: Path) -> None:
    rows, _ = converter.parse_e33_markdown_file(
        synthetic_e33_file, domain="visa", lang="en", source_priority=80,
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
        }
        assert row["domain"] == "visa"
        assert row["lang"] == "en"
        assert row["source_priority"] == 80
        assert isinstance(row["answer"], str) and row["answer"]


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
        path, domain="visa", lang="en", source_priority=80, source_date_override="2026-07-15",
    )

    assert len(rows) == 1
    assert rows[0]["confidence_class"] == "SOME_NEW_CLASS"
    assert counts == {"SOME_NEW_CLASS": 1}


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
        path, domain="visa", lang="en", source_priority=80, source_date_override="2026-01-01",
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
