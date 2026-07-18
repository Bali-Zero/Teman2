"""Unit tests for backend/scripts/kg_staging_promotion.py (S5).

Mocks asyncpg entirely (FakeConn/FakePool, duck-typed) — no live Postgres.
Every validation rule is covered in guilt+innocence pairs:

- provenance missing → rejected(missing_provenance) / set → passes
- confidence 0.64 → rejected(low_confidence) / 0.65 → passes
- name normalization mapping (§3.4: "PT PMA" → "pt_pma")
- entity_id must equal canonical normalize_entity_id(name, type)
- exact prod match → confidence-boost UPDATE on prod, NO INSERT
- fuzzy name similarity > 0.85 → rejected(fuzzy_ambiguous_review), NEVER merged
- dangling edge endpoint → rejected(dangling_endpoint)
- edge corroboration +0.05, hard-capped at 1.0
- chunk boundary at 25 rows per transaction; daily cap 50 nodes/day
- advisory-lock busy → exit 0 with zero work done
- dry-run performs zero writes (no execute/executemany, no advisory lock)
- chunk failure rolls back (staging untouched) and the run continues
"""

from __future__ import annotations

import copy
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from backend.scripts import kg_staging_promotion as mod
from backend.scripts.kg_staging_promotion import StagingPromotionJob

NOW = datetime.now(timezone.utc)
OLD = NOW - timedelta(days=40)
RECENT = NOW - timedelta(days=5)


# ---------------------------------------------------------------------------
# Row factories
# ---------------------------------------------------------------------------


def make_staging_node(
    entity_id: str = "visa:kitas",
    name: str = "KITAS",
    entity_type: str = "kitas",
    confidence: float = 0.7,
    extraction_source: str | None = "auto_heuristic",
    status: str = "pending",
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    **over: Any,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "name": name,
        "description": f"desc {name}",
        "properties": {},
        "confidence": confidence,
        "source_chunk_ids": ["chunk-1"],
        "extraction_source": extraction_source,
        "promotion_status": status,
        "rejection_reason": None,
        "created_at": created_at or NOW,
        "updated_at": updated_at or NOW,
    }
    row.update(over)
    return row


def make_prod_node(
    entity_id: str,
    name: str,
    entity_type: str,
    confidence: float = 0.8,
) -> dict[str, Any]:
    return {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "name": name,
        "description": f"prod {name}",
        "properties": {},
        "confidence": confidence,
        "source_chunk_ids": ["chunk-prod"],
        "created_at": NOW,
        "updated_at": NOW,
    }


def make_staging_edge(
    relationship_id: str = "edge:e1",
    source: str = "visa:a",
    target: str = "visa:b",
    rel_type: str = "REQUIRES",
    confidence: float = 0.7,
    status: str = "pending",
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    **over: Any,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "relationship_id": relationship_id,
        "source_entity_id": source,
        "target_entity_id": target,
        "relationship_type": rel_type,
        "properties": {},
        "confidence": confidence,
        "source_chunk_ids": ["chunk-1"],
        "extraction_source": "auto_heuristic",
        "promotion_status": status,
        "rejection_reason": None,
        "created_at": created_at or NOW,
        "updated_at": updated_at or NOW,
    }
    row.update(over)
    return row


def make_prod_edge(
    relationship_id: str,
    source: str,
    target: str,
    rel_type: str,
    confidence: float = 0.9,
) -> dict[str, Any]:
    return {
        "relationship_id": relationship_id,
        "source_entity_id": source,
        "target_entity_id": target,
        "relationship_type": rel_type,
        "properties": {},
        "confidence": confidence,
        "source_chunk_ids": ["chunk-prod"],
        "created_at": NOW,
    }


# ---------------------------------------------------------------------------
# Fake asyncpg (duck-typed Pool/Connection/Transaction with real rollback)
# ---------------------------------------------------------------------------


def _norm(sql: str) -> str:
    return " ".join(sql.split())


def _aware(ts: datetime | None) -> datetime:
    if ts is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


class _FakeTransaction:
    def __init__(self, conn: FakeConn, readonly: bool = False) -> None:
        self._conn = conn
        self._readonly = readonly

    async def __aenter__(self) -> _FakeTransaction:
        self._conn.tx_readonly.append(self._readonly)
        self._conn._snapshot()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        if exc_type is None:
            self._conn.commits += 1
        else:
            self._conn.rollbacks += 1
            self._conn._restore()
        return False


class _Acquire:
    def __init__(self, conn: FakeConn) -> None:
        self._conn = conn

    async def __aenter__(self) -> FakeConn:
        return self._conn

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False


class FakePool:
    """Duck-typed asyncpg.Pool: always hands out the same FakeConn."""

    def __init__(self, conn: FakeConn) -> None:
        self._conn = conn

    def acquire(self) -> _Acquire:
        return _Acquire(self._conn)


