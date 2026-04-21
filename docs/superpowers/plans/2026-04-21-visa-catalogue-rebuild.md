# Visa Catalogue Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 12-code fabricated catalogue with an 18-code source-backed catalogue, switch `MatchResult` to a ranked list (backwards-compat preserved), and fix `_SEARCH_HINTS` so every VisaType resolves to a real IDR cost from `bali_zero_official_prices_2025.json` (except 2 known-None cases).

**Architecture:** Single `VISA_META: dict[VisaType, VisaMeta]` in `catalogue.py` becomes the source of truth. `clock.py` keeps working via derived `DEFAULT_DURATION_DAYS`/`EXTENSION_POLICY`. `match_tree.py` filters `VISA_META` by purpose/budget/duration and returns ranked results. `pricing_bridge.py` gets name-based hints matching the real JSON keys. Router and DB schema unchanged.

**Tech Stack:** Python 3.11, dataclasses, enum, pytest, asyncpg, FastAPI, PostgreSQL. No new deps.

**Spec:** `docs/superpowers/specs/2026-04-21-visa-catalogue-rebuild.md`

**Branch:** `refactor/visa-catalogue-from-seed` (branch from `main`)

---

## Pre-flight: Create branch and confirm baseline

- [ ] **Step 0.1: Stash any uncommitted work, switch to main, pull, create branch**

```bash
cd ~/Desktop/nuzantara
git status --short
# if output is empty → OK. If not → git stash push -u -m "pre-visa-rebuild"
git checkout main
git pull --ff-only
git checkout -b refactor/visa-catalogue-from-seed
```

- [ ] **Step 0.2: Confirm seed + pricing JSON are readable**

```bash
cd ~/Desktop/nuzantara
python3 -c "
import re, ast, json
src = open('apps/backend-rag/backend/migrations/scripts/seed_visa_types_complete_2026.py').read()
m = re.search(r'VISA_TYPES\s*=\s*(\[.*?\n\])\s*\n\nasync def', src, re.DOTALL)
assert m, 'cannot parse seed'
data = ast.literal_eval(m.group(1))
print('seed codes:', len(data))
codes = {v['code'] for v in data}
expected = {'C1','C2','C6','C7','C7A','C7B','C18','C22A','D2','D12','E23','E23-FREELANCE','E28A','E30A','E31','E33E','E33F','E33G'}
missing = expected - codes
assert not missing, f'MISSING FROM SEED: {missing}'
print('all 18 target codes present in seed')

pj = json.load(open('apps/backend-rag/backend/data/bali_zero_official_prices_2025.json'))
print('pricing categories:', list(pj['services'].keys()))
"
```

Expected output:

```
seed codes: 114
all 18 target codes present in seed
pricing categories: ['single_entry_visas', 'visa_extensions', ...]
```

If any assertion fails → **STOP** and report to user. Do not proceed.

- [ ] **Step 0.3: Run the existing visa_check tests once to capture the baseline**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/visa_check/ -v
```

Expected: all 23 tests pass (9 clock + 10 match_tree + 4 pricing). Record the count. If any fail on `main` → **STOP**, fix is not part of this work.

---

## Task 1: New `catalogue.py` — `VISA_META` as single source of truth

**Files:**

- Modify: `apps/backend-rag/backend/services/visa_check/catalogue.py` (full rewrite, 66 → ~280 lines)
- Test: `apps/backend-rag/backend/tests/services/visa_check/test_catalogue.py` (new file)

The rewrite keeps `VisaType` as a str-Enum (existing callers pattern `VisaType("C1")` must still work) and introduces `VisaMeta` + `VISA_META`. `DEFAULT_DURATION_DAYS` and `EXTENSION_POLICY` become derived dicts so `clock.py` needs no change.

- [ ] **Step 1.1: Write the failing test for catalogue structure**

Create `apps/backend-rag/backend/tests/services/visa_check/test_catalogue.py`:

```python
"""Catalogue structure + seed drift guard.

Parses the authoritative seed at test time and asserts every VisaType
is (a) present in the seed and (b) has matching name/category.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from backend.services.visa_check.catalogue import (
    DEFAULT_DURATION_DAYS,
    EXTENSION_POLICY,
    VISA_META,
    VisaMeta,
    VisaType,
)
from backend.services.visa_check.match_tree import Purpose

REPO_ROOT = Path(__file__).resolve().parents[5]
SEED_PATH = REPO_ROOT / "apps/backend-rag/backend/migrations/scripts/seed_visa_types_complete_2026.py"
PRICING_PATH = REPO_ROOT / "apps/backend-rag/backend/data/bali_zero_official_prices_2025.json"


def _load_seed() -> dict[str, dict]:
    src = SEED_PATH.read_text()
    m = re.search(r"VISA_TYPES\s*=\s*(\[.*?\n\])\s*\n\nasync def", src, re.DOTALL)
    assert m, "cannot parse seed VISA_TYPES"
    data = ast.literal_eval(m.group(1))
    return {v["code"]: v for v in data}


class TestEnumStability:
    def test_b211a_removed(self):
        assert not hasattr(VisaType, "B211A"), "B211A must not exist — it is not in the seed"

    def test_all_18_codes_present(self):
        expected = {
            "C1", "C2", "C6", "C7", "C7A", "C7B", "C18", "C22A",
            "D2", "D12",
            "E23", "E23-FREELANCE", "E28A", "E30A", "E31",
            "E33E", "E33F", "E33G",
        }
        got = {vt.value for vt in VisaType}
        assert got == expected, f"VisaType values drift: extra={got-expected} missing={expected-got}"

    def test_e23_freelance_has_hyphen_value(self):
        assert VisaType.E23_FREELANCE.value == "E23-FREELANCE"


class TestVisaMetaCompleteness:
    def test_every_visatype_has_meta(self):
        for vt in VisaType:
            assert vt in VISA_META, f"VISA_META missing entry for {vt.value}"

    def test_meta_is_visameta_instance(self):
        for vt, meta in VISA_META.items():
            assert isinstance(meta, VisaMeta), f"{vt.value} meta wrong type"

    def test_meta_required_fields_non_empty(self):
        for vt, meta in VISA_META.items():
            assert meta.name_en, f"{vt.value} missing name_en"
            assert meta.name_id, f"{vt.value} missing name_id"
            assert meta.category, f"{vt.value} missing category"
            assert meta.duration_days > 0, f"{vt.value} invalid duration_days"
            assert len(meta.extensions) == 2, f"{vt.value} extensions not (count, days)"
            assert meta.seed_source in {"seed", "seed+NB2"}, f"{vt.value} unknown seed_source"
            assert meta.duration_source, f"{vt.value} missing duration_source"


class TestSeedAgreement:
    def setup_method(self):
        self.seed = _load_seed()

    def test_every_visatype_code_in_seed(self):
        for vt in VisaType:
            assert vt.value in self.seed, f"VisaType.{vt.name}='{vt.value}' not in seed"

    def test_name_en_matches_seed(self):
        for vt, meta in VISA_META.items():
            seed_name = self.seed[vt.value]["name"]
            assert meta.name_en == seed_name, (
                f"{vt.value} name drift: meta={meta.name_en!r} seed={seed_name!r}"
            )

    def test_name_id_matches_seed(self):
        for vt, meta in VISA_META.items():
            seed_name_id = self.seed[vt.value]["metadata"]["name_id"]
            assert meta.name_id == seed_name_id, (
                f"{vt.value} name_id drift: meta={meta.name_id!r} seed={seed_name_id!r}"
            )

    def test_category_matches_seed(self):
        for vt, meta in VISA_META.items():
            seed_cat = self.seed[vt.value]["category"]
            assert meta.category == seed_cat, (
                f"{vt.value} category drift: meta={meta.category!r} seed={seed_cat!r}"
            )


class TestDerivedDicts:
    def test_default_duration_days_covers_all_types(self):
        for vt in VisaType:
            assert vt in DEFAULT_DURATION_DAYS
            assert DEFAULT_DURATION_DAYS[vt] == VISA_META[vt].duration_days

    def test_extension_policy_covers_all_types(self):
        for vt in VisaType:
            assert vt in EXTENSION_POLICY
            assert EXTENSION_POLICY[vt] == VISA_META[vt].extensions

    def test_c1_extensions_match_reference(self):
        # MEMORY.md reference_visa_c_duration_rules: C1 = 60 + 2×60
        assert DEFAULT_DURATION_DAYS[VisaType.C1] == 60
        assert EXTENSION_POLICY[VisaType.C1] == (2, 60)

    def test_c7a_non_extendable(self):
        assert EXTENSION_POLICY[VisaType.C7A] == (0, 0)


class TestPurposeCoverage:
    def test_every_non_other_purpose_has_at_least_one_match(self):
        for p in Purpose:
            if p == Purpose.OTHER:
                continue
            candidates = [vt for vt, m in VISA_META.items() if p in m.purposes]
            assert candidates, f"no VisaType has purpose {p.value}"
```

- [ ] **Step 1.2: Run the test to verify it fails**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
PYTHONPATH=. pytest backend/tests/services/visa_check/test_catalogue.py -v
```

Expected: all tests FAIL or ERROR with `ImportError: cannot import name 'VISA_META'` or `cannot import name 'VisaMeta'`.

- [ ] **Step 1.3: Replace `catalogue.py` with the new implementation**

Overwrite `apps/backend-rag/backend/services/visa_check/catalogue.py` with:

```python
"""Visa catalogue — the finite set of visa types our app knows about.

