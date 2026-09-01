#!/usr/bin/env python3
"""evidence_pack_lint.py — Evidence Pack contract enforcement (PR-3 of the
fleet-order program, per pr3-brief.md + harness-v2-teman2.md §5 + the schema
correction in 2026-08-10-fleet-order-spec.md §4).

WHY THIS EXISTS: harness-v2 §5 says it plainly — "i prompt non bastano" — an
Evidence Pack is "l'unico input del gate", not a report. Its anti-hallucination
value (receipts = "mai citare output di tool non eseguito" made physical) only
holds if something machine-checkable actually enforces the shape. This is that
something. It is itself a GUARD in the cicatrix-superscar.md #3 sense (a
textual/structural decision procedure that accepts or rejects an artifact), so
it ships with guilt+innocence tests and a guard-conformance registry entry —
the mandate rule ("nessuna guardia mergiata senza un test di innocenza E di
colpevolezza") applies to the linter that enforces OTHER guards' evidence too.

WHAT IT VALIDATES (an Evidence Pack YAML, default path evidence/pack.yml):
  1. receipts        — every entry needs {claim, cmd, exit, ts, seat}. An entry
                        missing any field is not a receipt, it is an unverified
                        OPINION wearing a receipt's shape — REJECTED so the
                        author either completes it or moves the claim out of
                        `receipts:` (harness-v2 §5 "Anti-Goodhart"). On a
                        Gear-3 pack, receipts must also be NON-EMPTY (symmetric
                        with rule 2 — an Evidence Pack with zero evidence at
                        the gear where it matters most is a defective pack,
                        not an innocent one; adversarial-review finding
                        2026-08-10, was previously accepted at any gear).
  2. dissent         — MANDATORY field (harness-v2 §5: "campo OBBLIGATORIO, non
                        opzionale"), must be a list. On a Gear-3 pack (declared
                        by the referenced brief) it must be non-empty: zero
                        dissent on Gear-3 is "consenso sospetto" — either no
                        refuter actually tried, or none were independent
                        (harness-v2 §5). Gear 1/2 may carry an empty list.
                        Every entry is structurally validated too —
                        {seat, objection, status∈{CONFIRMED,PLAUSIBLE,RETRACTED}}
                        — `dissent: [{}]` used to pass on length alone
                        (adversarial-review finding 2026-08-10).
  3. pii_scan        — must equal the literal string "clean" (Law 2 / UU PDP).
                        This validates the PACK'S DECLARED state, deliberately
                        NOT an independent PII/secret re-scan — a real scanner
                        is a separate tool (e.g. secrets_permissions_audit.py,
                        the fleet-order-spec §5 redaction pre-pass); the
                        Evidence Pack's own anti-Goodhart defense against a
                        false "clean" is receipts + dissent + the gate's
                        spot-check right, not this linter re-deriving PII
                        status from scratch (harness-v2 §5).
  4. size            — approx tokens = len(raw bytes)/4 <= 30_000 (harness-v2
                        §5 hard cap — protects the Fable gate's weekly
                        allowance and forces compression of EVIDENCE, not more
                        narration). Checked on the RAW BYTES *before*
                        yaml.safe_load ever runs — checking only after parsing
                        protects nothing against an oversized/adversarial
                        input (adversarial-review finding 2026-08-10).
  5. brief_ref       — must be present, a REPO-RELATIVE path (an absolute path
                        or a `..`-escape is rejected — pathlib's `/` operator
                        silently discards the left operand when the right is
                        absolute, a real path-confinement bug found by
                        adversarial review 2026-08-10), confined under
                        repo_root, and resolve to a real FILE (not a
                        directory — `brief_ref: "."` used to raise an
                        uncaught IsADirectoryError).
  6. gear >= floor   — the brief's declared `gear` must be a genuine `int`
                        (not `true`/`1.0` — Python's bare `in` on a tuple of
                        ints treats `bool`/`float` as equal, so `gear: true`
                        used to pass; adversarial-review finding 2026-08-10)
                        and must be >= the DETERMINISTIC
                        floor computed from the PR's changed-file set against
                        the hot-zone list (fleet-order-spec.md §4 "Floor note":
                        "gear classification is the DETERMINISTIC FLOOR
                        computed from the diff ... never the conductor's
                        choice"). The floor is a LOWER BOUND only: this repo's
                        deterministic PATH signal distinguishes "touches a
                        hot-zone path" (floor 3) from "everything else" (floor
                        1) — the middle "Gear 2 minimo, feature PR standard"
                        bucket needs human/semantic judgment no diff can
                        carry, so a non-hotzone PR floors at 1, never asserts
                        2 ON THE PATH TERM ALONE. compute_floor()'s optional
                        SIZE term (S1, 2026-08-27) is the one exception: a
                        diff large enough (measured via --numstat-file) DOES
                        assert floor 2 regardless of path — a diff already
                        past the PR contract's own ~400-net-line target needs
                        at least a session verdict even when it touches
                        nothing sensitive; see that function's own docstring.
                        The model may always raise gear above the floor; CI
                        here only catches a DOWNGRADE below it (harness-v2 §1
                        monotonia).
                        Reuses the merge-base-anchored file-enumeration
                        semantics of scripts/ci/hotzone_changed_files.sh (never
                        a two-dot diff — that is the exact W102 lie); this
                        script does not re-implement the enumeration, it
                        consumes its output via --changed-files-file so there
                        is one source of truth for "what did this PR touch".
                        HOTZONE_PATTERNS below is a deliberate, DECLARED
                        duplication of the case-block in
                        .github/workflows/hot-zone-pr-gate.yml (bash `case`
                        syntax is not importable from Python) — a future
                        consolidation into one JSON/py source is a fair
                        follow-up (see PENDING-ARMS), not a blocker here; until
                        then, a change to one list without the other is a
                        silent-drift risk a human reviewer should catch.

  7. gear ceiling  — the MIRROR of rule 6 (2026-08-21 audit,
                        research/operations/2026-08-21-token-ceremony-ci-
                        system-audit.md §7 lever L6 / §8): the floor stops a
                        diff from declaring LESS gear than a hot-zone hit
                        demands; the ceiling stops the opposite — a diff
                        shaped like a docs/ledger-only or small (<=2 files,
                        <=60 net lines) change may not silently declare
                        Gear 3 while also convening a `council` or
                        dispatching >=3 graders. REJECTED unless the pack
                        carries a non-empty, reasoned `gear_override:`
                        one-liner — in which case it is REPORTED (stderr
                        NOTICE), never a violation. The net-line count
                        prefers a MEASURED value (--net-lines /
                        --numstat-file, a real `git diff --numstat` sum)
                        over the pack's own self-declared `net_lines:` field
                        (adversarial-review finding 2026-08-21 — a pack
                        under-reporting its size must not escape the
                        ceiling); falling back to the self-declared value
                        also emits a "ceiling (notice)" line naming that
                        fact. Floor always wins when the two conflict: a
                        hot-zone hit floors AND ceilings at 3, silently. See
                        compute_ceiling()'s own docstring for the full
                        contract. Skipped, same as rule 6, whenever
                        --changed-files-file is not supplied.

  8. lanes seat diversity (D3) — every Gear >= 2 pack must declare `lanes:`
                        as a non-empty list. If it declares >= 2 build
                        lanes, at least one must use a non-Anthropic
                        builder seat. Gear 1 is exempt from both
                        requirements; fewer than 2 build lanes exempts only
                        the seat-diversity floor, not the `lanes:`
                        declaration. Missing `lanes:`, an empty `lanes: []`,
                        and a declared multi-build set with zero non-
                        Anthropic builders all share the same phased
                        rollout: before 2026-08-24 each emits a NOTICE and
                        does not fail; on/after 2026-08-24 each is a
                        violation. Shape violations (lanes not a list, entry
                        not a mapping, missing/empty lane/role/seat, invalid
                        role) fail immediately whenever `lanes:` is a
                        non-empty list. The flip date lives in code (not a
                        ledger) so the gate enforces it mechanically. Note
                        the asymmetry with rule 7: the ceiling check only
                        NOTICEs a self-declared gear that exceeds the
                        computed floor, but this rule treats that same
                        self-declared gear as binding — a builder who
                        cautiously over-declares `gear: 2` on a Gear-1-
                        shaped diff owes a `lanes:` block post-flip.

  9. seat rules by path class (E3/R8-R11, 2026-08-26 seat-rules program)
                        — phased rules, each a NOTICE before SEAT_RULES_
                        ENFORCEMENT_DATE (2026-09-02) and a violation
                        on/after, each honoring one shared, ALWAYS-
                        reported escape (`seat_override: <non-empty
                        reason>`, mirroring rule 7's `gear_override`).
                        Two ship here; two more (R11 cheap-seat floor,
                        R9 Gear-3 council) land in a follow-up PR on the
                        same module/phasing — not documented as live
                        until their own code does (a doctrine describing
                        a state that does not exist is worse than none):
                          (b) R8 ground-truth lane — a diff touching a
                              ground-truth path (backend KB, visa_engine,
                              a KBLI dataset, an official pricing table,
                              research/regulatory, or a mouth claim page
                              for visa/KBLI/tax/zoning/property) must
                              declare a lane {role: ground_truth, seat,
                              nb, query_hash} — `ground_truth` is a new
                              VALID_LANE_ROLES member so it coexists with
                              rule 8's own lane-shape check.
                          (c) R10 PII-local seat — a diff touching a PII
                              path (document intake, CRM/CRM-guardian,
                              the WhatsApp channel, the yield-optimizer
                              pitch gate) requires every lane's seat to
                              start with `ollama-`, unless the pack also
                              carries `cloud_ok: <DPA ref>` AND
                              `pii_scan: clean` (reads that existing
                              field, never re-derives PII status — same
                              boundary as rule 3).
                        Both are skipped, same convention as rules 6/7,
                        when there is no --changed-files-file.

  10. evidence root path deprecation (S12/C6 follow-through) — the fixed
                        root path `evidence/pack.yml` is deprecated. Two
                        Gear>=2 PRs writing that one path can never coexist
                        cleanly in the merge queue: whichever merges first
                        rewrites the file wholesale and every other open PR
                        carrying it goes DIRTY, by construction — measured
                        2026-08-27 on #5069/#4640/#5037/#5059, all four
                        DIRTY on the same pair within one hour of one
                        merge. `scripts/ci/evidence_paths.py` (S12/C6,
                        2026-08-23) gives every PR a collision-free
                        per-task directory instead
                        (`evidence/<YYYY-MM>/<task-slug>-<8hex>/`), and
                        harness-floor.yml has resolved through it
                        end-to-end since that date — this rule is what
                        actually moves pack producers off the root path.
                        Same phased shape as rule 8: before
                        `EVIDENCE_ROOT_DEPRECATION_DATE` (2026-09-05) a
                        root-path pack NOTICEs; on/after, it is a
                        violation. This rule judges THIS PR's own
                        diff-relative pack path (`--source-path`), never
                        the path the pack was actually read from — under
                        CI staging (see rule 5's brief_ref note) that is
                        always the canonical `evidence/pack.yml`
                        regardless of where the real file lives, so
                        checking the read path would flag every PR,
                        migrated or not. Skipped (no notice, no violation)
                        for a Python caller of lint()/
                        check_pack_not_at_deprecated_root() that supplies
                        no source_path info at all — same "skip, don't
                        guess" shape as rules 6/7 without
                        `--changed-files-file`. NOTE: via the CLI this is
                        NOT the same as omitting `--source-path` — the
                        flag defaults to the PACK_PATH positional argument
                        itself when absent, so a bare local invocation
                        (`evidence_pack_lint.py evidence/pack.yml`) is
                        actively judged, never silently skipped.

  11. countable claims (2026-08-29) — a number the pack states ABOUT ITSELF
                        and a machine can derive is DERIVED, not trusted.
                        Changed-file count and +insertions/-deletions are
                        recomputed from the same `git diff --numstat` blob
                        rule 6's size term already consumes; the commit
                        count is read from the GitHub event payload
                        (GITHUB_EVENT_PATH, so no workflow change is
                        needed) or from `--commit-count`; a test count
                        narrated in `diff`/`lanes` must be substantiated by
                        a receipt in the same pack, since a linter cannot
                        run the suite itself. Scanned subtrees are ONLY
                        `diff` and `lanes` — `dissent` and `receipts` are
                        judgment prose where a number legitimately
                        describes something other than this diff. An
                        unavailable measurement NOTICEs, never convicts.
                        `--print-measured` prints the canonical sentence to
                        paste, so the value need not be narrated by hand at
                        all. This removes an avoidable arithmetic-miss
                        class from the gate; it lowers no bar and rejects
                        nothing the rules above accepted.

  12. acceptance-probe pairing (2026-08-29) — an `acceptance:` bullet may
                        now be a mapping `{text, probe}` instead of a bare
                        string, where `probe:` names the command, test id,
                        or check that would prove the criterion true.
                        NOTICE-only, always (this rule never returns a
                        violation): names bullets with no declared probe,
                        declared probes absent from every receipt's
                        `claim`/`cmd` (an unrecorded outcome), and bullets
                        whose text carries none of the EARS keywords
                        WHEN/WHILE/IF/WHERE/SHALL as a whole UPPERCASE
                        word (case-sensitive — lowercase "if"/"when" in
                        ordinary prose does not count, or this very
                        docstring's own prose would trip it). HONEST
                        LIMIT, stated so it is never read as more than it
                        is: this checks FIELD PRESENCE ONLY — a receipt
                        claiming a probe ran is self-reported prose, not
                        proof of execution, until a CI step actually runs
                        it (see ASSEMBLY-LINE.md's enforcement backlog).

  13. assumptions register (2026-08-29) — an optional top-level `assumptions:`
                        list in `brief.yml`, each entry a mapping `{text,
                        status, probe}` where `status` is expected to be
                        `verified` or `unverified` and `probe` names the check
                        that would settle an `unverified` one. NOTICE-only,
                        always, and — unlike rule 12 — deliberately NOT
                        gear-gated: absence is already silent (measured 0/50
                        briefs on disk carry the block, 2026-08-29), so gating
                        an optional block would be a bypass, not a safeguard.
                        Names entries still `unverified`, entries whose status
                        is unrecognised or missing (a typo like `unverfied`
                        must not launder an unverified assumption into silence
                        — matching only the literal string would let it
                        through), and unverified entries with no `probe:` at
                        all. HONEST LIMIT, stated so it is never read as more
                        than it is: `status: verified` is self-reported prose —
                        this rule checks the SHAPE of the declaration, never
                        its TRUTH (see `check_assumptions_register`'s own
                        docstring and ASSEMBLY-LINE.md's enforcement backlog).

  14. appetite acknowledgment (2026-08-29) — an optional top-level
                        `appetite: {wall_clock_hours, adversarial_rounds,
                        tokens}` ceiling in `brief.yml`, declared at TRIAGE
                        next to the gear, checked against an optional
                        top-level `spend:` block in `pack.yml` (same three
                        keys, ex-post observed). THE ONLY RULE IN THIS LANE
                        THAT CAN FAIL — rules 11-13 above are NOTICE-only;
                        this one returns a real violation. A declared
                        numeric ceiling with observed spend strictly
                        greater than it (`observed > declared` — equality
                        is NOT a breach) and no non-empty
                        `appetite_exceeded:` acknowledgment in the pack
                        (mirrors rule 7's `gear_override` exactly) is
                        REJECTED, naming every breached dimension's
                        declared-vs-observed pair; the SAME breach WITH
                        that acknowledgment is REPORTED (stderr NOTICE),
                        never a violation. An unmeasured declared ceiling
                        (`spend:` absent, not a mapping, or no matching
                        numeric key) also only NOTICEs — "not verified
                        this run", never convicts. `appetite:` as
                        anything but a mapping — including the one real
                        corpus instance, a free-text `str` — declares no
                        machine-readable ceiling and stays SILENT, same
                        as absence. HONEST LIMIT, stated so it is never
                        read as more than it is: this is EX-POST /
                        PR-LIFETIME ACCOUNTING, NEVER AN IN-FLIGHT
                        BREAKER — values are self-reported, the linter
                        has no clock and no session-runtime access, and
                        it cannot interrupt a live session; it only makes
                        an overrun visible and demands acknowledgment
                        after the fact (see
                        `check_appetite_acknowledgment`'s own docstring).
                        Auto-suspend on breach and the default ceiling
                        VALUES are carried, not decided, here (lane spec
                        needs-ruling 1 and 3) — this rule ships
                        acknowledgment-only.

Floor check is SKIPPED (not silently passed — an explicit NOTICE on stderr)
when --changed-files-file is not supplied: not every invocation of this linter
has PR-diff context (e.g. a spot-check of a pack on a laptop). The CI workflow
(harness-floor.yml) is the required check that always supplies it. The
ceiling check (rule 7) is skipped under the same condition, for the same
reason. The lanes check (rule 8) does NOT depend on changed-files and always
runs.

VERDICT / EXIT CODES (fail-visible, superscar #2 "esiste != armato" antidote:
a lint that scanned nothing must not report clean):
  0  pack is conformant (floor check honored whenever changed-files is known)
  1  pack has 1+ REJECTED violations (guilt)
  2  BLIND — pack file missing/unreadable/not-a-mapping, refuses to report
     "clean" about a pack it never actually read
  3  usage error (bad CLI arguments)

CLI:
  python3 scripts/evidence_pack_lint.py [PACK_PATH] [--repo-root DIR]
      [--changed-files-file PATH] [--net-lines INT] [--numstat-file PATH]
      [--source-path PATH] [--print-floor] [--print-floor-source]
      [--effort-for GEAR] [--json] [--selftest]

  PACK_PATH        defaults to evidence/pack.yml (relative to --repo-root)
  --repo-root      defaults to the git top-level, else cwd
  --source-path    THIS PR's own diff-relative pack path (rule 9) — e.g.
                    the output of `evidence_paths.py --resolve pack`,
                    BEFORE any CI staging copies it to a canonical name.
                    Defaults to PACK_PATH itself, which is correct for a
                    direct/local invocation (the path you point the linter
                    at IS the real path) but MUST be passed explicitly by
                    a caller that stages the pack under a different name
                    (harness-floor.yml's Gear-3 step) — otherwise rule 9
                    always sees the staged literal and misjudges every PR.
  --changed-files-file  newline-delimited changed-path list (the output of
                        scripts/ci/hotzone_changed_files.sh) — enables rules
                        6 (floor) and 7 (ceiling)
  --net-lines INT  a pre-computed net-line count (e.g. `git diff --numstat
                    "$BASE" "$HEAD" | awk '{a+=$1;d+=$2} END {print a-d}'`,
                    merge-base anchored — never a two-dot diff, W102) for
                    rule 7's shape (b). Takes precedence over --numstat-file,
                    which takes precedence over the pack's own self-declared
                    `net_lines:` field. No effect without
                    --changed-files-file. Does NOT affect the rule-6 floor's
                    own size term (S1) — that one always reads
                    --numstat-file directly; see below.
  --numstat-file PATH  raw `git diff --numstat` output (tab-separated
                    added/deleted/path per line, `-`/`-` for binary files
                    skipped). Feeds TWO independent computations: the
                    CEILING's measured net-lines (this script sums
                    added-deleted itself so callers don't need the awk
                    one-liner — ignored there if --net-lines is also given,
                    which wins outright) and, always when given regardless
                    of --net-lines, the FLOOR's size term (S1, 2026-08-27 —
                    see compute_floor()'s docstring), which needs the raw
                    per-file rows rather than one pre-summed integer.
  --patch-file PATH  raw `git diff` text for the `.github/workflows/`
                    files in this diff (any -U level). Feeds ONE thing: the
                    FLOOR's path-term EXEMPTION for first-party action
                    version pins (2026-09-01 — see
                    workflow_paths_exempt_from_path_term()). Strictly
                    opt-in and strictly fail-closed: omitted, missing or
                    unreadable, NOTHING is exempted and the floor is
                    exactly what it was before the exemption existed —
                    which is why, unlike --numstat-file, an unreadable
                    --patch-file is a stderr notice and not exit 3.
  --print-floor    given --changed-files-file, print the computed floor int
                    and exit 0 (no pack read) — lets any caller (CI, a human)
                    ask "what floor would this diff impose" without spinning
                    up a second implementation of HOTZONE_PATTERNS. Also
                    honors --numstat-file when given (S1's size term) — omit
                    it for the path-only floor exactly as before that term
                    existed. Honors --patch-file the same way (the
                    first-party-pin exemption).
  --print-floor-source  given --changed-files-file, print WHY the floor is
                    what it is (S2, 2026-08-27) — one of "none"/"path"/
                    "size"/"both" (see compute_floor_source()'s docstring)
                    and exit 0. Same --numstat-file handling as
                    --print-floor. Lets harness-floor.yml distinguish a
                    floor==2 diff reached via the SIZE term (grace period,
                    SIZE_GEAR2_ENFORCEMENT_DATE) from a hypothetical
                    path-sourced floor==2 (no grace) — see that constant's
                    own comment in harness-floor.yml for the full contract.
  --effort-for GEAR  print effort_for_gear(GEAR) (medium/xhigh) and exit 0
                    (no pack, no repo-root needed) — lets a wrapper look up
                    "what effort should this gear run at" without importing
                    this module; exit 3 (usage error) if GEAR isn't 1/2/3
  --json           machine-readable {"exit": N, "violations": [...]} on stdout
  --selftest       run the embedded guilt+innocence corpus and exit 0/1

Registered in infra/guard-conformance/registry.json (surface
"evidence_pack_lint", census method ast-def-prefix "check_") — every
`check_*` function below is a censused guard and needs both proofs there.
"""

from __future__ import annotations

import argparse
import datetime
import fnmatch
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Hot-zone floor (rule 6) — DELIBERATE, DECLARED duplication of the case-block
# in .github/workflows/hot-zone-pr-gate.yml. Keep the two lists in sync by
# hand until a follow-up extracts one shared source (PENDING-ARMS).
# ---------------------------------------------------------------------------
HOTZONE_PATTERNS: tuple[str, ...] = (
    "apps/backend-rag/backend/db/migrations_v2/*",
    "apps/backend-rag/backend/app/auth/*",
    "apps/backend-rag/backend/app/core/config.py",
    "apps/backend-rag/backend/services/invoicing/*",
    "apps/backend-rag/backend/services/pricing/*",
    "scripts/nuzantara-sentinel.py",
    "scripts/dlq_autopilot.py",
    "scripts/lint_launchagents.sh",
    "scripts/lint_migration_numbers.py",
    "infra/launchagents/*",
    "docs/infra/launchagents/*",
    ".github/workflows/*",
    ".github/CODEOWNERS",
    "fly.toml",
    "apps/backend-rag/fly.toml",
)

# ---------------------------------------------------------------------------
# Path-term EXEMPTION: first-party action version pins (2026-09-01, owner
# ruling "Cambio la regola adesso").
#
# `.github/workflows/*` is in HOTZONE_PATTERNS because a workflow edit can
# disarm a gate. A version bump of an action it already uses cannot: it adds
# no step, removes no step, and changes no `if:`, `permissions:` or `paths:`.
# Yet it floored at Gear 3 and demanded a full evidence pack — measured
# 2026-09-01 on PRs #5442 / #5444 / #5445, each a ONE-to-TWO-line `uses:` pin
# whose ONLY red check was "Harness floor recompute". Three mechanical bumps
# sat blocked behind a ceremony that reads none of what they changed.
#
# The exemption is decided by the DIFF's CONTENT, never by its AUTHOR. That is
# deliberate and is the whole safety argument: scar W98 is a Dependabot bump
# that shipped a malicious `fastapi` to PROD past a constraint the updater
# could not see, so "dependabot[bot] opened it" must never be a key that opens
# a gate. A human hand-editing the same line gets the same treatment, and a
# bot that changes anything else gets none.
#
# Three conditions, ALL required, per workflow file:
#   1. every ADDED and REMOVED line parses as a `uses: <owner>/<repo>@<ref>`
#      line — one non-conforming changed line re-arms the path term for the
#      whole file;
#   2. every such owner is FIRST-PARTY (FIRST_PARTY_ACTION_OWNERS) — a
#      third-party action IS a live supply-chain surface and keeps its floor;
#   3. the multiset of action IDENTITIES on the minus side EQUALS the one on
#      the plus side — so only refs may move. This is what stops the swap
#      attack (`actions/checkout` -> `actions/chekcout`): the identities would
#      differ and the file falls back to Gear 3.
#
# FAIL-CLOSED by construction: the exemption needs a patch to be PROVEN, and
# `patch=None` (every caller that does not pass one) exempts nothing at all —
# so a missing, unreadable or truncated patch floors exactly as it did before
# this existed. A file with no parsed hunks (mode change only) is likewise not
# proven safe and is not exempted.
#
# What this does NOT touch: `.github/workflows/*` stays in HOTZONE_PATTERNS
# verbatim, so hot-zone-pr-gate.yml's deliberately duplicated case-block still
# matches these PRs and no drift is introduced between the two lists. This is
# an exemption applied to the FLOOR term, not a change to hot-zone membership.
# ---------------------------------------------------------------------------
FIRST_PARTY_ACTION_OWNERS: frozenset[str] = frozenset({"actions", "github"})

WORKFLOW_DIR_PREFIX = ".github/workflows/"

#: A single `uses:` step reference. Tolerates the list-item dash, quotes, and
#: the trailing `# v4.37.9` comment that accompanies a SHA pin (PR #5444's
#: exact shape) — the comment is discarded, the identity and ref are not.
_USES_LINE_RE = re.compile(
    r"""^\s*(?:-\s+)?uses:\s*
        ["']?(?P<identity>[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9._/-]+)
        @(?P<ref>[^\s"'\#]+)["']?
        \s*(?:\#.*)?$""",
    re.VERBOSE,
)


#: A ref that PINS. Either a full 40-hex commit SHA (what Dependabot writes when
#: a repo pins by SHA, and what GitHub Actions requires — an abbreviated SHA is
#: not a valid `uses:` ref) or a version-shaped tag: `v4`, `v7`, `4.37.9`,
#: `v4.37.9`, `v1.2.3-beta.1`. Deliberately NOT `main`, `master`, `latest`,
#: `release` or any other branch name.
_PINNED_REF_RE = re.compile(
    r"^(?:[0-9a-f]{40}|v?\d+(?:\.\d+)*(?:-[A-Za-z0-9.]+)?)$"
)


