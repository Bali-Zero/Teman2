"""Tests for the Naga Action Engine.

Covers all deterministic trigger rules, trusted-mode stratification,
and edge cases.
"""

from __future__ import annotations

import pytest

from backend.core.claims.models import ClaimRecord
from backend.services.naga.actions.action_engine import ActionItem, detect_actions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_claim(
    *,
    claim_text: str = "Some claim",
    confidence_class: str = "VERIFIED",
    confidence_score: float = 0.85,
    geographic_scope: str = "NATIONAL",
    category: str = "LEGAL_CHANGE",
    claim_id: str = "c-001",
) -> ClaimRecord:
    """Factory for minimal ClaimRecord instances."""
    return ClaimRecord(
        claim_id=claim_id,
        claim_text=claim_text,
        category=category,
        confidence_class=confidence_class,
        confidence_score=confidence_score,
        source_ids=["src-1"],
        extracted="2026-04-03",
        geographic_scope=geographic_scope,
    )


# ---------------------------------------------------------------------------
# Rule 1: Client impact (VERIFIED + indonesia + impact keyword)
# ---------------------------------------------------------------------------


class TestClientImpact:
    """Rule 1: VERIFIED + Indonesia domain + impact keyword -> crm_alert + notify."""

    def test_client_impact_detected(self) -> None:
        """VERIFIED claim with 'fee' keyword -> crm_alert + notify."""
        claim = _make_claim(
            claim_text="New immigration fee increase effective January 2027",
            confidence_class="VERIFIED",
            geographic_scope="NATIONAL",
        )
        actions = detect_actions([claim])

        types = [a.action_type for a in actions]
        assert "crm_alert" in types
        assert "notify" in types
        assert len([a for a in actions if a.action_type == "crm_alert"]) == 1
        assert len([a for a in actions if a.action_type == "notify"]) == 1

    def test_client_impact_priority_is_high(self) -> None:
        """Both crm_alert and notify should be high priority."""
        claim = _make_claim(
            claim_text="Biaya KITAS berlaku mulai Februari",
            geographic_scope="LOCAL_BALI",
        )
        actions = detect_actions([claim])
        for action in actions:
            assert action.priority == "high"

    def test_client_impact_requires_verified(self) -> None:
        """PROVISIONAL claim with impact keywords should NOT trigger crm_alert."""
        claim = _make_claim(
            claim_text="New fee structure announced",
            confidence_class="PROVISIONAL",
            geographic_scope="NATIONAL",
        )
        actions = detect_actions([claim])
        types = [a.action_type for a in actions]
        assert "crm_alert" not in types
        assert "notify" not in types

    def test_client_impact_requires_indonesia_domain(self) -> None:
        """VERIFIED + impact keywords but non-Indonesia scope should NOT trigger."""
        claim = _make_claim(
            claim_text="New fee structure announced in Thailand",
            confidence_class="VERIFIED",
            geographic_scope="INTERNATIONAL",
        )
        actions = detect_actions([claim])
        types = [a.action_type for a in actions]
        assert "crm_alert" not in types

    def test_client_impact_local_bali_counts(self) -> None:
        """LOCAL_BALI geographic scope counts as Indonesia domain."""
        claim = _make_claim(
            claim_text="Tarif baru untuk izin tinggal",
            geographic_scope="LOCAL_BALI",
        )
        actions = detect_actions([claim])
        types = [a.action_type for a in actions]
        assert "crm_alert" in types

    def test_client_impact_indonesia_fallback_from_text(self) -> None:
        """When geographic_scope is empty, fall back to text keyword detection."""
        claim = _make_claim(
            claim_text="Indonesia imigrasi cost increased by 20%",
            geographic_scope="",
        )
        actions = detect_actions([claim])
        types = [a.action_type for a in actions]
        assert "crm_alert" in types


# ---------------------------------------------------------------------------
# Rule 2: Newsworthy (VERIFIED + news keyword)
# ---------------------------------------------------------------------------


class TestNewsworthy:
    """Rule 2: VERIFIED + news keyword -> draft_article."""

    def test_newsworthy_detected(self) -> None:
        """VERIFIED claim with 'new regulation' -> draft_article."""
        claim = _make_claim(
            claim_text="New regulation on foreign worker permits announced",
            confidence_class="VERIFIED",
        )
        actions = detect_actions([claim])
        types = [a.action_type for a in actions]
        assert "draft_article" in types

    def test_newsworthy_golden_visa(self) -> None:
        """Golden visa keyword triggers draft_article."""
        claim = _make_claim(
            claim_text="Indonesia golden visa program launched for investors",
        )
        actions = detect_actions([claim])
        draft_actions = [a for a in actions if a.action_type == "draft_article"]
        assert len(draft_actions) >= 1

    def test_newsworthy_requires_verified(self) -> None:
        """LOW confidence claim with news keywords should NOT trigger draft_article."""
        claim = _make_claim(
            claim_text="New regulation rumored for 2027",
            confidence_class="LOW",
            confidence_score=0.3,
        )
        actions = detect_actions([claim])
        types = [a.action_type for a in actions]
        assert "draft_article" not in types


