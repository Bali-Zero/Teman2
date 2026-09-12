"""Obligations register: catalog validation, applicability, due dates, profile mapping, repository.

Pure-function tests plus the repository against mock_db_pool (no database).
Calendar facts used below: 2026-01-31, 2026-02-28, 2026-10-10 and 2027-07-31 are Saturdays;
2026-11-15 is a Sunday; 2027-04-30 is a Friday.
"""

from __future__ import annotations

import re
from dataclasses import fields as dataclass_fields
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from backend.db.migration_base import split_migration_sql
from backend.services.compliance.obligations_register import (
    ATTRIBUTES,
    CatalogError,
    ClientProfile,
    DueRule,
    ObligationRule,
    applies,
    due_dates,
    load_catalog,
    profile_from_rows,
    profile_inputs,
    propose,
)
from backend.services.compliance.obligations_repository import (
    MAX_PAGE,
    ObligationRow,
    ObligationsRepository,
)

MIGRATION = (
    Path(__file__).resolve().parents[3] / "db" / "migrations_v2" / "309_client_obligations.sql"
)
PMA = ClientProfile(company_type="PT_PMA", has_employees=True, employee_count=5, pkp=True)
CV = ClientProfile(company_type="CV")


@pytest.fixture(scope="module")
def catalog() -> dict[str, ObligationRule]:
    return {rule.id: rule for rule in load_catalog()}


def _synthetic(frequency: str, day: int = 10, after: int = 1, basis: str = "fiscal", month=None):
    due = DueRule(frequency, day, month, after, "none", basis)
    return ObligationRule("synthetic", "n", "a", "s", False, (), due)


def _catalog_file(tmp_path: Path, predicate: str, extra: str = "") -> Path:
    path = tmp_path / "catalog.yaml"
    path.write_text(
        "rules:\n"
        "  - id: some_rule\n    name: n\n    authority: a\n    legal_source: s\n"
        f"    applies_if:\n      - {predicate}\n"
        "    due: {frequency: monthly, day: 10, months_after_period_end: 1, roll: none}\n" + extra
    )
    return path


# -- catalog ---------------------------------------------------------------------------------


def test_catalog_loads_and_every_rule_validates(catalog):
    assert len(catalog) >= 15
    assert not any(rule.verified for rule in catalog.values())
    assert {"lkpm_quarterly", "spt_masa_pph21", "spt_tahunan_badan", "pse_registration"} <= set(
        catalog
    )


def test_unscheduled_rules_name_their_trigger(catalog):
    for rule in catalog.values():
        unscheduled = rule.due.frequency in ("one_time", "event")
        assert (rule.trigger is not None) == unscheduled, rule.id


@pytest.mark.parametrize(
    ("predicate", "message"),
    [
        ("{attr: pkp, op: truthy}", "unknown op"),
        ("{attr: sells_on_marketplaces, op: is_true}", "unknown attr"),
        ("{attr: company_type, op: in, value: [PT_PMA, PT_XYZ]}", "impossible company_type"),
        ("{attr: pkp, op: is_true, value: true}", "is_true"),
        ("{attr: employee_count, op: gte, value: many}", "gte"),
        ('{attr: pkp, op: eq, value: "true"}', "impossible pkp"),
        ("{attr: investment_stage, op: eq, value: comercial}", "impossible investment_stage"),
        ('{attr: employee_count, op: in, value: ["5"]}', "impossible employee_count"),
        ("{attr: fiscal_year_end, op: eq, value: 12-32}", "impossible fiscal_year_end"),
    ],
)
def test_load_catalog_rejects_bad_predicates(tmp_path, predicate, message):
    with pytest.raises(CatalogError, match=message):
        load_catalog(_catalog_file(tmp_path, predicate))


def test_load_catalog_accepts_a_valid_file(tmp_path):
    rules = load_catalog(_catalog_file(tmp_path, "{attr: employee_count, op: gte, value: 1}"))
    assert [r.id for r in rules] == ["some_rule"]


def test_load_catalog_rejects_duplicate_rule_ids(tmp_path):
    path = _catalog_file(tmp_path, "{attr: pkp, op: is_true}")
    path.write_text(path.read_text() + path.read_text().split("rules:\n", 1)[1])
    with pytest.raises(CatalogError, match="duplicate rule ids"):
        load_catalog(path)


