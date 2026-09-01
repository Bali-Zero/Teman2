"""Tests for scripts/lint_arm_probe.py (autoMergeRequest null-ambiguity lint).

Every FAIL-class detector gets a GUILT case (the disease IS caught) and an
INNOCENCE case (the adjacent legitimate state is NOT flagged) — same
discipline lint_home_fork.py's and lint_plist_keepalive.py's tests apply
(cicatrix-superscar.md #3, guard-over-match).

SELF-SCAN NOTE: every fixture string below embeds the literal decision
pattern this lint scans for (a `.get` lookup or bracket subscript keyed on
the field name, etc.), which means the SOURCE lines that define them, in
THIS tracked file, would themselves
trip the lint if it ever walked scripts/tests/. Each such source line
therefore carries a trailing `# lint-arm-probe:fixture` comment — Python
discards `#` comments at parse time, so the comment never becomes part of
the fixture TEXT a test hands to `scan_text()` (the runtime string a guilt
test asserts a finding against has no marker in it at all, and correctly
still finds one). The marker only blinds `lint_arm_probe.py`'s own
repo-walk to ITS SOURCE LINE. `test_marker_appears_only_in_this_lints_own_test_file`
and `test_this_test_files_own_source_produces_no_findings_when_scanned`
both verify the mechanism actually holds — see their docstrings.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "lint_arm_probe.py"
_spec = importlib.util.spec_from_file_location("lint_arm_probe", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
larp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(larp)


# ---------------------------------------------------------------- fixtures
#
# Each pair below mirrors a SHAPE actually found in the 2026-08-29 audit of
# this repo's 17 autoMergeRequest consumers.

# GUILT — dict.get("autoMergeRequest") used as an eligibility filter, no
# positive probe anywhere (mirrors scripts/merge_train.py::order_queue).
GUILTY_GET_PY = (
    'def order_queue(prs):\n'
    '    return [p for p in prs if p.get("autoMergeRequest")]\n'  # lint-arm-probe:fixture
)

# INNOCENCE — same .get(...) test, but mergeQueueEntry co-occurs in the file
# (mirrors .github/workflows/merge-queue-watch.yml's Condition 2 / scripts/
# lane_ship.sh's isInMergeQueue cross-check, generalized to the mergeQueueEntry
# shape).
INNOCENT_GET_WITH_PROBE_PY = (
    'def order_queue(prs):\n'
    '    eligible = [p for p in prs if p.get("mergeQueueEntry") or p.get("autoMergeRequest")]\n'  # lint-arm-probe:fixture
    '    return eligible\n'
)

# GUILT — bracket subscript access, no probe (mirrors scripts/
# queue_baseline_probe.py::fetch_automerge_enabled_at).
GUILTY_SUBSCRIPT_PY = (
    'def fetch_automerge_enabled_at(payload):\n'
    '    enabled_at = payload["data"]["repository"]["pullRequest"]["autoMergeRequest"]\n'  # lint-arm-probe:fixture
    '    return enabled_at\n'
)

# GUILT — jq select()/==null filter, no probe (mirrors scripts/ci/
# queue_rearm_population.sh's --candidates mode).
GUILTY_JQ_SH = (
    'jq -r \'.[]|select(.mergeable=="MERGEABLE" and .autoMergeRequest==null)|.number\'\n'  # lint-arm-probe:fixture
)

# INNOCENCE — jq decision line, mergeQueue( snapshot probed elsewhere in the
# same file (mirrors scripts/ci/queue_rearm.sh's `inq=$(... mergeQueue(...) ...)`
# cross-check before acting on any candidate).
INNOCENT_JQ_WITH_MERGEQUEUE_PAREN_SH = (
    'inq=$(gh api graphql -f query="{repository{mergeQueue(branch:\\"main\\"){entries{nodes{pullRequest{number}}}}}}" --jq \'.\')\n'  # lint-arm-probe:fixture
    'cand=$(echo "$all" | jq -r \'.[]|select(.autoMergeRequest==null)|.number\')\n'  # lint-arm-probe:fixture
)

# INNOCENCE — isInMergeQueue alone counts as the probe (mirrors
# merge-queue-watch.yml's ARMED-STUCK condition: `amr` is only tested when
# truthy, and the alert additionally requires `not isInMergeQueue`).
INNOCENT_ISINMERGEQUEUE_PY = (
    'amr = pr.get("autoMergeRequest")\n'  # lint-arm-probe:fixture
    'if amr and amr.get("enabledAt") and not pr.get("isInMergeQueue"):\n'  # lint-arm-probe:fixture
    '    alert("armed but stuck")\n'
)

# INNOCENCE — field requested (--json field list) but never tested: no
# .get(/subscript/select syntax touches it, so there is nothing to decide on
# (mirrors scripts/mq.sh's confirm-step, which only echoes the response).
FIELD_ONLY_NO_DECISION_SH = (
    'gh pr view "$pr" --json autoMergeRequest,mergeStateStatus,headRefOid\n'  # lint-arm-probe:fixture
    'echo "confirm: $OUT"\n'
)

# INNOCENCE — a full-line comment that WOULD match the decision pattern if
# comment-stripping did not apply (mirrors scripts/pr_watch.sh's own doc
# comment warning future readers off autoMergeRequest).
COMMENT_WOULD_MATCH_IF_NOT_STRIPPED_PY = (
    '# example: `if pr.get("autoMergeRequest"): reroll(pr)` is the anti-pattern this file avoids\n'  # lint-arm-probe:fixture
)


# ---------------------------------------------------------------- scan_text (pure)


class TestScanTextGuilt:
    def test_dict_get_without_probe_is_a_finding(self):
        result = larp.scan_text(GUILTY_GET_PY, "fake.py")
        assert len(result["findings"]) == 1
        assert "fake.py:2" in result["findings"][0]
        assert result["has_positive_probe"] is False

    def test_bracket_subscript_without_probe_is_a_finding(self):
        result = larp.scan_text(GUILTY_SUBSCRIPT_PY, "fake.py")
        assert len(result["findings"]) == 1
        assert "fake.py:2" in result["findings"][0]

    def test_jq_select_without_probe_is_a_finding(self):
        result = larp.scan_text(GUILTY_JQ_SH, "fake.sh")
        assert len(result["findings"]) == 1
        assert "fake.sh:1" in result["findings"][0]


class TestScanTextInnocence:
    def test_dict_get_with_mergequeueentry_probe_is_clean(self):
        result = larp.scan_text(INNOCENT_GET_WITH_PROBE_PY, "fake.py")
        assert result["findings"] == []
        assert result["has_positive_probe"] is True

    def test_jq_decision_with_mergequeue_paren_probe_is_clean(self):
        result = larp.scan_text(INNOCENT_JQ_WITH_MERGEQUEUE_PAREN_SH, "fake.sh")
        assert result["findings"] == []
        assert result["has_positive_probe"] is True

    def test_isinmergequeue_probe_alone_is_sufficient(self):
        result = larp.scan_text(INNOCENT_ISINMERGEQUEUE_PY, "fake.py")
        assert result["findings"] == []
        assert result["has_positive_probe"] is True

    def test_field_requested_but_never_tested_has_no_decision_lines(self):
        result = larp.scan_text(FIELD_ONLY_NO_DECISION_SH, "fake.sh")
        assert result["findings"] == []
        assert result["decision_lines"] == []

    def test_full_comment_line_is_not_treated_as_a_decision(self):
        result = larp.scan_text(COMMENT_WOULD_MATCH_IF_NOT_STRIPPED_PY, "fake.py")
        assert result["findings"] == []
        assert result["decision_lines"] == []
        assert result["has_positive_probe"] is False

    def test_suppression_marker_hides_a_line_from_both_directions(self):
        # A line carrying the marker is invisible even though it would
        # otherwise match the decision pattern with no probe in scope.
        text = 'x = pr.get("autoMergeRequest")  # lint-arm-probe:fixture\n'
        result = larp.scan_text(text, "fake.py")
        assert result["findings"] == []
        assert result["decision_lines"] == []


# ---------------------------------------------------------------- run() (file I/O)


class TestRunDiscovery:
    def test_finds_guilty_file_under_root(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "scripts").mkdir(parents=True)
        (repo / "scripts" / "bad.py").write_text(GUILTY_GET_PY)
        result = larp.run([repo], repo)
        assert result["exit"] & 1
        assert any("bad.py" in f for f in result["findings"])

    def test_clean_file_with_probe_produces_no_finding(self, tmp_path, monkeypatch):
        # Isolated from the real ALLOWLIST: its 2 real entries name paths
        # that do not exist under this synthetic `repo`, and would
        # otherwise report as spurious stale_allowlist (exit bit 2) —
        # a real repo scan (--root ., the CLI default) never hits this,
        # since both real paths genuinely are under the walked root there.
        monkeypatch.setattr(larp, "ALLOWLIST", {})
        repo = tmp_path / "repo"
        (repo / "scripts").mkdir(parents=True)
        (repo / "scripts" / "good.py").write_text(INNOCENT_GET_WITH_PROBE_PY)
        result = larp.run([repo], repo)
        assert result["exit"] == 0
        assert result["findings"] == []

    def test_prunes_vendored_dirs(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "node_modules" / "pkg").mkdir(parents=True)
        (repo / "node_modules" / "pkg" / "bad.py").write_text(GUILTY_GET_PY)
        result = larp.run([repo], repo)
        assert result["files_scanned"] == 0
        assert result["findings"] == []

    def test_skips_non_scanned_extensions(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "bad.txt").write_text(GUILTY_GET_PY)
        result = larp.run([repo], repo)
        assert result["files_scanned"] == 0
        assert result["findings"] == []

    def test_dedupes_overlapping_roots(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "scripts").mkdir(parents=True)
        (repo / "scripts" / "bad.py").write_text(GUILTY_GET_PY)
        result = larp.run([repo, repo / "scripts"], repo)
        assert result["files_scanned"] == 1

    def test_unreadable_file_is_an_operational_error_not_silent(self, tmp_path, monkeypatch):
        repo = tmp_path / "repo"
        (repo / "scripts").mkdir(parents=True)
        bad = repo / "scripts" / "unreadable.py"
        bad.write_text(GUILTY_GET_PY)
        orig_read_text = Path.read_text

        def _boom(self, *a, **k):
            if self == bad:
                raise OSError("permission denied")
            return orig_read_text(self, *a, **k)

        monkeypatch.setattr(Path, "read_text", _boom)
        result = larp.run([repo], repo)
        assert result["exit"] & 4
        assert any("unreadable.py" in e for e in result["errors"])

    def test_exit_bitmask_combines_findings_and_errors(self, tmp_path, monkeypatch):
        monkeypatch.setattr(larp, "ALLOWLIST", {})  # isolate from the 2 real entries — see above
        repo = tmp_path / "repo"
        (repo / "scripts").mkdir(parents=True)
        (repo / "scripts" / "bad.py").write_text(GUILTY_GET_PY)
        unreadable = repo / "scripts" / "unreadable.py"
        unreadable.write_text(GUILTY_GET_PY)
        orig_read_text = Path.read_text

        def _boom(self, *a, **k):
            if self == unreadable:
                raise OSError("permission denied")
            return orig_read_text(self, *a, **k)

        monkeypatch.setattr(Path, "read_text", _boom)
        result = larp.run([repo], repo)
        assert result["exit"] == 5  # 1 (finding) | 4 (error)


# ---------------------------------------------------------------- main() / CLI


class TestMainCli:
    def test_json_output_reports_exit_and_findings(self, tmp_path, capsys, monkeypatch):
        monkeypatch.setattr(larp, "ALLOWLIST", {})  # isolate from the 2 real entries — see above
        repo = tmp_path / "repo"
        (repo / "scripts").mkdir(parents=True)
        (repo / "scripts" / "bad.py").write_text(GUILTY_GET_PY)
        rc = larp.main(["--json", "--repo-root", str(repo), "--root", "scripts"])
        assert rc == 1
        out = json.loads(capsys.readouterr().out)
        assert out["exit"] == 1
        assert len(out["findings"]) == 1

    def test_clean_repo_exits_zero(self, tmp_path, capsys, monkeypatch):
        monkeypatch.setattr(larp, "ALLOWLIST", {})  # isolate from the 2 real entries — see above
        repo = tmp_path / "repo"
        (repo / "scripts").mkdir(parents=True)
        (repo / "scripts" / "good.py").write_text(INNOCENT_GET_WITH_PROBE_PY)
        rc = larp.main(["--repo-root", str(repo), "--root", "scripts"])
        assert rc == 0
        assert "clean" in capsys.readouterr().out


# ---------------------------------------------------------------- ALLOWLIST (real-file exemptions)
#
# SUPPRESSION_MARKER is reserved for this lint's own synthetic fixtures (see
# TestSelfScanIsClean below) — ALLOWLIST is the path-keyed mechanism for real
# files a decision pattern matches by text alone without ever deriving a
# verdict from it. These tests exercise the mechanism generically by
# monkeypatching `larp.ALLOWLIST`, not the two real production entries —
# TestRealAllowlistEntries below covers those directly.


class TestAllowlistMechanism:
    def test_allowlisted_guilty_file_is_reported_as_allowlisted_not_a_finding(self, tmp_path, monkeypatch):
        repo = tmp_path / "repo"
        (repo / "scripts").mkdir(parents=True)
        (repo / "scripts" / "reporter.py").write_text(GUILTY_GET_PY)
        monkeypatch.setattr(larp, "ALLOWLIST", {"scripts/reporter.py": {"lines": (2,), "reason": "test reason"}})
        result = larp.run([repo], repo)
        assert result["exit"] == 0
        assert result["findings"] == []
        assert result["allowlisted"] == [{"path": "scripts/reporter.py", "reason": "test reason", "lines": [2]}]
        assert result["stale_allowlist"] == []

    def test_allowlist_does_not_blanket_suppress_a_different_guilty_file(self, tmp_path, monkeypatch):
        # INNOCENCE of the mechanism: allowlisting one path must not silence
        # an unrelated real violation elsewhere in the tree.
        repo = tmp_path / "repo"
        (repo / "scripts").mkdir(parents=True)
        (repo / "scripts" / "reporter.py").write_text(GUILTY_GET_PY)
        (repo / "scripts" / "other_bad.py").write_text(GUILTY_SUBSCRIPT_PY)
        monkeypatch.setattr(larp, "ALLOWLIST", {"scripts/reporter.py": {"lines": (2,), "reason": "test reason"}})
        result = larp.run([repo], repo)
        assert result["exit"] == 1
        assert len(result["findings"]) == 1
        assert "other_bad.py" in result["findings"][0]
        assert result["allowlisted"] == [{"path": "scripts/reporter.py", "reason": "test reason", "lines": [2]}]

    def test_allowlist_does_not_blanket_suppress_a_new_violation_in_the_same_file(self, tmp_path, monkeypatch):
        # Axis-2 regression (cross-family review, 2026-08-31): a SECOND,
        # genuinely different decision line inside the SAME allowlisted file
        # must still surface. The pre-fix code checked `if result["findings"]:
        # continue` at file granularity, so waiving line 2 would have also
        # silently swallowed a brand-new line-3 violation with no relation to
        # the documented reason.
        repo = tmp_path / "repo"
        (repo / "scripts").mkdir(parents=True)
        (repo / "scripts" / "reporter.py").write_text(
            'def order_queue(prs):\n'
            '    return [p for p in prs if p.get("autoMergeRequest")]\n'  # lint-arm-probe:fixture
            '    other = p2["data"]["autoMergeRequest"]\n'  # lint-arm-probe:fixture
        )
        monkeypatch.setattr(larp, "ALLOWLIST", {"scripts/reporter.py": {"lines": (2,), "reason": "test reason"}})
        result = larp.run([repo], repo)
        assert result["exit"] & 1
        assert len(result["findings"]) == 1
        assert "reporter.py:3" in result["findings"][0]
        assert result["allowlisted"] == [{"path": "scripts/reporter.py", "reason": "test reason", "lines": [2]}]

    def test_stale_allowlist_entry_reported_when_file_no_longer_matches(self, tmp_path, monkeypatch):
        # SHRINK-ONLY discipline: a waiver over a file that no longer needs
        # it (rewritten clean — a positive probe now co-occurs, so the line
        # is no longer a live finding) must not sit silently forever.
        repo = tmp_path / "repo"
        (repo / "scripts").mkdir(parents=True)
        (repo / "scripts" / "clean_now.py").write_text(INNOCENT_GET_WITH_PROBE_PY)
        monkeypatch.setattr(larp, "ALLOWLIST", {"scripts/clean_now.py": {"lines": (2,), "reason": "test reason"}})
        result = larp.run([repo], repo)
        assert result["exit"] & 2
        assert not result["exit"] & 1
        assert result["allowlisted"] == []
        assert result["stale_allowlist"] == [
            "scripts/clean_now.py: line [2] no longer matches any decision pattern — "
            "SHRINK-ONLY: remove it from the entry"
        ]

    def test_stale_allowlist_entry_reported_when_file_is_missing(self, tmp_path, monkeypatch):
        repo = tmp_path / "repo"
        repo.mkdir()
        monkeypatch.setattr(larp, "ALLOWLIST", {"scripts/gone.py": {"lines": (1,), "reason": "test reason"}})
        result = larp.run([repo], repo)
        assert result["exit"] & 2
        assert not result["exit"] & 1
        assert result["allowlisted"] == []
        assert result["stale_allowlist"] == [
            "scripts/gone.py: file no longer scanned (missing, moved, or pruned) — "
            "SHRINK-ONLY: remove this ALLOWLIST entry"
        ]


class TestRealAllowlistEntries:
    """The two real entries this session added (2026-08-31, PR rescuing
    scripts/ci/queue_rearm_population.sh's positive-probe fix) actually exist
    on disk and, scanned raw (without ALLOWLIST), actually produce a finding
    — i.e. neither entry is dead weight from the day it was written.

    Deliberately NOT `larp.REPO_ROOT` (see `_canonical_repo_root()`'s
    worktree-hardening): that constant redirects OUT of a `.worktrees/<lane>/`
    checkout to the main one, which is correct for the lint's own CLI
    default but wrong here — this test must see whatever tree it is actually
    running in (this worktree, mid-PR), same technique as
    `test_marker_appears_only_in_this_lints_own_test_file_and_its_definition`
    below."""

    @staticmethod
    def _running_repo_root() -> Path:
        this_file = Path(__file__).resolve()
        top = subprocess.run(
            ["git", "-C", str(this_file.parent), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=20,
        )
        assert top.returncode == 0, f"git rev-parse failed: {top.stderr}"
        return Path(top.stdout.strip())

    def test_both_real_allowlist_entries_exist_on_disk(self):
        repo_root = self._running_repo_root()
        for relpath in larp.ALLOWLIST:
            assert (repo_root / relpath).exists(), f"stale ALLOWLIST entry, missing: {relpath}"

    def test_both_real_allowlist_entries_are_still_needed(self):
        repo_root = self._running_repo_root()
        for relpath, entry in larp.ALLOWLIST.items():
            text = (repo_root / relpath).read_text(encoding="utf-8", errors="replace")
            result = larp.scan_text(text, relpath)
            assert result["findings"], (
                f"{relpath} no longer matches any decision pattern — this ALLOWLIST "
                f"entry is stale, SHRINK-ONLY says remove it"
            )
            # Line-scoped (2026-08-31): the declared `lines` must be EXACTLY
            # the decision lines scan_text() finds today, not a superset
            # (would silently waive a future, different violation on an
            # undeclared line) or a subset (would leave a documented line
            # unwaived, permanently red).
            actual_lines = {ln for ln, _snippet in result["decision_lines"]}
            assert set(entry["lines"]) == actual_lines, (
                f"{relpath}: ALLOWLIST declares lines {sorted(entry['lines'])} but "
                f"scan_text() finds decision lines {sorted(actual_lines)} today — "
                f"update the entry to match"
            )


# ---------------------------------------------------------------- self-scan governance


class TestSelfScanIsClean:
    """Proves the marker mechanism described in the module docstring actually
    holds — this is the concrete answer to "make sure the lint does not flag
    its own test fixtures"."""

    def test_this_test_files_own_source_produces_no_findings_when_scanned(self):
        this_file = Path(__file__).resolve()
        text = this_file.read_text(encoding="utf-8")
        result = larp.scan_text(text, "scripts/tests/test_lint_arm_probe.py")
        assert result["findings"] == [], (
            "this lint's own test fixtures are not fully marker-suppressed: "
            f"{result['findings']}"
        )

    def test_marker_appears_only_in_this_lints_own_test_file_and_its_definition(self):
        """The suppression marker is a deliberately narrow escape hatch (see
        module docstring: content-based, not directory-based — cicatrix #3/
        W109). Exactly two tracked files may carry it: THIS test file (the
        only place it functions as a suppression) and lint_arm_probe.py
        itself (which defines the SUPPRESSION_MARKER constant and documents
        it — that file's own self-scan passes not via this marker but
        because its docstring's positive-probe mentions co-occur file-wide,
        see its module docstring). Nothing else in the tracked tree may
        carry it; if something does, it is silently exempting real decision
        code, not a fixture."""
        this_file = Path(__file__).resolve()
        top = subprocess.run(
            ["git", "-C", str(this_file.parent), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=20,
        )
        assert top.returncode == 0, f"git rev-parse failed: {top.stderr}"
        repo_root = Path(top.stdout.strip())
        this_file_rel = this_file.relative_to(repo_root).as_posix()
        lint_file_rel = "scripts/lint_arm_probe.py"

        # --untracked: this test must pass BEFORE `git add`, not only after —
        # a brand-new file (this one, on first run) is untracked by definition.
        grep = subprocess.run(
            ["git", "-C", str(repo_root), "grep", "--untracked", "-l", "-F",
             larp.SUPPRESSION_MARKER],
            capture_output=True, text=True, timeout=20,
        )
        assert grep.returncode in (0, 1), f"git grep failed: {grep.stderr}"
        hits = sorted(line.strip() for line in grep.stdout.splitlines() if line.strip())
        assert hits, "expected the suppression marker to appear at least in this test file"
        assert hits == sorted([this_file_rel, lint_file_rel]), (
            f"lint-arm-probe:fixture marker leaked outside its own defining/consuming "
            f"files: {hits}"
        )
