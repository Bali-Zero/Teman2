"""Actuator: restart a launchd-managed agent via launchctl kickstart.

Resolves `agent_ref` to a launchd label, in priority order:
1. **Genome lookup (authoritative)** — if `agent_ref` matches an organ `id` in
   organs_registry.yaml, use that organ's `recovery_params.label`. This is the
   real launchd label (e.g. `pro.dlq_autopilot` → `com.nuzantara.dlq-autopilot`).
2. Already a launchd label — if it has a dot AND looks like a launchd label
   (starts with a reverse-DNS namespace `com.`/`homebrew.`/etc.), pass as-is.
3. Otherwise prefix with `com.balizero.` (legacy namespace convention).

Why the genome lookup exists (W: A2 dead-letter, 2026-06-27): the supervisor's
heartbeat_silent events carry `agent_ref = "<node>.<organ>"` (e.g.
`pro.dlq_autopilot`) — an ORGAN ID, NOT a launchd label. The old resolver saw a
dot and used it as-is, so `launchctl kickstart gui/<uid>/pro.dlq_autopilot`
fired at a label that does not exist → kickstart no-op → the organ stayed dead →
re-flagged every tick. The genome carries the true label; read it.

Then invokes:
    launchctl kickstart -k gui/<uid>/<label>

The `-k` flag forcibly restarts a running service; absence of the service is
surfaced via non-zero returncode plus stderr — we do NOT raise on that case,
so the caller can treat "agent not loaded" as a soft failure.
"""
import asyncio
import os
from functools import lru_cache
from pathlib import Path

import yaml

from organism.actuators.base import ActuatorBase

# Reverse-DNS namespaces that mark a string as an already-resolved launchd label.
_LAUNCHD_NAMESPACES = ("com.", "homebrew.", "org.", "io.", "net.")

_DEFAULT_GENOME = (
    Path(__file__).resolve().parents[2] / "organism" / "organs_registry.yaml"
)


@lru_cache(maxsize=1)
def _organ_label_map() -> dict[str, str]:
    """Map organ `id` -> launchd label from the genome's recovery_params.

    Cached for the process lifetime. Path overridable via ORGANISM_GENOME_PATH
    (falls back to ORGANISM_RULES_PATH's sibling, then the package default) so a
    test or an alternate runtime root resolves the right registry.
    """
    candidates = []
    env_path = os.getenv("ORGANISM_GENOME_PATH")
    if env_path:
        candidates.append(Path(env_path).expanduser())
    rules_path = os.getenv("ORGANISM_RULES_PATH")
    if rules_path:
        candidates.append(Path(rules_path).expanduser().parents[1] / "organs_registry.yaml")
    candidates.append(_DEFAULT_GENOME)

    for path in candidates:
        try:
            data = yaml.safe_load(path.read_text()) or {}
        except (OSError, yaml.YAMLError):
            continue
        organs = data.get("organs", []) if isinstance(data, dict) else []
        mapping: dict[str, str] = {}
        for organ in organs:
            if not isinstance(organ, dict):
                continue
            oid = organ.get("id")
            label = (organ.get("recovery_params") or {}).get("label")
            if oid and label:
                mapping[oid] = label
        if mapping:
            return mapping
    return {}


class RestartAgent(ActuatorBase):
    name = "restart_agent"

    def _label(self, agent_ref: str) -> str:
        # 1. Authoritative: organ_id -> launchd label from the genome.
        genome_label = _organ_label_map().get(agent_ref)
        if genome_label:
            return genome_label
        # 2. Already a launchd label (reverse-DNS namespace prefix).
        if agent_ref.startswith(_LAUNCHD_NAMESPACES):
            return agent_ref
        # 3. Legacy namespace convention.
        return f"com.balizero.{agent_ref}"

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
