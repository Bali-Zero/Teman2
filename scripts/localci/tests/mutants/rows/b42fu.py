"""B42 follow-up: the test gaps gate-b42 found by its own mutants — one rule per row, against test_author_intent.py."""
PY = "scripts/localci/merger.py"
AI = ("scripts/localci/tests/test_author_intent.py",)
WIDE = AI + ("scripts/localci/tests/test_label_census.py", "scripts/localci/tests/test_merger_phase_f.py", "scripts/localci/tests/test_merger.py")

ROWS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "b42fu-author-any-non-bot": (PY, 'author.get("__typename") == "User"', 'author.get("__typename") != "Bot"', AI),
    "b42fu-author-mannequin-counts": (PY, 'author.get("__typename") == "User"', 'author.get("__typename") in ("User", "Mannequin", "EnterpriseUserAccount")', AI),
    "b42fu-role-casefold-strip": (PY, 'role == "write"', 'str(role).strip().lower() == "write"', AI),
    "b42fu-role-denylist": (PY, 'role == "write"', 'role not in ("read", "triage", "none", None)', AI),
    "b42fu-role-from-permission-first": (PY, 'role = perm.get("role_name") if isinstance(perm, dict) else None',
                                         'role = (perm.get("permission") or perm.get("role_name")) if isinstance(perm, dict) else None', WIDE),
    "b42fu-author-login-none-counts": (PY, 'and author.get("login") == login)', 'and author.get("login") in (login, None))', AI),
}
