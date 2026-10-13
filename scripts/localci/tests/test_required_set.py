"""The required set after the phase F flip: classic protection is deleted, so the BASE matrix is the source, and only then."""
from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
LOCALCI = HERE.parent
_spec = importlib.util.spec_from_file_location("hosted_compare_required_set", LOCALCI / "hosted_compare.py")
hc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hc)
flip = hc._flip_module()

REPO, BRANCH = "o/r", "main"
SHA = "0123456789abcdef0123456789abcdef01234567"
PROTECTION_CHECKS = json.loads((HERE / "fixtures" / "protection_required_checks_2026-10-14.json").read_text())   # gh api GET, read once
NOT_PROTECTED = hc.GhError("gh api failed (rc=1): Branch not protected (HTTP 404)", "gh: Branch not protected (HTTP 404)")
MATRIX_DOC = {"encoding": "base64", "content": base64.b64encode((LOCALCI / "contexts_matrix.yaml").read_bytes()).decode()}


def flipped_ruleset(**over):
    rs = {"id": 7, "name": flip.RULESET, "source_type": "Repository", "target": "branch", "enforcement": "active",
          "conditions": {"ref_name": {"include": [f"refs/heads/{BRANCH}"], "exclude": []}},
          "rules": json.loads(json.dumps(flip.TARGET_RULES)), "bypass_actors": json.loads(json.dumps(flip.TARGET_BYPASS))}
    rs.update(over)
    return rs


class Gh:
    """A recorded GitHub: the answers per path prefix; an exception is raised, anything else returned. Records every path asked."""

    def __init__(self, protection, ruleset="flipped", matrix=MATRIX_DOC, listing=None):
        rs = flipped_ruleset() if ruleset == "flipped" else ruleset
        self.paths: list[str] = []
        self.answers = {f"repos/{REPO}/branches/{BRANCH}/protection/required_status_checks": protection,
                        f"repos/{REPO}/rulesets?": listing if listing is not None else ([] if rs is None else [{"id": 7, "name": flip.RULESET, "source_type": "Repository"}]),
                        f"repos/{REPO}/rulesets/7": rs, f"repos/{REPO}": {"default_branch": BRANCH},
                        f"repos/{REPO}/contents/": matrix}

    def __call__(self, path):
        self.paths.append(path)
        for prefix in sorted(self.answers, key=len, reverse=True):
            if path.startswith(prefix):
                got = self.answers[prefix]
                if isinstance(got, Exception):
                    raise got
                return got
        raise AssertionError(f"unexpected read {path}")


def live(monkeypatch, gh):
    monkeypatch.setattr(hc, "gh_get", gh)
    monkeypatch.setattr(hc, "_paged", lambda path, key: [])
    return hc.fetch_live(REPO, BRANCH, SHA)


def test_protection_present_the_live_list_is_used_and_the_matrix_is_never_read(monkeypatch):
    gh = Gh({"checks": PROTECTION_CHECKS})
    got = live(monkeypatch, gh)
    assert got["required_checks"] == PROTECTION_CHECKS and got["required_source"] == "protection"
    assert not any("contents" in p or "rulesets" in p for p in gh.paths)


def test_404_with_the_flipped_ruleset_the_base_matrix_gives_the_same_14_as_protection_did(monkeypatch):
    gh = Gh(NOT_PROTECTED)
    got = live(monkeypatch, gh)
    assert got["required_source"] == "matrix_after_flip" and len(got["required_checks"]) == 14
    assert got["required_checks"] == PROTECTION_CHECKS   # names, order and the three Actions-app pins, from the BASE matrix
    assert hc.required_names(got["required_checks"]) == hc.required_names(PROTECTION_CHECKS)


def test_the_matrix_is_read_at_the_base_branch_never_at_the_candidate_sha(monkeypatch):
    gh = Gh(NOT_PROTECTED)
    live(monkeypatch, gh)
    reads = [p for p in gh.paths if "contents" in p]
    assert reads == [f"repos/{REPO}/contents/{hc.MATRIX_PATH}?ref={BRANCH}"] and SHA not in " ".join(gh.paths)


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
    {"encoding": "none", "content": ""},
    {"encoding": "base64", "content": base64.b64encode(b"not: [a, matrix").decode()},
    {"encoding": "base64", "content": base64.b64encode(b"contexts: []\n").decode()},
    {"encoding": "base64", "content": base64.b64encode(b"contexts:\n  - name: a\n    required_app_id: 0\n").decode()},
], ids=["not-base64", "bad-yaml", "empty-set", "bad-pin"])
def test_a_matrix_that_cannot_be_read_as_a_required_set_fails_closed(monkeypatch, matrix):
    with pytest.raises(hc.CompareError):
        live(monkeypatch, Gh(NOT_PROTECTED, matrix=matrix))


def test_the_journal_carries_the_source(monkeypatch):
    spec = importlib.util.spec_from_file_location("merger_required_set", LOCALCI / "merger.py")
    mg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mg)
    monkeypatch.setattr(mg.hc, "fetch_live", lambda *a: {"required_checks": [], "required_source": "matrix_after_flip", "check_runs": [], "statuses": []})
    out, got = mg.hosted_summary(REPO, BRANCH, {}, SHA, Path("/nonexistent"))
    assert out["required_source"] == "matrix_after_flip"
