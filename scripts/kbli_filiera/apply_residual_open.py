#!/usr/bin/env python3
"""Relabel the RESIDUAL-OPEN codes from ``declared_gap`` to ``located``.

WHAT THIS CHANGES, AND WHAT IT DOES NOT
----------------------------------------
Its sibling `apply_statutory_closures.py` located the codes an instrument
CLOSES. This one locates the codes no instrument touches at all — the largest
block in the catalogue, published ``TERBUKA`` / 100% and, until this compiler,
``declared_gap``: the page said "foreign ownership not yet verified" about a
code whose openness the Perpres decides by its residual article. The locator
already exists and is already emitted to the mouth
(`perpres_body_default_relation.py --emit` -> `apps/mouth/data/perpres-locators.json`,
bucket ``residual-besar-observed``, cite «Perpres 10/2021 Pasal 3(1)(d) — no
annex names this activity»); what was missing is the same fact INSIDE the
canonical, which is what the app (Qdrant/KG/`kbli_documents`) and the page's
own PMA tuple read.

It changes NO verdict and NO cap. A record that is not already ``TERBUKA``/100
is REFUSED, never flipped, and ``pma_kondisi``/``pma_nota``/``pma_source`` are
left exactly as found.

THE CLASS IS RE-DERIVED, NEVER TRUSTED FROM THE SPEC
-----------------------------------------------------
The spec lists the lot's codes, but the compiler recomputes the population
from the instrument on every run — `perpres_body_default_relation.report()`,
the same module that emits the mouth's locators — and refuses on ANY set
difference in EITHER direction (superscar #3: a guard that only checks the
codes it was handed is guilt without innocence). A code the rule reaches and
the spec omits is a refusal; a code the spec lists and the rule does not reach
is a refusal. So the spec cannot silently widen or narrow the class, and a
re-run after the canonical moves fails loudly instead of writing a stale set.

WHY A LOT, AND WHY THIS ONE FIRST
----------------------------------
Relabelling ``declared_gap`` -> ``located`` does two things at once: it
publishes the national openness, AND it makes `discloseBaliL4` disclose the
record's Bali overlay for the first time (the provincial row is subordinate to
the national tuple — `apps/mouth/src/lib/kbli-pma-disclosure.ts`). The lots are
therefore cut on the BALI axis, not alphabetically, so each PR changes one
client-facing thing at a time. Lot 1 is the ``OK_or_HIGHER_RISK`` group: the
Bali row it unveils says the code is not on the closure list, so the only new
assertion is the national one.

AND IT UNVEILS THE RECORD'S LEGACY PMA PROSE, WHICH IS WHY THE RULE EXCLUDES IT
------------------------------------------------------------------------------
The same gate publishes four more fields the moment the tuple is verified:
`pma_kondisi`, `pma_nota`, `pma_prioritas` and `pma_cap_note`. On the chat and
retrieval surfaces they are printed IMMEDIATELY BELOW the basis this compiler
writes — `- Official basis: …` then `- Conditions: …` / `- Note: …`
(`apps/backend-rag/backend/services/kbli_pma_disclosure.py`), `- Kondisi:` /
`- Catatan PMA:` in the document body (`kbli_documents_cure.py`) and in the
embedded Qdrant text (`kbli_qdrant_pma_sync.py`). On the residual block that
prose is generator-era: `git log -S` puts "Kemitraan dengan masyarakat setempat"
in `f63d86ed19` (2026-02-21), an LLM batch-enrichment run — no instrument
behind it. Publishing it under a Perpres basis line would attribute to the
Perpres a requirement the Perpres does not state, and on 31 of the 36 records
it CONTRADICTS the locator itself: six say «Sektor prioritas …» (or carry
`pma_prioritas: true`) about a code the relation places OUTSIDE Lampiran I, and
twenty-five assert «Tunduk pada ketentuan divestasi dan IUP», a mining
divestiture regime this basis never swept. So the rule requires those four
fields EMPTY, and the 36 records that carry them are deferred to their own
adjudication lot instead of being silently cleaned — deleting a field is an
assertion too, and the prose may well be true for some of them.

AND THE NEGATIVE LOCATOR UNDER-MATCHES WHERE THE PERPRES NAMES A CATEGORY
-------------------------------------------------------------------------
Membership here is decided by ABSENCE, so the relation is only as sharp as its
matchers: an annex row or a body article that names an activity by DESCRIPTION
instead of by 5-digit code leaves the code in the residual bucket and this
compiler would publish it as open-by-absence. That is superscar #3's UNDER-match
side, and it is not hypothetical — `classify()` puts 11030 «Industri Minuman
Beralkohol Hasil Fermentasi Malt» in `residual-besar-observed` while its two
4-digit neighbours 11010/11020 are TERTUTUP under the body's closed list, which
names «minuman keras mengandung alkohol» and no code at all.

Two subtractions answer it, and BOTH are re-derived, never trusted:

* `adjudicated_sibling_prefix` — a residual code is withheld when another code
  sharing its 4-digit subgolongan is already ADJUDICATED closed or capped
  (TERTUTUP/TERBATAS and `located`). The subgolongan is the same activity at a
  finer grain, so a neighbour an instrument reached is evidence the instrument
  is in this neighbourhood, and publishing the sibling as open-by-absence is the
  claim least likely to survive. It is computed from the canonical, so it
  TIGHTENS by itself as later lots adjudicate more codes.
* `excluded_codes` — the hand-adjudicated remainder, one entry per code with its
  reason, for the categories the body states in prose and the 4-digit rule
  cannot see: alcohol and malt, tobacco and its e-liquid, explosives and weapons
  repair, CITES-protected aquatic species, and the two `penjaminan` codes the PP
  14/2018 cure deliberately left `cap_verified` unset. Each entry must still be
  REACHED by the rule — a stale exclusion (a code the rule no longer reaches)
  refuses, so the list cannot rot into decoration.

Both are subtractions only: a withheld code stays `declared_gap`, which is the
state it already had. Nothing here flips a verdict — that remains Zero's call.

Usage (dry-run is the default; nothing is written without --apply):
  python3 scripts/kbli_filiera/apply_residual_open.py
  python3 scripts/kbli_filiera/apply_residual_open.py --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

_FILIERA_DIR = Path(__file__).resolve().parent
if str(_FILIERA_DIR) not in sys.path:
    sys.path.insert(0, str(_FILIERA_DIR))

from apply_umkm_reservations import (  # noqa: E402
    CANONICAL,
    CURE_SPECS,
    EXIT_OK,
    EXIT_REFUSED,
    load,
    propagate,
)
from perpres_body_default_relation import (  # noqa: E402
    CAPS,
    CannotVerify,
    annex_codes,
    priority_codes,
    report,
    sector_law_carveout_codes,
)

SPEC = CURE_SPECS / "residual_open_naso_2026_09_18_lot1.json"

# Every bucket `classify()` can emit. A rule naming something else is a typo or
# a renamed bucket and MUST refuse; a known bucket that happens to be empty on
# this dataset is an empty population, not a broken relation (the difference is
# the whole refusal message a reader acts on).
KNOWN_BUCKETS = (
    "body-tertutup",
    "body-other-requirement",
    "named-in-annex",
    "priority-lampiran-i",
    "sector-law-carveout",
    "residual-besar-observed",
    "residual-besar-absent",
    "residual-besar-unobserved",
)

# The four PMA fields the disclosure gate publishes alongside the basis. A lot
# member must carry NONE of them — see the docstring.
LEGACY_PMA_PROSE = ("pma_kondisi", "pma_nota", "pma_prioritas", "pma_cap_note")

BASIS = (
    "Perpres 10/2021 Pasal 3(1)(d) + 3(2) (as amended by Perpres 49/2021): the "
    "residual category — «Bidang Usaha yang tidak termasuk dalam huruf a, huruf b, "
    "dan huruf c» — «dapat diusahakan oleh semua Penanam Modal». Derived from the "
    "instrument by ABSENCE, not from a row that names this code: over the BPS "
    "2020→2025 crosswalk the code is on no Lampiran I (prioritas), Lampiran II "
    "(dialokasikan/kemitraan Koperasi-UMKM) or Lampiran III (persyaratan tertentu, "
    "foreign-ownership caps included) row — tested against Lampiran III BOTH by "
    "code through the crosswalk AND by activity title, because BPS re-scopes "
    "numbers between vintages while a cap attaches to the ACTIVITY the annex "
    "names — no body article names it (Pasal 2(2) "
    "closed list, Pasal 6(3a) alcohol trade) and no Pasal 11(2) sector-law "
    "referral reaches its SECTOR — the article's unit is «Bidang Usaha keuangan "
    "dan Bidang Usaha perbankan», so the whole of KBLI divisions 64, 65 and 66 "
    "is withheld from this lane, not merely the six codes the carve-out artifact "
    "enumerates. No instrument maps the 5-digit code; the residual article IS "
    "the locator. Open to all Penanam Modal, max foreign 100%. Scope: this is "
    "the Perpres investment axis only — sector statutes OUTSIDE the Perpres were "
    "not swept per code, and where that gap is load-bearing (divisions 09, 35, "
    "49-53, 61: migas, ketenagalistrikan, pelayaran, penerbangan, pos, "
    "telekomunikasi) the codes are withheld from this lane rather than published "
    "under it. Four Pasal 2(2) items close an ACTIVITY and name no code "
    "(narkotika golongan I; perjudian/kasino; CITES species and koral; industri "
    "senjata kimia and bahan perusak lapisan ozon): they are tested here by the "
    "state's OWN per-code markers — the licensing requirement for a «Surat "
    "Pernyataan tidak memproduksi senjata kimia … Bahan Perusak Ozon/BPO», plus "
    "the hand-held exclusions for the alcohol, tobacco, explosives and CITES "
    "chains — and none of them reaches a code in this lot. This basis does not "
    "clear a closed ACTIVITY carried on under an open code. "
    "The OSS licensing gate (risk tier, scale, zoning, and for a PMA "
    "the Pasal 7(1) >Rp10bn Usaha Besar test) is a separate question this basis "
    "does not answer."
)


# The spec may choose WHICH codes it lists; it may not choose the predicates that
# decide whether a code is eligible at all. Every load-bearing rule field is
# pinned here and compared before the population is derived, because otherwise
# "the population is re-derived from the instrument" is circular: the spec would
# be re-deriving it with predicates the spec itself wrote (council round 1,
# codex-gpt-5.6-sol HIGH (4)). Widening the class is a code change under review,
# not a JSON edit.
#
# Keyed by `spec["lot"]` because the lots are cut on the BALI axis (module
# docstring, "WHY A LOT"): each lot unveils one `l4_bali.status` value and
# nothing else about the rule may move. Lot 1 is unchanged from the pin this
# replaces. Lot 2 is IDENTICAL to lot 1 except `l4_bali_status`, on purpose —
# a lot spec cannot widen ANY other predicate just because it is allowed to
# name a different Bali status. An unknown lot, or a spec whose `rule` drifts
# from its own lot's pin, refuses in `check()` below.
REQUIRED_RULE_BY_LOT: dict[int, dict[str, Any]] = {
    1: {
        "bucket": "residual-besar-observed",
        "pma_status": "TERBUKA",
        "pma_max_asing": 100,
        "pma_verification_status": "declared_gap",
        "l4_bali_status": "OK_or_HIGHER_RISK",
        "l4_bali_blocked": False,
        "no_legacy_pma_prose": True,
        "adjudicated_sibling_prefix": 4,
    },
    2: {
        "bucket": "residual-besar-observed",
        "pma_status": "TERBUKA",
        "pma_max_asing": 100,
        "pma_verification_status": "declared_gap",
        "l4_bali_status": "ATTENZIONE_FASCIA_BALI",
        "l4_bali_blocked": False,
        "no_legacy_pma_prose": True,
        "adjudicated_sibling_prefix": 4,
    },
}


def patch_for(spec: dict[str, Any]) -> dict[str, Any]:
    """The whole patch, identical for every member — the legal fact is one fact.

    `pma_kondisi` is deliberately ABSENT: a residual-open code has no condition,
    and writing an empty one would turn "nothing to say" into an assertion.
    `pma_cap_note` is absent for the same reason — the located precedents carry
    "OFFICIAL: Perpres 10/2021 lampiran", which is exactly what is NOT true here.
    """
    return {
        "pma_verification_status": "located",
        "pma_official_basis": BASIS,
        "pma_source_vintage": spec["vintage"],
        "pma_cap_verified": True,
    }


def drift_from(record: dict[str, Any], want: dict[str, Any]) -> list[str]:
    """The patch fields this record does NOT already carry.

    Empty means "already applied, byte for byte". Idempotence is checked on the
    WHOLE patch and not on `pma_official_basis` alone: a record carrying the
    right basis with a stale vintage or a `pma_cap_verified` somebody flipped is
    HALF applied, and a re-run that reports it as a clean no-op teaches the next
    reader to trust a record the compiler never finished writing (PR-3 council,
    kimi-code/k3 LOW (2) and tp1-qwen3.8-max LOW (5), folded here as promised).
    """
    return sorted(k for k, v in want.items() if record.get(k) != v)


def _bali(record: dict[str, Any]) -> dict[str, Any]:
    l4 = record.get("l4_bali")
    return l4 if isinstance(l4, dict) else {}


def legacy_prose(record: dict[str, Any]) -> list[str]:
    """The `LEGACY_PMA_PROSE` fields this record would publish once located."""
    return [f for f in LEGACY_PMA_PROSE if record.get(f) not in (None, "", False)]


def eligible(record: dict[str, Any], rule: dict[str, Any]) -> bool:
    """The rule, applied to ONE record. The bucket leg is the caller's."""
    if rule.get("no_legacy_pma_prose") and legacy_prose(record):
        return False
    return (
        record.get("pma_status") == rule["pma_status"]
        and record.get("pma_max_asing") == rule["pma_max_asing"]
        and record.get("pma_verification_status") == rule["pma_verification_status"]
        and _bali(record).get("status") == rule["l4_bali_status"]
        and _bali(record).get("blocked") is rule["l4_bali_blocked"]
    )


