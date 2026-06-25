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
    g._query_rag = empty
    out = asyncio.run(g.ground_enrichment({"enrichment": {}, "article_summary": "y"}, "t"))
    assert out["enrichment"] == {}


if __name__ == "__main__":
    for fn in [test_law_extraction_matches_factchecker, test_inject_roundtrips,
               test_disabled_passthrough, test_enabled_injects, test_no_citation_degrades]:
        fn(); print("PASS", fn.__name__)
    print("ALL PASS")
