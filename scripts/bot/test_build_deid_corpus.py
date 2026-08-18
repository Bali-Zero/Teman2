"""Unit tests for scripts/bot/build_deid_corpus.py.

Orchestrator corpus gate (2026-08-15, closing line): "Please test
guilt+innocence for localhost enforcement, fingerprints, permissions,
residual PII and no-key state." This file proves each of those five
points with actual pytest, on top of the manual smoke tests already run
during development (which found and fixed the `min_remaining_chars` gate
mismatch — see `build_corpus`'s docstring comment on that).

Run:
    cd ~/nuzantara && python3 -m pytest scripts/bot/test_build_deid_corpus.py -v
"""

from __future__ import annotations

import json
import logging
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR.parent.parent))

from scripts.bot.build_deid_corpus import (  # noqa: E402
    RawRecord,
    _has_residual_pii,
    _has_spaced_digit_pii,
    _independent_pii_scan,
    _is_date_or_amount_shape,
    _iter_txt_records,
    _load_records,
    _mkdir_private,
    _ollama_ner_pass,
    _write_jsonl_private,
    build_corpus,
)


@pytest.fixture(autouse=True)
def _isolate_dynamic_crm_database_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep corpus tests independent from backend-suite environment mutation."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("PGURL", raising=False)


def _write_wa_txt(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestGuiltResidualAndIndependentScan:
    """Scan A (residual PII) + Scan B (independent heuristic) each must
    actually DROP the shapes they claim to catch."""

    def test_phone_number_redacted_and_kept_no_raw_digits_survive(self, tmp_path: Path):
        """The primary Redactor (reused, not reimplemented) catches this
        shape and replaces it with a placeholder — that IS the intended
        success path, so the record is correctly KEPT, just with the raw
        phone number gone. Scan A/B exist for what the Redactor MISSES,
        not as a second copy of what it already catches."""
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        _write_wa_txt(
            input_dir / "chat.txt",
            ["12/01/26, 09:00 - Client: Call me at 081234567890 please"],
        )
        out_dir = tmp_path / "out"
        stats = build_corpus(
            input_dir=input_dir,
            output_dir=out_dir,
            execute=True,
            use_ollama_ner=False,
            ollama_model="unused",
            require_role_aware=False,
        )
        assert stats["kept"] == 1
        written_text = "".join(f.read_text(encoding="utf-8") for f in out_dir.glob("*.local.jsonl"))
        assert "081234567890" not in written_text
        assert "[PHONE-ID-LOCAL-REDACTED]" in written_text

    def test_email_redacted_and_kept_no_raw_address_survives(self, tmp_path: Path):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        _write_wa_txt(
            input_dir / "chat.txt",
            ["12/01/26, 09:00 - Client: email me at someone@example.com thanks"],
        )
        out_dir = tmp_path / "out"
        stats = build_corpus(
            input_dir=input_dir,
            output_dir=out_dir,
            execute=True,
            use_ollama_ner=False,
            ollama_model="unused",
            require_role_aware=False,
        )
        assert stats["kept"] == 1
        written_text = "".join(f.read_text(encoding="utf-8") for f in out_dir.glob("*.local.jsonl"))
        assert "someone@example.com" not in written_text

    def test_residual_phone_that_survives_redaction_is_still_dropped(self, tmp_path: Path):
        """Scan A's actual job: catch a phone-shaped digit run the primary
        Redactor's specific pattern does NOT recognize (a malformed/partial
        number), so it must not reach output un-redacted."""
        from scripts.bot.build_deid_corpus import _has_residual_pii

        # A long digit run the Redactor's phone-specific rule may not
        # target (not in local 08xx format) but Scan A's broad
        # long-digit-run net still catches.
        assert _has_residual_pii("reference number 1234567890123") is True

    def test_honorific_name_dropped_by_independent_scan(self):
        findings = _independent_pii_scan("Please contact Ibu Siti Rahayu about the KITAS")
        assert "honorific_name" in findings

    def test_address_marker_dropped_by_independent_scan(self):
        findings = _independent_pii_scan("The villa is on Jl. Sunset Road number 8")
        assert "address_marker" in findings

    def test_id_doc_near_digits_dropped_by_independent_scan(self):
        findings = _independent_pii_scan("My NPWP is 123456789012345 for the filing")
        assert "id_doc_near_digits" in findings

    def test_titlecase_bigram_dropped_by_independent_scan(self):
        findings = _independent_pii_scan("Please forward this to John Smith at the office")
        assert "titlecase_bigram" in findings

    def test_end_to_end_honorific_and_address_both_drop_full_pipeline(self, tmp_path: Path):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        _write_wa_txt(
            input_dir / "chat.txt",
            [
                "12/01/26, 09:00 - Client: Ibu Siti Rahayu tinggal di Jl. Sunset Road",
                "12/01/26, 09:01 - Client: John Smith akan datang besok",
            ],
        )
        stats = build_corpus(
            input_dir=input_dir,
            output_dir=tmp_path / "out",
            execute=False,
            use_ollama_ner=False,
            ollama_model="unused",
            require_role_aware=False,
        )
        assert stats["kept"] == 0
        assert stats["dropped_independent_scan"] == 2


class TestG1SpacedDigitRuns:
    """G1 (orchestrator corpus gate / Gemini diagnostic, 2026-08-15):
    Scan A's original contiguous-digit-run check missed phone/NIK numbers
    written with everyday WA-style separators (spaces, dots, dashes)."""

    def test_spaced_phone_number_flagged(self):
        assert _has_spaced_digit_pii("call me at 0812 3456 7890 please") is True

    def test_spaced_nik_flagged_even_with_no_keyword_nearby(self):
        """The addendum's specific concern: a NIK with no ID-keyword
        nearby escapes Scan B's `_ID_DOC_NEAR_DIGITS_RE` too — Scan A must
        catch it on shape alone."""
        assert _has_spaced_digit_pii("my number is 3171 2345 6789 0123 for the form") is True

    def test_dash_and_dot_separated_digit_run_flagged(self):
        assert _has_spaced_digit_pii("081.2345.6789 or 081-2345-6789 works") is True

    def test_iso_date_not_flagged(self):
        """Negative test (mandated): a date must not be eaten as a
        phone/NIK just because it has enough digits and separators."""
        assert _has_spaced_digit_pii("meeting on 2026-08-15 at the office") is False

    def test_grouped_amount_not_flagged(self):
        """Negative test (mandated): a thousands-grouped currency amount
        must not be eaten either."""
        assert _has_spaced_digit_pii("total cost is 2.500.000 rupiah") is False

    def test_larger_grouped_amount_still_not_flagged(self):
        """A larger amount whose digit count alone would clear the 8-digit
        threshold (25.000.000 = 8 digits) — proves the date/amount shape
        exclusion is doing real work, not just coincidentally safe on the
        mandate's smaller example."""
        assert _has_spaced_digit_pii("budget is 25.000.000 rupiah total") is False

    def test_short_spaced_run_below_threshold_not_flagged(self):
        """Innocence: a short spaced number (e.g. a 4-digit PIN written
        with a space) has too few digits to be phone/NIK-shaped."""
        assert _has_spaced_digit_pii("room 12 34") is False

    def test_slash_separated_regulation_number_not_flagged(self):
        """R14-1 binding correction, 2026-08-15 (Kimi K3 round-14
        review): this docstring used to say "`/` is deliberately excluded
        from the separator class" — false since R8-8, which INCLUDED `/`
        in `_RESIDUAL_SPACED_DIGIT_RUN_RE`'s separator class precisely to
        close a slash-separated-NIK hole ("3171/2345/6789/0123"). The
        risk the old wording described is real, but the mitigation is NOT
        exclusion — it's two independent things downstream of the regex:
        (1) `_is_date_or_amount_shape` validates a slash-separated
        candidate against the REAL calendar via `datetime.date` before
        exempting it (so "15/08/2026" is exempt but a 16-digit run that
        merely LOOKS date-shaped is not); (2) a short legal citation like
        "PP 45/2024" never reaches the regex's own 8-character minimum
        span at all ("45/2024" is 7 characters). A maintainer who reads
        only the old comment and "simplifies away" the date-shape
        exemption as dead weight would reopen the exact slash-separated-
        NIK hole R8-8 closed — this docstring exists to prevent that."""
        assert _has_spaced_digit_pii("per PP 45/2024 dated 15/08/2026") is False

    def test_is_date_or_amount_shape_direct(self):
        """R15-1 binding correction, 2026-08-15 (Kimi K3 round-15
        review): the amount branch used to exempt on shape alone,
        context-free — `_is_date_or_amount_shape("2.500.000")` with NO
        context returned `True`. It now requires an explicit currency
        marker near the span (see `_CURRENCY_MARKER_ADJACENT_BEFORE_ALT`/
        `_AFTER_ALT` — R18-4 removed the since-dead `_CURRENCY_MARKER_RE`
        this comment used to cite; those two alternations are the live
        authorities now), so a bare,
        context-free call to the amount shapes below correctly returns
        `False` — this is not a test regression, it is the exact
        behavior change R15-1 exists to make. The date branch (a pure
        calendar check) is unaffected by the absence of context."""
        assert _is_date_or_amount_shape("2026-08-15") is True
        assert _is_date_or_amount_shape("2.500.000") is False
        assert _is_date_or_amount_shape("25.000.000") is False
        assert _is_date_or_amount_shape("0812 3456 7890") is False

    def test_amount_shape_exempted_only_with_currency_marker_in_context(self):
        """R15-1 (Kimi K3 round-15 review, HIGH): the amount exemption is
        now CONTEXT-DEPENDENT — guilt (no marker nearby, shape+ceiling
        alone are not enough) and innocence (an explicit marker within
        the short window exempts it), exercised directly against
        `_is_date_or_amount_shape` with `text=`/`span=` so the currency-
        marker path itself is pinned, independent of the outer 8-digit
        gate `_has_spaced_digit_pii` applies before ever calling this
        function."""
        # Guilt: shape matches, ceiling holds, but no marker anywhere near.
        assert _is_date_or_amount_shape("62.812.345.678", text="Call me on +62.812.345.678", span=(12, 26)) is False
        assert _is_date_or_amount_shape("123.456.789", text="123.456.789", span=(0, 11)) is False
        # Innocence: an explicit marker (from the reviewer's own list)
        # within the window exempts it — the mandate's literal examples.
        assert _is_date_or_amount_shape("1.500.000", text="Rp 1.500.000", span=(3, 12)) is True
        assert _is_date_or_amount_shape("2.500.000", text="harga 2.500.000 IDR", span=(6, 15)) is True

    def test_out_of_range_month_shaped_number_not_exempted(self):
        """Guilt (pass 1 of the LOW binding correction, still holds under
        pass 2's calendar rewrite): `"6208-15-15"` has month=15, which is
        not a real month at all — this is a NIK/phone number that merely
        LOOKS date-shaped, and must be caught by the PII scan, not
        exempted from it."""
        assert _is_date_or_amount_shape("6208-15-15") is False

    def test_calendar_impossible_day_not_exempted(self):
        """Guilt for the pass-2 refinement specifically: `"2026-02-30"`
        passes a bare numeric range check (month=2 in [1,12], day=30 in
        [1,31]) but February never has a 30th day — `datetime.date`
        rejects it, and this candidate must NOT be exempted from the PII
        scan on the strength of a shape that only looks like a date."""
        assert _is_date_or_amount_shape("2026-02-30") is False

    def test_leap_year_valid_date_still_exempted(self):
        """Innocence for the pass-2 refinement: `"2024-02-29"` IS a real
        calendar date (2024 is a leap year) and must still be recognized
        as a genuine date, not wrongly caught by an overly strict
        calendar check."""
        assert _is_date_or_amount_shape("2024-02-29") is True

    def test_non_contiguous_phone_number_without_currency_marker_flagged(self):
        """R15-1 (Kimi K3 round-15 review, HIGH), confirmed scenario: a
        phone number typed with dots (thousands-grouping style, not a
        space/dash separator) matches the amount SHAPE exactly as readily
        as a genuine IDR figure. With no currency marker anywhere in the
        text, it must now be caught by the residual PII scan — the exact
        backstop this scan exists to provide — instead of silently
        exempted on shape alone."""
        assert _has_spaced_digit_pii("Call me on +62.812.345.678") is True

    def test_bare_grouped_reference_number_without_currency_marker_flagged(self):
        """R15-1, second confirmed scenario: a bare reference/account
        number written with thousands-style grouping and NO amount
        context at all."""
        assert _has_spaced_digit_pii("123.456.789") is True

    def test_grouped_amount_with_explicit_marker_still_exempted_at_eight_digits(self):
        """Innocence at the `_has_spaced_digit_pii` level (not just the
        direct-call level above): an 8-digit grouped amount — enough
        digits to reach the amount branch at all — stays exempt when an
        explicit currency marker (`IDR`) sits next to it."""
        assert _has_spaced_digit_pii("harga 25.000.000 IDR") is False

    def test_currency_marker_substring_inside_unrelated_word_does_not_reopen_exemption(self):
        """R15-1b binding correction, 2026-08-15 (orchestrator live-gate
        on the frozen round-15 delivery): `_CURRENCY_MARKER_RE` used to be a
        bare substring match — the everyday Indonesian words "terpisah"
        ("separate") and "terpercaya" ("trustworthy") both CONTAIN "rp"
        and satisfied the marker with zero currency meaning. Proven
        exactly the orchestrator gate's confirmed scenario: "nomor terpisah:
        62.812.345.678" ("separate number: ...") had "terpisah" inside
        the 30-char window, re-opening the amount exemption and letting
        the pointed phone number survive the scan — a partial re-opening
        of the exact HIGH-severity R15-1 hole. Word-boundary anchoring
        fixes it: "terpisah" contains "rp" but is not the WORD "rp", so
        it no longer matches at all, and the phone number is flagged
        again."""
        assert _has_spaced_digit_pii("nomor terpisah: 62.812.345.678") is True

    def test_currency_marker_word_boundary_innocence_cases(self):
        """R15-1b innocence: genuine markers, including the adjacent-to-
        digits case (no space between the marker and the amount), still
        exempt — the word-boundary fix must not have collaterally broken
        any real marker match."""
        assert _is_date_or_amount_shape("1.500.000", text="Rp 1.500.000", span=(3, 12)) is True
        # Adjacent case, no space: pins the slice subtlety noted in
        # `_CURRENCY_MARKER_ADJACENT_BEFORE_RE`'s own comment (R19-4:
        # re-pointed from the since-removed `_CURRENCY_MARKER_RE`, which
        # this test file's comment still cited after R18-4 deleted it)
        # — the pre-span window ends exactly at "...Rp", and end-of-string
        # right after the word character "p" IS itself a `\b`, so no
        # special lookahead is needed for this to match.
        assert _is_date_or_amount_shape("1.500.000", text="Rp1.500.000", span=(2, 11)) is True
        # Marker AFTER the span, not before — currency markers are
        # checked on both sides (unlike the birth marker, which is
        # before-only).
        assert _is_date_or_amount_shape("2.500.000", text="harga 2.500.000 rupiah", span=(6, 15)) is True

    def test_birth_context_vetoes_date_exemption_dob_marker(self):
        """R15-3 (Kimi K3 round-15 review, MEDIUM): a date that IS a real
        calendar date is still identifying PII when it's a date OF BIRTH
        — a `DOB` marker within the short window before the span vetoes
        the exemption regardless of calendar validity."""
        assert _has_spaced_digit_pii("DOB saya 15/08/1990") is True

    def test_birth_context_vetoes_date_exemption_tanggal_lahir_marker(self):
        """R15-3, second confirmed scenario: the Indonesian phrase
        `tanggal lahir` (matched via the `lahir` substring)."""
        assert _has_spaced_digit_pii("tanggal lahir: 15-08-1990") is True

    def test_date_without_birth_context_still_exempted(self):
        """Innocence for R15-3: an ordinary meeting date with no birth
        marker anywhere nearby is completely unaffected by the veto —
        it stays exempt exactly as before this round."""
        assert _has_spaced_digit_pii("meeting 15/08/2026 confirmed") is False

    def test_birth_marker_substring_inside_kelahiran_vetoes_exemption(self):
        """R16-1 (Kimi K3 round-16 review, MEDIUM — orchestrator-mandate
        defect, ADR §15 precedent class): the R15-1b mandate anchored
        `_BIRTH_MARKER_RE` with `\\b` for "entity-not-form consistency"
        with `_CURRENCY_MARKER_RE`, without checking the opposite cost-
        model asymmetry a VETO pattern has. Proven regression: pre-R15-1b,
        the bare substring "lahir" matched inside "kelahiran" ("[date of]
        birth") and correctly vetoed the date exemption; the anchored
        `\\blahir\\b` requires "lahir" to be a WHOLE word, which it is not
        inside "kelahiran" (bounded by word characters on both sides, no
        `\\b` fires), so the veto silently stopped firing and the date
        came back exempt. Reverting to a bare substring match restores
        this guilt case."""
        assert _has_spaced_digit_pii("kelahiran saya 15/08/1990") is True

    def test_birth_marker_substring_inside_dilahirkan_vetoes_exemption(self):
        """R16-1, second confirmed scenario: "dilahirkan" ("was born")
        contains "lahir" as a substring, same regression/fix as the
        "kelahiran" case above."""
        assert _has_spaced_digit_pii("anak itu dilahirkan 15/08/1990") is True

    def test_birth_context_veto_also_applies_when_label_follows_the_date(self):
        """R16-3 (Kimi K3 round-16 review, LOW): the veto used to check
        ONLY the window BEFORE the candidate span, on the undocumented
        assumption a birth-context label always precedes the date it
        labels. Proven false: "15/08/1990 itu tanggal lahir dia"
        ("15/08/1990, that's his date of birth") puts the label AFTER the
        date — this must now be caught too."""
        assert _has_spaced_digit_pii("15/08/1990 itu tanggal lahir dia") is True

    def test_currency_marker_must_be_adjacent_not_merely_co_located_in_window(self):
        """R16-2 (Kimi K3 round-16 review, MEDIUM): the currency-marker
        check used to be a plain `.search()` across the whole
        `_CURRENCY_CONTEXT_WINDOW_CHARS`-char window — a marker belonging
        to ONE amount could exempt an unrelated span later in the same
        message. Proven with the ordinary shape of a real Bali Zero
        client message (a price and a phone number in the same
        sentence): "biaya Rp 2.500.000, hubungi 812.345.678" — "Rp" (the
        genuine, correctly word-boundary-anchored marker for the amount)
        used to still fall inside the PHONE NUMBER's own 30-char window
        and wrongly exempt it too. The marker must now be ADJACENT to the
        span it exempts, not merely present somewhere nearby."""
        assert _has_spaced_digit_pii("biaya Rp 2.500.000, hubungi 812.345.678") is True

    def test_currency_marker_adjacent_innocence_cases_still_exempted(self):
        """R16-2 innocence: every marker-adjacency shape from the mandate
        stays exempt under the new adjacency check — space-separated
        before, no-space-before, space-separated after, and light
        punctuation (`:`) before the marker (which sits before the marker
        itself, not between the marker and the span, so it does not
        affect adjacency)."""
        assert _has_spaced_digit_pii("harga Rp 2.500.000 saja") is False
        assert _has_spaced_digit_pii("totalnya Rp2.500.000 saja") is False
        assert _has_spaced_digit_pii("totalnya 2.500.000 rupiah saja") is False
        assert _has_spaced_digit_pii("biaya: Rp 2.500.000 saja") is False

    def test_currency_marker_with_period_stays_adjacent_and_exempt(self):
        """R16-2b binding correction, 2026-08-15 (Codex gate, found on the
        R16-2 adjacency implementation after round 16 (`af7763b21`) had
        already been delivered — MICRO-THAW, same pattern as R15-1b on
        §22): reusing `_CURRENCY_MARKER_RE.pattern` verbatim for the
        BEFORE-adjacency regex broke "Rp." specifically — the `.` in
        "rp\\.?" consumes a character that the trailing `\\b` then can't
        find a boundary around (period followed by space is a
        non-word-to-non-word transition, no `\\b` fires), and the
        alternative parse (stop before the `.`) leaves the leftover `.`
        unconsumed by the `[ \\t:=]*$` tail. Net effect: "Rp. 25.000.000
        dana masuk" was wrongly flagged even though "Rp."/"Rp" are both
        explicitly documented, contract-listed markers. Fixed by giving
        the BEFORE regex its own alternation where the "rp\\.?" branch
        drops its own trailing `\\b` (the `[ \\t:=]*$` tail already
        enforces the right-boundary more strictly than a bare `\\b`
        would)."""
        assert _has_spaced_digit_pii("Rp. 25.000.000 dana masuk") is False
        assert _has_spaced_digit_pii("Rp 25.000.000") is False
        assert _has_spaced_digit_pii("Rp25.000.000") is False
        assert _has_spaced_digit_pii("harga 25.000.000 rupiah") is False
        # Guilt is unaffected by R16-2b: the two-amount scenario (R16-2)
        # and the "terpisah" substring scenario (R15-1b) must both still
        # flag correctly — the leading `\b` before "rp" in the new
        # BEFORE-only alternation is unchanged, so it still guards against
        # the substring-inside-a-word class R15-1b closed.
        assert _has_spaced_digit_pii("biaya Rp 2.500.000, hubungi 812.345.678") is True
        assert _has_spaced_digit_pii("nomor terpisah: 62.812.345.678") is True

    def test_rp_removed_from_after_side_no_longer_exempts_unrelated_span(self):
        """R17-1 (Kimi K3 round-17 review, MEDIUM — supersedes the R16-2b
        "AFTER unchanged" defense, ADR §19-style honest correction): the
        AFTER regex was a PREFIX match with nothing constraining what
        followed a matched "rp" — so "rp"/"rp." occurring AFTER an
        unrelated span (not as a genuine currency marker at all) still
        exempted it. Proven: "hubungi 812.345.678 rp. palsu" and "...rp
        palsu" (Indonesian for "fake/counterfeit rp" — not a currency
        statement at all) both wrongly exempted the phone number. Fixed
        structurally: `rp` is removed from the AFTER alternation entirely
        — Indonesian currency stated after a number is always spelled
        "rupiah"/"juta"/"miliar"/"ribu"/"IDR"/"USD", never a bare "N rp"."""
        assert _has_spaced_digit_pii("hubungi 812.345.678 rp. palsu") is True
        assert _has_spaced_digit_pii("hubungi 812.345.678 rp palsu") is True
        # Innocence: the real AFTER-side markers still work.
        assert _has_spaced_digit_pii("transfer 2.500.000 rupiah ok") is False
        assert _has_spaced_digit_pii("harga 25.000.000 idr") is False

    def test_birth_marker_vocabulary_covers_birthday_and_indonesian_synonyms(self):
        """R17-2 (Kimi K3 round-17 review, MEDIUM): the birth-marker
        vocabulary was incomplete — "birthday"/"b-day" (English) and
        "ulang tahun"/"ultah" (Indonesian) contain none of the prior
        tokens. Proven: all three phrasings below came back exempt before
        this fix. Fixed by widening `_BIRTH_MARKER_RE` (a veto pattern —
        over-matching is free, per the R16-1 directional rule): "date of
        birth" replaced by the more general "birth" (a strict widening,
        since "birth" is already a substring of "date of birth"), plus
        "ulang tahun"/"ultah"/"b-day" added as new literal alternatives."""
        assert _has_spaced_digit_pii("my birthday is 15/08/1990") is True
        assert _has_spaced_digit_pii("ultah saya 15/08/1990") is True
        assert _has_spaced_digit_pii("ulang tahun 15/08/1990") is True
        # Innocence: an ordinary meeting date is unaffected by the wider
        # vocabulary.
        assert _has_spaced_digit_pii("meeting 15/08/2026 ok dikonfirmasi") is False

    def test_end_to_end_spaced_phone_dropped_by_full_pipeline(self, tmp_path: Path):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        _write_wa_txt(
            input_dir / "chat.txt",
            ["12/01/26, 09:00 - Client: reach me on 0812 3456 7890 anytime"],
        )
        stats = build_corpus(
            input_dir=input_dir,
            output_dir=tmp_path / "out",
            execute=False,
            use_ollama_ner=False,
            ollama_model="unused",
            require_role_aware=False,
        )
        assert stats["kept"] == 0
        assert stats["dropped_residual_pii"] == 1

    def test_end_to_end_date_and_amount_survive_full_pipeline(self, tmp_path: Path):
        """Innocence at the harness level: a message that only contains a
        date and an amount must be KEPT, not dropped as a false-positive
        phone/NIK."""
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        _write_wa_txt(
            input_dir / "chat.txt",
            ["12/01/26, 09:00 - Client: on 2026-08-15 the total is 2.500.000 rupiah"],
        )
        stats = build_corpus(
            input_dir=input_dir,
            output_dir=tmp_path / "out",
            execute=False,
            use_ollama_ner=False,
            ollama_model="unused",
            require_role_aware=False,
        )
        assert stats["kept"] == 1
        assert stats["dropped_residual_pii"] == 0


class TestR6_1PIIScanGaps:
    """R6-1 (Kimi K3 round-6 review): three composed gaps in the PII scan.
    (a) the grouped-amount exemption had no digit-count ceiling, so a
    16-digit NIK written with thousands-style grouping borrowed the
    amount exemption; (b) `,` was missing from the spaced-digit-run
    separator class, so a comma-only-separated NIK/phone escaped Scan A
    entirely; (c) `NIK` was absent from Scan B's id-doc-near-digits
    alternation despite this file's own G1 comment naming it as the exact
    shape being protected against."""

    def test_a_nik_shaped_grouped_number_is_not_exempted_as_an_amount(self):
        """Guilt for (a): a 16-digit NIK written with comma-thousands
        grouping must NOT pass the amount-shape exemption."""
        assert _is_date_or_amount_shape("3,171,234,567,890,123") is False

    def test_a_legitimate_large_amount_still_exempted(self):
        """Innocence for (a): a real Bali Zero PMA investment figure
        (11 digits, well under the 13-digit ceiling) must still be
        exempted.

        R15-1 binding correction, 2026-08-15 (Kimi K3 round-15 review,
        HIGH): the amount exemption is now context-dependent (see
        `_CURRENCY_MARKER_ADJACENT_BEFORE_ALT`/`_AFTER_ALT` — R19-4
        disclosed addendum: this third live-looking pointer to the
        since-removed `_CURRENCY_MARKER_RE` was found while fixing the
        two the mandate named at :207/:303, same defect class) — a bare
        context-free call no longer
        exempts on shape+ceiling alone, so this test now supplies the
        `text`/`span` context with an explicit `IDR` marker, matching
        how this figure would actually appear in a real client message."""
        assert (
            _is_date_or_amount_shape(
                "10,000,000,000",
                text="modal disetor 10,000,000,000 IDR",
                span=(14, 28),
            )
            is True
        )

    def test_b_comma_separated_nik_flagged_by_scan_a(self):
        """Guilt for (b): a NIK written with commas instead of
        spaces/dots/dashes — previously invisible to the spaced-digit-run
        regex entirely (no separator in its old character class matched a
        bare comma) — must now be caught."""
        assert _has_spaced_digit_pii("NIK saya 3171,2345,6789,0123") is True

    def test_b_comma_grouped_nik_dropped_end_to_end(self):
        """Guilt for (a)+(b) together, at the harness level: the exact
        16-digit-NIK-as-grouped-amount shape from the mandate must be
        dropped by the full pipeline, not just by the unit-level scan."""
        assert _has_residual_pii("3,171,234,567,890,123") is True

    def test_b_comma_grouped_amount_innocence_still_survives(self):
        """Innocence for (b): adding `,` to the separator class must not
        start eating ordinary comma-grouped amounts — they still hit the
        date/amount-shape exclusion inside `_has_spaced_digit_pii`.

        R15-1 binding correction, 2026-08-15 (Kimi K3 round-15 review,
        HIGH): the first two assertions stay exempt purely on the
        8-digit gate `_has_spaced_digit_pii` applies BEFORE ever calling
        `_is_date_or_amount_shape` (7 digits each, below the threshold),
        unaffected by the context-dependent amount exemption either way.
        The third assertion (11 digits) DOES reach the amount branch and
        therefore now needs an explicit currency marker in the fixture
        text — added (`IDR`) — to stay exempt under the new contract;
        the original `"harga 10,000,000,000"` (no recognized marker)
        would now correctly be flagged, which is the R15-1 fix working
        as intended, not a regression in this test."""
        assert _has_spaced_digit_pii("biaya 2,500,000") is False
        assert _has_spaced_digit_pii("2.500.000") is False
        assert _has_spaced_digit_pii("harga 10,000,000,000 IDR") is False

    def test_c_nik_near_digits_flagged_by_scan_b(self):
        """Guilt for (c): `NIK` next to a digit run must be caught by
        Scan B, the same way NPWP/KTP/passport already are."""
        findings = _independent_pii_scan("NIK saya 3171234567890123 untuk KTP baru")
        assert "id_doc_near_digits" in findings

    def test_c_kk_and_sim_deliberately_not_added(self):
        """Documents the investigated-and-rejected extension: `KK` and
        `SIM` were evaluated and found to over-match ordinary casual text
        (`KK` collides with Indonesian chat slang for "kakak"/sibling,
        and with neighborhood unit numbers like "RT 005") — verified
        empirically before deciding not to add them. This innocence test
        pins that a genuinely PII-free message naming an RT/RW unit
        number near the word "kk" is NOT flagged by Scan B."""
        findings = _independent_pii_scan("kk ini alamat RT 005 nya")
        assert "id_doc_near_digits" not in findings

    def test_innocence_clean_fixtures_unaffected_by_all_three_r6_1_fixes(self):
        clean = [
            "Ciao, quanto costa il KITAS investor?",
            "Berapa biaya untuk PT PMA?",
            "How long does the visa process take?",
        ]
        for text in clean:
            assert _has_residual_pii(text) is False
            assert _independent_pii_scan(text) == []

    def test_end_to_end_nik_shaped_grouped_number_dropped_by_full_pipeline(self, tmp_path: Path):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        _write_wa_txt(
            input_dir / "chat.txt",
            ["12/01/26, 09:00 - Client: NIK saya 3171,2345,6789,0123 untuk pengurusan"],
        )
        stats = build_corpus(
            input_dir=input_dir,
            output_dir=tmp_path / "out",
            execute=False,
            use_ollama_ner=False,
            ollama_model="unused",
            require_role_aware=False,
        )
        assert stats["kept"] == 0

    def test_end_to_end_legitimate_amounts_still_kept_by_full_pipeline(self, tmp_path: Path):
        """R15-1 binding correction, 2026-08-15 (Kimi K3 round-15 review,
        HIGH): the fixture below now names `IDR` next to the 11-digit
        figure — `10,000,000,000` reaches the amount branch (unlike
        `2,500,000`'s 7 digits, which stays below the 8-digit gate
        either way) and needs an explicit currency marker in context to
        stay exempt under the new context-dependent rule; the original
        fixture had no marker at all next to that figure."""
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        _write_wa_txt(
            input_dir / "chat.txt",
            ["12/01/26, 09:00 - Client: biaya PT PMA sekitar 2,500,000 atau modal 10,000,000,000 IDR"],
        )
        stats = build_corpus(
            input_dir=input_dir,
            output_dir=tmp_path / "out",
            execute=False,
            use_ollama_ner=False,
            ollama_model="unused",
            require_role_aware=False,
        )
        assert stats["kept"] == 1
        assert stats["dropped_residual_pii"] == 0
        assert stats["dropped_independent_scan"] == 0


class TestG2CaseInsensitiveScanB:
    """G2 (orchestrator corpus gate / Gemini diagnostic, 2026-08-15):
    `_HONORIFIC_NAME_RE`/`_ADDRESS_MARKER_RE` were case-sensitive against
    Title-Case marker literals — real WhatsApp text is overwhelmingly
    lowercase."""

    def test_lowercase_honorific_name_flagged(self):
        """R18-1 fixture correction, 2026-08-15 (Kimi K3 round-18 review,
        discovered as a byproduct of fixing R18-1, not requested by the
        mandate directly): this fixture's name used to be "siti"
        (lowercase). It passed only because `_HONORIFIC_NAME_RE`'s
        `re.IGNORECASE` compile flag was GLOBAL — it accidentally widened
        the name-arm's `[A-Z]` character class to accept lowercase too,
        not just the marker-word alternation (the G2 CORRECTION documents
        this at `_HONORIFIC_NAME_RE`'s own definition). R18-1 fixes that
        accidental widening as part of closing a real over-match hole
        (`_HONORIFIC_NAME_RE` was also matching ordinary lowercase
        sentences like "makasih pak sudah bantu", not just names) —
        which correctly requires this test's name to be genuinely
        titlecase now. Name capitalized to "Siti"; the marker word
        ("ibu") stays deliberately lowercase, since testing THAT the
        marker word is still case-insensitive (the G2 fix's actual,
        still-correct intent) is this test's whole point."""
        findings = _independent_pii_scan("please contact ibu Siti rahayu about the kitas")
        assert "honorific_name" in findings

    def test_lowercase_address_marker_flagged(self):
        findings = _independent_pii_scan("the villa is on jl. sunset road number 8")
        assert "address_marker" in findings

    def test_no_space_wa_typing_style_address_marker_flagged(self):
        """R17-3 (Kimi K3 round-17 review, LOW): the marker required
        `\\s+` immediately after it — a real WA-typing style that skips
        the space after a period ("jl.sunset road", "gang.mawar no 3")
        escaped Scan B entirely (proven: both were undetected before this
        fix). Fixed: the literal dot became its own optional suffix on
        the whole alternation and the mandatory `\\s+` became optional
        `\\s*` — a widening on a DETECTOR pattern, fail-closed and free
        under the same directional rule established at R16-1. Innocence
        for the pre-existing spaced form ("Jl. Sunset Road") is covered
        by `test_lowercase_address_marker_flagged` and
        `test_mixed_case_honorific_and_address_flagged`, both unaffected
        by this widening."""
        assert "address_marker" in _independent_pii_scan("alamat jl.sunset road 8")
        assert "address_marker" in _independent_pii_scan("gang.mawar no 3")

    def test_mixed_case_honorific_and_address_flagged(self):
        """Real WA text is rarely PERFECTLY lowercase either — a message
        typed quickly often mixes cases mid-sentence.

        R18-1 fixture correction, 2026-08-15: same class as
        `test_lowercase_honorific_name_flagged` above — "siti" corrected
        to "Siti" so the name genuinely satisfies the now-real titlecase
        requirement on `_HONORIFIC_NAME_RE`'s spaced branch; see that
        test's docstring for the full explanation."""
        findings = _independent_pii_scan("Ibu Siti tinggal di JL. sunset road")
        assert "honorific_name" in findings
        assert "address_marker" in findings

    def test_clean_messages_still_survive_under_case_insensitive_scan(self):
        """Innocence: the exact fixtures `TestInnocenceCleanMessagesSurvive`
        already pins must still clear Scan B once it's case-insensitive —
        proves the widened case-matching didn't widen WHAT counts as a
        marker, only WHICH CASE the same fixed marker words can appear
        in."""
        clean = [
            "Ciao, quanto costa il KITAS investor?",
            "Berapa biaya untuk PT PMA?",
            "How long does the visa process take?",
        ]
        for text in clean:
            findings = _independent_pii_scan(text)
            assert findings == [], f"{text!r} unexpectedly flagged: {findings}"

    def test_titlecase_bigram_deliberately_not_made_case_insensitive(self):
        """Documents the investigated-and-rejected fix: making
        `_TITLECASE_BIGRAM_RE` case-insensitive would flag ordinary
        two-word phrases with no capitalization signal at all — this test
        pins that `_independent_pii_scan` still does NOT flag a lowercase
        two-word phrase that has no honorific/address marker, proving the
        titlecase heuristic's selectivity (capitalization-as-signal) is
        still intact after the G2 fix."""
        findings = _independent_pii_scan("john smith akan datang besok pagi")
        assert "titlecase_bigram" not in findings

    def test_end_to_end_lowercase_honorific_dropped_by_full_pipeline(self, tmp_path: Path):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        _write_wa_txt(
            input_dir / "chat.txt",
            ["12/01/26, 09:00 - Client: ibu siti rahayu tinggal di jl. sunset road"],
        )
        stats = build_corpus(
            input_dir=input_dir,
            output_dir=tmp_path / "out",
            execute=False,
            use_ollama_ner=False,
            ollama_model="unused",
            require_role_aware=False,
        )
        assert stats["kept"] == 0
        assert stats["dropped_independent_scan"] == 1


class TestK3OllamaEnvMinimised:
    """K3 (Kimi K3 diagnostic, 2026-08-15): the Ollama NER subprocess used
    to receive `dict(os.environ)` — the FULL parent environment, including
    any secrets this process happens to be carrying. Now an explicit
    allowlist."""

    def test_secret_env_var_not_forwarded_to_ollama_subprocess(self, monkeypatch):
        secret_marker = "SECRET_API_KEY_MUST_NEVER_REACH_OLLAMA_SUBPROCESS"
        monkeypatch.setenv("SOME_OTHER_SERVICE_API_KEY", secret_marker)
        captured_env = {}

        def _fake_run(cmd, *, input=None, capture_output, text, timeout, check, env):
            captured_env.update(env)

            class _Result:
                returncode = 0
                stdout = "unchanged text"

            return _Result()

        import scripts.bot.build_deid_corpus as module

        monkeypatch.setattr(module.subprocess, "run", _fake_run)
        _ollama_ner_pass("some text", model="qwen3.5:9b")

        assert secret_marker not in captured_env.values(), (
            "an ambient secret env var leaked into the Ollama subprocess environment"
        )
        assert "SOME_OTHER_SERVICE_API_KEY" not in captured_env, (
            "an ambient env var not on the allowlist was forwarded verbatim"
        )

    def test_allowlisted_vars_still_forwarded(self, monkeypatch):
        """Innocence: PATH (needed to resolve the `ollama` binary) must
        still make it through — the fix is a NARROWING, not a total
        blackout that would break the subprocess call itself."""
        monkeypatch.setenv("PATH", "/usr/bin:/bin")
        captured_env = {}

        def _fake_run(cmd, *, input=None, capture_output, text, timeout, check, env):
            captured_env.update(env)

            class _Result:
                returncode = 0
                stdout = "unchanged text"

            return _Result()

        import scripts.bot.build_deid_corpus as module

        monkeypatch.setattr(module.subprocess, "run", _fake_run)
        _ollama_ner_pass("some text", model="qwen3.5:9b")

        assert captured_env.get("PATH") == "/usr/bin:/bin"

    def test_ollama_host_always_forced_regardless_of_allowlist(self, monkeypatch):
        """Innocence companion to the pre-existing loopback-enforcement
        tests — narrowing the env to an allowlist must not accidentally
        drop the OLLAMA_HOST force-set."""
        captured_env = {}

        def _fake_run(cmd, *, input=None, capture_output, text, timeout, check, env):
            captured_env.update(env)

            class _Result:
                returncode = 0
                stdout = "unchanged text"

            return _Result()

        import scripts.bot.build_deid_corpus as module

        monkeypatch.setattr(module.subprocess, "run", _fake_run)
        _ollama_ner_pass("some text", model="qwen3.5:9b")

        assert captured_env["OLLAMA_HOST"] == "http://127.0.0.1:11434"


class TestR6_4OllamaPromptViaStdin:
    """R6-4 (Kimi K3 round-6 review): the Ollama NER subprocess used to put
    the WhatsApp text straight into `["ollama", "run", model, prompt]` —
    this process's own argv, visible to any other process on the machine
    via `ps`, and subject to ARG_MAX for a long chat export. The prompt
    now travels via `subprocess.run(..., input=prompt)` instead."""

    SENTINEL = "SENTINEL_TEXT_MUST_NEVER_APPEAR_IN_ARGV_XYZ789"

    def test_prompt_text_is_not_in_the_subprocess_argv(self, monkeypatch):
        """Guilt: the sentinel text must not appear anywhere in `cmd`."""
        captured_cmd = []
        captured_input = []

        def _fake_run(cmd, *, input=None, capture_output, text, timeout, check, env):
            captured_cmd.append(list(cmd))
            captured_input.append(input)

            class _Result:
                returncode = 0
                stdout = "unchanged text"

            return _Result()

        import scripts.bot.build_deid_corpus as module

        monkeypatch.setattr(module.subprocess, "run", _fake_run)
        _ollama_ner_pass(self.SENTINEL, model="qwen3.5:9b")

        assert len(captured_cmd) == 1
        cmd = captured_cmd[0]
        assert self.SENTINEL not in cmd, f"prompt text leaked into argv: {cmd!r}"
        for arg in cmd:
            assert self.SENTINEL not in arg, f"prompt text leaked into an argv element: {arg!r}"

    def test_prompt_text_arrives_via_input_kwarg(self, monkeypatch):
        """Innocence/positive: the prompt must still actually reach Ollama
        — via `input=`, carrying the sentinel text."""
        captured_input = []

        def _fake_run(cmd, *, input=None, capture_output, text, timeout, check, env):
            captured_input.append(input)

            class _Result:
                returncode = 0
                stdout = "unchanged text"

            return _Result()

        import scripts.bot.build_deid_corpus as module

        monkeypatch.setattr(module.subprocess, "run", _fake_run)
        _ollama_ner_pass(self.SENTINEL, model="qwen3.5:9b")

        assert len(captured_input) == 1
        assert captured_input[0] is not None
        assert self.SENTINEL in captured_input[0], "prompt text must reach Ollama via input="

    def test_argv_is_exactly_ollama_run_model(self, monkeypatch):
        """The command line itself is now fixed-shape and model-only —
        proves the prompt was removed from `cmd`, not merely that the
        sentinel happens not to match."""
        captured_cmd = []

        def _fake_run(cmd, *, input=None, capture_output, text, timeout, check, env):
            captured_cmd.append(list(cmd))

            class _Result:
                returncode = 0
                stdout = "unchanged text"

            return _Result()

        import scripts.bot.build_deid_corpus as module

        monkeypatch.setattr(module.subprocess, "run", _fake_run)
        _ollama_ner_pass("any text at all", model="qwen3.5:9b")

        assert captured_cmd == [["ollama", "run", "qwen3.5:9b"]]


class TestK5PrivateOutputDirectory:
    """K5 (Kimi K3 diagnostic, 2026-08-15): `output_dir.mkdir()` had no
    explicit `mode=` — created at the process umask's (typically 0o755)
    permissions. `_mkdir_private` mirrors the file-level 0600-from-
    creation discipline at the directory level."""

    def test_freshly_created_directory_is_mode_0700(self, tmp_path: Path):
        target = tmp_path / "fresh" / "nested"
        old_umask = os.umask(0o022)
        try:
            _mkdir_private(target)
        finally:
            os.umask(old_umask)
        mode = stat.S_IMODE(target.stat().st_mode)
        assert mode == 0o700, f"expected 0o700, got {oct(mode)}"

    def test_already_existing_looser_directory_is_tightened(self, tmp_path: Path):
        """The `exist_ok=True` case: a directory that already existed with
        looser permissions must still end up at 0700, not silently kept
        loose."""
        target = tmp_path / "preexisting"
        target.mkdir(mode=0o750)
        os.chmod(target, 0o750)  # force group access without ever granting world access
        assert stat.S_IMODE(target.stat().st_mode) == 0o750

        _mkdir_private(target)

        mode = stat.S_IMODE(target.stat().st_mode)
        assert mode == 0o700, f"expected tightened to 0o700, got {oct(mode)}"

    def test_build_corpus_output_directory_is_mode_0700(self, tmp_path: Path):
        """End-to-end: the real corpus output directory `build_corpus`
        creates via `--execute` ends up 0700, not just the standalone
        helper in isolation."""
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        _write_wa_txt(
            input_dir / "chat.txt",
            ["12/01/26, 09:00 - Client: Ciao, quanto costa il KITAS investor?"],
        )
        out_dir = tmp_path / "out"
        old_umask = os.umask(0o022)
        try:
            stats = build_corpus(
                input_dir=input_dir,
                output_dir=out_dir,
                execute=True,
                use_ollama_ner=False,
                ollama_model="unused",
                require_role_aware=False,
            )
        finally:
            os.umask(old_umask)
        assert stats["kept"] >= 1
        mode = stat.S_IMODE(out_dir.stat().st_mode)
        assert mode == 0o700, f"expected 0o700, got {oct(mode)}"


class TestR9_8MkdirPrivateRefusesSymlinkLeaf:
    """R9-8 (MICRO, Kimi K3 round-9 review): the directory-component twin
    of R8-13's leaf-file symlink hole (`wa_blind_bench.py`'s
    `_open_private`). `Path.mkdir(exist_ok=True)` silently accepts a
    pre-planted symlink whose target is a directory, and `os.chmod`
    follows it to the target by default — `_mkdir_private` must refuse
    rather than chmod through the symlink."""

    def test_guilt_symlink_leaf_is_refused(self, tmp_path: Path):
        real_target = tmp_path / "real-dir"
        real_target.mkdir(mode=0o750)
        os.chmod(real_target, 0o750)

        symlink_path = tmp_path / "out"
        symlink_path.symlink_to(real_target)

        with pytest.raises(OSError):
            _mkdir_private(symlink_path)

        assert stat.S_IMODE(real_target.stat().st_mode) == 0o750, (
            "a symlink target's permissions must never be tightened by a call that refuses it"
        )

    def test_innocence_plain_directory_still_gets_0700(self, tmp_path: Path):
        target = tmp_path / "plain-dir"
        _mkdir_private(target)
        assert not target.is_symlink()
        mode = stat.S_IMODE(target.stat().st_mode)
        assert mode == 0o700, f"expected 0o700, got {oct(mode)}"


class TestInnocenceCleanMessagesSurvive:
    """A benign, PII-free WA-style message must NOT be dropped — otherwise
    the fail-closed posture degenerates into 'drop everything', which
    would silently defeat the harness's purpose."""

    def test_clean_short_messages_are_kept(self, tmp_path: Path):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        _write_wa_txt(
            input_dir / "chat.txt",
            [
                "12/01/26, 09:00 - Client: Ciao, quanto costa il KITAS investor?",
                "12/01/26, 09:01 - Client: Berapa biaya untuk PT PMA?",
                "12/01/26, 09:02 - Client: How long does the visa process take?",
            ],
        )
        stats = build_corpus(
            input_dir=input_dir,
            output_dir=tmp_path / "out",
            execute=False,
            use_ollama_ner=False,
            ollama_model="unused",
            require_role_aware=False,
        )
        assert stats["kept"] == 3
        assert stats["dropped_residual_pii"] == 0
        assert stats["dropped_independent_scan"] == 0


class TestWAExportLeftToRightMarkPrefix:
    """`_WA_LINE_RE`'s leading `(?:‎)?` group exists because WhatsApp's
    own `.txt` export prefixes each timestamped line with U+200E (the
    LEFT-TO-RIGHT MARK) — not an encoding artifact to strip. Every other
    test in this file constructs WA lines WITHOUT the mark (innocence is
    already covered by e.g. `TestInnocenceCleanMessagesSurvive`), so a
    regression that stripped the literal from the regex would pass every
    existing suite silently. This is the guilt side: a mark-prefixed line,
    the actual shape WhatsApp emits, must still parse."""

    def test_left_to_right_mark_prefixed_line_still_parses(self, tmp_path: Path):
        export_file = tmp_path / "chat.txt"
        export_file.write_text(
            "‎15/08/26, 10:30 - Sender: pesan biasa\n",
            encoding="utf-8",
        )
        records = list(_iter_txt_records(export_file))
        assert len(records) == 1
        assert records[0].text == "pesan biasa"


class TestFingerprintAbsence:
    """Orchestrator corpus gate: no stable pseudonymous fingerprint
    derived from sender identity or source path may appear in output."""

    def test_fixture_ids_are_pure_sequence_no_sender_or_path_derivation(self, tmp_path: Path):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        secret_sender = "AntonelloSecretSender"
        _write_wa_txt(
            input_dir / f"{secret_sender}-export.txt",
            [
                f"12/01/26, 09:00 - {secret_sender}: Ciao, quanto costa il KITAS?",
                f"12/01/26, 09:01 - {secret_sender}: Grazie mille per la risposta",
            ],
        )
        out_dir = tmp_path / "out"
        stats = build_corpus(
            input_dir=input_dir,
            output_dir=out_dir,
            execute=True,
            use_ollama_ner=False,
            ollama_model="unused",
            require_role_aware=False,
        )
        assert stats["kept"] >= 1

        all_output_text = ""
        for jsonl_file in out_dir.glob("*.local.jsonl"):
            all_output_text += jsonl_file.read_text(encoding="utf-8")

        assert secret_sender not in all_output_text, (
            "sender identity leaked into fixture output — data minimization violated"
        )
        assert str(input_dir) not in all_output_text, "source path leaked into fixture output"

        rows = [
            json.loads(line)
            for jsonl_file in out_dir.glob("*.local.jsonl")
            for line in jsonl_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert rows, "expected at least one written fixture row"
        for row in rows:
            assert set(row.keys()) == {"id", "language", "text"}
            assert row["id"].startswith("fixture-")
            # Pure sequence number, zero-padded — not a hash (hex digest
            # would contain a-f letters beyond the "fixture-" prefix).
            suffix = row["id"].removeprefix("fixture-")
            assert suffix.isdigit()

    def test_raw_record_has_no_sender_field_at_all(self):
        """Structural guard: role-aware grouping may retain canonical role
        and a local-only conversation ID, but never the sender field."""
        fields = set(RawRecord.__dataclass_fields__)
        assert fields == {"text", "source_file", "role", "conversation_id"}
        assert "sender" not in fields


class TestOutputPermissions:
    def test_written_fixture_files_are_mode_0600(self, tmp_path: Path):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        _write_wa_txt(
            input_dir / "chat.txt",
            ["12/01/26, 09:00 - Client: Ciao, quanto costa il KITAS investor?"],
        )
        out_dir = tmp_path / "out"
        # Force a permissive umask so a passing test proves the explicit
        # chmod, not an accommodating process umask.
        old_umask = os.umask(0o022)
        try:
            stats = build_corpus(
                input_dir=input_dir,
                output_dir=out_dir,
                execute=True,
                use_ollama_ner=False,
                ollama_model="unused",
                require_role_aware=False,
            )
        finally:
            os.umask(old_umask)
        assert stats["kept"] >= 1

        written = list(out_dir.glob("*.local.jsonl"))
        assert written, "expected at least one output file"
        for f in written:
            mode = stat.S_IMODE(f.stat().st_mode)
            assert mode == 0o600, f"{f} has mode {oct(mode)}, expected 0o600"


class TestWriteJsonlPrivateFchmod:
    """MEDIUM binding correction, 2026-08-15 (Kimi K3, live-gate round 5,
    two passes): `os.open(..., mode=0o600)` only sets permissions when the
    file is actually CREATED — a PRE-EXISTING looser file kept its old
    permissions. `_write_jsonl_private` now `os.fchmod`s unconditionally;
    the orchestrator's pass-2 refinement additionally required that a
    FAILED fchmod not destroy the pre-existing file's content (the first
    fix opened with `O_TRUNC` up front, zeroing the file before the
    fchmod check could even run)."""

    def test_preexisting_loose_file_is_tightened_to_0600(self, tmp_path: Path):
        target = tmp_path / "preexisting.jsonl"
        target.write_text('{"id": "old-1", "language": "en", "text": "old"}\n', encoding="utf-8")
        os.chmod(target, 0o640)
        assert stat.S_IMODE(target.stat().st_mode) == 0o640

        _write_jsonl_private(target, [{"id": "new-1", "language": "en", "text": "new"}])

        mode = stat.S_IMODE(target.stat().st_mode)
        assert mode == 0o600, f"expected tightened to 0o600, got {oct(mode)}"

    def test_fchmod_failure_leaves_original_content_untouched_and_fd_closed(
        self,
        tmp_path: Path,
        monkeypatch,
    ):
        """Guilt for the pass-2 refinement specifically: a failed
        `os.fchmod` must not have already truncated the file. Spies on
        `os.close` (rather than asserting on an internal implementation
        detail) to confirm the opened fd was actually closed on the
        failure path — no fd leak — and reads the file back to confirm
        its ORIGINAL bytes, not just "no new bytes appended"."""
        target = tmp_path / "existing.jsonl"
        original_content = '{"id": "orig-1", "language": "en", "text": "keep me byte-identical"}\n'
        target.write_text(original_content, encoding="utf-8")
        os.chmod(target, 0o640)

        closed_fds: list[int] = []
        real_close = os.close

        def _spy_close(fd: int) -> None:
            closed_fds.append(fd)
            real_close(fd)

        def _raise_fchmod(fd: int, mode: int) -> None:
            raise OSError("simulated fchmod failure")

        monkeypatch.setattr(os, "fchmod", _raise_fchmod)
        monkeypatch.setattr(os, "close", _spy_close)

        with pytest.raises(OSError):
            _write_jsonl_private(target, [{"id": "new-1", "language": "en", "text": "should never land"}])

        assert len(closed_fds) == 1, "the fd opened before the failed fchmod must be closed exactly once"
        assert target.read_text(encoding="utf-8") == original_content, (
            "pre-existing content must survive a failed fchmod completely untouched — not just 'no new content added'"
        )

    def test_r11_1_ftruncate_failure_closes_fd_exactly_once_and_propagates(
        self,
        tmp_path: Path,
        monkeypatch,
    ):
        """R11-1 (Kimi K3 round-11 review): R10-4's fix moved `os.ftruncate`/
        `os.lseek` inside the `os.fchmod` guard, but the ADR claimed "no new
        branch to pin" while the fd-closed-on-truncate-failure BEHAVIOR is
        genuinely new — the existing `os.fchmod`-failure test above never
        reaches the `os.ftruncate` call at all (it raises first). This test
        exercises the branch R10-4 actually added: `os.ftruncate` raising.

        R12-5 binding correction, 2026-08-15 (Kimi K3 round-12 review):
        this test asserted fd-closed-exactly-once but, unlike its sibling
        `os.fchmod`-failure test above, never asserted that the
        pre-existing content actually survived the failure untouched —
        the exact guarantee this function's docstring claims for this
        branch. Added below, mirroring the sibling assertion."""
        target = tmp_path / "existing-ftruncate.jsonl"
        original_content = '{"id": "orig-1", "language": "en", "text": "keep me byte-identical"}\n'
        target.write_text(original_content, encoding="utf-8")
        os.chmod(target, 0o640)

        closed_fds: list[int] = []
        real_close = os.close

        def _spy_close(fd: int) -> None:
            closed_fds.append(fd)
            real_close(fd)

        def _raise_ftruncate(fd: int, length: int) -> None:
            raise OSError("simulated ftruncate failure")

        monkeypatch.setattr(os, "ftruncate", _raise_ftruncate)
        monkeypatch.setattr(os, "close", _spy_close)

        with pytest.raises(OSError):
            _write_jsonl_private(target, [{"id": "new-1", "language": "en", "text": "should never land"}])

        assert len(closed_fds) == 1, "the fd must be closed exactly once when os.ftruncate fails"
        assert target.read_text(encoding="utf-8") == original_content, (
            "pre-existing content must survive a failed ftruncate completely untouched"
        )

    # R12-4 (Kimi K3 round-12 review): the sibling test that pinned
    # `os.fdopen` failing INSIDE the fchmod/ftruncate/lseek guard
    # (`test_r11_2_fdopen_failure_closes_fd_exactly_once_and_propagates`)
    # is DELETED here — it pinned exactly the R11-2 behavior round-12
    # reverts (see `_write_jsonl_private`'s docstring for the CPython
    # double-close/fd-recycling hazard that made the wrap unsafe).
    # `os.fdopen` is deliberately unguarded again; there is no
    # close-on-exception branch left to pin for it.

    def test_happy_path_replaces_longer_preexisting_content_with_no_residual_tail(self, tmp_path: Path):
        """Guilt for the deferred-truncation mechanics specifically (not
        just the fail-closed path): writing SHORTER new content over a
        LONGER pre-existing file must not leave a residual tail of old
        bytes — this would fail if `os.ftruncate(fd, 0)` were dropped
        while keeping the rest of the fix."""
        target = tmp_path / "shrinking.jsonl"
        long_original = "\n".join(f'{{"id": "old-{i}", "language": "en", "text": "padding {i}"}}' for i in range(20))
        target.write_text(long_original + "\n", encoding="utf-8")
        assert len(target.read_text(encoding="utf-8")) > 100

        _write_jsonl_private(target, [{"id": "short", "language": "en", "text": "x"}])

        final_content = target.read_text(encoding="utf-8")
        assert final_content == '{"id": "short", "language": "en", "text": "x"}\n'
        assert "old-" not in final_content, "no residual tail from the longer pre-existing content"


class TestLocalhostEnforcement:
    """Orchestrator corpus gate: `_ollama_ner_pass` must FORCE loopback,
    never trust an ambient OLLAMA_HOST."""

    def test_ollama_host_forced_to_loopback_even_with_malicious_ambient_value(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_HOST", "http://evil.example.com:9999")
        captured_env = {}

        def _fake_run(cmd, *, input=None, capture_output, text, timeout, check, env):
            captured_env.update(env)

            class _Result:
                returncode = 0
                stdout = "unchanged text"

            return _Result()

        import scripts.bot.build_deid_corpus as module

        monkeypatch.setattr(module.subprocess, "run", _fake_run)
        result = _ollama_ner_pass("some text", model="qwen3.5:9b")

        assert captured_env["OLLAMA_HOST"] == "http://127.0.0.1:11434", (
            "ambient OLLAMA_HOST must be overridden, never trusted — this is exactly "
            "the vector the orchestrator flagged: 'ollama CLI honors OLLAMA_HOST'"
        )
        assert result == "unchanged text"

    def test_ollama_host_forced_to_loopback_when_ambient_unset(self, monkeypatch):
        monkeypatch.delenv("OLLAMA_HOST", raising=False)
        captured_env = {}

        def _fake_run(cmd, *, input=None, capture_output, text, timeout, check, env):
            captured_env.update(env)

            class _Result:
                returncode = 0
                stdout = "unchanged text"

            return _Result()

        import scripts.bot.build_deid_corpus as module

        monkeypatch.setattr(module.subprocess, "run", _fake_run)
        _ollama_ner_pass("some text", model="qwen3.5:9b")

        assert captured_env["OLLAMA_HOST"] == "http://127.0.0.1:11434"

    def test_ollama_failure_is_best_effort_never_raises(self, monkeypatch):
        import scripts.bot.build_deid_corpus as module

        def _raise(*args, **kwargs):
            raise FileNotFoundError("ollama not installed")

        monkeypatch.setattr(module.subprocess, "run", _raise)
        result = _ollama_ner_pass("some text unchanged", model="qwen3.5:9b")
        assert result == "some text unchanged"


class TestIndependentScanFailsClosed:
    def test_exception_in_independent_scan_drops_record_not_keeps_it(self, tmp_path, monkeypatch):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        _write_wa_txt(
            input_dir / "chat.txt",
            ["12/01/26, 09:00 - Client: this text would normally pass both scans clean"],
        )

        import scripts.bot.build_deid_corpus as module

        def _explode(text: str) -> list[str]:
            raise RuntimeError("simulated scan crash")

        monkeypatch.setattr(module, "_independent_pii_scan", _explode)

        stats = build_corpus(
            input_dir=input_dir,
            output_dir=tmp_path / "out",
            execute=False,
            use_ollama_ner=False,
            ollama_model="unused",
            require_role_aware=False,
        )
        assert stats["kept"] == 0
        assert stats["independent_scan_errors"] == 1


class TestLogsNeverLeakExceptionText:
    """P1-privacy (orchestrator corpus gate, 2026-08-15, second veto):
    every exception logged in this file must carry the exception's TYPE
    only, never `str(e)` — a `RedactionError`, an independent-scan crash,
    or a `subprocess.TimeoutExpired` can all embed a slice of the actual
    message text. `subprocess.TimeoutExpired` is the sharpest case: its
    `__str__` includes the full `cmd` list it was constructed from, and
    `_ollama_ner_pass` builds that list as `["ollama", "run", model,
    prompt]` where `prompt` embeds the WhatsApp text verbatim — logging
    that exception's string would put the text straight into the log file
    this script writes to, on the SAME failure path a prior draft treated
    as 'best-effort, so it's fine to log'.

    Each test below plants a sentinel string in the input and asserts it
    never reaches any `caplog`-captured record for that failure path —
    this is a class-audit test, one per log site the orchestrator named,
    not a single spot-check."""

    SENTINEL = "SENTINEL_PII_SECRET_MUST_NEVER_APPEAR_IN_LOGS_XYZ123"

    def test_ollama_ner_timeout_never_logs_the_prompt_text(self, monkeypatch, caplog):
        import scripts.bot.build_deid_corpus as module

        def _raise_timeout(cmd, *, input=None, capture_output, text, timeout, check, env):
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)

        monkeypatch.setattr(module.subprocess, "run", _raise_timeout)
        text_with_sentinel = f"visa question, {self.SENTINEL} is my passport number"

        with caplog.at_level(logging.WARNING):
            result = module._ollama_ner_pass(text_with_sentinel, model="qwen3.5:9b")

        assert result == text_with_sentinel, "best-effort failure must return the input unchanged"
        for record in caplog.records:
            assert self.SENTINEL not in record.getMessage(), (
                f"sentinel leaked into a log record: {record.getMessage()!r}"
            )

    def test_redaction_failure_never_logs_input_text(self, tmp_path, monkeypatch, caplog):
        import scripts.bot.build_deid_corpus as module
        from scripts._redact_pii import RedactionError

        input_dir = tmp_path / "in"
        input_dir.mkdir()
        _write_wa_txt(input_dir / "chat.txt", [f"12/01/26, 09:00 - Client: {self.SENTINEL} needs a KITAS"])

        class _Gate:
            min_remaining_chars = 3

        class _Config:
            gate = _Gate()

        class _ExplodingRedactor:
            config = _Config()

            def redact(self, text: str) -> str:
                # Mirrors how scripts/_redact_pii.py's own RedactionError
                # messages can embed a slice of the text a nested rule was
                # applied to — this is exactly the shape that made the
                # module-under-test's original `%s`, e` logging unsafe.
                raise RedactionError(f"simulated failure while processing: {text}")

        monkeypatch.setattr(module.Redactor, "load_default", staticmethod(lambda: _ExplodingRedactor()))

        with caplog.at_level(logging.DEBUG):
            stats = module.build_corpus(
                input_dir=input_dir,
                output_dir=tmp_path / "out",
                execute=False,
                use_ollama_ner=False,
                ollama_model="unused",
                require_role_aware=False,
            )

        assert stats["redaction_failed"] == 1
        for record in caplog.records:
            assert self.SENTINEL not in record.getMessage(), (
                f"sentinel leaked into a log record: {record.getMessage()!r}"
            )

    def test_independent_scan_crash_never_logs_input_text(self, tmp_path, monkeypatch, caplog):
        import scripts.bot.build_deid_corpus as module

        input_dir = tmp_path / "in"
        input_dir.mkdir()
        _write_wa_txt(
            input_dir / "chat.txt",
            [f"12/01/26, 09:00 - Client: {self.SENTINEL} otherwise clean message"],
        )

        def _explode(text: str) -> list[str]:
            raise RuntimeError(f"scan crashed while inspecting: {text}")

        monkeypatch.setattr(module, "_independent_pii_scan", _explode)

        with caplog.at_level(logging.ERROR):
            stats = module.build_corpus(
                input_dir=input_dir,
                output_dir=tmp_path / "out",
                execute=False,
                use_ollama_ner=False,
                ollama_model="unused",
                require_role_aware=False,
            )

        assert stats["independent_scan_errors"] == 1
        for record in caplog.records:
            assert self.SENTINEL not in record.getMessage(), (
                f"sentinel leaked into a log record: {record.getMessage()!r}"
            )


class TestR6_3NoExportFilenameInLogs:
    """R6-3 (Kimi K3 round-6 review): a real WhatsApp export filename is
    `WhatsApp Chat with <contact name>.txt`-shaped — logging the full
    path/filename of an export file is exactly the class of leak this
    whole script exists to prevent, and it was happening at every log
    site in this file that touched a `Path`. Class-audit: one test per
    log site named in the mandate, not a single spot-check."""

    def test_unparseable_jsonl_line_logs_no_filename(self, tmp_path: Path, caplog):
        import scripts.bot.build_deid_corpus as module

        contact_name = "AntonelloSecretContact"
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        bad_file = input_dir / f"WhatsApp Chat with {contact_name}.jsonl"
        bad_file.write_text("not valid json at all\n", encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            list(module._load_records(input_dir))

        assert any("unparseable JSON" in r.getMessage() for r in caplog.records)
        for record in caplog.records:
            msg = record.getMessage()
            assert contact_name not in msg, f"contact name leaked into log: {msg!r}"
            assert str(bad_file) not in msg, f"full export path leaked into log: {msg!r}"
        # The opaque per-file ordinal must still be present — the fix is a
        # SUBSTITUTION (index instead of name), not a total blackout.
        assert any("file #1" in r.getMessage() for r in caplog.records)

    def test_non_dict_jsonl_line_logs_no_filename(self, tmp_path: Path, caplog):
        import scripts.bot.build_deid_corpus as module

        contact_name = "AnotherSecretContact"
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        bad_file = input_dir / f"WhatsApp Chat with {contact_name}.jsonl"
        bad_file.write_text("[1, 2, 3]\n", encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            list(module._load_records(input_dir))

        assert any("not an object" in r.getMessage() for r in caplog.records)
        for record in caplog.records:
            msg = record.getMessage()
            assert contact_name not in msg, f"contact name leaked into log: {msg!r}"
            assert str(bad_file) not in msg, f"full export path leaked into log: {msg!r}"

    def test_no_files_found_warning_does_not_log_the_input_dir_value(self, tmp_path: Path, caplog):
        import scripts.bot.build_deid_corpus as module

        contact_name = "YetAnotherSecretContact"
        input_dir = tmp_path / f"WhatsApp Chat with {contact_name}"
        input_dir.mkdir()

        with caplog.at_level(logging.WARNING):
            list(module._load_records(input_dir))

        assert any("No .txt or .jsonl" in r.getMessage() for r in caplog.records)
        for record in caplog.records:
            msg = record.getMessage()
            assert contact_name not in msg, f"input-dir name leaked into log: {msg!r}"
            assert str(input_dir) not in msg, f"full input-dir path leaked into log: {msg!r}"

    def test_input_dir_missing_error_does_not_log_the_path(self, tmp_path: Path, monkeypatch, caplog):
        import scripts.bot.build_deid_corpus as module

        contact_name = "MissingDirSecretContact"
        missing_dir = tmp_path / f"WhatsApp Chat with {contact_name}"

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "build_deid_corpus.py",
                "--input-dir",
                str(missing_dir),
                "--output-dir",
                str(tmp_path / "out"),
            ],
        )
        with caplog.at_level(logging.ERROR):
            rc = module.main()

        assert rc == 1
        for record in caplog.records:
            msg = record.getMessage()
            assert contact_name not in msg, f"input-dir name leaked into log: {msg!r}"
            assert str(missing_dir) not in msg, f"full input-dir path leaked into log: {msg!r}"

    def test_end_to_end_export_filename_never_reaches_any_log_record(self, tmp_path: Path, caplog):
        """Broadest form of the mandate's own test spec: run a mixed-shape
        input (one clean record, one malformed JSONL line) through the
        FULL `build_corpus` pipeline with a contact-named export filename
        and assert the name is absent from every captured log record,
        across every level."""
        import scripts.bot.build_deid_corpus as module

        contact_name = "FullPipelineSecretContact"
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        export_file = input_dir / f"WhatsApp Chat with {contact_name}.txt"
        _write_wa_txt(
            export_file,
            ["12/01/26, 09:00 - Client: Ciao, quanto costa il KITAS investor?"],
        )
        bad_jsonl = input_dir / f"WhatsApp Chat with {contact_name} (2).jsonl"
        bad_jsonl.write_text("not json\n", encoding="utf-8")

        with caplog.at_level(logging.DEBUG):
            stats = module.build_corpus(
                input_dir=input_dir,
                output_dir=tmp_path / "out",
                execute=False,
                use_ollama_ner=False,
                ollama_model="unused",
                require_role_aware=False,
            )

        assert stats["kept"] == 1
        for record in caplog.records:
            msg = record.getMessage()
            assert contact_name not in msg, f"export filename leaked into log: {msg!r}"
            assert str(export_file) not in msg
            assert str(bad_jsonl) not in msg


class TestR6_7NonDictJsonlLineDoesNotCrash:
    """R6-7 (Kimi K3 round-6 review): a syntactically valid JSONL line
    whose top-level value is not an object — `[1, 2]`, `"a string"`,
    `42`, `null` — used to reach `obj.get("text")` and raise a raw
    `AttributeError`/`TypeError`, contradicting this module's own
    docstring promise ("counted and skipped, never guessed at")."""

    def test_list_valued_jsonl_line_does_not_raise(self, tmp_path: Path):
        import scripts.bot.build_deid_corpus as module

        input_dir = tmp_path / "in"
        input_dir.mkdir()
        (input_dir / "export.jsonl").write_text(
            '[1, 2, 3]\n{"sender": "Client", "text": "Berapa biaya untuk PT PMA?"}\n',
            encoding="utf-8",
        )
        records = list(module._load_records(input_dir))
        assert [r.text for r in records] == ["Berapa biaya untuk PT PMA?"]

    def test_string_valued_jsonl_line_does_not_raise(self, tmp_path: Path):
        import scripts.bot.build_deid_corpus as module

        input_dir = tmp_path / "in"
        input_dir.mkdir()
        (input_dir / "export.jsonl").write_text(
            '"just a bare string"\n{"sender": "Client", "text": "How long does the visa process take?"}\n',
            encoding="utf-8",
        )
        records = list(module._load_records(input_dir))
        assert [r.text for r in records] == ["How long does the visa process take?"]

    def test_number_and_null_valued_jsonl_lines_do_not_raise(self, tmp_path: Path):
        import scripts.bot.build_deid_corpus as module

        input_dir = tmp_path / "in"
        input_dir.mkdir()
        (input_dir / "export.jsonl").write_text("42\nnull\n", encoding="utf-8")
        records = list(module._load_records(input_dir))
        assert records == []

    def test_innocence_normal_dict_line_still_yielded(self, tmp_path: Path):
        """Innocence: the guard must not reject a genuinely well-formed
        record dict."""
        import scripts.bot.build_deid_corpus as module

        input_dir = tmp_path / "in"
        input_dir.mkdir()
        (input_dir / "export.jsonl").write_text(
            '{"sender": "Client", "text": "Ciao, quanto costa il KITAS investor?"}\n',
            encoding="utf-8",
        )
        records = list(module._load_records(input_dir))
        assert len(records) == 1
        assert records[0].text == "Ciao, quanto costa il KITAS investor?"

    def test_end_to_end_non_dict_line_dropped_not_fatal(self, tmp_path: Path):
        """Full pipeline: a non-dict line mixed in with a clean record
        must not crash `build_corpus`, and the clean record must still
        be kept."""
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        (input_dir / "export.jsonl").write_text(
            '[1, 2]\n{"sender": "Client", "text": "Berapa biaya untuk PT PMA?"}\n',
            encoding="utf-8",
        )
        stats = build_corpus(
            input_dir=input_dir,
            output_dir=tmp_path / "out",
            execute=False,
            use_ollama_ner=False,
            ollama_model="unused",
            require_role_aware=False,
        )
        assert stats["kept"] == 1
        assert stats["read"] == 1


class TestNoKeyAndEmptyCorpusState:
    """CORPUS ELIGIBILITY: main() must exit non-zero when --execute
    produced zero fixtures — 'no-key state' analogue for this script is
    'no usable input', which must never present as a quiet success."""

    def test_main_returns_nonzero_when_execute_and_zero_input_files(self, tmp_path, monkeypatch):
        import scripts.bot.build_deid_corpus as module

        empty_input = tmp_path / "empty_in"
        empty_input.mkdir()
        out_dir = tmp_path / "out"

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "build_deid_corpus.py",
                "--input-dir",
                str(empty_input),
                "--output-dir",
                str(out_dir),
                "--execute",
            ],
        )
        rc = module.main()
        assert rc == 1, "an empty corpus with --execute must exit non-zero (esiste≠armato)"

    def test_main_returns_nonzero_when_execute_and_all_records_dropped(self, tmp_path, monkeypatch):
        import scripts.bot.build_deid_corpus as module

        input_dir = tmp_path / "in"
        input_dir.mkdir()
        # Titlecase-bigram shape: something the primary Redactor has no
        # rule for at all (it's not a phone/email/NPWP/etc. pattern), so
        # this is guaranteed to reach Scan B and be dropped there — unlike
        # a phone/email, which the Redactor itself neutralizes and KEEPS.
        _write_wa_txt(
            input_dir / "chat.txt",
            ["12/01/26, 09:00 - Client: John Smith akan datang besok pagi"],
        )
        out_dir = tmp_path / "out"

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "build_deid_corpus.py",
                "--input-dir",
                str(input_dir),
                "--output-dir",
                str(out_dir),
                "--execute",
            ],
        )
        rc = module.main()
        assert rc == 1

    def test_main_returns_zero_on_dry_run_even_with_zero_input(self, tmp_path, monkeypatch):
        """A dry run (no --execute) reports and exits 0 regardless — the
        eligibility gate is specifically about --execute producing an
        empty ARMED corpus, not about dry-run reporting."""
        import scripts.bot.build_deid_corpus as module

        empty_input = tmp_path / "empty_in"
        empty_input.mkdir()
        out_dir = tmp_path / "out"

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "build_deid_corpus.py",
                "--input-dir",
                str(empty_input),
                "--output-dir",
                str(out_dir),
            ],
        )
        rc = module.main()
        assert rc == 0

    def test_main_returns_1_when_input_dir_missing(self, tmp_path, monkeypatch):
        import scripts.bot.build_deid_corpus as module

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "build_deid_corpus.py",
                "--input-dir",
                str(tmp_path / "does-not-exist"),
                "--output-dir",
                str(tmp_path / "out"),
            ],
        )
        rc = module.main()
        assert rc == 1


