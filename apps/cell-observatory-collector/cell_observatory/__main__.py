"""python -m cell_observatory — entrypoint for LaunchAgent."""
import asyncio
import structlog

from cell_observatory.collector import run_collector
from cell_observatory.api import run_api

structlog.configure(processors=[
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.JSONRenderer(),
])

log = structlog.get_logger()


async def main():
    log.info("cell-observatory-collector starting", version="0.1.0")
    await asyncio.gather(run_collector(), run_api())


if __name__ == "__main__":
    asyncio.run(main())
