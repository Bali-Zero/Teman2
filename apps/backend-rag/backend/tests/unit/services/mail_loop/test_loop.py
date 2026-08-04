"""Orchestration corpus, run against a fake mailbox.

No token, no network, no Zoho. The fake records every mutation, so the assertions
are about what the loop DID, not about what it logged — a run that reports
success while moving nothing is the failure this file exists to catch.

The behaviours pinned here are the ones that would otherwise be discovered in
production:

  * a missing destination folder leaves mail in the inbox instead of moving it
    somewhere arbitrary, and the run is marked degraded;
  * `--dry-run` performs ZERO mutations (a dry run that writes is not a dry run);
  * UNKNOWN stays in the inbox where a human sees it;
  * noise is filed but never answered;
  * drafting nothing while there was mail to answer does NOT read as success;
  * the learning pass turns a real draft/sent difference into a stored lesson.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from backend.services.mail_loop import draft as draft_module
from backend.services.mail_loop import loop as loop_module
from backend.services.mail_loop.loop import (
    DRAFT_MARKER,
    MailLoop,
    PendingDrafts,
)
from backend.services.mail_loop.style import ReplyStyleStore

FOLDERS = [
    {"folderId": "F-INBOX", "folderName": "Inbox"},
    {"folderId": "F-SENT", "folderName": "Sent"},
    {"folderId": "F-VISA", "folderName": "_Visa"},
    {"folderId": "F-TAX", "folderName": "_Tax"},
    {"folderId": "F-NOISE", "folderName": "_Noise"},
]


class FakeBackend:
    """Records mutations. Deliberately not a MagicMock: the recorded calls are
    the assertions, and a mock would happily accept a method that does not exist
    on the real service."""

    def __init__(
        self,
        inbox: list[dict[str, Any]],
        bodies: dict[str, dict[str, Any]],
        sent: list[dict[str, Any]] | None = None,
        folders: list[dict[str, Any]] | None = None,
    ) -> None:
        self.inbox = inbox
        self.bodies = bodies
        self.sent = sent or []
        self.folders = folders if folders is not None else FOLDERS
        self.moves: list[tuple[list[str], str]] = []
        self.drafts: list[dict[str, Any]] = []

    async def list_folders(self, user_id: str) -> list[dict[str, Any]]:
        return self.folders

    async def list_emails(
        self,
        user_id: str,
        folder_id: str = "inbox",
        limit: int = 50,
        start: int = 0,
        search_key: str | None = None,
        is_unread: bool | None = None,
    ) -> dict[str, Any]:
        if folder_id == "F-SENT":
            return {"emails": self.sent}
        return {"emails": self.inbox}

    async def get_email(
        self, user_id: str, message_id: str, folder_id: str | None = None
    ) -> dict[str, Any]:
        return self.bodies[message_id]

    async def move_to_folder(
        self, user_id: str, message_ids: list[str], folder_id: str
    ) -> bool:
        self.moves.append((list(message_ids), folder_id))
        return True

    async def save_draft(
        self,
        user_id: str,
        to: list[str] | None = None,
        subject: str = "",
        content: str = "",
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        attachments: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        self.drafts.append({"to": to, "subject": subject, "content": content})
        return {"messageId": f"D-{len(self.drafts)}"}


def _msg(mid: str, subject: str, sender: str, thread: str = "") -> dict[str, Any]:
    return {"messageId": mid, "subject": subject, "sender": sender, "threadId": thread}


def _body(mid: str, subject: str, content: str, sender: str, thread: str = "") -> dict[str, Any]:
    return {
        "messageId": mid,
        "subject": subject,
        "content": content,
        "fromAddress": sender,
        "threadId": thread,
    }


@pytest.fixture
def stub_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the model call. The CLI is not under test here."""
    monkeypatch.setattr(
        draft_module,
        "generate",
        lambda request, dry_run=False: f"Drafted reply about {request.intent}.",
    )

    monkeypatch.setattr(
        loop_module,
        "generate",
        lambda request, dry_run=False: f"Drafted reply about {request.intent}.",
    )


def _loop(backend: FakeBackend, tmp_path: Path, *, dry_run: bool = False) -> MailLoop:
    return MailLoop(
        backend,
        user_id="zero",
        style=ReplyStyleStore(tmp_path / "reply-style.md"),
        pending=PendingDrafts(tmp_path / "pending.json"),
        dry_run=dry_run,
    )


def test_routes_and_drafts(tmp_path: Path, stub_model: None) -> None:
    backend = FakeBackend(
        inbox=[_msg("m1", "KITAS renewal", "sofia@x.example", "T1")],
        bodies={
            "m1": _body(
                "m1",
                "KITAS renewal",
                "My KITAS expires next month, what do you need?",
                "sofia@x.example",
                "T1",
            )
        },
    )
    summary = asyncio.run(_loop(backend, tmp_path).run())

    assert summary.seen == 1
    assert summary.routed == 1
    assert summary.drafted == 1
    assert backend.moves == [(["m1"], "F-VISA")]
    assert backend.drafts[0]["subject"] == "Re: KITAS renewal"
    assert backend.drafts[0]["to"] == ["sofia@x.example"]
    assert summary.degraded is False