def adjudicated_siblings(
    records: list[dict[str, Any]], prefix_len: int
) -> dict[str, list[str]]:
    """code -> the codes sharing its `prefix_len` prefix that are already CLOSED
    or CAPPED by an instrument (`TERTUTUP`/`TERBATAS` and `located`).

    The code itself is never its own sibling, and a code that IS adjudicated is
    not in the map: this answers "is there evidence an instrument reaches this
    neighbourhood", which only a DIFFERENT record can supply.
    """
    adjudicated: dict[str, list[str]] = {}
    for record in records:
        code = str(record["kode_kbli_2025"])
        if (
            record.get("pma_status") in ("TERTUTUP", "TERBATAS")
            and record.get("pma_verification_status") == "located"
        ):
            adjudicated.setdefault(code[:prefix_len], []).append(code)

    out: dict[str, list[str]] = {}
    for record in records:
        code = str(record["kode_kbli_2025"])
        others = sorted(c for c in adjudicated.get(code[:prefix_len], []) if c != code)
        if others:
            out[code] = others
    return out


def reached(spec: dict[str, Any], records: list[dict[str, Any]]) -> set[str]:
    """The rule's raw reach, BEFORE the two subtractions. `CannotVerify` on a gap."""
    rule = spec["rule"]
    if rule["bucket"] not in KNOWN_BUCKETS:
        raise CannotVerify(
            f"bucket {rule['bucket']!r} is not one classify() can emit"
        )
    canonical = {str(r["kode_kbli_2025"]): r for r in records}
    rep = report(
        canonical,
        *annex_codes(),
        priority_codes(),
        sector_law_carveout_codes(),
    )
    bucket = rep["detail"].get(rule["bucket"], [])
    return {
        row["code"] for row in bucket if eligible(canonical[row["code"]], rule)
    }