# ---------------------------------------------------------------------------
# Rule 3: Contested regulation (LOW + indonesia)
# ---------------------------------------------------------------------------


class TestContestedEscalation:
    """Rule 3: LOW confidence + Indonesia domain -> escalation."""

    def test_contested_escalation(self) -> None:
        """LOW confidence + indonesia -> escalation."""
        claim = _make_claim(
            claim_text="Unclear regulation about property ownership",
            confidence_class="LOW",
            confidence_score=0.3,
            geographic_scope="NATIONAL",
        )
        actions = detect_actions([claim])
        types = [a.action_type for a in actions]
        assert "escalation" in types

    def test_contested_escalation_is_auto(self) -> None:
        """Escalation actions should always be auto_execute=True."""
        claim = _make_claim(
            claim_text="Unclear KITAS policy change",
            confidence_class="LOW",
            confidence_score=0.4,
            geographic_scope="LOCAL_BALI",
        )
        actions = detect_actions([claim], trusted_mode=False)
        esc = [a for a in actions if a.action_type == "escalation"]
        assert len(esc) == 1
        assert esc[0].auto_execute is True

    def test_contested_requires_low_confidence(self) -> None:
        """VERIFIED claims should NOT trigger escalation."""
        claim = _make_claim(
            claim_text="Unclear regulation about property ownership",
            confidence_class="VERIFIED",
            geographic_scope="NATIONAL",
        )
        actions = detect_actions([claim])
        types = [a.action_type for a in actions]
        assert "escalation" not in types


# ---------------------------------------------------------------------------
# Rule 4: Critical gap (regulation / normativa in gaps)
# ---------------------------------------------------------------------------


class TestGapFollowup:
    """Rule 4: gaps containing 'regulation' or 'normativa' -> followup."""

    def test_gap_followup(self) -> None:
        """Gap with 'regulation' keyword triggers followup."""
        actions = detect_actions([], gaps=["Missing regulation on digital nomad visa"])
        types = [a.action_type for a in actions]
        assert "followup" in types

    def test_gap_normativa_followup(self) -> None:
        """Gap with 'normativa' keyword triggers followup."""
        actions = detect_actions([], gaps=["Normativa non chiara sulle tasse"])
        followups = [a for a in actions if a.action_type == "followup"]
        assert len(followups) == 1

    def test_gap_without_keywords_no_followup(self) -> None:
        """Gap without regulation/normativa should NOT trigger followup."""
        actions = detect_actions([], gaps=["Outdated pricing information"])
        types = [a.action_type for a in actions]
        assert "followup" not in types


# ---------------------------------------------------------------------------
# Trusted mode stratification
# ---------------------------------------------------------------------------