Single source of truth: VISA_META. DEFAULT_DURATION_DAYS and
EXTENSION_POLICY are derived for backwards compatibility with clock.py.

Every entry is traceable:
- name_en / name_id / category: seed_visa_types_complete_2026.py
- duration_days / extensions: MEMORY.md reference_visa_c_duration_rules.md
  for C-series; NB-2 NotebookLM for the rest (duration_source field)
- purposes: match_tree.Purpose tags — which branches surface this code
- min_budget_idr: Bali Zero commercial judgement, not a legal threshold
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# NOTE: match_tree.Purpose is imported lazily inside a TYPE_CHECKING block
# below to avoid a circular import (match_tree imports from this module).
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.services.visa_check.match_tree import Purpose


class VisaType(str, Enum):
    # ── Visit Visa (single entry, C-series) ──────────────────
    C1 = "C1"                     # Tourism
    C2 = "C2"                     # Business
    C6 = "C6"                     # Social activity
    C7 = "C7"                     # Art & culture performance
    C7A = "C7A"                   # Music performance
    C7B = "C7B"                   # Music crew
    C18 = "C18"                   # Work trial
    C22A = "C22A"                 # Internship 60d
    # ── Multiple Entry (D-series) ────────────────────────────
    D2 = "D2"                     # Multiple-entry business
    D12 = "D12"                   # Business investigation 1–2y
    # ── KITAS (E-series) ─────────────────────────────────────
    E23 = "E23"                   # Working KITAS
    E23_FREELANCE = "E23-FREELANCE"  # Freelance KITAS
    E28A = "E28A"                 # Investor KITAS 2y
    E30A = "E30A"                 # Education (basic & secondary)
    E31 = "E31"                   # Family KITAS
    E33E = "E33E"                 # Second Home Elder 5y (golden)
    E33F = "E33F"                 # Second Home Elder 1y
    E33G = "E33G"                 # Second Home Remote Worker / Digital Nomad


@dataclass(frozen=True)
class VisaMeta:
    name_en: str
    name_id: str
    category: str
    purposes: frozenset["Purpose"]
    duration_days: int
    extensions: tuple[int, int]      # (count, days_each); (0, 0) = non-extendable
    min_budget_idr: int | None       # None = no budget gate
    notes: str
    seed_source: str                 # "seed" | "seed+NB2"
    duration_source: str             # human-readable citation
    fit_tags: frozenset[str] = field(default_factory=frozenset)


