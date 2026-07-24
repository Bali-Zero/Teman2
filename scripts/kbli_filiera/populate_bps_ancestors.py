"""Batch-B migration step (2) — bulk-populate `bps_2020_ancestors` (mechanical-only).

Writes the additive canonical field `bps_2020_ancestors` (design §2.2) onto the
**1,338 Batch-B codes** — the OSS-native population, identified by `_l2_status is
None`. Batch A's 221 no-scope codes (`_l2_status == "no_oss_risk"`) are explicitly
OUT of scope for this field and are never touched (design §2.2, §2.4).

The edge set for each code is copied VERBATIM from the Phase-0 crosswalk relation
artifact (`data/kbli-filiera/phase0/bps_crosswalk.json`), which the acceptance gate
(§1.4) certified. This compiler REFUSES to run unless the gate report says the parse
PASSED and its `parser_run_digest` matches the relation artifact's
`output_relation_digest` — a code never gets mechanical ancestry from an uncertified
or moved parse (W88/W90: act on a verdict only while its data-source is still the one
that was judged). Nothing about the edges is invented here — a genuinely new-in-2025
code (empty ancestry) is a hard error, not a silent empty write, because every Batch-B
code was verified to carry non-empty ancestry when this tool was written (rule #9).

Every written entry is `adjudication_status: mechanical-only` /
`inheritance_verdict: not-adjudicated`: mechanical edge presence NEVER implies the
licensing regime transfers — that is the separate D1/D5 semantic judgment the per-code
cure-spec compilers apply later (design §2.2, §4). This tool is idempotent: a record
that already carries `bps_2020_ancestors` is left untouched (so a later per-code
adjudication is never clobbered by a re-run); a pre-existing entry whose
`parser_run_digest` differs from the current relation is reported LOUD, never
silently overwritten.

Writer discipline (#2550): this compiler lives under `scripts/kbli_filiera/` and is an
authorized writer of `data/source_documents/KBLI_2025_FINAL_CLEAN.json`. On `--apply`
it mutates the canonical (atomic tmp+replace), then runs `sync_kbli_dataset.sh sync`
to propagate to the consumer copies and bumps the mouth sidecar sha256 — the exact
flow `cure_canonical_collisions.py` uses.

    python scripts/kbli_filiera/populate_bps_ancestors.py            # dry-run (default)
    python scripts/kbli_filiera/populate_bps_ancestors.py --apply    # mutate + sync + sidecar
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kbli_filiera import bps_crosswalk_parser as parser  # noqa: E402
from kbli_filiera import vault_common as common  # noqa: E402

logger = common.setup_logger("populate_bps_ancestors")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
DEFAULT_RELATION = REPO_ROOT / "data" / "kbli-filiera" / "phase0" / "bps_crosswalk.json"
DEFAULT_GATE_REPORT = REPO_ROOT / "data" / "kbli-filiera" / "phase0" / "gate_report.json"
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_kbli_dataset.sh"
SIDECAR_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-dataset-version.json"
SIDECAR_DATASET_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "KBLI_2025_FINAL_CLEAN.json"

CODE_FIELD = "kode_kbli_2025"
FIELD = "bps_2020_ancestors"

# Batch membership markers (design §2.4). Batch B is the OSS-native population that
# gets this field; Batch A is out of scope for it.
BATCH_B_MARKER = None            # _l2_status is None
BATCH_A_MARKER = "no_oss_risk"   # _l2_status == "no_oss_risk"
EXPECTED_BATCH_B = 1338          # design-pinned; --expect-batch-b overrides on a real catalog change

# Every bulk-written entry is mechanical-only / not-adjudicated (design §2.2).
ADJUDICATION_STATUS = "mechanical-only"
INHERITANCE_VERDICT = "not-adjudicated"
ADJUDICATED_BY = "mechanical-only"


class PopulateError(RuntimeError):
    """A precondition/artifact mismatch severe enough to make the run's exit non-zero."""


def _detect_indent(raw_text: str) -> int:
    """Measure the JSON indent width from the file's own formatting rather than
    assuming 2 — measure, don't presume (cure_canonical_collisions.py:158)."""
    for line in raw_text.splitlines()[1:8]:
        stripped = line.lstrip(" ")
        leading = len(line) - len(stripped)
        if leading > 0:
            return leading
    return 2


