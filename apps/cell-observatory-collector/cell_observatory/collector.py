from __future__ import annotations
import asyncio
import json
import structlog
from typing import Any

import asyncpg

from cell_observatory.classifier import CircuitOpenError, MinimaxClassifier
from cell_observatory.config import Config
from cell_observatory.models import PulseEventV1
from cell_observatory.storage import Storage

log = structlog.get_logger(__name__)


class Collector:
    """Listens to cell_pulse_observed PG channel + replays unconsumed outbox rows."""

    def __init__(
        self,
        storage: Storage,
        classifier: MinimaxClassifier,
        classifier_max_inflight: int = 50,
        classifier_queue_maxsize: int = 10000,
    ):
        self.storage = storage
        self.classifier = classifier
        self._semaphore = asyncio.Semaphore(classifier_max_inflight)
        self._classification_queue: asyncio.Queue = asyncio.Queue(maxsize=classifier_queue_maxsize)
        self._classification_workers: list[asyncio.Task] = []

    def _enqueue_for_classification(self, payload: dict[str, Any]) -> None:
        """G1 fix: drop-oldest on overflow, log WARN."""
        try:
            self._classification_queue.put_nowait(payload)
        except asyncio.QueueFull:
            try:
                dropped = self._classification_queue.get_nowait()
                log.warning("classification queue full, dropped oldest",
                            dropped_outbox_id=dropped.get("outbox_id"),
                            new_outbox_id=payload.get("outbox_id"))
                self._classification_queue.put_nowait(payload)
            except asyncio.QueueEmpty:
                pass

    async def _classification_worker(self) -> None:
        while True:
            payload = await self._classification_queue.get()
            try:
                async with self._semaphore:
                    event = PulseEventV1.model_validate(payload)
                    try:
                        result = await self.classifier.classify(event)
                        await self.storage.upsert_classification(result.model_dump())
                    except CircuitOpenError:
                        log.warning("classifier circuit open, skipping",
                                    outbox_id=event.outbox_id)
                    except Exception as exc:
                        log.error("classification failed",
                                  outbox_id=event.outbox_id, error=str(exc))
                        # Persist error row so backfill knows we tried
                        await self.storage.upsert_classification({
                            "outbox_id": event.outbox_id, "label": "uncertain",
                            "confidence": 0.0, "reasoning": "",
                            "label_diff": "agree", "model": "minimax-m2-v1",
                            "model_version": None, "cost_usd": 0.0,
                            "latency_ms": 0, "error": str(exc)[:500],
                        })
            finally:
                self._classification_queue.task_done()

    async def _replay_outbox_unconsumed(self, conn: asyncpg.Connection) -> None:
        # Schema reference: migration 144 created events_outbox with PK
        # column "id" (BIGSERIAL), NOT "outbox_id". Confirmed in production
        # schema 2026-05-02 via psql introspection. The Python-side variable
        # _outbox_id is a contract with downstream consumers — we inject it
        # into the payload for dedup/replay correlation.
        rows = await conn.fetch(
            "SELECT id, payload FROM events_outbox "
            "WHERE channel='cell_pulse_observed' AND consumed_at IS NULL "
            "ORDER BY id ASC LIMIT 1000"
        )
        for row in rows:
            try:
                raw = row["payload"]
                payload = raw if isinstance(raw, dict) else json.loads(raw)
                outbox_id = int(row["id"])
                payload["_outbox_id"] = outbox_id
                inserted = await self.storage.insert_pulse_event(payload)
                if inserted:
                    self._enqueue_for_classification(payload)
                await conn.execute(
                    "UPDATE events_outbox SET consumed_at=NOW() WHERE id=$1",
                    outbox_id,
                )
            except Exception as exc:
                log.warning("replay row failed", outbox_id=row["id"], error=str(exc))

    def _on_notify(self, conn, pid, channel, payload_str):
        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError:
            log.warning("invalid notify payload", payload=payload_str[:200])
            return
        # Schedule the async work without blocking the listener
        asyncio.create_task(self._handle_notification(payload))

    async def _handle_notification(self, payload: dict[str, Any]) -> None:
        try:
            inserted = await self.storage.insert_pulse_event(payload)
            if inserted:
                self._enqueue_for_classification(payload)
        except Exception as exc:
            log.error("notification handling failed", error=str(exc))

    async def run(self, db_url: str, num_workers: int = 4) -> None:
        # Start classification workers
        self._classification_workers = [
            asyncio.create_task(self._classification_worker())
            for _ in range(num_workers)
        ]

        while True:
            try:
                conn = await asyncpg.connect(db_url)
                try:
                    await conn.add_listener("cell_pulse_observed", self._on_notify)
                    log.info("listener attached, replaying outbox")
                    await self._replay_outbox_unconsumed(conn)
                    log.info("replay complete, awaiting events")
                    while True:
                        await asyncio.sleep(30)
                        # heartbeat
                        await conn.execute("SELECT 1")
                finally:
                    await conn.close()
            except (asyncpg.PostgresError, OSError) as exc:
                log.warning("listener disconnected, retry in 5s", error=str(exc))
                await asyncio.sleep(5)


async def run_collector():
    """Entrypoint used by __main__."""
    cfg = Config.from_env()
    storage = Storage(db_path=cfg.db_path)
    await storage.init()
    classifier = MinimaxClassifier(api_key=cfg.minimax_api_key)
    collector = Collector(
        storage=storage, classifier=classifier,
        classifier_max_inflight=cfg.classifier_max_inflight,
        classifier_queue_maxsize=cfg.classifier_queue_maxsize,
    )
    try:
        await collector.run(cfg.eventbus_database_url)
    finally:
        await classifier.aclose()
        await storage.close()
