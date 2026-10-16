#!/usr/bin/env python3
"""harness_fable_gate.py — publisher for the `harness/fable-gate` commit status.

WHAT THIS IS (harness-v2-teman2.md §6 "Meccanizzazione"): the Fable gate
session decides a verdict interactively — PASS / PASS-WITH-CONDITIONS /
REWORK-BUILD / REWORK-DESIGN / BLOCK. This script's ONLY job is to make that
already-decided verdict visible to GitHub as the `harness/fable-gate` commit
status, via `gh api`.

HOW THAT STATUS IS ENFORCED — a two-part mechanism, described here because
an earlier draft of this docstring claimed "branch protection can require
it", i.e. that this commit-status CONTEXT could itself be a required check.
It cannot, and that false premise is what a 2026-08-24 PENDING-ARMS row
recorded as "published but not required" (measured: the context absent from
main's required_status_checks). The truth, since the 2026-08-21 redesign
(research/operations/2026-08-21-fable-gate-required-promotion.md): branch
protection requires the `Harness floor recompute` JOB
(.github/workflows/harness-floor.yml — a required context before the
redesign and after), NEVER this status. A status posted on a PR's real head
sha never appears on the merge queue's synthetic test-merge sha, so a
required `harness/fable-gate` context would deadlock every gated PR in the
queue; and a fork PR's read-only token could never post it anyway. Instead,
for a PR declaring gear >= 2 (threshold RULED 2026-09-10; was Gear 3) that
job READS this status on the PR's real head sha
(scripts/ci/harness_gate_read.py) and mirrors the verdict as its own exit
code; gear-1 and no-brief diffs pass the job unconditionally. So merging a
gear >= 2 PR without a real gate verdict IS physically impossible — via the
job plus this status together, not via this context being required ("il
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

LEDGER FIRST (B25-prime P1, docs/specs/localci-sovereign-2026-10-07.md 2b.2): the verdict is appended to the Pro ledger
(~/.nuzantara-pilots/local-ci-gate/verdicts.jsonl) BEFORE the GitHub status is posted, over `ssh pro` through the tick wrapper's
`gate-append` mode (the entry travels as ONE base64 argv; on Pro itself the wrapper runs locally). A failed append posts nothing, so a
GitHub-only success is always an anomaly. The ledger is the verdict LocalCI trusts; the GitHub status is storage and, until the phase F
flip, what the hosted floor reads. Run this script from origin/main, never from a candidate's checkout (a candidate's code must not
reach the ssh key). `--supersede` also names, on the ledger, every unsuperseded failure of the head (success verdicts only).

CLI:
  python3 scripts/harness_fable_gate.py --verdict PASS --sha <commit-sha> --pr <number>
      [--repo owner/repo] [--degraded] [--description "extra context"]
      [--conditions-ref <PENDING-ARMS pointer>] [--supersede "reason"]
      [--gate-session NAME] [--evidence-sha256 HEX64] [--dry-run]

  --pr             the PR number of --sha for the ledger entry; optional (a gate usually posts before its PR exists): when
                   omitted the entry carries pr null, never a guess
  --gate-session   who gated, at most 80 characters (default: gate)
  --evidence-sha256  the sha256 of the evidence pack, when there is one

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
     cannot see what is already posted must not publish blind; also when
     the ledger append fails (nothing is posted then)
  2  refused: a harness/fable-gate status already exists on --sha and
     --supersede was not given (or --supersede was given with nothing to
     supersede, or with an empty/whitespace-only reason)
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys

CONTEXT = "harness/fable-gate"
LEDGER_WRAPPER = "~/.nuzantara-cron/localci_merger_tick.sh"   # Pro's live copy of scripts/localci/localci_merger_tick.sh
LEDGER_STATE = {"success": "success", "failure": "failure"}   # GitHub state -> ledger verdict

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


PREFLIGHT = (   # read-only on Pro: neither probe may run the wrapper, an old wrapper treats ANY argv as a tick
    'W={w}; M="${{MERGER_STATE_DIR:-$HOME/.nuzantara-pilots/local-ci/merger}}/repo.git"; '
    '[ -f "$W" ] || exit 10; grep -q gate-append "$W" || exit 10; '
    'R=refs/merger/wrapper; git -C "$M" rev-parse --verify --quiet "$R^{{commit}}" >/dev/null || R=refs/merger/base; '
    'git -C "$M" cat-file -e "$R:scripts/localci/gate_ledger.py" 2>/dev/null || exit 11'
)
PREFLIGHT_WHY = {
    10: "the live wrapper on Pro has no gate-append mode (an old wrapper would run a TICK on this argv): deploy step 1 of "
        "docs/runbooks/localci-gate-ledger.md (copy the wrapper pair)",
    11: "the merger mirror on Pro has no scripts/localci/gate_ledger.py at refs/merger/wrapper: deploy step 2 of "
        "docs/runbooks/localci-gate-ledger.md (forced fetch with the wrapper's refspec)",
}


def _on_pro() -> bool:
    return os.uname().nodename.split(".")[0].lower() == "nuzantara"


def preflight_command() -> list[str]:
    script = PREFLIGHT.format(w=LEDGER_WRAPPER)
    if _on_pro():
        return ["/bin/bash", "-c", script.replace("~", os.path.expanduser("~"))]
    return ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "pro", script]


def ledger_command(b64: str, supersede: bool) -> list[str]:
    """The argv that appends: the wrapper locally on Pro, `ssh pro` from anywhere else."""
    tail = ["gate-append", b64] + (["--supersede"] if supersede else [])
    if _on_pro():
        return ["/bin/bash", os.path.expanduser(LEDGER_WRAPPER)] + tail
    return ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "pro", f"bash {LEDGER_WRAPPER} " + " ".join(tail)]


def ledger_append(repo: str, sha: str, pr: int | None, state: str, session: str, evidence: str | None,
                  supersede: bool, dry_run: bool) -> int:
    """Append the verdict to the Pro ledger. Non-zero means the caller must post NOTHING. `pr` is recorded as given, null when the
    gate posts before the PR exists: it is not part of the verification key (repo, head_sha) and is never guessed."""
    if dry_run:
        print("DRY-RUN: ledger preflight would run:", " ".join(preflight_command()[:6]), "...")
        print("DRY-RUN: ledger append would run:", " ".join(ledger_command("<entry-b64>", supersede and state == "success")))
        return 0
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        print(f"harness_fable_gate: --sha {sha!r} is not a full 40-hex commit sha — the ledger keys on it", file=sys.stderr)
        return 1
    try:
        pre = subprocess.run(preflight_command(), capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        print(f"harness_fable_gate: ledger preflight could not run (Pro unreachable?), nothing is posted: {exc}", file=sys.stderr)
        return 1
    if pre.returncode != 0:
        why = PREFLIGHT_WHY.get(pre.returncode, f"preflight rc={pre.returncode}: {pre.stderr.strip()[:200]}")
        print(f"harness_fable_gate: the ledger is not deployed on Pro, nothing is posted: {why}", file=sys.stderr)
        return 1
    entry = {"repo": repo, "pr": pr, "head_sha": sha, "verdict": LEDGER_STATE[state], "gate_session": session[:80],
             "evidence_sha256": evidence, "supersedes": None}
    b64 = base64.b64encode(json.dumps(entry, separators=(",", ":")).encode()).decode()
    try:
        proc = subprocess.run(ledger_command(b64, supersede and state == "success"), capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        print(f"harness_fable_gate: ledger append could not run: {exc}", file=sys.stderr)
        return 1
    if proc.returncode != 0:
        print(f"harness_fable_gate: ledger append FAILED (rc={proc.returncode}), nothing is posted: {proc.stderr.strip()[:300]}",
              file=sys.stderr)
        return 1
    print(f"harness_fable_gate: ledger entry {proc.stdout.split()[-1][:12] if proc.stdout.split() else '?'} appended")
    return 0


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


def main(argv: list[str] | None = None, read_statuses=read_existing_statuses, append_ledger=None) -> int:
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
    parser.add_argument("--pr", type=int, default=None, help="PR number of --sha for the ledger entry (null when omitted)")
    parser.add_argument("--gate-session", default="gate", help="who gated, at most 80 characters")
    parser.add_argument("--evidence-sha256", default=None, help="sha256 of the evidence pack, when there is one")
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

    # e. the ledger first: a failed append posts nothing, so a GitHub-only success is always an anomaly (B25-prime 2b.2)
    rc = (append_ledger or ledger_append)(repo, args.sha, args.pr, state, args.gate_session, args.evidence_sha256,
                                          args.supersede is not None, args.dry_run)
    if rc != 0:
        return 1
    return publish(repo, args.sha, state, description, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
