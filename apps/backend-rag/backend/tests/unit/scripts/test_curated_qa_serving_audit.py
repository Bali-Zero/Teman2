"""Guilt + innocence for the curated_qa serving audit.

The fake sits at the **HTTP boundary** — it answers `/points/scroll` with the
envelope shape measured against the live Qdrant on 2026-08-11
(`{"result": {"points": [...], "next_page_offset": ...}}`), not at the client
boundary. A fake placed at the service boundary would speak whatever
vocabulary the caller imagined, and two copies of one assumption confirming
each other is not evidence.

Every corpus here is built under `tmp_path`; nothing reads the real corpus or
the real collection.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.curated_qa_harvest import _stable_point_id
from scripts.curated_qa_serving_audit import (
    EXIT_CANNOT_VERIFY,
    EXIT_OK,
    EXIT_ORPHANS,
    EXIT_ROWS_NOT_SERVED,
    audit,
    render,
    scroll_all,
)
from scripts.curated_qa_serving_audit import (
    _load_disk_rows as load_disk_rows,
)


class _Resp:
    def __init__(self, body: dict[str, Any]) -> None:
        self._body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._body


class _FakeQdrant:
    """Answers scroll like the live API: one page per call, cursor in the body."""

    def __init__(self, pages: list[list[dict]]) -> None:
        self.pages = pages
        self.calls: list[dict] = []

    async def post(self, url: str, body: dict) -> _Resp:
        self.calls.append(body)
        idx = 0 if "offset" not in body else int(body["offset"])
        page = self.pages[idx] if idx < len(self.pages) else []
        nxt = idx + 1 if idx + 1 < len(self.pages) else None
        return _Resp({"result": {"points": page, "next_page_offset": nxt}})


class _BrokenQdrant:
    async def post(self, url: str, body: dict) -> _Resp:
        raise ConnectionError("qdrant unreachable")


def _row(question: str, domain: str = "visa", cls: str = "BERSYARAT") -> dict:
    return {
        "question": question,
        "answer": f"vetted answer for {question}",
        "domain": domain,
        "lang": "en",
        "source_ref": "FIXTURE#1",
        "source_date": "2026-07-19",
        "confidence_class": cls,
        "law_refs": [],
        "source_priority": 10,
        "verbatim_eligible": cls == "JELAS",
        "client_specific": False,
    }


def _corpus(tmp_path: Path, rows: list[dict], name: str = "visa-fixture.jsonl") -> Path:
    d = tmp_path / "curated_qa"
    d.mkdir(exist_ok=True)
    (d / name).write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8"
    )
    return d


def _point(row: dict, **payload_overrides: Any) -> dict:
    """A served point built the way the harvester builds one."""
    payload = {
        "domain": row["domain"],
        "confidence_class": row["confidence_class"],
        "answer": row["answer"],
        "text": row["question"],
        "source_date": row["source_date"],
    }
    payload.update(payload_overrides)
    return {"id": _stable_point_id(row["question"], row["domain"]), "payload": payload}


def _orphan_point(question: str, domain: str = "visa", **payload: Any) -> dict:
    """A point whose (domain, question) is NOT on disk — the 412-shape.

    Deliberately carries no `active`, no `batch_id`: that is exactly what the
    pre-Phase-0 points look like, and `active` missing is what makes them
    reach grounding.
    """
    base = {"domain": domain, "confidence_class": "BERSYARAT", "answer": "…", "text": question}
    base.update(payload)
    return {"id": _stable_point_id(question, domain), "payload": base}


class TestGuiltTheOrphansAreSeen:
    def test_a_point_with_no_corpus_row_is_reported_as_orphan(self, tmp_path: Path) -> None:
        rows = [_row("q1")]
        d = _corpus(tmp_path, rows)
        ids, problems = load_disk_rows(d)
        assert problems == []

        a = audit([_point(rows[0]), _orphan_point("a question nobody kept on disk")], ids)

        assert a.orphans == 1
        assert a.matched == 1
        assert a.served_points == 2

    def test_an_orphan_without_active_counts_as_reaching_grounding(self, tmp_path: Path) -> None:
        """Missing `active` means served — this mirrors the read path's own
        default, which is what makes the 412 a live condition rather than
        archaeology. An audit that assumed the safer reading would report a
        problem smaller than the one production has."""
        ids, _ = load_disk_rows(_corpus(tmp_path, [_row("q1")]))

        a = audit([_orphan_point("untracked")], ids)

        assert a.orphans == 1
        assert a.orphans_reachable == 1

    def test_a_corpus_row_that_no_point_answers_is_reported(self, tmp_path: Path) -> None:
        rows = [_row("q1"), _row("q2")]
        ids, _ = load_disk_rows(_corpus(tmp_path, rows))

        a = audit([_point(rows[0])], ids)

        assert len(a.rows_not_served) == 1
        assert "q2" in a.rows_not_served[0]

    @pytest.mark.asyncio
    async def test_an_orphan_on_the_second_page_is_not_missed(self, tmp_path: Path) -> None:
        """One scroll call returns ONE page. Reading it as the collection
        under-reports every orphan past the first page — the failure this
        tool exists to prevent, committed by the tool itself."""
        rows = [_row("q1")]
        ids, _ = load_disk_rows(_corpus(tmp_path, rows))
        fake = _FakeQdrant([[_point(rows[0])], [_orphan_point("only on page two")]])

        points, problems = await scroll_all(fake.post, "curated_qa", page_size=1)

        assert problems == []
        assert len(points) == 2, "the cursor must be followed to exhaustion"
        assert audit(points, ids).orphans == 1

    @pytest.mark.asyncio
    async def test_a_scroll_that_never_terminates_is_a_problem_not_a_result(self) -> None:
        never_ending = _FakeQdrant([[{"id": "x", "payload": {}}]] * 5)
        points, problems = await scroll_all(never_ending.post, "curated_qa", max_pages=2)

        assert problems, "a truncated read must be declared, never returned as the answer"
        assert len(points) == 2


class TestGuiltItRefusesToReadCleanWhenItSawNothing:
    @pytest.mark.asyncio
    async def test_an_unreachable_collection_is_cannot_verify(self) -> None:
        points, problems = await scroll_all(_BrokenQdrant().post, "curated_qa")

        assert points == []
        assert problems and "scroll failed" in problems[0]

    def test_a_missing_corpus_dir_is_a_problem(self, tmp_path: Path) -> None:
        ids, problems = load_disk_rows(tmp_path / "nope")
        assert ids == {}
        assert problems

    def test_a_corpus_dir_without_jsonl_is_a_problem(self, tmp_path: Path) -> None:
        (tmp_path / "curated_qa").mkdir()
        ids, problems = load_disk_rows(tmp_path / "curated_qa")
        assert ids == {}
        assert problems, "no rows means nothing to attribute points to — never 'clean'"


class TestInnocence:
    def test_a_collection_that_matches_disk_exactly_is_clean(self, tmp_path: Path) -> None:
        rows = [_row("q1"), _row("q2", cls="JELAS")]
        ids, _ = load_disk_rows(_corpus(tmp_path, rows))

        a = audit([_point(r) for r in rows], ids)

        assert a.orphans == 0
        assert a.rows_not_served == []
        assert a.matched == 2

    def test_a_matched_point_flagged_inactive_is_not_an_orphan(self, tmp_path: Path) -> None:
        """Quarantine sets `active=False` and deliberately KEEPS the point as
        an audit trail. Calling that an orphan would turn every correctly
        withdrawn answer into a finding."""
        rows = [_row("q1")]
        ids, _ = load_disk_rows(_corpus(tmp_path, rows))

        a = audit([_point(rows[0], active=False)], ids)

        assert a.orphans == 0
        assert a.matched == 1

    def test_an_orphan_already_flagged_inactive_does_not_count_as_reaching_grounding(
        self, tmp_path: Path
    ) -> None:
        ids, _ = load_disk_rows(_corpus(tmp_path, [_row("q1")]))

        a = audit([_orphan_point("withdrawn", active=False)], ids)

        assert a.orphans == 1
        assert a.orphans_reachable == 0, "explicitly inactive is exactly what the read path drops"

    def test_the_same_question_in_two_domains_is_two_distinct_rows(self, tmp_path: Path) -> None:
        """The id folds `domain` in (harvester FATAL-1). If this audit ever
        stopped honouring that, the second domain's point would read as an
        orphan of the first."""
        rows = [_row("same wording", domain="visa"), _row("same wording", domain="tax")]
        ids, _ = load_disk_rows(_corpus(tmp_path, rows))

        assert len(ids) == 2
        assert audit([_point(r) for r in rows], ids).orphans == 0


class TestGuiltTheLegacyIdIsCalledOut:
    """412 of 412 prod orphans carry the legacy id, and that is what rules out
    the obvious cure — so the audit has to distinguish the two shapes."""

    def _legacy_point(self, question: str, domain: str = "visa") -> dict:
        import hashlib
        import uuid

        from scripts.curated_qa_serving_audit import _legacy_point_id

        pid = _legacy_point_id(question)
        # Pin the rule itself, not just the helper's own output: the legacy id
        # is sha256 of the QUESTION ALONE. A helper that quietly folded the
        # domain back in would agree with itself forever.
        assert pid == str(
            uuid.uuid5(
                uuid.NAMESPACE_URL, hashlib.sha256(question.strip().lower().encode()).hexdigest()
            )
        )
        return {"id": pid, "payload": {"domain": domain, "text": question, "answer": "…"}}

    def test_an_orphan_carrying_the_legacy_id_is_counted(self, tmp_path: Path) -> None:
        ids, _ = load_disk_rows(_corpus(tmp_path, [_row("q1")]))

        a = audit([self._legacy_point("a question from the old generation")], ids)

        assert a.orphans == 1
        assert a.orphans_old_derivation == 1

    def test_the_render_warns_that_exporting_will_not_reach_them(self, tmp_path: Path) -> None:
        """The warning is the actionable half: without it the next reader
        exports the questions, gets a duplicate, and the orphan keeps serving."""
        ids, _ = load_disk_rows(_corpus(tmp_path, [_row("q1")]))

        text = render(audit([self._legacy_point("old one")], ids))

        assert "LEGACY id" in text
        assert "will NOT reach them" in text


class TestInnocenceOnTheLegacyIdCheck:
    def test_an_orphan_written_by_the_CURRENT_rule_is_not_called_legacy(
        self, tmp_path: Path
    ) -> None:
        """An orphan whose id the current rule CAN address is a different
        case entirely — exporting its question would genuinely reach it, so
        calling it legacy would send the reader down the wrong path."""
        ids, _ = load_disk_rows(_corpus(tmp_path, [_row("q1")]))

        a = audit([_orphan_point("addressable by today's rule")], ids)

        assert a.orphans == 1
        assert a.orphans_old_derivation == 0

    def test_a_point_matching_disk_is_never_examined_for_legacy_ids(self, tmp_path: Path) -> None:
        rows = [_row("q1")]
        ids, _ = load_disk_rows(_corpus(tmp_path, rows))

        a = audit([_point(rows[0])], ids)

        assert a.orphans_old_derivation == 0

    def test_an_orphan_with_no_question_text_is_not_guessed_at(self, tmp_path: Path) -> None:
        """No `text` means the derivation cannot be tested — that is unknown,
        not legacy. Counting it either way would be inventing evidence."""
        ids, _ = load_disk_rows(_corpus(tmp_path, [_row("q1")]))

        a = audit(
            [{"id": "11111111-2222-3333-4444-555555555555", "payload": {"domain": "visa"}}], ids
        )

        assert a.orphans == 1
        assert a.orphans_old_derivation == 0


def test_the_audit_uses_the_harvesters_own_id_rule_not_a_copy() -> None:
    """Two implementations of one id rule diverge the day one of them
    changes, and this one would then report the entire corpus as orphaned."""
    import scripts.curated_qa_harvest as harvest
    import scripts.curated_qa_serving_audit as sut

    assert sut._stable_point_id is harvest._stable_point_id


@pytest.mark.parametrize(
    ("orphans", "rows_not_served", "strict", "expect_bits"),
    [
        (0, 0, False, EXIT_OK),
        (0, 1, False, EXIT_ROWS_NOT_SERVED),
        (1, 0, False, EXIT_OK),
        (1, 0, True, EXIT_ORPHANS),
    ],
)
def test_exit_bits_follow_the_documented_severity(
    orphans: int, rows_not_served: int, strict: bool, expect_bits: int, tmp_path: Path
) -> None:
    """A row the bot cannot ground on is always non-zero; a bare orphan is
    advisory unless asked. `--strict` must not be the only way to learn that
    coverage is missing."""
    rows = [_row(f"q{i}") for i in range(1 + rows_not_served)]
    ids, _ = load_disk_rows(_corpus(tmp_path, rows))
    points = [_point(rows[0])]
    points += [_orphan_point(f"orphan{i}") for i in range(orphans)]

    a = audit(points, ids)
    code = EXIT_OK
    if a.rows_not_served:
        code |= EXIT_ROWS_NOT_SERVED
    if strict and a.orphans:
        code |= EXIT_ORPHANS

    assert code == expect_bits
    assert not (code & EXIT_CANNOT_VERIFY)
