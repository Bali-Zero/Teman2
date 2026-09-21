#!/usr/bin/env python3
"""harness_fable_gate.py — publisher for the `harness/fable-gate` commit status.

WHAT THIS IS (harness-v2-teman2.md §6 "Meccanizzazione"): the Fable gate
session decides a verdict interactively — PASS / PASS-WITH-CONDITIONS /
REWORK-BUILD / REWORK-DESIGN / BLOCK. This script's ONLY job is to make that
already-decided verdict visible to GitHub as the `harness/fable-gate` commit
status, via `gh api`, so branch protection can require it and merging a
Gear-3 PR without a real gate verdict becomes physically impossible ("il
gate diventa CI-enforced, non prompt-enforced").

THE NAME IS HISTORICAL — THIS SCRIPT NEVER INVOKES FABLE (note added
2026-08-21). Zero ruled Fable out of the workflow on 2026-08-20, and a reader
meeting "fable-gate" reasonably concludes this context depends on a model
that is no longer routed to. It does not: the context is a relay for a
verdict a SESSION already reached, and it is indifferent to which model
reached it — the routing question and the "does a Gear-3 PR carry a real
verdict" question are separate, and only the second one lives here. The
context string is deliberately NOT renamed: `harness/fable-gate` appears in
15 tracked files at origin/main — harness-v2-teman2.md, fleet-order-spec.md,
and dated research captures that record what was true when written. Renaming
across those is a doctrine change, not a cleanup, and a status context is
also the exact string branch protection would match. Fix the misreading
where a reader meets it, not by rewriting the record.

CITATION CORRECTED 2026-08-21 (cross-family review, before merge): an earlier
draft of this note also cited FLEET_TOPOLOGY.json. It does NOT contain the
string — `grep -c "fable-gate"` returns 0. What it carried was a role-chain
key `fable_gate_gear3`, and that key was ALREADY renamed to `gear3_final_gate`
under the same 2026-08-20 ruling. So the one file cited as a reason not to
rename had itself already been renamed. The argument stands on the other
grounds; that citation did not, and is removed rather than quietly dropped.

**PUBLISHER ONLY — NO VERDICT LOGIC.** This script never decides PASS vs
REWORK vs BLOCK; it only validates that a caller-supplied verdict is one of
the five legal values, maps it to a GitHub commit-status `state`
(success|failure|pending|error), and posts it. The verdict itself is the
conductor's (fleet-order-spec.md §0: "the verdict is the conductor's").

VERDICT → STATE mapping (harness-v2 §6):
  PASS                  -> success  (ship immediately)
  PASS-WITH-CONDITIONS  -> success  (ship allowed; the PWC ledger discipline —
                                      owner + deadline in PENDING-ARMS for
                                      every condition — is the calling
                                      session's responsibility, not this
                                      script's: it only relays the verdict)
  REWORK-BUILD           -> failure (plan sound, implementation defective)
  REWORK-DESIGN          -> failure (the plan itself is wrong)
  BLOCK                  -> failure (task suspended, escalation required)

`--degraded` marks `gate_degraded: fable->opus` in the posted description —
the ONLY sanctioned fallback (fleet-order-spec.md §4 "Ruling Zero
2026-08-09": Opus 5 effort=max ONLY when no Anthropic account can run Fable
for the Gear-3 verdict stage; never for the final on-disk gate; never paid).

CLI:
  python3 scripts/harness_fable_gate.py --verdict PASS --sha <commit-sha>
      [--repo owner/repo] [--degraded] [--description "extra context"]
      [--conditions-ref <PENDING-ARMS pointer>] [--supersede "reason"]
      [--dry-run]

  --sha           commit to post the status against (required — never
                   guessed from a local HEAD that may not be the PR's head)
  --repo           owner/repo; auto-detected via `gh repo view` if omitted
  --degraded       sets gate_degraded: fable->opus in the description
  --description    free-text appended to the auto-generated description
                    (e.g. a one-line reason, a PENDING-ARMS pointer)
  --conditions-ref  REQUIRED for PASS-WITH-CONDITIONS: where the ledger entry
                    with owner+deadline lives (e.g. a PENDING-ARMS.md
                    pointer) — appended to the description. This script has
                    no ledger access so it cannot verify the entry EXISTS,
                    but it refuses to publish a PWC with no pointer at all:
                    harness-v2 §6 calls PWC-without-enforcement "la falla da
                    cui passa tutto" (adversarial-review finding 2026-08-10 —
                    this flag used to be optional even for PWC).
  --supersede      REQUIRED to overwrite an EXISTING `harness/fable-gate`
                    status on --sha. GitHub keeps every commit status ever
                    posted on a sha but renders only the LATEST per context
                    — so two gate sessions racing on the same PR silently
                    overwrite each other and neither sees it (measured on
                    PR #7000's head, two publishes 2 minutes apart, and on
                    #6999, two PASS-WITH-CONDITIONS with different
                    conditions pointers). Worst case: a PASS lands over an
                    earlier REWORK/BLOCK and the floor turns green with the
                    rework never surfaced. Without --supersede, publishing
                    against a sha that already carries a harness/fable-gate
                    status is refused (exit 2) — read the existing verdict
                    first. With --supersede, the reason is folded into the
                    posted description as `supersedes=<prev-state>@<prev-
                    created_at>: <reason>`, so it is visible on the PR.
                    WHAT THIS DOES NOT CLOSE: the read and the post are two
                    calls, so two publishes landing inside the same few
                    seconds can still both pass the read. The collisions it
                    was built for were minutes apart (a gate is tens of
                    minutes of work, the publish is its last second), and
                    GitHub offers no compare-and-set on commit statuses —
                    a lock would have to live outside it.
  --dry-run        print the `gh api` invocation instead of running it
                   (used by tests — no network, no auth required); the
                   overwrite check itself is skipped in --dry-run (no
                   network read), and a --supersede reason is shown with a
                   placeholder `<unread>` marker instead of a real previous
                   status.

Exit codes:
  0  published (or, with --dry-run, printed) successfully
  1  usage error (bad --verdict, missing --sha, PWC without
     --conditions-ref) or `gh api` call failed; also returned when the
     existing-statuses read itself fails — fail-closed, a publisher that
     cannot see what is already posted must not publish blind
  2  refused: a harness/fable-gate status already exists on --sha and
     --supersede was not given (or --supersede was given with nothing to
     supersede, or with an empty/whitespace-only reason)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

CONTEXT = "harness/fable-gate"

# harness-v2-teman2.md §6 — the five legal verdicts and their GitHub state.
VERDICT_STATE: dict[str, str] = {
    "PASS": "success",
    "PASS-WITH-CONDITIONS": "success",
    "REWORK-BUILD": "failure",
    "REWORK-DESIGN": "failure",
    "BLOCK": "failure",
}


def build_description(
    verdict: str,
    degraded: bool,
    extra: str | None,
    conditions_ref: str | None,
    supersedes: str | None = None,
) -> str:
    """Pure formatting — no verdict logic. Kept separate from main() so tests
    can assert the exact string without shelling out to `gh`."""
    parts = [verdict]
    if degraded:
        parts.append("gate_degraded=fable->opus")
    if verdict == "PASS-WITH-CONDITIONS" and conditions_ref:
        parts.append(f"conditions={conditions_ref}")
    if supersedes:
        parts.append(f"supersedes={supersedes}")
    if extra:
        parts.append(extra)
    description = " | ".join(parts)
    # GitHub's commit-status description field is capped at 140 characters;
    # truncate loudly (visible ellipsis) rather than let `gh api` reject the
    # call or silently clip mid-word. `supersedes` sits before `extra` above
    # so this truncation eats free-text `extra` first, never the audit trail
    # of what was overwritten.
    if len(description) > 140:
        description = description[:137] + "..."
    return description


def read_existing_statuses(repo: str, sha: str) -> list[dict] | None:
    """Read every `harness/fable-gate` commit status already posted on `sha`.

    Returns `[]` when the read succeeded and none exist, or `None` when the
    read itself failed (network, auth, malformed JSON) — `None` is NOT the
    same as `[]`: the caller must fail closed on `None` rather than treat an
    unreadable sha as a clean one (see `main`'s overwrite guard).
    """
    try:
        out = subprocess.run(
            [
                "gh", "api", "--paginate",
                f"repos/{repo}/commits/{sha}/statuses?per_page=100",
                "--jq", f'.[] | select(.context=="{CONTEXT}") | {{state, description, created_at}}',
            ],
            capture_output=True, text=True, check=True, timeout=30,
        ).stdout
        statuses = []
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            statuses.append(json.loads(line))
        return statuses
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None


def check_overwrite(existing: list[dict], supersede: str | None) -> tuple[bool, str]:
    """PURE — no I/O. Decide whether publishing may proceed given what
    already exists on the sha and whether the caller declared a supersede.

    See the module docstring's `--supersede` paragraph for the WHY (the
    invisible collision measured on PR #7000 and #6999)."""
    if supersede is not None and not supersede.strip():
        return False, "harness_fable_gate: --supersede needs a reason (got empty/whitespace-only)"
    if not existing:
        if supersede is None:
            return True, ""
        return False, (
            "harness_fable_gate: --supersede was given but no harness/fable-gate "
            "status exists yet on this sha — there is nothing to supersede; drop --supersede"
        )
    if supersede is None:
        prev = max(existing, key=lambda s: s["created_at"])
        return False, (
            f"harness_fable_gate: {len(existing)} harness/fable-gate status(es) already exist "
            f"on this sha — most recent: state={prev['state']} created_at={prev['created_at']} "
            f"description={prev['description']!r}. Read the existing verdict first; if "
            f"overwriting it is the decision, re-run with --supersede \"<reason>\"."
        )
    return True, ""


def resolve_repo() -> str | None:
    try:
        out = subprocess.run(
            ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
            capture_output=True, text=True, check=True, timeout=15,
        ).stdout.strip()
        return out or None
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None


def publish(repo: str, sha: str, state: str, description: str, dry_run: bool) -> int:
    cmd = [
        "gh", "api", f"repos/{repo}/statuses/{sha}",
        "-f", f"state={state}",
        "-f", f"context={CONTEXT}",
        "-f", f"description={description}",
    ]
    if dry_run:
        print("DRY-RUN:", " ".join(cmd))
        return 0
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=30)
    except subprocess.CalledProcessError as exc:
        print(f"harness_fable_gate: gh api call FAILED: {exc.stderr}", file=sys.stderr)
        return 1
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        print(f"harness_fable_gate: could not invoke gh: {exc}", file=sys.stderr)
        return 1
    print(f"harness_fable_gate: published {CONTEXT}={state} on {sha} ({repo})")
    return 0


