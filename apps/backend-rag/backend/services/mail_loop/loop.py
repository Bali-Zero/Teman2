"""Orchestration: route the inbox, draft replies, learn from Sent.

Built on top of the existing `ZohoEmailService`. It opens no connection of its
own, holds no credential of its own, and adds no second copy of the Zoho API
surface — a duplicate organ for a job that already has one is how this codebase
ended up with `apps/cell` next to `packages/cell-core`.

State. Zero asked for nothing to be archived on our side, and nothing is: no
message body, no attachment, no subject, no address. Two exceptions, both narrow
and both ours rather than the client's:

  * `reply-style.md` — the learned habits (see `style`).
  * a pending-comparison buffer of OUR OWN draft text, keyed by Zoho's thread
    id. It exists because Zoho deletes a draft the moment it is sent, so without
    it there is nothing left to diff against on the next run. It stores the text
    we wrote plus a thread id — deliberately NOT the subject, the recipient or
    any identifier — and each entry is deleted as soon as it has been learned
    from or after `PENDING_TTL_DAYS`.

Failure posture. Every step reports what it did and what it could not do. A run
that files thirty messages and drafts nothing must not look like a success: the
summary carries the counts and the caller turns a degraded run into a visible
alert. The alternative — a green cron with an empty output directory — is the
single most repeated failure in this repo's history.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from html import unescape
from pathlib import Path
from typing import Any, Protocol

from backend.services.mail_loop.classify import FOLDER_BY_INTENT, Intent, classify
from backend.services.mail_loop.draft import (
    DraftRequest,
    DraftUnavailable,
    generate,
)
from backend.services.mail_loop.learn import (
    MatchCandidate,
    extract_signals,
    match_sent,
    phrase_lesson,
)
from backend.services.mail_loop.state_io import write_private
from backend.services.mail_loop.style import (
    Lesson,
    ReplyStyleStore,
    bucket_for,
    today,
)

logger = logging.getLogger(__name__)

PENDING_TTL_DAYS = 14
MAX_MESSAGES_PER_RUN = 40

# Marker prepended to a drafted body. Visible to Zero when he opens the draft,
# and a deliberate choice over an HTML comment: a hidden marker would travel
# into the sent mail and reach the client. Zero deletes this line as he edits,
# which is exactly what should happen.
DRAFT_MARKER = "[bozza automatica — rileggi prima di inviare]"


class MailBackend(Protocol):
    """The slice of ZohoEmailService this loop uses.

    Declared as a Protocol so the orchestration can be exercised against a fake
    without a mailbox, a token or a network. The real implementation is
    `services.integrations.zoho_email_service.ZohoEmailService`.
    """

    async def list_folders(self, user_id: str) -> list[dict[str, Any]]: ...

    async def list_emails(
        self,
        user_id: str,
        folder_id: str = "inbox",
        limit: int = 50,
        start: int = 0,
        search_key: str | None = None,
        is_unread: bool | None = None,
    ) -> dict[str, Any]: ...

    async def get_message_content(
        self, user_id: str, folder_id: str, message_id: str
    ) -> str: ...

    async def get_message_headers(
        self, user_id: str, folder_id: str, message_id: str
    ) -> dict[str, str]: ...

    async def move_to_folder(
        self, user_id: str, message_ids: list[str], folder_id: str
    ) -> bool: ...

    async def save_draft(
        self,
        user_id: str,
        to: list[str] | None = None,
        subject: str = "",
        content: str = "",
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        attachments: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]: ...


@dataclass
class RunSummary:
    """What one run actually accomplished. Read by the wrapper, not by a human."""

    seen: int = 0
    routed: int = 0
    left_in_inbox: int = 0
    drafted: int = 0
    draft_failures: int = 0
    lessons_learned: int = 0
    missing_folders: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False

    @property
    def degraded(self) -> bool:
        """True when the run technically completed but did half its job.

        Drafting nothing while there was mail to answer is the shape that must
        never read as success.
        """
        if self.errors or self.missing_folders:
            return True
        if self.seen and self.routed == 0:
            return True
        return bool(self.draft_failures) and self.drafted == 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "seen": self.seen,
            "routed": self.routed,
            "left_in_inbox": self.left_in_inbox,
            "drafted": self.drafted,
            "draft_failures": self.draft_failures,
            "lessons_learned": self.lessons_learned,
            "missing_folders": self.missing_folders,
            "errors": self.errors,
            "dry_run": self.dry_run,
            "degraded": self.degraded,
        }


class PendingDrafts:
    """Short-lived buffer of our own drafts, awaiting comparison with Sent.

    Contains no client data: a thread id, the text we wrote, and a bucket. If a
    future edit adds the recipient or the subject here, that turns this file into
    a mail archive and breaks the promise the loop is built on.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            # A corrupt buffer costs us learning, not correctness. Say so and
            # start clean rather than crashing the routing half.
            logger.warning("pending: unreadable buffer (%s), starting empty", exc)
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self, data: dict[str, dict[str, Any]]) -> None:
        write_private(self.path, json.dumps(data, indent=2, ensure_ascii=False))

    def add(self, thread_id: str, *, text: str, bucket: str) -> None:
        if not thread_id:
            logger.debug("pending: no thread id, this draft cannot be learned from")
            return
        data = self._load()
        data[thread_id] = {"text": text, "bucket": bucket, "ts": time.time()}
        self._save(data)

    def take_all(self) -> dict[str, dict[str, Any]]:
        """Return live entries, dropping expired ones as a side effect."""
        data = self._load()
        cutoff = time.time() - PENDING_TTL_DAYS * 86400
        live = {k: v for k, v in data.items() if float(v.get("ts", 0)) >= cutoff}
        if len(live) != len(data):
            logger.info("pending: expired %d entries", len(data) - len(live))
            self._save(live)
        return live

    def drop(self, thread_id: str) -> None:
        data = self._load()
        if data.pop(thread_id, None) is not None:
            self._save(data)