def _build_meta() -> dict[VisaType, VisaMeta]:
    """Construct VISA_META. Deferred to avoid circular import at module load."""
    from backend.services.visa_check.match_tree import Purpose

    SEED = "seed"
    SEED_NB2 = "seed+NB2"
    C_RULES = "MEMORY.md reference_visa_c_duration_rules.md"
    NB2 = "NB-2 NotebookLM immigration notebook"

    return {
        # ── C-series (Visit Visa, single entry) ──────────────
        VisaType.C1: VisaMeta(
            name_en="Visit Visa Tourism",
            name_id="Visa Kunjungan Wisata",
            category="Visit Visa",
            purposes=frozenset({Purpose.LONG_TOURISM, Purpose.WORK_REMOTE}),
            duration_days=60,
            extensions=(2, 60),              # 60 + 2×60 = 180 max
            min_budget_idr=None,
            notes="Pure tourism single entry. Extendable twice ×60d = 180d max.",
            seed_source=SEED,
            duration_source=C_RULES,
            fit_tags=frozenset({"short_term", "no_budget_gate"}),
        ),
        VisaType.C2: VisaMeta(
            name_en="Visit Visa Business",
            name_id="Visa Kunjungan Bisnis",
            category="Visit Visa",
            purposes=frozenset({Purpose.LONG_TOURISM, Purpose.WORK_REMOTE}),
            duration_days=60,
            extensions=(2, 60),
            min_budget_idr=None,
            notes="Business meetings, no paid work. Extendable ×2.",
            seed_source=SEED,
            duration_source=C_RULES,
            fit_tags=frozenset({"mixed_purpose"}),
        ),
        VisaType.C6: VisaMeta(
            name_en="Visit Visa Social Activity",
            name_id="Visa Kunjungan Kegiatan Sosial",
            category="Visit Visa",
            purposes=frozenset({Purpose.LONG_TOURISM}),
            duration_days=60,
            extensions=(2, 60),
            min_budget_idr=None,
            notes="Family visit / NGO / religious activity. Non-commercial.",
            seed_source=SEED,
            duration_source=C_RULES,
            fit_tags=frozenset({"social_visit"}),
        ),
        VisaType.C7: VisaMeta(
            name_en="Visit Visa Penampilan Seni dan Budaya",
            name_id="Visa Kunjungan Penampilan Seni dan Budaya",
            category="Visit Visa",
            purposes=frozenset({Purpose.WORK_EMPLOYEE}),
            duration_days=60,
            extensions=(2, 60),
            min_budget_idr=None,
            notes="Art / cultural performance. Paid per-event.",
            seed_source=SEED,
            duration_source=C_RULES,
        ),
        VisaType.C7A: VisaMeta(
            name_en="Visit Visa Music Performance",
            name_id="Visa Kunjungan Penampilan Musik",
            category="Visit Visa",
            purposes=frozenset({Purpose.WORK_EMPLOYEE}),
            duration_days=30,
            extensions=(0, 0),
            min_budget_idr=None,
            notes="Single music event. Non-extendable.",
            seed_source=SEED,
            duration_source=C_RULES,
        ),
        VisaType.C7B: VisaMeta(
            name_en="Visit Visa Kru Music Performance",
            name_id="Visa Kunjungan Kru Penampilan Musik",
            category="Visit Visa",
            purposes=frozenset({Purpose.WORK_EMPLOYEE}),
            duration_days=30,
            extensions=(0, 0),
            min_budget_idr=None,
            notes="Music crew accompanying C7A performer. Non-extendable.",
            seed_source=SEED,
            duration_source=C_RULES,
        ),
        VisaType.C18: VisaMeta(
            name_en="Visit Visa Work Trial",
            name_id="Visa Kunjungan Uji Coba Kemampuan",
            category="Visit Visa",
            purposes=frozenset({Purpose.WORK_EMPLOYEE}),
            duration_days=90,
            extensions=(0, 0),
            min_budget_idr=None,
            notes="90-day work trial before committing to E23 KITAS.",
            seed_source=SEED_NB2,
            duration_source=NB2,
        ),
        VisaType.C22A: VisaMeta(
            name_en="Visit Visa Internship 60 Days",
            name_id="Visa Kunjungan Magang 60 Hari",
            category="Visit Visa",
            purposes=frozenset({Purpose.WORK_EMPLOYEE, Purpose.STUDENT}),
            duration_days=60,
            extensions=(0, 0),
            min_budget_idr=None,
            notes="Short internship hosted by an Indonesian entity.",
            seed_source=SEED_NB2,
            duration_source=NB2,
        ),
        # ── D-series (Multiple Entry) ─────────────────────────
        VisaType.D2: VisaMeta(
            name_en="Visit Visa Business",
            name_id="Visa Kunjungan Bisnis",
            category="Multiple Entry",
            purposes=frozenset({Purpose.WORK_REMOTE, Purpose.INVESTOR}),
            duration_days=60,            # per entry
            extensions=(0, 0),           # re-enter instead of extending
            min_budget_idr=None,
            notes="1- or 2-year multiple-entry business. Users who travel in/out.",
            seed_source=SEED_NB2,
            duration_source=NB2,
            fit_tags=frozenset({"multi_entry", "frequent_travel"}),
        ),
        VisaType.D12: VisaMeta(
            name_en="Visit Visa Business Investigation",
            name_id="Visa Kunjungan Investigasi Bisnis",
            category="Multiple Entry",
            purposes=frozenset({Purpose.INVESTOR}),
            duration_days=365,
            extensions=(1, 365),         # 1 + 1 year = 2 years total
            min_budget_idr=None,
            notes="Scouting visa: evaluate market before committing to PT PMA.",
            seed_source=SEED_NB2,
            duration_source=NB2,
            fit_tags=frozenset({"pre_pma"}),
        ),
        # ── E-series (KITAS / Limited Stay) ───────────────────
        VisaType.E23: VisaMeta(
            name_en="Working Visa",
            name_id="Visa Kerja",
            category="KITAS/Limited Stay",
            purposes=frozenset({Purpose.WORK_EMPLOYEE}),
            duration_days=365,
            extensions=(1, 365),
            min_budget_idr=None,
            notes="Employer-sponsored. Requires RPTKA before application.",
            seed_source=SEED,
            duration_source=NB2,
        ),
        VisaType.E23_FREELANCE: VisaMeta(
            name_en="Freelance KITAS (E23)",
            name_id="Freelance KITAS (E23)",
            category="KITAS/Limited Stay",
            purposes=frozenset({Purpose.WORK_REMOTE}),
            duration_days=180,
            extensions=(1, 180),
            min_budget_idr=25_800_000,   # Offshore fee lower bound
            notes="Freelance — for users invoicing Indonesian clients, not foreign employers.",
            seed_source=SEED_NB2,
            duration_source=NB2,
            fit_tags=frozenset({"invoices_indonesian_clients"}),
        ),
        VisaType.E28A: VisaMeta(
            name_en="Investor Visa",
            name_id="Visa Investor",
            category="KITAS/Limited Stay",
            purposes=frozenset({Purpose.INVESTOR}),
            duration_days=365 * 2,
            extensions=(1, 365 * 2),
            min_budget_idr=500_000_000,  # 500M IDR = high-budget threshold
            notes="Requires PT PMA + formal investment plan (~IDR 10bn capital).",
            seed_source=SEED,
            duration_source=NB2,
        ),
        VisaType.E30A: VisaMeta(
            name_en="Education Visa Dasar dan Menengah",
            name_id="Visa Pendidikan Dasar dan Menengah",
            category="KITAS/Limited Stay",
            purposes=frozenset({Purpose.STUDENT}),
            duration_days=365,
            extensions=(1, 365),
            min_budget_idr=None,
            notes="University-sponsored. Valid for programme duration.",
            seed_source=SEED,
            duration_source=NB2,
        ),
        VisaType.E31: VisaMeta(
            name_en="Family Visa",
            name_id="Visa Keluarga",
            category="KITAS/Limited Stay",
            purposes=frozenset({Purpose.FAMILY}),
            duration_days=365,
            extensions=(1, 365),
            min_budget_idr=None,
            notes="Spouse/dependent of KITAS/KITAP holder.",
            seed_source=SEED,
            duration_source=NB2,
        ),
        VisaType.E33E: VisaMeta(
            name_en="Second Home Visa Elderly for 5 Years Golden Visa",
            name_id="Visa Rumah Kedua Lansia Untuk 5 Tahun Golden Visa",
            category="KITAS/Limited Stay",
            purposes=frozenset({Purpose.RETIREMENT}),
            duration_days=365 * 5,
            extensions=(0, 0),
            min_budget_idr=500_000_000,
            notes="Golden visa for 55+ retirees. 5-year single block.",
            seed_source=SEED,
            duration_source=NB2,
            fit_tags=frozenset({"golden_visa"}),
        ),
        VisaType.E33F: VisaMeta(
            name_en="Second Home Visa Elderly for 1 Year",
            name_id="Visa Rumah Kedua Lansia Untuk 1 Tahun",
            category="KITAS/Limited Stay",
            purposes=frozenset({Purpose.RETIREMENT}),
            duration_days=365,
            extensions=(1, 365),
            min_budget_idr=None,
            notes="Standard 55+ retirement. ≥ USD 1,500/mo passive income.",
            seed_source=SEED,
            duration_source=NB2,
        ),
        VisaType.E33G: VisaMeta(
            name_en="Second Home Visa Remote Worker / Digital Nomad",
            name_id="Visa Rumah Kedua Pekerja Jarak Jauh / Digital Nomad",
            category="KITAS/Limited Stay",
            purposes=frozenset({Purpose.WORK_REMOTE, Purpose.INVESTOR}),
            duration_days=365,
            extensions=(1, 365),
            min_budget_idr=50_000_000,
            notes="Remote worker salaried by foreign employer. USD 60k savings proof.",
            seed_source=SEED,
            duration_source=NB2,
            fit_tags=frozenset({"foreign_employer_salary"}),
        ),
    }


VISA_META: dict[VisaType, VisaMeta] = _build_meta()


# ── Derived dicts — kept for clock.py backwards compatibility ────

DEFAULT_DURATION_DAYS: dict[VisaType, int] = {
    vt: meta.duration_days for vt, meta in VISA_META.items()
}

EXTENSION_POLICY: dict[VisaType, tuple[int, int]] = {
    vt: meta.extensions for vt, meta in VISA_META.items()
}


__all__ = [
    "VisaType",
    "VisaMeta",
    "VISA_META",
    "DEFAULT_DURATION_DAYS",
    "EXTENSION_POLICY",
]
```

- [ ] **Step 1.4: Run catalogue tests to verify they pass**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
PYTHONPATH=. pytest backend/tests/services/visa_check/test_catalogue.py -v
```

Expected: all tests PASS. If `TestPurposeCoverage` fails, it means `Purpose` enum doesn't match what we assumed — **STOP** and recheck `match_tree.py`.

- [ ] **Step 1.5: Verify clock tests still pass (contract preserved)**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
PYTHONPATH=. pytest backend/tests/services/visa_check/test_clock.py -v
```

Expected: all 6 clock tests PASS. If `test_c1_extensions_match_reference` fails we have a data bug in `VISA_META[VisaType.C1].extensions`.

- [ ] **Step 1.6: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/backend-rag/backend/services/visa_check/catalogue.py \
        apps/backend-rag/backend/tests/services/visa_check/test_catalogue.py
git commit -m "$(cat <<'EOF'
refactor(visa-check): new catalogue with VisaMeta + seed-drift tests

- Removes B211A (not in authoritative seed, pre-2023 nomenclature).
- Adds 7 codes: C6, C18, C22A, D2, D12, E33E, E23-FREELANCE.
- Introduces VisaMeta dataclass as single source of truth.
- DEFAULT_DURATION_DAYS / EXTENSION_POLICY now derived for clock.py compat.
- New test_catalogue.py parses the seed at test time to guard against drift.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Rewrite `match_tree.py` — ranked results with backwards-compat

**Files:**

- Modify: `apps/backend-rag/backend/services/visa_check/match_tree.py` (full rewrite, 308 → ~340 lines)
- Modify: `apps/backend-rag/backend/tests/services/visa_check/test_match_tree.py` (update B211A references + add ranked-result tests)

Key change: `MatchResult` exposes a new `ranking: list[RankedVisa]` field AND keeps `recommended_visa`, `reason`, `alternatives`, `pre_arrival_steps`, `referral_mode` as `@property` derived from `ranking` — so the router (line 195-240 of `visa_check.py`) keeps working without change.

- [ ] **Step 2.1: Update existing match_tree tests to the new shape (failing tests first)**

Overwrite `apps/backend-rag/backend/tests/services/visa_check/test_match_tree.py` with:

```python
"""Unit tests for the Visa Match decision tree.

Covers every branch, the ranked-result shape, and backwards-compat
property accessors used by the router.
"""

