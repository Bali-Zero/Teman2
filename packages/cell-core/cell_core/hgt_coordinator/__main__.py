"""Allow ``python -m cell_core.hgt_coordinator`` to dispatch to the CLI.

Both ``python -m cell_core.hgt_coordinator.cli ...`` and
``python -m cell_core.hgt_coordinator ...`` work — useful so the
OpenClaw agent prompt can stay compact.
"""
from __future__ import annotations

from cell_core.hgt_coordinator.cli import main

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
