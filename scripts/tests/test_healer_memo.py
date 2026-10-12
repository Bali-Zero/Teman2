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
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_MOD_PATH = Path(os.environ.get(
    "HEALER_MEMO_UNDER_TEST", Path(__file__).resolve().parents[1] / "healer_memo.py"
))
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
            {"id": "a", "status": "fail", "cure": "owner", "age_s": 100},
            {"id": "b", "status": "degraded", "cure": "session", "age_s": 7200},
        ],
        "arsenal_new_dead": ["claude:AUTH_DEAD"],
        "session_curable": {"registry": 1, "proprioception": 0, "home_fork": 0},
    }
    state_b = {
        "session_curable": {"home_fork": 0, "proprioception": 0, "registry": 1},
        "arsenal_new_dead": ["claude:AUTH_DEAD"],
        "dead_organs": [
            {"id": "b", "age_s": 7200, "cure": "session", "status": "degraded"},
            {"age_s": 100, "id": "a", "status": "fail", "cure": "owner"},
        ],
    }
    assert mod.fingerprint(state_a) == mod.fingerprint(state_b)


def test_fingerprint_stable_for_same_dead_set_observed_six_hours_later():
    base = {
        "dead_organs": [{"id": "a", "status": "fail", "cure": "owner", "age_s": 10}],
        "arsenal_new_dead": [],
        "session_curable": {"registry": 0, "proprioception": 0, "home_fork": 0},
    }
    later = json.loads(json.dumps(base))
    later["dead_organs"][0]["age_s"] += 6 * 3600

    assert mod.fingerprint(base) == mod.fingerprint(later)


def test_new_dead_organ_changes_fingerprint_and_spawns(tmp_path):
    base = {
        "dead_organs": [{"id": "a", "status": "fail", "cure": "owner", "age_s": 100}],
        "arsenal_new_dead": [],
        "session_curable": {"registry": 0, "proprioception": 0, "home_fork": 0},
    }
    changed = json.loads(json.dumps(base))
    changed["dead_organs"].append({"id": "b", "cure": "session", "age_s": 1})

    base_fp = mod.fingerprint(base)
    changed_fp = mod.fingerprint(changed)
    assert base_fp != changed_fp
    state = tmp_path / "memo.json"
    assert mod.main([
        "record", "--state", str(state), "--fingerprint", base_fp,
        "--verdict", "incurable", "--spawned-at", _now_iso(),
    ]) == 0
    assert mod.main([
        "check", "--state", str(state), "--fingerprint", changed_fp,
    ]) == mod.EXIT_SPAWN


def test_fingerprint_component_table():
    """Every key component moves the fingerprint (guilt); age/status/note never do (innocence)."""
    base = {
        "dead_organs": [{"id": "a", "cure": "owner", "status": "fail", "note": "n", "age_s": 1}],
        "diverged_probes": ["p:session"],
        "drifted_pairs": ["/x/y.sh"],
        "session_curable": {"registry": 0, "proprioception": 1, "home_fork": 0},
        "arsenal_new_dead": [],
        "receptor_failures": [],
    }
    edits = {
        "dead-id": lambda s: s["dead_organs"][0].update(id="b"),
        "dead-cure": lambda s: s["dead_organs"][0].update(cure="session"),
        "dead-label": lambda s: s["dead_organs"][0].update(label="com.new.job"),
        "dead-recovery-action": lambda s: s["dead_organs"][0].update(recovery_action="human_only"),
        "diverged-probe-cure": lambda s: s.update(diverged_probes=["p:owner"]),
        "drifted-pair": lambda s: s.update(drifted_pairs=["/x/z.sh"]),
        "count-registry": lambda s: s["session_curable"].update(registry=1),
        "count-proprioception": lambda s: s["session_curable"].update(proprioception=2),
        "count-home-fork": lambda s: s["session_curable"].update(home_fork=1),
        "arsenal-new-dead": lambda s: s.update(arsenal_new_dead=["claude:AUTH_DEAD"]),
        "receptor-failure": lambda s: s.update(receptor_failures=["registry-receptor-broken"]),
        "observation": lambda s: s.update(observations=["main-required-red:ci"]),
        "age-48h-innocence": lambda s: s["dead_organs"][0].update(age_s=48 * 3600),
        "status-innocence": lambda s: s["dead_organs"][0].update(status="degraded"),
        "note-innocence": lambda s: s["dead_organs"][0].update(note="other"),
    }
    got = {}
    for row, edit in edits.items():
        state = json.loads(json.dumps(base))
        edit(state)
        got[row] = mod.fingerprint(state) != mod.fingerprint(base)
    assert got == {row: not row.endswith("-innocence") for row in edits}


def test_observations_axis_is_optional_and_order_free():
    """The Mini healer's extra axis: absent/empty leaves the Pro hash untouched; order never matters."""
    base = {"dead_organs": [{"id": "a"}], "diverged_probes": ["p:owner"]}
    assert mod.fingerprint({**base, "observations": []}) == mod.fingerprint(base)
    one = {**base, "observations": ["a:1", "b:2"]}
    two = {**base, "observations": ["b:2", "a:1"]}
    assert mod.fingerprint(one) == mod.fingerprint(two) != mod.fingerprint(base)




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
