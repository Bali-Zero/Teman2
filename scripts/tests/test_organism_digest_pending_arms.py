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
