#!/usr/bin/env python3
"""Tests for scripts/council_journal.py.

Every guard here is exercised for GUILT and INNOCENCE. The load-bearing pair is the one about
backdating: the innocence test proves a written line is accepted by the REAL R9 reader, and the
guilt test proves there is no door through which a timestamp can be supplied. If a future change
adds a `--ts` flag "for tests", `test_no_backdating_door_exists` goes red — which is the whole
point, because the reason this script exists is that a qualifying journal line cannot be written
after the fact without inventing one.

The quorum assertions never reimplement R9. They import `check_council_run_gear3` and
`_read_council_journal_seats` from `scripts/evidence_pack_lint.py` and assert on what THOSE
return, so a change to the rule surfaces here instead of drifting past a private copy.
"""

from __future__ import annotations

import datetime
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cj = _load("_cj_under_test", "council_journal.py")
lint = _load("_cj_lint", "evidence_pack_lint.py")

QUALIFYING = list(lint.COUNCIL_REVIEW_SEATS)
FLIP = lint.R9_R11_ENFORCEMENT_DATE


def _pack_dir(tmp_path: Path, *, gear: int | None = 3, council_run: str | None = None,
              seat_override: str | None = None, gear_in: str = "pack") -> Path:
    """Build a pack dir. `gear_in` selects where the gear is declared.

    `gear_in="brief"` is the shape EVERY real pack in this repo uses (measured 2026-09-02:
    0 of 40 declare gear in pack.yml, 37 declare it only in the sibling brief). `gear_in="pack"`
    is the shape the tool was first written against. Both must work.
    """
    import yaml

    d = tmp_path / "evidence" / "2026-09" / "task-slug-deadbeef"
    d.mkdir(parents=True)
    pack: dict = {"brief_ref": "evidence/brief.yml"}
    brief: dict = {"task": "a test pack"}
    if gear is not None:
        (pack if gear_in == "pack" else brief)["gear"] = gear
    if council_run is not None:
        pack["council_run"] = council_run
    if seat_override is not None:
        pack["seat_override"] = seat_override
    (d / "pack.yml").write_text(yaml.safe_dump(pack, sort_keys=False), encoding="utf-8")
    (d / "brief.yml").write_text(yaml.safe_dump(brief, sort_keys=False), encoding="utf-8")
    return d


def _append(pack_dir: Path, seat: str, outcome: str = "ok", note: str = "said a thing",
            journal: str | None = None) -> int:
    argv = ["append", "--pack-dir", str(pack_dir), "--seat", seat, "--outcome", outcome]
    if note:
        argv += ["--note", note]
    if journal is not None:
        argv += ["--journal", journal]
    return cj.main(argv)


# --------------------------------------------------------------------------- INNOCENCE


def test_a_written_line_is_accepted_by_the_real_r9_reader(tmp_path: Path) -> None:
    """INNOCENCE: what this script writes is what R9 counts — asserted through R9's own reader."""
    d = _pack_dir(tmp_path)
    assert _append(d, QUALIFYING[0]) == 0
    seats = lint._read_council_journal_seats(d, cj.DEFAULT_JOURNAL_NAME)
    assert seats == {QUALIFYING[0]}


def test_two_qualifying_seats_satisfy_r9_after_the_flip(tmp_path: Path) -> None:
    """INNOCENCE: quorum reached -> no violation even on/after the enforcement date."""
    d = _pack_dir(tmp_path, council_run=cj.DEFAULT_JOURNAL_NAME)
    assert _append(d, QUALIFYING[0]) == 0
    assert _append(d, QUALIFYING[1]) == 0
    import yaml

    pack = yaml.safe_load((d / "pack.yml").read_text(encoding="utf-8"))
    violations, _ = lint.check_council_run_gear3(pack, pack_dir=d, gear=3, today=FLIP)
    assert violations == []


