#!/usr/bin/env python3
"""End-to-end guilt/innocence tests for pro-healer receptors A-D."""

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
HEALER_RUN_CHECKS = Path(os.environ.get(
    "HEALER_RUN_CHECKS_UNDER_TEST", ROOT / "scripts/healer_run_checks.py"
))
HEALER_MEMO = Path(os.environ.get(
    "HEALER_MEMO_UNDER_TEST", ROOT / "scripts/healer_memo.py"
))
CLEAN_PROBES = [{"id": "clean", "status": "RECONCILED", "severity": "P1"}]


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
        shutil.copy2(HEALER_RUN_CHECKS, self.repo / "scripts")
        (self.repo / "infra/healer/HEALER-PRO-MANDATE.md").write_text("test mandate\n")

        _executable(self.bin / "hostname", "#!/bin/sh\necho nuzantara\n")
        _executable(self.bin / "stat", """#!/bin/sh
for last do :; done
python3 -c 'import os,sys; print(int(os.path.getmtime(sys.argv[1])))' "$last"
""")
        self.marker = self.tmp / "claude-spawns"
        _executable(self.bin / "claude", """#!/bin/sh
echo spawned >> "$FAKE_CLAUDE_MARKER"
printf '%s' "$1" > "$FAKE_PROMPT"
printf '%s\n' "${FAKE_SESSION_OUTPUT:-}"
exit 0
""")
        self.cascade = self.tmp / "fake-cascade"
        _executable(self.cascade, "#!/bin/sh\nexec claude \"$@\"\n")
        _executable(self.repo / "scripts/healer_receptor_registry.py", """#!/usr/bin/env python3
import os, sys
print(os.environ.get("FAKE_REG_JSON", '{"dead": []}'))
sys.exit(int(os.environ.get("FAKE_REG_RC", "0")))
""")
        _executable(self.repo / "scripts/proprioception.py", """#!/usr/bin/env python3
import os
print(os.environ["FAKE_PROP_JSON"])
""")
        _executable(self.repo / "scripts/lint_home_fork.py", """#!/usr/bin/env python3
import os, sys
sys.stderr.write(os.environ.get("FAKE_LHF_STDERR", ""))
print(os.environ.get("FAKE_LHF_JSON", '{"check_breaches": []}'))
sys.exit(int(os.environ.get("FAKE_LHF_RC", "0")))
""")
        _executable(self.repo / "scripts/arsenal_probe.py", "#!/usr/bin/env python3\n")
        _executable(self.repo / "scripts/tg_notify.py", "#!/usr/bin/env python3\nprint('fake')\n")
        _executable(self.repo / "scripts/healer_memo.py", """#!/usr/bin/env python3
import os, subprocess, sys
cmd = sys.argv[1]
if cmd == "fingerprint":
    with open(os.environ.get("FAKE_MEMO_INPUTS", os.devnull), "a") as fh:
        fh.write(sys.stdin.read().strip() + "\\n")
    print("fixture-fingerprint")
elif cmd == "check": print("MISS")
elif cmd == "verdict-from-escalations": print(os.environ.get("FAKE_ESC_VERDICT", "unknown"))
elif cmd == "verdict-from-session":
    raise SystemExit(subprocess.call([sys.executable, os.environ["REAL_MEMO"], *sys.argv[1:]]))
elif cmd == "record":
    with open(os.environ["FAKE_RECORDED"], "a") as fh:
        fh.write(sys.argv[sys.argv.index("--verdict") + 1] + "\\n")
""")
        self.arsenal = self.home / ".organism/arsenal/last.json"
        self.arsenal.parent.mkdir(parents=True)
        self._write_arsenal([])

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_arsenal(self, transitions: list[dict], ts: str = "2026-10-06T01:00:00Z") -> None:
        self.arsenal.write_text(json.dumps({"ts": ts, "transitions": transitions}))

    def _run(
        self,
        probes: list[dict],
        *,
        registry: dict | str | None = None,
        registry_rc: int = 0,
        home_fork: dict | str | None = None,
        home_fork_rc: int = 0,
        session_output: str = "",
        esc_verdict: str = "unknown",
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.update({
            "HOME": str(self.home),
            "PATH": f"{self.bin}:{env['PATH']}",
            "SSH_CONNECTION": "fixture",
            "FAKE_CLAUDE_MARKER": str(self.marker),
            "FAKE_PROP_JSON": json.dumps({"probes": probes}),
            "FAKE_REG_JSON": registry if isinstance(registry, str)
            else json.dumps(registry or {"dead": []}),
            "FAKE_REG_RC": str(registry_rc),
            "FAKE_LHF_JSON": home_fork if isinstance(home_fork, str)
            else json.dumps(home_fork or {"check_breaches": []}),
            "FAKE_LHF_STDERR": "warning: fixture noise on stderr\n",
            "FAKE_LHF_RC": str(home_fork_rc),
            "PRO_HEALER_CASCADE_BIN": str(self.cascade),
            "PRO_HEALER_PIDFILE": str(self.tmp / "healer.pid"),
            "FAKE_MEMO_INPUTS": str(self.tmp / "memo-inputs"),
            "FAKE_PROMPT": str(self.tmp / "prompt"),
            "FAKE_SESSION_OUTPUT": session_output,
            "FAKE_ESC_VERDICT": esc_verdict,
            "REAL_MEMO": str(HEALER_MEMO),
            "FAKE_RECORDED": str(self.tmp / "recorded"),
        })
        return subprocess.run(
            ["bash", str(self.wrapper)], env=env, text=True, capture_output=True,
            timeout=15, check=False,
        )

    def _spawn_count(self) -> int:
        return len(self.marker.read_text().splitlines()) if self.marker.exists() else 0

    def _log(self) -> str:
        return (self.home / "logs/pro-healer/run.log").read_text()

    def test_a_guilt_session_curable_dead_organ_spawns(self) -> None:
        registry = {"dead": [{"id": "fixable", "cure": "session"}]}
        result = self._run(CLEAN_PROBES, registry=registry, registry_rc=1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._spawn_count(), 1)
        self.assertIn("ACTIONABLE: registry:1/1-dead 0-findings", self._log())
        self.assertNotIn("alive_with_findings", self._log())

    def test_a_reason_names_dead_session_dead_and_findings(self) -> None:
        registry = {
            "dead": [{"id": "fixable", "cure": "session"}, {"id": "tcc", "cure": "owner"}],
            "findings": [{"id": "kbli"}, {"id": "launchd"}],
        }
        result = self._run(CLEAN_PROBES, registry=registry, registry_rc=1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._spawn_count(), 1)
        self.assertIn("ACTIONABLE: registry:1/2-dead 2-findings", self._log())
        self.assertIn("registry alive_with_findings: 2 (kbli,launchd)", self._log())

    def test_a_innocence_findings_only_do_not_spawn(self) -> None:
        registry = {"dead": [], "findings": [{"id": "kbli"}]}
        result = self._run(CLEAN_PROBES, registry=registry, registry_rc=0)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._spawn_count(), 0, self._log())
        self.assertIn("registry alive_with_findings: 1 (kbli)", self._log())
        self.assertNotIn("ACTIONABLE", self._log())

    def test_a_malformed_findings_bucket_is_a_broken_receptor(self) -> None:
        registry = {"dead": [], "findings": "kbli"}
        result = self._run(CLEAN_PROBES, registry=registry, registry_rc=0)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._spawn_count(), 1)
        self.assertIn("ACTIONABLE: registry-receptor-broken", self._log())

    def test_verdict_total_counts_every_receptor_item(self) -> None:
        live = self.tmp / "live-user.sh"
        live.write_text("fixture\n")
        drift = {"check_breaches": [f"DIVERGED: {live} != scripts/live-user.sh — fixture"]}
        self._write_arsenal([{"seat": "claude", "from": "LIVE", "to": "AUTH_DEAD"}])
        probes = [{"id": "fixable", "status": "DIVERGED", "severity": "P1"}]
        rows = {  # registry session 1 + probe 1 + drift 1 + arsenal 1 (+ broken receptor 1)
            "dead-probe-drift-arsenal": dict(registry={"dead": [{"id": "x"}]}, registry_rc=1),
            "broken-probe-drift-arsenal": dict(registry={"receptor_broken": "x"}, registry_rc=2),
        }
        got = {}
        for row, kwargs in rows.items():
            (self.home / ".organism/healer-pro/arsenal-last-acted.json").unlink(missing_ok=True)
            self._run(probes, home_fork=drift, home_fork_rc=1, **kwargs)
            got[row] = (self.tmp / "prompt").read_text().rsplit("<n_cured>/", 1)[1]
        self.assertEqual(got, {"dead-probe-drift-arsenal": "4", "broken-probe-drift-arsenal": "4"})

    def test_session_verdict_reaches_the_memo_record(self) -> None:
        two = [{"id": f"fix-{x}", "status": "DIVERGED", "severity": "P1"} for x in "ab"]
        rows = {  # row: (session output, escalation verdict, recorded verdict, ledger token)
            "cured": ("HEALER_VERDICT: cured 2/2", "unknown", "cured", None),
            "incurable": ("HEALER_VERDICT: incurable 0/2", "unknown", "incurable", None),
            "partial": ("HEALER_VERDICT: partial 1/2", "unknown", "partial", None),
            "part-of-the-work": ("HEALER_VERDICT: incurable 0/1", "incurable", "unknown", "invalid"),
            "missing": ("result: 0 cure runtime eseguite", "unknown", "unknown", "missing"),
            "missing-escalation-fallback": ("", "incurable", "incurable", "missing"),
            "garbage": ("HEALER_VERDICT: garbage", "unknown", "unknown", "invalid"),
            "later-garbage-no-fallback": (
                "HEALER_VERDICT: incurable 0/2\nHEALER_VERDICT: garbage", "incurable", "unknown", "invalid"),
            "line-beats-escalation": ("HEALER_VERDICT: cured 2/2", "incurable", "cured", None),
        }
        got = {}
        for row, (output, esc, _, _) in rows.items():
            self._run(two, session_output=output, esc_verdict=esc)
            tick = self._log().rsplit("ACTIONABLE:", 1)[1]
            ledger = [t for t in ("missing", "invalid") if f"verdict-line-{t}" in tick]
            got[row] = ((self.tmp / "recorded").read_text().splitlines()[-1], ledger[0] if ledger else None)
        self.assertEqual(got, {row: (v, t) for row, (_, _, v, t) in rows.items()})
        self.assertIn(
            "HEALER_VERDICT: cured|incurable|partial <n_cured>/2",
            (self.tmp / "prompt").read_text(),
        )

    def test_a_innocence_owner_only_dead_skips_with_ledger(self) -> None:
        registry = {"dead": [{"id": "tcc-only", "cure": "owner"}]}
        result = self._run(CLEAN_PROBES, registry=registry, registry_rc=1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._spawn_count(), 0, self._log())
        self.assertIn(
            "skip: registry 1 dead, none session-curable: tcc-only", self._log()
        )
        self.assertEqual(self._log().count("skip:"), 1)
        self.assertNotIn("ACTIONABLE", self._log())

    def test_a_broken_receptor_still_spawns(self) -> None:
        result = self._run(
            CLEAN_PROBES, registry={"receptor_broken": "fixture"}, registry_rc=2
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._spawn_count(), 1)
        self.assertIn("ACTIONABLE: registry-receptor-broken", self._log())

    def test_c_guilt_writable_live_path_spawns(self) -> None:
        live = self.tmp / "live-user.sh"
        live.write_text("fixture\n")
        breach = f"DIVERGED: {live} != scripts/live-user.sh — fixture"
        result = self._run(
            CLEAN_PROBES, home_fork={"check_breaches": [breach]}, home_fork_rc=1
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._spawn_count(), 1)
        self.assertIn("ACTIONABLE: home-fork-drift:1/1-session-curable", self._log())

    def test_c_innocence_root_owned_live_path_skips_with_ledger(self) -> None:
        breach = "DIVERGED: /bin/sh != scripts/sh — fixture"
        result = self._run(
            CLEAN_PROBES, home_fork={"check_breaches": [breach]}, home_fork_rc=1
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._spawn_count(), 0, self._log())
        self.assertIn(
            "skip: home-fork 1 drift, none session-curable: /bin/sh", self._log()
        )
        self.assertEqual(self._log().count("skip:"), 1)
        self.assertIn("home-fork --check (rc=1):", self._log())
        self.assertNotIn("receptor-broken", self._log())

    def test_a_and_c_third_states_spawn_with_named_reasons(self) -> None:
        unrecognised = "DIVERGED: scripts/x.sh is absent from this checkout — the CHECKOUT is the stale side"
        rows = {
            "a-exit1-no-dead": dict(registry={"dead": []}, registry_rc=1),
            "a-exit1-not-json": dict(registry="not json", registry_rc=1),
            "a-exit0-not-json": dict(registry="not json", registry_rc=0),
            "a-undeclared-cure": dict(registry={"dead": [{"id": "x", "cure": "Owner"}]}, registry_rc=1),
            "a-cure-missing": dict(registry={"dead": [{"id": "x"}]}, registry_rc=1),
            "a-mixed": dict(registry={"dead": [{"id": "x", "cure": "owner"},
                                               {"id": "y", "cure": "session"}]}, registry_rc=1),
            "c-rc1-no-breach": dict(home_fork={"check_breaches": []}, home_fork_rc=1),
            "c-rc1-not-json": dict(home_fork="not json", home_fork_rc=1),
            "c-unrecognised-line": dict(home_fork={"check_breaches": [unrecognised]}, home_fork_rc=1),
        }
        got = {}
        for row, kwargs in rows.items():
            self.marker.unlink(missing_ok=True)
            (self.home / "logs/pro-healer/run.log").unlink(missing_ok=True)
            self._run(CLEAN_PROBES, **kwargs)
            line = next((ln for ln in self._log().splitlines() if "ACTIONABLE:" in ln), "")
            got[row] = (self._spawn_count(), line.split("ACTIONABLE: ", 1)[-1].split(" —")[0].strip())
        self.assertEqual(got, {
            "a-exit1-no-dead": (1, "registry-receptor-broken"),
            "a-exit1-not-json": (1, "registry-receptor-broken"),
            "a-exit0-not-json": (1, "registry-receptor-broken"),
            "a-undeclared-cure": (1, "registry-receptor-broken"),
            "a-cure-missing": (1, "registry:1/1-dead 0-findings"),
            "a-mixed": (1, "registry:1/2-dead 0-findings"),
            "c-rc1-no-breach": (1, "home-fork-receptor-broken"),
            "c-rc1-not-json": (1, "home-fork-receptor-broken"),
            "c-unrecognised-line": (1, "home-fork-drift:1/1-session-curable"),
        })

    def test_b_guilt_p1_session_probe_spawns(self) -> None:
        result = self._run([
            {"id": "fixable", "status": "DIVERGED", "severity": "P1", "cure": "session"},
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._spawn_count(), 1)
        self.assertIn("ACTIONABLE: proprioception:1/1-session-curable", self._log())

    def test_b_registry_handoff_removes_duplicate_organ_count(self) -> None:
        result = self._run([
            {"id": "organs_heartbeat", "status": "DIVERGED", "severity": "P1", "cure": "session"},
            {"id": "fixable", "status": "DIVERGED", "severity": "P1", "cure": "session"},
        ])
        registry_file = self.home / ".organism/healer-pro/registry-last.json"

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._spawn_count(), 1)
        self.assertIn("ACTIONABLE: proprioception:1/2-session-curable", self._log())
        self.assertIn("organs_heartbeat judged by receptor A", self._log())
        self.assertEqual(registry_file.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(registry_file.read_text()), {"dead": []})

    def test_b_absent_registry_keeps_old_count_and_does_not_pass_flag(self) -> None:
        result = self._run([
            {"id": "organs_heartbeat", "status": "DIVERGED", "severity": "P1", "cure": "session"},
        ], registry="")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._spawn_count(), 1)
        self.assertIn("proprioception:1/1-session-curable", self._log())
        self.assertNotIn("proprioception-receptor-broken", self._log())

    def test_b_empty_registry_file_is_not_passed(self) -> None:
        registry_file = self.home / ".organism/healer-pro/registry-last.json"
        registry_file.parent.mkdir(parents=True)
        registry_file.write_text("")

        result = self._run([
            {"id": "organs_heartbeat", "status": "DIVERGED", "severity": "P1", "cure": "session"},
        ], registry="")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("proprioception:1/1-session-curable", self._log())
        self.assertNotIn("proprioception-receptor-broken", self._log())

    def test_b_keeps_its_own_count_when_a_is_broken(self) -> None:
        organ = [{"id": "organs_heartbeat", "status": "DIVERGED", "severity": "P1", "cure": "session"}]
        registry_file = self.home / ".organism/healer-pro/registry-last.json"
        for row, kwargs in {
            "not-json": dict(registry="not json"),
            "receptor-broken-rc2": dict(registry={"receptor_broken": "x", "exit": 2}, registry_rc=2),
            "exit1-no-dead": dict(registry={"dead": []}, registry_rc=1),
            "valid-json-killed-rc137": dict(registry={"dead": []}, registry_rc=137),
        }.items():
            with self.subTest(row=row):
                self.marker.unlink(missing_ok=True)
                result = self._run(organ, **kwargs)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self._spawn_count(), 1)
                last = [line for line in self._log().splitlines() if "ACTIONABLE: " in line][-1]
                self.assertIn("proprioception:1/1-session-curable", last)
                self.assertNotIn("proprioception-receptor-broken", last)
                self.assertFalse(registry_file.exists())
                if row != "valid-json-killed-rc137":  # A's own rc-137 blind spot predates this hand-off
                    self.assertIn("registry-receptor-broken proprioception:1/1-session-curable", last)

    def test_b_rc3_on_the_handoff_branch_is_a_broken_receptor(self) -> None:
        self._run([{"id": "fixable", "status": "DIVERGED", "severity": "P1", "cure": "Owner"}])

        self.assertIn("probe fixable: invalid cure 'Owner'", self._log())
        self.assertIn("ACTIONABLE: proprioception-receptor-broken", self._log())
        self.assertNotIn("organs_heartbeat judged by receptor A", self._log())

    def test_b_never_defers_to_a_previous_ticks_snapshot(self) -> None:
        registry_file = self.home / ".organism/healer-pro/registry-last.json"
        registry_file.parent.mkdir(parents=True)
        registry_file.write_text('{"dead": []}\n')
        debris = registry_file.with_name("registry-last.json.tmp.crashed")
        debris.write_text('{"dead": []}\n')

        result = self._run([
            {"id": "organs_heartbeat", "status": "DIVERGED", "severity": "P1", "cure": "session"},
        ], registry="")
        self.assertFalse(debris.exists())

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("proprioception:1/1-session-curable", self._log())
        self.assertNotIn("organs_heartbeat judged by receptor A", self._log())
        self.assertFalse(registry_file.exists())

    def test_a_snapshot_write_failure_leaves_a_and_b_whole(self) -> None:
        registry_file = self.home / ".organism/healer-pro/registry-last.json"
        registry_file.parent.mkdir(parents=True)
        registry_file.write_text('{"dead": []}\n')  # last tick's, undeletable below
        registry_file.parent.chmod(0o500)
        try:
            result = self._run([
                {"id": "organs_heartbeat", "status": "DIVERGED", "severity": "P1", "cure": "session"},
            ], registry={"dead": [{"id": "fixable", "cure": "session"}]}, registry_rc=1)
        finally:
            registry_file.parent.chmod(0o700)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("registry snapshot write failed", self._log())
        self.assertIn("ACTIONABLE: registry:1/1-dead 0-findings proprioception:1/1-session-curable", self._log())
        self.assertNotIn("receptor-broken", self._log())
        self.assertNotIn("organs_heartbeat judged by receptor A", self._log())
        self.assertIn('"fixable"', (self.tmp / "memo-inputs").read_text())

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

    def test_memo_key_carries_the_drifted_pair_and_the_dead_cure(self) -> None:
        live = self.tmp / "live-user.sh"
        live.write_text("fixture\n")
        self._run(CLEAN_PROBES, registry={"dead": [{"id": "x", "cure": "owner", "age_s": 9}]},
                  registry_rc=1, home_fork={"check_breaches": [f"DIVERGED: {live} != s/l.sh — f"]},
                  home_fork_rc=1)
        breaches = [f"DIVERGED: {live} != s/l.sh — f", "DIVERGED: /bin/sh != s/sh — f"]
        self._run(CLEAN_PROBES, home_fork={"check_breaches": breaches}, home_fork_rc=1)
        keys = [json.loads(line) for line in (self.tmp / "memo-inputs").read_text().splitlines()]
        self.assertEqual(
            [(k["drifted_pairs"], k["dead_organs"][0]["cure"] if k["dead_organs"] else None) for k in keys],
            [([f"{live}:session"], "owner"), ([f"{live}:session", "/bin/sh:owner"], None)],
        )

    def test_memo_key_carries_proprioception_session_curable_count(self) -> None:
        registry = {"dead": [{"id": "also-fixable", "cure": "session"}]}
        for cure in ("session", "owner"):
            self._run(
                [{"id": "a", "status": "DIVERGED", "severity": "P1", "cure": cure}],
                registry=registry,
                registry_rc=1,
            )
        counts = [json.loads(line)["session_curable"]["proprioception"]
                for line in (self.tmp / "memo-inputs").read_text().splitlines()]
        self.assertEqual(counts, [1, 0])


