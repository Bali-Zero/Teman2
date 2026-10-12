#!/usr/bin/env python3
"""Print the Visa Oracle holiday-coverage assessment as one JSON line.

Run by `scripts/visa_freshness_sentinel.py` under its own bare python3: the decree table, the
processing windows and the working-day walk are stdlib-only, so no venv is needed.

`backend.services.compliance.__init__` pulls the whole app settings (DB, JWT, API keys) just to
reach `business_days`, which is pure. The probe therefore registers that package as an empty
namespace so its submodule loads without running the heavy `__init__`: the probe needs the decree
table, not an app configuration.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import types
from datetime import date, datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "apps" / "backend-rag"


def _load_assess():
    sys.path.insert(0, str(BACKEND))
    pkg = "backend.services.compliance"
    if pkg not in sys.modules:
        stub = types.ModuleType(pkg)
        stub.__path__ = [str(BACKEND / "backend" / "services" / "compliance")]
        sys.modules[pkg] = stub
    return importlib.import_module("backend.services.visa_engine.holiday_coverage").assess


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--today", default=None, help="ISO date override (tests only).")
    args = parser.parse_args(argv)
    today = date.fromisoformat(args.today) if args.today else datetime.now(timezone.utc).date()
    print(json.dumps(_load_assess()(today), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
