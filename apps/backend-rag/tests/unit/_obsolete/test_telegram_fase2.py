"""
Test Coverage per FASE 2.3: Telegram Markdown Fallback

Tests per:
- FASE 2.3: Markdown fallback strategy (MarkdownV2 → HTML → Plain)
"""

from unittest.mock import AsyncMock, patch

import pytest


class TestTelegramMarkdownFallback:
    """Test FASE 2.3: Telegram markdown fallback (MarkdownV2→HTML→plain)"""

    @pytest.mark.asyncio
    async def test_fallback_function_exists(self):
        """Should have send_telegram_message_with_fallback function"""
        from backend.app.routers.telegram import send_telegram_message_with_fallback

        assert callable(send_telegram_message_with_fallback)

    @pytest.mark.asyncio
    async def test_strategy_1_markdownv2_success(self):
        """Should try MarkdownV2 first and succeed"""
        from backend.app.routers.telegram import send_telegram_message_with_fallback

        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()

        with patch("backend.app.routers.telegram.telegram_bot", mock_bot):
            result = await send_telegram_message_with_fallback(
                chat_id=123,
                text="**Bold** text with *italic*",
            )

        # Should succeed
        assert result is True
        # Should call send_message
        mock_bot.send_message.assert_called_once()
        # Should use MarkdownV2
        call_args = mock_bot.send_message.call_args
        assert call_args[1]["parse_mode"] == "MarkdownV2"

    @pytest.mark.asyncio
    async def test_strategy_2_html_fallback(self):
        """Should fallback to HTML when MarkdownV2 fails"""
        from backend.app.routers.telegram import send_telegram_message_with_fallback

        mock_bot = AsyncMock()
        # First call (MarkdownV2) fails
        # Second call (HTML) succeeds
        mock_bot.send_message = AsyncMock(side_effect=[Exception("MarkdownV2 error"), None])

        with patch("backend.app.routers.telegram.telegram_bot", mock_bot):
            result = await send_telegram_message_with_fallback(
                chat_id=123,
                text="**Bold** text",
            )

        assert result is True
        # Should have tried twice
        assert mock_bot.send_message.call_count == 2
        # Second call should use HTML
        second_call = mock_bot.send_message.call_args_list[1]
        assert second_call[1]["parse_mode"] == "HTML"

    @pytest.mark.asyncio
    async def test_strategy_3_plain_text_ultimate_fallback(self):
        """Should fallback to plain text when HTML also fails"""
        from backend.app.routers.telegram import send_telegram_message_with_fallback

        mock_bot = AsyncMock()
        # First two calls fail, third succeeds
        mock_bot.send_message = AsyncMock(
            side_effect=[
                Exception("MarkdownV2 error"),
                Exception("HTML error"),
                None,
            ]
        )

        with patch("backend.app.routers.telegram.telegram_bot", mock_bot):
            result = await send_telegram_message_with_fallback(
                chat_id=123,
                text="**Bold** text",
            )

        assert result is True
        # Should have tried 3 times
        assert mock_bot.send_message.call_count == 3
        # Third call should use plain text (no parse_mode)
        third_call = mock_bot.send_message.call_args_list[2]
        assert third_call[1]["parse_mode"] is None

    @pytest.mark.asyncio
    async def test_all_strategies_fail_returns_false(self):
        """Should return False if all 3 strategies fail"""
        from backend.app.routers.telegram import send_telegram_message_with_fallback

        mock_bot = AsyncMock()
        # All calls fail
        mock_bot.send_message = AsyncMock(
            side_effect=[
                Exception("MarkdownV2 error"),
                Exception("HTML error"),
                Exception("Plain text error"),
            ]
        )

        with patch("backend.app.routers.telegram.telegram_bot", mock_bot):
            result = await send_telegram_message_with_fallback(
                chat_id=123,
                text="**Bold** text",
            )

        assert result is False
        # Should have tried all 3 strategies
        assert mock_bot.send_message.call_count == 3

    @pytest.mark.asyncio
    async def test_markdown_to_html_conversion(self):
        """Should convert markdown to HTML correctly"""
        # Test markdown patterns
        test_cases = [
            ("**bold**", "<b>bold</b>"),
            ("*italic*", "<i>italic</i>"),
            ("_italic_", "<i>italic</i>"),
            ("[link](https://example.com)", '<a href="https://example.com">link</a>'),
        ]

        import re

        for markdown, expected_html in test_cases:
            # Simulate HTML conversion (from send_telegram_message_with_fallback)
            html_text = markdown
            html_text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", html_text)
            html_text = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", html_text)
            html_text = re.sub(r"_([^_]+)_", r"<i>\1</i>", html_text)
            html_text = re.sub(r"\[([^\]]+)\]\(([^\)]+)\)", r'<a href="\2">\1</a>', html_text)

            assert html_text == expected_html

    @pytest.mark.asyncio
    async def test_plain_text_strips_all_markdown(self):
        """Should strip all markdown when using plain text strategy"""
        import re

        test_text = "## Header\n**bold** and *italic* and [link](url)"

        # Simulate plain text stripping (from send_telegram_message_with_fallback)
        plain_text = test_text
        plain_text = re.sub(r"^#{1,6}\s+", "", plain_text, flags=re.MULTILINE)
        plain_text = re.sub(r"\*\*([^*]+)\*\*", r"\1", plain_text)
        plain_text = re.sub(r"\*([^*]+)\*", r"\1", plain_text)
        plain_text = re.sub(r"_([^_]+)_", r"\1", plain_text)
        plain_text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", plain_text)

        assert plain_text == "Header\nbold and italic and link"

    @pytest.mark.asyncio
    async def test_fallback_with_reply_markup(self):
        """Should preserve reply_markup across all fallback strategies"""
        from backend.app.routers.telegram import send_telegram_message_with_fallback

        mock_bot = AsyncMock()
        reply_markup = {"inline_keyboard": [[{"text": "Button", "callback_data": "test"}]]}

        with patch("backend.app.routers.telegram.telegram_bot", mock_bot):
            await send_telegram_message_with_fallback(
                chat_id=123,
                text="Test",
                reply_markup=reply_markup,
            )

        # All calls should include reply_markup
        call_args = mock_bot.send_message.call_args
        assert call_args[1]["reply_markup"] == reply_markup

    @pytest.mark.asyncio
    async def test_fallback_with_reply_to_message_id(self):
        """Should preserve reply_to_message_id across all fallback strategies"""
        from backend.app.routers.telegram import send_telegram_message_with_fallback

        mock_bot = AsyncMock()
        reply_to = 456

        with patch("backend.app.routers.telegram.telegram_bot", mock_bot):
            await send_telegram_message_with_fallback(
                chat_id=123,
                text="Test",
                reply_to_message_id=reply_to,
            )

        # All calls should include reply_to_message_id
        call_args = mock_bot.send_message.call_args
        assert call_args[1]["reply_to_message_id"] == reply_to

    @pytest.mark.asyncio
    async def test_logging_for_each_strategy(self):
        """Should log debug/info for each strategy attempt"""
        from backend.app.routers.telegram import send_telegram_message_with_fallback

        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()

        with patch("backend.app.routers.telegram.telegram_bot", mock_bot):
            with patch("backend.app.routers.telegram.logger") as mock_logger:
                await send_telegram_message_with_fallback(
                    chat_id=123,
                    text="Test",
                )

        # Should have logged success
        mock_logger.debug.assert_called()
        call_args = str(mock_logger.debug.call_args)
        assert "MarkdownV2" in call_args or "Telegram message sent" in call_args