class TestR7_5InvalidUtf8InJsonlDoesNotCrashTheBuild:
    """R7-5 (Kimi K3 round-7 review): `_iter_jsonl_records` opened its
    input WITHOUT `errors="replace"` while its `.txt` sibling
    `_iter_txt_records` already has it — a single non-UTF-8 byte in a
    `.jsonl` input file raised `UnicodeDecodeError` straight out of the
    file iterator (not `json.JSONDecodeError`), which the per-line
    try/except cannot catch, killing the whole build over one bad byte in
    one file."""

    def test_invalid_utf8_byte_in_jsonl_does_not_crash_load_records(self, tmp_path: Path):
        import scripts.bot.build_deid_corpus as module

        input_dir = tmp_path / "in"
        input_dir.mkdir()
        bad_file = input_dir / "export.jsonl"
        good_line = json.dumps({"sender": "Client", "text": "Berapa biaya untuk PT PMA?"}).encode("utf-8")
        # 0xFF is not valid UTF-8 in any position — guaranteed to trip a
        # strict `encoding="utf-8"` open with no errors= handling.
        bad_file.write_bytes(b"\xff\xfe not valid utf-8 at all\n" + good_line + b"\n")

        # Must not raise UnicodeDecodeError.
        records = list(module._load_records(input_dir))
        assert [r.text for r in records] == ["Berapa biaya untuk PT PMA?"]

    def test_end_to_end_invalid_utf8_byte_does_not_crash_build_corpus(self, tmp_path: Path):
        """Full pipeline: the mangled first line (now containing U+FFFD
        replacement characters) becomes invalid JSON and is counted as
        unparseable, same fail-soft posture as every other malformed-input
        case — the clean second record still comes through."""
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        bad_file = input_dir / "export.jsonl"
        good_line = json.dumps({"sender": "Client", "text": "How long does the visa process take?"}).encode(
            "utf-8",
        )
        bad_file.write_bytes(b"\xff\xfe garbage\n" + good_line + b"\n")

        stats = build_corpus(
            input_dir=input_dir,
            output_dir=tmp_path / "out",
            execute=False,
            use_ollama_ner=False,
            ollama_model="unused",
            require_role_aware=False,
        )
        assert stats["kept"] == 1
        assert stats["read"] == 1