def test_load_catalog_rejects_duplicate_yaml_keys(tmp_path):
    extra = "    due: {frequency: annual, day: 31, months_after_period_end: 4, roll: none}\n"
    with pytest.raises(CatalogError, match="duplicate keys"):
        load_catalog(_catalog_file(tmp_path, "{attr: pkp, op: is_true}", extra))


# -- applicability ---------------------------------------------------------------------------


def test_lkpm_applies_to_pt_pma_not_cv(catalog):
    assert applies(catalog["lkpm_quarterly"], PMA)
    assert not applies(catalog["lkpm_quarterly"], CV)
    assert applies(catalog["spt_tahunan_badan"], CV)


@pytest.mark.parametrize(
    "rule_id", ["spt_masa_pph21", "bpjs_kesehatan_monthly", "bpjs_ketenagakerjaan_monthly"]
)
def test_employee_rules_need_employees(catalog, rule_id):
    assert applies(catalog[rule_id], PMA)
    assert not applies(catalog[rule_id], ClientProfile(company_type="PT_PMA"))


def test_vat_return_needs_pkp(catalog):
    assert applies(catalog["spt_masa_ppn"], PMA)
    assert not applies(catalog["spt_masa_ppn"], CV)


def test_pse_registration_needs_online_and_unregistered(catalog):
    online = ClientProfile(company_type="PT_PMDN", serves_indonesian_users_online=True)
    registered = ClientProfile(
        company_type="PT_PMDN", serves_indonesian_users_online=True, pse_registered=True
    )
    assert applies(catalog["pse_registration"], online)
    assert not applies(catalog["pse_registration"], registered)
    assert not applies(catalog["pse_registration"], PMA)


# C4 (#6122): a FOREIGN_PLATFORM client must never get these six domestic-employer/VAT rules,
# even with has_employees/pkp set true — the catalog's company_type list excludes it on purpose.
@pytest.mark.parametrize(
    "rule_id",
    [
        "pph21_payment",
        "spt_masa_pph21",
        "spt_masa_ppn",
        "bpjs_kesehatan_monthly",
        "bpjs_ketenagakerjaan_monthly",
        "wajib_lapor_ketenagakerjaan",
    ],
)
def test_foreign_platform_excluded_from_employer_and_vat_rules(catalog, rule_id):
    platform = ClientProfile(company_type="FOREIGN_PLATFORM", has_employees=True, pkp=True)
    pma = ClientProfile(company_type="PT_PMA", has_employees=True, pkp=True)
    assert not applies(catalog[rule_id], platform)
    assert applies(catalog[rule_id], pma)


# -- due dates -------------------------------------------------------------------------------


def test_monthly_payment_day_15_rolls_over_weekend(catalog):
    assert due_dates(catalog["pph21_payment"], PMA, date(2026, 10, 1), 30) == [
        ("2026-09", date(2026, 10, 15))
    ]
    assert due_dates(catalog["pph23_26_payment"], PMA, date(2026, 11, 1), 30) == [
        ("2026-10", date(2026, 11, 16))
    ]


def test_bpjs_ketenagakerjaan_period_is_the_contribution_month(catalog):
    assert due_dates(catalog["bpjs_ketenagakerjaan_monthly"], PMA, date(2026, 10, 1), 31) == [
        ("2026-09", date(2026, 10, 15))
    ]


def test_payment_and_return_are_separate_deadlines(catalog):
    assert due_dates(catalog["spt_masa_pph21"], PMA, date(2026, 10, 1), 30) == [
        ("2026-09", date(2026, 10, 20))
    ]
    assert due_dates(catalog["spt_masa_pph23_26"], PMA, date(2026, 10, 15), 10) == [
        ("2026-09", date(2026, 10, 20))
    ]


def test_roll_none_keeps_the_weekend_date(catalog):
    assert due_dates(catalog["bpjs_kesehatan_monthly"], PMA, date(2026, 10, 1), 30) == [
        ("2026-10", date(2026, 10, 10))
    ]


def test_day_31_clamps_to_month_end_then_rolls(catalog):
    # 2025-12 is due Sat 31 Jan and rolls INTO the window; 2026-01 is due 28 (not 31) Feb.
    assert due_dates(catalog["spt_masa_ppn"], PMA, date(2026, 2, 1), 40) == [
        ("2025-12", date(2026, 2, 2)),
        ("2026-01", date(2026, 3, 2)),
    ]