# The two shapes of "the Perpres annexes do not own this ownership question",
# kept apart because they are not the same claim and a reader must not read one
# as the other. `instrument_referral` is INTERNAL to the instrument and provable
# from its text; `unswept_sector_statute` is OUR OWN caution about a statute
# this lane did not read. Neither asserts that the code is closed.
REFERRAL_KINDS = ("instrument_referral", "unswept_sector_statute")


def sector_referral(code: str, spec: dict[str, Any]) -> str | None:
    """The reason this code's whole SECTOR is not the annexes' to answer.

    Absence from every Lampiran is evidence of openness only where the Perpres
    governs the ownership question at all. Perpres 10/2021 Pasal 11 ayat (2)
    says it does not, for two named sectors: «Perizinan berusaha dan pelaksanaan
    kegiatan dalam rangka Penanaman Modal untuk Bidang Usaha keuangan dan Bidang
    Usaha perbankan dilaksanakan sesuai dengan ketentuan peraturan
    perundang-undangan di bidangnya masing-masing.» A financial code is absent
    from the annexes because the Perpres never reached it — the opposite of open
    (council round 1: codex-gpt-5.6-sol BLOCK (1) and kimi-code/k3 BLOCK (1),
    independently, on the same 61 codes). The unit is the KBLI DIVISION because
    the instrument's unit is the sector, not the 5-digit code — which is also
    why the 4-digit sibling leg could not see it (kimi-code/k3 BLOCK (2)).
    """
    for block in spec.get("sector_referral", []):
        if code[:2] in block["divisions"]:
            return f"{block['kind']}: {block['instrument']} — {block['why']}"
    return None


