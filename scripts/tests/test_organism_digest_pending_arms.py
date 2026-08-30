"""Tests for organism_digest.pending_arms_overdue — the W81 ledger line.

WHY THIS EXISTS (cicatrix #2 "Esiste != Armato", and #9 vocabulary drift):
`pending_arms_report.py --json` emits each entry with the key **"class"**.
`organism_digest.pending_arms_overdue()` read **"classification"**. That key is
never emitted, so `e.get("classification")` was always None, the filter was
always empty, and the `if overdue:` branch never fired once — dead code on the
only path for which it exists (W116). Measured on 2026-08-21 against the real
ledger: counts.tech_debt_overdue = 262, filter matched 0. Every session start
printed NOTHING about pending arms, and silence reads as "nothing is overdue".

The sentinel for built-but-not-armed was itself not armed.

Contract (guilt + innocence):
  - GUILT: overdue TECH-DEBT entries produce a line naming the real count.
  - INNOCENCE: a ledger with nothing overdue produces NO line.
  - INNOCENCE: OPERATOR-GATED / FIREBREAK overdue entries are not TECH-DEBT
    and must not raise the alarm on their own.
  - SCAR PIN: a payload carrying ONLY the old "classification" spelling must
    NOT go silent — counts and entries disagree, and the digest says so.
  - The count comes from counts.tech_debt_overdue, so a future per-entry key
    rename costs the top-artifact detail but can never zero the alarm.
"""

import json
import os
import sys
import textwrap

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import organism_digest  # noqa: E402


def _fake_reporter(tmp_path, payload):
    """Install a fake reporter at the REAL boundary the digest crosses.

    The digest shells out to scripts/pending_arms_report.py and parses its
    stdout, so the fake is a real script on disk, exercising subprocess +
    json.loads rather than stubbing them away (the W114 lesson: a fake placed
    inside the boundary just confirms your own assumption).
    """
    scripts = tmp_path / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    reporter = scripts / "pending_arms_report.py"
    reporter.write_text(
        textwrap.dedent(
            """\
            import sys
            sys.stdout.write(%r)
            """
        )
        % json.dumps(payload)
    )
    return tmp_path


def _run(monkeypatch, tmp_path, payload, *, opt_in=True):
    root = _fake_reporter(tmp_path, payload)
    monkeypatch.setattr(organism_digest, "_repo_root", lambda: root)
    # The overdue line is opt-in since 2026-08-22 (see pending_arms_overdue);
    # these tests exercise the reporter contract, so they opt in explicitly.
    if opt_in:
        monkeypatch.setenv("ORGANISM_DIGEST_PENDING_ARMS", "1")
    else:
        monkeypatch.delenv("ORGANISM_DIGEST_PENDING_ARMS", raising=False)
    return organism_digest.pending_arms_overdue()


def _entry(cls, artifact="**a suspended arming**", overdue=True):
    return {
        "age_days": 9,
        "artifact": artifact,
        "class": cls,
        "opened": "2026-08-12",
        "overdue": overdue,
        "owner": "owner: session",
        "raw_head": "- opened 2026-08-12 | " + artifact,
    }


def test_guilt_overdue_tech_debt_is_reported(monkeypatch, tmp_path):
    lines, errs = _run(
        monkeypatch,
        tmp_path,
        {
            "counts": {"total": 3, "tech_debt_overdue": 3},
            "entries": [_entry("TECH-DEBT", "**the top one**")] * 3,
        },
    )
    assert errs == []
    assert len(lines) == 1
    assert "3 armamenti sospesi OVERDUE" in lines[0]
    assert "the top one" in lines[0]


def test_innocence_nothing_overdue_says_nothing(monkeypatch, tmp_path):
    lines, errs = _run(
        monkeypatch,
        tmp_path,
        {"counts": {"total": 4, "tech_debt_overdue": 0}, "entries": []},
    )
    assert lines == []
    assert errs == []


