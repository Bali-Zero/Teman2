"""Unit tests for WR2 critic_rubric (Phase 2.4 — 4 NB-7 PASS/FAIL gates + format + aggregate).

Tests cover gate1_primary_citation, gate2_notebook_consistency, gate3_disclaimer,
gate4_brand_voice_red_flags, format_check, and evaluate_rubric aggregate logic.
"""
from __future__ import annotations

from backend.services.war_room.critic_rubric import (
    EXPECTED_TEMPLATE_ID,
    GateStatus,
    RubricVerdict,
    evaluate_rubric,
    format_check,
    gate1_primary_citation,
    gate2_notebook_consistency,
    gate3_disclaimer,
    gate4_brand_voice_red_flags,
)

# -----------------------------------------------------------------------------
# Gate 1 — primary citation
# -----------------------------------------------------------------------------


def test_gate1_pass_when_regulatory_mention_has_citation() -> None:
    """PASS: slide with regulatory mention + [Fonte: UU 7/2021 Pasal 3]."""
    slides = [
        {
            "body": "Secondo UU 7/2021 Pasal 3 le aliquote sono. [Fonte: UU 7/2021 Pasal 3]",
            "text": "",
        }
    ]
    result = gate1_primary_citation(slides)
    assert result.status == GateStatus.PASS
    assert result.evidence["citations_found"] == 1


def test_gate1_retryable_fail_regulatory_without_fonte_format() -> None:
    """RETRYABLE_FAIL: regulatory mention 'UU 7/2021' without [Fonte: ...] format."""
    slides = [{"body": "Secondo UU 7/2021 le aliquote sono diverse.", "text": ""}]
    result = gate1_primary_citation(slides)
    assert result.status == GateStatus.RETRYABLE_FAIL
    assert any("regulatory mention without [Fonte" in iss for iss in result.issues)


def test_gate1_retryable_fail_numeric_claim_without_citation() -> None:
    """RETRYABLE_FAIL: numeric claim 'IDR 10 miliar' without citation."""
    slides = [{"body": "Investasi minima IDR 10 miliar per PMA.", "text": ""}]
    result = gate1_primary_citation(slides)
    assert result.status == GateStatus.RETRYABLE_FAIL
    assert any("numeric claim without citation" in iss for iss in result.issues)


def test_gate1_pass_when_no_regulatory_or_numeric_claims() -> None:
    """PASS: slide with no regulatory/numeric claims."""
    slides = [{"body": "Benvenuti al carosello informativo Bali Zero.", "text": ""}]
    result = gate1_primary_citation(slides)
    assert result.status == GateStatus.PASS
    assert result.evidence["citations_found"] == 0


def test_gate1_uses_text_field_when_body_missing() -> None:
    """gate1 reads `text` key when `body` absent — OR logic between body/text."""
    slides = [{"text": "UU 7/2021 dice cose. [Fonte: UU 7/2021 Pasal 3]"}]
    result = gate1_primary_citation(slides)
    assert result.status == GateStatus.PASS


# -----------------------------------------------------------------------------
# Gate 2 — notebook consistency
# -----------------------------------------------------------------------------


def test_gate2_pass_skipped_when_no_notebook_result() -> None:
    """PASS + skipped: when notebook_query_result=None."""
    result = gate2_notebook_consistency([], notebook_query_result=None)
    assert result.status == GateStatus.PASS
    assert result.evidence.get("skipped") is True


def test_gate2_pass_when_no_contradictions() -> None:
    """PASS: when notebook_query_result={'contradictions': []}."""
    result = gate2_notebook_consistency([], notebook_query_result={"contradictions": []})
    assert result.status == GateStatus.PASS
    assert result.evidence.get("nb_verified") is True


def test_gate2_retryable_fail_when_contradictions_present() -> None:
    """RETRYABLE_FAIL: when contradictions list non-empty."""
    result = gate2_notebook_consistency(
        [],
        notebook_query_result={"contradictions": ["aliquota errata", "scadenza errata"]},
    )
    assert result.status == GateStatus.RETRYABLE_FAIL
    assert result.evidence["contradiction_count"] == 2
    assert all("NB-7 contradiction" in iss for iss in result.issues)


# -----------------------------------------------------------------------------
# Gate 3 — disclaimer
# -----------------------------------------------------------------------------


def test_gate3_pass_with_informativo_generale() -> None:
    """PASS: last slide contains 'informativo generale'."""
    slides = [
        {"body": "intro", "text": ""},
        {"body": "Contenuto a scopo informativo generale, non costituisce consulenza.", "text": ""},
    ]
    result = gate3_disclaimer(slides)
    assert result.status == GateStatus.PASS
    assert "informativo generale" in result.evidence["matched_keywords"]


