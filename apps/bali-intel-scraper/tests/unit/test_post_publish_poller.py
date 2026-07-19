"""Tests for the batch-branch/PR GitHub commit mechanism in post_publish_poller.py.

Direct PUT-to-main via the Contents API is rejected by branch protection (25
required checks, enforce_admins=true, since ~2026-05-22) — every generated
cover image / SEO update was silently discarded. These tests cover the
replacement: writes are staged in-memory during a poller tick and flushed
once, per kind, into ONE bot branch + auto-merged PR.
"""

import base64
import json
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


# ── git_commit_and_push_translations (translations batch-branch/PR flow) ───
#
# Regression coverage: the poller used to `git add` + `git commit --no-verify`
# + `git push --no-verify origin main` directly on the main checkout. Branch
# protection rejects that push every time, but the commit had already landed
# locally — leaving an orphan commit that blocks every subsequent tick's
# `git pull --ff-only` until rescued by hand (live incident 2026-07-18:
# commits e2c3951c/be43e312d, both rescued manually the same day). The fix
# routes translations through the same batch-branch/PR mechanism as
# image/seo/layout — never touching local git state at all.


def _write_translation_file(tmp_path, slug, lang, category="business", content="---\nfoo\n---\nbody"):
    articles_dir = tmp_path / "apps" / "mouth" / "src" / "content" / "articles" / category
    articles_dir.mkdir(parents=True, exist_ok=True)
    f = articles_dir / f"{slug}.{lang}.mdx"
    f.write_text(content, encoding="utf-8")
    return f


def _fake_repo_root(tmp_path, monkeypatch):
    """Point ppp.SCRIPT_DIR at tmp_path/apps/bali-intel-scraper/scripts so
    SCRIPT_DIR.parent.parent.parent (repo_root inside the function) resolves
    to tmp_path — lets us stage real files without touching the real repo."""
    fake_script_dir = tmp_path / "apps" / "bali-intel-scraper" / "scripts"
    fake_script_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ppp, "SCRIPT_DIR", fake_script_dir)


class TestGitCommitAndPushTranslations:
    def test_never_invokes_git_push_or_commit_to_main(self, tmp_path, monkeypatch):
        """GUILT: the translations flow must never shell out to git at all —
        no `git add`, no `git commit`, no `git push ... main`. Everything goes
        through the gh-api batch-branch/PR mechanism instead."""
        _fake_repo_root(tmp_path, monkeypatch)
        _write_translation_file(tmp_path, "test-slug", "fr")

        calls = []
        with patch("scripts.post_publish_poller.subprocess.run", side_effect=_happy_path_fake_run(calls)):
            ok = ppp.git_commit_and_push_translations(["test-slug"])

        assert ok is True
        git_calls = [c for c in calls if c["cmd"] and c["cmd"][0] == "git"]
        assert git_calls == []  # zero direct git subprocess invocations
        push_main_calls = [c for c in calls if "push" in c["cmd"] and "main" in c["cmd"]]
        assert push_main_calls == []

    def test_uses_translations_branch_prefix_and_gh_pr_create(self, tmp_path, monkeypatch):
        """INNOCENCE: expected behavior is the same batch-branch/PR mechanism
        as image/seo/layout — branch prefix bot/articles-translations, one
        gh api PUT per staged file, gh pr create + --auto --squash arm."""
        _fake_repo_root(tmp_path, monkeypatch)
        _write_translation_file(tmp_path, "test-slug", "fr")
        _write_translation_file(tmp_path, "test-slug", "ru")

        calls = []
        with patch("scripts.post_publish_poller.subprocess.run", side_effect=_happy_path_fake_run(calls)):
            ok = ppp.git_commit_and_push_translations(["test-slug"])

        assert ok is True
        assert ppp._PENDING_COMMITS == []  # drained by the flush

        import json as _json

        create_ref_calls = [
            c for c in calls
            if c["cmd"][:2] == ["gh", "api"] and c["cmd"][2].endswith("/git/refs") and "POST" in c["cmd"]
        ]
        assert len(create_ref_calls) == 1
        ref_payload = _json.loads(create_ref_calls[0]["kwargs"]["input"])
        assert ref_payload["ref"].startswith("refs/heads/bot/articles-translations-")

        pr_create_calls = [c for c in calls if c["cmd"][:3] == ["gh", "pr", "create"]]
        pr_merge_calls = [c for c in calls if c["cmd"][:3] == ["gh", "pr", "merge"]]
        assert len(pr_create_calls) == 1
        assert len(pr_merge_calls) == 1
        assert "--auto" in pr_merge_calls[0]["cmd"]
        assert "--squash" in pr_merge_calls[0]["cmd"]

        title = pr_create_calls[0]["cmd"][pr_create_calls[0]["cmd"].index("--title") + 1]
        assert title.startswith("feat(articles): add translations ")

        put_calls = [c for c in calls if "/contents/" in c["cmd"][2] and "PUT" in c["cmd"]]
        assert len(put_calls) == 2  # both translation files staged+committed
        for pc in put_calls:
            payload = _json.loads(pc["kwargs"]["input"])
            assert payload["message"].startswith("feat(articles): add translations for test-slug")
            assert payload["branch"].startswith("bot/articles-translations-")

    def test_no_files_found_is_noop_returns_true(self, tmp_path, monkeypatch, _silence_log):
        _fake_repo_root(tmp_path, monkeypatch)

        calls = []
        with patch("scripts.post_publish_poller.subprocess.run", side_effect=_happy_path_fake_run(calls)):
            ok = ppp.git_commit_and_push_translations(["nonexistent-slug"])

        assert ok is True
        assert calls == []
        assert any("No translation files to commit" in m for m in _silence_log)

    def test_flush_failure_returns_false_and_never_touches_local_git_state(self, tmp_path, monkeypatch, _silence_log):
        """On a flush failure the function must return False and the .mdx file
        must remain untouched on disk — no git add/commit ever ran, so the
        next tick's rglob picks it right back up and re-stages it."""
        _fake_repo_root(tmp_path, monkeypatch)
        f = _write_translation_file(tmp_path, "test-slug", "fr")

        def fake_run(cmd, **kwargs):
            s = " ".join(cmd)
            if "git/refs/heads/main" in s:
                return _res(stdout="deadbeef\n")
            if s.endswith("git/refs --method POST --input -"):
                return _res(returncode=1, stderr="422 Reference already exists")
            return _res(returncode=0)

        with patch("scripts.post_publish_poller.subprocess.run", side_effect=fake_run):
            ok = ppp.git_commit_and_push_translations(["test-slug"])

        assert ok is False
        assert f.exists()
        assert f.read_text(encoding="utf-8") == "---\nfoo\n---\nbody"  # untouched
        assert any("Reference already exists" in m for m in _silence_log)