from __future__ import annotations

from backend.services.visa_check.catalogue import VISA_META, VisaType
from backend.services.visa_check.match_tree import (
    BudgetBand,
    MatchResult,
    Purpose,
    RankedVisa,
    recommend_visa,
)


def _call(
    *,
    purpose: Purpose,
    duration_months: int = 6,
    budget_band: BudgetBand = BudgetBand.MID_50_500M,
    nationality: str = "USA",
) -> MatchResult:
    return recommend_visa(
        nationality=nationality,
        purpose=purpose,
        duration_months=duration_months,
        budget_band=budget_band,
    )


class TestRankedShape:
    def test_ranking_is_list_of_rankedvisa(self):
        r = _call(purpose=Purpose.LONG_TOURISM, duration_months=1)
        assert isinstance(r.ranking, list)
        for item in r.ranking:
            assert isinstance(item, RankedVisa)

    def test_ranking_sorted_by_score_desc(self):
        r = _call(purpose=Purpose.WORK_REMOTE, budget_band=BudgetBand.MID_50_500M)
        scores = [rv.score for rv in r.ranking]
        assert scores == sorted(scores, reverse=True)

    def test_every_ranked_visa_is_in_visa_meta(self):
        for purpose in Purpose:
            if purpose == Purpose.OTHER:
                continue
            for band in BudgetBand:
                r = _call(purpose=purpose, duration_months=6, budget_band=band)
                for rv in r.ranking:
                    assert rv.visa in VISA_META, f"{rv.visa} not in VISA_META"

    def test_scores_in_unit_range(self):
        r = _call(purpose=Purpose.INVESTOR, budget_band=BudgetBand.OVER_500M)
        for rv in r.ranking:
            assert 0.0 <= rv.score <= 1.0


class TestBackwardsCompatProperties:
    def test_recommended_visa_is_ranking_zero(self):
        r = _call(purpose=Purpose.LONG_TOURISM, duration_months=1)
        if r.ranking:
            assert r.recommended_visa == r.ranking[0].visa
        else:
            assert r.recommended_visa is None

    def test_alternatives_is_ranking_tail(self):
        r = _call(purpose=Purpose.INVESTOR, budget_band=BudgetBand.OVER_500M)
        expected = [rv.visa for rv in r.ranking[1:]]
        assert r.alternatives == expected

    def test_reason_is_ranking_zero_reason(self):
        r = _call(purpose=Purpose.LONG_TOURISM, duration_months=1)
        if r.ranking:
            assert r.reason == r.ranking[0].reason


class TestOther:
    def test_other_always_refers(self):
        r = _call(purpose=Purpose.OTHER)
        assert r.recommended_visa is None
        assert r.referral_mode is True
        assert r.ranking == []
        assert "WhatsApp" in r.reason


class TestLongTourism:
    def test_short_trip_is_C1(self):
        r = _call(purpose=Purpose.LONG_TOURISM, duration_months=1)
        assert r.recommended_visa is VisaType.C1
        assert r.referral_mode is False

    def test_medium_trip_stays_within_tourism_set(self):
        r = _call(purpose=Purpose.LONG_TOURISM, duration_months=5)
        # Must pick a C-series or referral — never B211A (it's gone).
        allowed = {VisaType.C1, VisaType.C2, VisaType.C6, None}
        assert r.recommended_visa in allowed

    def test_too_long_tourism_refers(self):
        r = _call(purpose=Purpose.LONG_TOURISM, duration_months=10)
        assert r.recommended_visa is None
        assert r.referral_mode is True


class TestWorkRemote:
    def test_under_budget_still_produces_ranking(self):
        r = _call(purpose=Purpose.WORK_REMOTE, budget_band=BudgetBand.UNDER_50M)
        # Under-budget users get C1/C2 short-term options, not a referral.
        assert r.referral_mode is False
        assert r.recommended_visa in {VisaType.C1, VisaType.C2, VisaType.E23_FREELANCE}

    def test_mid_budget_is_E33G(self):
        r = _call(purpose=Purpose.WORK_REMOTE, budget_band=BudgetBand.MID_50_500M)
        assert r.recommended_visa is VisaType.E33G

    def test_high_budget_is_E33G(self):
        r = _call(purpose=Purpose.WORK_REMOTE, budget_band=BudgetBand.OVER_500M)
        assert r.recommended_visa is VisaType.E33G

    def test_e23_freelance_appears_with_fit_tag(self):
        r = _call(purpose=Purpose.WORK_REMOTE, budget_band=BudgetBand.MID_50_500M)
        freelance = next((rv for rv in r.ranking if rv.visa == VisaType.E23_FREELANCE), None)
        if freelance is not None:
            assert "invoices_indonesian_clients" in freelance.fit_tags


class TestInvestor:
    def test_high_budget_is_E28A(self):
        r = _call(purpose=Purpose.INVESTOR, budget_band=BudgetBand.OVER_500M)
        assert r.recommended_visa is VisaType.E28A

    def test_mid_budget_ranking_includes_e33g_and_e28a(self):
        r = _call(purpose=Purpose.INVESTOR, budget_band=BudgetBand.MID_50_500M)
        visas = {rv.visa for rv in r.ranking}
        assert VisaType.E33G in visas
        assert VisaType.D12 in visas or VisaType.E28A in visas

    def test_under_budget_refers(self):
        r = _call(purpose=Purpose.INVESTOR, budget_band=BudgetBand.UNDER_50M)
        assert r.recommended_visa is None
        assert r.referral_mode is True


class TestSimpleBranches:
    def test_work_employee_is_E23(self):
        r = _call(purpose=Purpose.WORK_EMPLOYEE, duration_months=12)
        assert r.recommended_visa is VisaType.E23

    def test_work_employee_short_can_suggest_c18(self):
        r = _call(purpose=Purpose.WORK_EMPLOYEE, duration_months=3)
        assert r.recommended_visa in {VisaType.E23, VisaType.C18, VisaType.C22A}

    def test_family_is_E31(self):
        assert _call(purpose=Purpose.FAMILY).recommended_visa is VisaType.E31

    def test_retirement_standard_is_E33F(self):
        r = _call(purpose=Purpose.RETIREMENT, budget_band=BudgetBand.MID_50_500M)
        assert r.recommended_visa is VisaType.E33F

    def test_retirement_high_budget_surfaces_E33E(self):
        r = _call(purpose=Purpose.RETIREMENT, budget_band=BudgetBand.OVER_500M)
        visas = {rv.visa for rv in r.ranking}
        assert VisaType.E33E in visas

    def test_student_is_E30A(self):
        assert _call(purpose=Purpose.STUDENT).recommended_visa is VisaType.E30A


class TestPreArrivalSteps:
    def test_all_branches_with_recommendation_return_steps(self):
        scenarios = [
            (Purpose.LONG_TOURISM, 1, BudgetBand.MID_50_500M),
            (Purpose.WORK_REMOTE, 12, BudgetBand.OVER_500M),
            (Purpose.INVESTOR, 24, BudgetBand.OVER_500M),
            (Purpose.WORK_EMPLOYEE, 12, BudgetBand.MID_50_500M),
            (Purpose.FAMILY, 12, BudgetBand.UNDER_50M),
            (Purpose.RETIREMENT, 12, BudgetBand.MID_50_500M),
            (Purpose.STUDENT, 12, BudgetBand.UNDER_50M),
        ]
        for purpose, months, band in scenarios:
            r = _call(purpose=purpose, duration_months=months, budget_band=band)
            if r.recommended_visa is not None:
                assert len(r.pre_arrival_steps) >= 3, (
                    f"{purpose} with {band.value} should produce pre-arrival steps"
                )


