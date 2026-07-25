#!/usr/bin/env python3
"""Contract tests for the multi-turn eval harness.

No network, no LLM. Pins the golden-set schema and the pure scoring
functions so a future edit cannot silently rot the four-outcome grading.

The load-bearing contract (explicit per the task mandate this harness was
built for): "a scenario that should ABSTAIN and does NOT must FAIL the run"
(guilt) AND "a correct answer is not scored as a failure by an over-eager
matcher" (innocence). Both are tested below for every outcome class, not
just ABSTAIN.
"""

from __future__ import annotations

from pathlib import Path

import multi_turn_eval as E

_GOLD = E._GOLDEN_FILE
_ZANTARA_CORE = (
    Path(__file__).resolve().parents[3]
    / "apps/backend-rag/backend/prompts/zantara_core.py"
)


# --------------------------------------------------------------------------- #
# Golden set schema                                                           #
# --------------------------------------------------------------------------- #
def test_golden_loads_and_covers_required_domains():
    data, scenarios = E.load_golden()
    assert data["embedding_model"] == E.FROZEN_EMBEDDING_MODEL
    assert data["embedding_dim"] == E.FROZEN_EMBEDDING_DIM
    domains = {s.domain for s in scenarios}
    for required in ("visa", "company", "tax", "property"):
        assert required in domains, f"missing domain {required}"
    ids = [s.id for s in scenarios]
    assert len(ids) == len(set(ids)), "duplicate scenario ids"


def test_golden_includes_all_four_outcome_classes():
    _, scenarios = E.load_golden()
    seen = set()
    for s in scenarios:
        for t in s.turns:
            seen.update(t.expected_outcomes)
    assert seen == E.VALID_OUTCOMES, f"golden set does not exercise all outcomes: {seen}"


def test_golden_includes_compound_and_ambiguous_and_no_grounding_scenarios():
    """The mandate requires: an ambiguous->CLARIFY turn, a no-grounding->
    ABSTAIN turn, a red-flag->ESCALATE turn, and a compound question. Pin
    that the golden set actually has all four so a future edit cannot
    silently drop one."""
    _, scenarios = E.load_golden()
    has_clarify = any(t.expected_outcomes == ["CLARIFY"] for s in scenarios for t in s.turns)
    has_abstain_no_grounding = any(
        t.expected_outcomes == ["ABSTAIN"] and not t.key_facts for s in scenarios for t in s.turns
    )
    has_escalate = any("ESCALATE" in t.expected_outcomes for s in scenarios for t in s.turns)
    has_compound = any("compound" in (s.notes or "").lower() for s in scenarios)
    assert has_clarify, "no pure-CLARIFY turn in the golden set"
    assert has_abstain_no_grounding, "no ungrounded ABSTAIN turn in the golden set"
    assert has_escalate, "no ESCALATE turn in the golden set"
    assert has_compound, "no compound-question scenario in the golden set"


def test_every_key_fact_has_a_source():
    """load_golden already raises on this; re-assert on the raw JSON as a
    second, independent check (anti-drift if load_golden's validation is
    ever weakened)."""
    import json

    raw = json.loads(_GOLD.read_text())
    for s in raw["scenarios"]:
        for t in s["turns"]:
            for kf in t.get("key_facts", []):
                assert kf.get("source", "").strip(), f"{s['id']} turn {t['turn']}: unsourced fact"


def test_golden_rejects_duplicate_ids(tmp_path):
    import json

    raw = json.loads(_GOLD.read_text())
    raw["scenarios"].append(raw["scenarios"][0])
    bad = tmp_path / "dup.json"
    bad.write_text(json.dumps(raw))
    try:
        E.load_golden(bad)
        raise AssertionError("expected ValueError on duplicate id")
    except ValueError as exc:
        assert "duplicate" in str(exc)


