#!/usr/bin/env python3
"""Apply the Lampiran II K-UMKM reservation to canonical, from an adjudicated spec.

WHAT THIS ASSERTS, AND ON WHAT
-------------------------------
Perpres 10/2021 as amended by 49/2021, **Lampiran II**, allocates a *bidang
usaha* to Indonesian cooperatives and MSMEs (the DIALOKASIKAN column). A foreign
investor cannot be a Koperasi or a UMKM, so for the allocated activity the
lawful foreign share is 0% — the reading our own catalogue already carries, once,
hand-adjudicated, on `47111` (minimarket).

Two articles that are NOT this one, and must not be conflated with it:

* **Pasal 7 ayat (1)** ("Penanam Modal asing hanya dapat melakukan kegiatan
  usaha pada Usaha Besar dengan nilai investasi lebih dari Rp10.000.000.000,00")
  conditions the INVESTOR and its project, not the activity. It can stop a
  particular PMA that cannot qualify as large; it does not open or close an
  activity, and it does not dissolve a Lampiran II allocation. Reading the
  Rp10B threshold as "so a PMA is above the reservation anyway" inverts a
  reservation into a permission and is wrong.
* **KEMITRAAN**, the other column of the same annex, is a duty to PARTNER with
  K-UMKM, which an open PMA discharges. 57 codes sit there and NONE of them
  appear in this spec.

WHAT IS IN THE SPEC, AND WHAT DELIBERATELY IS NOT
--------------------------------------------------
`cure_specs/umkm_lampiran_ii_readjudicated_2026_08_06.json` carries NINE codes,
each one where two INDEPENDENT passes of different model families agreed on
PATCH — a Claude lane proposing from the annex row and an OpenAI lane
re-deriving the same code blind, with the bias stated against restricting ("a
wrongly-restricted code costs a client a business they could lawfully run; that
is not a safer error, it is a different error" — and refusing is NOT the safe
direction either: the opposite error tells a client he may wholly own an
activity the annex reserves).

It replaces `umkm_lampiran_ii_2026_08_06.json`, which was WITHDRAWN whole before
merge: the evidence handed to its 21 adjudicating agents had the scope qualifier
stripped out, because Lampiran II writes the scope on a numbered PARENT row and
the parser emitted only the indented child. That spec stays on disk, still
carrying its verdicts, and this tool refuses it BY NAME (see `WITHDRAWN_SPEC`).

The re-adjudication ran in two rounds over the 68 `whole-row` codes and kept
what survived both: 11 refused as SEGMENT-only (reserved just below 25 Ha, or
only at simple/intermediate technology grade), 9 refused as BROADER than the
reserved activity, 13 where the families disagreed, 3+2 called unclear, 1 whose
annex text the OCR destroyed on the token that sets its scope, and 6 vintage
carries whose 1:1 heir has not yet been checked for ACTIVITY identity (lineage
is not identity). None of that is a silent drop — every population is named in
the spec's `excluded` block and pinned by a test.

Round 2's evidence pack carried, for the first time, BOTH the parent bidang
usaha and the SIBLING 2025 codes that share each ancestor. That second field is
what moved eight verdicts from PATCH to REFUSE_BROADER: a 2025 code that also
absorbs 2020 activities the annex never named is wider than the reservation.

A spec row judged on a KBLI-2020 number that is not a 2025 code records
`judged_as`. This tool re-derives that heir itself, in BOTH directions, and
refuses if either disagrees — the vintage trap has bitten this catalogue twice
in one day and a written-down mapping is a proxy, not the fact.

REFUSES RATHER THAN GUESSES
----------------------------
`--apply` aborts, writing nothing, if: a spec code is absent from the dataset;
a spec row's `judged_as` does not resolve to its stated target through
`bps_2020_ancestors`; a record already carries a DIFFERENT `pma_official_basis`
(someone adjudicated it by hand and this tool is not the later word); or the
observed `pma_status`/`pma_max_asing` differ from what the spec recorded when it
was built, which means the world moved under the adjudication.

AND IT REACHES THE CONSUMERS, WHICH IT USED NOT TO
---------------------------------------------------
Writing canonical is not shipping. `apps/mouth` (balizero.com/kbli),
`apps/kbli-navigator` and the RAG's own copy each hold a physical duplicate, and
a vitest guard fails when the dataset hash moves without the sidecar version
file moving with it. Every sibling cure compiler runs `sync_kbli_dataset.sh` and
re-hashes that sidecar; this one did not, so its cure landed on canonical alone
and the drift check would have failed the NEXT innocent PR (W86). `--apply` now
does both, and refuses if a consumer copy still differs afterwards.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
CURE_SPECS = Path(__file__).resolve().parent / "cure_specs"
SPEC = CURE_SPECS / "umkm_lampiran_ii_readjudicated_2026_08_06.json"

# Kept on disk on purpose. It still carries the 39 verdicts and the record of WHY
# they were withdrawn; `main()` refuses it by its own `withdrawn` marker, so
# pointing `--spec` at it is a loud refusal rather than a silent 39-code write.
WITHDRAWN_SPEC = CURE_SPECS / "umkm_lampiran_ii_2026_08_06.json"

SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_kbli_dataset.sh"
SIDECAR_VERSION = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-dataset-version.json"
SIDECAR_DATASET = REPO_ROOT / "apps" / "mouth" / "data" / "KBLI_2025_FINAL_CLEAN.json"

VINTAGE = "2021-05-25"
KONDISI = (
    "Bidang usaha dialokasikan untuk Koperasi dan UMKM (Perpres 49/2021 "
    "Lampiran II) — foreign ownership 0%"
)

EXIT_OK = 0
EXIT_REFUSED = 2


def load(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    text = path.read_text(encoding="utf-8")
    payload = json.loads(text)
    records = payload["data"] if isinstance(payload, dict) else payload
    if not isinstance(records, list) or not records:
        raise ValueError(f"{path}: expected a non-empty record list")
    return payload, records, text


def heirs_of(records: list[dict[str, Any]]) -> dict[str, list[str]]:
    """2020 code -> the 2025 codes that record it as an ancestor."""
    out: dict[str, list[str]] = {}
    for r in records:
        anc = r.get("bps_2020_ancestors")
        codes = anc.get("codes") if isinstance(anc, dict) else None
        for c in codes or []:
            out.setdefault(str(c), []).append(str(r["kode_kbli_2025"]))
    return out


def patch_for(item: dict[str, Any]) -> dict[str, Any]:
    """Pure — the field-level patch for one adjudicated code."""
    return {
        "pma_max_asing": 0,
        "pma_status": "TERBATAS",
        "pma_official_basis": item["locator"],
        "pma_cap_verified": True,
        "pma_source_vintage": VINTAGE,
        "pma_kondisi": KONDISI,
    }


def check(
    spec: dict[str, Any], records: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Returns (applicable items, refusals). A refusal aborts the whole run:
    a spec that is wrong about one code is not trustworthy about the rest."""
    by_code = {str(r["kode_kbli_2025"]): r for r in records}
    heirs = heirs_of(records)
    refusals: list[str] = []
    todo: list[dict[str, Any]] = []

    for item in spec["items"]:
        code = item["code"]
        record = by_code.get(code)
        if record is None:
            refusals.append(f"{code}: not in the dataset")
            continue

        judged = item.get("judged_as")
        if judged:
            # Re-derive rather than trust the spec's own mapping.
            found = heirs.get(judged, [])
            if found != [code]:
                refusals.append(
                    f"{code}: judged on 2020 {judged}, which resolves to "
                    f"{found or 'no 2025 heir'} — not this code alone"
                )
                continue

            # …and the OTHER direction, which the rule above cannot see. "One
            # heir" says the 2020 activity did not split; it says nothing about
            # whether the 2025 code MERGED several 2020 activities, in which
            # case the code is BROADER than the one row the annex reserves and
            # belongs with the 28 refused for exactly that (Pasal 5(5): the
            # allocation attaches to the named bidang usaha).
            #
            # Measured on the seven vintage rows: six are 1:1, and `79110`
            # (Aktivitas Agen Perjalanan) absorbs THREE 2020 codes — 79111,
            # 79112, 79119 — so reserving all of it on 79111's row would close
            # an activity the annex never named. That one was already out of the
            # spec, but for an unrelated reason (a competing determination in a
            # test), i.e. it was luck, not this rule. Now it is this rule.
            ancestors = (record.get("bps_2020_ancestors") or {}).get("codes") or []
            others = [str(a) for a in ancestors if str(a) != judged]
            if others:
                refusals.append(
                    f"{code}: judged on 2020 {judged}, but this 2025 code also "
                    f"absorbs {others} — broader than the reserved activity"
                )
                continue

        existing = record.get("pma_official_basis")
        if existing and existing != item["locator"]:
            refusals.append(f"{code}: already carries a different pma_official_basis")
            continue

        was = item.get("was") or {}
        now = {
            "pma_status": record.get("pma_status"),
            "pma_max_asing": record.get("pma_max_asing"),
        }
        if was and was != now:
            refusals.append(f"{code}: moved since adjudication — spec {was}, now {now}")
            continue

        todo.append(item)

    return todo, refusals


