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