class TestFlushTranslationBatch:
    def test_uses_distinct_branch_prefix_and_title(self):
        ppp._stage_commit(
            "translation", "apps/mouth/src/content/articles/business/foo.fr.mdx", b"---\n---\nbody",
            "feat(articles): add translations for foo",
        )
        calls = []
        with patch("scripts.post_publish_poller.subprocess.run", side_effect=_happy_path_fake_run(calls)):
            ok = ppp.flush_translation_batch()

        assert ok is True
        create_ref_calls = [
            c for c in calls
            if c["cmd"][:2] == ["gh", "api"] and c["cmd"][2].endswith("/git/refs") and "POST" in c["cmd"]
        ]
        import json as _json

        ref_payload = _json.loads(create_ref_calls[0]["kwargs"]["input"])
        assert ref_payload["ref"].startswith("refs/heads/bot/articles-translations-")

        pr_create_calls = [c for c in calls if c["cmd"][:3] == ["gh", "pr", "create"]]
        title = pr_create_calls[0]["cmd"][pr_create_calls[0]["cmd"].index("--title") + 1]
        assert title.startswith("feat(articles): add translations ")


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


# ── process_item: image step must never be skipped on completed_steps alone ─
#
# Regression coverage for the queue-necrosis bug: `completed_steps.image=true`
# used to gate a hard skip of run_image() — if a run died before flushing, the
# flag was already true in the DB (mark_step_done fires before the flush), so
# the cover was lost FOREVER (next run trusts the lying flag). run_image()'s
# own idempotency (_image_exists_on_github check against main) makes calling
# it unconditionally safe: cheap no-op when covers are really there, regen
# when the flag lied.


