"""Anello 1b — feed LIVE WhatsApp media into the intake queue.

This is the DB-coupled half of Anello 1b. It chains the two pure pieces:

    webhook dict
      → parse_media_webhook()            (pure, tested on M5)
      → download_media() per attachment  (pure I/O, tested on M5 with mocks)
      → enqueue(... received_by=...)      (DB — tested on the Pro nuzantara_dev)

The pure pieces are fully unit-tested anywhere. THIS module does real DB writes
via ``enqueue`` and real Meta downloads, so its integration test MUST run on the
Pro against nuzantara_dev (the pool fixture skips if the DSN is unreachable, and
skipping on M5 hid 4 real bugs in #1145 — do NOT trust an M5 skip as a pass).

Law 2 (sovereignty): client PII (passports/KTP) is downloaded to ``dest_dir``,
which the caller chooses. Where this runs (Fly vs Pro) and therefore where
``dest_dir`` physically lives is a deliberate upstream decision — this module
only takes a directory. It NEVER sends bytes to a third-party cloud.

⚠️ received_by resolution is intentionally CALLER-SUPPLIED. There is no
``phone_number_id → team owner`` mapping in the system today: the live flow has
ONE official BALI ZERO line (phone_number_id=1104946272705747) shared by the
whole team, so "who received it" is NOT derivable from the line alone. Options
the caller may implement (out of scope here): (a) the team member currently
assigned to the conversation in whatsapp_message_context.team_member_email;
(b) the client's existing assigned_to; (c) None → the doc is a NO-receiver
orphan that falls back to assigned_to scoping in the gate. This module does not
guess — it records whatever ``resolve_received_by`` returns.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

import asyncpg
import httpx

from backend.channels.whatsapp.media_download import (
    MediaDownloadError,
    download_media,
)
from backend.channels.whatsapp.media_webhook_parse import (
    InboundMedia,
    parse_media_webhook,
)
from backend.services.intake.contact_autocreate import resolve_or_create_contact
from backend.services.intake.enqueue import EnqueueResult, enqueue

logger = logging.getLogger(__name__)

_SOURCE = "whatsapp"  # reuses the existing chk_iq_source value (live + export share it)

# Resolver signature: given the parsed media, return the team-member email that
# should OWN this document in the gate (or None for an assigned_to-scoped orphan).
ReceivedByResolver = Callable[[InboundMedia], Awaitable[str | None]]


@dataclass
class IngestCounters:
    """Outcome counters for one webhook ingest call."""

    media_found: int = 0
    enqueued_new: int = 0
    already_present: int = 0
    download_errors: int = 0
    enqueue_errors: int = 0


async def ingest_live_media(
    raw_event: dict,
    *,
    pool: asyncpg.Pool,
    http_client: httpx.AsyncClient,
    access_token: str,
    dest_dir: str | Path,
    resolve_received_by: ReceivedByResolver,
    api_version: str = "v18.0",
) -> IngestCounters:
    """Parse a Meta webhook, download each attachment, enqueue it for intake.

    Idempotent end-to-end: ``download_media`` names blobs by media_id and
    ``enqueue`` dedups on intake_key, so re-delivering the same webhook (Meta
    retries) does not create duplicates. A download failure on one attachment
    does NOT abort the others — it's counted and the message is left for Meta
    to retry (we never silently drop a client's document).

    Args:
        raw_event: The Meta webhook JSON body.
        pool: Persistent asyncpg pool (Golden Rule #10).
        http_client: Persistent httpx client for Meta GETs (Golden Rule #10).
        access_token: WHATSAPP_ACCESS_TOKEN.
        dest_dir: Local sovereign directory for downloaded blobs (Law 2).
        resolve_received_by: Async fn mapping a parsed media to the owning
            team-member email (or None). See module docstring — no mapping is
            assumed here.
        api_version: Meta Graph API version.

    Returns:
        IngestCounters describing what happened.
    """
    parsed = parse_media_webhook(raw_event)
    counters = IngestCounters(media_found=len(parsed.media))
    if not parsed.media:
        return counters

    for media in parsed.media:
        # 1. Download (pure I/O) — failure isolates to this attachment.
        try:
            downloaded = await download_media(
                http_client,
                media_id=media.media_id,
                access_token=access_token,
                dest_dir=dest_dir,
                api_version=api_version,
            )
        except MediaDownloadError:
            logger.exception("live WA media download failed media_id=%s", media.media_id)
            counters.download_errors += 1
            continue

        # 2. Resolve who owns it (caller policy — may be None).
        try:
            received_by = await resolve_received_by(media)
        except Exception:
            logger.exception("received_by resolver failed media_id=%s", media.media_id)
            received_by = None

        # 2b. Identity capture at the door (intake-v2 PR-1). The sender phone
        #     is ALWAYS present on WhatsApp — resolve it to a client_id_hint so
        #     the document never lands 0-candidate for the trivial reason that
        #     nobody ever created a contact for this number. Team-roster
        #     numbers never get a contact (they're forwarders); unknown
        #     numbers auto-create a minimal contact when
        #     INTAKE_AUTOCREATE_CONTACT_ENABLED is armed (default OFF — until
        #     then this degrades to "existing match only", never worse than
        #     today). A resolver fault must NOT drop the document — it just
        #     falls back to no hint, same as before this feature existed.
        client_id_hint: int | None = None
        try:
            async with pool.acquire() as identity_conn:
                async with identity_conn.transaction():
                    resolution = await resolve_or_create_contact(
                        identity_conn, sender_phone=media.from_phone
                    )
            client_id_hint = resolution.client_id
            logger.info(
                "contact_autocreate: media_id=%s kind=%s client_id=%s",
                media.media_id,
                resolution.kind,
                resolution.client_id,
            )
        except Exception:
            logger.exception(
                "contact_autocreate resolver failed media_id=%s — falling back "
                "to no client_id_hint",
                media.media_id,
            )

        # 3. Enqueue (DB) — source_ref ties the queue row back to the WA message
        #    so the live flow is distinguishable from the export flow and the
        #    intake_key is stable across Meta retries.
        source_ref = f"whatsapp-live:{media.wa_message_id or media.media_id}"
        try:
            result: EnqueueResult = await enqueue(
                pool,
                source=_SOURCE,
                source_ref=source_ref,
                blob_path=downloaded.blob_path,
                mime_type=downloaded.mime_type,
                blob_hash=downloaded.sha256,
                byte_size=downloaded.byte_size,
                received_by=received_by,
                sender_phone=media.from_phone,
                client_id_hint=client_id_hint,
            )
        except Exception:
            logger.exception("live WA enqueue failed media_id=%s", media.media_id)
            counters.enqueue_errors += 1
            continue

        if result.was_new:
            counters.enqueued_new += 1
        else:
            counters.already_present += 1

    logger.info(
        "live WA ingest: found=%d new=%d dup=%d dl_err=%d enq_err=%d",
        counters.media_found,
        counters.enqueued_new,
        counters.already_present,
        counters.download_errors,
        counters.enqueue_errors,
    )
    return counters