def _norm(text: str) -> str:
    """Lowercase, punctuation to space, whitespace collapsed.

    The shape in which two vintages of the SAME activity name stay comparable:
    «Penerbitan surat kabar, majalah, dan buletin (pers)» and «Penerbitan Surat
    Kabar» differ in case, comma and parenthesis, not in what they name.
    """
    spaced = "".join(c if c.isalnum() or c.isspace() else " " for c in text)
    return " ".join(spaced.lower().split())


@lru_cache(maxsize=1)
def _catalogue_codes() -> frozenset[str]:
    """KBLI 2025 as it is ON DISK, not as a caller's record list describes it.

    `sector_law_closures` names codes in the catalogue, so its staleness is a
    property of the catalogue — reading it from whatever `records` a caller
    passed would make a synthetic fixture able to declare the real guard stale.
    """
    payload = json.loads(CANONICAL.read_text(encoding="utf-8"))
    rows = payload["data"] if isinstance(payload, dict) else payload
    return frozenset(str(r["kode_kbli_2025"]) for r in rows)


@lru_cache(maxsize=1)
def _cap_rows() -> tuple[tuple[str, str, int, int], ...]:
    """Lampiran III as (kbli_2020, normalised bidang_usaha, entry, cap%)."""
    rows = json.loads(CAPS.read_text(encoding="utf-8"))["rows"]
    return tuple(
        (
            str(row["kbli_2020"]),
            _norm(str(row["bidang_usaha"])),
            int(row["entry"]),
            int(row["foreign_cap_pct"]),
        )
        for row in rows
    )


def annex_title_collision(code: str, record: dict[str, Any]) -> str | None:
    """Whether this code's 2025 title is the ACTIVITY of a capped annex row
    filed under a DIFFERENT code.

    Absence from Lampiran III is matched by CODE, through the BPS 2020->2025
    crosswalk. But BPS also re-scopes numbers between vintages: 2020-58120 was
    «Penerbitan Direktori dan Mailing List» and 2020-58130 was the press row, and
    in 2025 the two swapped — 58120 IS «Penerbitan Surat Kabar». The cap follows
    the ACTIVITY the annex names; the crosswalk follows the NUMBER. Where they
    disagree the code passes an absence test it should have failed, and this lane
    publishes a verified 100% over a row that reads 0% at establishment.

    Restricted to Lampiran III on purpose: it is the only annex carrying a
    `foreign_cap_pct`, so a hit here is a cap we would be contradicting rather
    than a partnership condition. Lampiran I's artifact holds no titles at all,
    and Lampiran II carries an OCR row whose whole text is «Industri» — it
    matches every industrial title in the catalogue and produced 82% of the raw
    noise when the probe was measured across all three.

    Like `category_markers` this is COARSE and fail-CLOSED, and
    `collided_codes` pins what it matches catalogue-wide so the over-match is
    measured rather than hypothetical.
    """
    title = _norm(str(record.get("judul") or ""))
    if not title:
        return None
    for annex_code, bidang, entry, cap in _cap_rows():
        if annex_code == code:
            continue
        if title in bidang or bidang in title:
            return (
                f"annex title collision: Lampiran III entry #{entry} caps "
                f"«{bidang}» at {cap}% and files it under {annex_code}, but this "
                f"code's 2025 judul IS that activity — the crosswalk matched the "
                "NUMBER where the annex names the ACTIVITY, so absence here is a "
                "re-scoped code, not an open one; adjudicate the cap per vintage"
            )
    return None


