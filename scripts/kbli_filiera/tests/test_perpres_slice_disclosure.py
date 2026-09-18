"""Guilt, innocence and freshness for perpres_slice_disclosure_relation.py.

The three refusal conditions named in the module's own docstring each get a
guilt test (fires) and an innocence test (a neighbouring, legitimate shape
does not fire) — the guilt/innocence convention this repo's guards all carry.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import perpres_slice_disclosure_relation as pm  # noqa: E402
from apply_perpres_foreign_caps import BROADER, PLAIN  # noqa: E402
from perpres_slice_disclosure_relation import (  # noqa: E402
    ADJACENT_NOT_CONTAINED,
    ARTIFACT,
    CANONICAL,
    CLOSED_BY_UNION,
    MANUAL_SLICE_ROWS,
    SliceDisclosureError,
    build_artifact,
    compute_disclosures,
    general_rows,
    load_canonical,
    manual_rows,
    _serialize,
)


def _record(code: str, pma_status: str = "TERBUKA", ancestors: list[str] | None = None) -> dict:
    rec: dict = {"kode_kbli_2025": code, "pma_status": pma_status}
    if ancestors is not None:
        rec["bps_2020_ancestors"] = {"codes": ancestors}
    return rec


def _union_closed_record(code: str = "13133") -> dict:
    # The shape CLOSED_BY_UNION's inverse guard demands: TERBATAS/0 and a
    # basis naming BOTH annexes.
    return {
        "kode_kbli_2025": code,
        "pma_status": "TERBATAS",
        "pma_max_asing": 0,
        "pma_official_basis": (
            "Perpres 49/2021 Lampiran II item 11; Perpres 49/2021 Lampiran III entry #2"
        ),
    }


def _with_real_manual_codes(
    canonical: list[dict], adjudication: dict[str, tuple[str, str]]
) -> tuple[list[dict], dict[str, tuple[str, str]]]:
    """`compute_disclosures` always walks the REAL (unpatched) module-global
    `MANUAL_SLICE_ROWS` for its ADJUDICATION-membership check, the REAL
    `ADJACENT_NOT_CONTAINED` and `CLOSED_BY_UNION` for their own drift
    checks, and the REAL `LAMPIRAN_II_MANUAL_SLICE_ROWS` (43110) — which
    needs no ADJUDICATION entry at all, since it is a Lampiran II population,
    never derived from the Lampiran III `ADJUDICATION` dict. Every synthetic
    scenario that does not itself replace one of those dicts (via
    `monkeypatch.setattr(pm, ...)`, see `TestInvalidCap` /
    `TestNonTerbukaCode`) must therefore also supply a valid canonical entry
    for 43110 and 13133, or an unrelated check (its own `pma_status` lookup)
    fires before the scenario under test is ever reached."""
    base_canonical = [
        _union_closed_record("13133"),
        _record("30111"),
        _record("30113"),
        _record("20235"),
        _record("30303"),
        _record("51103"),
        _record("60103"),
        _record("60203"),
        _record("43110"),
    ]
    base_adjudication = {
        "30111": (BROADER, "real"),
        "30113": (BROADER, "real"),
        "20235": (BROADER, ADJACENT_NOT_CONTAINED["20235"]),
        "30303": (BROADER, ADJACENT_NOT_CONTAINED["30303"]),
        "51103": (BROADER, ADJACENT_NOT_CONTAINED["51103"]),
        "60103": (BROADER, ADJACENT_NOT_CONTAINED["60103"]),
        "60203": (BROADER, ADJACENT_NOT_CONTAINED["60203"]),
        "13133": (BROADER, CLOSED_BY_UNION["13133"]),
    }
    return base_canonical + canonical, {**base_adjudication, **adjudication}


# ---------------------------------------------------------------------------
# Refusal #1 — a BROADER code missing from the join
# ---------------------------------------------------------------------------


class TestMissingFromJoin:
    def test_guilt_broader_code_with_no_ancestor_raises(self):
        canonical = [_record("99999", ancestors=[])]
        adjudication = {"99999": (BROADER, "test-only")}
        with pytest.raises(SliceDisclosureError, match="missing from the ancestor join"):
            compute_disclosures(canonical, adjudication)

    def test_innocence_broader_code_with_a_matching_ancestor_does_not_raise(self):
        # "10761" is a real KBLI-2020 ancestor carrying exactly one RELATION
        # row (entry 1) — a legitimate neighbour of the guilt case above.
        canonical, adjudication = _with_real_manual_codes(
            [_record("99998", ancestors=["10761"])],
            {"99998": (BROADER, "test-only")},
        )
        disclosures = compute_disclosures(canonical, adjudication)
        assert "99998" in disclosures
        assert disclosures["99998"][0]["bidangUsaha"] == (
            "Industri pengolahan kopi yang sudah mendapatkan indikasi geografis"
        )

    def test_innocence_non_broader_code_is_never_required_to_join(self):
        # A PLAIN-adjudicated code (21021-shape) is never a slice-disclosure
        # target — absent from the join is expected, not a refusal.
        canonical, adjudication = _with_real_manual_codes(
            [_record("21021", ancestors=[])],
            {"21021": (PLAIN, "test-only")},
        )
        disclosures = compute_disclosures(canonical, adjudication)
        assert "21021" not in disclosures


# ---------------------------------------------------------------------------
# Refusal #2 — foreign_cap_pct not in {0, 49}
# ---------------------------------------------------------------------------


class TestInvalidCap:
    def test_guilt_manual_row_with_bad_cap_raises(self, monkeypatch):
        # Full replacement, not an additive setitem — the real 30111/30113
        # entries must NOT be present here, or the ADJUDICATION-membership
        # check (tested separately below) fires first on THEM instead of
        # reaching the cap check this test targets. ADJACENT_NOT_CONTAINED
        # is neutralised the same way — unrelated to what this test targets.
        monkeypatch.setattr(
            pm, "MANUAL_SLICE_ROWS", {"99997": [(1, "Industri uji coba", 30, None)]}
        )
        monkeypatch.setattr(pm, "ADJACENT_NOT_CONTAINED", {})
        monkeypatch.setattr(pm, "CLOSED_BY_UNION", {})
        monkeypatch.setattr(pm, "LAMPIRAN_II_MANUAL_SLICE_ROWS", {})
        canonical = [_record("99997")]
        adjudication = {"99997": (BROADER, "test-only")}
        with pytest.raises(SliceDisclosureError, match="not one of"):
            compute_disclosures(canonical, adjudication)

    def test_innocence_manual_row_with_valid_cap_does_not_raise(self, monkeypatch):
        monkeypatch.setattr(
            pm, "MANUAL_SLICE_ROWS", {"99996": [(1, "Industri uji coba", 49, None)]}
        )
        monkeypatch.setattr(pm, "ADJACENT_NOT_CONTAINED", {})
        monkeypatch.setattr(pm, "CLOSED_BY_UNION", {})
        monkeypatch.setattr(pm, "LAMPIRAN_II_MANUAL_SLICE_ROWS", {})
        canonical = [_record("99996")]
        adjudication = {"99996": (BROADER, "test-only")}
        disclosures = compute_disclosures(canonical, adjudication)
        assert disclosures["99996"][0]["foreignCapPct"] == 49


# ---------------------------------------------------------------------------
# Refusal #3 — code's own pma_status is not TERBUKA
# ---------------------------------------------------------------------------


class TestNonTerbukaCode:
    def test_guilt_restricted_code_with_slice_row_raises(self, monkeypatch):
        # The 50113-class shape: a code whose WHOLE code already carries a
        # code-wide restriction has no business ALSO carrying a slice row —
        # that would double-speak.
        monkeypatch.setattr(
            pm, "MANUAL_SLICE_ROWS", {"99995": [(1, "Industri uji coba", 49, None)]}
        )
        monkeypatch.setattr(pm, "ADJACENT_NOT_CONTAINED", {})
        monkeypatch.setattr(pm, "CLOSED_BY_UNION", {})
        monkeypatch.setattr(pm, "LAMPIRAN_II_MANUAL_SLICE_ROWS", {})
        canonical = [_record("99995", pma_status="TERBATAS")]
        adjudication = {"99995": (BROADER, "test-only")}
        with pytest.raises(SliceDisclosureError, match="double-speak"):
            compute_disclosures(canonical, adjudication)

    def test_innocence_terbuka_code_with_slice_row_does_not_raise(self, monkeypatch):
        monkeypatch.setattr(
            pm, "MANUAL_SLICE_ROWS", {"99994": [(1, "Industri uji coba", 49, None)]}
        )
        monkeypatch.setattr(pm, "ADJACENT_NOT_CONTAINED", {})
        monkeypatch.setattr(pm, "CLOSED_BY_UNION", {})
        monkeypatch.setattr(pm, "LAMPIRAN_II_MANUAL_SLICE_ROWS", {})
        canonical = [_record("99994", pma_status="TERBUKA")]
        adjudication = {"99994": (BROADER, "test-only")}
        disclosures = compute_disclosures(canonical, adjudication)
        assert "99994" in disclosures


# ---------------------------------------------------------------------------
# MANUAL_SLICE_ROWS <-> ADJUDICATION guilt/innocence — the two hand-authored
# codes must stay BROADER-adjudicated; if ADJUDICATION drifts (e.g. someone
# later patches 30111/30113 to a single cap), the disclosure must refuse
# rather than keep disclosing a slice on a code that no longer needs one.
# ---------------------------------------------------------------------------


class TestManualRowsTrackAdjudication:
    def test_guilt_manual_code_no_longer_broader_raises(self):
        canonical = [_record(code) for code in MANUAL_SLICE_ROWS]
        adjudication = {code: (PLAIN, "drifted") for code in MANUAL_SLICE_ROWS}
        with pytest.raises(SliceDisclosureError, match="no longer marks it BROADER"):
            compute_disclosures(canonical, adjudication)

    def test_innocence_real_adjudication_keeps_manual_codes_broader(self):
        from apply_perpres_foreign_caps import ADJUDICATION

        for code in MANUAL_SLICE_ROWS:
            verdict, _ = ADJUDICATION[code]
            assert verdict == BROADER, code


# ---------------------------------------------------------------------------
# ADJACENT_NOT_CONTAINED — 20235, 30303, 51103, 60103 and 60203 are excluded
# because their OWN ADJUDICATION reason says the annex activity is a neighbour,
# not a slice actually inside the code. Guilt/innocence on the exclusion itself
# and its drift-protection (same shape as TestManualRowsTrackAdjudication above).
# ---------------------------------------------------------------------------


class TestAdjacentNotContained:
    def test_pin_the_exclusion_set_is_exactly_these_five_codes(self):
        assert set(ADJACENT_NOT_CONTAINED) == {"20235", "30303", "51103", "60103", "60203"}

    def test_guilt_excluded_codes_are_absent_from_general_rows(self):
        from apply_perpres_foreign_caps import ADJUDICATION

        rows = general_rows(load_canonical(), ADJUDICATION)
        for code in ADJACENT_NOT_CONTAINED:
            assert code not in rows

    def test_innocence_sibling_codes_under_the_same_ancestor_still_appear(self):
        # 20235 shares ancestor "20232" with 20232 itself; 30303 shares
        # ancestor "30300" with 30301/30302; 60103/60203 descend from
        # broadcasting ancestors alongside 60102/60202 — the exclusion must
        # remove ONLY the named codes, not the whole ancestor family. (51103's
        # air-transport siblings 51101/51102 are whole-code restricted, not
        # BROADER, so they never reach the general derivation.)
        from apply_perpres_foreign_caps import ADJUDICATION

        rows = general_rows(load_canonical(), ADJUDICATION)
        assert "20232" in rows
        assert "30301" in rows
        assert "30302" in rows
        assert "60102" in rows
        assert "60202" in rows

    def test_guilt_verdict_drift_raises(self):
        canonical, adjudication = _with_real_manual_codes(
            [_record("20235"), _record("30303")],
            {"20235": (PLAIN, "drifted"), "30303": (BROADER, ADJACENT_NOT_CONTAINED["30303"])},
        )
        with pytest.raises(SliceDisclosureError, match="no longer marks it BROADER"):
            compute_disclosures(canonical, adjudication)

    def test_guilt_reason_drift_raises(self):
        canonical, adjudication = _with_real_manual_codes(
            [_record("20235"), _record("30303")],
            {
                "20235": (BROADER, "a different reason nobody re-checked"),
                "30303": (BROADER, ADJACENT_NOT_CONTAINED["30303"]),
            },
        )
        with pytest.raises(SliceDisclosureError, match="reason changed"):
            compute_disclosures(canonical, adjudication)

    def test_innocence_real_adjudication_keeps_the_exclusion_valid(self):
        from apply_perpres_foreign_caps import ADJUDICATION

        for code, reason in ADJACENT_NOT_CONTAINED.items():
            verdict, live_reason = ADJUDICATION[code]
            assert verdict == BROADER, code
            assert live_reason == reason, code

    def test_adjacent_not_contained_codes_never_reach_the_inside_this_code_sentence(
        self, real_disclosures
    ):
        # GUILT: a code the adjudication calls adjacent-not-contained must
        # never reach the client-facing "one specific activity INSIDE this
        # code" sentence (kbli-faq.ts). The exclusion exists precisely because
        # the annex activity is NOT inside the code. These three were the
        # false-restriction regression in commit 599f4a91d.
        for code in ("51103", "60103", "60203"):
            assert code not in real_disclosures
        # INNOCENCE: the map is not empty — a genuinely-contained BROADER code
        # still carries its slice row, so this pin cannot be satisfied by
        # silently dropping every disclosure.
        assert "20232" in real_disclosures
        rows = real_disclosures["20232"]
        assert len(rows) == 1
        assert rows[0]["bidangUsaha"] == "Industri kosmetik tradisional"
        assert rows[0]["foreignCapPct"] == 0


# ---------------------------------------------------------------------------
# 30111 / 30113 — the exact cross-product bug the general loop must not
# reproduce (module docstring: "an unmanned vehicle cannot be a traditional
# wooden vessel")
# ---------------------------------------------------------------------------


class TestManualRowsExcludedFromGeneralLoop:
    def test_30111_and_30113_are_not_in_general_rows(self):
        from apply_perpres_foreign_caps import ADJUDICATION

        rows = general_rows(load_canonical(), ADJUDICATION)
        assert "30111" not in rows
        assert "30113" not in rows

    def test_30113_never_receives_the_pinisi_row(self):
        rows = manual_rows()
        bidang_list = [r["bidangUsaha"] for r in rows["30113"]]
        assert not any("Pinisi" in b for b in bidang_list)

    def test_30111_receives_both_rows(self):
        rows = manual_rows()
        assert len(rows["30111"]) == 2
        caps = {r["foreignCapPct"] for r in rows["30111"]}
        assert caps == {0, 49}


# ---------------------------------------------------------------------------
# Closed-by-union exclusion — 13133 left the population the OTHER way round:
# the whole code closed, so a partial slice would contradict the record. The
# exclusion holds only while canonical still carries that closure on both
# annexes; the moment the code reopens, the slice must come back.
# ---------------------------------------------------------------------------


class TestClosedByUnion:
    def test_innocence_union_closed_code_is_excluded_and_the_rest_survives(self):
        canonical, adjudication = _with_real_manual_codes(
            [_record("20232", ancestors=["20232"])],
            {"20232": (BROADER, "real")},
        )
        rows = compute_disclosures(canonical, adjudication)
        assert "13133" not in rows
        assert "20232" in rows

    def test_guilt_reopened_code_must_disclose_the_slice_again(self):
        # Canonical says TERBUKA again: the retired slice would now hide a real
        # annex restriction from a client filing under the open code.
        canonical, adjudication = _with_real_manual_codes([], {})
        for rec in canonical:
            if rec["kode_kbli_2025"] == "13133":
                rec["pma_status"] = "TERBUKA"
                rec["pma_max_asing"] = 100
        with pytest.raises(SliceDisclosureError, match="must be disclosed again"):
            compute_disclosures(canonical, adjudication)

    def test_guilt_one_annex_basis_is_not_a_union(self):
        canonical, adjudication = _with_real_manual_codes([], {})
        for rec in canonical:
            if rec["kode_kbli_2025"] == "13133":
                rec["pma_official_basis"] = "Perpres 49/2021 Lampiran II item 11"
        with pytest.raises(SliceDisclosureError, match="does not name"):
            compute_disclosures(canonical, adjudication)

    def test_guilt_verdict_drift_raises(self):
        canonical, adjudication = _with_real_manual_codes(
            [], {"13133": (PLAIN, CLOSED_BY_UNION["13133"])}
        )
        with pytest.raises(
            SliceDisclosureError, match="closed-by-union but ADJUDICATION"
        ):
            compute_disclosures(canonical, adjudication)

    def test_guilt_reason_drift_raises(self):
        canonical, adjudication = _with_real_manual_codes(
            [], {"13133": (BROADER, "somebody re-read the annex differently")}
        )
        with pytest.raises(
            SliceDisclosureError, match="reason changed since the union"
        ):
            compute_disclosures(canonical, adjudication)

    def test_guilt_code_missing_from_canonical_raises(self):
        canonical, adjudication = _with_real_manual_codes([], {})
        canonical = [r for r in canonical if r["kode_kbli_2025"] != "13133"]
        with pytest.raises(
            SliceDisclosureError, match="cannot verify the union closure"
        ):
            compute_disclosures(canonical, adjudication)

    def test_innocence_real_canonical_still_carries_the_union_closure(self):
        from apply_perpres_foreign_caps import ADJUDICATION

        by_code = {str(r["kode_kbli_2025"]): r for r in load_canonical()}
        for code, reason in CLOSED_BY_UNION.items():
            assert ADJUDICATION[code] == (BROADER, reason), code
            rec = by_code[code]
            assert (rec["pma_status"], rec["pma_max_asing"]) == ("TERBATAS", 0), code
            assert "Lampiran II" in rec["pma_official_basis"], code
            assert "Lampiran III" in rec["pma_official_basis"], code

    def test_innocence_artifact_names_the_exclusion(self):
        artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        assert artifact["_meta"]["excluded_closed_by_union"] == CLOSED_BY_UNION
        assert "13133" not in artifact["disclosures"]


# ---------------------------------------------------------------------------
# The real catalogue — pins on adjudicated membership
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_disclosures():
    from apply_perpres_foreign_caps import ADJUDICATION

    return compute_disclosures(load_canonical(), ADJUDICATION)


class TestRealCatalogue:
    def test_population_count(self, real_disclosures):
        # 6 general BROADER codes (12 BROADER-adjudicated minus 20235/30303/
        # 51103/60103/60203, excluded as adjacent-not-contained, minus 13133,
        # closed as a whole by the union of Lampiran II item 11 and Lampiran
        # III entry #2 on 2026-09-18) + 30111 (2 rows) + 30113 (1 row) + 43110
        # (1 Lampiran II row, SAETTA-20260915 W-H PR-2 — a separate
        # hand-authored population, never derived from ADJUDICATION).
        assert len(real_disclosures) == 12
        assert sum(len(rows) for rows in real_disclosures.values()) == 13

    def test_43110_lampiran_ii_demolition_slice(self, real_disclosures):
        rows = real_disclosures["43110"]
        assert len(rows) == 1
        assert rows[0]["bidangUsaha"] == (
            "Pembongkaran yang menggunakan teknologi sederhana dan madya"
        )
        assert rows[0]["foreignCapPct"] == 0
        assert "Lampiran II" in rows[0]["locator"]

    def test_20235_and_30303_never_appear(self, real_disclosures):
        # Their own ADJUDICATION reason says the annex activity is a
        # neighbour, not something inside the code — disclosing a slice
        # there would assert a containment the adjudication itself denies.
        assert "20235" not in real_disclosures
        assert "30303" not in real_disclosures

    def test_30301_and_30302_still_appear(self, real_disclosures):
        # The other two military-aircraft-ancestor siblings are real
        # intersections and must NOT be caught by the 30303 exclusion.
        assert "30301" in real_disclosures
        assert "30302" in real_disclosures

    def test_20232_traditional_cosmetics_slice(self, real_disclosures):
        rows = real_disclosures["20232"]
        assert len(rows) == 1
        assert rows[0]["bidangUsaha"] == "Industri kosmetik tradisional"
        assert rows[0]["foreignCapPct"] == 0

    def test_13133_closed_by_union_carries_no_slice(self, real_disclosures):
        # Lampiran III entry #2 (batik cap) still names 13133's ancestor and
        # ADJUDICATION still says BROADER — but Lampiran II item 11 allocates
        # batik tulis + kombinasi to Koperasi/UMKM, so the canonical is
        # TERBATAS/0 and a partial disclosure would contradict the record.
        assert "13133" not in real_disclosures

    def test_30111_manned_vessel_two_rows(self, real_disclosures):
        rows = real_disclosures["30111"]
        assert len(rows) == 2
        caps = sorted(r["foreignCapPct"] for r in rows)
        assert caps == [0, 49]

    def test_30113_unmanned_vessel_defence_only(self, real_disclosures):
        rows = real_disclosures["30113"]
        assert len(rows) == 1
        assert rows[0]["foreignCapPct"] == 49

    def test_21021_and_21022_never_appear(self, real_disclosures):
        # PLAIN-adjudicated, whole-code restricted — no slice to disclose.
        assert "21021" not in real_disclosures
        assert "21022" not in real_disclosures

    def test_50113_never_appears(self, real_disclosures):
        # Not a slice case at all — the code-wide restriction IS the answer.
        assert "50113" not in real_disclosures

    def test_every_row_has_a_locator(self, real_disclosures):
        for code, rows in real_disclosures.items():
            for row in rows:
                assert row["locator"], code


# ---------------------------------------------------------------------------
# Artifact freshness
# ---------------------------------------------------------------------------


class TestArtifactFreshness:
    def test_emitted_artifact_matches_recomputation(self):
        from apply_perpres_foreign_caps import ADJUDICATION

        recomputed = _serialize(
            build_artifact(compute_disclosures(load_canonical(), ADJUDICATION))
        )
        assert ARTIFACT.exists(), (
            "run perpres_slice_disclosure_relation.py --emit "
            f"({ARTIFACT})"
        )
        assert ARTIFACT.read_text() == recomputed, (
            "kbli-perpres-slice-disclosures.json is stale — re-run "
            "scripts/kbli_filiera/perpres_slice_disclosure_relation.py "
            "--emit and commit it with the data change"
        )

    def test_sources_exist(self):
        assert CANONICAL.exists()

    def test_artifact_meta_count_matches_disclosures(self):
        artifact = json.loads(ARTIFACT.read_text())
        assert artifact["_meta"]["count"] == len(artifact["disclosures"])
