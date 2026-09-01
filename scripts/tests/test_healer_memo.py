"""healer_memo — D-004 memoization tests (~/.tokenaudit/DECISIONS.md).

Guards the invariant the healer wrapper leans on: SKIP (exit 3) only when the
organ-state fingerprint is byte-identical to the last spawn AND the last
verdict was "incurable" AND the spawn is still fresh AND the skip streak is
under budget — every other combination, including any memo-tooling failure,
must SPAWN (exit 0). A false SKIP silently buries a real cure (superscar #2);
a false SPAWN merely costs one wasted headless session, so every ambiguous
branch below asserts SPAWN, never SKIP.
"""

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_MOD_PATH = Path(__file__).resolve().parents[1] / "healer_memo.py"
_spec = importlib.util.spec_from_file_location("healer_memo", _MOD_PATH)
mod = importlib.util.module_from_spec(_spec)
sys.modules["healer_memo"] = mod
_spec.loader.exec_module(mod)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _now_iso() -> str:
    return _iso(datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# fingerprint()
# ---------------------------------------------------------------------------


def test_fingerprint_is_deterministic_across_key_and_list_order():
    state_a = {
        "dead_organs": [
            {"id": "a", "status": "fail", "recovery_action": "human_only", "age_s": 100},
            {"id": "b", "status": "degraded", "recovery_action": "", "age_s": 7200},
        ],
        "diverged_probes": ["p2", "p1"],
        "drifted_pairs": ["pair-x"],
        "arsenal_new_dead": ["claude:AUTH_DEAD"],
        "reasons": "registry:2-dead-organs proprioception:1-diverged",
    }
    state_b = {
        "reasons": "proprioception:1-diverged registry:2-dead-organs",
        "arsenal_new_dead": ["claude:AUTH_DEAD"],
        "drifted_pairs": ["pair-x"],
        "diverged_probes": ["p1", "p2"],
        "dead_organs": [
            {"id": "b", "age_s": 7200, "recovery_action": "", "status": "degraded"},
            {"age_s": 100, "id": "a", "status": "fail", "recovery_action": "human_only"},
        ],
    }
    assert mod.fingerprint(state_a) == mod.fingerprint(state_b)


def test_fingerprint_sensitive_to_organ_status_change():
    base = {
        "dead_organs": [{"id": "a", "status": "fail", "recovery_action": "x", "age_s": 10}],
        "diverged_probes": [],
        "drifted_pairs": [],
        "arsenal_new_dead": [],
        "reasons": "registry:1-dead-organs",
    }
    changed = json.loads(json.dumps(base))
    changed["dead_organs"][0]["status"] = "degraded"

    assert mod.fingerprint(base) != mod.fingerprint(changed)


def test_fingerprint_sensitive_to_age_bucket_change():
    base = {
        "dead_organs": [{"id": "a", "status": "fail", "recovery_action": "x", "age_s": 100}],
        "diverged_probes": [],
        "drifted_pairs": [],
        "arsenal_new_dead": [],
        "reasons": "",
    }
    later = json.loads(json.dumps(base))
    later["dead_organs"][0]["age_s"] = 100 + 3700  # crosses a 1h bucket boundary

    assert mod.fingerprint(base) != mod.fingerprint(later)


def test_fingerprint_age_bucket_caps_and_never_raises_on_bad_age():
    huge = {
        "dead_organs": [{"id": "a", "status": "fail", "recovery_action": "", "age_s": 999999}],
        "diverged_probes": [], "drifted_pairs": [], "arsenal_new_dead": [], "reasons": "",
    }
    huger = json.loads(json.dumps(huge))
    huger["dead_organs"][0]["age_s"] = 9999999
    malformed = json.loads(json.dumps(huge))
    malformed["dead_organs"][0]["age_s"] = "not-a-number"

    # Both huge ages saturate the same cap bucket -> identical fingerprint.
    assert mod.fingerprint(huge) == mod.fingerprint(huger)
    # A malformed age must not raise.
    mod.fingerprint(malformed)


# ---------------------------------------------------------------------------
# check()
# ---------------------------------------------------------------------------


def test_check_spawns_when_no_state_file(tmp_path):
    rc = mod.main(
        ["check", "--state", str(tmp_path / "missing.json"), "--fingerprint", "abc"]
    )
    assert rc == mod.EXIT_SPAWN


def test_check_skips_on_identical_fingerprint_incurable_and_fresh(tmp_path, capsys):
    state = tmp_path / "memo.json"
    rc = mod.main(
        ["record", "--state", str(state), "--fingerprint", "deadbeef",
         "--verdict", "incurable", "--spawned-at", _now_iso()]
    )
    assert rc == 0

    rc = mod.main(["check", "--state", str(state), "--fingerprint", "deadbeef"])
    assert rc == mod.EXIT_SKIP
    out = capsys.readouterr().out
    assert "SKIP" in out

    persisted = json.loads(state.read_text())
    assert persisted["skips"] == 1


def test_check_spawns_when_fingerprint_differs(tmp_path):
    state = tmp_path / "memo.json"
    mod.main(
        ["record", "--state", str(state), "--fingerprint", "aaaa",
         "--verdict", "incurable", "--spawned-at", _now_iso()]
    )
    rc = mod.main(["check", "--state", str(state), "--fingerprint", "bbbb"])
    assert rc == mod.EXIT_SPAWN


@pytest.mark.parametrize("verdict", ["cured", "unknown"])
def test_check_spawns_when_verdict_not_incurable(tmp_path, verdict):
    state = tmp_path / "memo.json"
    mod.main(
        ["record", "--state", str(state), "--fingerprint", "abc",
         "--verdict", verdict, "--spawned-at", _now_iso()]
    )
    rc = mod.main(["check", "--state", str(state), "--fingerprint", "abc"])
    assert rc == mod.EXIT_SPAWN


def test_check_spawns_when_last_spawn_is_stale(tmp_path):
    state = tmp_path / "memo.json"
    old = _iso(datetime.now(timezone.utc) - timedelta(hours=48))
    mod.main(
        ["record", "--state", str(state), "--fingerprint", "abc",
         "--verdict", "incurable", "--spawned-at", old]
    )
    rc = mod.main(
        ["check", "--state", str(state), "--fingerprint", "abc", "--max-age-h", "24"]
    )
    assert rc == mod.EXIT_SPAWN


def test_check_spawns_after_max_skips_streak(tmp_path):
    state = tmp_path / "memo.json"
    mod.main(
        ["record", "--state", str(state), "--fingerprint", "abc",
         "--verdict", "incurable", "--spawned-at", _now_iso()]
    )
    # Exhaust the skip budget (default max-skips=3): skip 3 times, 4th must spawn.
    for _ in range(3):
        rc = mod.main(
            ["check", "--state", str(state), "--fingerprint", "abc", "--max-skips", "3"]
        )
        assert rc == mod.EXIT_SKIP
    rc = mod.main(
        ["check", "--state", str(state), "--fingerprint", "abc", "--max-skips", "3"]
    )
    assert rc == mod.EXIT_SPAWN


def test_check_kill_switch_always_spawns(tmp_path, monkeypatch):
    state = tmp_path / "memo.json"
    mod.main(
        ["record", "--state", str(state), "--fingerprint", "abc",
         "--verdict", "incurable", "--spawned-at", _now_iso()]
    )
    monkeypatch.setenv("PRO_HEALER_MEMO", "0")
    rc = mod.main(["check", "--state", str(state), "--fingerprint", "abc"])
    assert rc == mod.EXIT_SPAWN


# ---------------------------------------------------------------------------
# record()
# ---------------------------------------------------------------------------


def test_record_is_atomic_and_resets_skip_counter(tmp_path):
    state = tmp_path / "sub" / "memo.json"  # parent dir must be created
    mod.main(
        ["record", "--state", str(state), "--fingerprint", "111",
         "--verdict", "incurable", "--spawned-at", _now_iso()]
    )
    # Simulate a few skips.
    mod.main(["check", "--state", str(state), "--fingerprint", "111"])
    mod.main(["check", "--state", str(state), "--fingerprint", "111"])
    assert json.loads(state.read_text())["skips"] == 2

    # A fresh record() (new tick, verdict changed) must reset skips to 0.
    mod.main(
        ["record", "--state", str(state), "--fingerprint", "222",
         "--verdict", "cured", "--spawned-at", _now_iso()]
    )
    persisted = json.loads(state.read_text())
    assert persisted == {
        "fingerprint": "222",
        "verdict": "cured",
        "spawned_at": persisted["spawned_at"],
        "skips": 0,
        "recorded_at": persisted["recorded_at"],
    }
    # No leftover .tmp* file after os.replace.
    assert not list(state.parent.glob("*.tmp*"))


# ---------------------------------------------------------------------------
# verdict-from-escalations
# ---------------------------------------------------------------------------


def _escalation_line(ts: float, summary: str) -> str:
    return json.dumps(
        {
            "job": "healer_pro_tick",
            "type": "healer_pro_finding",
            "priority": "HIGH",
            "error_summary": summary,
            "machine": "pro",
            "ts": ts,
            "status": "pending",
            "_writer": "pro.healer",
        }
    )


def test_verdict_from_escalations_reads_incurable(tmp_path):
    now = datetime.now(timezone.utc).timestamp()
    log = tmp_path / "escalations.jsonl"
    log.write_text(
        _escalation_line(now, "3 dead organs, 0/3 curable in Pro-runtime whitelist") + "\n"
    )
    rc_out = _run_verdict(log, _iso(datetime.now(timezone.utc) - timedelta(minutes=5)))
    assert rc_out == "incurable"


def test_verdict_from_escalations_reads_cured(tmp_path):
    now = datetime.now(timezone.utc).timestamp()
    log = tmp_path / "escalations.jsonl"
    log.write_text(
        _escalation_line(now, "2 dead organs, 2/2 curable, both kickstarted OK") + "\n"
    )
    rc_out = _run_verdict(log, _iso(datetime.now(timezone.utc) - timedelta(minutes=5)))
    assert rc_out == "cured"


def test_verdict_from_escalations_no_matching_line_is_unknown(tmp_path):
    log = tmp_path / "escalations.jsonl"
    log.write_text(_escalation_line(0, "0/5 curable, ancient") + "\n")  # ts=epoch 0, excluded
    rc_out = _run_verdict(log, _iso(datetime.now(timezone.utc) - timedelta(minutes=5)))
    assert rc_out == "unknown"


def test_verdict_from_escalations_missing_file_is_unknown(tmp_path):
    rc_out = _run_verdict(tmp_path / "does-not-exist.jsonl", _now_iso())
    assert rc_out == "unknown"


def test_verdict_from_escalations_picks_newest_matching_line(tmp_path):
    log = tmp_path / "escalations.jsonl"
    now = datetime.now(timezone.utc).timestamp()
    lines = [
        _escalation_line(now - 60, "1 dead organ, 0/1 curable"),
        _escalation_line(now, "1 dead organ, 1/1 curable, cured this tick"),
    ]
    log.write_text("\n".join(lines) + "\n")
    rc_out = _run_verdict(log, _iso(datetime.now(timezone.utc) - timedelta(minutes=5)))
    assert rc_out == "cured"


def test_verdict_from_escalations_ignores_lines_before_since(tmp_path):
    log = tmp_path / "escalations.jsonl"
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=6)).timestamp()
    log.write_text(_escalation_line(old_ts, "0/4 curable") + "\n")
    rc_out = _run_verdict(log, _iso(datetime.now(timezone.utc) - timedelta(hours=1)))
    assert rc_out == "unknown"


def _run_verdict(path: Path, since_iso: str) -> str:
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = mod.main(
            ["verdict-from-escalations", "--file", str(path), "--since", since_iso]
        )
    assert rc == 0
    return buf.getvalue().strip()
