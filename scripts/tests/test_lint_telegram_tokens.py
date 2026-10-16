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


def test_innocence_an_explicitly_marked_synthetic_fixture_passes() -> None:
    """The tree legitimately holds one token-shaped literal — the corpus pinning
    the 2026-08-11 log-leak scar needs the real SHAPE. Blocking it would be the
    over-match that gets a guard switched off."""
    same_line = f'FAKE = "{_token()}"  # synthetic-telegram-token'
    line_above = f"# synthetic-telegram-token\nFAKE = \"{_token()}\"\n"
    assert not lint.scan_text(same_line)
    assert not lint.scan_text(line_above)


def test_the_synthetic_marker_cannot_launder_a_known_burned_token(monkeypatch) -> None:
    """An exemption that can excuse a credential we KNOW is real is not an
    exemption, it is a hole with a comment on it."""
    monkeypatch.setitem(lint.KNOWN_COMPROMISED, lint._fingerprint(_REAL_BODY), "@testbot")
    marked = f'TOKEN = "{_token()}"  # synthetic-telegram-token'
    hits = lint.scan_text(marked)
    assert hits, "a burned token must be reported however it is marked"
    assert "@testbot" in hits[0]


def test_the_marker_two_lines_above_does_not_reach() -> None:
    """Same line or the line directly above — a reviewer must read the claim
    next to the value, not hunt for it."""
    text = "# synthetic-telegram-token\n# unrelated comment\n" + f'T = "{_token()}"\n'
    assert lint.scan_text(text)


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


# ------------------------------------------------- mutation-sweep pins (2026-10-12)
#
# Expected values come from the module's documented contract (placeholder = "a
# handful of distinct characters", marker = same line or line directly above,
# findings carry file:line + a 16-hex fingerprint and never the body, exit
# 2 = could not scan). Fixtures are assembled at runtime and are synthetic.

import hashlib
import re
import subprocess


def test_five_distinct_chars_is_a_placeholder_six_is_a_token() -> None:
    # 33 chars after "AA": 5 distinct vs 6 distinct
    five = "AA" + ("bcdef" * 7)[:33]
    six = "AA" + ("bcdefg" * 6)[:33]
    assert len(set(five[2:])) == 5 and len(set(six[2:])) == 6
    assert not lint.scan_text("123456789:" + five)
    assert lint.scan_text("123456789:" + six)


def test_placeholder_count_ignores_the_AA_prefix_but_counts_the_first_body_char() -> None:
    # distinct set AFTER the prefix is 6 only because of the very first char
    first_char_only = "AA" + "b" + ("cdefg" * 7)[:32]
    assert len(set(first_char_only[2:])) == 6
    assert lint.scan_text("123456789:" + first_char_only)
    # the prefix 'A' must not count: 5 distinct after the prefix, body mixes no extra A
    prefix_a_only = "AA" + ("bcdef" * 7)[:33]
    assert not lint.scan_text("123456789:" + prefix_a_only)


def test_finding_names_file_line_bot_id_and_a_16_hex_fingerprint() -> None:
    text = "ok line\n" + _token("123456789") + "\n"
    (finding,) = lint.scan_text(text, "docs/x.md")
    expected_fp = hashlib.sha256(_REAL_BODY.encode()).hexdigest()[:16]
    assert finding.startswith("docs/x.md:2: Telegram bot token for bot id 123456789 ")
    assert "(body 34 chars, sha256:" + expected_fp + ")" in finding
    assert re.search(r"sha256:[0-9a-f]{16}\)", finding)


def test_marker_on_the_last_line_does_not_excuse_a_token_on_the_first() -> None:
    """The 'line above' lookup for line 1 must be empty, never wrap around to
    the end of the file."""
    text = f'T = "{_token()}"\nunrelated\n# synthetic-telegram-token\n'
    assert len(lint.scan_text(text)) == 1


def test_marker_directly_above_a_second_line_token_excuses_only_that_one() -> None:
    text = f'A = "{_token()}"\n# synthetic-telegram-token\nB = "{_token("111111111")}"\n'
    findings = lint.scan_text(text)
    assert len(findings) == 1
    assert ":1:" in findings[0]


def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    return repo


