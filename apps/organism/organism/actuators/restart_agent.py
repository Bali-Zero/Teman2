"""Actuator: restart a launchd-managed agent via launchctl kickstart.

Resolves `agent_ref`:
- If it already contains a dot (e.g. `com.third.party.foo`) it's treated as a
  full launchd label and passed through as-is.
- Otherwise it's prefixed with `com.balizero.` (our namespace convention).

Then invokes:
    launchctl kickstart -k gui/<uid>/<label>

The `-k` flag forcibly restarts a running service; absence of the service is
surfaced via non-zero returncode plus stderr — we do NOT raise on that case,
so the caller can treat "agent not loaded" as a soft failure.
"""
import asyncio
import os

from organism.actuators.base import ActuatorBase


class RestartAgent(ActuatorBase):
    name = "restart_agent"

    def _label(self, agent_ref: str) -> str:
        return agent_ref if "." in agent_ref else f"com.balizero.{agent_ref}"

    async def _execute(self, params: dict) -> dict:
        agent_ref = params["agent_ref"]
        label = self._label(agent_ref)
        proc = await asyncio.create_subprocess_exec(
            "launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{label}",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=30.0)
        except asyncio.TimeoutError as exc:
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
            raise RuntimeError(
                f"launchctl kickstart timed out after 30s (label={label})"
            ) from exc
        return {
            "agent_ref": agent_ref, "label": label,
            "returncode": proc.returncode,
            "stdout": out.decode("utf-8", errors="replace")[:500],
            "stderr": err.decode("utf-8", errors="replace")[:500],
        }

    async def _dry_run(self, params: dict) -> dict:
        return {"would_kickstart": self._label(params["agent_ref"])}
