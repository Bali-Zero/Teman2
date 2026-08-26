"""rebind_accepted_explanations.py — carry accepted gold explanations across a
pack re-signing, and REFUSE to carry any whose divergence changed.

WHY THIS EXISTS

`gold_replay_driver._matching_explanation` binds every accepted explanation to
the exact pack it was accepted against (`rule_pack_id`, `sequence`, `version`,
`payload_sha256`). Sign a new pack and all of them detach at once — the gate
drops to `explained 0` and `overall_pass: false`. That is anti-staleness working
as designed, not a defect: an explanation is a human judgement about a SPECIFIC
divergence, and a new pack may have changed what diverges.

The wrong cure is to rewrite the hash. That silently re-attaches a judgement to
a divergence nobody re-read — the explanation would then describe something that
no longer happens, and the gate would go green over it.

The right cure, and what this script does: carry an explanation forward ONLY if
the divergence it explains is byte-identical under the new pack. Anything that
moved is dropped LOUDLY and has to be re-judged by a human.

USAGE (two steps — this script does not write the final artifact)

    # 1. replay the freshly signed pack
    PYTHONPATH=. python -m backend.scripts.visa_engine.gold_replay_driver \
        --offline --out /tmp/replay.json

    # 2. carry the explanations onto it, refusing any whose core moved
    PYTHONPATH=. python -m backend.scripts.visa_engine.rebind_accepted_explanations \
        --accepted backend/services/visa_engine/contracts/gold-accepted-explanations.json \
        --report /tmp/replay.json --out /tmp/rebound.json

    # 3. regenerate the real artifact THROUGH the driver, so the file it writes
    #    is a fixed point of the driver rather than something assembled by hand
    PYTHONPATH=. python -m backend.scripts.visa_engine.gold_replay_driver \
        --offline --accepted-explanations /tmp/rebound.json \
        --out backend/services/visa_engine/contracts/gold-accepted-explanations.json

Step 3 is not optional. Hand-injecting explanations produced a file that
contradicted its own `summary` once already (2026-08-26): the persona rows
carried explanations while the counts still described the state before them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

#: The fields that DEFINE the divergence an explanation was accepted against.
#: If any of these moved, the explanation is about something that no longer
#: happens and must not be carried.
_CORE_FIELDS = ("divergence", "expected", "actual", "differences")


class RebindError(RuntimeError):
    """A carried explanation no longer describes what the engine does."""


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _by_id(personas: list[dict[str, Any]]) -> dict[Any, dict[str, Any]]:
    out: dict[Any, dict[str, Any]] = {}
    for persona in personas:
        pid = persona.get("persona_id")
        if pid in out:
            raise RebindError(f"duplicate persona_id {pid!r}")
        out[pid] = persona
    return out


def rebind(accepted: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    new_pack = report.get("pack")
    if not new_pack:
        raise RebindError("report carries no `pack` block — refusing to rebind to nothing")

    old_by_id = _by_id(accepted.get("personas") or [])
    new_personas = report.get("personas") or []
    if not new_personas:
        raise RebindError("report carries no personas")

    carried: list[Any] = []
    dropped: list[str] = []

    for persona in new_personas:
        pid = persona.get("persona_id")
        old = old_by_id.get(pid)
        if old is None or old.get("explanation") in (None, ""):
            continue

        moved = [f for f in _CORE_FIELDS if _canon(old.get(f)) != _canon(persona.get(f))]
        if moved:
            dropped.append(
                f"persona {pid}: {', '.join(moved)} changed under the new pack — "
                "the accepted explanation describes a divergence that no longer occurs"
            )
            continue

        # Carry the EXPLANATION STRING ONLY. Never touch `persona["pack"]`: the
        # fresh report already stamped each row with the pack it replayed, and
        # `_matching_explanation` compares that block by EXACT dict equality.
        # The first draft of this script copied the TOP-LEVEL pack block in —
        # which carries one extra key, `consistent_across_personas` — so every
        # comparison failed and all 15 explanations were dropped SILENTLY (the
        # matcher returns None; nothing raises). The regenerated file came back
        # `explained 0`, which reads exactly like a real detachment instead of
        # a bug in this script.
        persona["explanation"] = old["explanation"]
        carried.append(pid)

    if dropped:
        raise RebindError(
            "refusing to rebind — "
            f"{len(dropped)} accepted explanation(s) no longer match their divergence:\n  "
            + "\n  ".join(dropped)
            + "\n\nThese must be re-judged by a human, not carried."
        )

    out = dict(report)
    out["personas"] = new_personas
    print(
        f"carried {len(carried)} explanation(s) onto pack "
        f"seq={new_pack.get('sequence')} sha={str(new_pack.get('payload_sha256'))[:16]}… "
        f"— personas {carried}",
        file=sys.stderr,
    )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--accepted", required=True, help="current accepted-explanations JSON")
    parser.add_argument("--report", required=True, help="fresh replay report against the new pack")
    parser.add_argument("--out", required=True, help="where to write the rebound intermediate")
    args = parser.parse_args(argv)

    accepted = json.loads(Path(args.accepted).read_text(encoding="utf-8"))
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    rebound = rebind(accepted, report)
    Path(args.out).write_text(
        json.dumps(rebound, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
