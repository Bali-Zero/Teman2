"""Tests for the batch-branch/PR GitHub commit mechanism in post_publish_poller.py.

Direct PUT-to-main via the Contents API is rejected by branch protection (25
required checks, enforce_admins=true, since ~2026-05-22) — every generated
cover image / SEO update was silently discarded. These tests cover the
replacement: writes are staged in-memory during a poller tick and flushed
once, per kind, into ONE bot branch + auto-merged PR.
"""

import base64
from io import BytesIO
import json
from pathlib import Path
import subprocess
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from scripts import post_publish_poller as ppp

_REAL_OPEN_FAMILY_PRS = getattr(ppp, "_open_family_prs", None)


def _res(returncode: int = 0, stdout: str = "", stderr: str = "") -> "subprocess.CompletedProcess[str]":
    r = MagicMock(spec=subprocess.CompletedProcess)
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


@pytest.fixture(autouse=True)
def _reset_pending_commits():
    ppp._PENDING_COMMITS.clear()
    ppp._PENDING_STEP_MARKS.clear()
    yield
    ppp._PENDING_COMMITS.clear()
    ppp._PENDING_STEP_MARKS.clear()


@pytest.fixture(autouse=True)
def _no_open_bot_prs(monkeypatch):
    """Default: GitHub holds no open bot PR (TestOnePrPerFamily opts back in)."""
    monkeypatch.setattr(ppp, "_open_family_prs", lambda branch_prefix: [], raising=False)
    monkeypatch.setattr(ppp, "_OPEN_COVER_REFS", {}, raising=False)


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
        if cmd[:3] == ["gh", "api", "graphql"]:
            pr = {"autoMergeRequest": {"enabledAt": "x"} if pr_merge_ok else None, "mergeQueueEntry": None,
                  "mergeable": "MERGEABLE",
                  "headRefOid": "head"}
            return _res(stdout=json.dumps({"data": {"repository": {"pullRequest": pr}}}))
        return _res(returncode=0)

    return fake_run


class TestFlushImageBatch:
    def test_empty_batch_is_a_noop(self):
        calls = []
        with patch("scripts.post_publish_poller.subprocess.run", side_effect=_happy_path_fake_run(calls)):
            ok = ppp.flush_image_batch()
        assert ok is True
        assert calls == []


