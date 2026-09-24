"""
Unit tests for language_detector
Target: >95% coverage
"""

import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.communication.language_detector import (
    detect_language,
    get_language_instruction,
)


class TestLanguageDetector:
    """Tests for language detection"""

    def test_detect_language_empty(self):
        """Test detecting language from empty text"""
        result = detect_language("")
        assert result == "it"  # Default to Italian

    def test_detect_language_italian(self):
        """Test detecting Italian"""
        result = detect_language("Ciao, come posso aiutarti?")
        assert result == "it"

    def test_detect_language_english(self):
        """Test detecting English"""
        result = detect_language("Hello, how can I help you?")
        assert result == "en"

    def test_detect_language_indonesian(self):
        """Test detecting Indonesian"""
        result = detect_language("Apa yang bisa saya bantu?")
        assert result == "id"

    def test_detect_language_ukrainian(self):
        """Test detecting Ukrainian"""
        result = detect_language("Привіт, як справи?")
        assert result == "uk"

    def test_detect_language_russian(self):
        """Test detecting Russian"""
        result = detect_language("Привет, как дела?")
        assert result == "ru"

    def test_detect_language_no_markers(self):
        """Test detecting language with no markers"""
        result = detect_language("123456789")
        assert result == "auto"

    def test_detect_language_mixed(self):
        """A message with one marker per language is a three-way tie — the
        scoring rule treats tied evidence as unreliable and returns 'auto'
        rather than picking one arbitrarily (2026-09-25 recall fix)."""
        result = detect_language("Ciao hello apa")
        assert result == "auto"

    def test_get_language_instruction_italian(self):
        """Test getting language instruction for Italian"""
        instruction = get_language_instruction("it")
        assert isinstance(instruction, str)
        assert len(instruction) > 0

    def test_get_language_instruction_english(self):
        """Test getting language instruction for English"""
        instruction = get_language_instruction("en")
        assert isinstance(instruction, str)
        assert len(instruction) > 0

    def test_get_language_instruction_indonesian(self):
        """Test getting language instruction for Indonesian"""
        instruction = get_language_instruction("id")
        assert isinstance(instruction, str)
        assert len(instruction) > 0

    def test_get_language_instruction_ukrainian(self):
        """Test getting language instruction for Ukrainian"""
        instruction = get_language_instruction("uk")
        assert isinstance(instruction, str)
        assert len(instruction) > 0

    def test_get_language_instruction_russian(self):
        """Test getting language instruction for Russian"""
        instruction = get_language_instruction("ru")
        assert isinstance(instruction, str)
        assert len(instruction) > 0

    def test_get_language_instruction_auto(self):
        """Test getting language instruction for auto"""
        instruction = get_language_instruction("auto")
        assert isinstance(instruction, str)
        assert len(instruction) > 0

    def test_get_language_instruction_unknown(self):
        """Test getting language instruction for unknown language"""
        instruction = get_language_instruction("unknown")
        assert isinstance(instruction, str)
        assert len(instruction) > 0

    def test_detect_language_italian_markers(self):
        """Test detecting Italian with various markers"""
        assert detect_language("Ciao come stai?") == "it"
        assert detect_language("Cosa vuoi?") == "it"
        assert detect_language("Grazie per l'aiuto") == "it"
        assert detect_language("Quando posso venire?") == "it"

    def test_detect_language_english_markers(self):
        """Test detecting English with various markers"""
        assert detect_language("Hello how are you?") == "en"
        assert detect_language("What can I do?") == "en"
        assert detect_language("Please help me") == "en"
        assert detect_language("Why is this?") == "en"

    def test_detect_language_indonesian_markers(self):
        """Test detecting Indonesian with various markers"""
        assert detect_language("Apa yang bisa saya bantu?") == "id"
        assert detect_language("Bagaimana caranya?") == "id"
        assert detect_language("Saya mau tahu") == "id"
        assert detect_language("Bisa tolong?") == "id"

    def test_detect_language_ukrainian_markers(self):
        """Test detecting Ukrainian"""
        assert detect_language("Привіт як справи?") == "uk"
        assert detect_language("Дякую за допомогу") == "uk"

    def test_detect_language_russian_markers(self):
        """Test detecting Russian"""
        assert detect_language("Привет как дела?") == "ru"
        assert detect_language("Спасибо за помощь") == "ru"

    def test_detect_language_tie_breaker(self):
        """Test language detection with equal scores"""
        # If multiple languages have same score, should return one of them
        result = detect_language("ciao hello")
        assert result in ["it", "en", "id", "uk", "ru", "auto"]

    def test_detect_language_word_boundaries(self):
        """Test that word boundaries work correctly"""
        # Should not match "ciao" in "ciaos" (if word boundary works)
        assert detect_language("ciao") == "it"
        # But should still match if it's a word
        assert detect_language("say ciao") == "it"

    def test_get_language_instruction_ua_alias(self):
        """Test that 'ua' maps to Ukrainian instruction"""
        instruction = get_language_instruction("ua")
        assert isinstance(instruction, str)
        assert "УКРАЇНСЬКА" in instruction or "ukrainian" in instruction.lower()

    def test_get_language_instruction_contains_expected_content(self):
        """Test that instructions contain expected content"""
        it_inst = get_language_instruction("it")
        assert "ITALIANO" in it_inst or "italian" in it_inst.lower()
        assert "ZANTARA" in it_inst

        en_inst = get_language_instruction("en")
        assert "ENGLISH" in en_inst or "english" in en_inst.lower()
        assert "ZANTARA" in en_inst

        id_inst = get_language_instruction("id")
        assert "INDONESIA" in id_inst or "indonesia" in id_inst.lower()
        assert "ZANTARA" in id_inst

    def test_detect_language_none_text(self):
        """Test detecting language with None text"""
        result = detect_language(None)
        assert result == "it"  # Default to Italian

    def test_detect_language_special_characters(self):
        """Test detecting language with special characters"""
        assert detect_language("Ciao! Come stai?") == "it"
        assert detect_language("Hello! How are you?") == "en"

    # --- 2026-09-25 recall fix: guilt (ordinary phrasing the OLD marker
    # list missed and returned 'auto' on) + innocence (must NOT flip to a
    # real language when it shouldn't) synthetic sentences. All sentences
    # below are written for this test, not taken from any real message. ---

    def test_guilt_italian_ordinary_price_question(self):
        """'Quanto costa il KITAS investor?' had zero markers in the old
        list (only 'ciao'/'come'/'cosa'/'sono'/'voglio'/'posso'/'grazie'/
        'quando'/'dove'/'perché') and returned 'auto'."""
        assert detect_language("Quanto costa il KITAS investor?") == "it"

    def test_guilt_english_ordinary_document_question(self):
        """'Which documents do I need for the company?' had zero markers
        in the old English list and returned 'auto'."""
        assert detect_language("Which documents do I need for the company?") == "en"

    def test_guilt_indonesian_ordinary_penalty_question(self):
        """'Klien belum lapor pajak bulan ini, berapa dendanya?' has none
        of the old Indonesian markers (apa/bagaimana/siapa/dimana/kapan/
        mengapa/saya/kamu/bisa/mau/terima/kasih/bantuan/bantuannya) and
        returned 'auto'."""
        assert detect_language("Klien belum lapor pajak bulan ini, berapa dendanya?") == "id"

    def test_guilt_ukrainian_script_decides_without_old_markers(self):
        """'Скільки коштує послуга KITAS?' contains none of the old
        Ukrainian substring markers but has the Ukrainian-only letter 'і'
        ('Скільки') — script alone now decides."""
        assert detect_language("Скільки коштує послуга KITAS?") == "uk"

    def test_guilt_russian_script_decides_without_old_markers(self):
        """'Сколько документов нужно для визы?' contains none of the old
        Russian substring markers but has the Russian-only letter 'ы'
        ('визы') — script alone now decides."""
        assert detect_language("Сколько документов нужно для визы?") == "ru"

    def test_innocence_english_with_italian_loanword_stays_english(self):
        """A loanword ('cappuccino') must not flip an otherwise-English
        sentence to Italian — none of the Italian function-word markers
        appear, only the borrowed noun."""
        assert (
            detect_language("I would like a cappuccino and my invoice, please.") == "en"
        )

    def test_innocence_mixed_language_stays_auto(self):
        """One marker per language is tied evidence, not a verdict."""
        assert detect_language("Ciao hello, mau tanya something") == "auto"

    def test_innocence_very_short_stays_auto(self):
        """Short, generic, or content-free strings never had — and still
        don't have — enough evidence to name a language."""
        assert detect_language("ok") == "auto"
        assert detect_language("?") == "auto"
        assert detect_language("\U0001f44d") == "auto"  # thumbs-up emoji

    def test_innocence_indonesian_with_english_tech_words_stays_id(self):
        """Business/tech loanwords ('setup', 'virtual office') must not
        flip an Indonesian-grammar sentence to English."""
        assert (
            detect_language("Klien mau setup PT PMA pakai virtual office, apa boleh?")
            == "id"
        )

    def test_detect_language_elongated_greeting_still_italian(self):
        """WhatsApp-style elongated vowels ('ciaooo') used to defeat the
        exact-word 'ciao' marker outright."""
        assert detect_language("ciaooo") == "it"
        assert detect_language("ciaoooo") == "it"

    def test_detect_language_perche_without_accent(self):
        """WA clients routinely drop the accent on 'perché'."""
        assert detect_language("non capisco perche") == "it"
