#!/usr/bin/env bash
set -euo pipefail
mkdir -p ~/.cell-observatory ~/logs/cell-observatory
set -a; source ~/.nuzantara-secrets.env; set +a
~/Desktop/nuzantara/apps/cell-observatory-collector/.venv/bin/python \
    -c "
import asyncio
from cell_observatory.storage import Storage
from cell_observatory.config import Config

async def main():
    cfg = Config.from_env()
    s = Storage(db_path=cfg.db_path)
    await s.init()
    await s.close()

asyncio.run(main())
"
echo "DB initialized at ~/.cell-observatory/observatory.db"