class TestR7_4OutputDirPathClassCoversTheOutputSide:
    """R7-4 (Kimi K3 round-7 review): the R6-3 discipline ("never log an
    operator-chosen path verbatim — a directory can be named after what it
    contains") applied only to `--input-dir` sites; `--output-dir` sites
    (this file's "Wrote %d fixtures -> %s" line) still leaked the
    operator-chosen path. Same end-to-end shape as
    `test_end_to_end_export_filename_never_reaches_any_log_record` above,
    but planting the contact name in the OUTPUT directory instead of the
    input filename."""

    def test_end_to_end_output_dir_contact_name_never_reaches_any_log_record(self, tmp_path: Path, caplog):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        _write_wa_txt(
            input_dir / "export.txt",
            ["12/01/26, 09:00 - Client: Ciao, quanto costa il KITAS investor?"],
        )
        contact_name = "OutputDirSecretContact"
        output_dir = tmp_path / f"WhatsApp Chat with {contact_name} bench-runs"

        with caplog.at_level(logging.DEBUG):
            stats = build_corpus(
                input_dir=input_dir,
                output_dir=output_dir,
                execute=True,
                use_ollama_ner=False,
                ollama_model="unused",
                require_role_aware=False,
            )

        assert stats["kept"] == 1
        for record in caplog.records:
            msg = record.getMessage()
            assert contact_name not in msg, f"output-dir name leaked into log: {msg!r}"
            assert str(output_dir) not in msg, f"full output-dir path leaked into log: {msg!r}"


