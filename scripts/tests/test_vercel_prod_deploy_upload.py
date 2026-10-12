#!/usr/bin/env python3
"""Corpus for `--upload`: deploy a git-archive of one sha through the Vercel CLI, no GitHub.

The public repo behind `gitSource` is being deleted, so the deploy script needs a route that
needs no GitHub. No network: git runs against a throwaway repo, the CLI is never invoked.
Guilt: flag parsing accepts the new mode, the archive holds exactly the include list at the
named sha, the CLI command carries the sha as build AND runtime env. Innocence: a bad sha or a
mixed flag set is refused, a working-tree edit never leaks into the archive, `--preview` never
adds `--prod`, and the default (no flag) path still parses unchanged.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import types
import unittest.mock

import fcntl

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

vpd = pytest.importorskip("vercel_prod_deploy")

SHA = "f0dea7af137caae842bff39db96762090b2d9653"
OTHER_SHA = "e2760f91b024daff17ac9266053b2aa93d5de143"
OLD_SHA = "aaaa111122223333444455556666777788889999"


def test_default_path_parses_unchanged():
    args = vpd._parse_args([])
    assert not args.upload and args.sha is None and not args.preview


def test_upload_parses_sha_and_preview():
    args = vpd._parse_args(["--upload", "--sha", SHA, "--preview"])
    assert args.upload and args.preview and args.sha == SHA


def test_upload_without_sha_parses_as_default_target():
    args = vpd._parse_args(["--upload"])
    assert args.upload and args.sha is None


def test_auto_build_without_upload_is_refused():
    with pytest.raises(SystemExit) as exc:
        vpd._parse_args(["--auto-build"])
    assert exc.value.code == 2


@pytest.mark.parametrize(
    "argv",
    [
        ["--upload", "--sha", "main"],
        ["--upload", "--sha", SHA.upper()],
        ["--upload", "--sha", SHA[:39]],
        ["--upload", "--sha", SHA, "--promote-only"],
        ["--upload", "--sha", SHA, "--ref", SHA],
        ["--sha", SHA],
        ["--preview"],
    ],
)
def test_bad_flag_sets_are_refused(argv):
    with pytest.raises(SystemExit) as exc:
        vpd._parse_args(argv)
    assert exc.value.code == 2


def test_include_list_covers_the_known_out_of_app_reads():
    paths = {p for p, _why in vpd.UPLOAD_INCLUDE}
    assert {"apps/mouth", "packages/core", "package.json", "package-lock.json"} <= paths
    assert "data/kbli-filiera/pma-editorial-certifications.json" in paths
    assert all(why.strip() for _p, why in vpd.UPLOAD_INCLUDE), "every entry says why"


def _repo(tmp_path: pathlib.Path) -> tuple[pathlib.Path, str]:
    repo = tmp_path / "repo"
    (repo / "apps/mouth").mkdir(parents=True)
    (repo / "apps/other").mkdir(parents=True)
    (repo / "apps/mouth/a.txt").write_text("committed")
    (repo / "apps/other/b.txt").write_text("not included")
    (repo / "package.json").write_text("{}")
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t"}
    for cmd in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "x"]):
        subprocess.run(["git", *cmd], cwd=repo, check=True, env=env, capture_output=True)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True,
                         text=True).stdout.strip()
    return repo, sha


def test_archive_holds_only_the_include_list_at_the_sha(tmp_path, monkeypatch):
    repo, sha = _repo(tmp_path)
    (repo / "apps/mouth/a.txt").write_text("dirty working tree")  # must NOT ship
    monkeypatch.setattr(vpd, "UPLOAD_INCLUDE", (("apps/mouth", "app"), ("package.json", "root")))
    monkeypatch.chdir(repo)
    dest = tmp_path / "out"
    dest.mkdir()
    vpd._archive_tree(sha, str(dest))
    assert (dest / "apps/mouth/a.txt").read_text() == "committed"
    assert (dest / "package.json").exists()
    assert not (dest / "apps/other").exists()


def test_archive_fails_loudly_when_an_include_path_is_missing(tmp_path, monkeypatch):
    repo, sha = _repo(tmp_path)
    monkeypatch.setattr(vpd, "UPLOAD_INCLUDE", (("apps/mouth", "app"), ("packages/core", "gone")))
    monkeypatch.chdir(repo)
    dest = tmp_path / "out"
    dest.mkdir()
    with pytest.raises(RuntimeError):
        vpd._archive_tree(sha, str(dest))


def test_project_link_names_org_and_project(tmp_path):
    vpd._write_project_link(str(tmp_path))
    import json
    data = json.loads((tmp_path / ".vercel/project.json").read_text())
    assert data == {"orgId": vpd.TEAM_ID, "projectId": vpd.PROJECT_ID}


def test_cli_command_carries_sha_as_build_and_runtime_env():
    cmd = vpd._vercel_deploy_cmd("/x", SHA, preview=True)
    assert f"BUILD_COMMIT_SHA={SHA}" in cmd
    assert cmd.count(f"BUILD_COMMIT_SHA={SHA}") == 2
    assert cmd[cmd.index("--build-env") + 1] == f"BUILD_COMMIT_SHA={SHA}"
    assert cmd[cmd.index("--env") + 1] == f"BUILD_COMMIT_SHA={SHA}"
    assert cmd[cmd.index("--meta") + 1] == f"nzBuildSha={SHA}"
    assert "--prod" not in cmd


def test_production_upload_adds_prod_only_without_preview():
    assert "--prod" in vpd._vercel_deploy_cmd("/x", SHA, preview=False)


def test_the_cli_never_waits_for_the_build_and_production_never_self_aliases() -> None:
    prod = vpd._vercel_deploy_cmd("/x", SHA, preview=False)
    preview = vpd._vercel_deploy_cmd("/x", SHA, preview=True)
    assert "--no-wait" in prod and "--no-wait" in preview
    assert "--skip-domain" in prod
    assert "--skip-domain" not in preview


def test_url_from_stdout_when_the_cli_finished():
    assert vpd._cli_deployment_url("https://mouth-abc123xyz-nuzantara-2026.vercel.app\n", "") == (
        "https://mouth-abc123xyz-nuzantara-2026.vercel.app"
    )


def test_url_from_stderr_when_the_cli_died_mid_poll():
    err = (
        "Uploading [====] (1.0MB/1.0MB)\n"
        "  Inspect     https://vercel.com/nuzantara-2026/mouth/DQ3eXRbGsddYCdhreA4awvvwXgSA\n"
        "  Preview     https://mouth-3umzckvvw-nuzantara-2026.vercel.app\n"
        "Error: read ETIMEDOUT\n"
    )
    assert vpd._cli_deployment_url("", err) == "https://mouth-3umzckvvw-nuzantara-2026.vercel.app"


def test_no_url_is_none_not_the_inspect_link():
    assert vpd._cli_deployment_url("", "Inspect https://vercel.com/nuzantara-2026/mouth/DQ3e\n") is None


def _run(argv: list[str]) -> int:
    with unittest.mock.patch.object(sys, "argv", ["vercel_prod_deploy.py", *argv]):
        return vpd.main()


def test_upload_without_sha_resolves_the_default_target(monkeypatch):
    uploaded: list[tuple[str, bool]] = []
    monkeypatch.setattr(vpd, "_deploy_relevant_head", lambda: (SHA, "test target"))
    monkeypatch.setattr(
        vpd, "_upload_with_guards", lambda sha, preview: uploaded.append((sha, preview)) or 0
    )

    assert _run(["--upload"]) == 0
    assert uploaded == [(SHA, False)]


def test_dep_sha_reads_github_and_upload_metadata():
    assert vpd._dep_sha({"meta": {"githubCommitSha": SHA, "nzBuildSha": OTHER_SHA}}) == SHA
    assert vpd._dep_sha({"meta": {"nzBuildSha": OTHER_SHA}}) == OTHER_SHA
    assert vpd._dep_sha({}) is None


def test_auto_build_promotes_ready_upload_for_target(monkeypatch):
    promoted: list[tuple[str, str]] = []
    uploaded = unittest.mock.Mock(return_value=0)

    def api(method, path, body=None):
        assert method == "GET", "auto-build must not POST when a READY upload exists"
        assert path.startswith("/v6/deployments")
        return 200, {
            "deployments": [{
                "uid": "dpl_upload",
                "state": "READY",
                "readySubstate": "STAGED",
                "meta": {"nzBuildSha": SHA},
            }]
        }

    monkeypatch.setattr(vpd, "_deploy_relevant_head", lambda: (SHA, "test target"))
    monkeypatch.setattr(vpd, "_served_commit", lambda: OLD_SHA)
    monkeypatch.setattr(vpd, "_production_includes", lambda target, live: False)
    monkeypatch.setattr(vpd, "_api", api)
    monkeypatch.setattr(vpd, "_promote", lambda dpl, sha: promoted.append((dpl, sha)) or True)
    monkeypatch.setattr(vpd, "_upload_with_guards", uploaded)

    assert _run(["--upload", "--auto-build"]) == 0
    assert promoted == [("dpl_upload", SHA)]
    uploaded.assert_not_called()


def test_auto_build_does_nothing_when_production_is_current(monkeypatch):
    uploaded = unittest.mock.Mock(return_value=0)
    api = unittest.mock.Mock(side_effect=AssertionError("current production needs no listing"))
    monkeypatch.setattr(vpd, "_deploy_relevant_head", lambda: (SHA, "test target"))
    monkeypatch.setattr(vpd, "_served_commit", lambda: SHA)
    monkeypatch.setattr(vpd, "_production_includes", lambda target, live: True)
    monkeypatch.setattr(vpd, "_api", api)
    monkeypatch.setattr(vpd, "_upload_with_guards", uploaded)

    assert _run(["--upload", "--auto-build"]) == 0
    api.assert_not_called()
    uploaded.assert_not_called()


def test_auto_build_refuses_a_degraded_default_target(monkeypatch):
    upload = unittest.mock.Mock(return_value=0)
    monkeypatch.setattr(
        vpd,
        "_deploy_relevant_head",
        lambda: (SHA, "main HEAD — git fetch failed (timeout), could not filter by path"),
    )
    monkeypatch.setattr(vpd, "_upload_with_guards", upload)

    assert _run(["--upload", "--auto-build"]) == 3
    upload.assert_not_called()


def test_auto_build_uploads_only_at_the_normal_create_point(monkeypatch):
    uploaded = unittest.mock.Mock(return_value=0)
    api_calls: list[tuple[str, str]] = []

    def api(method, path, body=None):
        api_calls.append((method, path))
        if path.startswith("/v6/deployments"):
            return 200, {"deployments": []}
        raise AssertionError("auto-build must replace, not accompany, the gitSource POST")

    monkeypatch.setattr(vpd, "_deploy_relevant_head", lambda: (SHA, "test target"))
    monkeypatch.setattr(vpd, "_served_commit", lambda: OLD_SHA)
    monkeypatch.setattr(vpd, "_production_includes", lambda target, live: False)
    monkeypatch.setattr(vpd, "_api", api)
    monkeypatch.setattr(vpd, "_upload_with_guards", uploaded)

    assert _run(["--upload", "--auto-build"]) == 0
    uploaded.assert_called_once_with(SHA, False)
    assert not any(method == "POST" for method, _path in api_calls)


def test_upload_ledger_suspends_after_two_failures_and_resets_for_new_sha(
    tmp_path, monkeypatch, capsys
):
    calls: list[str] = []
    monkeypatch.setattr(vpd, "UPLOAD_LEDGER_PATH", str(tmp_path / "attempts.json"))
    monkeypatch.setattr(vpd, "UPLOAD_LOCK_PATH", str(tmp_path / "deploy.lock"))
    monkeypatch.setattr(vpd, "_disk_ok", lambda min_gib=3: True)
    monkeypatch.setattr(
        vpd, "_upload_main", lambda sha, preview: calls.append(sha) or 1
    )

    assert vpd._upload_with_guards(SHA, False) == 1
    assert vpd._upload_with_guards(SHA, False) == 1
    assert vpd._upload_with_guards(SHA, False) == 4
    assert calls == [SHA, SHA]
    assert "SUSPENDED" in capsys.readouterr().out

    assert vpd._upload_with_guards(OTHER_SHA, False) == 1
    assert calls == [SHA, SHA, OTHER_SHA]


def test_upload_exceptions_are_counted_toward_suspension(tmp_path, monkeypatch):
    calls = 0

    def timeout(_sha, _preview):
        nonlocal calls
        calls += 1
        raise subprocess.TimeoutExpired(["vercel", "deploy"], 1800)

    monkeypatch.setattr(vpd, "UPLOAD_LEDGER_PATH", str(tmp_path / "attempts.json"))
    monkeypatch.setattr(vpd, "UPLOAD_LOCK_PATH", str(tmp_path / "deploy.lock"))
    monkeypatch.setattr(vpd, "_disk_ok", lambda min_gib=3: True)
    monkeypatch.setattr(vpd, "_upload_main", timeout)

    assert vpd._upload_with_guards(SHA, False) == 1
    assert vpd._upload_with_guards(SHA, False) == 1
    assert vpd._upload_with_guards(SHA, False) == 4
    assert calls == 2


def test_busy_upload_lock_exits_zero(tmp_path, monkeypatch, capsys):
    lock_path = tmp_path / "deploy.lock"
    monkeypatch.setattr(vpd, "UPLOAD_LOCK_PATH", str(lock_path))
    monkeypatch.setattr(vpd, "UPLOAD_LEDGER_PATH", str(tmp_path / "attempts.json"))
    upload = unittest.mock.Mock(return_value=1)
    monkeypatch.setattr(vpd, "_upload_main", upload)

    with lock_path.open("a+") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert vpd._upload_with_guards(SHA, False) == 0

    upload.assert_not_called()
    assert "already in progress" in capsys.readouterr().out


def test_disk_floor_refuses_before_archiving(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(vpd, "UPLOAD_LOCK_PATH", str(tmp_path / "deploy.lock"))
    monkeypatch.setattr(vpd, "UPLOAD_LEDGER_PATH", str(tmp_path / "attempts.json"))
    monkeypatch.setattr(
        vpd.shutil,
        "disk_usage",
        lambda _path: types.SimpleNamespace(free=3 * (1 << 30) - 1),
    )
    upload = unittest.mock.Mock(return_value=0)
    monkeypatch.setattr(vpd, "_upload_main", upload)

    assert vpd._upload_with_guards(SHA, False) == 1
    upload.assert_not_called()
    assert "3 GiB" in capsys.readouterr().out


@pytest.mark.parametrize("served_already", [True, False])
def test_production_tail_promotes_only_when_the_probe_has_not_proven_it(monkeypatch, capsys, served_already):
    url = "https://mouth-abc123def-nuzantara-2026.vercel.app"
    monkeypatch.setattr(vpd, "_token", lambda: "x")
    monkeypatch.setattr(vpd, "_archive_tree", lambda sha, dest: None)
    monkeypatch.setattr(vpd, "_write_project_link", lambda dest: None)
    monkeypatch.setattr(vpd.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, url + "\n", ""))
    monkeypatch.setattr(vpd, "_api", lambda method, path, body=None: (200, {"id": "dpl_X", "readyState": "READY"}))
    monkeypatch.setattr(vpd, "_probe_until", lambda sha, attempts: served_already)
    promote = unittest.mock.Mock(return_value=True)
    monkeypatch.setattr(vpd, "_promote", promote)

    assert vpd._upload_main(SHA, preview=False) == 0
    out = capsys.readouterr().out
    if served_already:
        promote.assert_not_called()
        assert "already serves" in out and "not promoted" in out
    else:
        promote.assert_called_once_with("dpl_X", SHA)
        assert "OK - promoted dpl_X" in out
