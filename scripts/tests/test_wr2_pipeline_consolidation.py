"""Unit tests for P-1 WR2 pipeline consolidation — slice 1.

Spec: research/operations/specs/P1-wr2-pipeline-consolidation.md (REV 2, panel-validated).

Covers:
  S1   shared topic_type_log writer module + canva delegation + html-apply hook
  R4.2 drain-loop in html-apply run() and draft-generator run()
  S9   supervisor maps route to html-apply, never canva-apply, no dead briefed_facted
  S10  watchdog re-key: html flag probe, DB-derived success rate (NO-DATA not 100%),
       ledger-gap probe, pipeline-state freshness off canva_applied_at
  R1   worktree-gc decoupled from Pipeline-A tables (fetch_inflight_carousels gone)

Modules are loaded via importlib (scripts/ has no package __init__).
"""
from __future__ import annotations

import importlib.util
import sys
import uuid
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load(name: str) -> ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / f"{name}.py")
    assert spec and spec.loader, f"cannot load {name}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ─────────────────────────────────────────────────────────────────────────
# S1 — shared writer module scripts/wr2_topic_type_log.py
# ─────────────────────────────────────────────────────────────────────────


class TestTopicTypeLogModule:
    @pytest.mark.asyncio
    async def test_inserts_derived_row_idempotently(self):
        ttl = _load("wr2_topic_type_log")
        tt = _load("wr2_topic_type")
        conn = MagicMock()
        conn.execute = AsyncMock()
        conn.fetchrow = AsyncMock()
        draft_id = uuid.uuid4()
        topic = "New KITAS rules for foreign investors"
        slides = {"slides": [{"image_mode": "human-silhouette", "layout": "hero-top"}]}

        await ttl.log_topic_type(conn, draft_id, topic=topic, slides_json=slides, register="ID-formal")

        conn.fetchrow.assert_not_awaited()  # all fields supplied — no fallback SELECT
        conn.execute.assert_awaited_once()
        sql = conn.execute.await_args.args[0]
        assert "INSERT INTO topic_type_log" in sql
        assert "ON CONFLICT (draft_id) DO NOTHING" in sql
        args = conn.execute.await_args.args
        assert args[1] == draft_id
        assert args[2] == tt.derive_domain(topic)
        assert args[3] == "ID-formal"
        assert args[4] == tt.derive_dominant_mode(slides)

    @pytest.mark.asyncio
    async def test_falls_back_to_select_when_fields_missing(self):
        ttl = _load("wr2_topic_type_log")
        conn = MagicMock()
        conn.execute = AsyncMock()
        conn.fetchrow = AsyncMock(
            return_value={"topic": "Pajak PPN 12%", "register": "ID-pop", "slides_json": {"slides": []}}
        )
        draft_id = uuid.uuid4()

        await ttl.log_topic_type(conn, draft_id)

        conn.fetchrow.assert_awaited_once()
        conn.execute.assert_awaited_once()
        args = conn.execute.await_args.args
        assert args[3] == "ID-pop"
        assert args[7] == "Pajak PPN 12%"


class TestCanvaApplyDelegatesToSharedModule:
    @pytest.mark.asyncio
    async def test_canva_log_topic_type_delegates(self, monkeypatch):
        canva = _load("wr2_canva_desktop_apply")
        shared = MagicMock()
        shared.log_topic_type = AsyncMock()
        monkeypatch.setitem(sys.modules, "wr2_topic_type_log", shared)
        conn = MagicMock()
        draft_id = uuid.uuid4()

        await canva._log_topic_type(conn, draft_id, "topic", {"slides": []}, "reg")

        shared.log_topic_type.assert_awaited_once()
        args = shared.log_topic_type.await_args
        assert args.args[0] is conn
        assert args.args[1] == draft_id


# ─────────────────────────────────────────────────────────────────────────
# S1 hook + R4.2 drain — scripts/wr2_html_render_apply.py
# ─────────────────────────────────────────────────────────────────────────


