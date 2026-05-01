from __future__ import annotations
import asyncio
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Header, HTTPException, Request
from typing import Optional

from cell_observatory.config import Config
from cell_observatory.storage import Storage


async def build_app() -> tuple[FastAPI, Storage]:
    cfg = Config.from_env()
    storage = Storage(db_path=cfg.db_path)
    await storage.init()

    app = FastAPI(title="Cell Observatory API", version="0.1.0")

    def _require_auth(x_observatory_key: Optional[str]) -> None:
        if not cfg.api_key:
            return
        if x_observatory_key != cfg.api_key:
            raise HTTPException(status_code=401, detail="Unauthorized")

    @app.get("/api/observatory/health")
    async def health(x_observatory_key: Optional[str] = Header(None, alias="X-Observatory-Key")):
        _require_auth(x_observatory_key)
        rows = await storage._fetchall("SELECT COUNT(*) AS n FROM pulse_events")
        events_24h = await storage._fetchall(
            "SELECT COUNT(*) AS n FROM pulse_events WHERE pulse_timestamp > ?",
            ((datetime.now(timezone.utc) - timedelta(hours=24)).timestamp() * 1000,),
        )
        return {
            "alive": True, "uptime_s": 0,  # stub for fase 0
            "events_total": rows[0]["n"],
            "events_24h": events_24h[0]["n"],
        }

    @app.get("/api/observatory/pulse")
    async def list_pulses(
        cell_id: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 100,
        x_observatory_key: Optional[str] = Header(None, alias="X-Observatory-Key"),
    ):
        _require_auth(x_observatory_key)
        clauses, params = [], []
        if cell_id:
            clauses.append("cell_id = ?"); params.append(cell_id)
        if since:
            since_ms = int(datetime.fromisoformat(since.replace("Z", "+00:00")).timestamp() * 1000)
            clauses.append("pulse_timestamp >= ?"); params.append(since_ms)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(min(limit, 1000))
        rows = await storage._fetchall(
            f"SELECT outbox_id, cell_id, pulse_id, pulse_timestamp, classifier_self "
            f"FROM pulse_events {where} ORDER BY pulse_timestamp DESC LIMIT ?",
            tuple(params),
        )
        return {"items": rows}

    @app.get("/api/observatory/anomalies")
    async def anomalies(
        since: Optional[str] = None,
        label: Optional[str] = None,
        x_observatory_key: Optional[str] = Header(None, alias="X-Observatory-Key"),
    ):
        _require_auth(x_observatory_key)
        clauses, params = [], []
        if label:
            clauses.append("c.label = ?"); params.append(label)
        else:
            clauses.append("c.label IN ('anomaly', 'critical', 'uncertain')")
        if since:
            since_ms = int(datetime.fromisoformat(since.replace("Z", "+00:00")).timestamp() * 1000)
            clauses.append("c.classified_at >= ?"); params.append(since_ms)
        where = "WHERE " + " AND ".join(clauses)
        rows = await storage._fetchall(
            f"SELECT c.outbox_id, c.label, c.confidence, c.reasoning, c.label_diff, "
            f"e.cell_id, e.pulse_timestamp "
            f"FROM pulse_classifications c JOIN pulse_events e ON e.outbox_id = c.outbox_id "
            f"{where} ORDER BY c.confidence DESC LIMIT 100",
            tuple(params),
        )
        return {"items": rows}

    @app.get("/api/observatory/rollup")
    async def rollup(
        day: str,
        cell_id: Optional[str] = None,
        x_observatory_key: Optional[str] = Header(None, alias="X-Observatory-Key"),
    ):
        _require_auth(x_observatory_key)
        if cell_id:
            rows = await storage._fetchall(
                "SELECT * FROM pulse_daily_rollup WHERE day = ? AND cell_id = ?", (day, cell_id),
            )
        else:
            rows = await storage._fetchall("SELECT * FROM pulse_daily_rollup WHERE day = ?", (day,))
        return {"items": rows}

    @app.get("/api/observatory/cost")
    async def cost(
        since: Optional[str] = None,
        x_observatory_key: Optional[str] = Header(None, alias="X-Observatory-Key"),
    ):
        _require_auth(x_observatory_key)
        params = []
        clause = ""
        if since:
            since_ms = int(datetime.fromisoformat(since.replace("Z", "+00:00")).timestamp() * 1000)
            clause = "WHERE classified_at >= ?"
            params.append(since_ms)
        rows = await storage._fetchall(
            f"SELECT SUM(cost_usd) AS total, COUNT(*) AS calls FROM pulse_classifications {clause}",
            tuple(params),
        )
        return {"total_usd": rows[0]["total"] or 0.0, "calls": rows[0]["calls"] or 0,
                "alert_threshold_usd": cfg.cost_alert_threshold_usd}

    return app, storage


async def run_api() -> None:
    """Entrypoint used by __main__."""
    import uvicorn
    cfg = Config.from_env()
    app, _ = await build_app()
    config = uvicorn.Config(app, host="127.0.0.1", port=cfg.api_port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()
