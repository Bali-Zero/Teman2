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
MOUTH_CONTENT_DIR = REPO_ROOT / "apps/mouth/src/content"

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

    def test_e33s_e33r_eradicated_everywhere(self) -> None:
        """Post #3044: the synthetic codes were replaced by real E33/E33E/E33F
        products in the gold harness, so they must appear NOWHERE outside the
        guard module and its tests (which legitimately name them as the
        patterns to detect)."""
        allowed = {
            "services/visa_check/e33_claim_guard.py",
            "tests/services/visa_check/test_e33_forbidden_claims.py",
            "tests/services/visa_check/test_e33_claim_guard.py",
        }
        offenders: list[str] = []
        for path in BACKEND_DIR.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".json", ".md"}:
                continue
            if "node_modules" in path.parts or ".venv" in path.parts:
                continue
            rel = str(path.relative_to(BACKEND_DIR))
            if rel in allowed:
                continue
            if re.search(r"\bE33[SR]\b", path.read_text(errors="replace")):
                offenders.append(rel)
        assert not offenders, f"E33S/E33R still present: {offenders}"


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


# --- Second-Home-predicated "5-10 years" over apps/mouth/src/content ---
#
# S13-510: base E33 is a 5-year first grant with a cumulative cap under
# Permenkumham 22/2023 Pasal 113 (first grant >=5y -> 10y cumulative) — two
# facts, never one bare "5-10 years" range. But the Golden Visa genuinely IS
# a 5-10 year product, and "5-10 Days" appears for unrelated document-prep
# timelines. A bare substring/whole-sentence scan over-matches the Golden
# Visa content (guard family #3, cicatrix-superscar.md) — instead this
# classifies each match by its NEAREST visa-name predicate (within a ±300
# char window, either direction, mirroring the sentence-scoped census that
# found this defect), never by "does the term appear anywhere in the
# sentence/file".

_SECOND_HOME_DURATION_VOCABULARY: dict[str, dict[str, tuple[str, ...]]] = {
    # language: conjunction separators, year units
    "en": {"conjunctions": ("or",), "units": ("year", "years")},
    "it": {"conjunctions": ("o",), "units": ("anno", "anni")},
    "id": {"conjunctions": ("atau",), "units": ("tahun",)},
    "fr": {"conjunctions": ("ou", "à"), "units": ("an", "ans")},
    "ru": {"conjunctions": ("или",), "units": ("год", "года", "лет")},
}
_SYMBOLIC_ALTERNATION_SEPARATORS = ("-", "–", "/")


def _duration_alternation_pattern(
    vocabulary: dict[str, tuple[str, ...]],
) -> str:
    """Match an alternation between 5 and 10 of one language's year unit."""
    conjunctions = "|".join(re.escape(item) for item in vocabulary["conjunctions"])
    units = "|".join(
        re.escape(item) for item in sorted(vocabulary["units"], key=len, reverse=True)
    )
    symbols = "|".join(re.escape(item) for item in _SYMBOLIC_ALTERNATION_SEPARATORS)
    separator = rf"(?:{symbols}|\b(?:{conjunctions})\b)"
    optional_first_unit = rf"(?:(?:\s*-\s*|\s+)(?:{units}))?"
    required_second_unit = rf"(?:\s*-\s*|\s+)(?:{units})\b"
    return rf"\b5{optional_first_unit}\s*{separator}\s*10{required_second_unit}"


_SECOND_HOME_DURATION_RE = re.compile(
    "|".join(
        _duration_alternation_pattern(vocabulary)
        for vocabulary in _SECOND_HOME_DURATION_VOCABULARY.values()
    ),
    re.IGNORECASE,
)
_GOLDEN_VISA_RE = re.compile(
    r"Golden\s+Visa|Visa\s+Emas|Золотая\s+Виза|золотую?\s+визу?\w*",
    re.IGNORECASE,
)
_SECOND_HOME_VISA_RE = re.compile(
    r"Second\s+Home(?:\s+Visa)?|Visa\s+Rumah\s+Kedua|Visa\s+Second\s+Home"
    r"|Rumah\s+Kedua|Виза\s+второго\s+дома"
    r"|второго\s+дома",
    re.IGNORECASE,
)
_PROXIMITY_WINDOW = 300


def _nearest_marker_distance(
    text: str, start: int, end: int, pattern: re.Pattern[str]
) -> int | None:
    """Char-distance from [start, end) to the nearest match of `pattern`
    within `_PROXIMITY_WINDOW` chars either side. None if no match in range."""
    lo = max(0, start - _PROXIMITY_WINDOW)
    hi = min(len(text), end + _PROXIMITY_WINDOW)
    segment = text[lo:hi]
    best: int | None = None
    for marker in pattern.finditer(segment):
        m_start, m_end = marker.start() + lo, marker.end() + lo
        if m_end <= start:
            distance = start - m_end
        elif m_start >= end:
            distance = m_start - end
        else:
            distance = 0
        if best is None or distance < best:
            best = distance
    return best


