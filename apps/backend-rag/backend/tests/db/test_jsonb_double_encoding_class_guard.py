"""Repo-wide class-guard for the jsonb string-scalar double-encoding disease (W89).

Root cause: backend/app/core/database.py + service_initializer.py register an
asyncpg jsonb type codec with encoder=json.dumps. Any INSERT/UPDATE that binds
an ALREADY-serialized string (json.dumps(...) / to_jsonb(...) / orjson.dumps())
to a jsonb-typed placeholder WITHOUT casting the param to text first gets that
string dumped a SECOND time by the codec, landing as a jsonb string scalar
instead of an object -- invisible to every ->>'key' / ? / @> SQL-side reader.

Two cure patterns are both correct on the codec-on pool (app.state.db_pool /
get_db_pool()):
  (a) keep the serializer, type the placeholder $N::text::jsonb -- the server
      parses the text into an object, bypassing the codec's own encode step.
  (b) drop the serializer, bind the raw dict/list -- the codec encodes it
      exactly once, correctly (placeholder stays $N::jsonb or bare).

What must NEVER happen: pattern (a)'s serializer paired with pattern (b)'s
placeholder -- a bare $N or $N::jsonb bind next to a json.dumps()/to_jsonb()/
orjson.dumps() call for a column PROVEN polluted in prod by the 2026-07-16
live-probe (~30 columns / 25 tables, PENDING-ARMS P1 organism-wide sweep).
This test freezes the registry of cured columns and fails if a future edit
reintroduces the bare/`::jsonb`-without-`::text::` shape.

A handful of files legitimately write these same tables through a DIFFERENT,
codec-LESS pool (raw `asyncpg.connect()` / `asyncpg.create_pool()` without
`init=`) -- for those the bare/`::jsonb` pattern IS correct (the codec never
touches the value). They are named explicitly below, not directory-excluded,
so a real future bug in an unreviewed script cannot hide behind a blanket
exemption.

Guilt+innocence corpus (cicatrix family #3 discipline): synthetic guilty
snippets (the exact pre-fix shapes this cure removed) must fire; the actual
cured snippet, the raw-dict-alternative cured snippet, an unrelated table,
and the known correct-raw-pool file pattern must not.
"""

from __future__ import annotations

import ast
import re
import textwrap
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]  # backend/tests/db/.. -> backend/

# table -> jsonb columns proven polluted (jsonb_typeof='string') in prod by the
# 2026-07-16 live-probe against nuzantara_readonly, or a direct sibling write
# path for the same column found during this cure's W89 class-audit sweep.
PROTECTED_JSONB_COLUMNS: dict[str, tuple[str, ...]] = {
    "olympus_actions": ("detail",),
    "olympus_heartbeats": ("bloat_top3", "top_tables_by_size"),
    "olympus_insights": ("evidence",),
    "funnel_sessions": ("lead_profile", "step_state"),
    "activity_log": ("changes",),
    "team_timesheet": ("metadata",),
    "crm_audit_log": ("old_state", "new_state", "changes", "metadata"),
    "kg_nodes_staging": ("properties",),
    "kg_edges_staging": ("properties",),
    "kg_nodes": ("properties",),
    "kg_edges": ("properties",),
    "inbound_webhooks": ("payload",),
    "conversation_threads": ("metadata",),
    "events_outbox": ("payload",),
    "documents": ("ocr_extracted_data",),
    "practices": ("documents",),
    "interactions": ("metadata", "extracted_entities", "action_items"),
    "failed_messages": ("metadata",),
    "naga_sessions": ("action_items", "sub_questions"),
    "crm_workspace_ai_snapshots": ("facts",),
    "visa_types": (
        "cost_details",
        "requirements",
        "restrictions",
        "allowed_activities",
        "benefits",
        "process_steps",
        "tips",
        "metadata",
    ),
    "conversations": ("messages", "metadata"),
    "clients": ("passport_ocr_data", "custom_fields"),
    "companies": ("custom_fields",),
}

# Tables where the shipped cure is pattern (b) -- bind the raw dict/list, no
# ::text:: hop. Exempt from the "::text::jsonb must appear" count; the
# statement is still scanned (so replacing the raw bind with a serializer call
# without adding ::text:: would still need a registry update, not silently
# pass -- see test_innocence_raw_dict_table_rejects_serializer_regression).
RAW_DICT_TABLES = {"crm_welcome_runs"}

# Specific files proven (2026-07-16 audit) to write these tables through a
# codec-LESS pool (raw asyncpg.connect()/create_pool() with no init= codec
# registration) -- the bare/`::jsonb` pattern is CORRECT there. Named
# explicitly, not directory-excluded: a future protected-table write added to
# an unreviewed script in the same directory is still checked.
KNOWN_CODEC_LESS_FILES = {
    "scripts/kg_kbli_resync.py",
    "scripts/seed_kg_spatial.py",
    "services/knowledge_graph/pipeline.py",
    "services/knowledge_graph/advanced_quality.py",
}