# --------------------------------------------------------------------------- #
# Shape normalisation.
#
# Two vocabularies meet here and they are NOT the same. Zoho's wire format is
# camelCase (`folderId`, `messageId`, `fromAddress`); `ZohoEmailService`
# deliberately translates it into the snake_case shape its other ten consumers
# — the webmail router included — are written against (`folder_id`,
# `message_id`, `from: {address, name}`).
#
# This module was originally written against the WIRE names while being wired to
# the SERVICE, so every lookup silently missed: folders never resolved (which is
# how the inbox id degraded into the literal string "inbox" and Zoho answered
# UNABLE_TO_PARSE_DATA_TYPE), every message read as "arrived without an id", and
# every draft would have gone out with an empty recipient. Nine read sites, one
# cause. The test suite stayed green throughout because its fake spoke the wire
# names too — a fixture agreeing with the code about a shape neither shares with
# production.
#
# So the translation lives HERE, in one place, and everything downstream reads
# canonical names. Both spellings are accepted on purpose: they denote the same
# entity, and a reader that only understood one is exactly what broke. The
# contract test in test_backend_contract.py pins this against the REAL service
# transform rather than against another hand-written fake.
# --------------------------------------------------------------------------- #

_TAG_RE = re.compile(r"<[^>]+>")


def _first(mapping: dict[str, Any], *keys: str) -> Any:
    """First key that is present and not empty. Order is preference, not luck."""
    for key in keys:
        value = mapping.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _folder_id(folders: list[dict[str, Any]], name: str) -> str | None:
    """Resolve a folder name to its Zoho id, case-insensitively."""
    want = name.strip().lower()
    for folder in folders:
        candidate = str(_first(folder, "folder_name", "folderName", "name") or "")
        if candidate.strip().lower() == want:
            fid = _first(folder, "folder_id", "folderId", "id")
            return str(fid) if fid is not None else None
    return None


def _folder_names(folders: list[dict[str, Any]]) -> list[str]:
    return [str(_first(f, "folder_name", "folderName", "name") or "") for f in folders]


def _message_id(item: dict[str, Any]) -> str:
    return str(_first(item, "message_id", "messageId", "id") or "")


def _thread_id(item: dict[str, Any]) -> str:
    return str(_first(item, "thread_id", "threadId") or "")


def _folder_of(item: dict[str, Any]) -> str:
    return str(_first(item, "folder_id", "folderId") or "")