def test_draft_carries_a_visible_marker(tmp_path: Path, stub_model: None) -> None:
    """The marker is visible text, not an HTML comment.

    A hidden marker would survive into the sent mail and reach the client. This
    one is a line Zero deletes while editing, which is the intended behaviour.
    """
    backend = FakeBackend(
        inbox=[_msg("m1", "SPT question", "a@x.example")],
        bodies={"m1": _body("m1", "SPT question", "How do I file my SPT?", "a@x.example")},
    )
    asyncio.run(_loop(backend, tmp_path).run())
    content = backend.drafts[0]["content"]
    assert content.startswith(DRAFT_MARKER)
    assert "<!--" not in content


def test_missing_folder_leaves_mail_in_inbox_and_degrades(
    tmp_path: Path, stub_model: None
) -> None:
    """No destination folder: do not move, do not pretend it worked."""
    backend = FakeBackend(
        inbox=[_msg("m1", "KITAS renewal", "a@x.example")],
        bodies={"m1": _body("m1", "KITAS renewal", "About my KITAS extension.", "a@x.example")},
        folders=[
            {"folderId": "F-INBOX", "folderName": "Inbox"},
            {"folderId": "F-SENT", "folderName": "Sent"},
        ],
    )
    summary = asyncio.run(_loop(backend, tmp_path).run())

    assert backend.moves == []
    assert summary.routed == 0
    assert summary.left_in_inbox == 1
    assert "_Visa" in summary.missing_folders
    assert summary.degraded is True


def test_unknown_stays_in_inbox(tmp_path: Path, stub_model: None) -> None:
    """Refusing to guess is a feature: a human still sees it."""
    backend = FakeBackend(
        inbox=[_msg("m1", "Hello", "a@x.example")],
        bodies={"m1": _body("m1", "Hello", "Just saying hi, hope you are well.", "a@x.example")},
    )
    summary = asyncio.run(_loop(backend, tmp_path).run())
    assert backend.moves == []
    assert backend.drafts == []
    assert summary.left_in_inbox == 1


def test_noise_is_filed_but_never_answered(tmp_path: Path, stub_model: None) -> None:
    backend = FakeBackend(
        inbox=[_msg("m1", "Immigration newsletter", "news@x.example")],
        bodies={
            "m1": {
                "messageId": "m1",
                "subject": "Immigration newsletter",
                "content": "Our monthly roundup on KITAS rules.",
                "fromAddress": "news@x.example",
                "headers": {"List-Unsubscribe": "<mailto:u@x.example>"},
            }
        },
    )
    summary = asyncio.run(_loop(backend, tmp_path).run())
    assert backend.moves == [(["m1"], "F-NOISE")]
    assert backend.drafts == []
    assert summary.drafted == 0
    assert summary.degraded is False


def test_dry_run_performs_zero_mutations(tmp_path: Path, stub_model: None) -> None:
    """A dry run that writes is not a dry run.

    This is the guard that lets the first live-ish run be observed safely.
    """
    backend = FakeBackend(
        inbox=[_msg("m1", "KITAS renewal", "a@x.example", "T1")],
        bodies={"m1": _body("m1", "KITAS renewal", "About my KITAS.", "a@x.example", "T1")},
    )
    summary = asyncio.run(_loop(backend, tmp_path, dry_run=True).run())

    assert backend.moves == []
    assert backend.drafts == []
    assert summary.routed == 1  # counted as "would route"
    assert summary.drafted == 1
    assert not (tmp_path / "pending.json").exists()


