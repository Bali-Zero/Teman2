"""
Guilt AND innocence for the `\\s`-overlaps-`\\n` ReDoS cure in the legal module.

py/polynomial-redos #7771/#7772/#7773 (chunker), #7781/#7782 and #7778/#7783
(structure_parser), #7777 (quality_validators). Two quantifiers that can eat the SAME
newline, in two forms: (a) a MULTILINE anchor followed by `\\s*`, and (b) `\\s*\\n?\\s*`.
`/api/legal/ingest` feeds this module OCR'd PDFs, which are mostly blank lines.

This file is shaped by the TWO mistakes the first draft of the cure made, both caught by
adversarial review rather than by its author. Neither is a detail:

  1. The cure was `[ \\t\\r]`, which LOOKS like "horizontal whitespace" but is not `\\s`
     minus `\\n` — Python's `\\s` also matches NBSP, FORM FEED (the PDF page break),
     vertical tab and every Unicode space, and nothing upstream normalises them away. So
     `\\xa0Pasal 1` went from two articles to zero: a fast regex that silently truncates
     a law. `TestTheClassIsExactlyBackslashSMinusNewline` is that mistake, guarded.
  2. Form (b) was measured "linear, <1ms at 16k" and shipped as such. It was 2.87s. The
     payloads were bare newline runs, which never get past `^BAB`, and payloads with any
     non-newline character let the trailing `(.+?)` close immediately — the measurement
     was of the payload, not the pattern. Every `PREFIX_*` payload below exists for that.

Innocence carries as much weight as guilt throughout: a regex that no longer backtracks
but no longer finds `Pasal 2` has traded a slow ingest for a silently truncated law, and
nothing downstream would notice — the chunker would just emit fewer chunks.
"""

import re
import sys
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
    "BAB_PATTERN": const.BAB_PATTERN,
    **{f"NOISE_PATTERNS[{i}]": p for i, p in enumerate(const.NOISE_PATTERNS)},
}

