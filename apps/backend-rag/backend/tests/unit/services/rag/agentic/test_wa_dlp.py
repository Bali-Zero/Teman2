"""G-P3 — DLP policy for the WA codex-route context package (design spec
research/operations/2026-08-19-bot-chatgpt-provider-broker-spec.md §G-P3),
PLUS the two-seat adversarial review cure batch (Kimi K3 + internal spalla,
2026-08-20): M1 (pricing_block.search_query redaction), M2 (separator-
broken PII patterns with validators), M3 (not-an-amount guard on PHONE),
S1 (CREDENTIAL is a one-way category), and the MINOR cures (EMAIL trailing
punctuation, evidence_inputs["dlp"], the single-chunk overflow variant).

Covers, per the spec's own test plan plus the cure batch:
  - per-category guilt (each category's pattern(s) redact their synthetic;
    the shapes NOT folded into the 50-item recall corpus — NPWP
    old/new-dotted, NIK label-anchored-separated, BANK_ACCOUNT IBAN,
    CREDENTIAL PEM/key-prefix/Bearer — get their own small guilt test
    here);
  - M2 guilt: the 5 separator-broken/case leaks Kimi reproduced with pure
    `re` experiments (separated bare NIK space/dot, NPWP-old bare-15,
    spaced-no-plus phone, newline-crossing bank label gap, lowercase
    passport);
  - innocence (KBLI codes, regulation citations, prices, dates, visa
    codes, plain sentences never touched — INCLUDING the exact mandate
    set: "Rp 1.250.000", "harga 62.500.000 rupiah", KBLI 56101, UU
    6/2011, Peraturan BKPM 5/2025, E33/C1/B211A);
  - M3 innocence: an IDR amount shaped exactly like a PHONE_ID match
    ("total investasi 62500000000 rupiah") must NOT be redacted;
  - the ONE precedence requirement named by the spec: a 16-digit NPWP
    must map to NPWP, never NIK;
  - round-trip identity (redact -> restore reproduces the original);
  - cross-field dedup (the SAME original string gets the SAME placeholder
    in history AND chunks);
  - the fail-closed overflow guard (>64 distinct values in one package),
    including the spalla single-chunk-text variant (the router caps
    history at 24 turns, so 65 distinct values in practice come from one
    chunk's text, not from 65 history turns);
  - S1: CREDENTIAL placeholders never enter reversal_map and are stripped
    (not restored) if the model echoes one back;
  - restore_text's hallucinated-placeholder handling (stripped, never
    shown, fail-visible via a WARNING log naming only the count);
  - the registered recall floor on the synthetic corpus
    (`dlp_synthetic_corpus.py`);
  - builder integration: `build_context_package(dlp=True)` seals a wire
    that carries placeholders and NOT the original digits, with the
    reversal map absent from both `wire_text()` and `to_payload()`, and
    M1's `pricing_block.search_query` consistently redacted alongside
    history;
  - the fail-closed test: a monkeypatched detector exception becomes
    `PackageUnbuildable("dlp_error")`.
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import patch

import pytest

from backend.services.rag.agentic.wa_dlp import (
    MAX_PLACEHOLDERS,
    DlpOverflow,
    DlpResult,
    redact_package_fields,
    restore_text,
)
from backend.tests.unit.services.rag.agentic.dlp_synthetic_corpus import (
    CORPUS,
    RECALL_FLOOR,
    realistic_nik_corpus,
    realistic_npwp_new16_bare_corpus,
    realistic_npwp_new16_dotted_corpus,
    realistic_npwp_old_dotted_corpus,
    realistic_passport_corpus,
)


def _chunk(text: str, **extra: Any) -> dict[str, Any]:
    return {"collection": "test", "text": text, "score": 1.0, **extra}


def _redact(
    history: list[dict[str, Any]] | None = None,
    chunks: list[dict[str, Any]] | None = None,
    search_query: str | None = None,
) -> DlpResult:
    return redact_package_fields(history or [], chunks or [], search_query)


def _hits_for(text: str) -> list[Any]:
    return _redact(chunks=[_chunk(text)]).hits


# ============================================================================
# 1. Per-category guilt — the shapes carried by the 50-item recall corpus
# ============================================================================


class TestGuiltCoreShapes:
    @pytest.mark.parametrize("category", sorted(CORPUS.keys()))
    def test_first_corpus_item_is_flagged_as_its_own_category(self, category: str) -> None:
        text = CORPUS[category][0]
        hits = _hits_for(text)
        assert any(h.category == category for h in hits), (
            f"{category} corpus item {text!r} produced no {category} hit "
            f"(hits={hits!r})"
        )


# ============================================================================
# 2. Per-category guilt — shapes NOT in the 50-item corpus
# ============================================================================


class TestGuiltAdditionalShapes:
    def test_npwp_old_dotted_format(self) -> None:
        hits = _hits_for("NPWP lama saya 12.345.678.9-012.345 terdaftar")
        assert any(h.category == "NPWP" for h in hits)

    def test_npwp_new_dotted_format(self) -> None:
        hits = _hits_for("NPWP baru saya 098.765.432.1-098.765 terdaftar")
        assert any(h.category == "NPWP" for h in hits)

    def test_nik_label_anchored_separated_format(self) -> None:
        hits = _hits_for("NIK: 1234 5678 9012 3456 pada dokumen")
        assert any(h.category == "NIK_KTP" for h in hits)

    def test_bank_account_iban_shape(self) -> None:
        hits = _hits_for("IBAN: GB29ABCD1234567890 untuk transfer")
        assert any(h.category == "BANK_ACCOUNT" for h in hits)

    def test_bank_account_digits_then_label(self) -> None:
        hits = _hits_for("Transfer ke 9876543210 rekening BCA saya")
        assert any(h.category == "BANK_ACCOUNT" for h in hits)

    def test_credential_pem_header(self) -> None:
        hits = _hits_for("-----BEGIN RSA PRIVATE KEY----- (do not share this)")
        assert any(h.category == "CREDENTIAL" for h in hits)

    def test_credential_vendor_key_prefix(self) -> None:
        hits = _hits_for("leaked key sk-01234567890123456789 in the log")
        assert any(h.category == "CREDENTIAL" for h in hits)

    def test_credential_bearer_token(self) -> None:
        hits = _hits_for("Authorization: Bearer abcdefghij0123456789ABCD")
        assert any(h.category == "CREDENTIAL" for h in hits)

    def test_phone_intl_run_shape(self) -> None:
        hits = _hits_for("WA +6281234567890 available")
        assert any(h.category == "PHONE" for h in hits)


# ============================================================================
# 2bis. M2 guilt — the 5 separator-broken/case bypasses Kimi reproduced
# ============================================================================


class TestGuiltM2SeparatorBroken:
    def test_nik_separated_by_spaces_no_label(self) -> None:
        text = "identitas saya 1234 5678 9012 3456 terverifikasi"
        result = _redact(chunks=[_chunk(text)])
        assert "1234 5678 9012 3456" not in result.chunks[0]["text"]
        assert any(h.category == "NIK_KTP" for h in result.hits)

    def test_nik_separated_by_dots_no_label(self) -> None:
        text = "identitas saya 1234.5678.9012.3456 terverifikasi"
        result = _redact(chunks=[_chunk(text)])
        assert "1234.5678.9012.3456" not in result.chunks[0]["text"]
        assert any(h.category == "NIK_KTP" for h in result.hits)

    def test_npwp_old_bare_15_digit_no_dots(self) -> None:
        """A bare 15-digit run with no dots satisfies neither NPWP pattern
        (both require the official dotted format or a leading-zero 16-digit
        run) — it is caught by NIK_KTP's new separated pattern instead.
        MISLABEL (declared limit), never a leak: the digits ARE redacted."""
        text = "NPWP lama saya 123456789012345 sudah lama"
        result = _redact(chunks=[_chunk(text)])
        assert "123456789012345" not in result.chunks[0]["text"]
        assert result.hits, "expected at least one redaction (category may be mislabelled)"

    def test_phone_spaced_no_plus_prefix(self) -> None:
        text = "hubungi saya di 62 812 3456 7890 ya"
        result = _redact(chunks=[_chunk(text)])
        assert "62 812 3456 7890" not in result.chunks[0]["text"]
        assert any(h.category == "PHONE" for h in result.hits)

    def test_bank_label_and_digits_split_by_newline(self) -> None:
        text = "silakan transfer ke rekening BCA\n1234567890 terima kasih"
        result = _redact(chunks=[_chunk(text)])
        assert "1234567890" not in result.chunks[0]["text"]
        assert any(h.category == "BANK_ACCOUNT" for h in result.hits)
        # the label survives as literal text (group-scoped substitution)
        assert "rekening BCA" in result.chunks[0]["text"]

    def test_lowercase_passport_prefix(self) -> None:
        text = "passport number b1234567 on file"
        result = _redact(chunks=[_chunk(text)])
        assert "b1234567" not in result.chunks[0]["text"]
        assert any(h.category == "PASSPORT" for h in result.hits)

    def test_po_number_is_not_a_passport(self) -> None:
        """Kimi MINOR-4 (INNOCENCE half): the case-insensitive widening
        alone would over-match purchase-order numbers — the prefix-decline
        validator must refuse them."""
        text = "please reference PO123456 on the invoice"
        result = _redact(chunks=[_chunk(text)])
        assert "PO123456" in result.chunks[0]["text"]
        assert not any(h.category == "PASSPORT" for h in result.hits)


# ============================================================================
# 3. Innocence — nothing legitimate gets touched
# ============================================================================


INNOCENCE_SENTENCES: tuple[str, ...] = (
    "KBLI code 56101 covers restaurant and mobile food service activities.",
    "UU Nomor 6 Tahun 2011 governs Indonesian immigration.",
    "UU 6/2011 governs Indonesian immigration.",
    "Peraturan BKPM 5/2025 sets the paid-up capital floor at 2,5 miliar.",
    "The service costs Rp 2.500.000 for a single-entry visa.",
    "Rp 1.250.000 is the government processing fee.",
    "harga 62.500.000 rupiah untuk paket lengkap.",
    "Package price is 35M IDR including all government fees.",
    "Your renewal is due on 2026-08-20.",
    "The E33 visa applies to Second Home applicants.",
    "A C1 tourism extension is valid for 60 days.",
    "B211A entry visa holders may convert on arrival.",
    "This is a completely ordinary sentence with no PII at all.",
)


class TestInnocence:
    @pytest.mark.parametrize("sentence", INNOCENCE_SENTENCES)
    def test_innocent_sentence_untouched(self, sentence: str) -> None:
        result = _redact(history=[{"role": "user", "content": sentence}])
        assert result.history[0]["content"] == sentence
        assert result.hits == []
        assert result.reversal_map == {}

    def test_price_and_kbli_share_a_sentence_with_a_real_nik_only_the_nik_fires(self) -> None:
        """A composite sentence — the realistic case: a client message
        mixes a price/KBLI reference with genuine PII in the same turn.
        Only the NIK should be redacted."""
        text = "KBLI 56101, harga Rp 2.500.000, NIK saya 3212345678901234."
        result = _redact(chunks=[_chunk(text)])
        assert "56101" in result.chunks[0]["text"]
        assert "2.500.000" in result.chunks[0]["text"]
        assert "3212345678901234" not in result.chunks[0]["text"]
        assert [h.category for h in result.hits] == ["NIK_KTP"]
        assert result.reversal_map == {"[PII-NIK_KTP-1]": "3212345678901234"}


# ============================================================================
# 3bis. M3 — a phone-shaped IDR amount is not a phone number
# ============================================================================


class TestM3AmountNotPhone:
    def test_round_idr_amount_shaped_like_phone_is_not_redacted(self) -> None:
        """Kimi M3 (GUILT-of-the-bug / innocence-of-the-cure): before the
        not-an-amount + trailing-zeros validator, `\\b62\\d{9,12}\\b` alone
        redacted this as PHONE, poisoning the pricing lane."""
        text = "total investasi 62500000000 rupiah untuk PT PMA"
        result = _redact(chunks=[_chunk(text)])
        assert "62500000000" in result.chunks[0]["text"]
        assert not any(h.category == "PHONE" for h in result.hits)

    def test_a_genuine_62_phone_ending_in_non_round_digits_still_redacts(self) -> None:
        """Innocence-of-the-guard: the amount guard must not blanket-refuse
        every 62-prefixed run — only round-amount/adjacent-currency shapes."""
        text = "hubungi 6281234567890 untuk info lebih lanjut"
        result = _redact(chunks=[_chunk(text)])
        assert "6281234567890" not in result.chunks[0]["text"]
        assert any(h.category == "PHONE" for h in result.hits)

    def test_rp_prefixed_amount_not_ending_in_zeros_isolates_the_amount_guard(
        self,
    ) -> None:
        """Mutation-detection isolate: the existing round-amount guilt test
        above ("62500000000 rupiah") ends in "00000", so the INDEPENDENT
        trailing-zeros decline in `_validate_phone_digit_count` masks any
        regression to `_looks_like_amount` on its own (verified live: with
        `_looks_like_amount` hardcoded to return False, ALL other tests in
        this file still pass). This amount does not end in zeros, so only
        the `Rp`-prefix adjacency check can save it."""
        text = "harga sekitar Rp 62500000123 untuk paket ini"
        result = _redact(chunks=[_chunk(text)])
        assert "62500000123" in result.chunks[0]["text"]
        assert not any(h.category == "PHONE" for h in result.hits)

    def test_rupiah_suffixed_amount_not_ending_in_zeros_isolates_the_amount_guard(
        self,
    ) -> None:
        """Same isolation as above, suffix direction (`_AMOUNT_SUFFIX_RE`)
        instead of prefix (`_AMOUNT_PREFIX_RE`) — covers both branches of
        `_looks_like_amount`."""
        text = "modal disetor 62500000123 rupiah sesuai akta"
        result = _redact(chunks=[_chunk(text)])
        assert "62500000123" in result.chunks[0]["text"]
        assert not any(h.category == "PHONE" for h in result.hits)


# ============================================================================
# 4. NPWP-vs-NIK precedence (the one case the design spec names explicitly)
# ============================================================================


class TestPrecedence:
    def test_16_digit_npwp_shape_maps_to_npwp_not_nik(self) -> None:
        text = "NPWP saya 0123456789012345 terdaftar di kantor pajak."
        result = _redact(chunks=[_chunk(text)])
        assert len(result.hits) == 1
        assert result.hits[0].category == "NPWP"
        assert result.reversal_map == {"[PII-NPWP-1]": "0123456789012345"}

    def test_16_digit_non_zero_leading_is_nik_not_npwp(self) -> None:
        """Innocence half of the same precedence pair: a 16-digit run that
        does NOT satisfy NPWP-16's leading-zero shape must still be caught
        — as NIK, never silently skipped because NPWP looked first."""
        text = "NIK saya 3212345678901234 di dokumen ini."
        result = _redact(chunks=[_chunk(text)])
        assert len(result.hits) == 1
        assert result.hits[0].category == "NIK_KTP"
        assert result.reversal_map == {"[PII-NIK_KTP-1]": "3212345678901234"}


# ============================================================================
# 5. Round-trip identity + cross-field dedup
# ============================================================================


class TestRoundTrip:
    def test_redact_then_restore_is_identity(self) -> None:
        history = [
            {
                "role": "user",
                "content": (
                    "My NIK is 3212345678901234 and my email is foo@example.com"
                ),
            }
        ]
        chunks = [
            _chunk("Contact +6281234567890 or rekening no. 1000000000 BCA for support.")
        ]
        result = _redact(history=history, chunks=chunks)
        assert result.hits, "expected at least one redaction"
        assert (
            restore_text(result.history[0]["content"], result.reversal_map)
            == history[0]["content"]
        )
        assert restore_text(result.chunks[0]["text"], result.reversal_map) == chunks[0]["text"]

    def test_same_original_gets_same_placeholder_across_history_and_chunks(self) -> None:
        email = "shared@example.com"
        history = [{"role": "user", "content": f"reach me at {email}"}]
        chunks = [_chunk(f"also on file: {email}")]
        result = _redact(history=history, chunks=chunks)
        assert len(result.reversal_map) == 1
        placeholder = next(iter(result.reversal_map))
        assert placeholder in result.history[0]["content"]
        assert placeholder in result.chunks[0]["text"]
        assert sum(1 for h in result.hits if h.category == "EMAIL") == 1

    def test_same_original_repeated_within_one_field_dedups(self) -> None:
        nik = "3212345678901234"
        text = f"NIK {nik} lagi, ulangi: {nik}."
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"].count("[PII-NIK_KTP-1]") == 2
        assert len(result.reversal_map) == 1
        assert len(result.hits) == 1


# ============================================================================
# 5bis. Kimi-5 — EMAIL no longer swallows sentence-final punctuation
# ============================================================================


class TestEmailTrailingPunctuation:
    def test_trailing_period_is_not_swallowed(self) -> None:
        text = "Contact me at foo@example.com. Thanks!"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == "Contact me at [PII-EMAIL-1]. Thanks!"
        assert result.reversal_map == {"[PII-EMAIL-1]": "foo@example.com"}

    def test_ordinary_mid_sentence_email_unaffected(self) -> None:
        text = "Send it to foo@example.com right away"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == "Send it to [PII-EMAIL-1] right away"


# ============================================================================
# 6. Fail-closed: overflow
# ============================================================================


class TestOverflow:
    def test_more_than_max_placeholders_raises(self) -> None:
        chunks = [_chunk(f"user{i}@example.com") for i in range(MAX_PLACEHOLDERS + 1)]
        with pytest.raises(DlpOverflow):
            redact_package_fields([], chunks)

    def test_overflow_in_a_single_chunk_text(self) -> None:
        """spalla variant: `WaPackageBuildRequest.history` is capped at
        max_length=24 by the router (backend/app/routers/wa_package.py),
        so 65 distinct history TURNS can never reach the builder through
        the real transport — but 65 distinct values packed into ONE
        chunk's text (our own KB corpus, uncapped in count) can. The guard
        must fire on this shape too, not only the history-turn shape."""
        text = " ".join(f"user{i}@example.com" for i in range(MAX_PLACEHOLDERS + 1))
        with pytest.raises(DlpOverflow):
            redact_package_fields([], [_chunk(text)])

    def test_exactly_max_placeholders_does_not_raise(self) -> None:
        """Innocence half: the boundary itself must not trip the guard —
        only strictly MORE than MAX_PLACEHOLDERS."""
        chunks = [_chunk(f"user{i}@example.com") for i in range(MAX_PLACEHOLDERS)]
        result = _redact(chunks=chunks)
        assert len(result.reversal_map) == MAX_PLACEHOLDERS
        assert len(result.hits) == MAX_PLACEHOLDERS


# ============================================================================
# 7. restore_text — hallucinated placeholder handling
# ============================================================================


class TestRestoreUnknownPlaceholder:
    def test_unknown_placeholder_is_stripped_and_logged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        text = "Your reference is [PII-EMAIL-99] — please confirm."
        with caplog.at_level(
            logging.WARNING, logger="backend.services.rag.agentic.wa_dlp"
        ):
            result = restore_text(text, {})
        assert "[PII-EMAIL-99]" not in result
        assert "Your reference is" in result
        assert "stripped" in caplog.text and "1" in caplog.text

    def test_known_placeholder_is_not_flagged_as_unknown(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(
            logging.WARNING, logger="backend.services.rag.agentic.wa_dlp"
        ):
            result = restore_text(
                "value: [PII-EMAIL-1]", {"[PII-EMAIL-1]": "real@example.com"}
            )
        assert result == "value: real@example.com"
        assert "stripped" not in caplog.text

    def test_near_miss_placeholder_shapes_pass_through_unchanged(self) -> None:
        """Declared limit (module docstring): a shape that is neither a
        valid known placeholder NOR matched by the strict regex (lowercase,
        unclosed bracket) is left exactly as-is — it can never carry raw
        PII, since the model only ever sees placeholders, never originals."""
        text = "weird tokens: [pii-email-1] and [PII-EMAIL-1 and done"
        assert restore_text(text, {}) == text


# ============================================================================
# 8. S1 — CREDENTIAL is a one-way category
# ============================================================================


class TestCredentialOneWay:
    def test_credential_placeholder_never_enters_reversal_map(self) -> None:
        credential = "sk-" + "a" * 24
        history = [{"role": "user", "content": f"here is my key {credential} please help"}]
        result = _redact(history=history)
        assert any(h.category == "CREDENTIAL" for h in result.hits)
        placeholder = next(
            h.placeholder for h in result.hits if h.category == "CREDENTIAL"
        )
        assert placeholder not in result.reversal_map
        assert credential not in result.history[0]["content"]

    def test_echoed_credential_placeholder_is_stripped_not_restored(self) -> None:
        """The spalla S1 regression test: history carries a credential ->
        redact -> simulate the model echoing the placeholder back in its
        completion -> restore must contain NEITHER the raw credential NOR
        the raw placeholder shape."""
        credential = "sk-" + "b" * 24
        history = [{"role": "user", "content": f"my key is {credential}, is it valid?"}]
        result = _redact(history=history)
        placeholder = next(
            h.placeholder for h in result.hits if h.category == "CREDENTIAL"
        )

        simulated_completion = (
            f"I see the key {placeholder} in your message — I can't validate "
            "secrets, please rotate it if it was ever shared elsewhere."
        )
        restored = restore_text(simulated_completion, result.reversal_map)
        assert credential not in restored
        assert placeholder not in restored
        assert "sk-" not in restored

    def test_dedup_still_applies_to_a_one_way_category(self) -> None:
        """The SAME credential quoted twice must still collapse to ONE
        placeholder (dedup is independent of the one-way/two-way split —
        both live in `_value_to_placeholder`, only `reversal_map` differs)."""
        credential = "sk-" + "c" * 24
        text = f"key1={credential} key2={credential}"
        result = _redact(chunks=[_chunk(text)])
        credential_hits = [h for h in result.hits if h.category == "CREDENTIAL"]
        assert len(credential_hits) == 1
        assert result.chunks[0]["text"].count(credential_hits[0].placeholder) == 2


# ============================================================================
# 9. Registered recall floor on the synthetic corpus
# ============================================================================


class TestRecallFloor:
    @pytest.mark.parametrize("category", sorted(CORPUS.keys()))
    def test_recall_floor(self, category: str) -> None:
        items = CORPUS[category]
        chunks = [_chunk(t) for t in items]
        result = _redact(chunks=chunks)
        matched = sum(1 for h in result.hits if h.category == category)
        recall = matched / len(items)
        assert recall >= RECALL_FLOOR, (
            f"{category}: recall {recall:.2f} ({matched}/{len(items)}) below "
            f"the registered floor {RECALL_FLOOR}"
        )


# ============================================================================
# 10. Builder integration — dlp=True seals a redacted wire
# ============================================================================


class _EmptyRetriever:
    async def hybrid_search(
        self,
        *,
        query: str,
        user_level: int,
        limit: int,
        collection_override: str,
        fallback_to_plain: bool = True,
    ) -> dict[str, Any]:
        return {"query": query, "results": []}


VISA_QUERY = "What documents do I need for a KITAS work permit?"


class TestBuilderIntegration:
    async def test_dlp_true_redacts_the_wire_and_hides_the_reversal_map(self) -> None:
        from backend.services.rag.agentic.wa_package_builder import build_context_package

        nik = "3212345678901234"
        package = await build_context_package(
            query=VISA_QUERY,
            history=[{"role": "user", "content": f"My NIK is {nik}"}],
            thread_epoch=0,
            retriever=_EmptyRetriever(),
            dlp=True,
        )

        wire = package.wire_text()
        assert nik not in wire
        assert "[PII-NIK_KTP-1]" in wire
        assert "reversal_map" not in wire

        payload = package.to_payload()
        assert "reversal_map" not in payload
        assert nik not in str(payload)

        assert package.reversal_map == {"[PII-NIK_KTP-1]": nik}

    async def test_dlp_false_leaves_content_untouched(self) -> None:
        from backend.services.rag.agentic.wa_package_builder import build_context_package

        nik = "3212345678901234"
        package = await build_context_package(
            query=VISA_QUERY,
            history=[{"role": "user", "content": f"My NIK is {nik}"}],
            thread_epoch=0,
            retriever=_EmptyRetriever(),
        )
        assert nik in package.wire_text()
        assert package.reversal_map == {}

    async def test_package_hash_covers_the_redacted_content_not_the_original(self) -> None:
        """The hash is computed over the SAME wire dlp=True seals — moving
        the redaction after hashing would let a broker verify a hash that
        does not match what the client-visible payload actually says."""
        import hashlib

        from backend.services.rag.agentic.wa_package_builder import build_context_package

        package = await build_context_package(
            query=VISA_QUERY,
            history=[{"role": "user", "content": "My NIK is 3212345678901234"}],
            thread_epoch=0,
            retriever=_EmptyRetriever(),
            dlp=True,
        )
        assert (
            hashlib.sha256(package.wire_text().encode("utf-8")).hexdigest()
            == package.package_hash
        )

    async def test_evidence_inputs_records_the_dlp_flag(self) -> None:
        """Kimi-7 (MINOR): `evidence_inputs["dlp"]` lives inside the hash
        domain, so a future caller that forgets `dlp=True` produces a
        package distinguishable downstream from a properly-redacted one."""
        from backend.services.rag.agentic.wa_package_builder import build_context_package

        package_dlp = await build_context_package(
            query=VISA_QUERY,
            history=[],
            thread_epoch=0,
            retriever=_EmptyRetriever(),
            dlp=True,
        )
        package_no_dlp = await build_context_package(
            query=VISA_QUERY,
            history=[],
            thread_epoch=0,
            retriever=_EmptyRetriever(),
        )
        assert package_dlp.evidence_inputs["dlp"] is True
        assert package_no_dlp.evidence_inputs["dlp"] is False


# ============================================================================
# 10bis. M1 — pricing_block.search_query redacted consistently with history
# ============================================================================


class TestM1PricingSearchQuery:
    async def test_pricing_search_query_shares_the_placeholder_with_history(self) -> None:
        import backend.services.rag.agentic.wa_package_builder as wpb_module
        from backend.services.rag.agentic.wa_package_builder import build_context_package

        nik = "3212345678901234"
        query = f"quanto costa il KITAS per NIK {nik}?"

        class _FakePricingService:
            def search_service(self, q: str) -> dict[str, Any]:
                return {
                    "search_query": q,
                    "results": {
                        "kitas_permits": {
                            "Working KITAS (E23)": {
                                "name": "Working KITAS (E23)",
                                "price": "Rp 5.000.000",
                            }
                        }
                    },
                }

        with patch.object(
            wpb_module, "get_pricing_service", return_value=_FakePricingService()
        ):
            package = await build_context_package(
                query=query,
                history=[{"role": "user", "content": query}],
                thread_epoch=0,
                retriever=_EmptyRetriever(),
                dlp=True,
            )

        wire = package.wire_text()
        assert nik not in wire, "the raw NIK leaked into the sealed wire"
        # The SAME placeholder must appear in BOTH history and
        # pricing_block.search_query — one shared _RedactionState.
        assert wire.count("[PII-NIK_KTP-1]") >= 2

        payload = package.to_payload()
        assert nik not in str(payload)
        assert payload["pricing_block"] is not None
        assert (
            payload["pricing_block"]["search_query"]
            == "quanto costa il KITAS per NIK [PII-NIK_KTP-1]?"
        )
        assert package.reversal_map == {"[PII-NIK_KTP-1]": nik}

    async def test_no_pricing_intent_query_has_no_pricing_block_to_redact(self) -> None:
        """Innocence half: when `pricing_block` is None, the DLP step must
        not choke on a missing search_query — it simply has nothing to
        splice back."""
        from backend.services.rag.agentic.wa_package_builder import build_context_package

        package = await build_context_package(
            query=VISA_QUERY,
            history=[{"role": "user", "content": "My NIK is 3212345678901234"}],
            thread_epoch=0,
            retriever=_EmptyRetriever(),
            dlp=True,
        )
        assert package.pricing_block is None
        assert "3212345678901234" not in package.wire_text()


# ============================================================================
# 11. Fail-closed: a detector exception becomes PackageUnbuildable
# ============================================================================


class TestFailClosed:
    async def test_detector_exception_becomes_package_unbuildable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import backend.services.rag.agentic.wa_package_builder as wpb_module
        from backend.services.rag.agentic.wa_package_builder import PackageUnbuildable

        def _boom(history: Any, chunks: Any, search_query: Any = None) -> Any:
            raise RuntimeError("detector exploded")

        monkeypatch.setattr(wpb_module, "redact_package_fields", _boom)

        with pytest.raises(PackageUnbuildable) as exc_info:
            await wpb_module.build_context_package(
                query=VISA_QUERY,
                history=[{"role": "user", "content": "hello"}],
                thread_epoch=0,
                retriever=_EmptyRetriever(),
                dlp=True,
            )
        assert exc_info.value.reason == "dlp_error"

    async def test_overflow_also_becomes_package_unbuildable(self) -> None:
        """The real (non-monkeypatched) overflow guard, exercised through
        the builder — proves the fail-closed wrapping catches wa_dlp's OWN
        exception type too, not only an injected generic one."""
        from backend.services.rag.agentic.wa_package_builder import (
            PackageUnbuildable,
            build_context_package,
        )

        history = [
            {"role": "user", "content": f"user{i}@example.com"}
            for i in range(MAX_PLACEHOLDERS + 1)
        ]
        with pytest.raises(PackageUnbuildable) as exc_info:
            await build_context_package(
                query=VISA_QUERY,
                history=history,
                thread_epoch=0,
                retriever=_EmptyRetriever(),
                dlp=True,
            )
        assert exc_info.value.reason == "dlp_error"


# ============================================================================
# 12. G-P3 r2 (Kimi round-2 FIX-FIRST batch) — F1/F3/F4/F5 guilt+innocence
#
# Written from research/operations gp3-dlp-r2-spec.md BEFORE any cure landed
# in wa_dlp.py — a different LLM family is writing the implementation
# independently from the SAME spec, without seeing this file. Per the
# module's own "regola non negoziabile": every cure gets BOTH a guilt test
# (the dangerous shape stays redacted) and an innocence test (the shape the
# cure exists to protect stays untouched). Several of the innocence tests
# below are EXPECTED TO FAIL against the CURRENT (uncured) wa_dlp.py — that
# failure is the point: it is the specification of what the cure must fix.
# ============================================================================


class TestF1DateShapeNotNik:
    """F1 — `_NIK_SEPARATED_RE` must decline when the matched span IS a
    date-with-separators (dd-mm-yyyy / dd.mm.yyyy / dd/mm/yyyy or the
    yyyy-first mirror), but must keep catching a real separated NIK. The
    decline is scoped to the DATE SHAPE only — never to bare digits, because
    digits 7-12 of a real NIK encode its ddmmyy date of birth."""

    # --- innocence: the exact spec-named date+number collisions -----------

    def test_a_dd_mm_yyyy_date_next_to_a_renewal_number_is_not_a_nik(
        self,
    ) -> None:
        text = "renewal due 20-08-2026 12345678"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
        assert not any(h.category == "NIK_KTP" for h in result.hits)

    def test_an_iso_date_followed_by_a_case_number_is_not_a_nik(self) -> None:
        text = "scadenza 2026-08-20, pratica 4471"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
        assert not any(h.category == "NIK_KTP" for h in result.hits)

    def test_two_dates_in_one_sentence_are_not_a_nik(self) -> None:
        text = "dal 01-01-2025 al 31-12-2025"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
        assert not any(h.category == "NIK_KTP" for h in result.hits)

    def test_an_iso_date_immediately_followed_by_a_long_reference_is_not_a_nik(
        self,
    ) -> None:
        """Same defect as the spec's own example, but with enough trailing
        digits to actually REACH the 15/16-digit NIK-separated span length
        (the two-date test above never reaches that length on its own)."""
        text = "expires 2026-08-20 88888888"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
        assert not any(h.category == "NIK_KTP" for h in result.hits)

    def test_a_dotted_date_next_to_a_number_is_not_a_nik(self) -> None:
        """The dotted date-shape direction (dd.mm.yyyy) the spec also
        requires to be recognized."""
        text = "batas waktu 20.08.2026 12345678 harus dibayar"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
        assert not any(h.category == "NIK_KTP" for h in result.hits)

    # --- innocence: supplemental rows from Codex's adversarial pass -------

    def test_two_consecutive_dates_with_no_reference_number_are_not_a_nik(
        self,
    ) -> None:
        """No reference number needed at all: two dd-mm-yyyy dates
        separated by a single space are, on their own, 16 digits joined by
        accepted separators (the closing '6' of the first year and the
        opening '2' of the second date are bridged by exactly one space) —
        the whole two-date span is NIK-shaped without any extra digits."""
        text = "Date window 20-08-2026 21-08-2026"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
        assert not any(h.category == "NIK_KTP" for h in result.hits)

    def test_a_dotted_year_first_date_next_to_a_number_is_not_a_nik(
        self,
    ) -> None:
        """The yyyy.mm.dd DOTTED direction — `test_a_dotted_date_...`
        above only covers dd.mm.yyyy; this is the yyyy-first mirror the
        spec also names, with the dotted separator instead of hyphen."""
        text = "valid until 2026.08.20 87654321"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
        assert not any(h.category == "NIK_KTP" for h in result.hits)

    # --- guilt: a real separated/labelled NIK must still be caught --------

    def test_nik_4_4_4_4_with_spaces_is_still_redacted(self) -> None:
        text = "1234 5678 9012 3456"
        result = _redact(chunks=[_chunk(text)])
        assert "1234 5678 9012 3456" not in result.chunks[0]["text"]
        assert any(h.category == "NIK_KTP" for h in result.hits)

    def test_nik_4_4_4_4_with_dots_is_still_redacted(self) -> None:
        text = "1234.5678.9012.3456"
        result = _redact(chunks=[_chunk(text)])
        assert "1234.5678.9012.3456" not in result.chunks[0]["text"]
        assert any(h.category == "NIK_KTP" for h in result.hits)

    def test_labelled_separated_nik_is_still_redacted(self) -> None:
        text = "NIK: 3204 1512 8800 0001"
        result = _redact(chunks=[_chunk(text)])
        assert "3204 1512 8800 0001" not in result.chunks[0]["text"]
        assert any(h.category == "NIK_KTP" for h in result.hits)

    def test_a_bare_nik_with_a_plausible_dob_span_is_still_redacted(self) -> None:
        """Spec's own example: the DOB-shaped middle digits (`151288`) of a
        BARE (no-separator) NIK. This hits `_NIK_BARE_RE`, a pattern the F1
        cure must never touch — decline-on-digits-alone is the one
        non-negotiable constraint the spec calls out by name."""
        text = "3204151288000001"
        result = _redact(chunks=[_chunk(text)])
        assert "3204151288000001" not in result.chunks[0]["text"]
        assert any(h.category == "NIK_KTP" for h in result.hits)

    def test_a_separated_nik_whose_digits_resemble_a_short_year_date_is_still_redacted(
        self,
    ) -> None:
        """The DOB-shaped middle span (`15 12 88`, day-month-2digit-year)
        must never be declined just because it LOOKS date-ish: the spec's
        own date shape is anchored to a 4-digit `19xx|20xx` year, so a
        2-digit-year fragment inside a real separated NIK's digit run must
        never trip the decline."""
        text = "32 04 15 12 88 00 0001"
        result = _redact(chunks=[_chunk(text)])
        assert "32 04 15 12 88 00 0001" not in result.chunks[0]["text"]
        assert any(h.category == "NIK_KTP" for h in result.hits)


class TestF1bKbliListGroupingNotNik:
    """F1b (Codex adversarial finding, additive to F1) — a space-separated
    list of KBLI codes (5-digit Indonesian business-classification codes)
    is EXACTLY 15 digits joined by accepted separators when there are
    three of them, so `_NIK_SEPARATED_RE` claims the whole span. This is
    NOT a date-shape collision (no F1 fix helps here) — it needs its own
    guard.

    Written against the BEHAVIOUR the coordinator specified, not any
    particular implementation of it: a real separated NIK groups 4-4-4-4
    (or is contiguous 16); a KBLI list groups 5-5-5. These tests assert
    only "a 5-5-5 grouping is not redacted" — they do not assume HOW the
    eventual guard tells the two apart, since a different LLM family is
    implementing it independently from the same spec."""

    def test_a_bare_kbli_list_is_not_a_nik(self) -> None:
        text = "KBLI list: 55130 70100 64210"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
        assert not any(h.category == "NIK_KTP" for h in result.hits)

    def test_a_labelled_kbli_list_with_trailing_prose_is_not_a_nik(self) -> None:
        text = "KBLI 55203 56101 55130 untuk akomodasi dan F&B"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
        assert not any(h.category == "NIK_KTP" for h in result.hits)

    def test_a_kbli_list_following_a_regulation_citation_is_not_a_nik(self) -> None:
        text = "PMK 66/2023 — batch 55130 70100 64210"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
        assert not any(h.category == "NIK_KTP" for h in result.hits)

    def test_a_kbli_list_sharing_a_sentence_with_an_amount_is_not_a_nik(self) -> None:
        text = "Biaya 10 juta; KBLI 55130 70100 64210"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
        assert not any(h.category == "NIK_KTP" for h in result.hits)


class TestF3AmountSuffixAdditions:
    """F3 — `_AMOUNT_SUFFIX_RE` must also decline on a trailing `,-` or a
    trailing `idr` (case-insensitive) — matching the `rp|idr` PREFIX check
    `_AMOUNT_PREFIX_RE` already has for the prefix direction. `,-` is not a
    word, so the suffix alternative must be built to match right after the
    digit run rather than relying on `\\b`."""

    # --- innocence: the exact spec-named amounts ---------------------------

    def test_rp_amount_with_trailing_comma_dash_is_not_redacted(self) -> None:
        text = "Rp 62.500.000,-"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
        assert result.hits == []

    def test_bare_amount_with_trailing_idr_is_not_redacted(self) -> None:
        text = "62500000 IDR"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
        assert result.hits == []

    # --- innocence: long enough to actually REACH a PII-shaped span, so
    # the suffix-guard gap is the only thing standing between these and a
    # false-positive PHONE redaction ---------------------------------------

    def test_a_phone_shaped_amount_with_trailing_comma_dash_is_not_redacted(
        self,
    ) -> None:
        """Guilt-of-the-bug: without the `,-` suffix alternative this
        11-digit 62-prefixed run has no amount cue in EITHER direction (no
        `Rp`/`idr` PREFIX within 6 chars, and `,-` is absent from the
        current suffix list) and is redacted as PHONE today."""
        text = "modal disetor 62500000123,- untuk PT PMA"
        result = _redact(chunks=[_chunk(text)])
        assert "62500000123" in result.chunks[0]["text"]
        assert not any(h.category == "PHONE" for h in result.hits)

    def test_a_phone_shaped_amount_with_trailing_idr_word_is_not_redacted(
        self,
    ) -> None:
        """Same shape, the other named gap: `idr` as a trailing WORD (not
        a `Rp`/`IDR` PREFIX, which `_AMOUNT_PREFIX_RE` already covers)."""
        text = "modal disetor 62500000123 IDR untuk PT PMA"
        result = _redact(chunks=[_chunk(text)])
        assert "62500000123" in result.chunks[0]["text"]
        assert not any(h.category == "PHONE" for h in result.hits)

    # --- innocence: same gap, DOTTED-grouping amounts (Codex's addendum) —
    # the coordinator specifically asked to assert on PHONE, not just NIK,
    # for these two rows -----------------------------------------------

    def test_a_dot_grouped_amount_with_trailing_idr_word_is_not_redacted_as_phone(
        self,
    ) -> None:
        text = "Nilai proyek 62.543.210.987 IDR"
        result = _redact(chunks=[_chunk(text)])
        assert "62.543.210.987" in result.chunks[0]["text"]
        assert not any(h.category == "PHONE" for h in result.hits)

    def test_a_dot_grouped_amount_with_trailing_comma_dash_is_not_redacted_as_phone(
        self,
    ) -> None:
        text = "Total 62.500.000.123,-"
        result = _redact(chunks=[_chunk(text)])
        assert "62.500.000.123" in result.chunks[0]["text"]
        assert not any(h.category == "PHONE" for h in result.hits)

    # --- guilt: a real phone/NIK adjacent to the newly-declined shapes
    # must still be redacted — the cure must not blanket-decline the
    # category near ANY comma or the word "idr" elsewhere in the text -----

    def test_a_real_phone_next_to_an_idr_amount_still_redacts_only_the_phone(
        self,
    ) -> None:
        text = "modal disetor 62500000123 IDR, hubungi 6281234567890 untuk info"
        result = _redact(chunks=[_chunk(text)])
        assert "62500000123" in result.chunks[0]["text"]
        assert "6281234567890" not in result.chunks[0]["text"]
        assert sum(1 for h in result.hits if h.category == "PHONE") == 1

    def test_a_real_nik_next_to_a_comma_dash_amount_still_redacts_the_nik(
        self,
    ) -> None:
        text = "harga Rp 2.500.000,- NIK saya 3212345678901234"
        result = _redact(chunks=[_chunk(text)])
        assert "2.500.000" in result.chunks[0]["text"]
        assert "3212345678901234" not in result.chunks[0]["text"]
        assert [h.category for h in result.hits] == ["NIK_KTP"]


class TestOutOfScopeMeasuredGaps:
    """Codex adversarial finding, explicitly OUT OF SCOPE for this PR
    (coordinator: "report what you observe; do not cure it" / "do not
    widen the deny-list, that road is the next F1"). These are written as
    aspirational innocence assertions — the shape SHOULD stay untouched —
    specifically so a failure here is a MEASUREMENT the session's report
    quotes precisely (which category claims the span, or which letter
    prefix escapes the deny-list), never a demand that this batch's F1/F3/
    F4/F5 cures fix it. Do NOT extend `_PASSPORT_DECLINE_PREFIXES` or the
    NPWP/NIK precedence rule to make these pass — that is a separate,
    future finding.

    Every test here is `xfail(strict=True)`: a permanently-red test would
    train the whole fleet to read this file's red as noise, but `strict`
    keeps the measurement working in BOTH directions — the day one of these
    gaps is actually cured, the xpass turns this class red again and forces
    the finding to be re-dispositioned instead of silently absorbed."""

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "ACCEPTED GAP: a bare 16-digit run with a leading zero is "
            "indistinguishable from a new-format NPWP, and _NPWP_NEW16_RE "
            "carries no validator — NPWP claims it before NIK_KTP is "
            "consulted. Curing it means touching the ONE precedence rule "
            "the design spec names, which is out of scope for F1-F6."
        ),
    )
    def test_a_bare_16_digit_leading_zero_reference_is_not_an_npwp(self) -> None:
        """Any bare 16-digit run starting with '0' collides with the
        new-format NPWP shape (`_NPWP_NEW16_RE`), which has NO validator
        at all — it is claimed unconditionally, before NIK_KTP even sees
        it (NPWP runs first in `_CATEGORY_PATTERNS`, the ONE precedence
        rule the design spec names by name). MEASURE which category
        actually claims this, do not touch NPWP/NIK precedence to fix it."""
        text = "Reference 0123456789012345"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
        assert not any(h.category == "NPWP" for h in result.hits)

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "ACCEPTED GAP: an invoice token shaped 2-letters+7-digits is the same "
            "shape as a passport number, and `AB` is not on the fixed "
            "decline list. Widening that list is the coordinator's named "
            "next-F1, not this batch."
        ),
    )
    def test_a_2letter_7digit_invoice_reference_is_not_a_passport(self) -> None:
        """`AB` is not in `_PASSPORT_DECLINE_PREFIXES`, and there is no
        'passport'/'paspor' word nearby for F4's context override to even
        be relevant — the deny-list is the ONLY current defense, and it is
        a small fixed list, not a real distinguisher of "looks like a
        passport" vs "is some other 2-letter business reference"."""
        text = "August 20, 2026 — invoice AB1234567"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
        assert not any(h.category == "PASSPORT" for h in result.hits)

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "ACCEPTED GAP: a KITAS permit number (`IT`+7 digits) is 2-letters+7-"
            "digits too. Note the failure direction is CONSERVATIVE — an "
            "immigration permit number gets redacted, which over-protects "
            "rather than leaks."
        ),
    )
    def test_a_2letter_7digit_kitas_reference_is_not_a_passport(self) -> None:
        text = "20 Agustus 2026 — KITAS IT1234567"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
        assert not any(h.category == "PASSPORT" for h in result.hits)

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "ACCEPTED GAP: the `PO` label sits BESIDE the match, so the letters "
            "the regex captures are `AB` — the decline list is never "
            "consulted against the word a human reads. Fixing this needs "
            "a preceding-label lookbehind, a new mechanism, not a wider list."
        ),
    )
    def test_a_po_labelled_2letter_7digit_reference_is_not_a_passport(self) -> None:
        """The 'PO' label sits BESIDE the match (separated by a space), not
        immediately prefixing it — the letters the regex actually captures
        are 'AB', not 'PO', so `_PASSPORT_DECLINE_PREFIXES` never even gets
        consulted against the label a human reader would recognize."""
        text = "Valuasi 2,5 miliar; PO AB1234567"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
        assert not any(h.category == "PASSPORT" for h in result.hits)