class TestRunTranslateTimeoutGuard:
    """Regression coverage for the crash bug: the subprocess.run() call for
    translate-articles.py used to be bare (no try/except). When the script
    wedges past the 15min timeout, subprocess.TimeoutExpired propagated
    uncaught and crashed the ENTIRE poller run — every remaining queue item
    was abandoned mid-tick (8 real incidents in post_publish_poller.err on
    Pro). run_translate() must catch the timeout, log the cause (stderr
    tail — never a bare fail), and return False so the item is reported as a
    failed step and retried on the next tick instead of killing the run."""

    def test_translate_timeout_is_caught_returns_false_not_raised(self, tmp_path, monkeypatch, _silence_log):
        _fake_repo_root(tmp_path, monkeypatch)
        # MDX already present locally so run_translate skips the GitHub-pull
        # branch entirely and goes straight to the translate subprocess call.
        mdx_dir = tmp_path / "apps" / "mouth" / "src" / "content" / "articles" / "business"
        mdx_dir.mkdir(parents=True, exist_ok=True)
        (mdx_dir / "test-slug.mdx").write_text("---\nfoo\n---\nbody", encoding="utf-8")

        distinctive_tail = "OLLAMA_HUNG_CUDA_TIMEOUT_XYZ123"

        def fake_run(cmd, **kwargs):
            if cmd[0] == "pgrep":
                return _res(returncode=1)  # no other translate running -> free immediately
            # This is the translate-articles.py invocation — simulate it wedging.
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=15 * 60, output="", stderr=distinctive_tail)

        with patch("scripts.post_publish_poller.subprocess.run", side_effect=fake_run):
            # Without the try/except this raises subprocess.TimeoutExpired and
            # the test errors out instead of asserting — that IS the guilt case.
            result = ppp.run_translate("test-slug", "business")

        assert result is False
        assert any(distinctive_tail in m for m in _silence_log)

    def test_translate_success_path_unaffected(self, tmp_path, monkeypatch):
        """INNOCENCE: the guard must not swallow a genuine success/failure exit."""
        _fake_repo_root(tmp_path, monkeypatch)
        mdx_dir = tmp_path / "apps" / "mouth" / "src" / "content" / "articles" / "business"
        mdx_dir.mkdir(parents=True, exist_ok=True)
        (mdx_dir / "ok-slug.mdx").write_text("---\nfoo\n---\nbody", encoding="utf-8")

        def fake_run(cmd, **kwargs):
            if cmd[0] == "pgrep":
                return _res(returncode=1)
            return _res(returncode=0)

        with patch("scripts.post_publish_poller.subprocess.run", side_effect=fake_run):
            result = ppp.run_translate("ok-slug", "business")

        assert result is True


class TestProcessItemNeverSkipsImageStep:
    def test_intel_source_calls_run_image_even_when_completed_steps_true(self):
        item = {
            "slug": "test-slug",
            "category": "business",
            "source": "intel",
            "title": "Test Title",
            "completed_steps": {"seo": True, "translate": True, "image": True},
        }
        with (
            patch.object(ppp, "run_seo", return_value=True) as mock_seo,
            patch.object(ppp, "run_translate", return_value=True) as mock_translate,
            patch.object(ppp, "run_image", return_value=True) as mock_image,
            patch.object(ppp, "mark_step_done") as mock_mark,
            patch.object(ppp, "rotate_hero") as mock_rotate,
        ):
            all_ok, failed_steps = ppp.process_item(item)

        assert all_ok is True
        assert failed_steps == []
        mock_image.assert_called_once_with("test-slug", "business", title="Test Title")
        mock_mark.assert_called_once_with("test-slug", "image")
        # seo/translate are genuinely done — only the image gate is bypassed
        mock_seo.assert_not_called()
        mock_translate.assert_not_called()
        mock_rotate.assert_not_called()

    def test_news_source_calls_run_image_even_when_completed_steps_true(self):
        item = {
            "slug": "news-slug",
            "category": "regulation",
            "source": "news",
            "article_id": "art-1",
            "title": "News Title",
            "completed_steps": {"image": True},
        }
        with (
            patch.object(ppp, "run_image", return_value=True) as mock_image,
            patch.object(ppp, "mark_step_done") as mock_mark,
        ):
            all_ok, failed_steps = ppp.process_item(item)

        assert all_ok is True
        assert failed_steps == []
        mock_image.assert_called_once_with(
            "news-slug", "regulation", title="News Title", article_id="art-1"
        )
        mock_mark.assert_called_once_with("news-slug", "image")

    def test_regenerates_and_reports_failure_when_flag_lied_and_regen_fails(self):
        """completed_steps.image=true but run_image() itself returns False
        (cover genuinely missing + Codex unreachable) — must be reported as a
        failed step (retried next tick), never silently trusted as done."""
        item = {
            "slug": "lost-slug",
            "category": "business",
            "source": "intel",
            "title": "Lost",
            "completed_steps": {"seo": True, "translate": True, "image": True},
        }
        with (
            patch.object(ppp, "run_seo", return_value=True),
            patch.object(ppp, "run_translate", return_value=True),
            patch.object(ppp, "run_image", return_value=False) as mock_image,
            patch.object(ppp, "mark_step_done") as mock_mark,
            patch.object(ppp, "rotate_hero"),
        ):
            all_ok, failed_steps = ppp.process_item(item)

        assert all_ok is False
        assert failed_steps == ["image"]
        mock_image.assert_called_once()
        # mark_step_done must NOT be called for "image" when run_image fails
        assert ("lost-slug", "image") not in [c.args for c in mock_mark.call_args_list]