def test_gate3_pass_with_non_costituiscono_consulenza() -> None:
    """PASS: last slide contains 'non costituiscono consulenza'."""
    slides = [{"body": "Queste informazioni non costituiscono consulenza legale.", "text": ""}]
    result = gate3_disclaimer(slides)
    assert result.status == GateStatus.PASS


def test_gate3_fail_when_disclaimer_missing() -> None:
    """FAIL: last slide missing keywords."""
    slides = [{"body": "Per info contattaci a Bali Zero.", "text": ""}]
    result = gate3_disclaimer(slides)
    assert result.status == GateStatus.FAIL
    assert any("missing disclaimer" in iss for iss in result.issues)


def test_gate3_fail_on_empty_slides_list() -> None:
    """FAIL: empty slides list."""
    result = gate3_disclaimer([])
    assert result.status == GateStatus.FAIL
    assert any("no slides" in iss for iss in result.issues)


# -----------------------------------------------------------------------------
# Gate 4 — brand voice red flags (5 patterns)
# -----------------------------------------------------------------------------


def test_gate4_fail_on_hardcoded_bz_price() -> None:
    """FAIL on hardcoded BZ price ('IDR 5000000 Bali Zero visa setup')."""
    slides = [{"body": "Prezzo IDR 5000000 Bali Zero visa setup completo.", "text": ""}]
    result = gate4_brand_voice_red_flags(slides)
    assert result.status == GateStatus.FAIL
    assert any("hardcoded_bz_price" in iss for iss in result.issues)


def test_gate4_fail_on_guaranteed_timeline() -> None:
    """FAIL on guaranteed timeline ('garantiamo entro 30 giorni').

    NOTE: regex pattern requires (garant\\w+) (approv\\w+|entro|in) (\\d+) (gg|giorn|day|week)
    — only ONE token allowed between guarantee verb and number. So 'garantiamo entro 30 giorni'
    matches but 'garantiamo approvazione entro 30 giorni' does NOT (3 tokens between).
    """
    slides = [{"body": "Garantiamo entro 30 giorni lavorativi.", "text": ""}]
    result = gate4_brand_voice_red_flags(slides)
    assert result.status == GateStatus.FAIL
    assert any("guaranteed_timeline" in iss for iss in result.issues)


def test_gate4_fail_on_competitor_denigration() -> None:
    """FAIL on competitor denigration ('A differenza di FosterParrots, noi...')."""
    slides = [{"body": "A differenza di FosterParrots, noi offriamo più servizi.", "text": ""}]
    result = gate4_brand_voice_red_flags(slides)
    assert result.status == GateStatus.FAIL
    assert any("competitor_denigration" in iss for iss in result.issues)


def test_gate4_fail_on_political_opinion() -> None:
    """FAIL on political opinion ('governo indonesiano sbaglia su...')."""
    slides = [
        {
            "body": "Il governo indonesiano sbaglia su questa policy fiscale.",
            "text": "",
        }
    ]
    result = gate4_brand_voice_red_flags(slides)
    assert result.status == GateStatus.FAIL
    assert any("political_opinion" in iss for iss in result.issues)


def test_gate4_fail_on_banned_opening() -> None:
    """FAIL on banned opening ('In questo carosello vedremo...')."""
    slides = [{"body": "In questo carosello vedremo le novità fiscali.", "text": ""}]
    result = gate4_brand_voice_red_flags(slides)
    assert result.status == GateStatus.FAIL
    assert any("banned_opening" in iss for iss in result.issues)


def test_gate4_pass_on_clean_text() -> None:
    """PASS on clean text without any red flag."""
    slides = [
        {
            "body": "Le novità fiscali 2026 introducono modifiche all'imposta sui redditi.",
            "text": "",
        }
    ]
    result = gate4_brand_voice_red_flags(slides)
    assert result.status == GateStatus.PASS


# -----------------------------------------------------------------------------
# format_check
# -----------------------------------------------------------------------------


def test_format_check_pass_valid_slides_template_ratio() -> None:
    """PASS: 5-13 slides, template_id matches, ratio 4:5."""
    slides = [{"body": f"slide {i}", "text": ""} for i in range(8)]
    metadata = {"template_id": EXPECTED_TEMPLATE_ID, "ratio": "4:5"}
    result = format_check(slides, metadata)
    assert result.status == GateStatus.PASS
    assert result.evidence["slide_count"] == 8


def test_format_check_retryable_fail_below_min_slides() -> None:
    """RETRYABLE_FAIL: 4 slides (below min)."""
    slides = [{"body": f"s{i}", "text": ""} for i in range(4)]
    result = format_check(slides, {})
    assert result.status == GateStatus.RETRYABLE_FAIL
    assert any("slide count 4 outside" in iss for iss in result.issues)


def test_format_check_retryable_fail_above_max_slides() -> None:
    """RETRYABLE_FAIL: 14 slides (above max)."""
    slides = [{"body": f"s{i}", "text": ""} for i in range(14)]
    result = format_check(slides, {})
    assert result.status == GateStatus.RETRYABLE_FAIL
    assert any("slide count 14 outside" in iss for iss in result.issues)


