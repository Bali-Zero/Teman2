"""No whole-code 0% foreign-ownership verdict may rest on a missing Usaha Besar scale.

THE CLAIM THIS GATE KILLS. PR #6488 (`cure_pma_closed_no_besar_scale.py`, spec
`pma_closed_no_besar_scale_2026_09_14.json`, never merged — see
DOSSIER-no-besar-normativo-2026-09-15.md) reasoned: OSS publishes no Usaha Besar scale row
for a KBLI 2025 code, therefore a PT PMA (Usaha Besar by Perpres 10/2021 Pasal 7(1) / BKPM
5/2025 Pasal 26(1)) cannot operate it, therefore foreign ownership is 0%. The dossier's
refuter found the opposite: BKPM 5/2025 Pasal 8(6) keeps a scale-absent activity
exercisable "sepanjang tidak dibatasi" by the Perpres bidang-usaha rules; closures/caps
live only in the Perpres 10/2021 (as amended by 49/2021) annexes (Lampiran II
`dialokasikan`, Lampiran III, the Pasal 2 closed list) or a Pasal 5(5) partial reservation
— never in the absence of a scale row. The same inference was withdrawn once already, on
2026-08-03 (PR #3551/#3579), for the l4_bali layer; this gate stops it re-entering through
the NATIONAL pma_* tuple #6488 targeted instead.

SCOPE, STATED. This gate reads a record's NATIONAL PMA-verdict fields — `pma_kondisi`,
`pma_nota`, `pma_source`, `pma_official_basis` — never `l4_bali`. Deliberate, and measured:
the four certified Lampiran II codes (95291, 96100, 96210, 96220) carry a *legacy*
`l4_bali.rule` reading literally "per-scala-Besar (OSS risk at scale Besar; PMA is Besar by
law)" — a stale internal label the client-facing `l4_bali.reason` (guarded by
`test_withdrawn_umkm_inference_absent.py`) already overrides. Reading `l4_bali` here would
convict the codes this gate exists to protect (filed as a finding in the PR-1 report; out
of lane to fix here).

ENTITY, NOT SPELLING (superscar #3). The predicate requires BOTH an annex/closed-list
locator AND the absence of scale-absence language — never either alone.
"""

from __future__ import annotations

import glob
import json
import re
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
CANONICAL = REPO / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
CURE_SPECS_DIR = REPO / "scripts/kbli_filiera/cure_specs"

# The locator this gate accepts. Measured against the 19 TERBATAS/located records on
# origin/main: every one names Lampiran II ("... DIALOKASIKAN untuk Koperasi dan UMKM
# ...") or Lampiran III ("Lampiran III (Daftar Bidang Usaha dengan Persyaratan
# Tertentu) entry #N") in `pma_official_basis` and/or `pma_kondisi`. Also accepts an
# EXPLICIT Pasal 2 closed-list citation (review finding 3, 2026-09-15): a record that
# names "Pasal 2 ... tertutup" or "daftar bidang usaha tertutup" directly is a MORE
# specific locator than the bare-citation bypass below and must not be rejected for
# lacking a Lampiran number it does not need. Naso PR-3 (2026-09-18) added the other
# three Pasal 2 exits from openness the statute names — UU 25/2007 Pasal 12(2) (the
# closed list itself, reached by Perpres Pasal 2(2)(a)), Pasal 2(1)(b)/2(3) (activities
# of the Pemerintah Pusat) and Pasal 2(1a) (the open fields are commercial fields) —
# because `apply_statutory_closures.py` now writes a per-code `pma_official_basis` on
# the 59 TERTUTUP records that used to pass through the bare-citation bypass. None of
# these is a scale argument, and the scale-absence check still runs FIRST.
ANNEX_LOCATOR = re.compile(
    r"lampiran\s*ii\b|lampiran\s*iii\b|dialokasikan"
    r"|pasal\s*2\b[^.\n]{0,80}?tertutup|tertutup[^.\n]{0,80}?pasal\s*2\b"
    r"|daftar\s+bidang\s+usaha\s+(?:yang\s+)?tertutup"
    r"|uu\s*25/2007\s+pasal\s*12\(2\)"
    r"|pasal\s*2\(1\)\(b\)|pasal\s*2\(3\)|pasal\s*2\(1a\)",
    re.IGNORECASE,
)