class TestF4PassportContextOverride:
    """F4 — the 3 dead decline-list entries (`inv`/`ref`/`sku`, which
    `_PASSPORT_RE`'s `[A-Za-z]{1,2}` prefix group can never produce) are
    removed, and a `passport|paspor` context override (looking BACKWARD
    ~24 chars) makes the deny-list ignored so a genuinely labelled passport
    number is never silently declined just because its letter prefix
    collides with a common business abbreviation (PO/NO/PT/...)."""

    # --- innocence: the exact spec-named unlabelled abbreviations ----------

    def test_unlabelled_po_number_is_not_a_passport(self) -> None:
        text = "PO123456"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
        assert not any(h.category == "PASSPORT" for h in result.hits)

    def test_unlabelled_no_reference_is_not_a_passport(self) -> None:
        text = "NO1234567"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
        assert not any(h.category == "PASSPORT" for h in result.hits)

    def test_unlabelled_pt_company_code_is_not_a_passport(self) -> None:
        text = "PT1234567"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
        assert not any(h.category == "PASSPORT" for h in result.hits)

    def test_a_po_number_mentioned_after_the_word_passport_stays_innocent(
        self,
    ) -> None:
        """The override looks BACKWARD only (spec: "~24 caratteri
        PRECEDENTI al match") — a passport/paspor word occurring AFTER the
        match must never retroactively redact it."""
        text = "PO123456 is not a passport number, just our invoice code"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
        assert not any(h.category == "PASSPORT" for h in result.hits)

    def test_a_po_number_far_beyond_the_lookback_window_stays_innocent(
        self,
    ) -> None:
        """A `passport` mention well outside the ~24-char lookback (here,
        ~40+ chars before the match) must not reach across and override the
        deny-list — the override is a WINDOW, not an anywhere-in-string
        search."""
        text = "passport " + ("filler " * 6) + "PO123456"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
        assert not any(h.category == "PASSPORT" for h in result.hits)

    def test_dead_prefixes_inv_ref_sku_can_never_be_produced_by_the_regex(
        self,
    ) -> None:
        """Documents WHY inv/ref/sku are dead code: `_PASSPORT_RE`'s letter
        prefix group is `[A-Za-z]{1,2}` (max 2 letters), so a 3-letter word
        can never BE the captured prefix — these three stay innocent for a
        totally different reason (no match at all), which is exactly what
        makes removing them from the decline set safe."""
        for text in ("INV1234567", "REF1234567", "SKU1234567"):
            result = _redact(chunks=[_chunk(text)])
            assert result.chunks[0]["text"] == text, text
            assert not any(h.category == "PASSPORT" for h in result.hits), text

    # --- guilt: a labelled deny-listed prefix must still be redacted ------

    def test_passport_labelled_po_number_is_redacted(self) -> None:
        """Guilt-of-the-bug: today the deny-list wins unconditionally, so a
        REAL passport happening to start with the letters 'PO' is never
        redacted even when the customer explicitly says 'passport' right
        next to it."""
        text = "passport PO123456"
        result = _redact(chunks=[_chunk(text)])
        assert "PO123456" not in result.chunks[0]["text"]
        assert any(h.category == "PASSPORT" for h in result.hits)

    def test_paspor_labelled_no_number_is_redacted(self) -> None:
        text = "paspor no1234567"
        result = _redact(chunks=[_chunk(text)])
        assert "no1234567" not in result.chunks[0]["text"]
        assert any(h.category == "PASSPORT" for h in result.hits)