LKPM_2026 = [
    ("2025-Q4", date(2026, 1, 10)),
    ("2026-Q1", date(2026, 4, 10)),
    ("2026-Q2", date(2026, 7, 10)),
    ("2026-Q3", date(2026, 10, 10)),
]


def test_lkpm_quarterly_dates_for_december_fiscal_year(catalog):
    assert due_dates(catalog["lkpm_quarterly"], PMA, date(2026, 1, 1), 365) == LKPM_2026


def test_lkpm_stays_on_calendar_quarters_for_non_calendar_fiscal_year(catalog):
    june_fy = ClientProfile(company_type="PT_PMA", fiscal_year_end="06-30")
    assert due_dates(catalog["lkpm_quarterly"], june_fy, date(2026, 1, 1), 365) == LKPM_2026


def test_fiscal_quarters_follow_a_june_fiscal_year():
    june_fy = ClientProfile(company_type="PT_PMA", fiscal_year_end="06-30")
    assert due_dates(_synthetic("quarterly"), june_fy, date(2026, 7, 1), 365) == [
        ("FY2026-Q4", date(2026, 7, 10)),
        ("FY2027-Q1", date(2026, 10, 10)),
        ("FY2027-Q2", date(2027, 1, 10)),
        ("FY2027-Q3", date(2027, 4, 10)),
    ]


def test_annual_spt_badan_four_months_after_december_year_end(catalog):
    assert due_dates(catalog["spt_tahunan_badan"], PMA, date(2027, 1, 1), 365) == [
        ("FY2026", date(2027, 4, 30))
    ]


def test_annual_spt_badan_for_march_year_end_rolls_off_saturday(catalog):
    march_fy = ClientProfile(company_type="PT_PMA", fiscal_year_end="03-31")
    assert due_dates(catalog["spt_tahunan_badan"], march_fy, date(2027, 1, 1), 365) == [
        ("FY2027", date(2027, 8, 2))
    ]


def test_annual_fixed_month_is_the_first_after_fiscal_year_end():
    rule = _synthetic("annual", day=31, after=0, month=3)
    assert due_dates(rule, PMA, date(2027, 1, 1), 365) == [("FY2026", date(2027, 3, 31))]


def test_horizon_start_is_inclusive_and_end_exclusive(catalog):
    rule = catalog["pph21_payment"]
    assert due_dates(rule, PMA, date(2026, 11, 16), 1) == [("2026-10", date(2026, 11, 16))]
    assert due_dates(rule, PMA, date(2026, 10, 19), 28) == []
    assert due_dates(rule, PMA, date(2026, 11, 16), 0) == []
    with pytest.raises(ValueError):
        due_dates(rule, PMA, date(2026, 11, 16), -1)


def test_due_on_a_libur_nasional_moves_to_the_next_business_day():
    # No 2026 catalog date lands on a decreed WEEKDAY, so this case needs a synthetic rule: due on
    # the 17th means Mon 2026-08-17, Proklamasi Kemerdekaan, a holiday that is not also a weekend.
    rule = ObligationRule(
        "synthetic_17", "n", "a", "s", False, (), DueRule("monthly", 17, None, 0, "none", "fiscal")
    )
    rolling = replace(rule, due=replace(rule.due, roll="next_business_day"))
    assert due_dates(rule, PMA, date(2026, 8, 1), 30) == [("2026-08", date(2026, 8, 17))]
    assert due_dates(rolling, PMA, date(2026, 8, 1), 30) == [("2026-08", date(2026, 8, 18))]


def test_due_on_a_cuti_bersama_moves_to_the_next_business_day(catalog):
    # Fri 2026-03-20 is cuti bersama Idulfitri and the block runs to Tue 24 Mar -> Wed 25 Mar.
    assert due_dates(catalog["spt_masa_pph21"], PMA, date(2026, 3, 1), 31) == [
        ("2026-02", date(2026, 3, 25))
    ]