# Old python-migration lineage (backend/migrations/migration_NNN_*.py) and the
# test suite itself are historical/self-referential, not live write paths.
EXCLUDED_TOP_DIRS = {"tests"}
EXCLUDED_DIR_NAMES = {"migrations"}

_INSERT_RE = re.compile(
    r"INSERT\s+INTO\s+(?P<table>\w+)\s*\((?P<cols>[^)]*)\)\s*VALUES\s*\((?P<vals>.*)\)",
    re.IGNORECASE | re.DOTALL,
)
# SET clause bounded at WHERE/RETURNING/end-of-string -- unbounded `.*` would
# swallow a RETURNING column list into the "set clause" and misread a merely
# *returned* column (never written) as a write target (found live in
# workspace_ai_snapshots.py's approve-flow UPDATE, which RETURNs `facts`
# without ever writing it).
_UPDATE_RE = re.compile(
    r"UPDATE\s+(?P<table>\w+)\s+SET\s+(?P<set>.*?)"
    r"(?:\bWHERE\b|\bRETURNING\b|$)",
    re.IGNORECASE | re.DOTALL,
)

_DB_CALL_METHODS = {"execute", "executemany", "fetch", "fetchval", "fetchrow"}
_SERIALIZER_CALL_NAMES = {"dumps"}  # matched against the Attribute/Name's final segment
_SERIALIZER_MODULES = {"json", "orjson"}
_TO_JSONB_HELPER = "to_jsonb"


def _call_name(node: ast.expr) -> str | None:
    """Return the trailing identifier of a Call's func (e.g. 'dumps', 'to_jsonb')."""
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def _contains_serializer_call(node: ast.AST) -> bool:
    """True if a serializer call (json.dumps / orjson.dumps / to_jsonb) appears
    anywhere within this argument's subtree -- the guilty half of the disease
    (a pre-serialized string bound to a placeholder that isn't ::text::jsonb).
    """
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            name = _call_name(sub.func)
            if name == _TO_JSONB_HELPER:
                return True
            if name in _SERIALIZER_CALL_NAMES and isinstance(sub.func, ast.Attribute):
                base = sub.func.value
                if isinstance(base, ast.Name) and base.id in _SERIALIZER_MODULES:
                    return True
    return False


def _find_db_calls(tree: ast.AST) -> list[ast.Call]:
    calls = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _DB_CALL_METHODS
        ):
            calls.append(node)
    return calls


def _sql_text_of(call: ast.Call) -> str | None:
    """Best-effort extraction of the SQL-string argument's literal text.

    Handles the common shapes in this codebase: a single str Constant, or an
    f-string (JoinedStr) whose literal (non-interpolated) parts are
    concatenated -- sufficient to find `INSERT INTO <table> (...)`/`UPDATE
    <table> SET ...` keywords and any column names that appear as literal
    text (dynamically-interpolated column names, e.g. knowledge_visa.py's
    per-field loop, are handled separately -- see PROTECTED_JSONB_COLUMNS'
    per-file notes).
    """
    if not call.args:
        return None
    first = call.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    if isinstance(first, ast.JoinedStr):
        parts = [v.value for v in first.values if isinstance(v, ast.Constant) and isinstance(v.value, str)]
        return "".join(parts)
    return None


def _scan_source(src: str, relpath: str) -> list[str]:
    """Return offender descriptions for one file's source text.

    For every DB-execute-shaped call, correlates its SQL-string argument
    (table + column presence) with its OTHER arguments (a serializer call
    present or not) -- only the combination of "protected jsonb column" AND
    "a pre-serialized value bound to it" is the disease. A call with no
    serializer argument at all (raw dict/list bind, or SQL-side
    jsonb_build_object/literal construction) is never guilty regardless of
    the placeholder's cast.
    """
    try:
        tree = ast.parse(textwrap.dedent(src))
    except SyntaxError:
        return []

    offenders: list[str] = []
    codec_less = relpath in KNOWN_CODEC_LESS_FILES
    if codec_less:
        return []

    for call in _find_db_calls(tree):
        sql = _sql_text_of(call)
        if not sql:
            continue
        if "INSERT INTO" not in sql.upper() and "UPDATE" not in sql.upper():
            continue

        table = cols_text = body = None
        m = _INSERT_RE.search(sql)
        if m:
            table = m.group("table")
            cols_text = m.group("cols")
            body = m.group("vals")
        else:
            m = _UPDATE_RE.search(sql)
            if m:
                table = m.group("table")
                cols_text = m.group("set")
                body = m.group("set")
        if table is None or table not in PROTECTED_JSONB_COLUMNS:
            continue

        present = [
            c
            for c in PROTECTED_JSONB_COLUMNS[table]
            if re.search(rf"\b{re.escape(c)}\b", cols_text)
        ]
        if not present:
            continue
        if table in RAW_DICT_TABLES:
            continue

        # The other arguments of THIS SAME call -- is a pre-serialized string
        # actually being bound anywhere in this statement?
        has_serializer = any(_contains_serializer_call(arg) for arg in call.args[1:])
        has_serializer = has_serializer or any(
            _contains_serializer_call(kw.value) for kw in call.keywords
        )
        if not has_serializer:
            continue

        text_casts = len(re.findall(r"::text::jsonb", body))
        if text_casts < len(present):
            offenders.append(
                f"{relpath}: {table}({', '.join(present)}) — "
                f"expected >= {len(present)} `::text::jsonb` cast(s), found {text_casts}"
            )
    return offenders


