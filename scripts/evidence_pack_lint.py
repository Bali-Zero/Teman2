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

  9. evidence root path deprecation (S12/C6 follow-through) — the fixed
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
  --print-floor    given --changed-files-file, print the computed floor int
                    and exit 0 (no pack read) — lets any caller (CI, a human)
                    ask "what floor would this diff impose" without spinning
                    up a second implementation of HOTZONE_PATTERNS. Also
                    honors --numstat-file when given (S1's size term) — omit
                    it for the path-only floor exactly as before that term
                    existed.
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
VALID_LANE_ROLES = ("build", "review", "read")

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
SIZE_TERM_EXCLUDE_SUFFIXES: tuple[str, ...] = (
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp",
    ".pdf", ".zip", ".gz", ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".mp4", ".mp3", ".wav", ".mov",
)


def _is_size_term_excluded(path: str) -> bool:
    """True when `path` should NOT count toward the size term (S1):
    generated/vendored output, well-known lockfiles, minified bundles, and
    binary/image assets. See the SIZE_TERM_EXCLUDE_* tuples above for what
    and why. Deliberately NOT a blanket `*.lock` suffix match (adversarial
    review, PR #5049): the mandate's "lockfiles" meant the well-known
    package-manager ones enumerated above, not every file a script happens
    to name `*.lock` — this repo's own coordination primitives use that
    suffix for real hand-written state (CLAUDE.md's `agent_lock:<resource>`
    Redis keys), and a blanket suffix match would have let a diff touching
    real lock-coordination code hide behind the same exemption."""
    p = PurePosixPath(path)
    if any(part in SIZE_TERM_EXCLUDE_DIR_NAMES for part in p.parts[:-1]):
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
    sum_numstat()."""
    net = 0
    for line in numstat.splitlines():
        line = line.strip()
        if not line:
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
    changed_files: list[str], numstat: str | None = None
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
    path_hit = False
    for f in changed_files:
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


def compute_floor(changed_files: list[str], numstat: str | None = None) -> int:
    """The deterministic floor (rule 6 docstring): the HIGHER of two
    independent terms.

    PATH TERM (original, unchanged): 3 on any hot-zone hit
    (HOTZONE_PATTERNS), else 1.

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
    return _compute_floor_with_source(changed_files, numstat)[0]


def compute_floor_source(changed_files: list[str], numstat: str | None = None) -> str:
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
    return _compute_floor_with_source(changed_files, numstat)[1]


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


#: R9 — review seats that count toward Gear-3 council quorum.
COUNCIL_REVIEW_SEATS: tuple[str, ...] = (
    "codex-gpt-5.6-sol",
    "kimi-code/k3",
    "tp1-qwen3.8-max",
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
    `council_run` entirely and will NOTICE (not FAIL) until 2026-09-02."""
    if gear != 3:
        return [], None
    seats = _read_council_journal_seats(pack_dir, pack.get("council_run"))
    has_quorum = len(seats) >= 2
    message = (
        "gear:3 pack declares no council_run journal with >=2 distinct "
        f"review seats from {COUNCIL_REVIEW_SEATS} marked ok:true"
    )
    return _r9_r11_verdict("council_run", not has_quorum, message, pack, today)


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


# ------------------------------------------------------------------- lint()


def lint(
    pack_path: Path,
    repo_root: Path,
    changed_files: list[str] | None,
    measured_net_lines: int | None = None,
    numstat_text: str | None = None,
    source_path: str | None = None,
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

    lane_violations, lane_notice = check_lanes_build_seat_diversity(pack, gear)
    violations += lane_violations
    if lane_notice:
        print(f"evidence_pack_lint: NOTICE — {lane_notice}", file=sys.stderr)

    root_violations, root_notice = check_pack_not_at_deprecated_root(source_path, repo_root)
    violations += root_violations
    if root_notice:
        print(f"evidence_pack_lint: NOTICE — {root_notice}", file=sys.stderr)

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
              "gear-floor check (rule 6) skipped for this run", file=sys.stderr)
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
    parser.add_argument("--source-path", default=None, metavar="PATH")
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
        print(compute_floor(changed, numstat_text_for_floor))
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
        print(compute_floor_source(changed, numstat_text_for_source))
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
        pack_path, repo_root, changed_files, measured_net_lines, numstat_text, source_path
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