# ── SEO step: migrated off the deprecated `gemini` CLI ──────────────────────
#
# `gemini -m gemini-2.5-pro` started returning `IneligibleTierError: ... migrate
# to the Antigravity suite` — Google discontinued the free-tier CLI outright
# (confirmed live 2026-07-18), a PERMANENT break, not a PATH/model mismatch.
# run_seo() now delegates to _seo_llm_complete(), which tries agy first
# (CLAUDE.md's mandated replacement) then falls back to codex (already wired
# into this file for cover images) — each pre-flight health-checked so a dead
# tool leaves the item queued instead of corrupting frontmatter.


class TestExtractSeoJson:
    def test_valid_json_only(self):
        raw = '{"seoTitle": "Foo", "seoDescription": "Bar"}'
        assert ppp._extract_seo_json(raw) == {"seoTitle": "Foo", "seoDescription": "Bar"}

    def test_json_with_surrounding_prose(self):
        raw = 'Here is the metadata:\n{"seoTitle": "Foo", "seoDescription": "Bar"}\nHope that helps!'
        assert ppp._extract_seo_json(raw) == {"seoTitle": "Foo", "seoDescription": "Bar"}

    def test_prompt_echo_then_real_answer_picks_the_last_valid_object(self):
        # Simulates an agentic CLI echoing an unrelated JSON blob (e.g. its
        # own input record) before the real answer — must pick the LAST
        # candidate that parses AND carries an expected key, not the first.
        raw = '{"unrelated": "echo"}\n\n{"seoTitle": "Real", "seoDescription": "Answer"}'
        assert ppp._extract_seo_json(raw) == {"seoTitle": "Real", "seoDescription": "Answer"}

    def test_no_braces_returns_none(self):
        assert ppp._extract_seo_json("Error: authentication required. Run 'agy' to log in.") is None

    def test_empty_string_returns_none(self):
        assert ppp._extract_seo_json("") is None

    def test_malformed_json_returns_none(self):
        assert ppp._extract_seo_json("{seoTitle: not valid json}") is None


class TestSeoLlmCascade:
    def test_agy_healthy_and_generates_uses_agy_only(self):
        with (
            patch.object(ppp, "agy_healthy", return_value=True),
            patch.object(ppp, "agy_generate_text", return_value='{"seoTitle": "x"}') as mock_agy,
            patch.object(ppp, "codex_healthy") as mock_codex_healthy,
        ):
            raw, tool = ppp._seo_llm_complete("prompt")

        assert (raw, tool) == ('{"seoTitle": "x"}', "agy")
        mock_agy.assert_called_once_with("prompt")
        mock_codex_healthy.assert_not_called()

    def test_agy_unreachable_falls_back_to_codex(self):
        with (
            patch.object(ppp, "agy_healthy", return_value=False),
            patch.object(ppp, "codex_healthy", return_value=True),
            patch.object(ppp, "codex_generate_text", return_value='{"seoDescription": "y"}') as mock_codex,
        ):
            raw, tool = ppp._seo_llm_complete("prompt")

        assert (raw, tool) == ('{"seoDescription": "y"}', "codex")
        mock_codex.assert_called_once_with("prompt")

    def test_agy_healthy_but_generation_fails_falls_back_to_codex(self):
        with (
            patch.object(ppp, "agy_healthy", return_value=True),
            patch.object(ppp, "agy_generate_text", return_value=None),
            patch.object(ppp, "codex_healthy", return_value=True),
            patch.object(ppp, "codex_generate_text", return_value='{"seoTitle": "z"}'),
        ):
            raw, tool = ppp._seo_llm_complete("prompt")

        assert (raw, tool) == ('{"seoTitle": "z"}', "codex")

    def test_both_unreachable_returns_none_never_fabricates(self):
        with (
            patch.object(ppp, "agy_healthy", return_value=False),
            patch.object(ppp, "codex_healthy", return_value=False),
        ):
            raw, tool = ppp._seo_llm_complete("prompt")

        assert raw is None
        assert tool == ""


