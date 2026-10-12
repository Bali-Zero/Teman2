"""Runtime tests for the trusted pre-push witness and its reconciler."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".husky"
RECONCILER = ROOT / "scripts" / "push_witness_reconcile.py"
PROPRIOCEPTION = ROOT / "scripts" / "proprioception.py"
BRANCH = "agent/air-m5/ops/witness-test"
TRUSTED_FILES = [".husky/pre-push", "scripts/prepush_classify.py", "scripts/prepush_suite_lock.sh",
                 "scripts/ci/prepush_tip_drift.sh"]  # what codex_auto_prepare_trusted_prepush copies

def trust_tree(root: Path) -> Path:
    for rel in TRUSTED_FILES:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)
        target.chmod(0o755)
    return root

def bundle_tree(tmp_path: Path) -> Path:
    return tmp_path / "state" / "codex-autofix-trusted-prepush" / ("1" * 40) / "tree"

def run(cmd: list[str], cwd: Path, *, env: dict[str, str] | None = None, check: bool = True):
    return subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True, check=check)

def git(repo: Path, *args: str, env: dict[str, str] | None = None, check: bool = True):
    return run(["git", *args], repo, env=env, check=check)

@pytest.fixture
def push_repo(tmp_path: Path):
    origin, repo = tmp_path / "origin.git", tmp_path / "repo"
    run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], tmp_path)
    run(["git", "init", "-q", "-b", "main", str(repo)], tmp_path)
    git(repo, "config", "user.name", "Push Witness Test")
    git(repo, "config", "user.email", "push-witness@example.invalid")
    git(repo, "remote", "add", "origin", str(origin))
    (repo / ".husky").mkdir()
    shutil.copy2(HOOKS / "pre-push", repo / ".husky" / "pre-push")  # the tip carries the witness
    git(repo, "add", ".husky/pre-push")
    git(repo, "commit", "-q", "-m", "base")
    git(repo, "-c", "core.hooksPath=/dev/null", "push", "-q", "-u", "origin", "main")
    git(repo, "checkout", "-q", "-b", BRANCH)
    (repo / "change.txt").write_text("change\n", encoding="utf-8")
    git(repo, "add", "change.txt")
    git(repo, "commit", "-q", "-m", "change")
    git(repo, "config", "core.hooksPath", str(HOOKS))
    witness_dir = tmp_path / "witness"
    env = {**os.environ, "NUZ_PREPUSH_TRUST_ROOT": str(trust_tree(bundle_tree(tmp_path))),
           "NUZ_PUSH_WITNESS_DIR": str(witness_dir), "QUICKCHECK_SKIP": "1",
           "PREFLIGHT_PACK_SKIP": "1", "PREPUSH_SKIP_CONSUMER_MAP": "1"}
    return repo, witness_dir, env, git(repo, "rev-parse", "HEAD").stdout.strip()

def reconcile(repo: Path, witness_dir: Path, sha: str | None, tmp_path: Path, *extra: str):
    refs = tmp_path / "refs.json"
    refs.write_text(json.dumps([[BRANCH, sha]]), encoding="utf-8")
    proc = run([sys.executable, "-I", str(RECONCILER), "--json", "--host", "air-m5",
                "--repo-root", str(repo), "--journal", str(witness_dir / "journal.jsonl"),
                *(["--refs-file", str(refs)] if sha else []), "--since", "24", *extra], repo)
    return json.loads(proc.stdout)

def marker(sha: str, trust_root: Path = ROOT, url: str = "", ts: str = ""):
    return {
        "ts": ts or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "host": "Air-M5", "remote": "origin", "url": url,
        "local_ref": f"refs/heads/{BRANCH}", "local_sha": sha,
        "remote_ref": f"refs/heads/{BRANCH}", "remote_sha": "0" * 40,
        "trust_root": str(trust_root), "hook_sha256": "a" * 64, "cwd": str(ROOT),
    }

def journal(witness_dir: Path, *rows: dict, epoch: bool = True, raw: str = "") -> None:
    """Append rows; ``epoch`` first writes an old marker for an unrelated sha (a past witness epoch)."""
    witness_dir.mkdir(exist_ok=True)
    head = [marker("e" * 40, ts="1999-01-01T00:00:00Z")] if epoch else []
    with (witness_dir / "journal.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(raw + "".join(json.dumps(row) + "\n" for row in [*head, *rows]))

def origin_url(repo: Path) -> str:
    return str(repo.parent / "origin.git")

def yesterday() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace("+00:00", "Z")

def drop_the_hook(repo: Path) -> str:
    git(repo, "rm", "-q", ".husky/pre-push")
    git(repo, "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "drop the hook")
    return git(repo, "rev-parse", "HEAD").stdout.strip()

def test_normal_push_writes_exactly_one_marker(push_repo, tmp_path: Path):
    repo, witness_dir, env, sha = push_repo
    git(repo, "push", "-q", "origin", BRANCH, env=env)
    rows = (witness_dir / "journal.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    row = json.loads(rows[0])
    assert (row["local_sha"], row["remote_ref"], row["trust_root"], row["cwd"], row["url"]) == (
        sha, f"refs/heads/{BRANCH}", str(bundle_tree(tmp_path)), str(repo), origin_url(repo)
    )
    assert row["hook_sha256"] == hashlib.sha256((HOOKS / "pre-push").read_bytes()).hexdigest()
    assert (witness_dir.stat().st_mode & 0o777, (witness_dir / "journal.jsonl").stat().st_mode & 0o777) == (0o700, 0o600)
    git(repo, "fetch", "-q", "origin")  # the for-each-ref path and the --refs-file path agree
    by_file, by_refs = reconcile(repo, witness_dir, sha, tmp_path), reconcile(repo, witness_dir, None, tmp_path)
    assert by_file == by_refs and (by_file["witnessed"], by_file["findings"]) == (1, [])

@pytest.mark.parametrize("prefix", [["-c", "core.hooksPath=/dev/null", "push"],
                                    ["push", "--no-verify"]])
def test_bypassed_hook_reports_no_witness(push_repo, tmp_path: Path, prefix: list[str]):
    repo, witness_dir, env, sha = push_repo
    journal(witness_dir)
    git(repo, *prefix, "-q", "origin", BRANCH, env=env)
    result = reconcile(repo, witness_dir, sha, tmp_path)
    assert result["findings"][0]["verdict"] == "NO-WITNESS"

def test_no_journal_means_no_epoch_yet(push_repo, tmp_path: Path):
    repo, witness_dir, env, sha = push_repo
    git(repo, "push", "--no-verify", "-q", "origin", BRANCH, env=env)
    result = reconcile(repo, witness_dir, sha, tmp_path)
    assert (result["checked"], result["findings"], result["note"]) == (0, [], "no witness epoch yet")

@pytest.mark.parametrize("case", ["committed-before-epoch", "tree-without-witness-code"])
def test_unmarked_tip_outside_coverage_is_uncovered(push_repo, tmp_path: Path, case: str):
    repo, witness_dir, _, sha = push_repo
    if case == "committed-before-epoch":
        journal(witness_dir, marker("b" * 40), epoch=False)
    else:
        journal(witness_dir, marker("b" * 40, ts=yesterday()), epoch=False)  # inside the grace
        sha = drop_the_hook(repo)
    result = reconcile(repo, witness_dir, sha, tmp_path)
    assert (result["checked"], result["uncovered"], result["findings"]) == (0, 1, [])

def test_after_the_grace_a_tip_whose_hook_lacks_the_witness_is_judged(push_repo, tmp_path: Path):
    repo, witness_dir, _, _ = push_repo
    journal(witness_dir)  # epoch in 1999: the grace is long over
    sha = drop_the_hook(repo)
    assert reconcile(repo, witness_dir, sha, tmp_path)["findings"][0]["verdict"] == "NO-WITNESS"

def test_marker_for_another_remote_is_no_witness(push_repo, tmp_path: Path):
    repo, witness_dir, env, sha = push_repo
    run(["git", "init", "-q", "--bare", str(tmp_path / "other.git")], tmp_path)
    journal(witness_dir)
    git(repo, "push", "-q", str(tmp_path / "other.git"), BRANCH, env=env)
    git(repo, "push", "--no-verify", "-q", "origin", BRANCH, env=env)
    assert reconcile(repo, witness_dir, sha, tmp_path)["findings"][0]["verdict"] == "NO-WITNESS"

def test_backdated_commit_pushed_around_the_hook_is_judged_by_its_push_time(push_repo, tmp_path: Path):
    repo, witness_dir, env, _ = push_repo
    old = {**env, "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z"}
    git(repo, "-c", "core.hooksPath=/dev/null", "commit", "-q", "--allow-empty", "-m", "backdated", env=old)
    sha = git(repo, "rev-parse", "HEAD").stdout.strip()
    journal(witness_dir)
    git(repo, "push", "--no-verify", "-q", "origin", BRANCH, env=env)  # the tracking-ref reflog dates the push
    result = reconcile(repo, witness_dir, sha, tmp_path)
    assert (result["findings"][0]["verdict"], result["unobserved"]) == ("NO-WITNESS", 0)

def test_a_valid_marker_wins_over_a_foreign_one_whatever_hostname_it_recorded(push_repo, tmp_path: Path):
    repo, witness_dir, _, sha = push_repo
    renamed = {**marker(sha, repo, origin_url(repo)), "host": "Renamed-Mac"}
    journal(witness_dir, marker(sha, tmp_path / "other-root", origin_url(repo)), renamed)
    result = reconcile(repo, witness_dir, sha, tmp_path)
    assert (result["witnessed"], result["findings"]) == (1, [])

@pytest.mark.parametrize("shape", ["origin-minus-suffix", "origin-plus-suffix", "origin-plus-slash"])
def test_a_marker_url_must_equal_the_origin_push_url(push_repo, tmp_path: Path, shape: str):
    repo, witness_dir, _, sha = push_repo
    url = {"origin-minus-suffix": origin_url(repo).removesuffix(".git"),
           "origin-plus-suffix": origin_url(repo) + "-evil",
           "origin-plus-slash": origin_url(repo) + "/"}[shape]
    journal(witness_dir, marker(sha, repo, url))
    assert reconcile(repo, witness_dir, sha, tmp_path)["findings"][0]["verdict"] == "NO-WITNESS"

def test_many_tips_each_keep_their_own_committer_date(push_repo, tmp_path: Path):
    repo, witness_dir, env, sha = push_repo
    old_env = {**env, "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z"}
    git(repo, "-c", "core.hooksPath=/dev/null", "commit", "-q", "--allow-empty", "-m", "old", env=old_env)
    old_sha = git(repo, "rev-parse", "HEAD").stdout.strip()
    other = BRANCH.replace("witness-test", "witness-other")
    journal(witness_dir, marker(sha, repo, origin_url(repo)))
    refs = tmp_path / "refs.json"  # one batched date lookup: the old tip must keep its own date, the new one its own
    refs.write_text(json.dumps([[BRANCH, sha], [other.replace("witness-other", "a-old"), old_sha]]),
                    encoding="utf-8")
    proc = run([sys.executable, "-I", str(RECONCILER), "--json", "--host", "air-m5", "--repo-root",
                str(repo), "--journal", str(witness_dir / "journal.jsonl"), "--refs-file", str(refs)], repo)
    result = json.loads(proc.stdout)
    assert (result["checked"], result["witnessed"], result["findings"]) == (1, 1, [])

def test_forced_push_over_a_witnessed_tip_is_no_witness(push_repo, tmp_path: Path):
    repo, witness_dir, env, sha = push_repo
    journal(witness_dir)
    git(repo, "push", "-q", "origin", BRANCH, env=env)
    assert reconcile(repo, witness_dir, sha, tmp_path)["witnessed"] == 1
    git(repo, "-c", "core.hooksPath=/dev/null", "commit", "-q", "--amend", "-m", "rewritten")
    git(repo, "push", "--no-verify", "--force", "-q", "origin", BRANCH, env=env)
    new = git(repo, "rev-parse", "HEAD").stdout.strip()
    assert reconcile(repo, witness_dir, new, tmp_path)["findings"][0]["verdict"] == "NO-WITNESS"

def test_url_userinfo_is_dropped_and_quotes_are_escaped(push_repo, tmp_path: Path):
    repo, witness_dir, env, _ = push_repo
    odd = tmp_path / 'o"r\\g.git'
    run(["git", "init", "-q", "--bare", str(odd)], tmp_path)
    url = "file://user:" + "s3cr3t" + "@localhost" + str(odd)
    git(repo, "push", "-q", url, BRANCH, env=env)
    row = json.loads((witness_dir / "journal.jsonl").read_text(encoding="utf-8"))
    assert row["url"] == row["remote"] == "file://localhost" + str(odd)

def test_foreign_root_is_reported(push_repo, tmp_path: Path):
    repo, witness_dir, _, sha = push_repo
    journal(witness_dir, marker(sha, tmp_path / "other-root", origin_url(repo)))
    assert reconcile(repo, witness_dir, sha, tmp_path)["findings"][0]["verdict"] == "FOREIGN-ROOT"

@pytest.mark.parametrize("where", ["agent-worktrees-dir", "registered-worktree"])
def test_a_linked_worktree_is_a_trusted_root(push_repo, tmp_path: Path, where: str):
    repo, witness_dir, _, sha = push_repo
    root = repo / ".worktrees" / "ops-lane"
    if where == "registered-worktree":
        root = tmp_path / "linked"
        git(repo, "worktree", "add", "-q", "--detach", str(root))
    journal(witness_dir, marker(sha, root, origin_url(repo)))
    result = reconcile(repo, witness_dir, sha, tmp_path)
    assert (result["witnessed"], result["findings"]) == (1, [])

def test_malformed_journal_line_is_counted_and_ignored(push_repo, tmp_path: Path):
    repo, witness_dir, _, sha = push_repo
    journal(witness_dir, marker(sha, repo, origin_url(repo)), raw="not-json\n")
    result = reconcile(repo, witness_dir, sha, tmp_path)
    assert (result["journal_malformed"], result["witnessed"], result["findings"]) == (1, 1, [])

def test_marker_older_than_commit_is_stale(push_repo, tmp_path: Path):
    repo, witness_dir, _, sha = push_repo
    journal(witness_dir, marker(sha, repo, origin_url(repo), ts="2000-01-01T00:00:00Z"))
    assert reconcile(repo, witness_dir, sha, tmp_path)["findings"][0]["verdict"] == "STALE-WITNESS"

def test_unreadable_tip_is_a_finding_and_json_still_exits_zero(push_repo, tmp_path: Path):
    repo, witness_dir, _, _ = push_repo
    journal(witness_dir)
    result = reconcile(repo, witness_dir, "f" * 40, tmp_path)  # run() raises on a non-zero exit
    assert result["findings"][0]["verdict"] == "RECONCILE-ERROR"
    proc = run([sys.executable, "-I", str(RECONCILER), "--check", "--repo-root", str(repo), "--host",
                "air-m5", "--journal", str(witness_dir / "journal.jsonl"), "--refs-file",
                str(tmp_path / "refs.json")], repo, check=False)
    assert proc.returncode == 1 and "RECONCILE-ERROR" in proc.stdout

def test_marker_write_failure_warns_but_does_not_block(push_repo, tmp_path: Path):
    repo, _, env, _ = push_repo
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("occupied\n", encoding="utf-8")
    proc = git(repo, "push", "-q", "origin", BRANCH,
               env={**env, "NUZ_PUSH_WITNESS_DIR": str(blocked)}, check=False)
    assert proc.returncode == 0
    assert "push witness" in proc.stderr.lower()
    assert git(repo, "ls-remote", "origin", BRANCH).stdout.strip()

def test_since_excludes_old_tip(push_repo, tmp_path: Path):
    repo, witness_dir, env, _ = push_repo
    old_env = {**env, "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z",
               "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z"}
    git(repo, "-c", "core.hooksPath=/dev/null", "commit", "-q", "--allow-empty",
        "-m", "old tip", env=old_env)
    sha = git(repo, "rev-parse", "HEAD").stdout.strip()
    journal(witness_dir)
    result = reconcile(repo, witness_dir, sha, tmp_path)
    assert (result["checked"], result["findings"], result["unobserved"]) == (0, [], 1)  # never fetched

def test_failed_hook_check_never_leaves_marker(push_repo, tmp_path: Path):
    repo, witness_dir, env, _ = push_repo
    bad_root = trust_tree(tmp_path / "bad-trust-root")
    (bad_root / "scripts/ci/prepush_tip_drift.sh").write_text(
        "#!/bin/sh\necho forced-check-failure >&2\nexit 1\n", encoding="utf-8"
    )
    proc = git(repo, "push", "-q", "origin", BRANCH,
               env={**env, "NUZ_PREPUSH_TRUST_ROOT": str(bad_root)}, check=False)
    assert proc.returncode != 0
    assert not (witness_dir / "journal.jsonl").exists()

def test_sha_prefix_is_not_a_witness(push_repo, tmp_path: Path):
    repo, witness_dir, _, sha = push_repo
    journal(witness_dir, marker(sha[:12], repo, origin_url(repo)))
    assert reconcile(repo, witness_dir, sha, tmp_path)["findings"][0]["verdict"] == "NO-WITNESS"

def test_probe_treats_every_finding_as_bad():
    text = PROPRIOCEPTION.read_text(encoding="utf-8")
    assert re.search(r'"id": "push_witness".{0,1200}?"ok_values": \[\]', text, re.DOTALL)

def test_the_healer_never_counts_a_witness_miss_as_session_curable():
    mods = {}
    for name in ("proprioception", "healer_run_checks"):
        spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
        mods[name] = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mods[name])
    entry = next(p for p in mods["proprioception"].DEFAULT_REGISTRY if p["id"] == "push_witness")
    report = {"probes": [{"id": "push_witness", "status": "DIVERGED", "severity": entry["severity"],
                          "cure": entry["cure"]}]}
    assert mods["healer_run_checks"].summarize_proprioception(json.dumps(report)) == (["push_witness"], [])
