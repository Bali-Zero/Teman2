#!/usr/bin/env python3
"""End-to-end guilt/innocence tests for pro-healer receptors B and D."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
WRAPPER = Path(os.environ.get(
    "PRO_HEALER_UNDER_TEST", ROOT / "infra/launchagents/wrappers/pro-healer.sh"
))
PROPRIOCEPTION = Path(os.environ.get(
    "PROPRIOCEPTION_UNDER_TEST", ROOT / "scripts/proprioception.py"
))


def _executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


class ProHealerHarness(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.home = self.tmp / "home"
        self.repo = self.home / "nuzantara"
        self.bin = self.tmp / "bin"
        (self.repo / "scripts").mkdir(parents=True)
        (self.repo / "infra/healer").mkdir(parents=True)
        (self.repo / "infra/launchagents/wrappers").mkdir(parents=True)
        self.bin.mkdir()
        (self.repo / "CLAUDE.md").write_text("fixture\n")
        self.wrapper = self.repo / "infra/launchagents/wrappers/pro-healer.sh"
        shutil.copy2(WRAPPER, self.wrapper)
        shutil.copy2(ROOT / "scripts/healer_run_checks.py", self.repo / "scripts")
        (self.repo / "infra/healer/HEALER-PRO-MANDATE.md").write_text("test mandate\n")

        _executable(self.bin / "hostname", "#!/bin/sh\necho nuzantara\n")
        _executable(self.bin / "stat", """#!/bin/sh
for last do :; done
python3 -c 'import os,sys; print(int(os.path.getmtime(sys.argv[1])))' "$last"
""")
        self.marker = self.tmp / "claude-spawns"
        _executable(self.bin / "claude", """#!/bin/sh
echo spawned >> "$FAKE_CLAUDE_MARKER"
exit 0
""")
        self.cascade = self.tmp / "fake-cascade"
        _executable(self.cascade, "#!/bin/sh\nexec claude \"$@\"\n")
        _executable(self.repo / "scripts/healer_receptor_registry.py", """#!/usr/bin/env python3
print('{"dead": []}')
""")
        _executable(self.repo / "scripts/proprioception.py", """#!/usr/bin/env python3
import os
print(os.environ["FAKE_PROP_JSON"])
""")
        _executable(self.repo / "scripts/lint_home_fork.py", "#!/usr/bin/env python3\n")
        _executable(self.repo / "scripts/arsenal_probe.py", "#!/usr/bin/env python3\n")
        _executable(self.repo / "scripts/tg_notify.py", "#!/usr/bin/env python3\nprint('fake')\n")
        _executable(self.repo / "scripts/healer_memo.py", """#!/usr/bin/env python3
import os, sys
cmd = sys.argv[1]
if cmd == "fingerprint":
    with open(os.environ.get("FAKE_MEMO_INPUTS", os.devnull), "a") as fh:
        fh.write(sys.stdin.read().strip() + "\\n")
    print("fixture-fingerprint")
