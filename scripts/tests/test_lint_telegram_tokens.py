"""Guilt + innocence for scripts/lint_telegram_tokens.py.

Every token-shaped string here is assembled from fragments at import time. A
literal one would make this file the scanner's first finding, and the usual
escape — exempting the guard's own test path — is how a guard grows a hole
named after itself.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "lint_telegram_tokens",
    Path(__file__).resolve().parents[1] / "lint_telegram_tokens.py",
)
assert _SPEC and _SPEC.loader
lint = importlib.util.module_from_spec(_SPEC)
sys.modules["lint_telegram_tokens"] = lint
_SPEC.loader.exec_module(lint)

_REAL_BODY = "AA" + "Hn4Kd9Wq2Zx7Lm1Pv6Rt3Yb8Sc5Ug0Jf"  # varied, 33 after "AA"


def _token(bot_id: str = "8295471667") -> str:
    return bot_id + ":" + _REAL_BODY


# ---------------------------------------------------------------- guilt


@pytest.mark.parametrize(
    "label,text",
    [
        ("markdown prose", "The plist carried " + _token() + " in cleartext."),
        ("plist value", "<string>" + _token("123456789") + "</string>"),
        ("shell export", "export TELEGRAM_BOT_TOKEN=" + _token("999999999")),
        ("json value", '{"token": "' + _token("100200300") + '"}'),
        ("inside a URL", "https://api.telegram.org/bot" + _token() + "/sendMessage"),
    ],
)
def test_guilt_a_real_shaped_token_is_found(label: str, text: str) -> None:
    assert lint.scan_text(text), f"scanner blind to a token in {label}"


def test_guilt_the_burned_balizerobot_token_is_named_not_merely_flagged() -> None:
    """The known-compromised registry is matched by hash, so a re-introduction
    of THAT token says which bot it belongs to instead of just 'a token'."""
    assert "a54b897b432002bb" in lint.KNOWN_COMPROMISED
    assert "Balizerobot" in lint.KNOWN_COMPROMISED["a54b897b432002bb"]


def test_guilt_findings_never_contain_the_token_body() -> None:
    """A gate that echoes the secret writes it into a CI log as public as the
    file it came from — the same disease one layer down."""
    findings = lint.scan_text(_token())
    assert findings
    assert _REAL_BODY not in "\n".join(findings)


# ------------------------------------------------------------ innocence


@pytest.mark.parametrize(
    "label,text",
    [
        ("env placeholder", "token: ${TELEGRAM_BOT_TOKEN}"),
        ("angle placeholder", "token: <bot-token>"),
        ("bare owner chat id", "TELEGRAM_OWNER_CHAT_ID=8847435604"),
        ("sha256 digest", "commit sha256:3d69bc0e10ab4419f8b2c7d5e6a1f0b3"),
        ("repeated-char placeholder", "token: 123456789:" + "AA" + "A" * 33),
        ("two-char placeholder", "token: 123456789:" + "AA" + "ab" * 17),
        ("too short", "token: 123456789:" + "AA" + "x" * 10),
        ("timestamp with colon", "the 12345678:00 run"),
        ("python assignment of an env read", 'TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]'),
    ],
)
def test_innocence_lookalikes_do_not_fire(label: str, text: str) -> None:
    assert not lint.scan_text(text), f"false positive on {label}"


# ------------------------------------------------------------- behaviour


def test_a_path_that_does_not_exist_is_an_error_not_a_clean_read(tmp_path, monkeypatch) -> None:
    """Caller and scanner disagreeing about what is being checked is a fault,
    not a pass."""
    monkeypatch.setattr(sys, "argv", ["lint", str(tmp_path / "does-not-exist.md")])
    assert lint.main() == 2


def test_an_all_scan_that_read_nothing_is_not_reported_clean(tmp_path, monkeypatch) -> None:
    """W84: in --all mode, zero files traversed means the enumeration broke."""
    monkeypatch.setattr(lint, "_tracked_files", lambda root: [])
    monkeypatch.setattr(sys, "argv", ["lint", "--all"])
    assert lint.main() == 2


def test_innocence_a_commit_of_only_binaries_is_not_blocked(tmp_path, monkeypatch) -> None:
    """pre-commit passes the staged files; a PNG-only commit reads zero text
    files and must still pass. Fail-closed belongs at the enumeration, not
    here — otherwise the guard fires on innocence."""
    png = tmp_path / "logo.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe\xfd")
    monkeypatch.setattr(sys, "argv", ["lint", str(png)])
    assert lint.main() == 0


def test_a_clean_readable_file_exits_zero(tmp_path, monkeypatch) -> None:
    good = tmp_path / "ok.md"
    good.write_text("token comes from ${TELEGRAM_BOT_TOKEN}\n")
    monkeypatch.setattr(sys, "argv", ["lint", str(good)])
    assert lint.main() == 0


def test_a_file_carrying_a_token_exits_one(tmp_path, monkeypatch) -> None:
    bad = tmp_path / "leak.md"
    bad.write_text("token: " + _token() + "\n")
    monkeypatch.setattr(sys, "argv", ["lint", str(bad)])
    assert lint.main() == 1


def test_the_embedded_selftest_passes() -> None:
    assert lint.selftest() == 0
