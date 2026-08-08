#!/usr/bin/env python3
"""cure_whatchanged_corroborated_predecessor.py — close the 4-code residue
PENDING-ARMS left open after the L2.1 `whatChanged` provenance pass.

BACKGROUND
----------
L2.1 (2026-07-25) found 4 codes whose `whatChanged` named a KBLI-2020
predecessor no crosswalk layer recorded (`46415`, `46496`, `49296`,
`64210`) and replaced the false claim with an honest "unconfirmed pending
re-verification" sentence — deliberately NOT substituting a number, because
on `46415` the two crosswalk layers disagree with each other and picking a
winner is the disease this lane exists to cure.

RE-MEASURED 2026-08-08 (ward-round `kbli-client-facing-content-defects`):
that refusal was right for `46415` and `46496` (the two layers genuinely
disagree — see below) and WRONG for `49296` and `64210`, where they agree:

  code    PP28/2025 lampiran (title-match)   official BPS 2020-2025 crosswalk
  46415   46694 (78%)                        46419                    DISAGREE
  46496   47854 (81%)                        46499                    DISAGREE
  49296   49424 (100%)                       49424                    AGREE
  64210   64200 (95%)                        64200                    AGREE

The BPS crosswalk (`data/kbli-filiera/phase0/bps_crosswalk.json::relation`,
Phase-0 gated P=R=1.0 on a 20-page holdout, cross-family verified) and the
PP28/2025 lampiran title-match (`pp28_sources`/`mapping_note`, a DIFFERENT
government instrument extracted by a DIFFERENT pass) are structurally
independent. Agreement between them, verified by MEMBERSHIP not by count, is
the same corroboration standard already used in this lane for the Lampiran
III cross-instrument check (F2, 2026-08-02: "asserted by MEMBERSHIP and not
by count"). So `49296`/`64210` get a CONFIRMED sentence; `46415`/`46496`
stay unconfirmed, unchanged.

THE SEPARATE DEFECT THIS SCRIPT ALSO CLOSES
--------------------------------------------
Gold (`apps/mouth/data/kbli-gold-all.json`) — which WINS on `/kbli/<code>`,
the page a client reads — was never scanned by L2.1's pass-C detector,
because gold authors this fact in a DIFFERENT template ("Previous code(s):
NNNNN") than canonical's ("KBLI 2020: NNNNN"), and `_NAMED_PREDECESSOR`
(`_whatchanged_basis.py`) is anchored to the literal "KBLI 2020: " phrase —
a guard UNDER-match (cicatrix superscar #3 / W82 shape: same disease, a
different formulation sails through). Measured: `46496`'s gold entry still
asserted the confident, uncited, CONTRADICTED claim "Previous code(s):
47854" — a live client-facing lie the L2.1 census never saw. `49296`'s gold
entry happened to already state the (now-confirmed) right value, but with
no citation and a different sentence than canonical — this script unifies
both onto the one corroborated sentence. `64210`'s gold entry already
matched canonical's L2.1 text byte-for-byte (that one WAS caught, because
its wording used "KBLI 2020: 64190").

SPEC-DRIVEN, FACTS-BASIS GUARDED
---------------------------------
Every replacement text is pinned in
`cure_specs/whatchanged_corroborated_predecessor_2026_08_08.json`; this
module authors none of it. Before touching a record, `assert_facts_basis()`
re-reads canonical's own `pp28_sources` / `kbli_2020_source` /
`bps_2020_ancestors` / `mapping_note` and refuses (exit 2) if the premise
this cure was adjudicated against has moved — a later re-adjudication must
not be silently overwritten by a stale spec.

Sanctioned writer of the canonical KBLI dataset alongside
cure_canonical_collisions.py / cure_metadata_pp28_sources.py /
cure_restore_per_ancestor.py: infra/claude-hooks/data_plane_guard.py allows
this program's own compilers/ (data-plane registry id "kbli-filiera") to
write data/source_documents/KBLI_2025_FINAL_CLEAN.json. Gold is not
data-plane-guarded but every change here is spec-pinned old->new, never
free-authored.

Usage:
  python scripts/kbli_filiera/cure_whatchanged_corroborated_predecessor.py            # dry-run
  python scripts/kbli_filiera/cure_whatchanged_corroborated_predecessor.py --apply
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger("kbli_filiera.cure_whatchanged_corroborated_predecessor")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC = (
    REPO_ROOT
    / "scripts"
    / "kbli_filiera"
    / "cure_specs"
    / "whatchanged_corroborated_predecessor_2026_08_08.json"
)
DEFAULT_CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
DEFAULT_GOLD = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-gold-all.json"
# The FULL BPS 2020<->2025 crosswalk relation (1,559/1,559 codes, Phase-0 gated
# P=R=1.0 on a 20-page holdout). Read this directly rather than canonical's own
# `bps_2020_ancestors` field: that field was written by a populate step scoped
# to OSS-native codes only (`_l2_status is null`, PR #3082) and is therefore
# ABSENT on no-oss-scope codes such as 49296 even though the underlying
# crosswalk relation covers them — reading the narrower copy would silently
# treat "the populate step skipped this code" as "no BPS source exists".
DEFAULT_BPS_CROSSWALK = REPO_ROOT / "data" / "kbli-filiera" / "phase0" / "bps_crosswalk.json"
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_kbli_dataset.sh"
SIDECAR_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-dataset-version.json"
SIDECAR_DATASET_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "KBLI_2025_FINAL_CLEAN.json"

CODE_FIELD = "kode_kbli_2025"
EXIT_OK = 0
EXIT_REFUSED = 2


class CureError(RuntimeError):
    """A spec/record mismatch severe enough to refuse rather than guess."""


def _detect_indent(raw_text: str) -> int:
    for line in raw_text.splitlines()[1:8]:
        stripped = line.lstrip(" ")
        leading = len(line) - len(stripped)
        if leading > 0:
            return leading
    return 2


def load_spec(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    codes = payload.get("codes")
    if not isinstance(codes, list) or not codes:
        raise CureError(f"{path}: 'codes' must be a non-empty list")
    return codes


def load_canonical(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], int, str]:
    raw_text = path.read_text(encoding="utf-8")
    indent = _detect_indent(raw_text)
    dataset = json.loads(raw_text)
    records = dataset["data"]
    return dataset, records, indent, raw_text


def load_gold(path: Path) -> tuple[dict[str, Any], dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    raw = json.loads(text)
    data = raw.get("data", raw) if isinstance(raw, dict) else raw
    return raw, data, text


def load_bps_relation(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    relation = payload.get("relation")
    if not isinstance(relation, dict):
        raise CureError(f"{path}: no 'relation' object — wrong file?")
    return relation


def assert_facts_basis(
    entry: dict[str, Any], record: dict[str, Any], bps_relation: dict[str, Any]
) -> None:
    """Re-derive the corroboration this entry was adjudicated against. Refuse,
    never guess, if the layers have moved since."""
    code = entry["code"]
    predecessor = entry.get("predecessor")
    bps = [str(c) for c in (bps_relation.get(code, {}).get("codes") or [])]
    if predecessor is None:
        # The "still disputed, only gold's wording is being aligned" shape:
        # assert the two layers still DISAGREE, so this script never silently
        # papers over a real re-adjudication that resolved it differently.
        pp28 = [str(c) for c in (record.get("pp28_sources") or [])]
        if pp28 and bps and set(pp28) == set(bps):
            raise CureError(
                f"{code}: facts_basis premise drifted — pp28_sources and "
                f"the BPS crosswalk now AGREE ({pp28}); this entry assumed "
                "disagreement. Re-adjudicate, do not apply this spec."
            )
        return

    pp28 = [str(c) for c in (record.get("pp28_sources") or [])]
    kbli_2020_source = str(record.get("kbli_2020_source") or "")
    mapping_note = str(record.get("mapping_note") or "")
    pct = entry.get("pp28_match_pct")

    problems = []
    if pp28 != [predecessor]:
        problems.append(f"pp28_sources == {pp28!r}, expected [{predecessor!r}]")
    if bps != [predecessor]:
        problems.append(f"BPS crosswalk relation == {bps!r}, expected [{predecessor!r}]")
    if kbli_2020_source != predecessor:
        problems.append(f"kbli_2020_source == {kbli_2020_source!r}, expected {predecessor!r}")
    if pct is not None and f"Match: {pct}%" not in mapping_note:
        problems.append(f"mapping_note {mapping_note!r} does not contain 'Match: {pct}%'")
    if problems:
        raise CureError(
            f"{code}: facts_basis premise drifted — " + "; ".join(problems) +
            ". The corroboration this cure was adjudicated against no longer "
            "holds — re-adjudicate, do not apply."
        )


def plan_canonical(entry: dict[str, Any], record: dict[str, Any]) -> dict[str, Any] | None:
    spec_field = entry.get("canonical_whatChanged")
    if spec_field is None:
        return None
    intel = record.get("intel_2026") or {}
    live = intel.get("whatChanged")
    if live == spec_field["new"]:
        return {"action": "noop", "reason": "already cured"}
    if live == spec_field["old"]:
        return {"action": "patch", "new": spec_field["new"]}
    raise CureError(
        f"{entry['code']}: canonical intel_2026.whatChanged matches neither the "
        f"pinned old nor new — live={live!r}"
    )


def plan_gold(entry: dict[str, Any], gold: dict[str, Any]) -> dict[str, Any] | None:
    spec_field = entry.get("gold_whatChanged")
    if spec_field is None:
        return None
    code = entry["code"]
    rec = gold.get(code)
    if rec is None:
        return {"action": "absent", "reason": "code not in gold — nothing to patch"}
    live = rec.get("whatChanged")
    if live == spec_field["new"]:
        return {"action": "noop", "reason": "already cured"}
    if live == spec_field["old"]:
        return {"action": "patch", "new": spec_field["new"]}
    raise CureError(
        f"{code}: gold whatChanged matches neither the pinned old nor new — live={live!r}"
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--bps-crosswalk", type=Path, default=DEFAULT_BPS_CROSSWALK)
    parser.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    entries = load_spec(args.spec)
    dataset, records, indent, _ = load_canonical(args.canonical)
    by_code = {r[CODE_FIELD]: r for r in records if CODE_FIELD in r}
    gold_raw, gold, gold_original = load_gold(args.gold)
    bps_relation = load_bps_relation(args.bps_crosswalk)

    print(f"cure_whatchanged_corroborated_predecessor.py — mode={'APPLY' if args.apply else 'DRY-RUN'}")
    print("-" * 78)

    canonical_plans: dict[str, dict[str, Any]] = {}
    gold_plans: dict[str, dict[str, Any]] = {}
    try:
        for entry in entries:
            code = entry["code"]
            record = by_code.get(code)
            if record is None:
                raise CureError(f"{code}: not in canonical — cannot verify facts_basis")
            assert_facts_basis(entry, record, bps_relation)
            cplan = plan_canonical(entry, record)
            if cplan is not None:
                canonical_plans[code] = cplan
                print(f"  canonical {code}: {cplan['action']}" + (f" ({cplan.get('reason')})" if cplan.get("reason") else ""))
            gplan = plan_gold(entry, gold)
            if gplan is not None:
                gold_plans[code] = gplan
                print(f"  gold      {code}: {gplan['action']}" + (f" ({gplan.get('reason')})" if gplan.get("reason") else ""))
    except CureError as exc:
        print(f"REFUSED: {exc}")
        return EXIT_REFUSED

    print("-" * 78)
    canonical_to_patch = {c: p for c, p in canonical_plans.items() if p["action"] == "patch"}
    gold_to_patch = {c: p for c, p in gold_plans.items() if p["action"] == "patch"}
    print(
        f"summary: canonical {len(canonical_to_patch)} to patch / {len(canonical_plans) - len(canonical_to_patch)} noop; "
        f"gold {len(gold_to_patch)} to patch / {len(gold_plans) - len(gold_to_patch)} noop-or-absent"
    )

    if not args.apply:
        print("\ndry-run — rerun with --apply to write")
        return EXIT_OK

    if not canonical_to_patch and not gold_to_patch:
        print("nothing to apply")
        return EXIT_OK

    for code, plan in canonical_to_patch.items():
        record = by_code[code]
        intel = dict(record.get("intel_2026") or {})
        intel["whatChanged"] = plan["new"]
        record["intel_2026"] = intel

    if canonical_to_patch:
        tmp_path = args.canonical.with_suffix(args.canonical.suffix + ".tmp")
        try:
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(dataset, f, ensure_ascii=False, indent=indent)
            tmp_path.replace(args.canonical)
            logger.info("wrote %d cured record(s) to %s", len(canonical_to_patch), args.canonical)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

    for code, plan in gold_to_patch.items():
        gold[code]["whatChanged"] = plan["new"]

    if gold_to_patch:
        if isinstance(gold_raw, dict) and "data" in gold_raw and isinstance(gold_raw["data"], dict):
            gold_raw["data"] = gold
            gold_out = gold_raw
        else:
            gold_out = gold
        body = json.dumps(gold_out, ensure_ascii=False, indent=2)
        args.gold.write_text(body + ("\n" if gold_original.endswith("\n") else ""), encoding="utf-8")
        logger.info("wrote %d cured gold record(s) to %s", len(gold_to_patch), args.gold)

    if canonical_to_patch:
        run_sync_script()
        update_sidecar()

    # Read back and prove every write, rather than trusting it happened.
    wrong: list[str] = []
    if canonical_to_patch:
        _, records_after, _, _ = load_canonical(args.canonical)
        by_code_after = {r[CODE_FIELD]: r for r in records_after if CODE_FIELD in r}
        for code, plan in canonical_to_patch.items():
            after = (by_code_after[code].get("intel_2026") or {}).get("whatChanged")
            if after != plan["new"]:
                wrong.append(f"canonical:{code}")
    if gold_to_patch:
        _, gold_after, _ = load_gold(args.gold)
        for code, plan in gold_to_patch.items():
            if gold_after[code].get("whatChanged") != plan["new"]:
                wrong.append(f"gold:{code}")
    if wrong:
        print(f"WROTE BUT READ BACK WRONG on: {wrong}")
        return EXIT_REFUSED

    print(f"\napplied and verified on re-read: canonical={len(canonical_to_patch)} gold={len(gold_to_patch)}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
