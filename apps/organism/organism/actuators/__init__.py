"""Actuator registry factory.

Resolves the asymmetry that Quarantine requires a Redis client while
other actuators don't. Dispatchers (W1.C/W2) call build_actuator_registry(redis)
once at startup to get a {name: instance} map.
"""
from organism.actuators.base import ActuatorBase
from organism.actuators.restart_agent import RestartAgent
from organism.actuators.cleanup_log import CleanupLog
from organism.actuators.notify_telegram import NotifyTelegram
from organism.actuators.quarantine import Quarantine
from organism.actuators.adopt_module import AdoptModule
from organism.actuators.consolidate_redundancy import ConsolidateRedundancy
from organism.actuators.propose_yaml_rule import ProposeYamlRule


__all__ = [
    "ActuatorBase",
    "RestartAgent",
    "CleanupLog",
    "NotifyTelegram",
    "Quarantine",
    "AdoptModule",
    "ConsolidateRedundancy",
    "ProposeYamlRule",
    "build_actuator_registry",
]


def build_actuator_registry(*, redis) -> dict[str, ActuatorBase]:
    """Return a {actuator_name: instance} map, pre-wired with shared Redis.

    Used by W1.C Dispatcher / W2 main supervisor loop. Quarantine and
    AdoptModule get the shared redis client; others don't need one.
    ProposeYamlRule is zero-arg — it shells out to git/gh subprocesses
    and does not need the redis bus.
    """
    return {
        RestartAgent.name: RestartAgent(),
        CleanupLog.name: CleanupLog(),
        NotifyTelegram.name: NotifyTelegram(),
        Quarantine.name: Quarantine(redis=redis),
        AdoptModule.name: AdoptModule(redis=redis),
        ConsolidateRedundancy.name: ConsolidateRedundancy(),
        ProposeYamlRule.name: ProposeYamlRule(),
    }