def test_due_on_a_weekend_skips_the_monday_holiday_too(catalog):
    # The PPh 21 DEPOSIT deadline (Pasal 94: the 15th) for Masa Pajak 2026-01 is Sun 15 Feb. The
    # old weekend-only roll stopped on Mon 16 Feb, which is cuti bersama Imlek; Tue 17 Feb is Imlek
    # itself. Wed 18 Feb is the first day the deposit can actually be made.
    assert due_dates(catalog["pph21_payment"], PMA, date(2026, 2, 1), 28) == [
        ("2026-01", date(2026, 2, 18))
    ]
    # The RETURN for the same month is a different deadline (Pasal 171: the 20th) and does not
    # move: Fri 20 Feb 2026 is a business day. Conflating the two is the easy mistake here.
    assert due_dates(catalog["spt_masa_pph21"], PMA, date(2026, 2, 1), 28) == [
        ("2026-01", date(2026, 2, 20))
    ]


def test_a_catalog_roll_none_rule_ignores_the_holiday_block_after_it(catalog):
    # BPJS Ketenagakerjaan for 2026-07 is due Sat 15 Aug with roll: none. The next business day is
    # Tue 18 Aug (Sun 16, then Independence Day on Mon 17), and none of that reaches this rule.
    assert due_dates(catalog["bpjs_ketenagakerjaan_monthly"], PMA, date(2026, 8, 1), 30) == [
        ("2026-07", date(2026, 8, 15))
    ]


def test_a_year_without_a_holiday_table_rolls_weekends_only_and_says_so(catalog):
    # 2028 has no decree yet (they are issued ~September of the preceding year). Sat 2028-01-15
    # therefore rolls on the weekend alone, to Mon 17 Jan, and the proposal says the date is
    # unfinished instead of presenting it as computed.
    rule = catalog["pph21_payment"]
    assert due_dates(rule, PMA, date(2028, 1, 1), 31) == [("2027-12", date(2028, 1, 17))]
    [proposed] = propose([rule], PMA, date(2028, 1, 1), 31)
    assert proposed.needs_review_reason == "holiday calendar for 2028 not loaded"


def test_the_holiday_gap_is_flagged_per_proposal_not_per_run(catalog):
    # One horizon straddles the decreed year and the undecreed one, so the flag cannot be a
    # property of the run: 2026-11 is due inside 2026 and says nothing, 2026-12 lands in 2027.
    reasons = {
        (p.period_key, p.due_date): p.needs_review_reason
        for p in propose([catalog["spt_masa_ppn"]], PMA, date(2026, 12, 1), 75)
    }
    assert reasons == {
        ("2026-11", date(2026, 12, 31)): None,
        ("2026-12", date(2027, 2, 1)): "holiday calendar for 2027 not loaded",
    }


def test_the_holiday_gap_reason_appends_to_the_rules_own_reason(catalog):
    rule = catalog["pph25_installment"]
    assert rule.needs_review_reason  # the rule already has one; the gap must not replace it
    [proposed] = propose([rule], PMA, date(2027, 1, 10), 10)
    assert proposed.needs_review_reason == (
        f"{rule.needs_review_reason}; holiday calendar for 2027 not loaded"
    )


def test_a_roll_none_rule_is_not_flagged_for_an_undecreed_year(catalog):
    # Nothing about an unknown holiday table can change a date that never moves.
    rule = catalog["bpjs_kesehatan_monthly"]
    [proposed] = propose([rule], PMA, date(2027, 1, 1), 15)
    assert proposed.due_date == date(2027, 1, 10)
    assert proposed.needs_review_reason == rule.needs_review_reason


def test_one_time_and_event_rules_produce_nothing(catalog):
    platform = ClientProfile(company_type="FOREIGN_PLATFORM", serves_indonesian_users_online=True)
    assert applies(catalog["pse_registration"], platform)
    assert due_dates(catalog["pse_registration"], platform, date(2026, 9, 11), 365) == []
    proposed = {p.rule_id for p in propose(catalog.values(), platform, date(2026, 9, 11), 365)}
    assert not proposed & {"pse_registration", "pmse_vat_assessment", "wajib_lapor_ketenagakerjaan"}