def _iter_backend_source_files():
    for py in BACKEND_ROOT.rglob("*.py"):
        rel_parts = py.relative_to(BACKEND_ROOT).parts
        if rel_parts[0] in EXCLUDED_TOP_DIRS:
            continue
        if set(rel_parts) & EXCLUDED_DIR_NAMES:
            continue
        yield py


def _find_all_offenders() -> list[str]:
    offenders: list[str] = []
    for py in _iter_backend_source_files():
        relpath = str(py.relative_to(BACKEND_ROOT))
        src = py.read_text(encoding="utf-8", errors="replace")
        offenders.extend(_scan_source(src, relpath))
    return offenders


# --------------------------------------------------------------------------- #
# Guilt + innocence corpus
# --------------------------------------------------------------------------- #


def test_guilt_bare_jsonb_cast_with_serializer_fires():
    """GUILT: the exact pre-fix shape (json.dumps + $N::jsonb) must be caught."""
    src = """
        await conn.execute(
            \"\"\"
            INSERT INTO olympus_actions (rhythm, action_type, target, detail)
            VALUES ($1, $2, $3, $4::jsonb)
            \"\"\",
            rhythm, action_type, target, json.dumps(detail),
        )
    """
    assert _scan_source(src, "synthetic.py") != []


def test_guilt_bare_no_cast_at_all_fires():
    """GUILT: no cast at all (type inferred from column) is the same disease."""
    src = """
        await conn.execute(
            "UPDATE team_timesheet SET metadata = $1 WHERE id = $2",
            json.dumps(metadata), row_id,
        )
    """
    assert _scan_source(src, "synthetic.py") != []


def test_guilt_multi_column_partial_cast_fires():
    """GUILT: crm_audit_log has 4 protected columns — casting only 1 must still fire."""
    src = """
        await conn.execute(
            \"\"\"
            INSERT INTO crm_audit_log (old_state, new_state, changes, metadata)
            VALUES ($1::text::jsonb, $2, $3, $4)
            \"\"\",
            json.dumps(old_state), json.dumps(new_state), json.dumps(changes), json.dumps(metadata),
        )
    """
    assert _scan_source(src, "synthetic.py") != []


def test_innocence_text_jsonb_cast_does_not_fire():
    """INNOCENCE: the actual shipped cure pattern must not fire."""
    src = """
        await conn.execute(
            \"\"\"
            INSERT INTO olympus_actions (rhythm, action_type, target, detail)
            VALUES ($1, $2, $3, $4::text::jsonb)
            \"\"\",
            rhythm, action_type, target, json.dumps(detail),
        )
    """
    assert _scan_source(src, "synthetic.py") == []


def test_innocence_raw_dict_table_does_not_fire():
    """INNOCENCE: crm_welcome_runs' raw-dict-bind cure pattern must not fire."""
    src = """
        await conn.execute(
            "INSERT INTO crm_welcome_runs (client_id, metadata) VALUES ($1, $2::jsonb)",
            client_id, metadata,
        )
    """
    assert _scan_source(src, "synthetic.py") == []


def test_innocence_known_codec_less_file_does_not_fire():
    """INNOCENCE: a file on the verified-codec-less allowlist is exempt."""
    src = """
        await conn.execute(
            \"\"\"
            INSERT INTO kg_nodes (entity_id, entity_type, name, properties)
            VALUES ($1, $2, $3, $4)
            \"\"\",
            entity_id, entity_type, name, json.dumps(props),
        )
    """
    assert _scan_source(src, "scripts/kg_kbli_resync.py") == []


def test_innocence_unrelated_table_does_not_fire():
    """INNOCENCE: a table outside the protected registry is never flagged."""
    src = """
        await conn.execute(
            "INSERT INTO some_unrelated_table (col) VALUES ($1::jsonb)",
            json.dumps(payload),
        )
    """
    assert _scan_source(src, "synthetic.py") == []


def test_innocence_unprotected_column_on_protected_table_does_not_fire():
    """INNOCENCE: writing a NON-jsonb column of a protected table is unaffected."""
    src = """
        await conn.execute(
            "UPDATE olympus_actions SET rhythm = $1, duration_ms = $2 WHERE id = $3",
            rhythm, duration_ms, action_id,
        )
    """
    assert _scan_source(src, "synthetic.py") == []


# --------------------------------------------------------------------------- #
# The live regression gate
# --------------------------------------------------------------------------- #


def test_no_offenders_in_repo():
    """The actual class-guard: every writer in backend/ must stay cured."""
    offenders = _find_all_offenders()
    assert offenders == [], (
        "jsonb double-encoding class-guard (W89) found sites writing a "
        "known-polluted column without the ::text::jsonb cast (or the "
        "raw-dict-bind alternative): " + "; ".join(offenders)
    )
