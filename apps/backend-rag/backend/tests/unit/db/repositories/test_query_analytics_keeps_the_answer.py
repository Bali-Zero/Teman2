"""`query_analytics` must keep the answer, not just assert there was one.

Measured 2026-08-11: over the window since the previous Gemini credit
top-up the table gained 304 rows, 229 of them with ``response_generated =
true``, and every one of those 229 with ``response_text`` NULL — because
the INSERT in ``log_query`` never named the column. Same in the history:
4,373 rows in March 2026 with zero answers, 1,573 in April with zero.

The cost of that is concrete rather than cosmetic. With no corpus of
answers, every evaluation of answer quality has to generate NEW paid
traffic: one night of probing burned ~500,000 IDR and left three answers
on disk to show for it.

The guard has two halves and each is tested on its own:

* the repository binds the answer into the INSERT, whole;
* every writer hands it the answer in the first place.

The second half is where this defect actually lived — ``log_query``
already accepted everything else it needed, and ``response_generated`` is
literally computed from the answer at both orchestrator call sites, so
the answer was in hand and dropped on the floor three times over.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

_ANSWER = "Untuk PT PMA, modal disetor minimum adalah IDR 2,5 miliar per KBLI per lokasi."


def _mock_pool() -> tuple[MagicMock, AsyncMock]:
    """Mock asyncpg pool whose acquire() yields a shared AsyncMock conn."""
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire.return_value = ctx
    return pool, conn


def _bound_response_text(conn: AsyncMock) -> Any:
    """Read the bound ``response_text`` by NAME, never by a hardcoded index.

    The INSERT's column list is the entity; a positional constant is a
    proxy for it that starts lying the day a column moves. Parse the
    column list out of the SQL and use its position.
    """
    call = conn.fetchrow.call_args
    sql: str = call[0][0]
    assert "INSERT INTO query_analytics" in sql, "asserting against the wrong INSERT"
    columns_block = sql.split("(", 1)[1].split(")", 1)[0]
    columns = [c.strip() for c in columns_block.replace("\n", " ").split(",") if c.strip()]
    assert "response_text" in columns, (
        f"the INSERT does not name response_text at all; columns={columns}"
    )
    # call[0][0] is the SQL, so bind $N lives at call[0][N].
    return call[0][columns.index("response_text") + 1]


class TestRepositoryBindsTheAnswer:
    @pytest.mark.asyncio
    async def test_guilt_the_answer_is_bound_into_the_insert(self) -> None:
        from backend.db.repositories.query_analytics_repository import (
            QueryAnalyticsRepository,
        )

        pool, conn = _mock_pool()
        conn.fetchrow = AsyncMock(return_value={"id": "00000000-0000-0000-0000-00000000000a"})

        await QueryAnalyticsRepository(pool).log_query(
            query_text="berapa modal PT PMA?",
            response_generated=True,
            response_text=_ANSWER,
        )

        assert _bound_response_text(conn) == _ANSWER

    @pytest.mark.asyncio
    async def test_guilt_a_long_answer_is_stored_whole(self) -> None:
        """No truncation, deliberately.

        A capped corpus measures the cap (W97). One production answer has
        been observed at 247,439 characters — that runaway IS the defect a
        corpus exists to catch, and a 4k cap would hide it behind a value
        that looks like every other row.
        """
        from backend.db.repositories.query_analytics_repository import (
            QueryAnalyticsRepository,
        )

        pool, conn = _mock_pool()
        conn.fetchrow = AsyncMock(return_value={"id": "00000000-0000-0000-0000-00000000000b"})
        runaway = "x" * 250_000

        await QueryAnalyticsRepository(pool).log_query(
            query_text="q",
            response_generated=True,
            response_text=runaway,
        )

        bound = _bound_response_text(conn)
        assert bound == runaway, f"answer stored at {len(bound or '')} chars, expected 250000"

    @pytest.mark.asyncio
    async def test_innocence_retention_off_stores_null_and_changes_nothing_else(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from backend.db.repositories import query_analytics_repository as repo_module

        monkeypatch.setenv("QUERY_ANALYTICS_STORE_RESPONSE", "0")
        pool, conn = _mock_pool()
        conn.fetchrow = AsyncMock(return_value={"id": "00000000-0000-0000-0000-00000000000c"})

        await repo_module.QueryAnalyticsRepository(pool).log_query(
            query_text="berapa modal PT PMA?",
            user_id="u@example.com",
            response_generated=True,
            response_text=_ANSWER,
        )

        assert _bound_response_text(conn) is None
        # The kill switch governs ONE column. Everything the table already
        # recorded must still arrive — including the jsonb-dict binding
        # pinned by the 2026-05-14 regression test next door.
        bound = conn.fetchrow.call_args[0]
        assert bound[1] == "berapa modal PT PMA?"
        assert bound[4] == {"user_email": "u@example.com"}
        assert bound[7] is True

    @pytest.mark.asyncio
    async def test_innocence_a_caller_that_passes_no_answer_still_writes(self) -> None:
        """Every other writer of this table keeps working untouched.

        ``response_text`` is keyword-optional; a caller that never heard of
        it must not start failing.
        """
        from backend.db.repositories.query_analytics_repository import (
            QueryAnalyticsRepository,
        )

        pool, conn = _mock_pool()
        conn.fetchrow = AsyncMock(return_value={"id": "00000000-0000-0000-0000-00000000000d"})

        query_id = await QueryAnalyticsRepository(pool).log_query(query_text="q", user_id=None)

        assert query_id == "00000000-0000-0000-0000-00000000000d"
        assert _bound_response_text(conn) is None

    def test_retention_defaults_on_and_reads_the_env_each_call(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Shipping dark would be its own scar (family #2, built-but-never-armed)."""
        from backend.db.repositories.query_analytics_repository import (
            response_retention_enabled,
        )

        monkeypatch.delenv("QUERY_ANALYTICS_STORE_RESPONSE", raising=False)
        assert response_retention_enabled() is True

        for off in ("0", "false", "FALSE", "no", "off", " off "):
            monkeypatch.setenv("QUERY_ANALYTICS_STORE_RESPONSE", off)
            assert response_retention_enabled() is False, f"{off!r} should disable retention"

        monkeypatch.setenv("QUERY_ANALYTICS_STORE_RESPONSE", "1")
        assert response_retention_enabled() is True


