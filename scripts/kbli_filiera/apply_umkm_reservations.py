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

# The cure currently pointed at by `--spec`'s default. Each spec is a distinct
# adjudication over a distinct POPULATION, and they are applied in sequence; a
# spec that has already been written stays on disk and stays pinned by tests,
# because "what did we assert about this code, and on whose two signatures" is a
# question a client-facing 0% verdict has to be able to answer years later.
SPEC = CURE_SPECS / "umkm_lampiran_ii_split_heirs_2026_08_06.json"

# Applied 2026-08-06 (#3666) — the nine codes whose 2020 ancestor did NOT split.
PRIOR_SPEC = CURE_SPECS / "umkm_lampiran_ii_readjudicated_2026_08_06.json"

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
        # Asked BEFORE either gate runs. Asked after, it can never fire: the
        # `judged_as` branch below consumes the item first and refuses it for a
        # multi-heir ancestor, so the reader is told the wrong thing about a
        # malformed spec and this check is decoration. Its own guilt test caught
        # that on the first run.
        if judged and item.get("judged_as_split_heir"):
            refusals.append(f"{code}: has both judged_as and judged_as_split_heir")
            continue
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

        split = item.get("judged_as_split_heir")
        if split:
            # A SEPARATE, NARROWER GATE — not a relaxation of the one above.
            #
            # `judged_as` refuses whenever the 2020 code has more than one 2025
            # heir, and that refusal is right for what it guards: when an
            # activity fans out you cannot tell from the crosswalk alone WHICH
            # heir the annex row names. But "cannot tell from the crosswalk" is
            # not "cannot tell". Two shapes recur and both are decidable:
            #
            #   `96111` (Pangkas rambut) -> {96210 barbering, 96400 a personal-
            #      services INTERMEDIATION platform that also swallows eight
            #      unrelated 2020 codes}. The activity itself is 96210.
            #   `55110` (all star hotels) -> {55101..55105 by star grade}. The
            #      annex names "Hotel Bintang I", one grade, which is 55105.
            #
            # What makes them decidable is the REVERSE direction: the heir that
            # absorbs no other 2020 code cannot be wider than the row. So this
            # gate re-derives, mechanically and without trusting the spec:
            #   1. the named 2020 code really is an ancestor of this 2025 code;
            #   2. this 2025 code absorbs NOTHING else (so it cannot over-reach);
            #   3. the 2020 code really did split — otherwise the item belongs
            #      on `judged_as`, and two gates that overlap drift apart;
            #   4. the siblings left open are NAMED in the spec and match what
            #      the dataset says they are, so the drop is visible rather than
            #      implied;
            #   5. those siblings are in fact still OPEN in the dataset — the
            #      spec's sentence about them has to be true of the catalogue;
            #   6. two independent lanes are NAMED in `agreed_by`.
            #
            # What this gate does NOT do is decide identity. Whether 96210 IS
            # "Pangkas rambut/barber shop" is a judgment; it is made by two
            # independent lanes and recorded per item in `agreed_by`, and
            # precondition 6 below refuses the item if two are not recorded.
            # That sentence used to end "and `main()` requires two of them",
            # which was simply false — nothing read the field, so an item with
            # `agreed_by: []` would have been written. A cross-family review of
            # this gate found it. The stricter evidence rule lives HERE and not
            # on the 1:1 gate above for a reason that is not arbitrary: there,
            # identity is mechanical (a single heir IS the ancestor), so the
            # crosswalk carries it. Here identity is a judgment, so the gate
            # that admits a judgment is the one that must prove it was made
            # twice.
            #
            # The mechanics here only guarantee that a wrong identity call
            # cannot ALSO over-reach into activities the annex never named.
            ancestors = [
                str(a) for a in (record.get("bps_2020_ancestors") or {}).get("codes") or []
            ]
            if split not in ancestors:
                refusals.append(
                    f"{code}: judged as a split heir of 2020 {split}, which is "
                    f"not among its ancestors {ancestors or 'none'}"
                )
                continue
            others = [a for a in ancestors if a != split]
            if others:
                refusals.append(
                    f"{code}: judged as a split heir of 2020 {split}, but it also "
                    f"absorbs {others} — broader than the reserved activity"
                )
                continue
            siblings = sorted(set(heirs.get(split, [])) - {code})
            if not siblings:
                refusals.append(
                    f"{code}: 2020 {split} has no other heir — this is the "
                    f"judged_as case, not a split"
                )
                continue
            declared = sorted(item.get("siblings_left_open") or [])
            if declared != siblings:
                refusals.append(
                    f"{code}: spec leaves open {declared or 'nothing'}, but 2020 "
                    f"{split} also went to {siblings}"
                )
                continue

            # 5. …and "left open" has to be TRUE of the catalogue, not merely
            #    written in the spec. The check above compares NAMES; it never
            #    asked the dataset whether those siblings are still open, so a
            #    sibling already restricted by some other cure would pass while
            #    the sentence "why_the_sibling_stays_open" asserted the
            #    opposite. That matters beyond tidiness: the reason this heir is
            #    narrow enough to close is that the siblings carry the REST of
            #    the ancestor's activity. A sibling that has itself been closed
            #    is no longer carrying anything, and the split the spec
            #    describes is not the split on disk. Raised by a cross-family
            #    review of this gate.
            #    Written as a POSITIVE observation on purpose. The first draft
            #    asked `status not in (None, "TERBUKA")`, which reads a sibling
            #    that is missing, or whose status field is absent, as open — a
            #    fail-open in the middle of a guard whose whole job is to
            #    establish that a fact is true. Unreachable today (the sibling
            #    set is derived from the records themselves, so every member is
            #    in `by_code`, and all 1,559 records carry one of exactly
            #    TERBUKA/TERTUTUP/TERBATAS), which is precisely why it would
            #    have survived: nothing exercises the branch that lies. A guard
            #    that cannot observe the fact must refuse, not assume it.
            not_open = [
                s for s in siblings if (by_code.get(s) or {}).get("pma_status") != "TERBUKA"
            ]
            if not_open:
                refusals.append(
                    f"{code}: spec says it leaves {not_open} open, but the dataset "
                    f"does not show them open — re-adjudicate, do not stack"
                )
                continue

            # 6. two independent adjudications, NAMED. One lane's word is not an
            #    adjudication, and the same lane written twice is one lane. This
            #    is the check the comment above used to claim `main()` performed.
            #    Compared on the SEAT, not on the whole string. The entries read
            #    "claude-sonnet-5 (proposer)" / "codex-gpt-5.6 (blind
            #    re-derivation)", and a set of whole strings would accept
            #    "claude-sonnet-5 (proposer)" alongside "claude-sonnet-5
            #    (grader)" — one model wearing two role labels, which is the
            #    thing this check exists to forbid. A second review found that
            #    the first version attested independence instead of enforcing
            #    it. The seat is everything before " (".
            lanes = {
                str(a).strip().split(" (")[0].strip().lower()
                for a in (item.get("agreed_by") or [])
                if str(a).strip()
            }
            if len(lanes) < 2:
                refusals.append(
                    f"{code}: split-heir identity is a judgment and needs two "
                    f"independent lanes in `agreed_by`, found {sorted(lanes) or 'none'}"
                )
                continue

        existing = record.get("pma_official_basis")
        if existing and existing != item["locator"]:
            refusals.append(f"{code}: already carries a different pma_official_basis")
            continue

        # Idempotent success is stricter than "the locator is already there":
        # every field owned by this compiler must match its intended patch.
        # Run this only AFTER the ancestry/split-heir guards above, so a later
        # structural drift is still a refusal even when the visible PMA fields
        # happen to look cured.
        target = patch_for(item)
        if all(record.get(key) == value for key, value in target.items()):
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

    already_applied = len(spec["items"]) - len(todo) - len(refusals)
    print(
        f"spec items {len(spec['items'])} · applicable {len(todo)} · "
        f"already applied {already_applied} · refused {len(refusals)}"
    )
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

    if not todo:
        print("\nalready applied — clean no-op; nothing written or propagated")
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
