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
                        `receipts:` (harness-v2 §5 "Anti-Goodhart").
  2. dissent         — MANDATORY field (harness-v2 §5: "campo OBBLIGATORIO, non
                        opzionale"), must be a list. On a Gear-3 pack (declared
                        by the referenced brief) it must be non-empty: zero
                        dissent on Gear-3 is "consenso sospetto" — either no
                        refuter actually tried, or none were independent
                        (harness-v2 §5). Gear 1/2 may carry an empty list.
  3. pii_scan        — must equal the literal string "clean" (Law 2 / UU PDP).
  4. size            — approx tokens = len(raw bytes)/4 <= 30_000 (harness-v2
                        §5 hard cap — protects the Fable gate's weekly
                        allowance and forces compression of EVIDENCE, not more
                        narration).
  5. brief_ref       — must be present and resolve to a real file relative to
                        the repo root (the pack is not self-contained by
                        design; it references the Task Brief that assigned the
                        grader before any code was written).
  6. gear >= floor   — the brief's declared `gear` must be >= the DETERMINISTIC
                        floor computed from the PR's changed-file set against
                        the hot-zone list (fleet-order-spec.md §4 "Floor note":
                        "gear classification is the DETERMINISTIC FLOOR
                        computed from the diff ... never the conductor's
                        choice"). The floor is a LOWER BOUND only: this repo's
                        deterministic signal distinguishes "touches a hot-zone
                        path" (floor 3) from "everything else" (floor 1) —
                        the middle "Gear 2 minimo, feature PR standard" bucket
                        needs human/semantic judgment no diff can carry, so a
                        non-hotzone PR floors at 1, never asserts 2. The model
                        may always raise gear above the floor; CI here only
                        catches a DOWNGRADE below it (harness-v2 §1 monotonia).
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

Floor check is SKIPPED (not silently passed — an explicit NOTICE on stderr)
when --changed-files-file is not supplied: not every invocation of this linter
has PR-diff context (e.g. a spot-check of a pack on a laptop). The CI workflow
(harness-floor.yml) is the required check that always supplies it.

VERDICT / EXIT CODES (fail-visible, superscar #2 "esiste != armato" antidote:
a lint that scanned nothing must not report clean):
  0  pack is conformant (floor check honored whenever changed-files is known)
  1  pack has 1+ REJECTED violations (guilt)
  2  BLIND — pack file missing/unreadable/not-a-mapping, refuses to report
     "clean" about a pack it never actually read
  3  usage error (bad CLI arguments)

CLI:
  python3 scripts/evidence_pack_lint.py [PACK_PATH] [--repo-root DIR]
      [--changed-files-file PATH] [--print-floor] [--json] [--selftest]

  PACK_PATH        defaults to evidence/pack.yml (relative to --repo-root)
  --repo-root      defaults to the git top-level, else cwd
  --changed-files-file  newline-delimited changed-path list (the output of
                        scripts/ci/hotzone_changed_files.sh) — enables rule 6
  --print-floor    given --changed-files-file, print the computed floor int
                    and exit 0 (no pack read) — lets any caller (CI, a human)
                    ask "what floor would this diff impose" without spinning
                    up a second implementation of HOTZONE_PATTERNS
  --json           machine-readable {"exit": N, "violations": [...]} on stdout
  --selftest       run the embedded guilt+innocence corpus and exit 0/1

Registered in infra/guard-conformance/registry.json (surface
"evidence_pack_lint", census method ast-def-prefix "check_") — every
`check_*` function below is a censused guard and needs both proofs there.
"""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path
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


def compute_floor(changed_files: list[str]) -> int:
    """The deterministic floor (rule 6 docstring): 3 on any hot-zone hit, else
    1. Pure function — no I/O, no git — so guilt+innocence tests exercise it
    directly without a filesystem fixture."""
    for f in changed_files:
        for pat in HOTZONE_PATTERNS:
            if fnmatch.fnmatchcase(f, pat):
                return 3
    return 1


def approx_tokens(raw: bytes) -> int:
    return len(raw) // 4


# --------------------------------------------------------------- check_* guards
# Each is censused by infra/guard-conformance/registry.json via ast-def-prefix
# "check_" — every one needs a guilt AND an innocence test in
# scripts/tests/test_evidence_pack_lint.py (superscar #3).


def check_receipts_have_provenance(pack: dict[str, Any]) -> list[str]:
    """GUILT: a receipts[] entry missing cmd/exit/ts/seat is an OPINION wearing
    a receipt's shape — rejected. INNOCENCE: a fully-shaped receipt passes,
    and a pack with NO receipts key at all is not this rule's problem (an
    empty evidence pack may legitimately have no claims yet — other rules
    still gate it)."""
    violations: list[str] = []
    receipts = pack.get("receipts")
    if receipts is None:
        return violations
    if not isinstance(receipts, list):
        return [f"receipts: must be a list, got {type(receipts).__name__}"]
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


def check_dissent_nonempty_on_gear3(pack: dict[str, Any], gear: int | None) -> list[str]:
    """GUILT: the `dissent` key absent entirely (mandatory field, any gear);
    GUILT: `dissent: []` on a Gear-3 pack ("consenso sospetto"). INNOCENCE: an
    empty dissent list on Gear 1/2 is fine (brief's own stated edge case) —
    the field only has to be NON-EMPTY once the task is Gear-3."""
    if "dissent" not in pack:
        return ["dissent: field is missing — mandatory on every Evidence Pack (harness-v2 §5)"]
    dissent = pack["dissent"]
    if not isinstance(dissent, list):
        return [f"dissent: must be a list, got {type(dissent).__name__}"]
    if gear == 3 and len(dissent) == 0:
        return ["dissent: consenso sospetto — zero dissent entries on a Gear-3 pack "
                "(either no refuter tried, or none were independent)"]
    return []


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
    """GUILT: brief_ref missing from the pack, or pointing at a file absent on
    disk. INNOCENCE: brief_ref present and resolvable loads and returns the
    referenced brief (a dict) for downstream rules (gear floor, dissent gear
    gate) to consume."""
    brief_ref = pack.get("brief_ref")
    if not brief_ref or not isinstance(brief_ref, str):
        return (["brief_ref: missing or not a string"], None)
    brief_path = repo_root / brief_ref
    if not brief_path.exists():
        return ([f"brief_ref: '{brief_ref}' does not resolve to a file on disk"], None)
    try:
        brief = yaml.safe_load(brief_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return ([f"brief_ref: '{brief_ref}' is not valid YAML: {exc}"], None)
    if not isinstance(brief, dict):
        return ([f"brief_ref: '{brief_ref}' did not parse to a mapping"], None)
    return ([], brief)


def check_gear_floor(brief: dict[str, Any] | None, changed_files: list[str] | None) -> list[str]:
    """GUILT: the brief's declared gear is below the deterministic floor
    computed from the PR's changed files. INNOCENCE: gear >= floor passes;
    gear ABOVE the floor always passes too (the model may only raise, never
    lower, the floor — harness-v2 §1 monotonia). When changed_files is None
    the check is explicitly SKIPPED (see module docstring) rather than
    silently treated as passing without evidence — the caller prints the
    NOTICE, this function just declines to add a violation."""
    if brief is None:
        return []  # already flagged by check_brief_ref_exists
    gear = brief.get("gear")
    if gear not in VALID_GEARS:
        return [f"brief.gear: must be one of {VALID_GEARS}, got {gear!r}"]
    if changed_files is None:
        return []
    floor = compute_floor(changed_files)
    if gear < floor:
        return [f"brief.gear: declared {gear} is BELOW the deterministic floor {floor} "
                f"computed from the changed-file set (hot-zone hit)"]
    return []


# ------------------------------------------------------------------- lint()


def lint(
    pack_path: Path,
    repo_root: Path,
    changed_files: list[str] | None,
) -> tuple[int, list[str]]:
    """Returns (exit_code, violations). exit_code: 0 clean, 1 guilty, 2 blind."""
    if not pack_path.exists():
        return 2, [f"BLIND: evidence pack not found at {pack_path}"]
    try:
        raw = pack_path.read_bytes()
    except OSError as exc:
        return 2, [f"BLIND: could not read evidence pack: {exc}"]
    try:
        pack = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        return 2, [f"BLIND: evidence pack is not valid YAML: {exc}"]
    if not isinstance(pack, dict):
        return 2, ["BLIND: evidence pack YAML did not parse to a mapping"]

    violations: list[str] = []
    violations += check_receipts_have_provenance(pack)
    violations += check_pii_scan_clean(pack)
    violations += check_size_budget(raw)

    brief_violations, brief = check_brief_ref_exists(pack, repo_root)
    violations += brief_violations

    gear = brief.get("gear") if isinstance(brief, dict) else None
    violations += check_dissent_nonempty_on_gear3(pack, gear if isinstance(gear, int) else None)
    violations += check_gear_floor(brief, changed_files)

    if changed_files is None:
        print("evidence_pack_lint: NOTICE — no --changed-files-file supplied, "
              "gear-floor check (rule 6) skipped for this run", file=sys.stderr)

    return (1 if violations else 0), violations


# --------------------------------------------------------------------- CLI


def _read_changed_files(path_str: str | None) -> list[str] | None:
    if not path_str:
        return None
    p = Path(path_str)
    text = p.read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip()]


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

        # ---- innocence: a fully-conformant Gear-1 pack passes --------------
        write(root / "evidence" / "brief.yml", {
            "task_id": "ops-selftest", "gear": 1, "l_level": "L1",
            "gate_class": "none", "objective": "prove the linter",
            "grader": "codex-sol", "pii": "none",
        })
        write(root / "evidence" / "pack.yml", {
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
            "brief_ref": "evidence/brief.yml",
            "receipts": [good_receipt],
            "dissent": [{"seat": "codex-sol", "objection": "x", "status": "PLAUSIBLE"}],
            "pii_scan": "clean",
        })
        rc, viol = lint(root / "evidence" / "pack.yml", root, None)
        check("innocence: non-empty dissent on gear-3 passes", rc == 0 and viol == [])

        # ---- guilt: dissent field missing entirely --------------------------
        write(root / "evidence" / "pack.yml", {
            "brief_ref": "evidence/brief.yml",
            "receipts": [good_receipt],
            "pii_scan": "clean",
        })
        rc, viol = lint(root / "evidence" / "pack.yml", root, None)
        check("guilt: missing dissent field rejected", rc == 1)

        # ---- guilt: receipt missing a required field ------------------------
        write(root / "evidence" / "brief.yml", {"task_id": "x", "gear": 1, "grader": "y"})
        write(root / "evidence" / "pack.yml", {
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
            "brief_ref": "evidence/brief.yml",
            "receipts": [good_receipt],
            "dissent": [],
            "pii_scan": "dirty",
        })
        rc, viol = lint(root / "evidence" / "pack.yml", root, None)
        check("guilt: pii_scan != clean rejected", rc == 1)

        # ---- guilt: oversize pack ---------------------------------------------
        write(root / "evidence" / "pack.yml", {
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
            "receipts": [good_receipt], "dissent": [], "pii_scan": "clean",
        })
        rc, viol = lint(root / "evidence" / "pack.yml", root, None)
        check("guilt: brief_ref key missing rejected", rc == 1)

        # ---- guilt: brief_ref points nowhere -----------------------------------
        write(root / "evidence" / "pack.yml", {
            "brief_ref": "evidence/does-not-exist.yml",
            "receipts": [good_receipt], "dissent": [], "pii_scan": "clean",
        })
        rc, viol = lint(root / "evidence" / "pack.yml", root, None)
        check("guilt: brief_ref dangling path rejected", rc == 1)

        # ---- guilt: gear below deterministic floor -----------------------------
        write(root / "evidence" / "brief.yml", {"task_id": "x", "gear": 1, "grader": "y"})
        write(root / "evidence" / "pack.yml", {
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
            "brief_ref": "evidence/brief.yml",
            "receipts": [good_receipt], "dissent": [], "pii_scan": "clean",
        })
        rc, viol = lint(root / "evidence" / "pack.yml", root, ["docs/readme.md"])
        check("innocence: gear 1 on non-hotzone diff passes", rc == 0 and viol == [])

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
    parser.add_argument("--print-floor", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else repo_root_default()

    if args.print_floor:
        if not args.changed_files_file:
            print("evidence_pack_lint: --print-floor requires --changed-files-file",
                  file=sys.stderr)
            return 3
        changed = _read_changed_files(args.changed_files_file) or []
        print(compute_floor(changed))
        return 0

    changed_files = _read_changed_files(args.changed_files_file)
    pack_path = Path(args.pack_path)
    if not pack_path.is_absolute():
        pack_path = repo_root / pack_path

    exit_code, violations = lint(pack_path, repo_root, changed_files)

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
