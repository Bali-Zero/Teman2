"""Tests for the batch-branch/PR GitHub commit mechanism in post_publish_poller.py.

Direct PUT-to-main via the Contents API is rejected by branch protection (25
required checks, enforce_admins=true, since ~2026-05-22) — every generated
cover image / SEO update was silently discarded. These tests cover the
replacement: writes are staged in-memory during a poller tick and flushed
once, per kind, into ONE bot branch + auto-merged PR.
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from scripts import post_publish_poller as ppp


def _res(returncode: int = 0, stdout: str = "", stderr: str = "") -> "subprocess.CompletedProcess[str]":
    r = MagicMock(spec=subprocess.CompletedProcess)
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


@pytest.fixture(autouse=True)
def _reset_pending_commits():
    ppp._PENDING_COMMITS.clear()
    yield
    ppp._PENDING_COMMITS.clear()


@pytest.fixture(autouse=True)
def _silence_log(monkeypatch):
    """Redirect log() to a list instead of stdout/logfile — tests inspect this."""
    logged = []
    monkeypatch.setattr(ppp, "log", lambda msg: logged.append(msg))
    return logged


def _happy_path_fake_run(calls, put_ok=True, pr_create_ok=True, pr_merge_ok=True):
    def fake_run(cmd, **kwargs):
        calls.append({"cmd": list(cmd), "kwargs": kwargs})
        s = " ".join(cmd)

        if "git/refs/heads/main" in s:
            return _res(stdout="deadbeef1234\n")
        if s.endswith("git/refs --method POST --input -"):
            return _res(returncode=0)
        if "/contents/" in s and "-f" in cmd:
            # existing-sha lookup on the branch — pretend the file is new
            return _res(returncode=1, stderr="HTTP 404: Not Found")
        if "/contents/" in s and "PUT" in cmd:
            return _res(returncode=0 if put_ok else 1, stderr="" if put_ok else "422 sha does not match")
        if cmd[:3] == ["gh", "pr", "create"]:
            return _res(
                returncode=0 if pr_create_ok else 1,
                stdout="https://github.com/Balizero1987/Teman2/pull/42\n" if pr_create_ok else "",
                stderr="" if pr_create_ok else "GraphQL: no commits between main and branch",
            )
        if cmd[:3] == ["gh", "pr", "merge"]:
            return _res(returncode=0 if pr_merge_ok else 1, stderr="" if pr_merge_ok else "auto-merge is not allowed")
        return _res(returncode=0)

    return fake_run


class TestFlushImageBatch:
    def test_empty_batch_is_a_noop(self):
        calls = []
        with patch("scripts.post_publish_poller.subprocess.run", side_effect=_happy_path_fake_run(calls)):
            ok = ppp.flush_image_batch()
        assert ok is True
        assert calls == []

    def test_creates_branch_puts_with_branch_key_and_arms_automerge(self):
        ppp._stage_commit(
            "image",
            "apps/mouth/public/static/news/foo-bar.jpg",
            b"\xff\xd8fake-jpeg-bytes",
            "feat(image): cover for 'Foo Bar'",
        )
        calls = []
        with patch("scripts.post_publish_poller.subprocess.run", side_effect=_happy_path_fake_run(calls)):
            ok = ppp.flush_image_batch()

        assert ok is True
        assert ppp._PENDING_COMMITS == []  # drained

        # create-ref was called (branch created off main HEAD sha)
        create_ref_calls = [
            c for c in calls
            if c["cmd"][:2] == ["gh", "api"] and c["cmd"][2].endswith("/git/refs") and "POST" in c["cmd"]
        ]
        assert len(create_ref_calls) == 1
        import json as _json

        ref_payload = _json.loads(create_ref_calls[0]["kwargs"]["input"])
        assert ref_payload["sha"] == "deadbeef1234"
        assert ref_payload["ref"].startswith("refs/heads/bot/news-covers-")

        # PUT call carries "branch" in its JSON payload
        put_calls = [c for c in calls if "/contents/" in c["cmd"][2] and "PUT" in c["cmd"]]
        assert len(put_calls) == 1
        put_payload = _json.loads(put_calls[0]["kwargs"]["input"])
        assert "branch" in put_payload
        assert put_payload["branch"].startswith("bot/news-covers-")
        assert put_payload["content"]  # base64 content present
        assert "sha" not in put_payload  # file didn't exist on branch yet

        # pr create + pr merge --auto --squash both invoked
        pr_create_calls = [c for c in calls if c["cmd"][:3] == ["gh", "pr", "create"]]
        pr_merge_calls = [c for c in calls if c["cmd"][:3] == ["gh", "pr", "merge"]]
        assert len(pr_create_calls) == 1
        assert len(pr_merge_calls) == 1
        assert "--auto" in pr_merge_calls[0]["cmd"]
        assert "--squash" in pr_merge_calls[0]["cmd"]
        assert pr_create_calls[0]["cmd"][pr_create_calls[0]["cmd"].index("--title") + 1].startswith(
            "feat(images): news covers "
        )

    def test_branch_create_failure_short_circuits_no_put_attempted(self, _silence_log):
        ppp._stage_commit("image", "apps/mouth/public/static/news/x.jpg", b"data", "msg")
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append({"cmd": list(cmd), "kwargs": kwargs})
            s = " ".join(cmd)
            if "git/refs/heads/main" in s:
                return _res(stdout="deadbeef\n")
            if s.endswith("git/refs --method POST --input -"):
                return _res(returncode=1, stderr="422 Reference already exists")
            return _res(returncode=0)

        with patch("scripts.post_publish_poller.subprocess.run", side_effect=fake_run):
            ok = ppp.flush_image_batch()

        assert ok is False
        put_calls = [c for c in calls if "/contents/" in " ".join(c["cmd"]) and "PUT" in c["cmd"]]
        assert put_calls == []
        assert any("Reference already exists" in m for m in _silence_log)

    def test_put_failure_logs_stderr_tail_not_bare_message(self, _silence_log):
        ppp._stage_commit("image", "apps/mouth/public/static/news/y.jpg", b"data", "msg")
        calls = []
        distinctive_tail = "SHA_DOES_NOT_MATCH_LIVE_TAIL_XYZ"
        fake_run = _happy_path_fake_run(calls, put_ok=False)

        def wrapped(cmd, **kwargs):
            res = fake_run(cmd, **kwargs)
            if "/contents/" in " ".join(cmd) and "PUT" in cmd:
                res.stderr = "z" * 250 + distinctive_tail
            return res

        with patch("scripts.post_publish_poller.subprocess.run", side_effect=wrapped):
            ok = ppp.flush_image_batch()

        assert ok is False
        assert any(distinctive_tail in m for m in _silence_log)
        assert any("rc=1" in m for m in _silence_log)

    def test_pr_create_failure_logs_stderr_and_returns_false(self, _silence_log):
        ppp._stage_commit("image", "apps/mouth/public/static/news/z.jpg", b"data", "msg")
        calls = []
        with patch(
            "scripts.post_publish_poller.subprocess.run",
            side_effect=_happy_path_fake_run(calls, pr_create_ok=False),
        ):
            ok = ppp.flush_image_batch()

        assert ok is False
        assert any("no commits between main and branch" in m for m in _silence_log)
        pr_merge_calls = [c for c in calls if c["cmd"][:3] == ["gh", "pr", "merge"]]
        assert pr_merge_calls == []  # never arm merge for a PR that doesn't exist

    def test_pr_merge_arm_failure_is_soft_pr_still_exists(self, _silence_log):
        """A failed --auto arm doesn't nuke the PR — logged as a warning, not fatal."""
        ppp._stage_commit("image", "apps/mouth/public/static/news/w.jpg", b"data", "msg")
        calls = []
        with patch(
            "scripts.post_publish_poller.subprocess.run",
            side_effect=_happy_path_fake_run(calls, pr_merge_ok=False),
        ):
            ok = ppp.flush_image_batch()

        assert ok is True  # PUTs + PR create succeeded; arm failure is non-fatal
        assert any("auto-merge is not allowed" in m for m in _silence_log)