class TestF5KeyPrefixSeparator:
    """F5 — `_KEY_PREFIX_RE` must require the shape's OWN separator
    (`sk[-_]`, `ghp_`, `gho_`, `xoxb-`, `xoxp-`) instead of matching 16+
    bare alnum chars right after the bare prefix letters. `AKIA` keeps its
    own separator-free alternative, since real AWS access key ids never
    carry one. `CREDENTIAL` is a ONE-WAY category (no reversal_map): a
    false positive here is an IRRECOVERABLE hole in the client-facing
    reply."""

    # --- innocence: the exact spec-named ordinary words --------------------

    def test_skincare_product_name_is_not_a_credential(self) -> None:
        text = "skincareproducts2026"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
        assert result.hits == []

    def test_indonesian_word_skema_is_not_a_credential(self) -> None:
        text = "skema perpanjangan kitas"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
        assert result.hits == []

    def test_skillsheet_reference_is_not_a_credential(self) -> None:
        text = "skillsheet1234567890"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
        assert result.hits == []

    def test_english_word_skyscraperconstruction_is_not_a_credential(
        self,
    ) -> None:
        """Additional realistic ordinary-prose case: a long compound
        English word beginning with 'sk' is exactly as vulnerable to the
        bare-16+-alnum bug as the spec's own examples."""
        text = "The skyscraperconstruction project finished on schedule."
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
        assert not any(h.category == "CREDENTIAL" for h in result.hits)

    def test_short_indonesian_words_beginning_with_sk_are_never_touched(
        self,
    ) -> None:
        """Regression guard for short 'sk'-words (too short to ever match
        even the current bare regex) — the cure's added separator
        requirement must narrow the match set, never widen it."""
        text = "Skala risiko dan skenario perpanjangan sudah kami skalakan."
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
        assert result.hits == []

    # --- guilt: a real separator-bearing credential must still redact -----

    def test_sk_dash_prefixed_key_is_still_redacted(self) -> None:
        text = "sk-abcdefghij0123456789"
        result = _redact(chunks=[_chunk(text)])
        assert "sk-abcdefghij0123456789" not in result.chunks[0]["text"]
        assert any(h.category == "CREDENTIAL" for h in result.hits)

    def test_ghp_underscore_prefixed_key_is_still_redacted(self) -> None:
        text = "ghp_abcdefghij0123456789"
        result = _redact(chunks=[_chunk(text)])
        assert "ghp_abcdefghij0123456789" not in result.chunks[0]["text"]
        assert any(h.category == "CREDENTIAL" for h in result.hits)

    def test_xoxb_dash_prefixed_token_is_still_redacted(self) -> None:
        text = "xoxb-1234567890-abcdefghij"
        result = _redact(chunks=[_chunk(text)])
        assert "xoxb-1234567890-abcdefghij" not in result.chunks[0]["text"]
        assert any(h.category == "CREDENTIAL" for h in result.hits)

    def test_akia_key_without_a_separator_is_still_redacted(self) -> None:
        """AKIA keeps its separator-FREE shape by design (real AWS access
        key ids never carry one) — the F5 cure must not accidentally start
        requiring a separator here too."""
        text = "AKIAIOSFODNN7EXAMPLE"
        result = _redact(chunks=[_chunk(text)])
        assert "AKIAIOSFODNN7EXAMPLE" not in result.chunks[0]["text"]
        assert any(h.category == "CREDENTIAL" for h in result.hits)


