#!/usr/bin/env python3
"""Overlay the 2026 Bali APPLIED PMA closure onto l4_bali (W-J B1, SAETTA-20260915).

WHAT THIS FIXES
---------------
The catalogue's Bali layer has, until now, derived every ``blocked`` verdict
from the OSS risk/scale tier alone (``resolve_kbli_l4_needs_review.py``): any
code whose Besar-scale risk sits in Rendah/Menengah-Rendah reads as blocked,
because the Governor's January 2026 REQUEST letter
(B.27.000/642/PM/DPMPTSP) asked BKPM to close OSS for every low/medium-low
risk PMA in Bali. That letter is a request, `Lampiran: -`, never itself an
instrument. What Bali PROVINCE actually did, per the Provincial Government's
own press release (24 Jul 2026) and the ANTARA Bali code list (23 Jul
2026), is close OSS for **18 named business fields** (KBLI 2020 numbering)
from the third week of May 2026, until further policy, with the Minister of
Investment/BKPM's approval — a much narrower set. Today's catalogue reads
~519 codes as blocked; the true applied closure touches 40 KBLI-2025 codes
(descended from the 18 via `bps_2020_ancestors`, never bare digits, never
`pp28_sources`).

WHAT THIS COMPILER DOES
------------------------
Reads ``data/kbli-filiera/bali-applied-closure-2026.json`` (emitted by
``emit_bali_applied_closure_spec.py`` — the guarded data plane forbids a
hand-edit of that file too) and re-derives, from the LIVE canonical's own
``bps_2020_ancestors.codes``, which 2025 codes descend from the 18-field
list — refusing the whole run if that derivation disagrees with the spec's
pinned ``expected_2025_codes`` (membership drift, never silently trusted).
For every code NOT owned by W-H's separate Perpres-49/2021 adjudication
(the 19 of #6488, ``excluded_codes`` below):

  1. On the 40 (regardless of current status) -> ``CHIUSO_BALI``,
     ``blocked=true``, a reason naming the press release + the KBLI-2020
     ancestor(s) actually on the list, and a ``closure`` object carrying the
     full provenance.
  2. Elsewhere, a record currently blocked purely by risk tier
     (``BLOCCATO_CLASSE_RISCHIO`` / ``CHIUSO_MORATORIA_BALI``) ->
     ``ATTENZIONE_FASCIA_BALI``, ``blocked=false`` — the tier alone never
     closed OSS; a real check on OSS is still owed. UNLESS (2b, added
     2026-09-15 SAETTA-20260915, Codex sol adversarial finding on #6597) the
     record ALSO carries a genuine national 0% cap (``pma_cap_special`` is
     not ``true`` and ``pma_status`` is ``TERTUTUP`` or ``pma_max_asing`` is
     ``0``) — a national cap is a non-tier reason to stay blocked, so that
     record instead follows the 47222 pattern (5, below): ``TERTUTUP``,
     ``blocked=true``, ``confidence=HIGH``, a field-derived
     ``tertutup_reason_fallback`` reason, never the tier/moratorium framing.
     Measured 2026-09-15: exactly 10214, 16221, 95220, 95299.
  3. A ``NON_CLASSIFICABILE`` record (blocked purely because the catalogue
     holds no licensing rows) -> stays ``NON_CLASSIFICABILE`` but
     ``blocked=false``, with a short appended note.
  4. Everything else (TERTUTUP, the regulator-closed pair, the four
     surviving ``CHIUSO_PMA_NO_BESAR`` codes outside W-H's 19, every
     non-blocked status) is untouched on every field but one — with one
     narrow exception (5).

That one field is ``l4_bali.moratorium`` — rewritten on ALL 1,559 records,
including the excluded 19: the OLD object asserted a blanket "ALL Low +
Medium-Low risk KBLI, island-wide, PERMANENT, 13 May 2026" rule that this
compiler exists to retire everywhere, not just on the codes whose verdict
changes.

  5. A single verified residual (47222, 2026-09-15): a TERTUTUP-status
     record whose ``reason`` is STILL the pre-B1 risk-tier/moratorium
     sentence (dated 13 May 2026) instead of a national-closure one. Fenced
     on the exact stale string (never a substring). The literal national
     closure sentence is written ONLY when the record's own ``pma_status``
     confirms ``TERTUTUP`` — checked live, not assumed, because some
     TERTUTUP-status records carry a non-TERTUTUP national ``pma_status``
     (47222 itself is TERBATAS/0% via a Perpres 49/2021 Lampiran II
     cooperative/UMKM reservation, not a blanket national closure); those
     get a distinct, still-accurate, field-derived sentence instead of the
     overclaiming one. See ``TERTUTUP_STALE_REASON`` /
     ``TERTUTUP_NATIONAL_REASON`` / ``tertutup_reason_fallback``.

``pma_status`` / ``pma_max_asing`` / ``pma_kondisi`` / ``per_skala`` are
never read for a write and never touched — this is the Bali overlay layer,
not the national ownership layer.

Usage:
    python scripts/kbli_filiera/cure_l4bali_applied_closure.py            # dry-run
    python scripts/kbli_filiera/cure_l4bali_applied_closure.py --check    # same report, never writes
    python scripts/kbli_filiera/cure_l4bali_applied_closure.py --apply
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

FILIERA_DIR = Path(__file__).resolve().parent
if str(FILIERA_DIR) not in sys.path:
    sys.path.insert(0, str(FILIERA_DIR))

import _hardened_cure_io as H  # noqa: E402
from _l4bali_basis import CODE_FIELD, derive_verdict_state  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
DEFAULT_SPEC = REPO_ROOT / "data" / "kbli-filiera" / "bali-applied-closure-2026.json"
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_kbli_dataset.sh"
SIDECAR_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-dataset-version.json"
SIDECAR_DATASET_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "KBLI_2025_FINAL_CLEAN.json"

EXIT_OK = 0
EXIT_REFUSED = 2

CureError = H.CureError

CHIUSO_BALI_STATUS = "CHIUSO_BALI"
ATTENZIONE_STATUS = "ATTENZIONE_FASCIA_BALI"
NON_CLASSIFICABILE_STATUS = "NON_CLASSIFICABILE"
ATTENZIONE_SOURCE_STATUSES = frozenset({"BLOCCATO_CLASSE_RISCHIO", "CHIUSO_MORATORIA_BALI"})

# The live `l4_bali.moratorium` shape (verified 2026-09-15 against the whole
# canonical: uniform across all 1,559 records) carries exactly these four
# keys; the new object adds three (`until`, `source_url`, `request`). Every
# one of the seven is a fresh diff leaf under `_hardened_cure_io._diff_paths`
# recursion (moratorium is a dict on both sides, so the walk descends into
# it instead of stopping at the parent key) — declare all seven, or a
# legitimate moratorium rewrite reads as an undeclared field change.
MORATORIUM_KEYS = ("rule", "effective", "until", "source", "source_url", "request", "virtual_office")
MORATORIUM_PATHS = frozenset(f"l4_bali.moratorium.{key}" for key in MORATORIUM_KEYS)

ATTENZIONE_REASON_TEMPLATE = (
    "Not among the 18 business fields Bali closed to new PMA licensing in 2026. "
    "The low/medium-low risk tier was named only in the Governor's January 2026 "
    "request letter ({request_id}); check the risk tier and zoning on OSS before filing."
)

# A residual: one TERTUTUP-status record (47222, verified 2026-09-15) still
# carries the OLD risk-tier/moratorium reason instead of an accurate
# national-closure sentence. Fenced on the EXACT stale string, never a
# substring match (scar family #3, guard-over-match) — a TERTUTUP record
# with any other reason is untouched.
TERTUTUP_STALE_REASON = (
    "OSS risk at scale Besar is Rendah/Menengah-Rendah on every scope → "
    "blocked by Bali moratorium 13 May 2026"
)
# The literal text this compiler is asked to write — ONLY when the record's
# OWN national `pma_status` confirms TERTUTUP (checked live, never assumed:
# some l4_bali.status=="TERTUTUP" records carry a national pma_status of
# TERBUKA or TERBATAS instead, a pre-existing mismatch this compiler does not
# adjudicate). Writing this exact sentence onto a TERBATAS/0%-via-Lampiran-II
# record would overclaim a blanket national closure it does not have.
TERTUTUP_NATIONAL_REASON = "Closed to foreign ownership at the national level (TERTUTUP/0%)."


def is_nationally_capped(record: dict[str, Any]) -> bool:
    """True when the record's own NATIONAL fields (not the Bali layer) already
    close it at 0% foreign ownership — a fact the tier->ATTENZIONE conversion
    (rule 2) must never override. ``pma_cap_special`` is the same escape hatch
    ``kbli-bali-block.test.ts``'s ``nationallyClosed`` predicate uses: a
    handful of records carry a 0% cap that is itself SPECIAL-CASED (e.g. a
    sector with its own regime), so it is excluded here on purpose, not an
    oversight. Added 2026-09-15 (SAETTA-20260915, Codex sol adversarial
    finding on #6597): the compiler used to un-block 10214/16221/95220/95299
    into ATTENZIONE_FASCIA_BALI purely because their `l4_bali.status` was tier-
    sourced, ignoring that all four are ALSO closed nationally (three by
    Perpres 49/2021 Lampiran II Koperasi/UMKM allocation, one by Lampiran III
    domestic-capital-only) — a national 0% cap is a non-tier, non-Bali reason
    to stay blocked, and reading it as "cleared by the tier test" was wrong
    regardless of what the tier test itself found."""
    if record.get("pma_cap_special") is True:
        return False
    status = (record.get("pma_status") or "").upper()
    max_asing = record.get("pma_max_asing")
    if max_asing is None:
        max_asing = 0
    return status == "TERTUTUP" or max_asing == 0


def tertutup_reason_fallback(record: dict[str, Any]) -> str:
    """Accurate, deterministic reason for a TERTUTUP-status record whose own
    `pma_status` is NOT literally TERTUTUP (e.g. 47222: TERBATAS, 0% via a
    Perpres 49/2021 Lampiran II cooperative/UMKM reservation — a national
    fact, not a Bali-specific one). Built only from the record's own fields,
    never invented prose."""
    pma_status = record.get("pma_status")
    max_asing = record.get("pma_max_asing")
    if isinstance(max_asing, (int, float)):
        ceiling_phrase = f"{max_asing}% max foreign ownership"
    else:
        ceiling_phrase = "no foreign-ownership ceiling recorded"
    source = record.get("pma_source") or "the national PMA ownership table"
    return f"Not a Bali-specific rule: nationally {pma_status} ({ceiling_phrase}), per {source}."

_MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _fmt_date(iso: str) -> str:
    """'2026-07-24' -> '24 Jul 2026' without a platform-specific strftime flag."""
    year, month, day = iso.split("-")
    return f"{int(day)} {_MONTHS[int(month)]} {year}"


def load_closure_spec(path: Path) -> dict[str, Any]:
    spec = json.loads(path.read_text(encoding="utf-8"))
    for key in ("eighteen", "expected_2025_codes", "excluded_codes", "moratorium", "sources", "effective", "until", "approval"):
        if key not in spec:
            raise CureError(f"{path}: missing required key {key!r}")
    if set(spec["moratorium"]) != set(MORATORIUM_KEYS):
        raise CureError(
            f"{path}: moratorium keys {sorted(spec['moratorium'])} != expected {sorted(MORATORIUM_KEYS)}"
        )
    return spec


def derive_forty(
    records_by_code: dict[str, dict[str, Any]], eighteen: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """2025-code -> {"ancestors_2020": [...], "matches": [...]} for every
    record carrying at least one KBLI-2020 ancestor on the 18-field list.

    ``ancestors_2020`` is the record's FULL ancestor set (this is what makes
    n_anc == 1 vs > 1 meaningful — a 2025 code can merge several KBLI-2020
    activities, only some of which are on the closure list); ``matches`` is
    the subset that is actually on the list.
    """
    out: dict[str, dict[str, Any]] = {}
    for code, record in records_by_code.items():
        ancestors = (record.get("bps_2020_ancestors") or {}).get("codes") or []
        matches = [c for c in ancestors if c in eighteen]
        if matches:
            out[code] = {"ancestors_2020": list(ancestors), "matches": matches}
    return out


def _ancestor_phrase(matches: list[str], eighteen: dict[str, Any]) -> str:
    parts = [f"{code} ({eighteen[code]['name']})" for code in matches]
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def chiuso_bali_reason(
    matches: list[str],
    ancestors_2020: list[str],
    eighteen: dict[str, Any],
    closure_spec: dict[str, Any],
) -> str:
    official = closure_spec["sources"]["official"]
    sentence = (
        "Closed to new PMA licensing in Bali: the Bali Provincial Government closed OSS "
        f"to foreign-owned companies for 18 business fields from the {closure_spec['effective']}, "
        f"{closure_spec['until']}, with the approval of the Minister of Investment/BKPM "
        f"(press release, {_fmt_date(official['published'])}). This code descends from KBLI 2020 "
        f"{_ancestor_phrase(matches, eighteen)} on that list (BPS KBLI 2020→2025 conversion table)."
    )
    if any(eighteen[code].get("scope_qualifier") for code in matches):
        sentence += " The list limits it to buildings under 6,000 m²."
    if len(ancestors_2020) > 1:
        sentence += (
            " This 2025 code also merges KBLI 2020 activities that are not on the list; "
            "the closure is applied to the whole code as a conservative reading."
        )
    return sentence


def chiuso_bali_closure_object(
    matches: list[str],
    ancestors_2020: list[str],
    eighteen: dict[str, Any],
    closure_spec: dict[str, Any],
) -> dict[str, Any]:
    official = closure_spec["sources"]["official"]
    code_list = closure_spec["sources"]["code_list"]
    scope_qualifier = None
    for code in matches:
        sq = eighteen[code].get("scope_qualifier")
        if sq:
            scope_qualifier = sq
            break
    return {
        "instrument": official["instrument"],
        "published": official["published"],
        "url": official["url"],
        "list_source": code_list["source"],
        "list_url": code_list["url"],
        "effective": closure_spec["effective"],
        "until": closure_spec["until"],
        "approval": closure_spec["approval"],
        "ancestors_2020": list(ancestors_2020),
        "scope_qualifier": scope_qualifier,
    }


def non_classificabile_note(closure_spec: dict[str, Any]) -> str:
    official = closure_spec["sources"]["official"]
    return (
        " Not among the 18 business fields Bali closed to new PMA licensing in 2026 "
        f"(Bali Provincial Government press release, {_fmt_date(official['published'])}); "
        "no longer read as blocked absent that closure."
    )


def touched_paths_for(group: str) -> frozenset[str]:
    if group == "chiuso_bali":
        extra = {
            "l4_bali.status",
            "l4_bali.blocked",
            "l4_bali.needs_review",
            "l4_bali.confidence",
            "l4_bali.reason",
            "l4_bali.closure",
            "l4_bali.verdict_state",
        }
    elif group == "attenzione":
        extra = {
            "l4_bali.status",
            "l4_bali.blocked",
            "l4_bali.reason",
            "l4_bali.needs_review",
            "l4_bali.verdict_state",
        }
    elif group == "tertutup_national_cap":
        extra = {
            "l4_bali.status",
            "l4_bali.blocked",
            "l4_bali.reason",
            "l4_bali.needs_review",
            "l4_bali.confidence",
            "l4_bali.verdict_state",
        }
    elif group == "non_classificabile":
        extra = {"l4_bali.blocked", "l4_bali.reason", "l4_bali.verdict_state"}
    elif group == "tertutup_reason":
        extra = {"l4_bali.reason"}
    else:
        extra = set()
    return frozenset(extra | MORATORIUM_PATHS)


def plan(records: list[dict[str, Any]], closure_spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return the per-code group/target/changed plan, or refuse the whole run."""
    by_code: dict[str, dict[str, Any]] = {}
    for record in records:
        code = str(record.get(CODE_FIELD) or "")
        if not code:
            raise CureError("canonical record without kode_kbli_2025")
        if code in by_code:
            raise CureError(f"duplicate canonical code {code!r}")
        by_code[code] = record

    eighteen = closure_spec["eighteen"]
    expected = set(closure_spec["expected_2025_codes"])
    excluded = set(closure_spec["excluded_codes"]["codes"])

    missing_excluded = excluded - set(by_code)
    if missing_excluded:
        raise CureError(f"excluded codes not present in canonical: {sorted(missing_excluded)}")

    forty = derive_forty(by_code, eighteen)
    derived_codes = set(forty)
    if derived_codes != expected:
        raise CureError(
            "membership drift — bps_2020_ancestors-derived 2025 codes disagree with the "
            f"pinned expected_2025_codes: missing={sorted(expected - derived_codes)}, "
            f"extra={sorted(derived_codes - expected)}"
        )
    overlap = derived_codes & excluded
    if overlap:
        raise CureError(f"code(s) in both the 40 and the excluded 19: {sorted(overlap)}")

    new_moratorium = closure_spec["moratorium"]

    plans: dict[str, dict[str, Any]] = {}
    for code, record in by_code.items():
        l4 = record.get("l4_bali")
        if not isinstance(l4, dict):
            raise CureError(f"{code}: l4_bali missing or not an object")
        current_status = l4.get("status")
        current_blocked = l4.get("blocked")

        if code in forty:
            group = "chiuso_bali"
            matches = forty[code]["matches"]
            ancestors_2020 = forty[code]["ancestors_2020"]
            confidence = "HIGH" if len(ancestors_2020) == 1 else "MEDIUM"
            target: dict[str, Any] = {
                "status": CHIUSO_BALI_STATUS,
                "blocked": True,
                "needs_review": False,
                "confidence": confidence,
                "reason": chiuso_bali_reason(matches, ancestors_2020, eighteen, closure_spec),
                "closure": chiuso_bali_closure_object(matches, ancestors_2020, eighteen, closure_spec),
                "moratorium": new_moratorium,
            }
        elif code in excluded:
            group = "excluded"
            target = {"moratorium": new_moratorium}
        elif (
            current_blocked is True
            and current_status in ATTENZIONE_SOURCE_STATUSES
            and is_nationally_capped(record)
        ):
            # 2b (2026-09-15, Codex sol finding on #6597): the tier alone
            # never closed OSS, but a national 0% cap did — this record
            # follows the 47222 pattern instead of the plain ATTENZIONE one
            # below, so it stays blocked for the fact that actually blocks
            # it.
            group = "tertutup_national_cap"
            target = {
                "status": "TERTUTUP",
                "blocked": True,
                "needs_review": False,
                "confidence": "HIGH",
                "reason": tertutup_reason_fallback(record),
                "moratorium": new_moratorium,
            }
        elif current_blocked is True and current_status in ATTENZIONE_SOURCE_STATUSES:
            group = "attenzione"
            target = {
                "status": ATTENZIONE_STATUS,
                "blocked": False,
                "needs_review": True,
                "reason": ATTENZIONE_REASON_TEMPLATE.format(
                    request_id=closure_spec["sources"]["request_letter"]["id"]
                ),
                "moratorium": new_moratorium,
            }
        elif current_blocked is True and current_status == NON_CLASSIFICABILE_STATUS:
            group = "non_classificabile"
            base_reason = str(l4.get("reason") or "")
            target = {
                "blocked": False,
                "reason": base_reason + non_classificabile_note(closure_spec),
                "moratorium": new_moratorium,
            }
        elif current_status == "TERTUTUP" and l4.get("reason") == TERTUTUP_STALE_REASON:
            group = "tertutup_reason"
            new_reason = (
                TERTUTUP_NATIONAL_REASON
                if record.get("pma_status") == "TERTUTUP"
                else tertutup_reason_fallback(record)
            )
            target = {"reason": new_reason, "moratorium": new_moratorium}
        else:
            group = "passthrough"
            target = {"moratorium": new_moratorium}

        if group in ("chiuso_bali", "attenzione", "tertutup_national_cap", "non_classificabile"):
            working = copy.deepcopy(record)
            working_l4 = working["l4_bali"]
            working_l4.update({key: value for key, value in target.items() if key != "moratorium"})
            try:
                target["verdict_state"] = derive_verdict_state(working)
            except ValueError as exc:
                raise CureError(f"{code}: cannot re-derive verdict_state: {exc}") from exc

        changed = (l4.get("moratorium") != target["moratorium"]) or any(
            l4.get(key) != value for key, value in target.items() if key != "moratorium"
        )
        plans[code] = {"group": group, "target": target, "changed": changed}

    return plans