# The fields THIS compiler writes, which the probe below must be BLIND to. The
# basis string quotes the closed category verbatim («senjata kimia», «bahan
# perusak lapisan ozon») — so a probe reading the whole record matches every
# member it has already shipped, against itself. Measured, not feared: the first
# run after the basis was extended withheld all 330 and refused the census.
PROBE_BLIND_FIELDS = (
    "pma_official_basis",
    "pma_source_vintage",
    "pma_cap_verified",
    "pma_verification_status",
)


def category_markers(record: dict[str, Any], markers: list[str]) -> list[str]:
    """Which Pasal 2(2) category markers this record carries, if any.

    Pasal 2 ayat (2) closes four items by ACTIVITY and names no KBLI code, so no
    annex leg can see them — there is no row to be absent from — and neither can
    the 4-digit sibling leg. What CAN see them is the state's own per-code
    marker: the licensing rows demand a «Surat Pernyataan tidak memproduksi
    senjata kimia dan industri yang menghasilkan Bahan Perusak Ozon/BPO» exactly
    where the closed category is a live risk. That string is the probe.

    It is deliberately COARSE — it matches anywhere in the record, not only in
    `persyaratan` — and deliberately fail-CLOSED: over-matching costs a lot
    member, under-matching costs a client the 11030 mistake (council round 1,
    kimi-code/k3 HIGH (3)). `marked_codes` in the spec pins what it matches
    catalogue-wide, so an over-match is measured rather than hypothetical.
    """
    government = {k: v for k, v in record.items() if k not in PROBE_BLIND_FIELDS}
    blob = json.dumps(government, ensure_ascii=False).lower()
    return [m for m in markers if m.lower() in blob]


def still_qualifies(record: dict[str, Any], rule: dict[str, Any]) -> list[str]:
    """What a LOCATED record fails TODAY, ignoring its verification state.

    An already-applied record is re-judged on every leg except the state itself,
    so evidence that arrives after the write can still revoke it: `eligible()`
    can never see a shipped record (it requires `declared_gap`), which made the
    "already applied" branch a one-way door (council round 1, codex-gpt-5.6-sol
    HIGH (2)).
    """
    bad: list[str] = []
    if record.get("pma_status") != rule["pma_status"]:
        bad.append(f"pma_status {record.get('pma_status')!r}")
    if record.get("pma_max_asing") != rule["pma_max_asing"]:
        bad.append(f"pma_max_asing {record.get('pma_max_asing')!r}")
    bali = _bali(record)
    if bali.get("status") != rule["l4_bali_status"]:
        bad.append(f"l4_bali.status {bali.get('status')!r}")
    if bali.get("blocked") is not rule["l4_bali_blocked"]:
        bad.append(f"l4_bali.blocked {bali.get('blocked')!r}")
    if rule.get("no_legacy_pma_prose") and legacy_prose(record):
        bad.append("legacy prose " + "+".join(legacy_prose(record)))
    return bad


def withheld(
    spec: dict[str, Any], records: list[dict[str, Any]], judged: set[str]
) -> dict[str, str]:
    """code -> why it is subtracted. `judged` is the reach PLUS the codes already
    shipped, so a shipped code can be withheld by evidence that arrived later."""
    out: dict[str, str] = {}
    prefix_len = spec["rule"].get("adjudicated_sibling_prefix")
    if prefix_len:
        siblings = adjudicated_siblings(records, prefix_len)
        for code in sorted(judged):
            if siblings.get(code):
                out[code] = (
                    f"adjudicated {prefix_len}-digit sibling(s) "
                    f"{', '.join(siblings[code])} — an instrument reaches this "
                    "subgolongan, so absence is not evidence of openness"
                )
    for code, why in sorted(spec.get("excluded_codes", {}).items()):
        out.setdefault(code, why)
    by_code = {str(r["kode_kbli_2025"]): r for r in records}
    # Before the division-wide referrals on purpose: a code this probe names is
    # contradicted by a SPECIFIC capped row, and a reader must be handed that row
    # rather than the broader "we did not read the sector statute" caution. It is
    # also the only leg that bites inside divisions the referrals do not cover.
    if spec.get("annex_title_collision_probe"):
        for code in sorted(judged):
            record = by_code.get(code)
            if record is None:
                continue
            why = annex_title_collision(code, record)
            if why:
                out.setdefault(code, why)
    for code in sorted(judged):
        why = sector_referral(code, spec)
        if why:
            out.setdefault(code, why)
    for block in spec.get("category_closure_probe", []):
        for code in sorted(judged):
            record = by_code.get(code)
            if record is None:
                continue
            hits = category_markers(record, block.get("markers") or [])
            if hits:
                out.setdefault(
                    code,
                    f"category-closure probe: {block['article']} — the record "
                    f"carries {', '.join(sorted(hits))}, the state's own per-code "
                    "marker for a category the Perpres closes by activity without "
                    "naming a code; adjudicate it, never publish it open by absence",
                )
    return out


