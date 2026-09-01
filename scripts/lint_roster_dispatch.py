#!/usr/bin/env python3
"""lint_roster_dispatch.py — every MODEL_ROSTER.md model id must resolve to a door.

THE DEFECT THIS KILLS (scar family #2, "Esiste != Armato" — cron theater / blind
autopilot — applied to a doc instead of a daemon): MODEL_ROSTER.md documented
seven live TP1 text models (deepseek-v4-pro, deepseek-v4-flash-0731, glm-5.2,
qwen3.8-max, qwen3.7-max, qwen3.7-plus, qwen3.6-flash) with strengths and effort
notes, and none of them had an invocation path anywhere on disk before this PR —
an orchestrator could read the roster and believe it, but not act on it.
scripts/arsenal_probe.py's own last board recorded this precisely: "tp1-*: no
door: line in roster", 3 of 16 seats covered. A roster row "exists" as prose;
whether it is "armed" (a caller can actually reach it) is a separate,
mechanically-checkable fact this script makes explicit instead of assumed.

WHAT COUNTS AS "A ROSTER ROW MAKING A DISPATCH CLAIM": only a markdown table
row whose FIRST cell is a backtick-quoted token (`| `id` | ...`). This is
deliberately narrower than "every backtick span in the file" — MODEL_ROSTER.md
also uses backticks inside prose paragraphs (the qwen-seat-fleet probe
journal's inline lists) and inside a plain bulleted list (the Local Ollama
section uses a line shaped like "- `model` — ...", not a table), and neither is a roster entry
claiming a dispatch door.

DOOR TYPES, checked in this order — see resolve_door()'s docstring for exactly
why each rule exists:
  1. `claude-*`                       -> the `claude` CLI (any alias resolves).
  2. one of the 7 live TP1 text slugs -> scripts/review_routes/<id>-v1.json
                                          must exist on disk (mechanical).
  3. `sol` / `terra` / `luna`         -> the codex CLI via PR #5044's `--seat
                                          codex --tier <id>` (-> `-m
                                          gpt-5.6-<id>`). The BARE `-m <id>`
                                          slug went dead 2026-07-21 (MODEL_
                                          ROSTER.md's OpenAI section) but the
                                          versioned door is live — verified
                                          2026-08-27 (see MODEL_ROSTER.md's
                                          row-level evidence per slug).
  4. `$imagegen`                      -> the `codex` CLI ($imagegen shortcut).
  5. an id containing "gemini"        -> the `agy` CLI.
  6. `k3` or an id starting `kimi-`   -> the `kimi` CLI.
  7. a known Ollama role value (read live from MODEL_TOPOLOGY.json's own
     `roles` mapping — never a hand-maintained second list that could drift).
  8. none of the above                -> the row's own line must carry the
     literal token `UNREACHABLE`, or it is an offender.

Exit codes: 0 = every row has a door or an UNREACHABLE marker · 1 = at least one
offender · 2 = operational error (roster/topology file unreadable, or 0 rows
parsed — the blind-scan guard, scar W84: a check that silently validated
nothing is not the same as a check that found everything clean).

`--fixture PATH` swaps the live MODEL_ROSTER.md + MODEL_TOPOLOGY.json reads for
a local JSON file (`{"roster": "<markdown>", "ollama_roles": [...], "route_files":
[...]}`) — real, fast, offline tests instead of ones that depend on repo state,
matching the pattern in lint_scar_number_collision.py's own `--fixture` arm.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Callable, NamedTuple, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROSTER_PATH = REPO_ROOT / "MODEL_ROSTER.md"
DEFAULT_TOPOLOGY_PATH = REPO_ROOT / "MODEL_TOPOLOGY.json"
ROUTE_DIR = REPO_ROOT / "scripts" / "review_routes"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arsenal_probe import TP1_SEAT_MODELS  # noqa: E402  (single source of truth for TP1 slugs)

TP1_LIVE_SLUGS = frozenset(TP1_SEAT_MODELS.values())

# MODEL_ROSTER.md's OpenAI section: the BARE `-m sol`/`-m terra`/`-m luna`
# slugs stopped resolving after a 2026-07-21 account rotation, but the
# versioned door `-m gpt-5.6-<id>` is live (verified 2026-08-27: PR #5044's
# own refuter round for sol, plus independent live 1-token probes for all
# three in this PR — see MODEL_ROSTER.md's row-level evidence). PR #5044
# ships `seat_build.sh --seat codex --tier sol|terra|luna` -> `-m
# gpt-5.6-<tier>`, so these roster ids resolve through the SAME `codex` door
# as `$imagegen` below, one tier level down. A hand-maintained set stays the
# honest choice over pattern-matching any bare word to the codex seat: if one
# of these tiers ever goes dead again, remove it here in the same PR that
# adds its UNREACHABLE marker back to MODEL_ROSTER.md — the two move together.
CODEX_TIER_SLUGS = frozenset({"sol", "terra", "luna"})

UNREACHABLE_MARKER = "UNREACHABLE"

ROW_RE = re.compile(r"^\|\s*`([^`]+)`")


class RosterRow(NamedTuple):
    line_no: int
    model_id: str
    line: str


def parse_roster_rows(markdown: str) -> list[RosterRow]:
    rows = []
    for i, line in enumerate(markdown.splitlines(), start=1):
        m = ROW_RE.match(line)
        if m:
            rows.append(RosterRow(line_no=i, model_id=m.group(1), line=line))
    return rows


def load_ollama_role_ids(topology_path: Path) -> frozenset[str]:
    """Ollama-shaped door ids, read live from MODEL_TOPOLOGY.json's own `roles`
    mapping — not a second hand-maintained list that could silently drift from
    the SSOT MODEL_ROSTER.md's own Local Ollama section already points to."""
    try:
        parsed = json.loads(topology_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return frozenset()
    roles = parsed.get("roles", {})
    if not isinstance(roles, dict):
        return frozenset()
    return frozenset(v for v in roles.values() if isinstance(v, str))


def _default_tp1_route_exists(slug: str) -> bool:
    return (ROUTE_DIR / f"{slug}-v1.json").exists()


def resolve_door(
    model_id: str,
    ollama_role_ids: frozenset[str],
    tp1_route_exists: Callable[[str], bool] = _default_tp1_route_exists,
) -> Optional[str]:
    """Returns a human-readable door description, or None if this id has no
    mechanically-verifiable door under the current rule set (see module
    docstring for the full, ordered rule list and the reasoning behind each).
    `tp1_route_exists` is injectable so tests never touch the real filesystem."""
    if model_id.startswith("claude-"):
        return "claude CLI alias"
    if model_id in TP1_LIVE_SLUGS:
        return f"scripts/review_routes/{model_id}-v1.json" if tp1_route_exists(model_id) else None
    if model_id in CODEX_TIER_SLUGS:
        return "codex CLI (--seat codex --tier <id> -> -m gpt-5.6-<id>, PR #5044)"
    if model_id == "$imagegen":
        return "codex CLI ($imagegen)"
    if "gemini" in model_id:
        return "agy CLI"
    if model_id == "k3" or model_id.startswith("kimi-"):
        return "kimi CLI"
    if model_id in ollama_role_ids:
        return "ollama"
    return None


def find_offenders(
    rows: list[RosterRow],
    ollama_role_ids: frozenset[str],
    tp1_route_exists: Callable[[str], bool] = _default_tp1_route_exists,
) -> list[RosterRow]:
    offenders = []
    for row in rows:
        door = resolve_door(row.model_id, ollama_role_ids, tp1_route_exists)
        if door is None and UNREACHABLE_MARKER not in row.line:
            offenders.append(row)
    return offenders


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--fixture",
        help='JSON file {"roster": "<markdown>", "ollama_roles": [...], '
        '"route_files": [...]} — swaps live file reads for this. route_files '
        "lists TP1 slugs to treat as having an on-disk review_routes JSON.",
    )
    ap.add_argument("--roster", default=str(DEFAULT_ROSTER_PATH))
    ap.add_argument("--topology", default=str(DEFAULT_TOPOLOGY_PATH))
    args = ap.parse_args(argv)

    tp1_route_exists = _default_tp1_route_exists

    if args.fixture:
        try:
            fx = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            sys.stderr.write(f"lint_roster_dispatch: cannot read fixture: {e}\n")
            return 2
        markdown = fx.get("roster", "")
        ollama_role_ids = frozenset(fx.get("ollama_roles", []))
        route_files = frozenset(fx.get("route_files", []))
        tp1_route_exists = lambda slug: slug in route_files  # noqa: E731
    else:
        try:
            markdown = Path(args.roster).read_text(encoding="utf-8")
        except OSError as e:
            sys.stderr.write(f"lint_roster_dispatch: cannot read {args.roster}: {e}\n")
            return 2
        ollama_role_ids = load_ollama_role_ids(Path(args.topology))

    rows = parse_roster_rows(markdown)
    if not rows:
        sys.stderr.write(
            "lint_roster_dispatch: 0 roster rows parsed — refusing to certify a "
            "doc that could not even be read (blind-scan guard, scar W84)\n"
        )
        return 2

    offenders = find_offenders(rows, ollama_role_ids, tp1_route_exists)
    if offenders:
        sys.stderr.write(
            f"lint_roster_dispatch: {len(offenders)} roster row(s) have no door "
            "and no UNREACHABLE marker:\n"
        )
        for row in offenders:
            sys.stderr.write(f"  MODEL_ROSTER.md:{row.line_no}: `{row.model_id}`\n")
        return 1

    print(
        f"lint_roster_dispatch: clean — {len(rows)} roster row(s), every one "
        "has a door or is marked UNREACHABLE"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
