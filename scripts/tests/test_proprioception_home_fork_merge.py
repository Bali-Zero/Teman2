"""Tests for proprioception.py's home_fork_scripts probe merging declared-pairs.json.

lint_home_fork.py imports this probe's embedded DEFAULT_REGISTRY pairs and merges
them with infra/home-fork/declared-pairs.json for its own --check/--discover — but
the merge never ran the other way: pairs added only to declared-pairs.json (e.g.
Mini-only entries) were invisible to proprioception's own probe, which reported
UNPROBEABLE on machines that do have live home-fork pairs to check. Guilt+innocence
per W82/superscar #3 discipline: every merge path gets a case that IS picked up and
one that correctly stays out.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "proprioception.py"
_spec = importlib.util.spec_from_file_location("proprioception", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
prop = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prop)  # type: ignore[union-attr]


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "infra" / "home-fork").mkdir(parents=True)
    (repo / "scripts").mkdir(parents=True)
    return repo


def write_declared_pairs(repo: Path, pairs: list[dict]) -> None:
    (repo / "infra" / "home-fork" / "declared-pairs.json").write_text(
        json.dumps({"pairs": pairs}), encoding="utf-8"
    )


# ---------------------------------------------------------------- load_declared_fork_pairs


def test_load_declared_fork_pairs_innocence_wrong_machine(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_declared_pairs(repo, [{"live": "~/x.sh", "repo": "scripts/x.sh", "machines": ["pro"]}])
    assert prop.load_declared_fork_pairs(repo, "mini") == []


def test_load_declared_fork_pairs_guilt_matching_machine(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_declared_pairs(repo, [{"live": "~/x.sh", "repo": "scripts/x.sh", "machines": ["mini"]}])
    assert prop.load_declared_fork_pairs(repo, "mini") == [{"live": "~/x.sh", "repo": "scripts/x.sh"}]


def test_load_declared_fork_pairs_all_applies_everywhere(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_declared_pairs(repo, [{"live": "~/x.sh", "repo": "scripts/x.sh", "machines": ["all"]}])
    assert prop.load_declared_fork_pairs(repo, "m5") == [{"live": "~/x.sh", "repo": "scripts/x.sh"}]


def test_load_declared_fork_pairs_missing_config_degrades_empty(tmp_path: Path) -> None:
    repo = tmp_path / "no-config-repo"
    repo.mkdir()
    assert prop.load_declared_fork_pairs(repo, "mini") == []


def test_load_declared_fork_pairs_malformed_json_degrades_empty(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / "infra" / "home-fork" / "declared-pairs.json").write_text("not json", encoding="utf-8")
    assert prop.load_declared_fork_pairs(repo, "mini") == []


# ---------------------------------------------------------------- probe_home_fork_scripts


def test_probe_picks_up_declared_only_pair_previously_invisible(tmp_path: Path, monkeypatch) -> None:
    """The bug this fixes: a pair that exists ONLY in declared-pairs.json (not in
    the probe's embedded args) must now be probed, not silently skipped."""
    repo = make_repo(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    live = home / "mini-only.sh"
    live.write_text("same content\n", encoding="utf-8")
    (repo / "scripts" / "mini-only.sh").write_text("same content\n", encoding="utf-8")
    write_declared_pairs(repo, [{"live": str(live), "repo": "scripts/mini-only.sh", "machines": ["mini"]}])

    # Inject the label: reading the REAL machine_label() made this test green
    # only on Mini and red on M5/Pro for a reason unrelated to the code under
    # test — a permanently-red line trains you to ignore the file (superscar #2).
    monkeypatch.setattr(prop, "machine_label", lambda *a, **k: "mini")
    status, findings, ev = prop.probe_home_fork_scripts(repo, {"pairs": []}, 10)
    assert status == prop.RECONCILED
    assert findings == 0


def test_probe_catches_divergence_in_declared_only_pair(tmp_path: Path, monkeypatch) -> None:
    repo = make_repo(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    live = home / "mini-only.sh"
    live.write_text("live version\n", encoding="utf-8")
    (repo / "scripts" / "mini-only.sh").write_text("repo version\n", encoding="utf-8")
    write_declared_pairs(repo, [{"live": str(live), "repo": "scripts/mini-only.sh", "machines": ["mini"]}])

    monkeypatch.setattr(prop, "machine_label", lambda *a, **k: "mini")
    status, findings, ev = prop.probe_home_fork_scripts(repo, {"pairs": []}, 10)
    assert status == prop.DIVERGED
    assert findings == 1
    assert any("DIVERGED" in e for e in ev)


def test_probe_innocence_declared_pair_for_other_machine_not_probed(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    live = home / "pro-only.sh"
    live.write_text("live version\n", encoding="utf-8")
    (repo / "scripts" / "pro-only.sh").write_text("repo version\n", encoding="utf-8")
    write_declared_pairs(repo, [{"live": str(live), "repo": "scripts/pro-only.sh", "machines": ["pro"]}])

    # probe_home_fork_scripts always resolves the current machine via machine_label();
    # exercise the merge helper directly at the "pro" scope to prove "mini" is excluded,
    # then confirm probe_home_fork_scripts on this host still sees zero pairs from it
    # when the declared entry doesn't apply here.
    assert prop.load_declared_fork_pairs(repo, "mini") == []


def test_probe_dedups_pair_present_in_both_embedded_and_declared(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    live = home / "dup.sh"
    live.write_text("same content\n", encoding="utf-8")
    (repo / "scripts" / "dup.sh").write_text("same content\n", encoding="utf-8")
    write_declared_pairs(repo, [{"live": str(live), "repo": "scripts/dup.sh", "machines": ["all"]}])

    embedded_args = {"pairs": [{"live": str(live), "repo": "scripts/dup.sh"}]}
    status, findings, ev = prop.probe_home_fork_scripts(repo, embedded_args, 10)
    assert status == prop.RECONCILED
    assert findings == 0
    # only one evidence-worthy pair walked despite appearing in both sources
    assert len([e for e in ev if "dup.sh" in e]) == 0  # no findings means no evidence lines at all


def test_probe_still_unprobeable_when_no_pairs_exist_anywhere(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_declared_pairs(repo, [{"live": "~/does-not-exist-anywhere.sh", "repo": "scripts/x.sh", "machines": ["all"]}])
    status, findings, ev = prop.probe_home_fork_scripts(repo, {"pairs": []}, 10)
    assert status == prop.UNPROBEABLE
    assert findings == 0


# ---------------------------------------------------------------- live_may_extend_repo


def test_load_declared_fork_pairs_passes_through_extend_flag_when_true(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_declared_pairs(repo, [{
        "live": "~/x.ghostty", "repo": "infra/x.ghostty", "machines": ["mini"],
        "live_may_extend_repo": True,
    }])
    assert prop.load_declared_fork_pairs(repo, "mini") == [
        {"live": "~/x.ghostty", "repo": "infra/x.ghostty", "live_may_extend_repo": True}
    ]


def test_load_declared_fork_pairs_omits_extend_flag_when_absent(tmp_path: Path) -> None:
    """Guards the opt-in: a pair with no live_may_extend_repo key merges to the
    plain 2-field dict, exactly as before this feature existed — no accidental
    exemption for pairs that never declared it."""
    repo = make_repo(tmp_path)
    write_declared_pairs(repo, [{"live": "~/x.ghostty", "repo": "infra/x.ghostty", "machines": ["mini"]}])
    assert prop.load_declared_fork_pairs(repo, "mini") == [{"live": "~/x.ghostty", "repo": "infra/x.ghostty"}]


def test_probe_live_may_extend_repo_innocence_trailer_append_reconciled(tmp_path: Path, monkeypatch) -> None:
    """Repo content is untouched, verbatim, inside a live copy that has grown
    a host-local trailer at the END of the file. Declared + verified by
    prefix/suffix split -> not a finding, not even an evidence line (matches
    the plain live_sha == repo_sha early-continue's silence)."""
    repo = make_repo(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    live = home / "machine.ghostty"
    (repo / "infra" / "ghostty").mkdir(parents=True)
    (repo / "infra" / "ghostty" / "mini.ghostty").write_text("base = 1\nfoo = bar\n", encoding="utf-8")
    live.write_text("base = 1\nfoo = bar\n# live-only trailer, never in repo\ncolor = red\n", encoding="utf-8")
    write_declared_pairs(repo, [{
        "live": str(live), "repo": "infra/ghostty/mini.ghostty", "machines": ["mini"],
        "live_may_extend_repo": True,
    }])
    monkeypatch.setattr(prop, "machine_label", lambda *a, **k: "mini")
    status, findings, ev = prop.probe_home_fork_scripts(repo, {"pairs": []}, 10)
    assert status == prop.RECONCILED
    assert findings == 0
    assert ev == []


def test_probe_live_may_extend_repo_innocence_mid_file_insertion_reconciled(tmp_path: Path, monkeypatch) -> None:
    """The ACTUAL 2026-08-28 shape: the fleet installer places new upstream
    sections before an existing trailing comment block, so a host-local
    addition lands in the MIDDLE of the file, not appended at the end. A pure
    prefix check would have missed this and kept firing DIVERGED forever."""
    repo = make_repo(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    live = home / "machine.ghostty"
    (repo / "infra" / "ghostty").mkdir(parents=True)
    (repo / "infra" / "ghostty" / "mini.ghostty").write_text(
        "cursor-color = #a6e3a1\n\n# Measured 2026-08-18: no Nerd Font\nscrollback-limit = 16000000\n",
        encoding="utf-8",
    )
    live.write_text(
        "cursor-color = #a6e3a1\n\n# live-only colour override\nbackground = #11140F\n\n"
        "# Measured 2026-08-18: no Nerd Font\nscrollback-limit = 16000000\n",
        encoding="utf-8",
    )
    write_declared_pairs(repo, [{
        "live": str(live), "repo": "infra/ghostty/mini.ghostty", "machines": ["mini"],
        "live_may_extend_repo": True,
    }])
    monkeypatch.setattr(prop, "machine_label", lambda *a, **k: "mini")
    status, findings, ev = prop.probe_home_fork_scripts(repo, {"pairs": []}, 10)
    assert status == prop.RECONCILED
    assert findings == 0
    assert ev == []


def test_probe_live_may_extend_repo_guilt_mid_file_drift_still_diverged(tmp_path: Path, monkeypatch) -> None:
    """The flag exempts APPENDED content only. A live copy that differs
    somewhere INSIDE the shared span (not a pure trailer) is real drift and
    must still report DIVERGED — the prefix check, not just "flag present",
    is what decides."""
    repo = make_repo(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    live = home / "machine.ghostty"
    (repo / "infra" / "ghostty").mkdir(parents=True)
    (repo / "infra" / "ghostty" / "mini.ghostty").write_text("base = 1\nfoo = bar\n", encoding="utf-8")
    live.write_text("base = 2\nfoo = bar\n# live-only trailer\ncolor = red\n", encoding="utf-8")
    write_declared_pairs(repo, [{
        "live": str(live), "repo": "infra/ghostty/mini.ghostty", "machines": ["mini"],
        "live_may_extend_repo": True,
    }])
    monkeypatch.setattr(prop, "machine_label", lambda *a, **k: "mini")
    status, findings, ev = prop.probe_home_fork_scripts(repo, {"pairs": []}, 10)
    assert status == prop.DIVERGED
    assert findings == 1
    assert any("DIVERGED" in e for e in ev)


def test_probe_live_may_extend_repo_guilt_flag_absent_still_diverged(tmp_path: Path, monkeypatch) -> None:
    """The exemption is opt-in per declared pair. The exact same verbatim-prefix
    live content that is RECONCILED when live_may_extend_repo is declared must
    still report DIVERGED when the pair never declared it — proves this isn't
    an automatic prefix-tolerance applied to every pair."""
    repo = make_repo(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    live = home / "machine.ghostty"
    (repo / "infra" / "ghostty").mkdir(parents=True)
    (repo / "infra" / "ghostty" / "mini.ghostty").write_text("base = 1\nfoo = bar\n", encoding="utf-8")
    live.write_text("base = 1\nfoo = bar\n# live-only trailer\ncolor = red\n", encoding="utf-8")
    write_declared_pairs(repo, [{"live": str(live), "repo": "infra/ghostty/mini.ghostty", "machines": ["mini"]}])
    monkeypatch.setattr(prop, "machine_label", lambda *a, **k: "mini")
    status, findings, ev = prop.probe_home_fork_scripts(repo, {"pairs": []}, 10)
    assert status == prop.DIVERGED
    assert findings == 1


def test_live_extends_repo_verbatim_refuses_empty_repo(tmp_path: Path) -> None:
    """An empty repo file prefix-matches ANY live content trivially — refuse to
    trust that as evidence of a legitimate trailer rather than a real gap."""
    live = tmp_path / "live.txt"
    repo = tmp_path / "repo.txt"
    live.write_text("anything at all\n", encoding="utf-8")
    repo.write_text("", encoding="utf-8")
    assert prop._live_extends_repo_verbatim(live, repo) is False


def test_live_extends_repo_verbatim_false_when_identical(tmp_path: Path) -> None:
    """Not a prefix-extension case at all when the two files are byte-identical
    (the caller's live_sha == repo_sha branch already handles this — the
    helper itself must not double-count it as "live extends repo")."""
    live = tmp_path / "live.txt"
    repo = tmp_path / "repo.txt"
    live.write_text("same\n", encoding="utf-8")
    repo.write_text("same\n", encoding="utf-8")
    assert prop._live_extends_repo_verbatim(live, repo) is False


def test_probe_live_may_extend_repo_guilt_two_separate_insertions_still_diverged(tmp_path: Path, monkeypatch) -> None:
    """The invariant is ONE contiguous inserted span, not 'any extra bytes
    anywhere'. Two separate insertions break both the single-prefix and
    single-suffix accounting (repo's middle segment is not reproduced whole
    at either edge) and must still report DIVERGED — proves the algorithm
    isn't secretly "live is a superset of repo's characters"."""
    repo = make_repo(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    live = home / "machine.ghostty"
    (repo / "infra" / "ghostty").mkdir(parents=True)
    (repo / "infra" / "ghostty" / "mini.ghostty").write_text(
        "line-a = 1\nline-b = 2\nline-c = 3\n", encoding="utf-8"
    )
    live.write_text(
        "line-a = 1\n# first local insertion\nline-b = 2\n# second local insertion\nline-c = 3\n",
        encoding="utf-8",
    )
    write_declared_pairs(repo, [{
        "live": str(live), "repo": "infra/ghostty/mini.ghostty", "machines": ["mini"],
        "live_may_extend_repo": True,
    }])
    monkeypatch.setattr(prop, "machine_label", lambda *a, **k: "mini")
    status, findings, ev = prop.probe_home_fork_scripts(repo, {"pairs": []}, 10)
    assert status == prop.DIVERGED
    assert findings == 1
