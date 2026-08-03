"""infra/vcr/store.py — append-only observation log (VCR spec §3).

Observations are append-only: a ClaimObservation is written once per probe and
never mutated. "Current state" is always a materialized VIEW derived by folding
this log (materializer.py) — never a hand-set value. Env-overridable root
(VCR_STORE_HOME) so tests never touch the real $HOME, mirroring
organism_digest.py's `_home()` pattern.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional

from infra.vcr.records import ClaimContext, ClaimObservation

_UNSAFE = re.compile(r"[^A-Za-z0-9_.-]")


def store_root() -> Path:
    override = os.environ.get("VCR_STORE_HOME")
    base = Path(override) if override else Path.home()
    return base / ".organism" / "vcr" / "observations"


def _slug(text: str) -> str:
    return _UNSAFE.sub("_", text)


def log_path(seat: str, context: ClaimContext) -> Path:
    fname = f"{_slug(seat)}__{_slug(context.host)}__{_slug(context.auth_context)}.jsonl"
    return store_root() / fname


def append_observation(obs: ClaimObservation) -> None:
    path = log_path(obs.subject_id, obs.context)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obs.to_dict(), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def read_observations(
    seat: str, context: ClaimContext, limit: Optional[int] = None
) -> tuple[list[ClaimObservation], list[str]]:
    """Returns (observations oldest-first, error lines for corrupt rows).

    A corrupt line is skipped but reported — never silently dropped (fail-visible,
    same discipline as organism_digest.py's source_errors).
    """
    path = log_path(seat, context)
    if not path.is_file():
        return [], []
    errors: list[str] = []
    obs: list[ClaimObservation] = []
    for i, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            obs.append(ClaimObservation.from_dict(json.loads(raw_line)))
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            errors.append(f"{path.name}:{i + 1} corrupt ({type(e).__name__})")
    if limit is not None:
        obs = obs[-limit:]
    return obs, errors