class FakeConn:
    """Duck-typed asyncpg.Connection backed by in-memory dicts.

    Records every call in `self.calls` as (method, normalized_sql, args) so
    tests can assert exactly what the job asked Postgres to do. Mutations
    (execute) update the in-memory tables; transactions snapshot/restore so a
    failed chunk genuinely rolls back.
    """

    def __init__(
        self,
        *,
        prod_nodes: list[dict[str, Any]] | None = None,
        prod_edges: list[dict[str, Any]] | None = None,
        staging_nodes: list[dict[str, Any]] | None = None,
        staging_edges: list[dict[str, Any]] | None = None,
        lock_available: bool = True,
        has_updated_at: bool = True,
        poison_node_inserts: set[str] | None = None,
    ) -> None:
        self.prod_nodes = {r["entity_id"]: dict(r) for r in prod_nodes or []}
        self.prod_edges = {r["relationship_id"]: dict(r) for r in prod_edges or []}
        self.staging_nodes = {r["entity_id"]: dict(r) for r in staging_nodes or []}
        self.staging_edges = {r["relationship_id"]: dict(r) for r in staging_edges or []}
        self.lock_available = lock_available
        self.has_updated_at = has_updated_at
        self.poison_node_inserts = set(poison_node_inserts or ())
        self.calls: list[tuple[str, str, tuple[Any, ...]]] = []
        self.commits = 0
        self.rollbacks = 0
        self.tx_readonly: list[bool] = []
        self._snap: tuple[Any, Any, Any, Any] | None = None

    # -- transaction / snapshot ---------------------------------------------

    def transaction(self, readonly: bool = False) -> _FakeTransaction:
        return _FakeTransaction(self, readonly)

    def _snapshot(self) -> None:
        self._snap = (
            copy.deepcopy(self.prod_nodes),
            copy.deepcopy(self.prod_edges),
            copy.deepcopy(self.staging_nodes),
            copy.deepcopy(self.staging_edges),
        )

    def _restore(self) -> None:
        if self._snap is not None:
            (
                self.prod_nodes,
                self.prod_edges,
                self.staging_nodes,
                self.staging_edges,
            ) = self._snap

    # -- asyncpg API ----------------------------------------------------------

    def _log(self, method: str, sql: str, args: tuple[Any, ...]) -> None:
        self.calls.append((method, _norm(sql), args))

    async def fetchval(self, sql: str, *args: Any) -> Any:
        self._log("fetchval", sql, args)
        return self._route_fetchval(_norm(sql), args)

    async def fetchrow(self, sql: str, *args: Any) -> Any:
        self._log("fetchrow", sql, args)
        return self._route_fetchrow(_norm(sql), args)

    async def fetch(self, sql: str, *args: Any) -> Any:
        self._log("fetch", sql, args)
        return self._route_fetch(_norm(sql), args)

    async def execute(self, sql: str, *args: Any) -> str:
        self._log("execute", sql, args)
        return self._route_execute(_norm(sql), args)

    # -- routing ---------------------------------------------------------------

    def _table(self, name: str) -> dict[str, dict[str, Any]]:
        return {
            "kg_nodes": self.prod_nodes,
            "kg_edges": self.prod_edges,
            "kg_nodes_staging": self.staging_nodes,
            "kg_edges_staging": self.staging_edges,
        }[name]

    def _route_fetchval(self, s: str, args: tuple[Any, ...]) -> Any:
        if "pg_try_advisory_lock" in s:
            return self.lock_available
        if "pg_advisory_unlock" in s:
            return True
        if "information_schema" in s:
            return 2 if self.has_updated_at else 0
        if "date_trunc" in s:  # promoted today (UTC day)
            today = datetime.now(timezone.utc).date()
            return sum(
                1
                for r in self.staging_nodes.values()
                if r.get("promotion_status") == "promoted"
                and r.get("updated_at") is not None
                and _aware(r["updated_at"]).date() == today
            )
        if "min(created_at)" in s:
            table = "kg_edges_staging" if "kg_edges_staging" in s else "kg_nodes_staging"
            times = [
                r["created_at"]
                for r in self._table(table).values()
                if r.get("promotion_status") == "pending" and r.get("created_at")
            ]
            return min(times) if times else None
        if "interval '1 day'" in s:  # 24h growth
            table = "kg_edges_staging" if "kg_edges_staging" in s else "kg_nodes_staging"
            cutoff = datetime.now(timezone.utc) - timedelta(days=1)
            return sum(
                1
                for r in self._table(table).values()
                if r.get("created_at") and _aware(r["created_at"]) > cutoff
            )
        if "interval '30 days'" in s:  # prunable rejected rows
            table = "kg_edges_staging" if "kg_edges_staging" in s else "kg_nodes_staging"
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            return sum(
                1
                for r in self._table(table).values()
                if r.get("promotion_status") == "rejected"
                and _aware(r.get("updated_at")) < cutoff
            )
        raise AssertionError(f"FakeConn: unrouted fetchval: {s}")

    def _route_fetchrow(self, s: str, args: tuple[Any, ...]) -> Any:
        if "in_prod" in s:  # endpoint state (check BEFORE plain kg_nodes lookup)
            eid = args[0]
            staged = self.staging_nodes.get(eid)
            return {
                "in_prod": 1 if eid in self.prod_nodes else None,
                "in_pending": (
                    1 if staged and staged.get("promotion_status") == "pending" else None
                ),
            }
        if "FROM kg_nodes WHERE entity_id" in s:
            row = self.prod_nodes.get(args[0])
            return dict(row) if row else None
        if "FROM kg_edges WHERE source_entity_id" in s:
            src, tgt, rel_type = args
            for row in self.prod_edges.values():
                if (
                    row.get("source_entity_id") == src
                    and row.get("target_entity_id") == tgt
                    and row.get("relationship_type") == rel_type
                ):
                    return dict(row)
            return None
        raise AssertionError(f"FakeConn: unrouted fetchrow: {s}")

    def _route_fetch(self, s: str, args: tuple[Any, ...]) -> list[dict[str, Any]]:
        if "GROUP BY promotion_status" in s:
            table = "kg_edges_staging" if "kg_edges_staging" in s else "kg_nodes_staging"
            counts: dict[str, int] = {}
            for row in self._table(table).values():
                status = row.get("promotion_status")
                counts[status] = counts.get(status, 0) + 1
            return [{"promotion_status": k, "n": v} for k, v in counts.items()]
        if "FROM kg_nodes WHERE entity_type" in s:
            return [
                {"entity_id": r["entity_id"], "name": r["name"]}
                for r in self.prod_nodes.values()
                if r.get("entity_type") == args[0]
            ]
        if "FROM kg_nodes_staging" in s and "'pending'" in s:
            return self._page(self.staging_nodes, args, id_key="entity_id")
        if "FROM kg_edges_staging" in s and "'pending'" in s:
            return self._page(self.staging_edges, args, id_key="relationship_id")
        raise AssertionError(f"FakeConn: unrouted fetch: {s}")

    def _page(
        self, table: dict[str, dict[str, Any]], args: tuple[Any, ...], *, id_key: str
    ) -> list[dict[str, Any]]:
        cursor_ts, cursor_id, limit = args[0], str(args[1]), args[2]

        def key(row: dict[str, Any]) -> tuple[datetime, str]:
            return (_aware(row.get("created_at")), str(row[id_key]))

        rows = [r for r in table.values() if r.get("promotion_status") == "pending"]
        rows.sort(key=key)
        cursor = (_aware(cursor_ts), cursor_id)
        out = [dict(r) for r in rows if key(r) > cursor]
        return out[:limit]

    def _route_execute(self, s: str, args: tuple[Any, ...]) -> str:
        now = datetime.now(timezone.utc)
        if "INSERT INTO kg_nodes" in s:
            eid, etype, name, desc, props, conf, chunk_ids, created_at = args
            if eid in self.poison_node_inserts:
                raise RuntimeError(f"poisoned insert for {eid}")
            if eid in self.prod_nodes:
                return "INSERT 0 0"
            self.prod_nodes[eid] = {
                "entity_id": eid,
                "entity_type": etype,
                "name": name,
                "description": desc,
                "properties": props,
                "confidence": conf,
                "source_chunk_ids": chunk_ids,
                "created_at": created_at,
                "updated_at": now,
            }
            return "INSERT 0 1"
        if "UPDATE kg_nodes SET confidence" in s:
            eid, bonus, cap = args
            row = self.prod_nodes[eid]
            row["confidence"] = min(row["confidence"] + bonus, cap)
            row["updated_at"] = now
            return "UPDATE 1"
        if "UPDATE kg_nodes_staging" in s:
            eid, status, reason = args
            row = self.staging_nodes[eid]
            row["promotion_status"] = status
            row["rejection_reason"] = reason
            row["updated_at"] = now
            return "UPDATE 1"
        if "INSERT INTO kg_edges" in s:
            rid, src, tgt, rel_type, props, conf, chunk_ids, created_at = args
            if rid in self.prod_edges:
                return "INSERT 0 0"
            self.prod_edges[rid] = {
                "relationship_id": rid,
                "source_entity_id": src,
                "target_entity_id": tgt,
                "relationship_type": rel_type,
                "properties": props,
                "confidence": conf,
                "source_chunk_ids": chunk_ids,
                "created_at": created_at,
            }
            return "INSERT 0 1"
        if "UPDATE kg_edges SET confidence" in s:
            rid, bonus, cap = args
            row = self.prod_edges[rid]
            row["confidence"] = min(row["confidence"] + bonus, cap)
            return "UPDATE 1"
        if "UPDATE kg_edges_staging" in s:
            rid, status, reason = args
            row = self.staging_edges[rid]
            row["promotion_status"] = status
            row["rejection_reason"] = reason
            row["updated_at"] = now
            return "UPDATE 1"
        if "DELETE FROM kg_nodes_staging" in s or "DELETE FROM kg_edges_staging" in s:
            table = "kg_edges_staging" if "kg_edges_staging" in s else "kg_nodes_staging"
            store = self._table(table)
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            doomed = [
                key
                for key, row in store.items()
                if row.get("promotion_status") == "rejected"
                and _aware(row.get("updated_at")) < cutoff
            ]
            for key in doomed:
                del store[key]
            return f"DELETE {len(doomed)}"
        raise AssertionError(f"FakeConn: unrouted execute: {s}")

    # -- test helpers ------------------------------------------------------------

    def write_calls(self) -> list[str]:
        """Normalized SQL of every execute() that mutates data."""
        return [
            s
            for m, s, _ in self.calls
            if m in ("execute", "executemany")
            and re.search(r"\b(INSERT|UPDATE|DELETE)\b", s)
        ]