class TestR8_5IdDocNearDigitsCrossesNewlines:
    """R8-5 (Kimi K3 round-8 review): `_ID_DOC_NEAR_DIGITS_RE` had no
    `re.DOTALL`, so its `.{0,20}?` window could never cross a `\\n` —
    `_iter_txt_records` joins a WA export's continuation lines with `\\n`,
    so a keyword and its digit run on DIFFERENT lines of the same message
    escaped Scan B entirely (and the digit run alone, 7 digits, is too
    short for either of Scan A's own thresholds — the message escaped
    BOTH scans)."""

    def test_guilt_keyword_and_digits_on_different_lines_now_caught(self):
        text = "ini nomor paspor saya:\nA1234567"
        findings = _independent_pii_scan(text)
        assert "id_doc_near_digits" in findings

    def test_innocence_same_line_still_caught_as_before(self):
        text = "nomor paspor saya A1234567"
        findings = _independent_pii_scan(text)
        assert "id_doc_near_digits" in findings

    def test_innocence_keyword_far_beyond_the_newline_window_not_flagged(self):
        """DOTALL widens `.` to cross newlines but the `{0,20}?` character
        budget is unchanged — a keyword and a digit run separated by more
        than 20 characters (newline included in the count) still must not
        match."""
        text = "nomor paspor saya adalah rahasia dan tidak akan\nA1234567"
        findings = _independent_pii_scan(text)
        assert "id_doc_near_digits" not in findings

    def test_end_to_end_multiline_message_with_id_doc_and_digits_is_dropped(self, tmp_path: Path):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        _write_wa_txt(
            input_dir / "chat.txt",
            [
                "12/01/26, 09:00 - Client: ini nomor paspor saya:",
                "A1234567",
            ],
        )
        stats = build_corpus(
            input_dir=input_dir,
            output_dir=tmp_path / "out",
            execute=False,
            use_ollama_ner=False,
            ollama_model="unused",
            require_role_aware=False,
        )
        assert stats["read"] == 1
        assert stats["kept"] == 0
        assert stats["dropped_independent_scan"] == 1


