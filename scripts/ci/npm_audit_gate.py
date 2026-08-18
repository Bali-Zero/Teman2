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
# Temporary waiver (2026-07-24, owner-approved, REMOVE when patched versions
# ship): 3 advisories with NO patched release available — every installed
# version is already the latest published.
#   GHSA-frvp-7c67-39w9  @hono/node-server path traversal (Windows-only %5C)
#   GHSA-9mqv-5hh9-4cgg  @hono/node-server WebSocket aborted-handshake mem-leak
#   GHSA-c96f-x56v-gq3h  find-my-way HTTP2 DDoS
# Reachability: @hono/node-server enters via @modelcontextprotocol/sdk (used for
# its optional HTTP transport; our MCP servers run stdio) and find-my-way via
# @prisma/dev (local dev tooling).
#
# GHSA-5p4m-2wfm-xmqj (2026-08-07): js-yaml quadratic CPU on !!omap. Waived for
# ONE path only. Why it cannot be fixed:
#   - the 3.x line has no backport (the advisory title says so);
#   - gray-matter@4.0.3 is the latest published and pins `js-yaml: ^3.13.1`;
#   - forcing 4.3.1 breaks gray-matter at import — `lib/engines.js:16` does
#     `yaml.safeLoad.bind(yaml)` and 4.x removed safeLoad/safeDump, so the bind
#     throws on undefined. gray-matter is a PRODUCTION dep of apps/mouth.
# Reachability: the only callers are apps/mouth/src/lib/blog/articles.ts and
# scripts/generate-llms-full.ts, both `fs.readFileSync` over
# `src/content/articles` — git-tracked markdown we author, parsed at build time.
# No route feeds user-supplied YAML to it. Re-check that claim before extending
# this waiver to any other node.
WAIVE: dict[str, set[str] | None] = {
    "GHSA-frvp-7c67-39w9": None,
    "GHSA-9mqv-5hh9-4cgg": None,
    "GHSA-c96f-x56v-gq3h": None,
    "GHSA-5p4m-2wfm-xmqj": {"node_modules/gray-matter/node_modules/js-yaml"},
}

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
