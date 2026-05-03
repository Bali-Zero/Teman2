"""
Message Chunking Utility
Splits long messages into platform-appropriate chunks.

Extracted from:
- WhatsAppService.chunk_message (whatsapp_service.py) - 4096 char limit
- InstagramService.chunk_message (instagram_service.py) - 1000 char limit

Both implementations were identical except for the max_length default.
"""

from __future__ import annotations


def chunk_message(text: str, max_length: int = 4000) -> list[str]:
    """
    Split a long message into chunks that respect platform character limits.

    Strategy:
    1. Split by paragraph (\\n\\n) boundaries first
    2. If a paragraph exceeds max_length, split by line (\\n) boundaries
    3. Each chunk is stripped of trailing whitespace

    Args:
        text: Full message text
        max_length: Maximum characters per chunk.
                    WhatsApp: 4000 (limit 4096, 96 safety margin)
                    Instagram: 950 (limit 1000, 50 safety margin)
                    Telegram: 4000 (limit 4096)

    Returns:
        List of message chunks, each within max_length.
        Returns single-element list if text is already short enough.
    """
    if not text:
        return []

    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    current_chunk = ""

    paragraphs = text.split("\n\n")

    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""

            # If a single paragraph exceeds max_length, split by lines
            if len(para) > max_length:
                lines = para.split("\n")
                for line in lines:
                    if len(current_chunk) + len(line) + 1 > max_length:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = line + "\n"
                    else:
                        current_chunk += line + "\n"
            else:
                current_chunk = para + "\n\n"
        else:
            current_chunk += para + "\n\n"

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


# Platform-specific convenience functions


def chunk_whatsapp(text: str) -> list[str]:
    """Chunk for WhatsApp (4096 char limit, 4000 safety)."""
    return chunk_message(text, max_length=4000)


def chunk_instagram(text: str) -> list[str]:
    """Chunk for Instagram (1000 char limit, 950 safety)."""
    return chunk_message(text, max_length=950)


def chunk_telegram(text: str) -> list[str]:
    """Chunk for Telegram (4096 char limit, 4000 safety)."""
    return chunk_message(text, max_length=4000)