class TestR8_8SlashSeparatedDigitRunsAndDayFirstDates:
    """R8-8 (Kimi K3 round-8 review): `/` used to be excluded from
    `_RESIDUAL_SPACED_DIGIT_RUN_RE`'s separator class — a NIK/phone number
    typed with slashes ("3171/2345/6789/0123") escaped Scan A entirely.
    `/` is now included, with `_is_date_or_amount_shape` extended to
    recognize the day-first `DD/MM/YYYY`/`DD-MM-YYYY` shape (real-calendar
    validated) so genuine dates and short legal citations stay exempt."""

    def test_guilt_slash_separated_nik_shaped_run_is_flagged(self):
        assert _has_spaced_digit_pii("KTP saya 3171/2345/6789/0123 ya") is True

    def test_innocence_dmy_valid_date_is_not_flagged(self):
        assert _is_date_or_amount_shape("15/08/2026") is True
        assert _has_spaced_digit_pii("Ketemu tanggal 15/08/2026 ya") is False

    def test_innocence_dmy_dash_valid_date_is_not_flagged(self):
        assert _is_date_or_amount_shape("15-08-2026") is True

    def test_guilt_dmy_shaped_but_calendar_impossible_is_not_exempted(self):
        """Month 15 does not exist — the shape matches `_DMY_DATE_SHAPE_RE`
        but must fail the real-calendar `datetime.date` check, same as the
        existing ISO-shape calendar-impossible test elsewhere in this
        file, and therefore fall through to the amount-shape check (which
        it also does not match, since it has no thousands-grouping
        pattern) — never exempted."""
        assert _is_date_or_amount_shape("32/15/2026") is False

    def test_innocence_short_legal_citation_never_reaches_the_regex_span(self):
        """`UU 6/2023` (6 characters) never reaches
        `_RESIDUAL_SPACED_DIGIT_RUN_RE`'s own 8-character minimum span in
        the first place — was never at risk from including `/`."""
        assert _has_spaced_digit_pii("Lihat UU 6/2023 soal ini") is False

    def test_end_to_end_slash_separated_nik_message_is_dropped(self, tmp_path: Path):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        _write_wa_txt(
            input_dir / "chat.txt",
            ["12/01/26, 09:00 - Client: NIK saya 3171/2345/6789/0123 ya pak"],
        )
        stats = build_corpus(
            input_dir=input_dir,
            output_dir=tmp_path / "out",
            execute=False,
            use_ollama_ner=False,
            ollama_model="unused",
            require_role_aware=False,
        )
        assert stats["kept"] == 0
        assert stats["dropped_residual_pii"] == 1