def test_propose_is_sorted_and_carries_review_reasons(catalog):
    proposed = propose(catalog.values(), PMA, date(2026, 9, 11), 90)
    assert proposed == sorted(proposed, key=lambda p: (p.due_date, p.rule_id, p.period_key))
    assert all(date(2026, 9, 11) <= p.due_date < date(2026, 12, 10) for p in proposed)
    assert ("pph25_installment", "2026-10", date(2026, 11, 16)) in {
        (p.rule_id, p.period_key, p.due_date) for p in proposed
    }
    for p in proposed:
        assert p.needs_review_reason == catalog[p.rule_id].needs_review_reason


# -- profile mapping -------------------------------------------------------------------------


def test_profile_from_rows_maps_pt_pma_and_custom_fields():
    company = {
        "company_type": "PT PMA",
        "custom_fields": {
            "employee_count": "5",
            "pkp": "yes",
            "fiscal_year_end": "03-31",
            "annual_turnover_idr": 1200,
        },
    }
    profile = profile_from_rows({"id": 1}, company)
    assert profile == ClientProfile(
        company_type="PT_PMA",
        has_employees=True,
        employee_count=5,
        pkp=True,
        annual_turnover_idr=1200,
        fiscal_year_end="03-31",
    )


@pytest.mark.parametrize(
    ("company_type", "expected"),
    [
        ("PT Perorangan", "PT_PMDN"),
        ("pt", "PT_PMDN"),
        ("CV", "CV"),
        ("Yayasan", "OTHER"),
        (None, "OTHER"),
    ],
)
def test_profile_from_rows_missing_custom_fields_gives_defaults(company_type, expected):
    profile = profile_from_rows(None, {"company_type": company_type})
    assert profile == ClientProfile(company_type=expected)


@pytest.mark.parametrize("raw", ["\u00b2", "\u00bd", "12x", " ", "-3"])
def test_int_attributes_drop_a_non_decimal_string_instead_of_raising(raw):
    """isdigit() accepts "\u00b2" but int("\u00b2") raises: that ValueError reached the API as a 500."""
    company = {"company_type": "PT PMA", "custom_fields": {"employee_count": raw}}
    assert profile_from_rows(None, company) == ClientProfile(company_type="PT_PMA")


def test_profile_from_rows_reads_json_text_and_drops_malformed_values():
    company = {
        "company_type": "PT PMA",
        "custom_fields": '{"pkp": "maybe", "fiscal_year_end": "13-40", "employee_count": -3}',
    }
    assert profile_from_rows({}, company) == ClientProfile(company_type="PT_PMA")


def test_profile_from_rows_foreign_platform_only_by_flag():
    flagged = {"company_type": "Foreign company", "custom_fields": {"is_foreign_platform": True}}
    assert profile_from_rows(None, flagged).company_type == "FOREIGN_PLATFORM"
    assert profile_from_rows(None, {"company_type": "Foreign company"}).company_type == "OTHER"
    assert profile_from_rows(None, {**flagged, "company_type": "PT PMA"}).company_type == "PT_PMA"


@pytest.mark.parametrize("raw", ["PT. PMA", "PT PMA (Persero)", " pt  pma "])
def test_profile_from_rows_normalises_company_type_spelling(raw):
    assert profile_from_rows(None, {"company_type": raw}).company_type == "PT_PMA"


def test_leap_day_fiscal_year_end_is_kept():
    company = {"company_type": "CV", "custom_fields": {"fiscal_year_end": "02-29"}}
    assert profile_from_rows(None, company).fiscal_year_end == "02-29"


def test_profile_from_rows_survives_unhashable_values():
    company = {"company_type": "PT PMA", "custom_fields": {"investment_stage": [], "pkp": {}}}
    assert profile_from_rows(None, company) == ClientProfile(company_type="PT_PMA")


# --------------------------------------------------------------------------- #
# company_type precedence and the provenance profile_inputs reports (PR M3):
# compliance_company_type is written by PATCH /profile/{client_id} and must win
# over the companies.company_type string, which is what lets a reviewer fix a
# company the string mapping reads as OTHER.
# --------------------------------------------------------------------------- #
def test_compliance_company_type_wins_over_an_unrecognised_company_type_string():
    company = {
        "company_type": "Yayasan Something Unrecognised",
        "custom_fields": {"compliance_company_type": "pt_pma"},
    }
    inputs = profile_inputs(None, company)
    assert inputs.profile.company_type == "PT_PMA"
    assert "compliance_company_type" in inputs.present_keys
    assert "company_type" not in inputs.missing_attributes


