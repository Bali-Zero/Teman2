#!/usr/bin/env python3
"""cure_l4bali_hold_review.py — Template H (r2) for the 12 no-Besar-row hold codes.

SAETTA-20260915 / W-H, lane PR-5. Ground: `#6488` (draft, superseded — reuse
NONE of it) argued that a KBLI 2025 code with no Usaha Besar scale row in OSS
is a national 0% closure. The dossier
(`~/BATTAGLIA-20260911/4-KBLI-APP/DOSSIER-no-besar-normativo-2026-09-15.md`,
verdict §0, §1.3) found the opposite: BKPM 5/2025 Pasal 8(6) says a scale
missing from the licensing rules does not by itself restrict the activity,
and none of the 12 codes below has any Perpres 10/2021 (as amended by
49/2021) annex reservation. Publishing "0%" on them would be legally
indefensible; the honest verdict is "PT PMA eligibility unverified in OSS,
not a national closure."

This cure touches ONLY `l4_bali` on the 12 codes, and only three of its keys:
  1. reason       -> Template H (dossier §2.1), with {scales}/{tier} MEASURED
                      from the record's own `per_skala` (never hardcoded —
                      a future re-ingestion that adds/removes a scale row
                      must change the sentence, not go stale silently) and
                      the per-code `{sector}` segment from the spec.
  2. confidence    -> "MEDIUM"
  3. needs_review  -> true

`status` and `blocked` are NEVER modified (Zero's D5g: the 12 keep their Bali
flag as a stated precaution; the correction to the overlay itself is a
separate window, B1). `moratorium` / `from_2020` / `verdict` / `rule` /
`review_basis` / `verdict_state` / any other l4_bali key are copied through
UNCHANGED — same discipline as `cure_l4bali_disclosure.py`.

Guard rails:
  - Per-code drift: a record whose current l4_bali does not match the spec's
    recorded pristine state, AND is not already in the cured state, is a
    CureError — never a guess (same contract as cure_l4bali_disclosure.py).
  - Multi-tier records: the template names ONE risk tier; a record whose
    `per_skala` carries more than one distinct `kategori_risiko` is a
    CureError (none of the 12 do today — verified live before this cure was
    written — but a future re-ingestion must not silently pick one).
  - Withdrawn-inference regex: the rendered reason is checked against the
    same phrases `test_withdrawn_umkm_inference_absent.py` bans ("no Usaha
    Besar scale row", "reserved for UMKM", "reserved for micro, small and
    medium enterprises") before it is ever written — Template H does not use
    them, but a future edit to the template must not reintroduce them
    silently.

Usage:
  # dry run (default) — prints a per-code diff summary, writes nothing
  python scripts/kbli_filiera/cure_l4bali_hold_review.py

  # apply — mutates canonical, propagates to the consumer copies via
  # sync_kbli_dataset.sh, recomputes+writes the vitest sha256 sidecar
  python scripts/kbli_filiera/cure_l4bali_hold_review.py --apply

  # subset
  python scripts/kbli_filiera/cure_l4bali_hold_review.py --only 73300 38110 --apply
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger("kbli_filiera.cure_l4bali_hold_review")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC = REPO_ROOT / "scripts" / "kbli_filiera" / "cure_specs" / "l4bali_hold_review_2026_09_15.json"
DEFAULT_CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_kbli_dataset.sh"
SIDECAR_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-dataset-version.json"
SIDECAR_DATASET_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "KBLI_2025_FINAL_CLEAN.json"

CODE_FIELD = "kode_kbli_2025"

# Canonical business-scale ordering (never alphabetical — "Kecil" < "Menengah"
# < "Mikro" alphabetically would print "Kecil, Menengah and Mikro", which
# reads backwards to a reader who knows the business-size ladder).
SCALE_ORDER = ["Mikro", "Kecil", "Menengah", "Besar"]

# Same bans as scripts/kbli_filiera/tests/test_withdrawn_umkm_inference_absent.py
# — the withdrawn inference is recognised by its ARGUMENT, not its conclusion.
WITHDRAWN_CLAIM = re.compile(
    r"no Usaha Besar scale row"
    r"|reserved for UMKM"
    r"|reserved for micro, small and medium enterprises",
    re.IGNORECASE,
)

NEW_CONFIDENCE = "MEDIUM"
NEW_NEEDS_REVIEW = True


class CureError(RuntimeError):
    """A spec/canonical mismatch severe enough to make the run's exit non-zero."""


def _detect_indent(raw_text: str) -> int:
    for line in raw_text.splitlines()[1:8]:
        stripped = line.lstrip(" ")
        leading = len(line) - len(stripped)
        if leading > 0:
            return leading
    return 2


