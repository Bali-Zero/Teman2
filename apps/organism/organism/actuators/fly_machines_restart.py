"""Actuator: restart a Fly.io machine via `fly machines restart`.

Used when a Fly machine is in `started` state but unhealthy (failing
health checks). `fly machines start` is a no-op on already-started
machines, so the W27 outage pattern (Cell observing sustained-red on
backend api machine) needs the restart primitive instead.

W31 (2026-05-23) — follow-up to W27 live outage test where
cell_pulse_sustained_red dispatched fly_machines_start → no-op because
machine was "started, 0/1 critical checks". Manual `fly machine restart`
fixed it. This actuator closes the loop.

Params:
  app:        Fly app name (mandatory; e.g. "nuzantara-rag")
  machine:    optional machine id — when provided, restarts only that
              machine; when omitted, fly restarts ALL machines in the app
              (be careful, prefer scoping to a specific machine_id)
  skip_health_checks:
              optional bool — if True, pass --skip-health-checks to fly
              CLI so the restart command returns immediately instead of
              waiting up to 120s for health checks to pass. Default False
              (safer; let fly verify recovery).

Behaviour:
  Shells out to `fly machines restart -a <app> [<machine>]
  [--skip-health-checks]` with a 180s timeout (longer than start because
  fly waits for health checks by default). Soft-failure on non-zero exit.

  Idempotency: `fly machines restart` is idempotent — a second call
  during cooldown is wasteful but harmless. Anti-loop guards live at
  the yaml-rule level (cooldown_minutes) and at the cell-emit level
  (_sustained_red_emitted flag), not here.

Anti-pattern:
  Do NOT call this on every red pulse. Cell now emits
  cell_pulse_sustained_red only after THRESHOLD=3 consecutive red pulses
  AND only ONCE per recovery (until pulse goes non-red and resets the
  flag). The yaml rule MUST set cooldown_minutes to prevent restart loops
  during a slow startup window (>2min uvicorn warmup).
"""
import asyncio
import os

from organism.actuators.base import ActuatorBase


class FlyMachinesRestart(ActuatorBase):
    name = "fly_machines_restart"

    def _build_argv(self, params: dict) -> list[str]:
        app = params["app"]
        argv = ["fly", "machines", "restart", "-a", app]
        machine = params.get("machine") or params.get("machine_id")
        if machine:
            argv.append(str(machine))
        if params.get("skip_health_checks"):
            argv.append("--skip-health-checks")
        return argv

    async def _execute(self, params: dict) -> dict:
        if "app" not in params:
            raise ValueError("fly_machines_restart requires 'app' in params")
        argv = self._build_argv(params)
        env = os.environ.copy()
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=180.0)
        except asyncio.TimeoutError as exc:
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
            raise RuntimeError(
                f"fly machines restart timed out after 180s (argv={argv})"
            ) from exc
        return {
            "argv": argv,
            "returncode": proc.returncode,
            "stdout": out.decode("utf-8", errors="replace")[:1000],
            "stderr": err.decode("utf-8", errors="replace")[:1000],
        }

    async def _dry_run(self, params: dict) -> dict:
        if "app" not in params:
            return {"would_restart": "<missing app param>"}
        return {"would_run": self._build_argv(params)}
