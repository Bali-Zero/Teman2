"""B31: the label read-back and the pre-flip census. GitHub is faked; nothing here writes to it."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from .fixture_repo import runner  # noqa: F401 — puts scripts/localci on sys.path like its siblings
from localci import label_census as lc  # noqa: E402

mg = lc.mg
PUSH, BEFORE, AFTER = "2026-10-14T10:00:00Z", "2026-10-14T09:00:00Z", "2026-10-14T11:00:00Z"
ROLES = {"boss": "admin", "maint": "maintain", "writer": "write"}


def pr(n, *, label=True, actor=("User", "boss"), at=AFTER, auto=True, draft=False, queue=False, head=None):
    ev = [{"__typename": "LabeledEvent", "createdAt": at, "label": {"name": mg.ARM_LABEL}, "actor": {"__typename": actor[0], "login": actor[1]}}] if label else []
    return {"number": n, "title": f"pr {n}", "isDraft": draft, "headRefOid": head or f"{n:040x}", "isInMergeQueue": queue,
            "autoMergeRequest": {"enabledAt": "x"} if auto else None, "labels": {"nodes": [{"name": mg.ARM_LABEL}] if label else []},
            "timelineItems": {"nodes": ev}}


@pytest.fixture(autouse=True)
def github(monkeypatch):
    def get(path):
        if (m := re.fullmatch(r"repos/[^/]+/[^/]+/collaborators/([^/]+)/permission", path)):
            return {"role_name": ROLES.get(m[1], "read")}
        if re.fullmatch(r"repos/[^/]+/[^/]+/commits/[0-9a-f]{40}/check-suites\?per_page=100", path):
            return {"total_count": 1, "check_suites": [{"created_at": PUSH}]}
        raise AssertionError(f"unexpected read {path}")
    monkeypatch.setattr(mg.hc, "gh_get", get)


def test_a_label_by_a_privileged_user_after_the_push_is_valid():
    assert mg.label_arm("o/r", pr(1)) == (None, "boss")
    assert mg.label_arm("o/r", pr(2, actor=("User", "maint")))[0] is None


@pytest.mark.parametrize("kw, why", [
    ({"label": False}, "absent"),
    ({"actor": ("User", "writer")}, "not admin or maintain"),
    ({"actor": ("Bot", "github-actions")}, "not applied last by a user account"),
    ({"at": BEFORE}, "predates the head"),
])
def test_the_census_names_every_armed_pr_without_a_valid_label_and_why(kw, why):
    rows = lc.census("o/r", [pr(7, **kw)])
    assert [r["pr"] for r in rows] == [7] and why in rows[0]["reason"]


def test_the_census_leaves_out_what_is_valid_unarmed_or_draft():
    rows = lc.census("o/r", [pr(1), pr(2, label=False, auto=False), pr(3, label=False, draft=True), pr(4, queue=True), pr(5, label=False, queue=True),
                             pr(6, at=BEFORE, auto=False), pr(8, label=False)])
    assert {r["pr"]: r["armed_by"] for r in rows} == {5: "queue", 6: "label", 8: "auto-merge"}


def test_the_census_reads_every_page(monkeypatch):
    pages = [{"pageInfo": {"hasNextPage": True, "endCursor": "c1"}, "nodes": [pr(1, label=False)]},
             {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": [pr(2, label=False)]}]
    seen = []
    monkeypatch.setattr(mg, "gh_graphql", lambda q, **v: seen.append(v.get("after")) or {"repository": {"pullRequests": pages[len(seen) - 1]}})
    assert [p["number"] for p in lc.open_prs("o/r")] == [1, 2] and seen == [None, "c1"]


def _graphql(monkeypatch, node):
    monkeypatch.setattr(mg, "gh_graphql", lambda q, **v: {"repository": {"pullRequest": node, "pullRequests": {"pageInfo": {"hasNextPage": False}, "nodes": [node] if node else []}}})


def test_verify_exit_codes_valid_invalid_unreadable(monkeypatch, capsys):
    _graphql(monkeypatch, pr(1))
    assert lc.main(["verify", "--repo", "o/r", "--pr", "1"]) == 0 and "LABEL_OK pr=1 actor=boss" in capsys.readouterr().out
    _graphql(monkeypatch, pr(1, at=BEFORE))
    assert lc.main(["verify", "--repo", "o/r", "--pr", "1"]) == 1 and "LABEL_INVALID pr=1" in capsys.readouterr().out
    monkeypatch.setattr(mg, "gh_graphql", lambda q, **v: (_ for _ in ()).throw(mg.GraphQLError("502")))
    assert lc.main(["verify", "--repo", "o/r", "--pr", "1"]) == 2 and "LABEL_UNREADABLE" in capsys.readouterr().err


def test_a_read_failure_inside_the_census_is_exit_2_not_a_clean_list(monkeypatch, capsys):
    monkeypatch.setattr(mg, "gh_graphql", lambda q, **v: (_ for _ in ()).throw(mg.GraphQLError("502")))
    assert lc.main(["census", "--repo", "o/r"]) == 2 and "LABEL_UNREADABLE" in capsys.readouterr().err


def test_census_exit_code_and_json(monkeypatch, capsys):
    _graphql(monkeypatch, pr(9, label=False))
    assert lc.main(["census", "--repo", "o/r", "--json"]) == 1
    assert json.loads(capsys.readouterr().out)[0]["pr"] == 9
    _graphql(monkeypatch, pr(9))
    assert lc.main(["census", "--repo", "o/r"]) == 0


def test_no_caller_swallows_the_helpers_exit():
    """B31 L2: `signal_merge_intent.sh ... || true` (or a discarded status) is how 31 of 49 PRs lost their label unseen."""
    root = Path(__file__).resolve().parents[3]
    swallowed = []
    for path in [*(root / "scripts").glob("*.sh"), *(root / "scripts" / "ci").glob("*.sh"), *(root / "scripts").glob("*.py"), *(root / "apps" / "bali-intel-scraper" / "scripts").glob("*.py")]:
        for i, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
            if "signal_merge_intent.sh" in line and not line.lstrip().startswith("#") and re.search(r"\|\|\s*(true|:)\b", line):
                swallowed.append(f"{path.relative_to(root)}:{i}")
    assert not swallowed, swallowed
