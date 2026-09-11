"""Pure unit tests for `naga_persistence`: validation order, zero-SQL-on-rejection, source scan.

No PostgreSQL here -- every test either calls `validate_object` directly (pure, no `conn`
argument at all) or drives `write_objects`/`write_successor` against `_RecordingConnection`, a
fake `asyncpg.Connection` whose every method raises `AssertionError` the instant it is called.
A rule that is supposed to reject BEFORE any INSERT proves it by never tripping that assertion.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

import pytest
from research_os.hashing import object_hash as _real_object_hash
from research_os.version import CONTRACT_VERSION

from backend.services.research_os import naga_persistence as np
from backend.services.research_os.naga_bitemporal_reader import registered_family_name

MODULE_PATH = Path(np.__file__)


class _RecordingConnection:
    """A fake `asyncpg.Connection`. Any call proves a rule failed to reject before touching SQL."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def execute(self, query: str, *args: Any) -> str:
        self.calls.append(f"execute:{query}")
        raise AssertionError(f"execute() called before rejection: {query!r}")

    async def fetchval(self, query: str, *args: Any) -> Any:
        self.calls.append(f"fetchval:{query}")
        raise AssertionError(f"fetchval() called before rejection: {query!r}")

    async def fetchrow(self, query: str, *args: Any) -> Any:
        self.calls.append(f"fetchrow:{query}")
        raise AssertionError(f"fetchrow() called before rejection: {query!r}")

    async def fetch(self, query: str, *args: Any) -> Any:
        self.calls.append(f"fetch:{query}")
        raise AssertionError(f"fetch() called before rejection: {query!r}")

    def transaction(self) -> Any:
        self.calls.append("transaction()")
        raise AssertionError("transaction() opened before rejection")


def _claim_payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "claim_id": str(uuid.uuid4()),
        "claim_family_id": str(uuid.uuid4()),
        "contract_version": CONTRACT_VERSION,
        "tenant": "bali-zero",
        "statement": {
            "subject_ref": {"object_kind": "regulation", "object_id": "reg-1", "object_hash": "a" * 64},
            "predicate": "naga.has-fee",
            "object_ref_or_value": 100.0,
        },
        "scope": {"domain": "tax"},
        "time": {"recorded_at": "2026-01-01T00:00:00Z"},
        "status": "supported",
        "evidence_refs": [],
        "confidence": {"score": 0.9, "method": "manual"},
        "classification": {"risk_class": "green", "sensitivity": "public"},
        "review": {"state": "unreviewed"},
        "lineage": {"run_id": str(uuid.uuid4()), "extractor": "naga.legacy", "input_claim_refs": []},
        "retention": {"retention_class": "operational", "legal_hold": False},
    }
    base.update(overrides)
    base["object_hash"] = _real_object_hash(base)
    return base


def _write(payload: dict[str, Any], *, kind: str = "claim", id_field: str = "claim_id") -> np.ObjectWrite:
    return np.ObjectWrite(object_kind=kind, object_id=payload[id_field], payload=payload)


# --------------------------------------------------------------------------------------------
# validate_object: pure, no conn argument exists to touch
# --------------------------------------------------------------------------------------------


def test_validate_object_accepts_a_hash_consistent_payload() -> None:
    assert np.validate_object(_write(_claim_payload())) is None


def test_validate_object_rejects_hash_mismatch() -> None:
    payload = _claim_payload()
    payload["scope"] = {"domain": "immigration"}  # mutate AFTER the hash was computed
    with pytest.raises(np.NagaWriteRejected) as excinfo:
        np.validate_object(_write(payload))
    assert excinfo.value.reason == "object_hash_mismatch"


@pytest.mark.parametrize(
    "spelling",
    [
        "2026-01-01t00:00:00Z",  # lowercase separator -- rule 5, literal text
        "2026-01-01T00:00:00z",  # lowercase terminator -- measured rejection, see module docstring
        "2026-01-01T00:00:00.1234567Z",  # 7 fractional digits -- rule 5, literal text
        "2026-01-01T00:00:00+07:00",  # non-UTC offset -- never admitted by the core's own pattern
        "not-an-instant",
    ],
)
def test_validate_object_rejects_malformed_write_path_instants(spelling: str) -> None:
    payload = _claim_payload(time={"recorded_at": spelling})
    with pytest.raises(np.NagaWriteRejected) as excinfo:
        np.validate_object(_write(payload))
    assert excinfo.value.reason == "malformed_instant"
    assert excinfo.value.detail == "time.recorded_at"


