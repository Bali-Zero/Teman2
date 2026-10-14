"""The required set after the phase F flip: classic protection is deleted, so the BASE matrix is the source, and only then."""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
LOCALCI = HERE.parent
_spec = importlib.util.spec_from_file_location("hosted_compare_required_set", LOCALCI / "hosted_compare.py")
hc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hc)
_fspec = importlib.util.spec_from_file_location("phase_e_flip_required_set", LOCALCI / "phase_e_flip.py")
flip = importlib.util.module_from_spec(_fspec)
sys.modules[_fspec.name] = flip
_fspec.loader.exec_module(flip)

REPO, BRANCH = "o/r", "main"
SHA = "0123456789abcdef0123456789abcdef01234567"
PROTECTION_CHECKS = json.loads((HERE / "fixtures" / "protection_required_checks_2026-10-14.json").read_text())   # gh api GET, read once
NOT_PROTECTED = hc.GhError("gh api failed (rc=1): Branch not protected (HTTP 404)", "gh: Branch not protected (HTTP 404)")
MATRIX_TEXT = (LOCALCI / "contexts_matrix.yaml").read_text()
BASE = "b" * 40


def flipped_ruleset(**over):
    rs = {"id": 7, "name": flip.RULESET, "source_type": "Repository", "target": "branch", "enforcement": "active",
          "conditions": {"ref_name": {"include": [f"refs/heads/{BRANCH}"], "exclude": []}},
          "rules": json.loads(json.dumps(flip.TARGET_RULES)), "bypass_actors": json.loads(json.dumps(flip.TARGET_BYPASS))}
    rs.update(over)
    return rs


class Gh:
    """A recorded GitHub: the answers per path prefix; an exception is raised, anything else returned. Records every path asked."""

    def __init__(self, protection, ruleset="flipped", listing=None):
        rs = flipped_ruleset() if ruleset == "flipped" else ruleset
        self.paths: list[str] = []
        self.answers = {f"repos/{REPO}/branches/{BRANCH}/protection/required_status_checks": protection,
                        f"repos/{REPO}/rulesets?": listing if listing is not None else ([] if rs is None else [{"id": 7, "name": flip.RULESET, "source_type": "Repository"}]),
                        f"repos/{REPO}/rulesets/7": rs, f"repos/{REPO}": {"default_branch": BRANCH},
                        }

    def __call__(self, path):
        self.paths.append(path)
        for prefix in sorted(self.answers, key=len, reverse=True):
            if path.startswith(prefix):
                got = self.answers[prefix]
                if isinstance(got, Exception):
                    raise got
                return got
        raise AssertionError(f"unexpected read {path}")


def reader(text=MATRIX_TEXT, calls=None):
    def read():
        if calls is not None:
            calls.append(1)
        if isinstance(text, Exception):
            raise text
        return text
    return BASE, read


def live(monkeypatch, gh, base="default"):
    monkeypatch.setattr(hc, "gh_get", gh)
    monkeypatch.setattr(hc, "_paged", lambda path, key: [])
    return hc.fetch_live(REPO, BRANCH, SHA, reader() if base == "default" else base)


def test_protection_present_the_live_list_is_used_and_the_matrix_is_never_read(monkeypatch):
    gh = Gh({"checks": PROTECTION_CHECKS})
    got = live(monkeypatch, gh)
    assert got["required_checks"] == PROTECTION_CHECKS and got["required_source"] == "protection"
    assert not any("rulesets" in p for p in gh.paths)


def test_404_with_the_flipped_ruleset_the_base_matrix_gives_the_same_14_as_protection_did(monkeypatch):
    gh = Gh(NOT_PROTECTED)
    got = live(monkeypatch, gh)
    assert got["required_source"] == "matrix_after_flip" and len(got["required_checks"]) == 14
    assert got["required_checks"] == PROTECTION_CHECKS   # names, order and the three Actions-app pins, from the BASE matrix
    assert hc.required_names(got["required_checks"]) == hc.required_names(PROTECTION_CHECKS)


def test_the_matrix_comes_from_the_decisions_own_base_ref_and_no_github_read_names_it(monkeypatch):
    gh = Gh(NOT_PROTECTED)
    asked = []
    got = live(monkeypatch, gh, (BASE, lambda: asked.append(BASE) or MATRIX_TEXT))
    assert got["required_checks"] == PROTECTION_CHECKS and asked == [BASE]
    assert not any("contents" in p or SHA in p.replace("commits", "") for p in gh.paths)


