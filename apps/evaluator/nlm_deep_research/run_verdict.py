"""One rule for "did this run actually do anything", read by all eight pipelines.

WHY THIS EXISTS (2026-08-07). Every one of the eight NB pipeline modules ended
main() with the same line:

    sys.exit(0 if result["phases"]["preflight"]["passed"] else 1)

**The exit code reported the GATE, not the WORK.** Everything after pre-flight —
L1 dying, the circuit breaker tripping, `error_nlm_add`, zero sources ingested —
was invisible to it. So a run that passed pre-flight and then achieved nothing
exited 0, and its wrapper printed "completed successfully".

Measured on Pro the day this was written, with the NotebookLM credential expired
(`nlm`: "Authentication expired"):

  - nb3's last TWELVE runs: `source_count: 0` every time, `status:
    error_nlm_add`, `degradation: NOMINAL` — and twelve "[DONE] NB-3 pipeline
    completed successfully".
  - all seven sibling pipelines reported success the same night.

The one job that told the truth did so **by accident**: nb2 is scheduled twice,
an hour apart. Its 01:10 run trips the 4-hour breaker and exits 0 ("Completed
Successfully", cron-agent `OK`); its 02:10 run then fails PRE-FLIGHT on that
breaker and exits 1. The alarm Zero receives is the second run complaining about
damage the first one did while declaring success. Remove the duplicate schedule
— which is the obviously correct thing to do — and the whole family goes silent
while the ground-truth layer sits frozen. That is why this had to be fixed
first, and why it lives in ONE module that all eight read rather than eight
copies of a corrected line.

WHAT COUNTS AS FAILURE, and what deliberately does not:

  - `halt_reason == "weekend"` → 0. An intentional calendar skip is a healthy
    no-op, not a death; this rule already existed in pipeline.py and is kept.
  - pre-flight failed → 1 (the only case the old line got right).
  - `halted_at` set → 1. This is the case that was exiting 0.
  - any `status` starting with "error" anywhere in the summary → 1. This is
    nb3's `error_nlm_add`, nested inside a phase.
  - **`success: False` is deliberately NOT a failure here.** A single L1 query
    can fail below the breaker threshold and the run still does real work
    downstream; failing on it would trade a false green for a false red, and a
    guard that cries wolf gets disarmed (superscar #2 by another road). When it
    matters, that failure reaches us anyway — it trips the breaker, and the
    breaker sets `halted_at`.

The verdict NAMES its reason, and the caller prints it: a run that exits 1
without saying why is the `last_error: "exit 1"` that this repo already knows
tells the reader nothing.
"""

from __future__ import annotations

from typing import Any

__all__ = ["verdict", "error_markers"]


def error_markers(node: Any, path: str = "") -> list[str]:
    """Every `status: error*` anywhere in the summary, with its path.

    Recursive rather than a fixed key path on purpose: the eight pipelines nest
    their phase dicts differently (nb3's marker sits inside an integration
    phase, pipeline.py's inside `phases.l1`), and a rule written against one
    layout would silently pass the other — which is the whole failure mode this
    file exists to end.
    """
    found: list[str] = []
    if isinstance(node, dict):
        status = node.get("status")
        if isinstance(status, str) and status.lower().startswith("error"):
            found.append(f"{path or 'run'}.status={status}")
        for key, value in node.items():
            found += error_markers(value, f"{path}.{key}" if path else str(key))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            found += error_markers(value, f"{path}[{i}]")
    return found


def verdict(summary: Any) -> tuple[int, str]:
    """(exit_code, human reason). See the module docstring for the rules."""
    if not isinstance(summary, dict):
        # A pipeline that returned nothing usable did not succeed. Fail loud
        # rather than treating an unreadable summary as a clean run.
        return 1, "pipeline returned no usable summary"

    if summary.get("halt_reason") == "weekend":
        return 0, "weekend skip (intentional no-op)"

    phases = summary.get("phases")
    preflight = phases.get("preflight") if isinstance(phases, dict) else None
    if not (isinstance(preflight, dict) and preflight.get("passed")):
        reason = summary.get("halt_reason") or "unnamed"
        return 1, f"pre-flight failed ({reason})"

    halted = summary.get("halted_at")
    if halted:
        return 1, f"halted at {halted}"

    markers = error_markers(summary)
    if markers:
        return 1, "phase reported an error: " + ", ".join(sorted(markers)[:4])

    return 0, "completed"