# The argument this gate refuses. The first four alternatives are verbatim from the
# #6488 fields actually written to `73300`/`38110`/`43110` on branch `5535726236`
# (pma_kondisi/pma_nota/pma_official_basis). Deliberately excludes a bare "per_skala"
# trigger: measured against the 52 files in cure_specs/, that field name is also used to
# describe/discuss OSS scale rows in passing (`l4_withdrawn_umkm_prose.json`,
# `editorial_body_national_scope.json`, `gold_86101_government_hospital_2026_08_07.json`)
# with no scale-absence verdict nearby — a bare match there is family #3 over-match, not
# guilt. Also deliberately excludes a bare "PMA is Besar by law" trigger (review finding
# 4, 2026-09-15): that sentence states the TRUE premise P1 of the withdrawn argument (a
# PMA must be Usaha Besar, BKPM 5/2025 Pasal 26(1)) and is legitimate anywhere, including
# beside a real Lampiran II locator; only the FALSE step P2 — that the ABSENCE of a scale
# row/slot, or an "only Mikro/Kecil" OSS offering, closes the activity — is guilt. The
# row/slot-absence alternatives are the trilingual pattern already proven in the sibling
# antidote `apps/mouth/src/lib/kbli-withdrawn-umkm-inference.test.ts`, reused here rather
# than re-derived.
SCALE_ABSENCE_BASIS = re.compile(
    r"PMA_CLOSED_NO_BESAR_SCALE"
    r"|no\s+Usaha\s+Besar\s+scale"
    r"|(?:tidak\s+ada|tanpa)\s+skala(?:\s+Usaha)?\s+Besar"
    r"|skala(?:\s+Usaha)?\s+Besar\s+tidak\s+tersedia"
    r"|no-Besar"
    r"|no\s+(?:\*\*)?(?:Usaha Besar|large-scale)(?:\*\*)?[^.\n]{0,40}?\b(?:row|slot)\b"
    r"|(?:non\s+offre\s+alcun[ao]|non\s+ha\s+un[ao]|nessun[ao]?)\s+(?:riga|fila|voce|slot)"
    r"[^.\n]{0,60}?(?:larga scala|Usaha Besar)"
    r"|tidak\s+(?:ada|memiliki|menawarkan|menyediakan)\s+(?:baris|slot)"
    r"[^.\n]{0,60}?(?:skala besar|Usaha Besar)"
    r"|only\s+(?:at\s+)?(?:Mikro|Micro)(?:\s*(?:/|,|and|dan)\s*)?(?:Kecil|Small)?\s*(?:-\s*)?scale"
    r"|hanya\s+(?:tersedia\s+)?(?:pada\s+)?skala\s+Mikro(?:\s*(?:/|,|dan)\s*Kecil)?",
    re.IGNORECASE,
)

# A bare mention of scale/skala anywhere in the rationale — used only to gate the
# TERTUTUP bare-citation bypass below (finding 1), never as a guilt trigger on its own
# (that would over-match the legitimate Pasal 26 investment-scale language finding 4
# protects).
_SCALE_MENTION = re.compile(r"\bscale\b|\bskala\b", re.IGNORECASE)


def _basis_text(rec: dict[str, Any]) -> str:
    return " || ".join(
        str(rec.get(k) or "") for k in ("pma_kondisi", "pma_nota", "pma_source", "pma_official_basis")
    )


