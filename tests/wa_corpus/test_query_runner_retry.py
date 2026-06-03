import json

from scripts.wa_corpus import query_runner
from scripts.wa_corpus.query_runner import QueryRunner

EMPTY = json.dumps({"value": {"answer": "**HEADLINE**: x", "references": []}})
WITH_CITES = json.dumps(
    {
        "value": {
            "answer": "**HEADLINE**: x",
            "references": [{"source_id": "s1", "cited_text": "real quote"}],
        }
    }
)


def test_retries_until_citations_appear(monkeypatch):
    # NLM returns empty citations twice, then populated (the flaky behaviour).
    calls = {"n": 0}
    seq = [EMPTY, EMPTY, WITH_CITES]

    def fake_nlm(args, timeout=300.0):
        out = seq[calls["n"]]
        calls["n"] += 1
        return out

    monkeypatch.setattr(query_runner, "_nlm", fake_nlm)
    r = QueryRunner().run_prompt_master("nb", "s1", max_attempts=3)
    assert r.has_citations is True
    assert r.cited_texts == ["real quote"]
    assert calls["n"] == 3  # retried twice before success


def test_gives_up_after_max_attempts_and_flags_empty(monkeypatch):
    def always_empty(args, timeout=300.0):
        return EMPTY

    monkeypatch.setattr(query_runner, "_nlm", always_empty)
    r = QueryRunner().run_prompt_master("nb", "s1", max_attempts=2)
    assert r.has_citations is False  # caller must flag as unverified


def test_stops_early_when_first_attempt_has_citations(monkeypatch):
    calls = {"n": 0}

    def first_ok(args, timeout=300.0):
        calls["n"] += 1
        return WITH_CITES

    monkeypatch.setattr(query_runner, "_nlm", first_ok)
    r = QueryRunner().run_prompt_master("nb", "s1", max_attempts=3)
    assert r.has_citations is True
    assert calls["n"] == 1  # no wasted retries
