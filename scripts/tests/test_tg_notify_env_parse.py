"""Tests for tg_notify._parse_env_file — `export FOO=bar` must resolve as FOO.

TRAUMA (2026-08-06): removing a duplicate TELEGRAM_BOT_TOKEN line on Mini left
only the `export`-prefixed one, and the gate went mute — resolve_credentials()
returned the empty string (proved by sha256 == e3b0c44298fc, the hash of "").
The parser did `k, _, v = line.partition("=")` and stored the key as the literal
`"export TELEGRAM_BOT_TOKEN"`, so every export-prefixed secret was invisible.
Measured blast radius on the live fleet the same day: Mini 19 invisible keys
(TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_CHAT_ID, DATABASE_URL, BREVO_API_KEY, ...),
Pro 6, M5 4. It stayed hidden because a duplicate non-export line masked it.

The file is BOTH sourced by shell wrappers (which need `export` for the value to
reach child processes) and read by this parser — so both spellings are the same
key, by construction.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import tg_notify  # noqa: E402


def _parse(tmp_path, body):
    p = tmp_path / "secrets.env"
    p.write_text(body)
    return tg_notify._parse_env_file(p)


# ----------------------------------------------------------------- GUILT
def test_export_prefixed_key_resolves(tmp_path):
    """The exact line shape that muted Mini."""
    env = _parse(tmp_path, "export TELEGRAM_BOT_TOKEN=abc123\n")
    assert env.get("TELEGRAM_BOT_TOKEN") == "abc123"


def test_export_and_bare_forms_are_the_same_key(tmp_path):
    env = _parse(tmp_path, "export A=1\nB=2\n")
    assert env == {"A": "1", "B": "2"}


def test_resolve_credentials_reads_export_lines(tmp_path, monkeypatch):
    """End-to-end through the real entry point, not just the helper."""
    p = tmp_path / "secrets.env"
    p.write_text("export TELEGRAM_BOT_TOKEN=tok\nexport TELEGRAM_OWNER_CHAT_ID=999\n")
    monkeypatch.setenv("TG_SECRETS_FILE", str(p))
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_OWNER_CHAT_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_ZERO_CHAT_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_ADMIN_CHAT_ID", raising=False)
    assert tg_notify.resolve_credentials() == ("tok", "999")


def test_extra_whitespace_after_export(tmp_path):
    env = _parse(tmp_path, "  export   TELEGRAM_BOT_TOKEN = xyz \n")
    assert env.get("TELEGRAM_BOT_TOKEN") == "xyz"


# ----------------------------------------------------------------- INNOCENCE
def test_key_starting_with_export_letters_is_not_mangled(tmp_path):
    """The lstrip('export ') trap: it strips CHARACTERS, not a prefix.

    EVENTBUS_* / EXPORT_* / TOKEN_* all begin with letters in 'export ' and would
    be silently renamed by a character-class strip. removeprefix must not touch
    them: there is no 'export ' PREFIX here.
    """
    env = _parse(tmp_path, "EVENTBUS_DATABASE_URL=u\nEXPORT_PATH=p\nOPERATOR=o\n")
    assert env == {"EVENTBUS_DATABASE_URL": "u", "EXPORT_PATH": "p", "OPERATOR": "o"}


def test_exportfoo_without_space_is_its_own_key(tmp_path):
    """`exportFOO=1` is a key literally named exportFOO, not FOO."""
    env = _parse(tmp_path, "exportFOO=1\n")
    assert env == {"exportFOO": "1"}


def test_value_containing_export_is_untouched(tmp_path):
    env = _parse(tmp_path, 'CMD="export PATH=/bin"\n')
    assert env.get("CMD") == "export PATH=/bin"


def test_comments_and_blanks_still_skipped(tmp_path):
    env = _parse(tmp_path, "# export FAKE=1\n\n   \nREAL=2\n")
    assert env == {"REAL": "2"}


def test_bare_export_line_yields_no_empty_key(tmp_path):
    """`export =v` must not create a "" key that shadows a lookup."""
    env = _parse(tmp_path, "export =v\nREAL=2\n")
    assert "" not in env
    assert env == {"REAL": "2"}
