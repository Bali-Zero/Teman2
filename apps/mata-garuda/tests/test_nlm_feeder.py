"""Tests for NLM Feeder worker — W3 Wave 1."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mata_garuda.config import NLM_DOMAIN_ROUTING, NLM_NOTEBOOKS
from mata_garuda.runtime.knowledge import KnowledgeBase
from mata_garuda.workers import nlm_feeder


# ── config wiring ──────────────────────────────────────────────────────────

class TestNotebookConfig:
    def test_all_4_nb_ids_populated(self):
        """W3 Wave 1 DOD: regulation/tax/immigration/press must be wired."""
        for key in ("regulation", "tax", "immigration", "press"):
            nb_id = NLM_NOTEBOOKS.get(key, "")
            assert nb_id, f"NLM_NOTEBOOKS[{key!r}] is empty — Wave 1 incomplete"
            # UUID v4 shape sanity check
            assert len(nb_id) == 36 and nb_id.count("-") == 4, (
                f"NLM_NOTEBOOKS[{key!r}] = {nb_id!r} does not look like a UUID"
            )

    def test_domain_routing_covers_briefing_spec(self):
        """Briefing spec: 4 domain mappings are required."""
        assert NLM_DOMAIN_ROUTING["immigration_visa"] == "immigration"
        assert NLM_DOMAIN_ROUTING["tax_fiscal"] == "tax"
        assert NLM_DOMAIN_ROUTING["investment_licensing"] == "regulation"
        # political_risk OR provincial_bali → press
        assert NLM_DOMAIN_ROUTING["political_risk"] == "press"


# ── routing ───────────────────────────────────────────────────────────────

class TestRouting:
    def test_route_immigration_visa(self):
        nb_key, nb_id = nlm_feeder.route_domain_to_notebook("immigration_visa")
        assert nb_key == "immigration"
        assert nb_id == NLM_NOTEBOOKS["immigration"]

    def test_route_tax_fiscal(self):
        nb_key, _ = nlm_feeder.route_domain_to_notebook("tax_fiscal")
        assert nb_key == "tax"

    def test_route_investment_licensing(self):
        nb_key, _ = nlm_feeder.route_domain_to_notebook("investment_licensing")
        assert nb_key == "regulation"

    def test_route_political_risk(self):
        nb_key, _ = nlm_feeder.route_domain_to_notebook("political_risk")
        assert nb_key == "press"

    def test_route_unknown_domain(self):
        nb_key, nb_id = nlm_feeder.route_domain_to_notebook("procurement")
        assert nb_key == ""
        assert nb_id == ""

    def test_route_empty_domain(self):
        nb_key, nb_id = nlm_feeder.route_domain_to_notebook("")
        assert nb_key == ""
        assert nb_id == ""

    def test_route_nb_key_directly(self):
        """PR #447 — domain may already be an NB key (e.g. inferred from
        source_type). route_domain_to_notebook should resolve it to the NB."""
        nb_key, nb_id = nlm_feeder.route_domain_to_notebook("ai_research")
        assert nb_key == "ai_research"
        assert nb_id == NLM_NOTEBOOKS["ai_research"]

    def test_route_property_to_regulation(self):
        """PR #450 — property → regulation NB."""
        nb_key, _ = nlm_feeder.route_domain_to_notebook("property")
        assert nb_key == "regulation"


# ── infer_domain_from_item heuristic (PR #446) ────────────────────────────

class TestInferDomain:
    def test_explicit_domain_wins(self):
        assert nlm_feeder.infer_domain_from_item({"domain": "tax_fiscal"}) == "tax_fiscal"

    def test_topic_fallback_when_domain_empty(self):
        assert nlm_feeder.infer_domain_from_item(
            {"domain": "", "topic": "immigration_visa"}
        ) == "immigration_visa"

    def test_source_type_arxiv_to_ai_research(self):
        assert nlm_feeder.infer_domain_from_item(
            {"source_type": "arxiv"}
        ) == "ai_research"

    def test_source_type_intel_scraper_to_press(self):
        assert nlm_feeder.infer_domain_from_item(
            {"source_type": "intel_scraper"}
        ) == "press"

    def test_source_field_fallback(self):
        """When source_type missing, source field is used."""
        assert nlm_feeder.infer_domain_from_item(
            {"source": "github"}
        ) == "ai_research"

    def test_unknown_source_returns_empty(self):
        assert nlm_feeder.infer_domain_from_item(
            {"source": "unknown.com", "source_type": "blog"}
        ) == ""

    def test_empty_data_returns_empty(self):
        assert nlm_feeder.infer_domain_from_item({}) == ""