def test_compliance_company_type_wins_over_a_recognised_company_type_string_too():
    company = {"company_type": "PT PMA", "custom_fields": {"compliance_company_type": "CV"}}
    assert profile_from_rows(None, company).company_type == "CV"


@pytest.mark.parametrize("bad", ["PT_XYZ", "", None, 7, ["PT_PMA"], {}])
def test_invalid_compliance_company_type_falls_back_to_the_string_mapping(bad):
    company = {"company_type": "PT PMA", "custom_fields": {"compliance_company_type": bad}}
    assert profile_from_rows(None, company).company_type == "PT_PMA"


def test_profile_inputs_reports_present_keys_and_missing_attributes():
    company = {"company_type": "PT PMA", "custom_fields": {"pkp": "yes", "employee_count": 3}}
    inputs = profile_inputs({"id": 1}, company)
    assert set(inputs.present_keys) == {"pkp", "employee_count"}
    assert "has_employees" not in inputs.missing_attributes  # derived from employee_count > 0
    assert {"pse_registered", "annual_turnover_idr", "investment_stage"} <= set(
        inputs.missing_attributes
    )
    assert "company_type" not in inputs.missing_attributes  # the string mapped to PT_PMA


def test_profile_inputs_lists_company_type_as_missing_when_it_defaulted_to_other():
    inputs = profile_inputs(None, {"company_type": "Koperasi"})
    assert inputs.profile.company_type == "OTHER"
    assert "company_type" in inputs.missing_attributes
    assert inputs.present_keys == ()


def test_profile_inputs_of_a_bare_client_has_every_attribute_missing():
    inputs = profile_inputs(None, None)
    assert set(inputs.missing_attributes) == set(ATTRIBUTES)
    assert inputs.present_keys == ()


def test_profile_inputs_counts_the_foreign_platform_flag_as_a_present_key():
    company = {"company_type": "Foreign co", "custom_fields": {"is_foreign_platform": True}}
    inputs = profile_inputs(None, company)
    assert inputs.profile.company_type == "FOREIGN_PLATFORM"
    assert inputs.present_keys == ("is_foreign_platform",)
    assert "company_type" not in inputs.missing_attributes


@pytest.mark.parametrize(
    "rule_id", ["marketplace_withholding_pmk37", "spt_masa_pph23_26", "halal_certification"]
)
def test_unknown_legal_form_still_gets_free_text_superset_rules(catalog, rule_id):
    assert applies(catalog[rule_id], ClientProfile(company_type="OTHER"))


def test_profile_rejects_unknown_company_type_and_bad_fiscal_year_end():
    with pytest.raises(ValueError):
        ClientProfile(company_type="PT PMA")
    with pytest.raises(ValueError):
        ClientProfile(company_type="PT_PMA", fiscal_year_end="31-12")


# -- repository (mock pool) ------------------------------------------------------------------


async def test_upsert_proposals_is_idempotent_and_never_resets_reviewed_rows(mock_db_pool, catalog):
    pool, conn = mock_db_pool
    conn.fetch.side_effect = [[{"id": 1}, {"id": 2}], []]
    proposals = propose(catalog.values(), PMA, date(2026, 9, 11), 90)[:2]
    repo = ObligationsRepository(pool)
    assert await repo.upsert_proposals(7, proposals) == 2
    assert await repo.upsert_proposals(7, proposals) == 0
    sql, client_id, rule_ids, *_ = conn.fetch.call_args.args
    assert "ON CONFLICT (client_id, rule_id, period_key) DO NOTHING" in sql
    assert "DO UPDATE" not in sql
    assert (client_id, rule_ids) == (7, [p.rule_id for p in proposals])


async def test_upsert_with_no_proposals_skips_the_database(mock_db_pool):
    pool, conn = mock_db_pool
    assert await ObligationsRepository(pool).upsert_proposals(7, []) == 0
    conn.fetch.assert_not_awaited()


@pytest.mark.parametrize("status", ["proposed", "alerted", "done", "bogus"])
async def test_set_status_allows_only_approve_or_reject(mock_db_pool, status):
    pool, conn = mock_db_pool
    with pytest.raises(ValueError):
        await ObligationsRepository(pool).set_status(1, status, "reviewer@example.com")
    conn.fetchrow.assert_not_awaited()


