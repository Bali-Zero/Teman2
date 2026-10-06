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
import unittest
from pathlib import Path


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
import sys
cmd = sys.argv[1]
if cmd == "fingerprint": print("fixture-fingerprint")
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


class ProprioceptionCureSchemaTest(unittest.TestCase):
    def test_undeclared_cure_defaults_to_session_and_both_boards_carry_it(self) -> None:
        spec = importlib.util.spec_from_file_location("proprioception_under_test", PROPRIOCEPTION)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
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
