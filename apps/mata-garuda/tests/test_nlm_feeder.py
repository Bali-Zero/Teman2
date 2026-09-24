"""Tests for NLM Feeder worker — W3 Wave 1."""
from __future__ import annotations

from unittest.mock import patch

from mata_garuda.config import NLM_DOMAIN_ROUTING, NLM_NOTEBOOKS
from mata_garuda.runtime.knowledge import KnowledgeBase
from mata_garuda.workers import nlm_feeder

# A body the no-body guard lets through: well past MIN_BODY_CHARS once the title is set aside.
BODY = "Peraturan text with a real paragraph of substance. " * 6

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
                "title": "Indonesia Visa Update", "content": BODY,
                "url": "https://ex.com/visa", "topic": "immigration_visa",
                "score": "5",
            }},
            {"id": "2-0", "data": {
                "title": "PMK 25/2026", "content": BODY,
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
                "title": "arxiv preprint", "content": BODY,
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
    msg_id: str, *, domain: str, url: str, title: str = "T", content: str = BODY
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
        # Pre-seed a fed marker on the ITEM-IDENTITY dedup key (title+url), which
        # is what the feeder now computes (W89 #2 — no longer the bare URL).
        seed_key = nlm_feeder._dedup_key("dup", "https://ex.com/dup")
        kb.store("nlm_feeder", "nlm_fed",
                 nlm_feeder._nlm_fed_marker(seed_key),
                 seed_key, 1.0)

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
        assert stats == {
            "processed": 0, "fed": 0, "skipped": 0, "errors": 0,
            "no_body": 0, "lake_owned": 0,
        }
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


class TestLakeOwnedSources:
    """intel_scraper items are owned end-to-end by the Intel Lake router +
    nb-pusher (see nlm_feeder._LAKE_OWNED_SOURCES docstring) — this feeder
    must leave them alone entirely, not feed them and not count them as
    no_body."""

    def test_intel_scraper_with_a_real_body_is_not_fed(self, tmp_path):
        """GUILT: even an intel_scraper item that DOES carry a real body
        (e.g. a future bridge upgrade) must still be left to the lake."""
        kb = KnowledgeBase(db_path=tmp_path / "feeder.db")
        items = [{
            "id": "1-0",
            "data": {
                "title": "Bali regulation update",
                "content": BODY,  # well past MIN_BODY_CHARS
                "url": "https://ex.com/intel-1",
                "source_type": "intel_scraper",
            },
        }]
        with patch.object(nlm_feeder, "stream_read_new", return_value=items), \
             patch.object(nlm_feeder, "_nlm_add_text", return_value=True) as m_add, \
             patch.object(nlm_feeder, "stream_ack") as m_ack:
            stats = nlm_feeder.run_nlm_feeder_from_stream(kb, sleep_s=0)
        kb.close()
        m_add.assert_not_called()
        assert stats["lake_owned"] == 1
        assert stats["fed"] == 0
        assert stats["no_body"] == 0
        assert m_ack.call_count == 1

    def test_intel_scraper_via_source_field_is_not_fed(self, tmp_path):
        """Same short-circuit when `source` (not `source_type`) carries it."""
        kb = KnowledgeBase(db_path=tmp_path / "feeder.db")
        items = [{
            "id": "1-0",
            "data": {
                "title": "Bali regulation update",
                "content": BODY,
                "url": "https://ex.com/intel-2",
                "source": "intel_scraper",
            },
        }]
        with patch.object(nlm_feeder, "stream_read_new", return_value=items), \
             patch.object(nlm_feeder, "_nlm_add_text", return_value=True) as m_add, \
             patch.object(nlm_feeder, "stream_ack"):
            stats = nlm_feeder.run_nlm_feeder_from_stream(kb, sleep_s=0)
        kb.close()
        m_add.assert_not_called()
        assert stats["lake_owned"] == 1

    def test_rss_item_with_real_body_is_still_fed(self, tmp_path):
        """INNOCENCE: an unrelated source still routes+feeds normally."""
        kb = KnowledgeBase(db_path=tmp_path / "feeder.db")
        items = [{
            "id": "1-0",
            "data": {
                "title": "AI research digest",
                "content": BODY,
                "url": "https://ex.com/rss-1",
                "source_type": "rss",
            },
        }]
        with patch.object(nlm_feeder, "stream_read_new", return_value=items), \
             patch.object(nlm_feeder, "_nlm_add_text", return_value=True) as m_add, \
             patch.object(nlm_feeder, "stream_ack"):
            stats = nlm_feeder.run_nlm_feeder_from_stream(kb, sleep_s=0)
        kb.close()
        m_add.assert_called_once()
        assert stats["fed"] == 1
        assert stats["lake_owned"] == 0

    def test_rss_item_without_body_still_counts_no_body(self, tmp_path):
        """INNOCENCE: a non-lake-owned source with no real body still hits
        the ordinary no_body path, untouched by the new short-circuit."""
        kb = KnowledgeBase(db_path=tmp_path / "feeder.db")
        items = [{
            "id": "1-0",
            "data": {
                "title": "Only a headline",
                "content": "",
                "url": "https://ex.com/rss-2",
                "source_type": "rss",
            },
        }]
        with patch.object(nlm_feeder, "stream_read_new", return_value=items), \
             patch.object(nlm_feeder, "_nlm_add_text", return_value=True) as m_add, \
             patch.object(nlm_feeder, "stream_ack"):
            stats = nlm_feeder.run_nlm_feeder_from_stream(kb, sleep_s=0)
        kb.close()
        m_add.assert_not_called()
        assert stats["no_body"] == 1
        assert stats["lake_owned"] == 0


class TestNlmCliPath:
    """Stage 3 (2026-06-30): the `nlm` CLI must resolve to an ABSOLUTE path so the
    feeder running under cron/non-login launchd (stripped PATH) stops failing mutely
    with `No such file or directory: 'nlm'`. Verified live on Pro: feeder read the
    enriched backlog but every push errored because bare 'nlm' was not on PATH.
    Same class + same cure as Stage 1's _resolve_redis_cli for redis-cli."""

    def test_nlm_resolves_absolute_when_found(self, monkeypatch):
        monkeypatch.setattr(nlm_feeder.shutil, "which", lambda _: "/Users/x/.local/bin/nlm")
        assert nlm_feeder._resolve_nlm_cli() == "/Users/x/.local/bin/nlm"

    def test_nlm_falls_back_to_known_path(self, monkeypatch):
        import os
        monkeypatch.setattr(nlm_feeder.shutil, "which", lambda _: None)
        real_exists = os.path.exists
        monkeypatch.setattr(
            nlm_feeder.os.path,
            "exists",
            lambda p: True if "/.local/bin/nlm" in p else real_exists(p),
        )
        assert nlm_feeder._resolve_nlm_cli().endswith("/.local/bin/nlm")

    def test_nlm_last_resort_is_bare_name(self, monkeypatch):
        monkeypatch.setattr(nlm_feeder.shutil, "which", lambda _: None)
        monkeypatch.setattr(nlm_feeder.os.path, "exists", lambda _: False)
        assert nlm_feeder._resolve_nlm_cli() == "nlm"

    def test_invocations_use_resolved_binary_not_bare_nlm(self):
        """Every subprocess invocation must start with the resolved NLM_CLI, never 'nlm'."""
        with patch.object(nlm_feeder.subprocess, "run") as m_run:
            from unittest.mock import MagicMock
            m_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
            nlm_feeder._nlm_notebook_source_count("nb-x")
            nlm_feeder._nlm_add_url("nb-x", "https://example.test/a")
        for call in m_run.call_args_list:
            argv = call.args[0]
            assert argv[0] == nlm_feeder.NLM_CLI
            # NLM_CLI is resolved at import; in CI it may be bare 'nlm' but must be the constant
            assert argv[0] != "nlm" or nlm_feeder.NLM_CLI == "nlm"


class TestCapRollover:
    """B2 (2026-06-30): when a domain NB hits the source cap, the feeder must roll
    over to its registry peer_uuids overflow NB automatically — no manual registry
    edit (B1 did that by hand). _resolve_writable_nb is the resolver every add goes
    through. Fail-safe: if no peer has room, return the original NB (the add then
    skips, as before — never crash, never lose-route silently)."""

    FULL = "dc5d01cd-e99f-4c8f-aae4-75060b43d0de"
    OVERFLOW = "069f009c-ce74-42e5-b75c-e584aa18feb1"

    def test_not_at_cap_returns_self(self):
        with patch.object(nlm_feeder, "_nlm_at_cap", return_value=False):
            assert nlm_feeder._resolve_writable_nb(self.FULL) == self.FULL

    def test_at_cap_rolls_over_to_peer_with_room(self):
        # FULL is at cap; its registry peer OVERFLOW has room
        def at_cap(nb):
            return nb == self.FULL
        with patch.object(nlm_feeder, "_nlm_at_cap", side_effect=at_cap):
            assert nlm_feeder._resolve_writable_nb(self.FULL) == self.OVERFLOW

    def test_at_cap_no_peer_room_returns_original(self):
        # everything is full → fail-safe to the original (add will skip)
        with patch.object(nlm_feeder, "_nlm_at_cap", return_value=True):
            assert nlm_feeder._resolve_writable_nb(self.FULL) == self.FULL

    def test_unknown_nb_returns_self(self):
        # a NB not in the registry has no peers → returns itself
        unknown = "00000000-0000-0000-0000-000000000000"
        with patch.object(nlm_feeder, "_nlm_at_cap", return_value=True):
            assert nlm_feeder._resolve_writable_nb(unknown) == unknown

    def test_add_url_writes_to_rolled_over_nb(self):
        """_nlm_add_url must target the resolved peer, not skip, when rolled over."""
        from unittest.mock import MagicMock
        def at_cap(nb):
            return nb == self.FULL
        with patch.object(nlm_feeder, "_nlm_at_cap", side_effect=at_cap), \
             patch.object(nlm_feeder.subprocess, "run") as m_run:
            m_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            ok = nlm_feeder._nlm_add_url(self.FULL, "https://example.test/x")
        assert ok is True
        # the add targeted the OVERFLOW, not the full FULL
        argv = m_run.call_args.args[0]
        assert self.OVERFLOW in argv and self.FULL not in argv


class TestNlmAddTextTitlePreserved:
    """Regression: _nlm_add_text must pass --text --title (NOT --file with a temp
    file whose name becomes the source title — that produced 8 mis-titled
    nlm_feed_*.txt sources in prod, fixed 2026-06-30)."""

    def test_uses_text_and_title_flags_not_file(self):
        from unittest.mock import patch, MagicMock
        ok = MagicMock(returncode=0, stdout="Source ID: x", stderr="")
        with patch.object(nlm_feeder, "_resolve_writable_nb", side_effect=lambda n: n), \
             patch.object(nlm_feeder, "_nlm_at_cap", return_value=False), \
             patch("subprocess.run", return_value=ok) as m_run:
            res = nlm_feeder._nlm_add_text("nb-1", "My Digest Title", "the body text")
        assert res is True
        argv = m_run.call_args.args[0]
        assert "--text" in argv and "--title" in argv
        assert "--file" not in argv                     # no temp-file path
        # the real title is passed, not a temp filename
        assert argv[argv.index("--title") + 1] == "My Digest Title"
        assert argv[argv.index("--text") + 1] == "the body text"


class TestNoBodyIsNotPublished:
    """An item whose only text is its title must not become an NLM source (the
    `content or title` fallback filled NB-INTEL-Press with title-only sources)."""

    def _feed(self, tmp_path, *, title, content):
        kb = KnowledgeBase(db_path=tmp_path / "feeder.db")
        items = [_fake_enriched_item("1-0", domain="political_risk",
                                     url="https://ex.com/a", title=title, content=content)]
        with patch.object(nlm_feeder, "stream_read_new", return_value=items), \
             patch.object(nlm_feeder, "_nlm_add_text", return_value=True) as m_add, \
             patch.object(nlm_feeder, "stream_ack") as m_ack:
            stats = nlm_feeder.run_nlm_feeder_from_stream(kb, sleep_s=0)
        kb.close()
        return stats, m_add, m_ack

    def test_empty_content_is_not_published(self, tmp_path):
        stats, m_add, m_ack = self._feed(tmp_path, title="Gubernur Bali lantik pejabat", content="")
        m_add.assert_not_called()
        assert stats["no_body"] == 1 and stats["fed"] == 0 and stats["errors"] == 0
        assert m_ack.call_count == 1

    def test_content_equal_to_title_is_not_published(self, tmp_path):
        title = "Gubernur Bali lantik pejabat"
        stats, m_add, _ = self._feed(tmp_path, title=title, content=f"  {title}\n")
        m_add.assert_not_called()
        assert stats["no_body"] == 1

    def test_title_plus_short_stub_is_not_published(self, tmp_path):
        title = "Gubernur Bali lantik pejabat"
        stats, m_add, _ = self._feed(tmp_path, title=title, content=f"{title}\n\nagent")
        m_add.assert_not_called()
        assert stats["no_body"] == 1

    def test_long_title_repeated_as_content_is_not_published(self, tmp_path):
        title = "T" * 250
        stats, m_add, _ = self._feed(tmp_path, title=title, content=title)
        m_add.assert_not_called()
        assert stats["no_body"] == 1

    def test_real_body_is_published_verbatim(self, tmp_path):
        stats, m_add, _ = self._feed(tmp_path, title="Gubernur Bali lantik pejabat", content=BODY)
        assert stats["fed"] == 1 and stats["no_body"] == 0
        assert m_add.call_args.args[2] == BODY.strip()

    def test_title_followed_by_real_body_is_published(self, tmp_path):
        title = "Gubernur Bali lantik pejabat"
        stats, m_add, _ = self._feed(tmp_path, title=title, content=f"{title}\n\n{BODY}")
        assert stats["fed"] == 1
        assert m_add.call_args.args[2].startswith(title)

    def test_body_just_over_the_bar_is_published(self, tmp_path):
        body = "x" * (nlm_feeder.MIN_BODY_CHARS + 1)
        stats, m_add, _ = self._feed(tmp_path, title="t", content=body)
        assert stats["fed"] == 1

    def test_body_at_the_bar_is_not_published(self, tmp_path):
        body = "x" * nlm_feeder.MIN_BODY_CHARS
        stats, m_add, _ = self._feed(tmp_path, title="t", content=body)
        m_add.assert_not_called()

    def test_legacy_kb_scan_text_path_skips_a_one_line_item(self, tmp_path):
        kb = KnowledgeBase(db_path=tmp_path / "feeder.db")
        kb.store("harvester", "harvested_item", "[rss] Only a headline", "http://ex.com/x", 1.0)
        with patch.object(nlm_feeder, "_route_to_notebook", return_value="nb-1"), \
             patch.object(nlm_feeder, "_nlm_add_text", return_value=True) as m_add:
            stats = nlm_feeder.run_nlm_feeder(kb)
        kb.close()
        m_add.assert_not_called()
        assert stats["no_body"] == 1