def _tertutup_bare_citation_ok(rec: dict[str, Any]) -> bool:
    """Pasal 2 closed-list basis, as the corpus already expresses it for its 60
    TERTUTUP/declared_gap records: no per-code Lampiran citation, no populated
    `pma_official_basis`, and — review finding 1, 2026-09-15 — no mention of scale/skala
    ANYWHERE in the rationale. A record that invokes scale is arguing from OSS licensing
    availability, not from the Pasal 2 activity-type list, and needs a real locator: a
    bare "Perpres 10/2021" citation is not enough for that argument, only for this one."""
    if rec.get("pma_status") != "TERTUTUP" or rec.get("pma_official_basis"):
        return False
    if not re.search(r"perpres\s*10/2021", rec.get("pma_source") or "", re.IGNORECASE):
        return False
    rationale = f"{rec.get('pma_kondisi') or ''} {rec.get('pma_nota') or ''}"
    return not _SCALE_MENTION.search(rationale)


def judge(rec: dict[str, Any]) -> tuple[bool, str]:
    """True (innocent) iff not a 0% verdict, or a 0% verdict whose basis names an annex/
    closed-list locator and does not argue from scale absence. False (guilty) otherwise."""
    if rec.get("pma_max_asing") != 0:
        return True, "not a 0% verdict"
    text = _basis_text(rec)
    if SCALE_ABSENCE_BASIS.search(text):
        return False, f"basis argues from scale absence: {text[:200]!r}"
    if ANNEX_LOCATOR.search(text):
        return True, "annex locator present"
    if _tertutup_bare_citation_ok(rec):
        return True, "TERTUTUP bare Perpres 10/2021 citation (Pasal 2 closed-list, corpus convention)"
    return False, f"no annex/closed-list locator named: {text[:200]!r}"


def _canonical_rows() -> list[dict]:
    return json.loads(CANONICAL.read_text(encoding="utf-8"))["data"]


def test_the_store_this_gate_reads_is_actually_there():
    assert CANONICAL.is_file(), f"canonical missing at {CANONICAL}"
    assert len(_canonical_rows()) == 1559


def test_every_zero_percent_verdict_on_main_passes_today():
    """MEASURED: 79 records carry `pma_max_asing == 0` on origin/main (60 TERTUTUP/
    declared_gap, 19 TERBATAS/located). Not pinned as an exact count — sibling PRs in this
    mission add Lampiran II allocations — only that the sweep actually read some."""
    zero = [r for r in _canonical_rows() if r.get("pma_max_asing") == 0]
    assert len(zero) > 0, "the sweep read no 0% records — a truncated checkout passes vacuously (W84)"
    offenders = []
    for rec in zero:
        ok, reason = judge(rec)
        if not ok:
            offenders.append((rec["kode_kbli_2025"], reason))
    assert offenders == [], f"0% verdicts with no valid basis: {offenders}"


def test_guilt_the_6488_patch_is_refused():
    """GUILT. Fields verbatim from `git show 5535726236:data/source_documents/
    KBLI_2025_FINAL_CLEAN.json` records `73300` and `38110` — the actual patch #6488
    would have shipped, not a sentence written to match this gate."""
    kondisi = (
        "No Usaha Besar scale in OSS for this code and a PT PMA must be an Usaha Besar — "
        "foreign ownership 0% / Tidak ada skala Usaha Besar di OSS untuk KBLI ini, sedangkan "
        "PMA wajib Usaha Besar — kepemilikan asing 0% (Perpres 10/2021 Pasal 7(1); "
        "Permeninves/BKPM 5/2025 Pasal 26(1))"
    )
    nota = (
        "PMA_CLOSED_NO_BESAR_SCALE: closed to PT PMA, no Usaha Besar scale / tertutup bagi "
        "PMA, tanpa skala Usaha Besar"
    )
    source = "Perpres 10/2021 Pasal 7(1); Permeninves/BKPM 5/2025 Pasal 26(1) (retrieved 2026-09-14)"
    official_basis = (
        "Perpres 10/2021 (as amended by Perpres 49/2021) Pasal 7 ayat (1) — a foreign investor "
        "may carry on business only as an Usaha Besar — and Peraturan Menteri Investasi dan "
        "Hilirisasi/Kepala BKPM No. 5 Tahun 2025 Pasal 26 ayat (1), «yang dikategorikan PMA "
        "merupakan usaha besar» (ditetapkan 2025-10-01; retrieved 2026-09-14). OSS publishes "
        "no Usaha Besar scale for this KBLI 2025 code, so a PT PMA cannot operate it; max "
        "foreign 0% [PMA_CLOSED_NO_BESAR_SCALE, owner ruling 2026-09-14]."
    )
    for code in ("73300", "38110"):
        patched = {
            "kode_kbli_2025": code,
            "pma_status": "TERBATAS",
            "pma_max_asing": 0,
            "pma_verification_status": "located",
            "pma_kondisi": kondisi,
            "pma_nota": nota,
            "pma_source": source,
            "pma_official_basis": official_basis,
        }
        ok, reason = judge(patched)
        assert not ok, f"{code}: the #6488 patch must be refused, was accepted ({reason})"