class TestEveryWriterHandsOverTheAnswer:
    """The half that was actually broken.

    These read the CALL SITES. Behaviourally pinning all three would mean
    driving the whole ReAct pipeline and a streaming generator; instead the
    argument list of each call is parsed from the AST, which is the entity
    in question here — "does this writer pass the answer at all". What it
    deliberately does NOT prove is that the value passed IS the answer; the
    orchestrator test below covers that for the site that can be driven.

    Written as an enumeration rather than a fixed list of three, so a FOURTH
    writer added later inherits the guard instead of slipping past it.
    """

    @staticmethod
    def _module_path(dotted: str) -> Path:
        import importlib

        module = importlib.import_module(dotted)
        assert module.__file__ is not None
        return Path(module.__file__)

    def _calls_named(self, dotted: str, attr: str) -> list[ast.Call]:
        tree = ast.parse(self._module_path(dotted).read_text(encoding="utf-8"))
        return [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == attr
            # the definition itself is a FunctionDef, never a Call — but a
            # recursive/self-forwarding call would be, so exclude the
            # repository's own forwarding by requiring a real receiver.
            and not isinstance(node.func.value, ast.Constant)
        ]

    @pytest.mark.parametrize(
        ("dotted", "attr", "minimum"),
        [
            ("backend.services.rag.agentic.orchestrator_core", "_log_query_analytics", 2),
            ("backend.services.rag.agentic.orchestrator_core", "log_query", 1),
            ("backend.services.rag.agentic.orchestrator_streaming_core", "log_query", 1),
        ],
    )
    def test_guilt_every_call_site_passes_response_text(
        self,
        dotted: str,
        attr: str,
        minimum: int,
    ) -> None:
        calls = self._calls_named(dotted, attr)
        # Guard the guard: a rename that makes this find nothing must fail
        # loudly rather than pass vacuously.
        assert len(calls) >= minimum, (
            f"found {len(calls)} call(s) to {attr} in {dotted}, expected >= {minimum} — "
            f"the probe is looking at the wrong name, not at a clean module"
        )
        for call in calls:
            kwargs = {kw.arg for kw in call.keywords if kw.arg}
            assert "response_text" in kwargs, (
                f"{dotted}:{call.lineno} calls {attr}() without response_text — "
                f"this writer records that an answer existed and keeps nothing of it"
            )

    def test_the_streaming_writer_passes_the_state_answer(self) -> None:
        """The streaming path has no accumulator, and does not need one.

        ``reasoning.py`` streams ``state.final_answer`` in 20-char chunks, so
        the whole text is on the state object by the time analytics runs.
        Pinned because a future refactor that starts accumulating tokens
        locally would silently make this read stale.
        """
        source = self._module_path(
            "backend.services.rag.agentic.orchestrator_streaming_core"
        ).read_text(encoding="utf-8")
        assert 'getattr(state, "final_answer", None)' in source


@pytest.mark.asyncio
async def test_guilt_the_orchestrator_forwards_the_real_answer() -> None:
    """End of the chain: the value handed over is the answer itself."""
    from backend.db.repositories import query_analytics_repository as repo_module
    from backend.services.rag.agentic.orchestrator_core import OrchestratorCore

    pool, conn = _mock_pool()
    conn.fetchrow = AsyncMock(return_value={"id": "00000000-0000-0000-0000-00000000000e"})
    core = OrchestratorCore.__new__(OrchestratorCore)
    core.db_pool = pool

    from backend.services.llm_clients.pricing import TokenUsage

    await core._log_query_analytics(
        query="berapa modal PT PMA?",
        user_id=None,
        session_id=None,
        collections_used=set(),
        sources=[],
        model_used="gemini",
        token_usage=TokenUsage(prompt_tokens=1, completion_tokens=1, model="gemini"),
        timings={"total": 0.5},
        response_generated=True,
        response_text=_ANSWER,
    )

    assert repo_module.response_retention_enabled() is True
    assert _bound_response_text(conn) == _ANSWER
