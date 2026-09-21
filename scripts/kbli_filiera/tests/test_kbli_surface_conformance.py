"""Tests for the state-based `kbli_documents` conformance detector.

Guilt + innocence per scar #3, on synthetic two-store fixtures. No DB.

The point of this detector is that it selects on a STATE, never on a list of
codes — so the guilt cases below deliberately use codes that appear in no cure
spec anywhere. If a future edit reintroduces a list, these tests keep passing
while the tool goes blind, so the FIRST test asserts the tool's own scope: every
row of the table is judged and every canonical code is asked for.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

FILIERA = Path(__file__).resolve().parents[1]
if str(FILIERA) not in sys.path:
    sys.path.insert(0, str(FILIERA))

import _coverage_basis as B  # noqa: E402
import kbli_surface_conformance as C  # noqa: E402


def canon(code: str, **kwargs) -> dict:
    base = {B.CODE_FIELD: code, "pma_status": "TERBUKA", "per_skala": [], "judul": "Judul Kanonico"}
    base.update(kwargs)
    return base


def located(code: str, **kwargs) -> dict:
    return canon(
        code,
        pma_official_basis="Perpres 10/2021 Lampiran III",
        pma_source_vintage="2021-05-25",
        pma_verification_status="located",
        **kwargs,
    )


def row(code: str, **kwargs) -> dict:
    base = {
        "code": code,
        "pma_status": "TERBUKA",
        "judul": "Judul Kanonico",
        "licensing_status": "N/A",
        "rows": 0,
    }
    base.update(kwargs)
    return base


def store(*records) -> dict:
    return {r[B.CODE_FIELD]: r for r in records}


def loc(bucket: str, cite: str = "some cite") -> dict:
    return {"bucket": bucket, "basis": "Pasal 3 ayat (1)", "cite": cite, "besar": "observed"}


def neutral_locators_file(tmp_path: Path) -> Path:
    """A `--locators` fixture with zero SPECIFIC-bucket codes, so CLI-level
    tests that don't care about citation-propagation stay hermetic — decoupled
    from whatever `apps/mouth/data/perpres-locators.json` says about "01111"
    on the day the suite runs (it does, live, carry `named-in-annex`)."""
    path = tmp_path / "locators.json"
    path.write_text(
        json.dumps({"locators": {"00000": loc("residual-besar-observed")}}), encoding="utf-8"
    )
    return path


def neutral_kg_snapshot_file(tmp_path: Path) -> Path:
    """A `--kg-json` fixture with one code, no admitted permits, so CLI-level
    tests that don't care about the KG dimension stay hermetic — no live
    `scripts/pg.sh` call, and no dependency on today's PROD KG state. The KG
    checks are all DECLARED (never fold into the exit code), so its content
    never changes what these tests assert."""
    path = tmp_path / "kg_snapshot.json"
    path.write_text(
        json.dumps([{"code_id": "kbli:00000", "licensing_status": "REGULATED", "targets": []}]),
        encoding="utf-8",
    )
    return path


def neutral_kg_allowlist_file(tmp_path: Path) -> Path:
    """A `--kg-allowlist` fixture, decoupled from the live 75-code freeze."""
    path = tmp_path / "kg_allowlist.json"
    path.write_text(json.dumps({"codes": ["00000"]}), encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# scope — the property that makes this tool different from every cure before it
# --------------------------------------------------------------------------


def test_it_judges_codes_no_cure_spec_has_ever_named():
    """A code invented for this test, in neither store's cure history, still
    gets caught. This is the whole thesis: state, not list."""
    report = C.plan_conformance(store(located("77777")), [row("77777", pma_status="TERTUTUP")])
    assert [d["code"] for d in report["pma_divergent"]] == ["77777"]


def test_it_asks_for_every_canonical_code():
    report = C.plan_conformance(store(canon("11111"), canon("22222")), [row("11111")])
    assert report["missing_from_table"] == ["22222"]
    assert report["enforced_divergences"] == 1


# --------------------------------------------------------------------------
# guilt
# --------------------------------------------------------------------------


def test_guilt_pma_status_disagreement():
    report = C.plan_conformance(
        store(located("50122", pma_status="TERBATAS")), [row("50122", pma_status="TERBUKA")]
    )
    assert report["pma_divergent"][0]["canonical"] == "TERBATAS"
    assert report["pma_divergent"][0]["table"] == "TERBUKA"


def test_guilt_table_serves_licensing_for_a_code_canonical_detached():
    """The 50113 disease: canonical declared the gap, the channel kept serving
    the vintage-2020 rows into the LLM context."""
    report = C.plan_conformance(store(canon("50113", per_skala=[])), [row("50113", rows=4)])
    assert report["licensing_divergent"] == [
        {"code": "50113", "canonical_rows": 0, "table_rows": 4}
    ]


def test_guilt_table_serves_nothing_where_canonical_has_verified_rows():
    """The opposite direction, found on 80 codes at first run: the channel
    answers "N/A" while the website publishes the verified permit table."""
    report = C.plan_conformance(store(canon("82400", per_skala=[{"x": 1}] * 8)), [row("82400", rows=0)])
    assert report["licensing_divergent"][0]["canonical_rows"] == 8


def test_guilt_row_absent_from_canonical_and_not_neutralised():
    report = C.plan_conformance(store(), [row("47911")])
    assert report["unneutralised_phantoms"] == ["47911"]


def test_guilt_live_code_advertised_as_retired():
    """The inverse phantom error: a code the catalogue still carries, marked as
    deleted-by-KBLI-2025 in the store clients talk to."""
    report = C.plan_conformance(store(canon("56101")), [row("56101", licensing_status=C.PHANTOM_MARKER)])
    assert report["live_marked_retired"] == ["56101"]


# --------------------------------------------------------------------------
# innocence
# --------------------------------------------------------------------------


def test_innocence_identical_stores_are_clean():
    report = C.plan_conformance(store(canon("01111")), [row("01111")])
    assert report["enforced_divergences"] == 0


def test_innocence_a_properly_neutralised_phantom_is_not_a_divergence():
    """`26120`/`60111`/`82920`/`85598` are KBLI-2020 codes 2025 retired. They
    are SUPPOSED to sit in the table with no canonical record — flagging them
    would make the gate red forever and get it muted."""
    report = C.plan_conformance(store(), [row("82920", licensing_status=C.PHANTOM_MARKER)])
    assert report["unneutralised_phantoms"] == []
    assert report["enforced_divergences"] == 0


def test_innocence_title_difference_alone_never_fails_the_gate():
    """1,423 rows still carry the original UPPERCASE seed titles. Enforcing on
    them would drown the ownership and licensing signals in cosmetic noise."""
    report = C.plan_conformance(
        store(canon("01111", judul="Pertanian Padi Inbrida")), [row("01111", judul="RICE FARMING (PERTANIAN PADI)")]
    )
    assert report["enforced_divergences"] == 0
    assert report["declared_only"]["judul_differs"] == 1


def test_case_only_title_difference_is_not_even_counted():
    report = C.plan_conformance(store(canon("01111", judul="Pertanian Padi")), [row("01111", judul="PERTANIAN PADI")])
    assert report["declared_only"]["judul_differs"] == 0


def test_truncated_titles_are_counted_separately_because_truncation_changes_meaning():
    """On 5 government codes the cut lands past the word `Pemerintah` — the one
    word that says the activity is governmental."""
    report = C.plan_conformance(
        store(canon("91221", judul="Situs Bersejarah dan Monumen yang Dikelola Pemerintah")),
        [row("91221", judul="Situs Bersejarah dan Monumen yang")],
    )
    assert report["declared_only"]["judul_truncated"] == 1
    assert report["enforced_divergences"] == 0


def test_innocence_matching_licensing_presence_is_clean_at_both_ends():
    both_full = C.plan_conformance(store(canon("01111", per_skala=[{"x": 1}])), [row("01111", rows=3)])
    both_empty = C.plan_conformance(store(canon("68112", per_skala=[])), [row("68112", rows=0)])
    assert both_full["licensing_divergent"] == []
    assert both_empty["licensing_divergent"] == []


# --------------------------------------------------------------------------
# the report must distinguish "syncs to evidence" from "syncs to the SSOT"
# --------------------------------------------------------------------------


def test_divergence_separates_verified_truth_from_declared_gap():
    """A declared gap is visible, but it is never safe input to a cure."""
    report = C.plan_conformance(
        store(
            located("50122", pma_status="TERBATAS"),
            canon(
                "02101",
                pma_status="TERBUKA",
                pma_cap_verified=False,
                pma_verification_status="declared_gap",
            ),
        ),
        [row("50122", pma_status="TERBUKA"), row("02101", pma_status="TERBATAS")],
    )
    assert [d["code"] for d in report["pma_divergent"]] == ["50122"]
    assert [d["code"] for d in report["pma_unverified_divergent"]] == ["02101"]
    assert report["pma_divergent"][0]["canonical_basis"] is True
    assert report["pma_unverified_divergent"][0]["canonical_cap_verified"] is False
    assert report["enforced_divergences"] == 1


def test_guilt_malformed_canonical_pma_state_fails_closed_without_claiming_truth():
    report = C.plan_conformance(
        store(canon("02101", pma_status="TERBUKA")),
        [row("02101", pma_status="TERBATAS")],
    )
    assert report["pma_divergent"] == []
    assert [d["code"] for d in report["pma_invalid_divergent"]] == ["02101"]
    assert report["enforced_divergences"] == 1


# --------------------------------------------------------------------------
# CLI contract
# --------------------------------------------------------------------------


def test_empty_snapshot_is_cannot_verify_never_clean(tmp_path, capsys):
    """Zero rows traversed is not a clean bill of health (W84)."""
    canonical = tmp_path / "c.json"
    canonical.write_text(json.dumps({"data": [canon("01111")]}), encoding="utf-8")
    snap = tmp_path / "s.json"
    snap.write_text("[]", encoding="utf-8")
    rc = C.main(
        [
            "--canonical",
            str(canonical),
            "--locators",
            str(neutral_locators_file(tmp_path)),
            "--table-json",
            str(snap),
        ]
    )
    assert rc == C.EXIT_CANNOT_VERIFY
    assert "not a clean bill" in capsys.readouterr().out


def test_unreachable_database_is_cannot_verify_not_divergence(tmp_path, capsys):
    canonical = tmp_path / "c.json"
    canonical.write_text(json.dumps({"data": [canon("01111")]}), encoding="utf-8")
    rc = C.main(
        [
            "--canonical",
            str(canonical),
            "--locators",
            str(neutral_locators_file(tmp_path)),
            "--psql-wrapper",
            str(tmp_path / "no-such-pg.sh"),
        ]
    )
    assert rc == C.EXIT_CANNOT_VERIFY
    assert "CANNOT VERIFY" in capsys.readouterr().out


def test_conformant_stores_exit_zero(tmp_path):
    canonical = tmp_path / "c.json"
    canonical.write_text(json.dumps({"data": [canon("01111")]}), encoding="utf-8")
    snap = tmp_path / "s.json"
    snap.write_text(json.dumps([row("01111")]), encoding="utf-8")
    assert (
        C.main(
            [
                "--canonical",
                str(canonical),
                "--locators",
                str(neutral_locators_file(tmp_path)),
                "--table-json",
                str(snap),
                "--kg-json",
                str(neutral_kg_snapshot_file(tmp_path)),
            ]
        )
        == C.EXIT_OK
    )


def test_divergent_stores_exit_one(tmp_path):
    canonical = tmp_path / "c.json"
    canonical.write_text(json.dumps({"data": [located("01111", pma_status="TERTUTUP")]}), encoding="utf-8")
    snap = tmp_path / "s.json"
    snap.write_text(json.dumps([row("01111", pma_status="TERBUKA")]), encoding="utf-8")
    assert (
        C.main(
            [
                "--canonical",
                str(canonical),
                "--locators",
                str(neutral_locators_file(tmp_path)),
                "--table-json",
                str(snap),
                "--kg-json",
                str(neutral_kg_snapshot_file(tmp_path)),
            ]
        )
        == C.EXIT_DIVERGENCE
    )


# --------------------------------------------------------------------------
# citation propagation — a THIRD surface (locators vs canonical only),
# independent of the kbli_documents table checks above
# --------------------------------------------------------------------------


def test_guilt_named_in_annex_with_no_canonical_basis():
    report = C.plan_citation_propagation(
        store(canon("01111")),  # no pma_official_basis
        {"01111": loc("named-in-annex")},
    )
    assert [d["code"] for d in report["citation_not_propagated"]] == ["01111"]
    assert report["specific_citation_codes"] == 1


def test_declared_gap_named_citation_is_pending_not_enforced():
    report = C.plan_citation_propagation(
        store(canon("01111", pma_verification_status="declared_gap")),
        {"01111": loc("named-in-annex")},
    )
    assert report["citation_not_propagated"] == []
    assert [d["code"] for d in report["citation_pending_adjudication"]] == ["01111"]


def test_stale_declared_gap_with_vintage_does_not_escape_citation_gate():
    report = C.plan_citation_propagation(
        store(
            canon(
                "01111",
                pma_verification_status="declared_gap",
                pma_source_vintage="2021-05-25",
            )
        ),
        {"01111": loc("named-in-annex")},
    )
    assert [d["code"] for d in report["citation_not_propagated"]] == ["01111"]
    assert report["citation_pending_adjudication"] == []


def test_innocence_priority_lampiran_i_is_not_an_ownership_citation():
    """This test asserted the OPPOSITE until 2026-08-06, and it was wrong.

    Being listed in Lampiran I means the activity is a PRIORITY business field
    — it attracts incentives; it states nothing about how much of it a foreigner
    may own. `perpres_body_default_relation.py` says so in its own words
    ("priority incentivises, it never restricts"), and the artifact agrees: all
    175 codes in the bucket share ONE cite, which names no code, no percentage
    and no ownership treatment.

    So flagging them as "a citation the website shows and canonical lacks" was
    demanding an adjudicated foreign-ownership basis for a fact nobody asserts
    — 173 entries of a 414-entry backlog that were never real work.
    """
    report = C.plan_citation_propagation(
        store(canon("10211")),  # no pma_official_basis, and correctly not asked for
        {"10211": loc("priority-lampiran-i")},
    )
    assert report["citation_not_propagated"] == []
    assert report["specific_citation_codes"] == 0


def test_innocence_generic_default_bucket_is_never_flagged():
    """residual-besar-* is the generic Pasal 3(1)(d)+(2) fallback, not a
    code-specific citation — flagging it would just restate the pre-existing
    "no annex" default, not surface anything new."""
    report = C.plan_citation_propagation(
        store(canon("01112")),  # no pma_official_basis either
        {"01112": loc("residual-besar-observed")},
    )
    assert report["citation_not_propagated"] == []
    assert report["specific_citation_codes"] == 0


def test_innocence_already_propagated_citation_is_not_flagged():
    report = C.plan_citation_propagation(
        store(canon("01111", pma_official_basis="Perpres 49/2021 Lampiran II")),
        {"01111": loc("named-in-annex")},
    )
    assert report["citation_not_propagated"] == []
    assert report["specific_citation_codes"] == 1


def test_edge_locator_code_absent_from_canonical_does_not_crash():
    """canonical is the 1,559-code universe of record; a locator code outside
    it is a separate informational-only oddity — never crash, never flag."""
    report = C.plan_citation_propagation(
        store(canon("11111")),
        {"99999": loc("named-in-annex")},
    )
    assert report["citation_not_propagated"] == []
    assert report["specific_citation_codes"] == 1


def test_malformed_locators_path_is_cannot_verify_not_a_crash(tmp_path, capsys):
    canonical = tmp_path / "c.json"
    canonical.write_text(json.dumps({"data": [canon("01111")]}), encoding="utf-8")
    snap = tmp_path / "s.json"
    snap.write_text(json.dumps([row("01111")]), encoding="utf-8")
    rc = C.main(
        [
            "--canonical",
            str(canonical),
            "--locators",
            str(tmp_path / "no-such-locators.json"),
            "--table-json",
            str(snap),
        ]
    )
    assert rc == C.EXIT_CANNOT_VERIFY
    assert "CANNOT VERIFY" in capsys.readouterr().out


def test_citation_not_propagated_folds_into_the_cli_exit_code(tmp_path):
    """Wiring check: an otherwise-conformant kbli_documents snapshot must
    still fail the gate if the citation-propagation check finds a gap."""
    canonical = tmp_path / "c.json"
    canonical.write_text(json.dumps({"data": [canon("01111")]}), encoding="utf-8")
    snap = tmp_path / "s.json"
    snap.write_text(json.dumps([row("01111")]), encoding="utf-8")
    locators = tmp_path / "locators.json"
    locators.write_text(json.dumps({"locators": {"01111": loc("named-in-annex")}}), encoding="utf-8")
    rc = C.main(
        [
            "--canonical",
            str(canonical),
            "--locators",
            str(locators),
            "--table-json",
            str(snap),
            "--kg-json",
            str(neutral_kg_snapshot_file(tmp_path)),
        ]
    )
    assert rc == C.EXIT_DIVERGENCE


def test_declared_gap_citation_backlog_does_not_fail_cli(tmp_path):
    canonical = tmp_path / "c.json"
    canonical.write_text(
        json.dumps({"data": [canon("01111", pma_verification_status="declared_gap")]}),
        encoding="utf-8",
    )
    snap = tmp_path / "s.json"
    snap.write_text(json.dumps([row("01111")]), encoding="utf-8")
    locators = tmp_path / "locators.json"
    locators.write_text(
        json.dumps({"locators": {"01111": loc("named-in-annex")}}),
        encoding="utf-8",
    )
    assert C.main(
        [
            "--canonical",
            str(canonical),
            "--locators",
            str(locators),
            "--table-json",
            str(snap),
            "--kg-json",
            str(neutral_kg_snapshot_file(tmp_path)),
        ]
    ) == C.EXIT_OK


# ---------------------------------------------------------------------------
# The eligibility set must judge what a citation SAYS, not which bucket it is
#
# `priority-lampiran-i` sat in SPECIFIC_CITATION_BUCKETS until 2026-08-06 and
# failed the very definition the constant's comment states. Its 175 codes share
# ONE cite naming no code and no ownership treatment, so the detector demanded
# an adjudicated foreign-ownership basis for 173 codes whose citation asserts
# nothing about ownership. The structural test below is the general form: a
# bucket whose codes all repeat a single string is generic BY MEASUREMENT,
# whatever it is called, so the next such bucket cannot be added silently.
# ---------------------------------------------------------------------------


def _real_locators():
    path = C.REPO_ROOT / "apps/mouth/data/perpres-locators.json"
    if not path.exists():  # pragma: no cover - artifact always shipped
        return None
    return C.load_locators(path)


def test_priority_listing_is_not_an_ownership_citation():
    """GUILT, pinned on the live artifact: the excluded bucket really is the
    degenerate case, and it really says nothing about foreign ownership."""
    locators = _real_locators()
    assert locators, "artifact missing — this pin cannot verify"

    priority = [v for v in locators.values() if v.get("bucket") == "priority-lampiran-i"]
    assert priority, "bucket vanished — re-derive this pin before deleting it"
    assert len({v["cite"] for v in priority}) == 1, "no longer degenerate"
    assert not any(
        w in v["cite"].lower()
        for v in priority
        for w in ("asing", "%", "foreign", "modal", "ownership")
    ), "priority cites now assert ownership — re-open the exclusion"
    assert "priority-lampiran-i" not in C.SPECIFIC_CITATION_BUCKETS


def test_every_eligible_bucket_is_code_named_by_measurement():
    """INNOCENCE for the narrowing, and the tripwire for the NEXT bucket: what
    stays in the set must earn it on the artifact, not by being named there.

    `named-in-annex` passes with 61 distinct cites across 270 codes, several
    carrying the KBLI-2020 crosswalk that earned the entry.
    """
    locators = _real_locators()
    assert locators, "artifact missing — this pin cannot verify"

    assert C.SPECIFIC_CITATION_BUCKETS, "an empty set would silently pass"
    for bucket in C.SPECIFIC_CITATION_BUCKETS:
        cites = {v["cite"] for v in locators.values() if v.get("bucket") == bucket}
        assert len(cites) > 1, (
            f"{bucket}: {len(cites)} distinct cite(s) — a single repeated string "
            "is a generic default, not a code-named citation"
        )


# ---------------------------------------------------------------------------
# KG dimension (spec §7) — five checks, both directions where the spec says
# both, all DECLARED. Guilt + innocence per scar #3.
#
# `admitted_permit_fn` is injected (never imported at module scope by
# `plan_kg_conformance` itself), so most tests below use the REAL
# `client_admitted_permit` from `apps/backend-rag` — it is a pure string
# classifier, no DB — for fidelity to production behaviour. Two tests use a
# FAKE stand-in instead, where noted, to isolate this detector's OWN logic
# from what the current classifier happens to admit.
# ---------------------------------------------------------------------------

_BACKEND_RAG_FOR_TESTS = C.REPO_ROOT / "apps" / "backend-rag"
if str(_BACKEND_RAG_FOR_TESTS) not in sys.path:
    sys.path.insert(0, str(_BACKEND_RAG_FOR_TESTS))
from backend.services.kbli_requires_kind import (  # noqa: E402
    client_admitted_permit as REAL_ADMITTED_PERMIT,
)


def kg_entry(code: str, status: str | None = "REGULATED", targets=None) -> dict:
    return {"code_id": f"kbli:{code}", "licensing_status": status, "targets": targets or []}


def kg_target(entity_id: str, entity_type: str, name: str) -> dict:
    return {"entity_id": entity_id, "entity_type": entity_type, "name": name}


def admitted_kg_target(n: int = 0) -> dict:
    """A target the REAL `client_admitted_permit` reads as admitted."""
    return kg_target(f"perizinan:admit{n}", "perizinan", "Sertifikat Standar")


def fake_admitting_permit_fn(entity_id, entity_type, name) -> bool:
    """Says True for ANY target — isolates a check's own bucketing logic
    (e.g. the `permit_type` arm of `kg_stray_admission`, which the real
    classifier structurally can never admit today) from the classifier."""
    return True


class TestKGStatusFunction:
    def test_guilt_forward_regulated_expected_but_absent(self):
        canonical = store(canon("11111", per_skala=[{"x": 1}]))
        kg = [kg_entry("11111", status="PENDING_REGULATION")]
        report = C.plan_kg_conformance(canonical, kg, set(), REAL_ADMITTED_PERMIT)
        forward = report["kg_status_function"]["forward_failures"]
        assert [d["code"] for d in forward] == ["11111"]
        assert report["kg_status_function"]["reverse_failures"] == []

    def test_guilt_reverse_pending_regulation_expected_but_regulated(self):
        """The measured 91300 shape: zero canonical rows, KG says REGULATED."""
        canonical = store(canon("91300", per_skala=[]))
        kg = [kg_entry("91300", status="REGULATED", targets=[admitted_kg_target()])]
        report = C.plan_kg_conformance(canonical, kg, set(), REAL_ADMITTED_PERMIT)
        reverse = report["kg_status_function"]["reverse_failures"]
        assert [d["code"] for d in reverse] == ["91300"]

    def test_innocence_both_directions_conformant(self):
        canonical = store(
            canon("11111", per_skala=[{"x": 1}]),
            canon("22222", per_skala=[]),
        )
        kg = [kg_entry("11111", status="REGULATED"), kg_entry("22222", status="PENDING_REGULATION")]
        report = C.plan_kg_conformance(canonical, kg, set(), REAL_ADMITTED_PERMIT)
        assert report["kg_status_function"]["forward_failures"] == []
        assert report["kg_status_function"]["reverse_failures"] == []

    def test_innocence_allowlisted_code_excluded_from_manifest(self):
        """A NOT_APPLICABLE_OSS code with zero rows and REGULATED (not
        PENDING_REGULATION) would fail the reverse direction if judged — the
        manifest exclusion is what keeps it out of both lists."""
        canonical = store(canon("84111", per_skala=[]))
        kg = [kg_entry("84111", status="REGULATED")]
        report = C.plan_kg_conformance(canonical, kg, {"84111"}, REAL_ADMITTED_PERMIT)
        assert report["kg_status_function"]["forward_failures"] == []
        assert report["kg_status_function"]["reverse_failures"] == []
        assert report["allowlist_excluded"] == 1

    def test_innocence_phase1b_code_excluded_from_manifest(self):
        record = canon(
            "55555",
            per_skala=[
                {
                    "persyaratan": (
                        "Lembaga OSS hanya menerbitkan NIB. Permohonan Perizinan "
                        "Berusaha diajukan ke Kementerian terkait."
                    )
                }
            ],
        )
        canonical = store(record)
        kg = [kg_entry("55555", status="PENDING_REGULATION")]  # would fail forward if judged
        report = C.plan_kg_conformance(canonical, kg, set(), REAL_ADMITTED_PERMIT)
        assert report["kg_status_function"]["forward_failures"] == []
        assert report["phase1b_excluded"] == 1

    def test_innocence_s3_code_excluded_from_manifest(self):
        """S3 = admitted >= 1 AND status PENDING_REGULATION, derived from the
        snapshot — this code would fail forward (rows > 0, status not
        REGULATED) if judged; the S3 exclusion is what keeps it out."""
        canonical = store(canon("66666", per_skala=[{"x": 1}]))
        kg = [kg_entry("66666", status="PENDING_REGULATION", targets=[admitted_kg_target()])]
        report = C.plan_kg_conformance(canonical, kg, set(), REAL_ADMITTED_PERMIT)
        assert report["kg_status_function"]["forward_failures"] == []
        assert report["s3_excluded"] == 1

    def test_manifest_arithmetic(self):
        canonical = store(
            canon("10000", per_skala=[]),  # plain manifest member
            canon("84111", per_skala=[]),  # allowlisted
            canon(
                "55555",
                per_skala=[{"persyaratan": "Lembaga OSS hanya menerbitkan NIB. X"}],
            ),  # phase1b
            canon("66666", per_skala=[{"x": 1}]),  # S3
        )
        kg = [
            kg_entry("10000", status="PENDING_REGULATION"),
            kg_entry("84111", status="NOT_APPLICABLE_OSS"),
            kg_entry("55555", status="PENDING_REGULATION"),
            kg_entry("66666", status="PENDING_REGULATION", targets=[admitted_kg_target()]),
        ]
        report = C.plan_kg_conformance(canonical, kg, {"84111"}, REAL_ADMITTED_PERMIT)
        assert report["manifest_size"] == 1
        assert report["phase1b_excluded"] == 1
        assert report["s3_excluded"] == 1
        assert report["allowlist_excluded"] == 1


class TestKGLicencePresence:
    def test_guilt_forward_rows_but_zero_admitted(self):
        canonical = store(canon("11111", per_skala=[{"x": 1}]))
        kg = [kg_entry("11111", status="REGULATED", targets=[])]
        report = C.plan_kg_conformance(canonical, kg, set(), REAL_ADMITTED_PERMIT)
        forward = report["kg_licence_presence"]["forward_failures"]
        assert [d["code"] for d in forward] == ["11111"]

    def test_guilt_reverse_zero_rows_but_admitted(self):
        canonical = store(canon("91300", per_skala=[]))
        kg = [kg_entry("91300", status="REGULATED", targets=[admitted_kg_target()])]
        report = C.plan_kg_conformance(canonical, kg, set(), REAL_ADMITTED_PERMIT)
        reverse = report["kg_licence_presence"]["reverse_failures"]
        assert [d["code"] for d in reverse] == ["91300"]
        assert reverse[0]["admitted"] == 1

    def test_innocence_both_directions_conformant(self):
        canonical = store(
            canon("11111", per_skala=[{"x": 1}]),
            canon("22222", per_skala=[]),
        )
        kg = [
            kg_entry("11111", status="REGULATED", targets=[admitted_kg_target()]),
            kg_entry("22222", status="PENDING_REGULATION", targets=[]),
        ]
        report = C.plan_kg_conformance(canonical, kg, set(), REAL_ADMITTED_PERMIT)
        assert report["kg_licence_presence"]["forward_failures"] == []
        assert report["kg_licence_presence"]["reverse_failures"] == []

    def test_innocence_non_permit_targets_never_count_as_admitted(self):
        """A cost/obligation/duration edge must not satisfy the presence
        check — the whole reason `client_admitted_permit` exists."""
        canonical = store(canon("11111", per_skala=[{"x": 1}]))
        kg = [
            kg_entry(
                "11111",
                status="REGULATED",
                targets=[kg_target("biaya:x", "biaya", "10 Billion IDR")],
            )
        ]
        report = C.plan_kg_conformance(canonical, kg, set(), REAL_ADMITTED_PERMIT)
        forward = report["kg_licence_presence"]["forward_failures"]
        assert [d["code"] for d in forward] == ["11111"]


class TestKGStrayAdmission:
    def test_guilt_real_classifier_admits_the_third_placeholder_id(self):
        """MEASURED (this PR): `izin_usaha_status_pending_regulation`'s name
        ("Status Perizinan PENDING_REGULATION", no colon) does not match
        `_NOT_A_PERMIT_LABELS`'s exact string and survives
        `permit_name_verdict` as a permit — the ID check below is what
        catches it, not the name rule."""
        canonical = store(canon("65121"))
        kg = [
            kg_entry(
                "65121",
                status="PENDING_REGULATION",
                targets=[
                    kg_target(
                        "izin_usaha_status_pending_regulation",
                        "izin_usaha",
                        "Status Perizinan PENDING_REGULATION",
                    )
                ],
            )
        ]
        report = C.plan_kg_conformance(canonical, kg, set(), REAL_ADMITTED_PERMIT)
        failures = report["kg_stray_admission"]["failures"]
        assert [f["code"] for f in failures] == ["65121"]
        assert failures[0]["entity_id"] == "izin_usaha_status_pending_regulation"

    def test_innocence_the_two_name_demoted_placeholders_are_already_clean(self):
        """The other two §2.1 ids are demoted by `permit_name_verdict`
        already (F5), so they are never ADMITTED and never trip this check —
        proving the check is phrased over admission, not edge existence."""
        canonical = store(canon("03300"))
        kg = [
            kg_entry(
                "03300",
                status="PENDING_REGULATION",
                targets=[
                    kg_target("status_perizinan_pending", "izin_usaha", "PENDING_REGULATION"),
                    kg_target(
                        "izin_usaha_pending", "izin_usaha", "Status Perizinan: PENDING_REGULATION"
                    ),
                ],
            )
        ]
        report = C.plan_kg_conformance(canonical, kg, set(), REAL_ADMITTED_PERMIT)
        assert report["kg_stray_admission"]["failures"] == []

    def test_guilt_permit_type_node_with_a_fake_admitting_classifier(self):
        """The current classifier structurally can never admit a
        `permit_type` target (`permit_type` left `PERMIT_TYPES` 2026-09-19),
        so this check's `permit_type` arm is future-proofing. A fake
        always-admits function isolates the DETECTOR's own bucketing logic
        from that classifier fact."""
        canonical = store(canon("11111"))
        kg = [
            kg_entry(
                "11111",
                targets=[kg_target("permit_type:kitas", "permit_type", "KITAS")],
            )
        ]
        report = C.plan_kg_conformance(canonical, kg, set(), fake_admitting_permit_fn)
        failures = report["kg_stray_admission"]["failures"]
        assert [f["code"] for f in failures] == ["11111"]

    def test_innocence_an_ordinary_admitted_permit_never_trips_the_check(self):
        canonical = store(canon("11111"))
        kg = [kg_entry("11111", targets=[admitted_kg_target()])]
        report = C.plan_kg_conformance(canonical, kg, set(), REAL_ADMITTED_PERMIT)
        assert report["kg_stray_admission"]["failures"] == []

    def test_innocence_a_kitas_edge_that_is_no_longer_admitted_is_clean(self):
        """After F5, a permit:kitas-shaped edge can still EXIST and must
        read clean because it is no longer ADMITTED — phrased over
        admission, never over edge existence."""
        canonical = store(canon("11111"))
        kg = [
            kg_entry(
                "11111",
                targets=[kg_target("permit_type:kitas", "permit_type", "KITAS")],
            )
        ]
        report = C.plan_kg_conformance(canonical, kg, set(), REAL_ADMITTED_PERMIT)
        assert report["kg_stray_admission"]["failures"] == []


class TestKGAllowlistContradiction:
    def test_guilt_nonzero_rows(self):
        canonical = store(canon("84111", per_skala=[{"x": 1}]))
        kg = [kg_entry("84111", status="NOT_APPLICABLE_OSS")]
        report = C.plan_kg_conformance(canonical, kg, {"84111"}, REAL_ADMITTED_PERMIT)
        failures = report["kg_allowlist_contradiction"]["failures"]
        assert [f["code"] for f in failures] == ["84111"]

    def test_guilt_nonzero_admitted(self):
        canonical = store(canon("84111", per_skala=[]))
        kg = [kg_entry("84111", status="NOT_APPLICABLE_OSS", targets=[admitted_kg_target()])]
        report = C.plan_kg_conformance(canonical, kg, {"84111"}, REAL_ADMITTED_PERMIT)
        failures = report["kg_allowlist_contradiction"]["failures"]
        assert [f["code"] for f in failures] == ["84111"]

    def test_guilt_status_not_exactly_not_applicable_oss(self):
        canonical = store(canon("84111", per_skala=[]))
        kg = [kg_entry("84111", status="PENDING_REGULATION")]
        report = C.plan_kg_conformance(canonical, kg, {"84111"}, REAL_ADMITTED_PERMIT)
        failures = report["kg_allowlist_contradiction"]["failures"]
        assert [f["code"] for f in failures] == ["84111"]

    def test_innocence_all_three_conditions_hold(self):
        canonical = store(canon("84111", per_skala=[]))
        kg = [kg_entry("84111", status="NOT_APPLICABLE_OSS", targets=[])]
        report = C.plan_kg_conformance(canonical, kg, {"84111"}, REAL_ADMITTED_PERMIT)
        assert report["kg_allowlist_contradiction"]["failures"] == []
        assert report["kg_allowlist_contradiction"]["allowlist_size"] == 1


class TestKGNodePresence:
    def test_guilt_forward_canonical_code_has_no_kg_node(self):
        canonical = store(canon("01122"))
        report = C.plan_kg_conformance(canonical, [], set(), REAL_ADMITTED_PERMIT)
        assert report["kg_node_presence"]["forward_failures"] == ["01122"]

    def test_guilt_reverse_kg_only_code_without_the_phantom_marker(self):
        canonical = store()
        kg = [kg_entry("99999", status="REGULATED")]
        report = C.plan_kg_conformance(canonical, kg, set(), REAL_ADMITTED_PERMIT)
        reverse = report["kg_node_presence"]["reverse_failures"]
        assert [d["code"] for d in reverse] == ["99999"]

    def test_innocence_kg_only_code_with_the_phantom_marker_is_clean(self):
        canonical = store()
        kg = [kg_entry("99999", status=C.NOT_IN_KBLI_2025_STATUS)]
        report = C.plan_kg_conformance(canonical, kg, set(), REAL_ADMITTED_PERMIT)
        assert report["kg_node_presence"]["reverse_failures"] == []

    def test_innocence_canonical_code_with_a_kg_node_is_clean(self):
        canonical = store(canon("11111"))
        kg = [kg_entry("11111", status="REGULATED")]
        report = C.plan_kg_conformance(canonical, kg, set(), REAL_ADMITTED_PERMIT)
        assert report["kg_node_presence"]["forward_failures"] == []


# ---------------------------------------------------------------------------
# CLI wiring — empty KG snapshot is CANNOT VERIFY; a KG failure never turns
# the exit code red (all five checks are DECLARED, per spec §7 / W116)
# ---------------------------------------------------------------------------


def test_empty_kg_snapshot_is_cannot_verify_never_clean(tmp_path, capsys):
    canonical = tmp_path / "c.json"
    canonical.write_text(json.dumps({"data": [canon("01111")]}), encoding="utf-8")
    snap = tmp_path / "s.json"
    snap.write_text(json.dumps([row("01111")]), encoding="utf-8")
    kg_snap = tmp_path / "kg.json"
    kg_snap.write_text("[]", encoding="utf-8")
    rc = C.main(
        [
            "--canonical",
            str(canonical),
            "--locators",
            str(neutral_locators_file(tmp_path)),
            "--table-json",
            str(snap),
            "--kg-json",
            str(kg_snap),
        ]
    )
    assert rc == C.EXIT_CANNOT_VERIFY
    assert "not a clean bill" in capsys.readouterr().out


def test_kg_failures_never_fail_the_cli_declared_only(tmp_path):
    """W116: all five KG checks are DECLARED — an otherwise-conformant run
    must stay exit 0 even when the KG dimension reports real failures."""
    canonical = tmp_path / "c.json"
    canonical.write_text(json.dumps({"data": [canon("01111", per_skala=[{"x": 1}])]}), encoding="utf-8")
    snap = tmp_path / "s.json"
    snap.write_text(json.dumps([row("01111", rows=1)]), encoding="utf-8")
    kg_snap = tmp_path / "kg.json"
    kg_snap.write_text(
        json.dumps([{"code_id": "kbli:01111", "licensing_status": "PENDING_REGULATION", "targets": []}]),
        encoding="utf-8",
    )
    rc = C.main(
        [
            "--canonical",
            str(canonical),
            "--locators",
            str(neutral_locators_file(tmp_path)),
            "--table-json",
            str(snap),
            "--kg-json",
            str(kg_snap),
        ]
    )
    assert rc == C.EXIT_OK


def test_kg_section_renders_and_reports_failures_in_json(tmp_path):
    canonical = tmp_path / "c.json"
    canonical.write_text(json.dumps({"data": [canon("01111", per_skala=[{"x": 1}])]}), encoding="utf-8")
    snap = tmp_path / "s.json"
    snap.write_text(json.dumps([row("01111", rows=1)]), encoding="utf-8")
    kg_snap = tmp_path / "kg.json"
    kg_snap.write_text(
        json.dumps([{"code_id": "kbli:01111", "licensing_status": "PENDING_REGULATION", "targets": []}]),
        encoding="utf-8",
    )
    rc = C.main(
        [
            "--canonical",
            str(canonical),
            "--locators",
            str(neutral_locators_file(tmp_path)),
            "--table-json",
            str(snap),
            "--kg-json",
            str(kg_snap),
            "--json",
        ]
    )
    assert rc == C.EXIT_OK


def test_malformed_kg_allowlist_path_is_cannot_verify_not_a_crash(tmp_path, capsys):
    canonical = tmp_path / "c.json"
    canonical.write_text(json.dumps({"data": [canon("01111")]}), encoding="utf-8")
    snap = tmp_path / "s.json"
    snap.write_text(json.dumps([row("01111")]), encoding="utf-8")
    rc = C.main(
        [
            "--canonical",
            str(canonical),
            "--locators",
            str(neutral_locators_file(tmp_path)),
            "--table-json",
            str(snap),
            "--kg-allowlist",
            str(tmp_path / "no-such-allowlist.json"),
        ]
    )
    assert rc == C.EXIT_CANNOT_VERIFY
    assert "CANNOT VERIFY" in capsys.readouterr().out


def test_emit_sql_prints_both_queries():
    rc = C.main(["--emit-sql"])
    assert rc == C.EXIT_OK