class TestFlushSeoBatch:
    def test_uses_distinct_branch_prefix_and_title(self):
        ppp._stage_commit(
            "seo", "apps/mouth/src/content/articles/business/foo.mdx", b"---\n---\nbody",
            "feat(seo): optimize GEO/AEO metadata for 'Foo'",
        )
        calls = []
        with patch("scripts.post_publish_poller.subprocess.run", side_effect=_happy_path_fake_run(calls)):
            ok = ppp.flush_seo_batch()

        assert ok is True
        create_ref_calls = [
            c for c in calls
            if c["cmd"][:2] == ["gh", "api"] and c["cmd"][2].endswith("/git/refs") and "POST" in c["cmd"]
        ]
        import json as _json

        ref_payload = _json.loads(create_ref_calls[0]["kwargs"]["input"])
        assert ref_payload["ref"].startswith("refs/heads/bot/seo-metadata-")

        pr_create_calls = [c for c in calls if c["cmd"][:3] == ["gh", "pr", "create"]]
        title = pr_create_calls[0]["cmd"][pr_create_calls[0]["cmd"].index("--title") + 1]
        assert title.startswith("fix(seo): GEO/AEO metadata ")

    def test_image_and_seo_batches_are_independent(self):
        """Staging both kinds and flushing one leaves the other queued."""
        ppp._stage_commit("image", "apps/mouth/public/static/news/a.jpg", b"img", "m1")
        ppp._stage_commit("seo", "apps/mouth/src/content/articles/business/a.mdx", b"seo", "m2")

        calls = []
        with patch("scripts.post_publish_poller.subprocess.run", side_effect=_happy_path_fake_run(calls)):
            ppp.flush_image_batch()

        remaining_kinds = {c["kind"] for c in ppp._PENDING_COMMITS}
        assert remaining_kinds == {"seo"}