def _job(conn: FakeConn, *, apply: bool, limit: int | None = None) -> StagingPromotionJob:
    return StagingPromotionJob(FakePool(conn), apply=apply, limit=limit)


# ---------------------------------------------------------------------------
# Static gates: provenance (guilt + innocence)
# ---------------------------------------------------------------------------


def test_gate_rejects_missing_provenance() -> None:
    assert mod.gate_staged_node(make_staging_node(extraction_source=None)) == (
        "missing_provenance"
    )
    assert mod.gate_staged_node(make_staging_node(extraction_source="")) == (
        "missing_provenance"
    )


def test_gate_passes_with_provenance() -> None:
    assert mod.gate_staged_node(make_staging_node()) is None


# ---------------------------------------------------------------------------
# Static gates: confidence boundary (guilt 0.64 / innocence 0.65)
# ---------------------------------------------------------------------------


def test_gate_confidence_064_rejects() -> None:
    assert mod.gate_staged_node(make_staging_node(confidence=0.64)) == "low_confidence"


def test_gate_confidence_065_passes() -> None:
    assert mod.gate_staged_node(make_staging_node(confidence=0.65)) is None


def test_gate_confidence_none_rejects() -> None:
    assert mod.gate_staged_node(make_staging_node(confidence=None)) == "low_confidence"


