"""Guilt + innocence for the curated-QA drift reporter.

Every case builds its own corpus under `tmp_path` — never the real one. The
real corpus is gitignored and ops-populated, so a test that read it would (a)
pass or fail depending on which machine ran it, and (b) be asserting against
production state (the test-writes-prod family). The fixtures below encode the
shapes measured on M5 on 2026-08-11, not a pointer to them.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.curated_qa_drift_report import (
    EXIT_CANNOT_VERIFY,
    EXIT_DRIFT,
    EXIT_OK,
    EXIT_PENDING_PROMOTION,
    main,
    scan,
)


def _row(question: str, cls: str = "BERSYARAT") -> str:
    return json.dumps(
        {
            "question": question,
            "answer": f"vetted answer for {question}",
            "domain": "visa",
            "lang": "en",
            "source_ref": "FIXTURE#1",
            "source_date": "2026-07-19",
            "confidence_class": cls,
            "law_refs": [],
            "source_priority": 10,
            "verbatim_eligible": cls == "JELAS",
            "client_specific": False,
        },
        ensure_ascii=False,
    )


def _corpus(tmp_path: Path, name: str, rows: list[str]) -> Path:
    d = tmp_path / "curated_qa"
    d.mkdir(exist_ok=True)
    f = d / name
    f.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return f


def _manifest(
    corpus_file: Path,
    *,
    sha: str | None = None,
    classes: dict[str, int] | None = None,
    created_at: str = "2026-07-19T10:00:00Z",
    faq_committed: bool = False,
    filename: str | None = None,
) -> Path:
    """`filename` exists so a test can make the STALE manifest sort LAST.

    Without it the on-disk name derives from the date, so the newest manifest
    also sorts last and any "last one wins" implementation looks correct — a
    mutation proved that exact false pass.
    """
    md = corpus_file.parent / "_manifests"
    md.mkdir(exist_ok=True)
    body = corpus_file.read_bytes()
    rows = [ln for ln in body.decode("utf-8").splitlines() if ln.strip()]
    if classes is None:
        classes = {}
        for ln in rows:
            c = json.loads(ln)["confidence_class"]
            classes[c] = classes.get(c, 0) + 1
    m = md / (filename or f"visa-{hashlib.sha256(body).hexdigest()[:12]}-{created_at[:10]}.json")
    m.write_text(
        json.dumps(
            {
                "batch_id": f"visa-{hashlib.sha256(body).hexdigest()[:12]}",
                "domain": "visa",
                "source_file": f"data/curated_qa/{corpus_file.name}",
                "source_file_sha256": sha if sha is not None else hashlib.sha256(body).hexdigest(),
                "row_count": len(rows),
                "class_histogram": classes,
                "created_at": created_at,
                "qdrant_committed": True,
                "faq_committed": faq_committed,
                "gate_flags": {},
            }
        ),
        encoding="utf-8",
    )
    return m


class TestGuiltDriftIsSeen:
    def test_an_edited_file_is_reported_as_drifted(self, tmp_path: Path) -> None:
        """The exact shape measured on M5: same row count, rewritten answers.

        A count-based check reads 20 == 20 and calls it healthy; this is why
        the comparison is on the sha, not on the size.
        """
        f = _corpus(tmp_path, "visa-a.jsonl", [_row("q1"), _row("q2")])
        _manifest(f)
        f.write_text("\n".join([_row("q1 EDITED"), _row("q2")]) + "\n", encoding="utf-8")

        verdicts, problems = scan(tmp_path / "curated_qa")

        assert problems == []
        (v,) = verdicts
        assert v.state == "drifted"
        assert v.rows_at_harvest == v.rows_on_disk == 2, "row count is deliberately unchanged"

    def test_a_promotion_to_jelas_is_called_out_separately(self, tmp_path: Path) -> None:
        """DINAMIS -> JELAS is the one drift that widens what may be served
        with the abstain gate bypassed. It must not read like ordinary drift."""
        f = _corpus(tmp_path, "visa-b.jsonl", [_row("q1", "DINAMIS"), _row("q2", "JELAS")])
        _manifest(f)
        f.write_text("\n".join([_row("q1", "JELAS"), _row("q2", "JELAS")]) + "\n", encoding="utf-8")

        (v,) = scan(tmp_path / "curated_qa")[0]

        assert v.state == "drifted"
        assert v.promotion_pending is True
        assert v.demotion_pending is False
        assert main(["--corpus-dir", str(tmp_path / "curated_qa")]) & EXIT_PENDING_PROMOTION

    def test_a_promotion_exits_nonzero_even_without_strict(self, tmp_path: Path) -> None:
        """Ordinary drift is advisory; a pending verbatim widening is not."""
        f = _corpus(tmp_path, "visa-c.jsonl", [_row("q1", "DINAMIS")])
        _manifest(f)
        f.write_text(_row("q1", "JELAS") + "\n", encoding="utf-8")

        assert main(["--corpus-dir", str(tmp_path / "curated_qa")]) != EXIT_OK

    def test_a_file_that_never_reached_a_sink_is_reported(self, tmp_path: Path) -> None:
        f = _corpus(tmp_path, "visa-d.jsonl", [_row("q1")])
        _manifest(f)
        _corpus(tmp_path, "visa-orphan.jsonl", [_row("q9")])

        verdicts, _ = scan(tmp_path / "curated_qa")
        orphan = next(v for v in verdicts if v.name == "visa-orphan.jsonl")

        assert orphan.state == "never_harvested"
        assert orphan.rows_on_disk == 1

    def test_a_harvested_file_deleted_from_disk_is_reported(self, tmp_path: Path) -> None:
        f = _corpus(tmp_path, "visa-e.jsonl", [_row("q1")])
        _manifest(f)
        f.unlink()

        (v,) = scan(tmp_path / "curated_qa")[0]

        assert v.state == "source_missing"
        assert main(["--strict", "--corpus-dir", str(tmp_path / "curated_qa")]) & EXIT_DRIFT


class TestGuiltTheScanRefusesToReadCleanWhenItSawNothing:
    def test_a_missing_corpus_dir_is_cannot_verify_not_clean(self, tmp_path: Path) -> None:
        code = main(["--corpus-dir", str(tmp_path / "does-not-exist")])
        assert code & EXIT_CANNOT_VERIFY

    def test_corpus_without_manifests_is_cannot_verify(self, tmp_path: Path) -> None:
        _corpus(tmp_path, "visa-f.jsonl", [_row("q1")])
        code = main(["--corpus-dir", str(tmp_path / "curated_qa")])
        assert code & EXIT_CANNOT_VERIFY, "no manifests means no baseline — never 'clean'"


class TestInnocence:
    def test_an_unchanged_corpus_reads_clean(self, tmp_path: Path) -> None:
        f = _corpus(tmp_path, "visa-g.jsonl", [_row("q1"), _row("q2", "JELAS")])
        _manifest(f)

        verdicts, problems = scan(tmp_path / "curated_qa")

        assert problems == []
        assert [v.state for v in verdicts] == ["in_sync"]
        assert main(["--strict", "--corpus-dir", str(tmp_path / "curated_qa")]) == EXIT_OK

    def test_drift_in_the_conservative_direction_is_not_a_promotion(self, tmp_path: Path) -> None:
        """Disk STRICTER than production is still drift, but it does not widen
        verbatim serving — ranking it alongside a promotion is how a report
        becomes noise."""
        f = _corpus(tmp_path, "visa-h.jsonl", [_row("q1", "JELAS"), _row("q2", "JELAS")])
        _manifest(f)
        f.write_text(
            "\n".join([_row("q1", "BERSYARAT"), _row("q2", "JELAS")]) + "\n", encoding="utf-8"
        )

        (v,) = scan(tmp_path / "curated_qa")[0]

        assert v.state == "drifted"
        assert v.promotion_pending is False
        assert v.demotion_pending is True
        assert not (main(["--corpus-dir", str(tmp_path / "curated_qa")]) & EXIT_PENDING_PROMOTION)

    def test_the_older_of_two_manifests_does_not_invent_drift(self, tmp_path: Path) -> None:
        """A file harvested twice has two manifests; the older one always
        mismatches disk. Counting manifests instead of files inflates the
        drift count — measured 28 manifests over 21 files.

        The filenames are deliberately ORDER-HOSTILE: the stale manifest sorts
        LAST, so an implementation that just keeps whichever it read last picks
        the stale one and reports drift. With the natural date-derived names the
        newest also sorts last, and this test passed against a mutant that had
        no newest-rule at all — it was agreeing with the traversal order, not
        with the code.
        """
        f = _corpus(tmp_path, "visa-i.jsonl", [_row("q1")])
        _manifest(f, sha="0" * 64, created_at="2026-07-19T10:00:00Z", filename="visa-zz-stale.json")
        _manifest(f, created_at="2026-07-21T10:00:00Z", filename="visa-aa-current.json")

        verdicts, _ = scan(tmp_path / "curated_qa")

        assert [v.state for v in verdicts] == ["in_sync"]

    def test_an_unparseable_line_is_counted_not_dropped(self, tmp_path: Path) -> None:
        f = _corpus(tmp_path, "visa-j.jsonl", [_row("q1")])
        _manifest(f)
        f.write_text(_row("q1") + "\n{not json\n", encoding="utf-8")

        (v,) = scan(tmp_path / "curated_qa")[0]

        assert v.rows_on_disk == 2, "a broken line must not make the file read smaller"
        assert v.classes_on_disk.get("__UNPARSEABLE__") == 1


@pytest.mark.parametrize("flag", [[], ["--json"]])
def test_both_output_modes_render_without_raising(tmp_path: Path, flag: list[str]) -> None:
    f = _corpus(tmp_path, "visa-k.jsonl", [_row("q1", "DINAMIS")])
    _manifest(f)
    f.write_text(_row("q1", "JELAS") + "\n", encoding="utf-8")

    assert main([*flag, "--corpus-dir", str(tmp_path / "curated_qa")]) & EXIT_PENDING_PROMOTION