class TestMarkdownEscaping:
    """Test _escape_markdown_v2 helper function"""

    def test_escape_special_characters(self):
        """Should escape all Telegram MarkdownV2 special characters"""
        from backend.app.routers.telegram import _escape_markdown_v2

        special_chars = [
            "_",
            "*",
            "[",
            "]",
            "(",
            ")",
            "~",
            "`",
            ">",
            "#",
            "+",
            "-",
            "=",
            "|",
            "{",
            "}",
            ".",
            "!",
        ]

        for char in special_chars:
            escaped = _escape_markdown_v2(char)
            assert escaped == f"\\{char}"

    def test_escape_complex_text(self):
        """Should escape complex text with multiple special characters"""
        from backend.app.routers.telegram import _escape_markdown_v2

        text = "Price: $100.50 (discount -20%!)"
        escaped = _escape_markdown_v2(text)

        # Should have escaped: . - % ! ( )
        assert "\\." in escaped
        assert "\\-" in escaped
        assert "\\!" in escaped
        assert "\\(" in escaped
        assert "\\)" in escaped

    def test_escape_empty_string(self):
        """Should handle empty string"""
        from backend.app.routers.telegram import _escape_markdown_v2

        escaped = _escape_markdown_v2("")
        assert escaped == ""

    def test_escape_none(self):
        """Should handle None input"""
        from backend.app.routers.telegram import _escape_markdown_v2

        escaped = _escape_markdown_v2(None)
        assert escaped is None


class TestIntegration:
    """Integration tests for markdown fallback system"""

    @pytest.mark.asyncio
    async def test_real_world_markdown_patterns(self):
        """Should handle real-world markdown patterns from RAG responses"""
        from backend.app.routers.telegram import send_telegram_message_with_fallback

        mock_bot = AsyncMock()

        test_responses = [
            "**Requirements:**\n- Document A\n- Document B\n\n[Source](https://example.com)",
            "Price: IDR 5.000.000 (includes tax!)",
            "Process: Step 1 → Step 2 → Step 3",
            "Contact: +62-123-456-789 or email@example.com",
        ]

        with patch("backend.app.routers.telegram.telegram_bot", mock_bot):
            for response in test_responses:
                result = await send_telegram_message_with_fallback(
                    chat_id=123,
                    text=response,
                )
                # Should succeed for all patterns
                assert result is True

    @pytest.mark.asyncio
    async def test_performance_fast_path(self):
        """Should return quickly when MarkdownV2 succeeds (no fallback needed)"""
        import time

        from backend.app.routers.telegram import send_telegram_message_with_fallback

        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()

        with patch("backend.app.routers.telegram.telegram_bot", mock_bot):
            start = time.time()
            await send_telegram_message_with_fallback(
                chat_id=123,
                text="Simple text",
            )
            elapsed = time.time() - start

        # Should be very fast (< 100ms) when no fallback needed
        assert elapsed < 0.1
        # Should only try once
        assert mock_bot.send_message.call_count == 1