@pytest.mark.parametrize(
    "spelling",
    [
        "2026-01-01T00:00:00Z",
        "2026-01-01T00:00:00.1Z",
        "2026-01-01T00:00:00.123456Z",
        "2026-01-01T00:00:00+00:00",
    ],
)
def test_validate_object_accepts_every_write_strict_spelling(spelling: str) -> None:
    assert np.validate_object(_write(_claim_payload(time={"recorded_at": spelling}))) is None


def test_hash_check_precedes_instant_check_deterministically() -> None:
    """A payload broken both ways always reports the hash defect first (rule order is fixed)."""

    payload = _claim_payload(time={"recorded_at": "2026-01-01t00:00:00Z"})
    payload["object_hash"] = "0" * 64  # now also hash-inconsistent
    with pytest.raises(np.NagaWriteRejected) as excinfo:
        np.validate_object(_write(payload))
    assert excinfo.value.reason == "object_hash_mismatch"


def test_validate_object_rejects_missing_object_id() -> None:
    payload = _claim_payload(claim_id="")
    with pytest.raises(np.NagaWriteRejected) as excinfo:
        np.validate_object(np.ObjectWrite(object_kind="claim", object_id="", payload=payload))
    assert excinfo.value.reason == "object_id_missing"


# --------------------------------------------------------------------------------------------
# write_objects / write_successor: zero SQL issued when validation rejects first
# --------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_write_objects_issues_no_sql_when_one_payload_is_hash_inconsistent() -> None:
    good = _write(_claim_payload())
    bad_payload = _claim_payload()
    bad_payload["object_hash"] = "0" * 64
    bad = _write(bad_payload)
    conn = _RecordingConnection()
    with pytest.raises(np.NagaWriteRejected) as excinfo:
        await np.write_objects(conn, [good, bad])
    assert excinfo.value.reason == "object_hash_mismatch"
    assert conn.calls == []


@pytest.mark.asyncio
async def test_write_objects_issues_no_sql_for_a_malformed_instant() -> None:
    bad = _write(_claim_payload(time={"recorded_at": "2026-01-01T00:00:00z"}))
    conn = _RecordingConnection()
    with pytest.raises(np.NagaWriteRejected):
        await np.write_objects(conn, [bad])
    assert conn.calls == []


@pytest.mark.asyncio
async def test_write_successor_issues_no_sql_when_successor_payload_is_hash_inconsistent() -> None:
    predecessor_id = str(uuid.uuid4())
    successor_payload = _claim_payload()
    successor_payload["object_hash"] = "0" * 64
    edge_payload = _edge_payload(predecessor_id, successor_payload["claim_id"], "family-x", "hash-a")
    conn = _RecordingConnection()
    with pytest.raises(np.NagaWriteRejected) as excinfo:
        await np.write_successor(
            conn,
            predecessor_id=predecessor_id,
            successor=_write(successor_payload),
            edge=_write(edge_payload, kind="object_successor_edge", id_field="object_successor_edge_id"),
        )
    assert excinfo.value.reason == "object_hash_mismatch"
    assert conn.calls == []


@pytest.mark.asyncio
async def test_write_successor_issues_no_sql_when_edge_refs_disagree_with_call_arguments() -> None:
    """`predecessor_id`/`successor.object_id` are checked against the edge's own refs before any
    connection use -- a caller-assembled mismatch never reaches the advisory lock or a query."""

    predecessor_id = str(uuid.uuid4())
    successor_payload = _claim_payload()
    edge_payload = _edge_payload(
        "some-other-predecessor-id", successor_payload["claim_id"], "family-x", "hash-a"
    )
    conn = _RecordingConnection()
    with pytest.raises(np.NagaWriteRejected) as excinfo:
        await np.write_successor(
            conn,
            predecessor_id=predecessor_id,
            successor=_write(successor_payload),
            edge=_write(edge_payload, kind="object_successor_edge", id_field="object_successor_edge_id"),
        )
    assert excinfo.value.reason == "edge_predecessor_ref_mismatch"
    assert conn.calls == []