def _first_party_uses_identity(line: str) -> str | None:
    """The `<owner>/<repo>[/<path>]` of a first-party `uses:` line, else None.

    None means BOTH "this is not a uses: line at all" and "this is a uses:
    line for a third-party action" — the caller treats them identically
    (the file keeps its Gear-3 floor), so they deliberately share a return."""
    m = _USES_LINE_RE.match(line)
    if m is None:
        return None
    identity = m.group("identity")
    if identity.split("/", 1)[0] not in FIRST_PARTY_ACTION_OWNERS:
        return None
    # The ref must PIN. "Only refs may move" was under-specified: it permitted
    # `actions/checkout@v4` -> `@main`, which is not a version bump at all but an
    # UNPINNING — the action stops being fixed and starts tracking a branch
    # somebody else can move. That is a supply-chain change of exactly the kind
    # this hot zone exists to catch, and the rule is named for version PINS.
    # Found 2026-09-01 by the adversarial reviewer as attack 1b, which it called
    # "worth a conscious decision, not obviously a blocker" — the decision is to
    # refuse it. Both sides are checked (each line goes through here), so a
    # re-pin `@main` -> `@v4` also floors at 3: rare, deliberate, and worth a
    # human look in the direction that adds a constraint as well as the one that
    # removes it.
    if not _PINNED_REF_RE.match(m.group("ref")):
        return None
    return identity


def workflow_paths_exempt_from_path_term(patch: str) -> set[str]:
    """Workflow files in `patch` whose ENTIRE change is first-party version pins.

    `patch` is raw `git diff` text (any -U level; -U0 is what harness-floor.yml
    produces). Returns a subset of the `.github/workflows/` paths it contains —
    never any other path, so this can only ever narrow the path term for the
    one directory it was written for (asserted by its own innocence test).

    Pure function, no I/O — guilt+innocence tests drive it directly."""
    per_file: dict[str, dict[str, Any]] = {}
    current: str | None = None
    in_hunk = False

    for raw in patch.splitlines():
        if raw.startswith("diff --git "):
            # b-side is the post-image path; refined by the `+++ ` line below
            # when there is one (a pure deletion has `+++ /dev/null`).
            current, in_hunk = None, False
            _, _, b_side = raw.partition(" b/")
            if b_side:
                current = b_side
                per_file.setdefault(current, {"minus": [], "plus": [], "clean": True})
            continue
        if raw.startswith("+++ ") and not in_hunk:
            # `and not in_hunk` is load-bearing, not defensive tidiness. A diff
            # ADDS a single "+", so a workflow line that itself begins "++ " is
            # emitted as "+++ …" — indistinguishable, by prefix alone, from a
            # new-file header. Reading it as a header reassigned `current` to a
            # phantom path AND set in_hunk=False, after which every remaining
            # line of that hunk was SILENTLY SKIPPED: a `+permissions:
            # write-all` following the forged line never reached the parser, so
            # a privilege escalation rode along inside a diff the floor scored
            # as a pure version pin. Found 2026-09-01 by the independent gate.
            #
            # It also falsified this function's own comment ("one non-conforming
            # changed line re-arms the path term for the whole file") — a
            # non-conforming ADDED line did not re-arm. Inside a hunk these
            # bytes are CONTENT: they fall through to the +/- branch below,
            # fail to parse as a `uses:` line, and set clean=False, which is
            # what the comment always claimed.
            #
            # `diff --git ` needs no such guard: git prefixes every content line
            # with " ", "+", "-" or "\\", so column 0 can never be "d" inside a
            # hunk. `--- ` needs none either — in a hunk it is already read as a
            # removed line whose body "-- …" does not parse.
            candidate = raw[4:].split("\t", 1)[0]
            if candidate.startswith("b/"):
                candidate = candidate[2:]
            if candidate and candidate != "/dev/null":
                current = candidate
                per_file.setdefault(current, {"minus": [], "plus": [], "clean": True})
            in_hunk = False
            continue
        if current is None:
            continue
        if raw.startswith("@@"):
            in_hunk = True
            continue
        if not in_hunk:
            # `index`, `old mode`, `--- a/...`, `similarity index` — headers,
            # not content. Checked BEFORE the +/- branch below precisely so a
            # `--- a/path` line is never mistaken for a removed content line.
            continue
        state = per_file[current]
        if raw.startswith("+"):
            body, bucket = raw[1:], "plus"
        elif raw.startswith("-"):
            body, bucket = raw[1:], "minus"
        else:
            continue  # context line, or `\ No newline at end of file`
        identity = _first_party_uses_identity(body)
        if identity is None:
            state["clean"] = False
        else:
            state[bucket].append(identity)

    exempt: set[str] = set()
    for path, state in per_file.items():
        if not path.startswith(WORKFLOW_DIR_PREFIX) or ".." in path.split("/"):
            # `.github/workflows/../../fly.toml` passes a naive
            # startswith() and names ANOTHER hot zone. It is already
            # harmless — compute_floor intersects this set against the
            # REAL changed-file list, where git records the normalised
            # path — but a defence that only holds because of a property
            # two functions away is one refactor from not holding, so
            # the boundary is restated at the parser too.
            continue
        if not state["clean"]:
            continue
        if not state["plus"] and not state["minus"]:
            continue  # no content hunk parsed -> not PROVEN safe -> no exemption
        if state["minus"] != state["plus"]:
            # SEQUENCE equality, not multiset. The first cut compared
            # sorted() and was defeated by a REORDER: two bare one-line
            # steps whose `uses:` lines swap places have an identical
            # multiset of identities, so they were exempted — while
            # actually changing execution order, which is a semantic change
            # and can vacuously disarm a scan that ran before the step
            # producing what it scans. Found 2026-09-01 by a cross-family
            # refuter (tp1 deepseek-v4-flash-0731), whose answer was cut off
            # at 214 bytes and still contained this. Both lists are in file
            # order, so a pure ref change leaves them identical and anything
            # that adds, removes, swaps or REORDERS an action does not.
            continue
        exempt.add(path)
    return exempt


def _read_patch_file(path: str | None) -> str | None:
    """Read a --patch-file, or None. Unreadable is None, NOT an error exit.

    Deliberately asymmetric with --numstat-file's `return 3`: that file can
    only ever RAISE a floor, so losing it silently would under-gate; this one
    can only ever LOWER a floor, so losing it fails CLOSED all by itself —
    no patch, no exemption, Gear 3 exactly as before. Turning an unreadable
    patch into a usage error would instead take a workflow that is behaving
    conservatively and paint it red."""
    if not path:
        return None
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        # UnicodeDecodeError is NOT an OSError — it is a ValueError — so an
        # earlier cut of this caught only OSError and let a patch containing one
        # invalid UTF-8 byte raise straight through: traceback, no floor on
        # stdout, exit 1. That could never UNDER-gate (the crash precedes
        # compute_floor), but it broke the contract this docstring promises and
        # the comment above it was therefore false. Found 2026-09-01 by the
        # adversarial reviewer, which graded it a suggestion rather than a hole;
        # a comment that lies about a fail-closed path is worth curing anyway,
        # because the next reader trusts it. Discards the WHOLE patch rather
        # than decoding with errors="replace": a workflow file that is not valid
        # UTF-8 is anomalous, and refusing every exemption in that patch is the
        # conservative reading.
        print(
            f"evidence_pack_lint: --patch-file unreadable ({exc}) — "
            "no path-term exemption applied (fail-closed)",
            file=sys.stderr,
        )
        return None


RECEIPT_REQUIRED_FIELDS = ("claim", "cmd", "exit", "ts", "seat")
SIZE_TOKEN_CAP = 30_000
VALID_GEARS = (1, 2, 3)

# D3 seat-diversity rule (fleet-order program): a Gear >= 2 pack must declare
# lanes; when it declares >= 2 build lanes, at least one builder seat must be
# non-Anthropic. The flip date lives IN THE LINT because a ledger line nobody
# reads cannot gate a merge — the code itself must enforce the grace window.
# Before 2026-08-24 either breach NOTICES; on/after 2026-08-24 it FAILS.
# (Rule ratified 2026-08-22 with a 14-day grace to 2026-09-05; owner ruling
# 2026-08-23 shortened the grace to 2026-08-24 — the rule had never actually
# fired on anything, and the fleet lanes running right now are the ones that
# must adopt `lanes:`, so a two-week wait bought two more weeks of zero
# adoption instead of protecting anyone from a live enforcement surprise.)
LANES_NON_ANTHROPIC_ENFORCEMENT_DATE = datetime.date(2026, 8, 24)

#: Minimal rule-8-conformant ``lanes`` block for selftest fixtures whose subject
#: is some OTHER rule (dissent, hot-zone, ceiling, net-lines). Added 2026-08-24
#: after the enforcement date above went live at UTC midnight and turned five
#: unrelated innocence fixtures red — they had been riding the grace period, so
#: the repo's merge queue stopped merging with no code change anywhere. Rule 8's
#: own guilt/innocence lives in the dedicated `check_lanes_build_seat_diversity`
#: cases, which pin `today` on both sides of the flip and are unaffected by this.
_SELFTEST_LANES = [{"lane": "D1", "role": "build", "seat": "codex"}]
VALID_LANE_ROLES = ("build", "review", "read", "ground_truth")
#: "ground_truth" added 2026-08-26 (E3/R8, seat-rules program) so a pack can
#: carry a {role: ground_truth, seat: nlm, ...} lane on a KB/visa_engine/
#: KBLI/pricing/regulatory-claim path WITHOUT tripping rule 8 (D3)'s own
#: "role must be one of VALID_LANE_ROLES" shape check on the same `lanes:`
#: list — the two rules share the list, not fight it. A ground_truth-role
#: entry is never counted toward D3's build-lane seat-diversity math (only
#: role=="build" is), so this extension changes no existing rule-8 verdict.

# Rule 9 (evidence root path deprecation, S12/C6 follow-through) — same
# "flip date lives in code, not a ledger" reasoning as
# LANES_NON_ANTHROPIC_ENFORCEMENT_DATE above. ~9 days of grace from the date
# this rule shipped (2026-08-27) for in-flight PRs to migrate their pack to a
# per-task directory before the root path starts failing the gate outright.
EVIDENCE_ROOT_DEPRECATION_DATE = datetime.date(2026, 9, 5)

#: The literal root path this rule deprecates — matches the fallback
#: `resolve_evidence_path()` returns in scripts/ci/evidence_paths.py when a
#: PR's diff touches neither a root nor a per-task evidence/pack.yml.
EVIDENCE_ROOT_PACK_PATH = "evidence/pack.yml"

# Rule 12 (evidence root path deprecation — THE BRIEF HALF). Rule 9 above
# closes only half the surface it was written for: it compares the resolved
# PACK path against EVIDENCE_ROOT_PACK_PATH and returns clean otherwise, so it
# is structurally blind to where the BRIEF lives. Measured on origin/main
# 2026-08-31 by executing check_pack_not_at_deprecated_root directly with
# `today` past the flip date: a source_path of
# `evidence/2026-08/<slug>/pack.yml` returns ([], None) — clean at ANY date —
# while that same PR's diff can still MODIFY the repo-root evidence/brief.yml
# and collide with every other PR that does. That is not hypothetical: of the
# 31 open PRs that day, SIX wrote the root brief (#5158 #5072 #5037 #4645
# #4644 #4640), and #5158 had exactly the invisible shape — pack correctly
# migrated to a per-task directory, brief still at the root, Rule 9 green.
#
# WHAT THIS RULE MUST NOT DO, and the reason it is easy to get wrong: every
# conformant pack is REQUIRED to declare the literal string
# `brief_ref: evidence/brief.yml` (the staging contract — harness-floor.yml
# lints a synthetic tree where both files carry canonical names, see
# scripts/ci/evidence_paths.py's module docstring). So that exact string
# appears inside every correct pack in the repo. This rule judges a PATH THIS
# PR'S DIFF WROTE, never a string in a field — conflating the two would fail
# every conformant pack in the fleet. The innocence tests pin that distinction.
#
# THE DATE IS DELIBERATELY *NOT* EVIDENCE_ROOT_DEPRECATION_DATE. Riding the
# pack's 2026-09-05 would silently re-price a measurement taken the same day
# this rule was written: research/operations/2026-08-31-two-nine-enforcement-
# readiness.md measured "3 PRs newly RED if EVIDENCE_ROOT moves alone"
# (#5072 #5037 #4640) and Zero's standing instruction there was to move dates
# only "if we are ready". Adding the brief to that date turns 3 into 6 without
# anyone re-measuring — a number aging into a lie, which is the exact defect
# class this file's own PR history spent 2026-08-31 correcting. So: its own
# constant, one week past the pack's, giving the six in-flight PRs a real
# window to migrate and giving the next readiness pass a separate number to
# price.
EVIDENCE_ROOT_BRIEF_DEPRECATION_DATE = datetime.date(2026, 9, 12)

#: The literal root brief path — the sibling of EVIDENCE_ROOT_PACK_PATH, and
#: the same value `resolve_evidence_path("brief", ...)` falls back to.
EVIDENCE_ROOT_BRIEF_PATH = "evidence/brief.yml"


# --------------------------------------------------------------------- utils


def repo_root_default() -> Path:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip()
        if out:
            return Path(out)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return Path(".").resolve()


# ---------------------------------------------------------------------------
# Floor SIZE TERM (S1, 2026-08-27 — research/operations/2026-08-26-retro-
# fleet-sessions-25-26.md "S1"): compute_floor() was PATH-ONLY — a diff could
# rewrite tens of thousands of lines across dozens of files and still floor
# at Gear 1 unless it happened to touch a hot-zone path (measured: of PRs
# >1500 net lines in a 48h window, only 5/12 carried a brief — a 4,979-line
# rewrite of the public funnel UI and a 1,618-line PII-in-logs cure both got
# none, neither touched .github/workflows/* or the other hot-zone globs).
# This is the SIZE half of the floor: a diff large enough gets Gear 2 or
# Gear 3 regardless of which paths it touches.
# SIZE_GEAR3_THRESHOLD is pinned at the measured p90 of CHURN
# (additions+deletions) over the 170 most recently merged PRs at
# ratification time (`gh pr list --state merged --limit 170 --json
# additions,deletions`), clamped to never go below 1500 — measured
# 2026-08-27: p90 == 1828. CHURN, not a plain add-minus-delete net: an
# earlier draft of this constant was calibrated on |additions-deletions|,
# matching what _size_term_net_lines() computed at the time — cross-family
# adversarial review (codex-sol, PR #5049) found that pairing gameable by a
# balanced in-place rewrite (2,000 added + 2,000 deleted in the SAME file
# nets to zero), so both the runtime formula below and this threshold's
# calibration moved to churn together, keeping them measuring the same
# distribution. SIZE_GEAR2_THRESHOLD reuses the Agent PR Contract's own
# ~400-net-line target (CLAUDE.md rule 1): a diff already past the
# contract's own size guidance floors at Gear 2, never silently at Gear 1.
# ---------------------------------------------------------------------------
SIZE_GEAR2_THRESHOLD = 400
SIZE_GEAR3_THRESHOLD = 1828  # measured churn p90, 170 merged PRs, 2026-08-27 (floor clamp: never < 1500)

# Paths excluded from the size term: generated output, vendored trees,
# lockfiles, minified bundles and binary/image assets inflate a numstat
# without inflating the blast radius a human reviewer actually has to read.
# Directory-name checks match a real PATH SEGMENT (PurePosixPath parts), not
# a substring — `not_fixtures/x.py` is NOT excluded, only a genuine
# `fixtures/`/`generated/`/vendored-tree path component is (superscar #3
# guard-over-match discipline). `vendor`/`node_modules`/`dist`/`build` added
# after the same review found `vendor/evoskill` (a real vendored tree in
# this repo) had no exclusion at all — a routine vendor bump would have
# false-floored at Gear 3 on volume alone.
SIZE_TERM_EXCLUDE_DIR_NAMES: tuple[str, ...] = (
    "fixtures", "generated", "vendor", "vendored", "node_modules", "dist", "build",
)
SIZE_TERM_EXCLUDE_FILENAMES: tuple[str, ...] = (
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "Cargo.lock", "uv.lock", "Gemfile.lock", "composer.lock",
)
#: Exact repo-relative PATHS (never a basename, never a glob) for this
#: repo's own pip-compile-style, hash-pinned, machine-derived lockfiles —
#: added 2026-09-02 after measurement on PR #5530 (a routine 55-package pip
#: dependabot bump, `gh api repos/Bali-Zero/Teman2/pulls/5530/files`): the
#: two files carried 3570 of 3672 total churned lines (97%); the remaining
#: 102 lines, spread across 5 human-reviewable `requirements*.txt` files,
#: still count in full.
#:
#: Went through TWO adversarial rounds on this same PR before landing here:
#: (1) a glob `requirements*.lock.txt` matched any basename in that shape,
#: including a hand-added `requirements-backdoor.lock.txt` nobody's tooling
#: produced; (2) fixing that to two exact LITERALS still matched by
#: basename only (`PurePosixPath(path).name`), so the same fabricated
#: content at `docs/requirements.lock.txt` or any other directory still
#: exempted itself — the well-known package-manager names above accept
#: that basename-only risk because they are unambiguous, single-ecosystem
#: conventions; "requirements.lock.txt" is generic enough that a decoy
#: elsewhere in the tree is a real, not hypothetical, shape. This repo
#: already treats exactly that shape as suspicious in the OTHER direction
#: (`scripts/prepush_classify.py`'s `NEVER_INNOCENT_BASENAMES`, proven by
#: `test_guilt_requirements_family_under_an_allowlisted_prefix_forces_full`
#: in `scripts/tests/test_prepush_classify.py`: a requirements manifest
#: under an allowlisted prefix it doesn't really live under must force
#: full attention, never read as innocent) — matching that discipline here
#: means exempting by FULL PATH, not name. Only these two exact,
#: currently-real paths are exempted; a genuine future sibling (e.g. a
#: split requirements-dev.lock.txt) needs its own literal added here.
SIZE_TERM_EXCLUDE_EXACT_PATHS: tuple[str, ...] = (
    "apps/backend-rag/requirements.lock.txt",
    "apps/backend-rag/requirements-prod.lock.txt",
)
SIZE_TERM_EXCLUDE_SUFFIXES: tuple[str, ...] = (
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp",
    ".pdf", ".zip", ".gz", ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".mp4", ".mp3", ".wav", ".mov",
)


def _is_size_term_excluded(path: str) -> bool:
    """True when `path` should NOT count toward the size term (S1):
    generated/vendored output, well-known lockfiles, minified bundles, and
    binary/image assets. See the SIZE_TERM_EXCLUDE_* tuples above for what
    and why. Deliberately NOT a blanket `*.lock`/`*.lock.txt` suffix or glob
    match (adversarial review, PR #5049 and again PR #5531): the mandate's
    "lockfiles" meant the well-known, actually-produced ones enumerated
    above, not every file a script happens to name that way — this repo's
    own coordination primitives use `*.lock` for real hand-written state
    (CLAUDE.md's `agent_lock:<resource>` Redis keys), and a blanket
    suffix/glob match would let a diff touching real lock-coordination
    code — or a fabricated file chosen to LOOK like a lockfile — hide
    behind the same exemption (superscar #3, W98-class). The well-known
    package-manager names in SIZE_TERM_EXCLUDE_FILENAMES match by BASENAME
    (any directory) because each is an unambiguous single-ecosystem
    convention; SIZE_TERM_EXCLUDE_EXACT_PATHS matches by FULL repo-relative
    PATH ONLY (PR #5531 round 2) because "requirements.lock.txt" is a
    generic enough name that a same-named decoy elsewhere in the tree is a
    real risk, not a hypothetical one."""
    p = PurePosixPath(path)
    if any(part in SIZE_TERM_EXCLUDE_DIR_NAMES for part in p.parts[:-1]):
        return True
    if p.as_posix() in SIZE_TERM_EXCLUDE_EXACT_PATHS:
        return True
    name = p.name
    if name in SIZE_TERM_EXCLUDE_FILENAMES:
        return True
    if ".min." in name.lower():
        return True
    return any(name.lower().endswith(suf) for suf in SIZE_TERM_EXCLUDE_SUFFIXES)


def _size_term_net_lines(numstat: str) -> int:
    """Σ(added+deleted) — CHURN, not a plain add-minus-delete net — over
    non-excluded files (S1's size term). Pure function, no I/O, mirrors
    sum_numstat()'s own parsing but differs from it in the two ways that
    matter here: (1) it sums BOTH added and deleted lines PER FILE rather
    than netting them, so a diff that deletes 10k lines from one file and
    adds 10k to another does not cancel to zero — sum_numstat()'s plain
    global net exists for compute_ceiling()'s "is this diff small" question,
    where that cancellation is the right behavior; this is the opposite
    question ("is this diff big"), where cancellation would hide exactly
    the blast radius S1 exists to catch. CORRECTED 2026-08-27 (adversarial
    review, codex-sol, PR #5049): the first cut summed the PER-FILE
    ABSOLUTE net (`abs(added-deleted)`) instead, which is gameable by a
    balanced in-place rewrite — 2,000 added + 2,000 deleted in the SAME
    file summed to zero, hiding a genuinely full rewrite from the floor
    entirely; churn cannot cancel that way, by construction. (2) it
    excludes generated/vendored/binary paths (_is_size_term_excluded) that
    inflate churn without inflating review burden. Binary rows
    ("-\\t-\\tpath") and malformed lines are skipped, same as
    sum_numstat(). CORRECTED again 2026-09-02 (adversarial review, codex-sol,
    PR #5531, round 3): the blankness check used to be `line = line.strip()`
    on the WHOLE line before splitting, which silently strips leading/
    trailing whitespace off the PATH field too — git permits a trailing
    space in a real filename, so a decoy committed as
    "apps/backend-rag/requirements.lock.txt " (note the space) numstat's as
    that literal string, gets stripped to the real lockfile's exact name,
    and its churn vanishes from the size term entirely. `sum_numstat()`
    above does the identical whole-line strip but is safe from this class —
    it never looks at `path` for a decision, only at the two numeric
    fields. Here, where `path` gates an exclusion, blankness is checked
    without mutating the line the path is sliced from."""
    net = 0
    for line in numstat.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added_s, deleted_s, path = parts[0], parts[1], parts[2]
        if added_s == "-" or deleted_s == "-":
            continue  # binary file — numstat can't report a line count
        if _is_size_term_excluded(path):
            continue
        try:
            net += int(added_s) + int(deleted_s)
        except ValueError:
            continue
    return net


FLOOR_SOURCE_NONE = "none"
FLOOR_SOURCE_PATH = "path"
FLOOR_SOURCE_SIZE = "size"
FLOOR_SOURCE_BOTH = "both"
FLOOR_SOURCES = (FLOOR_SOURCE_NONE, FLOOR_SOURCE_PATH, FLOOR_SOURCE_SIZE, FLOOR_SOURCE_BOTH)


def _compute_floor_with_source(
    changed_files: list[str], numstat: str | None = None, patch: str | None = None
) -> tuple[int, str]:
    """Single source of truth for compute_floor()/compute_floor_source() — the
    two public entry points are thin wrappers over this so they can never
    drift apart (S2, 2026-08-27, gate round 2 on PR #5049: the workflow needs
    to know WHY a floor is what it is, not just the number, to grant the
    SIZE_GEAR2_ENFORCEMENT_DATE grace period ONLY to floor==2 diffs that got
    there via the size term — never to a hypothetical future path-based
    floor==2, which would get no grace).

    Returns (floor, source). `source` in FLOOR_SOURCES:
      - "none": neither term fired (floor == 1).
      - "path": a hot-zone hit alone explains the floor (floor == 3).
      - "size": the size term alone explains the floor (floor == 2, i.e.
        SIZE_GEAR2_THRESHOLD <= churn < SIZE_GEAR3_THRESHOLD with no
        hot-zone hit; OR floor == 3 via churn >= SIZE_GEAR3_THRESHOLD with
        no hot-zone hit).
      - "both": a hot-zone hit AND churn >= SIZE_GEAR3_THRESHOLD are BOTH
        present — i.e. removing EITHER term alone would still leave the
        other one flooring at 3 on its own. Deliberately NOT triggered by a
        hot-zone hit alongside a merely SIZE_GEAR2_THRESHOLD-level churn:
        in that case the path term is doing all the real work (floor stays
        3 with or without the size signal, which never independently
        cleared the Gear-3 bar), so source is "path", not "both" — "both"
        means both terms are independently sufficient, not merely both
        present.

    PROVABLE INVARIANT, not just an empirical fact about today's
    HOTZONE_PATTERNS: floor == 2 implies source == "size", always. A
    hot-zone hit sets floor = 3 BEFORE the size term ever runs, and nothing
    in the size term's branches can lower a floor already at 3 (`max(3, 2)
    == 3`) — so the only way this function returns exactly 2 is the size
    term's own `elif` branch firing with the path term never having fired
    at all. The workflow can therefore gate the SIZE_GEAR2_ENFORCEMENT_DATE
    grace period on `floor == 2` alone with identical behavior to also
    checking `source == "size"` — the explicit source check is kept anyway,
    both to self-document the condition for a reader who doesn't know this
    invariant, and so the grace-period gating stays correct even if a
    future HOTZONE_PATTERNS change ever made a path-sourced floor==2
    reachable (it would then correctly get NO grace, unlike a bare
    `floor == 2` check).

    Pure function — no I/O, no git — so guilt+innocence tests exercise it
    directly without a filesystem fixture; the caller is responsible for
    producing `numstat` (e.g. `git diff --numstat`, merge-base anchored —
    never a two-dot diff, W102)."""
    # Files PROVEN to be nothing but first-party action version pins are
    # skipped by the path term (2026-09-01) — see
    # workflow_paths_exempt_from_path_term()'s own block for the three
    # conditions and the W98 reason the test is on CONTENT, not on author.
    # `patch=None` yields an empty set, so every caller that does not supply
    # a patch computes exactly the floor it computed before this existed.
    exempt = workflow_paths_exempt_from_path_term(patch) if patch else frozenset()
    path_hit = False
    for f in changed_files:
        if f in exempt:
            continue
        for pat in HOTZONE_PATTERNS:
            if fnmatch.fnmatchcase(f, pat):
                path_hit = True
                break
        if path_hit:
            break

    floor = 3 if path_hit else 1
    size_hit_gear3 = False
    size_hit_gear2 = False
    if numstat is not None:
        size_net = _size_term_net_lines(numstat)
        if size_net >= SIZE_GEAR3_THRESHOLD:
            size_hit_gear3 = True
            floor = 3
        elif size_net >= SIZE_GEAR2_THRESHOLD:
            size_hit_gear2 = True
            floor = max(floor, 2)

    if path_hit and size_hit_gear3:
        source = FLOOR_SOURCE_BOTH
    elif path_hit:
        source = FLOOR_SOURCE_PATH
    elif size_hit_gear3 or size_hit_gear2:
        source = FLOOR_SOURCE_SIZE
    else:
        source = FLOOR_SOURCE_NONE

    return floor, source


