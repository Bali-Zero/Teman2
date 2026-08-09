"""The seam: what `ZohoEmailService` PRODUCES must be what the mail loop READS.

This file exists because both sides were individually well tested and the join
between them was broken in nine places at once.

Zoho puts camelCase on the wire (`folderId`, `messageId`, `fromAddress`).
`ZohoEmailService` deliberately translates that into the snake_case shape its
ten other consumers — the webmail router included — are written against
(`folder_id`, `message_id`, `from: {address, name}`). The loop was written
against the WIRE names while being wired to the SERVICE, so every lookup
silently missed: no folder ever resolved (which is how the inbox id degraded
into the literal string "inbox" and Zoho answered UNABLE_TO_PARSE_DATA_TYPE),
every message read as "arrived without an id", and every draft would have gone
out with an empty recipient.

The unit suites stayed green the whole time, because the loop's fake spoke the
wire names too. A fake and the code agreeing about a vocabulary neither shares
with production is not evidence — so the fake here is placed at the HTTP
boundary (`_request`) instead. Everything above it is the real transform.

The raw payloads below are the shapes measured against the live Zoho API on
2026-08-05 by a read-only probe, not invented. (The observed key list for a
message was read through a display cap, so more keys may exist upstream —
nothing here depends on that list being complete.)
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from backend.services.integrations.zoho_email_service import ZohoEmailService
from backend.services.mail_loop.loop import (
    _folder_id,
    _folder_of,
    _message_id,
    _plain_body,
    _sender_of,
    _subject_of,
    _thread_id,
)

# --- raw wire payloads, as Zoho actually answers -------------------------- #

RAW_FOLDERS = [
    {
        "folderId": "1228340000000008014",
        "folderName": "Inbox",
        "folderType": "Inbox",
        "folderPath": "/Inbox",
        "unreadCount": 2,
        "messageCount": 91,
    },
    {
        "folderId": "1228340000000008016",
        "folderName": "Sent",
        "folderType": "Sent",
        "folderPath": "/Sent",
    },
    {
        "folderId": "1228340000000123456",
        "folderName": "_Visa",
        "folderType": "custom",
        "folderPath": "/_Visa",
    },
]

RAW_MESSAGE = {
    "messageId": "1785808829789153900",
    "folderId": "1228340000000008014",
    "threadId": "1785808829789100001",
    "subject": "KITAS renewal",
    "fromAddress": "client@example.test",
    "sender": "A Client",
    "toAddress": "zero@balizero.com",
    "summary": "My KITAS expires next month",
    "receivedTime": "1754300000000",
    "status": "0",
    "hasAttachment": False,
}


class _RecordingService(ZohoEmailService):
    """The real service with only its HTTP call replaced.

    Subclassed rather than monkeypatched so the override cannot drift from the
    signature it is standing in for.
    """

    def __init__(self, replies: dict[str, Any]) -> None:
        super().__init__(db_pool=None)  # type: ignore[arg-type]
        self._replies = replies
        self.requests: list[tuple[str, str]] = []

    async def _request(  # type: ignore[override]
        self,
        user_id: str,
        method: str,
        endpoint: str,
        json_data: dict | None = None,
        params: dict | None = None,
    ) -> dict[str, Any]:
        self.requests.append((method, endpoint))
        for key, reply in self._replies.items():
            if endpoint.endswith(key) or endpoint == key:
                return reply
        raise AssertionError(f"unexpected call: {method} {endpoint}")


def _folders() -> list[dict[str, Any]]:
    service = _RecordingService({"/folders": {"data": RAW_FOLDERS}})
    return asyncio.run(service.list_folders("u1"))


def _messages() -> list[dict[str, Any]]:
    service = _RecordingService({"/messages/view": {"data": [RAW_MESSAGE]}})
    listing = asyncio.run(service.list_emails("u1", folder_id="1228340000000008014"))
    return listing["emails"]


class TestFolderVocabulary:
    """A folder the service produced must be resolvable by the loop."""

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Inbox", "1228340000000008014"),
            ("inbox", "1228340000000008014"),  # the loop asks in lower case
            ("Sent", "1228340000000008016"),
            ("_Visa", "1228340000000123456"),
        ],
    )
    def test_the_loop_resolves_folders_the_service_returned(
        self, name: str, expected: str
    ) -> None:
        assert _folder_id(_folders(), name) == expected

    def test_an_absent_folder_is_none_not_a_guess(self) -> None:
        """Innocence: resolution must not invent an id for a folder that is gone.

        Without this, the guilt case above could be satisfied by a `_folder_id`
        that returns something for every name it is asked about.
        """
        assert _folder_id(_folders(), "_Tax") is None

    def test_the_service_does_not_speak_the_wire_vocabulary(self) -> None:
        """Pins WHICH vocabulary is real, so the loop cannot go back to guessing.

        If a future change makes `list_folders` pass Zoho's payload through
        untranslated, this fails loudly here rather than silently in a cron.
        """
        folder = _folders()[0]
        assert "folder_name" in folder and "folder_id" in folder
        assert "folderName" not in folder and "folderId" not in folder


class TestMessageVocabulary:
    """Every field the loop reads off a listed message must actually arrive."""

    def test_every_reader_resolves(self) -> None:
        message = _messages()[0]
        assert _message_id(message) == RAW_MESSAGE["messageId"]
        assert _thread_id(message) == RAW_MESSAGE["threadId"]
        assert _folder_of(message) == RAW_MESSAGE["folderId"]
        assert _subject_of(message) == RAW_MESSAGE["subject"]
        assert _sender_of(message) == RAW_MESSAGE["fromAddress"]

    def test_the_sender_is_an_address_not_a_display_name(self) -> None:
        """`sender` is the human-readable name; a draft addressed to it bounces."""
        assert _sender_of(_messages()[0]) != RAW_MESSAGE["sender"]

    def test_the_snippet_is_the_last_resort_body(self) -> None:
        """A listing carries only a preview — usable, but only if nothing better."""
        message = _messages()[0]
        assert _plain_body(message) == RAW_MESSAGE["summary"]
        assert _plain_body({**message, "text_content": "the whole mail"}) == (
            "the whole mail"
        )


class TestReadingDoesNotMutate:
    """A pass over the mailbox must not change it. `--dry-run` depends on it."""

    def test_content_fetch_issues_one_get_and_no_write(self) -> None:
        service = _RecordingService({"/content": {"data": {"content": "<p>hello</p>"}}})
        body = asyncio.run(service.get_message_content("u1", "F1", "M1"))

        assert body == "<p>hello</p>"
        assert service.requests == [("GET", "/folders/F1/messages/M1/content")]
        # The method this replaces (`get_email`) marks the message read on every
        # fetch. On a loop that selects `is_unread`, that would have made a dry
        # run mark the whole unread inbox as read.
        assert all(method == "GET" for method, _ in service.requests)

    def test_headers_survive_folding_and_repetition(self) -> None:
        blob = (
            "Received: from a.example by b.example;\r\n"
            "\tTue, 05 Aug 2026 03:00:00 +0800\r\n"
            "Subject: Perpanjangan KITAS\r\n"
            "List-Unsubscribe: <mailto:u@example.test>,\r\n"
            " <https://example.test/u>\r\n"
            "Auto-Submitted: auto-generated\r\n"
        )
        service = _RecordingService({"/header": {"data": {"headerContent": blob}}})
        headers = asyncio.run(service.get_message_headers("u1", "F1", "M1"))

        assert headers["Subject"] == "Perpanjangan KITAS"
        assert headers["Auto-Submitted"] == "auto-generated"
        # Folded across two lines: a split(":") parser loses the second half.
        assert "https://example.test/u" in headers["List-Unsubscribe"]

    def test_absent_headers_are_empty_not_an_error(self) -> None:
        """Missing headers mean "no evidence", never "not bulk"."""
        service = _RecordingService({"/header": {"data": {}}})
        assert asyncio.run(service.get_message_headers("u1", "F1", "M1")) == {}