class TestHtmlApplyLedger:
    @pytest.mark.asyncio
    async def test_ledger_best_effort_swallows_failures(self, monkeypatch, caplog):
        html = _load("wr2_html_render_apply")
        shared = MagicMock()
        shared.log_topic_type = AsyncMock(side_effect=RuntimeError("db down"))
        monkeypatch.setitem(sys.modules, "wr2_topic_type_log", shared)
        conn = MagicMock()
        conn.transaction = MagicMock(side_effect=RuntimeError("no tx"))
        draft_id = uuid.uuid4()

        with caplog.at_level("WARNING"):
            await html._log_ledger_best_effort(conn, draft_id)  # must NOT raise

        assert any("topic_type_log" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_ledger_best_effort_calls_shared_writer(self, monkeypatch):
        html = _load("wr2_html_render_apply")
        shared = MagicMock()
        shared.log_topic_type = AsyncMock()
        monkeypatch.setitem(sys.modules, "wr2_topic_type_log", shared)

        class _Tx:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

        conn = MagicMock()
        conn.transaction = MagicMock(return_value=_Tx())
        draft_id = uuid.uuid4()

        await html._log_ledger_best_effort(conn, draft_id)

        shared.log_topic_type.assert_awaited_once()
        assert shared.log_topic_type.await_args.args[1] == draft_id

    @pytest.mark.asyncio
    async def test_apply_one_writes_ledger_after_persist(self, monkeypatch, tmp_path):
        html = _load("wr2_html_render_apply")
        order: list[str] = []
        draft_id = uuid.uuid4()

        slides_dir = tmp_path / "slides"
        slides_dir.mkdir()
        # Codex red-team MEDIUM #7: real render output is numeric-stem only
        # ("01.png"); a "slide_01.png" fixture doesn't match derive_slide_paths()
        # (the shared filter now enforced end-to-end) and would spuriously read
        # as "no PNGs after render".
        (slides_dir / "01.png").write_bytes(b"png")

        conn = MagicMock()
        conn.execute = AsyncMock()
        conn.fetchval = AsyncMock(return_value=0)
        conn.close = AsyncMock()
        monkeypatch.setattr(html.asyncpg, "connect", AsyncMock(return_value=conn))

        pg = MagicMock()
        pg.acquire_html_lease_and_fetch = AsyncMock(
            return_value={"slides_json": {"slides": [{"heading": "x"}]}}
        )

        async def _persist(*a, **k):
            order.append("persist")
            return {}

        pg.persist_html_result_and_enqueue_notifications = AsyncMock(side_effect=_persist)
        monkeypatch.setattr(html, "_pg", pg)

        async def _ledger(*a, **k):
            order.append("ledger")

        monkeypatch.setattr(html, "_log_ledger_best_effort", AsyncMock(side_effect=_ledger))
        # visibility chain (R1-R3 cure) is filesystem/Telegram-touching — inert here;
        # its own unit tests live in test_wr2_visibility_chain.py
        monkeypatch.setattr(html, "_publish_visibility", AsyncMock())

        async def _hb(*a, **k):
            return None

        monkeypatch.setattr(html, "_heartbeat_loop", _hb)
        monkeypatch.setattr(html, "_normalize_heroes", lambda slides, *a, **k: slides)

        class _Srv:
            def __init__(self, *a, **k):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(html, "_HeroServer", _Srv)
        # _render_carousel now returns (slides_dir, weak_slides) — N-1 semantics
        monkeypatch.setattr(html, "_render_carousel", AsyncMock(return_value=(slides_dir, [])))
        monkeypatch.setattr(html, "_drive_upload_carousel", AsyncMock(return_value="https://drive/x"))
        monkeypatch.setattr(html, "_ops_alert", AsyncMock())
        monkeypatch.delenv("WR2_HTML_SHADOW", raising=False)

        result = await html._apply_one("postgres://x", draft_id, "owner-1")

        assert result.startswith("rendered")
        assert order == ["persist", "ledger"]


class TestHtmlApplyDrainLoop:
    @pytest.mark.asyncio
    async def test_run_drains_until_queue_empty(self, monkeypatch):
        html = _load("wr2_html_render_apply")
        monkeypatch.setenv("DATABASE_URL", "postgres://x")
        scan = MagicMock()
        scan.close = AsyncMock()
        monkeypatch.setattr(html.asyncpg, "connect", AsyncMock(return_value=scan))

        id1, id2 = uuid.uuid4(), uuid.uuid4()
        pg = MagicMock()
        pg.is_html_kill_switch_enabled = AsyncMock(return_value=True)
        pg.reset_stale_html_leases = AsyncMock(return_value=[])
        pg.fetch_pending_html_draft_ids = AsyncMock(side_effect=[[id1], [id2], []])
        monkeypatch.setattr(html, "_pg", pg)

        apply_one = AsyncMock(return_value="rendered report={}")
        monkeypatch.setattr(html, "_apply_one", apply_one)

        rc = await html.run()

        assert apply_one.await_count == 2
        assert {c.args[1] for c in apply_one.await_args_list} == {id1, id2}
        assert pg.fetch_pending_html_draft_ids.await_count == 3
        assert rc == 0

    @pytest.mark.asyncio
    async def test_run_uses_html_specific_fetch_not_canva_fetch(self, monkeypatch):
        """The Canva-lane fetch filters canva_edit_url IS NULL, which starves
        pre-cutover drafts that Canva touched (e.g. 948883c6/3e2c2923 stuck in
        drafts_imaged_checked while reconcile kept kicking them); the HTML lane
        must use its own drive_url-based fetch and never the Canva one."""
        html = _load("wr2_html_render_apply")
        monkeypatch.setenv("DATABASE_URL", "postgres://x")
        scan = MagicMock()
        scan.close = AsyncMock()
        monkeypatch.setattr(html.asyncpg, "connect", AsyncMock(return_value=scan))

        pg = MagicMock()
        pg.is_html_kill_switch_enabled = AsyncMock(return_value=True)
        pg.reset_stale_html_leases = AsyncMock(return_value=[])
        pg.fetch_pending_html_draft_ids = AsyncMock(return_value=[])
        pg.fetch_pending_draft_ids = AsyncMock(return_value=[])
        monkeypatch.setattr(html, "_pg", pg)
        monkeypatch.setattr(html, "_apply_one", AsyncMock())

        rc = await html.run()

        assert pg.fetch_pending_html_draft_ids.await_count >= 1
        assert pg.fetch_pending_draft_ids.await_count == 0
        assert rc == 0  # empty queue = nothing to do = success

    @pytest.mark.asyncio
    async def test_run_drain_loop_is_capped(self, monkeypatch):
        html = _load("wr2_html_render_apply")
        monkeypatch.setenv("DATABASE_URL", "postgres://x")
        monkeypatch.setenv("WR2_HTML_DRAIN_MAX_LOOPS", "3")
        scan = MagicMock()
        scan.close = AsyncMock()
        monkeypatch.setattr(html.asyncpg, "connect", AsyncMock(return_value=scan))

        pg = MagicMock()
        pg.is_html_kill_switch_enabled = AsyncMock(return_value=True)
        pg.reset_stale_html_leases = AsyncMock(return_value=[])
        # queue never drains — a bouncing draft must not loop forever
        pg.fetch_pending_html_draft_ids = AsyncMock(return_value=[uuid.uuid4()])
        monkeypatch.setattr(html, "_pg", pg)
        monkeypatch.setattr(html, "_apply_one", AsyncMock(return_value="retry:1:boom"))

        await html.run()

        assert pg.fetch_pending_html_draft_ids.await_count <= 3


# ─────────────────────────────────────────────────────────────────────────
# R4.2 drain — scripts/wr2_draft_generator.py
# ─────────────────────────────────────────────────────────────────────────


class _AcquireCM:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *a):
        return False