class TestStageCommit:
    def test_stage_commit_base64_encodes_and_tags_kind(self):
        ppp._stage_commit("image", "path/to/file.jpg", b"raw-bytes", "commit message")
        assert len(ppp._PENDING_COMMITS) == 1
        item = ppp._PENDING_COMMITS[0]
        assert item["kind"] == "image"
        assert item["gh_path"] == "path/to/file.jpg"
        assert item["message"] == "commit message"
        import base64

        assert base64.b64decode(item["content_b64"]) == b"raw-bytes"


class TestFlushLayoutBatch:
    def test_uses_distinct_branch_prefix_and_title(self):
        ppp._stage_commit(
            "layout", ppp.HOMEPAGE_LAYOUT_PATH, b'{"hero_main": "foo"}',
            "feat(homepage): rotate hero → foo",
        )
        calls = []
        with patch("scripts.post_publish_poller.subprocess.run", side_effect=_happy_path_fake_run(calls)):
            ok = ppp.flush_layout_batch()

        assert ok is True
        assert ppp._PENDING_COMMITS == []  # drained

        create_ref_calls = [
            c for c in calls
            if c["cmd"][:2] == ["gh", "api"] and c["cmd"][2].endswith("/git/refs") and "POST" in c["cmd"]
        ]
        import json as _json

        ref_payload = _json.loads(create_ref_calls[0]["kwargs"]["input"])
        assert ref_payload["ref"].startswith("refs/heads/bot/homepage-layout-")

        pr_create_calls = [c for c in calls if c["cmd"][:3] == ["gh", "pr", "create"]]
        title = pr_create_calls[0]["cmd"][pr_create_calls[0]["cmd"].index("--title") + 1]
        assert title.startswith("chore(homepage): hero rotation ")


# ── rotate_hero (homepage-layout.json write path) ──────────────────────────
#
# Regression coverage: rotate_hero() used to PUT apps/mouth/src/content/
# homepage-layout.json straight to main via the Contents API — rejected by
# branch protection (live prod log: "❌ Hero rotation pushed"). It must now
# stage the write for flush_layout_batch (kind="layout") instead, same as the
# image/SEO paths above.


def _layout_read_result(layout: dict, sha: str = "layoutsha123") -> "subprocess.CompletedProcess[str]":
    import base64 as _b64
    import json as _json

    content_b64 = _b64.b64encode(_json.dumps(layout).encode("utf-8")).decode("utf-8")
    return _res(stdout=_json.dumps({"content": content_b64, "sha": sha}))


class TestRotateHero:
    def _fake_read(self, layout, calls):
        read_cmd = ["gh", "api", f"repos/{ppp.GITHUB_OWNER}/{ppp.GITHUB_REPO}/contents/{ppp.HOMEPAGE_LAYOUT_PATH}"]

        def fake_run(cmd, **kwargs):
            calls.append({"cmd": list(cmd), "kwargs": kwargs})
            if list(cmd) == read_cmd:
                return _layout_read_result(layout)
            return _res(returncode=0)

        return fake_run

    def test_stages_layout_write_instead_of_direct_put(self):
        """rotate_hero must NOT PUT directly to main — it stages into
        _PENDING_COMMITS (kind='layout') for flush_layout_batch to commit via a
        bot branch + auto-merged PR."""
        layout = {
            "hero_main": "old-hero", "hero_2": "h2", "hero_3": "h3", "hero_4": "h4", "hero_5": "h5",
            "latest_1": "l1", "latest_2": "l2", "latest_3": "l3", "latest_4": "l4", "latest_5": "l5",
        }
        calls = []
        with patch("scripts.post_publish_poller.subprocess.run", side_effect=self._fake_read(layout, calls)):
            ok = ppp.rotate_hero("new-hero")

        assert ok is True

        # No direct PUT to the Contents API happened
        put_calls = [c for c in calls if "PUT" in c["cmd"]]
        assert put_calls == []

        # Staged exactly one "layout" commit with the rotated content
        layout_commits = [c for c in ppp._PENDING_COMMITS if c["kind"] == "layout"]
        assert len(layout_commits) == 1
        assert layout_commits[0]["gh_path"] == ppp.HOMEPAGE_LAYOUT_PATH

        import base64 as _b64
        import json as _json

        staged_layout = _json.loads(_b64.b64decode(layout_commits[0]["content_b64"]).decode("utf-8"))
        assert staged_layout["hero_main"] == "new-hero"
        assert staged_layout["hero_2"] == "old-hero"
        assert staged_layout["latest_1"] == "h5"  # evicted old hero_5, cascaded to latest_1

    def test_already_hero_main_is_noop_no_stage(self):
        layout = {"hero_main": "same-slug"}
        calls = []
        with patch("scripts.post_publish_poller.subprocess.run", side_effect=self._fake_read(layout, calls)):
            ok = ppp.rotate_hero("same-slug")

        assert ok is True
        assert ppp._PENDING_COMMITS == []


