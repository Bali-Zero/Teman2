#!/usr/bin/env python3
"""B31: is the merge label really on the PR, and which armed PRs lack it. Read-only: nothing here writes to GitHub.

    label_census.py verify --repo R --pr N [--quiet]    exit 0 valid, 1 not valid (reason printed), 2 unreadable
    label_census.py census --repo R [--json]            exit 0 none lacks it, 1 some do (listed), 2 unreadable

"Valid" is the merger's own condition, `merger.label_arm`: the label is on the PR AND the last LabeledEvent for it was made by a user whose
role is admin or maintain (B42: or write, on its own same-repo PR) AND GitHub stamped it no earlier than the head's push (B2a). Nothing is redefined here, so the read-back and the
merger cannot disagree."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import merger as mg  # noqa: E402

CENSUS_QUERY = ("query($owner: String!, $name: String!, $after: String) { repository(owner: $owner, name: $name) {"
                " pullRequests(states: OPEN, first: 50, after: $after, orderBy: {field: CREATED_AT, direction: ASC}) {"
                " pageInfo { hasNextPage endCursor } nodes { number title isDraft isCrossRepository author { __typename login } headRefOid isInMergeQueue autoMergeRequest { enabledAt }"
                " labels(first: 100) { nodes { name } } timelineItems(itemTypes: [LABELED_EVENT, UNLABELED_EVENT], last: 100) { nodes {"
                " __typename ... on LabeledEvent { createdAt label { name } actor { __typename login } } ... on UnlabeledEvent { label { name } } } } } } } }")


def verify(repo: str, number: int) -> tuple[str | None, str | None]:
    """(reason the label is not valid | None, the actor's login). Raises when GitHub cannot be read."""
    owner, name = repo.split("/")
    p = (mg.gh_graphql(mg.PR_QUERY, owner=owner, name=name, number=number).get("repository") or {}).get("pullRequest")
    if not isinstance(p, dict):
        raise mg.GraphQLError(f"#{number} is not a pull request of {repo}")
    reason, actor = mg.label_arm(repo, p)
    if reason and _unreadable(reason):
        raise mg.GraphQLError(f"the label of #{number} could not be judged: {reason}")
    return reason, actor


def _unreadable(reason: str) -> bool:
    """merger.label_postdates_head folds a read that failed (check suites, event time, head) into a reason; for the helper that is UNKNOWN, not invalid."""
    return reason.startswith((f"{mg.ARM_LABEL} event time or PR head unreadable", "check suites of "))


def open_prs(repo: str) -> list[dict]:
    owner, name = repo.split("/")
    out, after = [], None
    while True:
        page = ((mg.gh_graphql(CENSUS_QUERY, owner=owner, name=name, **({"after": after} if after else {})).get("repository") or {}).get("pullRequests"))
        if not isinstance(page, dict):
            raise mg.GraphQLError("the open pull requests could not be listed")
        out += [n for n in page.get("nodes") or [] if isinstance(n, dict)]
        info = page.get("pageInfo") or {}
        if not info.get("hasNextPage"):
            return out
        after = info.get("endCursor")


def census(repo: str, prs: list[dict] | None = None) -> list[dict]:
    """Every open, non-draft PR that is armed (auto-merge request, queue entry, or the label present) without a valid label."""
    rows = []
    for p in prs if prs is not None else open_prs(repo):
        has_label = mg.ARM_LABEL in {lb.get("name") for lb in (p.get("labels") or {}).get("nodes") or [] if isinstance(lb, dict)}
        if p.get("isDraft") or not (p.get("autoMergeRequest") or p.get("isInMergeQueue") or has_label):
            continue
        reason, actor = mg.label_arm(repo, p)
        if reason:
            rows.append({"pr": p["number"], "title": str(p.get("title") or "")[:70], "label": has_label, "armed_by": "label" if has_label else
                         "queue" if p.get("isInMergeQueue") else "auto-merge", "actor": actor, "reason": reason})
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verify")
    v.add_argument("--repo", required=True)
    v.add_argument("--pr", type=int, required=True)
    v.add_argument("--quiet", action="store_true")
    c = sub.add_parser("census")
    c.add_argument("--repo", required=True)
    c.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "verify":
            reason, actor = verify(a.repo, a.pr)
            if reason:
                print(f"LABEL_INVALID pr={a.pr}: {mg.redact(reason)}", file=sys.stderr if a.quiet else sys.stdout)
                return 1
            print(f"LABEL_OK pr={a.pr} actor={actor}")
            return 0
        rows = census(a.repo)
    except Exception as exc:  # noqa: BLE001 — a read that failed is neither valid nor invalid
        print(f"LABEL_UNREADABLE: {mg.redact(f'{type(exc).__name__}: {exc}')}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(rows, indent=1))
    else:
        for r in rows:
            print(f"#{r['pr']} [{r['armed_by']}] {r['reason']} — {r['title']}")
        print(f"CENSUS {len(rows)} armed PR(s) without a valid {mg.ARM_LABEL}")
    return 1 if rows else 0


if __name__ == "__main__":
    sys.exit(main())