class TestDeferredStepMarks:
    def test_seo_step_is_marked_done_only_after_the_batch_flushes(self):
        ppp._stage_commit("seo", "apps/mouth/src/content/articles/business/s.mdx", b"seo", "seo")
        ppp._defer_step_mark("seo", "S", "seo")

        with (
            patch.object(ppp, "_github_default_branch_sha", return_value="sha"),
            patch.object(ppp, "_create_bot_branch", return_value=True),
            patch.object(ppp, "_commit_to_branch", return_value=True),
            patch.object(ppp, "_open_pr", return_value="https://github.com/o/r/pull/1"),
            patch.object(ppp, "_arm_pr", return_value=True),
            patch.object(ppp, "mark_step_done") as mock_mark,
        ):
            mock_mark.assert_not_called()
            assert ppp.flush_seo_batch() is True

        mock_mark.assert_called_once_with("S", "seo")

    def test_seo_step_stays_unmarked_when_the_batch_fails(self, _silence_log):
        ppp._stage_commit("seo", "apps/mouth/src/content/articles/business/s.mdx", b"seo", "seo")
        ppp._defer_step_mark("seo", "S", "seo")

        with (
            patch.object(ppp, "_github_default_branch_sha", return_value="sha"),
            patch.object(ppp, "_create_bot_branch", return_value=False),
            patch.object(ppp, "mark_step_done") as mock_mark,
        ):
            assert ppp.flush_seo_batch() is False

        mock_mark.assert_not_called()
        assert ppp._PENDING_STEP_MARKS == {}
        assert any("left unmarked for retry" in message for message in _silence_log)

    def test_translation_step_stays_unmarked_when_one_put_fails(self):
        ppp._stage_commit("translation", "one.fr.mdx", b"one", "translation")
        ppp._stage_commit("translation", "one.ru.mdx", b"two", "translation")
        ppp._defer_step_mark("translation", "S", "translate")

        with (
            patch.object(ppp, "_github_default_branch_sha", return_value="sha"),
            patch.object(ppp, "_create_bot_branch", return_value=True),
            patch.object(ppp, "_commit_to_branch", side_effect=[True, False]),
            patch.object(ppp, "_open_pr", return_value="https://github.com/o/r/pull/1") as mock_open_pr,
            patch.object(ppp, "_arm_pr", return_value=True),
            patch.object(ppp, "mark_step_done") as mock_mark,
        ):
            assert ppp.flush_translation_batch() is False

        mock_open_pr.assert_called_once()
        mock_mark.assert_not_called()

    def test_empty_batch_marks_pending_steps(self):
        ppp._defer_step_mark("seo", "S", "seo")

        with patch.object(ppp, "mark_step_done") as mock_mark:
            assert ppp.flush_seo_batch() is True

        mock_mark.assert_called_once_with("S", "seo")

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

        # pr create + pr merge --auto (never --squash under the merge queue) both invoked
        pr_create_calls = [c for c in calls if c["cmd"][:3] == ["gh", "pr", "create"]]
        pr_merge_calls = [c for c in calls if c["cmd"][:3] == ["gh", "pr", "merge"]]
        assert len(pr_create_calls) == 1
        assert len(pr_merge_calls) == 1
        assert "--auto" in pr_merge_calls[0]["cmd"]
        assert "--squash" not in pr_merge_calls[0]["cmd"]
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

    def test_pr_merge_arm_failure_is_loud_and_fails_the_flush(self, _silence_log):
        """An unarmed bot PR sits unmerged while siblings pile up — alert, never just a log line."""
        ppp._stage_commit("image", "apps/mouth/public/static/news/w.jpg", b"data", "msg")
        calls = []
        with (
            patch("scripts.post_publish_poller.subprocess.run",
                  side_effect=_happy_path_fake_run(calls, pr_merge_ok=False)),
            patch.object(ppp, "send_telegram_alert") as alert,
        ):
            ok = ppp.flush_image_batch()

        assert ok is False
        assert any("auto-merge is not allowed" in m for m in _silence_log)
        alert.assert_called_once()


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
            "feat(homepage): rotate hero → foo", slug="foo",
        )
        calls = []
        happy = _happy_path_fake_run(calls)
        main_read = ["gh", "api", f"repos/{ppp.GITHUB_OWNER}/{ppp.GITHUB_REPO}/contents/{ppp.HOMEPAGE_LAYOUT_PATH}"
                     "?ref=deadbeef1234"]

        def fake_run(cmd, **kwargs):
            return _layout_read_result({"hero_main": "bar"}) if list(cmd) == main_read else happy(cmd, **kwargs)

        with patch("scripts.post_publish_poller.subprocess.run", side_effect=fake_run):
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
        assert "--squash" not in pr_merge_calls[0]["cmd"]

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

    def test_a_slug_promoted_out_of_latest_is_not_left_there_twice(self):
        keys = ppp.HERO_KEYS + ppp.LATEST_KEYS
        layout = dict(zip(keys, ["h1", "h2", "h3", "h4", "h5", "l1", "x", "l3", "l4", "l5"]))

        rotated = ppp._rotate_layout(layout, "x")

        assert [rotated[k] for k in ppp.HERO_KEYS] == ["x", "h1", "h2", "h3", "h4"]
        assert [rotated[k] for k in ppp.LATEST_KEYS] == ["h5", "l1", "l3", "l4", "l5"]

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
        mock_mark.assert_not_called()
        assert ppp._PENDING_STEP_MARKS == {"image": [("test-slug", "image")]}
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
        mock_mark.assert_not_called()
        assert ppp._PENDING_STEP_MARKS == {"image": [("news-slug", "image")]}

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

    def test_run_seo_preserves_authored_seo_title_and_description(self):
        content = (
            "---\n"
            'title: "Test Article"\n'
            'seoTitle: "Authored title"\n'
            'seoDescription: "Authored description"\n'
            "---\n"
            "Body text here.\n"
        )
        gh_payload = json.dumps({"content": base64.b64encode(content.encode()).decode("ascii")})
        seo_json = (
            '{"seoTitle": "Generated title", "seoDescription": "Generated description", '
            '"aiOptimization": {"answerSnippet": "The answer.", '
            '"primaryQuestion": "What is it?"}}'
        )

        with (
            patch("scripts.post_publish_poller.subprocess.run", return_value=_res(stdout=gh_payload)),
            patch.object(ppp, "_seo_llm_complete", return_value=(seo_json, "agy")),
        ):
            assert ppp.run_seo("test-slug", "business") is True

        decoded = base64.b64decode(ppp._PENDING_COMMITS[0]["content_b64"]).decode()
        assert 'seoTitle: "Authored title"' in decoded
        assert 'seoDescription: "Authored description"' in decoded
        assert 'answerSnippet: "The answer."' in decoded
        assert 'primaryQuestion: "What is it?"' in decoded

    def test_run_seo_fills_empty_seo_fields(self):
        gh_payload = _mdx_frontmatter_payload()
        seo_json = (
            '{"seoTitle": "Generated title", "seoDescription": "Generated description", '
            '"aiOptimization": {"answerSnippet": "The answer.", '
            '"primaryQuestion": "What is it?"}}'
        )

        with (
            patch("scripts.post_publish_poller.subprocess.run", return_value=_res(stdout=gh_payload)),
            patch.object(ppp, "_seo_llm_complete", return_value=(seo_json, "agy")),
        ):
            assert ppp.run_seo("test-slug", "business") is True

        decoded = base64.b64decode(ppp._PENDING_COMMITS[0]["content_b64"]).decode()
        assert 'seoTitle: "Generated title"' in decoded
        assert 'seoDescription: "Generated description"' in decoded