def test_golden_rejects_malformed_anchors(tmp_path):
    import json

    raw = json.loads(_GOLD.read_text())
    raw["scenarios"][0]["turns"][0]["key_facts"][0]["anchors"] = ["ok", 42]  # not all strings
    bad = tmp_path / "bad_anchors.json"
    bad.write_text(json.dumps(raw))
    try:
        E.load_golden(bad)
        raise AssertionError("expected ValueError on malformed anchors")
    except ValueError as exc:
        assert "anchors" in str(exc)


def test_golden_set_key_facts_anchors_are_literal_substrings_of_their_own_fact():
    """Anti-reward-hacking / anti-invention guard on the golden set itself:
    every anchor must be a literal (case-insensitive) substring of the SAME
    key_fact's ``fact`` prose — anchors are extracted from already-vetted
    text, never invented to make the coverage number look better."""
    _, scenarios = E.load_golden()
    for s in scenarios:
        for t in s.turns:
            for kf in t.key_facts:
                for a in kf.get("anchors") or []:
                    assert a.lower() in kf["fact"].lower(), (
                        f"{s.id} turn {t.turn}: anchor {a!r} is not a literal substring of its fact"
                    )


def test_golden_rejects_unknown_outcome(tmp_path):
    import json

    raw = json.loads(_GOLD.read_text())
    raw["scenarios"][0]["turns"][0]["expected_outcomes"] = ["MAYBE"]
    bad = tmp_path / "bad_outcome.json"
    bad.write_text(json.dumps(raw))
    try:
        E.load_golden(bad)
        raise AssertionError("expected ValueError on unknown outcome")
    except ValueError as exc:
        assert "unknown outcome" in str(exc)


# --------------------------------------------------------------------------- #
# ESCALATION_PROTOCOL anti-drift (mirrors rag_eval's grounded-source test)     #
# --------------------------------------------------------------------------- #
def test_escalation_phrases_are_grounded_in_the_live_prompt():
    """Anti-hallucination: every phrase this harness matches against must be
    grep-verifiable, verbatim, in the actual prompt file that defines the
    contract — never a phrase invented for the eval."""
    if not _ZANTARA_CORE.exists():
        return  # skip gracefully outside the full repo tree
    text = _ZANTARA_CORE.read_text(encoding="utf-8")
    for phrase in E.ESCALATION_PHRASES:
        assert phrase in text, f"phrase not found verbatim in zantara_core.py: {phrase!r}"


# --------------------------------------------------------------------------- #
# classify_outcome — structural signals                                       #
# --------------------------------------------------------------------------- #
def test_classify_abstain_structural_guilt():
    resp = {"answer": "Non ho trovato informazioni sufficienti.", "abstain": True, "abstain_reason": "no_relevant_context"}
    c = E.classify_outcome(resp)
    assert c.structural_outcome == "ABSTAIN"
    assert c.abstain_reason == "no_relevant_context"


def test_classify_escalate_marker_structural_guilt():
    resp = {"answer": "Ti metto in contatto col team. [ESCALATE]", "abstain": False}
    c = E.classify_outcome(resp)
    assert c.structural_outcome == "ESCALATE"
    assert c.escalate_marker_detected is True


def test_classify_send_innocence():
    """A normal, correct, content-bearing answer must classify as SEND —
    not as a false ABSTAIN/ESCALATE/CLARIFY."""
    resp = {
        "answer": (
            "The current KBLI 2025 code for a villa is 55203 (AKTIVITAS VILA). "
            "55193 is a legacy KBLI 2020 code, not the current one."
        ),
        "abstain": False,
    }
    c = E.classify_outcome(resp)
    assert c.structural_outcome == "SEND"
    assert c.escalate_marker_detected is False
    assert c.escalate_phrase_detected is False
    assert c.clarify_heuristic_detected is False


def test_classify_escalate_phrase_fallback_without_marker():
    resp = {"answer": "Let me check with the team and get back to you.", "abstain": False}
    c = E.classify_outcome(resp)
    assert c.structural_outcome == "SEND"  # marker absent -> structurally still SEND
    assert c.escalate_phrase_detected is True  # advisory fallback signal fires


