"""Post-deploy probe: the live /evaluate carries the documentation catalogue.

Posts the 20 canonical gold personas to the public evaluate endpoint as
``traffic_source=synthetic_gold`` (driver token read from the operator-owned token
file, never logged) and checks the ``display`` block of every candidate it gets back:
an E33F candidate must carry documentation AVAILABLE with the penjamin letter
("surat penjaminan"), and an E31B candidate must stay UNKNOWN. Both product codes must
be seen at least once, so an empty replay cannot pass.

No arguments: the endpoint, the token path and the checks are literals of the gold
replay driver and of this file. Run from ``apps/backend-rag`` with ``PYTHONPATH=.``.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Iterable, Mapping
from typing import Any

import httpx

from backend.scripts.visa_engine.gold_replay_driver import (
    DRIVER_TOKEN_PATH,
    LIVE_ENDPOINT,
    GoldReplayDriverError,
    _read_driver_token,
    build_persona_payload,
)
from backend.tests.services.visa_engine.test_evaluator_gold import PERSONAS

AVAILABLE_CODE = "E33F"
UNKNOWN_CODE = "E31B"
PENJAMIN_NEEDLE = "surat penjaminan"


def check_documentation(bodies: Iterable[Mapping[str, Any]]) -> list[str]:
    """Return the failures found in the evaluate response bodies (empty means in force)."""

    failures: list[str] = []
    seen: set[str] = set()
    for body in bodies:
        display = body.get("display")
        candidates = display.get("candidates", []) if isinstance(display, Mapping) else []
        for shown in candidates:
            code = shown.get("product_code")
            documentation = shown.get("documentation") or {}
            if code == AVAILABLE_CODE:
                seen.add(code)
                items = documentation.get("requirements", []) + documentation.get("checklist", [])
                if documentation.get("status") != "AVAILABLE":
                    failures.append(f"{code} documentation is {documentation.get('status')!r}")
                elif not any(PENJAMIN_NEEDLE in str(item.get("id", "")).lower() for item in items):
                    failures.append(f"{code} documentation lacks the penjamin letter")
            elif code == UNKNOWN_CODE:
                seen.add(code)
                if documentation.get("status") != "UNKNOWN":
                    failures.append(f"{code} documentation is {documentation.get('status')!r}")
    for code in (AVAILABLE_CODE, UNKNOWN_CODE):
        if code not in seen:
            failures.append(f"no {code} candidate came back from the replay")
    return failures


async def _replay() -> list[Mapping[str, Any]]:
    token = _read_driver_token(DRIVER_TOKEN_PATH)
    bodies: list[Mapping[str, Any]] = []
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
        for persona in PERSONAS:
            response = await client.post(
                LIVE_ENDPOINT,
                params={"traffic_source": "synthetic_gold"},
                headers={"X-Visa-Driver-Token": token},
                json=build_persona_payload(persona),
            )
            if response.status_code != 200:
                raise GoldReplayDriverError(
                    f"live endpoint returned HTTP {response.status_code} for persona {persona.id:02d}"
                )
            bodies.append(response.json())
    return bodies


def main() -> int:
    try:
        failures = check_documentation(asyncio.run(_replay()))
    except (GoldReplayDriverError, httpx.HTTPError, ValueError) as exc:
        print(json.dumps({"ok": False, "failures": [type(exc).__name__ + ": " + str(exc)]}))
        return 1
    print(json.dumps({"ok": not failures, "failures": failures}))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