class TestRunImage:
    @staticmethod
    def _hero_bytes() -> bytes:
        image = Image.new("RGB", (2100, 900), "navy")
        output = BytesIO()
        image.save(output, format="JPEG")
        return output.getvalue()

    def test_run_image_derives_card_from_existing_hero_without_codex(self):
        hero_bytes = self._hero_bytes()

        with (
            patch.object(ppp, "_image_exists_on_github", side_effect=[True, False]),
            patch.object(ppp, "_download_github_file", return_value=hero_bytes),
            patch.object(ppp, "codex_generate_image", side_effect=AssertionError("must not be called")),
        ):
            assert ppp.run_image("test-slug", "business") is True

        assert len(ppp._PENDING_COMMITS) == 1
        staged = ppp._PENDING_COMMITS[0]
        assert staged["gh_path"].endswith("_card.jpg")
        with Image.open(BytesIO(base64.b64decode(staged["content_b64"]))) as card:
            assert card.format == "JPEG"
            assert abs((card.width / card.height) - 1.6) < 0.01

    def test_run_image_generates_both_when_hero_missing(self):
        def generate_image(_: str, destination: Path) -> bool:
            destination.write_bytes(self._hero_bytes())
            return True

        with (
            patch.object(ppp, "_image_exists_on_github", side_effect=[False, False]),
            patch.object(ppp, "_fetch_mdx_meta", return_value=("Test Article", None)),
            patch.object(ppp, "codex_healthy", return_value=True),
            patch.object(ppp, "codex_generate_image", side_effect=generate_image) as generate,
        ):
            assert ppp.run_image("test-slug", "business") is True

        assert generate.call_count == 2
        assert [commit["gh_path"] for commit in ppp._PENDING_COMMITS] == [
            f"{ppp.IMAGE_GH_DIR}/test-slug.jpg",
            f"{ppp.IMAGE_GH_DIR}/test-slug_card.jpg",
        ]


class TestAgyGenerateText:
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


def test_poller_targets_the_bali_zero_org_not_the_old_user_path() -> None:
    # 2026-09-04: on Balizero1987/Teman2 GitHub answers 307 and every gh api
    # create-ref / contents call fails; a whole SEO + layout batch was lost.
    assert ppp.GITHUB_OWNER == "Bali-Zero"
    assert ppp.GITHUB_REPO == "Teman2"


def test_commit_to_branch_looks_up_the_existing_sha_with_an_explicit_get() -> None:
    # 2026-09-04: `gh api … -f ref=<branch>` without --method GET is a POST,
    # answers Not Found, and the PUT of an existing file then carries no sha
    # ("gh: Invalid request" on SEO, layout and 2/4 translations).
    calls: list[list[str]] = []
    inputs: list[str] = []

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        calls.append(list(cmd))
        inputs.append(kwargs.get("input") or "")
        return subprocess.CompletedProcess(cmd, 0, stdout="abc123\n", stderr="")

    with patch.object(ppp.subprocess, "run", side_effect=fake_run):
        assert ppp._commit_to_branch("apps/x.mdx", "Zm9v", "msg", "bot/b") is True

    lookup, put = calls[0], calls[1]
    assert lookup[:4] == ["gh", "api", "--method", "GET"]
    assert "ref=bot/b" in lookup
    assert "PUT" in put
    assert json.loads(inputs[1])["sha"] == "abc123"