def population(spec: dict[str, Any], records: list[dict[str, Any]]) -> set[str]:
    """Re-derive the lot from the instrument, minus the declared subtractions."""
    reach = reached(spec, records)
    return reach - set(withheld(spec, records, reach))


def check(
    spec: dict[str, Any], records: list[dict[str, Any]]
) -> tuple[list[str], list[str]]:
    """Return (todo codes, refusals). Any refusal blocks the write."""
    by_code = {str(r["kode_kbli_2025"]): r for r in records}
    listed = [str(c) for c in spec["items"]]
    refusals: list[str] = []
    todo: list[str] = []

    dupes = sorted({c for c in listed if listed.count(c) > 1})
    refusals += [f"{c}: listed twice" for c in dupes]

    want = patch_for(spec)
    for field in sorted(set(want) - set(PROBE_BLIND_FIELDS)):
        refusals.append(
            f"patch writes {field!r} but PROBE_BLIND_FIELDS does not list it — "
            "the category probe would read our own prose back as government "
            "evidence; add it there or stop writing it"
        )
    rule = spec["rule"]
    lot = spec.get("lot")
    required_rule = REQUIRED_RULE_BY_LOT.get(lot)
    if required_rule is None:
        refusals.append(
            f"spec lot {lot!r} is not a known lot — REQUIRED_RULE_BY_LOT has "
            f"{sorted(REQUIRED_RULE_BY_LOT)}, and an unknown lot cannot be "
            "trusted to pin the right predicates"
        )
    else:
        for key, value in sorted(required_rule.items()):
            if rule.get(key) != value:
                refusals.append(
                    f"rule.{key} is {rule.get(key)!r}, not {value!r} — this "
                    "compiler only writes the residual class, and a spec cannot "
                    "widen it"
                )
    if not spec.get("sector_referral"):
        refusals.append(
            "rule: no sector_referral block — Pasal 11(2) routes whole sectors "
            "out of the Perpres, and absence cannot be read as openness there"
        )
    for i, block in enumerate(spec.get("sector_referral", [])):
        if block.get("kind") not in REFERRAL_KINDS:
            refusals.append(
                f"sector_referral[{i}]: kind {block.get('kind')!r} is not one of "
                f"{REFERRAL_KINDS} — a referral must say whether the instrument "
                "itself routes the sector out or we simply did not read the statute"
            )
        for field in ("divisions", "instrument", "why"):
            if not block.get(field):
                refusals.append(f"sector_referral[{i}]: empty {field}")
        for div in block.get("divisions", []):
            if not (isinstance(div, str) and len(div) == 2 and div.isdigit()):
                refusals.append(
                    f"sector_referral[{i}]: division {div!r} is not a 2-digit "
                    "string — the unit of a sector referral is the KBLI division"
                )
    if not spec.get("category_closure_probe"):
        refusals.append(
            "rule: no category_closure_probe block — Pasal 2(2) closes four items "
            "by ACTIVITY and names no code, so absence from every annex cannot "
            "see them and the lot would publish openness it never tested"
        )
    for i, block in enumerate(spec.get("category_closure_probe", [])):
        for field in ("article", "category", "finding"):
            if not block.get(field):
                refusals.append(f"category_closure_probe[{i}]: empty {field}")
        markers = block.get("markers")
        pinned = block.get("marked_codes")
        if not markers or not isinstance(markers, list):
            refusals.append(
                f"category_closure_probe[{i}]: markers must be a non-empty list — "
                "a probe with nothing to look for withholds nothing and says it did"
            )
            continue
        if not isinstance(pinned, list):
            refusals.append(
                f"category_closure_probe[{i}]: marked_codes must be a list "
                "(possibly empty) — it is the census the probe is pinned to"
            )
            continue
        marked = {
            code
            for code, record in by_code.items()
            if category_markers(record, markers)
        }
        if marked != set(pinned):
            refusals.append(
                f"category_closure_probe[{i}]: the catalogue marks "
                f"{sorted(marked)} but the spec pins {sorted(pinned)} — a code "
                "entered or left the closed category since the finding was "
                "written; re-adjudicate it before writing"
            )
    if not spec.get("annex_title_collision_probe"):
        refusals.append(
            "rule: no annex_title_collision_probe block — Lampiran III is matched "
            "by CODE through the BPS crosswalk while the annex names an ACTIVITY, "
            "and where a number was re-scoped between vintages the lot would "
            "publish a verified 100% over a capped row"
        )
    for i, block in enumerate(spec.get("annex_title_collision_probe", [])):
        for field in ("annex", "artifact", "why", "finding"):
            if not block.get(field):
                refusals.append(f"annex_title_collision_probe[{i}]: empty {field}")
        want_artifact = str(CAPS.relative_to(CAPS.parents[2]))
        if block.get("artifact") != want_artifact:
            refusals.append(
                f"annex_title_collision_probe[{i}]: artifact "
                f"{block.get('artifact')!r} is not {want_artifact!r} — this probe "
                "reads the foreign-cap annex and nothing else; pointing it "
                "elsewhere would change what a hit MEANS without changing the text"
            )
        pinned = block.get("collided_codes")
        if not isinstance(pinned, list):
            refusals.append(
                f"annex_title_collision_probe[{i}]: collided_codes must be a list "
                "(possibly empty) — it is the census the probe is pinned to"
            )
            continue
        collided = {
            code
            for code, record in by_code.items()
            if annex_title_collision(code, record)
        }
        if collided != set(pinned):
            refusals.append(
                f"annex_title_collision_probe[{i}]: the catalogue collides on "
                f"{sorted(collided)} but the spec pins {sorted(pinned)} — a title "
                "or a capped row moved since the finding was written; re-read the "
                "annex against the new vintage before writing"
            )
    if not spec.get("sector_law_closures"):
        refusals.append(
            "rule: no sector_law_closures block — the codes a sector statute "
            "closes outright are held out of this lane today by the Bali and "
            "eligibility filters, i.e. BY ACCIDENT, and nothing would notice when "
            "a later lot lifts those filters"
        )
    for i, block in enumerate(spec.get("sector_law_closures", [])):
        for field in ("instrument", "why"):
            if not block.get(field):
                refusals.append(f"sector_law_closures[{i}]: empty {field}")
        codes = block.get("codes")
        if not codes or not isinstance(codes, list):
            refusals.append(
                f"sector_law_closures[{i}]: codes must be a non-empty list — a "
                "closure that names nobody guards nobody and says it did"
            )
            continue
        for code in codes:
            if code not in _catalogue_codes():
                refusals.append(
                    f"sector_law_closures[{i}]: {code} is not in KBLI 2025 — "
                    "stale guard, remove it or fix the code"
                )

    if refusals:
        return [], refusals

    try:
        reach = reached(spec, records)
    except CannotVerify as exc:
        return [], [f"cannot re-derive the population: {exc}"]
    # The shipped codes are judged too: `eligible()` requires `declared_gap`, so
    # without this a relabelled record could never be withheld again.
    held = withheld(spec, records, reach | set(listed))
    derived = reach - set(held)

    # The invariant behind the guard, not the guard itself: these codes must
    # never be SHIPPED, whatever leg happens to be holding them. Today 58120 is
    # held by the title-collision probe and the other three are simply out of
    # reach; if either of those stops being true the run REFUSES rather than
    # withholding quietly, because a statute closure is an adjudication a human
    # owes, not a subtraction a compiler may make on its own.
    for i, block in enumerate(spec.get("sector_law_closures", [])):
        for code in block["codes"]:
            if code in listed:
                refusals.append(
                    f"{code}: sector_law_closures[{i}] names it — "
                    f"{block['instrument']} closes it, it cannot be a lot member"
                )
            elif code in reach and code not in held:
                refusals.append(
                    f"{code}: sector_law_closures[{i}] names it and the rule now "
                    f"REACHES it with nothing holding it — {block['instrument']}; "
                    "the filters that kept it out are gone, adjudicate it"
                )

    # A hand-written exclusion the rule does not reach anyway is STALE: it looks
    # like protection and protects nothing, and the next reader trusts it.
    for code in sorted(set(spec.get("excluded_codes", {})) - reach):
        refusals.append(
            f"{code}: excluded_codes lists it but the rule does not reach it — "
            "stale exclusion, remove it or fix the rule"
        )

    for code in sorted(set(listed) - derived):
        record = by_code.get(code)
        if record is None:
            refusals.append(f"{code}: not in canonical")
        elif record.get("pma_verification_status") == "located" and (
            "pma_official_basis" not in drift_from(record, want)
        ):
            drift = drift_from(record, want)
            stale = still_qualifies(record, rule)
            if code in held:
                refusals.append(
                    f"{code}: already located under this basis but now WITHHELD — "
                    f"{held[code]}; revoke it, do not re-affirm it"
                )
            elif stale:
                refusals.append(
                    f"{code}: already located under this basis but no longer "
                    f"qualifies today ({', '.join(stale)}) — new evidence revokes"
                )
            elif drift:
                refusals.append(
                    f"{code}: already located under THIS basis but {', '.join(drift)} "
                    "differ(s) from the patch — half applied, not an idempotent no-op"
                )
            else:
                continue  # still qualifies, applied in full: a true no-op
        else:
            if code in held:
                refusals.append(f"{code}: listed in the lot but withheld — {held[code]}")
                continue
            prose = legacy_prose(record)
            refusals.append(
                f"{code}: listed in the lot but the rule does not reach it "
                f"(published {record.get('pma_status')}/{record.get('pma_max_asing')}/"
                f"{record.get('pma_verification_status')}, Bali "
                f"{_bali(record).get('status')}/{_bali(record).get('blocked')}"
                + (f", legacy prose {'+'.join(prose)}" if prose else "")
                + ")"
            )
    for code in sorted(derived - set(listed)):
        refusals.append(f"{code}: reached by the lot rule but not listed")

    for code in sorted(derived & set(listed)):
        record = by_code[code]
        state = record.get("pma_verification_status")
        if state == "located":
            drift = drift_from(record, want)
            stale = still_qualifies(record, rule)
            if "pma_official_basis" in drift:
                refusals.append(f"{code}: already located under a different basis")
            elif stale:
                refusals.append(
                    f"{code}: already located under this basis but no longer "
                    f"qualifies today ({', '.join(stale)}) — new evidence revokes"
                )
            elif drift:
                refusals.append(
                    f"{code}: already located under THIS basis but {', '.join(drift)} "
                    "differ(s) from the patch — half applied, not an idempotent no-op"
                )
            continue
        if state != "declared_gap":
            refusals.append(f"{code}: verification state {state!r} is neither known value")
            continue
        todo.append(code)
    return todo, refusals


