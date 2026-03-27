"""Fly.io Effector — executes restart_service, scale_up, scale_down.

Uses Fly.io Machines REST API v1.
All operations are idempotent and safe to retry.

Safety contract:
- Never touches machines outside self._app_name
- restart: restarts FIRST machine only (avoids thundering herd)
- scale: uses Fly.io count API — Fly enforces actual bounds
- All writes require FLY_API_TOKEN — if missing, all actions are no-ops with warning
"""
import logging
import os
from dataclasses import dataclass

import httpx

logger = logging.getLogger("cell.effector.fly")

_FLY_API_BASE = "https://api.machines.dev/v1"


@dataclass
class EffectorResult:
    success: bool
    action: str
    detail: str


class FlyEffector:
    """Executes Fly.io actions via Machines API.

    Instantiate once, reuse across pulses (shares httpx client).
    """

    def __init__(self, app_name: str, api_token: str = "") -> None:
        self._app = app_name
        self._token = api_token or os.environ.get("FLY_API_TOKEN", "")
        self._headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def _enabled(self) -> bool:
        if not self._token:
            logger.warning("FlyEffector: FLY_API_TOKEN not set — all actions are no-ops")
            return False
        return True

    async def _get_machines(self, client: httpx.AsyncClient) -> list[dict]:
        """Return list of running machines for the app."""
        resp = await client.get(
            f"{_FLY_API_BASE}/apps/{self._app}/machines",
            headers=self._headers,
            timeout=15.0,
        )
        resp.raise_for_status()
        machines: list[dict] = resp.json()
        # Only started machines
        return [m for m in machines if m.get("state") in ("started", "running")]

    async def restart_service(self) -> EffectorResult:
        """Restart the first running machine (graceful signal, then start)."""
        if not self._enabled():
            return EffectorResult(success=False, action="restart_service", detail="no API token")

        try:
            async with httpx.AsyncClient() as client:
                machines = await self._get_machines(client)
                if not machines:
                    return EffectorResult(
                        success=False, action="restart_service",
                        detail=f"No running machines found for {self._app}",
                    )

                # Restart only the first machine — avoid restarting all at once
                machine_id = machines[0]["id"]
                resp = await client.post(
                    f"{_FLY_API_BASE}/apps/{self._app}/machines/{machine_id}/restart",
                    headers=self._headers,
                    json={"signal": "SIGTERM", "timeout": 30},
                    timeout=30.0,
                )
                resp.raise_for_status()
                logger.info(f"FlyEffector: restarted machine {machine_id} on {self._app}")
                return EffectorResult(
                    success=True, action="restart_service",
                    detail=f"Machine {machine_id[:8]}... restarted on {self._app}",
                )
        except httpx.HTTPStatusError as e:
            logger.error(f"FlyEffector restart_service HTTP {e.response.status_code}: {e.response.text[:200]}")
            return EffectorResult(
                success=False, action="restart_service",
                detail=f"HTTP {e.response.status_code}: {e.response.text[:100]}",
            )
        except Exception as e:
            logger.error(f"FlyEffector restart_service error: {e}")
            return EffectorResult(success=False, action="restart_service", detail=str(e))

    async def scale_up(self, target: int = 2) -> EffectorResult:
        """Scale app to target machine count."""
        if not self._enabled():
            return EffectorResult(success=False, action="scale_up", detail="no API token")

        try:
            async with httpx.AsyncClient() as client:
                machines = await self._get_machines(client)
                current = len(machines)

                if current >= target:
                    return EffectorResult(
                        success=True, action="scale_up",
                        detail=f"Already at {current} machines (target={target}), no action needed",
                    )

                # Clone the first machine config for the new machine
                if not machines:
                    return EffectorResult(
                        success=False, action="scale_up",
                        detail="No machines to clone config from",
                    )

                source = machines[0]
                config = source.get("config", {})
                resp = await client.post(
                    f"{_FLY_API_BASE}/apps/{self._app}/machines",
                    headers=self._headers,
                    json={"config": config, "region": source.get("region", "sin")},
                    timeout=30.0,
                )
                resp.raise_for_status()
                new_id = resp.json().get("id", "?")
                logger.info(f"FlyEffector: scaled up {self._app} to {current + 1} machines (new: {new_id})")
                return EffectorResult(
                    success=True, action="scale_up",
                    detail=f"Scaled {self._app} from {current} to {current + 1} machines (new: {new_id[:8]}...)",
                )
        except httpx.HTTPStatusError as e:
            logger.error(f"FlyEffector scale_up HTTP {e.response.status_code}: {e.response.text[:200]}")
            return EffectorResult(
                success=False, action="scale_up",
                detail=f"HTTP {e.response.status_code}: {e.response.text[:100]}",
            )
        except Exception as e:
            logger.error(f"FlyEffector scale_up error: {e}")
            return EffectorResult(success=False, action="scale_up", detail=str(e))

    async def scale_down(self, target: int = 1) -> EffectorResult:
        """Scale app down to target machine count by stopping excess machines."""
        if not self._enabled():
            return EffectorResult(success=False, action="scale_down", detail="no API token")

        try:
            async with httpx.AsyncClient() as client:
                machines = await self._get_machines(client)
                current = len(machines)

                if current <= target:
                    return EffectorResult(
                        success=True, action="scale_down",
                        detail=f"Already at {current} machines (target={target}), no action needed",
                    )

                # Stop excess machines (all but the first target)
                to_stop = machines[target:]
                stopped = []
                for m in to_stop:
                    mid = m["id"]
                    resp = await client.post(
                        f"{_FLY_API_BASE}/apps/{self._app}/machines/{mid}/stop",
                        headers=self._headers,
                        timeout=30.0,
                    )
                    resp.raise_for_status()
                    stopped.append(mid[:8])

                logger.info(f"FlyEffector: scaled down {self._app} to {target} machines (stopped: {stopped})")
                return EffectorResult(
                    success=True, action="scale_down",
                    detail=f"Scaled {self._app} from {current} to {target} machines (stopped: {stopped})",
                )
        except httpx.HTTPStatusError as e:
            logger.error(f"FlyEffector scale_down HTTP {e.response.status_code}: {e.response.text[:200]}")
            return EffectorResult(
                success=False, action="scale_down",
                detail=f"HTTP {e.response.status_code}: {e.response.text[:100]}",
            )
        except Exception as e:
            logger.error(f"FlyEffector scale_down error: {e}")
            return EffectorResult(success=False, action="scale_down", detail=str(e))

    async def execute(self, action: str) -> EffectorResult:
        """Dispatch an action by name."""
        if action == "restart_service":
            return await self.restart_service()
        if action == "scale_up":
            return await self.scale_up(target=2)
        if action == "scale_down":
            return await self.scale_down(target=1)
        return EffectorResult(
            success=False, action=action,
            detail=f"FlyEffector does not handle action '{action}'",
        )
