"""SAETTA bootstrap contract, with synthetic paths and no live providers."""
import importlib.util
import json
import contextlib
import io
import os
import signal
import sys
import time
import tempfile
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "saetta.py"
spec = importlib.util.spec_from_file_location("saetta", SOURCE)
saetta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(saetta)


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.brief = self.root / "scope.md"
        self.brief.write_text("# Synthetic scope\nNo product work.")
        self.manifest = {"mission": "synthetic", "colour": "BLUE", "tasks": [
            {"key": "one", "brief": "scope.md", "dependsOn": [], "scope": ["scripts/"]},
            {"key": "two", "brief": "scope.md", "dependsOn": ["one"], "scope": ["docs/"]},
        ]}

    def prepare(self):
        return saetta.prepare(self.manifest, self.root, self.root)

    def test_portable_absolute_paths_and_default_limit(self):
        result = self.prepare()
        self.assertEqual(result["repo"], str(self.root))
        self.assertEqual(result["tasks"][0]["brief"], str(self.brief))
        self.assertEqual(result["maxParallel"], 3)
        self.assertTrue(Path(result["outputDir"]).is_absolute())
        self.assertNotIn("/Users/", json.dumps(result))

    def test_cycle_rejected_before_any_agent(self):
        self.manifest["tasks"][0]["dependsOn"] = ["two"]
        with self.assertRaisesRegex(ValueError, "cycle"):
            self.prepare()

    def test_missing_brief_rejected(self):
        self.brief.unlink()
        with self.assertRaisesRegex(ValueError, "brief"):
            self.prepare()

    def test_invalid_graph_and_limits(self):
        for updates in ({"maxParallel": 4}, {"maxParallel": True}, {"colour": "ORANGE"}, {"tasks": []}):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                saetta.prepare(dict(self.manifest, **updates), self.root, self.root)
        self.manifest["tasks"][1]["dependsOn"] = ["absent"]
        with self.assertRaisesRegex(ValueError, "dependency"):
            self.prepare()

    def test_scope_cannot_escape_repo(self):
        self.manifest["tasks"][0]["scope"] = ["../private"]
        with self.assertRaisesRegex(ValueError, "scope"):
            self.prepare()

    def test_machine_identification_and_unknown_fail_closed(self):
        self.assertEqual(saetta.machine("Air-M5", Path("/Users/balizero")), "M5")
        self.assertEqual(saetta.machine("Nuzantara", Path("/Users/nuzantara")), "Pro")
        self.assertEqual(saetta.machine("mini-pro2", Path("/Users/nuzantara")), "Mini")
        self.assertEqual(saetta.machine("unrelated", self.root), "UNKNOWN")

    def test_literal_route_brackets_and_braces_are_preserved(self):
        for path in ("apps/mouth/src/app/(workspace)/clients/[id]/ClientDetailClient.tsx",
                     "apps/mouth/src/app/[...slug]/page.tsx", "apps/example/{literal}/page.tsx"):
            with self.subTest(path=path):
                self.manifest["tasks"][0]["scope"] = [path]
                self.assertEqual(self.prepare()["tasks"][0]["scope"], [path])

    def test_wildcard_control_and_invalid_scope_segments_are_rejected(self):
        for path in ("apps/*/page.tsx", "apps/?/page.tsx", "apps/../private",
                     "apps/./page.tsx", "apps//page.tsx", "apps/\tpage.tsx",
                     "apps/\x7fpage.tsx", "apps/\npage.tsx", "apps/\x00page.tsx"):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "scope"):
                self.manifest["tasks"][0]["scope"] = [path]
                self.prepare()

    def test_native_launch_is_pinned_without_bypass_or_credentials(self):
        argv = saetta.launch_argv("/opt/bin/claude", self.root / "saetta.js", self.prepare())
        self.assertEqual(argv[argv.index("--model") + 1], "opus")
        self.assertEqual(argv[argv.index("--effort") + 1], "xhigh")
        self.assertIn("Workflow", argv[argv.index("--allowedTools") + 1])
        self.assertFalse(any("bypass" in arg for arg in argv))
        self.assertIn("scriptPath", argv[-1])

    def test_missing_context_install_is_not_ready(self):
        result = saetta.context_check(self.root, self.root)
        self.assertFalse(result["ready"])

    def test_native_smoke_has_no_installed_script_dependency(self):
        argv = saetta.launch_argv("/opt/bin/claude", self.root / "absent.js", {}, smoke=True)
        self.assertNotIn("scriptPath", argv[-1].split("Wait for its completion")[0])
        self.assertIn("SAETTA_NATIVE_SMOKE", argv[-1])
        self.assertEqual(argv[argv.index("--tools") + 1], "Workflow,Read,TaskOutput")
        self.assertEqual(argv[-2], "--")

    def test_version_prefix_does_not_truncate_node_major(self):
        self.assertEqual(saetta.version_text("v25.5.0\n"), "25.5.0")
        self.assertEqual(saetta.version_text("codex-cli 0.154.0\n"), "0.154.0")

    def test_timeout_stops_only_its_owned_process_and_returns_block(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = saetta.run_bounded([sys.executable, "-c", "import time; time.sleep(5)"],
                                       cwd=self.root, env=dict(os.environ), timeout=0.05)
        self.assertEqual(result, 124)
        self.assertEqual(json.loads(output.getvalue()), {"verdict": "BLOCK", "reason": "timeout"})

    def test_exit_zero_and_model_prose_without_native_receipt_is_block(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = saetta.run_bounded(["/usr/bin/printf", "BLOCK: Workflow unavailable; sensitive-output"],
                                       cwd=self.root, env=dict(os.environ), timeout=1)
        self.assertNotEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue()), {"verdict": "BLOCK", "reason": "native_receipt_missing"})
        self.assertNotIn("sensitive-output", output.getvalue())

    def test_timeout_kills_descendant_after_leader_exits_on_term(self):
        pidfile = self.root / "owned-pids"
        argv = ["/bin/sh", "-c", '/bin/sh -c \'trap "" TERM; /bin/sleep 30\' & echo "$$ $!" > "$1"; wait',
                "fixture", str(pidfile)]
        with contextlib.redirect_stdout(io.StringIO()):
            code = saetta.run_bounded(argv, cwd=self.root, env=dict(os.environ), timeout=0.2)
        group, child = map(int, pidfile.read_text().split())
        try:
            self.assertEqual(code, 124)
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                try:
                    os.kill(child, 0)
                except ProcessLookupError:
                    return
                time.sleep(0.05)
            self.fail("owned child survived the launcher timeout")
        finally:
            try:
                os.killpg(group, signal.SIGKILL)
            except ProcessLookupError:
                pass


if __name__ == "__main__":
    unittest.main()
