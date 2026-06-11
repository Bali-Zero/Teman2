#!/usr/bin/env python3
"""Async review supervisor (ship #3 V1 — LABEL + BLOCK, never revert).

4-LLM panel design (research/operations/2026-06-09-ship3-async-review-supervisor-4llm-design.md):
a thin Pro-side wrapper around the EXISTING ``scripts/codex_tri_llm_review.py`` tri-LLM panel.
It does NOT re-implement review logic — it polls open PRs, applies a per-path PII gate, invokes
the existing panel, and maps the panel's outcome to a GitHub **label + check-status + comment**.

The single load-bearing constraint (Gemini's "Infinite Agent Death-Loop" failure mode):
**LABEL + BLOCK, NEVER REVERT.** This script must NEVER ``gh pr merge``, ``gh pr close``,
``git revert``, or ``git branch -D`` an unmerged branch. Auto-revert makes the originating agent
regenerate the work on a new branch → endless orphan-branch loop (cicatrix W59/W62). The supervisor's
only power is: fail a required check (blocks merge) + label + comment. A human (or the originating
agent, reading the comment) decides what to do.

V1 scope: dry-run by default. ``--apply`` actually writes labels/status/comment to GitHub.
Daemon install (launchd on Pro), required-check wiring, and the first live ``--apply`` are DEFERRED
to a dedicated Pro session — this is the script + its tests, built on M5 (dev).

Kill-switch: ``REVIEW_SUPERVISOR_OFF=1`` → exit 0 immediately (no-op).

Usage:
    python scripts/async_review_supervisor.py --pr 1238 --dry-run     # show intended action, write nothing
    python scripts/async_review_supervisor.py --pr 1238 --apply       # write label+status+comment
    python scripts/async_review_supervisor.py --poll --dry-run        # scan open PRs (dry-run)
"""

from __future__ import annotations

import argparse
import os
import re
import sys

# --- PII per-path gate (panel: skip cloud for diffs touching these) -----------
# Diffs touching these path fragments may carry client PII (akta/KTP/CRM/fixtures
# with real data) → must NOT go to the DeepSeek cloud reviewer (Law 2 / UU PDP).
# The underlying panel still runs, but the supervisor routes such PRs to a
# PII-local-only label so a human knows the cloud reviewer was withheld.
PII_PATH_FRAGMENTS: tuple[str, ...] = (
    "/kb/",
    "/fixtures/",
    "/crm/",
    "research/visa/clients/",
    "OSINT-Nexus/",
)

# Panel outcome → (label, check-conclusion, blocks-merge?). The supervisor's
# entire authority lives in this table — and none of it reverts/merges/closes.
OUTCOME_ACTION: dict[str, dict[str, object]] = {
    "green": {"label": "review:green", "check": "success", "blocks": False},
    "yellow": {"label": "review:needs-human", "check": "neutral", "blocks": False},
    "red": {"label": "review:auto-reject", "check": "failure", "blocks": True},
    "inconclusive": {"label": "review:needs-human", "check": "neutral", "blocks": False},
}

CHECK_CONTEXT = "nuzantara/async-review-supervisor"

# Actions this script must NEVER take (enforced by absence + the test-suite grep).
_FORBIDDEN_GH = ("pr merge", "pr close", "git revert", "branch -D", "branch --delete")


def pii_risk(changed_files: list[str]) -> list[str]:
    """Return the subset of changed files that touch a PII-risk path fragment."""
    hits: list[str] = []
    for f in changed_files:
        if any(frag in f for frag in PII_PATH_FRAGMENTS):
            hits.append(f)
    return hits


def plan_action(outcome: str, pii_files: list[str]) -> dict[str, object]:
    """Map a panel outcome (+ PII gate) to the intended GitHub action.

    Pure function — no side effects, no network. This is what the test-suite
    asserts and what ``--dry-run`` prints. PII-risk overrides the label to
    surface that the cloud reviewer was withheld, but never escalates to a block.
    """
    base = OUTCOME_ACTION.get(outcome, OUTCOME_ACTION["inconclusive"])
    action = dict(base)
    if pii_files:
        # Cloud reviewer withheld for these files; flag for a human, do not block
        # on the PII fact alone (a red verdict still blocks via `base`).
        action["pii_local_only"] = True
        if action["check"] != "failure":
            action["label"] = "review:pii-local-only"
    action["context"] = CHECK_CONTEXT
    return action


def _assert_no_destructive_intent(action: dict[str, object]) -> None:
    """Defense-in-depth: the planned action must never imply a destructive gh op."""
    blob = repr(action).lower()
    for forbidden in _FORBIDDEN_GH:
        if forbidden in blob:
            raise RuntimeError(
                f"REFUSING: planned action implies forbidden destructive op '{forbidden}'. "
                "The supervisor may only label + block + comment (never revert/merge/close)."
            )


def render_comment(outcome: str, action: dict[str, object], green: int, live: int) -> str:
    """Human-readable PR comment body (posted only with --apply)."""
    lines = [
        f"**async-review-supervisor** — panel outcome: `{outcome}` ({green}/{live} live reviewers green)",
        f"- label: `{action['label']}`",
        f"- check `{action['context']}`: `{action['check']}`"
        + ("  ⛔ **blocks merge**" if action.get("blocks") else ""),
    ]
    if action.get("pii_local_only"):
        lines.append(
            "- ⚠️ PII-risk files in this diff → DeepSeek cloud reviewer was **withheld** (Law 2). "
            "Reviewed locally only; a human should confirm."
        )
    lines.append("")
    lines.append("_LABEL+BLOCK mode: this bot never reverts, merges, or closes. A human decides._")
    return "\n".join(lines)


def main() -> int:
    if os.environ.get("REVIEW_SUPERVISOR_OFF") == "1":
        print("[review-supervisor] kill-switch REVIEW_SUPERVISOR_OFF=1 → no-op exit 0")
        return 0

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--pr", type=int, help="Single PR number to review")
    src.add_argument("--poll", action="store_true", help="Scan all open PRs (gh)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Print intended action, write nothing (default)")
    mode.add_argument("--apply", action="store_true", help="Actually write label/status/comment to GitHub")
    args = ap.parse_args()

    # V1 default is dry-run unless --apply is explicit (safety: never write by accident).
    apply = bool(args.apply)

    # NOTE: the live gh-poll + codex_tri_llm_review invocation + gh writes are wired
    # in step 3 (Pro session). V1 here ships the pure decision logic + its guards so
    # the dangerous surface (network writes) is added separately, on the Pro, behind
    # --apply. This keeps the M5-built slice testable and write-free.
    print(
        f"[review-supervisor] V1 decision-core ready. mode={'APPLY' if apply else 'DRY-RUN'} "
        f"pr={args.pr if args.pr else 'poll'}. "
        "Live gh-poll + panel invocation wired on the Pro (step 3 of the ship-plan)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