def _edge_payload(
    predecessor_id: str, successor_id: str, family_id: str, predecessor_hash: str
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "object_successor_edge_id": str(uuid.uuid4()),
        "contract_version": CONTRACT_VERSION,
        "tenant": "bali-zero",
        "object_kind": "claim",
        "family_id": family_id,
        "predecessor_ref": {
            "object_kind": "claim",
            "object_id": predecessor_id,
            "object_hash": predecessor_hash,
        },
        "successor_ref": {"object_kind": "claim", "object_id": successor_id, "object_hash": "b" * 64},
        "reason_code": "naga.correction",
        "recorded_at": "2026-01-02T00:00:00Z",
        "producer": {"name": "naga.backfill", "version": "1.0.0"},
        "lineage": {"input_hashes": []},
        "retention": {"retention_class": "operational", "legal_hold": False},
    }
    base["object_hash"] = _real_object_hash(base)
    return base


# --------------------------------------------------------------------------------------------
# rule 10: this module writes ONLY research_os_objects and research_os_naga_admission
# --------------------------------------------------------------------------------------------
#
# Deliberately AST-based, not a raw source grep: a grep for "INSERT INTO|UPDATE|DELETE FROM|
# TRUNCATE|COPY" would also match this very sentence (and the module's own docstring, which
# names all five verbs in prose to describe this test). Walking the AST for the actual first
# positional argument of every `conn.execute`/`fetch`/`fetchval`/`fetchrow` call inspects only
# strings that are REAL SQL sent over the connection, never a comment or docstring.

_WRITE_STATEMENT_RE = re.compile(
    r"\b(INSERT INTO|UPDATE|DELETE FROM|TRUNCATE|COPY)\s+([A-Za-z_][A-Za-z0-9_.]*)", re.IGNORECASE
)
_ALLOWED_TABLES = {"research_os_objects", "research_os_naga_admission"}
_CONN_METHODS = {"execute", "fetch", "fetchval", "fetchrow"}


def _sql_string_literals() -> list[str]:
    import ast

    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    literals: list[str] = []
    for node in ast.walk(tree):
        call = node.value if isinstance(node, ast.Await) else node
        if not isinstance(call, ast.Call):
            continue
        if not (isinstance(call.func, ast.Attribute) and call.func.attr in _CONN_METHODS):
            continue
        if not call.args:
            continue
        first = call.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            literals.append(first.value)
        elif isinstance(first, ast.JoinedStr):  # an f-string SQL literal (load_subject_objects)
            literals.append(
                "".join(
                    piece.value
                    for piece in first.values
                    if isinstance(piece, ast.Constant) and isinstance(piece.value, str)
                )
            )
    return literals


def test_module_issues_at_least_one_real_sql_statement() -> None:
    assert _sql_string_literals(), "expected real SQL literals passed to conn.execute/fetch*"


def test_module_source_writes_only_the_two_authorised_tables() -> None:
    matches: list[tuple[str, str]] = []
    for sql in _sql_string_literals():
        matches.extend(_WRITE_STATEMENT_RE.findall(sql))
    assert matches, "expected at least one INSERT statement among the module's SQL literals"
    for _verb, table in matches:
        assert table in _ALLOWED_TABLES, f"unexpected write target: {table!r}"


def test_module_source_never_hashes_in_sql() -> None:
    # The literal forbidden shape (migration 279:54): a SQL-side re-hash of the payload text.
    for sql in _sql_string_literals():
        assert re.search(r"sha256\s*\(", sql, re.IGNORECASE) is None


# Keep flake8/vulture-style "unused" lints quiet for the reuse-not-duplicate import; it documents
# that this module's family-identity handling is meant to agree with the reader's, not that this
# test file calls it directly.
assert registered_family_name is not None
