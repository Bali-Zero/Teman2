"""Actuator: start a Fly.io machine via `fly machines start`.

Used to recover the 7 organs in organs_registry.yaml whose
recovery_action == "fly_machines_start" (infra.postgres, infra.qdrant,
backend.api, channel.whatsapp, channel.telegram, channel.instagram,
channel.web). Wave-5 closes the dead-letter on these — before this
actuator existed, the Supervisor received the heartbeat_silent event
and could not act on it.

Params:
  app:      Fly app name (mandatory; e.g. "nuzantara-rag")
  machine:  optional machine id (when omitted, fly auto-routes to all
            stopped machines in the app — same as `fly machines start -a APP`
            without --machine)

Behaviour:
  Shells out to `fly machines start -a <app> [<machine>]` with a 60s
  timeout. The Fly API returns ~immediately once the start request is
  accepted; actual cold-start takes seconds-to-minutes. We do NOT wait
  for the machine to be `started` here — the next sentinel cycle will
  pick it up via heartbeat freshness. Soft-failure on non-zero exit
  (returncode + stdout + stderr surfaced) so the caller decides.
"""
import asyncio
import os

from organism.actuators.base import ActuatorBase


class FlyMachinesStart(ActuatorBase):
    name = "fly_machines_start"

    def _build_argv(self, params: dict) -> list[str]:
        app = params["app"]
        argv = ["fly", "machines", "start", "-a", app]
        machine = params.get("machine") or params.get("machine_id")
        if machine:
            argv.append(str(machine))
        return argv

    async def _execute(self, params: dict) -> dict:
        if "app" not in params:
            raise ValueError("fly_machines_start requires 'app' in params")
        argv = self._build_argv(params)
        # Inherit FLY_API_TOKEN / FLY_ACCESS_TOKEN from environment so the
        # supervisor process must already have them sourced (it does — see
        # com.nuzantara.organism.supervisor plist EnvironmentVariables).
        env = os.environ.copy()
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=60.0)
        except asyncio.TimeoutError as exc:
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
            raise RuntimeError(
                f"fly machines start timed out after 60s (argv={argv})"
            ) from exc
        return {
            "argv": argv,
            "returncode": proc.returncode,
            "stdout": out.decode("utf-8", errors="replace")[:1000],
            "stderr": err.decode("utf-8", errors="replace")[:1000],
        }

    async def _dry_run(self, params: dict) -> dict:
        if "app" not in params:
            return {"would_start": "<missing app param>"}
        return {"would_run": self._build_argv(params)}