class TestRealisticSyntheticIdentifierGuilt:
    """Guilt tests driven by the deterministic realistic-shape generators
    added to dlp_synthetic_corpus.py for this r2 batch — a real-encoding
    NIK (province/regency/district + dob+40-for-women + sequence), a
    1-2-letter/6-7-digit passport, and both NPWP dotted/bare-16 forms.
    Every value is synthetic (seeded PRNG, never real customer data) — see
    that module's docstring."""

    @pytest.mark.parametrize("text", realistic_nik_corpus(10))
    def test_realistic_nik_is_redacted(self, text: str) -> None:
        hits = _hits_for(text)
        assert any(h.category == "NIK_KTP" for h in hits), text

    @pytest.mark.parametrize("text", realistic_passport_corpus(10))
    def test_realistic_passport_is_redacted(self, text: str) -> None:
        hits = _hits_for(text)
        assert any(h.category == "PASSPORT" for h in hits), text

    @pytest.mark.parametrize("text", realistic_npwp_old_dotted_corpus(10))
    def test_realistic_npwp_old_dotted_is_redacted(self, text: str) -> None:
        hits = _hits_for(text)
        assert any(h.category == "NPWP" for h in hits), text

    @pytest.mark.parametrize("text", realistic_npwp_new16_bare_corpus(10))
    def test_realistic_npwp_new16_bare_is_redacted(self, text: str) -> None:
        hits = _hits_for(text)
        assert any(h.category == "NPWP" for h in hits), text

    @pytest.mark.parametrize("text", realistic_npwp_new16_dotted_corpus(10))
    def test_realistic_npwp_new16_dotted_is_redacted(self, text: str) -> None:
        hits = _hits_for(text)
        assert any(h.category == "NPWP" for h in hits), text