# ── alerts stream consumer (PR #447) ──────────────────────────────────────

class TestAlertsConsumer:
    def test_alerts_stream_uses_separate_consumer_group(self):
        """alerts has its own CG so feeding alerts doesn't fight with enriched."""
        assert nlm_feeder.ALERTS_CONSUMER_GROUP != nlm_feeder.STREAM_CONSUMER_GROUP
        assert nlm_feeder.ALERTS_CONSUMER_NAME != nlm_feeder.STREAM_CONSUMER_NAME

    def test_alerts_routes_and_feeds_via_topic(self, tmp_path):
        """Alerts items have `topic` set by scorer.py — should route directly."""
        kb = KnowledgeBase(db_path=tmp_path / "feeder.db")
        items = [
            {"id": "1-0", "data": {
                "title": "Indonesia Visa Update", "content": "imigrasi.go.id news",
                "url": "https://ex.com/visa", "topic": "immigration_visa",
                "score": "5",
            }},
            {"id": "2-0", "data": {
                "title": "PMK 25/2026", "content": "tax regulation",
                "url": "https://ex.com/tax", "topic": "tax_fiscal",
                "score": "4",
            }},
        ]
        with patch.object(nlm_feeder, "stream_read_new", return_value=items), \
             patch.object(nlm_feeder, "_nlm_add_text", return_value=True) as m_add, \
             patch.object(nlm_feeder, "stream_ack") as m_ack:
            stats = nlm_feeder.run_nlm_feeder_from_alerts(kb, sleep_s=0)

        assert stats["processed"] == 2
        assert stats["fed"] == 2
        assert m_add.call_count == 2
        assert m_ack.call_count == 2
        kb.close()

    def test_alerts_uses_inferred_domain_when_topic_missing(self, tmp_path):
        """Backward compat: items in alerts without topic still route via
        source heuristic from infer_domain_from_item."""
        kb = KnowledgeBase(db_path=tmp_path / "feeder.db")
        items = [{
            "id": "1-0",
            "data": {
                "title": "arxiv preprint", "content": "neural network paper",
                "url": "https://arxiv.org/abs/1234", "source_type": "arxiv",
                # NO topic / domain field
            },
        }]
        with patch.object(nlm_feeder, "stream_read_new", return_value=items), \
             patch.object(nlm_feeder, "_nlm_add_text", return_value=True), \
             patch.object(nlm_feeder, "stream_ack"):
            stats = nlm_feeder.run_nlm_feeder_from_alerts(kb, sleep_s=0)
        assert stats["fed"] == 1
        kb.close()


# ── stream consumer behaviour ─────────────────────────────────────────────

def _fake_enriched_item(
    msg_id: str, *, domain: str, url: str, title: str = "T", content: str = "C"
) -> dict:
    return {
        "id": msg_id,
        "data": {
            "title": title,
            "content": content,
            "url": url,
            "domain": domain,
        },
    }