class TestR8_13SymlinkRefusedOnWrite:
    """R8-13 MICRO (Kimi K3 round-8 review): `_write_jsonl_private` now
    opens with `O_NOFOLLOW` — a pre-planted symlink at the target path
    must be refused, never followed and written through."""

    def test_guilt_preexisting_symlink_is_refused_not_followed(self, tmp_path: Path):
        real_target = tmp_path / "attacker_owned_file.jsonl"
        real_target.write_text("original\n", encoding="utf-8")
        symlink_path = tmp_path / "fixtures_en.local.jsonl"
        symlink_path.symlink_to(real_target)

        with pytest.raises(OSError):
            _write_jsonl_private(symlink_path, [{"id": "fixture-000001", "language": "en", "text": "hi"}])

        assert real_target.read_text(encoding="utf-8") == "original\n", (
            "a symlink target's content must never be overwritten by a call that O_NOFOLLOW refuses"
        )

    def test_innocence_plain_new_file_still_written_normally(self, tmp_path: Path):
        target = tmp_path / "fixtures_en.local.jsonl"
        _write_jsonl_private(target, [{"id": "fixture-000001", "language": "en", "text": "hi"}])
        assert target.exists()
        assert json.loads(target.read_text(encoding="utf-8").splitlines()[0])["id"] == "fixture-000001"


