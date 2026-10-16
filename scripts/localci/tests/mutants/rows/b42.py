"""B42: a write-role author's own label is a merge order on its own PR — one rule per row, against test_author_intent.py."""
PY = "scripts/localci/merger.py"
CENSUS = "scripts/localci/label_census.py"
AI = ("scripts/localci/tests/test_author_intent.py",)

ROWS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "b42-triage-counts": (PY, 'return (role == "write" and p.get(', 'return (role in ("write", "triage") and p.get(', AI),
    "b42-any-role-counts": (PY, "        if not own_write_label(p, login, role):", '        if not own_write_label(p, login, "write"):', AI),
    "b42-write-is-an-arm-role": (PY, '("admin", "maintain")   # the two halves', '("admin", "maintain", "write")   # the two halves', AI),
    "b42-fork-counts": (PY, 'p.get("isCrossRepository") is False and isinstance(author, dict)', "isinstance(author, dict)", AI),
    "b42-unknown-fork-flag-counts": (PY, 'p.get("isCrossRepository") is False and isinstance(author, dict)', 'p.get("isCrossRepository") is not True and isinstance(author, dict)', AI),
    "b42-bot-author-counts": (PY, 'author.get("__typename") == "User"\n            and author.get("login") == login)', 'author.get("__typename") in ("User", "Bot")\n            and author.get("login") == login)', AI),
    "b42-other-authors-pr-counts": (PY, '\n            and author.get("login") == login)', "\n            and True)", AI),
    "b42-login-case-folded": (PY, 'and author.get("login") == login)', 'and str(author.get("login")).lower() == login.lower())', AI),
    "b42-label-before-head-counts": (PY, "    return label_postdates_head(repo, p.get(\"headRefOid\"), labelled_at, p.get(\"number\")), login", "    return None, login", AI),
    "b42-pr-query-drops-author": (PY, "isCrossRepository author { __typename login } baseRefName", "isCrossRepository baseRefName", AI),
    "b42-census-query-drops-author": (CENSUS, "isCrossRepository author { __typename login } headRefOid", "isCrossRepository headRefOid", AI),
    "b42-census-query-drops-fork-flag": (CENSUS, "isDraft isCrossRepository author", "isDraft author", AI),
}
