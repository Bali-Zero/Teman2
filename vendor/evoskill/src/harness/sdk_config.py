"""SDK configuration and selection logic.

Bali Zero Nuzantara vendor addition (Gemini + Codex panel 2026-05-18
CRITICAL convergent): added "deepseek" to SDKType + _VALID_SDKS so
evolver.toml provider=deepseek is dispatchable. See harness/deepseek/
(Phase 0 stub) and vendor/evoskill/UPSTREAM.md §5.
"""

from typing import Literal

SDKType = Literal["claude", "opencode", "codex", "goose", "openhands", "deepseek"]

# Global SDK selection (can be overridden via CLI arguments).
# Default remains "claude" for upstream compatibility — Bali Zero
# evolver.toml explicitly sets "deepseek" before any .run() call.
_current_sdk: SDKType = "claude"

_VALID_SDKS = ("claude", "opencode", "codex", "goose", "openhands", "deepseek")


def set_sdk(sdk: SDKType) -> None:
    """Set the current SDK to use globally."""
    global _current_sdk
    if sdk not in _VALID_SDKS:
        raise ValueError(
            f"Invalid SDK type: {sdk}. Must be one of: {', '.join(repr(s) for s in _VALID_SDKS)}"
        )
    _current_sdk = sdk


def get_sdk() -> SDKType:
    """Get the currently configured SDK."""
    return _current_sdk


def is_claude_sdk() -> bool:
    """Check if claude-agent-sdk is the current SDK."""
    return _current_sdk == "claude"


def is_opencode_sdk() -> bool:
    """Check if opencode-ai is the current SDK."""
    return _current_sdk == "opencode"


def is_openhands_sdk() -> bool:
    """Check if OpenHands is the current SDK."""
    return _current_sdk == "openhands"
  
  
def is_codex_sdk() -> bool:
    """Check if codex is the current SDK."""
    return _current_sdk == "codex"


def is_goose_sdk() -> bool:
    """Check if goose is the current SDK."""
    return _current_sdk == "goose"


def is_deepseek_sdk() -> bool:
    """Check if DeepSeek V4 Pro is the current SDK.

    Bali Zero Nuzantara vendor addition (panel 2026-05-18). Returns True
    when evolver.toml provider=deepseek has been applied via set_sdk.
    """
    return _current_sdk == "deepseek"