def test_innocence_the_certified_lampiran_ii_codes_pass():
    by_code = {r["kode_kbli_2025"]: r for r in _canonical_rows()}
    for code in ("95291", "96100", "96210", "96220"):
        rec = by_code[code]
        assert rec.get("pma_max_asing") == 0, f"{code}: fixture assumption drifted, re-measure"
        ok, reason = judge(rec)
        assert ok, f"{code}: certified Lampiran II allocation wrongly refused ({reason})"


def test_innocence_tertutup_bare_citation_and_lampiran_iii_pass():
    by_code = {r["kode_kbli_2025"]: r for r in _canonical_rows()}
    rec_tertutup = by_code["01287"]  # Budidaya tanaman narkoba golongan I — Pasal 2 closure
    assert rec_tertutup.get("pma_status") == "TERTUTUP"
    ok, reason = judge(rec_tertutup)
    assert ok, f"01287: TERTUTUP national closure wrongly refused ({reason})"

    rec_l3 = by_code["16221"]
    assert "Lampiran III" in (rec_l3.get("pma_official_basis") or "")
    ok, reason = judge(rec_l3)
    assert ok, f"16221: Lampiran III basis wrongly refused ({reason})"


def test_innocence_a_legitimate_usaha_besar_mention_is_not_scale_absence():
    """A Pasal 26 investment-threshold note conditions the INVESTOR, not the activity — it
    must stay sayable. Over-match here would accuse every PMA-eligibility note of guilt."""
    sentence = (
        "Perpres 10/2021 Pasal 7(1) and BKPM 5/2025 Pasal 26(1) require a foreign investor "
        "to invest as Usaha Besar, above Rp10 miliar per KBLI — a condition on the investor, "
        "not a closure of the activity."
    )
    assert SCALE_ABSENCE_BASIS.search(sentence) is None


# --- Review findings, 2026-09-15 (Codex GPT-5.6 sol xhigh, checkpoint before rollover) ---


def test_finding1_guilt_tertutup_bare_citation_with_scale_rationale_is_refused():
    """UNDER-match. A TERTUTUP record with an empty `pma_official_basis` and a bare
    "Perpres 10/2021" `pma_source` used to pass unconditionally — even when the actual
    rationale argued OSS licensing scale, not a Pasal 2 activity-type closure."""
    rec = {
        "kode_kbli_2025": "99001",
        "pma_status": "TERTUTUP",
        "pma_max_asing": 0,
        "pma_source": "Perpres 10/2021, 49/2021",
        "pma_nota": "Hanya cocok untuk skala kecil menurut catatan OSS internal",
    }
    assert not _tertutup_bare_citation_ok(rec), "bypass wrongly allowed a scale-bearing rationale"
    ok, reason = judge(rec)
    assert not ok, f"99001: scale-bearing TERTUTUP rationale wrongly accepted ({reason})"