def test_tracked_files_skips_vendor_dirs_at_any_depth_and_returns_absolute_paths(tmp_path) -> None:
    repo = _git_repo(tmp_path)
    for rel in ("a.md", "docs/b.md", "node_modules/c.md", "pkg/.venv/d.md", "x/dist/e.md", ".next/f.md"):
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x\n")
    subprocess.run(["git", "add", "-A", "-f"], cwd=repo, check=True)
    got = lint._tracked_files(repo)
    assert sorted(got) == sorted([repo / "a.md", repo / "docs/b.md"])


def test_tracked_files_raises_when_git_fails(tmp_path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(subprocess.CalledProcessError):
        lint._tracked_files(plain)


def test_scan_paths_counts_only_readable_text_files(tmp_path) -> None:
    a = tmp_path / "a.md"
    a.write_text("clean\n")
    b = tmp_path / "b.md"
    b.write_text("also clean\n")
    blob = tmp_path / "blob.bin"
    blob.write_bytes(b"\xff\xfe\x00")
    d = tmp_path / "somedir"
    d.mkdir()
    findings, scanned, missing = lint.scan_paths([a, b, blob, d, tmp_path / "nope.md"], tmp_path)
    assert (findings, scanned) == ([], 2)
    assert missing == [str(tmp_path / "nope.md")]


def test_scan_paths_reports_paths_relative_to_root_and_absolute_outside(tmp_path) -> None:
    inside = tmp_path / "sub" / "leak.md"
    inside.parent.mkdir()
    inside.write_text(_token() + "\n")
    outside_dir = tmp_path / "elsewhere"
    outside_dir.mkdir()
    outside = outside_dir / "leak2.md"
    outside.write_text(_token("111111111") + "\n")
    root = tmp_path / "sub"
    findings, scanned, _ = lint.scan_paths([inside, outside], root)
    assert scanned == 2
    assert findings[0].startswith("leak.md:1:")
    assert findings[1].startswith(str(outside) + ":1:")


def test_selftest_fails_when_the_scanner_is_blind(monkeypatch, capsys) -> None:
    monkeypatch.setattr(lint, "scan_text", lambda text, path="<m>": [])
    assert lint.selftest() == 1
    out = capsys.readouterr().out
    assert "GUILT   miss" in out
    assert "selftest FAILED (4 of 11)" in out


def test_selftest_fails_on_false_positives(monkeypatch, capsys) -> None:
    monkeypatch.setattr(lint, "scan_text", lambda text, path="<m>": ["hit"])
    assert lint.selftest() == 1
    out = capsys.readouterr().out
    assert "INNOCENCE false positive" in out
    assert "selftest FAILED (7 of 11)" in out


def test_selftest_ok_message_counts(capsys) -> None:
    assert lint.selftest() == 0
    assert "selftest OK — 4 guilt, 7 innocence" in capsys.readouterr().out


def test_no_args_means_nothing_to_scan_exit_two(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["lint"])
    assert lint.main() == 2
    assert "nothing to scan" in capsys.readouterr().err


def test_all_mode_on_a_real_repo_flags_a_leak_and_passes_a_clean_tree(tmp_path, monkeypatch, capsys) -> None:
    repo = _git_repo(tmp_path)
    (repo / "ok.md").write_text("token from ${TELEGRAM_BOT_TOKEN}\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    monkeypatch.chdir(repo)
    monkeypatch.setattr(sys, "argv", ["lint", "--all"])
    assert lint.main() == 0
    assert "no Telegram bot token in 1 tracked text file(s)" in capsys.readouterr().out

    (repo / "leak.md").write_text("x\n" + _token() + "\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    assert lint.main() == 1
    out = capsys.readouterr().out
    assert "found in 1 place(s)" in out
    assert "leak.md:2:" in out
    assert _REAL_BODY not in out


def test_outside_a_git_repo_the_guard_never_reports_clean(tmp_path, monkeypatch) -> None:
    """Exit contract: 'could not scan' is never silently clean — it either
    raises or exits non-zero."""
    clean = tmp_path / "ok.md"
    clean.write_text("nothing here\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["lint", str(clean)])
    try:
        rc = lint.main()
    except subprocess.CalledProcessError:
        return
    assert rc != 0
