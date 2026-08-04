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
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from backend.services.mail_loop.classify import Intent, classify
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

    async def get_email(
        self, user_id: str, message_id: str, folder_id: str | None = None
    ) -> dict[str, Any]: ...

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
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

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


def _folder_id(folders: list[dict[str, Any]], name: str) -> str | None:
    """Resolve a folder name to its Zoho id, case-insensitively."""
    want = name.strip().lower()
    for folder in folders:
        candidate = str(folder.get("folderName") or folder.get("name") or "")
        if candidate.strip().lower() == want:
            fid = folder.get("folderId") or folder.get("id")
            return str(fid) if fid is not None else None
    return None


def _plain_body(email: dict[str, Any]) -> str:
    for key in ("content", "body", "summary", "snippet"):
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
        inbox_id = _folder_id(folders, "inbox") or "inbox"
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
            message_id = str(message.get("messageId") or message.get("id") or "")
            if not message_id:
                summary.errors.append("a message arrived without an id, skipped")
                continue
            try:
                await self._handle_one(message_id, message, folders, summary)
            except Exception as exc:  # broad on purpose: one bad message must not
                # abort the run: the remaining mail still deserves routing.
                summary.errors.append(f"message {message_id[:12]}: {exc}")

    async def _handle_one(
        self,
        message_id: str,
        listed: dict[str, Any],
        folders: list[dict[str, Any]],
        summary: RunSummary,
    ) -> None:
        full = await self.backend.get_email(self.user_id, message_id)
        subject = str(full.get("subject") or listed.get("subject") or "")
        body = _plain_body(full) or _plain_body(listed)
        headers = full.get("headers") if isinstance(full.get("headers"), dict) else None

        verdict = classify(subject, body, headers=headers)

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
        sender = str(
            full.get("fromAddress") or listed.get("sender") or listed.get("from") or ""
        )
        subject = str(full.get("subject") or "")
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
            logger.warning("loop: no draft for %s: %s", subject[:40], exc)
            return

        reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        content = f"{DRAFT_MARKER}\n\n{text}"

        if self.dry_run:
            logger.info("loop: DRY-RUN would save draft %r (%d chars)", reply_subject, len(content))
        else:
            await self.backend.save_draft(
                self.user_id,
                to=[sender] if sender else [],
                subject=reply_subject,
                content=content,
            )
            thread_id = str(full.get("threadId") or listed.get("threadId") or "")
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
            mid = str(item.get("messageId") or item.get("id") or "")
            if not mid:
                continue
            full = await self.backend.get_email(self.user_id, mid)
            candidates.append(
                MatchCandidate(
                    message_id=mid,
                    thread_id=str(full.get("threadId") or item.get("threadId") or "") or None,
                    subject=str(full.get("subject") or ""),
                    to=(),
                    body=_plain_body(full),
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