def compute_floor(
    changed_files: list[str], numstat: str | None = None, patch: str | None = None
) -> int:
    """The deterministic floor (rule 6 docstring): the HIGHER of two
    independent terms.

    PATH TERM: 3 on any hot-zone hit (HOTZONE_PATTERNS), else 1 — EXCEPT
    for a `.github/workflows/` file whose entire change is first-party
    action version pins, when an optional `patch` proves it (2026-09-01;
    see workflow_paths_exempt_from_path_term). `patch=None` exempts
    nothing, so the term is unchanged for every caller that omits it.

    SIZE TERM (S1, 2026-08-27, optional — only asserted when `numstat` is
    given): a blast-radius measure over raw `git diff --numstat` text — see
    _size_term_net_lines()'s own docstring for exactly what it counts and
    why. >= SIZE_GEAR3_THRESHOLD floors at 3; >= SIZE_GEAR2_THRESHOLD raises
    the floor to at least 2 — the ONE path by which this function can
    return 2 at all (the path term alone never does; see the module
    docstring's rule-6 section). `numstat=None` (the default) skips the
    size term entirely and returns exactly what this function returned
    before the term existed — no caller that never passes it is affected.

    Thin wrapper over _compute_floor_with_source() — see that function for
    the shared implementation and compute_floor_source() for the sibling
    entry point that returns WHY, not just the number (S2, 2026-08-27)."""
    return _compute_floor_with_source(changed_files, numstat, patch)[0]


def compute_floor_source(
    changed_files: list[str], numstat: str | None = None, patch: str | None = None
) -> str:
    """Sibling of compute_floor(), same inputs, returns WHY the floor is
    what it is instead of the floor itself — one of FLOOR_SOURCES
    ("none"/"path"/"size"/"both"). Added S2 (2026-08-27, gate round 2 on PR
    #5049): harness-floor.yml's Step 5b needs to distinguish a floor==2 diff
    that got there via the SIZE term (grace period applies,
    SIZE_GEAR2_ENFORCEMENT_DATE) from a hypothetical path-sourced floor==2
    (would get none) — see _compute_floor_with_source()'s docstring for the
    full semantics and the proof that floor==2 implies source=="size" under
    the CURRENT HOTZONE_PATTERNS, and why the explicit check is kept anyway.

    Thin wrapper over _compute_floor_with_source() — never duplicates its
    logic, so the two can never drift apart."""
    return _compute_floor_with_source(changed_files, numstat, patch)[1]


# ---------------------------------------------------------------------------
# Gear CEILING (2026-08-21 audit, research/operations/2026-08-21-token-
# ceremony-ci-system-audit.md §7 lever L6 / §8): the floor above already
# stops a diff from declaring LESS gear than a hot-zone hit demands, but
# nothing stopped the opposite — a Gear-1-shaped diff paying for a council,
# cross-family refuters and `xhigh` thinking it never needed (measured: 65%
# of declared gears are Gear-3, 70% of Agent dispatches are graders). The
# ceiling is the mirror rule: "the model may only raise, never lower, the
# floor" gets a matching "a trivial diff may not silently over-provision
# Gear-3 machinery either" — with an explicit, reasoned escape hatch
# (`gear_override`) for the genuine exception, never a hard ban.
# ---------------------------------------------------------------------------
DOCS_LEDGER_EXTENSIONS: tuple[str, ...] = (".md", ".json")
CEILING_SMALL_DIFF_MAX_FILES = 2
CEILING_SMALL_DIFF_MAX_NET_LINES = 60
CEILING_HEAVY_GRADER_DISPATCH_MIN = 3


def compute_ceiling(
    changed_paths: list[str],
    declared_gear: int | None,
    pack: dict[str, Any],
    measured_net_lines: int | None = None,
) -> tuple[int, list[str]]:
    """Returns (ceiling, reasons). Mirrors compute_floor()'s lower-bound-only
    shape but at the opposite end: it names a Gear-1-shaped diff (never a
    Gear-2 ceiling — like the floor, the "standard PR" middle bucket needs
    human judgment no diff shape alone can carry) and flags an over-
    provisioned Gear-3 declaration against it.

    A diff is Gear-1-SHAPED when either:
      (a) every changed path is docs/ledger/markdown/json-only
          (DOCS_LEDGER_EXTENSIONS), or
      (b) it touches at most CEILING_SMALL_DIFF_MAX_FILES files AND its net
          line count is at or under CEILING_SMALL_DIFF_MAX_NET_LINES.
    The net-line count for (b) is `measured_net_lines` when the caller
    supplies one (a real `git diff --numstat` sum, computed OUTSIDE this
    function — it stays pure, no I/O, like compute_floor). MEASURED ALWAYS
    WINS over the pack's own `net_lines:` field (adversarial-review finding
    2026-08-21 — a pack declaring 10 while the real diff is 400 lines must
    not silently escape the ceiling just because the author under-reported
    it). Only when `measured_net_lines` is absent does this function fall
    back to the pack-declared `net_lines`, and it then ADDS an informational
    "ceiling (notice): net_lines self-declared (no --net-lines supplied)"
    line — self-declared data is lower-trust, and the caller should know
    which source decided shape (b). Neither source present -> shape (b) is
    simply not asserted (an unmeasured diff is not evidence of smallness).

    FLOOR ALWAYS WINS: if changed_paths hits the hot-zone (compute_floor==3),
    this function returns (3, []) immediately — a hot-zone docs file still
    floors AND ceilings at 3, silently, never a conflicting verdict.

    On a Gear-1-shaped, non-hot-zone diff, a `declared_gear == 3` pack is
    only "heavy" (worth flagging) if it also carries a convened `council`
    (pack["council"] truthy — non-empty list or True) or
    `grader_dispatches >= CEILING_HEAVY_GRADER_DISPATCH_MIN`. A Gear-3 pack
    with neither is not over-provisioned by this signal and gets no reason.

    Reason-string contract for the caller (lint()): an entry that starts
    with the bare "ceiling: " prefix (colon directly after the word) is a
    hard violation (guilt — fail). Any entry with a parenthetical qualifier
    right after "ceiling" — "ceiling (overridden): ..." (a non-empty
    `gear_override` was supplied) or "ceiling (notice): ..." (self-declared
    net_lines was consulted) — is informational only and must NOT be added
    to `violations`; "the ceiling does not fail, it reports."
    """
    pack = pack if isinstance(pack, dict) else {}
    changed_paths = changed_paths or []

    if not changed_paths:
        # No diff context at all — nothing to assert a shape against.
        return 3, []

    if compute_floor(changed_paths) == 3:
        # Floor wins over ceiling when they conflict (mandate rule, see
        # module docstring reference above) — a hot-zone hit floors AND
        # ceilings at 3, silently.
        return 3, []

    docs_shaped = all(
        any(f.endswith(ext) for ext in DOCS_LEDGER_EXTENSIONS) for f in changed_paths
    )

    net_lines: int | None
    net_lines_source: str | None
    if type(measured_net_lines) is int:  # exclude bool — True/False is not a count
        net_lines = measured_net_lines
        net_lines_source = "measured"
    else:
        raw = pack.get("net_lines")
        if type(raw) is int:
            net_lines = raw
            net_lines_source = "pack"
        else:
            net_lines = None
            net_lines_source = None

    small_shaped = (
        len(changed_paths) <= CEILING_SMALL_DIFF_MAX_FILES
        and net_lines is not None
        and net_lines <= CEILING_SMALL_DIFF_MAX_NET_LINES
    )

    if not (docs_shaped or small_shaped):
        return 3, []  # not a Gear-1-shaped diff — no ceiling to assert

    reasons: list[str] = []
    if small_shaped and net_lines_source == "pack":
        reasons.append(
            "ceiling (notice): net_lines self-declared (no --net-lines supplied)"
        )

    council = bool(pack.get("council"))
    grader_dispatches = pack.get("grader_dispatches")
    heavy_graders = (
        type(grader_dispatches) is int and grader_dispatches >= CEILING_HEAVY_GRADER_DISPATCH_MIN
    )

    if declared_gear == 3 and (council or heavy_graders):
        cause = "council" if council else f"{grader_dispatches} grader dispatches"
        override = pack.get("gear_override")
        if isinstance(override, str) and override.strip():
            return 1, [
                f"ceiling (overridden): Gear 1 shape — declared Gear 3 with {cause}, "
                f"overridden: {override.strip()}"
            ] + reasons
        return 1, [
            "ceiling: Gear 1 shape — declared Gear 3 with "
            f"{cause}; declare the reason in `gear_override:`"
        ] + reasons

    return 1, reasons


# ---------------------------------------------------------------------------
# Effort per gear (same audit, lever L0: "reasoning budget tied to the
# gear" — ~86% of output tokens are thinking, and effort is the primary
# cost/latency lever on Opus 5, cf. CLAUDE.md §5). `max` is deliberately
# ABSENT from this mapping: the gate adjudication step is the one place
# that may reach for it, and only via an explicit `effort_override` a
# session sets by hand — never this function's default for any gear.
# ---------------------------------------------------------------------------
GEAR_EFFORT: dict[int, str] = {1: "medium", 2: "xhigh", 3: "xhigh"}


def effort_for_gear(gear: int) -> str:
    """GUILT (implicit, via ValueError): a gear outside {1,2,3}, or not a
    genuine int (bool/float coercion — same VALID_GEARS trap check_gear_floor
    already guards), raises rather than silently guessing an effort level.
    INNOCENCE: gear 1 -> "medium", gear 2/3 -> "xhigh" (Gear-3's own `max`
    reservation is the caller's explicit choice, not this function's)."""
    if type(gear) is not int or gear not in GEAR_EFFORT:
        raise ValueError(
            f"effort_for_gear: gear must be exactly one of {tuple(GEAR_EFFORT)} (int), "
            f"got {gear!r}"
        )
    return GEAR_EFFORT[gear]


def approx_tokens(raw: bytes) -> int:
    return len(raw) // 4


# --------------------------------------------------------------- check_* guards
# Each is censused by infra/guard-conformance/registry.json via ast-def-prefix
# "check_" — every one needs a guilt AND an innocence test in
# scripts/tests/test_evidence_pack_lint.py (superscar #3).


def check_receipts_have_provenance(pack: dict[str, Any], gear: int | None = None) -> list[str]:
    """GUILT: a receipts[] entry missing cmd/exit/ts/seat is an OPINION wearing
    a receipt's shape — rejected. GUILT: on a Gear-3 pack, receipts entirely
    missing or empty is rejected too — symmetric with the dissent rule below;
    an "Evidence Pack" with zero evidence defeats its own purpose at the gear
    where it matters most (adversarial-review finding, 2026-08-10). INNOCENCE:
    a fully-shaped receipt passes; on Gear 1/2 a pack with NO receipts key at
    all is not this rule's problem (an empty evidence pack may legitimately
    have no claims yet — other rules still gate it)."""
    violations: list[str] = []
    receipts = pack.get("receipts")
    if receipts is None:
        receipts = []
    if not isinstance(receipts, list):
        return [f"receipts: must be a list, got {type(receipts).__name__}"]
    if gear == 3 and len(receipts) == 0:
        violations.append(
            "receipts: empty/missing on a Gear-3 pack — an Evidence Pack with "
            "zero receipts carries no evidence"
        )
    for idx, entry in enumerate(receipts):
        if not isinstance(entry, dict):
            violations.append(f"receipts[{idx}]: must be a mapping, got {type(entry).__name__}")
            continue
        missing = [f for f in RECEIPT_REQUIRED_FIELDS if not str(entry.get(f, "")).strip()
                   and entry.get(f) != 0]
        if missing:
            claim = entry.get("claim", "<no claim text>")
            violations.append(
                f"receipts[{idx}] (claim={claim!r}): missing/empty field(s) "
                f"{missing} — not a receipt, downgrade to OPINION or complete it"
            )
    return violations


DISSENT_REQUIRED_FIELDS = ("seat", "objection", "status")
DISSENT_VALID_STATUSES = ("CONFIRMED", "PLAUSIBLE", "RETRACTED")


def check_dissent_nonempty_on_gear3(pack: dict[str, Any], gear: int | None) -> list[str]:
    """GUILT: the `dissent` key absent entirely (mandatory field, any gear);
    GUILT: `dissent: []` on a Gear-3 pack ("consenso sospetto"); GUILT: a
    dissent entry missing seat/objection/status, or carrying a status outside
    {CONFIRMED, PLAUSIBLE, RETRACTED} — `dissent: [{}]` used to pass this
    check purely on length (adversarial-review finding, 2026-08-10; the
    receipts rule already validated per-entry shape, this one didn't).
    INNOCENCE: an empty dissent list on Gear 1/2 is fine (brief's own stated
    edge case); a fully-shaped entry with a valid status passes on Gear-3."""
    if "dissent" not in pack:
        return ["dissent: field is missing — mandatory on every Evidence Pack (harness-v2 §5)"]
    dissent = pack["dissent"]
    if not isinstance(dissent, list):
        return [f"dissent: must be a list, got {type(dissent).__name__}"]
    if gear == 3 and len(dissent) == 0:
        return ["dissent: consenso sospetto — zero dissent entries on a Gear-3 pack "
                "(either no refuter tried, or none were independent)"]
    violations: list[str] = []
    for idx, entry in enumerate(dissent):
        if not isinstance(entry, dict):
            violations.append(f"dissent[{idx}]: must be a mapping, got {type(entry).__name__}")
            continue
        missing = [f for f in DISSENT_REQUIRED_FIELDS if not str(entry.get(f, "")).strip()]
        if missing:
            violations.append(f"dissent[{idx}]: missing/empty field(s) {missing}")
            continue
        if entry.get("status") not in DISSENT_VALID_STATUSES:
            violations.append(
                f"dissent[{idx}]: status must be one of {DISSENT_VALID_STATUSES}, "
                f"got {entry.get('status')!r}"
            )
    return violations


def check_pii_scan_clean(pack: dict[str, Any]) -> list[str]:
    """GUILT: pii_scan missing or any value other than the literal "clean".
    INNOCENCE: pii_scan == "clean" passes."""
    value = pack.get("pii_scan")
    if value != "clean":
        return [f"pii_scan: must equal 'clean', got {value!r}"]
    return []


def check_size_budget(raw: bytes) -> list[str]:
    """GUILT: pack exceeds the 30k-approx-token hard cap. INNOCENCE: a pack
    at or under the cap passes. Overflow is a DEFECTIVE pack per harness-v2
    §5 ("Overflow = pack difettoso, non 'gate più lungo'"), not grounds to
    raise the cap."""
    tokens = approx_tokens(raw)
    if tokens > SIZE_TOKEN_CAP:
        return [f"size: approx {tokens} tokens exceeds the {SIZE_TOKEN_CAP} hard cap"]
    return []