def _status_blocked_counter(records: list[dict[str, Any]]) -> Counter:
    counter: Counter = Counter()
    for record in records:
        l4 = record.get("l4_bali") or {}
        counter[(l4.get("status"), l4.get("blocked"))] += 1
    return counter


def _census_after(records: list[dict[str, Any]], plans: dict[str, dict[str, Any]]) -> Counter:
    by_code = {str(r.get(CODE_FIELD)): r for r in records}
    counter: Counter = Counter()
    for code, item in plans.items():
        l4 = by_code[code].get("l4_bali") or {}
        status = item["target"].get("status", l4.get("status"))
        blocked = item["target"].get("blocked", l4.get("blocked"))
        counter[(status, blocked)] += 1
    return counter


def _print_counter(label: str, counter: Counter) -> None:
    print(f"{label}:")
    total_blocked = sum(c for (_, blocked), c in counter.items() if blocked is True)
    print(f"  TOTAL blocked=True: {total_blocked}")
    for (status, blocked), count in sorted(counter.items(), key=lambda kv: (-kv[1], str(kv[0]))):
        print(f"  {status!s:30} blocked={blocked!s:5} {count}")


def run_sync_script() -> None:
    result = subprocess.run(
        ["bash", str(SYNC_SCRIPT), "sync"], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode != 0:
        raise CureError(f"sync_kbli_dataset.sh sync failed with exit {result.returncode}")


def update_sidecar() -> None:
    if not SIDECAR_DATASET_PATH.exists():
        raise CureError(f"sidecar dataset copy missing: {SIDECAR_DATASET_PATH} (sync must run first)")
    digest = "sha256:" + hashlib.sha256(SIDECAR_DATASET_PATH.read_bytes()).hexdigest()
    sidecar = json.loads(SIDECAR_PATH.read_text(encoding="utf-8"))
    sidecar["datasetSha256"] = digest
    sidecar["lastModified"] = date.today().isoformat()
    H.atomic_write_text(SIDECAR_PATH, json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n")
    print(f"sidecar datasetSha256 -> {digest}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="write; default is dry-run")
    parser.add_argument(
        "--check", action="store_true", help="alias for dry-run — never writes (report-only, exit 0)"
    )
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    args = parser.parse_args(argv)

    try:
        closure_spec = load_closure_spec(args.spec)
        payload, records, original = H.load_dataset(args.canonical)
        plans = plan(records, closure_spec)
    except (OSError, json.JSONDecodeError, CureError) as exc:
        print(f"REFUSED: {exc}")
        return EXIT_REFUSED

    mode = "APPLY" if args.apply else ("CHECK" if args.check else "DRY-RUN")
    print(f"cure_l4bali_applied_closure.py — mode={mode}")
    _print_counter("before", _status_blocked_counter(records))
    groups = Counter(item["group"] for item in plans.values())
    to_patch = {code: item for code, item in plans.items() if item["changed"]}
    changed_groups = Counter(item["group"] for item in to_patch.values())
    print(f"plan: {len(to_patch)} record(s) to patch of {len(plans)}")
    for group in (
        "chiuso_bali",
        "attenzione",
        "tertutup_national_cap",
        "non_classificabile",
        "tertutup_reason",
        "excluded",
        "passthrough",
    ):
        print(f"  {group:20} total={groups[group]:5} to_patch={changed_groups[group]:5}")
    _print_counter("after", _census_after(records, plans))

    if not args.apply:
        print("dry-run — no files written; rerun with --apply to write")
        return EXIT_OK
    if not to_patch:
        print("nothing to patch")
        return EXIT_OK

    before_records = copy.deepcopy(records)
    by_code = {str(r.get(CODE_FIELD)): r for r in records}
    for code, item in to_patch.items():
        l4 = by_code[code]["l4_bali"]
        for key, value in item["target"].items():
            l4[key] = value

    try:
        H.verify_untouched(
            before_records,
            records,
            CODE_FIELD,
            touched_codes=set(to_patch),
            touched_field_paths={code: set(touched_paths_for(item["group"])) for code, item in to_patch.items()},
        )
    except CureError as exc:
        print(f"REFUSED (untouched fields): {exc}")
        return EXIT_REFUSED

    body = json.dumps(payload, ensure_ascii=False, indent=2)
    H.atomic_write_text(args.canonical, body + ("\n" if original.endswith("\n") else ""))

    try:
        _, reread, _ = H.load_dataset(args.canonical)
        reread_by_code = {str(r.get(CODE_FIELD)): r for r in reread}
        wrong = [
            code
            for code, item in to_patch.items()
            if any(reread_by_code[code]["l4_bali"].get(key) != value for key, value in item["target"].items())
        ]
        if wrong:
            raise CureError(f"write read-back mismatch on {wrong[:10]}")
        print(f"applied and verified on re-read: {len(to_patch)} code(s)")
        if args.canonical.resolve() == DEFAULT_CANONICAL.resolve():
            run_sync_script()
            update_sidecar()
            print("consumer copies synced; sidecar SHA updated")
        else:
            print("custom canonical fixture — consumer sync and sidecar update skipped")
    except (OSError, json.JSONDecodeError, CureError) as exc:
        print(f"REFUSED after canonical write: {exc}")
        return EXIT_REFUSED
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