class TestDraftGeneratorDrainLoop:
    @pytest.mark.asyncio
    async def test_run_drains_briefed_queue(self, monkeypatch):
        dg = _load("wr2_draft_generator")
        monkeypatch.setenv("DATABASE_URL", "postgres://x")

        conn = MagicMock()
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=_AcquireCM(conn))
        pool.close = AsyncMock()
        monkeypatch.setattr(dg.asyncpg, "create_pool", AsyncMock(return_value=pool))

        def _row(topic: str):
            r = MagicMock()
            r.__getitem__ = MagicMock(side_effect=lambda k: {"id": uuid.uuid4(), "topic": topic, "brief_json": "{}"}[k])
            return r

        fetch = AsyncMock(side_effect=[[_row("a"), _row("b")], [_row("c")], []])
        monkeypatch.setattr(dg, "_fetch_briefed_drafts", fetch)
        process = AsyncMock(return_value="success")
        monkeypatch.setattr(dg, "_process_one", process)

        rc = await dg.run()

        assert process.await_count == 3
        assert fetch.await_count == 3
        assert rc == 0

    @pytest.mark.asyncio
    async def test_run_keeps_no_work_exit_code(self, monkeypatch):
        dg = _load("wr2_draft_generator")
        monkeypatch.setenv("DATABASE_URL", "postgres://x")
        conn = MagicMock()
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=_AcquireCM(conn))
        pool.close = AsyncMock()
        monkeypatch.setattr(dg.asyncpg, "create_pool", AsyncMock(return_value=pool))
        monkeypatch.setattr(dg, "_fetch_briefed_drafts", AsyncMock(return_value=[]))

        rc = await dg.run()

        assert rc == 1  # first-fetch-empty semantics preserved (launchd contract)

    @pytest.mark.asyncio
    async def test_run_all_parked_batch_exits_zero_not_two(self, monkeypatch):
        """2026-07-17 red-team finding #4: a batch where every draft is
        correctly parked (0 successes, 0 real failures) must exit 0. The old
        `return 0 if successes > 0 else 2` treated an all-parked batch the
        same as an all-failed batch, and
        scripts/launchagent-state-bridge.py:594 reads any nonzero exit as a
        failed run -> false P-incident. `parked` is a deliberate terminal
        outcome (B2 backstop), not an error, so it must not count against
        the exit code."""
        dg = _load("wr2_draft_generator")
        monkeypatch.setenv("DATABASE_URL", "postgres://x")
        conn = MagicMock()
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=_AcquireCM(conn))
        pool.close = AsyncMock()
        monkeypatch.setattr(dg.asyncpg, "create_pool", AsyncMock(return_value=pool))

        def _row(topic: str):
            r = MagicMock()
            r.__getitem__ = MagicMock(side_effect=lambda k: {"id": uuid.uuid4(), "topic": topic, "brief_json": "{}"}[k])
            return r

        fetch = AsyncMock(side_effect=[[_row("a")], []])
        monkeypatch.setattr(dg, "_fetch_briefed_drafts", fetch)
        process = AsyncMock(return_value="parked")
        monkeypatch.setattr(dg, "_process_one", process)

        rc = await dg.run()

        assert process.await_count == 1
        assert rc == 0

    @pytest.mark.asyncio
    async def test_run_all_failed_batch_still_exits_two(self, monkeypatch):
        """Innocence pair for the finding #4 fix: a batch with a REAL
        failure and zero successes/parks must still exit 2 — the fix must
        not accidentally launder genuine failures into a green exit."""
        dg = _load("wr2_draft_generator")
        monkeypatch.setenv("DATABASE_URL", "postgres://x")
        conn = MagicMock()
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=_AcquireCM(conn))
        pool.close = AsyncMock()
        monkeypatch.setattr(dg.asyncpg, "create_pool", AsyncMock(return_value=pool))

        def _row(topic: str):
            r = MagicMock()
            r.__getitem__ = MagicMock(side_effect=lambda k: {"id": uuid.uuid4(), "topic": topic, "brief_json": "{}"}[k])
            return r

        fetch = AsyncMock(side_effect=[[_row("a")], []])
        monkeypatch.setattr(dg, "_fetch_briefed_drafts", fetch)
        process = AsyncMock(return_value="failed")
        monkeypatch.setattr(dg, "_process_one", process)

        rc = await dg.run()

        assert process.await_count == 1
        assert rc == 2


