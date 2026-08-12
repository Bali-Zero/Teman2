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

    # Make the return contract above TRUE. Until 2026-08-11 the docstring
    # promised "each within max_length" while the line-splitting branch did
    # `current_chunk = line + "\n"` unconditionally — so a single line longer
    # than max_length was appended whole. Text with no `\n\n` and no `\n` (one
    # long paragraph, which is an ordinary LLM answer shape) came back in ONE
    # oversized chunk, and every caller then handed it straight to a platform
    # that refuses it: WhatsApp truncates at 4096, and Instagram's limit is
    # 1000, where the overflow is four times likelier.
    #
    # Only oversized chunks are touched; every other chunk passes through
    # byte-identical, so no existing caller sees a different split.
    result: list[str] = []
    for chunk in chunks:
        if len(chunk) <= max_length:
            result.append(chunk)
        else:
            result.extend(_split_oversized(chunk, max_length))
    return result


def _split_oversized(chunk: str, max_length: int) -> list[str]:
    """Break a chunk no boundary could shrink into pieces within max_length.

    Cuts at the last space that fits, so a word is not severed; falls back to a
    hard cut only when there is no whitespace at all in the window (a URL, or a
    script that does not space-separate). That fallback is deliberate: an
    oversized chunk is rejected or silently truncated by the platform, which is
    worse than a cut word.
    """
    pieces: list[str] = []
    while len(chunk) > max_length:
        cut = chunk.rfind(" ", 0, max_length + 1)
        if cut <= 0:
            cut = max_length
        pieces.append(chunk[:cut].rstrip())
        chunk = chunk[cut:].lstrip()
    if chunk:
        pieces.append(chunk)
    return pieces


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
