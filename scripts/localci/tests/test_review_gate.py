"""B29: a changes-requested review blocks the merge once the classic protection is gone. The predicate, its place in the criterion, and B24's count of it."""
from __future__ import annotations

import pytest

from .test_liveness import NOW, REQUIRED, measure, row
from .test_merger import mg


def pull(decision=None, *states, total=None):
    return {"reviewDecision": decision, "latestOpinionatedReviews": {"totalCount": len(states) if total is None else total, "nodes": [{"state": st} for st in states]}}


@pytest.mark.parametrize("p", [pull(), pull("REVIEW_REQUIRED"), pull("APPROVED", "APPROVED"), pull(None, "DISMISSED"), pull(None, "COMMENTED", "APPROVED"),
                               pull("APPROVED", "APPROVED", "DISMISSED", "COMMENTED", "PENDING")], ids=range(6))
def test_innocence_no_review_an_approval_a_dismissal_or_a_comment_do_not_block(p):
    assert mg.review_block(p) is None


@pytest.mark.parametrize("p", [pull("CHANGES_REQUESTED"), pull(None, "CHANGES_REQUESTED"), pull("APPROVED", "APPROVED", "CHANGES_REQUESTED"),
                               pull("CHANGES_REQUESTED", "CHANGES_REQUESTED", "CHANGES_REQUESTED")], ids=range(4))
def test_guilt_a_changes_requested_review_blocks_by_the_decision_or_by_one_reviewer_alone(p):
    assert "requests changes" in mg.review_block(p)


@pytest.mark.parametrize("p", [{}, {"reviewDecision": None}, {"latestOpinionatedReviews": {"totalCount": 0, "nodes": []}}, pull(5), pull(None, total=2),
                               {"reviewDecision": None, "latestOpinionatedReviews": {"totalCount": 1, "nodes": ["x"]}}, pull(None, "MERGED"), pull(None, None),
                               {"reviewDecision": None, "latestOpinionatedReviews": {"totalCount": "0", "nodes": []}}, None, [], "x"], ids=range(12))
def test_guilt_anything_unreadable_blocks(p):
    assert "unreadable" in mg.review_block(p)


def test_the_term_is_in_the_gate_and_therefore_in_the_criterion_and_counted_by_liveness():
    assert "review_not_blocking" in mg.GATE and "review_not_blocking" in mg.CRITERION
    assert "review_not_blocking" not in mg.LIVENESS_EXCLUDED and "review_not_blocking" in REQUIRED
    assert measure([row(pr=1)])["mergeable_rows"] == 1
    assert measure([row(pr=1, false=("review_not_blocking",))])["mergeable_rows"] == 0


def test_a_row_journalled_before_the_term_existed_is_not_mergeable():
    old = row(pr=1)
    del old["criterion"]["review_not_blocking"]
    assert measure([old])["mergeable_rows"] == 0


def test_the_query_asks_for_the_decision_and_every_reviewers_latest_opinionated_review():
    assert "reviewDecision" in mg.PR_QUERY and "latestOpinionatedReviews(first: 100) { totalCount nodes { state } }" in mg.PR_QUERY