# ─────────────────────────────────────────────────────────────────────────
# S9 — supervisor maps (scripts/wr2_supervisor.py)
# ─────────────────────────────────────────────────────────────────────────

_NONTERMINAL_STATUSES = {
    "briefed",
    "drafts",
    "drafts_imaged",
    "drafts_imaged_facted",
    "drafts_imaged_checked",
}


class TestSupervisorMaps:
    def test_no_target_is_canva_apply(self):
        sup = _load("wr2_supervisor")
        targets = [t for t in sup.TRANSITIONS.values() if t]
        targets += list(sup.NONTERMINAL_TO_NEXT_STAGE.values())
        assert all("canva-apply" not in t for t in targets), targets

    def test_checked_status_routes_to_html_apply(self):
        sup = _load("wr2_supervisor")
        assert (
            sup.TRANSITIONS[("drafts_imaged_facted", "drafts_imaged_checked")]
            == "com.balizero.wr2.html-apply"
        )
        assert sup.NONTERMINAL_TO_NEXT_STAGE["drafts_imaged_checked"] == "com.balizero.wr2.html-apply"

    def test_dead_briefed_facted_rows_removed(self):
        sup = _load("wr2_supervisor")
        for old, new in sup.TRANSITIONS:
            assert "briefed_facted" not in {old, new}
        assert "briefed_facted" not in sup.NONTERMINAL_TO_NEXT_STAGE

    def test_reconcile_map_covers_exactly_the_state_machine(self):
        sup = _load("wr2_supervisor")
        assert set(sup.NONTERMINAL_TO_NEXT_STAGE) == _NONTERMINAL_STATUSES


