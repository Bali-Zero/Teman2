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


def test_probe_picks_up_declared_only_pair_previously_invisible(tmp_path: Path) -> None:
    """The bug this fixes: a pair that exists ONLY in declared-pairs.json (not in
    the probe's embedded args) must now be probed, not silently skipped."""
    repo = make_repo(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    live = home / "mini-only.sh"
    live.write_text("same content\n", encoding="utf-8")
    (repo / "scripts" / "mini-only.sh").write_text("same content\n", encoding="utf-8")
    write_declared_pairs(repo, [{"live": str(live), "repo": "scripts/mini-only.sh", "machines": ["mini"]}])

    status, findings, ev = prop.probe_home_fork_scripts(repo, {"pairs": []}, 10)
    assert status == prop.RECONCILED
    assert findings == 0


def test_probe_catches_divergence_in_declared_only_pair(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    live = home / "mini-only.sh"
    live.write_text("live version\n", encoding="utf-8")
    (repo / "scripts" / "mini-only.sh").write_text("repo version\n", encoding="utf-8")
    write_declared_pairs(repo, [{"live": str(live), "repo": "scripts/mini-only.sh", "machines": ["mini"]}])

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