def test_send_telegram_alert_reads_last_verdict_line_not_first(monkeypatch, tmp_path) -> None:
    # 2026-09-24: an undeliverable P0 makes tg_notify.py print a human
    # diagnostic `tg_notify:` line BEFORE its machine verdict. This module's
    # own (now-retired) private `_GATEWAY_VERDICT_RE.search()` took the FIRST
    # `tg_notify:` match — the diagnostic's leading word — instead of the
    # real, accepted p0_unsent_spooled outcome.
    logged: list[str] = []
    monkeypatch.setattr(ppp, "log", lambda msg: logged.append(msg))
    monkeypatch.setattr(ppp, "_find_gateway", lambda: tmp_path / "tg_notify.py")

    two_line_stderr = (
        "tg_notify: P0 unsendable (no token/relay) — spooled as p0_unsent\n"
        "tg_notify: p0_unsent_spooled\n"
    )
    fake_proc = subprocess.CompletedProcess(["tg_notify.py"], 0, stdout="", stderr=two_line_stderr)

    with patch("scripts.post_publish_poller.subprocess.run", return_value=fake_proc):
        ppp.send_telegram_alert("test message", dedup_key="test-key")

    assert any("p0_unsent_spooled" in line for line in logged)
    assert not any("P0 unsendable" in line for line in logged)


def test_send_telegram_alert_reads_single_canonical_line(monkeypatch, tmp_path) -> None:
    logged: list[str] = []
    monkeypatch.setattr(ppp, "log", lambda msg: logged.append(msg))
    monkeypatch.setattr(ppp, "_find_gateway", lambda: tmp_path / "tg_notify.py")
    fake_proc = subprocess.CompletedProcess(["tg_notify.py"], 0, stdout="", stderr="tg_notify: sent\n")

    with patch("scripts.post_publish_poller.subprocess.run", return_value=fake_proc):
        ppp.send_telegram_alert("test message", dedup_key="test-key")

    assert any("tg_notify: sent" in line for line in logged)


# ── one open PR per bot family (2026-10-02) ─────────────────────────────────
#
# 33 bot PRs open, most DIRTY for days: every flush opened a new branch + PR
# and nothing ever closed one. #7681 and #7682 carried the same two covers;
# #7681 merged and #7682 was ejected from the merge queue for merge_conflict,
# which is what cleared its auto-merge — the "unarmed" half of the pile.

_IMG = "apps/mouth/public/static/news"
_OLD_COVERS = "bot/news-covers-20261001-120000"