class TestR8_14ZeroRecordTxtFileWarns:
    """R8-14 (Kimi K3 round-8 review): `_iter_txt_records`'s own docstring
    promised the caller counts a `.txt` file that yields zero records as
    unparsed — `_load_records` never actually implemented that promise.
    Now it logs a warning by opaque per-file ordinal (never the path)."""

    def test_guilt_zero_record_txt_file_logs_a_warning(self, tmp_path: Path, caplog):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        secret_name = "ContactNameSecretExport"
        bad_file = input_dir / f"WhatsApp Chat with {secret_name}.txt"
        bad_file.write_text("this file has no WA-shaped lines at all\njust plain text\n", encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            records = list(_load_records(input_dir))

        assert records == []
        messages = [r.getMessage() for r in caplog.records]
        assert any("yielded zero records" in m for m in messages)
        for m in messages:
            assert secret_name not in m, f"path/contact name leaked into zero-record warning: {m!r}"

    def test_innocence_txt_file_with_records_does_not_warn(self, tmp_path: Path, caplog):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        _write_wa_txt(
            input_dir / "chat.txt",
            ["12/01/26, 09:00 - Client: How long does the visa process take?"],
        )

        with caplog.at_level(logging.WARNING):
            records = list(_load_records(input_dir))

        assert len(records) == 1
        messages = [r.getMessage() for r in caplog.records]
        assert not any("yielded zero records" in m for m in messages)


class TestR9_2ZeroRecordJsonlFileWarns:
    """R9-2 (Kimi K3 round-9 review): R8-14's zero-record warning covered
    only the `.txt` branch of `_load_records` — a `.jsonl` file that
    yields zero records (e.g. entirely blank lines) counted and warned
    nothing. Both branches now share the same posture."""

    def test_guilt_zero_record_jsonl_file_logs_a_warning(self, tmp_path: Path, caplog):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        blank_file = input_dir / "export.jsonl"
        blank_file.write_text("\n\n   \n", encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            records = list(_load_records(input_dir))

        assert records == []
        messages = [r.getMessage() for r in caplog.records]
        assert any("yielded zero records" in m and "(.jsonl)" in m for m in messages)

    def test_innocence_jsonl_file_with_records_does_not_warn(self, tmp_path: Path, caplog):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        record_file = input_dir / "export.jsonl"
        record_file.write_text(
            json.dumps({"text": "How long does the visa process take?"}) + "\n",
            encoding="utf-8",
        )

        with caplog.at_level(logging.WARNING):
            records = list(_load_records(input_dir))

        assert len(records) == 1
        messages = [r.getMessage() for r in caplog.records]
        assert not any("yielded zero records" in m for m in messages)


class TestR18_1DotAttachedHonorificAndSigNormalization:
    """R18-1 (Kimi K3 round-18 review, MEDIUM): `_HONORIFIC_NAME_RE`
    missed the dot-elided, no-space WA-typing shortcut ("ibu.siti
    rahayu", "pak.budi santoso") entirely — both the required `\\s+`
    separator and the (undiscovered-until-now) accidental global
    `re.IGNORECASE` widening of the name-arm's `[A-Z]` combined into a
    two-cause bug; see the pattern's own module-level comment (G2
    CORRECTION + R18-1 binding correction) for the full derivation.
    Fixed with a new dot-attached branch that allows a lowercase name
    only when the literal dot is present (the dot itself is the
    name-elision signal), plus genuine scoped case-sensitivity
    (`(?i:...)`) on the pre-existing spaced branch so an honorific
    marker followed by an ordinary lowercase word ("makasih pak",
    "bu, besok ya") is no longer mistaken for a name."""

    def test_guilt_dot_attached_lowercase_name_flagged(self):
        assert "honorific_name" in _independent_pii_scan("tolong sampaikan ke ibu.siti rahayu besok")
        assert "honorific_name" in _independent_pii_scan("pak.budi santoso datang")

    def test_innocence_marker_followed_by_ordinary_lowercase_word_not_flagged(self):
        """The bug this fix closes: before R18-1, the marker-word
        `re.IGNORECASE` flag was GLOBAL and silently also widened the
        name-arm's `[A-Z]` class to accept lowercase — so an honorific
        followed by any ordinary lowercase word (not a name at all) was
        wrongly flagged. Both fixtures below are extremely common casual
        Indonesian with zero PII."""
        assert "honorific_name" not in _independent_pii_scan("makasih pak sudah bantu")
        assert "honorific_name" not in _independent_pii_scan("bu, besok ya")

    def test_existing_dot_spaced_titlecase_name_still_flagged(self):
        """Pre-existing behaviour (the spaced branch, dot-then-space,
        genuine titlecase name) must survive the fix unchanged."""
        assert "honorific_name" in _independent_pii_scan("ke Ibu. Siti Rahayu")

    def test_addendum_sig_dot_attached_titlecase_name_flagged(self):
        """ADDENDUM (Codex pre-freeze gate on R18-1's own implementation,
        integrated before commit): "Sig.Rossi" — bare "Sig" plus the new
        dot-attached branch consuming ".Rossi". Guards the Sig-token
        normalization (the dot moved OUT of the marker literal and
        became the branch's own separator, `Sig(?:\\.ra)?`)."""
        assert "honorific_name" in _independent_pii_scan("Sig.Rossi chiede update")

    def test_addendum_sig_ra_long_form_still_flagged_via_spaced_branch(self):
        """ADDENDUM form-innocence: "Sig.ra Rossi" must still match via
        the full "Sig.ra" token (tried first by alternation, greedy) plus
        the spaced branch on " Rossi" — NOT mis-parsed as "Sig" + "." +
        "ra" (the dot-attached branch's own 3-char minimum rejects "ra").
        Pins that the Sig-token renormalization did not regress the
        long-form "Signora" abbreviation."""
        assert "honorific_name" in _independent_pii_scan("Sig.ra Rossi")


class TestR18_1bSpacedLowercaseNameStopwordGuard:
    """R18-1b micro-disposition (orchestrator live-gate finding on the
    frozen round-18 delivery, not Kimi): R18-1's scoped case-sensitivity
    fix closed the marker-followed-by-ordinary-lowercase-word over-match
    but, as an unnamed side effect, ALSO closed the spaced-lowercase NAME
    case entirely — the single most common real WA shape ("ibu siti
    rahayu", no dot, name all-lowercase). Pre-R18-1, this shape matched
    (via the accidental global-IGNORECASE over-match); post-R18-1 it did
    not, a fail-open residual this file's own cost model treats as unsafe
    ("a dropped fixture costs zero, a leaked name does not"). Fixed with
    a third, stopword-guarded branch
    (`_has_honorific_spaced_lowercase_name`): an honorific followed by a
    spaced lowercase word FLAGS unless that word is in a short closed
    stoplist of common Indonesian non-name particles — see the
    module-level R18-1b comment for the full derivation."""

    def test_guilt_spaced_lowercase_name_flagged(self):
        assert "honorific_name" in _independent_pii_scan("tolong ke ibu siti rahayu besok")
        assert "honorific_name" in _independent_pii_scan("pak budi santoso datang")

    def test_innocence_marker_followed_by_stopword_not_flagged(self):
        """Three stoplist scenarios: "sudah" (already covered by R18-1's
        own innocence test, re-pinned here under the new branch's more
        specific reasoning), plus "tolong" — a marker immediately
        followed by a DIFFERENT stopword than the one in the guilt
        fixture above, proving the guard checks the actual captured word,
        not just the presence of "tolong" anywhere in the sentence."""
        assert "honorific_name" not in _independent_pii_scan("makasih pak sudah bantu")
        assert "honorific_name" not in _independent_pii_scan("pak tolong kirim")

    def test_innocence_comma_after_marker_still_not_flagged(self):
        """ "bu, besok ya" — the VERDICT is unchanged (unflagged), but the
        MECHANISM changed at R20-3: this docstring originally described
        the comma as breaking the marker-then-space adjacency the
        candidate regex required, a structural reason independent of the
        stoplist. R20-3 widened the separator to `[.:,]?\\s+` specifically
        so light punctuation like this comma no longer blocks the match
        (a DELIBERATE side effect, not a regression) — so this fixture
        now REACHES the two-mode scan and stays unflagged via mode (a)/
        mode (b) failing on the stopword "besok", exactly like
        `test_innocence_marker_followed_by_stopword_not_flagged` above.
        Kept as its own test to pin that the comma case specifically
        still resolves to unflagged, even though it no longer exercises
        a distinct code path from the stopword-guard tests."""
        assert "honorific_name" not in _independent_pii_scan("bu, besok ya")

    def test_regression_r18_1_dot_attached_and_addendum_sig_cases_unaffected(self):
        """The R18-1b branch is purely additive (an OR'd-in extra
        detector) — every guilt/innocence case R18-1 and its Sig ADDENDUM
        already pinned must remain byte-for-byte identical."""
        assert "honorific_name" in _independent_pii_scan("tolong sampaikan ke ibu.siti rahayu besok")
        assert "honorific_name" in _independent_pii_scan("pak.budi santoso datang")
        assert "honorific_name" in _independent_pii_scan("ke Ibu. Siti Rahayu")
        assert "honorific_name" in _independent_pii_scan("Sig.Rossi chiede update")
        assert "honorific_name" in _independent_pii_scan("Sig.ra Rossi")


class TestR18_2ExtendedBirthMarkerVocabulary:
    """R18-2 (Kimi K3 round-18 review, MEDIUM): `_BIRTH_MARKER_RE` was
    missing "bday" (no hyphen), "d.o.b." (with periods), and the Italian
    birth vocabulary ("compleanno", "nascita", "nato"/"nata") — this
    corpus's `_LANG_MARKERS` already includes an `it` bucket, so Italian
    is in-scope. Each of these previously let a birth date slip past the
    birth-context veto in `_is_date_or_amount_shape` and get exempted as
    an ordinary date."""

    def test_guilt_new_birth_markers_veto_the_date_exemption(self):
        for text in (
            "my bday 15/08/1990",
            "d.o.b. 15/08/1990",
            "compleanno 15/08/1990",
            "nato il 15/08/1990",
        ):
            assert _has_spaced_digit_pii(text), f"{text!r} unexpectedly NOT flagged"

    def test_innocence_ordinary_meeting_date_without_birth_marker_still_exempt(self):
        """No birth marker nearby — an ordinary calendar date used to
        schedule a meeting must stay exempt, proving the new vocabulary
        didn't widen what counts as a birth context beyond these
        specific new tokens."""
        assert not _has_spaced_digit_pii("meeting 15/08/2026 ok dikonfirmasi")


class TestR18_3ExtendedAddressMarkerVocabulary:
    """R18-3 (Kimi K3 round-18 review, MEDIUM): `_ADDRESS_MARKER_RE`'s
    marker vocabulary was missing standard Indonesian address
    abbreviations ("Gg." for "Gang", "Komp."/"Perum." for
    "Komplek"/"Perumahan") and several street/complex-type words never
    covered at all ("Dusun", "Kampung", "Ruko", "Blok"). Both fixtures
    below previously passed Scan B (and the titlecase-bigram heuristic)
    entirely undetected."""

    def test_guilt_gg_abbreviation_flagged(self):
        assert "address_marker" in _independent_pii_scan("alamat: Gg. Melati II No. 4, Denpasar")

    def test_guilt_gg_abbreviation_lowercase_no_space_flagged(self):
        assert "address_marker" in _independent_pii_scan("gg. melati no 3")


class TestR19_1HonorificAdjacentPairStopwordGuard:
    """R19-1 (Kimi K3 round-19 review, HIGH): R18-1b's stopword guard
    judged ONLY the first word after the honorific — a single bridging
    stopword ("minta", "tolong") shields the real name pair behind it
    entirely. Fixed under the ADJACENT-PAIR rule: look at the next ~4
    words after the honorific and flag if any two CONSECUTIVE words are
    both lowercase and both outside the stoplist (Indonesian names come
    in pairs — given name + family name)."""

    def test_guilt_name_pair_behind_a_bridging_stopword_flagged(self):
        assert "honorific_name" in _independent_pii_scan("pak minta budi santoso datang")
        assert "honorific_name" in _independent_pii_scan("ibu tolong siti rahayu")

    def test_innocence_no_adjacent_non_stopword_pair_not_flagged(self):
        """R20-4 correction, 2026-08-15 (Kimi K3 round-20 review, MICRO):
        the second fixture used to be "bu, besok ya" — but R20-3 widened
        the marker-only separator to admit light punctuation, so that
        fixture now reaches this scan for a DIFFERENT reason (the comma
        no longer blocks the match structurally) than the one this test
        names ("no adjacent non-stopword pair"); its comma-specific case
        is pinned in its own dedicated test
        (`test_innocence_comma_after_marker_still_not_flagged`, updated
        this round). Replaced with "ibu minta bantu" — a genuinely
        DIFFERENT marker+stopword+single-word combination ("minta" is
        the stopword, "bantu" the lone content word, no adjacent
        partner) that exercises the SAME mechanism
        ("makasih pak sudah bantu" does) without relying on a fixture
        whose own history is about punctuation, not the pair rule."""
        assert "honorific_name" not in _independent_pii_scan("makasih pak sudah bantu")
        assert "honorific_name" not in _independent_pii_scan("ibu minta bantu")

    def test_regression_r18_1b_pre_existing_guilt_cases_unaffected(self):
        """The R18-1b guilt fixtures already had their name pair
        adjacent to the marker — must remain flagged identically under
        the new pair rule."""
        assert "honorific_name" in _independent_pii_scan("pak budi santoso datang")
        assert "honorific_name" in _independent_pii_scan("tolong ke ibu siti rahayu besok")


class TestR19_1bHonorificTwoModeStopwordGuard:
    """R19-1b micro-disposition (Codex pre-freeze gate on R19-1's own
    implementation, integrated after round 19 (`037d697c9`) had already
    been delivered — MICRO-THAW). R19-1's pure adjacent-pair rule closed
    the bridging-stopword hole but introduced its own declared residual:
    "pak budi ya" stayed unflagged, since the single real name word
    ("budi") had no adjacent non-stopword partner anywhere in the
    window — unnecessary, since R18-1b's original single-word rule was
    already correct for the case where the FIRST word after the marker
    is itself a valid candidate. Corrected to TWO-MODE semantics: (a) the
    word immediately after the marker flags alone if it's a valid
    candidate (closes the "pak budi ya" residual); (b) only when that
    first word fails to qualify (a stopword) does the adjacent-pair rule
    from R19-1 apply."""

    def test_mode_a_first_word_candidate_flags_alone(self):
        """Closes the R19-1-declared residual: "pak budi ya" now flags
        via mode (a) — "budi", the immediate first word, is a valid
        candidate on its own, with no pair required."""
        assert "honorific_name" in _independent_pii_scan("pak budi santoso")
        assert "honorific_name" in _independent_pii_scan("pak budi ya")

    def test_mode_b_bridging_stopword_still_requires_a_pair(self):
        """Regression: the R19-1 bridging-stopword+pair cases must
        remain flagged identically under mode (b)."""
        assert "honorific_name" in _independent_pii_scan("pak minta budi santoso")
        assert "honorific_name" in _independent_pii_scan("ibu tolong siti rahayu")

    def test_mode_b_innocence_single_word_after_stopword_still_not_flagged(self):
        """Regression: a bridging stopword followed by only ONE
        non-stopword word (no adjacent pair) must still stay unflagged."""
        assert "honorific_name" not in _independent_pii_scan("pak tolong kirim")
        assert "honorific_name" not in _independent_pii_scan("makasih pak sudah bantu")

    def test_declared_residual_bridging_stopword_plus_single_name_not_flagged(self):
        """New declared residual, STRICTLY NARROWER than R19-1's own —
        the only case left needing a pair at all: a bridging stopword
        followed by exactly ONE name word and nothing else that
        qualifies still escapes, since mode (b) never fires on a single
        candidate."""
        assert "honorific_name" not in _independent_pii_scan("pak minta budi")
        assert "honorific_name" not in _independent_pii_scan("pak tolong siti ya")


class TestR19_2AddressMarkerPrefixBoundary:
    """R19-2 (Kimi K3 round-19 review, MEDIUM): the short address
    markers were unanchored prefixes of ordinary Indonesian words with no
    address meaning ("komplain", "blokir", "gangguan", "kompensasi") —
    at corpus scale this starves the Indonesian-language bucket rather
    than merely dropping occasional fixtures, so (unlike most over-matches
    on this detector) it was worth tightening. Fixed with a zero-width
    lookahead requiring whitespace or a literal dot right after the
    marker; `Jln` added as its own explicit token since the lookahead
    would otherwise silently lose the R17-3 "jln mawar" bonus (which used
    to work only via "Jl" matching as an unanchored prefix of "jln")."""

    def test_guilt_ordinary_words_no_longer_flagged(self):
        for text in (
            "ada komplain dari klien",
            "jangan blokir nomor itu",
            "ada gangguan jaringan",
            "minta kompensasi dulu",
        ):
            findings = _independent_pii_scan(text)
            assert "address_marker" not in findings, f"{text!r} unexpectedly flagged"

    def test_innocence_regression_genuine_address_markers_still_flagged(self):
        for text in (
            "alamat: Gg. Melati II No. 4, Denpasar",
            "alamat jl.sunset road 8",
            "gg.mawar no 3",
            "Jl Sunset city",
            # "Blok C" — R19-1b amendment addition (Codex gate confirmed
            # this must survive the R19-2 tightening; pinned here rather
            # than left unprobed).
            "rumah di Blok C",
        ):
            assert "address_marker" in _independent_pii_scan(text), f"{text!r} lost"

    def test_jln_explicit_token_still_flagged_after_tightening(self):
        """The R17-3 "jln mawar" bonus used to work only via "Jl"
        matching as an unanchored prefix of "jln" — the new lookahead
        would silently lose that shape without an explicit "Jln" token."""
        assert "address_marker" in _independent_pii_scan("kita mau jln mawar")

    def test_bonus_jalankan_false_positive_incidentally_closed(self):
        """Not required by the mandate, but measured as a side effect:
        the R17-3-declared "jalankan" ("run/execute") false positive is
        also closed by this same lookahead, since "k" (the char right
        after "Jalan" in "jalankan") is not whitespace or a dot."""
        assert "address_marker" not in _independent_pii_scan("kita mau jalankan program ini")


class TestR19_3DotAttachedHonorificStopwordGuard:
    """R19-3 (Kimi K3 round-19 review, LOW): the dot-attached honorific
    branch (extracted from `_HONORIFIC_NAME_RE` this round into its own
    `_HONORIFIC_DOT_ATTACHED_CANDIDATE_RE`) never carried the
    R18-1b/R19-1 stopword guard its spaced-lowercase sibling has — an
    inconsistency between two branches of the same over-match class.

    R21-4 declared-stale note (Kimi K3 round-21 review, LOW): the
    `_HONORIFIC_DOT_ATTACHED_CANDIDATE_RE` symbol named above is
    historical narration of what THIS round (R19-3) did at the time —
    it was later REMOVED as dead code in R20-1 (see that round's own
    binding correction in `build_deid_corpus.py`, above
    `_has_honorific_attached_name`), and the surviving branch was
    further renamed "dot-attached" -> "attached" in R21-2. Per this
    file's own corrections convention, the historical claim above is
    left as-is rather than rewritten; this paragraph is the required
    declare-and-move-on for a reader who greps for a symbol that no
    longer exists."""

    def test_guilt_stopword_after_dot_no_longer_flagged(self):
        assert "honorific_name" not in _independent_pii_scan("makasih pak.sudah bantu")
        assert "honorific_name" not in _independent_pii_scan("bu.tolong kirim")

    def test_regression_dot_attached_and_addendum_sig_cases_unaffected(self):
        """Every R18-1/ADDENDUM dot-attached guilt case must remain
        flagged identically after the stopword guard is applied."""
        assert "honorific_name" in _independent_pii_scan("tolong sampaikan ke ibu.siti rahayu besok")
        assert "honorific_name" in _independent_pii_scan("pak.budi santoso datang")
        assert "honorific_name" in _independent_pii_scan("Sig.Rossi chiede update")
        assert "honorific_name" in _independent_pii_scan("Sig.ra Rossi")
        assert "honorific_name" in _independent_pii_scan("Sig.raffaele")


class TestR20_1DotAttachedTwoModeStopwordGuard:
    """R20-1 (Kimi K3 round-20 review, MEDIUM): the dot-attached branch
    only ever had the mode-(a) single-word check — it was never given
    the mode-(b) bridging-pair mirror R19-1/R19-1b added to the spaced
    branch, and a dot-attached honorific cannot fall through to the
    spaced function either (that one requires literal whitespace right
    after the marker). Fixed by routing the dot branch through the same
    `_has_honorific_name_after_marker` shared two-mode scan the spaced
    branch uses (mode (a): any-case, preserving titlecase names like
    "Sig.Rossi"; mode (b): the shared ANY-CASE
    `_is_honorific_pair_candidate` pair-scan — corrected R22-2, ADR §29:
    this sentence named the lowercase-only `_is_honorific_name_candidate`
    here, accurate when R20-1 wrote it but false since R21-1 widened
    mode (b) to any-case on both branches; zero assertion changes)."""

    def test_guilt_name_pair_behind_a_dot_attached_bridging_stopword_flagged(self):
        assert "honorific_name" in _independent_pii_scan("ibu.tolong siti rahayu")
        assert "honorific_name" in _independent_pii_scan("pak.minta budi santoso datang")

    def test_innocence_regress_dot_attached_single_word_after_stopword_not_flagged(self):
        assert "honorific_name" not in _independent_pii_scan("makasih pak.sudah bantu")
        assert "honorific_name" not in _independent_pii_scan("bu.tolong kirim")

    def test_regression_pure_mode_a_dot_attached_cases_unaffected(self):
        """Titlecase (ADDENDUM) and lowercase (R18-1) mode-(a) dot-attached
        cases must remain flagged identically under the restructure."""
        assert "honorific_name" in _independent_pii_scan("ibu.siti rahayu")
        assert "honorific_name" in _independent_pii_scan("Sig.Rossi chiede update")
        assert "honorific_name" in _independent_pii_scan("Sig.raffaele")

    def test_declared_residual_dot_attached_bridging_stopword_plus_single_name(self):
        """Declared residual, MIRRORING the spaced branch's own R19-1b
        residual exactly: a dot-attached bridging stopword followed by
        exactly ONE name word and nothing else that qualifies still
        escapes, since mode (b) never fires on a single candidate."""
        assert "honorific_name" not in _independent_pii_scan("pak.minta budi")


class TestR20_2IdDocEncliticSuffix:
    """R20-2 (Kimi K3 round-20 review, MEDIUM): `_ID_DOC_NEAR_DIGITS_RE`'s
    trailing `\\b` right after the keyword alternation rejected
    Indonesian enclitic suffixes ("-nya"/"-ku"/"-mu"/"-lah") glued
    directly onto the noun with no space — the MORE common real-WA form,
    not an edge case. Fixed with an optional non-capturing suffix group
    between the keyword and the trailing `\\b`."""

    def test_guilt_enclitic_suffixed_keywords_flagged(self):
        for text in (
            "paspornya A1234567",
            "KTPnya 3171234567",
            "NIKnya 317123456789",
        ):
            findings = _independent_pii_scan(text)
            assert "id_doc_near_digits" in findings, f"{text!r} not flagged"

    def test_regression_unsuffixed_form_still_flagged(self):
        """R21-6(b) rename (Kimi K3 round-21 review, MICRO): the previous
        name, `test_innocence_regression_unsuffixed_form_still_flagged`,
        lied about its own verdict — "innocence" means NOT flagged, but
        the assertion below pins a POSITIVE match (a guilt-regression:
        the unsuffixed bare-keyword case must stay flagged after R20-2's
        enclitic-suffix widening). Content unchanged, name corrected to
        match the verdict it actually pins."""
        assert "id_doc_near_digits" in _independent_pii_scan("paspor A1234567")


class TestR20_3HonorificLightPunctuationSeparator:
    """R20-3 (Kimi K3 round-20 review, LOW), amended by R20-3b (Codex
    gate, in-flight during round 20): the separator between an honorific
    marker and the name allowed only an optional literal dot before the
    mandatory whitespace — real WA messages routinely punctuate with a
    colon, comma, or hyphen instead ("pak: Budi Santoso", "pak, budi
    santoso ok", "pak- budi santoso"), which were rejected entirely.
    Fixed by widening `\\.?` to `[.:,-]?` (R20-3 landed `[.:,]?` first;
    R20-3b added the hyphen the finding's own text named but the
    delivered class omitted) on both `_HONORIFIC_NAME_RE`
    (spaced-titlecase) and `_HONORIFIC_MARKER_ONLY_RE` (the two-mode
    spaced-lowercase scan)."""

    def test_guilt_colon_and_comma_separators_flagged(self):
        assert "honorific_name" in _independent_pii_scan("pak: budi santoso")
        assert "honorific_name" in _independent_pii_scan("pak, budi santoso ok")

    def test_innocence_comma_plus_single_stopword_word_still_not_flagged(self):
        """ "pak, sudah bantu" — the comma now reaches the two-mode scan
        (R20-3's own widening), but stays unflagged via the stopword
        guard on "sudah", exactly like the unpunctuated equivalent."""
        assert "honorific_name" not in _independent_pii_scan("pak, sudah bantu")

    def test_r20_3b_guilt_and_innocence_hyphen_separator(self):
        """R20-3b (Codex gate, in-flight): F3's finding text explicitly
        named "colon/hyphen-after-honorific", but the R20-3 delivery's
        separator class omitted the hyphen — proven: "pak- budi santoso"
        passed undetected. Fixed same-round, before recomposition."""
        assert "honorific_name" in _independent_pii_scan("pak- budi santoso")
        assert "honorific_name" not in _independent_pii_scan("bu- besok ya")


class TestR21_1HonorificPairScanAnyCase:
    """R21-1 (Kimi K3 round-21 review, MEDIUM): mode (b)'s adjacent-pair
    scan reused `_is_honorific_name_candidate` — LOWERCASE-ONLY — on
    BOTH the spaced and punct-attached branches identically, rejecting a
    capitalized pair member ("Budi", "Siti"). **F1 is VALID ON BOTH
    BRANCHES — there is no asymmetry** (R21-1b micro-disposition,
    orchestrator gate, correcting an earlier partial-refutation triage
    of this same round): Kimi's own example ("pak minta Budi santoso
    datang") reproduced the defect only by ACCIDENT, via an unrelated,
    purely-lowercase pair further in the same window ("santoso",
    "datang"), not because "Budi" was recognized — that made it look
    like the spaced branch already worked, but it never did. The
    CANONICAL spaced reproduction ends on the surname with nothing
    lowercase-pair-shaped behind it — "pak minta Budi santoso" (bare) or
    "pak minta Budi santoso ya" (trailing stopword, which cannot itself
    supply a rescuing pair) — both fail without the fix, both flag with
    it. Fixed: mode (b) now uses `_is_honorific_pair_candidate` (any
    case) uniformly on both branches."""

    def test_guilt_mixed_case_pair_flagged_on_punct_attached_branch(self):
        """The branch the gate itself already confirmed as broken."""
        assert "honorific_name" in _independent_pii_scan("ibu.tolong Siti rahayu")

    def test_guilt_mixed_case_pair_flagged_on_spaced_branch_without_the_lucky_extra_word(self):
        """Canonical spaced reproduction #1 (bare): with NO trailing
        word to coincidentally supply a second, purely-lowercase pair,
        the capitalized "Budi" must be recognized directly by mode (b)
        itself for this to flag."""
        assert "honorific_name" in _independent_pii_scan("pak minta Budi santoso")

    def test_guilt_mixed_case_pair_flagged_on_spaced_branch_with_trailing_stopword(self):
        """Canonical spaced reproduction #2 (trailing stopword, R21-1b
        micro-disposition): "ya" cannot itself pair with "santoso" (it
        is a stopword), so this variant also isolates the true
        mechanism — the capitalized pair, not an accidental lowercase
        one further out."""
        assert "honorific_name" in _independent_pii_scan("pak minta Budi santoso ya")

    def test_regression_spaced_branch_original_fixture_still_flagged(self):
        """Kimi's own fixture — which passed BEFORE this fix too, but
        via the coincidental (santoso, datang) pair, not via the actual
        defect — must stay flagged after the fix, now for the right
        reason (the capitalized "Budi" pair itself)."""
        assert "honorific_name" in _independent_pii_scan("pak minta Budi santoso datang")

    def test_innocence_stopword_only_still_not_flagged_on_both_branches(self):
        """The any-case widening must not turn a bare bridging stopword,
        with nothing candidate-shaped behind it, into a false positive."""
        assert "honorific_name" not in _independent_pii_scan("makasih pak.sudah bantu")
        assert "honorific_name" not in _independent_pii_scan("makasih pak sudah bantu")


class TestR21_2HonorificAttachedPunctuationClass:
    """R21-2 (Kimi K3 round-21 review, LOW): the punct-attached branch's
    marker-only regex (then named `_HONORIFIC_DOT_MARKER_ONLY_RE`)
    required a LITERAL DOT between the marker and the name, never
    carrying the comma/colon/hyphen widening R20-3/R20-3b already gave
    its `_HONORIFIC_NAME_RE`/`_HONORIFIC_MARKER_ONLY_RE` siblings.
    Renamed dot-attached -> punct-attached to match; widened `\\.` to
    `[.:,-]` (still mandatory — this branch's entire purpose is
    "punctuation glued directly onto the marker, no space before it")."""

    def test_guilt_comma_colon_hyphen_separators_flagged(self):
        assert "honorific_name" in _independent_pii_scan("pak,budi santoso ok")
        assert "honorific_name" in _independent_pii_scan("pak-budi santoso")
        assert "honorific_name" in _independent_pii_scan("pak:budi santoso")

    def test_innocence_comma_and_hyphen_plus_stopword_still_not_flagged(self):
        assert "honorific_name" not in _independent_pii_scan("bu,tolong kirim")
        assert "honorific_name" not in _independent_pii_scan("pak-sudah bantu")


class TestR21_3HonorificStopwordStackSkip:
    """R21-3 (Kimi K3 round-21 review, MEDIUM): mode (b)'s pair-scan ran
    over a FIXED window measured from the marker itself — a STACK of
    multiple leading bridging stopwords consumed that whole window
    before ever reaching the real name pair behind it. Fixed: leading
    stopwords are skipped first (bounded by `_HONORIFIC_STOPWORD_SKIP_CAP`),
    then the pair-scan window runs starting after that skip."""

    def test_guilt_stopword_stack_then_pair_flagged(self):
        assert "honorific_name" in _independent_pii_scan("pak minta tolong dong budi santoso")

    def test_regression_single_stopword_cases_unaffected(self):
        """The pre-existing R19-1/R19-1b/R20-1 single-stopword guilt and
        innocence cases must be unaffected by the skip-then-scan
        restructure."""
        assert "honorific_name" in _independent_pii_scan("pak minta budi santoso")
        assert "honorific_name" in _independent_pii_scan("ibu tolong siti rahayu")
        assert "honorific_name" not in _independent_pii_scan("makasih pak sudah bantu")
        assert "honorific_name" not in _independent_pii_scan("pak tolong kirim")

    def test_declared_residual_stopword_stack_plus_single_name_still_escapes(self):
        """Same declared-residual SHAPE as R19-1b/R20-1 (bridging
        stopword(s) followed by exactly ONE name word and nothing else
        that qualifies) — generalizes naturally to a stopword STACK
        rather than changing shape, since mode (b) still never fires on
        a single candidate."""
        assert "honorific_name" not in _independent_pii_scan("pak minta tolong budi")


class TestR21_5IdDocEncliticSuffixExtension:
    """R21-5 (Kimi K3 round-21 review, MICRO): R20-2's enclitic group
    named only `nya`/`ku`/`mu`/`lah` — the interrogative/emphatic `-kah`
    and emphatic `-pun` enclitics were absent. Fixed by extending the
    same optional non-capturing suffix group."""

    def test_guilt_kah_and_pun_enclitic_suffixes_flagged(self):
        assert "id_doc_near_digits" in _independent_pii_scan("KTPkah 3171234567")
        assert "id_doc_near_digits" in _independent_pii_scan("KTPpun 3171234567")

    def test_regression_r20_2_suffixes_and_bare_form_unaffected(self):
        assert "id_doc_near_digits" in _independent_pii_scan("paspornya A1234567")
        assert "id_doc_near_digits" in _independent_pii_scan("paspor A1234567")


class TestR28RoleAwareMultiturnCorpus:
    """The default builder mode emits user targets with at most 12 prior
    de-identified role-labelled turns and never serializes conversation IDs."""

    @staticmethod
    def _write_records(path: Path, rows: list[dict[str, str]]) -> None:
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )

    def test_default_mode_preserves_roles_and_context_without_group_identifier(self, tmp_path: Path):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        output_dir = tmp_path / "out"
        conversation_id = "local-conversation-never-serialize"
        self._write_records(
            input_dir / "export.jsonl",
            [
                {
                    "role": "assistant",
                    "conversation_id": conversation_id,
                    "text": "hello, how can i help?",
                },
                {
                    "role": "user",
                    "conversation_id": conversation_id,
                    "text": "what visa options should i verify?",
                },
                {
                    "role": "assistant",
                    "conversation_id": conversation_id,
                    "text": "the team should verify eligibility.",
                },
                {
                    "role": "user",
                    "conversation_id": conversation_id,
                    "text": "thanks, what documents are usually checked?",
                },
            ],
        )

        stats = build_corpus(
            input_dir=input_dir,
            output_dir=output_dir,
            execute=True,
            use_ollama_ner=False,
            ollama_model="unused",
        )

        fixtures = [
            json.loads(line)
            for path in output_dir.glob("fixtures_*.local.jsonl")
            for line in path.read_text(encoding="utf-8").splitlines()
            if line
        ]
        assert stats["mode"] == "role-aware-multiturn"
        assert stats["kept"] == 2
        assert [turn["role"] for turn in fixtures[0]["history"]] == ["assistant"]
        assert [turn["role"] for turn in fixtures[1]["history"]] == [
            "assistant",
            "user",
            "assistant",
        ]
        assert all(fixture["role"] == "user" for fixture in fixtures)
        assert conversation_id not in json.dumps(fixtures)

    def test_history_is_capped_at_twelve_prior_turns(self, tmp_path: Path):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        output_dir = tmp_path / "out"
        rows = [
            {
                "role": "assistant",
                "conversation_id": "opaque-local-1",
                "text": f"please review item {index}.",
            }
            for index in range(14)
        ]
        rows.append(
            {
                "role": "user",
                "conversation_id": "opaque-local-1",
                "text": "what should i verify next?",
            },
        )
        self._write_records(input_dir / "export.jsonl", rows)

        stats = build_corpus(
            input_dir=input_dir,
            output_dir=output_dir,
            execute=True,
            use_ollama_ner=False,
            ollama_model="unused",
        )

        fixture_lines = [
            line
            for path in output_dir.glob("fixtures_*.local.jsonl")
            for line in path.read_text(encoding="utf-8").splitlines()
            if line
        ]
        assert stats["kept"] == 1
        assert len(json.loads(fixture_lines[0])["history"]) == 12

    def test_interleaved_conversations_do_not_share_history(self, tmp_path: Path):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        output_dir = tmp_path / "out"
        self._write_records(
            input_dir / "export.jsonl",
            [
                {
                    "role": "assistant",
                    "conversation_id": "opaque-a",
                    "text": "answer for conversation alpha.",
                },
                {
                    "role": "assistant",
                    "conversation_id": "opaque-b",
                    "text": "answer for conversation beta.",
                },
                {
                    "role": "user",
                    "conversation_id": "opaque-a",
                    "text": "what should i verify?",
                },
            ],
        )

        build_corpus(
            input_dir=input_dir,
            output_dir=output_dir,
            execute=True,
            use_ollama_ner=False,
            ollama_model="unused",
        )

        fixture_lines = [
            line
            for path in output_dir.glob("fixtures_*.local.jsonl")
            for line in path.read_text(encoding="utf-8").splitlines()
            if line
        ]
        history = json.loads(fixture_lines[0])["history"]
        assert history == [{"role": "assistant", "text": "answer for conversation alpha."}]

    def test_unsafe_turn_resets_context_instead_of_bridging_over_gap(self, tmp_path: Path):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        output_dir = tmp_path / "out"
        self._write_records(
            input_dir / "export.jsonl",
            [
                {
                    "role": "assistant",
                    "conversation_id": "opaque-local-1",
                    "text": "hello, how can i help?",
                },
                {
                    "role": "assistant",
                    "conversation_id": "opaque-local-1",
                    "text": "John Smith will review this.",
                },
                {
                    "role": "user",
                    "conversation_id": "opaque-local-1",
                    "text": "what should i verify now?",
                },
            ],
        )

        stats = build_corpus(
            input_dir=input_dir,
            output_dir=output_dir,
            execute=True,
            use_ollama_ner=False,
            ollama_model="unused",
        )

        fixture_lines = [
            line
            for path in output_dir.glob("fixtures_*.local.jsonl")
            for line in path.read_text(encoding="utf-8").splitlines()
            if line
        ]
        assert stats["dropped_independent_scan"] == 1
        assert stats["context_resets"] == 1
        assert json.loads(fixture_lines[0])["history"] == []

    def test_missing_role_or_conversation_id_is_dropped_fail_closed(self, tmp_path: Path):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        self._write_records(
            input_dir / "export.jsonl",
            [
                {"conversation_id": "opaque-local-1", "text": "what visa applies?"},
                {"role": "user", "text": "what visa applies?"},
            ],
        )

        stats = build_corpus(
            input_dir=input_dir,
            output_dir=tmp_path / "out",
            execute=False,
            use_ollama_ner=False,
            ollama_model="unused",
        )

        assert stats["read"] == 2
        assert stats["dropped_role_unknown"] == 2
        assert stats["kept"] == 0

    def test_missing_conversation_id_clears_prior_histories_from_same_file(self, tmp_path: Path):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        output_dir = tmp_path / "out"
        self._write_records(
            input_dir / "export.jsonl",
            [
                {
                    "role": "assistant",
                    "conversation_id": "opaque-local-1",
                    "text": "hello, how can i help?",
                },
                {
                    "role": "assistant",
                    "text": "this unattributable turn breaks continuity.",
                },
                {
                    "role": "user",
                    "conversation_id": "opaque-local-1",
                    "text": "what should i verify now?",
                },
            ],
        )

        stats = build_corpus(
            input_dir=input_dir,
            output_dir=output_dir,
            execute=True,
            use_ollama_ner=False,
            ollama_model="unused",
        )

        fixture_lines = [
            line
            for path in output_dir.glob("fixtures_*.local.jsonl")
            for line in path.read_text(encoding="utf-8").splitlines()
            if line
        ]
        assert stats["dropped_role_unknown"] == 1
        assert stats["context_resets"] == 1
        assert json.loads(fixture_lines[0])["history"] == []