# ── maybe_flush_all_batches (periodic mid-run flush, crash-exposure fix) ───
#
# Regression coverage: the poller used to stage every GitHub write in RAM for
# the FULL run (5-10h with the current backlog) and only flush once at the
# very end — a run that dies mid-tick (no traceback, killer unknown) lost
# every staged cover. maybe_flush_all_batches() shrinks that exposure window
# by flushing image+seo+layout batches once staged writes reach a threshold.


class TestMaybeFlushAllBatches:
    def test_below_threshold_is_noop(self):
        for i in range(ppp._FLUSH_THRESHOLD - 1):
            ppp._stage_commit("image", f"apps/mouth/public/static/news/{i}.jpg", b"x", "m")

        with (
            patch.object(ppp, "flush_image_batch") as mock_img,
            patch.object(ppp, "flush_seo_batch") as mock_seo,
            patch.object(ppp, "flush_layout_batch") as mock_layout,
            patch.object(ppp, "send_telegram_alert") as mock_alert,
        ):
            triggered = ppp.maybe_flush_all_batches()

        assert triggered is False
        mock_img.assert_not_called()
        mock_seo.assert_not_called()
        mock_layout.assert_not_called()
        mock_alert.assert_not_called()

    def test_at_threshold_flushes_all_three_batches(self):
        for i in range(ppp._FLUSH_THRESHOLD):
            ppp._stage_commit("image", f"apps/mouth/public/static/news/{i}.jpg", b"x", "m")

        with (
            patch.object(ppp, "flush_image_batch", return_value=True) as mock_img,
            patch.object(ppp, "flush_seo_batch", return_value=True) as mock_seo,
            patch.object(ppp, "flush_layout_batch", return_value=True) as mock_layout,
            patch.object(ppp, "send_telegram_alert") as mock_alert,
        ):
            triggered = ppp.maybe_flush_all_batches()

        assert triggered is True
        mock_img.assert_called_once()
        mock_seo.assert_called_once()
        mock_layout.assert_called_once()
        mock_alert.assert_not_called()

    def test_flush_failure_sends_telegram_alert_same_condition_as_final_sweep(self):
        for i in range(ppp._FLUSH_THRESHOLD):
            ppp._stage_commit("image", f"apps/mouth/public/static/news/{i}.jpg", b"x", "m")

        with (
            patch.object(ppp, "flush_image_batch", return_value=False),
            patch.object(ppp, "flush_seo_batch", return_value=True),
            patch.object(ppp, "flush_layout_batch", return_value=True),
            patch.object(ppp, "send_telegram_alert") as mock_alert,
        ):
            triggered = ppp.maybe_flush_all_batches()

        assert triggered is True
        mock_alert.assert_called_once()
        assert "image=False" in mock_alert.call_args.args[0]

    def test_custom_threshold_respected(self):
        ppp._stage_commit("image", "apps/mouth/public/static/news/a.jpg", b"x", "m")
        ppp._stage_commit("image", "apps/mouth/public/static/news/b.jpg", b"x", "m")

        with (
            patch.object(ppp, "flush_image_batch", return_value=True) as mock_img,
            patch.object(ppp, "flush_seo_batch", return_value=True),
            patch.object(ppp, "flush_layout_batch", return_value=True),
        ):
            triggered = ppp.maybe_flush_all_batches(threshold=2)

        assert triggered is True
        mock_img.assert_called_once()