@pytest.mark.parametrize("base", [None, ("", lambda: MATRIX_TEXT), (BASE, None), "main"], ids=["none", "empty-ref", "no-reader", "bare-string"])
def test_a_call_without_a_base_ref_fails_closed_after_the_flip(monkeypatch, base):
    with pytest.raises(hc.CompareError):
        live(monkeypatch, Gh(NOT_PROTECTED), base)


def test_a_base_without_the_blob_fails_closed(monkeypatch):
    with pytest.raises(hc.CompareError):
        live(monkeypatch, Gh(NOT_PROTECTED), reader(OSError("no such blob")))


def test_protection_present_ignores_a_missing_base(monkeypatch):
    assert live(monkeypatch, Gh({"checks": PROTECTION_CHECKS}), None)["required_source"] == "protection"


def test_many_fetches_read_protection_and_the_ruleset_once_and_the_matrix_once_per_base(monkeypatch):
    gh, calls = Gh(NOT_PROTECTED), []
    monkeypatch.setattr(hc, "gh_get", gh)
    monkeypatch.setattr(hc, "_paged", lambda path, key: [])
    for _ in range(25):
        hc.fetch_live(REPO, BRANCH, SHA, reader(calls=calls))
    assert len(calls) == 1
    assert sum(p.endswith("/protection/required_status_checks") for p in gh.paths) == 1
    assert sum("rulesets" in p for p in gh.paths) == 2   # the list and the one ruleset
    other = ("c" * 40, lambda: calls.append(2) or MATRIX_TEXT)
    hc.fetch_live(REPO, BRANCH, SHA, other)
    assert len(calls) == 2


def test_protection_reads_are_made_once_too(monkeypatch):
    gh = Gh({"checks": PROTECTION_CHECKS})
    monkeypatch.setattr(hc, "gh_get", gh)
    monkeypatch.setattr(hc, "_paged", lambda path, key: [])
    for _ in range(10):
        hc.fetch_live(REPO, BRANCH, SHA)
    assert len(gh.paths) == 1