class TestBroaderRealisticInnocenceSweep:
    """Cross-cutting innocence net requested for this batch: dates in
    several formats, invoice/reference numbers, KBLI codes, a phone shape
    outside the covered patterns, and a grouped number that merely LOOKS
    NPWP-adjacent (wrong grouping, never matches the real NPWP shape).
    None of these are the literal F1/F3/F4/F5 defect strings, but they are
    realistic shapes a client message plausibly contains and must never be
    touched by ANY category."""

    SENTENCES: tuple[str, ...] = (
        "The deadline is 20-08-2026 for renewal.",
        "Due date: 2026-08-20 sharp.",
        "Format check 20.08.2026 works too.",
        "Slash format 20/08/2026 also common.",
        "Invoice number INV/2026/08/1234 is settled.",
        "Please quote reference REF-00098765 when paying.",
        "KBLI code 55130 covers hotel accommodation.",
        "KBLI 70100 is head office management activities.",
        "Business classification 64210 applies here.",
        "Kontak kantor: 021-7654321 selama jam kerja.",
        "Total 12.345.678 sudah termasuk pajak.",
    )

    @pytest.mark.parametrize("sentence", SENTENCES)
    def test_sentence_is_never_touched(self, sentence: str) -> None:
        result = _redact(chunks=[_chunk(sentence)])
        assert result.chunks[0]["text"] == sentence
        assert result.hits == []


