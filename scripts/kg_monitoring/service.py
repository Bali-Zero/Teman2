#!/usr/bin/env python3
"""
KG Monitoring Service - Standalone Service

Runs the monitoring service as a standalone process.
Can be managed by systemd, supervisor, or Docker.

Features:
- Periodic monitoring runs
- Health check endpoint
- Graceful shutdown
- Metrics export

Usage:
    python service.py [--port PORT] [--interval INTERVAL]
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException
from uvicorn import Config, Server

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("kg_monitoring.service")

# Global state
service_state = {
    "running": False,
    "last_run": None,
    "next_run": None,
    "total_runs": 0,
    "errors_count": 0,
}


class KGMonitoringService:
    """Standalone monitoring service"""

    def __init__(
        self,
        check_interval_minutes: int = 60,
        max_pages: int = 5,
    ):
        self.check_interval = check_interval_minutes
        self.max_pages = max_pages
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None

    async def start(self):
        """Start the service"""
        logger.info("🚀 Starting KG Monitoring Service")
        logger.info(f"   Check interval: {self.check_interval} minutes")
        logger.info(f"   Max pages: {self.max_pages}")

        service_state["running"] = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self):
        """Stop the service gracefully"""
        logger.info("🛑 Stopping KG Monitoring Service...")
        service_state["running"] = False
        self._stop_event.set()

        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=30)
            except asyncio.TimeoutError:
                logger.warning("Service stop timed out, forcing...")
                self._task.cancel()

        logger.info("✅ Service stopped")

    async def run_once(self) -> dict:
        """Run monitoring once"""
        from cron_runner import run_monitoring

        logger.info("🔄 Running manual check...")
        service_state["last_run"] = datetime.now().isoformat()

        try:
            results = await run_monitoring(
                check_only=False,
                max_pages=self.max_pages,
            )
            service_state["total_runs"] += 1
            return results

        except Exception as e:
            logger.error(f"Monitoring run failed: {e}")
            service_state["errors_count"] += 1
            raise

    async def _run_loop(self):
        """Main service loop"""
        while service_state["running"] and not self._stop_event.is_set():
            try:
                service_state["next_run"] = (
                    datetime.now() + __import__("datetime").timedelta(minutes=self.check_interval)
                ).isoformat()

                await self.run_once()

                # Wait for next interval
                logger.info(f"⏳ Next check in {self.check_interval} minutes")
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self.check_interval * 60,
                    )
                except asyncio.TimeoutError:
                    pass  # Normal timeout, continue loop

            except Exception as e:
                logger.error(f"Error in service loop: {e}")
                service_state["errors_count"] += 1
                await asyncio.sleep(60)  # Wait 1 min before retry


# FastAPI app for health checks and manual triggers
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage service lifecycle"""
    # Startup
    service = KGMonitoringService()
    await service.start()
    app.state.service = service

    yield

    # Shutdown
    await service.stop()


app = FastAPI(
    title="KG Monitoring Service",
    description="Knowledge Graph monitoring and auto-ingestion service",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy" if service_state["running"] else "unhealthy",
        "running": service_state["running"],
        "last_run": service_state["last_run"],
        "next_run": service_state["next_run"],
        "total_runs": service_state["total_runs"],
        "errors": service_state["errors_count"],
    }


@app.post("/run")
async def trigger_run():
    """Trigger a manual monitoring run"""
    try:
        service = app.state.service
        results = await service.run_once()
        return {
            "status": "success",
            "results": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status")
async def get_status():
    """Get detailed service status"""
    return {
        "service": service_state,
        "config": {
            "interval_minutes": app.state.service.check_interval if hasattr(app.state, "service") else None,
            "max_pages": app.state.service.max_pages if hasattr(app.state, "service") else None,
        },
    }


def handle_signals():
    """Setup signal handlers"""
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}")
        asyncio.create_task(app.state.service.stop())
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="KG Monitoring Service")
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="HTTP port for health checks (default: 8080)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Check interval in minutes (default: 60)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="Max pages to scrape per source (default: 5)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )

    args = parser.parse_args()

    # Setup signal handlers
    handle_signals()

    # Create service config
    service = KGMonitoringService(
        check_interval_minutes=args.interval,
        max_pages=args.max_pages,
    )

    # Create uvicorn config
    config = Config(
        app=app,
        host=args.host,
        port=args.port,
        log_level="info",
    )

    # Run
    server = Server(config)

    try:
        asyncio.run(server.serve())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")


if __name__ == "__main__":
    main()