def main(argv: list[str] | None = None, read_statuses=read_existing_statuses) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--verdict", required=True, choices=sorted(VERDICT_STATE))
    parser.add_argument("--sha", required=True, help="commit SHA to post the status against")
    parser.add_argument("--repo", default=None, help="owner/repo (auto-detected if omitted)")
    parser.add_argument("--degraded", action="store_true")
    parser.add_argument("--description", default=None)
    parser.add_argument("--conditions-ref", default=None)
    parser.add_argument(
        "--supersede", default=None,
        help="reason for overwriting an existing harness/fable-gate status on --sha "
             "(only when overwriting is the decision — shown on the PR)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    # a. harness-v2 §6: PASS-WITH-CONDITIONS without an enforced conditions
    # pointer is "la falla da cui passa tutto" — refuse to publish one with
    # no --conditions-ref rather than silently post a bare PWC (adversarial-
    # review finding 2026-08-10).
    if args.verdict == "PASS-WITH-CONDITIONS" and not args.conditions_ref:
        print(
            "harness_fable_gate: --verdict PASS-WITH-CONDITIONS requires "
            "--conditions-ref (a PENDING-ARMS.md pointer for the "
            "owner+deadline entry) — refusing to publish an unenforceable PWC",
            file=sys.stderr,
        )
        return 1

    # b. resolve repo
    repo = args.repo or resolve_repo()
    if not repo:
        print("harness_fable_gate: could not resolve owner/repo — pass --repo explicitly",
              file=sys.stderr)
        return 1

    # c. overwrite guard — two gate sessions racing on the same sha must not
    # silently overwrite each other's verdict (measured on PR #7000 and
    # #6999; see the module docstring's --supersede paragraph).
    supersedes_text: str | None = None
    if args.dry_run:
        print(
            "DRY-RUN: overwrite check skipped — would read: gh api --paginate "
            f"repos/{repo}/commits/{args.sha}/statuses?per_page=100"
        )
        if args.supersede:
            supersedes_text = f"<unread>: {args.supersede}"
    else:
        existing = read_statuses(repo, args.sha)
        if existing is None:
            print(
                f"harness_fable_gate: could not read existing statuses on {args.sha} — "
                "refusing to publish blind; retry",
                file=sys.stderr,
            )
            return 1
        ok, msg = check_overwrite(existing, args.supersede)
        if not ok:
            print(msg, file=sys.stderr)
            return 2
        if args.supersede and existing:
            prev = max(existing, key=lambda s: s["created_at"])
            supersedes_text = f"{prev['state']}@{prev['created_at']}: {args.supersede}"

    # d. build the description (with `supersedes` when the guard passed with
    # one) and publish.
    state = VERDICT_STATE[args.verdict]
    description = build_description(
        args.verdict, args.degraded, args.description, args.conditions_ref,
        supersedes=supersedes_text,
    )

    return publish(repo, args.sha, state, description, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
