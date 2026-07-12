"""trim_self_echo: the router persists inbound BEFORE the engine loads
context, so on a Redis cache miss the DB history includes the CURRENT
message — the LLM must not see it twice (Codex review 2026-07-13)."""

from backend.conversation._history import trim_self_echo


def test_guilt_trailing_current_message_is_trimmed():
    history = [
        {"role": "user", "content": "quanto costa il KITAS?"},
        {"role": "assistant", "content": "Dipende dal tipo..."},
        {"role": "user", "content": "e il C1?"},
    ]
    trimmed = trim_self_echo(history, "e il C1?")
    assert trimmed == history[:2]


def test_innocence_different_trailing_message_untouched():
    history = [{"role": "user", "content": "prima domanda"}]
    assert trim_self_echo(history, "seconda domanda") == history


def test_innocence_trailing_assistant_untouched():
    history = [
        {"role": "user", "content": "ciao"},
        {"role": "assistant", "content": "ciao"},
    ]
    # same text but assistant turn — not a self-echo
    assert trim_self_echo(history, "ciao") == history


def test_innocence_repeated_message_deeper_in_history_untouched():
    history = [
        {"role": "user", "content": "ping"},
        {"role": "assistant", "content": "pong"},
    ]
    # "ping" appears earlier but not as the trailing entry
    assert trim_self_echo(history, "ping") == history


def test_empty_history_ok():
    assert trim_self_echo([], "x") == []