def propagation_verdict(path: Path) -> int:
    """Propagate to the consumer copies and report. Idempotent, so a retry after
    a half-finished run finishes it instead of declaring victory."""
    if path.resolve() != CANONICAL.resolve():
        print(f"not canonical ({path}) — skipping consumer propagation")
        return EXIT_OK
    problems = propagate()
    for problem in problems:
        print(f"  PROPAGATION FAILED: {problem}")
    if problems:
        return EXIT_REFUSED
    print("consumer copies in sync with canonical")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    ap.add_argument("--dataset", default=str(CANONICAL))
    ap.add_argument("--spec", default=str(SPEC))
    args = ap.parse_args(argv)

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    path = Path(args.dataset)
    payload, records, original = load(path)

    todo, refusals = check(spec, records)
    total = len(spec["items"])
    # Counted, never subtracted: `total - todo - refusals` goes NEGATIVE the moment
    # one code draws two refusals (PR-3 council, kimi-code/k3 LOW (3)).
    by_code_for_count = {str(r["kode_kbli_2025"]): r for r in records}
    want_for_count = patch_for(spec)
    already = sum(
        1
        for c in spec["items"]
        if str(c) in by_code_for_count
        and not drift_from(by_code_for_count[str(c)], want_for_count)
    )
    print(
        f"lot {spec['lot']} · spec items {total} · applicable {len(todo)} · "
        f"already applied {already} · refused {len(refusals)}"
    )
    try:
        held = withheld(
            spec, records, reached(spec, records) | {str(c) for c in spec["items"]}
        )
    except CannotVerify:
        held = {}
    if held:
        print(f"  withheld from the reach: {len(held)} code(s)")
    # Named, not merely counted: this leg withholds a HANDFUL where every other
    # leg withholds a class, so it is exactly the guard that can rot into a
    # no-op without moving any number a reader watches (superscar #2).
    collided = sorted(c for c, why in held.items() if why.startswith("annex title collision"))
    if spec.get("annex_title_collision_probe"):
        print(
            f"  annex title collision: {len(collided)} of the reach — "
            f"{', '.join(collided) if collided else 'NONE, and the probe is therefore proving nothing'}"
        )
    for group, block in sorted(spec.get("deferred", {}).items()):
        print(f"  deferred {group}: {block['codes']} code(s) — {block['why']}")
    for r in refusals:
        print(f"  REFUSE {r}")
    if refusals:
        print(
            "\nrefusing to write: a spec wrong about one code is not trusted for the rest"
        )
        return EXIT_REFUSED

    for code in todo:
        print(f"  {code}: declared_gap -> located (TERBUKA/100 unchanged)")

    if not args.apply:
        print("\ndry-run — rerun with --apply to write")
        return EXIT_OK
    if not todo:
        # NOT an early return: the canonical is written BEFORE the copies, so a
        # run that died between the two leaves consumers behind and the retry
        # sees nothing to relabel. The retry's job is exactly the propagation
        # (council round 1, codex-gpt-5.6-sol HIGH (3)).
        print("\nalready applied — nothing to write; re-checking consumer copies")
        return propagation_verdict(path)

    by_code = {str(r["kode_kbli_2025"]): r for r in records}
    patch = patch_for(spec)
    for code in todo:
        by_code[code].update(patch)

    body = json.dumps(payload, ensure_ascii=False, indent=2)
    path.write_text(body + ("\n" if original.endswith("\n") else ""), encoding="utf-8")

    _, again, _ = load(path)
    fresh = {str(r["kode_kbli_2025"]): r for r in again}
    wrong = [
        code
        for code in todo
        if fresh[code].get("pma_verification_status") != "located"
        or fresh[code].get("pma_status") != "TERBUKA"
        or fresh[code].get("pma_max_asing") != 100
        or fresh[code].get("pma_official_basis") != patch["pma_official_basis"]
    ]
    if wrong:
        print(f"WROTE BUT READ BACK WRONG on {len(wrong)}: {wrong[:10]}")
        return EXIT_REFUSED
    print(f"\napplied and verified on re-read: {len(todo)} code(s)")

    return propagation_verdict(path)


if __name__ == "__main__":
    raise SystemExit(main())