def _subject_of(item: dict[str, Any]) -> str:
    return str(_first(item, "subject") or "")


def _sender_of(item: dict[str, Any]) -> str:
    """The reply address, from either vocabulary.

    The service nests it (`from: {address, name}`); the wire keeps it flat
    (`fromAddress`, with `sender` as the display name). An address is wanted
    here, so the display name is only a last resort.
    """
    origin = item.get("from")
    if isinstance(origin, dict):
        address = origin.get("address") or origin.get("name")
        if address:
            return str(address)
    if isinstance(origin, str) and origin:
        return origin
    return str(_first(item, "fromAddress", "sender") or "")


def _html_to_text(content: str) -> str:
    """Flatten Zoho's HTML body enough for the classifier to read it.

    The classifier matches word-boundary markers, so tags left in place would
    both hide words behind markup and offer `<a href=...>` as false matches.
    This is not a renderer and does not try to be one.
    """
    if not content or "<" not in content:
        return content
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", content)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", text)
    text = _TAG_RE.sub(" ", text)
    text = unescape(text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def _plain_body(email: dict[str, Any]) -> str:
    """Best available text for a message.

    `text_content` / `html_content` are what the service produces; `content` /
    `body` are the wire names; `snippet` and `summary` are a truncated preview
    and therefore the LAST resort — classifying on a preview means classifying
    on the first two lines of a mail, which is how a visa enquiry that mentions
    KITAS in its third paragraph ends up unrouted.
    """
    for key in ("text_content", "content", "body"):
        value = email.get(key)
        if isinstance(value, str) and value.strip():
            return value
    html = email.get("html_content")
    if isinstance(html, str) and html.strip():
        return _html_to_text(html)
    for key in ("snippet", "summary"):
        value = email.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


class MailLoop:
    """One daily pass over the mailbox."""

    def __init__(
        self,
        backend: MailBackend,
        *,
        user_id: str,
        style: ReplyStyleStore,
        pending: PendingDrafts,
        dry_run: bool = False,
    ) -> None:
        self.backend = backend
        self.user_id = user_id
        self.style = style
        self.pending = pending
        self.dry_run = dry_run

    async def run(self) -> RunSummary:
        summary = RunSummary(dry_run=self.dry_run)

        try:
            folders = await self.backend.list_folders(self.user_id)
        except Exception as exc:  # broad on purpose: reported in the summary, not swallowed
            summary.errors.append(f"list_folders failed: {exc}")
            return summary

        # Check the routing targets NOW, against the listing we already hold.
        #
        # This used to happen lazily, one message at a time, only when a message
        # actually classified into a folder. That made an empty `missing_folders`
        # ambiguous in the worst way: it reads as "all six are there" when it can
        # equally mean "the check never ran" — which is precisely what happened
        # while list_emails was failing upstream and the run reported no missing
        # folders for a mailbox that had none of them.
        for folder_name in sorted(set(FOLDER_BY_INTENT.values())):
            if _folder_id(folders, folder_name) is None:
                summary.missing_folders.append(folder_name)
        if summary.missing_folders:
            logger.warning(
                "loop: %d routing folder(s) absent from the mailbox: %s — mail that "
                "classifies into them will be left in the inbox rather than moved "
                "somewhere arbitrary",
                len(summary.missing_folders),
                ", ".join(summary.missing_folders),
            )

        # Learning first: yesterday's verdict shapes today's drafts.
        try:
            summary.lessons_learned = await self._learn(folders)
        except Exception as exc:
            summary.errors.append(f"learning pass failed: {exc}")

        await self._route_and_draft(folders, summary)
        return summary

    # -- routing ---------------------------------------------------------- #

    async def _route_and_draft(
        self, folders: list[dict[str, Any]], summary: RunSummary
    ) -> None:
        # No fallback to the literal "inbox" here, and that is deliberate. Zoho
        # wants a numeric folder id; handing it a word produces
        # UNABLE_TO_PARSE_DATA_TYPE, so the old `or "inbox"` did not rescue an
        # unresolvable inbox — it converted a clear "I could not find the inbox"
        # into an opaque parser error from a remote API. If the inbox is not in
        # the listing, say so.
        inbox_id = _folder_id(folders, "inbox")
        if inbox_id is None:
            summary.errors.append(
                "no Inbox in the folder listing (saw: "
                f"{', '.join(sorted(n for n in _folder_names(folders) if n)) or 'nothing'})"
            )
            return

        try:
            listing = await self.backend.list_emails(
                self.user_id,
                folder_id=inbox_id,
                limit=MAX_MESSAGES_PER_RUN,
                is_unread=True,
            )
        except Exception as exc:
            summary.errors.append(f"list_emails failed: {exc}")
            return

        messages = listing.get("emails") or listing.get("data") or []
        summary.seen = len(messages)

        for message in messages:
            message_id = _message_id(message)
            if not message_id:
                summary.errors.append("a message arrived without an id, skipped")
                continue
            try:
                await self._handle_one(message_id, message, folders, summary, inbox_id)
            except Exception as exc:  # broad on purpose: one bad message must not
                # abort the run: the remaining mail still deserves routing.
                summary.errors.append(f"message {message_id[:12]}: {exc}")

    async def _handle_one(
        self,
        message_id: str,
        listed: dict[str, Any],
        folders: list[dict[str, Any]],
        summary: RunSummary,
        inbox_id: str,
    ) -> None:
        # Read the body without disturbing the mailbox.
        #
        # The obvious call here is `get_email`, and it is the wrong one: it marks
        # the message read as a side effect. This loop selects on `is_unread`, so
        # a --dry-run — which promises to mutate nothing — would have marked the
        # entire unread inbox as read, and the next real run would have been
        # blind to exactly the mail it was supposed to file. It also re-lists
        # fifty messages per fetch to rebuild metadata `listed` already carries.
        folder_id = _folder_of(listed) or inbox_id
        raw_body = await self.backend.get_message_content(
            self.user_id, folder_id, message_id
        )

        # Headers are evidence, not a requirement: `is_bulk` treats their absence
        # as "no evidence of bulk", never as "not bulk". So a header fetch that
        # fails must not cost us the message — it costs us one signal.
        headers: dict[str, str] = {}
        try:
            headers = await self.backend.get_message_headers(
                self.user_id, folder_id, message_id
            )
        except Exception as exc:
            logger.warning(
                "loop: no headers for %s (%s) — classifying without the bulk signal",
                message_id[:12],
                exc,
            )

        # `subject` comes from the listing; the header blob is the fallback,
        # because the content endpoint returns a body and nothing else.
        subject = _subject_of(listed) or str(headers.get("Subject") or "")
        body = _html_to_text(raw_body) or _plain_body(listed)

        full: dict[str, Any] = {
            "message_id": message_id,
            "folder_id": folder_id,
            "thread_id": _thread_id(listed),
            "subject": subject,
            "text_content": body,
            "from": {"address": _sender_of(listed)},
        }

        verdict = classify(subject, body, headers=headers or None)

        if not verdict.routable:
            summary.left_in_inbox += 1
            logger.info(
                "loop: message %s is %s — left in inbox for a human",
                message_id[:12],
                verdict.intent.value,
            )
            return

        folder_name = verdict.folder or ""
        target = _folder_id(folders, folder_name)
        if target is None:
            if folder_name not in summary.missing_folders:
                summary.missing_folders.append(folder_name)
            summary.left_in_inbox += 1
            logger.warning(
                "loop: folder %r does not exist in Zoho — message left in inbox "
                "rather than moved somewhere arbitrary",
                folder_name,
            )
            return

        if self.dry_run:
            logger.info(
                "loop: DRY-RUN would move %s -> %s (%s/%s)",
                message_id[:12],
                folder_name,
                verdict.intent.value,
                verdict.language,
            )
        else:
            await self.backend.move_to_folder(self.user_id, [message_id], target)
        summary.routed += 1

        if verdict.intent is Intent.NOISE:
            return  # nothing to answer

        await self._draft_reply(full, listed, verdict, summary)

    async def _draft_reply(
        self,
        full: dict[str, Any],
        listed: dict[str, Any],
        verdict: Any,
        summary: RunSummary,
    ) -> None:
        sender = _sender_of(full) or _sender_of(listed)
        subject = _subject_of(full)
        bucket = bucket_for(verdict.intent.value, verdict.language)

        request = DraftRequest(
            subject=subject,
            body=_plain_body(full),
            sender_name=sender,
            language=verdict.language,
            intent=verdict.intent.value,
            style_block=self.style.prompt_block(bucket),
        )

        try:
            text = generate(request, dry_run=self.dry_run)
        except DraftUnavailable as exc:
            summary.draft_failures += 1
            # The subject is CLIENT DATA. It routinely carries a name, a
            # passport number, a company — "KITAS renewal for <person>" is a
            # normal subject line here. SYMBIOSIS Law 2 is absolute about logs
            # (UU PDP Art. 67-68), and this log is world-readable on the Pro and
            # tailed by other organs. Identify the message by its opaque id and
            # its lane; that is everything a human debugging this needs, and it
            # names nobody.
            logger.warning(
                "loop: no draft for %s (%s/%s): %s",
                _message_id(full)[:12] or "?",
                verdict.intent.value,
                verdict.language,
                exc,
            )
            return

        reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        content = f"{DRAFT_MARKER}\n\n{text}"

        if self.dry_run:
            # Same rule as above: no subject in the log. Length and lane are the
            # facts worth having; the subject is somebody's business.
            logger.info(
                "loop: DRY-RUN would save draft for %s (%s/%s, %d chars)",
                _message_id(full)[:12] or "?",
                verdict.intent.value,
                verdict.language,
                len(content),
            )
        else:
            await self.backend.save_draft(
                self.user_id,
                to=[sender] if sender else [],
                subject=reply_subject,
                content=content,
            )
            thread_id = _thread_id(full) or _thread_id(listed)
            self.pending.add(thread_id, text=text, bucket=bucket)

        summary.drafted += 1

    # -- learning --------------------------------------------------------- #

    async def _learn(self, folders: list[dict[str, Any]]) -> int:
        pending = self.pending.take_all()
        if not pending:
            return 0

        sent_id = _folder_id(folders, "sent") or _folder_id(folders, "sent items")
        if sent_id is None:
            logger.warning("learn: no Sent folder found, cannot learn this run")
            return 0

        listing = await self.backend.list_emails(
            self.user_id, folder_id=sent_id, limit=MAX_MESSAGES_PER_RUN
        )
        sent_messages = listing.get("emails") or listing.get("data") or []

        candidates: list[MatchCandidate] = []
        for item in sent_messages:
            mid = _message_id(item)
            if not mid:
                continue
            # Same reasoning as _handle_one: read the body, do not mark our own
            # Sent mail read, and do not re-list the folder once per message.
            try:
                raw_body = await self.backend.get_message_content(
                    self.user_id, _folder_of(item) or sent_id, mid
                )
            except Exception as exc:
                logger.warning("learn: could not read sent message %s: %s", mid[:12], exc)
                continue
            candidates.append(
                MatchCandidate(
                    message_id=mid,
                    thread_id=_thread_id(item) or None,
                    subject=_subject_of(item),
                    to=(),
                    body=_html_to_text(raw_body) or _plain_body(item),
                )
            )

        learned = 0
        for thread_id, entry in pending.items():
            # Thread id only. The buffer holds no subject and no recipient, so
            # the subject+recipient fallback in match_sent cannot fire here —
            # that is the intended cost of keeping client data out of the file.
            hit = match_sent(
                draft_thread_id=thread_id,
                draft_subject="",
                draft_to=(),
                candidates=candidates,
            )
            if hit is None:
                continue  # still unanswered, or sent outside this window

            bucket = str(entry.get("bucket") or "global")
            language = bucket.split("/")[-1] if "/" in bucket else "en"
            intent = bucket.split("/")[0] if "/" in bucket else "global"

            signals = extract_signals(str(entry.get("text") or ""), hit.body, language=language)
            lesson_text = phrase_lesson(signals, intent=intent, language=language)
            self.pending.drop(thread_id)

            if lesson_text is None:
                continue
            if self.style.append(
                Lesson(bucket=bucket, text=lesson_text, observed_on=today())
            ):
                learned += 1
                logger.info("learn: new lesson in %s", bucket)

        return learned
