#!/usr/bin/env python3
"""Fail CI on non-waived high/critical npm advisories.

Extracted from the inline block in `.github/workflows/tests.yml` so it can carry
a guilt+innocence corpus (`test_npm_audit_gate.py`) instead of being a guard
nobody can execute.

Two things it does that the inline version did not:

1. **Waivers are scoped to a dependency PATH, not just an advisory id.** An
   advisory id is a property of the vulnerability; reachability is a property of
   the path it arrives on. Waiving `GHSA-x` outright silently forgives a *future*
   arrival of the same advisory on a genuinely reachable path. Legacy waivers
   keep `None` (= any path) because that is the shape they were approved in.

2. **A shapeless audit file is CANNOT-VERIFY, not clean.** The workflow runs
   `npm audit … || true`, so a failed audit still leaves a file behind. An empty
   object has no vulnerabilities and used to read as a pass.

Exit codes: 0 clean/waived · 1 non-waived findings · 2 cannot verify.
"""

from __future__ import annotations

import json
import sys

# advisory id -> set of node paths the waiver covers, or None for "any path".
#
# Retired the July/August exceptions on 2026-09-11 after checking the lockfile
# against the upstream advisory ranges: @hono/node-server 2.0.11 contains the
# frvp/9mqv fixes (2.0.5/2.0.10), find-my-way 9.7.0 fixes c96f, and js-yaml
# 3.15.1 backports 5p4m without a gray-matter-breaking 4.x override.
# A future regression must be reported again. New advisories are not covered
# by the retired approvals. Evidence: research/secondhome/2026-09-11-f7-reverification.md.
WAIVE: dict[str, set[str] | None] = {}

BLOCKING = ("high", "critical")


def advisory_ids(vuln: dict) -> set[str]:
    return {
        str(x.get("url", "")).rsplit("/", 1)[-1]
        for x in vuln.get("via", [])
        if isinstance(x, dict)
    }


def evaluate(data: dict, waive: dict[str, set[str] | None] = WAIVE) -> list[tuple]:
    """Return the blocking findings. Empty list means the gate passes."""
    bad: list[tuple] = []
    for name, vuln in (data.get("vulnerabilities") or {}).items():
        if vuln.get("severity") not in BLOCKING:
            continue
        ids = advisory_ids(vuln)
        if not ids:
            # No advisory id of its OWN: every `via` entry is a bare package
            # name, i.e. this package is a CARRIER of someone else's advisory.
            # It still blocks — but it must not fall through to the waiver
            # branch below, which would report it as "waived, but on unexpected
            # paths" and so name a waiver that was never granted. On 2026-08-17
            # `prisma` and `@prisma/config` (carriers of deepmerge-ts's
            # GHSA-ggr8-5vv4-36mx) read exactly that way, and it sent a session
            # hunting through WAIVE for entries that do not exist while the repo
            # sat unmergeable. The verdict was right; the message pointed away
            # from the cause.
            carries = sorted(str(x) for x in (vuln.get("via") or []) if isinstance(x, str))
            bad.append(
                (
                    name,
                    vuln.get("severity"),
                    [],
                    f"no advisory of its own — carries: {carries or ['<unknown>']}",
                )
            )
            continue
        unwaived = ids - waive.keys()
        if unwaived:
            bad.append((name, vuln.get("severity"), sorted(ids), "not waived"))
            continue
        # Every id is waived in principle — now check it arrived where we said
        # it would. A node is fine if ANY of this vuln's ids permits it.
        nodes = set(vuln.get("nodes") or [])
        stray = sorted(
            n
            for n in nodes
            if not any(waive[i] is None or n in waive[i] for i in ids)
        )
        if stray:
            bad.append(
                (name, vuln.get("severity"), sorted(ids), f"waived, but on unexpected paths: {stray}")
            )
    return bad


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: npm_audit_gate.py <audit.json>", file=sys.stderr)
        return 2
    try:
        with open(argv[1]) as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"npm audit: CANNOT VERIFY — audit report unreadable ({exc})")
        return 2
    # `npm audit … || true` means a failed audit still leaves a file. An object
    # with no `vulnerabilities` key is a shapeless report, not a clean one.
    if not isinstance(data, dict) or "vulnerabilities" not in data:
        print("npm audit: CANNOT VERIFY — report has no 'vulnerabilities' key; "
              "the audit itself probably failed (the step swallows its exit code)")
        return 2

    bad = evaluate(data)
    if bad:
        print("npm audit: non-waived high/critical vulnerabilities found:")
        for row in bad:
            print("  ", row)
        return 1
    print("npm audit: only waived advisories present — gate OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