class _FakeGitHub:
    """Just enough of `gh` for the supersede, carry and arm paths."""

    def __init__(self, open_prs=(), queued=(), pr_files=None, main=None, base=None, blobs=None,
                 layouts=None, armed_after_merge=True, list_ok=True):
        self.open_prs = [{"number": n, "url": f"https://github.com/o/r/pull/{n}", "headRefName": ref,
                          "headRefOid": f"oid-{n}"} for n, ref in open_prs]
        self.ref_of = {p["headRefOid"]: p["headRefName"] for p in self.open_prs}
        self.moved = set()  # PR numbers whose head moved after listing
        self.dirty, self.put_fail = set(), set()  # conflicting PR numbers; paths whose PUT fails
        self.queue_on_recheck, self.reads = set(), {}  # PRs that enter the queue after one read
        self.queued, self.armed = set(queued), set()
        self.pr_files = pr_files or {}  # branch -> {path: (blob sha, status)}
        self.main = main or {}  # path -> blob sha on main
        self.base = base or {}  # "base:<branch>" -> {path: blob sha at the merge-base}
        self.blobs = blobs or {}  # blob sha -> bytes
        self.layouts = layouts or {}  # ref -> layout dict
        self.armed_after_merge, self.list_ok = armed_after_merge, list_ok
        self.calls, self.puts, self.put_shas, self.closed = [], {}, {}, []

    def __call__(self, cmd, **kwargs):
        cmd = list(cmd)
        self.calls.append(cmd)
        s = " ".join(cmd)
        if cmd[:3] == ["gh", "pr", "list"]:
            return _res(stdout=json.dumps(self.open_prs)) if self.list_ok else _res(1, stderr="HTTP 502")
        if "--paginate" in cmd and s.endswith("/files --jq .[].filename"):
            n = int(s.split("/pulls/", 1)[1].split("/", 1)[0])
            ref = next(p["headRefName"] for p in self.open_prs if p["number"] == n)
            return _res(stdout="\n".join(self.pr_files.get(ref, {})))
        if cmd[:3] == ["gh", "pr", "create"]:
            return _res(stdout="https://github.com/Bali-Zero/Teman2/pull/900\n")
        if cmd[:3] == ["gh", "pr", "merge"]:
            if self.armed_after_merge:
                self.armed.add(int(cmd[3]))
            return _res()
        if cmd[:3] == ["gh", "pr", "close"]:
            self.closed.append(int(cmd[3]))
            return _res()
        if cmd[:3] == ["gh", "api", "graphql"]:
            n = int(next(a for a in cmd if a.startswith("n="))[2:])
            self.reads[n] = self.reads.get(n, 0) + 1
            if n in self.queue_on_recheck and self.reads[n] > 1:
                self.queued.add(n)
            pr = {"mergeable": "CONFLICTING" if n in self.dirty else "MERGEABLE","autoMergeRequest": {"enabledAt": "x"} if n in self.armed else None,
                  "mergeQueueEntry": {"state": "QUEUED"} if n in self.queued else None,
                  "headRefOid": f"oid-{n}" + ("-moved" if n in self.moved else "")}
            return _res(stdout=json.dumps({"data": {"repository": {"pullRequest": pr}}}))
        if "/compare/mainsha..." in s:
            ref = self.ref_of[s.split("/compare/mainsha...", 1)[1].split()[0]]
            files = [{"filename": p, "sha": sha, "status": st} for p, (sha, st) in self.pr_files[ref].items()]
            return _res(stdout=json.dumps({"merge_base_commit": {"sha": f"base:{ref}"}, "files": files}))
        if "/git/blobs/" in s:
            content = base64.b64encode(self.blobs[s.rsplit("/", 1)[1]]).decode()
            return _res(stdout=json.dumps({"content": content}))
        if "git/refs/heads/main" in s:
            return _res(stdout="mainsha\n")
        if s.endswith("git/refs --method POST --input -"):
            return _res()
        if "/contents/" in s and "PUT" in cmd:
            payload = json.loads(kwargs["input"])
            path = cmd[2].split("/contents/", 1)[1]
            if path in self.put_fail:
                return _res(1, stderr="HTTP 422")
            self.puts[path], self.put_shas[path] = base64.b64decode(payload["content"]), payload.get("sha")
            return _res()
        if "/contents/" in s and "--jq" in cmd:
            path = cmd[cmd.index("--jq") - 1 if "-f" not in cmd else 4].split("/contents/", 1)[1]
            ref = next((a[4:] for a in cmd if a.startswith("ref=")), "main").replace("mainsha", "main")
            # a fresh bot branch is a snapshot of main
            sha = self.base.get(ref, {}).get(path) if ref.startswith("base:") else self.main.get(path)
            return _res(stdout=f"{sha}\n") if sha else _res(1, stderr="gh: Not Found (HTTP 404)")
        if "/contents/" in s:
            ref = s.split("?ref=", 1)[1] if "?ref=" in s else "main"
            ref = {"mainsha": "main"}.get(ref, self.ref_of.get(ref, ref))
            if ref not in self.layouts:
                return _res(1, stderr="gh: Not Found (HTTP 404)")
            return _layout_read_result(self.layouts[ref])
        raise AssertionError(f"unexpected gh call: {s}")


@pytest.fixture
def real_family_listing(monkeypatch):
    monkeypatch.setattr(ppp, "_open_family_prs", _REAL_OPEN_FAMILY_PRS, raising=False)
    monkeypatch.setattr(ppp, "_OPEN_COVER_REFS", None, raising=False)


