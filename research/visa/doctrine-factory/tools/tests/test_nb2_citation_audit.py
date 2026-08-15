"""No-network tests for nb2_citation_audit.py.

Covers the mandate's required guilt/innocence surface:
  - guilt: hallucinated [Source 99] not in snapshot -> NOT_COMPILABLE
  - innocence: valid pointer resolves -> VERIFIED
  - empty citations + resolvable prose pointer -> PROSE_ONLY
"""
import json

import nb2_citation_audit as ca

SNAPSHOT_INDEX = {
    "src-1": {"id": "src-1", "title": "BKPM Regulation 5 of 2025 on Paid-Up Capital", "type": "generated_text"},
    "src-2": {"id": "src-2", "title": "Permenkumham 22 of 2023 on Stay Permits", "type": "generated_text"},
}


def _ok_record(**overrides):
    base = {
        "query_id": "q1",
        "status": "OK",
        "conversation_id_sent": "c1",
        "answer": "",
        "citations": {},
        "references": [],
        "sources_used": [],
    }
    base.update(overrides)
    return base


def test_guilt_hallucinated_pointer_no_citation_map_entry():
    """[Source 99] is cited in prose but no citations/references entry ever mapped citation 99
    to anything — a classic hallucinated citation number."""
    record = _ok_record(answer="Per [Source 99] this is allowed.", citations={"1": "src-1"})
    verdict = ca.audit_record(record, SNAPSHOT_INDEX)
    assert verdict["verdict"] == ca.VERDICT_NOT_COMPILABLE
    assert verdict["unresolved_pointers"]
    assert verdict["unresolved_pointers"][0]["pointer"] == "[Source 99]"


def test_guilt_pointer_resolves_to_source_id_absent_from_snapshot():
    """The citations map DOES have an entry for citation 1, but it points to a source_id that
    the frozen snapshot has never heard of (a stale/fabricated source reference)."""
    record = _ok_record(answer="Per [Source 1] this is allowed.", citations={"1": "src-does-not-exist"})
    verdict = ca.audit_record(record, SNAPSHOT_INDEX)
    assert verdict["verdict"] == ca.VERDICT_NOT_COMPILABLE
    assert verdict["unresolved_pointers"][0]["source_id"] == "src-does-not-exist"


def test_innocence_valid_pointer_resolves_to_verified():
    record = _ok_record(answer="Per [Source 1] this is allowed.", citations={"1": "src-1"})
    verdict = ca.audit_record(record, SNAPSHOT_INDEX)
    assert verdict["verdict"] == ca.VERDICT_VERIFIED
    assert verdict["resolved_pointers"][0]["source_id"] == "src-1"
    assert not verdict["unresolved_pointers"]


def test_innocence_multiple_valid_pointers_all_resolve():
    record = _ok_record(
        answer="Per [Source 1] and [Source 2] this is allowed.",
        citations={"1": "src-1", "2": "src-2"},
    )
    verdict = ca.audit_record(record, SNAPSHOT_INDEX)
    assert verdict["verdict"] == ca.VERDICT_VERIFIED
    assert len(verdict["resolved_pointers"]) == 2


def test_empty_structured_citations_with_resolvable_title_mention_is_prose_only():
    record = _ok_record(
        answer="This matches BKPM Regulation 5 of 2025 on Paid-Up Capital exactly.",
        citations={},
        references=[],
        sources_used=[],
    )
    verdict = ca.audit_record(record, SNAPSHOT_INDEX)
    assert verdict["verdict"] == ca.VERDICT_PROSE_ONLY
    assert "BKPM Regulation 5 of 2025 on Paid-Up Capital" in verdict["title_mentions"]


def test_no_citations_and_no_prose_pointers_is_unsupported():
    record = _ok_record(answer="This is a bare assertion with no traceable grounding at all.")
    verdict = ca.audit_record(record, SNAPSHOT_INDEX)
    assert verdict["verdict"] == ca.VERDICT_UNSUPPORTED


def test_transport_error_record_is_skipped_not_audited():
    """A record whose transport already failed (isolation mismatch, CLI error, unparseable
    JSON) must never be graded as if its `answer` field were trustworthy."""
    record = {"query_id": "qX", "status": "ISOLATION_MISMATCH", "anomaly": "boom"}
    verdict = ca.audit_record(record, SNAPSHOT_INDEX)
    assert verdict["verdict"] == ca.VERDICT_SKIPPED
    assert verdict["reason"] == "boom"


def test_references_list_also_resolves_pointers():
    """references (source_id + citation_number + cited_text) is a second valid structured
    channel besides the bare citations dict."""
    record = _ok_record(
        answer="Per [Source 1] this is allowed.",
        citations={},
        references=[{"source_id": "src-1", "citation_number": 1, "cited_text": "..."}],
    )
    verdict = ca.audit_record(record, SNAPSHOT_INDEX)
    assert verdict["verdict"] == ca.VERDICT_VERIFIED


def test_load_source_index_from_snapshot_file(tmp_path):
    snapshot = {"notebook_id": "nb", "sources": [{"id": "s1", "title": "T1"}, {"id": "s2", "title": "T2"}]}
    p = tmp_path / "snap.json"
    p.write_text(json.dumps(snapshot), encoding="utf-8")
    idx = ca.load_source_index(p)
    assert set(idx) == {"s1", "s2"}


def test_load_source_index_accepts_bare_list_form(tmp_path):
    p = tmp_path / "snap.json"
    p.write_text(json.dumps([{"id": "s1", "title": "T1"}]), encoding="utf-8")
    idx = ca.load_source_index(p)
    assert set(idx) == {"s1"}


def test_load_response_log_reads_jsonl(tmp_path):
    p = tmp_path / "log.jsonl"
    p.write_text('{"a": 1}\n{"a": 2}\n', encoding="utf-8")
    records = ca.load_response_log(p)
    assert records == [{"a": 1}, {"a": 2}]


def test_audit_log_end_to_end(tmp_path):
    snapshot_path = tmp_path / "snap.json"
    snapshot_path.write_text(json.dumps({"sources": list(SNAPSHOT_INDEX.values())}), encoding="utf-8")
    log_path = tmp_path / "log.jsonl"
    log_path.write_text(
        json.dumps(_ok_record(answer="Per [Source 1] ok.", citations={"1": "src-1"})) + "\n",
        encoding="utf-8",
    )
    verdicts = ca.audit_log(log_path, snapshot_path)
    assert len(verdicts) == 1
    assert verdicts[0]["verdict"] == ca.VERDICT_VERIFIED