def test_finding1_innocence_tertutup_bare_citation_without_scale_mention_passes():
    rec = {
        "kode_kbli_2025": "99002",
        "pma_status": "TERTUTUP",
        "pma_max_asing": 0,
        "pma_source": "Perpres 10/2021, 49/2021",
        "pma_nota": "Perjudian dan pertaruhan",
    }
    assert _tertutup_bare_citation_ok(rec)
    ok, reason = judge(rec)
    assert ok, f"99002: genuine Pasal 2 bare-citation wrongly refused ({reason})"


def test_finding2_guilt_widened_row_and_only_small_scale_wordings_are_caught():
    """UNDER-match, "even when an annex token is also present" (review's own wording): a
    scale-absence argument must convict even when an unrelated Lampiran mention sits next
    to it — otherwise pasting any Lampiran citation beside the old wording would launder
    it, which is precisely the family #3 risk finding 3 also probes from the other side."""
    guilty_kondisi = [
        "Lampiran II lists this KBLI for an unrelated activity; here, the OSS system has "
        "no large-scale row for this code, so it is closed to a PT PMA.",
        "Skala Usaha Besar tidak tersedia di OSS untuk kode ini (lihat juga Lampiran II "
        "untuk kode lain) — tertutup bagi PMA.",
        "Only at Mikro/Kecil scale is this code registrable in OSS (cf. Lampiran III for a "
        "sibling code); a PT PMA cannot enter.",
        "il sistema OSS non ha una voce per registrazioni su larga scala per questo codice "
        "(si veda anche Lampiran II per un altro settore)",
    ]
    for kondisi in guilty_kondisi:
        rec = {
            "pma_status": "TERBATAS",
            "pma_max_asing": 0,
            "pma_kondisi": kondisi,
            "pma_source": "Perpres 10/2021, 49/2021",
        }
        ok, reason = judge(rec)
        assert not ok, f"scale-absence wording wrongly accepted: {kondisi!r} ({reason})"


def test_finding2_innocence_a_real_row_citation_still_passes():
    """A locator that happens to contain the word "row" (Lampiran II annex rows are named
    literally "row" in `pma_official_basis`) must not trip the widened row-absence match —
    the trigger requires "no"/negation immediately before it, not the bare word."""
    rec = {
        "pma_status": "TERBATAS",
        "pma_max_asing": 0,
        "pma_official_basis": (
            'Perpres 49/2021 Lampiran II (DIALOKASIKAN untuk Koperasi dan UMKM), p2, row '
            '"Industri pemindangan ikan" — allocated to Koperasi/UMKM.'
        ),
        "pma_source": "Perpres 10/2021, 49/2021",
    }
    ok, reason = judge(rec)
    assert ok, f"real Lampiran II row citation wrongly refused ({reason})"


def test_finding3_innocence_an_explicit_pasal2_closed_list_locator_passes():
    rec = {
        "pma_status": "TERTUTUP",
        "pma_max_asing": 0,
        "pma_official_basis": (
            "Perpres 10/2021 Pasal 2(2), daftar bidang usaha tertutup — closed to all "
            "foreign and domestic private investment."
        ),
        "pma_source": "Perpres 10/2021, 49/2021",
    }
    ok, reason = judge(rec)
    assert ok, f"explicit Pasal 2 closed-list locator wrongly refused ({reason})"


def test_finding3_guilt_a_stray_pasal2_mention_does_not_launder_scale_absence():
    """A record cannot cite Pasal 2 in passing while its REAL argument is scale absence —
    entity, not spelling (superscar #3): the locator check is necessary, not sufficient."""
    rec = {
        "pma_status": "TERBATAS",
        "pma_max_asing": 0,
        "pma_official_basis": (
            "Perpres 10/2021 Pasal 2 states the closed list in general terms; however this "
            "code is closed here because OSS lists no Usaha Besar scale for it."
        ),
        "pma_source": "Perpres 10/2021, 49/2021",
    }
    ok, reason = judge(rec)
    assert not ok, f"stray Pasal 2 mention wrongly laundered a scale-absence argument ({reason})"