elif cmd == "check": print("MISS")
elif cmd == "verdict-from-escalations": print("curable")
""")
        self.arsenal = self.home / ".organism/arsenal/last.json"
        self.arsenal.parent.mkdir(parents=True)
        self._write_arsenal([])

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_arsenal(self, transitions: list[dict], ts: str = "2026-10-06T01:00:00Z") -> None:
        self.arsenal.write_text(json.dumps({"ts": ts, "transitions": transitions}))

    def _run(self, probes: list[dict]) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.update({
            "HOME": str(self.home),
            "PATH": f"{self.bin}:{env['PATH']}",
            "SSH_CONNECTION": "fixture",
            "FAKE_CLAUDE_MARKER": str(self.marker),
            "FAKE_PROP_JSON": json.dumps({"probes": probes}),
            "PRO_HEALER_CASCADE_BIN": str(self.cascade),
            "PRO_HEALER_PIDFILE": str(self.tmp / "healer.pid"),
            "FAKE_MEMO_INPUTS": str(self.tmp / "memo-inputs"),
        })
        return subprocess.run(
            ["bash", str(self.wrapper)], env=env, text=True, capture_output=True,
            timeout=15, check=False,
        )

    def _spawn_count(self) -> int:
        return len(self.marker.read_text().splitlines()) if self.marker.exists() else 0

    def _log(self) -> str:
        return (self.home / "logs/pro-healer/run.log").read_text()

    def test_b_guilt_p1_session_probe_spawns(self) -> None:
        result = self._run([
            {"id": "fixable", "status": "DIVERGED", "severity": "P1", "cure": "session"},
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._spawn_count(), 1)
        self.assertIn("ACTIONABLE: proprioception:1/1-session-curable", self._log())

    def test_b_invalid_cure_fails_visible_not_skipped(self) -> None:
        self._run([{"id": "fixable", "status": "DIVERGED", "severity": "P1", "cure": "Owner"}])
        self.assertIn("probe fixable: invalid cure 'Owner'", self._log())
        self.assertIn("ACTIONABLE: proprioception-receptor-broken", self._log())

    def test_b_innocence_owner_and_p3_skip_with_ledger(self) -> None:
        result = self._run([
            {"id": "owner_only", "status": "DIVERGED", "severity": "P1", "cure": "owner"},
            {"id": "p3_only", "status": "DIVERGED", "severity": "P3", "cure": "session"},
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._spawn_count(), 0, self._log())
        self.assertIn(
            "skip: 2 diverged, none session-curable at P0-P1: owner_only,p3_only", self._log()
        )

    def test_d_guilt_newer_report_timestamp_spawns_and_persists_tuple(self) -> None:
        state = self.home / ".organism/healer-pro/arsenal-last-acted.json"
        state.parent.mkdir(parents=True)
        state.write_text(json.dumps({"last_acted": [
            {"seat": "claude", "state": "AUTH_DEAD", "report_ts": "2026-10-06T00:00:00Z"}
        ]}))
        self._write_arsenal([
            {"seat": "claude", "from": "LIVE", "to": "AUTH_DEAD"},
        ])
        result = self._run([{"id": "clean", "status": "RECONCILED", "severity": "P1"}])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._spawn_count(), 1)
        self.assertIn(
            {"seat": "claude", "state": "AUTH_DEAD", "report_ts": "2026-10-06T01:00:00Z"},
            json.loads(state.read_text())["last_acted"],
        )

    def test_d_innocence_same_report_timestamp_next_tick_skips_with_ledger(self) -> None:
        self._write_arsenal([
            {"seat": "claude", "from": "LIVE", "to": "AUTH_DEAD"},
        ])
        probes = [{"id": "clean", "status": "RECONCILED", "severity": "P1"}]
        self.assertEqual(self._run(probes).returncode, 0)
        self.assertEqual(self._run(probes).returncode, 0)
        self.assertEqual(self._spawn_count(), 1)
        self.assertIn(
            "skip: arsenal transition already acted: claude:AUTH_DEAD report-ts=2026-10-06T01:00:00Z",
            self._log(),
        )

    def test_d_corrupt_state_reads_as_never_acted_and_says_so(self) -> None:
        state = self.home / ".organism/healer-pro/arsenal-last-acted.json"
        state.parent.mkdir(parents=True)
        state.write_text("{truncated")
        self._write_arsenal([{"seat": "claude", "from": "LIVE", "to": "AUTH_DEAD"}])
        self.assertEqual(self._run([{"id": "clean", "status": "RECONCILED", "severity": "P1"}]).returncode, 0)
        self.assertEqual(self._spawn_count(), 1)
        self.assertIn("arsenal state unreadable (JSONDecodeError), treated as never acted", self._log())
        self.assertEqual(json.loads(state.read_text())["last_acted"][0]["report_ts"], "2026-10-06T01:00:00Z")


    def test_memo_key_changes_when_two_probes_swap_cures(self) -> None:
        for a, b in (("owner", "session"), ("session", "owner")):
            self._run([{"id": "a", "status": "DIVERGED", "severity": "P1", "cure": a},
                       {"id": "b", "status": "DIVERGED", "severity": "P1", "cure": b}])
        keys = [json.loads(line)["diverged_probes"]
                for line in (self.tmp / "memo-inputs").read_text().splitlines()]
        self.assertEqual(len(keys), 2)
        self.assertNotEqual(keys[0], keys[1])


def _proprioception():
    spec = importlib.util.spec_from_file_location("proprioception_under_test", PROPRIOCEPTION)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _seat(status: str) -> str:
    return json.dumps({"status": status, "seat": "x"})


def _launchd(verdict: str, marker: str, **extra: str) -> str:
    return json.dumps({"verdict": verdict, "log_marker": marker, **extra})


TCC = _launchd("DEAD-GREEN", "Operation not permitted")
ROOT_DIV = "DIVERGED: /usr/local/lib/wa.sh != scripts/wa.sh — a fix is stranded on one side (x)"
ROOT_NOREPO = "NO REPO COUNTERPART: /usr/local/bin/k.sh executes live with no source of truth in repo"
USER_NOREPO = "NO REPO COUNTERPART: /Users/u/scripts/y.sh executes live with no source of truth in repo"

# (branch-row, evidence, n, expected). Every branch of cure_for_result that returns owner or
# falls back has a guilt row (owner) and an innocence row (stays session); n=None means len(evidence).
ARSENAL_ROWS = [
    ("A1-parse-guilt", [_seat("AUTH_DEAD")], None, "owner"),
    ("A1-parse-innocence-cut-at-160", [json.dumps({"status": "AUTH_DEAD", "detail": "x" * 200})[:160]], None, "session"),
    ("A1-parse-innocence-not-a-string", [None], None, "session"),
    ("A2-coverage-guilt", [_seat("AUTH_DEAD"), _seat("BALANCE_DEAD")], None, "owner"),
    ("A2-coverage-innocence", [_seat("AUTH_DEAD")], 2, "session"),
    ("A3-nonempty-innocence", [], 0, "session"),
    ("A4-all-guilt", [_seat("AUTH_DEAD"), _seat("AUTH_DEAD")], None, "owner"),
    ("A4-all-innocence", [_seat("AUTH_DEAD"), _seat("MODEL_ERR"), _seat("UNKNOWN_ERR")], None, "session"),
    ("A5-state-set-guilt", [_seat("BALANCE_DEAD")], None, "owner"),
    ("A5-state-set-innocence-caseless", [_seat("auth_dead")], None, "session"),
    ("A5-state-set-innocence-prefix", [_seat("AUTH_DEAD_SOFT")], None, "session"),
    ("A5-state-set-innocence-quota", [_seat("QUOTA_DEAD")], None, "session"),
    ("A6-status-key-innocence", [json.dumps({"seat": "x"})], None, "session"),
]
LAUNCHD_ROWS = [
    ("L1-parse-guilt", [TCC], None, "owner"),
    ("L1-parse-innocence-cut-at-160",
     [_launchd("DEAD-GREEN", "Operation not permitted", program="x" * 200)[:160]], None, "session"),
    ("L1-parse-innocence-not-a-string", [None], None, "session"),
    ("L2-coverage-guilt", [TCC, TCC], None, "owner"),
    ("L2-coverage-innocence", [TCC], 2, "session"),
    ("L3-nonempty-innocence", [], 0, "session"),
    ("L4-all-innocence", [TCC, _launchd("FAILING-HONESTLY", "exit 1")], None, "session"),
    ("L5-verdict-innocence", [_launchd("DEAD-NONZERO", "Operation not permitted")], None, "session"),
    ("L6-tcc-marker-innocence", [_launchd("DEAD-GREEN", "exit 0")], None, "session"),
    ("L7-caseless-marker-guilt", [_launchd("DEAD-GREEN", "OPERATION NOT PERMITTED")], None, "owner"),
]
HOME_FORK_ROWS = [
    ("H1-diverged-form-guilt", [ROOT_DIV], None, "owner"),
    ("H1-diverged-form-innocence", ["DIVERGED /usr/local/lib/wa.sh != scripts/wa.sh"], None, "session"),
    ("H2-norepo-form-guilt", [ROOT_NOREPO], None, "owner"),
    ("H2-norepo-form-innocence", [USER_NOREPO], None, "session"),
    ("H3-coverage-innocence", [ROOT_DIV, "CHECKOUT-STALE: origin/main unknown"], 2, "session"),
    ("H4-nonempty-innocence", [], 0, "session"),
    ("H5-all-guilt", [ROOT_DIV, ROOT_NOREPO], None, "owner"),
    ("H5-all-innocence", [ROOT_DIV, USER_NOREPO], None, "session"),
    ("H6-stat-error-innocence", ["DIVERGED: /usr/local/vanished.sh != scripts/v.sh — x"], None, "session"),
    ("H7-expanduser-guilt", ["DIVERGED: ~/root.sh != scripts/root.sh — x"], None, "owner"),
]


class CureForResultTest(unittest.TestCase):
    """The classifier receptor B skips on: owner only when EVERY finding proves it."""

    def setUp(self) -> None:
        self.mod = _proprioception()

    def _cures(self, pid: str, rows: list) -> dict[str, str]:
        return {name: self.mod.cure_for_result({"id": pid}, self.mod.DIVERGED,
                                               len(evidence) if n is None else n, evidence)
                for name, evidence, n, _ in rows}

    def test_arsenal_branches(self) -> None:
        self.assertEqual(self._cures("arsenal_seats", ARSENAL_ROWS), {r[0]: r[3] for r in ARSENAL_ROWS})

    def test_launchd_branches(self) -> None:
        self.assertEqual(self._cures("launchd_liveness", LAUNCHD_ROWS), {r[0]: r[3] for r in LAUNCHD_ROWS})

    def test_home_fork_branches(self) -> None:
        def stat(path: Path, *args: object, **kwargs: object) -> types.SimpleNamespace:
            if "vanished" in str(path):
                raise FileNotFoundError(str(path))
            root = str(path).startswith("/usr/local/") or str(path) == os.path.expanduser("~/root.sh")
            return types.SimpleNamespace(st_uid=0 if root else 501)
        with mock.patch.object(self.mod.Path, "stat", stat):
            cures = self._cures("home_fork_scripts", HOME_FORK_ROWS)
        self.assertEqual(cures, {r[0]: r[3] for r in HOME_FORK_ROWS})

    def test_common_branches(self) -> None:
        cure, m = self.mod.cure_for_result, self.mod
        with self.subTest(branch="C1-not-diverged-guilt"):
            self.assertEqual(cure({"id": "tailnet_policy_drift", "cure": "owner"}, m.UNPROBEABLE, 0, []), "owner")
        with self.subTest(branch="C1-not-diverged-innocence"):
            self.assertEqual(cure({"id": "arsenal_seats"}, m.RECONCILED, 1, [_seat("AUTH_DEAD")]), "session")
        with self.subTest(branch="C2-declared-guilt"):
            self.assertEqual(cure({"id": "git_alignment", "cure": "owner"}, m.DIVERGED, 1, ["behind 12"]), "owner")
        with self.subTest(branch="C2-declared-innocence"):
            self.assertEqual(cure({"id": "regulatory_promotion", "cure": "pr"}, m.DIVERGED, 1, ["x"]), "pr")
        with self.subTest(branch="C3-default-innocence"):
            self.assertEqual(cure({"id": "worktree_gate_shim"}, m.DIVERGED, 2, ["a", "b"]), "session")

    def test_registry_static_cures_and_validation(self) -> None:
        declared = {e["id"]: e.get("cure", "session") for e in self.mod.DEFAULT_REGISTRY}
        self.assertEqual({k: v for k, v in declared.items() if v != "session"}, {
            "tailnet_policy_drift": "owner", "git_alignment": "owner",
            "regulatory_promotion": "pr", "door_canon_parity": "pr"})
        self.assertEqual(self.mod.validate_registry(self.mod.DEFAULT_REGISTRY), [])
        bad = [dict(e, cure="Owner") if e["id"] == "git_alignment" else e for e in self.mod.DEFAULT_REGISTRY]
        self.assertTrue(any("invalid cure" in err for err in self.mod.validate_registry(bad)))


class ProprioceptionCureSchemaTest(unittest.TestCase):
    def test_undeclared_cure_defaults_to_session_and_both_boards_carry_it(self) -> None:
        mod = _proprioception()
        with tempfile.TemporaryDirectory() as td:
            mod.REPORT_DIR = Path(td)
            probe = mod.verdict(
                "fixture", "a<->b", "home<->repo", mod.DIVERGED, "P1", 1,
                ["drift"], "fix it", time.monotonic(),
            )
            report = {
                "machine": "fixture", "ts": "2026-10-06T00:00:00Z", "summary": "fixture",
                "runner_version": mod.RUNNER_VERSION, "config_source": "test", "config_sha": "x",
                "repo_head": "x", "probes_run": 1, "probes_expected": 1,
                "probes": [probe], "unwatched_classes": [],
            }
            mod.write_report(report)
            self.assertEqual(probe["cure"], "session")
            self.assertEqual(json.loads((Path(td) / "last.json").read_text())["probes"][0]["cure"], "session")
            self.assertIn("cure=session", (Path(td) / "last.md").read_text())


if __name__ == "__main__":
    unittest.main()