# ---------------------------------------------------------------------------
# Name normalization mapping (§3.4) + entity_id canonical form
# ---------------------------------------------------------------------------


def test_normalize_name_mapping() -> None:
    assert mod.normalize_name("PT PMA") == "pt_pma"
    assert mod.normalize_name("  KITAS   Investor ") == "kitas_investor"
    assert mod.normalize_name("e-Visa  B211A") == "e_visa_b211a"
    assert mod.normalize_name("UU 6/2023") == "uu_6/2023"  # slashes untouched here


def test_gate_entity_id_must_be_canonical() -> None:
    good = make_staging_node(
        entity_id="company:pt_pma", name="PT PMA", entity_type="pt_pma"
    )
    assert mod.gate_staged_node(good) is None

    bad = make_staging_node(
        entity_id="company:PT PMA", name="PT PMA", entity_type="pt_pma"
    )
    assert mod.gate_staged_node(bad) == "entity_id_not_normalized"


# ---------------------------------------------------------------------------
# Contract constants tripwire (loosening requires a reviewed change)
# ---------------------------------------------------------------------------


def test_contract_constants() -> None:
    assert mod.ADVISORY_LOCK_ID == 770077
    assert mod.CHUNK_SIZE == 25
    assert mod.DAILY_NODE_CAP == 50
    assert mod.MIN_CONFIDENCE == 0.65
    assert mod.FUZZY_MATCH_THRESHOLD == 0.85
    assert mod.CORROBORATION_BONUS == 0.05
    assert mod.MAX_CONFIDENCE == 1.0
    assert mod.REJECTION_RETENTION_DAYS == 30


# ---------------------------------------------------------------------------
# Exact prod match → boost-not-insert
# ---------------------------------------------------------------------------


async def test_exact_prod_match_boosts_without_insert() -> None:
    conn = FakeConn(
        prod_nodes=[make_prod_node("visa:kitas", "KITAS", "kitas", confidence=0.80)],
        staging_nodes=[make_staging_node("visa:kitas", "KITAS", "kitas")],
    )
    code = await _job(conn, apply=True).run()

    assert code == 0
    writes = conn.write_calls()
    assert any("UPDATE kg_nodes SET confidence" in s for s in writes)
    assert not any("INSERT INTO kg_nodes" in s for s in writes)
    assert conn.prod_nodes["visa:kitas"]["confidence"] == pytest.approx(0.85)
    assert conn.staging_nodes["visa:kitas"]["promotion_status"] == "promoted"


