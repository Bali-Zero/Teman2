"""What the loop leaves behind must not name anybody, and must not be readable.

Two defences, one concern. SYMBIOSIS Law 2 (UU PDP Art. 67-68) is absolute about
persisted artifacts, and an email subject is client data in the plainest sense —
"KITAS renewal for <person>" is an ordinary subject line in this mailbox.

  * LOG PRIVACY. The loop's log is world-readable on the Pro and is tailed by
    other organs. Two lines used to interpolate the subject: one on a draft
    failure (truncated to 40 characters, which is not redaction, only a smaller
    leak) and one on the dry-run draft line (the full subject). Both are now
    identified by the opaque message id and the lane.

  * FILE MODE. `pending-drafts.json` holds the reply text we generated, which
    opens with a salutation and therefore carries a name. Left to the default
    umask it lands 0644 in a 0755 directory — superscar #4, waiting for the
    first backup, sync client or second account on the machine.

Both halves carry guilt AND innocence. The innocence half matters more than
usual here: a log that says nothing at all would pass a naive leak test while
being useless to whoever is debugging the organ at 07:30.
"""

from __future__ import annotations

import asyncio
import json
import logging
import stat
from pathlib import Path

import pytest

from backend.services.mail_loop import draft as draft_module
from backend.services.mail_loop.loop import MailLoop, PendingDrafts
from backend.services.mail_loop.state_io import DIR_MODE, FILE_MODE, write_private
from backend.services.mail_loop.style import Lesson, ReplyStyleStore, today
from backend.tests.unit.services.mail_loop.test_loop import (
    FOLDERS,
    FakeBackend,
    _msg,
    stub_model,  # noqa: F401  -- imported so pytest resolves it as a fixture here
)

# A string no marker table, folder name or log template could produce by
# accident, so its presence in a log can only mean the subject was echoed.
CANARY = "Zzcanary-Quenneville-77"


def _loop(backend: FakeBackend, tmp_path: Path, *, dry_run: bool) -> MailLoop:
    return MailLoop(
        backend,
        user_id="zero",
        style=ReplyStyleStore(tmp_path / "reply-style.md"),
        pending=PendingDrafts(tmp_path / "pending.json"),
        dry_run=dry_run,
    )


# --------------------------------------------------------------------------- #
# Log privacy.                                                                 #
# --------------------------------------------------------------------------- #


def test_dry_run_log_does_not_echo_the_subject(
    tmp_path: Path, stub_model: None, caplog: pytest.LogCaptureFixture
) -> None:
    """GUILT: the dry-run draft line named the message, subject and all."""
    backend = FakeBackend(
        inbox=[_msg("m1", f"KITAS renewal — {CANARY}", "a@x.example", "T1")],
        bodies={"m1": "My KITAS expires next month, what do you need?"},
    )
    with caplog.at_level(logging.DEBUG, logger="backend.services.mail_loop.loop"):
        summary = asyncio.run(_loop(backend, tmp_path, dry_run=True).run())

    assert summary.drafted == 1, "premise: this run must actually reach the draft line"
    assert CANARY not in caplog.text


def test_draft_failure_log_does_not_echo_the_subject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """GUILT: the failure path leaked the subject's first 40 characters.

    A truncated leak is still a leak, and 40 characters is more than enough for
    a name.
    """

    def _boom(request, dry_run: bool = False):  # type: ignore[no-untyped-def]
        raise draft_module.DraftUnavailable("model refused")

    monkeypatch.setattr(draft_module, "generate", _boom)
    monkeypatch.setattr("backend.services.mail_loop.loop.generate", _boom)

    backend = FakeBackend(
        inbox=[_msg("m1", f"{CANARY} needs a KITAS", "a@x.example", "T1")],
        bodies={"m1": "My KITAS expires next month, what do you need?"},
    )
    with caplog.at_level(logging.DEBUG, logger="backend.services.mail_loop.loop"):
        summary = asyncio.run(_loop(backend, tmp_path, dry_run=True).run())

    assert summary.draft_failures == 1, "premise: this run must hit the failure path"
    assert CANARY not in caplog.text


def _lines_about(caplog: pytest.LogCaptureFixture, needle: str) -> list[str]:
    """Log lines mentioning `needle`, so an assertion names ONE line.

    Written after a mutation run caught this file lying: the first version of
    the innocence check below asserted that the id and the lane appeared
    "somewhere in caplog", and deleting the draft line outright left the suite
    green — the ROUTING line a few statements earlier carries the same id and
    the same lane. A test that accepts any line is not testing a line.
    """
    return [line for line in caplog.text.splitlines() if needle in line]


def test_the_draft_log_line_still_identifies_the_message(
    tmp_path: Path, stub_model: None, caplog: pytest.LogCaptureFixture
) -> None:
    """INNOCENCE: privacy is not silence.

    Without this, deleting the draft log line would pass the leak tests above
    while leaving whoever debugs this organ at 07:30 with nothing. The line
    must still exist and still say WHICH message and WHICH lane.
    """
    backend = FakeBackend(
        inbox=[_msg("m1", f"KITAS renewal — {CANARY}", "a@x.example", "T1")],
        bodies={"m1": "My KITAS expires next month, what do you need?"},
    )
    with caplog.at_level(logging.DEBUG, logger="backend.services.mail_loop.loop"):
        asyncio.run(_loop(backend, tmp_path, dry_run=True).run())

    drafted = _lines_about(caplog, "draft")
    assert drafted, "the draft line was removed, not redacted"
    assert any("m1" in line for line in drafted), "the opaque id must survive"
    assert any("visa" in line for line in drafted), "the lane must survive"