def test_drafting_nothing_is_not_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Routing succeeds, every draft fails: the run must read as degraded."""

    def boom(request: Any, dry_run: bool = False) -> str:
        raise draft_module.DraftUnavailable("no model available")

    monkeypatch.setattr(loop_module, "generate", boom)

    backend = FakeBackend(
        inbox=[_msg("m1", "KITAS renewal", "a@x.example")],
        bodies={"m1": _body("m1", "KITAS renewal", "About my KITAS.", "a@x.example")},
    )
    summary = asyncio.run(_loop(backend, tmp_path).run())

    assert summary.routed == 1
    assert summary.drafted == 0
    assert summary.draft_failures == 1
    assert summary.degraded is True


def test_one_bad_message_does_not_abort_the_run(tmp_path: Path, stub_model: None) -> None:
    """The rest of the mail still deserves routing."""
    backend = FakeBackend(
        inbox=[_msg("bad", "x", "a@x.example"), _msg("m2", "KITAS renewal", "b@x.example")],
        bodies={"m2": _body("m2", "KITAS renewal", "About my KITAS.", "b@x.example")},
    )
    summary = asyncio.run(_loop(backend, tmp_path).run())

    assert summary.routed == 1
    assert summary.errors, "the failing message must be reported, not swallowed"
    assert backend.moves == [(["m2"], "F-VISA")]


def test_learning_pass_stores_a_lesson(tmp_path: Path, stub_model: None) -> None:
    """End-to-end: a pending draft plus a real send becomes a lesson on disk."""
    style_path = tmp_path / "reply-style.md"
    pending_path = tmp_path / "pending.json"

    pending = PendingDrafts(pending_path)
    pending.add(
        "T-42",
        text=(
            "Dear client, thank you for reaching out. The KITAS renewal costs "
            "IDR 12.500.000 all in. We can start once you send the passport scan."
        ),
        bucket="visa/en",
    )

    sent_body = _body(
        "s1",
        "Re: KITAS renewal",
        (
            "Dear client, thanks for writing. For the KITAS renewal our team will "
            "send the official quotation shortly. Could you send the passport scan?"
        ),
        "zero@balizero.com",
        "T-42",
    )
    backend = FakeBackend(
        inbox=[],
        bodies={"s1": sent_body},
        sent=[{"messageId": "s1", "threadId": "T-42", "subject": "Re: KITAS renewal"}],
    )

    loop = MailLoop(
        backend,
        user_id="zero",
        style=ReplyStyleStore(style_path),
        pending=pending,
        dry_run=False,
    )
    summary = asyncio.run(loop.run())

    assert summary.lessons_learned == 1
    text = style_path.read_text(encoding="utf-8")
    assert "## visa/en" in text
    assert "do not quote prices" in text
    # The lesson must not carry what the client or Zero literally wrote.
    assert "12.500.000" not in text
    assert "passport scan" not in text
    # And the buffer entry is consumed, so the same send cannot be learned twice.
    # `take_all` DRAINS, so it is called outside the assert: `python -O` strips
    # assert statements, and a draining call inside one leaves a check that
    # exercises nothing under optimisation. Same class as the two CodeQL flagged
    # in test_learn_and_style.py — a pattern fix is a class audit, not one line.
    remaining = pending.take_all()
    assert remaining == {}


def test_learning_is_idempotent_across_runs(tmp_path: Path, stub_model: None) -> None:
    """A second run over the same Sent folder must not re-learn the same habit."""
    pending = PendingDrafts(tmp_path / "pending.json")
    # The two texts must be an ADJUSTMENT, not a rewrite: below ~0.25 similarity
    # the loop deliberately learns nothing, so a fixture that differs completely
    # would make this test pass for the wrong reason (it would assert 0 == 0).
    pending.add(
        "T-1",
        text=(
            "Dear client, thanks for writing. The fee is IDR 9.000.000 and we can "
            "start today once you confirm."
        ),
        bucket="tax/en",
    )
    sent_body = _body(
        "s1",
        "Re: fee",
        (
            "Dear client, thanks for writing. Our team will send the official "
            "quotation and we can start once you confirm."
        ),
        "zero@balizero.com",
        "T-1",
    )
    backend = FakeBackend(
        inbox=[], bodies={"s1": sent_body},
        sent=[{"messageId": "s1", "threadId": "T-1", "subject": "Re: fee"}],
    )
    style = ReplyStyleStore(tmp_path / "reply-style.md")

    first = asyncio.run(
        MailLoop(backend, user_id="zero", style=style, pending=pending).run()
    )
    second = asyncio.run(
        MailLoop(backend, user_id="zero", style=style, pending=pending).run()
    )

    assert first.lessons_learned == 1
    assert second.lessons_learned == 0


def test_pending_buffer_holds_no_client_identifiers(tmp_path: Path, stub_model: None) -> None:
    """The buffer stores our text and a thread id — not the client.

    If a future edit adds the recipient or the subject here, this file becomes a
    mail archive and breaks the promise the whole loop is built on.
    """
    backend = FakeBackend(
        inbox=[_msg("m1", "KITAS for Sofia Mueller", "sofia.mueller@client.example", "T9")],
        bodies={
            "m1": _body(
                "m1",
                "KITAS for Sofia Mueller",
                "About my KITAS, my number is +62 812 3456 7890.",
                "sofia.mueller@client.example",
                "T9",
            )
        },
    )
    asyncio.run(_loop(backend, tmp_path).run())

    raw = (tmp_path / "pending.json").read_text(encoding="utf-8")
    assert "sofia.mueller@client.example" not in raw
    assert "Sofia Mueller" not in raw
    assert "812 3456 7890" not in raw
    assert "T9" in raw  # the thread id is the only external reference kept


def test_corrupt_pending_buffer_does_not_break_routing(
    tmp_path: Path, stub_model: None
) -> None:
    """Losing the buffer costs learning, never correctness."""
    (tmp_path / "pending.json").write_text("{ this is not json", encoding="utf-8")
    backend = FakeBackend(
        inbox=[_msg("m1", "KITAS renewal", "a@x.example")],
        bodies={"m1": _body("m1", "KITAS renewal", "About my KITAS.", "a@x.example")},
    )
    summary = asyncio.run(_loop(backend, tmp_path).run())
    assert summary.routed == 1
    assert summary.lessons_learned == 0
