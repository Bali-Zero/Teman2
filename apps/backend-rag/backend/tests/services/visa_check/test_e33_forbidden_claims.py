"""E33 Second Home — forbidden-claim regression tests over static surfaces.

Task 1.2 of the E33 source-guard lane. Parametrizes the forbidden-claim
patterns from the E33 fact registry (fixture copy at
``fixtures/e33_fact_registry.json``; canonical:
``research/secondhome/e33-fact-registry.json``, branch pending merge) and
asserts the platform's key E33 static surfaces do NOT contain them:

- ``backend/services/visa_check/catalogue.py``
- ``backend/services/visa_check/match_tree.py``
- ``backend/services/rag/kg_enhanced_retrieval.py``
- ``backend/data/bali_zero_official_prices_2026.json``

Deterministic regex-over-file checks; no external services. The runtime twin
of these patterns lives in ``backend/services/visa_check/e33_claim_guard.py``
— a consistency test below keeps the two pattern sets in sync.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from backend.services.visa_check.e33_claim_guard import (
    E33_FORBIDDEN_PATTERNS,
    LEGACY_ERROR_REF,
)


def _find_repo_root(start: Path) -> Path:
    """Walk up from `start` until a directory containing `.git` is found.

    Works for both plain checkouts (`.git/` dir) and worktrees
    (`.git` file pointing to the real gitdir).
    """
    for parent in [start, *start.parents]:
        if (parent / ".git").exists():
            return parent
    raise RuntimeError(f"no .git found walking up from {start}")


REPO_ROOT = _find_repo_root(Path(__file__).resolve())
BACKEND_DIR = REPO_ROOT / "apps/backend-rag/backend"

SURFACES: dict[str, Path] = {
    "catalogue": BACKEND_DIR / "services/visa_check/catalogue.py",
    "match_tree": BACKEND_DIR / "services/visa_check/match_tree.py",
    "kg_enhanced_retrieval": BACKEND_DIR / "services/rag/kg_enhanced_retrieval.py",
    "prices_2026": BACKEND_DIR / "data/bali_zero_official_prices_2026.json",
}

FIXTURE_REGISTRY = Path(__file__).parent / "fixtures" / "e33_fact_registry.json"

# Forbidden-claim patterns asserted on every surface. Zero-tolerance: no
# legitimate occurrence exists on these surfaces (prices in the JSON use
# "<amount> IDR" order, so "IDR 2.000.000"-style patterns cannot collide).
SURFACE_FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "e33f_superseded_income_usd1500",
        re.compile(r"\bUSD\s*1[.,]?500\b", re.IGNORECASE),
        "USD 1,500/month is the superseded pre-2024 E33F figure (current: USD 3,000/month)",
    ),
    (
        "second_home_any_bank",
        re.compile(r"\bany\s+(?:Indonesian\s+)?bank\b", re.IGNORECASE),
        "deposit must be at a state-owned (BUMN) bank, not 'any bank'",
    ),
    (
        "e33s_e33r_codes",
        re.compile(r"\bE33[SR]\b"),
        "E33S/E33R exist only inside gold_harness fixtures",
    ),
    (
        "e33_permits_local_work",
        re.compile(
            r"\bE33[A-Z]?\b[^.\n]{0,60}\b(?:allows?|permits?|authoriz\w*|entitle\w*)\b"
            r"[^.\n]{0,40}\b(?:work|employment)\b",
            re.IGNORECASE,
        ),
        "base E33 does NOT authorize local employment",
    ),
    (
        "e33_itap_kitap_automatic_promise",
        re.compile(
            r"\bautomatic(?:ally)?\b(?!\s+included)[^.\n]{0,25}\b(?:KITAP|ITAP)\b"
            r"|\b(?:KITAP|ITAP)\b[^.\n]{0,40}\bautomatic(?:ally)?\b(?!\s+included)"
            r"|\bafter\s+3\s+years\b[^.\n]{0,50}\b(?:eligible|convert\w*|automatic\w*)\b"
            r"[^.\n]{0,30}\b(?:KITAP|ITAP)\b",
            re.IGNORECASE,
        ),
        "ITAP/KITAP conversion after 3 years is unconfirmed — never promise it",
    ),
    (
        "second_home_first_grant_5_10_years",
        re.compile(r"\b5\s*[-–]\s*10\s*years?\b", re.IGNORECASE),
        "base E33 first grant is up to 5 years; '5-10 years' mixes other categories",
    ),
    (
        "idr_2m_fee_error",
        re.compile(r"\bIDR\s*2[.,]?000[.,]?000\b", re.IGNORECASE),
        "IDR 2,000,000 is the 1000x legacy fee error",
    ),
    (
        "approval_guaranteed",
        re.compile(
            r"\b(?:approval|approved|application|visa)\b[^.\n]{0,30}\b(?:is\s+|are\s+)?"
            r"(?<!not\s)(?<!never\s)guaranteed\b"
            r"|\b(?<!not\s)(?<!never\s)guaranteed\s+(?:approval|visa)\b",
            re.IGNORECASE,
        ),
        "visa approval is never guaranteed",
    ),
    (
        "lps_full_coverage",
        re.compile(
            r"\bLPS\b[^.\n]{0,60}\b(?:full(?:y)?|100\s*%|entire(?:ly)?|whole)\b",
            re.IGNORECASE,
        ),
        "LPS deposit insurance has a cap — never claim full coverage",
    ),
    (
        "bsi_sharia_equivalence",
        re.compile(
            r"\b(?:BSI|Bank\s+Syariah\s+Indonesia)\b[^.\n]{0,80}\b"
            r"(?:qualif\w*|accept\w*|state[- ]owned|BUMN|equivalent|counts?\s+as)\b",
            re.IGNORECASE,
        ),
        "BSI sharia placement as qualifying state-bank deposit is unconfirmed",
    ),
    (
        "split_deposit_accepted",
        re.compile(
            r"\bsplit\b[^.\n]{0,40}\bdeposit\b|\bdeposit\b[^.\n]{0,40}\bsplit\b"
            r"|\bmultiple\s+(?:BUMN\s+|state[- ]owned\s+)?banks\b[^.\n]{0,50}\bdeposit\b",
            re.IGNORECASE,
        ),
        "splitting the USD 130,000 deposit across banks is unconfirmed",
    ),
]

_CASES = [
    pytest.param(surface_name, pattern_id, id=f"{surface_name}::{pattern_id}")
    for surface_name in SURFACES
    for pattern_id, _, _ in SURFACE_FORBIDDEN_PATTERNS
]

_PATTERN_BY_ID = {pid: (rx, desc) for pid, rx, desc in SURFACE_FORBIDDEN_PATTERNS}


class TestStaticSurfaces:
    @pytest.mark.parametrize(("surface_name", "pattern_id"), _CASES)
    def test_surface_has_no_forbidden_claim(self, surface_name: str, pattern_id: str) -> None:
        path = SURFACES[surface_name]
        assert path.is_file(), f"surface missing: {path}"
        content = path.read_text()
        regex, description = _PATTERN_BY_ID[pattern_id]
        matches = list(regex.finditer(content))
        assert not matches, (
            f"forbidden E33 claim '{pattern_id}' ({description}) in {path}: "
            f"{[m.group(0)[:80] for m in matches[:3]]}"
        )


class TestE33SRE33RScope:
    """E33S/E33R codes must exist ONLY inside gold_harness fixtures."""

    def test_no_e33s_e33r_outside_gold_harness(self) -> None:
        this_file = Path(__file__).resolve()  # self-reference: contains the pattern as data
        offenders: list[str] = []
        for path in BACKEND_DIR.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".json", ".md", ".txt"}:
                continue
            if path.resolve() == this_file:
                continue
            rel = path.relative_to(BACKEND_DIR)
            if "gold_harness" in rel.parts:
                continue
            if re.search(r"\bE33[SR]\b", path.read_text(errors="replace")):
                offenders.append(str(rel))
        assert not offenders, f"E33S/E33R outside gold_harness: {offenders}"

    def test_gold_harness_fixtures_actually_use_e33s_e33r(self) -> None:
        """Sanity: the exclusion above is not vacuous."""
        fixtures = BACKEND_DIR / "tests/services/visa_engine/gold_harness/fixtures"
        assert fixtures.is_dir(), f"gold_harness fixtures missing: {fixtures}"
        found = any(
            re.search(r"\bE33[SR]\b", p.read_text(errors="replace"))
            for p in fixtures.rglob("*.json")
        )
        assert found, "expected E33S/E33R inside gold_harness fixtures"


class TestGuardPatternConsistency:
    """Surface patterns and the runtime guard must not drift apart."""

    def test_surface_pattern_ids_exist_in_guard_module(self) -> None:
        guard_ids = {p.pattern_id for p in E33_FORBIDDEN_PATTERNS}
        surface_ids = {pid for pid, _, _ in SURFACE_FORBIDDEN_PATTERNS}
        # e33s_e33r_codes is structural (fixtures-only), not a runtime claim.
        surface_ids.discard("e33s_e33r_codes")
        missing = surface_ids - guard_ids
        assert not missing, f"surface patterns missing from e33_claim_guard: {missing}"

    def test_guard_registry_refs_resolve_in_fixture(self) -> None:
        fixture = json.loads(FIXTURE_REGISTRY.read_text())
        fact_ids = {f["id"] for f in fixture["facts"]}
        for pattern in E33_FORBIDDEN_PATTERNS:
            if pattern.registry_ref == LEGACY_ERROR_REF:
                continue
            assert pattern.registry_ref in fact_ids, (
                f"guard pattern '{pattern.pattern_id}' references unknown registry fact "
                f"'{pattern.registry_ref}'"
            )
