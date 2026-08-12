#!/usr/bin/env python3
"""The NEGATIVE locator: what the Perpres body says about a code no annex names.

WHAT THIS IS, AND WHY IT IS THE BIGGEST GAP ON THE PMA AXIS
-----------------------------------------------------------
Third and last reader of the Daftar Positif Investasi, after
`perpres_umkm_reservation_relation.py` (Lampiran II) and
`perpres_foreign_cap_relation.py` (Lampiran III). Those two speak for the codes
a RESTRICTING annex names — 271 of 1,559 once the 2020->2025 crosswalk is
honoured. This module speaks for the rest, which is the block that until now
carried `pma_source: "Perpres 10/2021, 49/2021"` with **no article behind it**:
a blanket attribution, not a locator. The navigator's north star is that every
rendered PMA fact is either government-sourced with a citable locator or an
honest declared gap. For most of the catalogue this file is that locator.

Measured: 175 codes are `Bidang Usaha Prioritas` (Pasal 3(1)(a)), 274 are named
by a restricting annex or the body, and **1,110 are genuinely residual**.

TWO THINGS AN INDEPENDENT LEGAL REVIEW CORRECTED BEFORE THIS SHIPPED
---------------------------------------------------------------------
Both were caught by a cross-family reviewer reading the article text, not by
any test here — recorded because the same two errors are easy to make again:

1. **Lampiran I was omitted**, so "named by nothing" quietly included category
   (a). 175 codes were being cited under **Pasal 3(1)(d)** — the residual
   article — when they fall under **huruf a**. No ownership verdict was wrong
   (priority incentivises, it never restricts), but the locator was, and the
   locator is this module's whole product: reproducing the blanket-attribution
   defect one annex to the left. `parse_perpres_lampiran1.py` closes it.
2. **Pasal 7(1) is not a bar on the ACTIVITY.** See `pasal7_review_flags` — the
   first version asserted that a code with no Besar row is one a PMA "may not
   operate at all", which the article does not say and `per_skala` cannot
   establish. It is a review queue, not a verdict.

THE BODY, READ RATHER THAN ASSUMED (vault 154474 + 161562)
-----------------------------------------------------------
`Perpres 10/2021` as amended by `49/2021`. What 49/2021 actually changes, read
off its own Pasal I: item 1 = Pasal 2, item 2 = Pasal 6, items 3/4/5 = the three
lampiran. **Pasal 3 and Pasal 7 are untouched**, which matters because both legs
of this join hang off them:

* **Pasal 3 ayat (1) huruf d + ayat (2)** — the residual category, "Bidang
  Usaha yang tidak termasuk dalam huruf a, huruf b, dan huruf c", and it "dapat
  diusahakan oleh semua Penanam Modal". THIS is the default that makes a
  100%-open verdict lawful for an unnamed code. It is not folklore.
* **Pasal 7 ayat (1)** — "Penanam Modal asing **hanya dapat** melakukan kegiatan
  usaha pada **Usaha Besar** dengan nilai investasi lebih dari
  Rp10.000.000.000,00 di luar nilai tanah dan bangunan." This conditions the
  INVESTOR and its project, not the activity: it can stop a particular PMA that
  cannot qualify as large, but it does not make an activity closed to foreign
  investment. Combined with our OSS scale data it yields a REVIEW QUEUE — 23
  codes published open whose `per_skala` shows no Besar row — never a verdict.

TWO MORE OPERATIVE LISTS LIVE IN THE BODY, NOT IN AN ANNEX
-----------------------------------------------------------
"Absent from both annexes" is NOT the same as "residual", and reading it that
way would hand six codes a default they do not have:

* **Pasal 2 ayat (2) huruf b** (inserted by 49/2021): `11010`, `11020`, `11031`
  — the three alcohol INDUSTRIES, tertutup by name, in the body.
* **Pasal 6 ayat (3a)** (inserted by 49/2021): `46333`, `47221`, `47826` — the
  alcohol TRADE codes under "persyaratan Penanaman Modal lainnya", a fourth
  regime that is deliberately not a percentage and not in Lampiran III.

They are hard-coded here with their article rather than regex-scraped, because
the body's text layer carries the same deterministic corruption as the annexes
(`KBLI a6333` for 46333, `KBLr 1 1031` for 11031) — a grep for the literal
"KBLI" silently undercounts. The test suite pins them against the PDF instead.

THE CROSSWALK IS LOAD-BEARING, AND IT IS ALSO NOT ADJUDICATED
--------------------------------------------------------------
The annexes speak KBLI 2020; the catalogue is KBLI 2025. Joining on identity
alone finds 169 codes — the crosswalk finds **271**. The 102-code difference is
entirely codes that would otherwise be declared residual-and-open while their
2020 predecessor sits in a restriction annex, which is the dangerous direction:
a missed restriction reads to a client as freedom the law does not grant.

Declared, not laundered: every `bps_2020_ancestors` block says
`adjudication_status: "mechanical-only"` / `inheritance_verdict:
"not-adjudicated"`, and **221 records have no crosswalk at all**. A residual
verdict reached through an unadjudicated crosswalk carries that provenance in
its bucket name; it is not upgraded to certainty by passing through this file.

IT REPORTS, IT DOES NOT DECIDE — AND IT WRITES NOTHING
-------------------------------------------------------
`--check` exits 0 while divergences exist, like both siblings. Whether a
no-Besar row should re-label a live client-facing page is a legal reading
reserved to the owner (Legge 5), and any third state must be a SEPARATE axis
rather than a new `pma_status` value: `apps/mouth/src/lib/kbli-data.server.ts`
returns "open" for anything that is not TERBATAS/TERTUTUP, so inventing an enum
member would render as "open" on all 1,559 pages.

THE ARTIFACT, AND WHY THIS FILE CHANGED ITS MIND ABOUT EMITTING ONE
--------------------------------------------------------------------
It first said "no output file either — persisting this join would create a
fourth source of truth that goes stale the moment any input moves (W88/W106)".
That objection was about STALENESS, and `--emit` answers it rather than ignores
it: `--check-artifact` recomputes the join from the instrument and fails if the
file on disk differs, so the artifact cannot drift in silence — the same shape
`parse_perpres_lampiran1.py` uses for its own output.

What forced the change is the rule against two writers of one field. The page
must cite the article, and the alternative was re-deriving the precedence
(body -> restricting annex -> priority -> residual) a second time in TypeScript.
Two implementations of one rule diverge; one implementation plus a pinned
artifact does not. So `apps/mouth/data/perpres-locators.json` is emitted here,
by the module that owns the rule, and `apps/mouth` only reads it.

The report itself still writes nothing: `--check` and `--json` are pure.

DECLARED LIMITS — the regime this speaks for
---------------------------------------------
A NEW investment, under the general regime, outside a KEK. The body itself
carves out: **Pasal 8 ayat (1)** (Lampiran III does not apply inside a kawasan
ekonomi khusus, and 8(2) lets tech start-ups there invest at or below 10 miliar,
i.e. the Pasal 7 floor moves), and **Pasal 6 ayat (4)** (the foreign-cap
requirement does not bind investments already approved before the Perpres, nor
investors holding treaty privileges). None of those are visible in a KBLI record,
so this module cannot and does not decide them.

Usage:
    python scripts/kbli_filiera/perpres_body_default_relation.py --check [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Sibling-module import: same sys.path pattern every compiler in this
# directory uses. The set we need lives in the slice-disclosure module
# because that is where the foreign-cap adjudication's
# adjacent-not-contained verdict is already written down (W105).
_FILIERA_DIR = Path(__file__).resolve().parent
if str(_FILIERA_DIR) not in sys.path:
    sys.path.insert(0, str(_FILIERA_DIR))

from perpres_slice_disclosure_relation import ADJACENT_NOT_CONTAINED  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
UMKM = REPO_ROOT / "data" / "kbli-filiera" / "perpres-umkm-reservation.json"
CAPS = REPO_ROOT / "data" / "kbli-filiera" / "perpres-foreign-caps.json"
PRIORITY = REPO_ROOT / "data" / "kbli-filiera" / "perpres-priority-codes.json"
SECTOR_LAW_CARVEOUT = REPO_ROOT / "data" / "kbli-filiera" / "sector-law-carveout.json"

EXIT_OK, EXIT_DIFFERS, EXIT_CANNOT_VERIFY = 0, 1, 4

INSTRUMENT = "Perpres 10/2021 as amended by Perpres 49/2021"

# Verbatim from the body. See the module docstring for why these are constants
# and not a regex over a corrupted text layer.
BODY_TERTUTUP: dict[str, str] = {
    "11010": "Pasal 2 ayat (2) huruf b — Industri Minuman Keras Mengandung Alkohol",
    "11020": "Pasal 2 ayat (2) huruf b — Industri Minuman Mengandung Alkohol: Anggur",
    "11031": "Pasal 2 ayat (2) huruf b — Industri Minuman Mengandung Malt",
}
BODY_OTHER_REQUIREMENT: dict[str, str] = {
    "46333": "Pasal 6 ayat (3a) huruf a — Perdagangan Besar Minuman Keras/Beralkohol",
    "47221": "Pasal 6 ayat (3a) huruf b — Perdagangan Eceran Minuman Keras atau Beralkohol",
    "47826": "Pasal 6 ayat (3a) huruf c — Perdagangan Eceran Kaki Lima Minuman Keras",
}

RESIDUAL_BASIS = "Pasal 3 ayat (1) huruf d + ayat (2)"
PRIORITY_BASIS = "Pasal 3 ayat (1) huruf a"
BESAR_BASIS = "Pasal 7 ayat (1)"

# 2026-08-08 fix-pack item G: six insurance/reinsurance codes absent from
# every annex for a DIFFERENT reason than the residual default — Pasal 11(2)
# routes financial/banking bidang usaha to sector law instead. Declared in
# its own file (see write_sector_law_carveout.py's docstring for why) rather
# than a third hardcoded dict beside BODY_TERTUTUP/BODY_OTHER_REQUIREMENT.
SECTOR_LAW_CARVEOUT_BASIS = "Pasal 11 ayat (2)"
SECTOR_LAW_CARVEOUT_CITE = (
    "Perpres 10/2021 Pasal 11(2) — financial/banking business fields follow "
    "their own sector legislation"
)

# The scale a foreign investor must reach, spelled as the catalogue spells it.
BESAR = "Besar"


class CannotVerify(Exception):
    """An input is missing or empty. Never degrade to 'everything is residual'."""


def load_canonical(path: Path = CANONICAL) -> dict[str, dict]:
    records = json.loads(path.read_text())["data"]
    if not records:
        raise CannotVerify(f"{path} carries no records")
    return {str(rec["kode_kbli_2025"]): rec for rec in records}


def annex_codes(umkm_path: Path = UMKM, caps_path: Path = CAPS) -> tuple[set[str], set[str]]:
    """The KBLI-2020 codes each operative annex names.

    An EMPTY annex is a hard failure, not an empty set. This whole module asks
    "is the code absent from the annexes?", so a missing input would make every
    one of the 1,559 look residual and the report would read "all open by
    default" — maximally wrong and maximally confident. The empty set disguises
    itself as both everything and nothing; here it must speak.
    """
    for path in (umkm_path, caps_path):
        if not path.is_file():
            raise CannotVerify(
                f"{path} missing — run: python scripts/kbli_filiera/parse_perpres_lampiran2.py --write"
            )
    umkm = {str(row["code"]) for row in json.loads(umkm_path.read_text())["rows"] if row.get("code")}
    caps = {str(row["kbli_2020"]) for row in json.loads(caps_path.read_text())["rows"] if row.get("kbli_2020")}
    if not umkm or not caps:
        raise CannotVerify(f"an annex yielded no codes (Lampiran II: {len(umkm)}, Lampiran III: {len(caps)})")
    return umkm, caps


def priority_codes(path: Path = PRIORITY) -> set[str]:
    """The Lampiran I codes — `Bidang Usaha Prioritas`, Pasal 3 ayat (1) huruf a.

    Priority membership INCENTIVISES, it never restricts, so it changes no
    ownership verdict. It is read here for one reason: a priority code is
    category (a), so citing Pasal 3(1)(d) for it would attribute a code to an
    article it does not fall under — the blanket-attribution defect this module
    exists to close, reproduced one annex to the left. An independent
    legal-reading review caught the omission before it shipped.
    """
    if not path.is_file():
        raise CannotVerify(
            f"{path} missing — run: python scripts/kbli_filiera/parse_perpres_lampiran1.py --write"
        )
    codes = {str(c) for c in json.loads(path.read_text()).get("codes") or []}
    if not codes:
        raise CannotVerify(f"{path} names no codes; the residual bucket would absorb category (a)")
    return codes


def sector_law_carveout_codes(path: Path = SECTOR_LAW_CARVEOUT) -> set[str]:
    """The declared sector-law carve-out set (item G, 2026-08-08 fix-pack).

    Missing/empty is a hard failure, same reasoning as `annex_codes` and
    `priority_codes`: silently treating it as empty would fall these six
    codes straight through to the residual bucket, re-citing Pasal 3(1)(d)
    for a code Pasal 11(2) already routed elsewhere — the exact defect this
    step exists to close.
    """
    if not path.is_file():
        raise CannotVerify(
            f"{path} missing — run: python scripts/kbli_filiera/write_sector_law_carveout.py --write"
        )
    codes = {str(c) for c in json.loads(path.read_text()).get("codes") or []}
    if not codes:
        raise CannotVerify(f"{path} names no codes")
    return codes


def ancestors(record: dict) -> set[str]:
    """The record's KBLI-2020 predecessors, or an empty set when it has none.

    `bps_2020_ancestors` is a DICT carrying a `codes` list plus provenance — not
    a list of codes. Reading it as a list yields an empty set for every record
    and the join silently finds nothing, which is how a probe measures its own
    breakage and reports it as a clean catalogue.
    """
    block = record.get("bps_2020_ancestors") or {}
    codes = block.get("codes") or []
    if isinstance(codes, str):  # a bare string iterates into CHARACTERS, not codes
        raise CannotVerify(f"bps_2020_ancestors.codes is a string, not a list: {codes!r}")
    return {str(code) for code in codes if code}


def has_crosswalk(record: dict) -> bool:
    return bool(record.get("bps_2020_ancestors"))


def scales(record: dict) -> set[str]:
    """Every business scale named across the record's `per_skala` entries.

    `skala_usaha` is a LIST on each entry (`["Mikro"]`), never a string.
    """
    out: set[str] = set()
    for entry in record.get("per_skala") or []:
        named = entry.get("skala_usaha") or []
        if isinstance(named, str):  # ditto: "Besar" would become {"B","e","s","a","r"}
            raise CannotVerify(f"skala_usaha is a string, not a list: {named!r}")
        out.update(named)
    return out


def besar_state(record: dict) -> str:
    """What the OSS licensing data says about this activity's scales — 3 states.

    NOT a legal verdict, and the naming here is deliberate after an independent
    legal-reading review (Codex, cross-family) refuted the first version.
    `per_skala` is a risk-based LICENSING interface artifact: it records which
    scale rows OSS publishes. "OSS publishes no Besar row" is not the same fact
    as "this activity cannot lawfully be conducted at Besar scale", and only the
    second would combine with Pasal 7(1) into a bar. See `pasal7_review_flags`.

    THREE states, never two. An ABSENT `per_skala` is not an observed absence of
    Besar: 217 records carry no scale data at all (the OSS ruang-lingkup 404s),
    and collapsing them would report a gap in OUR data as a fact about the world
    — which is exactly what 17 of the Bali overlay's closures already do.
    """
    named = scales(record)
    if not named:
        return "unobserved"
    return "observed" if BESAR in named else "absent"


def locate(code: str, record: dict, umkm: set[str], caps: set[str],
           priority: set[str],
           adjacent_not_contained: set[str] = frozenset()) -> dict:
    """EVERY locator that names this code, not just the strongest one.

    A code can be named twice — `47221` is under Pasal 6(3a) in the body and
    reaches Lampiran II through its 2020 ancestor `47911`. Returning only the
    winning locator would make the second invisible to whoever reads the row.

    For codes the foreign-cap adjudication marks `ADJACENT_NOT_CONTAINED`, an
    ancestor-mediated Lampiran III hit is NOT treated as naming the code: the
    adjudication itself says the annex activity is a neighbour in the same
    ancestor family, not a slice inside this code. The exclusion is scoped to
    Lampiran III only — Lampiran I priority and Lampiran II UMKM hits keep
    flowing through normally.
    """
    reach = {code} | ancestors(record)
    # Scope the exclusion to ancestor-mediated Lampiran III hits. A code named
    # by Lampiran III under its OWN 2025 number is unaffected (none of the
    # current exclusions are in that situation, but the guard is honest).
    if code in adjacent_not_contained:
        effective_caps = caps - ancestors(record)
    else:
        effective_caps = caps
    restricting = umkm | effective_caps
    return {
        "body": BODY_TERTUTUP.get(code) or BODY_OTHER_REQUIREMENT.get(code),
        "lampiran_i": sorted(reach & priority),
        "lampiran_ii": sorted(reach & umkm),
        "lampiran_iii": sorted(reach & effective_caps),
        "via_ancestor_only": bool((reach & restricting) and code not in restricting),
        "crosswalk": "absent" if not has_crosswalk(record) else "mechanical-only",
    }


def classify(code: str, record: dict, umkm: set[str], caps: set[str],
             priority: set[str], sector_law_carveout: set[str] = frozenset(),
             adjacent_not_contained: set[str] = frozenset()) -> tuple[str, dict]:
    """Locate one code against the instrument. Returns (bucket, evidence).

    Order is load-bearing. The BODY names a code before any annex does; among
    the annexes the RESTRICTING ones are read before the incentivising one, so a
    code that is both priority and reserved reports as reserved. And being named
    anywhere — including Lampiran I — excludes the residual category by the
    plain words of Pasal 3 ayat (1) huruf d ("tidak termasuk dalam huruf a,
    huruf b, dan huruf c").
    """
    evidence = locate(code, record, umkm, caps, priority, adjacent_not_contained)
    evidence["besar"] = besar_state(record)
    evidence["besar_basis"] = BESAR_BASIS
    evidence["scales"] = sorted(scales(record))

    in_carveout = code in sector_law_carveout
    if in_carveout:
        # DISJOINTNESS INVARIANT (item G): the carve-out set is declared
        # against Pasal 11(2), a routing rule independent of every annex and
        # the body-level lists above. Today the two are disjoint by
        # construction (none of the six insurance codes is named by any
        # annex or the body) — if that ever stops being true, the precedence
        # below would silently let the annex/body branch win and the
        # carve-out would never be reported, hiding a real conflict between
        # two adjudications. Raise instead of choosing one silently.
        named_elsewhere = bool(
            code in BODY_TERTUTUP
            or code in BODY_OTHER_REQUIREMENT
            or evidence["lampiran_ii"]
            or evidence["lampiran_iii"]
            or evidence["lampiran_i"]
        )
        if named_elsewhere:
            raise CannotVerify(
                f"{code}: declared as a Pasal 11(2) sector-law carve-out but "
                "ALSO named by an annex or the body — the carve-out set is "
                "supposed to be disjoint from those; re-derive both "
                "adjudications before trusting either"
            )

    # `basis` is set on EVERY path. The two body branches used to return without
    # it, which nothing noticed until a consumer read the field — the report
    # printed bucket names and never touched it. A key that only some branches
    # populate is a KeyError waiting for its first reader.
    if code in BODY_TERTUTUP:
        evidence["basis"] = BODY_TERTUTUP[code]
        return "body-tertutup", evidence
    if code in BODY_OTHER_REQUIREMENT:
        evidence["basis"] = BODY_OTHER_REQUIREMENT[code]
        return "body-other-requirement", evidence
    if evidence["lampiran_ii"] or evidence["lampiran_iii"]:
        evidence["basis"] = "Pasal 3 ayat (1) huruf b / huruf c"
        return "named-in-annex", evidence
    if evidence["lampiran_i"]:
        # Priority INCENTIVISES and restricts nothing, so no ownership verdict
        # moves — but the code is category (a), and citing (d) for it would be
        # the blanket attribution this module exists to end.
        evidence["basis"] = PRIORITY_BASIS
        return "priority-lampiran-i", evidence
    if in_carveout:
        # Precedence BEFORE the residual bucket: Pasal 11(2) is the reason
        # these six are absent from every annex, not the residual-open
        # default — citing Pasal 3(1)(d) for them would be the same
        # blanket-attribution defect this whole module exists to end, one
        # article further down the precedence chain.
        evidence["basis"] = SECTOR_LAW_CARVEOUT_BASIS
        return "sector-law-carveout", evidence

    # Residual by Pasal 3(1)(d)+(2) — genuinely residual only now that (a), (b)
    # and (c) have all been asked.
    evidence["basis"] = RESIDUAL_BASIS
    return f"residual-besar-{evidence['besar']}", evidence


def body_codes_absent_from_catalogue(canonical: dict[str, dict]) -> list[str]:
    """Body-named codes the 2025 catalogue does not carry.

    Measured: `11031` (Industri Minuman Mengandung Malt) and `47826`
    (Perdagangan Eceran Kaki Lima Minuman Keras) are named by the body and are
    NOT in the 1,559 — 47826 survives as a 2020 ancestor of `47221`. A
    hard-coded list whose members quietly fail to exist is the phantom-code
    class; this reports them instead of absorbing them.
    """
    return sorted(c for c in (BODY_TERTUTUP | BODY_OTHER_REQUIREMENT) if c not in canonical)


OVERLAY_STATUS = "CHIUSO_PMA_NO_BESAR"


def overlay_reconciliation(canonical: dict[str, dict]) -> dict:
    """Where the Bali overlay's OWN Pasal 7(1) reading agrees with the evidence.

    `l4_bali.status` already carries `CHIUSO_PMA_NO_BESAR` on 39 codes, so the
    organism has taken this reading before — the question is whether it took it
    on evidence. Measured, the same rule is misapplied in BOTH directions:

    * **17 closures rest on an EMPTY `per_skala`** — a code with no scale data
      is not a code observed to lack Besar, and closing on it turns a gap in our
      data into a bar in the law.
    * **`93114` (Fasilitas Lapangan) is left `APERTO`** while its own scale data
      names no Besar row — the evidence the overlay accepts on 22 other codes.

    The rule is not the disease; the selector is. Reported, never applied: which
    way each of those moves is the owner's reading (Legge 5).
    """
    closed = {c for c, r in canonical.items() if (r.get("l4_bali") or {}).get("status") == OVERLAY_STATUS}
    absent = {c for c, r in canonical.items() if besar_state(r) == "absent"}
    unobserved = {c for c, r in canonical.items() if besar_state(r) == "unobserved"}
    return {
        "overlay_closed": len(closed),
        "corroborated_by_scales": sorted(closed & absent),
        "closed_on_empty_scales": sorted(closed & unobserved),
        "closed_with_a_besar_row": sorted(closed - absent - unobserved),
        "absent_besar_not_closed": [
            {"code": c, "l4_bali": (canonical[c].get("l4_bali") or {}).get("status"),
             "pma_status": canonical[c].get("pma_status")}
            for c in sorted(absent - closed)
        ],
    }


def published(record: dict) -> dict:
    return {
        "pma_status": record.get("pma_status"),
        "pma_max_asing": record.get("pma_max_asing"),
        "judul": record.get("judul"),
    }


def report(canonical: dict[str, dict], umkm: set[str], caps: set[str],
           priority: set[str], sector_law_carveout: set[str] = frozenset()) -> dict:
    # The single source of the adjacent-not-contained verdict. Using the dict
    # keys keeps us scoped to the exact codes the foreign-cap adjudication
    # named; importing the dict itself (not re-typing the codes) is the W105
    # guard against two writers of one verdict.
    adjacent_not_contained = set(ADJACENT_NOT_CONTAINED)
    buckets: dict[str, list[dict]] = {}
    for code, record in sorted(canonical.items()):
        bucket, evidence = classify(code, record, umkm, caps, priority,
                                    sector_law_carveout, adjacent_not_contained)
        buckets.setdefault(bucket, []).append({"code": code, **published(record), **evidence})

    total = sum(len(rows) for rows in buckets.values())
    if total != len(canonical):
        raise CannotVerify(f"bucketing lost records: {total} of {len(canonical)}")

    besar = {"observed": 0, "absent": 0, "unobserved": 0}
    for rows in buckets.values():
        for row in rows:
            besar[row["besar"]] += 1

    return {
        "instrument": INSTRUMENT,
        "codes": len(canonical),
        "annex_codes": {"lampiran_i": len(priority), "lampiran_ii": len(umkm),
                        "lampiran_iii": len(caps)},
        "body_codes_absent_from_catalogue": body_codes_absent_from_catalogue(canonical),
        "buckets": {name: len(rows) for name, rows in sorted(buckets.items())},
        "besar_axis": besar,
        "overlay": overlay_reconciliation(canonical),
        "detail": buckets,
    }


# What the PAGE calls open, copied from the renderer rather than guessed:
# `apps/mouth/src/lib/kbli-data.server.ts::mapPmaStatus` returns "restricted"
# for TERBATAS, "closed" for TERTUTUP, and **"open" for everything else** —
# including a null or an unrecognised value. Asking `== "TERBUKA"` here would
# make this detector blind to exactly the codes the page treats most generously,
# which is the blind-spot class the rest of this module exists to close.
RENDERS_AS_OPEN_UNLESS = frozenset({"TERBATAS", "TERTUTUP"})


def renders_as_open(record_or_row: dict) -> bool:
    return record_or_row.get("pma_status") not in RENDERS_AS_OPEN_UNLESS


def pasal7_review_flags(rep: dict) -> list[dict]:
    """Codes the page publishes as open where a Pasal 7(1) question is unanswered.

    A REVIEW FLAG, and the name is the correction. The first version of this
    function was called `foreign_barred_but_published_open` and the docstring
    said Pasal 7(1) "keeps a foreign investor out" — an independent
    legal-reading review refuted it, and the refutation is right on the text:

    * **Pasal 7(1) conditions the INVESTOR, not the ACTIVITY.** "Penanam Modal
      asing hanya dapat melakukan kegiatan usaha pada Usaha Besar" bars a
      particular PMA project that cannot qualify as large; it does not convert
      the underlying activity into one closed to foreign investment. Only a
      reservation, a cap, or a rule making large-scale operation unavailable
      does that — and those live in the annexes this module already reads.
    * **`per_skala` is licensing data, not a legal determination.** "OSS
      publishes no Besar row" is not "this activity cannot be conducted at Besar
      scale". Reading one as the other is the same conflation the three-state
      `besar_state` already refuses one level down, committed one level up.

    So the honest output is a queue for verification, never a verdict: for each
    of these, does an actual reservation/cap apply, and can the activity in fact
    be run at Usaha Besar? Read across EVERY bucket deliberately — the ten codes
    that are both annex-named and Besar-less are the ones a locator-partition
    hid, and they are this agency's daily questions (villa, homestay, salon).

    "Open" is the RENDERER's definition, not the label's. Today no record has a
    null `pma_status`, so the two readings coincide — the point is that they
    will not the day one does, and the page would be the generous one.
    """
    out = [row for rows in rep["detail"].values() for row in rows
           if row["besar"] == "absent" and renders_as_open(row)]
    return sorted(out, key=lambda r: r["code"])


# Emitted where the CONSUMER reads, not next to its inputs. `apps/mouth` has its
# own `vercel.json`, so the Vercel build root IS the app directory and nothing
# outside it is guaranteed to be in the build context; every data file the app
# loads sits in `apps/mouth/data/` via `path.join(process.cwd(), "data", ...)`.
# One file, at the reader, rather than a copy on each side: nothing to keep in
# sync is nothing that can drift. It is registered in
# `infra/claude-hooks/data-plane-registry.json` under the `kbli-filiera` entry,
# so the same guard that protects the compiled annexes protects the citations
# this file puts on public pages — leaving it outside the data plane just
# because the path is convenient would be the weaker half of the trade.
LOCATORS_OUT = REPO_ROOT / "apps" / "mouth" / "data" / "perpres-locators.json"

# One sentence per bucket, written to be read by a client on a public page, not
# by us. Each names the instrument, the article, and — where it applies — the
# fact that the activity is named through its KBLI-2020 predecessor, because a
# reader who greps the annex for the 2025 code and finds nothing deserves to
# know why rather than to conclude we made it up.
_LINE = {
    "body-tertutup":
        "Perpres 10/2021 Pasal 2(2)(b) (as amended by 49/2021) — closed by name",
    "body-other-requirement":
        "Perpres 10/2021 Pasal 6(3a) (as amended by 49/2021) — special requirements regime",
    "priority-lampiran-i":
        "Perpres 49/2021 Lampiran I — priority business field (Pasal 3(1)(a))",
    "sector-law-carveout": SECTOR_LAW_CARVEOUT_CITE,
}


def locator_line(bucket: str, evidence: dict) -> str:
    """The citation as a page renders it. Total over the buckets by construction."""
    if bucket in _LINE:
        return _LINE[bucket]
    if bucket == "named-in-annex":
        annexes = []
        if evidence["lampiran_ii"]:
            annexes.append("Lampiran II (Koperasi/UMKM)")
        if evidence["lampiran_iii"]:
            annexes.append("Lampiran III (foreign ownership)")
        named = sorted(set(evidence["lampiran_ii"]) | set(evidence["lampiran_iii"]))
        via = f" via KBLI-2020 {', '.join(named)}" if evidence["via_ancestor_only"] else ""
        return f"Perpres 49/2021 {' + '.join(annexes)}{via}"
    # Residual, whatever the OSS scale axis says — the scale is not a locator.
    return "Perpres 10/2021 Pasal 3(1)(d) — no annex names this activity"


def locators(rep: dict) -> dict:
    """`{code: {basis, cite, ...}}` for every code in the report.

    Emitted so `apps/mouth` can cite the article without re-deriving the
    precedence in TypeScript. Carries `besar` too, but as raw OSS scale data
    under its own key — never folded into the citation, because Pasal 7(1)
    conditions the investor and a scale row is not a locator.
    """
    out: dict[str, dict] = {}
    for bucket, rows in rep["detail"].items():
        for row in rows:
            out[row["code"]] = {
                "bucket": bucket,
                "basis": row["basis"],
                "cite": locator_line(bucket, row),
                "besar": row["besar"],
            }
    if len(out) != rep["codes"]:
        raise CannotVerify(f"locators cover {len(out)} of {rep['codes']} codes")
    return {
        "instrument": rep["instrument"],
        "generated_by": "scripts/kbli_filiera/perpres_body_default_relation.py --emit",
        "codes": len(out),
        "locators": dict(sorted(out.items())),
    }


def _display(path: Path) -> str:
    """Repo-relative when it can be, absolute otherwise.

    `Path.relative_to` RAISES for anything outside the repo, so a bare call
    turned every message on this path into a crash the moment the output moved
    — found by the test that redirects it to a tmp dir, which is exactly the
    shape a future caller would use. A progress message must never be the thing
    that fails.
    """
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="print the negative-locator report (the default action; accepted for symmetry with the sibling relations)")
    ap.add_argument("--json", action="store_true", help="machine-readable report on stdout")
    ap.add_argument("--emit", action="store_true",
                    help=f"write the per-code citations to {LOCATORS_OUT.name} (consumed by apps/mouth)")
    ap.add_argument("--check-artifact", action="store_true",
                    help="recompute the citations and fail if the emitted file differs")
    args = ap.parse_args(argv)

    try:
        rep = report(
            load_canonical(),
            *annex_codes(),
            priority_codes(),
            sector_law_carveout_codes(),
        )
    except (CannotVerify, FileNotFoundError) as exc:
        print(f"CANNOT-VERIFY: {exc}", file=sys.stderr)
        return EXIT_CANNOT_VERIFY

    if args.emit or args.check_artifact:
        try:
            built = locators(rep)
        except CannotVerify as exc:
            print(f"CANNOT-VERIFY: {exc}", file=sys.stderr)
            return EXIT_CANNOT_VERIFY
        if args.emit:
            # One-time migration: the first draft emitted next to the INPUTS, in
            # `data/kbli-filiera/`. It belongs at the reader instead (see
            # LOCATORS_OUT). The compiler removes its own old output because it
            # is the only writer the data-plane guard admits for that directory
            # — reaching for DATA_PLANE_GUARD_OFF to tidy up would disarm a
            # guard for convenience, which is how guards stop being guards.
            legacy = REPO_ROOT / "data" / "kbli-filiera" / "perpres-locators.json"
            if legacy.is_file():
                legacy.unlink()
                print(f"removed legacy {_display(legacy)}")
            LOCATORS_OUT.write_text(json.dumps(built, ensure_ascii=False, indent=1) + "\n")
            print(f"wrote {_display(LOCATORS_OUT)} ({built['codes']} codes)")
            return EXIT_OK
        if not LOCATORS_OUT.is_file():
            print(f"{_display(LOCATORS_OUT)} missing — run with --emit", file=sys.stderr)
            return EXIT_DIFFERS
        on_disk = json.loads(LOCATORS_OUT.read_text())
        if on_disk.get("locators") != built["locators"]:
            disk, fresh = on_disk.get("locators") or {}, built["locators"]
            moved = sorted(c for c in fresh.keys() & disk.keys() if fresh[c] != disk[c])
            print(f"DIFFERS — {len(fresh.keys() - disk.keys())} added, "
                  f"{len(disk.keys() - fresh.keys())} removed, {len(moved)} changed "
                  f"(e.g. {moved[:5]}). Re-run with --emit.", file=sys.stderr)
            return EXIT_DIFFERS
        print(f"{_display(LOCATORS_OUT)} matches the instrument ({built['codes']} codes)")
        return EXIT_OK

    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
        return EXIT_OK

    print(f"{rep['instrument']} — negative locator over {rep['codes']} codes")
    print(f"  annexes name: Lampiran I {rep['annex_codes']['lampiran_i']} · "
          f"II {rep['annex_codes']['lampiran_ii']} · "
          f"III {rep['annex_codes']['lampiran_iii']} (KBLI 2020)")
    print("  LOCATOR — which instrument names the code")
    for name, count in rep["buckets"].items():
        print(f"    {name:30} {count}")
    print(f"  OSS scale data — a SEPARATE axis, and NOT a legal verdict")
    for state, count in rep["besar_axis"].items():
        print(f"    besar {state:24} {count}")
    absent = rep["body_codes_absent_from_catalogue"]
    if absent:
        print(f"  body names {len(absent)} code(s) the 2025 catalogue does not carry: {', '.join(absent)}")

    ov = rep["overlay"]
    print(f"  the Bali overlay already reads {BESAR_BASIS} on {ov['overlay_closed']} codes — on what:")
    print(f"    corroborated by observed scales   {len(ov['corroborated_by_scales'])}")
    print(f"    closed on an EMPTY per_skala      {len(ov['closed_on_empty_scales'])}")
    print(f"    closed despite a Besar row        {len(ov['closed_with_a_besar_row'])}")
    for row in ov["absent_besar_not_closed"]:
        print(f"    NOT closed though Besar is absent: {row['code']} "
              f"({row['pma_status']}, l4_bali={row['l4_bali']})")

    rows = pasal7_review_flags(rep)
    if rows:
        print(f"\n  {BESAR_BASIS} REVIEW QUEUE — {len(rows)} codes published open with no Besar row")
        print("  NOT a bar: Pasal 7(1) conditions the INVESTOR, not the activity, and OSS")
        print("  scale data is not a determination that the activity cannot be run at Besar.")
        print("  Each needs: is there an actual reservation/cap, and can it run at Usaha Besar?")
        for row in rows:
            cap = row["pma_max_asing"]
            where = "L-II " + ",".join(row["lampiran_ii"]) if row["lampiran_ii"] else "body default"
            print(f"    {row['code']}  {cap if cap is not None else '-'}%  "
                  f"{(row['judul'] or '')[:42]:42} {where:14} scales: {','.join(row['scales'])}")
    # Reporter, never a gate: the re-label is a legal reading (Legge 5).
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
