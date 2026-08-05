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

# The fixtures speak the shape `ZohoEmailService` PRODUCES (snake_case,
# `from: {address}`), not the camelCase Zoho puts on the wire.
#
# They used to speak the wire shape, and that is how this suite stayed green over
# a loop that could not resolve a single folder, could not read a single message
# id, and would have sent every draft to an empty recipient: the fake agreed with
# the code about a vocabulary neither of them shared with the real backend. A
# fixture is only evidence if it is shaped like the thing it stands in for —
# which is what test_backend_contract.py now checks against the real transform.
FOLDERS = [
    {"folder_id": "F-INBOX", "folder_name": "Inbox"},
    {"folder_id": "F-SENT", "folder_name": "Sent"},
    {"folder_id": "F-VISA", "folder_name": "_Visa"},
    {"folder_id": "F-TAX", "folder_name": "_Tax"},
    {"folder_id": "F-PTPMA", "folder_name": "_PTPMA"},
    {"folder_id": "F-PROPERTY", "folder_name": "_Property"},
    {"folder_id": "F-ADMIN", "folder_name": "_Admin"},
    {"folder_id": "F-NOISE", "folder_name": "_Noise"},
]


class FakeBackend:
    """Records mutations. Deliberately not a MagicMock: the recorded calls are
    the assertions, and a mock would happily accept a method that does not exist
    on the real service."""

    def __init__(
        self,
        inbox: list[dict[str, Any]],
        bodies: dict[str, str],
        sent: list[dict[str, Any]] | None = None,
        folders: list[dict[str, Any]] | None = None,
        headers: dict[str, dict[str, str]] | None = None,
    ) -> None:
        self.inbox = inbox
        self.bodies = bodies
        self.sent = sent or []
        self.folders = folders if folders is not None else FOLDERS
        self.headers = headers or {}
        self.moves: list[tuple[list[str], str]] = []
        self.drafts: list[dict[str, Any]] = []
        self.reads: list[str] = []

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

    async def get_message_content(
        self, user_id: str, folder_id: str, message_id: str
    ) -> str:
        self.reads.append(message_id)
        return self.bodies[message_id]

    async def get_message_headers(
        self, user_id: str, folder_id: str, message_id: str
    ) -> dict[str, str]:
        return self.headers.get(message_id, {})

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
        return {"message_id": f"D-{len(self.drafts)}"}


def _msg(mid: str, subject: str, sender: str, thread: str = "") -> dict[str, Any]:
    """One entry as `ZohoEmailService.list_emails` transforms it."""
    return {
        "message_id": mid,
        "folder_id": "F-INBOX",
        "thread_id": thread,
        "subject": subject,
        "from": {"address": sender, "name": ""},
        "snippet": "",
    }