def propagate(dry: bool = False) -> list[str]:
    """Push canonical to every consumer copy and re-stamp the version sidecar.

    Returns the list of problems; empty means the fleet agrees with canonical.
    Separated from `main()` so a test can drive it without a 37MB write.
    """
    problems: list[str] = []
    result = subprocess.run(
        ["bash", str(SYNC_SCRIPT), "sync"], capture_output=True, text=True
    )
    if result.returncode != 0:
        problems.append(f"sync_kbli_dataset.sh exited {result.returncode}: {result.stderr[-400:]}")
        return problems

    # Prove the propagation instead of trusting the exit code (superscar #2).
    check = subprocess.run(
        ["bash", str(SYNC_SCRIPT), "--check"], capture_output=True, text=True
    )
    if check.returncode != 0:
        problems.append(f"consumer copies still differ after sync: {check.stdout[-400:]}")
        return problems

    if not SIDECAR_DATASET.exists():
        problems.append(f"sidecar dataset copy missing: {SIDECAR_DATASET}")
        return problems

    digest = "sha256:" + hashlib.sha256(SIDECAR_DATASET.read_bytes()).hexdigest()
    sidecar = json.loads(SIDECAR_VERSION.read_text(encoding="utf-8"))
    if sidecar.get("datasetSha256") == digest:
        return problems  # content did not move; nothing to bump

    if not dry:
        sidecar["datasetSha256"] = digest
        SIDECAR_VERSION.write_text(
            json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(f"  sidecar version -> {digest}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    ap.add_argument("--dataset", default=str(CANONICAL))
    ap.add_argument("--spec", default=str(SPEC))
    args = ap.parse_args(argv)

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))

    # A withdrawn spec is not an empty one, and the difference must not depend on
    # a reader noticing that `items` happens to be []. The 2026-08-06 spec was
    # withdrawn whole after a cross-family review found its evidence had the
    # scope qualifier stripped out; running it would publish a 0% foreign cap on
    # activities the annex reserves only below 25 Ha, or only at simple and
    # intermediate technology grade. Refuse loudly, name the reason, write nothing.
    withdrawn = spec.get("withdrawn")
    if withdrawn:
        print(f"REFUSING: this spec was withdrawn on {withdrawn.get('date')}.")
        print(f"  by:     {withdrawn.get('by')}")
        print(f"  reason: {withdrawn.get('reason')}")
        print(f"  next:   {withdrawn.get('next')}")
        return EXIT_REFUSED

    path = Path(args.dataset)
    payload, records, original = load(path)

    todo, refusals = check(spec, records)

    print(f"spec items {len(spec['items'])} · applicable {len(todo)} · refused {len(refusals)}")
    print(f"excluded by the adjudication itself: {spec['excluded']}")
    for r in refusals:
        print(f"  REFUSE {r}")
    if refusals:
        print("\nrefusing to write: a spec wrong about one code is not trusted for the rest")
        return EXIT_REFUSED

    for item in todo:
        via = f" (judged as {item['judged_as']})" if item.get("judged_as") else ""
        print(f"  {item['code']}{via}: {item['was']} -> TERBATAS/0")

    if not args.apply:
        print("\ndry-run — rerun with --apply to write")
        return EXIT_OK

    by_code = {str(r["kode_kbli_2025"]): r for r in records}
    for item in todo:
        by_code[item["code"]].update(patch_for(item))

    body = json.dumps(payload, ensure_ascii=False, indent=2)
    path.write_text(body + ("\n" if original.endswith("\n") else ""), encoding="utf-8")

    # Read back and prove the write, rather than trusting that it happened.
    _, again, _ = load(path)
    fresh = {str(r["kode_kbli_2025"]): r for r in again}
    wrong = [
        i["code"]
        for i in todo
        if fresh[i["code"]].get("pma_max_asing") != 0
        or fresh[i["code"]].get("pma_status") != "TERBATAS"
    ]
    if wrong:
        print(f"WROTE BUT READ BACK WRONG on {len(wrong)}: {wrong[:10]}")
        return EXIT_REFUSED
    print(f"\napplied and verified on re-read: {len(todo)} code(s)")

    # Propagation is a statement about CANONICAL. Run against any other dataset —
    # a test sandbox, a scratch copy — pushing canonical to the fleet would be a
    # side effect nobody asked for, and under `--check` it would report on a file
    # this run never touched. Say so instead of doing it.
    if path.resolve() != CANONICAL.resolve():
        print(f"not canonical ({path}) — skipping consumer propagation")
        return EXIT_OK

    problems = propagate()
    for p in problems:
        print(f"  PROPAGATION FAILED: {p}")
    if problems:
        # Canonical is already cured; stopping here is honest, not tidy. A cure
        # that reached one store and not the others is exactly the state that
        # must be visible rather than reported as success.
        return EXIT_REFUSED
    print("consumer copies in sync with canonical")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