def _proprioception():
    spec = importlib.util.spec_from_file_location("proprioception_under_test", PROPRIOCEPTION)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _healer_run_checks():
    spec = importlib.util.spec_from_file_location("healer_run_checks_under_test", HEALER_RUN_CHECKS)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _seat(status: str) -> str:
    return json.dumps({"status": status, "seat": "x"})


def _launchd(verdict: str, marker: str | None, **extra: str) -> str:
    return json.dumps({"verdict": verdict, "log_marker": marker, **extra})


def _worktree(path: str, origin: str) -> str:
    return json.dumps({"path": path, "origin": origin, "health": "MISSING"})


def _organ(status: str) -> str:
    return json.dumps({"organ_id": "x", "kind": "unhealthy", "status": status})


TCC = _launchd("DEAD-GREEN", "Operation not permitted")
ROOT_DIV = "DIVERGED: /usr/local/lib/wa.sh != scripts/wa.sh — a fix is stranded on one side (x)"
ROOT_NOREPO = "NO REPO COUNTERPART: /usr/local/bin/k.sh executes live with no source of truth in repo"
USER_NOREPO = "NO REPO COUNTERPART: /Users/u/scripts/y.sh executes live with no source of truth in repo"

# (branch-row, evidence, n, expected). Every branch of cure_for_result that returns owner or
# falls back has a guilt row (owner) and an innocence row (stays session); n=None means len(evidence).
ARSENAL_ROWS = [
    ("A1-parse-guilt", [_seat("AUTH_DEAD")], None, "owner"),
    ("A1-parse-guilt-complete-before-cut",
     [json.dumps({"status": "AUTH_DEAD", "detail": "x" * 200})[:160]], None, "owner"),
    ("A1-parse-innocence-field-cut",
     [json.dumps({"status": "AUTH_" + "x" * 200})[:160]], None, "session"),
    ("A1-parse-innocence-not-a-string", [None], None, "session"),
    ("A2-coverage-guilt", [_seat("AUTH_DEAD"), _seat("BALANCE_DEAD")], None, "owner"),
    ("A2-coverage-innocence", [_seat("AUTH_DEAD")], 2, "session"),
    ("A3-nonempty-innocence", [], 0, "session"),
    ("A4-all-guilt", [_seat("AUTH_DEAD"), _seat("AUTH_DEAD")], None, "owner"),
    ("A4-all-innocence", [_seat("AUTH_DEAD"), _seat("MODEL_ERR"), _seat("UNKNOWN_ERR")], None, "session"),
    ("A5-state-set-guilt", [_seat("BALANCE_DEAD")], None, "owner"),
    ("A5-state-set-innocence-caseless", [_seat("auth_dead")], None, "session"),
    ("A5-state-set-innocence-prefix", [_seat("AUTH_DEAD_SOFT")], None, "session"),
    ("A5-state-set-guilt-quota", [_seat("QUOTA_DEAD")], None, "owner"),
    ("A5-state-set-guilt-model", [_seat("MODEL_ERR")], None, "owner"),
    ("A5-state-set-innocence-unknown", [_seat("UNKNOWN_ERR")], None, "session"),
    ("A5-state-set-innocence-timeout", [_seat("TIMEOUT")], None, "session"),
    ("A6-status-key-innocence", [json.dumps({"seat": "x"})], None, "session"),
]
LAUNCHD_ROWS = [
    ("L1-parse-guilt", [TCC], None, "owner"),
    ("L1-parse-guilt-complete-before-cut",
     [_launchd("DEAD-GREEN", "Operation not permitted", program="x" * 200)[:160]], None, "owner"),
    ("L1-parse-innocence-field-cut",
     [_launchd("DEAD-GREEN", "Operation not " + "x" * 200)[:160]], None, "session"),
    ("L1-parse-innocence-not-a-string", [None], None, "session"),
    ("L2-coverage-guilt", [TCC, TCC], None, "owner"),
    ("L2-coverage-innocence", [TCC], 2, "session"),
    ("L3-nonempty-innocence", [], 0, "session"),
    ("L4-all-innocence", [TCC, _launchd("DEAD-NONZERO", "exit 1")], None, "session"),
    ("L5-verdict-innocence", [_launchd("DEAD-NONZERO", "Operation not permitted")], None, "session"),
    ("L6-tcc-marker-innocence", [_launchd("DEAD-GREEN", "exit 0")], None, "session"),
    ("L7-caseless-marker-guilt", [_launchd("DEAD-GREEN", "OPERATION NOT PERMITTED")], None, "owner"),
    ("L8-not-loaded-guilt", [_launchd("NOT-LOADED", "plist present")], None, "owner"),
    ("L8-owner-only-mix-guilt", [_launchd("NOT-LOADED", "plist present"), TCC], None, "owner"),
    ("L8-dead-nonzero-mix-innocence",
     [_launchd("NOT-LOADED", "plist present"), _launchd("DEAD-NONZERO", "boom")], None, "session"),
    ("L9-failing-honestly-guilt", [_launchd("FAILING-HONESTLY", None)], None, "owner"),
    ("L9-expected-nonzero-guilt", [_launchd("EXPECTED-NONZERO", None)], None, "owner"),
    ("L9-armed-to-nothing-innocence", [_launchd("ARMED-TO-NOTHING", None)], None, "session"),
    ("L9-dead-green-loaded-innocence",
     [_launchd("FAILING-HONESTLY", None), _launchd("DEAD-GREEN", None)], None, "session"),
    ("L9-unknown-verdict-innocence", [_launchd("SOMETHING-NEW", None)], None, "session"),
    ("L9-caseless-verdict-innocence", [_launchd("failing-honestly", None)], None, "session"),
    # Pro 2026-10-08: 14 findings, the detector's "2 alarms" are only the NOT-LOADED two.
    ("L10-pro-population-guilt",
     [_launchd("FAILING-HONESTLY", None)] * 10 + [_launchd("EXPECTED-NONZERO", None)] * 2
     + [_launchd("NOT-LOADED", None)] * 2, None, "owner"),
    ("L10-pro-population-capped-innocence",
     [_launchd("FAILING-HONESTLY", None)] * 5, 14, "session"),
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
WORKTREE_ROWS = [
    ("W1-all-foreign-guilt",
     [_worktree("/Users/u/.codex/worktrees/3354", "external"),
      _worktree("/private/tmp/seat", "external")], None, "owner"),
    ("W1-repo-worktree-innocence",
     [_worktree("/Users/u/.codex/worktrees/3354", "external"),
      _worktree("/Users/u/nuzantara/.worktrees/task", "broker")], None, "session"),
    ("W1-repo-path-innocence", [_worktree("/Users/u/nuzantara/.worktrees/task", "external")],
     None, "session"),
    ("W2-unprovable-innocence", [json.dumps({"origin": "external", "health": "MISSING"})], None, "session"),
    ("W3-complete-fields-before-cut-guilt",
     [json.dumps({"path": "/Users/u/.codex/worktrees/3354", "origin": "external",
                  "origin_detail": "x" * 200})[:160]], None, "owner"),
]
ORGAN_ROWS = [
    ("O1-owner-statuses-guilt", [_organ("disabled"), _organ("disabled")], None, "owner"),
    ("O1-mixed-status-innocence", [_organ("disabled"), _organ("error")], None, "session"),
    ("O1-cased-status-innocence", [_organ("DISABLED")], None, "session"),
    ("O1-trailing-space-innocence", [_organ("disabled ")], None, "session"),
    ("O1-substring-innocence", [_organ("not-disabled-now")], None, "session"),
    ("O1-never-armed-is-not-a-sidecar-status-innocence", [_organ("never_armed")], None, "session"),
    ("O1-pro-today-innocence", [_organ("fail"), _organ("error"), _organ("failed")], None, "session"),
    ("O2-unprovable-innocence", [json.dumps({"organ_id": "x", "kind": "unhealthy"})], None, "session"),
    ("O3-complete-status-before-cut-guilt",
     [json.dumps({"organ_id": "x", "kind": "unhealthy", "age_days": 1.0,
                  "status": "disabled", "detail": "x" * 200})[:160]], None, "owner"),
    ("O3-status-cut-innocence",
     [json.dumps({"organ_id": "x", "kind": "unhealthy", "age_days": 1.0,
                  "status": "disabled" + "x" * 200})[:160]], None, "session"),
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

    def test_worktree_branches(self) -> None:
        self.assertEqual(self._cures("worktree_gate_shim", WORKTREE_ROWS),
                         {r[0]: r[3] for r in WORKTREE_ROWS})

    def test_organs_branches(self) -> None:
        self.assertEqual(self._cures("organs_heartbeat", ORGAN_ROWS),
                         {r[0]: r[3] for r in ORGAN_ROWS})

    def test_real_probe_json_shapes_round_trip_to_owner(self) -> None:
        samples = {
            "worktree_gate_shim": {"worktrees": [
                {"path": "/Users/u/.codex/worktrees/3354", "origin": "external",
                 "origin_detail": "outside repo tree " + "x" * 200, "health": "MISSING",
                 "is_symlink": False, "is_finding": True, "branch": "agent/seat",
                 "detached": False, "locked_reason": None},
            ]},
            "launchd_liveness": {"findings": [
                {"label": "sota.m13-collect", "verdict": "NOT-LOADED", "last_exit": None,
                 "program": "/Users/u/" + "x" * 200, "program_exists": False,
                 "log_marker": None, "stale_green": False},
            ]},
            "organs_heartbeat": [
                {"organ_id": "x", "kind": "stale", "age_days": 9.0,
                 "status": "disabled", "detail": "x" * 200},
            ],
            "arsenal_seats": {"findings": [
                {"seat": "codex-spark", "status": "MODEL_ERR"},
            ]},
        }
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for probe_id, payload in samples.items():
                stub = root / f"{probe_id}.py"
                stub.write_text(f"print({json.dumps(json.dumps(payload))})\n")
                entry = next(e for e in self.mod.DEFAULT_REGISTRY if e["id"] == probe_id)
                status, n, evidence = self.mod.run_wrap(
                    root, dict(entry, target=["python3", str(stub)]), 10,
                )
                with self.subTest(probe=probe_id):
                    self.assertEqual(status, self.mod.DIVERGED)
                    if probe_id != "arsenal_seats":
                        self.assertEqual(len(evidence[0]), 160)
                    self.assertEqual(self.mod.cure_for_result(entry, status, n, evidence), "owner")

    def test_every_finding_reaches_the_cure_but_the_board_shows_five(self) -> None:
        payload = {"findings": [{"label": f"j{i}", "verdict": "FAILING-HONESTLY", "log_marker": None}
                                for i in range(14)], "alarms": 0}
        with tempfile.TemporaryDirectory() as td:
            stub = Path(td) / "launchd.py"
            stub.write_text(f"print({json.dumps(json.dumps(payload))})\n")
            entry = next(e for e in self.mod.DEFAULT_REGISTRY if e["id"] == "launchd_liveness")
            status, n, evidence = self.mod.run_wrap(Path(td), dict(entry, target=["python3", str(stub)]), 10)
        self.assertEqual((status, n, len(evidence)), (self.mod.DIVERGED, 14, 14))
        self.assertEqual(self.mod.cure_for_result(entry, status, n, evidence), "owner")
        board = self.mod.verdict("launchd_liveness", "b", "c", status, "P1", n, evidence, "h", 0.0, "owner")
        self.assertEqual((board["n_findings"], len(board["evidence"])), (14, 5))

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
            "regulatory_promotion": "pr", "door_canon_parity": "pr",
            "kbli_dataset_anchor": "pr"})
        self.assertEqual(self.mod.validate_registry(self.mod.DEFAULT_REGISTRY), [])
        bad = [dict(e, cure="Owner") if e["id"] == "git_alignment" else e for e in self.mod.DEFAULT_REGISTRY]
        self.assertTrue(any("invalid cure" in err for err in self.mod.validate_registry(bad)))