def test_naso_pr3_innocence_the_three_statutory_exits_are_locators():
    """The 59 relabelled closures cite UU 25/2007 Pasal 12(2), Perpres Pasal 2(1)(b)/2(3)
    or Pasal 2(1a) — activity-type exits from openness, never a scale argument."""
    for basis in (
        "UU 25/2007 Pasal 12(2) as replaced by UU 6/2023 Pasal 77 item 2, Pasal 12(2)(a) "
        "«budi daya dan industri narkotika golongan I», incorporated by Perpres 10/2021 "
        "Pasal 2(2)(a) — matched by the record's title; closed to all Penanaman Modal.",
        "Perpres 10/2021 Pasal 2(1)(b) + 2(3) (as amended by Perpres 49/2021): activities of "
        "the Pemerintah Pusat are outside the open fields — the code sits under KBLI 84.",
        "Perpres 10/2021 Pasal 2(1a) (as amended by Perpres 49/2021): the open fields are "
        "Bidang Usaha yang bersifat komersial; not an investable field, max foreign 0%.",
    ):
        rec = {
            "pma_status": "TERTUTUP",
            "pma_max_asing": 0,
            "pma_official_basis": basis,
            "pma_source": "Perpres 10/2021, 49/2021",
        }
        ok, reason = judge(rec)
        assert ok, f"statutory exit wrongly refused ({reason})"


def test_naso_pr3_guilt_a_government_locator_does_not_launder_scale_absence():
    rec = {
        "pma_status": "TERTUTUP",
        "pma_max_asing": 0,
        "pma_official_basis": (
            "Perpres 10/2021 Pasal 2(3) names government activities; this code is closed "
            "because OSS lists no Usaha Besar scale for it."
        ),
        "pma_source": "Perpres 10/2021, 49/2021",
    }
    ok, reason = judge(rec)
    assert not ok, f"Pasal 2(3) mention wrongly laundered a scale-absence argument ({reason})"


def test_finding4_innocence_a_pasal26_legal_fact_note_beside_a_real_locator_passes():
    """OVER-match. Stating the TRUE premise, in the OLD trigger's own exact word order —
    "a PT PMA is Besar by law" — beside a real Lampiran II locator used to be refused by
    the bare "PMA is Besar by law" trigger — convicting the true half of the withdrawn
    argument (P1), not the false half (P2, the absence argument) that is the real guilt."""
    rec = {
        "pma_status": "TERBATAS",
        "pma_max_asing": 0,
        "pma_kondisi": (
            "Bidang usaha dialokasikan untuk Koperasi dan UMKM (Perpres 49/2021 Lampiran II) "
            "— foreign ownership 0%. Note: a PT PMA is Besar by law (BKPM 5/2025 Pasal "
            "26(1)), a separate investor-eligibility condition, not the reason for this "
            "reservation."
        ),
        "pma_source": "Perpres 10/2021, 49/2021",
    }
    ok, reason = judge(rec)
    assert ok, f"legitimate Pasal 26 note beside a real locator wrongly refused ({reason})"


# Review finding 5, 2026-09-15: the original sweep only recognised the `items[].locator`
# schema and would silently miss a resurrected `to_patch`-shaped spec (#6488's own shape).
# These keys hold a PRECONDITION or a SNAPSHOT, never a value the spec itself WRITES — a
# subtree rooted at one of them is skipped entirely, wherever it is nested. Measured: every
# `pma_max_asing: 0` occurrence in the 9 files that had one sits under `expect`; the
# withdrawn wording quoted verbatim in `l4_withdrawn_umkm_prose.json` and
# `l4bali_gap_disclosure_2026_07_25.json` sits under `old`/`expected_reason`-as-diagnostic —
# evidence of what was CURED, not a live basis.
_PRECONDITION_KEYS = {"expect", "was", "old", "excluded", "withdrawn_items", "withdrawn"}
_CODE_KEY = re.compile(r"^\d{4,6}$")


