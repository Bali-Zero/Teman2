#!/usr/bin/env python3
"""seat_gate.py — the preflight infra/workflows/kbli-nav-design.js runs before ANY dispatch, fail-closed.

The kit must exist and sit outside every git checkout: `kit ok <path>` or one `refused:` line (no seat_io call can
then trace back on a bad path). A seat is live only when the arsenal report (arsenal_probe.REPORT_DIR/last.json) exists,
parses, is at most --max-age-h old by its own `ts`, and carries the seat's row with status LIVE. Anything else — no
report (arsenal's NEVER_RAN), an unreadable or stale report, no row, another status — is `dead <seat>: <reason>`.
Path, the LIVE status and the seat names (codex, agy, nlm) are the probe's own, imported, never restated.
A dead seat dispatched anyway is granted, burns its single round and comes back empty (R1 of this very kit).
FIRST of all, before any refusal can return, --preview P empties the gallery of the previous run: every *.png under
P/mockups/ goes (nothing else is touched) and `gallery cleared P/mockups pngs=<left>` is printed, so a run that is
refused anywhere later never leaves sets nobody read in front of the vote."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.arsenal_probe import ALL_SEATS, LIVE, REPORT_DIR  # noqa: E402

REPORT = REPORT_DIR / "last.json"
SEATS = ("codex", "agy", "nlm")  # Sol, Gemini, the NotebookLM witness: the names the probe emits (ALL_SEATS)


def kit_line(kit: str) -> str:
    """The kit is echoed exactly as given: the workflow compares `kit ok <its own KIT string>` byte for byte."""
    real = Path(kit).resolve()
    if not real.is_dir():
        return f"refused: kit {kit} does not exist"
    if any((d / ".git").exists() for d in (real, *real.parents)):
        return f"refused: kit {kit} is inside a git checkout; it must live outside the repo (C3)"
    return f"kit ok {kit}"


def seat_lines(report: Path, seats: list[str], max_age_h: float, now: dt.datetime) -> list[str]:
    try:
        data = json.loads(report.read_text(encoding="utf-8"))
        ts = dt.datetime.strptime(data["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
        rows = {r["seat"]: r.get("status") for r in data["seats"]}
    except FileNotFoundError:
        return [f"dead {s}: no arsenal report (NEVER_RAN)" for s in seats]
    except (OSError, ValueError, KeyError, TypeError) as e:
        return [f"dead {s}: unreadable arsenal report ({type(e).__name__})" for s in seats]
    age = (now - ts).total_seconds() / 3600
    out = []
    for s in seats:
        if not 0 <= age <= max_age_h:
            out.append(f"dead {s}: arsenal report is {age:.1f}h old, bound {max_age_h:g}h")
        elif s not in rows:
            out.append(f"dead {s}: no row in the arsenal report")
        elif rows[s] != LIVE:
            out.append(f"dead {s}: {rows[s]}")
        else:
            out.append(f"live {s}")
    return out


def clear_gallery(preview: str) -> str:
    root = Path(preview) / "mockups"
    for png in root.rglob("*.png") if root.is_dir() else ():
        png.unlink(missing_ok=True)
    for d in sorted((x for x in root.rglob("*") if x.is_dir()), reverse=True) if root.is_dir() else ():
        if not any(d.iterdir()):
            d.rmdir()
    left = sum(1 for _ in root.rglob("*.png")) if root.is_dir() else 0
    return f"gallery cleared {preview}/mockups pngs={left}"  # echoed as given: the workflow compares ${PREVIEW}/mockups


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kit", required=True)
    ap.add_argument("--report", type=Path, default=REPORT)
    ap.add_argument("--max-age-h", type=float, default=12.0)
    ap.add_argument("--seats", default=",".join(SEATS))
    ap.add_argument("--preview")
    a = ap.parse_args(argv)
    if a.preview:
        print(clear_gallery(a.preview))
    line = kit_line(a.kit)
    print(line)
    if line.startswith("kit ok"):
        print("\n".join(seat_lines(a.report, a.seats.split(","), a.max_age_h, dt.datetime.now(dt.timezone.utc))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