def _find_second_home_predicated_5_10_offenders(text: str) -> list[tuple[int, str]]:
    """Nearest-predicate scan: flag a '5-10 year(s)/anni/tahun/...' range
    ONLY when the nearest visa-name predicate is Second Home, not Golden
    Visa. A range with no Second-Home predicate within the window at all
    (e.g. blacklist-ban durations, KITAP renewal, unrelated '5-10 days')
    is never flagged."""
    offenders: list[tuple[int, str]] = []
    for match in _SECOND_HOME_DURATION_RE.finditer(text):
        start, end = match.span()
        second_home_dist = _nearest_marker_distance(text, start, end, _SECOND_HOME_VISA_RE)
        if second_home_dist is None:
            continue
        golden_dist = _nearest_marker_distance(text, start, end, _GOLDEN_VISA_RE)
        if golden_dist is not None and golden_dist < second_home_dist:
            continue
        offenders.append((start, match.group(0)))
    return offenders


def _iter_mouth_content_files() -> list[Path]:
    if not MOUTH_CONTENT_DIR.is_dir():
        return []
    return sorted(
        p
        for p in MOUTH_CONTENT_DIR.rglob("*")
        if p.is_file() and p.suffix in {".mdx", ".ts", ".tsx"}
    )


class TestMouthContentSecondHomeDuration:
    """Guards apps/mouth/src/content against the Second-Home '5-10 years'
    claim that TestStaticSurfaces above never saw (it only scans
    apps/backend-rag/backend/**)."""

    def test_second_home_predicated_5_10_year_range_absent(self) -> None:
        offenders: list[str] = []
        for path in _iter_mouth_content_files():
            text = path.read_text(errors="replace")
            for start, matched in _find_second_home_predicated_5_10_offenders(text):
                line_no = text.count("\n", 0, start) + 1
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{line_no}: {matched!r}")
        assert not offenders, (
            "Second-Home-predicated '5-10 years' claim in apps/mouth/src/content — base "
            "E33 is a 5-year first grant, renewable up to a 10-year cumulative maximum "
            f"(Permenkumham 22/2023 Pasal 113), never a bare 5-10 range: {offenders}"
        )

    def test_guilt_second_home_predicated_range_is_flagged(self) -> None:
        """A Second-Home-predicated '5-10 years' line re-introduced into a
        mouth content file MUST make the guard fail."""
        text = 'answer: "Second Home Visa (5-10 years with IDR 2B savings)."'
        offenders = _find_second_home_predicated_5_10_offenders(text)
        assert offenders, "guard must flag a Second-Home-predicated 5-10 year range"

    def test_guilt_real_second_home_conjunction_is_flagged(self) -> None:
        """The real pre-fix e-visa sentence must exercise the conjunction branch."""
        text = (
            "The Second Home Visa (E33), introduced in 2022, remains one of the most "
            "significant long-stay options, granting 5 or 10-year residency rights to "
            "qualifying foreign nationals meeting fund placement thresholds."
        )
        assert _SECOND_HOME_DURATION_RE.search(text), (
            "guilt fixture must exercise the widened duration matcher"
        )
        offenders = _find_second_home_predicated_5_10_offenders(text)
        assert offenders, "guard must flag the real Second-Home conjunction claim"

    @pytest.mark.parametrize(
        "claim",
        [
            'Renewals: "After 5/10 years",',
            'Renewals: "Dopo 5/10 anni",',
            'Renewals: "Setelah 5/10 tahun",',
            'Renouvellements: "Après 5/10 ans",',
            'Renewals: "Через 5/10 лет",',
        ],
    )
    def test_guilt_real_second_home_slash_is_flagged(self, claim: str) -> None:
        """The five real pre-fix renewal lines must exercise the slash branch."""
        text = f'name: "Second Home Visa"\n{claim}'
        assert _SECOND_HOME_DURATION_RE.search(claim), (
            "guilt fixture must exercise the slash duration matcher"
        )
        offenders = _find_second_home_predicated_5_10_offenders(text)
        assert offenders, "guard must flag the real Second-Home slash claim"

    def test_guilt_real_second_home_repeated_unit_is_flagged(self) -> None:
        """The real canonical-guide sentence must exercise repeated year units."""
        text = (
            "**Second Home Visa (SHV)** adalah izin tinggal jangka panjang Indonesia "
            "untuk orang asing yang ingin menjadikan Indonesia sebagai kediaman kedua "
            "— tanpa memerlukan perusahaan sponsor. Tersedia dalam dua opsi: 5 tahun "
            "atau 10 tahun, dengan syarat utama bukti kemampuan finansial sesuai "
            "ketentuan imigrasi yang berlaku."
        )
        assert _SECOND_HOME_DURATION_RE.search(text), (
            "guilt fixture must exercise the repeated-unit duration matcher"
        )
        offenders = _find_second_home_predicated_5_10_offenders(text)
        assert offenders, "guard must flag the real repeated-unit Second-Home claim"

    @pytest.mark.parametrize(
        ("relative_path", "text"),
        [
            pytest.param(
                "articles/immigration/golden-visa-indonesia-complete-guide.mdx",
                "### What happens if I don't renew after 5/10 years?",
                id="golden-slash-en",
            ),
            pytest.param(
                "articles/immigration/golden-visa-indonesia-complete-guide.it.mdx",
                "### Cosa succede se non rinnovo dopo 5/10 anni?",
                id="golden-slash-it",
            ),
            pytest.param(
                "articles/immigration/golden-visa-indonesia-complete-guide.id.mdx",
                "### Apa yang terjadi jika saya tidak memperbarui setelah 5/10 tahun?",
                id="golden-slash-id",
            ),
            pytest.param(
                "articles/immigration/golden-visa-indonesia-complete-guide.fr.mdx",
                "### Que se passe-t-il si je ne renouvelle pas après 5/10 ans ?",
                id="golden-slash-fr",
            ),
            pytest.param(
                "articles/immigration/golden-visa-indonesia-complete-guide.ru.mdx",
                "### Что произойдет, если я не продлю визу через 5/10 лет?",
                id="golden-slash-ru",
            ),
        ],
    )
    def test_innocence_real_golden_slash_stays_clean(
        self, relative_path: str, text: str
    ) -> None:
        """Real Golden-Visa slash sentences must remain legitimate."""
        source = MOUTH_CONTENT_DIR / relative_path
        source_text = source.read_text()
        assert text in source_text, f"innocence sentence drifted from {source}"
        assert _SECOND_HOME_DURATION_RE.search(text), (
            "innocence fixture must exercise the slash duration matcher"
        )
        assert not _find_second_home_predicated_5_10_offenders(source_text)

    def test_innocence_real_golden_repeated_unit_stays_clean(self) -> None:
        """The real Golden-Visa repeated-unit feature must stay legitimate."""
        source = (
            MOUTH_CONTENT_DIR
            / "articles/immigration/golden-visa-indonesia-complete-guide.mdx"
        )
        text = "- **5-year or 10-year validity** - No annual renewals"
        source_text = source.read_text()
        assert text in source_text, f"innocence sentence drifted from {source}"
        assert _SECOND_HOME_DURATION_RE.search(text), (
            "innocence fixture must exercise the repeated-unit duration matcher"
        )
        assert not _find_second_home_predicated_5_10_offenders(source_text)

    @pytest.mark.parametrize(
        ("relative_path", "text"),
        [
            pytest.param(
                "articles/immigration/golden-visa-indonesia-complete-guide.mdx",
                "Indonesia's Golden Visa program (officially called ITAP - Izin Tinggal "
                "Tetap untuk Investor) offers **5 or 10-year residence permits** to "
                "foreign investors without the traditional 5-year KITAS waiting period "
                "required for KITAP.",
                id="golden-visa-en",
            ),
            pytest.param(
                "articles/immigration/golden-visa-indonesia-complete-guide.it.mdx",
                "Il programma Golden Visa dell'Indonesia (ufficialmente chiamato ITAP - "
                "Izin Tinggal Tetap per Investitore) offre **permessi di residenza da 5 o "
                "10 anni** agli investitori stranieri senza il tradizionale periodo di "
                "attesa di 5 anni richiesto per il KITAS necessario per ottenere il KITAP.",
                id="golden-visa-it",
            ),
            pytest.param(
                "articles/immigration/golden-visa-indonesia-complete-guide.id.mdx",
                "Program Visa Emas Indonesia (secara resmi disebut ITAP - Izin Tinggal "
                "Tetap untuk Investor) menawarkan **izin tinggal 5 atau 10 tahun** bagi "
                "investor asing tanpa periode tunggu KITAS 5 tahun tradisional yang "
                "diperlukan untuk KITAP.",
                id="golden-visa-id",
            ),
            pytest.param(
                "articles/immigration/golden-visa-indonesia-complete-guide.fr.mdx",
                "Le programme Golden Visa de l'Indonésie (officiellement appelé ITAP - "
                "Izin Tinggal Tetap pour Investor) offre des **permis de séjour de 5 ou "
                "10 ans** aux investisseurs étrangers sans la période d'attente "
                "traditionnelle de 5 ans du KITAS requise pour le KITAP.",
                id="golden-visa-fr",
            ),
            pytest.param(
                "articles/immigration/golden-visa-indonesia-complete-guide.ru.mdx",
                "Программа Золотой Визы Индонезии (официально называемая ITAP - Izin Tinggal "
                "Tetap untuk Investor) предлагает **разрешения на проживание на 5 или "
                "10 лет** для иностранных инвесторов без традиционного 5-летнего периода "
                "ожидания KITAS, необходимого для KITAP.",
                id="golden-visa-ru",
            ),
            pytest.param(
                "articles/business/kbli-2025-agriculture-agritourism.fr.mdx",
                "\\*Les secteurs prioritaires (café, cacao, caoutchouc) en vertu du "
                "Règlement présidentiel 10/2021 (Tax Holiday) exigent un investissement "
                "total de 100 milliards d'IDR pour être éligibles à l'exonération d'impôt "
                "sur les sociétés (0 % pendant 5 à 10 ans).",
                id="tax-holiday-fr",
            ),
            pytest.param(
                "articles/business/kbli-2025-location-restrictions-bali.fr.mdx",
                '**Important :** Les "droits acquis" ne signifient pas "pour toujours" '
                "– certaines réglementations imposent une élimination progressive sur 5 à "
                "10 ans.",
                id="regulatory-phase-out-fr",
            ),
        ],
    )
    def test_innocence_real_conjunction_sentences_stay_clean(
        self, relative_path: str, text: str
    ) -> None:
        """Real Golden-Visa and unrelated conjunction sentences must stay green."""
        source = MOUTH_CONTENT_DIR / relative_path
        assert text in source.read_text(), f"innocence sentence drifted from {source}"
        assert _SECOND_HOME_DURATION_RE.search(text), (
            "innocence fixture must exercise the widened duration matcher"
        )
        offenders = _find_second_home_predicated_5_10_offenders(text)
        assert not offenders, "guard must not flag a real legitimate conjunction sentence"

    @pytest.mark.parametrize(
        ("relative_path", "text"),
        [
            pytest.param(
                "articles/property/title-insurance-indonesia.mdx",
                "**Cost:** IDR 5-10 million",
                id="idr-money-range",
            ),
            pytest.param(
                "articles/immigration/visa-agent-vs-diy-indonesia.id.mdx",
                "| E33G Pekerja Jarak Jauh | Rp 5.000.000-10.000.000  | "
                "Rp 13.000.000-20.000.000 | Rp 5-10 jt      |",
                id="rupiah-money-range",
            ),
            pytest.param(
                "articles/business/bpjs-ketenagakerjaan-employer-guide.it.mdx",
                "4. Elaborazione: 5-10 giorni lavorativi",
                id="italian-working-days",
            ),
            pytest.param(
                "articles/immigration/second-home-visa-indonesia.id.mdx",
                "### Tahap 1: Persiapan Dokumen (5-10 Hari)",
                id="indonesian-document-preparation-days",
            ),
        ],
    )
    def test_innocence_real_non_duration_ranges_stay_out(
        self, relative_path: str, text: str
    ) -> None:
        """Real money and working-day ranges must never enter the duration scan."""
        source = MOUTH_CONTENT_DIR / relative_path
        assert text in source.read_text(), f"innocence sentence drifted from {source}"
        assert not _SECOND_HOME_DURATION_RE.search(text)
        assert not _find_second_home_predicated_5_10_offenders(text)

    def test_innocence_golden_visa_range_stays_clean(self) -> None:
        """The real second-home-visa-indonesia.mdx sentence (canonical guide,
        verified CLEAN in the S13-510 census) must stay green: the Golden
        Visa duration is a legitimate 5-10 year range."""
        text = (
            "## What Is the Second Home Visa?\n\n"
            "Indonesia's Second Home Visa (Visa Rumah Kedua) is a long-term stay permit. "
            "The visa grants a 5-year stay permit. It sits between the KITAS "
            "(1-2 years, work-focused) and the Golden Visa (5-10 years, investment-focused) "
            "in terms of duration and requirements."
        )
        offenders = _find_second_home_predicated_5_10_offenders(text)
        assert not offenders, "guard must not flag the legitimate Golden Visa 5-10 year range"

    def test_innocence_document_prep_days_stays_clean(self) -> None:
        """'5-10 Days' is a document-prep timeline, not a visa-duration claim,
        and must stay green even in a Second-Home-titled document."""
        text = (
            "## Second Home Visa Application Process\n\n"
            "### Stage 1: Document Preparation (5-10 Days)\n\n"
            "Gather your bank statements and proof of funds."
        )
        offenders = _find_second_home_predicated_5_10_offenders(text)
        assert not offenders, (
            "guard must not flag '5-10 Days' (document prep, not a visa duration claim)"
        )