async def test_set_status_updates_only_proposed_rows(mock_db_pool):
    pool, conn = mock_db_pool
    repo = ObligationsRepository(pool)
    assert await repo.set_status(1, "approved", "Reviewer@Example.com") is None
    sql, *args = conn.fetchrow.call_args.args
    assert "WHERE id = $1 AND status = 'proposed'" in sql
    assert args == [1, "approved", "reviewer@example.com", None]
    with pytest.raises(ValueError):
        await repo.set_status(1, "rejected", "  ")


async def test_set_status_returns_the_reviewed_row(mock_db_pool):
    pool, conn = mock_db_pool
    record = {
        "id": 1, "client_id": 7, "rule_id": "spt_masa_ppn", "period_key": "2026-09", "due_date": date(2026, 11, 2),
        "status": "rejected", "needs_review_reason": None, "reviewer_email": "reviewer@example.com",
        "reviewed_at": None, "review_note": "not pkp", "alert_id": None, "created_at": None, "updated_at": None,
    }  # fmt: skip
    conn.fetchrow.return_value = record
    row = await ObligationsRepository(pool).set_status(
        1, "rejected", "reviewer@example.com", "not pkp"
    )
    assert (row.status, row.review_note, row.client_id) == ("rejected", "not pkp", 7)


async def test_list_by_status_validates_and_clamps(mock_db_pool):
    pool, conn = mock_db_pool
    repo = ObligationsRepository(pool)
    with pytest.raises(ValueError):
        await repo.list_by_status("pending")
    assert await repo.list_by_status("proposed", limit=10_000, offset=-5) == []
    assert conn.fetch.call_args.args[1:] == ("proposed", MAX_PAGE, 0)


# -- migration -------------------------------------------------------------------------------


@pytest.mark.skipif(not MIGRATION.exists(), reason="migration 309 not present yet")
def test_migration_309_shape_and_rollback():
    forward, rollback = split_migration_sql(MIGRATION.read_text())
    assert "REFERENCES clients(id) ON DELETE CASCADE" in forward
    assert "UNIQUE (client_id, rule_id, period_key)" in forward
    assert "'proposed','approved','rejected','alerted','done'" in forward
    assert "alert_id            TEXT" in forward
    # Not just presence: pin the two types upsert_proposals()/set_status() rely
    # on structurally. Council finding (kimi-code/k3): a name-only check would
    # pass a `status TEXT NOT NULL` with no default (breaks the upsert, which
    # never writes status) or a `due_date TEXT` (breaks the `$4::date[]` unnest).
    assert "status              TEXT NOT NULL DEFAULT 'proposed'" in forward
    assert "due_date            DATE NOT NULL" in forward
    # Rollback is prose, not literal DDL: the client guardrail blocks writing
    # DROP TABLE/DELETE FROM/etc. into any .sql file, even inside a comment
    # (same convention as 270_wa_broker_jobs.sql) -- it states the inverse in
    # words instead of shipping an unexecutable/blocked statement.
    assert rollback is not None
    assert "client_obligations" in rollback
    assert "guardrail" in rollback.lower()


@pytest.mark.skipif(not MIGRATION.exists(), reason="migration 309 not present yet")
def test_migration_309_covers_every_repository_column():
    """Every ObligationRow field (every column the repository SELECTs, INSERTs or
    UPDATEs) must be declared in the migration DDL -- parsed from the SQL text,
    no database required."""
    forward, _ = split_migration_sql(MIGRATION.read_text())
    start = forward.index("CREATE TABLE IF NOT EXISTS client_obligations")
    create_stmt = forward[start : forward.index(");", start) + 1]
    # Strip /* ... */ block comments first (council finding, codex-gpt-5.6-sol):
    # without this, a column commented out of the real DDL inside a block
    # comment would still count as "declared" by the bare regex below.
    create_stmt = re.sub(r"/\*.*?\*/", "", create_stmt, flags=re.DOTALL)
    declared = set(re.findall(r"^ {4}(?!CONSTRAINT\b)(\w+) +\S", create_stmt, re.MULTILINE))
    expected = {f.name for f in dataclass_fields(ObligationRow)}
    missing = expected - declared
    assert not missing, f"migration is missing columns ObligationRow reads: {sorted(missing)}"
