"""Guard: detect inline company-roster / SA-identity literals shaped like the
ones this PR deleted from apps/backend-rag/.

WHY THIS EXISTS
----------------
This PR deleted three one-off scripts under `apps/backend-rag/` that hardcoded
company rosters (company_id/name/Drive-folder-id, ~139 rows total across the
three files) and a Google service-account identity block (project_id +
client_email + numeric client_id — the private key itself was read from env,
never committed) directly as Python literals. No existing lint caught this
shape: `lint_google_oauth_credentials.py` matches `client_secret`/refresh-token
material, not an identity-only SA block, and nothing in the repo counted
roster-sized literals.

NOT the same incident as `scripts/lint_no_inline_credential_tables.py`
(landing separately, same day, via the OSS-credentials lane): that guard
matches tuples ending in two trailing plaintext strings next to a
password/login keyword — a username/password pair. This guard matches a
large roster keyed by company identity (Drive folder id) or a bare SA
identity block. Different shapes, same family of incident, deliberately not
merged into one file so neither guard's guilt/innocence fixtures have to
reason about the other's threat model.

Detects, in a given source string:
  1. A list/set/dict literal with >=20 elements where at least one string
     literal inside it is Drive-file-id shaped (`1[A-Za-z0-9_-]{25,}`, mixing
     upper/lower/digit — see `_looks_like_drive_id` for why the shape alone
     isn't enough).
  2. A dict literal carrying BOTH `client_email` and `project_id` string keys
     (a Google service-account identity block).

This is fixture-only guilt+innocence (family #3 discipline: judge the shape,
not a substring), not a whole-repo sweep — a standing "assert the entire tree
is clean" test would couple this PR's CI to unrelated in-flight deletions on
other lanes (observed: apps/backend-rag/process_batches_2_3.py, owned by a
sibling PII lane, still present on origin/main as of this PR and a genuine,
separately-tracked positive for this exact shape). The precedent this PR
follows (`scripts/tests/test_lint_no_inline_credential_tables.py`, same day)
made the same choice for the same reason.

Never prints the offending literal or file contents — file:line and rule
name only. All fixtures below are synthetic; no real company/SA data.

Run:  python3 -m pytest scripts/tests/test_no_inline_credential_tables.py -q
"""

from __future__ import annotations

import ast
import re

DRIVE_ID_RE = re.compile(r"^1[A-Za-z0-9_-]{25,}$")
MIN_ENTRIES = 20


def find_inline_credential_tables(source: str) -> list[str]:
    """Return findings as '<rule>:<lineno>' strings; [] if the source is clean."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    findings: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.List, ast.Set)):
            if len(node.elts) >= MIN_ENTRIES and _contains_drive_id(node):
                findings.append(f"roster-literal:{node.lineno}")
        elif isinstance(node, ast.Dict):
            if len(node.keys) >= MIN_ENTRIES and _contains_drive_id(node):
                findings.append(f"roster-literal:{node.lineno}")
            if _is_sa_identity_block(node):
                findings.append(f"sa-identity-block:{node.lineno}")
    return findings


def _looks_like_drive_id(value: str) -> bool:
    """Shape check plus an entropy floor: real Drive IDs mix upper/lower/digit.

    The shape regex alone also matches things that are NOT Drive ids, e.g. a
    lowercase snake_case migration tag (`108_lkpm_receipts_import`) or an
    all-digit numeric fixture — both start with `1` and clear 26 chars by
    coincidence (both were found while validating this guard against the real
    tree). Every Drive id sampled from the deleted rosters mixed all three
    character classes; requiring that clears those false positives without
    narrowing what a real folder id looks like.
    """
    if not DRIVE_ID_RE.match(value):
        return False
    return (
        any(c.isupper() for c in value)
        and any(c.islower() for c in value)
        and any(c.isdigit() for c in value)
    )


def _contains_drive_id(node: ast.AST) -> bool:
    return any(
        isinstance(sub, ast.Constant)
        and isinstance(sub.value, str)
        and _looks_like_drive_id(sub.value)
        for sub in ast.walk(node)
    )


def _is_sa_identity_block(node: ast.Dict) -> bool:
    keys = {
        k.value
        for k in node.keys
        if isinstance(k, ast.Constant) and isinstance(k.value, str)
    }
    return {"client_email", "project_id"}.issubset(keys)


# ---------------------------------------------------------------------------
# Guilt + innocence — synthetic fixtures only, assembled here, never a real
# company name / SA field.
# ---------------------------------------------------------------------------


def test_guilt_flags_a_20_plus_roster_carrying_a_drive_id() -> None:
    fake_drive_id = "1Xy9" * 8
    rows = "\n".join(
        f'    {{"company_id": {i}, "name": "Synthetic Co {i}", "drive_id": "{fake_drive_id}"}},'
        for i in range(MIN_ENTRIES)
    )
    src = f"ROSTER = [\n{rows}\n]\n"
    findings = find_inline_credential_tables(src)
    assert any(f.startswith("roster-literal:") for f in findings)


def test_guilt_flags_a_service_account_identity_block() -> None:
    src = (
        "SA_INFO = {\n"
        '    "project_id": "synthetic-project",\n'
        '    "client_email": "synthetic@synthetic.iam.gserviceaccount.com",\n'
        '    "client_id": "000000000000000000000",\n'
        "}\n"
    )
    findings = find_inline_credential_tables(src)
    assert any(f.startswith("sa-identity-block:") for f in findings)


def test_innocence_under_20_entries_does_not_flag() -> None:
    fake_drive_id = "1Xy9" * 8
    rows = "\n".join(
        f'    {{"company_id": {i}, "drive_id": "{fake_drive_id}"}},' for i in range(5)
    )
    src = f"ROSTER = [\n{rows}\n]\n"
    assert find_inline_credential_tables(src) == []


def test_innocence_large_literal_without_a_drive_id_does_not_flag() -> None:
    rows = "\n".join(f'    "Synthetic Name {i}",' for i in range(25))
    src = f"NAMES = [\n{rows}\n]\n"
    assert find_inline_credential_tables(src) == []


def test_innocence_partial_sa_keys_does_not_flag() -> None:
    src = 'CONFIG = {"project_id": "synthetic-project", "other": 1}\n'
    assert find_inline_credential_tables(src) == []


def test_innocence_migration_tag_style_literal_does_not_flag() -> None:
    """Regression: an all-lowercase snake_case migration-number tag can start
    with `1` and clear 26 chars by coincidence (found in
    apps/backend-rag/backend/db/schema_audit.py while validating this guard).
    It must not be mistaken for a Drive id."""
    fake_tag = "108_synthetic_migration_tag_name"
    rows = "\n".join(
        f'    ({i}, "{fake_tag}"): ("synthetic_group", True),' for i in range(MIN_ENTRIES)
    )
    src = f"MIGRATION_GROUPS = {{\n{rows}\n}}\n"
    assert find_inline_credential_tables(src) == []
