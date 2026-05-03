"""Federation Alert Dispatcher — main daemon loop.

PR #2 scope:
    * LISTEN federation_alert (PG NOTIFY)
    * Replay unconsumed events_outbox rows on startup (B7)
    * Mode-aware processing:
        observe        — persist + JSONL audit only
        dry_deliberate — same as observe in PR #2 (consiglio added in PR #3)
        dry_action     — execute action with dry_run=True
        production     — execute action with dry_run=False
                         (only for ALLOWED_L2 actions; rest → quarantine
                         or HITL_ONLY which is fully wired in PR #3)

The daemon is intentionally simple here. Multi-LLM consensus + Telegram
approval gate land in PR #3.

Crash safety:
    * On SIGTERM/SIGINT: cancels listener task, releases lease, exits 0.
    * On unhandled exception in a single proposal: logs + advances that
      proposal to status='failed', then continues processing others.

Single-instance: lease + advisory lock per proposal_id (B5+B6). Two
daemons on the same Pro coexist safely — only one acquires each
proposal's lease.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import signal
from typing import Any

import asyncpg

from backend.services.events.outbox import replay_unconsumed
from backend.services.federation_alerts.actions import (
    classify_action,
    get_action,
)
from backend.services.federation_alerts.audit import AuditLogger
from backend.services.federation_alerts.config import FADConfig
from backend.services.federation_alerts.dispatcher import quick_subprocess_check
from backend.services.federation_alerts.models import (
    FederationAlertMode,
    ProposalStatus,
    effective_mode,
)
from backend.services.federation_alerts.repository import FederationAlertRepo

logger = logging.getLogger(__name__)

PG_CHANNEL = "federation_alert"


class FederationAlertDaemon:
    """Long-running daemon for the Federation Alert Dispatcher."""

    def __init__(self, config: FADConfig) -> None:
        config.assert_required()
        self._config = config
        self._audit = AuditLogger(config.audit_log_dir)
        self._pool: asyncpg.Pool | None = None
        self._stop_event = asyncio.Event()
        self._listener_conn: asyncpg.Connection | None = None
        # Probe ai-dispatch.sh at construction; the daemon won't refuse
        # to start, but it will refuse to leave 'observe' mode if False.
        self._dispatch_available: bool = quick_subprocess_check()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Block until SIGTERM. Idempotent for the same instance."""
        self._pool = await asyncpg.create_pool(
            self._config.database_url, min_size=1, max_size=4
        )
        self._install_signal_handlers()

        repo = FederationAlertRepo(pool=self._pool)
        self._audit.emit(
            "daemon.starting",
            data={
                "owner": self._config.daemon_owner,
                "dispatch_available": self._dispatch_available,
                "env_mode": self._config.env_mode,
            },
        )

        # B7: replay unconsumed events_outbox rows for federation_alert
        # (recovers events lost during a previous reconnect window).
        try:
            async with self._pool.acquire() as conn:
                await replay_unconsumed(
                    conn,
                    self._enqueue_replay,
                    channel=PG_CHANNEL,
                    consumer_id=self._config.daemon_owner,
                )
        except Exception as exc:  # noqa: BLE001 — keep daemon alive
            logger.warning("replay_unconsumed failed at boot: %s", exc)
            self._audit.emit(
                "daemon.replay_failed",
                data={"error": repr(exc)[:300]},
            )

        # Run the LISTEN loop until stop_event is set.
        try:
            await self._listen_loop(repo)
        finally:
            await self._cleanup()

    def _install_signal_handlers(self) -> None:
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, self._stop_event.set)
            except (NotImplementedError, ValueError):
                # Windows / non-main-thread fallback
                signal.signal(sig, lambda *_: self._stop_event.set())

    async def _cleanup(self) -> None:
        self._audit.emit("daemon.stopping", data={})
        if self._listener_conn is not None:
            with contextlib.suppress(Exception):
                await self._listener_conn.close()
        if self._pool is not None:
            await self._pool.close()

    # ------------------------------------------------------------------
    # LISTEN loop with reconnect
    # ------------------------------------------------------------------

    async def _listen_loop(self, repo: FederationAlertRepo) -> None:
        backoff = 1.0
        while not self._stop_event.is_set():
            try:
                conn = await asyncpg.connect(self._config.database_url)
                self._listener_conn = conn
                queue: asyncio.Queue[str] = asyncio.Queue()

                # Bind the queue to a default arg so each loop iteration
                # gets its own reference (avoids ruff B023: closure
                # capture across reconnect rebinds the queue object).
                def _on_notify(
                    _c: Any,
                    _pid: int,
                    _channel: str,
                    payload: str,
                    *,
                    _queue: asyncio.Queue[str] = queue,
                ) -> None:
                    _queue.put_nowait(payload)

                await conn.add_listener(PG_CHANNEL, _on_notify)
                logger.info("LISTEN %s active", PG_CHANNEL)
                self._audit.emit(
                    "daemon.listener_active",
                    data={"channel": PG_CHANNEL},
                )
                backoff = 1.0  # reset on successful connect

                while not self._stop_event.is_set():
                    try:
                        payload = await asyncio.wait_for(queue.get(), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue
                    await self._process_notify_payload(payload, repo)
            except (
                asyncpg.PostgresConnectionError,
                ConnectionError,
                OSError,
            ) as exc:
                logger.warning(
                    "LISTEN %s connection lost: %s; reconnecting in %.1fs",
                    PG_CHANNEL, exc, backoff,
                )
                self._audit.emit(
                    "daemon.listener_lost",
                    data={"error": repr(exc)[:300], "backoff_s": backoff},
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
            except Exception as exc:  # noqa: BLE001 — keep daemon alive
                logger.exception("LISTEN loop crashed: %s", exc)
                self._audit.emit(
                    "daemon.listener_crashed",
                    data={"error": repr(exc)[:300]},
                )
                await asyncio.sleep(5.0)

    # ------------------------------------------------------------------
    # Per-payload processing
    # ------------------------------------------------------------------

    async def _enqueue_replay(self, payload: dict[str, Any]) -> None:
        """Callback invoked by replay_unconsumed for each unconsumed row.

        ``replay_unconsumed`` decodes the JSONB column into a dict and
        injects ``_outbox_id`` / ``_replay`` keys before dispatching.
        The daemon's main NOTIFY loop, by contrast, receives the raw
        payload string from ``add_listener``. Re-serialise here so both
        paths funnel through ``_process_notify_payload``.
        """
        repo = FederationAlertRepo(pool=self._pool)  # type: ignore[arg-type]
        await self._process_notify_payload(json.dumps(payload), repo)

    async def _process_notify_payload(
        self, payload_str: str, repo: FederationAlertRepo
    ) -> None:
        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError as exc:
            logger.warning("malformed federation_alert payload: %s", exc)
            self._audit.emit(
                "daemon.payload_malformed",
                data={"error": repr(exc)[:200]},
            )
            return

        proposal_id = payload.get("proposal_id")
        if not proposal_id:
            logger.warning("federation_alert missing proposal_id: %s", payload)
            return

        proposal = await repo.get_by_proposal_id(proposal_id)
        if proposal is None:
            logger.warning(
                "federation_alert references unknown proposal %s", proposal_id
            )
            return

        # Skip terminal proposals (already processed).
        if proposal.is_terminal():
            return

        # B5+B6: lease before processing — losing this race is normal
        # (another daemon got to it first). No retry; the row will be
        # picked up on the next NOTIFY or replay.
        acquired = await repo.acquire_lease(
            proposal_id,
            owner=self._config.daemon_owner,
            ttl_seconds=self._config.lease_ttl_sec,
        )
        if not acquired:
            return

        mode = await self._effective_mode(repo)
        self._audit.emit(
            "alert.received",
            proposal_id=proposal_id,
            run_id=proposal.run_id,
            mode=mode,
            data={
                "alert_type": proposal.alert_type,
                "severity": proposal.severity,
                "requested_action": proposal.requested_action,
            },
        )

        try:
            await self._dispatch_proposal(repo, proposal, mode)
        except Exception as exc:  # noqa: BLE001 — keep daemon alive
            logger.exception("proposal %s crashed: %s", proposal_id, exc)
            self._audit.emit(
                "proposal.crashed",
                proposal_id=proposal_id,
                run_id=proposal.run_id,
                mode=mode,
                data={"error": repr(exc)[:500]},
            )
            with contextlib.suppress(Exception):
                await repo.advance_status(
                    proposal_id,
                    ProposalStatus.FAILED,
                    last_error=repr(exc)[:500],
                )
        finally:
            await repo.release_lease(
                proposal_id, owner=self._config.daemon_owner
            )

    async def _effective_mode(self, repo: FederationAlertRepo) -> str:
        db_mode = await repo.get_db_mode()
        return effective_mode(db_mode, self._config.env_mode)

    # ------------------------------------------------------------------
    # Proposal dispatch (mode-aware)
    # ------------------------------------------------------------------

    async def _dispatch_proposal(
        self,
        repo: FederationAlertRepo,
        proposal: Any,
        mode: str,
    ) -> None:
        proposal_id = proposal.proposal_id
        action_name = proposal.requested_action

        # ----- observe mode: persist only -----
        if mode == FederationAlertMode.OBSERVE.value:
            await repo.advance_status(proposal_id, ProposalStatus.OBSERVED)
            self._audit.emit(
                "proposal.observed",
                proposal_id=proposal_id,
                run_id=proposal.run_id,
                mode=mode,
                data={"action": action_name},
            )
            return

        # ----- whitelist gate -----
        if action_name is None:
            # No action requested → dry deliberation in dry_deliberate;
            # quarantine in dry_action/production (no point running anything).
            if mode == FederationAlertMode.DRY_DELIBERATE.value:
                await repo.advance_status(proposal_id, ProposalStatus.PROPOSED)
                self._audit.emit(
                    "proposal.proposed_no_action",
                    proposal_id=proposal_id,
                    run_id=proposal.run_id,
                    mode=mode,
                )
                return
            await repo.advance_status(
                proposal_id,
                ProposalStatus.QUARANTINED,
                last_error="no requested_action, cannot execute",
            )
            return

        policy = classify_action(action_name)
        if policy.blocked:
            await repo.advance_status(
                proposal_id,
                ProposalStatus.QUARANTINED,
                last_error=policy.reason or f"action blocked: {action_name}",
            )
            self._audit.emit(
                "proposal.action_blocked",
                proposal_id=proposal_id,
                run_id=proposal.run_id,
                mode=mode,
                data={"action": action_name, "reason": policy.reason},
            )
            return

        if policy.requires_approval:
            await self._request_telegram_approval(
                repo, proposal, mode, reason=policy.reason
            )
            return

        # ----- ALLOWED_L2 actions: execute (dry-run gated by mode) -----
        action_fn = get_action(action_name)
        if action_fn is None:
            await repo.advance_status(
                proposal_id,
                ProposalStatus.QUARANTINED,
                last_error=f"action not registered: {action_name}",
            )
            return

        is_dry = mode in (
            FederationAlertMode.DRY_DELIBERATE.value,
            FederationAlertMode.DRY_ACTION.value,
        )

        # dry_deliberate doesn't even simulate the action — it stays in
        # 'proposed'. dry_action runs the action with dry_run=True.
        if mode == FederationAlertMode.DRY_DELIBERATE.value:
            await repo.advance_status(proposal_id, ProposalStatus.PROPOSED)
            self._audit.emit(
                "proposal.proposed",
                proposal_id=proposal_id,
                run_id=proposal.run_id,
                mode=mode,
                data={"action": action_name},
            )
            return

        # dry_action OR production
        await repo.advance_status(
            proposal_id,
            ProposalStatus.DRY_EXECUTING if is_dry else ProposalStatus.EXECUTING,
        )

        result = await action_fn(
            proposal,
            dry_run=is_dry,
            db_pool=self._pool,
        )

        if is_dry:
            terminal = (
                ProposalStatus.DRY_SUCCEEDED
                if result.success
                else ProposalStatus.DRY_FAILED
            )
        else:
            terminal = (
                ProposalStatus.COMPLETED
                if result.success
                else ProposalStatus.FAILED
            )

        await repo.advance_status(
            proposal_id,
            terminal,
            last_error=None if result.success else result.message,
            artifact_uri=None,
        )

        self._audit.emit(
            "proposal.executed",
            proposal_id=proposal_id,
            run_id=proposal.run_id,
            mode=mode,
            data={
                "action": action_name,
                "success": result.success,
                "message": result.message[:300],
                "dry_run": is_dry,
                "side_effects_count": len(result.side_effects),
            },
        )

    # ------------------------------------------------------------------
    # PR #3 helpers — Telegram approval + ConsiglioOrchestrator hook
    # ------------------------------------------------------------------

    async def _request_telegram_approval(
        self,
        repo: FederationAlertRepo,
        proposal: Any,
        mode: str,
        *,
        reason: str | None,
    ) -> None:
        """Generate a fresh approval_token, store it, send Telegram message.

        Failures degrade gracefully: the proposal stays in
        awaiting_approval (DB row written), even if Telegram delivery
        fails the audit captures the gap and a future retry can
        re-issue the message via a separate workflow.
        """
        from backend.services.federation_alerts.approval import (
            generate_approval_token,
        )
        from backend.services.federation_alerts.notifier import (
            send_proposal_to_telegram,
        )

        proposal_id = proposal.proposal_id
        token = generate_approval_token()
        chat_id = self._config.telegram_chat_id

        if not chat_id or not self._config.telegram_bot_token:
            # Without Telegram credentials we still mark the proposal
            # awaiting_approval — admins can review via DB and trigger
            # external approval. Audit captures the missing channel.
            await repo.request_approval(
                proposal_id,
                approval_token=token,
                telegram_chat_id="<no-telegram>",
                telegram_message_id=None,
            )
            self._audit.emit(
                "proposal.awaiting_approval_offline",
                proposal_id=proposal_id,
                run_id=proposal.run_id,
                mode=mode,
                data={
                    "reason": reason,
                    "missing": "telegram_credentials",
                },
            )
            return

        # Send to Telegram synchronously (urllib) on a worker thread
        # so the daemon's main event loop is never blocked.
        message_id = await asyncio.to_thread(
            send_proposal_to_telegram,
            bot_token=self._config.telegram_bot_token,
            chat_id=chat_id,
            proposal=proposal,
            approval_token=token,
        )

        # Persist the token + message_id BEFORE returning so a callback
        # arriving immediately can be verified.
        try:
            await repo.request_approval(
                proposal_id,
                approval_token=token,
                telegram_chat_id=str(chat_id),
                telegram_message_id=message_id,
            )
        except RuntimeError as exc:
            logger.warning(
                "request_approval failed for %s: %s", proposal_id, exc
            )
            self._audit.emit(
                "proposal.approval_request_failed",
                proposal_id=proposal_id,
                run_id=proposal.run_id,
                mode=mode,
                data={"error": str(exc)[:200]},
            )
            return

        self._audit.emit(
            "proposal.awaiting_approval",
            proposal_id=proposal_id,
            run_id=proposal.run_id,
            mode=mode,
            data={
                "reason": reason,
                "telegram_message_id": message_id,
                "telegram_delivered": message_id is not None,
            },
        )

    async def _run_consiglio_if_configured(
        self,
        proposal: Any,
        timeout_sec: int,
    ) -> dict[str, Any] | None:
        """Run ConsiglioV1.deliberate() asynchronously, with a hard deadline.

        Returns the normalized deliberation result (see
        ``dispatcher.deliberate_with_deadline``) or None if Consiglio
        is not importable in this runtime (e.g. missing CLI binaries).
        """
        try:
            from backend.services.federation_alerts.dispatcher import (
                deliberate_with_deadline,
            )
            from backend.services.research.consiglio_orchestrator import (
                ConsiglioV1,
            )
        except ImportError as exc:
            logger.warning("ConsiglioV1 unavailable: %s", exc)
            return None

        consiglio = ConsiglioV1()
        prompt = self._build_consiglio_prompt(proposal)
        return await deliberate_with_deadline(
            consiglio,
            prompt,
            deadline_sec=timeout_sec,
        )

    @staticmethod
    def _build_consiglio_prompt(proposal: Any) -> str:
        """Compose the prompt string sent to each LLM in ConsiglioV1.

        Keeps payload minimal — full alert context lives in the DB row,
        but Consiglio voters only need enough to vote on whether the
        action is appropriate for the alert.
        """
        action = getattr(proposal, "requested_action", None) or "(none)"
        alert_type = getattr(proposal, "alert_type", "alert")
        severity = getattr(proposal, "severity", "medium")
        target_file = getattr(proposal, "target_file", None) or "(none)"
        return (
            "Federation Alert Dispatcher proposal review.\n\n"
            f"alert_type: {alert_type}\n"
            f"severity: {severity}\n"
            f"requested_action: {action}\n"
            f"target_file: {target_file}\n\n"
            "Vote whether the requested_action is appropriate for the alert. "
            'Respond with JSON: {"claims":[{"key":"action_appropriate",'
            '"value":"yes|no","confidence":0.0-1.0}]}'
        )


__all__ = ["FederationAlertDaemon"]
