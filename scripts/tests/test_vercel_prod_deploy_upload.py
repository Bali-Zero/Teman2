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

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

vpd = pytest.importorskip("vercel_prod_deploy")

SHA = "f0dea7af137caae842bff39db96762090b2d9653"


def test_default_path_parses_unchanged():
    args = vpd._parse_args([])
    assert not args.upload and args.sha is None and not args.preview


def test_upload_parses_sha_and_preview():
    args = vpd._parse_args(["--upload", "--sha", SHA, "--preview"])
    assert args.upload and args.preview and args.sha == SHA


@pytest.mark.parametrize(
    "argv",
    [
        ["--upload"],
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
    assert "--prod" not in cmd


def test_production_upload_adds_prod_only_without_preview():
    assert "--prod" in vpd._vercel_deploy_cmd("/x", SHA, preview=False)