def check_brief_ref_exists(
    pack: dict[str, Any], repo_root: Path
) -> tuple[list[str], dict[str, Any] | None]:
    """GUILT: brief_ref missing from the pack; pointing at a file absent on
    disk; an ABSOLUTE path or one escaping repo_root via `..` (pathlib's `/`
    operator silently DISCARDS the left side when the right side is absolute
    — `Path(repo_root) / "/etc/passwd"` resolves to `/etc/passwd`, a real
    path-confinement bug this repo's own py/path-injection scar class exists
    to catch, found by adversarial review 2026-08-10); or a DIRECTORY rather
    than a file (`brief_ref: "."` used to raise an uncaught IsADirectoryError
    — now rejected cleanly). INNOCENCE: brief_ref present, relative, confined
    under repo_root, and resolvable to a real file loads and returns the
    referenced brief (a dict) for downstream rules to consume."""
    brief_ref = pack.get("brief_ref")
    if not brief_ref or not isinstance(brief_ref, str):
        return (["brief_ref: missing or not a string"], None)
    if Path(brief_ref).is_absolute():
        return ([f"brief_ref: '{brief_ref}' must be a repo-relative path, not absolute"], None)
    repo_root_resolved = repo_root.resolve()
    brief_path = (repo_root / brief_ref).resolve()
    if repo_root_resolved not in (brief_path, *brief_path.parents):
        return ([f"brief_ref: '{brief_ref}' escapes repo_root (path traversal)"], None)
    if not brief_path.is_file():
        return ([f"brief_ref: '{brief_ref}' does not resolve to a file on disk"], None)
    try:
        brief = yaml.safe_load(brief_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return ([f"brief_ref: '{brief_ref}' could not be read/parsed: {exc}"], None)
    if not isinstance(brief, dict):
        return ([f"brief_ref: '{brief_ref}' did not parse to a mapping"], None)
    return ([], brief)


def check_gear_floor(
    brief: dict[str, Any] | None,
    changed_files: list[str] | None,
    numstat: str | None = None,
) -> list[str]:
    """GUILT: the brief's declared gear is below the deterministic floor
    computed from the PR's changed files; GUILT: gear is not a genuine int
    (`gear: true` or `gear: 1.0` used to pass — Python's `bool`/`float` are
    `==`-equal to `int` members of VALID_GEARS via bare `in`, so
    `True in (1,2,3)` is True; found by adversarial review 2026-08-10, fixed
    with an explicit `type(gear) is int` check). INNOCENCE: gear >= floor
    passes; gear ABOVE the floor always passes too (the model may only
    raise, never lower, the floor — harness-v2 §1 monotonia). When
    changed_files is None the check is explicitly SKIPPED (see module
    docstring) rather than silently treated as passing without evidence —
    the caller prints the NOTICE, this function just declines to add a
    violation. `numstat`, when given, feeds compute_floor()'s optional SIZE
    term (S1) too — omitting it (the default) exercises the path term
    alone, unchanged from before that term existed."""
    if brief is None:
        return []  # already flagged by check_brief_ref_exists
    gear = brief.get("gear")
    if type(gear) is not int or gear not in VALID_GEARS:
        return [f"brief.gear: must be exactly one of {VALID_GEARS} (int), got {gear!r}"]
    if changed_files is None:
        return []
    floor = compute_floor(changed_files, numstat)
    if gear < floor:
        return [f"brief.gear: declared {gear} is BELOW the deterministic floor {floor} "
                f"computed from the changed-file set (hot-zone path and/or blast-radius size)"]
    return []


# ---------------------------------------------------------------------------
# Rule 12 (acceptance-probe pairing, 2026-08-29 — module docstring rule 12).
# `_EARS_KEYWORD_RE` is deliberately NOT `re.IGNORECASE`: an ordinary
# sentence routinely contains lowercase "if"/"when" that states no
# falsifiable condition at all ("we'll ship if the tests pass" reads fine
# in prose but is not an EARS clause) — matching those would be exactly the
# superscar #3 over-match this rule exists to avoid. Uppercase
# WHEN/WHILE/IF/WHERE/SHALL, matched as a whole word, is the deliberate
# authoring convention (EARS — Easy Approach to Requirements Syntax) this
# rule rewards, not a stylistic accident it happens to detect.
# ---------------------------------------------------------------------------
_EARS_KEYWORD_RE = re.compile(r"\b(?:WHEN|WHILE|IF|WHERE|SHALL)\b")


def _probe_is_bound(probe: str, receipt_text: str) -> bool:
    """A declared probe counts as bound when it occurs in a receipt's
    `claim`/`cmd` as a WHOLE token run, not merely as a substring.

    Plain `probe in receipt_text` bound `ls` to "run the tools suite"
    (verified before this fix) — a false silence, the under-match
    direction of superscar #3: the notice that should have said "this
    probe has no receipt" said nothing. The boundary is applied only on
    the side where the probe's own edge character is itself a word
    character, so a probe ending in punctuation (`make test;`) is not
    made artificially unbindable, while `ls` can no longer hide inside
    `tools`. Deliberately still a LITERAL match with no fuzzy/semantic
    step: a probe naming extra flags the receipt lacks stays unbound,
    and matching by meaning is exactly the over-match this rule refuses
    (see `_EARS_KEYWORD_RE`'s note)."""
    if not probe:
        return False
    pattern = re.escape(probe)
    if probe[0].isalnum() or probe[0] == "_":
        pattern = r"(?<!\w)" + pattern
    if probe[-1].isalnum() or probe[-1] == "_":
        pattern = pattern + r"(?!\w)"
    return re.search(pattern, receipt_text) is not None


def _sanitize_notice_text(text: str) -> str:
    """The ONE sanitiser every stderr-bound NOTICE text passes through.

    Collapses interior whitespace (newlines included) to single spaces,
    swaps double quotes for single ones, and DROPS every non-printable
    code point. The three operations are not interchangeable and each
    exists for a defect that actually happened:

    * the whitespace collapse stops one NOTICE spanning several stderr
      lines (acceptance/assumption texts routinely arrive from a YAML
      block scalar);
    * the quote swap keeps `"..."` delimiters closing where a caller
      wraps the result in quotes;
    * the non-printable drop is the one the collapse CANNOT do —
      `"\x1b".isspace()` is False, so ESC/BEL/NUL sailed through it
      verbatim into a terminal. Found by blind adversarial review of
      rule 13 (Kimi K3, finding 1, 2026-08-29) and verified on disk.

    Extracted to a named function when rule 14 shipped, because rule
    14's `appetite_exceeded:` reason reached stderr WITHOUT any of the
    three — the SAME defect, in the SAME lane, one PR later, on prose
    even more likely to be multi-line than an acceptance bullet. A
    sanitiser that lives inside one rule's formatter is a sanitiser the
    next rule will forget; this one is shared by construction.

    It deliberately does NOT truncate or quote — those are the CALLER's
    presentation choices (`_acceptance_examples` renders bullets; rule
    14 renders prose), and folding them in here would force one shape on
    both."""
    return "".join(
        ch for ch in " ".join(text.split()).replace('"', "'") if ch.isprintable()
    )


def _acceptance_examples(items: list[str], limit: int = 3) -> str:
    """Shared truncate/quote/join helper for rule 12's three NOTICE
    messages so all of them share one implementation — up to `limit`
    items, each carrying at most 60 characters OF CONTENT followed by an
    ellipsis when it was cut (so the rendered field is <= 63 chars, not
    60 — spelled out because "truncated to 60 chars" read two ways in
    adversarial review), each wrapped in double quotes, joined by "; ".
    An empty string (a mapping bullet whose declared `text:` is missing
    or non-string) renders as `"<non-text bullet>"` rather than a bare,
    confusing pair of quotes a reader could mistake for a real, empty
    acceptance criterion.

    Every item is SANITIZED first: interior whitespace (newlines
    included) collapses to single spaces, any double quote becomes a
    single quote, and every non-printable code point is DROPPED (ESC,
    BEL, NUL and friends are not whitespace, so the collapse alone let
    them through — see the inline comment). Acceptance text routinely arrives from a YAML block
    scalar and legitimately contains both; without this, one NOTICE
    would span several stderr lines and its `"..."` delimiters would not
    close — a `grep`-hostile message, and a real defect found by
    adversarial review 2026-08-29 (verified: a bullet containing a
    newline produced a two-line notice before this)."""
    rendered: list[str] = []
    for item in items[:limit]:
        # Whitespace collapse + quote swap + non-printable drop, all three
        # in `_sanitize_notice_text` (shared with rule 14 — see its
        # docstring for why each is load-bearing). Behaviour here is
        # unchanged by that extraction; verified byte-identical.
        text = _sanitize_notice_text(item) if item else ""
        if not text:
            text = "<non-text bullet>"
        elif len(text) > 60:
            text = text[:60] + "..."
        rendered.append(f'"{text}"')
    return "; ".join(rendered)


def check_acceptance_probe_pairing(
    brief: dict[str, Any] | None,
    pack: dict[str, Any],
    gear: int | None,
) -> list[str]:
    """Rule 12 — NOTICE-only BY DESIGN: this function NEVER returns a
    violation, only advisory strings the caller prints to stderr (an
    always-empty `violations` list is not tracked here at all — dead code
    on the only path it would exist for).

    GUILT (what it flags, each as a NOTICE, never a fail):
      N1 (probe coverage)   — a bullet with no declared `probe:` (a
                               command, test id, or check name).
      N2 (receipt binding)  — a declared `probe:` whose stripped text is
                               not a verbatim substring of any receipt's
                               `claim` or `cmd` — the outcome it names is
                               unrecorded. Silent when zero probes are
                               declared (nothing to bind).
      N3 (EARS shape)       — a bullet whose text carries none of the
                               EARS keywords WHEN/WHILE/IF/WHERE/SHALL as
                               a whole UPPERCASE word, matched
                               case-SENSITIVELY (`_EARS_KEYWORD_RE`) —
                               lowercase "if"/"when" in ordinary prose
                               does not count.
    Emits AT MOST THREE notices total, one aggregate per class above
    (never one per bullet — a real pack can carry dozens of acceptance
    bullets; per-bullet output would be unusable), each naming up to 3
    example bullets via `_acceptance_examples()`.

    INNOCENCE (silent, `[]`): `brief` is None or not a dict (rule 6's
    check_brief_ref_exists already flagged that); `gear` is not a genuine
    `int` >= 2 (same `type(gear) is int` discipline as check_gear_floor —
    a bool/float never coerces in, and Gear 1 is out of scope entirely);
    `brief.get("acceptance")` is missing, not a list, or an empty list; a
    fully mapping-shaped acceptance block whose every bullet declares a
    probe, every declared probe is bound to a receipt, and every text is
    EARS-shaped emits nothing.

    A bullet is the MAPPING form when `isinstance(bullet, dict)`: its
    text is `bullet.get("text")` if that is a `str`, else `""`; its
    probe is `bullet.get("probe").strip()` when that is a non-empty
    `str`, else absent. A `str` bullet is the LEGACY form: text = the
    string itself, probe absent (a legacy string bullet can never
    declare a probe — it has nowhere to put one). Any other type: text =
    `""`, probe absent.

    HONEST LIMIT, stated so it is never mistaken for more than it is:
    this rule checks FIELD PRESENCE ONLY. A `receipts:` entry is
    self-reported prose — an author can write `probe: "pytest -k foo"`
    and a receipt claiming that exact string ran, without any CI step
    having actually executed it. A stored outcome is FORGEABLE until a
    CI step runs the probe and the receipt is machine-generated rather
    than hand-typed; this rule cannot see that difference and does not
    pretend to. It exists to make the GAP visible — which bullets carry
    no probe at all, which declared probes have no matching receipt,
    which bullets are not even shaped as a falsifiable condition — so a
    later change can flip NOTICE to FAIL once real execution is wired in
    (see ASSEMBLY-LINE.md's enforcement backlog)."""
    if not isinstance(brief, dict):
        return []
    if type(gear) is not int or gear < 2:
        return []
    acceptance = brief.get("acceptance")
    if not isinstance(acceptance, list) or not acceptance:
        return []

    total = len(acceptance)
    texts: list[str] = []
    probes: list[str | None] = []
    for bullet in acceptance:
        if isinstance(bullet, dict):
            raw_text = bullet.get("text")
            text = raw_text if isinstance(raw_text, str) else ""
            raw_probe = bullet.get("probe")
            probe = (
                raw_probe.strip()
                if isinstance(raw_probe, str) and raw_probe.strip()
                else None
            )
        elif isinstance(bullet, str):
            text = bullet
            probe = None
        else:
            text = ""
            probe = None
        texts.append(text)
        probes.append(probe)

    notices: list[str] = []

    # N1 — probe coverage: bullets that declare no probe at all.
    uncovered = [t for t, p in zip(texts, probes) if p is None]
    if uncovered:
        notices.append(
            f"acceptance-probe: {len(uncovered)} of {total} Gear-{gear} acceptance "
            f"bullet(s) carry no 'probe:' (a command, test id, or check name). "
            f"e.g. {_acceptance_examples(uncovered)}. This rule lints FIELD "
            f"PRESENCE only — a recorded outcome is not an executed probe."
        )

    # N2 — receipt binding: only over bullets that DO declare a probe.
    # De-duplicated, order-preserving: two bullets naming the SAME probe are
    # one probe to bind, and counting it twice made the notice overstate the
    # gap ("2 declared probe(s)" for one string — adversarial review
    # 2026-08-29, verified before accepting).
    declared = list(dict.fromkeys(p for p in probes if p is not None))
    if declared:
        # `lint()` guarantees a mapping, but this function is also called
        # directly (selftest + pytest, and any future caller): a bare
        # `pack.get` raised AttributeError on `pack=None` — a crash inside a
        # NOTICE-only rule, which must never be able to fail a run.
        receipts = pack.get("receipts") if isinstance(pack, dict) else None
        receipt_texts: list[str] = []
        if isinstance(receipts, list):
            for entry in receipts:
                if not isinstance(entry, dict):
                    continue
                for field in ("claim", "cmd"):
                    value = entry.get(field)
                    if isinstance(value, str):
                        receipt_texts.append(value)
        unbound = [
            p for p in declared
            if not any(_probe_is_bound(p, rt) for rt in receipt_texts)
        ]
        if unbound:
            notices.append(
                f"acceptance-probe: {len(unbound)} declared probe(s) appear in no "
                f"receipt's claim/cmd — the outcome is unrecorded. "
                f"e.g. {_acceptance_examples(unbound)}."
            )

    # N3 — EARS shape: over EVERY bullet, mapping and legacy string alike.
    non_ears = [t for t in texts if not _EARS_KEYWORD_RE.search(t)]
    if non_ears:
        notices.append(
            f"acceptance-probe: {len(non_ears)} of {total} acceptance bullet(s) "
            f"are not EARS-shaped (no WHEN/WHILE/IF/WHERE/SHALL keyword). "
            f"e.g. {_acceptance_examples(non_ears)}."
        )

    return notices


def check_assumptions_register(brief: dict[str, Any] | None) -> list[str]:
    """Rule 13 — NOTICE-only BY DESIGN, exactly like rule 12: this
    function NEVER returns a violation, only advisory strings the caller
    prints to stderr, and it NEVER raises — a NOTICE-only rule crashing
    inside a run it is not allowed to fail would be the defect, not the
    fix it was meant to be.

    An optional top-level `assumptions:` list in `brief.yml` registers
    the assumptions a pack is built on, each entry a mapping
    `{text, status, probe}` where `status` is expected to be `verified`
    or `unverified` and `probe` (relevant only when the assumption is
    `unverified`) names the check that would settle it.

    GUILT (what it flags, each as ONE aggregate NOTICE, never per-entry
    — mirrors rule 12's reasoning: a real register can carry dozens of
    assumptions and per-entry output would be unusable):
      N1 (unverified)      — entries whose `status`, when it IS a `str`,
                              `.strip().lower()`s to exactly
                              `"unverified"`.
      N2 (unadjudicated)   — entries that are not a mapping at all, OR
                              whose `status` is missing, not a `str`, or
                              whose stripped-lowered value is not in
                              {"verified", "unverified"}. LOAD-BEARING,
                              the whole reason N1 alone is insufficient:
                              matching only the literal string
                              `unverified` lets `status: pending`, the
                              typo `status: unverfied`, and a bare
                              string entry escape in TOTAL silence — an
                              unverified assumption made invisible by
                              one keystroke. An unrecognised or missing
                              status is NOT the same as verified.
      N3 (unsettleable)    — a SUBSET of N1: entries N1 already matched
                              (status is exactly `unverified`) that also
                              carry no usable `probe` (missing, not a
                              `str`, or blank after `.strip()`) — nothing
                              names the check that would settle them.
                              Same shape rule 12 already has (a bullet
                              can be in its N1 and N3 both): two
                              different facts, two different remedies.

    INNOCENCE (silent, `[]`): `brief` is None or not a dict;
    `brief.get("assumptions")` is missing, not a list, or an empty list;
    every entry is a mapping whose `status` is `verified` (stripped,
    case-insensitive).

    NOT GEAR-GATED, unlike rule 12, and deliberately so: rule 12 gates
    on Gear>=2 because ITS Build clause said so. This rule's clause
    says only "a zero-assumption brief passes silently" — and absence
    is ALREADY silent by the INNOCENCE rule above, with adoption at
    0/50 briefs on disk (measured 2026-08-29): the block is opt-in by
    construction. A Gear-1 brief that troubles itself to declare an
    unverified assumption deserves the notice as much as a Gear-3 one
    — gating it would be a bypass of that opt-in, not a safeguard.

    HONEST LIMIT, stated so it is never mistaken for more than it is
    (same posture as rule 12): `status: verified` is SELF-REPORTED
    prose. This rule checks the SHAPE of a declaration — is there a
    recognised status, does an unverified entry name a probe — never
    the TRUTH of it. An author can write `verified` about something
    nobody verified and this rule cannot tell the difference; it exists
    to make the register's OWN gaps visible, not to adjudicate the
    assumptions it registers."""
    if not isinstance(brief, dict):
        return []
    assumptions = brief.get("assumptions")
    if not isinstance(assumptions, list) or not assumptions:
        return []

    total = len(assumptions)
    unverified_texts: list[str] = []
    unadjudicated_texts: list[str] = []
    unsettleable_texts: list[str] = []

    for entry in assumptions:
        if isinstance(entry, dict):
            raw_text = entry.get("text")
            text = raw_text if isinstance(raw_text, str) else ""
            raw_status = entry.get("status")
            status = (
                raw_status.strip().lower()
                if isinstance(raw_status, str)
                else None
            )
        else:
            text = entry if isinstance(entry, str) else ""
            status = None

        if status == "unverified":
            unverified_texts.append(text)
            raw_probe = entry.get("probe")
            probe_ok = isinstance(raw_probe, str) and bool(raw_probe.strip())
            if not probe_ok:
                unsettleable_texts.append(text)
        elif status != "verified":
            unadjudicated_texts.append(text)

    notices: list[str] = []

    # N1 — unverified: entries explicitly marked as such.
    if unverified_texts:
        notices.append(
            f"assumptions: {len(unverified_texts)} of {total} assumption(s) "
            f"are still 'unverified'. e.g. "
            f"{_acceptance_examples(unverified_texts)}."
        )

    # N2 — unadjudicated: no mapping, or a status outside the two known
    # values — a typo or a bare string must not read as silence.
    if unadjudicated_texts:
        notices.append(
            f"assumptions: {len(unadjudicated_texts)} of {total} "
            f"assumption(s) declare no recognised status (expected "
            f"'verified' or 'unverified') — an unrecognised or missing "
            f"status is NOT the same as verified. e.g. "
            f"{_acceptance_examples(unadjudicated_texts)}."
        )

    # N3 — unsettleable: a subset of N1, over unverified entries with no
    # probe to settle them.
    if unsettleable_texts:
        notices.append(
            f"assumptions: {len(unsettleable_texts)} unverified "
            f"assumption(s) declare no 'probe:' — nothing names the "
            f"check that would settle them. e.g. "
            f"{_acceptance_examples(unsettleable_texts)}."
        )

    return notices


_APPETITE_CEILING_DIMENSIONS: tuple[str, ...] = (
    "wall_clock_hours",
    "adversarial_rounds",
    "tokens",
)


def _appetite_numeric(value: Any) -> int | float | None:
    """A usable appetite/spend number: exactly `int` or `float`, FINITE, and
    NOT NEGATIVE. Anything else is "no number here" — which routes a declared
    ceiling to silence and an observed spend to the unmeasured NOTICE.

    Three independent reasons, each for a defect measured on this branch by
    blind cross-family review (Kimi K3, 2026-08-29) before merge:

    * `type(v) is` and not `isinstance` — rejects `bool`, which
      `isinstance(True, int)` would admit (same discipline as
      `type(raw_gear) is int` elsewhere in this module).
    * `math.isfinite` — `type(nan) is float` is True and EVERY NaN comparison
      is False, so a `spend: {tokens: .nan}` was admitted as a MEASUREMENT,
      never exceeded its ceiling, and therefore escaped the violation AND the
      "not verified this run" notice: total silence. That is a bypass — report
      any overrun as `.nan` and the rule says nothing — and it contradicted
      this module's own promise to notice a dimension with "no comparable
      numeric value". `-.inf` was the same shape. NaN is not a measurement; it
      is the absence of one, and must be reported as such.
    * `>= 0` — a negative CEILING (`adversarial_rounds: -1`, a typo) is
      unreachable by construction, so `0 > -1` convicted an honest pack. None
      of the three dimensions (hours, rounds, tokens) can legitimately go
      negative, so a negative value is nonsense in either position and is
      treated as undeclared/unmeasured rather than as grounds to fail a merge.

    Zero remains a legitimate value on BOTH sides — `wall_clock_hours: 0` is a
    real (harsh) declaration and a real observation, so the bound is `>= 0`,
    not `> 0`."""
    if type(value) is not int and type(value) is not float:
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return value


def check_appetite_acknowledgment(
    brief: dict[str, Any] | None,
    pack: dict[str, Any] | None,
) -> tuple[list[str], list[str]]:
    """Rule 14 — THE ONLY RULE IN THIS LANE THAT CAN FAIL. Rules 11
    (countable claims), 12 (acceptance-probe pairing) and 13 (assumptions
    register) are all NOTICE-only by design; this one returns real
    violations. Returns (violations, notices) — the SAME two-list shape as
    `check_countable_claims` and `check_lanes_build_seat_diversity`. It
    must NEVER raise.

    An optional top-level `appetite: {wall_clock_hours, adversarial_rounds,
    tokens}` mapping in `brief.yml` declares ceilings the session expects
    to stay under; an optional top-level `spend: {wall_clock_hours,
    adversarial_rounds, tokens}` mapping in `pack.yml` (same three keys,
    ex-post observed) reports what actually happened. `appetite_exceeded:
    "<reason>"` in the pack is the acknowledgment — this mirrors
    `gear_override` (rule 7) EXACTLY: a non-empty, stripped `str` is the
    acknowledgment, anything else (missing, blank/whitespace-only, or a
    non-`str` such as `appetite_exceeded: 42`) is treated as absent. The
    reason is passed through `_sanitize_notice_text` before it can reach
    stderr, and emptiness is judged AFTER that — so a "reason" made only
    of control bytes buys no silent pass.

    VERDICT, in the order it is decided:
      SILENT (`[], []`)   — `brief` is not a dict, or `appetite` is
                            missing, OR `appetite` is anything other than
                            a mapping. CRITICAL, measured 2026-08-29: on
                            disk right now `appetite:` appears in 1 of 53
                            briefs and its value is a free-text STRING,
                            not a mapping — a string declares no
                            machine-readable ceiling either, so it has
                            nothing to exceed and must ALSO stay silent, or
                            this rule would crash or falsely convict on the
                            only real instance in the corpus.
      SILENT               — `appetite` is a mapping, but none of its
                            three recognised keys carries a USABLE number
                            (see `_appetite_numeric`: exactly int/float,
                            finite, non-negative — so a `bool`, a `str`,
                            `.nan`, `.inf`, a negative typo, a missing
                            key, or an unrecognised key name all count as
                            "no numeric ceiling declared" for that
                            dimension). `appetite: {}` is this case.
      NOTICE ("not verified this run")
                            — 1+ ceiling IS declared, but `spend:` is
                            absent, not a mapping, or has no comparable
                            numeric value for that dimension. Only
                            dimensions present in BOTH mappings are ever
                            compared; a declared ceiling with no matching
                            `spend` key contributes to THIS notice, never
                            to a violation — an unmeasured ceiling is not a
                            breached one.
      SILENT                — every dimension that WAS measured is at or
                            under its declared ceiling. Comparison is
                            `observed > declared` — EQUALITY IS NOT A
                            BREACH. (A pack can be silent here while still
                            carrying the unmeasured NOTICE above, for a
                            different dimension — the two are independent
                            facts about independent dimensions.)
      NOTICE ("acknowledged")
                            — 1+ measured dimension is over its declared
                            ceiling, AND the pack carries a non-empty
                            `appetite_exceeded:` acknowledgment. Reported,
                            not failed — same "generator≠grader, but a
                            named human call is not a silent pass" posture
                            as `gear_override`.
      VIOLATION              — 1+ measured dimension is over its declared
                            ceiling and there is NO acknowledgment. Names
                            EVERY breached dimension's declared-vs-observed
                            pair, so the reader can act on each one. When an
                            `appetite_exceeded:` IS present but is not a
                            `str` (`yes` → YAML bool, `42` → int), the
                            conviction stands — the field mirrors
                            `gear_override`, where the REASON is the
                            artifact and a checkbox would be a one-token
                            bypass — but the message SAYS SO and names the
                            type, instead of telling the author there was no
                            acknowledgment when they plainly wrote one.

    KNOWN SHARP EDGE, decided rather than smoothed: the comparison is raw
    IEEE `>`, so a `spend` machine-summed from float components can be
    `0.30000000000000004` against a declared `0.3` and convict over 4e-17.
    No epsilon is applied, for two reasons. Picking a tolerance is picking a
    NUMBER, and ceiling values are explicitly a Zero ruling this rule carries
    rather than decides (lane spec needs-ruling 3); and a relative epsilon
    large enough to absorb float noise on `wall_clock_hours` would silently
    forgive a genuine breach on `tokens`, where the same relative slack is
    thousands of tokens. The mitigation is that the message prints BOTH
    numbers, so the author sees the 4e-17 and either rounds the spend or
    acknowledges — it is visible, not silent.

    HONEST LIMIT, stated so it is never read as more than it is: this is
    EX-POST / PR-LIFETIME ACCOUNTING, NEVER AN IN-FLIGHT BREAKER. Values
    are SELF-REPORTED; this linter has no clock and no session-runtime
    access. It cannot interrupt a live 44h session and must not be read as
    if it could. It makes an overrun VISIBLE and demands acknowledgment
    after the fact — that is the entire claim. "Unmeasured never
    convicts": a declared ceiling with no recorded spend NOTICES, it
    never fails.

    Auto-suspend on breach and the default ceiling VALUES are CARRIED,
    not DECIDED, by this rule (lane spec needs-ruling 1 and 3) — this
    rule ships acknowledgment-only; it does not suspend anything and does
    not supply a default number for any dimension."""
    violations: list[str] = []
    notices: list[str] = []

    if not isinstance(brief, dict):
        return violations, notices
    appetite = brief.get("appetite")
    if not isinstance(appetite, dict):
        # Absence, the one real corpus shape (a free-text str), or any
        # other non-mapping — none of these declare a machine-readable
        # ceiling, so none of them have anything to exceed. SILENT.
        return violations, notices

    declared: dict[str, int | float] = {}
    for dim in _APPETITE_CEILING_DIMENSIONS:
        value = _appetite_numeric(appetite.get(dim))
        if value is not None:
            declared[dim] = value
    if not declared:
        return violations, notices

    spend_raw = pack.get("spend") if isinstance(pack, dict) else None
    spend = spend_raw if isinstance(spend_raw, dict) else None

    measured: dict[str, tuple[int | float, int | float]] = {}
    unmeasured: list[str] = []
    for dim in _APPETITE_CEILING_DIMENSIONS:
        if dim not in declared:
            continue
        observed = _appetite_numeric(spend.get(dim)) if spend is not None else None
        if observed is None:
            unmeasured.append(dim)
        else:
            measured[dim] = (declared[dim], observed)

    if unmeasured:
        names = ", ".join(unmeasured)
        notices.append(
            f"appetite: {len(unmeasured)} ceiling(s) declared ({names}) but "
            f"the pack records no comparable `spend:` — not verified this run."
        )

    exceeded = [
        (dim, declared_value, observed_value)
        for dim, (declared_value, observed_value) in measured.items()
        if observed_value > declared_value
    ]
    if not exceeded:
        return violations, notices

    breach_text = "; ".join(
        f"{dim} declared {declared_value} observed {observed_value}"
        for dim, declared_value, observed_value in exceeded
    )

    raw_ack = pack.get("appetite_exceeded") if isinstance(pack, dict) else None
    # SANITIZE before this reason can reach stderr. It is free-text prose a
    # human writes to justify an overrun, so it is MORE likely than an
    # acceptance bullet to arrive as a multi-line YAML block scalar — and
    # unsanitised it broke the notice across lines and carried ESC/BEL to
    # the terminal verbatim (measured on this branch before the fix; the
    # identical defect blind review found in rule 13 one PR earlier).
    # Emptiness is judged AFTER sanitising, so a reason made entirely of
    # control bytes is correctly treated as no acknowledgment at all — it
    # would otherwise buy a silent pass with an unreadable excuse.
    acknowledged = _sanitize_notice_text(raw_ack) if isinstance(raw_ack, str) else ""
    if len(acknowledged) > 200:
        # Generous next to `_acceptance_examples`' 60: a reason is prose and
        # its substance is the point, but it must not be able to emit an
        # unbounded stderr line.
        acknowledged = acknowledged[:200] + "..."

    if acknowledged:
        notices.append(
            f"appetite (acknowledged): declared ceiling exceeded — "
            f'{breach_text}; acknowledged: "{acknowledged}"'
        )
    elif raw_ack is not None and not isinstance(raw_ack, str):
        # An acknowledgment IS present but is not a reason. `appetite_exceeded:
        # yes` parses as the BOOL True under YAML 1.1, and `42` is an int — in
        # both cases the previous message told the author there was "no
        # `appetite_exceeded:` acknowledgment" when they had plainly written
        # one, sending them to grep for a field that is right there. The
        # CONVICTION is correct and deliberately unchanged: this field mirrors
        # `gear_override`, where the REASON is the artifact — a checkbox
        # acknowledges nothing and would turn the rule into a one-token bypass.
        # What was defective was the message, so only the message changes.
        violations.append(
            f"appetite: declared ceiling exceeded and `appetite_exceeded:` is "
            f"a {type(raw_ack).__name__}, not a reason — {breach_text}. A bare "
            f"`yes`/`true`/number does not acknowledge anything; write "
            f'`appetite_exceeded: "<why it went over>"`, or correct the spend.'
        )
    else:
        violations.append(
            f"appetite: declared ceiling exceeded with no "
            f"`appetite_exceeded:` acknowledgment — {breach_text}. Add "
            f'`appetite_exceeded: "<reason>"` to the pack, or correct the '
            f"spend."
        )

    return violations, notices


def _is_anthropic_seat(seat: Any) -> bool:
    """Token-based match for Anthropic seat names.

    The normalised seat is split on ``-`` only (NOT on ``_``). It counts as
    Anthropic when its FIRST token is exactly one of ``claude``, ``sonnet``,
    ``opus``, or ``haiku``. This defends against BOTH failure directions of
    superscar #3:

    * over-match: ``opusculum`` / ``claude_ish`` are NOT Anthropic (the
      underscore is not a separator, so the first token is not ``claude``);
    * under-match: roster-style names such as ``opus-5``, ``sonnet-5`` and
      ``haiku-4-5`` ARE Anthropic because the first token is the family name.
    """
    if not isinstance(seat, str):
        return False
    norm = seat.strip().lower()
    if not norm:
        return False
    first_token = norm.split("-", 1)[0]
    return first_token in {"claude", "sonnet", "opus", "haiku"}


def check_lanes_build_seat_diversity(
    pack: dict[str, Any],
    gear: int | None = None,
    today: datetime.date | None = None,
) -> tuple[list[str], str | None]:
    """D3 lane-declaration and seat-diversity rule. GUILT/NOTICE: a Gear >= 2
    pack must declare `lanes:` as a non-empty list; when it has >= 2 build
    lanes, at least one must use a non-Anthropic builder seat. Gear 1 is
    exempt from both requirements. Fewer than 2 build lanes exempts only
    seat diversity, not the declaration. `lanes: []` (present but empty) is
    treated the same as `lanes:` absent — an empty list satisfies the shape
    checks trivially and produces zero build lanes, so without this it would
    silently exempt itself from D3 entirely. Shape violations (lanes not a
    list, entry not a mapping, missing/empty lane/role/seat, invalid role)
    are always failures whenever `lanes:` is a non-empty list, regardless of
    gear or date.

    Returns (violations, notice). `notice` is set only during the pre-
    enforcement grace period (before LANES_NON_ANTHROPIC_ENFORCEMENT_DATE)
    when either phased requirement would otherwise fail; violations is empty
    in that window. On/after the enforcement date the same shape becomes a
    violation.

    The `today` parameter makes the date overridable for tests without
    monkeypatching date.today() or env vars."""
    if "lanes" not in pack:
        if gear is None or gear < 2:
            return [], None
        message = (
            f"lanes: field is missing — mandatory on Gear-{gear} packs "
            "(D3 lane-declaration rule)"
        )
        if today is None:
            today = datetime.datetime.now(datetime.timezone.utc).date()
        if today < LANES_NON_ANTHROPIC_ENFORCEMENT_DATE:
            return [], message
        return [message], None

    lanes = pack["lanes"]
    if not isinstance(lanes, list):
        return [f"lanes: must be a list, got {type(lanes).__name__}"], None

    violations: list[str] = []
    build_lanes: list[tuple[int, dict[str, Any]]] = []

    for idx, entry in enumerate(lanes):
        if not isinstance(entry, dict):
            violations.append(f"lanes[{idx}]: must be a mapping, got {type(entry).__name__}")
            continue
        for field in ("lane", "role", "seat"):
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                violations.append(f"lanes[{idx}]: {field} missing/empty")
                break
        else:
            role = entry.get("role", "").strip().lower()
            if role not in VALID_LANE_ROLES:
                violations.append(
                    f"lanes[{idx}]: role must be one of {VALID_LANE_ROLES}, "
                    f"got {entry.get('role')!r}"
                )
                continue
            if role == "build":
                build_lanes.append((idx, entry))

    if violations:
        return violations, None

    if gear is None or gear < 2:
        return [], None

    if not lanes:
        message = (
            f"lanes: field is empty — mandatory on Gear-{gear} packs "
            "(D3 lane-declaration rule)"
        )
        if today is None:
            today = datetime.datetime.now(datetime.timezone.utc).date()
        if today < LANES_NON_ANTHROPIC_ENFORCEMENT_DATE:
            return [], message
        return [message], None

    if len(build_lanes) < 2:
        return [], None
    if not all(_is_anthropic_seat(entry.get("seat")) for _idx, entry in build_lanes):
        return [], None

    idxs = ",".join(str(i) for i, _e in build_lanes)
    message = (
        f"lanes: Gear-{gear} pack has {len(build_lanes)} build lane(s) "
        f"([{idxs}]) and zero non-Anthropic builder seats "
        f"(D3 seat-diversity rule)"
    )

    if today is None:
        today = datetime.datetime.now(datetime.timezone.utc).date()
    if today < LANES_NON_ANTHROPIC_ENFORCEMENT_DATE:
        return [], message
    return [message], None


# ---------------------------------------------------------------------------
# Seat rules by path class (E3/R8-R11 — 2026-08-26 seat-rules program, spec
# §8 in 2026-08-26-PIANO-SPEC-receptor-live.md). Two rules ship here (R8
# ground-truth, R10 PII-local); two more (R11 cheap-seat floor, R9 Gear-3
# council) land in a follow-up PR on this same module, reusing the shared
# plumbing below — split per the mandate's own PR-size contract (4 rules
# in one module exceeded ~400 net lines together). All four reuse rule 8
# (D3)'s own NOTICE-before/FAIL-on-or-after shape against their OWN flip
# date (this program never fired before, so it gets its own clock rather
# than borrowing D3's — same "a ledger line nobody reads cannot gate a
# merge" reasoning as LANES_NON_ANTHROPIC_ENFORCEMENT_DATE). Each also
# honors ONE shared, ALWAYS-reported escape — a pack-level `seat_override:
# <non-empty reason>` — mirroring rule 7's `gear_override`: a deliberate,
# named human call, never a silent pass, reported so X3 (ASSEMBLY-LINE.md
# gate-lifecycle ledger) can count how often it fires.
# ---------------------------------------------------------------------------
# MOVED FORWARD 2026-09-02 -> 2026-08-31 (Squad S lane 6, Zero: «anche subito
# se siamo pronti»). "Ready" was MEASURED, not asserted: every one of the 43
# open PRs was linted twice, once with today's dates and once with this
# constant alone pulled into the past, staged exactly as harness-floor.yml
# stages a pack (--source-path included, without which every pack falsely reads
# as a deprecated evidence/ root). Moving THIS date alone turns ZERO open PRs
# red. The other two were measured separately and are NOT moved here:
# R9_R11 would redden 9, and EVIDENCE_ROOT_DEPRECATION 3 — see
# research/operations/2026-08-31-two-nine-enforcement-readiness.md for the
# per-PR table and the two independent causes behind the 9.
SEAT_RULES_ENFORCEMENT_DATE = datetime.date(2026, 8, 31)

#: R8 — ground-truth path classes: backend KB, visa_engine (any depth —
#: services/scripts/tests alike, fnmatch's `*` already crosses `/`), the
#: real on-disk KBLI datasets (grepped 2026-08-26: data/source_documents/
#: and apps/mouth/data/, both casings — kbli-gold-all.json is lowercase,
#: KBLI_2025_FINAL_CLEAN.json is not), PricingTool's own official-prices
#: JSON (apps/backend-rag/backend/services/pricing/pricing_service.py:29
#: `_PRICING_FILENAME`) plus its apps/mouth mirror, research/regulatory,
#: and the mouth "claim pages" — public content asserting a SPECIFIC
#: regulated fact (visa eligibility/cost, a KBLI code, a tax deadline, a
#: zoning/property rule) as opposed to account/UI/marketing surfaces
#: (login, chat, portal, blog, terms, ...), which make no such claim.
GROUND_TRUTH_PATH_PATTERNS: tuple[str, ...] = (
    "apps/backend-rag/backend/kb/*",
    "*/visa_engine/*",
    "data/source_documents/KBLI*.json",
    "data/kbli-filiera/*",
    "apps/mouth/data/KBLI*.json",
    "apps/mouth/data/kbli*.json",
    "apps/backend-rag/backend/data/bali_zero_official_prices_*.json",
    "apps/mouth/data/bali-zero-prices.json",
    "research/regulatory/*",
    "apps/mouth/src/app/visa/*",
    "apps/mouth/src/app/(visa-oracle)/*",
    "apps/mouth/src/app/kbli/*",
    "apps/mouth/src/app/kbli-explorer/*",
    "apps/mouth/src/app/taxes/*",
    "apps/mouth/src/app/(tax-calendar)/*",
    "apps/mouth/src/app/zoning/*",
    "apps/mouth/src/app/property/*",
)

#: R8/R10 shared guard — `fnmatch`'s `*` crosses `/`, so every
#: `.../<claim-page-dir>/*` pattern above also matches that page's own test
#: scaffolding (found live 2026-08-26 by the R8/R10 refuter round 1: the
#: `apps/mouth/src/app/kbli-explorer/*` pattern matches
#: `apps/mouth/src/app/kbli-explorer/hooks/__tests__/useTypewriter.test.ts`,
#: an innocuous UI test with no regulatory claim of its own). A test file
#: makes no public claim by itself — the page it tests does, and the page
#: file is still covered directly. Family #3 (guard-over-match) doctrine:
#: narrow the trigger to entities/intent, never leave a bare glob to decide.
_TEST_PATH_MARKERS: tuple[str, ...] = ("__tests__/", "/tests/", ".test.", ".spec.")

#: R8 only (folded into the same exclusion helper — harmless for R10's
#: Python-only patterns, which never look like a `.tsx` filename) — the
#: exact, Next.js-App-Router-reserved special filenames that are ALWAYS
#: framework scaffolding, never page content, by the framework's own
#: naming contract (found live 2026-08-26 by refuter round 2:
#: `.../kbli-explorer/loading.tsx` and `.../error.tsx` also matched the
#: claim-page glob, and neither can ever render a regulatory claim — Next
#: invokes them only for the loading-skeleton / error-boundary slot).
#: Deliberately NOT excluded: `layout.tsx` (can carry a persistent
#: claim-adjacent banner) and every component/hook under the page
#: directory (KBLIInspector.tsx, RiskGauge.tsx, ComparisonModal.tsx etc.
#: DO render the substantive claim data) — narrowing further would trade
#: this over-match for a worse under-match, the failure mode family #3
#: warns against preferring one direction's cure over the other's.
_NEXTJS_FRAMEWORK_BASENAMES: frozenset[str] = frozenset({
    "loading.tsx", "error.tsx", "not-found.tsx", "global-error.tsx",
})


def _is_test_path(path: str) -> bool:
    """True for test scaffolding nested under a matched directory (see
    _TEST_PATH_MARKERS) or a reserved Next.js framework special file (see
    _NEXTJS_FRAMEWORK_BASENAMES) — both make no claim/carry no PII of
    their own, whatever directory they sit in. Matches on the lowercased
    full path (path separators are always `/` in git-diff-style
    changed-files lists) plus a `test_`-prefixed basename (pytest
    convention). Name kept as `_is_test_path` (not renamed to something
    broader) since the Next.js exception is a second, narrow addition to
    the same "this file itself carries no claim" exclusion, not a second
    concept."""
    lowered = path.lower()
    if any(marker in lowered for marker in _TEST_PATH_MARKERS):
        return True
    basename = lowered.rsplit("/", 1)[-1]
    return basename.startswith("test_") or basename in _NEXTJS_FRAMEWORK_BASENAMES

#: R8 — the lane role this rule requires; a member of VALID_LANE_ROLES
#: (above) so it coexists with rule 8's own lane-shape check on the same
#: `lanes:` list rather than fighting it.
GROUND_TRUTH_LANE_ROLE = "ground_truth"
GROUND_TRUTH_LANE_REQUIRED_FIELDS = ("seat", "nb", "query_hash")

#: R10 — PII path classes: document intake, CRM + CRM-guardian client-data
#: services, the WhatsApp channel, and the yield-optimizer pitch gate
#: (grepped 2026-08-26: scripts/yield_optimizer_pitch_gate.py is the real
#: script — there is no bare yield_optimizer.py).
#: The `services/*` layer above is where the PII-bearing logic lives, but
#: the FastAPI `app/routers/*` layer that exposes it over HTTP was missing
#: entirely (found live 2026-08-26 by the same refuter round:
#: `app/routers/crm_clients.py` and `app/routers/whatsapp_conversations.py`
#: — both read/serve client phone numbers and names — matched neither
#: pattern). Router filenames verified on disk against the real tree
#: (`ls apps/backend-rag/backend/app/routers/`), not guessed.
#: NOTE (refuter round 2, 2026-08-26): the router layer does NOT include a
#: standalone `guardian.py` entry — that file is Core Guardian (decision
#: audit trail + risk scores, `app/routers/guardian.py`'s own docstring),
#: an unrelated system-health/monitoring API, not the CRM-Guardian
#: feature. The real CRM-Guardian router is `crm_guardian_drive.py`,
#: already covered by the `crm_*.py` glob below — adding bare
#: `guardian.py` would have been a false-positive AND redundant.
PII_PATH_PATTERNS: tuple[str, ...] = (
    "apps/backend-rag/backend/services/intake/*",
    "apps/backend-rag/backend/services/crm/*",
    "apps/backend-rag/backend/services/crm_guardian/*",
    "apps/backend-rag/backend/channels/whatsapp/*",
    "apps/backend-rag/backend/app/routers/crm_*.py",
    "apps/backend-rag/backend/app/routers/admin_crm_kg.py",
    "apps/backend-rag/backend/app/routers/admin_pii.py",
    "apps/backend-rag/backend/app/routers/intake_*.py",
    "apps/backend-rag/backend/app/routers/whatsapp_*.py",
    "scripts/yield_optimizer_pitch_gate.py",
)


def _any_path_matches(changed_files: list[str], patterns: tuple[str, ...]) -> bool:
    """True if ANY changed file matches ANY pattern — the trigger shape for
    R8/R10 (a single hit is enough to require the lane/seat discipline).
    Test scaffolding is excluded first (see _is_test_path) — a test asserts
    behavior, it does not itself carry a regulatory claim or client PII."""
    return any(
        fnmatch.fnmatchcase(f, pat)
        for f in changed_files
        if not _is_test_path(f)
        for pat in patterns
    )


def _seat_rule_verdict(
    rule: str,
    is_violation: bool,
    message: str,
    pack: dict[str, Any],
    today: datetime.date | None,
) -> tuple[list[str], str | None]:
    """Shared phasing+override plumbing for the seat rules (R8-R11 — R8/
    R10 land here, R11/R9 reuse this same helper in a follow-up PR): not
    a violation -> clean; else an explicit pack-level `seat_override:
    <non-empty reason>` wins outright (reported, never failed, and
    reported even after the flip — an override is a human call, not a
    rollout clock); else NOTICE before SEAT_RULES_ENFORCEMENT_DATE, hard
    violation on/after. `today` is overridable for tests, same convention
    as check_lanes_build_seat_diversity's own `today` parameter."""
    if not is_violation:
        return [], None
    override = pack.get("seat_override")
    if isinstance(override, str) and override.strip():
        return [], f"{rule} (overridden): {message} — {override.strip()}"
    if today is None:
        today = datetime.datetime.now(datetime.timezone.utc).date()
    if today < SEAT_RULES_ENFORCEMENT_DATE:
        return [], f"{rule}: {message}"
    return [f"{rule}: {message}"], None


def check_ground_truth_lane(
    pack: dict[str, Any],
    changed_files: list[str] | None,
    today: datetime.date | None = None,
) -> tuple[list[str], str | None]:
    """R8: a diff touching a GROUND_TRUTH_PATH_PATTERNS hit must declare a
    lane {role: ground_truth, seat, nb, query_hash} (all three non-empty
    strings — the same "complete or it's not evidence" shape as rule 1's
    receipts). GUILT: hit, no such lane, no override -> phased violation.
    INNOCENCE: no hit (skipped outright); hit with a well-formed
    ground_truth lane; hit with `seat_override`."""
    if not changed_files or not _any_path_matches(changed_files, GROUND_TRUTH_PATH_PATTERNS):
        return [], None
    lanes = pack.get("lanes")
    has_ground_truth_lane = False
    if isinstance(lanes, list):
        for entry in lanes:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("role", "")).strip().lower() != GROUND_TRUTH_LANE_ROLE:
                continue
            if all(
                isinstance(entry.get(f), str) and entry.get(f).strip()
                for f in GROUND_TRUTH_LANE_REQUIRED_FIELDS
            ):
                has_ground_truth_lane = True
                break
    message = (
        "diff touches a ground-truth path (backend KB / visa_engine / KBLI "
        "dataset / official pricing table / research-regulatory / a mouth "
        "claim page) but declares no well-formed {role: ground_truth, "
        "seat, nb, query_hash} lane"
    )
    return _seat_rule_verdict(
        "ground_truth", not has_ground_truth_lane, message, pack, today
    )


