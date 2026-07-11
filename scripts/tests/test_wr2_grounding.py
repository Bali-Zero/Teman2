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


if __name__ == "__main__":
    for fn in [test_law_extraction_matches_factchecker, test_inject_roundtrips,
               test_disabled_passthrough, test_enabled_injects, test_no_citation_degrades,
               test_oracle_fallback_used_when_chat_stream_has_no_citations,
               test_oracle_query_extracts_snippets_from_response_shape,
               test_oracle_failure_leaves_brief_unchanged]:
        fn(); print("PASS", fn.__name__)
    print("ALL PASS")
