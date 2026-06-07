"""Mata Garuda bridge to the repo-wide organism heartbeat writer."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Callable


def _load_writer() -> Callable[[str, str, str], bool] | None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "scripts" / "lib" / "heartbeat.py"
        if not candidate.is_file():
            continue
        spec = importlib.util.spec_from_file_location("organism_heartbeat_lib", candidate)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return getattr(module, "organism_heartbeat", None)
    return None


def organism_heartbeat(organ_id: str, status: str = "ok", note: str = "") -> None:
    writer = _load_writer()
    if writer is None:
        return
    writer(organ_id, status, note)


def run_with_heartbeat(organ_id: str, main: Callable[[], int | None]) -> int:
    organism_heartbeat(organ_id, "starting", "run started")
    try:
        result = main()
    except KeyboardInterrupt:
        organism_heartbeat(organ_id, "degraded", "keyboard interrupt")
        raise
    except Exception as exc:
        organism_heartbeat(organ_id, "error", f"crashed: {exc}")
        raise

    rc = 0 if result is None else int(result)
    organism_heartbeat(organ_id, "ok" if rc == 0 else "error", f"rc={rc}")
    return rc