def check_pii_local_seat(
    pack: dict[str, Any],
    changed_files: list[str] | None,
    today: datetime.date | None = None,
) -> tuple[list[str], str | None]:
    """R10: a diff touching a PII_PATH_PATTERNS hit requires EVERY lane's
    seat (any role — build/review/read/ground_truth alike) to start with
    `ollama-`, unless the pack ALSO carries a non-empty `cloud_ok: <DPA
    ref>` AND `pii_scan: clean` (reads that existing rule-3 field rather
    than re-deriving PII status — same boundary the module docstring
    states for rule 3). GUILT: hit, >=1 non-`ollama-` seat, no cloud_ok+
    clean pair -> phased violation naming the offending seats. Also GUILT
    (refuter finding #7, 2026-08-27): hit, `lanes` absent/empty, no
    cloud_ok+clean pair -> phased violation — a pack with no lanes at all
    cannot demonstrate ANY seat was local, and D3/rule-8 already lets a
    Gear-1 pack omit `lanes` entirely, so without this branch a Gear-1
    diff could touch CRM/WhatsApp/intake code, declare no lanes, and get
    zero R10 signal (not even a NOTICE) — a silent bypass, not a coverage
    hole. Mirrors how check_ground_truth_lane already treats a missing/
    non-list `lanes` as "no matching lane found" by construction; R10 had
    the asymmetric shortcut because `offending` only ever grew from an
    actual iteration. INNOCENCE: no hit; every seat is `ollama-*`;
    cloud_ok+clean is present (still the escape even with zero lanes: a
    pack can assert "reviewed clean, DPA on file" without a lane list).
    Known, documented simplification: a lane whose job is not LLM
    inference over PII (e.g. an `nlm` ground-truth query, or the
    orchestrating `session` itself) is not exempted by role — a pack
    mixing a PII hit with a ground-truth hit in the same diff needs
    `cloud_ok` for its `nlm` lane too. Not fixed here: the spec names no
    role carve-out, and this rule ships NOTICE-only."""
    if not changed_files or not _any_path_matches(changed_files, PII_PATH_PATTERNS):
        return [], None
    if pack.get("pii_scan") == "clean":
        cloud_ok = pack.get("cloud_ok")
        if isinstance(cloud_ok, str) and cloud_ok.strip():
            return [], None
    lanes = pack.get("lanes")
    if not isinstance(lanes, list) or not lanes:
        message = (
            "diff touches a PII path (intake / CRM / CRM-guardian / "
            "WhatsApp channel / yield-optimizer) but declares no `lanes` "
            "at all — cannot confirm any seat that touched it was local, "
            "and no `cloud_ok: <DPA ref>` + `pii_scan: clean` pair either"
        )
        return _seat_rule_verdict("pii_local", True, message, pack, today)
    offending: list[str] = []
    for entry in lanes:
        if not isinstance(entry, dict):
            continue
        seat = entry.get("seat")
        if not isinstance(seat, str) or not seat.strip():
            continue
        if not seat.strip().lower().startswith("ollama-"):
            offending.append(seat.strip())
    message = (
        "diff touches a PII path (intake / CRM / CRM-guardian / WhatsApp "
        f"channel / yield-optimizer) — non-local seat(s) {offending} "
        "declared, and no `cloud_ok: <DPA ref>` + `pii_scan: clean` pair"
    )
    return _seat_rule_verdict("pii_local", bool(offending), message, pack, today)


# --------------------------------------------------------------------------
# R11/R9 — cheap-seat floor for mechanical diffs + Gear-3 council_run.
#
# PR-B of the seat-rules program (spec: 2026-08-26-PIANO-SPEC-receptor-live.md
# §8; PR-A landed R8 ground-truth-lane + R10 PII-local-seat as #5054). This
# branch was created from origin/main BEFORE #5054 merged, so it does not
# have that PR's `SEAT_RULES_ENFORCEMENT_DATE` / `_seat_rule_verdict` shared
# helper to reuse — self-contained here by design (mandate's own fallback
# for this ordering), under a distinct name (`R9_R11_ENFORCEMENT_DATE` /
# `_r9_r11_verdict`) specifically so this file never carries two same-named
# top-level definitions regardless of which PR's merge lands first. Same
# enforcement date (2026-09-02) and same `seat_override: <reason>` escape
# convention as R8/R10 — a human call, always reported, never silently
# dropped.
# --------------------------------------------------------------------------

R9_R11_ENFORCEMENT_DATE = datetime.date(2026, 9, 2)


def _r9_r11_verdict(
    rule: str,
    is_violation: bool,
    message: str,
    pack: dict[str, Any],
    today: datetime.date | None,
) -> tuple[list[str], str | None]:
    """Shared phasing+override plumbing for R9/R11 — not a violation ->
    clean; else an explicit pack-level `seat_override: <non-empty reason>`
    wins outright (reported, never failed — a human call, not a rollout
    clock); else NOTICE before R9_R11_ENFORCEMENT_DATE, hard violation
    on/after. `today` overridable for tests."""
    if not is_violation:
        return [], None
    override = pack.get("seat_override")
    if isinstance(override, str) and override.strip():
        return [], f"{rule} (overridden): {message} — {override.strip()}"
    if today is None:
        today = datetime.datetime.now(datetime.timezone.utc).date()
    if today < R9_R11_ENFORCEMENT_DATE:
        return [], f"{rule}: {message}"
    return [f"{rule}: {message}"], None


#: R11 — path classes judged MECHANICAL: translated strings, test fixtures,
#: the modus PENDING-ARMS ledger (append-only, human-authored prose), and a
#: mouth catalog asset (product photo, not source code). CORRECTED
#: 2026-08-27 by refuter round 1: the original `**/i18n/**/*.json` and
#: `**/locales/**/*.json` (a DOUBLED `**` with a literal `/` in between)
#: each demand an EXTRA path segment between the directory name and the
#: file — verified empirically with `fnmatch.fnmatchcase`, not by regex
#: reasoning by hand (the reasoning-by-hand version of this comment was
#: itself wrong and is why this needed correcting): every real on-disk
#: locale file sits directly at `<i18n-dir>/locales/<lang>.json` with NO
#: further subdirectory, so `**/locales/**/*.json` matched ZERO real files
#: (dead code) and `**/i18n/**/*.json` matched only by the incidental luck
#: of the `locales/` segment supplying that extra required `/` — a locale
#: file placed directly under `i18n/` with no `locales/` subfolder would
#: have been missed. Since `fnmatch`'s single `*` already crosses `/`,
#: the trailing `**` bought nothing: `**/i18n/*.json` and
#: `**/locales/*.json` (single star before the filename) match every real
#: file below EITHER nesting depth and are the patterns actually in force.
MECHANICAL_PATH_PATTERNS: tuple[str, ...] = (
    ".claude/skills/modus/PENDING-ARMS.md",
    "**/i18n/*.json",
    "**/locales/*.json",
    "**/fixtures/**",
    "apps/mouth/**/catalog*/**",
)

#: R11 — a build-lane seat token starting with one of these is "cheap"
#: (low-cost/high-speed tier), per the mandate's exact roster.
CHEAP_SEATS: tuple[str, ...] = (
    "claude-haiku-4-5",
    "codex-gpt-5.6-luna",
    "kimi-code/kimi-for-coding-highspeed",
    "tp1-qwen3.6-flash",
    "tp1-deepseek-v4-flash-0731",
)


def compute_seat_floor(changed_files: list[str] | None) -> bool:
    """R11 pure predicate (mirrors compute_floor's shape): True only when
    changed_files is non-empty AND every single file matches at least one
    MECHANICAL_PATH_PATTERNS entry. False on None/empty — "zero files are
    all mechanical" is not evidence of anything, same convention
    compute_floor uses for its own hotzone check on an empty diff."""
    if not changed_files:
        return False
    return all(
        any(fnmatch.fnmatchcase(f, pat) for pat in MECHANICAL_PATH_PATTERNS)
        for f in changed_files
    )


def check_cheap_seat_floor(
    pack: dict[str, Any],
    changed_files: list[str] | None,
    today: datetime.date | None = None,
) -> tuple[list[str], str | None]:
    """R11: when compute_seat_floor(changed_files) is True (100% of the
    diff is mechanical), the pack must declare at least one `role: build`
    lane whose `seat` starts with a CHEAP_SEATS entry, or carry a non-empty
    `seat_override: <reason>` naming why a frontier seat was used anyway.
    GUILT: 100% mechanical, no cheap build lane, no override -> phased
    violation. INNOCENCE: not 100% mechanical (skipped outright); >=1 cheap
    build lane present; seat_override present."""
    if not compute_seat_floor(changed_files):
        return [], None
    lanes = pack.get("lanes")
    has_cheap_build_lane = False
    if isinstance(lanes, list):
        for entry in lanes:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("role", "")).strip().lower() != "build":
                continue
            seat = entry.get("seat")
            if isinstance(seat, str) and any(
                seat.strip().lower().startswith(cheap) for cheap in CHEAP_SEATS
            ):
                has_cheap_build_lane = True
                break
    message = (
        "diff is 100% mechanical (i18n/locales strings, test fixtures, "
        "PENDING-ARMS.md, or a mouth catalog data file) but declares no "
        f"build lane on a cheap seat ({', '.join(CHEAP_SEATS)})"
    )
    return _r9_r11_verdict("seat_floor", not has_cheap_build_lane, message, pack, today)


#: R9 — review seats that count toward Gear-3 council quorum. RULED by Zero
#: 2026-09-02, verbatim: "metti codex, kimi (tanto tra 2 ore riprende), qwen,
#: deepseek, glm (questi 3 da TP1), gemini. I primi 3 titolari e gli altri
#: fallback nel caso un titolare e' indisponibile".
#:
#: WHY THE ROSTER GREW, measured the day it was ruled: the previous list held
#: exactly three seats, and on 2026-09-02 Kimi was 403 weekly-quota-dead while
#: arsenal_probe.py reported Codex TIMEOUT — so the quorum for EVERY Gear-3 PR
#: in the fleet rested on two seats, one of which the fleet's own liveness
#: probe called dead. (It was not: that TIMEOUT is the probe's flat 15s
#: ceiling, and called directly the seat answered and found a real defect.)
#: A quorum that a single quota reset can take to zero is not a quorum.
COUNCIL_REVIEW_SEATS_TITOLARI: tuple[str, ...] = (
    "codex-gpt-5.6-sol",
    "kimi-code/k3",
    "tp1-qwen3.8-max",
)

#: The reserve bench. Zero, correcting an earlier draft of this rule on the
#: day it was written: "le riserve non intervengono se i titolari ci sono" —
#: the bench does NOT play while the starters are available. So a reserve is a
#: SUBSTITUTION, not an equal alternative, and check_council_run_gear3 requires
#: any pack that counts even ONE reserve toward quorum to name the titolare it
#: replaced and how that unavailability was observed.
#:
#: The first draft only asked for a reason when the council was seated
#: ENTIRELY on reserves. That was strictly weaker than the ruling: it let one
#: reserve walk in beside an available titolare with nothing said, which is
#: exactly the substitution the ruling governs.
#:
#: A reserve's VERDICT still weighs the same as a titolare's — a finding is not
#: worth less because of which seat found it, and scoring it lower would be
#: scoring the messenger. Deliberately NOT enforced: "was that titolare really
#: down?" — the lint has no liveness data, and a guard that judges what it
#: cannot see is the guard-over-match family this repo already has scars in.
#: What is enforced is that somebody had to WRITE the substitution down.
COUNCIL_REVIEW_SEATS_FALLBACK: tuple[str, ...] = (
    "tp1-deepseek-v4-pro",
    "tp1-glm-5.2",
    "agy-gemini-3.1-pro",
)

COUNCIL_REVIEW_SEATS: tuple[str, ...] = (
    COUNCIL_REVIEW_SEATS_TITOLARI + COUNCIL_REVIEW_SEATS_FALLBACK
)


def _read_council_journal_seats(pack_dir: Path, council_run: Any) -> set[str]:
    """Resolves `council_run` (declared as a path relative to the pack's
    OWN directory — mirrors check_brief_ref_exists's repo-confinement
    shape, scoped to pack_dir instead of repo_root) to a journal.jsonl and
    returns the set of COUNCIL_REVIEW_SEATS values seen on lines shaped
    {"seat": str, "role": "review", "ok": true, "ts": str}. A line with
    extra/missing/wrong-typed keys just doesn't count (skipped, never
    raises) — same "degrade, don't crash" convention as sum_numstat().
    Returns the empty set (never raises) on: council_run missing/not a
    string, an absolute path, a path escaping pack_dir via `..`, a path
    that doesn't resolve to a file, or unreadable/non-JSON-Lines content —
    the caller treats that exactly like "found zero qualifying seats"."""
    if not isinstance(council_run, str) or not council_run.strip():
        return set()
    if Path(council_run).is_absolute():
        return set()
    pack_dir_resolved = pack_dir.resolve()
    journal_path = (pack_dir / council_run).resolve()
    if pack_dir_resolved not in (journal_path, *journal_path.parents):
        return set()
    if not journal_path.is_file():
        return set()
    try:
        text = journal_path.read_text(encoding="utf-8")
    except OSError:
        return set()
    seats: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        if entry.get("role") != "review" or entry.get("ok") is not True:
            continue
        ts = entry.get("ts")
        if not isinstance(ts, str) or not ts.strip():
            continue  # the declared minimal schema requires "ts" too
        seat = entry.get("seat")
        if isinstance(seat, str) and seat.strip() in COUNCIL_REVIEW_SEATS:
            seats.add(seat.strip())
    return seats


def check_council_run_gear3(
    pack: dict[str, Any],
    pack_dir: Path,
    gear: int | None,
    today: datetime.date | None = None,
) -> tuple[list[str], str | None]:
    """R9: a Gear-3 pack must declare `council_run: <path relative to the
    pack dir>` resolving to a journal.jsonl (inside the pack dir) carrying
    >=2 DISTINCT seats from COUNCIL_REVIEW_SEATS, each posting a line
    shaped {"seat": "...", "role": "review", "ok": true, "ts": "..."}.
    GUILT: gear==3, <2 distinct qualifying seats, no override -> phased
    violation. INNOCENCE: gear != 3 (skipped outright — Gear-3-only, same
    convention as check_dissent_nonempty_on_gear3); >=2 distinct seats
    found; seat_override present. Known day-0 measure, declared in this
    PR's body and NOT a bug: every EXISTING Gear-3 pack predates
    `council_run` entirely and will NOTICE (not FAIL) until 2026-09-02.

    SECOND LIMB (Zero 2026-09-02, roster split into titolari + reserves;
    "le riserve non intervengono se i titolari ci sono"): once quorum holds,
    a council counting ANY seat from COUNCIL_REVIEW_SEATS_FALLBACK — one is
    enough, beside a titolare is enough — must also declare a non-empty
    `seat_fallback_reason`. GUILT: >=1 reserve seat counted, no reason, no
    override. INNOCENCE: every counted seat is a titolare (the common path,
    untouched); a non-empty reason string; gear != 3; quorum already failing
    (that violation is reported alone rather than stacking a second one on
    the same pack)."""
    if gear != 3:
        return [], None
    seats = _read_council_journal_seats(pack_dir, pack.get("council_run"))
    has_quorum = len(seats) >= 2
    message = (
        "gear:3 pack declares no council_run journal with >=2 distinct "
        f"review seats from {COUNCIL_REVIEW_SEATS} marked ok:true"
    )
    verdict = _r9_r11_verdict("council_run", not has_quorum, message, pack, today)
    if not has_quorum:
        return verdict
    # Quorum is satisfied. Second limb (Zero 2026-09-02): "le riserve non
    # intervengono se i titolari ci sono". A reserve is a SUBSTITUTION, so ANY
    # reserve counted toward quorum — even one, even standing beside a
    # titolare — must be explained. This is the only half of the ruling a
    # linter can honestly check: it has no liveness data and cannot verify the
    # reason is TRUE, only that somebody was made to state one. A council of
    # titolari only never trips it, which is why the common path is untouched.
    benched = seats & set(COUNCIL_REVIEW_SEATS_FALLBACK)
    if benched:
        reason = pack.get("seat_fallback_reason")
        if not (isinstance(reason, str) and reason.strip()):
            return _r9_r11_verdict(
                "council_fallback_reason",
                True,
                "gear:3 council counts reserve seat(s) "
                f"({', '.join(sorted(benched))}) toward quorum — reserves do "
                "not play while the titolari "
                f"({', '.join(COUNCIL_REVIEW_SEATS_TITOLARI)}) are available, "
                "so declare `seat_fallback_reason: <which titolare each "
                "reserve replaced, and how that unavailability was observed>`",
                pack,
                today,
            )
    return verdict


