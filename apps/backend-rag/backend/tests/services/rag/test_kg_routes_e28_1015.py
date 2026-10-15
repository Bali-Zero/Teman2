"""E28 family: Zantara's golden routes say only what the signed pack and the official pages say.

Audit findings F30 (E28A is not a worker permit), F31 (IDR 10 billion is not the PT PMA
capital), F34 (Golden Visa figures per code) and F35 (E28G is not a product).
Sources: signed pack seq-29, saved official pages research/visa/2026-10-15-e28-pages/.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from backend.prompts import zantara_core_v4
from backend.services.rag.kg_enhanced_retrieval import GoldenRoute, KGEnhancedRetrieval

REPO_ROOT = Path(__file__).resolve().parents[6]
PAGES_DIR = REPO_ROOT / "research" / "visa" / "2026-10-15-e28-pages"
ROUTES = KGEnhancedRetrieval.GOLDEN_ROUTES

# Routes that named "KITAS E28G" on origin/main c68ae57f15 (F35).
E28G_ROUTES = (
    "restaurant_foreigner",
    "import_export_business",
    "tech_company_digital",
    "villa_rental_business",
    "hotel_business",
    "real_estate_developer",
    "property_management",
    "visa_pre_investment_d12",
)
SHAREHOLDING = "own shareholding of at least IDR 10 billion"
V4_CITATION = "Permen Investasi/BKPM 5/2025, Article 26"


def _strings(route: GoldenRoute) -> list[str]:
    return [route.name, route.description, *route.path, *route.key_conditions]


def _all_strings() -> list[tuple[str, str]]:
    return [(rid, s) for rid, r in ROUTES.items() for s in _strings(r)]


def _page(code: str) -> str:
    for line in (PAGES_DIR / "e28-pages.receipts.jsonl").read_text().splitlines():
        rec = json.loads(line)
        if rec["key_phrase"] == code:
            return (PAGES_DIR / "text" / Path(rec["text_file"]).name).read_text()
    raise AssertionError(f"no saved page for {code}")


# ── guilt checkers (entity based, so over- and under-match are both tested) ──

E28G_RE = re.compile(r"\bE28G\b")
# E28A named as a worker/employee permit inside ONE step or condition.
E28A_WORKER_RE = re.compile(r"\b(worker|workers|employee|employees|employed|hire|hires|hiring)\b", re.I)
E28A_WORKER_PAREN_RE = re.compile(r"\bE28A\s*\((?:Worker|Employee)", re.I)
# Minimum / paid-up / subscribed capital stated as IDR 10 billion, either word order.
CAP_10BN_RE = re.compile(
    r"(?:minimum|min\.?|paid-up|subscribed)\s+(?:paid-up\s+)?capital[^.;\n]{0,40}?"
    r"(?:IDR|Rp)\s?10 billion|(?:IDR|Rp)\s?10 billion[^.;\n]{0,40}?"
    r"(?:minimum|paid-up|subscribed)?\s*capital",
    re.I,
)
PAID_UP_25_RE = re.compile(r"paid-up capital:?\s*minimum 25%", re.I)


def e28g_offenders(strings: list[tuple[str, str]]) -> list[str]:
    return sorted({rid for rid, s in strings if E28G_RE.search(s)})


def e28a_worker_offenders(strings: list[tuple[str, str]]) -> list[str]:
    return [
        s
        for _, s in strings
        if E28A_WORKER_PAREN_RE.search(s) or (re.search(r"\bE28A\b", s) and E28A_WORKER_RE.search(s))
    ]


def capital_offenders(strings: list[tuple[str, str]]) -> list[str]:
    return [s for _, s in strings if (CAP_10BN_RE.search(s) and "not paid-up" not in s) or PAID_UP_25_RE.search(s)]


# ── checker self-tests: each checker convicts the old text and acquits the new ──


def test_checkers_convict_the_old_text_and_acquit_the_new() -> None:
    assert e28g_offenders([("r", "Sponsor yourself for KITAS E28G (Investor)")]) == ["r"]
    assert e28g_offenders([("r", "Sponsor yourself for the E28A Investor KITAS")]) == []
    assert e28a_worker_offenders([("r", "hire with KITAS E28A (Worker)")])
    assert e28a_worker_offenders([("r", "or E28A (Worker/Director)")])
    assert e28a_worker_offenders([("r", "E28A lets the shareholder act as director; hands-on operational work needs a Working KITAS (E23)")]) == []
    assert capital_offenders([("r", "Minimum capital: IDR 10 billion")])
    assert capital_offenders([("r", "minimum IDR 10 billion capital")])
    assert capital_offenders([("r", "Paid-up capital: minimum 25%")])
    assert capital_offenders([("r", "total investment value of more than IDR 10 billion; IDR 10 billion is not paid-up capital")]) == []
    assert capital_offenders([("r", "your own shareholding of at least IDR 10 billion in that company")]) == []


# ── guilt on the shipped routes ──


def test_no_golden_route_names_e28g() -> None:
    assert e28g_offenders(_all_strings()) == []


def test_no_golden_route_presents_e28a_as_a_worker_permit() -> None:
    assert e28a_worker_offenders(_all_strings()) == []


def test_no_golden_route_states_ten_billion_as_minimum_or_paid_up_capital() -> None:
    assert capital_offenders(_all_strings()) == []


# ── innocence ──


@pytest.mark.parametrize("route_id", E28G_ROUTES)
def test_former_e28g_routes_name_e28a_with_the_page_shareholding(route_id: str) -> None:
    text = "\n".join(_strings(ROUTES[route_id]))
    assert re.search(r"\bE28A\b", text), route_id
    assert SHAREHOLDING in text, route_id
    # the page states it; prove the claim is on the saved E28A page
    assert "Rp10.000.000.000" in _page("E28A")


def test_pt_pma_capital_rule_matches_zantara_core_v4() -> None:
    v4 = zantara_core_v4.ZANTARA_MASTER_TEMPLATE
    assert "Rp2.500.000.000 per limited company" in v4 and V4_CITATION in v4
    for rid in ("pt_pma_setup", "restaurant_foreigner", "import_export_business", "real_estate_developer"):
        text = "\n".join(_strings(ROUTES[rid]))
        assert "IDR 2.5 billion" in text, rid
        assert V4_CITATION in text, rid
        assert "more than IDR 10 billion" in text, rid
    pma = "\n".join(ROUTES["pt_pma_setup"].key_conditions)
    assert "NEVER" not in pma and "not paid-up capital" in pma


def test_foreign_staff_route_is_the_working_kitas_not_e28a() -> None:
    hire = "\n".join(_strings(ROUTES["hire_foreign_worker"]))
    assert "Working KITAS (E23)" in hire
    assert not re.search(r"\bE28A\b", hire)
    tech = "\n".join(_strings(ROUTES["tech_company_digital"]))
    assert "act as director or commissioner" in tech
    assert "operational work needs a Working KITAS (E23)" in tech


# ── F34 visa_golden: every figure bound to the saved page that states it ──

USD_RE = re.compile(r"USD ([\d,]+)")
PAIR_RE = re.compile(r"USD ([\d,]+) for (\d+) years")
PAGE_USD_RE = re.compile(r"US\$\s?([\d.]+)")
CODE_LINE_RE = re.compile(r"^(E28[BCDF])\b")
EXPECTED = {
    "E28B": {(2_500_000, 5), (5_000_000, 10)},
    "E28C": {(350_000, 5), (700_000, 10)},
    "E28D": {(25_000_000, 5), (50_000_000, 10)},
    "E28F": {(5_000_000, 5), (10_000_000, 10)},
}


def _page_figures(code: str) -> set[int]:
    return {int(m.replace(".", "")) for m in PAGE_USD_RE.findall(_page(code))} - {2_000}


def _golden_lines() -> dict[str, str]:
    lines = {}
    for s in ROUTES["visa_golden"].path:
        m = CODE_LINE_RE.match(s)
        if m:
            lines[m.group(1)] = s
    return lines


def golden_figure_errors(lines: dict[str, str]) -> list[str]:
    errors = []
    for code, expected in EXPECTED.items():
        line = lines.get(code, "")
        pairs = {(int(a.replace(",", "")), int(b)) for a, b in PAIR_RE.findall(line)}
        figures = {int(f.replace(",", "")) for f in USD_RE.findall(line)}
        if pairs != expected:
            errors.append(f"{code}: pairs {sorted(pairs)} != {sorted(expected)}")
        extra = {1_000_000} if code == "E28C" else set()
        if figures != {a for a, _ in expected} | extra:
            errors.append(f"{code}: figures {sorted(figures)}")
        if not figures <= _page_figures(code):
            errors.append(f"{code}: figure not on the saved page")
    return errors


def test_visa_golden_figures_equal_the_saved_pages() -> None:
    assert golden_figure_errors(_golden_lines()) == []


def test_visa_golden_figures_checker_convicts_mutants() -> None:
    good = _golden_lines()
    for code, old, new in (
        ("E28B", "USD 2,500,000", "USD 3,500,000"),
        ("E28C", "USD 350,000 for 5 years", "USD 350,000 for 10 years"),
        ("E28D", "USD 50,000,000", "USD 5,000,000"),
        ("E28F", "USD 10,000,000", "USD 15,000,000"),
    ):
        assert old in good[code]
        mutant = dict(good, **{code: good[code].replace(old, new)})
        assert golden_figure_errors(mutant), (code, new)


def test_visa_golden_pages_state_the_conditions() -> None:
    assert "90 hari" in _page("E28B") and "90 hari" in _page("E28D")
    assert "apartemen" in _page("E28C")
    for code in ("E28B", "E28C", "E28D", "E28F"):
        assert "tidak membutuhkan penjamin" in _page(code)
    g = "\n".join(_strings(ROUTES["visa_golden"]))
    assert "within 90 days" in g and "No sponsor" in g and "on consultation" in g
    assert "apartment worth at least USD 1,000,000" in g


def test_visa_golden_drops_claims_no_page_or_pack_supports() -> None:
    g = "\n".join(_strings(ROUTES["visa_golden"])).lower()
    for claim in ("talent", "designated areas", "threshold applies", "property investment", "sktt", "fast-track", "premium"):
        assert claim not in g, claim