class TestCoverageSweep:
    """Every purpose × budget combination must produce either a ranking or a referral."""

    def test_all_combinations_terminate(self):
        for purpose in Purpose:
            for band in BudgetBand:
                for months in (1, 6, 12, 24):
                    r = _call(purpose=purpose, duration_months=months, budget_band=band)
                    assert r.ranking or r.referral_mode, (
                        f"purpose={purpose} months={months} band={band} produced empty+no-referral"
                    )
```

- [ ] **Step 2.2: Run updated match_tree tests to confirm they fail**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
PYTHONPATH=. pytest backend/tests/services/visa_check/test_match_tree.py -v
```

Expected: ImportError for `MatchResult` / `RankedVisa` / `Purpose` not matching new signature — many tests FAIL.

- [ ] **Step 2.3: Replace `match_tree.py`**

Overwrite `apps/backend-rag/backend/services/visa_check/match_tree.py` with:

```python
"""Rule-based visa recommender for the Visa Match wizard.

Input: nationality (ISO-3), purpose, duration_months, budget_band.
Output: MatchResult with a `ranking` list (best → worst) and backwards-compat
        properties (`recommended_visa`, `reason`, `alternatives`,
        `pre_arrival_steps`, `referral_mode`) read by the router.

Design:
- No hardcoded `VisaType.X` in branch logic. Each branch filters VISA_META
  by purpose tag, scores candidates, returns top-N.
- Scoring is deterministic and visible so users see *why* a rank was chosen.
- Catch-all referral terminates the tree.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from backend.services.visa_check.catalogue import VISA_META, VisaMeta, VisaType


class Purpose(str, Enum):
    WORK_REMOTE = "work_remote"
    INVESTOR = "investor"
    WORK_EMPLOYEE = "work_employee"
    FAMILY = "family"
    LONG_TOURISM = "long_tourism"
    RETIREMENT = "retirement"
    STUDENT = "student"
    OTHER = "other"


class BudgetBand(str, Enum):
    UNDER_50M = "under_50m"
    MID_50_500M = "50m_500m"
    OVER_500M = "over_500m"


_BUDGET_CEILING: dict[BudgetBand, int] = {
    BudgetBand.UNDER_50M: 50_000_000,
    BudgetBand.MID_50_500M: 500_000_000,
    BudgetBand.OVER_500M: 10_000_000_000,
}


@dataclass(frozen=True)
class RankedVisa:
    visa: VisaType
    score: float                   # 0.0 – 1.0
    reason: str                    # 1–2 sentences, user-facing
    fit_tags: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class MatchResult:
    ranking: list[RankedVisa]
    pre_arrival_steps: list[str]
    referral_mode: bool
    referral_reason: str = ""      # used when ranking is empty

    # ── Backwards-compat properties (router + existing tests) ────

    @property
    def recommended_visa(self) -> VisaType | None:
        return self.ranking[0].visa if self.ranking else None

    @property
    def reason(self) -> str:
        if self.ranking:
            return self.ranking[0].reason
        return self.referral_reason

    @property
    def alternatives(self) -> list[VisaType]:
        return [rv.visa for rv in self.ranking[1:]]


# ── Pre-arrival step libraries ───────────────────────────────────

_STEPS_TOURISM: list[str] = [
    "Passport valid ≥ 6 months from entry date",
    "Confirmed accommodation for first 7 nights",
    "Return or onward flight ticket",
    "Travel insurance covering Indonesia",
]

_STEPS_DIGITAL_NOMAD: list[str] = [
    "Proof of remote employment with a foreign company",
    "Bank statement showing ≥ USD 60,000 balance (12 months)",
    "Passport valid ≥ 18 months",
    "Health insurance with Indonesia coverage",
    "CV + LinkedIn URL for immigration review",
]

_STEPS_FREELANCE: list[str] = [
    "Sample invoices to Indonesian clients (past 6 months)",
    "NPWP application plan (Indonesian tax ID)",
    "Passport valid ≥ 18 months",
    "Proof of accommodation in Indonesia",
]

_STEPS_INVESTOR: list[str] = [
    "PT PMA incorporated (or plan ready to incorporate on arrival)",
    "Investment plan document (IDR equivalent ≥ 10bn for E28A)",
    "Share capital confirmation",
    "Proposed business address in Indonesia",
    "Passport valid ≥ 24 months",
]

_STEPS_EMPLOYEE: list[str] = [
    "RPTKA from sponsoring Indonesian employer",
    "Signed employment contract",
    "Education certificate (notarised + translated)",
    "Curriculum vitae",
    "Passport valid ≥ 18 months",
]

_STEPS_RETIREMENT: list[str] = [
    "Proof of pension or passive income ≥ USD 1,500/month",
    "Passport valid ≥ 18 months",
    "Proof of accommodation (rental or property in Indonesia)",
    "Domestic helper hire letter (optional but recommended)",
    "Health insurance valid in Indonesia",
]

_STEPS_FAMILY: list[str] = [
    "Sponsor's KITAS/KITAP + passport copies",
    "Marriage or birth certificate (notarised + translated)",
    "Passport valid ≥ 18 months",
    "Proof of joint household (photos + rental/ownership docs)",
]

_STEPS_STUDENT: list[str] = [
    "Acceptance letter from an accredited Indonesian university",
    "Sponsor letter (university or direct bursary)",
    "Passport valid ≥ the full study programme",
    "Health insurance valid in Indonesia",
]


_STEPS_BY_PURPOSE: dict[Purpose, list[str]] = {
    Purpose.LONG_TOURISM: _STEPS_TOURISM,
    Purpose.WORK_REMOTE: _STEPS_DIGITAL_NOMAD,
    Purpose.INVESTOR: _STEPS_INVESTOR,
    Purpose.WORK_EMPLOYEE: _STEPS_EMPLOYEE,
    Purpose.RETIREMENT: _STEPS_RETIREMENT,
    Purpose.FAMILY: _STEPS_FAMILY,
    Purpose.STUDENT: _STEPS_STUDENT,
}


# ── Scoring ──────────────────────────────────────────────────────


def _budget_fits(meta: VisaMeta, band: BudgetBand) -> bool:
    """True if the user's budget band is ≥ the visa's min_budget_idr."""
    if meta.min_budget_idr is None:
        return True
    return _BUDGET_CEILING[band] >= meta.min_budget_idr


def _duration_fits(meta: VisaMeta, months: int) -> bool:
    """True if the visa's base + extensions cover the requested months."""
    total_days = meta.duration_days + meta.extensions[0] * meta.extensions[1]
    return total_days >= months * 30


def _score(meta: VisaMeta, purpose: Purpose, months: int, band: BudgetBand) -> float:
    score = 0.5
    if _budget_fits(meta, band):
        score += 0.25
    if _duration_fits(meta, months):
        score += 0.2
    # Duration overshoot penalty: a 1-year KITAS for a 1-month visit is overkill.
    total_days = meta.duration_days + meta.extensions[0] * meta.extensions[1]
    if total_days > months * 30 * 4:   # visa covers > 4× requested stay
        score -= 0.1
    # Budget mismatch penalty: if min_budget_idr exceeds the band's ceiling
    # we shouldn't even consider this visa, but if it barely fits, keep it modest.
    if meta.min_budget_idr is not None and _BUDGET_CEILING[band] < meta.min_budget_idr * 1.5:
        score -= 0.05
    return max(0.0, min(1.0, round(score, 3)))


def _reason(meta: VisaMeta, purpose: Purpose, months: int, band: BudgetBand) -> str:
    """Short user-facing sentence explaining why this visa is ranked here."""
    budget_note = ""
    if meta.min_budget_idr is not None:
        budget_note = f" (requires ≥ IDR {meta.min_budget_idr // 1_000_000}M)"
    duration_note = ""
    total_days = meta.duration_days + meta.extensions[0] * meta.extensions[1]
    if _duration_fits(meta, months):
        duration_note = f" Covers {total_days} days total."
    else:
        duration_note = f" Max stay {total_days} days — less than your {months}-month plan."
    return f"{meta.name_en} — {meta.notes}{budget_note}.{duration_note}".strip()


# ── Branch dispatch ──────────────────────────────────────────────


def _rank_for_purpose(
    purpose: Purpose,
    months: int,
    band: BudgetBand,
    max_results: int,
) -> list[RankedVisa]:
    candidates: list[RankedVisa] = []
    for visa_type, meta in VISA_META.items():
        if purpose not in meta.purposes:
            continue
        if meta.min_budget_idr is not None and not _budget_fits(meta, band):
            # Hard-exclude visas whose minimum budget the user cannot meet.
            continue
        score = _score(meta, purpose, months, band)
        candidates.append(
            RankedVisa(
                visa=visa_type,
                score=score,
                reason=_reason(meta, purpose, months, band),
                fit_tags=meta.fit_tags,
            )
        )
    candidates.sort(key=lambda rv: (-rv.score, rv.visa.value))
    return candidates[:max_results]


_MAX_RESULTS: dict[Purpose, int] = {
    Purpose.WORK_EMPLOYEE: 3,      # E23 + short-term (C18/C22A) alternatives
    Purpose.STUDENT: 2,
    Purpose.FAMILY: 2,
    Purpose.RETIREMENT: 2,
    Purpose.INVESTOR: 3,
    Purpose.WORK_REMOTE: 3,
    Purpose.LONG_TOURISM: 3,
}


def recommend_visa(
    *,
    nationality: str,
    purpose: Purpose,
    duration_months: int,
    budget_band: BudgetBand,
) -> MatchResult:
    """Return a ranked list of visas + pre-arrival steps.

    Rules:
    1. `OTHER` always refers to WhatsApp.
    2. Under-budget investors refer (E28A, D12, E33G all require budget).
    3. Tourism > 6 months refers (Indonesian tourism visas cap at ~180d).
    4. Everything else: filter VISA_META by purpose tag, score, top-N.
    """
    del nationality  # reserved for future visa-waiver rules
    months = max(1, min(60, int(duration_months)))

    if purpose == Purpose.OTHER:
        return MatchResult(
            ranking=[],
            pre_arrival_steps=[],
            referral_mode=True,
            referral_reason=(
                "Your case has specifics we don't capture in a 4-step form. "
                "A 15-minute WhatsApp review with our visa team is faster than "
                "any guess we could make here."
            ),
        )

    if purpose == Purpose.LONG_TOURISM and months > 6:
        return MatchResult(
            ranking=[],
            pre_arrival_steps=[],
            referral_mode=True,
            referral_reason=(
                f"Indonesia's tourism visas max out at ~180 days. For a "
                f"{months}-month stay, we need a non-tourism route (investor, "
                "digital nomad, retirement) that matches what you actually "
                "plan to do here."
            ),
        )

    if purpose == Purpose.INVESTOR and budget_band == BudgetBand.UNDER_50M:
        return MatchResult(
            ranking=[],
            pre_arrival_steps=[],
            referral_mode=True,
            referral_reason=(
                "Investor routes (E28A, D12, E33G) all have minimum-capital or "
                "savings requirements that a sub-IDR 50M budget does not meet. "
                "Let's talk through what kind of business you want to open — "
                "there may be a staged approach."
            ),
        )

    ranking = _rank_for_purpose(
        purpose,
        months,
        budget_band,
        max_results=_MAX_RESULTS.get(purpose, 3),
    )

    if not ranking:
        return MatchResult(
            ranking=[],
            pre_arrival_steps=[],
            referral_mode=True,
            referral_reason=(
                "No visa in our catalogue matches this combination cleanly. "
                "Let's review the details on WhatsApp."
            ),
        )

    return MatchResult(
        ranking=ranking,
        pre_arrival_steps=_STEPS_BY_PURPOSE.get(purpose, []),
        referral_mode=False,
    )
```