@pytest.mark.usefixtures("real_family_listing")
class TestOnePrPerFamily:
    def _flush(self, gh, flush):
        with (
            patch("scripts.post_publish_poller.subprocess.run", side_effect=gh),
            patch.object(ppp, "send_telegram_alert") as alert,
        ):
            ok = flush()
        return ok, alert

    def test_supersedes_the_older_open_pr_carrying_its_unlanded_cover(self):
        gh = _FakeGitHub(open_prs=[(7001, _OLD_COVERS)], blobs={"s-old": b"old-bytes"},
                         pr_files={_OLD_COVERS: {f"{_IMG}/old.jpg": ("s-old", "added")}})
        ppp._stage_commit("image", f"{_IMG}/new.jpg", b"new-bytes", "msg")

        ok, _ = self._flush(gh, ppp.flush_image_batch)

        assert ok is True
        assert gh.puts == {f"{_IMG}/old.jpg": b"old-bytes", f"{_IMG}/new.jpg": b"new-bytes"}
        assert gh.closed == [7001]
        creates = [i for i, c in enumerate(gh.calls) if c[:3] == ["gh", "pr", "create"]]
        closes = [i for i, c in enumerate(gh.calls) if c[:3] == ["gh", "pr", "close"]]
        assert len(creates) == 1 and closes[0] > creates[0]  # closed only once its successor exists
        close = next(c for c in gh.calls if c[:3] == ["gh", "pr", "close"])
        assert "--delete-branch" in close and "pull/900" in close[close.index("--comment") + 1]

    def test_a_pr_holding_a_merge_queue_slot_is_never_read_rewritten_or_closed(self):
        gh = _FakeGitHub(open_prs=[(7001, _OLD_COVERS)], queued={7001},
                         pr_files={_OLD_COVERS: {f"{_IMG}/old.jpg": ("s-old", "added")}})
        ppp._stage_commit("image", f"{_IMG}/new.jpg", b"new-bytes", "msg")

        ok, _ = self._flush(gh, ppp.flush_image_batch)

        assert ok is True
        assert gh.closed == []
        assert gh.puts == {f"{_IMG}/new.jpg": b"new-bytes"}
        assert not any("/compare/" in " ".join(c) for c in gh.calls)

    def test_a_cover_main_already_serves_with_other_bytes_is_landed_not_a_conflict(self):
        # the #7681/#7682 twin: main has the slug's cover, the old PR a regenerated copy
        gh = _FakeGitHub(open_prs=[(7001, _OLD_COVERS)], main={f"{_IMG}/twin.jpg": "s-main"},
                         pr_files={_OLD_COVERS: {f"{_IMG}/twin.jpg": ("s-twin", "added")}})
        ppp._stage_commit("image", f"{_IMG}/new.jpg", b"new-bytes", "msg")

        ok, _ = self._flush(gh, ppp.flush_image_batch)

        assert ok is True
        assert gh.puts == {f"{_IMG}/new.jpg": b"new-bytes"}
        assert gh.closed == [7001]

    def test_a_file_main_changed_since_the_pr_branched_is_not_carried_and_its_pr_stays_open(self):
        old_seo = "bot/seo-metadata-20261001-120000"
        art = "apps/mouth/src/content/articles/business"
        gh = _FakeGitHub(
            open_prs=[(7002, old_seo)], blobs={"s-pr-b": b"seo-b"},
            pr_files={old_seo: {f"{art}/a.mdx": ("s-pr-a", "modified"), f"{art}/b.mdx": ("s-pr-b", "modified")}},
            base={f"base:{old_seo}": {f"{art}/a.mdx": "s-base-a", f"{art}/b.mdx": "s-base-b"}},
            main={f"{art}/a.mdx": "s-main-a-newer", f"{art}/b.mdx": "s-base-b"},
        )
        ppp._stage_commit("seo", f"{art}/c.mdx", b"seo-c", "seo")

        ok, alert = self._flush(gh, ppp.flush_seo_batch)

        assert gh.puts == {f"{art}/b.mdx": b"seo-b", f"{art}/c.mdx": b"seo-c"}
        assert gh.put_shas[f"{art}/b.mdx"] == "s-base-b"  # an update of main's copy, not a blind create
        assert gh.closed == []
        assert any("#7002" in c.args[0] for c in alert.call_args_list)
        assert ok is True

    def test_a_pr_whose_head_moved_after_the_carry_is_not_closed(self):
        gh = _FakeGitHub(open_prs=[(7001, _OLD_COVERS)], blobs={"s-old": b"old-bytes"},
                         pr_files={_OLD_COVERS: {f"{_IMG}/old.jpg": ("s-old", "added")}})
        gh.moved.add(7001)  # someone pushed to the old branch while the flush ran
        ppp._stage_commit("image", f"{_IMG}/new.jpg", b"new-bytes", "msg")

        ok, _ = self._flush(gh, ppp.flush_image_batch)

        assert ok is True
        assert gh.closed == []

    def test_an_seo_edit_overridden_by_a_newer_copy_keeps_its_pr_open(self):
        old_seo = "bot/seo-metadata-20261001-120000"
        art = "apps/mouth/src/content/articles/business"
        gh = _FakeGitHub(open_prs=[(7002, old_seo)], blobs={"s-pr-a": b"seo-a-v1"},
                         pr_files={old_seo: {f"{art}/a.mdx": ("s-pr-a", "modified")}},
                         base={f"base:{old_seo}": {f"{art}/a.mdx": "s-base-a"}}, main={f"{art}/a.mdx": "s-base-a"})
        ppp._stage_commit("seo", f"{art}/a.mdx", b"seo-a-v2", "seo")

        ok, alert = self._flush(gh, ppp.flush_seo_batch)

        assert gh.puts == {f"{art}/a.mdx": b"seo-a-v2"}
        assert gh.closed == []
        assert any("#7002" in c.args[0] for c in alert.call_args_list)

    def test_run_image_leaves_the_item_queued_when_open_prs_are_unreadable(self):
        gh = _FakeGitHub(list_ok=False)

        with (
            patch("scripts.post_publish_poller.subprocess.run", side_effect=gh),
            patch.object(ppp, "codex_healthy", side_effect=AssertionError("must not regenerate blind")),
        ):
            assert ppp.run_image("blind", "business") is False

        assert ppp._PENDING_COMMITS == []

    def _old_cover_pr(self, **kwargs):
        gh = _FakeGitHub(open_prs=[(7001, _OLD_COVERS)], blobs={"s-old": b"old-bytes"},
                         pr_files={_OLD_COVERS: {f"{_IMG}/old.jpg": ("s-old", "added")}}, **kwargs)
        ppp._stage_commit("image", f"{_IMG}/new.jpg", b"new-bytes", "msg")
        return gh

    def test_a_failed_write_on_the_new_branch_closes_nothing(self):
        gh = self._old_cover_pr()
        gh.put_fail.add(f"{_IMG}/new.jpg")

        ok, _ = self._flush(gh, ppp.flush_image_batch)

        assert ok is False
        assert gh.closed == []

    def test_a_pr_that_entered_the_queue_before_its_close_is_not_closed(self):
        gh = self._old_cover_pr()
        gh.queue_on_recheck.add(7001)

        ok, _ = self._flush(gh, ppp.flush_image_batch)

        assert ok is True
        assert gh.puts[f"{_IMG}/old.jpg"] == b"old-bytes"
        assert gh.closed == []

    def test_a_pr_too_large_to_compare_is_kept_open_and_named(self):
        gh = self._old_cover_pr()
        gh.pr_files[_OLD_COVERS] = {f"{_IMG}/c{i}.jpg": (f"s{i}", "added") for i in range(300)}
        gh.blobs.update({f"s{i}": b"c" for i in range(300)})  # carryable, were the cap not honoured

        ok, alert = self._flush(gh, ppp.flush_image_batch)

        assert gh.puts == {f"{_IMG}/new.jpg": b"new-bytes"}
        assert gh.closed == []
        assert any("#7001" in c.args[0] for c in alert.call_args_list)

    def test_an_armed_mergeable_covers_pr_is_left_to_merge(self):
        # covers flush every ~15 min, a PR needs 22-68 min to merge: superseding
        # a healthy armed one would restart it at every flush
        gh = self._old_cover_pr()
        gh.armed.add(7001)

        ok, _ = self._flush(gh, ppp.flush_image_batch)

        assert ok is True
        assert gh.puts == {f"{_IMG}/new.jpg": b"new-bytes"}
        assert gh.closed == []
        assert not any("/compare/" in " ".join(c) for c in gh.calls)

    def test_an_armed_but_conflicting_covers_pr_is_still_superseded(self):
        gh = self._old_cover_pr()
        gh.armed.add(7001)
        gh.dirty.add(7001)

        ok, _ = self._flush(gh, ppp.flush_image_batch)

        assert ok is True
        assert gh.puts[f"{_IMG}/old.jpg"] == b"old-bytes"
        assert gh.closed == [7001]

    def test_an_unreadable_pr_list_opens_nothing_and_leaves_the_steps_for_retry(self):
        gh = _FakeGitHub(list_ok=False)
        ppp._stage_commit("image", f"{_IMG}/new.jpg", b"new-bytes", "msg")
        ppp._defer_step_mark("image", "S", "image")

        with patch.object(ppp, "mark_step_done") as mark:
            ok, _ = self._flush(gh, ppp.flush_image_batch)

        assert ok is False
        assert not any(c[:3] == ["gh", "pr", "create"] for c in gh.calls)
        mark.assert_not_called()

    def test_arms_with_auto_only_and_reads_the_pr_state_back(self):
        gh = _FakeGitHub()
        ppp._stage_commit("image", f"{_IMG}/new.jpg", b"new-bytes", "msg")

        ok, alert = self._flush(gh, ppp.flush_image_batch)

        merge = next(c for c in gh.calls if c[:3] == ["gh", "pr", "merge"])
        assert "--auto" in merge and "--squash" not in merge
        assert any(c[:3] == ["gh", "api", "graphql"] and "n=900" in c for c in gh.calls)
        assert ok is True
        alert.assert_not_called()

    def test_a_pr_left_unarmed_alerts_and_fails_the_flush(self):
        gh = _FakeGitHub(armed_after_merge=False)
        ppp._stage_commit("image", f"{_IMG}/new.jpg", b"new-bytes", "msg")

        ok, alert = self._flush(gh, ppp.flush_image_batch)

        assert ok is False
        assert [c.kwargs["dedup_key"] for c in alert.call_args_list] == ["post-publish:bot-pr-unarmed:image"]

    def test_run_image_does_not_regenerate_covers_held_by_an_open_pr(self):
        gh = _FakeGitHub(open_prs=[(7001, _OLD_COVERS)], pr_files={_OLD_COVERS: {
            f"{_IMG}/held.jpg": ("s1", "added"), f"{_IMG}/held_card.jpg": ("s2", "added")}})

        with (
            patch("scripts.post_publish_poller.subprocess.run", side_effect=gh),
            patch.object(ppp, "_fetch_mdx_meta", return_value=("T", None)),
            patch.object(ppp, "codex_healthy", side_effect=AssertionError("must not regenerate")),
        ):
            assert ppp.run_image("held", "business") is True

        assert ppp._PENDING_COMMITS == []

    def test_run_image_derives_the_card_from_a_hero_held_only_by_an_open_pr(self):
        gh = _FakeGitHub(open_prs=[(7001, _OLD_COVERS)],
                         pr_files={_OLD_COVERS: {f"{_IMG}/half.jpg": ("s1", "added")}})

        with (
            patch("scripts.post_publish_poller.subprocess.run", side_effect=gh),
            patch.object(ppp, "_download_github_file", return_value=TestRunImage._hero_bytes()) as download,
        ):
            assert ppp.run_image("half", "business") is True

        download.assert_called_once_with(f"{_IMG}/half.jpg", ref=_OLD_COVERS)
        assert [c["gh_path"] for c in ppp._PENDING_COMMITS] == [f"{_IMG}/half_card.jpg"]

    def test_layout_replays_older_pr_promotions_and_this_ticks_rotations_onto_current_main(self):
        old_layout = "bot/homepage-layout-20261001-120000"
        keys = ppp.HERO_KEYS + ppp.LATEST_KEYS
        main = dict(zip(keys, ["m1", "m2", "m3", "m4", "m5", "l1", "l2", "l3", "l4", "l5"]))
        base = dict(zip(keys, ["b1", "b2", "b3", "b4", "b5", "l1", "l2", "l3", "l4", "l5"]))
        # the old PR promoted p0 (already cascaded to latest_1), m3 (main shows it by now), then p1
        head = dict(zip(keys, ["p1", "m3", "b1", "b2", "b3", "p0", "b4", "b5", "l1", "l2"]))
        gh = _FakeGitHub(open_prs=[(7003, old_layout)],
                         pr_files={old_layout: {ppp.HOMEPAGE_LAYOUT_PATH: ("s-layout", "modified")}},
                         layouts={"main": main, f"base:{old_layout}": base, old_layout: head})
        for slug in ("t1", "t2"):
            ppp._stage_commit("layout", ppp.HOMEPAGE_LAYOUT_PATH, b"{}", f"rotate {slug}", slug=slug)

        ok, _ = self._flush(gh, ppp.flush_layout_batch)

        assert ok is True
        written = json.loads(gh.puts[ppp.HOMEPAGE_LAYOUT_PATH])
        assert [written[k] for k in ppp.HERO_KEYS] == ["t2", "t1", "p1", "p0", "m1"]
        assert [written[k] for k in ppp.LATEST_KEYS] == ["m2", "m3", "m4", "m5", "l1"]
        assert gh.closed == [7003]
