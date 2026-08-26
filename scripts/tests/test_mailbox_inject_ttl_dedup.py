#!/usr/bin/env python3
"""S3 — state-keyed fleet mailbox: TTL + per-key dedup (guilt/innocence).

Companion to infra/claude-hooks/test_mailbox_inject.py (the general hook
contract suite, untouched by this change). This file pins the NEW behaviour
added 2026-08-27: a message may carry `key:`/`expires:` front matter right
after `from:`; the collector (1) sorts NEWEST-first BY MTIME, (2) keeps
only the newest surviving file per effective key — an older same-key file
is superseded and renamed away so it can never resurface, (3) drops a
message once `expires:` (when present/parseable) says so — SHORTENING or
extending the flat 48h default, clamped to a max extension — falling back
to the flat 48h-by-mtime rule with no `expires:`, and (4) must fail OPEN
(0 injections, rc 0) on any internal exception — never fall back to a
naive, undeduped delivery of raw candidates. Covers BOTH the direct-mail
and the broadcast collector — the broadcast path is the actual disease
surface and was the round-1 refuter's biggest finding: the first cut of
this suite tested direct mail only, so reverting every `_collect_broadcast`
change would have stayed green.

Disease this cures, measured 2026-08-26 (see fleet retro
research/operations/2026-08-26-retro-fleet-sessions-25-26.md item S3): 94
undelivered broadcasts (2026-08-23..26) replayed at MAX_MESSAGES_PER_FIRE=3
per fire into every new session AND every subagent; 45/94 were repeat
`queue_unstick` DIRTY-PR pages, one PR (#4664) paged 12+ times — reproduced
live in the session that wrote this fix (see the shipping PR body for the
transcript count).

Runs standalone (`python3 scripts/tests/test_mailbox_inject_ttl_dedup.py`)
or under pytest, same pattern as its companion.
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
    or (pathlib.Path(__file__).resolve().parent.parent.parent
        / "infra" / "claude-hooks" / "mailbox_inject.py")
)


def run_hook(payload, mailbox_dir):
    env = dict(os.environ)
    env.pop("NUZ_MAILBOX_OFF", None)
    env["NUZ_MAILBOX_DIR"] = str(mailbox_dir)
    stdin_data = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(HOOK)], input=stdin_data,
        capture_output=True, text=True, env=env,
    )


def write_msg(path, sender, body, *, key=None, expires=None, age_seconds=None):
    """Write a message file with optional key:/expires: front matter, and
    optionally backdate its mtime by age_seconds (simulates an old,
    never-collected message without waiting real time)."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    header = f"from: {sender}\n"
    if key:
        header += f"key: {key}\n"
    if expires:
        header += f"expires: {expires}\n"
    header += "\n"
    path.write_text(header + body, encoding="utf-8")
    if age_seconds is not None:
        old = time.time() - age_seconds
        os.utime(path, (old, old))


class MailboxTTLDedupTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name) / "mailbox"
        self.root.mkdir(mode=0o700)
        self.sid = "sess-ttl-dedup-0001"

    def tearDown(self):
        self._tmp.cleanup()

    # ── guilt: a naive (unfixed) collector on this fixture yields 3 ────────
    # (oldest-filename-first with no dedup/TTL, capped at MAX_MESSAGES_PER_FIRE=3
    # — it delivers page v1/v2/v3 and never even reaches the 4th/stale file;
    # verified red against the pre-fix hook: 3 != 1. See also
    # test_sole_stale_message_that_naive_code_would_deliver below, which
    # isolates the TTL claim from a naive collector that WOULD deliver it.)
    def test_three_same_key_plus_one_stale_yields_exactly_one_injection(self):
        sdir = self.root / self.sid
        # Three messages sharing one key, oldest to newest, all fresh (well
        # inside the 48h TTL) — only the NEWEST must survive.
        write_msg(sdir / "20260101T000000-0001.md", "pro:a", "page v1", key="queue_unstick:4664")
        write_msg(sdir / "20260101T000001-0002.md", "pro:a", "page v2", key="queue_unstick:4664")
        write_msg(sdir / "20260101T000002-0003.md", "pro:a", "page v3 (newest)", key="queue_unstick:4664")
        # A fourth, unrelated (keyless) message that is 4 days old — past
        # the 48h default TTL with no expires: override -> dropped outright.
        write_msg(sdir / "20260101T000003-0004.md", "pro:a", "ancient unrelated notice",
                  age_seconds=4 * 86400)

        p = run_hook({"session_id": self.sid, "hook_event_name": "PostToolUse"}, self.root)
        self.assertEqual(p.returncode, 0)
        out = json.loads(p.stdout)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(ctx.count("<cross-machine-message"), 1)
        self.assertIn("page v3 (newest)", ctx)
        self.assertNotIn("page v1", ctx)
        self.assertNotIn("page v2", ctx)
        self.assertNotIn("ancient unrelated notice", ctx)

        # The two older same-key copies are superseded and the stale one is
        # expired — all three are renamed away and can never resurface.
        remaining_live = [f for f in sdir.iterdir() if f.suffix == ".md"]
        self.assertEqual(len(remaining_live), 0, [f.name for f in remaining_live])
        self.assertEqual(len(list(sdir.glob("*.superseded-*"))), 2)
        self.assertEqual(len(list(sdir.glob("*.expired-*"))), 1)
        self.assertEqual(len(list(sdir.glob("*.delivered-*"))), 1)

    # ── innocence: distinct keys are never conflated ────────────────────────
    def test_two_distinct_fresh_keys_yields_two_injections(self):
        sdir = self.root / self.sid
        write_msg(sdir / "20260101T000000-0001.md", "pro:a", "alpha notice", key="topic:alpha")
        write_msg(sdir / "20260101T000001-0002.md", "pro:a", "beta notice", key="topic:beta")

        p = run_hook({"session_id": self.sid, "hook_event_name": "PostToolUse"}, self.root)
        self.assertEqual(p.returncode, 0)
        out = json.loads(p.stdout)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(ctx.count("<cross-machine-message"), 2)
        self.assertIn("alpha notice", ctx)
        self.assertIn("beta notice", ctx)

    # ── innocence: a keyless message is its OWN unique key ("never deduped
    # against another" — round 1 refuter finding: this promise had no test) ──
    def test_two_distinct_fresh_keyless_messages_yields_two_injections(self):
        sdir = self.root / self.sid
        write_msg(sdir / "20260101T000000-0001.md", "pro:a", "keyless notice one")
        write_msg(sdir / "20260101T000001-0002.md", "pro:a", "keyless notice two")

        p = run_hook({"session_id": self.sid, "hook_event_name": "PostToolUse"}, self.root)
        self.assertEqual(p.returncode, 0)
        out = json.loads(p.stdout)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(ctx.count("<cross-machine-message"), 2)
        self.assertIn("keyless notice one", ctx)
        self.assertIn("keyless notice two", ctx)

    # ── guilt: TTL alone, isolated from the budget-shielding in the fixture
    # above (round 1 refuter finding: a sole stale message is the clean guilt
    # test — naive/pre-fix code WOULD deliver it, since there's no backlog to
    # cap it out) ─────────────────────────────────────────────────────────
    def test_sole_stale_message_that_naive_code_would_deliver(self):
        sdir = self.root / self.sid
        write_msg(sdir / "20260101T000000-0001.md", "pro:a", "lone stale notice",
                  age_seconds=4 * 86400)

        p = run_hook({"session_id": self.sid, "hook_event_name": "PostToolUse"}, self.root)
        self.assertEqual(p.returncode, 0)
        # No survivors at all -> the hook prints NOTHING (no hookSpecificOutput),
        # not an empty additionalContext — verified against main()'s `if not
        # messages: sys.exit(0)` path.
        self.assertEqual(p.stdout.strip(), "")
        self.assertEqual(len(list(sdir.glob("*.expired-*"))), 1)

    # ── round 1 refuter bug fix: expires: can SHORTEN life, not just extend
    # it (`--ttl` shorter than the 48h default used to be a silent no-op) ───
    def test_expires_can_shorten_life_below_the_default_ttl(self):
        sdir = self.root / self.sid
        past = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 60))
        write_msg(sdir / "20260101T000000-0001.md", "pro:a", "short-lived notice",
                  key="topic:short", expires=past)  # fresh mtime, but expires already in the past

        p = run_hook({"session_id": self.sid, "hook_event_name": "PostToolUse"}, self.root)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout.strip(), "")  # no survivors -> nothing printed at all
        self.assertEqual(len(list(sdir.glob("*.expired-*"))), 1)

    # ── round 1 refuter bug fix: survivor selection must follow real mtime,
    # not a filename that can lie (a hand-delivered or clock-skewed file) ───
    def test_dedup_survivor_is_chosen_by_mtime_not_by_filename(self):
        sdir = self.root / self.sid
        # Filename SAYS "0002" is newer than "0001" — but the real mtime says
        # the opposite (0001 was actually written 10s after 0002). The
        # message that is ACTUALLY newest by mtime must be the survivor.
        write_msg(sdir / "20260101T000001-0002.md", "pro:a", "filename-newer but mtime-older",
                  key="topic:clock-skew")
        write_msg(sdir / "20260101T000000-0001.md", "pro:a", "filename-older but mtime-newer",
                  key="topic:clock-skew")
        now = time.time()
        os.utime(sdir / "20260101T000001-0002.md", (now - 20, now - 20))
        os.utime(sdir / "20260101T000000-0001.md", (now - 5, now - 5))

        p = run_hook({"session_id": self.sid, "hook_event_name": "PostToolUse"}, self.root)
        self.assertEqual(p.returncode, 0)
        out = json.loads(p.stdout)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(ctx.count("<cross-machine-message"), 1)
        self.assertIn("filename-older but mtime-newer", ctx)
        self.assertNotIn("filename-newer but mtime-older", ctx)

    # ── expires: extends a message past the 48h default ────────────────────
    def test_expires_extends_a_message_past_the_default_ttl(self):
        sdir = self.root / self.sid
        future = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 30 * 86400))
        write_msg(sdir / "20260101T000000-0001.md", "pro:a", "long-lived notice",
                  key="topic:long", expires=future, age_seconds=4 * 86400)

        p = run_hook({"session_id": self.sid, "hook_event_name": "PostToolUse"}, self.root)
        self.assertEqual(p.returncode, 0)
        out = json.loads(p.stdout)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(ctx.count("<cross-machine-message"), 1)
        self.assertIn("long-lived notice", ctx)

    # ── guilt: an internal collector exception fails OPEN, never naive ─────
    def test_collector_exception_yields_zero_injections_and_rc_zero(self):
        bdir = self.root / "broadcast"
        bdir.mkdir(mode=0o700, parents=True)
        for i in range(4):
            write_msg(bdir / f"2026010{i}T000000-000{i}.md", "pro:a", f"msg {i}")
        os.chmod(bdir, 0o000)  # force iterdir() to raise PermissionError mid-scan
        try:
            p = run_hook({"session_id": self.sid, "hook_event_name": "PostToolUse"}, self.root)
        finally:
            os.chmod(bdir, 0o700)  # restore so tearDown can clean up
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout.strip(), "")

    # ── guilt: the BROADCAST path, the actual disease surface (round 1
    # refuter finding: this suite originally tested direct mail only —
    # reverting every _collect_broadcast change would have stayed green) ───
    def test_broadcast_same_key_dedup_and_ttl_prune_across_two_sessions(self):
        bdir = self.root / "broadcast"
        write_msg(bdir / "20260101T000000-0001.md", "pro:a", "DIRTY page v1", key="queue_unstick:9001")
        write_msg(bdir / "20260101T000001-0002.md", "pro:a", "DIRTY page v2", key="queue_unstick:9001")
        write_msg(bdir / "20260101T000002-0003.md", "pro:a", "DIRTY page v3 (newest)", key="queue_unstick:9001")
        write_msg(bdir / "20260101T000003-0004.md", "pro:a", "ancient unrelated broadcast",
                  age_seconds=4 * 86400)

        # First session's fire: superseded/expired pruning is GLOBAL — it
        # touches the shared broadcast dir, not just this session's own view.
        sid_a = "sess-bcast-a-00000001"
        p = run_hook({"session_id": sid_a, "hook_event_name": "PostToolUse"}, self.root)
        self.assertEqual(p.returncode, 0)
        out = json.loads(p.stdout)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(ctx.count("<cross-machine-message"), 1)
        self.assertIn("DIRTY page v3 (newest)", ctx)

        # v3 survives as a live .md (broadcast delivery never renames — other
        # sessions still need it); v1/v2/ancient are gone fleet-wide.
        remaining_live = [f for f in bdir.iterdir() if f.suffix == ".md"]
        self.assertEqual([f.name for f in remaining_live], ["20260101T000002-0003.md"])
        self.assertEqual(len(list(bdir.glob("*.superseded-*"))), 2)
        self.assertEqual(len(list(bdir.glob("*.expired-*"))), 1)

        # A SECOND, brand-new session must still receive the survivor (each
        # session gets a live broadcast once) but never the superseded v1/v2
        # or the expired notice — those are gone for everyone, not just A.
        sid_b = "sess-bcast-b-00000002"
        p2 = run_hook({"session_id": sid_b, "hook_event_name": "PostToolUse"}, self.root)
        self.assertEqual(p2.returncode, 0)
        out2 = json.loads(p2.stdout)
        ctx2 = out2["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(ctx2.count("<cross-machine-message"), 1)
        self.assertIn("DIRTY page v3 (newest)", ctx2)
        self.assertNotIn("page v1", ctx2)
        self.assertNotIn("page v2", ctx2)
        self.assertNotIn("ancient unrelated broadcast", ctx2)

    # ── guilt: oversize broadcasts are pruned globally, not left to be
    # re-stat'd by every session forever (round 1 refuter finding) ─────────
    def test_oversize_broadcast_is_pruned_globally_not_left_forever(self):
        bdir = self.root / "broadcast"
        write_msg(bdir / "20260101T000000-0001.md", "pro:a", "z" * (1024 * 1024))  # 1 MiB
        p = run_hook({"session_id": self.sid, "hook_event_name": "PostToolUse"}, self.root)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout.strip(), "")
        remaining_live = [f for f in bdir.iterdir() if f.suffix == ".md"]
        self.assertEqual(len(remaining_live), 0, [f.name for f in remaining_live])
        self.assertEqual(len(list(bdir.glob("*.skipped-oversize-*"))), 1)


if __name__ == "__main__":
    unittest.main()