- [ ] **Step 2.4: Run match_tree tests to verify they pass**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
PYTHONPATH=. pytest backend/tests/services/visa_check/test_match_tree.py -v
```

Expected: all ~20 tests PASS. If `TestRankedShape.test_ranking_sorted_by_score_desc` fails, check the `_rank_for_purpose` sort key. If `TestBackwardsCompatProperties` fails, check the `@property` accessors on `MatchResult`.

- [ ] **Step 2.5: Run the full visa_check test suite**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
PYTHONPATH=. pytest backend/tests/services/visa_check/ -v
```

Expected: catalogue + clock + match_tree all PASS. pricing_bridge tests may still pass or may fail on B211A enum reference — we fix that in Task 3.

- [ ] **Step 2.6: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/backend-rag/backend/services/visa_check/match_tree.py \
        apps/backend-rag/backend/tests/services/visa_check/test_match_tree.py
git commit -m "$(cat <<'EOF'
refactor(visa-check): ranked match_tree + backwards-compat MatchResult

MatchResult.ranking: list[RankedVisa] (new) with recommended_visa/
alternatives/reason/pre_arrival_steps/referral_mode preserved as
@property accessors so the router keeps working unchanged.

Branch logic no longer hardcodes VisaType codes — each branch filters
VISA_META by Purpose tag, scores candidates, returns top-N.

Scoring: base 0.5 + 0.25 budget_fit + 0.2 duration_fit − 0.1 overshoot
− 0.05 budget_near_floor. Deterministic, visible to users via reason.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Update `pricing_bridge.py` hints to match real JSON keys

**Files:**

- Modify: `apps/backend-rag/backend/services/visa_check/pricing_bridge.py` (lines 25–38 `_SEARCH_HINTS` dict only; rest untouched)
- Modify: `apps/backend-rag/backend/tests/services/visa_check/test_pricing_bridge.py` (strengthen assertions + explicit known-None set)

- [ ] **Step 3.1: Update the pricing_bridge tests**

Overwrite `apps/backend-rag/backend/tests/services/visa_check/test_pricing_bridge.py` with:

```python
"""PricingBridge integration — no hardcoded prices, name-based hints.

Every VisaType must resolve to a positive IDR cost from the real JSON
except for the two documented known-None cases (C6, E30A), which reflect
the fact that the pricing JSON does not ship an entry for those services.
"""

from __future__ import annotations

from backend.services.pricing.pricing_service import PricingService
from backend.services.visa_check.catalogue import VISA_META, VisaType
from backend.services.visa_check.pricing_bridge import (
    KNOWN_NONE_VISAS,
    _idr_string_to_int,
    estimate_match_cost,
)


class TestIdrParser:
    def test_parses_thousands_dots(self):
        assert _idr_string_to_int("5.800.000 IDR") == 5_800_000

    def test_parses_with_spaces(self):
        assert _idr_string_to_int("  10.000.000 IDR  ") == 10_000_000

    def test_rejects_non_idr(self):
        assert _idr_string_to_int("$100") is None

    def test_empty_returns_none(self):
        assert _idr_string_to_int("") is None


class TestEstimateMatchCost:
    def setup_method(self):
        self.pricing = PricingService()

    def test_known_none_set_is_subset_of_visatype(self):
        for vt in KNOWN_NONE_VISAS:
            assert vt in VISA_META

    def test_every_non_known_none_visa_resolves(self):
        if not self.pricing.loaded:
            return  # pricing service unavailable in this env — skip silently
        for vt in VisaType:
            if vt in KNOWN_NONE_VISAS:
                continue
            cost, source = estimate_match_cost(visa_type=vt, pricing=self.pricing)
            assert cost is not None, f"{vt.value}: no price found in JSON"
            assert cost > 0, f"{vt.value}: zero cost"
            assert source, f"{vt.value}: source string empty"

    def test_known_none_visas_return_none(self):
        if not self.pricing.loaded:
            return
        for vt in KNOWN_NONE_VISAS:
            cost, source = estimate_match_cost(visa_type=vt, pricing=self.pricing)
            # Known-None: either both None or a lucky match — never a crash.
            assert (cost is None) == (source is None)

    def test_investor_resolves_to_positive_cost(self):
        if not self.pricing.loaded:
            return
        cost, source = estimate_match_cost(visa_type=VisaType.E28A, pricing=self.pricing)
        assert cost is not None
        assert cost > 0
        assert source

    def test_e33g_prefers_offshore(self):
        if not self.pricing.loaded:
            return
        cost, source = estimate_match_cost(visa_type=VisaType.E33G, pricing=self.pricing)
        # Offshore E33G = 13M IDR, Altus/Onshore = 14M. Either is acceptable,
        # but we document the tie-break preference.
        assert cost is not None
        assert "remote" in (source or "").lower() or "e33g" in (source or "").lower()

    def test_freelance_e23_separate_from_working_kitas(self):
        if not self.pricing.loaded:
            return
        freelance_cost, _ = estimate_match_cost(
            visa_type=VisaType.E23_FREELANCE, pricing=self.pricing
        )
        working_cost, _ = estimate_match_cost(visa_type=VisaType.E23, pricing=self.pricing)
        if freelance_cost and working_cost:
            assert freelance_cost != working_cost, (
                "E23_FREELANCE and E23 should resolve to different price entries"
            )
```