def test_classify_escalate_phrase_innocence_generic_team_mention():
    """Guard-over-match regression test (cicatrix-superscar family #3): a
    normal sentence that happens to contain the word 'team' must NOT be
    misclassified as an escalation signal — only the full canonical phrase
    counts."""
    resp = {
        "answer": "Our team has helped over 500 clients set up their PT PMA in Bali.",
        "abstain": False,
    }
    c = E.classify_outcome(resp)
    assert c.escalate_phrase_detected is False
    assert c.structural_outcome == "SEND"


def test_classify_clarify_heuristic_detects_short_question():
    resp = {"answer": "Which visa type do you mean — tourist, retirement, or investor?", "abstain": False}
    c = E.classify_outcome(resp)
    assert c.clarify_heuristic_detected is True
    assert c.structural_outcome == "SEND"  # still no structural CLARIFY signal — documented gap


def test_classify_clarify_heuristic_innocence_long_substantive_answer():
    """A long, correct, content-bearing answer must not be flagged as a
    clarifying question just because SOME sentence inside it ends with a
    question mark far from the end, or because it is generally wordy."""
    resp = {
        "answer": (
            "The minimum paid-up capital for a PT PMA is IDR 2.5 billion under BKPM 5/2025 "
            "Article 26(10), with a 12-month lock-up period during which the capital cannot "
            "be withdrawn except for asset purchase, construction, or operating expenses. "
            "This replaced the previous IDR 10 billion baseline under the older regulation."
        ),
        "abstain": False,
    }
    c = E.classify_outcome(resp)
    assert c.clarify_heuristic_detected is False


def test_classify_clarify_heuristic_never_fires_alongside_abstain_or_escalate():
    resp_abstain = {"answer": "Not sure — can you clarify?", "abstain": True}
    c = E.classify_outcome(resp_abstain)
    assert c.clarify_heuristic_detected is False  # abstain wins, no double-signal

    resp_escalate = {"answer": "Let me connect you with the team, ok? [ESCALATE]", "abstain": False}
    c2 = E.classify_outcome(resp_escalate)
    assert c2.clarify_heuristic_detected is False


# --------------------------------------------------------------------------- #
# grade_turn                                                                   #
# --------------------------------------------------------------------------- #
def test_grade_turn_abstain_expected_but_got_send_is_a_hard_fail():
    """The mandate's explicit fixture requirement: a scenario that SHOULD
    abstain and does NOT must FAIL the run."""
    classification = E.classify_outcome({"answer": "Here is a confident, invented answer.", "abstain": False})
    verdict = E.grade_turn(["ABSTAIN"], classification)
    assert verdict is False


def test_grade_turn_send_expected_and_correct_is_a_pass_innocence():
    classification = E.classify_outcome({"answer": "55203 is the current KBLI 2025 villa code.", "abstain": False})
    verdict = E.grade_turn(["SEND"], classification)
    assert verdict is True


def test_grade_turn_send_expected_but_got_abstain_is_a_fail():
    classification = E.classify_outcome({"answer": "I don't know.", "abstain": True})
    verdict = E.grade_turn(["SEND"], classification)
    assert verdict is False


def test_grade_turn_clarify_expected_is_ungraded_not_silently_passed():
    classification = E.classify_outcome({"answer": "Which visa do you mean?", "abstain": False})
    verdict = E.grade_turn(["CLARIFY"], classification)
    assert verdict is None  # never a fake True/False


def test_grade_turn_escalate_expected_passes_via_marker():
    classification = E.classify_outcome({"answer": "Escalating now. [ESCALATE]", "abstain": False})
    verdict = E.grade_turn(["ESCALATE"], classification)
    assert verdict is True


def test_grade_turn_escalate_expected_passes_via_phrase_fallback():
    classification = E.classify_outcome(
        {"answer": "Ti metto in contatto col team per questo.", "abstain": False}
    )
    verdict = E.grade_turn(["ESCALATE"], classification)
    assert verdict is True


def test_grade_turn_escalate_expected_fails_when_neither_signal_present():
    classification = E.classify_outcome({"answer": "Here is a normal factual answer.", "abstain": False})
    verdict = E.grade_turn(["ESCALATE"], classification)
    assert verdict is False


