"""MODEL_TOPOLOGY.json loader — single import for all consumers."""
import json
import socket
from pathlib import Path

_TOPOLOGY_PATH = Path(__file__).parent.parent / "MODEL_TOPOLOGY.json"
_CACHE: dict | None = None


def load() -> dict:
    global _CACHE
    if _CACHE is None:
        _CACHE = json.loads(_TOPOLOGY_PATH.read_text())
    return _CACHE


def get_role(role: str) -> str:
    """Get model name for a role. E.g. get_role('cron_primary') -> 'qwen3.5:9b'"""
    return load()["roles"][role]


def get_node() -> dict:
    """Get config for current node based on hostname."""
    hostname = socket.gethostname()
    topo = load()
    for node in topo["nodes"].values():
        if node["hostname"] == hostname:
            return node
    raise ValueError(f"Unknown host: {hostname}")


def get_warm_model() -> str:
    """Get the warm model for current node."""
    return get_node()["warm_model"]