def _pack_source_relpath(source_path: str, repo_root: Path) -> str:
    """POSIX-style, dot-segment-normalized repo-relative form of
    `source_path`, for comparing against EVIDENCE_ROOT_PACK_PATH. An
    absolute path outside repo_root falls back to its own normalized POSIX
    string rather than raising — this is a NOTICE-vs-violation classifier,
    not a path-confinement boundary (that job belongs to
    check_brief_ref_exists).

    Cross-family review (agy, 2026-08-27) on this PR's own diff caught a
    real gap the initial version had: a RELATIVE path was returned as-is,
    unnormalized, so a value like "evidence/x/../pack.yml" would never
    textually equal the literal "evidence/pack.yml" and silently pass as
    per-task even though it names the exact same file. `PurePosixPath`'s
    `.` component collapsing plus manual `..` resolution below closes that
    — os.path.normpath is NOT used here because it is platform-dependent
    (backslash handling on Windows) for a value that is always POSIX-style
    in this repo's evidence/ paths."""
    p = Path(source_path)
    if p.is_absolute():
        try:
            # Resolve BOTH sides before relative_to — an unresolved absolute
            # path (e.g. built from a tmp_path fixture through /tmp on
            # macOS, a symlink to /private/tmp) can fail relative_to()
            # against a resolved repo_root even when they name the same
            # file, a false-negative this rule must not produce.
            p = p.resolve().relative_to(repo_root.resolve())
        except ValueError:
            return _normalize_posix_segments(p.as_posix())
    return _normalize_posix_segments(p.as_posix())


def _normalize_posix_segments(posix_path: str) -> str:
    """Collapses `.`/`..` segments in a POSIX-style relative path string
    WITHOUT touching the filesystem (no symlink resolution, unlike
    Path.resolve() — the value being normalized here is frequently a
    string that names nothing on disk yet, e.g. a per-task path this
    linter never writes to). Pure string/segment logic: a leading `..`
    that would escape above the root simply stays as a literal `..`
    segment (this function classifies, it does not confine — path
    confinement is check_brief_ref_exists's job)."""
    segments: list[str] = []
    for part in posix_path.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if segments and segments[-1] != "..":
                segments.pop()
            else:
                segments.append(part)
            continue
        segments.append(part)
    return "/".join(segments) if segments else "."


def check_pack_not_at_deprecated_root(
    source_path: str | None,
    repo_root: Path,
    today: datetime.date | None = None,
) -> tuple[list[str], str | None]:
    """Rule 9 — deprecates the fixed root path `evidence/pack.yml`
    (EVIDENCE_ROOT_PACK_PATH). `source_path` must be THIS PR's own
    diff-relative pack path (e.g. `evidence_paths.py --resolve pack`'s
    stdout), resolved BEFORE any CI staging renames the file — see the
    module docstring rule 9 and scripts/ci/evidence_paths.py's `brief_ref`
    contract note for why the path a pack was actually READ from is the
    wrong signal here (under CI staging it is always the canonical
    `evidence/pack.yml`, whether the real file lives at root or in a
    per-task directory).

    `source_path` is `None` or empty (`""`) when the caller has no diff
    context — same "skip, don't guess" shape as check_gear_floor/
    compute_ceiling when --changed-files-file is absent: returns clean, no
    notice, rather than presuming guilt or innocence. NOTE (corrected
    2026-08-27, agy cross-family review of this PR's own diff): via the
    CLI this branch is in practice UNREACHABLE — `main()` defaults
    `--source-path` to the `pack_path` positional argument itself when the
    flag is omitted, precisely so a direct/local invocation (`python3
    evidence_pack_lint.py evidence/pack.yml`) is judged, not silently
    skipped. The `None`/`""` shape exists for OTHER Python callers of
    `lint()`/this function directly that don't thread source_path info
    through at all (every pre-rule-9 test in this file, for backward
    compatibility) — not for a CLI invocation with a bare `--source-path`
    flag and no value, which argparse rejects as a usage error before this
    function ever runs.

    Returns (violations, notice): before EVIDENCE_ROOT_DEPRECATION_DATE a
    root-path pack NOTICEs (exit 0); on/after, it is a violation (exit 1).
    A per-task-directory pack (any path other than the literal root one,
    dot-segments collapsed — see _normalize_posix_segments) is clean at
    any date — this function does not itself validate the per-task path's
    shape, that's evidence_paths.py's job. `today` overridable for tests
    without monkeypatching date.today()."""
    if not source_path:
        return [], None
    if _pack_source_relpath(source_path, repo_root) != EVIDENCE_ROOT_PACK_PATH:
        return [], None
    message = (
        f"{EVIDENCE_ROOT_PACK_PATH} is deprecated — write per-task evidence "
        "to evidence/<YYYY-MM>/<task-slug>-<8hex>/pack.yml instead "
        "(scripts/ci/evidence_paths.py resolves the path for you: "
        "--ref <branch>). The root path makes any two Gear>=2 PRs mutually "
        "exclusive in the merge queue by construction — see "
        "scripts/ci/evidence_paths.py's module docstring."
    )
    if today is None:
        today = datetime.datetime.now(datetime.timezone.utc).date()
    if today < EVIDENCE_ROOT_DEPRECATION_DATE:
        return [], f"evidence_root_deprecated: {message}"
    return [f"evidence_root_deprecated: {message}"], None


def check_brief_not_at_deprecated_root(
    brief_source_path: str | None,
    repo_root: Path,
    today: datetime.date | None = None,
) -> tuple[list[str], str | None]:
    """Rule 12 — the BRIEF half of the root-path deprecation Rule 9 opened.

    `brief_source_path` must be THIS PR's own diff-relative brief path — the
    value `scripts/ci/evidence_paths.py --resolve brief` prints, which
    harness-floor.yml's Step 2b already computes and exposes as
    `steps.evpaths.outputs.brief`. It is resolved from the PR's changed-files
    enumeration, so it is the path the diff actually WROTE, never a string
    read out of the pack.

    That distinction is the whole rule. A conformant pack always declares
    `brief_ref: evidence/brief.yml` (the staging contract), so the literal
    root string is present in every correct pack in this repo; judging that
    string would fail the entire fleet. This function never reads the pack.

    Same "skip, don't guess" shape as its pack sibling: a `None`/empty value
    means the caller has no diff context, and returns clean with no notice
    rather than presuming guilt or innocence. Unlike the pack rule there is
    no CLI default that backfills it from a positional argument — a local
    `python3 evidence_pack_lint.py evidence/pack.yml` knows the pack's path
    but genuinely does not know the brief's, and inventing one would be a
    guess. So this rule is inert outside CI by design, and the workflow is
    what arms it; that is stated rather than papered over, because "the rule
    exists" and "the rule is armed" are different claims (superscar #2).

    Returns (violations, notice): before EVIDENCE_ROOT_BRIEF_DEPRECATION_DATE
    a root-path brief NOTICEs (exit 0); on/after, it is a violation (exit 1).
    A per-task brief is clean at any date. `today` overridable for tests
    without monkeypatching date.today()."""
    if not brief_source_path:
        return [], None
    if _pack_source_relpath(brief_source_path, repo_root) != EVIDENCE_ROOT_BRIEF_PATH:
        return [], None
    message = (
        f"{EVIDENCE_ROOT_BRIEF_PATH} is deprecated as a WRITE target — write "
        "per-task evidence to evidence/<YYYY-MM>/<task-slug>-<8hex>/brief.yml "
        "instead (scripts/ci/evidence_paths.py --resolve brief). This does NOT "
        "change the `brief_ref:` contract: a pack must still declare the "
        "literal `brief_ref: evidence/brief.yml`, because CI lints a staged "
        "tree using canonical names — only the FILE moves, never the "
        "reference. Rule 9 deprecates the root pack for the same reason and "
        "cannot see this half: a PR whose pack is already migrated still "
        "makes every other root-brief PR mutually exclusive in the merge "
        "queue by construction (six such PRs measured open on 2026-08-31)."
    )
    if today is None:
        today = datetime.datetime.now(datetime.timezone.utc).date()
    if today < EVIDENCE_ROOT_BRIEF_DEPRECATION_DATE:
        return [], f"evidence_root_brief_deprecated: {message}"
    return [f"evidence_root_brief_deprecated: {message}"], None


# ------------------------------------------------------------------- lint()


def lint(
    pack_path: Path,
    repo_root: Path,
    changed_files: list[str] | None,
    measured_net_lines: int | None = None,
    numstat_text: str | None = None,
    source_path: str | None = None,
    measured_commits: int | None = None,
    brief_source_path: str | None = None,
) -> tuple[int, list[str]]:
    """Returns (exit_code, violations). exit_code: 0 clean, 1 guilty, 2 blind.

    `measured_net_lines` feeds compute_ceiling()'s rule 7 (a single
    pre-summed int — global net, no path filtering). `numstat_text` is a
    SEPARATE, raw `git diff --numstat` blob that feeds check_gear_floor()'s
    rule 6 size term (S1) — the floor needs the raw per-file rows (to
    exclude generated/vendored paths and sum CHURN, added+deleted per file —
    corrected 2026-08-27, was a cancelable per-file Σ|added−deleted| before
    the round-2 refuter fix), not the ceiling's pre-summed global net, so
    the two parameters are independent and neither substitutes for the
    other."""
    if not pack_path.exists():
        return 2, [f"BLIND: evidence pack not found at {pack_path}"]
    try:
        raw = pack_path.read_bytes()
    except OSError as exc:
        return 2, [f"BLIND: could not read evidence pack: {exc}"]

    # Size is checked on the RAW BYTES before yaml.safe_load ever runs (moved
    # here, adversarial review 2026-08-10): checking size only after parsing
    # protects nothing — an oversized/adversarial YAML has already paid the
    # full parse cost (and any amplification a crafted anchor/alias tree can
    # cause) before this function ever sees a violation. Short-circuit.
    size_violation = check_size_budget(raw)
    if size_violation:
        return 1, size_violation

    try:
        pack = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        return 2, [f"BLIND: evidence pack is not valid YAML: {exc}"]
    if not isinstance(pack, dict):
        return 2, ["BLIND: evidence pack YAML did not parse to a mapping"]

    # brief_ref resolves FIRST — receipts/dissent's gear-3-specific rules need
    # a STRICTLY validated gear (never a bool/float that happens to == 3).
    brief_violations, brief = check_brief_ref_exists(pack, repo_root)
    raw_gear = brief.get("gear") if isinstance(brief, dict) else None
    gear = raw_gear if type(raw_gear) is int and raw_gear in VALID_GEARS else None

    violations: list[str] = []
    violations += check_receipts_have_provenance(pack, gear)
    violations += check_pii_scan_clean(pack)
    violations += brief_violations
    violations += check_dissent_nonempty_on_gear3(pack, gear)
    violations += check_gear_floor(brief, changed_files, numstat_text)
    for _notice in check_acceptance_probe_pairing(brief, pack, gear):
        print(f"evidence_pack_lint: NOTICE — {_notice}", file=sys.stderr)
    for _notice in check_assumptions_register(brief):
        print(f"evidence_pack_lint: NOTICE — {_notice}", file=sys.stderr)

    appetite_violations, appetite_notices = check_appetite_acknowledgment(brief, pack)
    violations += appetite_violations
    for _notice in appetite_notices:
        print(f"evidence_pack_lint: NOTICE — {_notice}", file=sys.stderr)

    lane_violations, lane_notice = check_lanes_build_seat_diversity(pack, gear)
    violations += lane_violations
    if lane_notice:
        print(f"evidence_pack_lint: NOTICE — {lane_notice}", file=sys.stderr)

    # E3/R8-R11 seat rules (2026-08-26 program) — one call site. R8/R10
    # land here; R11 (seat_floor) and R9 (council_run) join this same
    # tuple in a follow-up PR (split per the mandate's PR-size contract),
    # reusing _seat_rule_verdict already defined above. Each is
    # independently phased+overridable, see their own docstrings.
    for _viol, _notice in (
        check_ground_truth_lane(pack, changed_files),
        check_pii_local_seat(pack, changed_files),
    ):
        violations += _viol
        if _notice:
            print(f"evidence_pack_lint: NOTICE — {_notice}", file=sys.stderr)

    root_violations, root_notice = check_pack_not_at_deprecated_root(source_path, repo_root)
    violations += root_violations
    if root_notice:
        print(f"evidence_pack_lint: NOTICE — {root_notice}", file=sys.stderr)

    # Rule 12 — the brief half. Kept as its own call rather than folded into
    # the pack rule above because the two take DIFFERENT inputs (the pack's
    # real path vs the brief's real path) and flip on DIFFERENT dates; one
    # function taking both would make it far too easy for a future edit to
    # judge a brief against the pack's constant, which is precisely the
    # blind spot this rule exists to close.
    brief_root_violations, brief_root_notice = check_brief_not_at_deprecated_root(
        brief_source_path, repo_root
    )
    violations += brief_root_violations
    if brief_root_notice:
        print(f"evidence_pack_lint: NOTICE — {brief_root_notice}", file=sys.stderr)

    if changed_files is None:
        # Self-contained notice (not folded into the shared "no
        # --changed-files-file supplied" message a few lines below, which
        # #5054/PR-A also extends — two PRs editing that one shared string
        # is a guaranteed merge collision; see this PR's own body for why
        # it stays self-contained from #5054 throughout).
        print("evidence_pack_lint: NOTICE — no --changed-files-file "
              "supplied, seat_floor check (rule 11) skipped for this run",
              file=sys.stderr)
    seat_floor_violations, seat_floor_notice = check_cheap_seat_floor(pack, changed_files)
    violations += seat_floor_violations
    if seat_floor_notice:
        print(f"evidence_pack_lint: NOTICE — {seat_floor_notice}", file=sys.stderr)

    council_violations, council_notice = check_council_run_gear3(pack, pack_path.parent, gear)
    violations += council_violations
    if council_notice:
        print(f"evidence_pack_lint: NOTICE — {council_notice}", file=sys.stderr)

    if changed_files is None:
        print("evidence_pack_lint: NOTICE — no --changed-files-file supplied, "
              "gear-floor/ceiling/ground-truth/pii-local checks "
              "(rules 6, 7, 9b-c) skipped for this run", file=sys.stderr)
    else:
        # Ceiling (rule 7 — see compute_ceiling() docstring): only the BARE
        # "ceiling: " prefix is a violation. Any parenthetical-qualified
        # variant — "ceiling (overridden): ..." or "ceiling (notice): ..." —
        # is a REPORT, never a violation, and does not fail the pack.
        _ceiling, ceiling_reasons = compute_ceiling(
            changed_files, gear, pack, measured_net_lines
        )
        for reason in ceiling_reasons:
            if reason.startswith("ceiling: "):
                violations.append(reason)
            else:
                print(f"evidence_pack_lint: NOTICE — {reason}", file=sys.stderr)

    # The countable-claims rule runs LAST, and deliberately independent of every
    # branch above: it needs no changed-files list, and it re-uses the SAME
    # numstat blob the floor's size term already consumes, so a pack's stated
    # diff stats are judged against the very measurement the gear floor was
    # computed from rather than against a second, possibly-divergent one.
    countable_violations, countable_notices = check_countable_claims(
        pack, numstat_text, measured_commits
    )
    violations += countable_violations
    for notice in countable_notices:
        print(f"evidence_pack_lint: NOTICE — {notice}", file=sys.stderr)

    return (1 if violations else 0), violations


# --------------------------------------------------------------------- CLI


def _read_changed_files(path_str: str | None) -> list[str] | None:
    if not path_str:
        return None
    p = Path(path_str)
    text = p.read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip()]


def sum_numstat(text: str) -> int:
    """Sum `git diff --numstat` output into a single net-line count
    (added - deleted), the measured source for compute_ceiling()'s rule-7
    shape (b) — pure function, no I/O, so it's testable directly (mirrors
    compute_floor()). Each line is "<added>\\t<deleted>\\t<path>"; binary
    files report "-\\t-\\tpath" per git's own numstat format and are
    skipped (their line-count is unknowable, not zero — excluding rather
    than miscounting them as 0 added/0 deleted). Malformed lines (wrong
    column count, non-numeric added/deleted where not "-") are skipped the
    same way — this function degrades gracefully rather than raising on a
    single garbled line from an unexpected git version."""
    net = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        added_s, deleted_s = parts[0], parts[1]
        if added_s == "-" or deleted_s == "-":
            continue  # binary file — numstat can't report a line count
        try:
            net += int(added_s) - int(deleted_s)
        except ValueError:
            continue
    return net


# ---------------------------------------------------------------------------
# COUNTABLE CLAIMS rule (2026-08-29). Every rule above judges the pack's
# SHAPE; none of them ever read a NUMBER the pack states about itself. PR #5157
# was BLOCKed three consecutive rounds and suspended under Agent-PR-Contract
# rule 8 without a single finding against its code: the gate kept catching
# arithmetic in the prose — "11 files, +1195/-119 across two commits" where the
# cited command returns 14 files, +1860/-83 and `rev-list --count` returns 6;
# "the 44 tests" where the branch has 64. Rule 8's own remedy applies ("if the
# correction is itself wrong, the surface is under-specified — write the spec"),
# and this is that spec in code: a number that a machine can derive is derived,
# never trusted.
#
# This is NOT a softening. It removes an avoidable class of miss from the human
# side of the gate so the adjudicator spends its rounds on judgment — dissent,
# risk framing, whether the fix is right — which stay judged exactly as they
# were. Nothing here lets a pack through that a previous rule rejected.
#
# THREE claim families, each with a DIFFERENT source of truth:
#   (a) diff stats  — recomputed from the same `git diff --numstat` blob CI
#                     already passes via --numstat-file (merge-base anchored,
#                     never a two-dot diff: W102).
#   (b) commit count — read from the GitHub event payload's
#                     `pull_request.commits`, which needs NO workflow change:
#                     GITHUB_EVENT_PATH is set for every Actions run. A local
#                     run passes --commit-count instead.
#   (c) test counts  — NOT recomputable by a linter (it does not run the
#                     suite), so the rule is SUBSTANTIATION: a test count
#                     narrated in `diff`/`lanes` must appear in some receipt in
#                     the same pack. This is deliberately lenient (any receipt
#                     whose claim/result contains that integer satisfies it) —
#                     it catches a number with no basis anywhere, which is the
#                     #5157 shape, and cannot convict a substantiated one.
#
# NEVER FAILS ON AN UNTAKEN MEASUREMENT (same discipline as the floor's size
# term): no numstat -> the diff-stat claims NOTICE, they do not convict. A pack
# that narrates no countable number is silent under this rule entirely.
#
# NO GRACE DATE, deliberately — and this is NOT a break with the E7 gate
# lifecycle (NOTICE, then FAIL) that rules 8/9/10 each honor. Those three ask
# authors to ADD something that does not exist yet (a `lanes:` block, a
# ground-truth lane, a per-task evidence directory), so a flip date buys the
# fleet time to adopt. This rule asks for nothing new: it can only convict a
# pack that states a number the repo contradicts, and every correct pack — and
# every pack stating no number at all — is clean on day one. A grace period
# here would protect nothing except inaccuracy.
#
# SCOPE IS DELIBERATELY NARROW (superscar #3, guard-over-match): only the
# `diff` and `lanes` subtrees are scanned. `dissent` and `receipts` are prose
# where numbers legitimately describe other things ("one test goes red where
# three do" is an argument, not a self-report), and the mandate that produced
# this rule says judgment stays judged.
# ---------------------------------------------------------------------------
COUNTABLE_SUBTREES: tuple[str, ...] = ("diff", "lanes")

#: Word forms that state a count. "both" is included because that is exactly
#: how #5157's `lanes[0]` narrated a 6-commit branch ("both commits").
_COUNT_WORDS: dict[str, int] = {
    "both": 2, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
_COUNT_WORD_ALT = "|".join(_COUNT_WORDS)

_FILES_CLAIM_RE = re.compile(r"\b(\d{1,5})\s+files?\b", re.IGNORECASE)
#: "+1195/-119", "+1195 / -119", "+1195/−119" (U+2212 minus, seen in prose).
_DIFFSTAT_CLAIM_RE = re.compile(r"\+\s?(\d{1,7})\s*/\s*[-−]\s?(\d{1,7})\b")
_COMMITS_CLAIM_RE = re.compile(
    rf"\b(\d{{1,4}}|{_COUNT_WORD_ALT})\s+commits?\b", re.IGNORECASE
)
_TESTS_CLAIM_RE = re.compile(r"\b(\d{1,5})\s+tests?\b", re.IGNORECASE)
_INTEGER_RE = re.compile(r"\d{1,7}")

_NUMSTAT_CMD = "git diff --numstat $(git merge-base origin/main HEAD)..HEAD"
_COMMITS_CMD = "git rev-list --count $(git merge-base origin/main HEAD)..HEAD"


def parse_numstat_totals(text: str | None) -> tuple[int, int, int, bool] | None:
    """`git diff --numstat` -> (files, insertions, deletions, has_binary).

    Returns None when there is no usable row at all (None/empty input, or every
    line malformed) — "could not measure", never "measured zero" (a zero here
    would be a false SMALL signal on what may be the largest diff in the run).
    Binary rows ("-\\t-\\tpath") COUNT as a changed file but contribute no
    line counts, and set has_binary so the caller can downgrade an
    insertions/deletions mismatch to a notice rather than convict on a total it
    knows is incomplete.
    """
    if not text:
        return None
    files = insertions = deletions = 0
    has_binary = False
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3 or not parts[2]:
            continue
        added_s, deleted_s = parts[0], parts[1]
        if added_s == "-" or deleted_s == "-":
            files += 1
            has_binary = True
            continue
        try:
            added, deleted = int(added_s), int(deleted_s)
        except ValueError:
            continue
        files += 1
        insertions += added
        deletions += deleted
    if files == 0:
        return None
    return files, insertions, deletions, has_binary


def measured_commit_count(
    explicit: int | None = None, event_path: str | None = None
) -> int | None:
    """The PR's commit count, or None when it cannot be measured.

    `explicit` (the --commit-count flag) always wins. Otherwise the GitHub
    Actions event payload is read from GITHUB_EVENT_PATH — present on every
    Actions run with no workflow change needed, which is why this rule can
    enforce commit counts today. A `merge_group` payload carries no
    `pull_request` key, an unreadable/garbled file carries nothing: both
    degrade to None (notice, never a violation).
    """
    if explicit is not None:
        return explicit if explicit >= 0 else None
    path = event_path if event_path is not None else os.environ.get("GITHUB_EVENT_PATH")
    if not path:
        return None
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    pr = payload.get("pull_request")
    if not isinstance(pr, dict):
        return None
    commits = pr.get("commits")
    return commits if type(commits) is int and commits >= 0 else None


def _iter_countable_scalars(pack: dict[str, Any]) -> list[tuple[str, str]]:
    """(dotted-path, text) for every string under COUNTABLE_SUBTREES."""
    out: list[tuple[str, str]] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}" if path else str(key))
        elif isinstance(node, list):
            for idx, value in enumerate(node):
                walk(value, f"{path}[{idx}]")
        elif isinstance(node, str):
            out.append((path, node))

    for subtree in COUNTABLE_SUBTREES:
        if subtree in pack:
            walk(pack[subtree], subtree)
    return out


def _receipt_integers(pack: dict[str, Any]) -> set[int]:
    """Every integer appearing in the receipts' `claim`/`result` prose.

    `cmd` and `ts` are excluded on purpose: a timestamp ("17:44Z") or a path
    fragment would substantiate a count it never measured.
    """
    found: set[int] = set()
    receipts = pack.get("receipts")
    if not isinstance(receipts, list):
        return found
    for entry in receipts:
        if not isinstance(entry, dict):
            continue
        for field in ("claim", "result"):
            value = entry.get(field)
            if isinstance(value, str):
                found.update(int(m) for m in _INTEGER_RE.findall(value))
    return found


def check_countable_claims(
    pack: dict[str, Any],
    numstat_text: str | None = None,
    commits: int | None = None,
) -> tuple[list[str], list[str]]:
    """The countable-claims rule — see the block comment above. Returns (violations, notices)."""
    violations: list[str] = []
    notices: list[str] = []
    if not isinstance(pack, dict):
        return violations, notices

    scalars = _iter_countable_scalars(pack)
    totals = parse_numstat_totals(numstat_text)
    receipt_ints = _receipt_integers(pack)

    for field, text in scalars:
        # ---- (a) diff stats -------------------------------------------
        file_claims = [int(m) for m in _FILES_CLAIM_RE.findall(text)]
        stat_claims = [(int(a), int(d)) for a, d in _DIFFSTAT_CLAIM_RE.findall(text)]
        if file_claims or stat_claims:
            if totals is None:
                notices.append(
                    f"countable claim (countable-claims rule): {field} narrates diff stats but no "
                    f"`git diff --numstat` was supplied (--numstat-file) — not verified "
                    f"this run"
                )
            else:
                files, insertions, deletions, has_binary = totals
                for claimed in file_claims:
                    if claimed != files:
                        violations.append(
                            f"countable claim (countable-claims rule): {field} narrates "
                            f"\"{claimed} files\" but the diff changes {files} — "
                            f"computed from `{_NUMSTAT_CMD}`. Correct the pack to the "
                            f"computed value or drop the number."
                        )
                for claimed_ins, claimed_del in stat_claims:
                    if (claimed_ins, claimed_del) == (insertions, deletions):
                        continue
                    message = (
                        f"countable claim (countable-claims rule): {field} narrates "
                        f"\"+{claimed_ins}/-{claimed_del}\" but the diff is "
                        f"+{insertions}/-{deletions} — computed from `{_NUMSTAT_CMD}`. "
                        f"Correct the pack to the computed value or drop the number."
                    )
                    if has_binary:
                        notices.append(
                            message + " (NOTICE only: this diff contains a binary file, "
                            "whose line counts numstat cannot report — the computed "
                            "totals are a lower bound.)"
                        )
                    else:
                        violations.append(message)

        # ---- (b) commit count -----------------------------------------
        for token in _COMMITS_CLAIM_RE.findall(text):
            claimed = _COUNT_WORDS.get(token.lower())
            if claimed is None:
                claimed = int(token)
            if commits is None:
                notices.append(
                    f"countable claim (countable-claims rule): {field} narrates \"{token} commits\" "
                    f"but no commit count was measurable (no --commit-count and no "
                    f"pull_request event payload) — not verified this run"
                )
            elif claimed != commits:
                violations.append(
                    f"countable claim (countable-claims rule): {field} narrates \"{token} commits\" "
                    f"(={claimed}) but the branch has {commits} — computed from "
                    f"`{_COMMITS_CMD}` (in CI, the pull_request event payload's "
                    f"`commits`). Correct the pack to the computed value or drop the "
                    f"number."
                )

        # ---- (c) test counts, substantiation --------------------------
        for token in _TESTS_CLAIM_RE.findall(text):
            claimed = int(token)
            if claimed not in receipt_ints:
                violations.append(
                    f"countable claim (countable-claims rule): {field} narrates \"{claimed} tests\" "
                    f"but no receipt in this pack reports that number — a test count "
                    f"must come from a receipt whose cmd actually ran the suite (e.g. "
                    f"`pytest -q` reporting \"N passed\"), never from prose. Add the "
                    f"receipt or drop the number."
                )

    return violations, notices