def _index_by_code(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {r[CODE_FIELD]: r for r in records if CODE_FIELD in r}


def format_scales(scales: set[str]) -> str:
    """Business-scale-ordered natural-language join: 'X', 'X and Y', 'X, Y and Z'."""
    ordered = [s for s in SCALE_ORDER if s in scales]
    unknown = sorted(scales - set(SCALE_ORDER))
    if unknown:
        raise CureError(f"unrecognised skala_usaha value(s) {unknown!r} — not in SCALE_ORDER")
    if not ordered:
        raise CureError("no skala_usaha values found — cannot render {scales}")
    if len(ordered) == 1:
        return ordered[0]
    if len(ordered) == 2:
        return f"{ordered[0]} and {ordered[1]}"
    return ", ".join(ordered[:-1]) + f" and {ordered[-1]}"


def measure_scales_and_tier(code: str, record: dict[str, Any]) -> tuple[str, str]:
    """Read {scales}/{tier} from the record's OWN per_skala — never from the
    spec — so a future re-ingestion changes the sentence instead of going
    silently stale."""
    rows = record.get("per_skala") or []
    if not rows:
        raise CureError(f"{code}: per_skala is empty — cannot measure scales/tier")
    scales = {s for row in rows for s in (row.get("skala_usaha") or [])}
    tiers = {row.get("kategori_risiko") for row in rows}
    if len(tiers) != 1:
        raise CureError(
            f"{code}: per_skala carries {len(tiers)} distinct risk tiers {sorted(tiers)!r} — "
            "Template H names exactly one; refusing to pick"
        )
    (tier,) = tiers
    if not tier:
        raise CureError(f"{code}: kategori_risiko is empty")
    return format_scales(scales), tier


def build_new_reason(template: str, sector: str, scales: str, tier: str) -> str:
    reason = template.format(sector=sector, scales=scales, tier=tier)
    hit = WITHDRAWN_CLAIM.search(reason)
    if hit:
        raise CureError(f"rendered reason matches the withdrawn-inference ban ({hit.group(0)!r}) — refusing to write it")
    return reason


class CurePlan:
    """status: 'apply' | 'already_cured' | 'missing'."""

    def __init__(self, code: str, status: str, detail: str, new_l4: dict[str, Any] | None = None):
        self.code = code
        self.status = status
        self.detail = detail
        self.new_l4 = new_l4


def evaluate_code(code: str, entry: dict[str, Any], template: str, by_code: dict[str, dict[str, Any]]) -> CurePlan:
    record = by_code.get(code)
    if record is None:
        return CurePlan(code, "missing", f"code {code!r} not found in canonical")

    l4 = record.get("l4_bali")
    if not isinstance(l4, dict):
        raise CureError(f"{code}: l4_bali missing or not a dict — cannot cure")

    current_reason = l4.get("reason")
    current_confidence = l4.get("confidence")
    current_needs_review = l4.get("needs_review")
    current_blocked = l4.get("blocked")
    current_status = l4.get("status")

    expected_blocked = entry["expected_blocked"]
    expected_status = entry["expected_status"]
    if current_blocked != expected_blocked or current_status != expected_status:
        raise CureError(
            f"{code}: l4_bali.status/blocked drifted from spec expectation "
            f"(status={current_status!r} vs {expected_status!r}, "
            f"blocked={current_blocked!r} vs {expected_blocked!r}) — this cure "
            "NEVER modifies status/blocked, refusing to proceed on unexpected drift"
        )

    scales, tier = measure_scales_and_tier(code, record)
    new_reason = build_new_reason(template, entry["sector"], scales, tier)

    already_cured = (
        current_confidence == NEW_CONFIDENCE
        and current_needs_review is NEW_NEEDS_REVIEW
        and current_reason == new_reason
    )
    if already_cured:
        return CurePlan(code, "already_cured", f"l4_bali already carries Template H (scales={scales!r}, tier={tier!r}) — no-op")

    is_pristine = (
        current_reason == entry["expected_reason"]
        and current_confidence == entry["expected_confidence"]
        and current_needs_review == entry["expected_needs_review"]
    )
    if not is_pristine:
        raise CureError(
            f"{code}: l4_bali is neither in the spec's pristine state nor already "
            f"cured — data has drifted (reason={current_reason!r}, "
            f"confidence={current_confidence!r}, needs_review={current_needs_review!r}); "
            "refusing to guess"
        )

    new_l4 = copy.deepcopy(l4)
    new_l4["confidence"] = NEW_CONFIDENCE
    new_l4["needs_review"] = NEW_NEEDS_REVIEW
    new_l4["reason"] = new_reason
    return CurePlan(
        code,
        "apply",
        f"scales={scales!r} tier={tier!r} confidence {current_confidence!r}->{NEW_CONFIDENCE}, "
        f"needs_review {current_needs_review!r}->{NEW_NEEDS_REVIEW}, "
        f"reason {len(current_reason)}->{len(new_reason)} chars",
        new_l4=new_l4,
    )


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
        raise CureError(f"sync_kbli_dataset.sh sync failed with exit {result.returncode}")


def update_sidecar() -> None:
    if not SIDECAR_DATASET_PATH.exists():
        raise CureError(f"sidecar dataset copy missing: {SIDECAR_DATASET_PATH} (sync must run first)")
    digest = hashlib.sha256(SIDECAR_DATASET_PATH.read_bytes()).hexdigest()
    sidecar = json.loads(SIDECAR_PATH.read_text(encoding="utf-8"))
    before = dict(sidecar)
    sidecar["datasetSha256"] = f"sha256:{digest}"
    sidecar["lastModified"] = date.today().isoformat()
    SIDECAR_PATH.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info("sidecar updated: %s -> %s", before.get("datasetSha256"), sidecar["datasetSha256"])
    logger.info("sidecar lastModified: %s -> %s", before.get("lastModified"), sidecar["lastModified"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--only", nargs="+", default=None, help="restrict to these KBLI codes")
    parser.add_argument("--apply", action="store_true", help="mutate the canonical (default: dry-run, writes nothing)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    spec: dict[str, Any] = json.loads(args.spec.read_text(encoding="utf-8"))
    template: str = spec["template"]
    all_codes: dict[str, Any] = spec["codes"]
    codes = sorted(all_codes.keys())
    if args.only:
        wanted = set(args.only)
        missing_requested = wanted - set(all_codes)
        if missing_requested:
            raise CureError(f"--only requested codes not present in spec: {sorted(missing_requested)}")
        codes = [c for c in codes if c in wanted]

    if not args.canonical.exists():
        raise CureError(f"canonical dataset not found: {args.canonical}")
    raw_text = args.canonical.read_text(encoding="utf-8")
    indent = _detect_indent(raw_text)
    dataset = json.loads(raw_text)
    records: list[dict[str, Any]] = dataset["data"]
    by_code = _index_by_code(records)

    print(f"cure_l4bali_hold_review.py — spec={args.spec} canonical={args.canonical} "
          f"mode={'APPLY' if args.apply else 'DRY-RUN'}")
    print("-" * 78)

    problems: list[str] = []
    to_apply: dict[str, dict[str, Any]] = {}
    already_cured_count = 0
    missing_count = 0

    for code in codes:
        entry = all_codes[code]
        try:
            plan = evaluate_code(code, entry, template, by_code)
        except CureError as exc:
            problems.append(str(exc))
            print(f"{code}: CURE ERROR — {exc}")
            continue

        if plan.status == "missing":
            missing_count += 1
            problems.append(f"spec code {code!r} not found in canonical {args.canonical}")
            print(f"{code}: NOT FOUND IN CANONICAL — cannot cure")
        elif plan.status == "already_cured":
            already_cured_count += 1
            print(f"{code}: ALREADY CURED — {plan.detail}")
        elif plan.status == "apply":
            to_apply[code] = plan.new_l4  # type: ignore[assignment]
            print(f"{code}: TO CURE — {plan.detail}")
        else:  # pragma: no cover - defensive
            raise CureError(f"{code}: unknown plan status {plan.status!r}")

    print("-" * 78)
    print(f"summary: {len(to_apply)} to cure, {already_cured_count} already cured, "
          f"{missing_count} missing, {len(problems)} problem(s)")

    if not args.apply:
        if problems:
            for p in problems:
                logger.error(p)
            return 1
        print("DRY RUN — no files written. Re-run with --apply to mutate the canonical.")
        return 0

    if to_apply:
        for code, new_l4 in to_apply.items():
            idx = next(i for i, r in enumerate(records) if r.get(CODE_FIELD) == code)
            records[idx]["l4_bali"] = new_l4
        tmp_path = args.canonical.with_suffix(args.canonical.suffix + ".tmp")
        try:
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(dataset, f, ensure_ascii=False, indent=indent)
            tmp_path.replace(args.canonical)
            logger.info("wrote %d cured record(s) to %s", len(to_apply), args.canonical)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

        run_sync_script()
        update_sidecar()
    else:
        logger.info("no canonical changes — skipping sync + sidecar update")

    if problems:
        for p in problems:
            logger.error(p)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
