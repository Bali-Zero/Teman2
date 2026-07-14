"""Guilt + innocence tests for the WABA subscription guardian.

The guardian re-arms unconditionally (the subscription state is not readable
with our token) and warns on inbound silence. Failure scenarios covered:
Meta rejects the POST, network flaps, missing config, deaf channel, and the
alert-dedup latch that keeps a long silence from spamming every 6h cycle.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from backend.services.misc.whatsapp_subscription_guardian import (
    WhatsAppSubscriptionGuardian,
    register_whatsapp_subscription_guardian,
)


def _guardian(**kwargs) -> WhatsAppSubscriptionGuardian:
    defaults = {
        "waba_id": "1234567890",
        "access_token": "test-token",
        "alert_service": None,
        "db_pool": None,
    }
    defaults.update(kwargs)
    return WhatsAppSubscriptionGuardian(**defaults)


def _mock_response(status_code: int = 200, body: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body if body is not None else {"success": True}
    return resp


class TestRearm:
    @pytest.mark.asyncio
    async def test_success_first_attempt(self):
        g = _guardian()
        g._client = MagicMock(is_closed=False)
        g._client.post = AsyncMock(return_value=_mock_response())

        result = await g.rearm()

        assert result["ok"] is True
        assert result["attempts"] == 1
        called_url = g._client.post.call_args[0][0]
        assert called_url.endswith("/1234567890/subscribed_apps")

    @pytest.mark.asyncio
    async def test_meta_rejection_is_terminal_no_retry(self):
        # A 400 with an error body is a token/permission problem — retrying
        # cannot fix it and would just hammer Meta.
        g = _guardian()
        g._client = MagicMock(is_closed=False)
        g._client.post = AsyncMock(
            return_value=_mock_response(
                400, {"error": {"code": 190, "type": "OAuthException", "message": "bad token"}}
            )
        )

        result = await g.rearm()

        assert result["ok"] is False
        assert g._client.post.await_count == 1
        assert "code=190" in result["detail"]

    @pytest.mark.asyncio
    async def test_network_flap_retries_then_succeeds(self, monkeypatch):
        # Scar family #8: one flap must not fail the cycle.
        monkeypatch.setattr(
            "backend.services.misc.whatsapp_subscription_guardian.REARM_BACKOFF_SECONDS",
            0.0,
        )
        g = _guardian()
        g._client = MagicMock(is_closed=False)
        g._client.post = AsyncMock(
            side_effect=[httpx.ConnectError("boom"), _mock_response()]
        )

        result = await g.rearm()

        assert result["ok"] is True
        assert result["attempts"] == 2

    @pytest.mark.asyncio
    async def test_network_dead_exhausts_attempts(self, monkeypatch):
        monkeypatch.setattr(
            "backend.services.misc.whatsapp_subscription_guardian.REARM_BACKOFF_SECONDS",
            0.0,
        )
        g = _guardian()
        g._client = MagicMock(is_closed=False)
        g._client.post = AsyncMock(side_effect=httpx.ConnectError("down"))

        result = await g.rearm()

        assert result["ok"] is False
        assert result["attempts"] == 3
        assert "network" in result["detail"]

    @pytest.mark.asyncio
    async def test_missing_config_short_circuits(self):
        g = _guardian(waba_id=None, access_token=None)

        result = await g.rearm()

        assert result == {"ok": False, "attempts": 0, "detail": "config_missing"}


class TestDeafness:
    def _pool_returning(self, last_inbound):
        pool = MagicMock()
        pool.fetchrow = AsyncMock(return_value={"last_inbound": last_inbound})
        return pool

    @pytest.mark.asyncio
    async def test_fresh_inbound_is_innocent(self):
        recent = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        g = _guardian(db_pool=self._pool_returning(recent))

        result = await g.check_deafness()

        assert result["deaf"] is False

    @pytest.mark.asyncio
    async def test_stale_inbound_is_deaf(self):
        stale = datetime.now(tz=timezone.utc) - timedelta(hours=100)
        g = _guardian(db_pool=self._pool_returning(stale))

        result = await g.check_deafness()

        assert result["deaf"] is True

    @pytest.mark.asyncio
    async def test_no_db_pool_degrades_gracefully(self):
        g = _guardian(db_pool=None)

        result = await g.check_deafness()

        assert result == {"deaf": False, "detail": "no_db_pool"}

    @pytest.mark.asyncio
    async def test_query_failure_never_kills_cycle(self):
        pool = MagicMock()
        pool.fetchrow = AsyncMock(side_effect=RuntimeError("db down"))
        g = _guardian(db_pool=pool)

        result = await g.check_deafness()

        assert result["deaf"] is False
        assert "query_failed" in result["detail"]


class TestCycleAlerts:
    def _alerting_guardian(self, **kwargs):
        alert_service = MagicMock()
        alert_service.send_alert = AsyncMock()
        g = _guardian(alert_service=alert_service, **kwargs)
        return g, alert_service

    @pytest.mark.asyncio
    async def test_healthy_cycle_sends_no_alert(self):
        recent = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        pool = MagicMock()
        pool.fetchrow = AsyncMock(return_value={"last_inbound": recent})
        g, alerts = self._alerting_guardian(db_pool=pool)
        g._client = MagicMock(is_closed=False)
        g._client.post = AsyncMock(return_value=_mock_response())

        result = await g.run_cycle()

        assert result["rearm"]["ok"] is True
        alerts.send_alert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rearm_failure_alerts_critical(self, monkeypatch):
        monkeypatch.setattr(
            "backend.services.misc.whatsapp_subscription_guardian.REARM_BACKOFF_SECONDS",
            0.0,
        )
        g, alerts = self._alerting_guardian()
        g._client = MagicMock(is_closed=False)
        g._client.post = AsyncMock(side_effect=httpx.ConnectError("down"))

        await g.run_cycle()

        assert alerts.send_alert.await_count == 1
        kwargs = alerts.send_alert.await_args.kwargs
        assert "FAILED" in kwargs["title"]
        assert kwargs["level"].value == "critical"

    @pytest.mark.asyncio
    async def test_deafness_alerts_once_then_latches(self):
        stale = datetime.now(tz=timezone.utc) - timedelta(hours=100)
        pool = MagicMock()
        pool.fetchrow = AsyncMock(return_value={"last_inbound": stale})
        g, alerts = self._alerting_guardian(db_pool=pool)
        g._client = MagicMock(is_closed=False)
        g._client.post = AsyncMock(return_value=_mock_response())

        await g.run_cycle()
        await g.run_cycle()  # second cycle inside the re-alert window

        deaf_alerts = [
            c for c in alerts.send_alert.await_args_list if "silence" in c.kwargs["title"]
        ]
        assert len(deaf_alerts) == 1

    @pytest.mark.asyncio
    async def test_recovery_resets_deafness_latch(self):
        stale = datetime.now(tz=timezone.utc) - timedelta(hours=100)
        recent = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        pool = MagicMock()
        pool.fetchrow = AsyncMock(
            side_effect=[
                {"last_inbound": stale},
                {"last_inbound": recent},
                {"last_inbound": stale},
            ]
        )
        g, alerts = self._alerting_guardian(db_pool=pool)
        g._client = MagicMock(is_closed=False)
        g._client.post = AsyncMock(return_value=_mock_response())

        await g.run_cycle()  # deaf → alert
        await g.run_cycle()  # recovered → latch reset
        await g.run_cycle()  # deaf again → alert again

        deaf_alerts = [
            c for c in alerts.send_alert.await_args_list if "silence" in c.kwargs["title"]
        ]
        assert len(deaf_alerts) == 2

    @pytest.mark.asyncio
    async def test_config_missing_alerts_once_per_lifetime(self):
        g, alerts = self._alerting_guardian(waba_id=None, access_token=None)

        await g.run_cycle()
        await g.run_cycle()

        config_alerts = [
            c
            for c in alerts.send_alert.await_args_list
            if "misconfigured" in c.kwargs["title"]
        ]
        assert len(config_alerts) == 1


class TestRegistration:
    def test_registers_on_scheduler(self):
        scheduler = MagicMock()

        guardian = register_whatsapp_subscription_guardian(scheduler, db_pool=None)

        assert guardian is not None
        kwargs = scheduler.register_task.call_args.kwargs
        assert kwargs["name"] == "wa_subscription_guardian"
        assert kwargs["interval_seconds"] == 21600
        assert kwargs["enabled"] is True

    def test_kill_switch_disables(self, monkeypatch):
        monkeypatch.setenv("WA_SUBSCRIPTION_GUARDIAN_ENABLED", "false")
        scheduler = MagicMock()

        guardian = register_whatsapp_subscription_guardian(scheduler)

        assert guardian is None
        scheduler.register_task.assert_not_called()


class TestLiveLoopStarter:
    """The scheduler registration alone is an unarmed arm (W81: the
    AutonomousScheduler is disabled in prod) — the live path is the loop."""

    @pytest.mark.asyncio
    async def test_starts_named_task(self):
        from backend.services.misc.whatsapp_subscription_guardian import (
            start_whatsapp_subscription_guardian_task,
        )

        task = start_whatsapp_subscription_guardian_task(interval_seconds=21600)

        assert task is not None
        assert task.get_name() == "wa_subscription_guardian"
        task.cancel()

    @pytest.mark.asyncio
    async def test_kill_switch_returns_none(self, monkeypatch):
        from backend.services.misc.whatsapp_subscription_guardian import (
            start_whatsapp_subscription_guardian_task,
        )

        monkeypatch.setenv("WA_SUBSCRIPTION_GUARDIAN_ENABLED", "false")

        assert start_whatsapp_subscription_guardian_task() is None

    @pytest.mark.asyncio
    async def test_loop_respects_leader_lock(self, monkeypatch):
        from backend.services.misc import whatsapp_subscription_guardian as mod

        cycles = []

        class FakeGuardian:
            async def run_cycle(self):
                cycles.append(1)

        async def no_sleep(_):
            if len(cycles) >= 1 or no_sleep.calls >= 3:
                raise asyncio.CancelledError
            no_sleep.calls += 1

        no_sleep.calls = 0
        monkeypatch.setattr(mod.asyncio, "sleep", no_sleep)
        monkeypatch.setattr(
            "backend.services.misc.autonomous_scheduler._acquire_task_lock",
            AsyncMock(return_value=True),
        )

        with pytest.raises(asyncio.CancelledError):
            await mod._guardian_loop(FakeGuardian(), 21600)

        assert cycles == [1]

    @pytest.mark.asyncio
    async def test_loop_skips_cycle_when_lock_denied(self, monkeypatch):
        from backend.services.misc import whatsapp_subscription_guardian as mod

        cycles = []

        class FakeGuardian:
            async def run_cycle(self):
                cycles.append(1)

        async def no_sleep(_):
            if no_sleep.calls >= 2:
                raise asyncio.CancelledError
            no_sleep.calls += 1

        no_sleep.calls = 0
        monkeypatch.setattr(mod.asyncio, "sleep", no_sleep)
        monkeypatch.setattr(
            "backend.services.misc.autonomous_scheduler._acquire_task_lock",
            AsyncMock(return_value=False),
        )

        with pytest.raises(asyncio.CancelledError):
            await mod._guardian_loop(FakeGuardian(), 21600)

        assert cycles == []