# ─────────────────────────────────────────────────────────────────────────
# S10 — watchdog re-key (scripts/wr2_supervisor_watchdog.py)
# ─────────────────────────────────────────────────────────────────────────


class TestWatchdogRekey:
    @pytest.mark.asyncio
    async def test_renderer_probe_reads_html_flag(self):
        wd = _load("wr2_supervisor_watchdog")
        conn = MagicMock()
        conn.fetchval = AsyncMock(return_value="true")

        assert await wd._probe_renderer_enabled(conn) is True
        assert conn.fetchval.await_args.args[1] == "wr2_html_renderer_enabled"

        conn.fetchval = AsyncMock(return_value="false")
        assert await wd._probe_renderer_enabled(conn) is False
        conn.fetchval = AsyncMock(return_value=None)
        assert await wd._probe_renderer_enabled(conn) is True  # degrade-open default

    @pytest.mark.asyncio
    async def test_success_rate_db_no_data_is_not_100(self):
        wd = _load("wr2_supervisor_watchdog")
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={"attempted": 0, "succeeded": 0})

        sr = await wd._probe_success_rate_db(conn)

        assert sr["no_data"] is True
        assert sr["rate_pct"] is None

    @pytest.mark.asyncio
    async def test_success_rate_db_computes_rate(self):
        wd = _load("wr2_supervisor_watchdog")
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={"attempted": 10, "succeeded": 8})

        sr = await wd._probe_success_rate_db(conn)

        assert sr["no_data"] is False
        assert sr["rate_pct"] == 80.0

    @pytest.mark.asyncio
    async def test_pipeline_state_uses_drive_url_not_canva_column(self, monkeypatch):
        wd = _load("wr2_supervisor_watchdog")
        monkeypatch.setattr(wd, "_probe_renderer_enabled", AsyncMock(return_value=True))
        conn = MagicMock()
        conn.fetchval = AsyncMock(side_effect=[1.5, 2])

        state = await wd._probe_pipeline_state(conn)

        assert state["renderer_disabled"] is False
        rendered_sql = conn.fetchval.await_args_list[1].args[0]
        assert "drive_url IS NOT NULL" in rendered_sql
        assert "canva_applied_at" not in rendered_sql

    @pytest.mark.asyncio
    async def test_ledger_gap_probe_counts_missing_rows(self):
        wd = _load("wr2_supervisor_watchdog")
        conn = MagicMock()
        conn.fetchval = AsyncMock(return_value=3)

        gap = await wd._probe_ledger_gap(conn)

        assert gap == 3
        sql = conn.fetchval.await_args.args[0]
        assert "topic_type_log" in sql
        assert "drive_url IS NOT NULL" in sql


# ─────────────────────────────────────────────────────────────────────────
# R1 — worktree-gc no longer references the Pipeline-A table at all
# ─────────────────────────────────────────────────────────────────────────


class TestWorktreeGcPipelineADecoupled:
    def test_fetch_inflight_carousels_symbol_gone(self):
        """R1: the SELECT on wr2_carousel_runs was removed, not feature-gated."""
        gc = _load("wr2_worktree_gc")
        assert not hasattr(gc, "fetch_inflight_carousels")

    def test_module_source_never_mentions_a_table(self):
        source = (SCRIPTS_DIR / "wr2_worktree_gc.py").read_text(encoding="utf-8")
        assert "wr2_carousel_runs" not in source