async def test_exact_match_boost_capped_at_1() -> None:
    conn = FakeConn(
        prod_nodes=[make_prod_node("visa:kitas", "KITAS", "kitas", confidence=0.99)],
        staging_nodes=[make_staging_node("visa:kitas", "KITAS", "kitas")],
    )
    code = await _job(conn, apply=True).run()

    assert code == 0
    assert conn.prod_nodes["visa:kitas"]["confidence"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Fuzzy > 0.85 → rejected(fuzzy_ambiguous_review), NEVER merged
# ---------------------------------------------------------------------------


async def test_fuzzy_match_rejected_never_merged() -> None:
    conn = FakeConn(
        prod_nodes=[
            make_prod_node("visa:kitas_investor", "KITAS Investor", "kitas", 0.9),
        ],
        staging_nodes=[
            make_staging_node("visa:kitas_investor_2", "KITAS Investor 2", "kitas"),
        ],
    )
    code = await _job(conn, apply=True).run()

    assert code == 0
    row = conn.staging_nodes["visa:kitas_investor_2"]
    assert row["promotion_status"] == "rejected"
    assert row["rejection_reason"] == "fuzzy_ambiguous_review"
    writes = conn.write_calls()
    assert not any("INSERT INTO kg_nodes" in s for s in writes)
    assert not any("UPDATE kg_nodes SET" in s for s in writes)
    # prod row untouched — provenance never auto-merged
    assert conn.prod_nodes["visa:kitas_investor"]["confidence"] == pytest.approx(0.9)
    assert conn.prod_nodes["visa:kitas_investor"]["source_chunk_ids"] == ["chunk-prod"]


async def test_clearly_different_name_is_candidate_not_fuzzy() -> None:
    """Innocence pair for the fuzzy rule: a distinct name must be promoted."""
    conn = FakeConn(
        prod_nodes=[make_prod_node("visa:kitas", "KITAS", "kitas", 0.9)],
        staging_nodes=[make_staging_node("visa:kitap", "KITAP", "kitap")],
    )
    code = await _job(conn, apply=True).run()

    assert code == 0
    assert "visa:kitap" in conn.prod_nodes
    assert conn.staging_nodes["visa:kitap"]["promotion_status"] == "promoted"


# ---------------------------------------------------------------------------
# Dangling edge → rejected
# ---------------------------------------------------------------------------


async def test_dangling_edge_rejected() -> None:
    conn = FakeConn(
        staging_edges=[make_staging_edge("edge:d1", "visa:ghost_a", "visa:ghost_b")],
    )
    code = await _job(conn, apply=True).run()

    assert code == 0
    row = conn.staging_edges["edge:d1"]
    assert row["promotion_status"] == "rejected"
    assert row["rejection_reason"] == "dangling_endpoint"
    assert not any("INSERT INTO kg_edges" in s for s in conn.write_calls())


async def test_edge_with_prod_endpoints_is_not_dangling() -> None:
    conn = FakeConn(
        prod_nodes=[
            make_prod_node("visa:a", "VISA A", "kitas"),
            make_prod_node("visa:b", "VISA B", "kitas"),
        ],
        staging_edges=[make_staging_edge("edge:ok", "visa:a", "visa:b")],
    )
    code = await _job(conn, apply=True).run()

    assert code == 0
    assert conn.staging_edges["edge:ok"]["promotion_status"] == "promoted"
    assert "edge:ok" in conn.prod_edges


# ---------------------------------------------------------------------------
# Edge corroboration +0.05, capped at 1.0
# ---------------------------------------------------------------------------


def test_boosted_confidence_pure() -> None:
    assert mod.boosted_confidence(0.70) == pytest.approx(0.75)
    assert mod.boosted_confidence(0.97) == pytest.approx(1.0)
    assert mod.boosted_confidence(1.0) == pytest.approx(1.0)


async def test_duplicate_edge_corroborates_without_insert() -> None:
    conn = FakeConn(
        prod_nodes=[
            make_prod_node("visa:a", "VISA A", "kitas"),
            make_prod_node("visa:b", "VISA B", "kitas"),
        ],
        prod_edges=[make_prod_edge("edge:prod", "visa:a", "visa:b", "REQUIRES", 0.80)],
        staging_edges=[make_staging_edge("edge:new", "visa:a", "visa:b", "REQUIRES")],
    )
    job = _job(conn, apply=True)
    code = await job.run()

    assert code == 0
    writes = conn.write_calls()
    assert any("UPDATE kg_edges SET confidence" in s for s in writes)
    assert not any("INSERT INTO kg_edges" in s for s in writes)
    assert conn.prod_edges["edge:prod"]["confidence"] == pytest.approx(0.85)
    assert conn.staging_edges["edge:new"]["promotion_status"] == "promoted"
    assert job.report["corroborated"]["edges"] == 1


async def test_duplicate_edge_corroboration_capped_at_1() -> None:
    conn = FakeConn(
        prod_nodes=[
            make_prod_node("visa:a", "VISA A", "kitas"),
            make_prod_node("visa:b", "VISA B", "kitas"),
        ],
        prod_edges=[make_prod_edge("edge:prod", "visa:a", "visa:b", "REQUIRES", 0.98)],
        staging_edges=[make_staging_edge("edge:new", "visa:a", "visa:b", "REQUIRES")],
    )
    code = await _job(conn, apply=True).run()

    assert code == 0
    assert conn.prod_edges["edge:prod"]["confidence"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Chunk boundary at 25 + daily cap 50/day + --limit
# ---------------------------------------------------------------------------


def _valid_nodes(n: int) -> list[dict[str, Any]]:
    # Distinct entity_type per node → no cross-node fuzzy collisions, so these
    # tests exercise chunk/cap mechanics only (fuzzy has its own dedicated tests).
    return [
        make_staging_node(f"entity:thing_{i}", f"THING {i}", f"type_{i}")
        for i in range(n)
    ]


async def test_chunk_boundary_25_rows_per_transaction() -> None:
    conn = FakeConn(staging_nodes=_valid_nodes(30))
    job = _job(conn, apply=True)
    code = await job.run()

    assert code == 0
    assert job.report["chunks"] == 2  # 25 + 5
    assert job.report["promoted"]["nodes_inserted"] == 30
    assert len(conn.prod_nodes) == 30
    assert all(
        r["promotion_status"] == "promoted" for r in conn.staging_nodes.values()
    )


async def test_daily_cap_50_nodes() -> None:
    conn = FakeConn(staging_nodes=_valid_nodes(60))
    job = _job(conn, apply=True)
    code = await job.run()

    assert code == 0
    assert job.report["budget_nodes"] == 50
    assert job.report["promoted"]["nodes_inserted"] == 50
    remaining = [
        r for r in conn.staging_nodes.values() if r["promotion_status"] == "pending"
    ]
    assert len(remaining) == 10


async def test_limit_defers_excess_within_chunk() -> None:
    conn = FakeConn(staging_nodes=_valid_nodes(60))
    job = _job(conn, apply=True, limit=30)
    code = await job.run()

    assert code == 0
    assert job.report["budget_nodes"] == 30
    assert job.report["promoted"]["nodes_inserted"] == 30
    assert job.report["deferred_nodes"] == 20  # rest of the 2nd chunk left pending
    remaining = [
        r for r in conn.staging_nodes.values() if r["promotion_status"] == "pending"
    ]
    assert len(remaining) == 30


# ---------------------------------------------------------------------------
# Advisory lock busy → exit 0, no work
# ---------------------------------------------------------------------------


async def test_advisory_lock_busy_exits_zero_no_work() -> None:
    conn = FakeConn(staging_nodes=_valid_nodes(3), lock_available=False)
    job = _job(conn, apply=True)
    code = await job.run()

    assert code == 0
    assert len(conn.calls) == 1
    method, sql, _ = conn.calls[0]
    assert method == "fetchval"
    assert "pg_try_advisory_lock" in sql
    # zero work: nothing promoted, nothing else queried, lock never unlocked
    assert all(r["promotion_status"] == "pending" for r in conn.staging_nodes.values())
    assert not any("pg_advisory_unlock" in s for _, s, _ in conn.calls)


async def test_advisory_lock_released_after_successful_run() -> None:
    conn = FakeConn(staging_nodes=_valid_nodes(1))
    code = await _job(conn, apply=True).run()

    assert code == 0
    assert any("pg_advisory_unlock" in s for _, s, _ in conn.calls)


# ---------------------------------------------------------------------------
# Dry-run: genuinely read-only, zero writes
# ---------------------------------------------------------------------------


def _mixed_fixture() -> FakeConn:
    return FakeConn(
        prod_nodes=[
            make_prod_node("visa:kitas", "KITAS", "kitas", 0.9),
            make_prod_node("visa:kitas_investor", "KITAS Investor", "kitas", 0.9),
        ],
        staging_nodes=[
            make_staging_node("visa:kitas", "KITAS", "kitas"),  # exact → boost
            make_staging_node("visa:kitap", "KITAP", "kitap"),  # candidate → insert
            make_staging_node(  # fuzzy → reject
                "visa:kitas_investor_2", "KITAS Investor 2", "kitas"
            ),
            make_staging_node(  # low confidence → reject
                "visa:vitas", "VITAS", "vitas", confidence=0.5
            ),
        ],
        staging_edges=[
            make_staging_edge("edge:e1", "visa:kitap", "visa:kitas"),  # would insert
            make_staging_edge("edge:e2", "visa:ghost", "visa:kitas"),  # dangling
        ],
    )


async def test_dry_run_performs_zero_writes() -> None:
    conn = _mixed_fixture()
    job = _job(conn, apply=False)
    code = await job.run()

    assert code == 0
    # No INSERT/UPDATE/DELETE on kg_ tables — in fact no write calls at all.
    assert conn.write_calls() == []
    assert not any(
        m in ("execute", "executemany")
        and re.search(r"\b(INSERT|UPDATE|DELETE)\b", s)
        for m, s, _ in conn.calls
    )
    # No advisory lock in dry-run (zero explicit locks), single read-only tx.
    assert not any("pg_try_advisory_lock" in s for _, s, _ in conn.calls)
    assert conn.tx_readonly == [True]
    # Staging untouched.
    assert all(
        r["promotion_status"] == "pending" for r in conn.staging_nodes.values()
    )
    assert all(
        r["promotion_status"] == "pending" for r in conn.staging_edges.values()
    )
    # But the report shows what WOULD happen.
    assert job.report["mode"] == "dry-run"
    assert job.report["census"]["pending_nodes"] == 4
    assert job.report["validated"]["nodes"] == 4
    assert job.report["promoted"]["nodes_inserted"] == 1
    assert job.report["promoted"]["nodes_exact_match"] == 1
    assert job.report["rejected"]["reasons"]["fuzzy_ambiguous_review"] == 1
    assert job.report["rejected"]["reasons"]["low_confidence"] == 1
    assert job.report["promoted"]["edges_inserted"] == 1
    assert job.report["rejected"]["reasons"]["dangling_endpoint"] == 1


async def test_dry_run_simulates_edges_behind_would_be_promoted_nodes() -> None:
    """Edge whose endpoint is a pending candidate: dry-run must count it as an
    insert (via _would_promote), not as deferred/dangling."""
    conn = FakeConn(
        prod_nodes=[make_prod_node("visa:kitas", "KITAS", "kitas", 0.9)],
        staging_nodes=[make_staging_node("visa:kitap", "KITAP", "kitap")],
        staging_edges=[make_staging_edge("edge:e1", "visa:kitap", "visa:kitas")],
    )
    job = _job(conn, apply=False)
    code = await job.run()

    assert code == 0
    assert job.report["promoted"]["edges_inserted"] == 1
    assert job.report["deferred_edges"] == 0
    assert conn.write_calls() == []


# ---------------------------------------------------------------------------
# Full apply flow: nodes before edges; deferred edges; reasons in report
# ---------------------------------------------------------------------------


async def test_apply_full_flow_nodes_before_edges() -> None:
    conn = FakeConn(
        prod_nodes=[make_prod_node("visa:kitas", "KITAS", "kitas", 0.9)],
        staging_nodes=[make_staging_node("visa:kitap", "KITAP", "kitap")],
        staging_edges=[make_staging_edge("edge:e1", "visa:kitap", "visa:kitas")],
    )
    job = _job(conn, apply=True)
    code = await job.run()

    assert code == 0
    # Node promoted first, then the edge could be inserted against prod state.
    assert "visa:kitap" in conn.prod_nodes
    assert "edge:e1" in conn.prod_edges
    assert conn.staging_nodes["visa:kitap"]["promotion_status"] == "promoted"
    assert conn.staging_edges["edge:e1"]["promotion_status"] == "promoted"
    assert job.report["promoted"]["nodes_inserted"] == 1
    assert job.report["promoted"]["edges_inserted"] == 1
    # INSERT of the node appears before INSERT of the edge in the write stream.
    writes = conn.write_calls()
    node_insert = next(i for i, s in enumerate(writes) if "INSERT INTO kg_nodes" in s)
    edge_insert = next(i for i, s in enumerate(writes) if "INSERT INTO kg_edges" in s)
    assert node_insert < edge_insert
    # Lock released at the end.
    assert any("pg_advisory_unlock" in s for _, s, _ in conn.calls)


async def test_edge_defers_when_endpoint_still_quarantined() -> None:
    conn = FakeConn(
        staging_nodes=[
            make_staging_node("visa:kitas_alpha", "KITAS Alpha", "kitas"),
            make_staging_node("visa:kitas_beta", "KITAS Beta", "kitas"),
        ],
        staging_edges=[
            make_staging_edge("edge:e1", "visa:kitas_alpha", "visa:kitas_beta")
        ],
    )
    job = _job(conn, apply=True, limit=1)
    code = await job.run()

    assert code == 0
    # Only alpha fits the budget; beta stays pending, so the edge defers.
    assert conn.staging_nodes["visa:kitas_alpha"]["promotion_status"] == "promoted"
    assert conn.staging_nodes["visa:kitas_beta"]["promotion_status"] == "pending"
    assert conn.staging_edges["edge:e1"]["promotion_status"] == "pending"
    assert job.report["deferred_nodes"] == 1
    assert job.report["deferred_edges"] == 1
    assert "edge:e1" not in conn.prod_edges


async def test_edge_rejected_when_endpoint_rejected_in_node_phase() -> None:
    """Endpoint fails the node gates (low confidence) → it will never reach
    prod → its edges are dangling, not deferred."""
    conn = FakeConn(
        prod_nodes=[make_prod_node("visa:kitas", "KITAS", "kitas", 0.9)],
        staging_nodes=[
            make_staging_node("visa:kitap", "KITAP", "kitap", confidence=0.4),
        ],
        staging_edges=[make_staging_edge("edge:e1", "visa:kitap", "visa:kitas")],
    )
    job = _job(conn, apply=True)
    code = await job.run()

    assert code == 0
    assert conn.staging_nodes["visa:kitap"]["promotion_status"] == "rejected"
    assert conn.staging_edges["edge:e1"]["promotion_status"] == "rejected"
    assert conn.staging_edges["edge:e1"]["rejection_reason"] == "dangling_endpoint"


# ---------------------------------------------------------------------------
# Chunk failure: rolls back, staging untouched, run continues
# ---------------------------------------------------------------------------


async def test_chunk_failure_rolls_back_and_run_continues() -> None:
    # Poison lands in chunk 1 (25 rows): that chunk raises, rolls back, its rows
    # stay pending and out of prod; the run continues and chunk 2 (5 rows) commits.
    conn = FakeConn(staging_nodes=_valid_nodes(30), poison_node_inserts={"entity:thing_3"})
    job = _job(conn, apply=True)
    code = await job.run()

    assert code == 0
    assert job.report["failures"] == 1
    assert job.report["chunks"] == 1  # only the 2nd chunk committed
    assert conn.rollbacks == 1
    promoted = {
        eid for eid, r in conn.staging_nodes.items() if r["promotion_status"] == "promoted"
    }
    pending = {
        eid for eid, r in conn.staging_nodes.items() if r["promotion_status"] == "pending"
    }
    assert len(promoted) == 5  # chunk 2
    assert len(pending) == 25  # chunk 1 rolled back, staging untouched
    assert "entity:thing_3" in pending
    assert pending.isdisjoint(conn.prod_nodes)
    assert promoted <= set(conn.prod_nodes)
    # Report only counts committed work (no rolled-back phantom promotions).
    assert job.report["promoted"]["nodes_inserted"] == 5


# ---------------------------------------------------------------------------
# Retention: prune rejected > 30d by updated_at (apply only)
# ---------------------------------------------------------------------------


async def test_retention_prunes_rejected_older_than_30d() -> None:
    conn = FakeConn(
        staging_nodes=[
            make_staging_node(
                "visa:old", "KITAS OLD", "kitas", status="rejected", updated_at=OLD
            ),
            make_staging_node(
                "visa:new", "KITAS NEW", "kitas", status="rejected", updated_at=RECENT
            ),
            make_staging_node("visa:pending", "KITAS PEND", "kitas", updated_at=OLD),
        ],
        staging_edges=[
            make_staging_edge(
                "edge:old", "visa:a", "visa:b", status="rejected", updated_at=OLD
            ),
        ],
    )
    job = _job(conn, apply=True)
    code = await job.run()

    assert code == 0
    assert "visa:old" not in conn.staging_nodes  # pruned
    assert "edge:old" not in conn.staging_edges  # pruned
    assert "visa:new" in conn.staging_nodes  # rejected but fresh → kept
    assert "visa:pending" in conn.staging_nodes  # pending rows never pruned
    assert job.report["pruned"] == {"nodes": 1, "edges": 1}


async def test_retention_skipped_when_updated_at_missing() -> None:
    conn = FakeConn(
        staging_nodes=[
            make_staging_node(
                "visa:old", "KITAS OLD", "kitas", status="rejected", updated_at=OLD
            ),
        ],
        has_updated_at=False,
    )
    job = _job(conn, apply=True)
    code = await job.run()

    assert code == 0
    assert "visa:old" in conn.staging_nodes  # nothing pruned pre-247
    assert job.report["pruned"] == {"nodes": 0, "edges": 0}
    assert "retention_skipped_no_updated_at" in job.report["alerts"]
    assert not any("DELETE FROM" in s for s in conn.write_calls())


# ---------------------------------------------------------------------------
# CLI parsing
# ---------------------------------------------------------------------------


def test_parse_args_defaults_to_dry_run() -> None:
    args = mod.parse_args([])
    assert args.apply is False
    assert args.limit is None


def test_parse_args_apply_and_limit() -> None:
    args = mod.parse_args(["--apply", "--limit", "10"])
    assert args.apply is True
    assert args.limit == 10


def test_parse_args_rejects_conflicting_modes() -> None:
    with pytest.raises(SystemExit):
        mod.parse_args(["--apply", "--dry-run"])
