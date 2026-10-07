"""The session's HEALER_VERDICT line reaches the memo, strictly, and only
`incurable` ever lets the memo skip a spawn."""

import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT = Path(__file__).resolve().parents[1] / "healer_memo.py"
_MOD_PATH = Path(os.environ.get("HEALER_MEMO_UNDER_TEST", _DEFAULT))
_spec = importlib.util.spec_from_file_location("healer_memo_session", _MOD_PATH)
mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = mod
_spec.loader.exec_module(mod)

TRAILER = (
    "[claude-cascade] used: claude-token-1-env\n"
    "[cascade-result] v=1 job=pro-healer.sh slot=1 seat=A1 rc=0\n"
)

ROWS = {
    "V1-cured-guilt": ("HEALER_VERDICT: cured 3/3", "cured"),
    "V1-cured-count-mismatch-innocence": ("HEALER_VERDICT: cured 2/3", "unknown"),
    "V2-incurable-guilt": ("HEALER_VERDICT: incurable 0/5", "incurable"),
    "V2-incurable-count-mismatch-innocence": ("HEALER_VERDICT: incurable 1/5", "unknown"),
    "V3-partial-guilt": ("HEALER_VERDICT: partial 2/5", "partial"),
    "V3-partial-zero-innocence": ("HEALER_VERDICT: partial 0/5", "unknown"),
    "V3-partial-all-innocence": ("HEALER_VERDICT: partial 5/5", "unknown"),
    "V4-zero-total-innocence": ("HEALER_VERDICT: cured 0/0", "unknown"),
    "V4-cured-over-total-innocence": ("HEALER_VERDICT: cured 5/3", "unknown"),
    "V5-missing-line": ("result: 0 cure runtime eseguite — tutti FAILING-HONESTLY", "missing"),
    "V6-garbage-counts": ("HEALER_VERDICT: incurable five/five", "unknown"),
    "V6-garbage-word": ("HEALER_VERDICT: hopeless 0/5", "unknown"),
    "V7-markdown-wrapped": ("**HEALER_VERDICT: incurable 0/5**", "unknown"),
    "V7-trailing-prose": ("HEALER_VERDICT: incurable 0/5 (all operator-gated)", "unknown"),
    "V7-template-echoed": ("HEALER_VERDICT: cured|incurable|partial <n_cured>/<n_total>", "unknown"),
    "V8-surrounding-blanks": ("  HEALER_VERDICT: incurable 0/5  ", "incurable"),
    "V9-last-valid-wins": ("HEALER_VERDICT: incurable 0/5\nHEALER_VERDICT: partial 2/5", "partial"),
    "V9-later-garbage-voids": ("HEALER_VERDICT: incurable 0/5\nHEALER_VERDICT: garbage", "unknown"),
    "V9-later-markdown-voids": ("HEALER_VERDICT: incurable 0/5\n**HEALER_VERDICT: cured 5/5**", "unknown"),
    "V9-earlier-garbage-ignored": ("HEALER_VERDICT: garbage\nHEALER_VERDICT: incurable 0/5", "incurable"),
    "V10-cascade-trailer-after-line": ("HEALER_VERDICT: incurable 0/5\n" + TRAILER, "incurable"),
}


def test_session_verdict_branch_table():
    got = {row: mod.verdict_from_session(text + "\n") for row, (text, _) in ROWS.items()}
    assert got == {row: expected for row, (_, expected) in ROWS.items()}


def test_the_total_must_be_the_ticks_own():
    got = {
        "T1-own-total": mod.verdict_from_session("HEALER_VERDICT: incurable 0/2\n", 2),
        "T2-part-of-the-work": mod.verdict_from_session("HEALER_VERDICT: incurable 0/1\n", 2),
        "T3-more-than-the-work": mod.verdict_from_session("HEALER_VERDICT: cured 3/3\n", 2),
        "T4-missing-stays-missing": mod.verdict_from_session("result: none\n", 2),
    }
    assert got == {
        "T1-own-total": "incurable", "T2-part-of-the-work": "unknown",
        "T3-more-than-the-work": "unknown", "T4-missing-stays-missing": "missing",
    }


def test_cli_reads_the_log_and_a_missing_log_is_unknown(tmp_path):
    log = tmp_path / "session.log"
    log.write_text("## esito\nHEALER_VERDICT: incurable 0/4\n" + TRAILER)

    def cli(path: Path, *extra: str) -> str:
        return subprocess.run(
            [sys.executable, str(_MOD_PATH), "verdict-from-session", "--file", str(path), *extra],
            capture_output=True, text=True, check=True,
        ).stdout.strip()

    assert cli(log) == "incurable"
    assert cli(log, "--expect-total", "4") == "incurable"
    assert cli(log, "--expect-total", "5") == "unknown"
    assert cli(tmp_path / "absent.log") == "missing"


def _record(state: Path, fingerprint: str, verdict: str) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert mod.main([
        "record", "--state", str(state), "--fingerprint", fingerprint,
        "--verdict", verdict, "--spawned-at", now,
    ]) == 0


def _check(state: Path, fingerprint: str) -> int:
    return mod.main(["check", "--state", str(state), "--fingerprint", fingerprint])


def test_only_incurable_skips_an_unchanged_state(tmp_path):
    got = {}
    for verdict in ("incurable", "partial", "cured", "unknown"):
        state = tmp_path / f"{verdict}.json"
        _record(state, "same", verdict)
        got[verdict] = _check(state, "same")
    assert got == {"incurable": 3, "partial": 0, "cured": 0, "unknown": 0}


def test_a_new_dead_organ_spawns_even_after_incurable(tmp_path):
    state = tmp_path / "memo.json"
    old = {"dead_organs": [{"id": "a", "cure": "session"}]}
    new = {"dead_organs": [*old["dead_organs"], {"id": "b", "cure": "session"}]}
    _record(state, mod.fingerprint(old), "incurable")

    assert _check(state, mod.fingerprint(old)) == 3
    assert _check(state, mod.fingerprint(new)) == 0
    assert json.loads(state.read_text())["fingerprint"] == mod.fingerprint(old)