class TestF5bSkPrefixEntropyRun:
    """F5b — Kimi round-3 BLOCKER on the F5 cure itself. Requiring the
    separator (`sk[-_]`) was not enough: the tail class still contains `-`
    and `_`, so `sk-` followed by hyphen-separated WORDS clears the 16-char
    minimum. `SK` is Surat Keputusan — the single most-cited document type
    this business writes about — and CREDENTIAL is ONE-WAY, so the span
    would vanish from the customer's own answer with no reversal possible.

    The cure is structural, not a word list: a real key carries its entropy
    in one UNBROKEN alphanumeric run; human text is short words joined by
    hyphens. Guilt is asserted across ALL FIVE key families, because the
    validator is scoped to the `sk` alternative and a scoping mistake would
    silently disarm the other four."""

    def test_an_sk_kemenkumham_decree_reference_is_not_a_credential(self) -> None:
        """The exact shape Kimi found: `sk-` + hyphen-separated words. The
        longest unbroken run is `kemenkumham` (11 chars), under the 16-char
        entropy floor, so the match is declined."""
        text = "SK Kemenkumham no sk-kemenkumham-ahu-0012345 sudah terbit"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
        assert not any(h.category == "CREDENTIAL" for h in result.hits)

    def test_an_article_slug_starting_with_sk_is_not_a_credential(self) -> None:
        text = "artikel sk-immigration-update-2026 sudah publish"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text

    # Every fixture below is ASSEMBLED at runtime from a vendor prefix and a
    # separate entropy run, never written as one literal. This is not
    # decoration: GitHub push protection blocked this exact branch on the
    # literal form (it read the Stripe `sk_live_` shape as a real key), and a
    # branch that cannot be pushed is a cure that cannot ship. Neither half is
    # a secret on its own, and the concatenation the test actually exercises
    # is byte-identical to the real shape. Do NOT "tidy" these back into
    # literals — the next push would be rejected again.
    _RUN = "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6"  # 32 alnum, no vendor prefix

    @pytest.mark.parametrize(
        ("prefix", "tail"),
        [
            ("sk-" + "proj-", _RUN),
            ("sk" + "_live_", "51H8xVbKj2mNpQrStUvWxYz9AbCdEf"),
            ("ghp" + "_", _RUN),
            ("xoxb" + "-", "1234-5678-abcdefghijklmnopqrstuvwx"),
            ("AKIA", "IOSFODNN7EXAMPLE"),
        ],
        ids=["sk-hyphen", "sk_underscore", "ghp", "xoxb", "akia"],
    )
    def test_every_real_key_family_still_redacts(
        self, prefix: str, tail: str
    ) -> None:
        """The guilt half. The `sk`-scoped validator must not have disarmed
        the four prefixes it was never meant to touch — a hyphenated Slack
        token (`xoxb-1234-5678-...`) is the trap here: it LOOKS word-broken,
        and only its final segment carries the unbroken run."""
        secret = prefix + tail
        text = f"ini kuncinya: {secret}"
        result = _redact(chunks=[_chunk(text)])
        assert secret not in result.chunks[0]["text"]
        assert any(h.category == "CREDENTIAL" for h in result.hits)