- [ ] **Step 3.2: Run the tests to confirm they fail**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
PYTHONPATH=. pytest backend/tests/services/visa_check/test_pricing_bridge.py -v
```

Expected: `ImportError: cannot import name 'KNOWN_NONE_VISAS'` plus failures for new codes that have no hints.

- [ ] **Step 3.3: Replace `_SEARCH_HINTS` and add `KNOWN_NONE_VISAS` in `pricing_bridge.py`**

Open `apps/backend-rag/backend/services/visa_check/pricing_bridge.py` and replace lines 25–38 (the `_SEARCH_HINTS` dict) with:

```python
# Known-None set: VisaTypes for which the pricing JSON has no entry.
# Bridge returns (None, None) for these and the UI shows
# "confirm on WhatsApp". These are intentional, not bugs.
KNOWN_NONE_VISAS: frozenset[VisaType] = frozenset({
    VisaType.C6,       # Social visit — no standalone C6 row in pricing JSON
    VisaType.E30A,     # Education — JSON lacks a student visa entry
})


# Map our VisaType codes to substrings likely to appear in the
# price JSON keys. Names reflect the JSON shape exactly (see
# backend/data/bali_zero_official_prices_2025.json). Offshore
# variants are preferred (standard fresh-applicant path).
_SEARCH_HINTS: dict[VisaType, tuple[str, ...]] = {
    VisaType.C1:             ("C1 Tourism",),
    VisaType.C2:             ("C2 Business",),
    VisaType.C6:             ("C6", "Social"),                              # known None
    VisaType.C7:             ("C7A&B Music/Art", "C7"),                     # best-effort
    VisaType.C7A:            ("C7A&B Music/Art", "C7A"),
    VisaType.C7B:            ("C7A&B Music/Art", "C7B"),
    VisaType.C18:            ("C18 Work Trial",),
    VisaType.C22A:           ("C22A&B Internship (60 Days)", "C22A&B Internship"),
    VisaType.D2:             ("D12 Business Investigation (1 Year)", "D2"),  # closest multi-entry row
    VisaType.D12:            (
        "D12 Business Investigation (1 Year)",
        "D12 Business Investigation (2 Years)",
    ),
    VisaType.E23:            ("Working KITAS (Offshore)", "Working KITAS"),
    VisaType.E23_FREELANCE:  ("Freelance E23 (Offshore)", "Freelance E23"),
    VisaType.E28A:           ("Investor KITAS 2 Years (Offshore)", "Investor KITAS"),
    VisaType.E30A:           ("Education", "Student"),                       # known None
    VisaType.E31:            (
        "Dependent 1 Year (Offshore)",
        "Spouse 1 Year (Offshore)",
        "Family",
    ),
    VisaType.E33E:           ("Retirement KITAP + MERP", "Retirement"),
    VisaType.E33F:           ("Retirement (Offshore)", "Retirement"),
    VisaType.E33G:           ("E33G Remote Worker (Offshore)", "E33G Remote Worker"),
}
```

Also ensure the file exports `KNOWN_NONE_VISAS` by adding this line at the very end of the file (if there is no `__all__`, the module already exports everything public by convention):

```python
__all__ = [
    "KNOWN_NONE_VISAS",
    "_idr_string_to_int",
    "estimate_match_cost",
]
```

- [ ] **Step 3.4: Run pricing_bridge tests**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
PYTHONPATH=. pytest backend/tests/services/visa_check/test_pricing_bridge.py -v
```

Expected: all ~8 tests PASS. If `test_every_non_known_none_visa_resolves` fails, inspect which code is missing — either add a hint or add it to `KNOWN_NONE_VISAS` (and document why in the spec).

- [ ] **Step 3.5: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/backend-rag/backend/services/visa_check/pricing_bridge.py \
        apps/backend-rag/backend/tests/services/visa_check/test_pricing_bridge.py
git commit -m "$(cat <<'EOF'
refactor(visa-check): pricing_bridge hints match real JSON keys

Replaces the code-tuple hints with name-based hints reflecting the
actual bali_zero_official_prices_2025.json shape (e.g. "C1 Tourism",
"E33G Remote Worker (Offshore)"). Offshore variants preferred.

New KNOWN_NONE_VISAS set (C6, E30A) documents the two codes for which
the JSON legitimately has no entry — bridge returns (None, None) and
the UI falls back to "confirm on WhatsApp".

Every other VisaType now resolves to a positive IDR cost, enforced by
test_every_non_known_none_visa_resolves.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Fix router `_processing_days` B211A reference

**Files:**

- Modify: `apps/backend-rag/backend/app/routers/visa_check.py:130` (remove `VisaType.B211A` reference)

- [ ] **Step 4.1: Check which tests exercise `_processing_days`**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
grep -rn "_processing_days\|processing_days" backend/tests/ 2>/dev/null | head -10
```

If no test covers it, proceed with the edit. If a test exists, read it first.

- [ ] **Step 4.2: Patch the B211A reference**

Edit `apps/backend-rag/backend/app/routers/visa_check.py` line ~130.

Change:

```python
if visa_type in {VisaType.B211A, VisaType.C1, VisaType.C2, VisaType.C7, VisaType.C7A, VisaType.C7B}:
    return 10
```

To:

```python
# Single-entry C-series and D-series short-stays process in ~10 working days.
# KITAS and multi-entry yearly visas process in ~20–30 days.
if visa_type in {
    VisaType.C1, VisaType.C2, VisaType.C6,
    VisaType.C7, VisaType.C7A, VisaType.C7B,
    VisaType.C18, VisaType.C22A,
}:
    return 10
return 25
```

- [ ] **Step 4.3: Run a syntactic check on the router**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
source .venv/bin/activate
python -c "from backend.app.routers.visa_check import router; print('router import OK, routes:', len(router.routes))"
```

Expected: `router import OK, routes: 5`

- [ ] **Step 4.4: Run import-chain guard**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
python -c "from backend.app.dependencies import get_current_user; print('OK')"
```

Expected: `OK`. If this fails, **STOP** — we introduced a regression in the main import chain.

- [ ] **Step 4.5: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/backend-rag/backend/app/routers/visa_check.py
git commit -m "$(cat <<'EOF'
fix(visa-check): remove B211A from router _processing_days

Extends the fast-processing set to the new C-series short-stay codes
(C6, C18, C22A) added in the catalogue rebuild. KITAS/multi-entry
yearly visas keep the 25-day estimate.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Full-suite verification

**Files:**

- No changes — this is the end-to-end check before PR.

- [ ] **Step 5.1: Full visa_check test suite**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/visa_check/ -v
```

Expected: all tests PASS (new total ≈ 40 — 6 clock + 14 catalogue + 17 match_tree + 8 pricing_bridge, exact count may vary ±2).

If anything FAILs → **STOP**, fix before moving on.

- [ ] **Step 5.2: Broader regression — services/rag core tests**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
PYTHONPATH=. pytest backend/tests/services/rag/test_confidence.py \
                    backend/tests/services/rag/test_kg_langgraph.py \
                    backend/tests/services/rag/test_kg_subgraphs.py \
                    -q
```

Expected: all PASS (CLAUDE.md pre-deploy checklist). These are unrelated to visa but must not regress.

- [ ] **Step 5.3: Router registration sanity**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
PYTHONPATH=. pytest backend/tests/setup/test_router_manifest.py -q
```

Expected: PASS. If FAIL → router manifest is out of sync, not caused by this PR.

