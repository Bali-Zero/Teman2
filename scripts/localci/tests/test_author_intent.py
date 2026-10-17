"""B42: a write-role author's own label is a merge order on its own PR. GitHub is faked; nothing here writes to it."""
from __future__ import annotations

import pytest

from .fixture_repo import runner  # noqa: F401 — puts scripts/localci on sys.path like its siblings
from localci import label_census as lc  # noqa: E402

mg = lc.mg
PUSH, BEFORE, AFTER = "2026-10-14T10:00:00Z", "2026-10-14T09:00:00Z", "2026-10-14T11:00:00Z"
ROLES = {"boss": "admin", "maint": "maintain", "writer": "write", "Writer": "write", "triager": "triage", "reader": "read",
         "UpperW": "WRITE", "padded": "write ", "custom": "contributor"}
PERMS = {"permwrite": {"permission": "write", "role_name": "triage"}, "rolewrite": {"permission": "read", "role_name": "write"}}
OWN = "no-other-actor"


def pull(*, actor=("User", "writer"), author=OWN, at=AFTER, cross=False):
    author = ("User", actor[1]) if author == OWN else author
    return {"number": 7, "headRefOid": "7" * 40, "isCrossRepository": cross,
            "author": None if author is None else {"__typename": author[0], "login": author[1]},
            "labels": {"nodes": [{"name": mg.ARM_LABEL}]},
            "timelineItems": {"nodes": [{"__typename": "LabeledEvent", "createdAt": at, "label": {"name": mg.ARM_LABEL},
                                         "actor": {"__typename": actor[0], "login": actor[1]}}]}}


@pytest.fixture(autouse=True)
def github(monkeypatch):
    reads = []

    def get(path):
        reads.append(path)
        if path.endswith("/permission"):
            login = path.split("/")[-2]
            if login == "flaky":
                raise RuntimeError("HTTP 502")
            if login == "garbled":
                return ["not", "a", "dict"]
            return PERMS.get(login) or {"role_name": ROLES.get(login, "read")}
        return {"total_count": 1, "check_suites": [{"created_at": PUSH}]}
    monkeypatch.setattr(mg.hc, "gh_get", get)
    return reads


def test_the_author_labelling_its_own_same_repo_pr_after_the_head_counts():
    assert mg.label_arm("o/r", pull()) == (None, "writer")


def test_the_role_read_is_the_one_call_the_admin_path_already_made(github):
    mg.label_arm("o/r", pull())
    assert [p for p in github if p.endswith("/permission")] == ["repos/o/r/collaborators/writer/permission"]


@pytest.mark.parametrize("actor", [("User", "boss"), ("User", "maint")])
def test_admin_and_maintain_behave_as_before_whoever_authored(actor):
    for author in (("User", "someone-else"), None, ("Bot", "dependabot[bot]")):
        assert mg.label_arm("o/r", pull(actor=actor, author=author)) == (None, actor[1])
    assert mg.label_arm("o/r", pull(actor=actor, cross=True)) == (None, actor[1])


@pytest.mark.parametrize("kw", [
    {"author": ("User", "someone-else")},                  # a write user labelling SOMEONE ELSE's PR
    {"actor": ("User", "triager")}, {"actor": ("User", "reader")},   # triage and read roles, own PR
    {"actor": ("User", "stranger")},                       # no collaborator role at all
    {"author": ("Bot", "writer")},                         # a bot author, whatever its login says
    {"author": None},                                      # an author GitHub could not name (ghost)
    {"cross": True}, {"cross": None},                      # a fork, and an unreadable fork flag
    {"at": BEFORE},                                        # a label before the head (B2a)
    {"author": ("User", "Writer")},                        # login differs only in case: exact comparison, fail closed
    {"actor": ("User", "Writer"), "author": ("User", "writer")},
], ids=["other-pr", "triage", "read", "no-role", "bot-author", "no-author", "fork", "fork-unknown", "before-head", "case-author", "case-actor"])
def test_every_guilt_case_does_not_count(kw):
    why, _ = mg.label_arm("o/r", pull(**kw))
    assert why is not None


def test_a_bot_actor_never_counts_even_as_the_author():
    assert "not applied last by a user account" in mg.label_arm("o/r", pull(actor=("Bot", "writer"), author=("Bot", "writer")))[0]


@pytest.mark.parametrize("login", ["flaky", "garbled"])
def test_a_role_that_cannot_be_read_does_not_count(login):
    try:
        why, _ = mg.label_arm("o/r", pull(actor=("User", login)))
    except RuntimeError:
        return   # the read raised: the caller treats it as unknown, and nothing was granted
    assert why is not None


def test_a_label_before_the_head_still_names_the_postdate_rule():
    assert "predates the head" in mg.label_arm("o/r", pull(at=BEFORE))[0]


def test_the_queries_ask_for_the_author_and_the_fork_flag():
    assert "author { __typename login }" in mg.PR_QUERY and "isCrossRepository" in mg.PR_QUERY
    assert "author { __typename login }" in lc.CENSUS_QUERY and "isCrossRepository" in lc.CENSUS_QUERY


def test_the_census_lets_a_write_authors_own_label_pass_and_still_names_the_rest():
    own, other = pull(), pull(author=("User", "someone-else"))
    own.update(number=1, title="own", isDraft=False, isInMergeQueue=False, autoMergeRequest=None)
    other.update(number=2, title="other", isDraft=False, isInMergeQueue=False, autoMergeRequest=None)
    rows = lc.census("o/r", [own, other])
    assert [r["pr"] for r in rows] == [2] and "not admin or maintain" in rows[0]["reason"]


@pytest.mark.parametrize("author", [("Mannequin", "writer"), ("EnterpriseUserAccount", "writer"), ("Organization", "writer"), ("User", None)],
                         ids=["mannequin", "enterprise-user", "organization", "login-none"])
def test_only_a_user_author_with_a_login_counts(author):
    assert mg.label_arm("o/r", pull(author=author))[0] is not None


@pytest.mark.parametrize("actor", [("User", "UpperW"), ("User", "padded"), ("User", "custom")], ids=["WRITE", "write-padded", "custom-role"])
def test_the_role_is_exactly_write(actor):
    assert mg.label_arm("o/r", pull(actor=actor))[0] is not None


def test_the_role_is_read_from_role_name_and_never_from_permission():
    assert mg.label_arm("o/r", pull(actor=("User", "permwrite")))[0] is not None   # permission "write", role_name "triage"
    assert mg.label_arm("o/r", pull(actor=("User", "rolewrite"))) == (None, "rolewrite")   # permission "read", role_name "write"