def test_format_check_retryable_fail_wrong_template_id() -> None:
    """RETRYABLE_FAIL: wrong template_id."""
    slides = [{"body": f"s{i}", "text": ""} for i in range(8)]
    result = format_check(slides, {"template_id": "WRONG_ID_xyz"})
    assert result.status == GateStatus.RETRYABLE_FAIL
    assert any("template_id" in iss for iss in result.issues)


def test_format_check_retryable_fail_wrong_ratio() -> None:
    """RETRYABLE_FAIL: wrong ratio."""
    slides = [{"body": f"s{i}", "text": ""} for i in range(8)]
    result = format_check(slides, {"ratio": "16:9"})
    assert result.status == GateStatus.RETRYABLE_FAIL
    assert any("ratio" in iss for iss in result.issues)


def test_format_check_pass_metadata_none_only_count_check() -> None:
    """PASS: metadata None or empty (only count check)."""
    slides = [{"body": f"s{i}", "text": ""} for i in range(8)]
    result = format_check(slides, None)
    assert result.status == GateStatus.PASS
    result_empty = format_check(slides, {})
    assert result_empty.status == GateStatus.PASS


# -----------------------------------------------------------------------------
# evaluate_rubric aggregate
# -----------------------------------------------------------------------------


def _build_clean_slides(n: int = 8) -> list[dict]:
    """Helper — builds n slides that pass all gates."""
    slides = [
        {
            "body": f"Slide {i}: contenuto generico senza claim numerici o normativi.",
            "text": "",
        }
        for i in range(n - 1)
    ]
    slides.append(
        {
            "body": "Contenuto a scopo informativo generale, non costituisce consulenza fiscale.",
            "text": "",
        }
    )
    return slides


def test_evaluate_rubric_pass_when_all_gates_pass() -> None:
    """PASS when all gates PASS."""
    slides = _build_clean_slides(8)
    metadata = {"template_id": EXPECTED_TEMPLATE_ID, "ratio": "4:5"}
    verdict = evaluate_rubric(
        slides, metadata=metadata, notebook_query_result={"contradictions": []}
    )
    assert verdict.overall == GateStatus.PASS
    assert "PASS" in verdict.summary
    assert len(verdict.gates) == 5


def test_evaluate_rubric_fail_when_any_gate_fails() -> None:
    """FAIL when any gate FAIL (even if others RETRYABLE_FAIL)."""
    # Build slides with both a brand-voice FAIL (banned opening) AND a format
    # RETRYABLE_FAIL (3 slides — below min).
    slides = [
        {"body": "In questo carosello vedremo cose.", "text": ""},
        {"body": "slide 2", "text": ""},
        {"body": "non costituiscono consulenza", "text": ""},
    ]
    verdict = evaluate_rubric(slides, metadata={}, notebook_query_result={"contradictions": []})
    assert verdict.overall == GateStatus.FAIL
    assert "FAIL" in verdict.summary
    # Confirm both brand_voice FAIL + format RETRYABLE were observed
    statuses = {g.gate: g.status for g in verdict.gates}
    assert statuses["brand_voice"] == GateStatus.FAIL
    assert statuses["format"] == GateStatus.RETRYABLE_FAIL


def test_evaluate_rubric_retryable_fail_when_only_retryables() -> None:
    """RETRYABLE_FAIL when at least one RETRYABLE_FAIL and no FAIL."""
    # 3 slides (format RETRYABLE — below min) but disclaimer present + clean.
    slides = [
        {"body": "Intro slide normale.", "text": ""},
        {"body": "Contenuto qualsiasi.", "text": ""},
        {
            "body": "Contenuto a scopo informativo generale, non costituiscono consulenza.",
            "text": "",
        },
    ]
    verdict = evaluate_rubric(slides, metadata={}, notebook_query_result={"contradictions": []})
    assert verdict.overall == GateStatus.RETRYABLE_FAIL
    assert "RETRYABLE_FAIL" in verdict.summary


def test_evaluate_rubric_to_dict_output_structure() -> None:
    """to_dict() output includes verdict + gates + summary fields."""
    slides = _build_clean_slides(8)
    metadata = {"template_id": EXPECTED_TEMPLATE_ID, "ratio": "4:5"}
    verdict: RubricVerdict = evaluate_rubric(
        slides, metadata=metadata, notebook_query_result={"contradictions": []}
    )
    d = verdict.to_dict()
    assert "verdict" in d
    assert "gates" in d
    assert "summary" in d
    assert d["verdict"] == "PASS"
    assert isinstance(d["gates"], list) and len(d["gates"]) == 5
    for g in d["gates"]:
        assert {"gate", "status", "issues", "evidence"}.issubset(g.keys())