def test_innocence_operator_gated_alone_does_not_alarm(monkeypatch, tmp_path):
    """OPERATOR-GATED and FIREBREAK are not technical debt — no alarm."""
    lines, errs = _run(
        monkeypatch,
        tmp_path,
        {
            "counts": {"total": 2, "tech_debt_overdue": 0, "operator_gated_overdue": 2},
            "entries": [_entry("OPERATOR-GATED"), _entry("FIREBREAK")],
        },
    )
    assert lines == []
    assert errs == []


def test_scar_pin_old_classification_key_is_loud_not_silent(monkeypatch, tmp_path):
    """The exact shape of the bug: entries speak a vocabulary the reader
    does not know. Before the fix this produced SILENCE against 262 real
    overdue entries. Now the count still lands, and the drift is named."""
    stale = {
        "age_days": 9,
        "artifact": "**a suspended arming**",
        "classification": "TECH-DEBT",  # the key the reader used to expect
        "overdue": True,
    }
    lines, errs = _run(
        monkeypatch,
        tmp_path,
        {"counts": {"total": 262, "tech_debt_overdue": 262}, "entries": [stale] * 262},
    )
    assert len(lines) == 1, "the alarm must still fire off counts"
    assert "262 armamenti sospesi OVERDUE" in lines[0]
    assert any("key drift" in e for e in errs), "the drift itself must be named"


def test_partial_drift_is_caught_too_not_only_a_total_wipeout(monkeypatch, tmp_path):
    """The first cure only fired when NOTHING matched. Half a ledger renaming
    a key is the likelier drift and would have slipped through reporting a
    counts-derived number with a `top:` drawn from the surviving sample.
    Guarding on inequality — not emptiness — is what closes that."""
    entries = [_entry("TECH-DEBT")] * 5 + [
        {"artifact": "**drifted**", "classification": "TECH-DEBT", "overdue": True}
    ] * 5
    lines, errs = _run(
        monkeypatch,
        tmp_path,
        {"counts": {"total": 10, "tech_debt_overdue": 10}, "entries": entries},
    )
    assert len(lines) == 1
    assert "10 armamenti sospesi OVERDUE" in lines[0], "the count still comes from counts"
    assert any("key drift" in e for e in errs), "5 of 10 matching must NOT read as healthy"
    assert any("10 overdue by counts, 5 matched" in e for e in errs)


def test_null_artifact_does_not_swallow_the_alarm(monkeypatch, tmp_path):
    """A drifted payload can carry `artifact` present-but-null. `None[:70]`
    would raise inside the catch-all and cost the whole line — losing the
    alarm to fix a detail."""
    row = _entry("TECH-DEBT")
    row["artifact"] = None
    lines, errs = _run(
        monkeypatch,
        tmp_path,
        {"counts": {"total": 1, "tech_debt_overdue": 1}, "entries": [row]},
    )
    assert len(lines) == 1
    assert "1 armamenti sospesi OVERDUE" in lines[0]
    assert "?" in lines[0]
    assert errs == []


def test_reporter_absent_is_not_an_error(monkeypatch, tmp_path):
    """A repo without the reporter is not a fault — stay quiet, per the
    existing guard at the top of the function."""
    monkeypatch.setattr(organism_digest, "_repo_root", lambda: tmp_path)
    lines, errs = organism_digest.pending_arms_overdue()
    assert lines == []
    assert errs == []


def test_default_boot_does_not_inject_the_overdue_count(monkeypatch, tmp_path):
    """2026-08-22: without the opt-in env the digest says NOTHING about the
    ledger even when it is deeply overdue — the boot line was a meta-work
    magnet (190 OVERDUE greeted every session for two days)."""
    payload = {
        "counts": {"tech_debt_overdue": 190},
        "entries": [_entry("TECH-DEBT") for _ in range(3)],
    }
    lines, errs = _run(monkeypatch, tmp_path, payload, opt_in=False)
    assert lines == []
    assert errs == []


