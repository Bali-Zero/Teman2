"""
Telegram Webhook Router - Multi-Channel Architecture.

Handles incoming Telegram Bot API updates using ChannelRouter.
Intercepts callback_query updates for intel approval voting.
Supports Agent Mesh: routes team member messages with role context.

Author: Claude Sonnet 4.5
Date: 2026-02-10
Updated: 2026-04-03 (Agent Mesh team member routing)
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request

from backend.app.core.config import settings
from backend.app.core.intel_approvers import get_required_votes
from backend.app.dependencies import get_channel_router
from backend.channels.router import ChannelRouter
from backend.services.integrations.telegram_bot_service import telegram_bot

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Agent Mesh — Team Member Lookup
# ═══════════════════════════════════════════════════════════════════

async def _resolve_team_agent(request: Request, chat_id: int | None) -> dict[str, Any] | None:
    """
    Resolve a Telegram chat_id to a team member agent context.

    Lookup chain: chat_id → messaging_users.user_id → user_profiles.email → TEAM_AGENTS config

    Returns:
        Agent context dict or None if not a registered team member.
    """
    if not chat_id:
        return None

    db_pool = getattr(request.app.state, "db_pool", None)
    if not db_pool:
        return None

    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT mu.user_id, mu.display_name, up.email, up.full_name
                FROM messaging_users mu
                JOIN user_profiles up ON up.id = mu.user_id
                WHERE mu.telegram_chat_id = $1
                  AND mu.channel = 'telegram'
                  AND mu.active = TRUE
                """,
                chat_id,
            )

        if not row:
            return None

        from backend.services.agents.team_agent_config import build_agent_context

        ctx = build_agent_context(
            email=row["email"],
            full_name=row["full_name"] or row["display_name"] or "Team Member",
        )

        if ctx:
            logger.info(
                f"🤖 Agent Mesh: {row['email']} → role={ctx['agent_role']}, "
                f"scope={ctx['agent_client_scope']}",
            )

        return ctx

    except Exception as e:
        logger.warning(f"Agent mesh lookup failed for chat_id={chat_id}: {e}")
        return None

router = APIRouter(prefix="/webhook", tags=["telegram"])


async def handle_intel_callback(callback_query: dict[str, Any]) -> bool:
    """
    Handle intel approval/rejection callback queries from Telegram inline keyboards.

    Callback data format: intel:{action}:{intel_type}:{item_id}
    Example: intel:approve:news:abc123

    Returns:
        True if handled successfully
    """
    callback_id = callback_query.get("id")
    callback_data = callback_query.get("data", "")
    voter = callback_query.get("from", {})
    voter_id = voter.get("id")
    voter_name = voter.get("first_name", "Unknown")
    message = callback_query.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    message_id = message.get("message_id")

    # Parse callback data
    parts = callback_data.split(":")
    if len(parts) != 4 or parts[0] != "intel":
        return False

    _, action, intel_type, item_id = parts

    if action not in ("approve", "reject"):
        logger.warning(f"Unknown intel callback action: {action}")
        return False

    logger.info(
        f"Intel callback: {action} from {voter_name} ({voter_id})",
        extra={"intel_type": intel_type, "item_id": item_id, "action": action},
    )

    # Load voting status from pending path
    pending_path = Path(settings.get_intel_pending_path)
    status_file = pending_path / f"{item_id}.json"

    if not status_file.exists():
        await telegram_bot.answer_callback_query(
            callback_id, text="Item not found or already processed.", show_alert=True,
        )
        return True

    voting_data = json.loads(status_file.read_text())

    # Check if already voted
    all_voters = [v["id"] for v in voting_data.get("votes", {}).get("approve", [])] + [
        v["id"] for v in voting_data.get("votes", {}).get("reject", [])
    ]

    if voter_id in all_voters:
        await telegram_bot.answer_callback_query(
            callback_id, text="You already voted!", show_alert=True,
        )
        return True

    # Record vote
    vote_entry = {"id": voter_id, "name": voter_name}
    votes = voting_data.setdefault("votes", {"approve": [], "reject": []})
    votes[action].append(vote_entry)
    status_file.write_text(json.dumps(voting_data, indent=2))

    # Acknowledge the vote
    await telegram_bot.answer_callback_query(callback_id, text=f"Vote recorded: {action.upper()}")

    # Check quorum
    required = get_required_votes(intel_type)
    approve_count = len(votes["approve"])
    reject_count = len(votes["reject"])

    if approve_count >= required:
        # Quorum reached — publish
        logger.info(
            f"Approval quorum reached ({approve_count}/{required})",
            extra={"intel_type": intel_type, "item_id": item_id},
        )

        try:
            from backend.app.routers.intel import publish_staging_item

            await publish_staging_item(intel_type, item_id)

            result_text = (
                f"APPROVED and published\nVotes: {approve_count} approve, {reject_count} reject"
            )
        except Exception as e:
            logger.error(
                f"Auto-publish failed after approval: {e}",
                exc_info=True,
                extra={"intel_type": intel_type, "item_id": item_id},
            )
            result_text = (
                f"APPROVED but publish failed: {e}\n"
                f"Votes: {approve_count} approve, {reject_count} reject"
            )

        # Update Telegram message to show result
        if chat_id and message_id:
            await telegram_bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"✅ {result_text}",
                parse_mode=None,
            )

    elif reject_count >= required:
        # Rejection quorum reached — archive
        logger.info(
            f"Rejection quorum reached ({reject_count}/{required})",
            extra={"intel_type": intel_type, "item_id": item_id},
        )

        try:
            from backend.services.intel import IntelStagingService

            staging_service = IntelStagingService()
            staging_service.archive_item(intel_type, item_id, "rejected")
        except Exception as e:
            logger.error(
                f"Archive after rejection failed: {e}",
                exc_info=True,
                extra={"intel_type": intel_type, "item_id": item_id},
            )

        result_text = (
            f"REJECTED and archived\nVotes: {approve_count} approve, {reject_count} reject"
        )

        if chat_id and message_id:
            await telegram_bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"❌ {result_text}",
                parse_mode=None,
            )

    return True


