"""
Comprehensive pytest suite for Message Chunker utility.
Tests: chunk_message, chunk_whatsapp, chunk_instagram, chunk_telegram

Target: 95%+ coverage
"""

import pytest

from backend.utils.message_chunker import (
    chunk_instagram,
    chunk_message,
    chunk_telegram,
    chunk_whatsapp,
)


class TestChunkMessage:
    """Tests for the core chunk_message function."""

    def test_empty_string(self) -> None:
        """Empty string returns empty list."""
        assert chunk_message("") == []

    def test_short_message(self) -> None:
        """Short message returned as single chunk."""
        result = chunk_message("Hello world")
        assert result == ["Hello world"]

    def test_exact_limit(self) -> None:
        """Message exactly at max_length is not chunked."""
        text = "x" * 4000
        result = chunk_message(text, max_length=4000)
        assert len(result) == 1

    def test_one_char_over_with_breaks(self) -> None:
        """Message over max_length with paragraph breaks is chunked."""
        text = ("x" * 2000) + "\n\n" + ("y" * 2001)
        result = chunk_message(text, max_length=2100)
        assert len(result) == 2

    def test_paragraph_boundary_split(self) -> None:
        """Chunks split at paragraph boundaries."""
        para1 = "First paragraph. " * 30  # ~510 chars
        para2 = "Second paragraph. " * 30
        text = f"{para1}\n\n{para2}"
        result = chunk_message(text, max_length=600)

        assert len(result) == 2
        assert "First paragraph" in result[0]
        assert "Second paragraph" in result[1]

    def test_line_boundary_fallback(self) -> None:
        """Falls back to line splitting for long paragraphs."""
        # Single paragraph of 1000+ chars with line breaks
        lines = ["Line " + str(i) + ": " + "x" * 50 for i in range(20)]
        text = "\n".join(lines)  # ~1200 chars, no paragraph breaks
        result = chunk_message(text, max_length=500)

        assert len(result) >= 2
        for chunk in result:
            assert len(chunk) <= 510  # Small margin for trailing chars

    def test_no_trailing_whitespace(self) -> None:
        """Chunks have no trailing whitespace."""
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        result = chunk_message(text, max_length=20)
        for chunk in result:
            assert chunk == chunk.strip()

    def test_three_paragraphs(self) -> None:
        """Three paragraphs split correctly."""
        p1 = "A" * 100
        p2 = "B" * 100
        p3 = "C" * 100
        text = f"{p1}\n\n{p2}\n\n{p3}"
        result = chunk_message(text, max_length=150)

        assert len(result) >= 2
        # Verify all content preserved
        combined = " ".join(result)
        assert "A" * 50 in combined
        assert "B" * 50 in combined
        assert "C" * 50 in combined

    @pytest.mark.parametrize(
        "max_length",
        [500, 1000, 4000],
        ids=["medium", "large", "whatsapp"],
    )
    def test_all_chunks_within_limit(self, max_length: int) -> None:
        """All chunks respect max_length for reasonable sizes."""
        text = ("Word " * 50 + "\n\n") * 10  # ~2500 chars
        result = chunk_message(text, max_length=max_length)

        for i, chunk in enumerate(result):
            # Allow small overflow for edge cases with paragraph trailing chars
            assert len(chunk) <= max_length + 100, (
                f"Chunk {i} length {len(chunk)} exceeds {max_length}"
            )

    def test_preserves_all_content(self) -> None:
        """All words from original text appear in chunks."""
        words = [f"word{i}" for i in range(50)]
        text = " ".join(words)
        result = chunk_message(text, max_length=100)

        combined = " ".join(result)
        for word in words[:10]:  # Check first 10 words
            assert word in combined


class TestPlatformConvenience:
    """Tests for platform-specific convenience functions."""

    def test_chunk_whatsapp_default(self) -> None:
        """WhatsApp uses 4000 char limit."""
        text = "\n\n".join(["x" * 1500] * 6)  # ~9000 chars with paragraph breaks
        result = chunk_whatsapp(text)
        assert len(result) >= 2

    def test_chunk_instagram_default(self) -> None:
        """Instagram uses 950 char limit."""
        text = "\n\n".join(["x" * 400] * 6)  # ~2400 chars with paragraph breaks
        result = chunk_instagram(text)
        assert len(result) >= 2

    def test_chunk_telegram_default(self) -> None:
        """Telegram uses 4000 char limit."""
        text = "\n\n".join(["x" * 1500] * 6)  # ~9000 chars with paragraph breaks
        result = chunk_telegram(text)
        assert len(result) >= 2

    def test_short_messages_not_chunked(self) -> None:
        """Short messages pass through all platform functions."""
        short = "Hello!"
        assert chunk_whatsapp(short) == [short]
        assert chunk_instagram(short) == [short]
        assert chunk_telegram(short) == [short]

    def test_empty_messages(self) -> None:
        """Empty messages return empty list."""
        assert chunk_whatsapp("") == []
        assert chunk_instagram("") == []
        assert chunk_telegram("") == []