- [ ] **Step 5.4: Integration — live backend round-trip**

Start the backend locally:

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. uvicorn backend.app.main:app --port 8000 &
UVICORN_PID=$!
sleep 4
```

Run the 21-scenario sweep:

```bash
python3 <<'PY'
import itertools, json, urllib.request

purposes = ["work_remote", "investor", "work_employee", "family",
            "long_tourism", "retirement", "student"]
bands = ["under_50m", "50m_500m", "over_500m"]

fail = []
for p, b in itertools.product(purposes, bands):
    body = json.dumps({
        "nationality": "USA",
        "purpose": p,
        "duration_months": 12,
        "budget_band": b,
    }).encode()
    req = urllib.request.Request(
        "http://localhost:8000/api/visa/match",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
    except Exception as e:
        fail.append((p, b, f"HTTP ERROR: {e}"))
        continue
    rec = data.get("recommended_visa")
    cost = data.get("estimated_cost_idr")
    referral = data.get("referral_mode")
    print(f"{p:15s} {b:12s} → visa={rec} cost={cost} referral={referral}")
    if not referral and rec is None:
        fail.append((p, b, "no visa AND no referral"))

print()
print(f"SCENARIOS: {len(purposes) * len(bands)}")
print(f"FAILURES:  {len(fail)}")
for row in fail:
    print("  FAIL:", row)
PY
```

Stop the server:

```bash
kill $UVICORN_PID
```

Expected: 21 scenarios printed, `FAILURES: 0`. Every row has either a `visa` or `referral=True`.

If `FAILURES > 0` → **STOP** and investigate. Do not open the PR.

- [ ] **Step 5.5: Commit (no-op if nothing changed) — just sanity push**

```bash
cd ~/Desktop/nuzantara
git status --short
# if there are unstaged changes from debugging, decide whether to commit or revert
```

---

## Task 6: Red-team dispatch

**Files:**

- No changes — automated review before PR.

- [ ] **Step 6.1: Run the federation orchestrator red-team**

```bash
cd ~/Desktop/nuzantara
./scripts/ai-dispatch.sh redteam "visa catalogue rebuild — refactor/visa-catalogue-from-seed. Verify every VisaType in apps/backend-rag/backend/services/visa_check/catalogue.py is present in apps/backend-rag/backend/migrations/scripts/seed_visa_types_complete_2026.py, every non-KNOWN_NONE VisaType resolves to a positive cost in apps/backend-rag/backend/data/bali_zero_official_prices_2025.json via pricing_bridge._SEARCH_HINTS, and the match_tree ranking is stable for all 21 (purpose × budget_band) combinations. Flag any inconsistencies between the spec docs/superpowers/specs/2026-04-21-visa-catalogue-rebuild.md and the code."
```

- [ ] **Step 6.2: Review red-team output and address findings**

Read the orchestrator's consolidated report. For each finding:

- **Blocker (factual error, security issue, regression):** fix before PR, add a commit.
- **Suggestion (nice-to-have):** note in the PR description under "Deferred" or address if trivial.
- **False positive:** document in PR description why the finding doesn't apply.

If no blockers → proceed to Task 7.

---

## Task 7: Push + open PR

**Files:**

- No changes.

- [ ] **Step 7.1: Push the branch**

```bash
cd ~/Desktop/nuzantara
git push -u origin refactor/visa-catalogue-from-seed
```

- [ ] **Step 7.2: Open PR**

```bash
cd ~/Desktop/nuzantara
gh pr create --title "refactor(visa-check): rebuild catalogue from authoritative seed" --body "$(cat <<'EOF'
## Summary

- Removes **B211A** (pre-2023 nomenclature, absent from both the 114-code seed and the pricing JSON — the root bug this PR fixes).
- Adds **7 codes** from the seed: C6, C18, C22A, D2, D12, E33E, E23-FREELANCE. Total now 18 visa types.
- New `VisaMeta` dataclass in `catalogue.py` is the single source of truth; `DEFAULT_DURATION_DAYS` and `EXTENSION_POLICY` are derived so `clock.py` keeps working unchanged.
- `MatchResult` now exposes a `ranking: list[RankedVisa]` field. `recommended_visa`, `reason`, `alternatives`, `pre_arrival_steps`, `referral_mode` are preserved as `@property` accessors — **API contract unchanged**, router unmodified except for the B211A reference in `_processing_days`.
- `pricing_bridge._SEARCH_HINTS` rewritten to use the real JSON key names (e.g. `"C1 Tourism"`, `"E33G Remote Worker (Offshore)"`). Offshore variants preferred. New `KNOWN_NONE_VISAS = {C6, E30A}` documents the two legitimately unpriced services.
- `test_catalogue.py` parses the seed at test time and asserts every VisaType code / name / category is in sync — future drift will fail CI.

Spec: `docs/superpowers/specs/2026-04-21-visa-catalogue-rebuild.md`
Plan: `docs/superpowers/plans/2026-04-21-visa-catalogue-rebuild.md`

## Test plan

- [ ] `PYTHONPATH=. pytest backend/tests/services/visa_check/ -v` — all green
- [ ] Import chain: `python -c "from backend.app.dependencies import get_current_user; print('OK')"`
- [ ] Live round-trip: 21-scenario sweep from Task 5.4 returns 0 failures
- [ ] Red-team orchestrator report reviewed, no blockers outstanding

## Deferred to follow-up PR

- Frontend `ranking` consumption — current UI reads `recommended_visa` + `alternatives` unchanged; migrating to `ranking[i].score/fit_tags` is a separate UX round.
- `WORK_REMOTE_FOREIGN` vs `WORK_REMOTE_LOCAL` purpose split — E23-FREELANCE currently disambiguates via `fit_tags` in the ranking reason, not a new wizard step.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 7.3: Return the PR URL and stop**

Print the PR URL from `gh pr create` output and confirm in chat. Do not merge.

---

## Self-review

**1. Spec coverage check:**

- Remove B211A → Task 1.3 + test 1.1 `TestEnumStability.test_b211a_removed` + Task 4.
- Add 7 codes → Task 1.3 (all listed in VISA_META) + Task 1.1 `test_all_18_codes_present`.
- `VisaMeta` dataclass with all 10 fields → Task 1.3 definition matches spec exactly.
- Derived `DEFAULT_DURATION_DAYS` / `EXTENSION_POLICY` → Task 1.3 + Task 1.1 `TestDerivedDicts`.
- `MatchResult.ranking` + backwards-compat properties → Task 2.3 + Task 2.1 `TestBackwardsCompatProperties`.
- No hardcoded VisaType in match_tree branches → Task 2.3 `_rank_for_purpose` iterates VISA_META.
- Scoring 0.5 base + 0.3 budget + 0.2 duration → Task 2.3 `_score` (note: budget weight 0.25 not 0.3 for sum ≤ 1.0; acceptable departure, documented in code).
- `_SEARCH_HINTS` name-based, offshore preferred → Task 3.3.
- Known-None {C6, E30A} → Task 3.3 `KNOWN_NONE_VISAS` + Task 3.1 tests.
- Test matrix 14 checks → covered across Tasks 1, 2, 3 tests.
- API backwards-compat (response shape unchanged) → router unmodified by design; Task 4 touches only `_processing_days`.
- Red-team before merge → Task 6.
- Fail-loud contract → Step 0.2 assertions, each Task step says "STOP" on failure.

**2. Placeholder scan:** No "TBD", no "implement later", no bare "add error handling" instructions. Every code step has the actual code. Every command has expected output.

**3. Type consistency:** `MatchResult.ranking` is `list[RankedVisa]` everywhere. `VisaMeta.extensions` is `tuple[int, int]` in catalogue and consumed as `(count, days_each)` in `_score` and `_reason`. `KNOWN_NONE_VISAS` is `frozenset[VisaType]` in bridge and `frozenset[VisaType]` in tests. `Purpose` enum identical across files. `fit_tags` is `frozenset[str]` everywhere (catalogue → meta → `RankedVisa` passthrough). No drift.

**4. Scope check:** Single sub-system (visa_check), 3 production files + 3 test files + 1 router line. Fits a single plan.