@router.post("/telegram")
async def telegram_webhook(
    request: Request,
    channel_router: ChannelRouter = Depends(get_channel_router),
) -> dict[str, Any]:
    """
    Telegram Bot API webhook endpoint.

    Receives updates from Telegram and routes them through the multi-channel architecture.
    Intercepts callback_query updates for intel approval voting.

    Returns:
        Success confirmation (Telegram expects 200 OK)
    """
    try:
        # Parse request body
        update = await request.json()

        # Validate update_id
        update_id = update.get("update_id")
        if not update_id:
            logger.warning("Received Telegram update without update_id")
            return {"ok": False, "error": "Missing update_id"}

        # Handle callback_query (inline keyboard button presses) before ChannelRouter
        callback_query = update.get("callback_query")
        if callback_query:
            callback_data = callback_query.get("data", "")
            logger.info(f"📨 Telegram callback_query {update_id}: data={callback_data}")

            if callback_data.startswith("intel:"):
                handled = await handle_intel_callback(callback_query)
                if handled:
                    return {"ok": True, "update_id": update_id, "type": "callback_query"}

            # Non-intel callbacks fall through to ChannelRouter
            return {"ok": True, "update_id": update_id}

        # Log incoming message update
        message = update.get("message", {})
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        text = message.get("text", "")

        logger.info(f"📨 Telegram update {update_id}: chat_id={chat_id}, text={text[:50]}...")

        # ── Agent Mesh: resolve team member context ──
        agent_context = await _resolve_team_agent(request, chat_id)
        if agent_context:
            # Inject into update so TelegramChannelAdapter copies it to metadata
            update["_agent_context"] = agent_context

        # Handle cover image uploads from Damar
        from_id = message.get("from", {}).get("id")
        has_photo = bool(message.get("photo")) or (
            message.get("document", {}).get("mime_type", "").startswith("image/")
        )

        if has_photo and from_id == 1813875994:  # Damar's chat_id
            try:
                from backend.services.intel.intel_cover_handler import intel_cover_handler

                result = await intel_cover_handler.handle_photo_message(message)
                if result:
                    return {"ok": True, "update_id": update_id, "type": "cover_image_upload"}
            except Exception as e:
                logger.error(f"Cover image handler failed: {e}", exc_info=True)
            # Fall through to channel router if handler didn't match

        # Route message through ChannelRouter
        await channel_router.route_message("telegram", update)

        # Return 200 OK (Telegram requires this)
        return {"ok": True, "update_id": update_id}

    except Exception as e:
        logger.error(f"Failed to process Telegram webhook: {e}", exc_info=True)

        # Return 200 OK even on error (to prevent Telegram from retrying)
        # Telegram will retry if we return 500, which can cause duplicates
        return {"ok": False, "error": str(e)}


@router.get("/telegram/health")
async def telegram_health() -> dict[str, Any]:
    """Health check for Telegram webhook."""
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")

    return {
        "status": "healthy",
        "channel": "telegram",
        "webhook_configured": bool(telegram_token),
    }
