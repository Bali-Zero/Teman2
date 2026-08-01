"""
Guilt AND innocence for the anchor-adjacent-`\\s` ReDoS cure in the legal module.

py/polynomial-redos alerts #7771/#7772/#7773 (chunker), #7781/#7782 (structure_parser)
and #7777 (quality_validators). The shape is a MULTILINE anchor — `^`, or the `(?:^|\\n)`
idiom — followed by `\\s*`: `\\s` matches `\\n`, the character the anchor already ranges
over, so the engine gets O(n) start positions times O(n) backtracking on a run of blank
lines. `/api/legal/ingest` feeds this module OCR'd PDFs, which are mostly blank lines.

Innocence carries as much weight as guilt here. A regex that no longer backtracks but no
longer finds `Pasal 2` has traded a slow ingest for a silently truncated law, and nothing
downstream would notice: the chunker would just emit fewer chunks.
"""

import re
import time

import pytest

from backend.core.legal import constants as const
from backend.core.legal.chunker import LegalChunker
from backend.core.legal.cleaner import LegalCleaner
from backend.core.legal.quality_validators import extract_ayat_numbers
from backend.core.legal.structure_parser import LegalStructureParser

# Sized by MUTATION, not by taste: at 20k the slowest pre-fix pattern still finished in
# ~0.45s, so a 2s budget let the AYAT mutant through and only the static guard caught it.
# At 60k every pre-fix pattern needs seconds (AYAT ≈4s, PASAL ≈24s) while the cured ones
# need ~2ms — 500x of headroom for a loaded CI runner, and no mutant survives.
ADVERSARIAL_N = 60_000
BUDGET_SECONDS = 1.0

CURED = {
    "PASAL_PATTERN": const.PASAL_PATTERN,
    "AYAT_PATTERN": const.AYAT_PATTERN,
    "AYAT_MARKER_PREFIX": re.compile(const.AYAT_MARKER_PREFIX, re.MULTILINE),
    "PAGE_NUMBER_LINE": re.compile(const.PAGE_NUMBER_LINE, re.MULTILINE),
    **{f"NOISE_PATTERNS[{i}]": p for i, p in enumerate(const.NOISE_PATTERNS)},
}

