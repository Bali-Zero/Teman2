import json

from scripts.wa_corpus.query_runner import RecapResult, parse_query_result

SAMPLE = json.dumps(
    {
        "value": {
            "answer": "## DEADLINES\nKITAS 2029-12-31 [1]\n## PAYMENTS\nnot mentioned",
            "conversation_id": "c1",
            "references": [
                {
                    "source_id": "s1",
                    "citation_number": 1,
                    "cited_text": "KITAS appointment 2029-12-31",
                }
            ],
        }
    }
)


def test_parse_extracts_answer_and_citations():
    r = parse_query_result(SAMPLE)
    assert isinstance(r, RecapResult)
    assert "DEADLINES" in r.answer
    assert r.has_citations is True
    assert r.cited_texts == ["KITAS appointment 2029-12-31"]


def test_parse_no_citations_flagged():
    no_cite = json.dumps({"value": {"answer": "x", "references": []}})
    r = parse_query_result(no_cite)
    assert r.has_citations is False
