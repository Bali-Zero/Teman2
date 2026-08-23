#!/usr/bin/env python3
"""Guilt + innocence for mailbox_inject.py (PostToolUse/Stop fleet mailbox).

Runs the REAL hook as a subprocess (never imports its internals) against a
throwaway `NUZ_MAILBOX_DIR`, so a passing suite proves the on-disk contract:
stdin JSON in, `additionalContext` JSON out (or silence), files renamed on
disk exactly once.

`MAILBOX_HOOK_PATH` env var overrides which hook file is exercised — the
installer (`install_mailbox_hook.sh`) points this at the INSTALLED copy
under `~/.claude/hooks/` as a self-verifying vaccine before it trusts the
install. Default is the repo copy sitting next to this test.

Run directly (`python3 test_mailbox_inject.py`) or under pytest.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import time
import unittest

HOOK = pathlib.Path(
    os.environ.get("MAILBOX_HOOK_PATH")
    or (pathlib.Path(__file__).resolve().parent / "mailbox_inject.py")
)


def run_hook(payload, mailbox_dir, extra_env=None, off=False):
    """Invoke the real hook. `payload` is a dict (JSON-encoded) or a raw str
    (sent verbatim, for malformed-stdin cases)."""
    env = dict(os.environ)
    env.pop("NUZ_MAILBOX_OFF", None)
    env["NUZ_MAILBOX_DIR"] = str(mailbox_dir)
    if off:
        env["NUZ_MAILBOX_OFF"] = "1"
    if extra_env:
        env.update(extra_env)
    stdin_data = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(HOOK)], input=stdin_data,
        capture_output=True, text=True, env=env,
    )


def write_msg(path, sender, body):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(f"from: {sender}\n\n{body}", encoding="utf-8")


class MailboxInjectTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name) / "mailbox"
        self.root.mkdir(mode=0o700)
        self.sid = "sess-alpha-0001"
        self.sid2 = "sess-bravo-0002"

    def tearDown(self):
        self._tmp.cleanup()

    # ── direct delivery ────────────────────────────────────────────────
    def test_direct_message_delivered_once_then_silent(self):
        msg = self.root / self.sid / "20260101T000000-0001.md"
        write_msg(msg, "pro:zero", "Ping from Pro.")
        p1 = run_hook({"session_id": self.sid, "hook_event_name": "PostToolUse"}, self.root)
        self.assertEqual(p1.returncode, 0)
        out = json.loads(p1.stdout)
        self.assertIn("Ping from Pro.", out["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "PostToolUse")
        self.assertFalse(msg.exists())  # renamed away
        delivered = list((self.root / self.sid).glob("*.delivered-*"))
        self.assertEqual(len(delivered), 1)

        p2 = run_hook({"session_id": self.sid, "hook_event_name": "PostToolUse"}, self.root)
        self.assertEqual(p2.returncode, 0)
        self.assertEqual(p2.stdout.strip(), "")

    # ── broadcast delivery ─────────────────────────────────────────────
    def test_broadcast_delivered_once_per_session_to_two_sessions(self):
        bmsg = self.root / "broadcast" / "20260101T000000-0001.md"
        write_msg(bmsg, "mini:cron", "Fleet-wide notice.")

        for sid in (self.sid, self.sid2):
            p1 = run_hook({"session_id": sid, "hook_event_name": "Stop"}, self.root)
            out = json.loads(p1.stdout)
            self.assertIn("Fleet-wide notice.", out["hookSpecificOutput"]["additionalContext"])
            p2 = run_hook({"session_id": sid, "hook_event_name": "Stop"}, self.root)
            self.assertEqual(p2.stdout.strip(), "")
        self.assertTrue(bmsg.exists())  # broadcast files are never renamed

    # ── kill switch ────────────────────────────────────────────────────
    def test_kill_switch_suppresses_output_even_with_mail(self):
        msg = self.root / self.sid / "20260101T000000-0001.md"
        write_msg(msg, "pro:zero", "Should not appear.")
        p = run_hook({"session_id": self.sid, "hook_event_name": "PostToolUse"}, self.root, off=True)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout.strip(), "")
        self.assertTrue(msg.exists())  # untouched while disarmed

    # ── missing root ───────────────────────────────────────────────────
    def test_missing_mailbox_root_is_silent(self):
        ghost = self.root / "does-not-exist"
        p = run_hook({"session_id": self.sid, "hook_event_name": "PostToolUse"}, ghost)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout.strip(), "")

    # ── malformed / empty stdin ────────────────────────────────────────
    def test_malformed_stdin_exits_clean(self):
        for bad in ("{not valid json", "", "null", "[]", '"just a string"'):
            p = run_hook(bad, self.root)
            self.assertEqual(p.returncode, 0, msg=repr(bad))
            self.assertEqual(p.stdout.strip(), "", msg=repr(bad))

    # ── truncation ─────────────────────────────────────────────────────
    def test_oversized_message_is_truncated_with_marker(self):
        msg = self.root / self.sid / "20260101T000000-0001.md"
        write_msg(msg, "pro:zero", "x" * 9000)
        p = run_hook({"session_id": self.sid, "hook_event_name": "PostToolUse"}, self.root)
        out = json.loads(p.stdout)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("[truncated]", ctx)
        self.assertLess(ctx.count("x"), 9000)

    # ── Stop with empty mailbox ────────────────────────────────────────
    def test_stop_event_empty_mailbox_is_silent(self):
        p = run_hook({"session_id": self.sid, "hook_event_name": "Stop"}, self.root)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout.strip(), "")

    # ── path-unsafe session_id ─────────────────────────────────────────
    def test_path_traversal_session_id_is_rejected(self):
        before = sorted(p.name for p in self.root.iterdir())
        p = run_hook({"session_id": "../../etc", "hook_event_name": "PostToolUse"}, self.root)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout.strip(), "")
        after = sorted(p.name for p in self.root.iterdir())
        self.assertEqual(before, after)  # nothing created/touched

    # ── per-fire cap ───────────────────────────────────────────────────
    def test_at_most_three_messages_per_fire(self):
        sdir = self.root / self.sid
        for i in range(5):
            write_msg(sdir / f"2026010{i}T000000-000{i}.md", "pro:zero", f"msg {i}")
            time.sleep(0.01)
        p1 = run_hook({"session_id": self.sid, "hook_event_name": "PostToolUse"}, self.root)
        out1 = json.loads(p1.stdout)
        self.assertEqual(out1["hookSpecificOutput"]["additionalContext"].count("<cross-machine-message"), 3)
        remaining = [f for f in sdir.iterdir() if ".delivered-" not in f.name]
        self.assertEqual(len(remaining), 2)

        p2 = run_hook({"session_id": self.sid, "hook_event_name": "PostToolUse"}, self.root)
        out2 = json.loads(p2.stdout)
        self.assertEqual(out2["hookSpecificOutput"]["additionalContext"].count("<cross-machine-message"), 2)


if __name__ == "__main__":
    unittest.main()