def test_grade_turn_dual_acceptable_outcomes():
    """persona-payment-status-defer style: either ABSTAIN or ESCALATE is
    correct; SEND is not."""
    abstain_cls = E.classify_outcome({"answer": "I can't confirm your payment status.", "abstain": True})
    assert E.grade_turn(["ABSTAIN", "ESCALATE"], abstain_cls) is True

    send_cls = E.classify_outcome({"answer": "Yes, your payment was received on Monday.", "abstain": False})
    assert E.grade_turn(["ABSTAIN", "ESCALATE"], send_cls) is False


# --------------------------------------------------------------------------- #
# key_facts_coverage / must_not_assert_violations                             #
# --------------------------------------------------------------------------- #
def test_key_facts_coverage_full_and_partial_and_empty():
    facts = [{"fact": "55203", "source": "x"}, {"fact": "terbuka", "source": "x"}]
    hits, total, cov = E.key_facts_coverage("KBLI 55203 is TERBUKA for foreign ownership.", facts)
    assert (hits, total) == (2, 2)
    assert cov == 1.0

    hits, total, cov = E.key_facts_coverage("KBLI 55203 exists.", facts)
    assert (hits, total) == (1, 2)
    assert abs(cov - 0.5) < 1e-9

    hits, total, cov = E.key_facts_coverage("anything", [])
    assert (hits, total) == (0, 0)
    assert cov != cov  # NaN


def test_key_facts_coverage_no_anchors_falls_back_to_whole_string():
    """Backward compatibility (mandate requirement 3): a key_fact with no
    ``anchors`` key must fall back to the ORIGINAL whole-``fact``-string
    substring test — this is the same fixture shape test_key_facts_coverage_
    full_and_partial_and_empty already uses (no 'anchors' key at all), pinned
    here explicitly under the new anchor-aware name so a future edit that
    drops the fallback branch fails loudly and unambiguously."""
    facts = [{"fact": "the sky is blue", "source": "x"}]
    hits, total, cov = E.key_facts_coverage("Yes, the sky is blue today.", facts)
    assert (hits, total, cov) == (1, 1, 1.0)

    hits, total, cov = E.key_facts_coverage("It is sunny today.", facts)
    assert (hits, total, cov) == (0, 1, 0.0)


def test_key_facts_coverage_anchor_hit_on_realistic_paraphrase_never_containing_prose():
    """The bug this whole change fixes: golden `fact` values are full vetted
    prose sentences a live answer will never echo verbatim. This pins that
    an ANCHORED fact scores a HIT against a realistic paraphrased answer
    that does NOT contain the prose sentence at all — mirrors the real
    company-pma-capital-vs-investment#1 entry (anchors ANY-OF "2,500,000,000"
    / "2.5 billion")."""
    facts = [
        {
            "fact": (
                "Minimum paid-up capital (modal ditempatkan/disetor) for a PT PMA is IDR "
                "2,500,000,000 (2.5 billion), set by Permen BKPM 5/2025 Pasal 26(10) — this "
                "abrogated the previous IDR 10 billion baseline under Permen BKPM 4/2021."
            ),
            "source": "x",
            "anchors": ["2,500,000,000", "2.5 billion"],
        }
    ]
    # A realistic live-bot paraphrase: correct substance, zero verbatim overlap
    # with the vetted prose sentence above.
    answer = (
        "For a PT PMA, the minimum you need to put in as paid-up capital is IDR 2.5 billion "
        "under the current BKPM regulation, and that money is locked for a year before you "
        "can move it out of the company account."
    )
    assert facts[0]["fact"].lower() not in answer.lower(), "fixture must not contain the whole prose sentence"
    hits, total, cov = E.key_facts_coverage(answer, facts)
    assert (hits, total, cov) == (1, 1, 1.0)


