"""Unit tests for wr2_grounding — deterministic paths (no network)."""
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import wr2_grounding as g  # noqa: E402


def test_law_extraction_matches_factchecker():
    s = "Capitale da PP 28/2025 e PMK 131/2024, vedi Pasal 6 della UU 6/2023."
    c = g._find_law_citations(s)
    assert "PP 28/2025" in c and "PMK 131/2024" in c and "UU 6/2023" in c
    assert any(x.startswith("Pasal") for x in c)


def test_inject_roundtrips():
    nb = {"regulatory_citations_verbatim": ["PP 28/2025"], "key_numbers": ["183 days"], "taboo_check": ["x"]}
    facts = g._inject_rails_into_facts("base", nb)
    assert g._find_law_citations(facts)


def test_disabled_passthrough():
    g.ENABLED = False
    b = {"enrichment": {}, "article_summary": "x"}
    assert asyncio.run(g.ground_enrichment(b, "t")) is b


def test_enabled_injects(monkeypatch=None):
    g.ENABLED = True
    async def fake(_): return "Regulation PP 28/2025 applies."
    g._query_rag = fake
    out = asyncio.run(g.ground_enrichment({"enrichment": {}, "article_summary": "y"}, "t"))
    assert g._find_law_citations(out["enrichment"]["the_facts"])
    assert out["enrichment"]["grounding_source"] == "fly-rag-http"


def test_no_citation_degrades():
    g.ENABLED = True
    async def empty(_): return "prose without any law number"
    async def oracle_empty(_): return ""
    g._query_rag = empty
    g._query_oracle = oracle_empty
    out = asyncio.run(g.ground_enrichment({"enrichment": {}, "article_summary": "y"}, "t"))
    assert out["enrichment"] == {}


def test_oracle_fallback_used_when_chat_stream_has_no_citations():
    """Chat-stream yields no citations -> falls back to /api/oracle/query snippets."""
    g.ENABLED = True

    async def chat_stream_empty(_):
        return "prose without any law number"

    async def oracle_with_snippets(_):
        # Simulates _query_oracle's scan-corpus assembly from citations[].snippet.
        return "Snippet A: per PP 28/2025.\nSnippet B: see PMK 37/2025 for details."

    g._query_rag = chat_stream_empty
    g._query_oracle = oracle_with_snippets
    out = asyncio.run(g.ground_enrichment({"enrichment": {}, "article_summary": "y"}, "t"))
    citations = g._find_law_citations(out["enrichment"]["the_facts"])
    assert "PP 28/2025" in citations
    assert "PMK 37/2025" in citations
    assert out["enrichment"]["grounding_source"] == "fly-oracle-http"


def test_oracle_query_extracts_snippets_from_response_shape(monkeypatch=None):
    """_query_oracle must scan answer + citations[].snippet + sources[].snippet."""
    class _FakeResponse:
        status_code = 200

        def json(self):
            return {
                "answer": "General overview, no citation here.",
                "citations": [
                    {"title": "PP 28/2025 art. 3", "snippet": "Ref PP 28/2025 applies to KBLI conversion."},
                ],
                "sources": [
                    {"title": "PMK circular", "snippet": "See PMK 37/2025 for the fee schedule."},
                ],
            }

    class _FakeAsyncClient:
        def __init__(self, timeout=None):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, json=None, headers=None):
            assert headers.get("X-API-Key") == g.API_KEY
            assert url.endswith("/api/oracle/query")
            return _FakeResponse()

    import httpx as real_httpx
    orig_client = real_httpx.AsyncClient
    real_httpx.AsyncClient = _FakeAsyncClient
    try:
        corpus = asyncio.run(g._query_oracle("KBLI conversion"))
    finally:
        real_httpx.AsyncClient = orig_client

    citations = g._find_law_citations(corpus)
    assert "PP 28/2025" in citations
    assert "PMK 37/2025" in citations


