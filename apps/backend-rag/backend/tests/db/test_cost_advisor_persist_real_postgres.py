"""Real-Postgres test for ``CostAdvisor.persist_recommendations``.

The INSERT ... SELECT used bare ``$n`` parameters in the SELECT list while
also using ``$1``/``$2``/``$3`` in ``endpoint = $1`` of the dedupe subquery.
Postgres types a SELECT-list parameter as text but the comparison deduces
varchar, so PREPARE failed with ``AmbiguousParameterError`` and the weekly job
exited 1 (observed live 2026-10-12). The unit tests mock ``conn.execute`` and
cannot see this; only a real PREPARE does, so this uses ``db_tx`` (rolled back).
``llm_cost_recommendations`` is migration ``119`` in ``migrations_v2``.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import asyncpg
import pytest

from backend.services.observability.cost_advisor import CostAdvisor, CostRecommendation

pytestmark = pytest.mark.integration


class _SingleConnectionPool:
    """Every ``acquire()`` yields the same ``db_tx`` connection."""

    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn

    def acquire(self) -> Any:
        conn = self._conn

        class _Ctx:
            async def __aenter__(self_inner) -> asyncpg.Connection:
                return conn

            async def __aexit__(self_inner, *exc: object) -> bool:
                return False

        return _Ctx()


@pytest.mark.asyncio
async def test_persist_recommendations_prepares_inserts_and_dedupes_on_real_postgres(
    db_tx: asyncpg.Connection,
) -> None:
    advisor = CostAdvisor(pg_pool=_SingleConnectionPool(db_tx), oauth_client=MagicMock())
    rec = CostRecommendation(
        endpoint="/test/persist-types",
        current_model="model-current-test",
        proposed_model="model-proposed-test",
        estimated_monthly_saving_usd=Decimal("12.345678"),
        quality_tradeoff="negligible",
        confidence="medium",
        spike_flag=True,
    )

    assert await advisor.persist_recommendations([rec]) == 1
    # Same triple within the 7-day window is skipped.
    assert await advisor.persist_recommendations([rec]) == 0
    # A different proposed_model is a new triple.
    other = replace(rec, proposed_model="model-proposed-test-2")
    assert await advisor.persist_recommendations([other]) == 1

    rows = await db_tx.fetch(
        "SELECT proposed_model, estimated_monthly_saving_usd, spike_flag, confidence "
        "FROM llm_cost_recommendations WHERE endpoint = $1 ORDER BY proposed_model",
        rec.endpoint,
    )
    assert [r["proposed_model"] for r in rows] == ["model-proposed-test", "model-proposed-test-2"]
    assert rows[0]["estimated_monthly_saving_usd"] == Decimal("12.345678")
    assert rows[0]["spike_flag"] is True
    assert rows[0]["confidence"] == "medium"