# Payloads shaped like what the anchor/`\s` overlap actually eats.
PAYLOADS = {
    "blank_lines": "\n" * ADVERSARIAL_N,
    "space_newline": " \n" * (ADVERSARIAL_N // 2),
    "crlf": "\r\n" * (ADVERSARIAL_N // 2),
    "tabs_and_newlines": "\t\n" * (ADVERSARIAL_N // 2),
}


def _elapsed(rx: re.Pattern, text: str) -> float:
    start = time.perf_counter()
    rx.findall(text)
    return time.perf_counter() - start


class TestLinearity:
    @pytest.mark.parametrize("name", sorted(CURED))
    @pytest.mark.parametrize("payload", sorted(PAYLOADS))
    def test_guilt_no_pattern_blows_up_on_whitespace_runs(self, name: str, payload: str) -> None:
        took = _elapsed(CURED[name], PAYLOADS[payload])
        assert took < BUDGET_SECONDS, (
            f"{name} took {took:.3f}s on {payload} (budget {BUDGET_SECONDS}s)"
        )

    # Each row is (name, the literal pre-fix source, the cured pattern it became).
    # The ONLY difference within a row is `\s*` vs `[ \t\r]*` after the anchor.
    PRE_FIX = [
        (
            "PASAL_PATTERN",
            r"(?:^|\n)\s*Pasal\s+([IVXLC]+|\d+[A-Z]?)\s*\n?\s*(.+?)"
            r"(?=(?:^|\n)\s*Pasal\s+(?:[IVXLC]+|\d+[A-Z]?)|^\s*BAB\s+|^Penjelasan|\Z)",
            lambda: const.PASAL_PATTERN,
        ),
        (
            "AYAT_PATTERN",
            r"(?:^|\n)\s*\((\d+)\)\s*(.+?)(?=(?:^|\n)\s*\(\d+\)|$)",
            lambda: const.AYAT_PATTERN,
        ),
        (
            "AYAT_MARKER_PREFIX",
            r"(?:^|\n)\s*\((\d+)\)",
            lambda: re.compile(const.AYAT_MARKER_PREFIX, re.MULTILINE),
        ),
        (
            "PAGE_NUMBER_LINE",
            r"^\s*\d+\s*$",
            lambda: re.compile(const.PAGE_NUMBER_LINE, re.MULTILINE),
        ),
        ("PAGE_SEPARATOR", r"^\s*-\s*\d+\s*-\s*$", lambda: const.NOISE_PATTERNS[3]),
    ]

    @pytest.mark.parametrize("name,pre_fix_source,cured", PRE_FIX, ids=[r[0] for r in PRE_FIX])
    def test_the_cure_is_what_makes_it_fast(self, name: str, pre_fix_source: str, cured) -> None:
        """
        Pins CAUSATION, not just the outcome. Without this a future rewrite could satisfy
        the budget above for some unrelated reason and the lesson would be lost — and it
        names each pattern, because a cure applied to one of six is how this family got
        five instances in the first place.
        """
        pre_fix = re.compile(pre_fix_source, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        text = "\n" * 8_000  # small: the pre-fix patterns are quadratic, keep CI cheap
        slow, fast = _elapsed(pre_fix, text), _elapsed(cured(), text)
        assert slow > 20 * fast, f"{name}: pre-fix {slow:.4f}s vs cured {fast:.4f}s"


class TestNoAnchorAdjacentWhitespaceReturns:
    """
    Class guard. The cure is for a SHAPE, so the test is over the shape — a seventh
    instance in this module fails here instead of waiting for the next scan.
    """

    # `^` (not the `[^...]` negation) or the tail of `(?:^|\n)`, then the `\s` class.
    DETECTOR = re.compile(r"(?<!\[)\^\\s|\\n\)\\s")

    def test_innocence_of_the_detector(self) -> None:
        """The detector must not fire on the cure, nor on a negated class, nor on a
        `\\s` that is gated by a literal (those have O(1) start positions)."""
        for safe in (
            r"(?:^|\n)[ \t\r]*Pasal\s+",
            r"^[ \t\r]*\d+[ \t\r]*$",
            r"[^\s|;&)]+",
            r"^PRESIDEN REPUBLIK INDONESIA\s*\n",
            r"^Halaman\s+\d+\s+dari\s+\d+",
            r"\n{3,}",
        ):
            assert not self.DETECTOR.search(safe), safe

    def test_guilt_of_the_detector(self) -> None:
        """And it must fire on every shape this commit removed."""
        for guilty in (
            r"(?:^|\n)\s*Pasal\s+([IVXLC]+|\d+[A-Z]?)",
            r"(?:^|\n)\s*\((\d+)\)",
            r"^\s*\d+\s*$",
            r"^\s*-\s*\d+\s*-\s*$",
        ):
            assert self.DETECTOR.search(guilty), guilty

    def test_no_pattern_in_the_module_has_the_shape(self) -> None:
        offenders = [
            name
            for name, value in vars(const).items()
            if isinstance(value, re.Pattern)
            and value.flags & re.MULTILINE
            and self.DETECTOR.search(value.pattern)
        ]
        assert offenders == [], f"anchor-adjacent `\\s` is back in: {offenders}"

    def test_no_string_constant_in_the_module_has_the_shape(self) -> None:
        """The raw-string constants are compiled at their call sites, so they need the
        same guard — `PAGE_NUMBER_LINE` reaches `re.sub(..., re.MULTILINE)` in cleaner.py
        and `AYAT_MARKER_PREFIX` reaches `re.findall(..., re.MULTILINE)` in
        quality_validators.py, neither of which is a `re.Pattern` here."""
        for name in ("PAGE_NUMBER_LINE", "AYAT_MARKER_PREFIX"):
            assert not self.DETECTOR.search(getattr(const, name)), name


class TestOneRuleOneSpelling:
    """
    Three of the six quadratic patterns were literal COPIES of another. A copy is why
    the scanner flagged `quality_validators` and not `AYAT_PATTERN`: it saw one spelling
    of the rule and missed the other.
    """

    def test_cleaner_uses_the_shared_page_number_rule(self) -> None:
        import backend.core.legal.cleaner as cleaner_mod

        assert cleaner_mod.PAGE_NUMBER_LINE is const.PAGE_NUMBER_LINE

    def test_noise_patterns_uses_the_shared_page_number_rule(self) -> None:
        assert any(p.pattern == const.PAGE_NUMBER_LINE for p in const.NOISE_PATTERNS)

    def test_quality_validators_uses_the_shared_ayat_rule(self) -> None:
        import backend.core.legal.quality_validators as qv

        assert qv.AYAT_MARKER_PREFIX is const.AYAT_MARKER_PREFIX

    def test_ayat_pattern_is_built_from_the_shared_prefix(self) -> None:
        assert const.AYAT_PATTERN.pattern.startswith(const.AYAT_MARKER_PREFIX)


# --- innocence: real documents must parse exactly as before -------------------------

BLANK = "\n\n"
DOCUMENTS = {
    "canonical": (
        "UNDANG-UNDANG REPUBLIK INDONESIA\nNOMOR 11 TAHUN 2020\nTENTANG CIPTA KERJA\n\n"
        "BAB I\nKETENTUAN UMUM\n\nPasal 1\nDalam UU ini yang dimaksud dengan:\n"
        "(1) Perizinan Berusaha adalah legalitas.\n(2) Pelaku Usaha adalah orang perseorangan.\n\n"
        "Pasal 2\nUU ini berasaskan pemerataan hak.\n\nBAB II\nPERIZINAN\n\n"
        "Pasal 3\nKetentuan lebih lanjut diatur dengan PP.\n\nPenjelasan\nCukup jelas.\n"
    ),
    # `Pasal I`, `Pasal 12A` — the numbering the pattern's alternation exists for.
    "roman_and_suffix": f"Pasal I{BLANK}Isi.{BLANK}Pasal 12A{BLANK}Isi.{BLANK}Pasal IV{BLANK}Isi.\n",
    # OCR reality: CRLF, tab/space-indented markers, a page separator, a stray page number.
    "crlf_and_indented": (
        "PRESIDEN REPUBLIK INDONESIA\r\n\r\n- 3 -\r\n\r\n\tPasal 4\r\n\tSetiap orang berhak.\r\n"
        "\t(1) Hak dijamin negara.\r\n  (2) Pelanggaran dikenai sanksi.\r\n\r\n12\r\n\r\n"
        "  Pasal 5\r\n  Ketentuan peralihan.\r\n"
    ),
    "pagesep_between_articles": f"Pasal 1{BLANK}Isi uno.{BLANK}- 12 -{BLANK}Pasal 2{BLANK}Isi due.\n",
    "pagenum_between_articles": f"Pasal 1{BLANK}Isi uno.{BLANK}7{BLANK}Pasal 2{BLANK}Isi due.\n",
}
EXPECTED_PASAL = {
    "canonical": ["1", "2", "3"],
    "roman_and_suffix": ["I", "12A", "IV"],
    "crlf_and_indented": ["4", "5"],
    "pagesep_between_articles": ["1", "2"],
    "pagenum_between_articles": ["1", "2"],
}


class TestInnocenceRealDocuments:
    @pytest.mark.parametrize("label", sorted(DOCUMENTS))
    def test_every_article_is_still_found(self, label: str) -> None:
        cleaned = LegalCleaner().clean(DOCUMENTS[label])
        parsed = LegalStructureParser().parse(cleaned)
        found = [p["number"] for p in parsed.get("pasal_list", [])]
        assert found == EXPECTED_PASAL[label]

    def test_indented_ayat_are_still_found(self) -> None:
        """Ayat markers arrive space- or tab-indented from OCR; `[ \\t\\r]*` must keep
        accepting exactly the indentation `\\s*` accepted, minus the newline."""
        text = "Pasal 5\nKetentuan:\n  (1) Ayat uno.\n\t(2) Ayat due.\n   (3) Ayat tre.\n"
        parsed = LegalStructureParser().parse(LegalCleaner().clean(text))
        ayat = parsed["pasal_list"][0]["ayat"]
        assert [a["number"] for a in ayat] == ["1", "2", "3"]

    def test_ayat_numbers_agree_between_the_two_call_sites(self) -> None:
        """`extract_ayat_numbers` and `AYAT_PATTERN` are now one rule; they must agree,
        which is the whole reason for sharing the prefix."""
        text = "Ketentuan:\n  (1) Uno.\n\t(2) Due.\n(3) Tre.\n"
        via_validator = extract_ayat_numbers(text)
        via_pattern = [int(n) for n, _ in const.AYAT_PATTERN.findall(text)]
        assert via_validator == via_pattern == [1, 2, 3]

    def test_a_mid_sentence_pasal_reference_does_not_open_an_article(self) -> None:
        """`Pasal 9` inside a sentence is a cross-reference, not a heading."""
        text = "Sebagaimana dimaksud dalam Pasal 9 ayat (2), ketentuan berlaku.\nPasal 10\nIsi.\n"
        parsed = LegalStructureParser().parse(LegalCleaner().clean(text))
        assert [p["number"] for p in parsed.get("pasal_list", [])] == ["10"]


class TestParagraphBreakSurvivesNoiseRemoval:
    """
    Scar pin. Every NOISE_PATTERNS entry is substituted with the EMPTY string, so a
    `\\n{3,}` entry in that list DELETED the paragraph break instead of collapsing it.
    The old page patterns hid it by swallowing the surrounding newlines with the very
    `\\s*` that made them quadratic — remove the ReDoS and the older bug surfaces.
    """

    @pytest.mark.parametrize(
        "noise",
        ["Halaman 2 dari 9", "- 12 -", "7"],
        ids=["halaman_footer", "page_separator", "bare_page_number"],
    )
    def test_removing_a_page_artifact_leaves_the_articles_separated(self, noise: str) -> None:
        text = f"Pasal 1{BLANK}Isi uno.{BLANK}{noise}{BLANK}Pasal 2{BLANK}Isi due.\n"
        cleaned = LegalCleaner().clean(text)
        assert noise not in cleaned
        parsed = LegalStructureParser().parse(cleaned)
        assert [p["number"] for p in parsed.get("pasal_list", [])] == ["1", "2"]

    def test_three_blank_lines_collapse_and_do_not_vanish(self) -> None:
        cleaned = LegalCleaner().clean(
            "BAB III\n\n\nPasal 6\n\n\nIsi sei.\n\n\nPasal 7\n\n\nIsi sette.\n"
        )
        assert "\n\n\n" not in cleaned  # still collapsed (Step 6's job)
        assert "IIIPasal" not in cleaned  # but NOT welded together
        parsed = LegalStructureParser().parse(cleaned)
        assert [p["number"] for p in parsed.get("pasal_list", [])] == ["6", "7"]

    def test_noise_patterns_does_not_delete_blank_line_runs(self) -> None:
        """The `\\n{3,}` entry must stay out of the substitute-with-empty list."""
        assert not any(p.pattern == r"\n{3,}" for p in const.NOISE_PATTERNS)


class TestChunkerCallerAssumption:
    """
    `PASAL_PATTERN.match()` is called at two chunker sites. `.match()` anchors at
    position 0, and the cured pattern — unlike the old one — cannot skip over a LEADING
    run of newlines to reach `Pasal`. That is only safe because `_split_by_pasal`
    hands it `.strip()`ed strings. The assumption lives in a different file from the
    pattern, so it gets a test rather than a comment.
    """

    @staticmethod
    def _split(text: str) -> list[str]:
        """`_split_by_pasal` reads no instance state — only the module-level pattern.
        Bypassing `__init__` keeps this test off the embeddings stack (`LegalChunker()`
        builds an EmbeddingsGenerator, which needs `openai` and an API key) while still
        exercising the REAL method rather than a copy of it."""
        return LegalChunker._split_by_pasal(LegalChunker.__new__(LegalChunker), text)

    @pytest.mark.parametrize("label", sorted(DOCUMENTS))
    def test_split_never_yields_a_chunk_starting_with_whitespace(self, label: str) -> None:
        cleaned = LegalCleaner().clean(DOCUMENTS[label])
        chunks = self._split(cleaned)
        assert chunks, "fixture produced no chunks — the assumption would be vacuous"
        assert [c for c in chunks if c[:1].isspace()] == []

    def test_the_split_still_recovers_the_articles_it_ever_recovered(self) -> None:
        """Innocence for the bypass above: it must be the real behaviour, not an empty
        list that trivially satisfies the whitespace assertion."""
        chunks = self._split(LegalCleaner().clean(DOCUMENTS["canonical"]))
        assert chunks[1].startswith("Pasal 1\n")
        assert chunks[-1].startswith("Pasal 3\n")

    def test_known_gap_split_by_pasal_mispairs_its_own_split_output(self) -> None:
        """
        PRE-EXISTING, NOT this commit's doing — pinned so a fix trips here on purpose.

        `re.split()` on a two-group pattern yields `[pre, g1, g2, between, g1, g2, ...]`
        — stride THREE — while `_split_by_pasal` walks it with `range(1, len(splits), 2)`.
        From the second article on, every pair is off by one: `Pasal 2`'s number becomes
        the BODY of a numberless chunk and its text is welded to the following `BAB`
        heading under a bogus `Pasal` label. Only the first and last chunks are sane.

        Verified byte-identical under the pre-fix pattern, so the ReDoS cure neither
        caused nor worsened it. Its blast radius is every legal chunk in the vector
        store, which is why it is a separate change and not a rider on this one.
        """
        chunks = self._split(LegalCleaner().clean(DOCUMENTS["canonical"]))
        assert chunks[2] == "Pasal \n2"
        assert chunks[3].startswith("Pasal UU ini berasaskan")

    def test_and_this_is_what_would_break_if_it_ever_did(self) -> None:
        """Documents the failure mode explicitly, so a future change to
        `_split_by_pasal` that stops stripping fails HERE with the reason."""
        assert const.PASAL_PATTERN.match("Pasal 1\nIsi.") is not None
        assert const.PASAL_PATTERN.match("\nPasal 1\nIsi.") is not None
        assert const.PASAL_PATTERN.match("\n\nPasal 1\nIsi.") is None
