"""
Confirmation Service — Interactive user confirmation gates for the agentic loop.

VASSAL Phase 3 (VASSAL_PLAN_V8 §5.2):
    Provides request/resolve semantics for tools that require human
    approval before the LLM can execute them. The motivating use case is
    ImageGenerationTool (per-call $ cost), but the pattern extends to any
    write tool added to `AgentRole.requires_confirmation` in future phases.

Architecture:
    * Each confirmation request is persisted in Redis (key `conf:{uuid}`,
      TTL 180s) and tracked locally with an `asyncio.Future`.
    * The `request_and_wait` coroutine blocks until the future is
      resolved (approve/reject), the timeout fires (170s default), or
      Redis is detected as unavailable (fail-closed).
    * Resolution can happen via the local fast path (same process sets
      the Future directly) or via Redis pub/sub (cross-process wakeup).
    * A background task (`_pubsub_listener`) subscribes to the
      `conf:resolutions` channel and resolves any matching local Future.

Fail-closed guarantee:
    Redis unavailable at request time → `ConfirmationRedisDown` raised.
    No resolution within timeout → `ConfirmationTimeout` raised.
    Both are caught by `tool_executor.execute_tool` and converted to a
    clear observation string for the LLM.

Frontend surface (Phase 3B):
    Phase 3 backend emits an SSE event `confirmation_required` via the
    optional `emitter` callback. Phase 3B frontend will render a modal
    and POST to `/api/agentic-rag/confirm`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

CONFIRMATION_KEY_PREFIX = "conf:"
CONFIRMATION_PUBSUB_CHANNEL = "conf:resolutions"
CONFIRMATION_TTL_SECONDS = 180
CONFIRMATION_TIMEOUT_SECONDS = 170


class ConfirmationError(Exception):
    """Base class for confirmation-flow errors."""


class ConfirmationRedisDown(ConfirmationError):
    """Redis unavailable at request time → fail-closed DENY."""


class ConfirmationTimeout(ConfirmationError):
    """No resolution within CONFIRMATION_TIMEOUT_SECONDS → fail-closed DENY."""


class ConfirmationService:
    """
    Cross-process confirmation gate for write tools.

    See module docstring for full architecture description.
    """

    def __init__(self, redis_manager: Any) -> None:
        self._redis_manager = redis_manager
        self._pending: dict[str, asyncio.Future[str]] = {}
        self._listener_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    # ─────────────────────────────────────────────────────────────────
    # Lifecycle
    # ─────────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the pub/sub listener. Call from app startup."""
        if self._listener_task is not None and not self._listener_task.done():
            return
        if not self._redis_available():
            logger.warning(
                "ConfirmationService: Redis unavailable at start; "
                "listener not started"
            )
            return
        self._listener_task = asyncio.create_task(self._pubsub_listener())
        logger.info("ConfirmationService: pubsub listener started")

    async def stop(self) -> None:
        """Stop the pub/sub listener. Call from app shutdown."""
        if self._listener_task is not None and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except (asyncio.CancelledError, Exception):
                pass
        for fut in list(self._pending.values()):
            if not fut.done():
                fut.set_exception(ConfirmationError("service stopped"))
        self._pending.clear()

    # ─────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────

    async def request_and_wait(
        self,
        tool_name: str,
        args: dict[str, Any],
        user_email: str,
        preview: str,
        emitter: Callable[[dict], Awaitable[None]] | None = None,
        timeout: float = CONFIRMATION_TIMEOUT_SECONDS,
    ) -> bool:
        """
        Request user confirmation and block until resolved.

        Returns True if approved, False if rejected.
        Raises ConfirmationRedisDown or ConfirmationTimeout on failure.
        """
        client = self._get_client()
        if client is None:
            raise ConfirmationRedisDown(
                "Redis unavailable; cannot persist confirmation request"
            )

        request_id = str(uuid.uuid4())
        payload = {
            "request_id": request_id,
            "tool_name": tool_name,
            "args": args,
            "user_email": user_email,
            "preview": preview,
        }

        # 1. Persist in Redis
        try:
            await client.set(
                f"{CONFIRMATION_KEY_PREFIX}{request_id}",
                json.dumps(payload),
                ex=CONFIRMATION_TTL_SECONDS,
            )
        except Exception as exc:
            raise ConfirmationRedisDown(f"Redis SET failed: {exc}") from exc

        # 2. Register local Future
        loop = asyncio.get_running_loop()
        future: asyncio.Future[str] = loop.create_future()
        async with self._lock:
            self._pending[request_id] = future

        # 3. Emit SSE event
        if emitter is not None:
            try:
                await emitter({
                    "type": "confirmation_required",
                    "data": {
                        "request_id": request_id,
                        "tool_name": tool_name,
                        "args": args,
                        "preview": preview,
                    },
                })
            except Exception as exc:
                logger.warning(
                    "ConfirmationService: emitter raised %s; continuing",
                    exc,
                )

        # 4. Block until resolved or timeout
        try:
            decision = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            raise ConfirmationTimeout(
                f"No resolution within {timeout}s"
            ) from None
        finally:
            async with self._lock:
                self._pending.pop(request_id, None)
            try:
                await client.delete(f"{CONFIRMATION_KEY_PREFIX}{request_id}")
            except Exception:
                pass

        return decision == "approve"

    async def resolve_confirmation(
        self,
        request_id: str,
        decision: str,
        user_email: str,
    ) -> bool:
        """
        Resolve a pending confirmation request.

        Returns True if found and resolved, False otherwise.
        """
        if decision not in ("approve", "reject"):
            return False

        client = self._get_client()
        if client is None:
            return False

        # 1. Verify ownership
        try:
            raw = await client.get(f"{CONFIRMATION_KEY_PREFIX}{request_id}")
        except Exception:
            return False

        if raw is None:
            return False

        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return False

        if payload.get("user_email") != user_email:
            logger.warning(
                "ConfirmationService: resolve denied — user %s does "
                "not own request %s (owner: %s)",
                user_email,
                request_id,
                payload.get("user_email"),
            )
            return False

        # 2. Local fast path
        async with self._lock:
            future = self._pending.get(request_id)
        if future is not None and not future.done():
            future.set_result(decision)

        # 3. Cross-process pub/sub
        try:
            await client.publish(
                CONFIRMATION_PUBSUB_CHANNEL,
                json.dumps({
                    "request_id": request_id,
                    "decision": decision,
                }),
            )
        except Exception as exc:
            logger.warning("ConfirmationService: publish failed: %s", exc)

        return True

    # ─────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────

    def _get_client(self) -> Any | None:
        if self._redis_manager is None:
            return None
        if not getattr(self._redis_manager, "available", False):
            return None
        return self._redis_manager.get_async_client()

    def _redis_available(self) -> bool:
        return self._get_client() is not None

    async def _pubsub_listener(self) -> None:
        """Subscribe to the confirmation channel and resolve local Futures."""
        client = self._get_client()
        if client is None:
            return
        pubsub = client.pubsub()
        try:
            await pubsub.subscribe(CONFIRMATION_PUBSUB_CHANNEL)
            logger.info(
                "ConfirmationService: subscribed to %s",
                CONFIRMATION_PUBSUB_CHANNEL,
            )
            async for raw_msg in pubsub.listen():
                if raw_msg is None or raw_msg.get("type") != "message":
                    continue
                try:
                    msg = json.loads(raw_msg["data"])
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue
                rid = msg.get("request_id")
                dec = msg.get("decision")
                if not rid or dec not in ("approve", "reject"):
                    continue
                async with self._lock:
                    future = self._pending.get(rid)
                if future is not None and not future.done():
                    future.set_result(dec)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(
                "ConfirmationService: listener error: %s",
                exc,
                exc_info=True,
            )
        finally:
            try:
                await pubsub.unsubscribe(CONFIRMATION_PUBSUB_CHANNEL)
                await pubsub.aclose()
            except Exception:
                pass


__all__ = [
    "CONFIRMATION_KEY_PREFIX",
    "CONFIRMATION_PUBSUB_CHANNEL",
    "CONFIRMATION_TIMEOUT_SECONDS",
    "CONFIRMATION_TTL_SECONDS",
    "ConfirmationError",
    "ConfirmationRedisDown",
    "ConfirmationService",
    "ConfirmationTimeout",
]