def load_relation_artifact(path: Path) -> tuple[dict[str, dict[str, Any]], str]:
    """Return (relation, output_relation_digest) after validating the artifact shape.

    Fail-loud on any structural surprise: the relation must be a non-empty dict whose
    every value carries exactly {codes, sebagian, source_locator}, with codes/sebagian
    equal-length lists (a per-edge boolean each). This is the only edge source; a
    malformed one must halt, never populate garbage."""
    if not path.exists():
        raise PopulateError(f"relation artifact not found: {path}")
    art = json.loads(path.read_text(encoding="utf-8"))
    relation = art.get("relation")
    digest = (art.get("manifest") or {}).get("output_relation_digest")
    if not isinstance(relation, dict) or not relation:
        raise PopulateError(f"{path}: 'relation' missing or empty")
    if not isinstance(digest, str) or len(digest) != 64:
        raise PopulateError(f"{path}: manifest.output_relation_digest missing or not a sha256")
    for code, rec in relation.items():
        if set(rec.keys()) != {"codes", "sebagian", "source_locator"}:
            raise PopulateError(f"{path}: relation[{code!r}] has unexpected keys {sorted(rec.keys())}")
        codes, sebagian, sl = rec["codes"], rec["sebagian"], rec["source_locator"]
        if not isinstance(codes, list) or not isinstance(sebagian, list) or not isinstance(sl, list):
            raise PopulateError(f"{path}: relation[{code!r}] codes/sebagian/source_locator must be lists")
        if len(codes) != len(sebagian):
            raise PopulateError(
                f"{path}: relation[{code!r}] len(codes)={len(codes)} != len(sebagian)={len(sebagian)}"
            )
        for loc in sl:
            if not isinstance(loc, dict):
                raise PopulateError(
                    f"{path}: relation[{code!r}] source_locator entry is not an object: {loc!r}"
                )
    # Content-bind the digest: recompute it from the relation itself with the parser's
    # OWN canonicalization (single source of truth, no duplicated algorithm) and refuse
    # if the stored value lies. A hand-edit to the edges that left output_relation_digest
    # stale is caught HERE, so the gate binding downstream is over verified content, not a
    # self-declared field (W88 — verify by CONTENT, never trust a proxy).
    recomputed = parser._relation_digest({"relation": relation})
    if recomputed != digest:
        raise PopulateError(
            f"{path}: manifest.output_relation_digest ({digest[:16]}…) does not match the digest "
            f"recomputed from the relation content ({recomputed[:16]}…) — the artifact was edited "
            f"without re-stamping its digest; regenerate it with the parser before populating"
        )
    return relation, digest


def assert_gate_certifies(gate_report_path: Path, relation_digest: str) -> None:
    """Refuse to populate unless the acceptance gate PASSED on THIS exact relation.

    Binds the write to the certified parse by CONTENT (the digest), not by trust that
    the artifact on disk is the one the gate judged (W88/W90). No override flag — a
    bypass would defeat the whole point of the gate."""
    if not gate_report_path.exists():
        raise PopulateError(f"gate report not found: {gate_report_path}")
    gate = json.loads(gate_report_path.read_text(encoding="utf-8"))
    verdict = gate.get("verdict")
    gate_digest = gate.get("parser_run_digest")
    if verdict != "PASS":
        raise PopulateError(
            f"acceptance gate verdict is {verdict!r}, not 'PASS' — refusing to populate "
            f"(re-run bps_phase0_gate.py until the parse clears §1.4)"
        )
    if gate_digest != relation_digest:
        raise PopulateError(
            f"gate.parser_run_digest ({str(gate_digest)[:16]}…) != relation "
            f"output_relation_digest ({relation_digest[:16]}…) — the certified parse and the "
            f"relation on disk have diverged; re-run the gate on the current relation before populating"
        )


def build_field(anc: dict[str, Any], digest: str, as_of: str) -> dict[str, Any]:
    """Assemble one `bps_2020_ancestors` value (design §2.2) from a relation entry.

    Edges (codes/sebagian/source_locator) are copied verbatim; the four adjudication
    fields are the frozen mechanical-only constants. `inheritance_verdict` is never
    inferred from the edges — a mechanical edge set does not imply regime transfer."""
    return {
        "codes": list(anc["codes"]),
        "sebagian": list(anc["sebagian"]),
        "source_locator": copy.deepcopy(anc["source_locator"]),
        "parser_run_digest": digest,
        "adjudication_status": ADJUDICATION_STATUS,
        "inheritance_verdict": INHERITANCE_VERDICT,
        "adjudicated_by": ADJUDICATED_BY,
        "adjudicated_at": as_of,
    }