def test_key_facts_coverage_anchor_miss_on_wrong_answer():
    """Innocence's mirror: a wrong/off-topic answer that never states any
    anchor of the fact must MISS — the anchor check must not be so loose it
    passes anything mentioning the general subject."""
    facts = [
        {
            "fact": "Minimum total investment must be greater than IDR 10,000,000,000 (10 billion) per KBLI code.",
            "source": "x",
            "anchors": ["10,000,000,000", "10 billion"],
        }
    ]
    wrong_answer = "The minimum paid-up capital for a PT PMA is IDR 2.5 billion, set by BKPM 5/2025."
    hits, total, cov = E.key_facts_coverage(wrong_answer, facts)
    assert (hits, total, cov) == (0, 1, 0.0)


def test_key_facts_coverage_anchor_any_of_not_all_of():
    """Documents/pins the chosen rule (ANY-OF, not ALL-OF): a fact with two
    alternative anchors (e.g. the two named current-route codes) must HIT
    when the answer contains only ONE of them — the source fact itself
    frames them as alternatives ('X or Y'), so requiring both would punish
    a correct answer for using just one valid phrasing."""
    facts = [
        {
            "fact": "The current short-stay business route is usually C2 Business or C12 Pre-Investment.",
            "source": "x",
            "anchors": ["C2 Business", "C12 Pre-Investment"],
        }
    ]
    hits, total, cov = E.key_facts_coverage("You'd want a C12 Pre-Investment visa for that.", facts)
    assert (hits, total, cov) == (1, 1, 1.0)


def test_must_not_assert_violations_detects_and_clears():
    forbidden = ["55193 is the current code"]
    bad = "For 2025, 55193 is the current code for villas."
    assert E.must_not_assert_violations(bad, forbidden) == forbidden
    good = "For 2025, 55203 is the current code for villas."
    assert E.must_not_assert_violations(good, forbidden) == []


# --------------------------------------------------------------------------- #
# conversation history builder                                                #
# --------------------------------------------------------------------------- #
def test_build_conversation_history_interleaves_oldest_first():
    prior = [("What is a KITAS?", "A KITAS is a residency permit."), ("How long does it last?", "It varies by category.")]
    history = E.build_conversation_history(prior)
    assert history == [
        {"role": "user", "content": "What is a KITAS?"},
        {"role": "assistant", "content": "A KITAS is a residency permit."},
        {"role": "user", "content": "How long does it last?"},
        {"role": "assistant", "content": "It varies by category."},
    ]


def test_build_conversation_history_empty_for_first_turn():
    assert E.build_conversation_history([]) == []


# --------------------------------------------------------------------------- #
# cost estimate                                                               #
# --------------------------------------------------------------------------- #
def test_estimate_cost_arithmetic():
    _, scenarios = E.load_golden()
    cost = E.estimate_cost(scenarios)
    total_turns = sum(len(s.turns) for s in scenarios)
    assert cost["turns"] == total_turns
    assert cost["estimated_llm_calls"] == total_turns * E.ESTIMATED_LLM_CALLS_PER_TURN


def test_estimate_cost_respects_prior_limit_slice():
    _, scenarios = E.load_golden()
    sliced = scenarios[:2]
    cost = E.estimate_cost(sliced)
    assert cost["scenarios"] == 2
    assert cost["turns"] == sum(len(s.turns) for s in sliced)


# --------------------------------------------------------------------------- #
# CLI --offline path (no network, exit 0)                                     #
# --------------------------------------------------------------------------- #
def test_main_offline_exits_zero(capsys):
    rc = E.main(["--offline"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "OFFLINE self-check PASSED" in out


def test_main_prod_without_confirm_is_refused(capsys):
    rc = E.main(["--prod"])
    assert rc == 2


def test_main_local_without_any_auth_header_is_needs_credential(monkeypatch, capsys):
    monkeypatch.delenv("AGENTIC_RAG_API_KEY", raising=False)
    monkeypatch.delenv("WA_MIRROR_INTERNAL_KEY", raising=False)
    monkeypatch.delenv("WA_INBOX_BOT_PROFILE_KEY", raising=False)
    rc = E.main(["--local"])
    assert rc == 3