def test_the_failure_log_line_still_identifies_the_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """INNOCENCE for the other redacted line, for the same reason.

    Two lines were changed; covering one is half a fix (W107).
    """

    def _boom(request, dry_run: bool = False):  # type: ignore[no-untyped-def]
        raise draft_module.DraftUnavailable("model refused")

    monkeypatch.setattr(draft_module, "generate", _boom)
    monkeypatch.setattr("backend.services.mail_loop.loop.generate", _boom)

    backend = FakeBackend(
        inbox=[_msg("m1", f"{CANARY} needs a KITAS", "a@x.example", "T1")],
        bodies={"m1": "My KITAS expires next month, what do you need?"},
    )
    with caplog.at_level(logging.DEBUG, logger="backend.services.mail_loop.loop"):
        asyncio.run(_loop(backend, tmp_path, dry_run=True).run())

    failed = _lines_about(caplog, "no draft for")
    assert failed, "the failure line was removed, not redacted"
    assert any("m1" in line for line in failed), "the opaque id must survive"
    assert any("visa" in line for line in failed), "the lane must survive"


def test_no_sender_address_reaches_the_log(
    tmp_path: Path, stub_model: None, caplog: pytest.LogCaptureFixture
) -> None:
    """GUILT: an address is PII too, and is easier to leak by accident."""
    backend = FakeBackend(
        inbox=[_msg("m1", "KITAS renewal", "canary.person@example.invalid", "T1")],
        bodies={"m1": "My KITAS expires next month, what do you need?"},
    )
    with caplog.at_level(logging.DEBUG, logger="backend.services.mail_loop.loop"):
        asyncio.run(_loop(backend, tmp_path, dry_run=True).run())

    assert "canary.person@example.invalid" not in caplog.text


# --------------------------------------------------------------------------- #
# File mode.                                                                   #
# --------------------------------------------------------------------------- #


def test_write_private_creates_owner_only_file_and_dir(tmp_path: Path) -> None:
    """GUILT: both the file and its parent are tightened, not just the file."""
    target = tmp_path / "nested" / "state.json"
    write_private(target, json.dumps({"a": 1}))

    assert stat.S_IMODE(target.stat().st_mode) == FILE_MODE
    assert stat.S_IMODE(target.parent.stat().st_mode) == DIR_MODE
    assert json.loads(target.read_text()) == {"a": 1}


def test_write_private_tightens_an_already_loose_directory(tmp_path: Path) -> None:
    """GUILT: `mkdir(exist_ok=True)` does nothing to a directory that exists.

    A state dir created by an older version of this code — or by a human —
    stays 0755 unless the mode is applied unconditionally.
    """
    loose = tmp_path / "loose"
    loose.mkdir(mode=0o755)
    write_private(loose / "state.json", "{}")

    assert stat.S_IMODE(loose.stat().st_mode) == DIR_MODE


def test_write_private_leaves_no_temp_file_behind(tmp_path: Path) -> None:
    """INNOCENCE: the atomic write must not litter.

    A stale `.tmp` sitting at the default mode would reintroduce exactly the
    exposure this helper removes.
    """
    target = tmp_path / "state.json"
    write_private(target, "{}")

    assert sorted(p.name for p in tmp_path.iterdir()) == ["state.json"]


def test_write_private_replaces_rather_than_appends(tmp_path: Path) -> None:
    """INNOCENCE: a second write is a replacement, not a concatenation."""
    target = tmp_path / "state.json"
    write_private(target, json.dumps({"round": 1}))
    write_private(target, json.dumps({"round": 2}))

    assert json.loads(target.read_text()) == {"round": 2}


def test_pending_buffer_lands_owner_only(tmp_path: Path) -> None:
    """The helper is actually WIRED, not merely present.

    Written against the real `PendingDrafts`, because a private-write helper
    nobody calls is the shape of a defence that exists and is not armed.
    """
    pending = PendingDrafts(tmp_path / "deep" / "pending-drafts.json")
    pending.add("T1", text="Dear client, ...", bucket="visa/en")

    path = tmp_path / "deep" / "pending-drafts.json"
    assert path.exists()
    assert stat.S_IMODE(path.stat().st_mode) == FILE_MODE
    assert stat.S_IMODE(path.parent.stat().st_mode) == DIR_MODE


def test_style_file_lands_owner_only(tmp_path: Path) -> None:
    """Same wiring check for the other writer.

    Two call sites were changed; a test that only covers one is half a fix
    (W107 — the cure went to one wrapper out of five).
    """
    store = ReplyStyleStore(tmp_path / "deep" / "reply-style.md")
    # The call is deliberately OUTSIDE the assert. `python -O` strips assert
    # statements, so a write hidden inside one simply would not happen, and
    # everything below would fail for a reason that has nothing to do with the
    # file mode. CodeQL flags exactly this (py/side-effect-in-assert) and it is
    # right to.
    stored = store.append(
        Lesson(bucket="visa/en", text="Keeps replies short.", observed_on=today())
    )
    assert stored, "premise: the lesson must survive redaction, or nothing gets written"

    path = tmp_path / "deep" / "reply-style.md"
    assert path.exists()
    assert stat.S_IMODE(path.stat().st_mode) == FILE_MODE
    assert stat.S_IMODE(path.parent.stat().st_mode) == DIR_MODE


def test_folders_fixture_is_reused_not_redefined() -> None:
    """The imports above are load-bearing; keep them honest.

    If `test_loop` stops exporting the shared fixtures, this file must fail
    loudly rather than silently drift onto a private copy that agrees with
    nothing (the W114 lesson: a fixture is evidence only when it is shared with
    the thing it stands in for).
    """
    assert any(f.get("folder_name") == "_Visa" for f in FOLDERS)
