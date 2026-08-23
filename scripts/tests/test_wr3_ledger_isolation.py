"""The WR3 credit ledger must be unwritable BY A TEST RUN (W96, 2026-08-23).

Measured before the cure: `~/.cache/wr3/credit-ledger.jsonl` held 106 rows,
every one a test artifact, including 28 tagged `mode: "real"`, `credits: 20` —
560 credits of spend that never happened — written by tests that drove
`submit_clip()` against a mocked gateway without redirecting
`WR3_CREDIT_LEDGER`. `record_spend()` falls back to the HOME path when that
variable is unset, so a green suite was quietly corrupting the one artifact
whose job is to answer "how much did we spend".

Two layers are under test, and each is probed for guilt as well as innocence,
because a fixture that is PRESENT is not the same as a fixture that BITES:

* the autouse redirection — proved by writing through the real API and finding
  the row in tmp_path with the real file unmoved;
* the session tripwire's detector — proved by making it see an append past the
  first 4 KiB (a prefix-only hash would pass every small-file test ever
  written), a brand-new sidecar file, and a deletion.

The 4 KiB case is not hypothetical: `hashlib.sha256(data[:4096])` keeps every
naive guilt test green while the real ledger, long past 4 KiB, can be appended
to forever with its digest frozen. That mutation was found by a cross-family
refuter, not by this suite's first draft.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wr3_credit_ledger import read_records, record_spend  # noqa: E402
from wr3_spend_authority import log_decision, parse_decision  # noqa: E402


# ---------------------------------------------------------------------------
# The redirection bites
# ---------------------------------------------------------------------------

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
    assert [r["episode_id"] for r in read_records(ledger_path=redirected)] == ["EP-isolation-probe"]

    after = real.read_bytes() if real.exists() else None
    assert after == before, "record_spend() reached the real ledger from inside the suite"


def test_log_decision_actually_writes_into_the_redirected_log(tmp_path: Path) -> None:
    """Exercise the WRITER, not the env var.

    Asserting that `os.environ["WR3_SPEND_DECISION_LOG"]` points into tmp_path
    would test the fixture's own `setenv` and nothing else: if `log_decision`
    stopped honouring the variable — say it were "simplified" to the
    import-time `_DEFAULT_LOG_PATH` in wr3_spend_authority — such a test would
    stay green while decisions landed in the real file.
    """
    real = Path(os.path.expanduser("~")) / ".cache" / "wr3" / "spend-decisions.jsonl"
    before = real.read_bytes() if real.exists() else None

    decision = parse_decision(f"EP-decision-probe:zero@balizero.com:{date.today().isoformat()}")
    log_decision(decision, episode_id="EP-decision-probe")

    redirected = Path(os.environ["WR3_SPEND_DECISION_LOG"])
    assert redirected.parent == tmp_path
    rows = [json.loads(line) for line in redirected.read_text().splitlines() if line.strip()]
    assert len(rows) == 1 and "EP-decision-probe" in json.dumps(rows[0])

    after = real.read_bytes() if real.exists() else None
    assert after == before, "log_decision() reached the real decision log"


# ---------------------------------------------------------------------------
# The detector bites — guilt
# ---------------------------------------------------------------------------

def _fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    state = home / ".cache" / "wr3"
    state.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    return state


def test_detector_notices_an_append_past_the_first_4096_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wr3_real_state_fingerprint
) -> None:
    """Kills the prefix-hash mutation.

    `sha256(read_bytes()[:4096])` passes every test written against a two-line
    fixture — and freezes the digest of the real ledger, which is far larger,
    so it could be appended to forever undetected. The file here is padded past
    4 KiB and only its TAIL changes.
    """
    state = _fake_home(tmp_path, monkeypatch)
    ledger = state / "credit-ledger.jsonl"
    padding = "".join(json.dumps({"pad": i}) + "\n" for i in range(400))
    assert len(padding.encode()) > 4096
    ledger.write_text(padding)

    before = wr3_real_state_fingerprint()
    with ledger.open("a") as fh:
        fh.write(json.dumps({"credits": 20, "mode": "real"}) + "\n")
    assert wr3_real_state_fingerprint() != before


def test_detector_notices_a_new_sidecar_appearing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wr3_real_state_fingerprint
) -> None:
    """`_record_failure` writes `<ledger>.failures` beside the ledger.

    A detector listing only the two named files would leave that whole write
    surface unguarded — real state mutated, session green.
    """
    state = _fake_home(tmp_path, monkeypatch)
    (state / "credit-ledger.jsonl").write_text("{}\n")

    before = wr3_real_state_fingerprint()
    (state / "credit-ledger.jsonl.failures").write_text('{"kind": "validation"}\n')
    after = wr3_real_state_fingerprint()

    assert set(after) - set(before) == {str(state / "credit-ledger.jsonl.failures")}


def test_detector_notices_a_file_vanishing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wr3_real_state_fingerprint
) -> None:
    state = _fake_home(tmp_path, monkeypatch)
    ledger = state / "credit-ledger.jsonl"
    ledger.write_text("{}\n")

    before = wr3_real_state_fingerprint()
    ledger.unlink()
    after = wr3_real_state_fingerprint()

    assert str(ledger) in before and str(ledger) not in after


# ---------------------------------------------------------------------------
# The detector bites — innocence
# ---------------------------------------------------------------------------

def test_detector_reports_an_empty_map_when_the_directory_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wr3_real_state_fingerprint
) -> None:
    """A CI runner or a fresh machine has no ~/.cache/wr3 at all. That must be
    an empty map, not an exception erroring every session."""
    monkeypatch.setenv("HOME", str(tmp_path / "empty-home"))
    assert wr3_real_state_fingerprint() == {}


def test_a_touched_but_unchanged_file_is_not_reported_as_mutated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wr3_real_state_fingerprint
) -> None:
    """The verdict must be over CONTENT, not mtime.

    A ledger whose timestamp moved — an editor save, a backup, an rsync — has
    not been spent against, and a tripwire that failed on that would fire on
    clean sessions until someone disarmed it.
    """
    state = _fake_home(tmp_path, monkeypatch)
    ledger = state / "credit-ledger.jsonl"
    ledger.write_text('{"credits": 0}\n')

    before = wr3_real_state_fingerprint()
    os.utime(ledger, (1_000_000_000, 1_000_000_000))
    assert wr3_real_state_fingerprint() == before, "the detector reacted to mtime, not content"

    ledger.write_text('{"credits": 20}\n')  # same length, different bytes
    assert wr3_real_state_fingerprint() != before