def test_the_flipped_state_restated_in_hosted_compare_is_phase_e_flips(monkeypatch):
    assert hc.FLIP_RULESET == flip.RULESET and hc.FLIP_RULES == flip.TARGET_RULES and hc.FLIP_BYPASS == flip.TARGET_BYPASS
    assert hc.NOT_PROTECTED == flip.NOT_PROTECTED
    cases = [flipped_ruleset(), flipped_ruleset(enforcement="disabled"), flipped_ruleset(bypass_actors=[]), flipped_ruleset(rules=[]),
             flipped_ruleset(rules=[{"type": "update", "parameters": {"update_allows_fetch_and_merge": True}}]),
             flipped_ruleset(rules=flip.TARGET_RULES + [{"type": "deletion"}]),
             flipped_ruleset(bypass_actors=[{"actor_id": 1, "actor_type": "DeployKey", "bypass_mode": "pull_request"}]),
             flipped_ruleset(conditions={"ref_name": {"include": ["~ALL"], "exclude": []}}),
             flipped_ruleset(conditions={"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}}),
             flipped_ruleset(conditions={"ref_name": {"include": ["~ALL"], "exclude": [f"refs/heads/{BRANCH}"]}}),
             flipped_ruleset(conditions={"ref_name": {"include": ["~ALL"], "exclude": ["refs/heads/m*"]}}),
             flipped_ruleset(conditions={"ref_name": {"include": ["refs/heads/other"], "exclude": []}}), flipped_ruleset(conditions={})]
    for rs in cases:
        want = flip.is_target(rs) and flip.covers(rs, BRANCH, BRANCH) and rs["target"] == "branch"
        assert hc.is_flipped_ruleset(rs, BRANCH, BRANCH) is want, rs


def wrapper_files():
    text = (LOCALCI / "localci_merger_tick.sh").read_text()
    names = [n for m in re.finditer(r"^for f in ([\w. ]+); do[^\n]*\n\s*git .*scripts/localci/\$f", text, re.M) for n in m.group(1).split()]
    assert {"merger.py", "hosted_compare.py", "contexts_matrix.yaml"} <= set(names)
    return names


def test_the_wrappers_extracted_layout_alone_serves_the_post_flip_path(tmp_path):
    code = tmp_path / "code"
    code.mkdir()
    for name in wrapper_files():
        (code / name).write_bytes((LOCALCI / name).read_bytes())
    assert "phase_e_flip.py" not in wrapper_files() and not (code / "phase_e_flip.py").exists()
    probe = tmp_path / "probe.py"
    probe.write_text(f"""
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("hc", {str(code / "hosted_compare.py")!r})
hc = importlib.util.module_from_spec(spec); spec.loader.exec_module(hc)
rs = {flipped_ruleset()!r}
def gh(path):
    if path.endswith("/protection/required_status_checks"):
        raise hc.GhError("x", "gh: Branch not protected (HTTP 404)")
    if "rulesets?" in path: return [{{"id": 7, "name": "merge-queue-main"}}]
    if path.endswith("/rulesets/7"): return rs
    return {{"default_branch": "main"}}
hc.gh_get = gh
hc._paged = lambda path, key: []
got = hc.fetch_live("o/r", "main", "a" * 40, ("b" * 40, lambda: open({str(code / "contexts_matrix.yaml")!r}).read()))
print(json.dumps([got["required_source"], got["required_checks"]]))
""")
    res = subprocess.run([sys.executable, "-I", str(probe)], capture_output=True, text=True, cwd=tmp_path)
    assert res.returncode == 0, res.stderr[-400:]
    assert json.loads(res.stdout) == ["matrix_after_flip", PROTECTION_CHECKS]


@pytest.mark.parametrize("ruleset", [
    None,
    flipped_ruleset(bypass_actors=[]),
    flipped_ruleset(bypass_actors=[{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}]),
    flipped_ruleset(rules=[{"type": "deletion"}]),
    flipped_ruleset(rules=[]),
    flipped_ruleset(enforcement="disabled"),
    flipped_ruleset(enforcement="evaluate"),
    flipped_ruleset(conditions={"ref_name": {"include": ["refs/heads/other"], "exclude": []}}),
    flipped_ruleset(target="tag"),
], ids=["absent", "no-bypass", "wrong-bypass", "no-update-rule", "no-rules", "disabled", "evaluate", "other-branch", "tag"])
def test_404_without_the_flipped_ruleset_fails_closed(monkeypatch, ruleset):
    with pytest.raises(hc.CompareError):
        live(monkeypatch, Gh(NOT_PROTECTED, ruleset=ruleset))


def test_two_rulesets_of_the_name_fail_closed(monkeypatch):
    listing = [{"id": 7, "name": flip.RULESET}, {"id": 8, "name": flip.RULESET}]
    with pytest.raises(hc.CompareError):
        live(monkeypatch, Gh(NOT_PROTECTED, listing=listing))


@pytest.mark.parametrize("err", [
    hc.GhError("gh api failed (rc=1): Not Found (HTTP 404)", "gh: Not Found (HTTP 404)"),
    hc.GhError("gh api failed (rc=1): Server Error (HTTP 502)", "gh: Server Error (HTTP 502)"),
    hc.GhError("gh api failed (rc=1): Forbidden (HTTP 403)", "gh: Branch not protected (HTTP 403)"),
    hc.CompareError("gh api returned no JSON"),
], ids=["other-404", "502", "403", "not-json"])
def test_any_other_error_fails_closed_without_looking_at_rulesets(monkeypatch, err):
    gh = Gh(err)
    with pytest.raises(hc.CompareError):
        live(monkeypatch, gh)
    assert not any("rulesets" in p for p in gh.paths)


def test_an_unreadable_ruleset_fails_closed(monkeypatch):
    with pytest.raises(hc.CompareError):
        live(monkeypatch, Gh(NOT_PROTECTED, ruleset=hc.GhError("gh api failed (rc=1): boom (HTTP 500)", "boom")))


@pytest.mark.parametrize("matrix", [
    "",
    "not: [a, matrix",
    "contexts: []\n",
    "contexts:\n  - name: a\n    required_app_id: 0\n",
], ids=["empty", "bad-yaml", "empty-set", "bad-pin"])
def test_a_matrix_that_cannot_be_read_as_a_required_set_fails_closed(monkeypatch, matrix):
    with pytest.raises(hc.CompareError):
        live(monkeypatch, Gh(NOT_PROTECTED), reader(matrix))


def test_the_journal_carries_the_source(monkeypatch):
    spec = importlib.util.spec_from_file_location("merger_required_set", LOCALCI / "merger.py")
    mg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mg)
    monkeypatch.setattr(mg.hc, "fetch_live", lambda *a: {"required_checks": [], "required_source": "matrix_after_flip", "check_runs": [], "statuses": []})
    out, got = mg.hosted_summary(REPO, BRANCH, {}, SHA, Path("/nonexistent"))
    assert out["required_source"] == "matrix_after_flip"