def format_measured_claims(
    numstat_text: str | None = None, commits: int | None = None
) -> str:
    """The canonical, machine-derived sentence an author should PASTE into
    `diff.net_lines` instead of counting by hand — the generate half of
    the countable-claims rule (`--print-measured`). Unmeasurable parts say so rather than
    guessing."""
    totals = parse_numstat_totals(numstat_text)
    if totals is None:
        stats = "diff stats unmeasured (no --numstat-file)"
    else:
        files, insertions, deletions, has_binary = totals
        stats = f"{files} files, +{insertions}/-{deletions}"
        if has_binary:
            stats += " (line counts exclude binary files)"
    commit_part = (
        f"{commits} commits" if commits is not None
        else "commit count unmeasured (no --commit-count, no pull_request payload)"
    )
    return f"{stats}, {commit_part}"


def selftest() -> int:
    import tempfile

    failures: list[str] = []

    def check(name: str, cond: bool) -> None:
        print(("  ok  " if cond else "  FAIL") + f" {name}")
        if not cond:
            failures.append(name)

    def write(p: Path, obj) -> None:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(yaml.safe_dump(obj, sort_keys=False), encoding="utf-8")

    good_receipt = {"claim": "tests pass", "cmd": "pytest -q", "exit": 0,
                     "ts": "2026-08-10T00:00:00Z", "seat": "sonnet-5"}

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        # ---- unit-level: compute_floor is pure, test directly -------------
        check("compute_floor: hotzone hit -> 3",
              compute_floor(["apps/backend-rag/backend/db/migrations_v2/0099_x.sql"]) == 3)
        check("compute_floor: workflow file -> 3",
              compute_floor([".github/workflows/new.yml"]) == 3)
        check("compute_floor: no hit -> 1",
              compute_floor(["docs/notes.md", "research/operations/x.md"]) == 1)
        check("compute_floor: empty list -> 1", compute_floor([]) == 1)

        # ---- unit-level: compute_ceiling / effort_for_gear are pure too ----
        docs_diff = ["docs/x.md"]
        _c, r = compute_ceiling(docs_diff, 3, {"council": True})
        check("compute_ceiling: guilt — gear-3 + council on 1-file md diff",
              bool(r) and r[0].startswith("ceiling:") and "gear_override" in r[0])
        _c, r = compute_ceiling(docs_diff, 3, {"council": True, "gear_override": "hotfix, verified live"})
        check("compute_ceiling: innocence — gear_override reports, does not fail",
              bool(r) and r[0].startswith("ceiling (overridden)"))
        _c, r = compute_ceiling(["apps/backend-rag/backend/app/auth/session.py"], 3, {"council": True})
        check("compute_ceiling: innocence — floor wins, hotzone diff silent", r == [])
        big_diff = [f"apps/backend-rag/backend/f{i}.py" for i in range(8)]
        _c, r = compute_ceiling(big_diff, 3, {"council": True})
        check("compute_ceiling: innocence — real 8-file backend diff not gear-1-shaped", r == [])
        _c, r = compute_ceiling(docs_diff, 3, {})
        check("compute_ceiling: innocence — gear-3 with no council/graders is not heavy", r == [])
        check("effort_for_gear: 1 -> medium", effort_for_gear(1) == "medium")
        check("effort_for_gear: 2 -> xhigh", effort_for_gear(2) == "xhigh")
        check("effort_for_gear: 3 -> xhigh", effort_for_gear(3) == "xhigh")
        try:
            effort_for_gear(4)
            check("effort_for_gear: guilt — invalid gear raises", False)
        except ValueError:
            check("effort_for_gear: guilt — invalid gear raises", True)

        # ---- innocence: a fully-conformant Gear-1 pack passes --------------
        write(root / "evidence" / "brief.yml", {
            "task_id": "ops-selftest", "gear": 1, "l_level": "L1",
            "gate_class": "none", "objective": "prove the linter",
            "grader": "codex-sol", "pii": "none",
        })
        write(root / "evidence" / "pack.yml", {
            "lanes": _SELFTEST_LANES,
            "brief_ref": "evidence/brief.yml",
            "receipts": [good_receipt],
            "dissent": [],
            "pii_scan": "clean",
        })
        rc, viol = lint(root / "evidence" / "pack.yml", root, None)
        check("innocence: conformant gear-1 pack passes", rc == 0 and viol == [])

        # ---- innocence: empty dissent on gear-2 is OK -----------------------
        write(root / "evidence" / "brief.yml", {
            "task_id": "ops-selftest", "gear": 2, "grader": "codex-sol",
        })
        rc, viol = lint(root / "evidence" / "pack.yml", root, None)
        check("innocence: empty dissent on gear-2 passes", rc == 0 and viol == [])

        # ---- guilt: zero dissent on gear-3 = consenso sospetto --------------
        write(root / "evidence" / "brief.yml", {
            "task_id": "ops-selftest", "gear": 3, "grader": "codex-sol",
        })
        rc, viol = lint(root / "evidence" / "pack.yml", root, None)
        check("guilt: zero dissent on gear-3 rejected", rc == 1)
        check("guilt: message names consenso sospetto",
              any("consenso sospetto" in v for v in viol))

        # ---- innocence: non-empty dissent on gear-3 passes ------------------
        write(root / "evidence" / "pack.yml", {
            "lanes": _SELFTEST_LANES,
            "brief_ref": "evidence/brief.yml",
            "receipts": [good_receipt],
            "dissent": [{"seat": "codex-sol", "objection": "x", "status": "PLAUSIBLE"}],
            "pii_scan": "clean",
        })
        rc, viol = lint(root / "evidence" / "pack.yml", root, None)
        check("innocence: non-empty dissent on gear-3 passes", rc == 0 and viol == [])

        # ---- guilt: dissent field missing entirely --------------------------
        write(root / "evidence" / "pack.yml", {
            "lanes": _SELFTEST_LANES,
            "brief_ref": "evidence/brief.yml",
            "receipts": [good_receipt],
            "pii_scan": "clean",
        })
        rc, viol = lint(root / "evidence" / "pack.yml", root, None)
        check("guilt: missing dissent field rejected", rc == 1)

        # ---- guilt: receipt missing a required field ------------------------
        write(root / "evidence" / "brief.yml", {"task_id": "x", "gear": 1, "grader": "y"})
        write(root / "evidence" / "pack.yml", {
            "lanes": _SELFTEST_LANES,
            "brief_ref": "evidence/brief.yml",
            "receipts": [{"claim": "no cmd here"}],
            "dissent": [],
            "pii_scan": "clean",
        })
        rc, viol = lint(root / "evidence" / "pack.yml", root, None)
        check("guilt: incomplete receipt rejected", rc == 1)
        check("innocence: a claim-free pack (no receipts key) isn't punished by rule 1",
              check_receipts_have_provenance({}) == [])

        # ---- guilt: pii_scan not clean ---------------------------------------
        write(root / "evidence" / "pack.yml", {
            "lanes": _SELFTEST_LANES,
            "brief_ref": "evidence/brief.yml",
            "receipts": [good_receipt],
            "dissent": [],
            "pii_scan": "dirty",
        })
        rc, viol = lint(root / "evidence" / "pack.yml", root, None)
        check("guilt: pii_scan != clean rejected", rc == 1)

        # ---- guilt: oversize pack ---------------------------------------------
        write(root / "evidence" / "pack.yml", {
            "lanes": _SELFTEST_LANES,
            "brief_ref": "evidence/brief.yml",
            "receipts": [good_receipt],
            "dissent": [],
            "pii_scan": "clean",
            "padding": "x" * (SIZE_TOKEN_CAP * 4 + 100),
        })
        rc, viol = lint(root / "evidence" / "pack.yml", root, None)
        check("guilt: oversize pack rejected", rc == 1)

        # ---- innocence: pack at the cap boundary is fine ----------------------
        check("innocence: exactly-at-cap size passes",
              check_size_budget(b"x" * (SIZE_TOKEN_CAP * 4)) == [])
        check("guilt: one byte over cap fails",
              check_size_budget(b"x" * (SIZE_TOKEN_CAP * 4 + 4)) != [])

        # ---- guilt: brief_ref missing key -------------------------------------
        write(root / "evidence" / "pack.yml", {
            "lanes": _SELFTEST_LANES,
            "receipts": [good_receipt], "dissent": [], "pii_scan": "clean",
        })
        rc, viol = lint(root / "evidence" / "pack.yml", root, None)
        check("guilt: brief_ref key missing rejected", rc == 1)

        # ---- guilt: brief_ref points nowhere -----------------------------------
        write(root / "evidence" / "pack.yml", {
            "lanes": _SELFTEST_LANES,
            "brief_ref": "evidence/does-not-exist.yml",
            "receipts": [good_receipt], "dissent": [], "pii_scan": "clean",
        })
        rc, viol = lint(root / "evidence" / "pack.yml", root, None)
        check("guilt: brief_ref dangling path rejected", rc == 1)

        # ---- guilt: gear below deterministic floor -----------------------------
        write(root / "evidence" / "brief.yml", {"task_id": "x", "gear": 1, "grader": "y"})
        write(root / "evidence" / "pack.yml", {
            "lanes": _SELFTEST_LANES,
            "brief_ref": "evidence/brief.yml",
            "receipts": [good_receipt], "dissent": [], "pii_scan": "clean",
        })
        hotzone_changed = ["apps/backend-rag/backend/app/auth/session.py"]
        rc, viol = lint(root / "evidence" / "pack.yml", root, hotzone_changed)
        check("guilt: gear 1 declared on a hotzone diff rejected", rc == 1)
        check("guilt: message names the floor", any("floor" in v for v in viol))

        # ---- innocence: gear 3 on the same hotzone diff passes -----------------
        write(root / "evidence" / "brief.yml", {"task_id": "x", "gear": 3, "grader": "y"})
        write(root / "evidence" / "pack.yml", {
            "lanes": _SELFTEST_LANES,
            "brief_ref": "evidence/brief.yml",
            "receipts": [good_receipt],
            "dissent": [{"seat": "codex-sol", "objection": "x", "status": "PLAUSIBLE"}],
            "pii_scan": "clean",
        })
        rc, viol = lint(root / "evidence" / "pack.yml", root, hotzone_changed)
        check("innocence: gear 3 on hotzone diff passes", rc == 0 and viol == [])

        # ---- innocence: non-hotzone diff never demands gear 3 ------------------
        write(root / "evidence" / "brief.yml", {"task_id": "x", "gear": 1, "grader": "y"})
        write(root / "evidence" / "pack.yml", {
            "lanes": _SELFTEST_LANES,
            "brief_ref": "evidence/brief.yml",
            "receipts": [good_receipt], "dissent": [], "pii_scan": "clean",
        })
        rc, viol = lint(root / "evidence" / "pack.yml", root, ["docs/readme.md"])
        check("innocence: gear 1 on non-hotzone diff passes", rc == 0 and viol == [])

        # ---- guilt: gear-3 pack + council over a Gear-1-shaped docs diff -------
        write(root / "evidence" / "brief.yml", {"task_id": "x", "gear": 3, "grader": "y"})
        write(root / "evidence" / "pack.yml", {
            "lanes": _SELFTEST_LANES,
            "brief_ref": "evidence/brief.yml",
            "receipts": [good_receipt],
            "dissent": [{"seat": "codex-sol", "objection": "x", "status": "PLAUSIBLE"}],
            "pii_scan": "clean",
            "council": True,
        })
        rc, viol = lint(root / "evidence" / "pack.yml", root, ["docs/x.md"])
        check("guilt: gear-3 + council on a docs-only diff rejected (ceiling)", rc == 1)
        check("guilt: ceiling message names gear_override",
              any("gear_override" in v for v in viol))

        # ---- innocence: same pack, but gear_override reports instead of failing
        write(root / "evidence" / "pack.yml", {
            "lanes": _SELFTEST_LANES,
            "brief_ref": "evidence/brief.yml",
            "receipts": [good_receipt],
            "dissent": [{"seat": "codex-sol", "objection": "x", "status": "PLAUSIBLE"}],
            "pii_scan": "clean",
            "council": True,
            "gear_override": "hotfix under active incident, verified live",
        })
        rc, viol = lint(root / "evidence" / "pack.yml", root, ["docs/x.md"])
        check("innocence: gear_override on the same diff passes (ceiling reports, not fails)",
              rc == 0 and viol == [])

        # ---- guilt: empty/missing receipts on a Gear-3 pack --------------------
        write(root / "evidence" / "brief.yml", {"task_id": "x", "gear": 3, "grader": "y"})
        write(root / "evidence" / "pack.yml", {
            "lanes": _SELFTEST_LANES,
            "brief_ref": "evidence/brief.yml",
            "dissent": [{"seat": "codex-sol", "objection": "x", "status": "PLAUSIBLE"}],
            "pii_scan": "clean",
        })
        rc, viol = lint(root / "evidence" / "pack.yml", root, None)
        check("guilt: empty receipts on gear-3 rejected", rc == 1)
        check("innocence: empty receipts on gear-1 is not this rule's problem",
              check_receipts_have_provenance({}, gear=1) == [])
        check("innocence: empty receipts on gear-3 IS this rule's problem",
              check_receipts_have_provenance({}, gear=3) != [])

        # ---- guilt: dissent entry missing structured fields --------------------
        write(root / "evidence" / "pack.yml", {
            "lanes": _SELFTEST_LANES,
            "brief_ref": "evidence/brief.yml",
            "receipts": [good_receipt],
            "dissent": [{}],
            "pii_scan": "clean",
        })
        rc, viol = lint(root / "evidence" / "pack.yml", root, None)
        check("guilt: dissent[{}] (missing fields) rejected", rc == 1)

        # ---- guilt: dissent entry with an invalid status ------------------------
        write(root / "evidence" / "pack.yml", {
            "lanes": _SELFTEST_LANES,
            "brief_ref": "evidence/brief.yml",
            "receipts": [good_receipt],
            "dissent": [{"seat": "codex-sol", "objection": "x", "status": "APPROVED"}],
            "pii_scan": "clean",
        })
        rc, viol = lint(root / "evidence" / "pack.yml", root, None)
        check("guilt: dissent status outside the closed set rejected", rc == 1)

        # ---- innocence: fully-structured dissent entry passes -------------------
        write(root / "evidence" / "pack.yml", {
            "lanes": _SELFTEST_LANES,
            "brief_ref": "evidence/brief.yml",
            "receipts": [good_receipt],
            "dissent": [{"seat": "codex-sol", "objection": "x", "status": "CONFIRMED"}],
            "pii_scan": "clean",
        })
        rc, viol = lint(root / "evidence" / "pack.yml", root, None)
        check("innocence: fully-structured dissent entry passes", rc == 0 and viol == [])

        # ---- guilt: brief_ref is an absolute path (path-confinement) ------------
        absolute_target = root / "evidence" / "brief.yml"
        write(root / "evidence" / "pack.yml", {
            "lanes": _SELFTEST_LANES,
            "brief_ref": str(absolute_target),
            "receipts": [good_receipt], "dissent": [], "pii_scan": "clean",
        })
        write(root / "evidence" / "brief.yml", {"task_id": "x", "gear": 1, "grader": "y"})
        rc, viol = lint(root / "evidence" / "pack.yml", root, None)
        check("guilt: absolute brief_ref rejected", rc == 1)
        check("guilt: message names absolute path", any("absolute" in v for v in viol))

        # ---- guilt: brief_ref escapes repo_root via .. --------------------------
        outside = root.parent / "outside-secret.yml"
        outside.write_text(yaml.safe_dump({"task_id": "x", "gear": 1, "grader": "y"}), encoding="utf-8")
        write(root / "evidence" / "pack.yml", {
            "lanes": _SELFTEST_LANES,
            "brief_ref": f"../{outside.name}",
            "receipts": [good_receipt], "dissent": [], "pii_scan": "clean",
        })
        rc, viol = lint(root / "evidence" / "pack.yml", root, None)
        check("guilt: brief_ref path-traversal escape rejected", rc == 1)
        outside.unlink()

        # ---- guilt: brief_ref names a directory, not a file ---------------------
        write(root / "evidence" / "pack.yml", {
            "lanes": _SELFTEST_LANES,
            "brief_ref": "evidence",
            "receipts": [good_receipt], "dissent": [], "pii_scan": "clean",
        })
        write(root / "evidence" / "brief.yml", {"task_id": "x", "gear": 1, "grader": "y"})
        rc, viol = lint(root / "evidence" / "pack.yml", root, None)
        check("guilt: brief_ref naming a directory rejected (no crash)", rc == 1)

        # ---- guilt: gear is a bool/float, not a genuine int (type coercion) -----
        write(root / "evidence" / "brief.yml", {"task_id": "x", "gear": True, "grader": "y"})
        write(root / "evidence" / "pack.yml", {
            "lanes": _SELFTEST_LANES,
            "brief_ref": "evidence/brief.yml",
            "receipts": [good_receipt], "dissent": [], "pii_scan": "clean",
        })
        rc, viol = lint(root / "evidence" / "pack.yml", root, None)
        check("guilt: gear=true (bool) rejected despite True==1", rc == 1)

        write(root / "evidence" / "brief.yml", {"task_id": "x", "gear": 1.0, "grader": "y"})
        rc, viol = lint(root / "evidence" / "pack.yml", root, None)
        check("guilt: gear=1.0 (float) rejected despite 1.0==1", rc == 1)

        # ---- lanes seat-diversity (D3) -----------------------------------------
        # shape violations always fail, regardless of date/gear
        write(root / "evidence" / "brief.yml", {"task_id": "x", "gear": 2, "grader": "y"})
        write(root / "evidence" / "pack.yml", {
            "brief_ref": "evidence/brief.yml",
            "receipts": [good_receipt], "dissent": [], "pii_scan": "clean",
            "lanes": "not-a-list",
        })
        rc, viol = lint(root / "evidence" / "pack.yml", root, None)
        check("guilt: lanes not a list rejected", rc == 1)

        write(root / "evidence" / "pack.yml", {
            "brief_ref": "evidence/brief.yml",
            "receipts": [good_receipt], "dissent": [], "pii_scan": "clean",
            "lanes": [{"lane": "D1", "role": "deploy", "seat": "codex"}],
        })
        rc, viol = lint(root / "evidence" / "pack.yml", root, None)
        check("guilt: invalid lane role rejected", rc == 1)

        # two Anthropic build lanes on Gear 2 -> violation on/after flip date
        before_flip = LANES_NON_ANTHROPIC_ENFORCEMENT_DATE - datetime.timedelta(days=1)
        after_flip = LANES_NON_ANTHROPIC_ENFORCEMENT_DATE
        write(root / "evidence" / "pack.yml", {
            "brief_ref": "evidence/brief.yml",
            "receipts": [good_receipt], "dissent": [], "pii_scan": "clean",
            "lanes": [
                {"lane": "D1", "role": "build", "seat": "sonnet"},
                {"lane": "D2", "role": "build", "seat": "opus"},
            ],
        })
        viol_pre, notice_pre = check_lanes_build_seat_diversity(
            {"lanes": [
                {"lane": "D1", "role": "build", "seat": "sonnet"},
                {"lane": "D2", "role": "build", "seat": "opus"},
            ]},
            gear=2, today=before_flip,
        )
        check("lanes: pre-flip Gear-2 + 2 Anthropic build lanes -> NOTICE (no violation)",
              viol_pre == [] and notice_pre is not None and "D3" in notice_pre)
        viol_post, notice_post = check_lanes_build_seat_diversity(
            {"lanes": [
                {"lane": "D1", "role": "build", "seat": "sonnet"},
                {"lane": "D2", "role": "build", "seat": "opus"},
            ]},
            gear=2, today=after_flip,
        )
        check("lanes: post-flip Gear-2 + 2 Anthropic build lanes -> violation",
              bool(viol_post) and notice_post is None and "D3" in viol_post[0])

        # two build lanes with one non-Anthropic -> innocent on both sides
        viol_mixed, notice_mixed = check_lanes_build_seat_diversity(
            {"lanes": [
                {"lane": "D1", "role": "build", "seat": "sonnet"},
                {"lane": "D2", "role": "build", "seat": "codex"},
            ]},
            gear=2, today=after_flip,
        )
        check("innocence: Gear-2 + 2 build lanes with one non-Anthropic -> clean",
              viol_mixed == [] and notice_mixed is None)

        # Gear 1 with two Anthropic build lanes -> exempt
        viol_g1, notice_g1 = check_lanes_build_seat_diversity(
            {"lanes": [
                {"lane": "D1", "role": "build", "seat": "sonnet"},
                {"lane": "D2", "role": "build", "seat": "opus"},
            ]},
            gear=1, today=after_flip,
        )
        check("innocence: Gear-1 + 2 Anthropic build lanes -> exempt", viol_g1 == [] and notice_g1 is None)

        # single build lane -> exempt
        viol_single, notice_single = check_lanes_build_seat_diversity(
            {"lanes": [
                {"lane": "D1", "role": "build", "seat": "sonnet"},
                {"lane": "D2", "role": "review", "seat": "opus"},
            ]},
            gear=2, today=after_flip,
        )
        check("innocence: Gear-2 + 1 build lane -> exempt", viol_single == [] and notice_single is None)

        # substring trap: opusculum / claude_ish are NOT Anthropic
        viol_trap, notice_trap = check_lanes_build_seat_diversity(
            {"lanes": [
                {"lane": "D1", "role": "build", "seat": "opusculum"},
                {"lane": "D2", "role": "build", "seat": "claude_ish"},
            ]},
            gear=2, today=after_flip,
        )
        check("innocence: opusculum/claude_ish are non-Anthropic by word-aware match",
              viol_trap == [] and notice_trap is None)

        # ---- countable claims (guilt + innocence) ------------------------------
        cc_numstat = "1800\t60\ta.py\n60\t23\tb.py\n"
        cc_receipts = [{"claim": "suite", "result": "64 passed", "cmd": "pytest -q",
                        "exit": 0, "ts": "2026-08-29T00:00:00Z", "seat": "sonnet-5"}]
        cc_bad = {
            "diff": {"net_lines": "11 files, +1195/-119 across two commits"},
            "lanes": [{"lane": "D1", "role": "build", "seat": "codex",
                       "note": "both commits, the 44 tests"}],
            "receipts": cc_receipts,
        }
        cc_viol, _ = check_countable_claims(cc_bad, cc_numstat, commits=6)
        check("countable claims: guilt — wrong file count convicted",
              any('"11 files"' in v and "changes 2" in v for v in cc_viol))
        check("countable claims: guilt — wrong +ins/-del convicted",
              any('"+1195/-119"' in v and "+1860/-83" in v for v in cc_viol))
        check("countable claims: guilt — wrong commit count convicted (digit and word form)",
              sum(1 for v in cc_viol if "commits" in v) == 2)
        check("countable claims: guilt — unsubstantiated test count convicted",
              any('"44 tests"' in v for v in cc_viol))
        cc_good = {
            "diff": {"net_lines": "2 files, +1860/-83 across 6 commits"},
            "lanes": [{"lane": "D1", "role": "build", "seat": "codex",
                       "note": "64 tests pass"}],
            "receipts": cc_receipts,
        }
        check("countable claims: innocence — accurate numbers pass",
              check_countable_claims(cc_good, cc_numstat, commits=6) == ([], []))
        cc_unmeasured_viol, cc_unmeasured_notes = check_countable_claims(
            cc_bad, None, commits=None
        )
        check("countable claims: innocence — unmeasured never convicts on diff stats/commits",
              not any("files" in v or "commits" in v for v in cc_unmeasured_viol)
              and bool(cc_unmeasured_notes))
        check("countable claims: innocence — dissent prose is out of scope",
              check_countable_claims(
                  {"dissent": [{"objection": "3 files, +1/-1, two commits, 44 tests"}],
                   "receipts": cc_receipts},
                  cc_numstat, commits=6,
              ) == ([], []))
        check("countable claims: --print-measured emits the pasteable sentence",
              format_measured_claims(cc_numstat, 6) == "2 files, +1860/-83, 6 commits")

        # ---- acceptance-probe pairing (rule 12, guilt + innocence) ------------
        cap_receipt_foo = {"claim": "foo test", "cmd": "pytest -k foo", "exit": 0,
                            "ts": "2026-08-10T00:00:00Z", "seat": "sonnet-5"}
        cap_receipt_drain = {"claim": "drain test", "cmd": "pytest -k drain", "exit": 0,
                              "ts": "2026-08-10T00:00:00Z", "seat": "sonnet-5"}
        cap_receipt_bar = {"claim": "bar test", "cmd": "pytest -k bar", "exit": 0,
                            "ts": "2026-08-10T00:00:00Z", "seat": "sonnet-5"}
        cap_receipt_baz = {"claim": "baz test", "cmd": "pytest -k baz", "exit": 0,
                            "ts": "2026-08-10T00:00:00Z", "seat": "sonnet-5"}
        cap_receipt_sha = {"claim": "sha256 verified against source manifest",
                            "cmd": "python3 verify.py", "exit": 0,
                            "ts": "2026-08-10T00:00:00Z", "seat": "sonnet-5"}

        cap_legacy_brief = {
            "acceptance": [
                "WHEN a client submits the form THE system SHALL confirm receipt.",
                "WHILE the queue is draining THE worker SHALL not double-process an item.",
            ],
        }
        cap_legacy_notices = check_acceptance_probe_pairing(cap_legacy_brief, {}, 2)
        check("acceptance-probe: guilt — gear-2 legacy string bullets emit coverage notice",
              len(cap_legacy_notices) == 1
              and cap_legacy_notices[0].startswith("acceptance-probe: 2 of 2"))
        check("acceptance-probe: innocence — gear 1 is out of scope",
              check_acceptance_probe_pairing(cap_legacy_brief, {}, 1) == [])

        cap_unbound_brief = {
            "acceptance": [
                {"text": "WHEN the suite runs THE gate SHALL report the exit code.",
                 "probe": "pytest -k foo"},
            ],
        }
        cap_unbound_notices = check_acceptance_probe_pairing(
            cap_unbound_brief, {"receipts": [good_receipt]}, 2
        )
        check("acceptance-probe: guilt — declared probe bound to no receipt notices",
              any("unrecorded" in n for n in cap_unbound_notices))

        cap_non_ears_brief = {
            "acceptance": [
                {"text": "the deploy finishes and the health check returns green",
                 "probe": "pytest -k bar"},
            ],
        }
        cap_non_ears_notices = check_acceptance_probe_pairing(
            cap_non_ears_brief, {"receipts": [cap_receipt_bar]}, 2
        )
        check("acceptance-probe: guilt — non-EARS bullet text notices",
              any("not EARS-shaped" in n for n in cap_non_ears_notices))

        cap_lowercase_brief = {
            "acceptance": [
                {"text": "the check is green if the migration applies when run",
                 "probe": "pytest -k baz"},
            ],
        }
        cap_lowercase_notices = check_acceptance_probe_pairing(
            cap_lowercase_brief, {"receipts": [cap_receipt_baz]}, 2
        )
        check("acceptance-probe: guilt — lowercase ears words do not count",
              any("not EARS-shaped" in n for n in cap_lowercase_notices))

        cap_clean_brief = {
            "acceptance": [
                {"text": "WHEN the suite runs THE gate SHALL report the exit code.",
                 "probe": "pytest -k foo"},
                {"text": "WHILE the queue is draining THE worker SHALL not double-process.",
                 "probe": "pytest -k drain"},
            ],
        }
        check("acceptance-probe: innocence — fully probed + bound + EARS pack is silent",
              check_acceptance_probe_pairing(
                  cap_clean_brief, {"receipts": [cap_receipt_foo, cap_receipt_drain]}, 2
              ) == [])

        check("acceptance-probe: innocence — absent acceptance block is silent",
              check_acceptance_probe_pairing({}, {}, 2) == [])

        cap_claim_bound_brief = {
            "acceptance": [
                {"text": "WHEN the case closes THE report SHALL cite the sha.",
                 "probe": "sha256 verified against source"},
            ],
        }
        check("acceptance-probe: innocence — probe bound via receipt claim (not only cmd)",
              check_acceptance_probe_pairing(
                  cap_claim_bound_brief, {"receipts": [cap_receipt_sha]}, 2
              ) == [])

        # ---- rule 12 regressions from adversarial review 2026-08-29 ----------
        # Each pins a defect a refuter found and this session REPRODUCED before
        # accepting it; without these the four fixes are unarmed (superscar #2).
        substring_brief = {"gear": 2,
                           "acceptance": [{"text": "SHALL run", "probe": "ls"}]}
        check("acceptance-probe: guilt — probe does not bind inside a longer word",
              any("unrecorded" in n for n in check_acceptance_probe_pairing(
                  substring_brief, {"receipts": [{"cmd": "run the tools suite"}]}, 2)))
        check("acceptance-probe: innocence — probe binds as a whole token",
              not any("unrecorded" in n for n in check_acceptance_probe_pairing(
                  substring_brief, {"receipts": [{"cmd": "ls -la"}]}, 2)))
        dupe_brief = {"gear": 2, "acceptance": [
            {"text": "SHALL a", "probe": "same-probe"},
            {"text": "SHALL b", "probe": "same-probe"}]}
        check("acceptance-probe: innocence — one probe named twice counts once",
              any("1 declared probe(s)" in n for n in check_acceptance_probe_pairing(
                  dupe_brief, {"receipts": []}, 2)))
        messy = check_acceptance_probe_pairing(
            {"gear": 2, "acceptance": ['he said "go"\nsecond line']}, {}, 2)
        check("acceptance-probe: innocence — a notice never spans stderr lines",
              all("\n" not in n and '"go"' not in n for n in messy))
        check("acceptance-probe: innocence — a non-mapping pack cannot crash the rule",
              any("unrecorded" in n for n in check_acceptance_probe_pairing(
                  {"gear": 2, "acceptance": [{"text": "SHALL x", "probe": "p"}]},
                  None, 2)))

        # ---- assumptions register (rule 13, guilt + innocence) ----------------
        aa_unverified_only = {
            "assumptions": [
                {"text": "the client already holds a valid B211A", "status": "unverified",
                 "probe": "pytest -k test_b211a_probe"},
            ],
        }
        aa_unverified_notices = check_assumptions_register(aa_unverified_only)
        check("assumptions: guilt — one unverified entry fires N1",
              len(aa_unverified_notices) == 1
              and aa_unverified_notices[0].startswith("assumptions: 1 of "))

        aa_pending = {"assumptions": [{"text": "the queue drains nightly", "status": "pending"}]}
        aa_pending_notices = check_assumptions_register(aa_pending)
        check("assumptions: guilt — status 'pending' fires N2 (recognised status)",
              any("no recognised status" in n for n in aa_pending_notices))
        check("assumptions: guilt — status 'pending' does NOT fire N1 ('unverified')",
              not any(n.startswith("assumptions: ") and "still 'unverified'" in n
                      for n in aa_pending_notices))

        aa_typo = {"assumptions": [{"text": "the mirror is idempotent", "status": "unverfied"}]}
        aa_typo_notices = check_assumptions_register(aa_typo)
        check("assumptions: guilt — status typo 'unverfied' fires N2, not N1",
              any("no recognised status" in n for n in aa_typo_notices)
              and not any("still 'unverified'" in n for n in aa_typo_notices))

        aa_bare_string = {"assumptions": ["the API key never expires"]}
        check("assumptions: guilt — a bare string entry fires N2",
              any("no recognised status" in n
                  for n in check_assumptions_register(aa_bare_string)))

        aa_missing_status = {"assumptions": [{"text": "the cron runs hourly"}]}
        check("assumptions: guilt — a missing 'status:' key fires N2",
              any("no recognised status" in n
                  for n in check_assumptions_register(aa_missing_status)))

        aa_no_probe = {"assumptions": [{"text": "the ledger is append-only", "status": "unverified"}]}
        aa_no_probe_notices = check_assumptions_register(aa_no_probe)
        check("assumptions: guilt — unverified with no probe fires BOTH N1 and N3",
              any("still 'unverified'" in n for n in aa_no_probe_notices)
              and any("declare no 'probe:'" in n for n in aa_no_probe_notices))

        aa_all_verified = {
            "assumptions": [
                {"text": "the schema migration already ran", "status": "verified"},
                {"text": "the receipt format is stable", "status": "verified"},
            ],
        }
        check("assumptions: innocence — every entry 'verified' is silent",
              check_assumptions_register(aa_all_verified) == [])

        check("assumptions: innocence — 'assumptions:' absent is silent",
              check_assumptions_register({}) == [])

        check("assumptions: innocence — 'assumptions: []' is silent",
              check_assumptions_register({"assumptions": []}) == [])

        check("assumptions: innocence — brief=None does not crash",
              check_assumptions_register(None) == [])

        check("assumptions: innocence — 'assumptions:' as a mapping does not crash",
              check_assumptions_register({"assumptions": {"text": "not a list"}}) == [])
        check("assumptions: innocence — 'assumptions:' as a bare string does not crash",
              check_assumptions_register({"assumptions": "not a list"}) == [])

        aa_whitespace_verified = {
            "assumptions": [{"text": "the token rotates weekly", "status": "  VERIFIED  "}],
        }
        check("assumptions: innocence — 'status' tolerates whitespace + case",
              check_assumptions_register(aa_whitespace_verified) == [])

        aa_unverified_with_probe = {
            "assumptions": [
                {"text": "the outbox drains within 5 minutes", "status": "unverified",
                 "probe": "pytest -k test_outbox_drain_latency"},
            ],
        }
        aa_unverified_with_probe_notices = check_assumptions_register(aa_unverified_with_probe)
        check("assumptions: innocence — unverified WITH a probe fires N1 but not N3",
              any("still 'unverified'" in n for n in aa_unverified_with_probe_notices)
              and not any("declare no 'probe:'" in n
                          for n in aa_unverified_with_probe_notices))

        # Two gaps found by MUTATION, not by reading: with a corpus that
        # lacked these, `probe: "   "` counted as a probe (N3 went silent on
        # exactly the boilerplate degeneration it exists to surface), and a
        # bare-string entry rendered as "<non-text bullet>" instead of naming
        # itself (N2's whole job is naming the offender, and for a bare string
        # the string IS the text). Both mutants survived the first corpus.
        aa_blank_probe = check_assumptions_register(
            {"assumptions": [
                {"text": "the lease renews", "status": "unverified", "probe": "   "},
            ]}
        )
        check("assumptions: guilt — a whitespace-only probe is not a probe (N3 fires)",
              any("declare no 'probe:'" in n for n in aa_blank_probe))

        aa_bare_string = check_assumptions_register(
            {"assumptions": ["the queue is drained by the nightly cron"]}
        )
        check("assumptions: guilt — a bare-string entry names ITSELF in the notice",
              any("the queue is drained by the nightly cron" in n
                  for n in aa_bare_string))

        # Blind adversarial review 2026-08-29 (Kimi K3, finding 1),
        # CONFIRMED on disk before accepting: the helper collapsed
        # whitespace but ESC/BEL/NUL are not whitespace, so they reached
        # stderr verbatim while the docstring claimed "SANITIZED first".
        aa_control = check_assumptions_register(
            {"assumptions": [
                {"text": "settle \x1b[31mRED\x1b[0m later \x07\x00",
                 "status": "unverified"},
            ]}
        )
        check("assumptions: innocence — control/ANSI bytes never reach a notice",
              all(not any(c in n for c in "\x1b\x07\x00") for n in aa_control))

        aa_messy = check_assumptions_register(
            {"assumptions": [{"text": 'he said "go"\nsecond line', "status": "unverified"}]}
        )
        check("assumptions: innocence — a notice never spans stderr lines",
              all("\n" not in n for n in aa_messy))

        # ---- appetite acknowledgment (rule 14, guilt + innocence) -------------
        # THE ONLY RULE IN THIS LANE THAT CAN FAIL — mirrors gear_override's
        # (rule 7) acknowledgment discipline exactly.
        ap_wc_brief = {"appetite": {"wall_clock_hours": 4}}
        ap_wc_over_pack = {"spend": {"wall_clock_hours": 11}}
        ap_wc_viol, ap_wc_notices = check_appetite_acknowledgment(ap_wc_brief, ap_wc_over_pack)
        check("appetite: guilt — over wall_clock_hours with no acknowledgment fires",
              bool(ap_wc_viol) and ap_wc_notices == [])

        ap_ar_brief = {"appetite": {"adversarial_rounds": 2}}
        ap_ar_over_pack = {"spend": {"adversarial_rounds": 5}}
        ap_ar_viol, _ = check_appetite_acknowledgment(ap_ar_brief, ap_ar_over_pack)
        check("appetite: guilt — over adversarial_rounds names BOTH numbers",
              bool(ap_ar_viol) and "declared 2" in ap_ar_viol[0]
              and "observed 5" in ap_ar_viol[0])

        ap_two_brief = {"appetite": {"wall_clock_hours": 4, "adversarial_rounds": 2}}
        ap_two_pack = {"spend": {"wall_clock_hours": 11, "adversarial_rounds": 5}}
        ap_two_viol, _ = check_appetite_acknowledgment(ap_two_brief, ap_two_pack)
        check("appetite: guilt — over two dimensions names both in the message",
              bool(ap_two_viol) and "wall_clock_hours" in ap_two_viol[0]
              and "adversarial_rounds" in ap_two_viol[0])

        ap_blank_ack_pack = {"spend": {"wall_clock_hours": 11}, "appetite_exceeded": "   "}
        ap_blank_ack_viol, _ = check_appetite_acknowledgment(ap_wc_brief, ap_blank_ack_pack)
        check("appetite: guilt — whitespace-only appetite_exceeded is not an acknowledgment",
              bool(ap_blank_ack_viol))

        ap_nonstr_ack_pack = {"spend": {"wall_clock_hours": 11}, "appetite_exceeded": 42}
        ap_nonstr_ack_viol, _ = check_appetite_acknowledgment(ap_wc_brief, ap_nonstr_ack_pack)
        check("appetite: guilt — non-str appetite_exceeded is not an acknowledgment",
              bool(ap_nonstr_ack_viol))

        ap_acked_pack = {
            "spend": {"wall_clock_hours": 11},
            "appetite_exceeded": "hotfix under active incident, verified live",
        }
        ap_acked_viol, ap_acked_notices = check_appetite_acknowledgment(ap_wc_brief, ap_acked_pack)
        check("appetite: innocence — the same overrun WITH acknowledgment reports, not fails",
              ap_acked_viol == [] and len(ap_acked_notices) == 1
              and "acknowledged" in ap_acked_notices[0])

        check("appetite: innocence — no 'appetite:' block is silent",
              check_appetite_acknowledgment({"gear": 1}, {}) == ([], []))

        ap_corpus_string = (
            'one session; two adversarial rounds (Kimi, then Codex on the fixes); no third round — leftover objections become spec caveats, not rewrites.'
        )
        check("appetite: innocence — the real corpus STRING shape is silent",
              check_appetite_acknowledgment({"appetite": ap_corpus_string}, {}) == ([], []))

        ap_unmeasured_viol, ap_unmeasured_notices = check_appetite_acknowledgment(ap_wc_brief, {})
        check("appetite: innocence — appetite declared, spend absent -> unmeasured notice",
              ap_unmeasured_viol == [] and len(ap_unmeasured_notices) == 1
              and "not verified this run" in ap_unmeasured_notices[0])

        check("appetite: innocence — spend EQUAL to the ceiling is not a breach",
              check_appetite_acknowledgment(
                  ap_wc_brief, {"spend": {"wall_clock_hours": 4}}
              ) == ([], []))

        check("appetite: innocence — spend under the ceiling is silent",
              check_appetite_acknowledgment(
                  ap_wc_brief, {"spend": {"wall_clock_hours": 1}}
              ) == ([], []))

        check("appetite: innocence — 'appetite: {}' is silent",
              check_appetite_acknowledgment({"appetite": {}}, {}) == ([], []))

        check("appetite: innocence — a bool ceiling is not a numeric ceiling",
              check_appetite_acknowledgment(
                  {"appetite": {"wall_clock_hours": True}},
                  {"spend": {"wall_clock_hours": 99}},
              ) == ([], []))

        check("appetite: innocence — brief=None / pack=None does not crash",
              check_appetite_acknowledgment(None, None) == ([], []))

        ap_non_mapping_spend = [
            check_appetite_acknowledgment(ap_wc_brief, {"spend": "eleven hours"}),
            check_appetite_acknowledgment(ap_wc_brief, {"spend": [1, 2, 3]}),
            check_appetite_acknowledgment(ap_wc_brief, {"spend": 11}),
        ]
        check("appetite: innocence — a non-mapping 'spend:' (str/list/int) does not crash",
              all(v == [] and len(n) == 1 and "not verified this run" in n[0]
                  for v, n in ap_non_mapping_spend))

        # ---- rule 14, found by the ORCHESTRATOR's gate, not the implementer ----
        # The acknowledgment reason reached stderr with NO sanitising at all
        # (measured on this branch before the fix: a newline split the notice
        # across two stderr lines and ESC/BEL travelled to the terminal). That
        # is the SAME defect blind review found in rule 13 one PR earlier —
        # which is why the sanitiser is now a shared, named function instead of
        # living inside one rule's formatter.
        ap_hostile_ack = check_appetite_acknowledgment(
            {"appetite": {"wall_clock_hours": 4}},
            {"spend": {"wall_clock_hours": 11},
             "appetite_exceeded": "line1\nline2\x1b[31mRED\x07 tail"},
        )
        check("appetite: the acknowledgment reason never carries a newline to stderr",
              ap_hostile_ack[0] == []
              and len(ap_hostile_ack[1]) == 1
              and "\n" not in ap_hostile_ack[1][0])
        check("appetite: the acknowledgment reason never carries a control byte",
              all(ch.isprintable() or ch == " " for ch in ap_hostile_ack[1][0]))

        # Emptiness is judged AFTER sanitising: a "reason" made only of control
        # bytes is no reason at all and must NOT buy a silent pass. Judging it
        # before would let three invisible bytes acknowledge any overrun.
        ap_ctrl_only_ack = check_appetite_acknowledgment(
            {"appetite": {"wall_clock_hours": 4}},
            {"spend": {"wall_clock_hours": 11}, "appetite_exceeded": "\x1b\x07"},
        )
        check("appetite: a control-bytes-only reason is NOT an acknowledgment",
              len(ap_ctrl_only_ack[0]) == 1 and ap_ctrl_only_ack[1] == [])

        # Legitimate non-ASCII prose must SURVIVE the sanitiser — the drop is
        # of non-printables, not of anything that is merely not ASCII.
        ap_unicode_ack = check_appetite_acknowledgment(
            {"appetite": {"tokens": 10}},
            {"spend": {"tokens": 99}, "appetite_exceeded": "caf\u00e9 na\u00efve overrun"},
        )
        check("appetite: non-ASCII acknowledgment prose survives sanitising",
              ap_unicode_ack[0] == []
              and "caf\u00e9 na\u00efve overrun" in ap_unicode_ack[1][0])

        # An unbounded reason must not emit an unbounded stderr line.
        ap_long_ack = check_appetite_acknowledgment(
            {"appetite": {"tokens": 10}},
            {"spend": {"tokens": 99}, "appetite_exceeded": "x" * 400},
        )
        check("appetite: an over-long acknowledgment reason is capped",
              ap_long_ack[0] == []
              and '..."' in ap_long_ack[1][0]
              and len(ap_long_ack[1][0]) < 400)

        # PARTIAL COVERAGE — flagged by the implementer as unpinned by any
        # specified case, and true: with three independent dimensions a pack
        # can breach one and leave another unmeasured in the SAME call. The
        # spec's prose ("never to a violation") decides it: the two facts are
        # independent and BOTH must be reported.
        ap_partial = check_appetite_acknowledgment(
            {"appetite": {"wall_clock_hours": 4, "tokens": 100}},
            {"spend": {"wall_clock_hours": 11}},
        )
        check("appetite: a breached dimension and an unmeasured one coexist",
              len(ap_partial[0]) == 1
              and "wall_clock_hours" in ap_partial[0][0]
              and "tokens" not in ap_partial[0][0]
              and len(ap_partial[1]) == 1
              and "tokens" in ap_partial[1][0]
              and "not verified this run" in ap_partial[1][0])

        # NaN/inf/negative — THIS CHECK WAS WRONG WHEN FIRST WRITTEN. It pinned
        # `([], [])`, i.e. total SILENCE, as correct on the reasoning that
        # fail-open is safe for the lane's only convicting rule. Half right:
        # fail-open on the VIOLATION is safe, fail-open on the NOTICE is a
        # BYPASS — `type(nan) is float` admitted NaN as a MEASUREMENT, so a
        # pack could report any overrun as `.nan` and the rule said nothing.
        # Caught by blind cross-family review (Kimi K3, F4) AFTER the author
        # had already examined this exact input and pinned the wrong half —
        # which is the argument for generator != grader in one line.
        ap_unusable_spend = [
            check_appetite_acknowledgment(
                {"appetite": {"tokens": 1000}}, {"spend": {"tokens": bad}})
            for bad in (float("nan"), float("inf"), float("-inf"), -5)
        ]
        check("appetite: an unusable spend is UNMEASURED (notice), never silent",
              all(v == [] and len(n) == 1 and "not verified this run" in n[0]
                  for v, n in ap_unusable_spend))
        # A nonsense CEILING declares nothing — `0 > -1` convicted an honest
        # pack before this (Kimi K3, F3).
        ap_nonsense_ceiling = [
            check_appetite_acknowledgment(
                {"appetite": {"adversarial_rounds": bad}},
                {"spend": {"adversarial_rounds": 0}})
            for bad in (-1, float("nan"), float("inf"))
        ]
        check("appetite: a negative/non-finite ceiling is not a ceiling",
              all(r == ([], []) for r in ap_nonsense_ceiling))
        # The over-correction twin (W94): the bound is `>= 0`, never `> 0`.
        check("appetite: zero is a real value on BOTH sides",
              check_appetite_acknowledgment(
                  {"appetite": {"wall_clock_hours": 0}},
                  {"spend": {"wall_clock_hours": 0}}) == ([], [])
              and len(check_appetite_acknowledgment(
                  {"appetite": {"wall_clock_hours": 0}},
                  {"spend": {"wall_clock_hours": 1}})[0]) == 1)
        # A present-but-non-str acknowledgment still CONVICTS, but the message
        # must stop claiming none was written (Kimi K3, F1 — `yes` is a YAML bool).
        ap_bool_ack = check_appetite_acknowledgment(
            {"appetite": {"tokens": 1000}},
            {"spend": {"tokens": 1500}, "appetite_exceeded": True})
        check("appetite: a non-str acknowledgment convicts, and the message says why",
              len(ap_bool_ack[0]) == 1
              and "bool" in ap_bool_ack[0][0]
              and "not a reason" in ap_bool_ack[0][0])
        ap_absent_ack = check_appetite_acknowledgment(
            {"appetite": {"tokens": 1000}}, {"spend": {"tokens": 1500}})
        check("appetite: a genuinely absent acknowledgment keeps the original message",
              len(ap_absent_ack[0]) == 1
              and "no `appetite_exceeded:` acknowledgment" in ap_absent_ack[0][0]
              and "not a reason" not in ap_absent_ack[0][0])

        # ---- blind-scan guard: pack file missing -------------------------------
        rc, viol = lint(root / "evidence" / "nope.yml", root, None)
        check("blind-scan guard: missing pack -> exit 2", rc == 2)

        # ---- blind-scan guard: pack is not a mapping ---------------------------
        (root / "evidence" / "scalar.yml").write_text("just a string\n", encoding="utf-8")
        rc, viol = lint(root / "evidence" / "scalar.yml", root, None)
        check("blind-scan guard: non-mapping pack -> exit 2", rc == 2)

    print("SELFTEST", "PASS" if not failures else f"FAIL ({failures})")
    return 0 if not failures else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("pack_path", nargs="?", default="evidence/pack.yml")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--changed-files-file", default=None)
    parser.add_argument("--net-lines", type=int, default=None, metavar="INT")
    parser.add_argument("--numstat-file", default=None, metavar="PATH")
    parser.add_argument("--patch-file", default=None, metavar="PATH")
    parser.add_argument("--source-path", default=None, metavar="PATH")
    # Rule 12's input: THIS PR's own real brief path, as resolved from its
    # changed-files list (`scripts/ci/evidence_paths.py --resolve brief`).
    # Deliberately has NO positional fallback, unlike --source-path above: a
    # local invocation is given the pack's path and genuinely does not know
    # where the brief was written, so defaulting it would be a guess dressed
    # as a measurement. Omitted => Rule 12 skips, silently and by design.
    parser.add_argument("--brief-source-path", default=None, metavar="PATH")
    # Countable-claims rule: the PR's commit count. Optional — in CI it is read from the
    # pull_request event payload automatically (see measured_commit_count()),
    # so no workflow change is needed; this flag is for local runs and tests.
    parser.add_argument("--commit-count", type=int, default=None, metavar="INT")
    parser.add_argument("--print-measured", action="store_true")
    parser.add_argument("--print-floor", action="store_true")
    parser.add_argument("--print-floor-source", action="store_true")
    parser.add_argument("--effort-for", type=int, default=None, metavar="GEAR")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    if args.effort_for is not None:
        try:
            print(effort_for_gear(args.effort_for))
        except ValueError as exc:
            print(f"evidence_pack_lint: {exc}", file=sys.stderr)
            return 3
        return 0

    repo_root = Path(args.repo_root).resolve() if args.repo_root else repo_root_default()

    if args.print_floor:
        if not args.changed_files_file:
            print("evidence_pack_lint: --print-floor requires --changed-files-file",
                  file=sys.stderr)
            return 3
        changed = _read_changed_files(args.changed_files_file) or []
        numstat_text_for_floor: str | None = None
        if args.numstat_file:
            try:
                numstat_text_for_floor = Path(args.numstat_file).read_text(encoding="utf-8")
            except OSError as exc:
                print(f"evidence_pack_lint: --numstat-file unreadable: {exc}", file=sys.stderr)
                return 3
        patch_text_for_floor = _read_patch_file(args.patch_file)
        print(compute_floor(changed, numstat_text_for_floor, patch_text_for_floor))
        return 0

    if args.print_floor_source:
        if not args.changed_files_file:
            print("evidence_pack_lint: --print-floor-source requires --changed-files-file",
                  file=sys.stderr)
            return 3
        changed = _read_changed_files(args.changed_files_file) or []
        numstat_text_for_source: str | None = None
        if args.numstat_file:
            try:
                numstat_text_for_source = Path(args.numstat_file).read_text(encoding="utf-8")
            except OSError as exc:
                print(f"evidence_pack_lint: --numstat-file unreadable: {exc}", file=sys.stderr)
                return 3
        patch_text_for_source = _read_patch_file(args.patch_file)
        print(compute_floor_source(changed, numstat_text_for_source, patch_text_for_source))
        return 0

    changed_files = _read_changed_files(args.changed_files_file)
    pack_path = Path(args.pack_path)
    if not pack_path.is_absolute():
        pack_path = repo_root / pack_path

    # --numstat-file is read ONCE, unconditionally, because it now feeds two
    # independent computations (see lint()'s own docstring): the CEILING's
    # measured net-lines, where --net-lines wins outright and this is only a
    # convenience so callers don't need to re-derive the awk one-liner
    # themselves; and the FLOOR's size term (S1), which always consults the
    # raw numstat text directly when given, regardless of --net-lines — it
    # needs the per-file rows, not a single pre-summed integer, so
    # --net-lines does not substitute for it there. Neither flag given ->
    # None both places, and compute_ceiling()/compute_floor() each fall back
    # to their own pre-S1 behavior (pack-declared net_lines with a NOTICE,
    # and path-only, respectively).
    numstat_text: str | None = None
    if args.numstat_file:
        try:
            numstat_text = Path(args.numstat_file).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"evidence_pack_lint: --numstat-file unreadable: {exc}", file=sys.stderr)
            return 3

    measured_commits = measured_commit_count(args.commit_count)

    if args.print_measured:
        print(format_measured_claims(numstat_text, measured_commits))
        return 0

    measured_net_lines: int | None = args.net_lines
    if measured_net_lines is None and numstat_text is not None:
        measured_net_lines = sum_numstat(numstat_text)

    # Rule 9 default: a direct/local invocation with no --source-path names
    # the path it was pointed at as the real one (args.pack_path — the
    # RAW CLI argument, not the possibly-repo-root-joined `pack_path`
    # above, since both are equally valid repo-relative forms and joining
    # first would just make an already-relative default absolute for no
    # reason). A caller staging the pack under a different name (CI) must
    # pass --source-path explicitly — see that flag's help text.
    source_path = args.source_path if args.source_path is not None else args.pack_path

    exit_code, violations = lint(
        pack_path, repo_root, changed_files, measured_net_lines, numstat_text,
        source_path, measured_commits, args.brief_source_path,
    )

    if args.json:
        import json as _json
        print(_json.dumps({"exit": exit_code, "violations": violations}, indent=2))
    else:
        if violations:
            label = "BLIND" if exit_code == 2 else "FAIL"
            print(f"evidence_pack_lint: {label} — {len(violations)} violation(s):", file=sys.stderr)
            for v in violations:
                print(f"  - {v}", file=sys.stderr)
        else:
            print(f"evidence_pack_lint: clean ({pack_path})")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