def _mdx_frontmatter_payload(body_extra: str = "") -> str:
    """A `gh api contents/...` response body for a not-yet-optimized MDX file
    (no answerSnippet in frontmatter, so run_seo won't short-circuit as
    already-optimized)."""
    content = (
        "---\n"
        'title: "Test Article"\n'
        'seoTitle: ""\n'
        "---\n"
        f"Body text here.{body_extra}\n"
    )
    return json.dumps({"content": base64.b64encode(content.encode()).decode("ascii")})


class TestRunSeo:
    def test_valid_json_response_stages_seo_commit(self):
        gh_payload = _mdx_frontmatter_payload()

        def fake_run(cmd, **kwargs):
            if cmd[:2] == ["gh", "api"]:
                return _res(stdout=gh_payload)
            raise AssertionError(f"unexpected subprocess call: {cmd}")

        seo_json = (
            '{"seoTitle": "Great SEO Title", "seoDescription": "Great SEO description.", '
            '"aiOptimization": {"answerSnippet": "The answer.", "primaryQuestion": "What is it?"}}'
        )
        with (
            patch("scripts.post_publish_poller.subprocess.run", side_effect=fake_run),
            patch.object(ppp, "_seo_llm_complete", return_value=(seo_json, "agy")),
        ):
            ok = ppp.run_seo("test-slug", "business")

        assert ok is True
        staged = [c for c in ppp._PENDING_COMMITS if c["kind"] == "seo"]
        assert len(staged) == 1
        decoded = base64.b64decode(staged[0]["content_b64"]).decode()
        assert "Great SEO Title" in decoded
        assert "Great SEO description." in decoded
        assert staged[0]["gh_path"] == "apps/mouth/src/content/articles/business/test-slug.mdx"

    def test_empty_or_non_json_response_does_not_stage_and_returns_false(self):
        """The CLI ran (agy/codex both reported healthy) but its answer had no
        parseable JSON (e.g. a stray auth-error string past the health-check,
        or a truncated response) — must NOT stage a commit and must return
        False so the item is honestly retried, never a silent no-op success."""
        gh_payload = _mdx_frontmatter_payload()

        def fake_run(cmd, **kwargs):
            if cmd[:2] == ["gh", "api"]:
                return _res(stdout=gh_payload)
            raise AssertionError(f"unexpected subprocess call: {cmd}")

        with (
            patch("scripts.post_publish_poller.subprocess.run", side_effect=fake_run),
            patch.object(ppp, "_seo_llm_complete", return_value=("not json at all", "agy")),
        ):
            ok = ppp.run_seo("test-slug", "business")

        assert ok is False
        assert [c for c in ppp._PENDING_COMMITS if c["kind"] == "seo"] == []

    def test_neither_agy_nor_codex_reachable_leaves_item_queued(self):
        """Both CLIs unreachable (e.g. agy needs interactive re-auth AND codex
        token revoked) — must leave the step queued (return False, no staged
        commit), never fabricate metadata to force a "done" state."""
        gh_payload = _mdx_frontmatter_payload()

        def fake_run(cmd, **kwargs):
            if cmd[:2] == ["gh", "api"]:
                return _res(stdout=gh_payload)
            raise AssertionError(f"unexpected subprocess call: {cmd}")

        with (
            patch("scripts.post_publish_poller.subprocess.run", side_effect=fake_run),
            patch.object(ppp, "_seo_llm_complete", return_value=(None, "")),
        ):
            ok = ppp.run_seo("test-slug", "business")

        assert ok is False
        assert [c for c in ppp._PENDING_COMMITS if c["kind"] == "seo"] == []

    def test_agy_invocation_uses_configured_model_and_sandbox(self):
        """Regression pin for the actual CLI invocation shape (agy_swarm_
        commander.py convention: --model "Gemini 3.1 Pro (High)" --sandbox)."""
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            captured["env"] = kwargs.get("env")
            return _res(stdout='{"seoTitle": "x"}')

        with patch("scripts.post_publish_poller.subprocess.run", side_effect=fake_run):
            out = ppp.agy_generate_text("some prompt")

        assert out == '{"seoTitle": "x"}'
        cmd = captured["cmd"]
        assert cmd[0] == "agy"
        assert "--model" in cmd and ppp.AGY_MODEL in cmd
        assert "--sandbox" in cmd
        assert "--print" in cmd and "some prompt" in cmd
        # PATH must include agy's install dir even if the cron PATH lacks it
        assert ppp.AGY_BIN_DIR in captured["env"]["PATH"].split(":")
