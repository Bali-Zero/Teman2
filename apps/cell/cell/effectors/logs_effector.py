"""Logs Effector — fetches recent Fly.io logs via Machines API.

Used when CELL's action is 'read_logs' — fetches the last N lines
from the app's log stream and stores a summary to cell_alerts table
so the dashboard can show what CELL found.
"""
import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger("cell.effector.logs")

_FLY_API_BASE = "https://api.machines.dev/v1"


@dataclass
class LogsResult:
    success: bool
    lines: list[str]
    summary: str
    detail: str


class LogsEffector:
    """Fetches Fly.io machine logs for the monitored app."""

    def __init__(self, app_name: str, api_token: str = "") -> None:
        self._app = app_name
        self._token = api_token
        self._headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def _enabled(self) -> bool:
        if not self._token:
            logger.warning("LogsEffector: FLY_API_TOKEN not set — read_logs is a no-op")
            return False
        return True

    async def read_logs(self, limit: int = 50) -> LogsResult:
        """Fetch recent log lines from the Fly.io app."""
        if not self._enabled():
            return LogsResult(
                success=False, lines=[], summary="",
                detail="No API token — logs unavailable",
            )

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                # Get machines list first
                resp = await client.get(
                    f"{_FLY_API_BASE}/apps/{self._app}/machines",
                    headers=self._headers,
                )
                resp.raise_for_status()
                machines = [m for m in resp.json() if m.get("state") in ("started", "running")]

                if not machines:
                    return LogsResult(
                        success=False, lines=[], summary="",
                        detail=f"No running machines for {self._app}",
                    )

                machine_id = machines[0]["id"]

                # Fetch logs via NATS/SSE stream — use the logs endpoint
                # Fly.io logs endpoint returns newline-delimited JSON events
                logs_resp = await client.get(
                    f"{_FLY_API_BASE}/apps/{self._app}/machines/{machine_id}/logs",
                    headers=self._headers,
                    params={"limit": limit, "_json": "true"},
                )

                lines: list[str] = []
                if logs_resp.status_code == 200:
                    for raw_line in logs_resp.text.splitlines():
                        raw_line = raw_line.strip()
                        if not raw_line or raw_line.startswith("data: "):
                            # SSE format
                            raw_line = raw_line.removeprefix("data: ").strip()
                        if raw_line:
                            lines.append(raw_line)
                    lines = lines[-limit:]

                if not lines:
                    # Fallback: summary from machine state
                    return LogsResult(
                        success=True, lines=[],
                        summary=f"Machine {machine_id[:8]} state=started, no log lines returned",
                        detail="Logs stream empty (machine may have just started)",
                    )

                # Extract ERROR/WARN lines for summary
                errors = [line for line in lines if any(kw in line.upper() for kw in ("ERROR", "CRITICAL", "EXCEPTION", "TRACEBACK"))]
                warns = [line for line in lines if "WARN" in line.upper() and line not in errors]

                if errors:
                    summary = f"{len(errors)} errors in last {len(lines)} lines: {errors[0][:120]}"
                elif warns:
                    summary = f"{len(warns)} warnings in last {len(lines)} lines: {warns[0][:120]}"
                else:
                    summary = f"Last {len(lines)} lines clean (no errors/warnings)"

                logger.info(f"LogsEffector: fetched {len(lines)} lines, {len(errors)} errors, {len(warns)} warnings")
                return LogsResult(
                    success=True, lines=lines, summary=summary,
                    detail=f"machine={machine_id[:8]}, lines={len(lines)}, errors={len(errors)}",
                )

        except httpx.HTTPStatusError as e:
            logger.error(f"LogsEffector HTTP {e.response.status_code}: {e.response.text[:200]}")
            return LogsResult(
                success=False, lines=[], summary="",
                detail=f"HTTP {e.response.status_code}: {e.response.text[:100]}",
            )
        except Exception as e:
            logger.error(f"LogsEffector error: {e}")
            return LogsResult(success=False, lines=[], summary="", detail=str(e))