def test_oracle_failure_leaves_brief_unchanged():
    g.ENABLED = True

    async def chat_stream_empty(_):
        return "prose without any law number"

    async def oracle_raises(_):
        raise RuntimeError("boom")

    g._query_rag = chat_stream_empty
    g._query_oracle = oracle_raises
    brief = {"enrichment": {}, "article_summary": "y"}
    out = asyncio.run(g.ground_enrichment(brief, "t"))
    assert out["enrichment"] == {}


# ─────────────────────────────────────────────────────────────────────────
# _grounding_injected_only marker (2026-07-17 — draft 1229c367 park backstop)
# ─────────────────────────────────────────────────────────────────────────

def test_marker_set_when_injecting_into_truly_empty_brief():
    """GUILT: no existing enrichment facts AND no article_summary to fall back
    on -> base_facts is empty -> the injected the_facts is PURELY the citation
    block -> marker MUST be set so the drafter's park backstop can tell."""
    g.ENABLED = True

    async def fake_rag(_):
        return "Regulation PP 31/2013 applies."

    g._query_rag = fake_rag
    out = asyncio.run(
        g.ground_enrichment({"enrichment": {}, "article_summary": ""}, "t")
    )
    assert out["enrichment"]["_grounding_injected_only"] is True
    # And the_facts really is citations-only — no prose line before it.
    assert out["enrichment"]["the_facts"].startswith("Riferimenti normativi")


def test_marker_not_set_when_article_summary_present():
    """INNOCENCE: article_summary has real content -> base_facts falls back to
    it (even truncated) -> the injection is NOT citations-only -> no marker."""
    g.ENABLED = True

    async def fake_rag(_):
        return "Regulation PP 31/2013 applies."

    g._query_rag = fake_rag
    out = asyncio.run(
        g.ground_enrichment(
            {"enrichment": {}, "article_summary": "Three foreigners were deported."},
            "t",
        )
    )
    assert "_grounding_injected_only" not in out["enrichment"]
    assert out["enrichment"]["the_facts"].startswith("Three foreigners were deported.")


def test_marker_not_set_when_enrichment_already_has_real_facts():
    """INNOCENCE: enrichment already carries real prose facts (no citation in
    them yet) -> base_facts uses that existing prose -> no marker, even though
    citations get appended on top."""
    g.ENABLED = True

    async def fake_rag(_):
        return "Regulation PP 31/2013 applies."

    g._query_rag = fake_rag
    out = asyncio.run(
        g.ground_enrichment(
            {
                "enrichment": {"the_facts": "Some real facts already present."},
                "article_summary": "",
            },
            "t",
        )
    )
    assert "_grounding_injected_only" not in out["enrichment"]
    assert out["enrichment"]["the_facts"].startswith("Some real facts already present.")


def test_marker_absent_when_no_citations_found():
    """No citations found at all -> early degrade-return, brief unchanged, no
    the_facts mutation, no marker (nothing was injected)."""
    g.ENABLED = True

    async def empty(_):
        return "prose without any law number"

    async def oracle_empty(_):
        return ""

    g._query_rag = empty
    g._query_oracle = oracle_empty
    out = asyncio.run(
        g.ground_enrichment({"enrichment": {}, "article_summary": ""}, "t")
    )
    assert out["enrichment"] == {}


if __name__ == "__main__":
    for fn in [test_law_extraction_matches_factchecker, test_inject_roundtrips,
               test_disabled_passthrough, test_enabled_injects, test_no_citation_degrades,
               test_oracle_fallback_used_when_chat_stream_has_no_citations,
               test_oracle_query_extracts_snippets_from_response_shape,
               test_oracle_failure_leaves_brief_unchanged,
               test_marker_set_when_injecting_into_truly_empty_brief,
               test_marker_not_set_when_article_summary_present,
               test_marker_not_set_when_enrichment_already_has_real_facts,
               test_marker_absent_when_no_citations_found]:
        fn(); print("PASS", fn.__name__)
    print("ALL PASS")
