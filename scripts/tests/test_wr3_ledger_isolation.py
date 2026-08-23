"""The WR3 credit ledger must be unwritable BY A TEST RUN (W96, 2026-08-23).

Measured before the cure: `~/.cache/wr3/credit-ledger.jsonl` held 28 rows
tagged `mode: "real"`, `credits: 20` — 560 credits of spend that never
happened — written by tests that drove `submit_clip()` against a mocked
gateway without redirecting `WR3_CREDIT_LEDGER`. `record_spend()` falls back to
the HOME path when that variable is unset, so a green suite was quietly
corrupting the one artifact whose entire job is to answer "how much did we
spend".

Two things are proved here, because a fixture that is present is not the same
as a fixture that BITES:

* guilt   — the fingerprint helper the session tripwire depends on actually
            notices a changed file and a vanished one;
* innocence — `record_spend()` with no explicit path, from inside the suite,
            lands in tmp_path and leaves the real HOME file alone.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wr3_credit_ledger import read_records, record_spend  # noqa: E402


def test_record_spend_without_an_explicit_path_stays_out_of_home(tmp_path: Path) -> None:
    """The autouse isolation fixture is what makes this pass.

    No env var is set here on purpose: this is exactly the shape of the tests
    that leaked. Delete the `monkeypatch.setenv("WR3_CREDIT_LEDGER", ...)` line
    in conftest and this goes red.
    """
    real = Path(os.path.expanduser("~")) / ".cache" / "wr3" / "credit-ledger.jsonl"
    before = real.read_bytes() if real.exists() else None

    record_spend(episode_id="EP-isolation-probe", shot_index=1, credits=20,
                 mode="real", veo_job_id="wf-probe", source="test", clip_cost_cr=20)

    redirected = Path(os.environ["WR3_CREDIT_LEDGER"])
    assert redirected.parent == tmp_path, f"fixture did not redirect: {redirected}"
    rows = read_records(ledger_path=redirected)
    assert [r["episode_id"] for r in rows] == ["EP-isolation-probe"]

    after = real.read_bytes() if real.exists() else None
    assert after == before, "record_spend() reached the real ledger from inside the suite"


def test_the_spend_decision_log_is_redirected_too(tmp_path: Path) -> None:
    """`log_decision()` has the same HOME fallback and the same exposure."""
    assert Path(os.environ["WR3_SPEND_DECISION_LOG"]).parent == tmp_path


def test_the_fingerprint_helper_notices_a_changed_file(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch,
                                                       wr3_real_state_fingerprint) -> None:
    """Guilt: the tripwire's detector must see a mutation, or it guards nothing."""
    fake_home = tmp_path / "home"
    (fake_home / ".cache" / "wr3").mkdir(parents=True)
    ledger = fake_home / ".cache" / "wr3" / "credit-ledger.jsonl"
    ledger.write_text(json.dumps({"credits": 0}) + "\n")
    monkeypatch.setenv("HOME", str(fake_home))

    before = wr3_real_state_fingerprint()
    with ledger.open("a") as fh:
        fh.write(json.dumps({"credits": 20}) + "\n")
    after = wr3_real_state_fingerprint()

    assert before[str(ledger)] != after[str(ledger)]
    assert "absent" not in (before[str(ledger)], after[str(ledger)])


def test_the_fingerprint_helper_reports_absent_rather_than_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wr3_real_state_fingerprint
) -> None:
    """Innocence: a machine with no ledger yet must not error the session."""
    monkeypatch.setenv("HOME", str(tmp_path / "empty-home"))
    fingerprint = wr3_real_state_fingerprint()
    assert set(fingerprint.values()) == {"absent"}
    assert len(fingerprint) == 2


def test_a_touched_but_unchanged_file_is_not_reported_as_mutated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wr3_real_state_fingerprint
) -> None:
    """Innocence, and a real claim about HOW the tripwire decides.

    The fingerprint must be over CONTENT, not over mtime. A ledger whose
    timestamp moved — an editor save, a backup tool, an rsync — has not been
    spent against, and a tripwire that failed on that would fire on clean
    sessions until someone disarmed it. So: same bytes, new mtime, same
    verdict.
    """
    fake_home = tmp_path / "home"
    (fake_home / ".cache" / "wr3").mkdir(parents=True)
    ledger = fake_home / ".cache" / "wr3" / "credit-ledger.jsonl"
    ledger.write_text('{"credits": 0}\n')
    monkeypatch.setenv("HOME", str(fake_home))

    before = wr3_real_state_fingerprint()
    os.utime(ledger, (1_000_000_000, 1_000_000_000))
    stamped = wr3_real_state_fingerprint()
    assert stamped == before, "the fingerprint reacted to mtime, not to content"

    ledger.write_text('{"credits": 20}\n')  # same length, different bytes
    assert wr3_real_state_fingerprint() != before