def test_written_timestamp_is_now_and_parses(tmp_path: Path) -> None:
    """INNOCENCE: `ts` is a real, current, parseable UTC stamp — not a placeholder."""
    d = _pack_dir(tmp_path)
    before = datetime.datetime.now(datetime.timezone.utc)
    assert _append(d, QUALIFYING[0]) == 0
    after = datetime.datetime.now(datetime.timezone.utc)
    entry = json.loads((d / cj.DEFAULT_JOURNAL_NAME).read_text(encoding="utf-8").strip())
    stamped = datetime.datetime.strptime(entry["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=datetime.timezone.utc
    )
    # one second of slack each way: the script truncates to whole seconds
    assert before - datetime.timedelta(seconds=1) <= stamped <= after + datetime.timedelta(seconds=1)


def test_line_field_order_matches_the_existing_journals(tmp_path: Path) -> None:
    """INNOCENCE: the on-disk shape matches the 25 journals already in the tree."""
    d = _pack_dir(tmp_path)
    assert _append(d, QUALIFYING[0], note="a note") == 0
    entry = json.loads((d / cj.DEFAULT_JOURNAL_NAME).read_text(encoding="utf-8").strip())
    assert list(entry) == ["seat", "role", "ok", "ts", "note"]
    assert entry["role"] == "review" and entry["ok"] is True


def test_check_reports_zero_when_quorum_is_met(tmp_path: Path) -> None:
    """INNOCENCE: `check` exits 0 once the pack genuinely satisfies R9."""
    d = _pack_dir(tmp_path, council_run=cj.DEFAULT_JOURNAL_NAME)
    _append(d, QUALIFYING[0])
    _append(d, QUALIFYING[1])
    assert cj.main(["check", "--pack-dir", str(d)]) == 0


def test_check_is_silent_on_non_gear3_packs(tmp_path: Path) -> None:
    """INNOCENCE: R9 is Gear-3 only; a Gear-2 pack must not be failed by this tool."""
    d = _pack_dir(tmp_path, gear=2)
    assert cj.main(["check", "--pack-dir", str(d)]) == 0


# --------------------------------------------------------------------------- GUILT


def test_no_backdating_door_exists(tmp_path: Path) -> None:
    """GUILT: there is no way to supply a timestamp. This is the reason the script exists.

    If someone adds `--ts` (even "just for tests"), this goes red on purpose.
    """
    d = _pack_dir(tmp_path)
    with pytest.raises(SystemExit) as excinfo:
        cj.main([
            "append", "--pack-dir", str(d), "--seat", QUALIFYING[0],
            "--outcome", "ok", "--note", "x", "--ts", "2020-01-01T00:00:00Z",
        ])
    assert excinfo.value.code != 0
    assert not (d / cj.DEFAULT_JOURNAL_NAME).exists()


def test_ok_without_a_note_is_refused_and_writes_nothing(tmp_path: Path) -> None:
    """GUILT: a qualifying line is a claim; a claim with nothing behind it is refused."""
    d = _pack_dir(tmp_path)
    assert _append(d, QUALIFYING[0], note="") == 2
    assert not (d / cj.DEFAULT_JOURNAL_NAME).exists()


@pytest.mark.parametrize("bad", ["../escaped.jsonl", "/tmp/absolute.jsonl", "pack.yml", "brief.yml"])
def test_journal_path_escapes_and_reserved_names_are_refused(tmp_path: Path, bad: str) -> None:
    """GUILT: a journal outside the pack dir is invisible to R9; one over pack.yml is worse."""
    d = _pack_dir(tmp_path)
    assert _append(d, QUALIFYING[0], journal=bad) == 2
    assert list(d.glob("*.jsonl")) == []


def test_a_non_judgement_is_recorded_but_does_not_count(tmp_path: Path) -> None:
    """GUILT: a seat that timed out must never reach quorum — silence is not agreement."""
    d = _pack_dir(tmp_path, council_run=cj.DEFAULT_JOURNAL_NAME)
    assert _append(d, QUALIFYING[0]) == 0
    assert _append(d, QUALIFYING[1], outcome="non-judgement", note="TP1 timeout") == 0
    # the line IS on disk — that is the point of recording it
    lines = (d / cj.DEFAULT_JOURNAL_NAME).read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[1])["ok"] is False
    # ...but it does not count toward quorum
    assert lint._read_council_journal_seats(d, cj.DEFAULT_JOURNAL_NAME) == {QUALIFYING[0]}
    assert cj.main(["check", "--pack-dir", str(d)]) == 1


def test_a_single_qualifying_seat_fails_check_after_the_flip(tmp_path: Path) -> None:
    """GUILT: one seat is not a council. `check` must say so, and exit non-zero."""
    d = _pack_dir(tmp_path, council_run=cj.DEFAULT_JOURNAL_NAME)
    _append(d, QUALIFYING[0])
    assert cj.main(["check", "--pack-dir", str(d)]) == 1


def test_unknown_seat_is_recorded_but_not_counted(tmp_path: Path, capsys) -> None:
    """GUILT: a non-qualifying seat must not silently look like quorum.

    Recording it is correct — a council may include seats R9 does not count. Letting the author
    believe it counted is not, so the tool says so out loud.
    """
    d = _pack_dir(tmp_path, council_run=cj.DEFAULT_JOURNAL_NAME)
    assert _append(d, "agy-gemini-3.1-pro", note="constructive width") == 0
    assert "does NOT" in capsys.readouterr().out
    assert lint._read_council_journal_seats(d, cj.DEFAULT_JOURNAL_NAME) == set()


def test_gear_declared_only_in_the_sibling_brief_is_still_checked(tmp_path: Path) -> None:
    """GUILT: the shape EVERY real pack uses must not read as "not Gear-3, nothing to check".

    Measured 2026-09-02: 0 of 40 real packs declare `gear` in pack.yml; 37 declare it only in the
    sibling brief. Reading pack.yml alone made this tool answer green on the entire repo — the
    exact "instrument answered a neighbouring question" failure it exists to prevent. Without the
    brief fallback this returns 0 (a false pass); with it, 1 (no quorum, correctly refused).
    """
    d = _pack_dir(tmp_path, council_run=cj.DEFAULT_JOURNAL_NAME, gear_in="brief")
    assert "gear" not in (d / "pack.yml").read_text(encoding="utf-8")
    assert cj.main(["check", "--pack-dir", str(d)]) == 1


def test_gear_nowhere_refuses_instead_of_passing_silently(tmp_path: Path) -> None:
    """GUILT: "I cannot find the gear" and "this is not Gear-3" are different answers.

    Collapsing them into 0 is how a checker reports green on everything it cannot parse.
    """
    d = _pack_dir(tmp_path, gear=None)
    assert cj.main(["check", "--pack-dir", str(d)]) == 2


def test_gear_in_pack_still_wins_when_present(tmp_path: Path) -> None:
    """INNOCENCE: the fallback must not shadow a gear the pack does declare."""
    d = _pack_dir(tmp_path, gear=2, gear_in="pack")
    assert cj.main(["check", "--pack-dir", str(d)]) == 0  # gear 2 -> R9 not applicable


def test_missing_pack_dir_is_refused(tmp_path: Path) -> None:
    """GUILT: never create a pack directory as a side effect of journaling into it."""
    missing = tmp_path / "nope"
    assert _append(missing, QUALIFYING[0]) == 2
    assert not missing.exists()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