class TestStreamConsumer:
    def test_routes_and_feeds_matched_domains(self, tmp_path):
        kb = KnowledgeBase(db_path=tmp_path / "feeder.db")

        items = [
            _fake_enriched_item("1-0", domain="immigration_visa",
                                url="https://ex.com/visa1", title="Visa update"),
            _fake_enriched_item("2-0", domain="tax_fiscal",
                                url="https://ex.com/tax1", title="PMK 25/2026"),
            _fake_enriched_item("3-0", domain="procurement",  # unrouted
                                url="https://ex.com/x", title="skip me"),
        ]

        with patch.object(nlm_feeder, "stream_read_new", return_value=items), \
             patch.object(nlm_feeder, "_nlm_add_text", return_value=True) as m_add, \
             patch.object(nlm_feeder, "stream_ack") as m_ack:
            stats = nlm_feeder.run_nlm_feeder_from_stream(kb, sleep_s=0)

        assert stats["processed"] == 3
        assert stats["fed"] == 2
        assert stats["skipped"] == 1
        assert stats["errors"] == 0
        # 2 successful NLM add calls
        assert m_add.call_count == 2
        # ALL 3 ACKed — we never leave unresolved items in the PEL
        assert m_ack.call_count == 3

        # Dedup markers stored for the 2 fed URLs
        fed = kb.search("nlm_fed", limit=10)
        assert len(fed) == 2
        kb.close()

    def test_nlm_add_failure_counts_as_error_and_still_acks(self, tmp_path):
        kb = KnowledgeBase(db_path=tmp_path / "feeder.db")
        items = [
            _fake_enriched_item("1-0", domain="investment_licensing",
                                url="https://ex.com/r", title="Reg X"),
        ]
        with patch.object(nlm_feeder, "stream_read_new", return_value=items), \
             patch.object(nlm_feeder, "_nlm_add_text", return_value=False), \
             patch.object(nlm_feeder, "stream_ack") as m_ack:
            stats = nlm_feeder.run_nlm_feeder_from_stream(kb, sleep_s=0)

        assert stats["fed"] == 0
        assert stats["errors"] == 1
        assert m_ack.call_count == 1
        # case_not_resolved logged
        crn = kb.get_by_type("case_not_resolved", limit=5)
        assert any("nlm_feed_fail" in c["content"] for c in crn)
        kb.close()

    def test_dedup_skips_already_fed(self, tmp_path):
        kb = KnowledgeBase(db_path=tmp_path / "feeder.db")
        # Pre-seed a fed marker
        kb.store("nlm_feeder", "nlm_fed",
                 nlm_feeder._nlm_fed_marker("https://ex.com/dup"),
                 "https://ex.com/dup", 1.0)

        items = [
            _fake_enriched_item("1-0", domain="tax_fiscal",
                                url="https://ex.com/dup", title="dup"),
        ]
        with patch.object(nlm_feeder, "stream_read_new", return_value=items), \
             patch.object(nlm_feeder, "_nlm_add_text", return_value=True) as m_add, \
             patch.object(nlm_feeder, "stream_ack"):
            stats = nlm_feeder.run_nlm_feeder_from_stream(kb, sleep_s=0)

        assert stats["skipped"] == 1
        assert stats["fed"] == 0
        # NLM never called when dup detected
        m_add.assert_not_called()
        kb.close()

    def test_empty_stream_returns_zero_stats(self, tmp_path):
        kb = KnowledgeBase(db_path=tmp_path / "feeder.db")
        with patch.object(nlm_feeder, "stream_read_new", return_value=[]):
            stats = nlm_feeder.run_nlm_feeder_from_stream(kb, sleep_s=0)
        assert stats == {"processed": 0, "fed": 0, "skipped": 0, "errors": 0}
        kb.close()

    def test_rate_limit_sleep_called_between_items(self, tmp_path):
        kb = KnowledgeBase(db_path=tmp_path / "feeder.db")
        items = [
            _fake_enriched_item(f"{i}-0", domain="immigration_visa",
                                url=f"https://ex.com/{i}", title=f"t{i}")
            for i in range(3)
        ]
        with patch.object(nlm_feeder, "stream_read_new", return_value=items), \
             patch.object(nlm_feeder, "_nlm_add_text", return_value=True), \
             patch.object(nlm_feeder, "stream_ack"), \
             patch.object(nlm_feeder.time, "sleep") as m_sleep:
            nlm_feeder.run_nlm_feeder_from_stream(kb, sleep_s=5)

        # 3 items → sleep called twice (between, not after last)
        assert m_sleep.call_count == 2
        for call in m_sleep.call_args_list:
            assert call.args[0] == 5
        kb.close()
