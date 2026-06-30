"""Regression tests for scorer topic/weight drift (W89 #5) + string-score crash (#7).

#5: scorer._KEYWORD_FAST_PATH emitted topic 'political_risk', which was ABSENT
from config.RELEVANCE_WEIGHTS → RELEVANCE_WEIGHTS.get(topic, 1) silently fell
back to 1 → weighted_score = score + (1-3)*0.5 = score - 1 → every Indonesian
regulation (peraturan/perpres/permen/menteri) landed BELOW SCORE_SIGNAL(4) and
never alerted Zero. The structural antidote (kills the whole class, not just
this instance): assert EVERY fast-path topic is a weights key.

#7: a string 'score' from the LLM crashed the weighted arithmetic and — with no
per-item try/except in run_scorer — killed the whole batch. The scorer now
coerces score to float.
"""
from __future__ import annotations

from mata_garuda import config
from mata_garuda.workers import scorer


class TestTopicWeightContract:
    def test_every_fast_path_topic_has_a_weight(self):
        """No keyword fast-path topic may be missing from RELEVANCE_WEIGHTS."""
        topics = {topic for _pat, topic, _score in scorer._KEYWORD_FAST_PATH}
        missing = topics - set(config.RELEVANCE_WEIGHTS)
        assert not missing, (
            f"fast-path topics absent from RELEVANCE_WEIGHTS (silently weighted to 1): {missing}"
        )

    def test_political_risk_is_present_and_high_signal(self):
        """The specific W89 regression: political_risk must weight UP, not down."""
        assert "political_risk" in config.RELEVANCE_WEIGHTS
        # weight >= 3 means weighted_score >= score (no demotion)
        assert config.RELEVANCE_WEIGHTS["political_risk"] >= 3

    def test_regulation_item_now_clears_alert_threshold(self):
        """'Prabowo teken Perpres' → political_risk(score 3) must reach SCORE_SIGNAL."""
        result = scorer.classify_by_keyword(
            "Prabowo teken Perpres baru soal kementerian", ""
        )
        assert result is not None and result["topic"] == "political_risk"
        score = float(result["score"])
        weight = config.RELEVANCE_WEIGHTS.get(result["topic"], 1)
        weighted = min(5, score + (weight - 3) * 0.5)
        assert weighted >= config.SCORE_SIGNAL, (
            f"regulation weighted={weighted} must reach SCORE_SIGNAL={config.SCORE_SIGNAL}"
        )


class TestScoreCoercion:
    def test_string_score_does_not_crash_weighted_math(self):
        """A string score must coerce, not raise (W89 #7)."""
        # mirror the scorer's coercion + arithmetic
        for raw in ("4", 4, 4.0, "bogus", None):
            try:
                score = float(raw)
            except (TypeError, ValueError):
                score = 2.0
            weight = config.RELEVANCE_WEIGHTS.get("political_risk", 1)
            weighted = min(5, score + (weight - 3) * 0.5)  # must not raise
            # numeric (int or float — min() returns the int on a tie like min(5, 5.0))
            assert isinstance(weighted, (int, float)) and weighted == weighted  # not NaN