class TestTrustedMode:
    """Verify auto_execute stratification by action type and trusted_mode."""

    def test_trusted_mode_affects_draft(self) -> None:
        """trusted_mode=True -> draft_article auto_execute=True."""
        claim = _make_claim(
            claim_text="New regulation on company formation",
            confidence_class="VERIFIED",
        )
        actions = detect_actions([claim], trusted_mode=True)
        drafts = [a for a in actions if a.action_type == "draft_article"]
        assert len(drafts) == 1
        assert drafts[0].auto_execute is True

    def test_untrusted_mode_draft_not_auto(self) -> None:
        """trusted_mode=False -> draft_article auto_execute=False."""
        claim = _make_claim(
            claim_text="New regulation on company formation",
            confidence_class="VERIFIED",
        )
        actions = detect_actions([claim], trusted_mode=False)
        drafts = [a for a in actions if a.action_type == "draft_article"]
        assert len(drafts) == 1
        assert drafts[0].auto_execute is False

    def test_notify_always_auto(self) -> None:
        """Notify should be auto_execute=True regardless of trusted_mode."""
        claim = _make_claim(
            claim_text="New immigration fee berlaku next month",
            geographic_scope="NATIONAL",
        )
        # trusted_mode=False
        actions_untrusted = detect_actions([claim], trusted_mode=False)
        notifs = [a for a in actions_untrusted if a.action_type == "notify"]
        assert len(notifs) >= 1
        for n in notifs:
            assert n.auto_execute is True

        # trusted_mode=True
        actions_trusted = detect_actions([claim], trusted_mode=True)
        notifs_t = [a for a in actions_trusted if a.action_type == "notify"]
        assert len(notifs_t) >= 1
        for n in notifs_t:
            assert n.auto_execute is True

    def test_crm_alert_never_auto(self) -> None:
        """CRM alert should be auto_execute=False regardless of trusted_mode."""
        claim = _make_claim(
            claim_text="Deadline for visa renewal changed",
            geographic_scope="NATIONAL",
        )
        # trusted_mode=True
        actions = detect_actions([claim], trusted_mode=True)
        alerts = [a for a in actions if a.action_type == "crm_alert"]
        assert len(alerts) >= 1
        for a in alerts:
            assert a.auto_execute is False

        # trusted_mode=False
        actions_f = detect_actions([claim], trusted_mode=False)
        alerts_f = [a for a in actions_f if a.action_type == "crm_alert"]
        assert len(alerts_f) >= 1
        for a in alerts_f:
            assert a.auto_execute is False

    def test_escalation_always_auto(self) -> None:
        """Escalation should be auto_execute=True regardless of trusted_mode."""
        claim = _make_claim(
            claim_text="Unclear tax rule in Indonesia",
            confidence_class="LOW",
            confidence_score=0.3,
        )
        for mode in (True, False):
            actions = detect_actions([claim], trusted_mode=mode)
            escs = [a for a in actions if a.action_type == "escalation"]
            assert len(escs) >= 1
            for e in escs:
                assert e.auto_execute is True

    def test_followup_respects_trusted_mode(self) -> None:
        """Followup auto_execute should match trusted_mode."""
        gaps = ["Missing regulation on work permits"]
        actions_t = detect_actions([], trusted_mode=True, gaps=gaps)
        fu_t = [a for a in actions_t if a.action_type == "followup"]
        assert fu_t[0].auto_execute is True

        actions_f = detect_actions([], trusted_mode=False, gaps=gaps)
        fu_f = [a for a in actions_f if a.action_type == "followup"]
        assert fu_f[0].auto_execute is False


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and empty-input handling."""

    def test_no_triggers_returns_empty(self) -> None:
        """Non-triggering claims should produce an empty list."""
        claim = _make_claim(
            claim_text="The weather in Bali is pleasant year-round",
            confidence_class="PROVISIONAL",
            confidence_score=0.65,
            geographic_scope="INTERNATIONAL",
        )
        actions = detect_actions([claim])
        assert actions == []

    def test_empty_claims_returns_empty(self) -> None:
        """Empty claims list with no gaps should return empty."""
        actions = detect_actions([])
        assert actions == []

    def test_multiple_claims_produce_multiple_actions(self) -> None:
        """Multiple triggering claims should each produce their actions."""
        claims = [
            _make_claim(
                claim_id="c-001",
                claim_text="New immigration fee effective next quarter",
                geographic_scope="NATIONAL",
            ),
            _make_claim(
                claim_id="c-002",
                claim_text="New regulation on golden visa requirements",
            ),
        ]
        actions = detect_actions(claims)
        types = [a.action_type for a in actions]
        # c-001 triggers crm_alert + notify (impact), c-002 triggers draft_article (news)
        assert "crm_alert" in types
        assert "notify" in types
        assert "draft_article" in types

    def test_actions_sorted_by_priority(self) -> None:
        """Actions should be sorted: high before medium."""
        claims = [
            _make_claim(
                claim_id="c-001",
                claim_text="New regulation announced by government",
                confidence_class="VERIFIED",
                geographic_scope="INTERNATIONAL",
            ),
            _make_claim(
                claim_id="c-002",
                claim_text="Fee changed for KITAS holders",
                confidence_class="VERIFIED",
                geographic_scope="NATIONAL",
            ),
        ]
        actions = detect_actions(claims)
        priorities = [a.priority for a in actions]
        # All high-priority actions should come before medium ones
        high_indices = [i for i, p in enumerate(priorities) if p == "high"]
        medium_indices = [i for i, p in enumerate(priorities) if p == "medium"]
        if high_indices and medium_indices:
            assert max(high_indices) < min(medium_indices)

    def test_claim_triggers_both_impact_and_news(self) -> None:
        """A claim matching both impact AND news rules should produce all actions."""
        claim = _make_claim(
            claim_text="New regulation: immigration fee increased effective immediately",
            geographic_scope="NATIONAL",
        )
        actions = detect_actions([claim])
        types = [a.action_type for a in actions]
        assert "crm_alert" in types
        assert "notify" in types
        assert "draft_article" in types

    def test_action_item_payload_contains_claim_id(self) -> None:
        """ActionItem payload should reference the source claim."""
        claim = _make_claim(
            claim_id="c-test-42",
            claim_text="Biaya baru berlaku untuk semua",
            geographic_scope="NATIONAL",
        )
        actions = detect_actions([claim])
        for action in actions:
            if action.action_type in ("crm_alert", "notify"):
                assert action.payload["claim_id"] == "c-test-42"

    def test_invalid_action_type_raises(self) -> None:
        """Creating ActionItem with invalid type should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid action_type"):
            ActionItem(action_type="invalid_type", description="test")