def run_sync_script() -> None:
    logger.info("running %s sync", SYNC_SCRIPT)
    result = subprocess.run(
        ["bash", str(SYNC_SCRIPT), "sync"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode != 0:
        raise PopulateError(f"sync_kbli_dataset.sh sync failed with exit {result.returncode}")


def update_sidecar() -> None:
    if not SIDECAR_DATASET_PATH.exists():
        raise PopulateError(f"sidecar dataset copy missing: {SIDECAR_DATASET_PATH} (sync must run first)")
    digest = hashlib.sha256(SIDECAR_DATASET_PATH.read_bytes()).hexdigest()
    sidecar = json.loads(SIDECAR_PATH.read_text(encoding="utf-8"))
    before = dict(sidecar)
    # Idempotent: if the sidecar already pins this exact dataset, do not rewrite it — a
    # spurious lastModified bump would be a phantom diff, and calling this unconditionally
    # on every --apply (the recovery-safe reconcile below) must be a true no-op when
    # nothing changed.
    if before.get("datasetSha256") == f"sha256:{digest}":
        logger.info("sidecar already current (%s) — no write", before.get("datasetSha256"))
        return
    sidecar["datasetSha256"] = f"sha256:{digest}"
    sidecar["lastModified"] = date.today().isoformat()
    SIDECAR_PATH.write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    logger.info("sidecar updated: %s -> %s", before.get("datasetSha256"), sidecar["datasetSha256"])
    logger.info("sidecar lastModified: %s -> %s", before.get("lastModified"), sidecar["lastModified"])


def plan_and_apply(
    records: list[dict[str, Any]],
    relation: dict[str, dict[str, Any]],
    digest: str,
    as_of: str,
    *,
    expected_batch_b: int,
    do_apply: bool,
) -> tuple[int, list[str]]:
    """Populate FIELD on every Batch-B record lacking it. Returns (n_populated, problems).

    When do_apply is False the record dicts are not mutated (pure classification) —
    the caller writes nothing. When True, records are mutated in place (the field is
    appended to each, a clean additive diff) and the caller persists them."""
    batch_b = [r for r in records if r.get("_l2_status") is BATCH_B_MARKER]
    batch_a = [r for r in records if r.get("_l2_status") == BATCH_A_MARKER]
    problems: list[str] = []

    # Completeness (W97): every record must classify as Batch-B or Batch-A. A record
    # carrying some other _l2_status is skipped by both branches — that "which batch does
    # this get?" ambiguity must halt a bulk write, not be sailed past silently.
    unclassified = [
        r for r in records
        if r.get("_l2_status") is not BATCH_B_MARKER and r.get("_l2_status") != BATCH_A_MARKER
    ]
    if unclassified:
        seen = sorted({str(r.get("_l2_status")) for r in unclassified})
        problems.append(
            f"{len(unclassified)} record(s) have an unrecognized _l2_status (neither Batch-B "
            f"None nor Batch-A {BATCH_A_MARKER!r}): {seen[:10]}"
        )

    # W97: the population size is a CLAIM, not a silent cap. A drift from the pinned
    # 1,338 must be acknowledged via --expect-batch-b, never sailed past.
    if len(batch_b) != expected_batch_b:
        problems.append(
            f"Batch-B population is {len(batch_b)}, expected {expected_batch_b} "
            f"(catalog changed? re-run with --expect-batch-b {len(batch_b)} to acknowledge)"
        )

    to_populate: list[dict[str, Any]] = []
    already_same = 0
    already_diff: list[str] = []
    for rec in batch_b:
        code = rec.get(CODE_FIELD)
        existing = rec.get(FIELD)
        if isinstance(existing, dict):
            # Idempotent: never clobber. A stale digest is a loud report, not an overwrite.
            if existing.get("parser_run_digest") == digest:
                already_same += 1
            else:
                already_diff.append(str(code))
            continue
        anc = relation.get(code)
        if anc is None:
            problems.append(f"Batch-B code {code!r} absent from certified relation — cannot populate")
            continue
        if not anc["codes"]:
            problems.append(
                f"Batch-B code {code!r} has EMPTY ancestry in the relation — a new-in-2025 code "
                f"needs an explicit decision, not a silent empty write (rule #9)"
            )
            continue
        to_populate.append(rec)

    if already_diff:
        problems.append(
            f"{len(already_diff)} Batch-B code(s) already carry {FIELD} with a DIFFERENT "
            f"parser_run_digest (not overwritten): {sorted(already_diff)[:10]}"
            + ("…" if len(already_diff) > 10 else "")
        )

    # Post-condition (W97 anti-scope-creep): Batch-A must NEVER carry the field.
    contaminated_a = [str(r.get(CODE_FIELD)) for r in batch_a if FIELD in r]
    if contaminated_a:
        problems.append(
            f"{len(contaminated_a)} Batch-A (no-scope) code(s) carry {FIELD} — out-of-scope "
            f"contamination: {sorted(contaminated_a)[:10]}"
        )

    logger.info(
        "Batch-B=%d Batch-A=%d | to-populate=%d already(same-digest)=%d already(diff-digest)=%d",
        len(batch_b), len(batch_a), len(to_populate), already_same, len(already_diff),
    )

    if do_apply:
        for rec in to_populate:
            rec[FIELD] = build_field(relation[rec[CODE_FIELD]], digest, as_of)

    return len(to_populate), problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL, help="canonical dataset to mutate")
    ap.add_argument("--relation", type=Path, default=DEFAULT_RELATION, help="Phase-0 crosswalk relation artifact")
    ap.add_argument("--gate-report", type=Path, default=DEFAULT_GATE_REPORT, help="Phase-0 acceptance gate report")
    ap.add_argument("--as-of", default=date.today().isoformat(), help="adjudicated_at date (default: today)")
    ap.add_argument("--expect-batch-b", type=int, default=EXPECTED_BATCH_B,
                    help=f"expected Batch-B population (default: {EXPECTED_BATCH_B})")
    ap.add_argument("--apply", action="store_true", help="mutate the canonical (default: dry-run, writes nothing)")
    args = ap.parse_args(argv)

    relation, digest = load_relation_artifact(args.relation)
    assert_gate_certifies(args.gate_report, digest)

    if not args.canonical.exists():
        raise PopulateError(f"canonical dataset not found: {args.canonical}")
    raw_text = args.canonical.read_text(encoding="utf-8")
    indent = _detect_indent(raw_text)
    dataset = json.loads(raw_text)
    records: list[dict[str, Any]] = dataset["data"]

    print(f"populate_bps_ancestors.py — canonical={args.canonical} relation={args.relation}")
    print(f"certified digest = {digest[:16]}…  as_of = {args.as_of}  indent = {indent}  "
          f"mode = {'APPLY' if args.apply else 'DRY-RUN'}")
    print("-" * 78)

    n_populate, problems = plan_and_apply(
        records, relation, digest, args.as_of,
        expected_batch_b=args.expect_batch_b, do_apply=args.apply,
    )

    print("-" * 78)
    print(f"summary: {n_populate} record(s) to populate with {FIELD}, {len(problems)} problem(s)")
    for p in problems:
        logger.error(p)

    if not args.apply:
        print("DRY RUN — no files written. Re-run with --apply to mutate the canonical.")
        return 1 if problems else 0

    if problems:
        logger.error("problems present — refusing to write (fix the artifacts and re-run)")
        return 1

    if n_populate:
        tmp_path = args.canonical.with_suffix(args.canonical.suffix + ".tmp")
        try:
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(dataset, f, ensure_ascii=False, indent=indent)
            tmp_path.replace(args.canonical)
            logger.info("wrote %d populated record(s) to %s", n_populate, args.canonical)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise
    else:
        logger.info("nothing new to populate — reconciling consumers + sidecar from canonical")

    # Always reconcile on --apply (both steps are idempotent no-ops when already in sync).
    # This lets a re-run RECOVER a prior partial apply where the canonical was written but
    # sync/sidecar then failed — never a dead end that leaves consumers stale (family #2).
    run_sync_script()
    update_sidecar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