# --------------------------------------------------------------------------
# Live schema self-test (2026-08-31) — the W120 class, closed at the source.
#
# Everything above this line proves the digest handles a payload of a given
# SHAPE. None of it proves the reporter still EMITS that shape: the two files
# were free to drift apart for months, and did (`class` vs `classification`),
# because no test ever put the real producer and the real consumer in the same
# room. A fixture that agrees with the consumer's assumption confirms the
# assumption, not the world (W114).
#
# These two run the REAL reporter against the REAL ledger and assert only the
# keys the digest actually reads. They are deliberately narrow: they must not
# become a schema-freeze that blocks the reporter from ever growing a field.
# --------------------------------------------------------------------------

import subprocess  # noqa: E402
from pathlib import Path  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPORTER = _REPO_ROOT / "scripts" / "pending_arms_report.py"

# The exact key names organism_digest.pending_arms_overdue() dereferences.
# Keep this list in sync with that function BY EDITING BOTH — that is the whole
# point; a rename on one side has to fail here.
_DIGEST_READS_COUNTS_KEY = "tech_debt_overdue"
_DIGEST_READS_ENTRY_KEYS = ("class", "overdue", "artifact", "age_days")


def _live_payload():
    proc = subprocess.run(
        [sys.executable, str(_REPORTER), "--json"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(_REPO_ROOT),
    )
    # Judge the OUTPUT, not just the code: the reporter is a signaler that can
    # exit 0 while printing a diagnostic instead of JSON.
    assert proc.returncode == 0, f"reporter exited {proc.returncode}: {proc.stderr[-400:]}"
    assert proc.stdout.strip(), "reporter printed nothing on --json"
    return json.loads(proc.stdout)


def test_live_reporter_emits_the_counts_key_the_digest_reads():
    """counts.tech_debt_overdue is where the ALARM's number comes from.

    If this key is ever renamed, the digest silently reports 0 overdue rows and
    a real backlog reads as silence — the exact 2026-08-21 failure, one level up.
    """
    payload = _live_payload()
    counts = payload.get("counts")
    assert isinstance(counts, dict), f"counts missing or not a dict: {type(counts)}"
    assert _DIGEST_READS_COUNTS_KEY in counts, (
        f"reporter no longer emits counts.{_DIGEST_READS_COUNTS_KEY}; "
        "organism_digest.pending_arms_overdue() reads exactly that key and would "
        "go silent instead of erroring (W120)"
    )
    assert isinstance(counts[_DIGEST_READS_COUNTS_KEY], int)


def test_live_reporter_entries_carry_every_key_the_digest_dereferences():
    """`class`, not `classification` — pinned against the live producer.

    Narrow on purpose: presence only, never an exhaustive key set, so the
    reporter stays free to ADD fields without reddening this.
    """
    payload = _live_payload()
    entries = payload.get("entries")
    assert isinstance(entries, list) and entries, "reporter emitted no entries at all"
    missing = {
        k for k in _DIGEST_READS_ENTRY_KEYS if k not in entries[0]
    }
    assert not missing, (
        f"reporter entry schema lost {sorted(missing)}; the digest dereferences "
        f"exactly {list(_DIGEST_READS_ENTRY_KEYS)} — a rename here is invisible at "
        "runtime because .get() returns None instead of raising"
    )


def test_rows_mode_names_the_oldest_rows_and_default_mode_still_does_not(monkeypatch, tmp_path):
    """The `rows` opt-in is a THIRD state, not a widening of `1`.

    Guilt: `rows` names the oldest rows, oldest first, capped.
    Innocence: `1` still yields exactly one line — the assertion every test
    above depends on, and the reason a boot receptor stays terse.
    """
    entries = [
        _entry("TECH-DEBT", artifact=f"row-{i}") | {"age_days": i}
        for i in range(1, 15)
    ]
    payload = {"counts": {"total": 14, "tech_debt_overdue": 14}, "entries": entries}

    root = _fake_reporter(tmp_path, payload)
    monkeypatch.setattr(organism_digest, "_repo_root", lambda: root)

    monkeypatch.setenv("ORGANISM_DIGEST_PENDING_ARMS", "1")
    summary_only, errs = organism_digest.pending_arms_overdue()
    assert errs == []
    assert len(summary_only) == 1, "opting into the COUNT must not start costing ten boot lines"

    monkeypatch.setenv("ORGANISM_DIGEST_PENDING_ARMS", "rows")
    detailed, errs = organism_digest.pending_arms_overdue()
    assert errs == []
    assert len(detailed) == 1 + organism_digest.MAX_PENDING_ARMS_ROWS
    # Oldest first — the bug this replaced showed file-order-first and called it
    # "top" (measured live: 7d shown while the true oldest was 56d).
    assert "row-14" in detailed[0], "summary must name the OLDEST, not the first in file order"
    assert detailed[1].strip().startswith("· 14d row-14")
    assert detailed[-1].strip().startswith("· 5d row-5")


def test_live_producer_and_live_consumer_actually_agree(monkeypatch):
    """The two key-presence tests above compare the producer against constants
    this test file owns. That is not the contract: renaming the CONSUMER to read
    `classification` again while leaving those constants at `class` keeps them
    green (cross-family gate finding — the named agreement was not being tested).

    This one derives from BOTH sides: the real reporter, the real digest, no
    fake in between. If the producer renames the counts key the line disappears;
    if it renames the per-entry key the digest's own drift check fires and
    `errs` is non-empty; if the consumer renames either, the same happens. Only
    genuine agreement is silent.
    """
    monkeypatch.setenv("ORGANISM_DIGEST_PENDING_ARMS", "1")
    lines, errs = organism_digest.pending_arms_overdue()

    assert errs == [], f"producer and consumer disagree: {errs}"
    # The live ledger is deeply overdue and has been for months; a run that
    # produced NO line would mean the count key vanished, not that the backlog
    # cleared. If this repo ever genuinely reaches zero overdue rows, this
    # assertion is the right place to find out.
    assert len(lines) == 1, f"expected exactly the summary line, got {lines}"
    assert "armamenti sospesi OVERDUE" in lines[0]

    payload = _live_payload()
    n = payload["counts"][_DIGEST_READS_COUNTS_KEY]
    assert lines[0].startswith(f"{n} "), (
        f"the digest reported a different number ({lines[0]!r}) than the reporter "
        f"computed ({n}) — the two are reading different things"
    )


def test_string_ages_do_not_misorder_or_crash_the_oldest_line(monkeypatch, tmp_path):
    """A drifted payload can carry `age_days` as a STRING.

    Two ways that used to go wrong (cross-family gate): all-string ages sort
    lexically, so "9" beats "10" and the line says "oldest" about the youngest;
    mixed int/str raises inside the sort and the catch-all collapses the whole
    alarm to a generic "reporter failed". Neither may happen.
    """
    entries = [
        _entry("TECH-DEBT", artifact="row-9") | {"age_days": "9"},
        _entry("TECH-DEBT", artifact="row-10") | {"age_days": "10"},
        _entry("TECH-DEBT", artifact="row-int-7") | {"age_days": 7},
        _entry("TECH-DEBT", artifact="row-null") | {"age_days": None},
    ]
    root = _fake_reporter(tmp_path, {"counts": {"tech_debt_overdue": 4}, "entries": entries})
    monkeypatch.setattr(organism_digest, "_repo_root", lambda: root)
    monkeypatch.setenv("ORGANISM_DIGEST_PENDING_ARMS", "rows")

    lines, errs = organism_digest.pending_arms_overdue()
    assert errs == [], f"a stringly-typed age must not cost the alarm: {errs}"
    assert "row-10" in lines[0], f"10 is older than 9: {lines[0]!r}"
    assert lines[1].strip().startswith("· 10d row-10")
    assert lines[-1].strip().startswith("· ?d row-null"), "unknown age sorts LAST, never oldest"