def _iter_write_entries(node: Any, code_hint: str | None = None):
    """Yield (code, entry) for every dict ANYWHERE in a spec's tree that carries
    `pma_max_asing` or `locator` directly — the two fields every write shape observed on
    disk uses (`to_patch`/`set`/`patch`: a flat pma_* dict keyed by code; `items`/
    `patches`: a list of `{code, locator, ...}` dicts) — outside any precondition subtree.
    A dict keyed by KBLI-code-shaped strings (`to_patch`'s own keys) propagates its key as
    the code hint to children that don't carry a `code` field themselves."""
    if isinstance(node, dict):
        if "pma_max_asing" in node or "locator" in node:
            yield node.get("code") or code_hint, node
        for k, v in node.items():
            if k in _PRECONDITION_KEYS:
                continue
            hint = k if _CODE_KEY.match(str(k)) else code_hint
            yield from _iter_write_entries(v, code_hint=hint)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_write_entries(item, code_hint=code_hint)


def _judge_write_entry(entry: dict[str, Any]) -> tuple[bool, str]:
    rec = {
        "pma_max_asing": entry.get("pma_max_asing", 0 if "locator" in entry else None),
        "pma_status": entry.get("pma_status"),
        "pma_kondisi": entry.get("pma_kondisi"),
        "pma_nota": entry.get("pma_nota"),
        "pma_source": entry.get("pma_source"),
        "pma_official_basis": entry.get("pma_official_basis") or entry.get("locator"),
    }
    return judge(rec)


def _all_write_entries() -> list[tuple[str, str, dict]]:
    entries: list[tuple[str, str, dict]] = []
    for path in sorted(glob.glob(str(CURE_SPECS_DIR / "*.json"))):
        spec = json.loads(Path(path).read_text(encoding="utf-8"))
        for code, entry in _iter_write_entries(spec):
            entries.append((path, str(code), entry))
    return entries


def test_spec_sweep_every_write_shape_entry_passes():
    entries = _all_write_entries()
    # 13 measured on origin/main via the `items[].locator` schema alone (finding 5's own
    # reproduction); the broader walker must see at least that many, never fewer (W84).
    assert len(entries) >= 13, f"the sweep saw only {len(entries)} write entries, expected >= 13"
    offenders = []
    for path, code, entry in entries:
        ok, reason = _judge_write_entry(entry)
        if not ok:
            offenders.append((Path(path).name, code, reason[:160]))
    assert offenders == [], f"cure_spec write entries with no valid basis: {offenders}"


def test_finding5_guilt_a_to_patch_shaped_spec_entry_is_refused():
    """The exact #6488 schema: `to_patch: {code: {pma_status, pma_max_asing, ...}}`. If
    such a spec file ever returns to `cure_specs/`, the sweep must catch it — the original
    sweep, scoped to `items[].locator`, would have silently ignored it."""
    guilty_spec = {
        "rule": "PMA_CLOSED_NO_BESAR_SCALE",
        "to_patch": {
            "38110": {
                "pma_status": "TERBATAS",
                "pma_max_asing": 0,
                "pma_kondisi": "No Usaha Besar scale in OSS for this code — foreign ownership 0%",
                "pma_source": "Perpres 10/2021 Pasal 7(1); Permeninves/BKPM 5/2025 Pasal 26(1)",
            }
        },
    }
    found = list(_iter_write_entries(guilty_spec))
    assert found, "the walker did not see the to_patch entry at all"
    code, entry = found[0]
    assert code == "38110"
    ok, reason = _judge_write_entry(entry)
    assert not ok, f"to_patch-shaped guilty entry wrongly accepted ({reason})"


def test_finding5_innocence_precondition_keys_are_not_swept():
    """An `expect` block asserts a PRE-existing state; it must not be walked as a write,
    or every editorial spec that merely checks `pma_max_asing == 0` before touching an
    unrelated prose field would be swept as if it set the cap itself."""
    editorial_spec = {
        "codes": {
            "10214": {
                "expect": {"pma_max_asing": 0, "pma_status": "TERBATAS"},
                "fields": {"whoThisIsFor": {"old": "...", "new": "..."}},
            }
        }
    }
    assert list(_iter_write_entries(editorial_spec)) == []