def _sent(mid: str, subject: str, thread: str) -> dict[str, Any]:
    """One entry from the Sent folder, same transform, different folder."""
    return {
        "message_id": mid,
        "folder_id": "F-SENT",
        "thread_id": thread,
        "subject": subject,
        "from": {"address": "zero@balizero.com", "name": "Zero"},
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
        bodies={"m1": "My KITAS expires next month, what do you need?"},
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
        bodies={"m1": "How do I file my SPT?"},
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
        bodies={"m1": "About my KITAS extension."},
        folders=[
            {"folder_id": "F-INBOX", "folder_name": "Inbox"},
            {"folder_id": "F-SENT", "folder_name": "Sent"},
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
        bodies={"m1": "Just saying hi, hope you are well."},
    )
    summary = asyncio.run(_loop(backend, tmp_path).run())
    assert backend.moves == []
    assert backend.drafts == []
    assert summary.left_in_inbox == 1


def test_noise_is_filed_but_never_answered(tmp_path: Path, stub_model: None) -> None:
    backend = FakeBackend(
        inbox=[_msg("m1", "Immigration newsletter", "news@x.example")],
        bodies={"m1": "Our monthly roundup on KITAS rules."},
        # Headers arrive from their own endpoint now, not folded into the body
        # payload — which is also the only place Zoho actually exposes them.
        headers={"m1": {"List-Unsubscribe": "<mailto:u@x.example>"}},
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
        bodies={"m1": "About my KITAS."},
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
        bodies={"m1": "About my KITAS."},
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
        bodies={"m2": "About my KITAS."},
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

    sent_body = (
        "Dear client, thanks for writing. For the KITAS renewal our team will "
        "send the official quotation shortly. Could you send the passport scan?"
    )
    backend = FakeBackend(
        inbox=[],
        bodies={"s1": sent_body},
        sent=[_sent("s1", "Re: KITAS renewal", "T-42")],
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
    sent_body = (
        "Dear client, thanks for writing. Our team will send the official "
        "quotation and we can start once you confirm."
    )
    backend = FakeBackend(
        inbox=[], bodies={"s1": sent_body},
        sent=[_sent("s1", "Re: fee", "T-1")],
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
        bodies={"m1": "About my KITAS, my number is +62 812 3456 7890."},
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
        bodies={"m1": "About my KITAS."},
    )
    summary = asyncio.run(_loop(backend, tmp_path).run())
    assert summary.routed == 1
    assert summary.lessons_learned == 0


# --------------------------------------------------------------------------- #
# A quiet day is not a broken day.                                            #
#                                                                             #
# Measured live on 2026-08-05, the second real run: 12 messages seen, 12       #
# declined by the classifier, 12 left where a human would see them — the       #
# correct outcome — reported as DEGRADED with a P0. An alarm that fires on the #
# correct outcome is an alarm nobody reads, and the gateway had already        #
# spooled a P0 for budget overflow that same night.                           #
#                                                                             #
# The first narrowing read "something WAS routable and none of it moved".      #
# Mutation-testing killed it: deleting the branch changed no test, because it   #
# had become UNREACHABLE — with routed==0 and no errors/missing folders, every  #
# seen message is necessarily counted unroutable. What replaced it is a         #
# conservation law (`unaccounted`), and the guilt half below aims at THAT,      #
# not at a branch that fires earlier.                                          #
# --------------------------------------------------------------------------- #


def test_a_run_that_understood_nothing_is_clean(tmp_path: Path, stub_model: None) -> None:
    """INNOCENCE: every message declined, nothing moved — not degraded."""
    backend = FakeBackend(
        inbox=[
            _msg("m1", "Re: lunch", "a@x.example", "T1"),
            _msg("m2", "Photos from Sunday", "b@x.example", "T2"),
        ],
        bodies={
            "m1": "Are we still on for Thursday? Let me know.",
            "m2": "Sending the pictures we took, hope you like them.",
        },
    )
    summary = asyncio.run(_loop(backend, tmp_path).run())

    assert summary.seen == 2
    assert summary.routed == 0
    assert summary.unroutable == 2, "premise: the classifier must have DECLINED both"
    assert summary.left_in_inbox == 2
    assert summary.unaccounted == 0
    assert summary.degraded is False
    assert backend.moves == [], "a clean quiet day must still mutate nothing"


def test_a_message_that_reached_no_outcome_is_degraded(
    tmp_path: Path, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GUILT: the conservation law, aimed at the ending that does not exist yet.

    Today every message ends routed, left-in-inbox or errored, so this shape is
    only reachable by simulating the edit that would introduce a fourth: a
    silent `return` out of `_handle_one` that touches no counter — a filter on
    message age, a "skip anything from ourselves", a guard added in a hurry.
    That is precisely the run that would otherwise report success while doing
    nothing, so the test injects it rather than waiting for someone to write it.
    """
    backend = FakeBackend(
        inbox=[_msg("m1", "KITAS renewal", "a@x.example", "T1")],
        bodies={"m1": "My KITAS expires next month, what do you need?"},
    )
    loop = _loop(backend, tmp_path)

    async def _silently_skip(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(loop, "_handle_one", _silently_skip)
    summary = asyncio.run(loop.run())

    assert summary.seen == 1
    assert not summary.errors, "premise: nothing raised"
    assert not summary.missing_folders, "premise: no folder was missing"
    assert summary.unaccounted == 1
    assert summary.degraded is True


def test_a_message_that_raised_is_accounted_for(
    tmp_path: Path, stub_model: None
) -> None:
    """A crash is a legal ending — it must not ALSO read as unaccounted.

    Otherwise the conservation law would double-count the shape the errors
    branch already reports, and `unaccounted` would stop meaning "nobody
    noticed this message".
    """
    backend = FakeBackend(
        inbox=[_msg("m1", "KITAS renewal", "a@x.example", "T1")],
        bodies={},  # get_message_content will raise KeyError
    )
    summary = asyncio.run(_loop(backend, tmp_path).run())

    assert summary.seen == 1
    assert summary.message_errors == 1
    assert summary.errors, "premise: the message must have raised"
    assert summary.unaccounted == 0
    assert summary.degraded is True  # via the errors branch, not the law


def test_a_missing_folder_is_accounted_for(tmp_path: Path, stub_model: None) -> None:
    """The other legal non-move: routable, but its folder is gone.

    It lands in `left_in_inbox`, so the law stays quiet and `missing_folders`
    does the reporting. Pins that the two guards do not overlap.
    """
    backend = FakeBackend(
        inbox=[_msg("m1", "KITAS renewal", "a@x.example", "T1")],
        bodies={"m1": "My KITAS expires next month, what do you need?"},
        folders=[f for f in FOLDERS if f.get("folder_name") != "_Visa"],
    )
    summary = asyncio.run(_loop(backend, tmp_path).run())

    assert summary.routed == 0
    assert summary.unroutable == 0, "premise: the message WAS routable"
    assert summary.missing_folders == ["_Visa"]
    assert summary.unaccounted == 0
    assert summary.degraded is True


def test_mixed_day_with_one_routed_is_clean(tmp_path: Path, stub_model: None) -> None:
    """INNOCENCE: one defensible routing among declines is a good day."""
    backend = FakeBackend(
        inbox=[
            _msg("m1", "KITAS renewal", "a@x.example", "T1"),
            _msg("m2", "Re: lunch", "b@x.example", "T2"),
        ],
        bodies={
            "m1": "My KITAS expires next month, what do you need?",
            "m2": "Are we still on for Thursday?",
        },
    )
    summary = asyncio.run(_loop(backend, tmp_path).run())

    assert summary.routed == 1
    assert summary.unroutable == 1
    assert summary.degraded is False


def test_unroutable_is_reported_so_a_quiet_day_is_explicable(
    tmp_path: Path, stub_model: None
) -> None:
    """The wrapper's log must be able to say WHY a run moved nothing.

    Without the count in the summary, "routed 0, clean" and "routed 0, broken"
    read identically to whoever finds the log at 07:30.
    """
    backend = FakeBackend(
        inbox=[_msg("m1", "Re: lunch", "a@x.example", "T1")],
        bodies={"m1": "Are we still on for Thursday?"},
    )
    summary = asyncio.run(_loop(backend, tmp_path).run())
    reported = summary.as_dict()
    assert reported["unroutable"] == 1
    assert reported["unaccounted"] == 0


def test_a_draft_that_crashes_after_the_move_does_not_unbalance_the_law(
    tmp_path: Path, stub_model: None
) -> None:
    """GUILT: the shape that made `unaccounted` read -1, reproduced.

    The message moves, then Zoho refuses to store the reply. Before the fix
    `routed` was incremented inside `_handle_one` and the crash propagated to
    the caller's per-message handler, which added `message_errors` on top —
    two endings for one message, `unaccounted == -1`.

    A negative value is truthy, so the run still read degraded and the defect
    was invisible. What it really costs is cancellation: a `-1` here silently
    absorbs a genuine `+1` elsewhere in the same run, and the law reports
    balanced while hiding both.
    """

    class RefusesToSaveDrafts(FakeBackend):
        async def save_draft(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("Zoho API 500 while saving draft")

    backend = RefusesToSaveDrafts(
        inbox=[_msg("m1", "KITAS renewal", "a@x.example", "T1")],
        bodies={"m1": "My KITAS expires next month, what do you need?"},
    )
    summary = asyncio.run(_loop(backend, tmp_path).run())

    assert backend.moves == [(["m1"], "F-VISA")], "premise: the message DID move"
    assert summary.errors, "premise: the draft step DID fail"
    assert summary.routed == 1
    assert summary.message_errors == 0, "a moved message is not also an error-ending"
    assert summary.unaccounted == 0
    assert summary.draft_failures == 1
    assert summary.degraded is True  # via errors + drafted==0, not via the law


def test_the_law_cannot_net_out(tmp_path: Path, stub_model: None) -> None:
    """Two messages, one crashing after its move and one silently skipped.

    This is the run the cancellation would hide: before the fix the crash gave
    -1 and the skip gave +1, so `unaccounted` read 0 and a run that lost a
    message reported balanced. Each defect must now be visible on its own.
    """

    class RefusesToSaveDrafts(FakeBackend):
        async def save_draft(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("Zoho API 500 while saving draft")

    backend = RefusesToSaveDrafts(
        inbox=[
            _msg("m1", "KITAS renewal", "a@x.example", "T1"),
            _msg("m2", "PT PMA setup", "b@x.example", "T2"),
        ],
        bodies={
            "m1": "My KITAS expires next month, what do you need?",
            "m2": "I want to open a PT PMA, what is required?",
        },
    )
    loop = _loop(backend, tmp_path)
    real_handle_one = loop._handle_one

    async def _skip_the_second(
        message_id: str, *args: Any, **kwargs: Any
    ) -> Any:
        if message_id == "m2":
            return None  # the fourth ending nobody recorded
        return await real_handle_one(message_id, *args, **kwargs)

    loop._handle_one = _skip_the_second  # type: ignore[method-assign]
    summary = asyncio.run(loop.run())

    assert summary.seen == 2
    assert summary.unaccounted == 1, "the skipped message must still show"
    assert summary.degraded is True