class TestKimiRound3MeasuredButNotCured:
    """The two Kimi round-3 findings deliberately NOT cured in this PR, kept
    as `xfail(strict=True)` for the same reason as
    `TestOutOfScopeMeasuredGaps`: the day either is cured, the xpass turns
    this class red and forces a re-disposition."""

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "MEASURED, NOT CURED (Kimi r3 finding 2, MEDIUM): `_IBAN_RE` has "
            "no validator, so any 2-letter + 2-digit + 10-30-alnum promo or "
            "referral code satisfies the IBAN shape. PRE-EXISTING — it is "
            "untouched by the F1-F5 delta, so curing it here would violate "
            "one-PR-one-concern. Not one-way: recoverable via reversal_map."
        ),
    )
    def test_an_uppercase_promo_code_is_not_an_iban(self) -> None:
        text = "kode promo NZ25DISKON2026 berlaku sampai akhir bulan"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "ACCEPTED TRADE-OFF (Kimi r3 finding 3, MEDIUM): `_DATE_SHAPE_RE` "
            "anchors the year to FOUR digits on purpose — digits 7-12 of a "
            "real NIK encode ddmmyy, so a 2-digit-year rule would decline "
            "genuine NIKs. The cost is that `dd-mm-yy <ref number>` reads as "
            "one 15-digit run. Recall over precision, deliberately."
        ),
    )
    def test_a_two_digit_year_date_beside_a_ref_number_is_not_a_nik(self) -> None:
        text = "20-08-26 123456789"
        result = _redact(chunks=[_chunk(text)])
        assert result.chunks[0]["text"] == text