class HealerRunChecksRegistryAwareTest(unittest.TestCase):
    def test_registry_result_removes_duplicate_organs_from_session_count(self) -> None:
        mod = _healer_run_checks()
        probes = [
            {"id": probe_id, "status": "DIVERGED", "severity": severity, "cure": cure}
            for probe_id, severity, cure in (
                ("worktree_gate_shim", "P1", "session"),
                ("launchd_liveness", "P1", "session"),
                ("organs_heartbeat", "P1", "session"),
                ("arsenal_seats", "P1", "session"),
                ("home_fork_scripts", "P1", "owner"),
                ("launchagent_canon", "P2", "session"),
                ("child_calibration", "P3", "session"),
            )
        ]
        report = json.dumps({"probes": probes})
        registry = json.dumps({"dead": [], "findings": [], "never_armed": [], "disabled": []})

        old_diverged, old_curable = mod.summarize_proprioception(report)
        new_diverged, new_curable = mod.summarize_proprioception(report, registry)

        self.assertEqual((len(old_diverged), len(old_curable)), (7, 4))
        self.assertEqual((len(new_diverged), len(new_curable)), (7, 3))
        self.assertNotIn("organs_heartbeat", new_curable)

    def test_an_invalid_registry_is_a_broken_receptor_not_a_silent_old_count(self) -> None:
        mod = _healer_run_checks()
        report = json.dumps({"probes": [
            {"id": "organs_heartbeat", "status": "DIVERGED", "severity": "P1", "cure": "session"}]})
        for bad in ("not json", "[]", json.dumps({"findings": []}), json.dumps({"dead": "x"})):
            with self.subTest(registry=bad), self.assertRaises(mod.ProbeReportError):
                mod.summarize_proprioception(report, bad)
        self.assertEqual(mod.summarize_proprioception(report, None), (["organs_heartbeat"], ["organs_heartbeat"]))


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
