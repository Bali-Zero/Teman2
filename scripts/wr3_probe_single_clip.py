#!/usr/bin/env python3
"""Retired WR3 probe entrypoint.

The historical implementation called private FlowKit generation primitives
directly and could create a second paid workflow when an operator meant to
recover an existing result. Keep the filename as a fail-closed compatibility
shim so stale runbooks cannot silently spend credits.
"""

from __future__ import annotations

import json


def main() -> int:
    print(
        json.dumps(
            {
                "status": "HALT",
                "reason": "legacy_paid_probe_entrypoint_retired",
                "automatic_generation_forbidden": True,
                "generate_with": "scripts/wr3_camera_probe_run.py",
                "recover_with": "scripts/wr3_camera_probe_recover.py",
            }
        )
    )
    return 64


if __name__ == "__main__":
    raise SystemExit(main())