# The anchor-overlap forms eat a bare run of blank lines. The INTERIOR `\s*\n?\s*` form
# does not: it hides behind the pattern's own literal, and any non-newline character in
# the run lets the trailing `(.+?)` close immediately. `BAB_PATTERN` measured "linear,
# <1ms at 16k" on every payload here EXCEPT `PREFIX_bab`, where it took 2.87s — the
# payload, not the pattern, was what the first audit measured. Every literal-prefixed
# row below exists because of that.
PAYLOADS = {
    "blank_lines": "\n" * ADVERSARIAL_N,
    "space_newline": " \n" * (ADVERSARIAL_N // 2),
    "crlf": "\r\n" * (ADVERSARIAL_N // 2),
    "tabs_and_newlines": "\t\n" * (ADVERSARIAL_N // 2),
    "nbsp_newline": "\xa0\n" * (ADVERSARIAL_N // 2),
    "formfeed_newline": "\f\n" * (ADVERSARIAL_N // 2),
    "PREFIX_pasal": "Pasal 1" + "\n" * ADVERSARIAL_N,
    "PREFIX_ayat": "(1)" + "\n" * ADVERSARIAL_N,
    "PREFIX_bab": "BAB I" + "\n" * ADVERSARIAL_N,
    "PREFIX_bab_nbsp": "BAB I" + "\xa0\n" * (ADVERSARIAL_N // 2),
    "PREFIX_pagesep": "- 1 -" + "\n" * ADVERSARIAL_N,
}


def _elapsed(rx: re.Pattern, text: str) -> float:
    start = time.perf_counter()
    rx.findall(text)
    return time.perf_counter() - start


# Repetitions for the RATIO verdict only. Timing noise is strictly additive — the
# CPU cannot run faster than its own best pass — so the MINIMUM of k runs is the
# low-noise estimator, and a genuinely quadratic pattern is slow in every one of
# them, which is why this cannot hide a regression. The control test below proves
# that on the pre-fix quadratic.
_RATIO_REPEATS = 3


def _elapsed_min(rx: re.Pattern, text: str, repeats: int = _RATIO_REPEATS) -> float:
    return min(_elapsed(rx, text) for _ in range(repeats))


class TestLinearity:
    @pytest.mark.parametrize("name", sorted(CURED))
    @pytest.mark.parametrize("payload", sorted(PAYLOADS))
    def test_guilt_no_pattern_blows_up_on_whitespace_runs(self, name: str, payload: str) -> None:
        took = _elapsed(CURED[name], PAYLOADS[payload])
        assert took < BUDGET_SECONDS, (
            f"{name} took {took:.3f}s on {payload} (budget {BUDGET_SECONDS}s)"
        )

    # Each row is (name, pre-fix source, ITS REAL FLAGS, the cured pattern it became, THE
    # PAYLOAD THAT EXPOSES IT). Both the flags and the payload are per-row on purpose:
    #   - a bare newline run exposes the anchor form but never BAB's interior one;
    #   - BAB is NOT DOTALL, and compiling its pre-fix source WITH DOTALL makes `(.+?)`
    #     swallow the first newline and the quadratic disappears.
    # Getting either wrong reproduces nothing and reads as "measured fast", which is
    # precisely how BAB shipped as "linear" in the first draft of this file.
    M = re.IGNORECASE | re.MULTILINE
    PRE_FIX = [
        (
            "PASAL_PATTERN",
            r"(?:^|\n)\s*Pasal\s+([IVXLC]+|\d+[A-Z]?)\s*\n?\s*(.+?)"
            r"(?=(?:^|\n)\s*Pasal\s+(?:[IVXLC]+|\d+[A-Z]?)|^\s*BAB\s+|^Penjelasan|\Z)",
            M | re.DOTALL,
            lambda: const.PASAL_PATTERN,
            "\n" * 8_000,
        ),
        (
            "AYAT_PATTERN",
            r"(?:^|\n)\s*\((\d+)\)\s*(.+?)(?=(?:^|\n)\s*\(\d+\)|$)",
            re.MULTILINE | re.DOTALL,
            lambda: const.AYAT_PATTERN,
            "\n" * 8_000,
        ),
        (
            "AYAT_MARKER_PREFIX",
            r"(?:^|\n)\s*\((\d+)\)",
            re.MULTILINE,
            lambda: re.compile(const.AYAT_MARKER_PREFIX, re.MULTILINE),
            "\n" * 8_000,
        ),
        (
            "PAGE_NUMBER_LINE",
            r"^\s*\d+\s*$",
            re.MULTILINE,
            lambda: re.compile(const.PAGE_NUMBER_LINE, re.MULTILINE),
            "\n" * 8_000,
        ),
        (
            "PAGE_SEPARATOR",
            r"^\s*-\s*\d+\s*-\s*$",
            re.MULTILINE,
            lambda: const.NOISE_PATTERNS[3],
            "\n" * 8_000,
        ),
        (
            "BAB_PATTERN",
            r"^BAB\s+([IVX]+|[A-Z]+|\d+)\s*\n?\s*(.+?)(?=\n|$)",
            M,  # NOT DOTALL — that is the whole point
            lambda: const.BAB_PATTERN,
            "BAB I" + "\n" * 8_000,  # the literal prefix IS the reproduction
        ),
    ]

    @pytest.mark.parametrize(
        "name,pre_fix_source,flags,cured,payload", PRE_FIX, ids=[r[0] for r in PRE_FIX]
    )
    def test_the_cure_is_what_makes_it_fast(
        self, name: str, pre_fix_source: str, flags: int, cured, payload: str
    ) -> None:
        """
        Pins CAUSATION, not just the outcome. Without this a future rewrite could satisfy
        the budget above for some unrelated reason and the lesson would be lost — and it
        names each pattern, because a cure applied to one of seven is how this family got
        six instances in the first place.
        """
        pre_fix = re.compile(pre_fix_source, flags)
        slow, fast = _elapsed(pre_fix, payload), _elapsed(cured(), payload)
        assert slow > 20 * fast, f"{name}: pre-fix {slow:.4f}s vs cured {fast:.4f}s"

    def test_the_pre_fix_flags_match_what_the_module_actually_compiles(self) -> None:
        """Innocence for the table above: a wrong flag makes a pre-fix source look fast
        and silently turns every causation row into a no-op."""
        assert const.PASAL_PATTERN.flags & re.DOTALL
        assert const.AYAT_PATTERN.flags & re.DOTALL
        assert not (const.BAB_PATTERN.flags & re.DOTALL)


class TestNoAnchorAdjacentWhitespaceReturns:
    """
    Class guard. The cure is for a SHAPE, so the test is over the shape — a seventh
    instance in this module fails here instead of waiting for the next scan.
    """

    # Form (a): `^` (not the `[^...]` negation) or the tail of `(?:^|\n)`, then `\s`.
    # Form (b): `\s*\n?\s*` — two `\s` quantifiers straddling an optional newline, all
    #           three able to eat the same character. Added after form (b) shipped
    #           undetected in BAB_PATTERN: a guard that knows one shape of a family
    #           certifies the others clean.
    DETECTOR = re.compile(r"(?<!\[)\^\\s|\\n\)\\s|\\s[*+]\\n\?\\s[*+]")

    def test_innocence_of_the_detector(self) -> None:
        """The detector must not fire on the cure, nor on a negated class, nor on a
        `\\s` that is gated by a literal (those have O(1) start positions)."""
        for safe in (
            r"(?:^|\n)[^\S\n]*Pasal\s+",
            r"^[^\S\n]*\d+[^\S\n]*$",
            r"^BAB\s+([IVX]+)(?:[^\S\n]*\n)*[^\S\n]*(.+?)(?=\n|$)",
            r"[^\s|;&)]+",
            r"^PRESIDEN REPUBLIK INDONESIA\s*\n",
            r"^Halaman\s+\d+\s+dari\s+\d+",
            r"\n{3,}",
        ):
            assert not self.DETECTOR.search(safe), safe

    def test_guilt_of_the_detector(self) -> None:
        """And it must fire on every shape this commit removed — BOTH forms."""
        for guilty in (
            r"(?:^|\n)\s*Pasal\s+([IVXLC]+|\d+[A-Z]?)",
            r"(?:^|\n)\s*\((\d+)\)",
            r"^\s*\d+\s*$",
            r"^\s*-\s*\d+\s*-\s*$",
            r"^BAB\s+([IVX]+|[A-Z]+|\d+)\s*\n?\s*(.+?)(?=\n|$)",  # form (b)
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


class TestTheClassIsExactlyBackslashSMinusNewline:
    """
    The cure narrows a character class, so the class itself is the risk — and this is
    where the first attempt was WRONG. `[ \\t\\r]` looks like "horizontal whitespace",
    but Python's `\\s` on a str pattern also matches NBSP, FORM FEED (the PDF page
    break), vertical tab and every Unicode space, and `WHITESPACE_FIXES` normalises
    none of them. `\\xa0Pasal 1` then parsed to ZERO articles. `[^\\S\\n]` is the
    complement done properly: `\\s` minus `\\n`, nothing else.
    """

    PRE_FIX_PASAL = re.compile(
        r"(?:^|\n)\s*Pasal\s+([IVXLC]+|\d+[A-Z]?)\s*\n?\s*(.+?)"
        r"(?=(?:^|\n)\s*Pasal\s+(?:[IVXLC]+|\d+[A-Z]?)|^\s*BAB\s+|^Penjelasan|\Z)",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    PRE_FIX_AYAT = re.compile(
        r"(?:^|\n)\s*\((\d+)\)\s*(.+?)(?=(?:^|\n)\s*\(\d+\)|$)", re.MULTILINE | re.DOTALL
    )
    PRE_FIX_PAGENUM = re.compile(r"^\s*\d+\s*$", re.MULTILINE)
    PRE_FIX_PAGESEP = re.compile(r"^\s*-\s*\d+\s*-\s*$", re.MULTILINE)

    # Every character `\s` matches except `\n` itself. A PDF text extractor emits the
    # exotic ones routinely — `\f` IS the page break.
    WHITESPACE = [" ", "\t", "\r", "\x0b", "\x0c", "\xa0", " ", " ", "　"]
    IDS = ["space", "tab", "cr", "vtab", "formfeed", "nbsp", "em", "narrow_nbsp", "ideographic"]

    @pytest.mark.parametrize("ws", WHITESPACE, ids=IDS)
    def test_articles_are_found_through_any_whitespace_the_old_pattern_accepted(
        self, ws: str
    ) -> None:
        text = f"Preamble\n{ws}Pasal 1\nIsi satu.\n{ws}Pasal 2\nIsi dua."
        assert const.PASAL_PATTERN.findall(text) == self.PRE_FIX_PASAL.findall(text)
        assert len(const.PASAL_PATTERN.findall(text)) == 2

    @pytest.mark.parametrize("ws", WHITESPACE, ids=IDS)
    def test_clauses_are_found_through_any_whitespace_the_old_pattern_accepted(
        self, ws: str
    ) -> None:
        text = f"Ketentuan:\n{ws}(1) Satu.\n{ws}(2) Due."
        assert const.AYAT_PATTERN.findall(text) == self.PRE_FIX_AYAT.findall(text)
        assert len(const.AYAT_PATTERN.findall(text)) == 2

    @pytest.mark.parametrize("ws", WHITESPACE, ids=IDS)
    def test_page_artifacts_are_still_stripped_through_any_whitespace(self, ws: str) -> None:
        page_num = f"Pasal 1\nIsi.\n{ws}12{ws}\nPasal 2\nIsi."
        page_sep = f"Pasal 1\nIsi.\n{ws}- 12 -{ws}\nPasal 2\nIsi."
        cured_num = re.compile(const.PAGE_NUMBER_LINE, re.MULTILINE)
        assert cured_num.sub("", page_num) == self.PRE_FIX_PAGENUM.sub("", page_num)
        assert const.NOISE_PATTERNS[3].sub("", page_sep) == self.PRE_FIX_PAGESEP.sub("", page_sep)
        assert "12" not in const.NOISE_PATTERNS[3].sub("", cured_num.sub("", page_sep))

    @pytest.mark.parametrize("ws", WHITESPACE, ids=IDS)
    def test_the_cured_classes_accept_exactly_that_character(self, ws: str) -> None:
        """Direct on the class, so a failure above cannot be blamed on the surrounding
        pattern. `\\n` is the one character that must NOT be accepted."""
        for source in (const.PAGE_NUMBER_LINE, const.AYAT_MARKER_PREFIX):
            assert r"[^\S\n]" in source, f"{source!r} no longer uses the shared class"
        cls = re.compile(r"^[^\S\n]+$")
        assert cls.match(ws), f"{ws!r} rejected by [^\\S\\n]"
        assert not cls.match("\n"), "newline must NOT be in the class — it is the anchor's job"


class TestBabTitleAcrossBlankLines:
    """
    BAB's body group is NOT DOTALL, so unlike PASAL its prefix genuinely has to cross the
    newlines to reach the title. That is why the cure there is `(?:[^\\S\\n]*\\n)*[^\\S\\n]*`
    — unambiguous but still multi-line — and not the same class the others got.
    """

    PRE_FIX = re.compile(
        r"^BAB\s+([IVX]+|[A-Z]+|\d+)\s*\n?\s*(.+?)(?=\n|$)", re.IGNORECASE | re.MULTILINE
    )

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("BAB I KETENTUAN\n", [("I", "KETENTUAN")]),
            ("BAB I\nKETENTUAN\n", [("I", "KETENTUAN")]),
            ("BAB II\n\nPERIZINAN\n", [("II", "PERIZINAN")]),
            ("BAB III\n\n\nSANKSI\n", [("III", "SANKSI")]),
            ("BAB IV\xa0\n\xa0PENUTUP\n", [("IV", "PENUTUP")]),
        ],
        ids=["same_line", "one_newline", "blank_line", "two_blank_lines", "nbsp_padded"],
    )
    def test_title_still_found_and_identical_to_the_pre_fix_pattern(self, text, expected) -> None:
        assert const.BAB_PATTERN.findall(text) == expected
        assert const.BAB_PATTERN.findall(text) == self.PRE_FIX.findall(text)


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


# ---------------------------------------------------------------------------
# The payload table above is HAND-PICKED, and a hand-picked table is exactly what let
# form (b) ship as "measured linear". After the merge, CodeQL re-scanned the merge commit
# and named two payloads nobody in this file had tried — `"\nPasal C" + "\n"*n` and
# `"BAB I" + "00"*n`. Neither reproduces anything (they are linear on the PRE-fix patterns
# too: a symbolic path through the NFA, not an executed one). But the point stands: the
# author picks payloads out of the same head that wrote the regex, so the blind spot is
# shared. This sweep replaces taste with a cross-product, and — the part that makes it
# worth its runtime — it is shown catching the bug we already know about before it is
# allowed to certify anything.
# ---------------------------------------------------------------------------

SWEEP_N = 20_000
# Two verdicts, because either one alone is weak. The ABSOLUTE ceiling catches a gross
# quadratic in one measurement; but a quadratic with a small coefficient can sit under any
# ceiling at a fixed n and still be pathological further up the curve, so anything slow
# enough to be measurable at all is also made to prove its GROWTH. Conversely a ratio
# alone is pure noise at 0.4ms, which is why the floor gates it.
#
# CORRECTED 2026-08-02, measured not reasoned. The sentence that stood here — "a healthy
# pattern never reaches the floor, never pays for the second measurement, and cannot flake
# on it" — was a MEASUREMENT FROZEN AT AUTHORING TIME (superscar #9 / W106: a constant that
# was true when written and that nothing re-measures). On a machine with `mediaanalysisd`
# holding ~188% CPU, a healthy pattern measured 0.0059s — past the 0.004s floor — and then
# produced a 4.2x ratio from pure scheduler noise, failing a REQUIRED pre-push gate on a
# branch containing zero backend changes. The ABSOLUTE ceiling passed comfortably in the
# same run (0.0246s against 0.25s), which is what proves the regex was innocent and the
# clock was not. The thresholds below are unchanged; only the ratio path's SAMPLING is,
# via `_elapsed_min` (see there for why min-of-k cannot hide a regression). A guard that
# fabricates reds under load is a guard someone eventually disarms — superscar #2 waiting
# to happen, and the reason this was fixed rather than merely tolerated.
#
# How exposed each pattern is, measured the same day — one full sweep each, worst payload
# combination, against the 0.004s floor:
#
#     PAGE_NUMBER_LINE   57.2 ms = 1429% of the floor   <- crosses on EVERY run
#     BAB_PATTERN         6.5 ms =  162% of the floor   <- crosses on EVERY run
#     PASAL_PATTERN       3.8 ms =   96% of the floor
#     AYAT_PATTERN        3.7 ms =   93% of the floor
#     AYAT_MARKER_PREFIX  3.2 ms =   80% of the floor
#
# So it was never one unlucky pattern under one unlucky load: two cross the floor on EVERY
# run and pay for the second measurement, and two more sit within 7% of it. Two consecutive
# pre-push reds came out of that — `NOISE_PATTERNS[1]` (0.0046s -> 0.0248s) and then
# `AYAT_MARKER_PREFIX` (0.0071s -> 0.0279s) — and `NOISE_PATTERNS[1]`'s honest worst case is
# 0.708 ms, 18% of the floor, so roughly 6x inflation carried it to a gate it should never
# see. Raising the floor is NOT the cure: it would blind the branch to exactly the
# small-coefficient quadratic the branch exists for.
SWEEP_CEILING_SECONDS = 0.25
SWEEP_RATIO_FLOOR_SECONDS = 0.004
SWEEP_MAX_RATIO = 3.0

# CORRECTED 2026-08-08, measured not reasoned (same lineage as the 2026-08-02 note above —
# `_elapsed_min` cut the false-red rate, it did not close it). PASAL_PATTERN convicted at
# 0.0056s -> 0.0796s (14.1x) on M5 with 4 pytest + 8 claude processes live, and passed in
# isolation on the same tree, same second: the window was noisy, min-of-3 on BOTH sides
# does not save you when the doubled-side's three repeats happen to land inside the same
# contention burst as each other but the base-side's three don't. More repeats narrows this
# but never closes it against SUSTAINED (not merely transient) load, because sustained load
# is a roughly uniform multiplier that a same-side min-of-k cannot distinguish from genuine
# cost. A uniform multiplier DOES cancel in a ratio, though — which is what a same-run
# linear control gives you: if a known-linear pattern's OWN doubled/base ratio is also
# inflated in this exact window, the window is noisy and the candidate's ratio is not
# evidence. `[\s\S]` is provably O(n) (single character class, no backtracking possible);
# `_CONTROL_N` is sized independently of SWEEP_N (10x) so the control's own absolute cost
# clears SWEEP_RATIO_FLOOR_SECONDS with margin — empirically ~13ms at 200k chars, ratio
# ~1.9-2.4 unloaded — because below the floor its own ratio would be exactly the kind of
# noise it exists to detect.
_LINEAR_CONTROL_PATTERN = re.compile(r"[\s\S]")
_CONTROL_N = SWEEP_N * 10
_LINEAR_CONTROL_MAX_RATIO = 2.5

SWEEP_PREFIXES = (
    "",
    "\n",
    "BAB I",
    "BAB I\n",
    "\nPasal 1",
    "\nPasal C",  # CodeQL's own witness: `C` is a roman numeral in `[IVXLC]`
    "\n(1)",
    "- 12 -",
    "\n 1 ",
    "Halaman 1 dari 2",
)
SWEEP_PUMPS = (
    "\n", "\n\n", " \n", "\n ", " ", "\t", "\r", "\xa0", "0", "00", "A", "x\n",
    # longer/mixed runs: a one-character pump cannot express an alternating interior
    "\n \n\t", "\n\xa0", " \n\n ",
)
# A suffix is not decoration: `PASAL_PATTERN` terminates on a lookahead with FOUR branches
# (`\nPasal`, `^BAB`, `^Penjelasan`, `\Z`), and a payload that only ever ends in `\Z`
# exercises one of them. Which branch fires changes where the backtracking stops.
SWEEP_SUFFIXES = ("", "\nPasal 2", "\nBAB II", "\nPenjelasan Umum")

# Kept verbatim as the sweep's CONTROL, never as a thing under test: a sweep that reports
# "nothing found" proves nothing until it is seen reporting the defect that already bit us.
_PRE_FIX_BAB = re.compile(
    r"^BAB\s+([IVX]+|[A-Z]+|\d+)\s*\n?\s*(.+?)(?=\n|$)",
    re.IGNORECASE | re.MULTILINE,
)


def _sweep_verdict(rx: re.Pattern) -> str | None:
    """Return a failure message for the first super-linear combination, or None.

    The control and the patterns under test go through THIS function, so "the control
    passes" and "the sweep would reject a regression" are the same claim rather than two
    hopeful ones — the earlier draft asserted only that a locally-copied historical regex
    was slow, which proves the budget discriminates and nothing about the sweep's reach.
    """
    for prefix in SWEEP_PREFIXES:
        for pump in SWEEP_PUMPS:
            for suffix in SWEEP_SUFFIXES:
                text = prefix + pump * SWEEP_N + suffix
                elapsed = _elapsed(rx, text)
                where = f"prefix={prefix!r} pump={pump!r} suffix={suffix!r}"
                if elapsed >= SWEEP_CEILING_SECONDS:
                    return (
                        f"{elapsed:.4f}s at n={SWEEP_N} on {where} "
                        f"(ceiling {SWEEP_CEILING_SECONDS}s)"
                    )
                if elapsed > SWEEP_RATIO_FLOOR_SECONDS:
                    # Both sides re-measured as min-of-k: the single sample above is
                    # enough to decide whether to LOOK, never enough to convict.
                    elapsed = _elapsed_min(rx, text)
                    doubled = _elapsed_min(rx, prefix + pump * (SWEEP_N * 2) + suffix)
                    if elapsed <= SWEEP_RATIO_FLOOR_SECONDS:
                        continue
                    ratio = doubled / max(elapsed, 1e-9)
                    if ratio > SWEEP_MAX_RATIO:
                        # Confirm against a same-run linear control before convicting — see
                        # _LINEAR_CONTROL_PATTERN above. A noisy window inflates the
                        # control's own ratio too; a clean one leaves it near its ideal 2.0x.
                        control_base_text = "\n" * _CONTROL_N
                        control_doubled_text = "\n" * (_CONTROL_N * 2)
                        control_elapsed = _elapsed_min(_LINEAR_CONTROL_PATTERN, control_base_text)
                        control_doubled = _elapsed_min(_LINEAR_CONTROL_PATTERN, control_doubled_text)
                        control_ratio = control_doubled / max(control_elapsed, 1e-9)
                        if control_ratio > _LINEAR_CONTROL_MAX_RATIO:
                            continue
                        return (
                            f"{elapsed:.4f}s -> {doubled:.4f}s ({ratio:.1f}x for 2x input, "
                            f"max {SWEEP_MAX_RATIO}x; linear control confirmed clean at "
                            f"{control_ratio:.1f}x) on {where}"
                        )
    return None


class TestRatioConfirmation:
    """The ratio branch's own guilt/innocence, with the clock taken OUT of the loop.

    `_elapsed_min` is what the branch now trusts, so the cure is worth exactly two claims:
    that the estimator really is the minimum, and that the re-measurement is consulted
    before a verdict comes out. Timing real regexes would prove neither — an
    anti-load-noise fix verified by timing on a machine whose load IS the variable under
    test is a coin flip — so every measurement here and in the sweep bracket below is
    scripted.

    What is NOT covered is stated plainly rather than implied: `TestPayloadSweep`'s control
    fires on the CEILING branch (`_PRE_FIX_BAB` takes ~7.6s at n=20k, 30x the ceiling), so
    no REAL regex in this file exercises the ratio branch end to end. That gap predates
    this change — the branch that fired falsely was also the branch with no proof it fires
    truly — and it is on the ledger. These tests cover the DECISION.
    """

    def test_elapsed_min_takes_the_minimum_not_the_first_or_the_mean(self, monkeypatch):
        """Load only ever ADDS time, so the minimum is the estimator — first and mean are not.

        0.002 is the honest cost and the other two are load. `first` would answer 0.100 and
        `mean` 0.0507: both report the machine, which is precisely what produced the two
        false reds this branch cost.
        """
        samples = iter([0.100, 0.002, 0.050])
        monkeypatch.setattr(
            sys.modules[__name__], "_elapsed", lambda rx, text: next(samples),
        )
        assert _elapsed_min(re.compile("x"), "y", repeats=3) == 0.002


class TestPayloadSweep:
    """Cross-product search, so the next quadratic is not found by the next scanner."""

    def test_control_the_sweep_rejects_the_pre_fix_quadratic(self):
        """If the sweep cannot fail, every clean result below is decoration."""
        verdict = _sweep_verdict(_PRE_FIX_BAB)
        assert verdict is not None, (
            "the sweep found NOTHING wrong with the pre-fix form (b), which took 2.87s at "
            "n=16k when it was live. Either the grid no longer reaches it or the "
            "thresholds no longer discriminate — in both cases the clean results below "
            "mean nothing and must not be believed."
        )

    @staticmethod
    def _script(
        monkeypatch, trigger, base_honest, doubled_first, doubled_honest,
        control_base_honest=0.002, control_doubled_honest=0.004,
    ):
        """Drive the whole sweep on a scripted clock: reads answer by ROLE, not by ordinal.

        The sweep's very first read is the single-sample TRIGGER and is the only one a
        load spike is scripted into; every read after it is the pattern's honest cost,
        told apart by payload length — anything longer than the first text is the doubled
        side. `doubled_first` is separate so the doubled side's own inflation can be
        scripted independently, which is what makes `_elapsed_min` on THAT side killable
        rather than decorative.

        The linear control (`_LINEAR_CONTROL_PATTERN`) is scripted independently by
        identity, not by length — its texts (`_CONTROL_N`-sized) are a different length
        class than the candidate's, so reusing the candidate's length bookkeeping for it
        would silently misclassify every control read. Default control readings are
        honest 2.0x (0.004 / 0.002) — a clean window — so a test that never overrides
        them is asserting "the confirmation was consulted and found nothing wrong",
        not "the confirmation never ran".
        """
        state = {"n": 0, "base_len": None, "d": 0, "control_base_len": None}

        def fake_elapsed(rx, text):
            state["n"] += 1
            if rx is _LINEAR_CONTROL_PATTERN:
                if state["control_base_len"] is None:
                    state["control_base_len"] = len(text)
                    return control_base_honest
                is_doubled = len(text) > state["control_base_len"]
                return control_doubled_honest if is_doubled else control_base_honest
            if state["base_len"] is None:
                state["base_len"] = len(text)
                return trigger
            if len(text) > state["base_len"]:
                state["d"] += 1
                return doubled_first if state["d"] == 1 else doubled_honest
            return base_honest

        monkeypatch.setattr(sys.modules[__name__], "_elapsed", fake_elapsed)
        return state

    def test_an_inflated_trigger_read_does_not_become_a_verdict(self, monkeypatch):
        """The false red of 2026-08-02, reproduced without a clock.

        Trigger read 5 ms — over the 4 ms floor, under the 0.25 s ceiling — but re-measured
        the pattern costs 1 ms, back UNDER the floor: it was never eligible for this branch,
        so its 20x ratio is never consulted. Mutation-checked both ways: drop the
        `elapsed <= FLOOR` re-check and the 20x convicts; keep the single sample as the base
        instead of re-measuring and 0.005 -> 0.020 convicts at 4x.
        """
        state = self._script(
            monkeypatch, trigger=0.005, base_honest=0.001,
            doubled_first=0.020, doubled_honest=0.020,
        )
        assert _sweep_verdict(CURED["PASAL_PATTERN"]) is None
        assert state["n"] > 1, "the re-measurement was never asked — the trigger never fired"

    def test_an_inflated_doubled_read_does_not_become_a_verdict(self, monkeypatch):
        """The other half of the same spike: the base is honest, the DOUBLED read is not.

        6 ms base sits legitimately above the floor (`BAB_PATTERN` and `PAGE_NUMBER_LINE`
        live there permanently), so this branch is entered on every combination. One 50 ms
        doubled read is 8.3x and would convict; re-measured it is 9 ms, an honest 1.5x.
        Without `_elapsed_min` on the doubled side this test goes red — which is the only
        reason that half of the change is not decoration.
        """
        self._script(
            monkeypatch, trigger=0.006, base_honest=0.006,
            doubled_first=0.050, doubled_honest=0.009,
        )
        assert _sweep_verdict(CURED["PASAL_PATTERN"]) is None

    def test_a_consistently_slow_and_growing_pattern_still_fails(self, monkeypatch):
        """Honest numbers that DESERVE a verdict: one must come out.

        Paired with the two above this brackets the branch — neither "always silent" nor
        "always loud" passes all three — and it is what proves min-of-k cannot hide a real
        regression: 6 ms doubling to 48 ms is slow in every sample, so its minimum is slow
        too and its doubled minimum still grows. The linear control is left at its default
        honest 2.0x (a clean window), so the confirmation added 2026-08-08 does not stand
        between a real regression and its verdict.
        """
        self._script(
            monkeypatch, trigger=0.006, base_honest=0.006,
            doubled_first=0.048, doubled_honest=0.048,
        )
        verdict = _sweep_verdict(CURED["PASAL_PATTERN"])
        assert verdict is not None and "8.0x for 2x input" in verdict, verdict

    def test_a_noisy_window_that_also_inflates_the_linear_control_does_not_convict(
        self, monkeypatch,
    ):
        """The false red of 2026-08-08, reproduced without a clock.

        PASAL_PATTERN measured 0.0056s -> 0.0796s (14.1x) on M5 with 4 pytest + 8 claude
        processes live, and passed in isolation on the same tree, same second — the
        window was noisy, not the regex. Scripted here with the same magnitudes: the
        candidate's own numbers are indistinguishable from
        `test_a_consistently_slow_and_growing_pattern_still_fails` above (which DOES
        convict) — the only difference is the linear control ALSO reads a blown-out
        ratio in this window (15x, scripted independently), which is what tells the
        branch to stand down. Without the control confirmation this test is identical to
        the false red that actually happened.
        """
        self._script(
            monkeypatch, trigger=0.006, base_honest=0.006,
            doubled_first=0.080, doubled_honest=0.080,
            control_base_honest=0.002, control_doubled_honest=0.030,
        )
        assert _sweep_verdict(CURED["PASAL_PATTERN"]) is None

    def test_a_control_confirming_clean_lets_the_verdict_through(self, monkeypatch):
        """Innocence for the confirmation step itself: a clean control does not suppress.

        Same shape as the noisy-window test above but the control stays honest (default
        2.0x) — proving the `continue` above is reached ONLY when the control itself is
        inflated, not on every ratio-branch trip. Without this, an implementation that
        always suppressed (e.g. `if True: continue`) would pass the noisy-window test
        for the wrong reason.
        """
        self._script(
            monkeypatch, trigger=0.006, base_honest=0.006,
            doubled_first=0.080, doubled_honest=0.080,
        )
        verdict = _sweep_verdict(CURED["PASAL_PATTERN"])
        assert verdict is not None and "13.3x for 2x input" in verdict, verdict

    @pytest.mark.parametrize("name", sorted(CURED))
    def test_no_cured_pattern_is_superlinear_on_any_swept_payload(self, name):
        verdict = _sweep_verdict(CURED[name])
        assert verdict is None, (
            f"{name}: {verdict}. A payload shape this file did not anticipate reaches a "
            "quadratic path."
        )
