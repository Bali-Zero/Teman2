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
    ARTIFACT,
    CANONICAL,
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


def _with_real_manual_codes(
    canonical: list[dict], adjudication: dict[str, tuple[str, str]]
) -> tuple[list[dict], dict[str, tuple[str, str]]]:
    """`compute_disclosures` always walks the REAL (unpatched) module-global
    `MANUAL_SLICE_ROWS` for its ADJUDICATION-membership check — every
    synthetic scenario that does not itself replace `MANUAL_SLICE_ROWS`
    (via `monkeypatch.setattr(pm, ...)`, see `TestInvalidCap` /
    `TestNonTerbukaCode`) must therefore also supply valid TERBUKA/BROADER
    entries for the two real hand-authored codes, or that unrelated check
    fires before the scenario under test is ever reached."""
    base_canonical = [_record("30111"), _record("30113")]
    base_adjudication = {"30111": (BROADER, "real"), "30113": (BROADER, "real")}
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
        # reaching the cap check this test targets.
        monkeypatch.setattr(
            pm, "MANUAL_SLICE_ROWS", {"99997": [(1, "Industri uji coba", 30, None)]}
        )
        canonical = [_record("99997")]
        adjudication = {"99997": (BROADER, "test-only")}
        with pytest.raises(SliceDisclosureError, match="not one of"):
            compute_disclosures(canonical, adjudication)

    def test_innocence_manual_row_with_valid_cap_does_not_raise(self, monkeypatch):
        monkeypatch.setattr(
            pm, "MANUAL_SLICE_ROWS", {"99996": [(1, "Industri uji coba", 49, None)]}
        )
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
        canonical = [_record("99995", pma_status="TERBATAS")]
        adjudication = {"99995": (BROADER, "test-only")}
        with pytest.raises(SliceDisclosureError, match="double-speak"):
            compute_disclosures(canonical, adjudication)

    def test_innocence_terbuka_code_with_slice_row_does_not_raise(self, monkeypatch):
        monkeypatch.setattr(
            pm, "MANUAL_SLICE_ROWS", {"99994": [(1, "Industri uji coba", 49, None)]}
        )
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
# The real catalogue — pins on adjudicated membership
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_disclosures():
    from apply_perpres_foreign_caps import ADJUDICATION

    return compute_disclosures(load_canonical(), ADJUDICATION)


class TestRealCatalogue:
    def test_population_count(self, real_disclosures):
        # 12 general BROADER codes + 30111 (2 rows) + 30113 (1 row).
        assert len(real_disclosures) == 14
        assert sum(len(rows) for rows in real_disclosures.values()) == 15

    def test_13133_batik_cap_slice(self, real_disclosures):
        rows = real_disclosures["13133"]
        assert len(rows) == 1
        assert rows[0]["bidangUsaha"] == "Industri batik cap"
        assert rows[0]["foreignCapPct"] == 0

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
