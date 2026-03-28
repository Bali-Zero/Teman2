"""
Intel Approval Service

Handles approval workflow and Telegram notifications for Intel articles.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from backend.app.core.config import settings
from backend.app.core.constants import IntelConstants
from backend.app.core.intel_approvers import get_chat_ids, get_team_config
from backend.services.integrations.telegram_bot_service import telegram_bot

logger = logging.getLogger(__name__)


class IntelApprovalService:
    """
    Service for managing Intel approval workflow.

    Handles Telegram notifications, voting status, and approval coordination.
    """

    def __init__(self) -> None:
        """Initialize the approval service."""
        self.pending_intel_path = Path(settings.get_intel_pending_path)
        self.pending_intel_path.mkdir(exist_ok=True)
        self.max_key_points = IntelConstants.MAX_KEY_POINTS

    async def send_approval_notification(
        self,
        intel_type: Literal["visa", "news"],
        item_id: str,
        item_data: dict[str, Any],
        enriched_data: dict[str, Any] | None = None,
        image_path: str | None = None,
    ) -> bool:
        """
        Send Telegram notification to approval team with voting buttons.

        Sends rich formatted article with image (Bali Zero style) instead of plain text.

        Args:
            intel_type: "news" or "visa"
            item_id: Unique item identifier
            item_data: Full item data from staging file
            enriched_data: Enriched content from ArticleEnrichmentService (optional)
            image_path: Path to generated cover image (optional)

        Returns:
            True if notification sent successfully
        """
        # Get team configuration
        team_config = get_team_config(intel_type)
        if not team_config or not team_config["approvers"]:
            logger.warning(
                f"No approvers configured for {intel_type}",
                extra={"intel_type": intel_type, "item_id": item_id},
            )
            return False

        chat_ids = get_chat_ids(intel_type)
        if not chat_ids:
            logger.warning(
                f"No chat IDs found for {intel_type}",
                extra={"intel_type": intel_type, "item_id": item_id},
            )
            return False

        # Build notification content
        caption = self._build_notification_caption(
            intel_type, item_id, item_data, enriched_data, team_config
        )
        keyboard = self._build_approval_keyboard(intel_type, item_id)

        # Save voting status
        self._save_voting_status(item_id, intel_type, item_data, enriched_data, image_path)

        # Send to all approvers
        success_count = 0
        for chat_id in chat_ids:
            try:
                if image_path and Path(image_path).exists():
                    with open(image_path, "rb") as photo:
                        await telegram_bot.send_photo(
                            chat_id=chat_id,
                            photo=photo,
                            caption=caption,
                            parse_mode="HTML",
                            reply_markup=keyboard,
                        )
                else:
                    await telegram_bot.send_message(
                        chat_id=chat_id,
                        text=caption,
                        parse_mode="HTML",
                        reply_markup=keyboard,
                    )

                success_count += 1
                logger.info(
                    f"Rich notification sent to {chat_id}",
                    extra={
                        "intel_type": intel_type,
                        "item_id": item_id,
                        "chat_id": chat_id,
                        "has_image": bool(image_path),
                        "enriched": bool(enriched_data),
                    },
                )
            except Exception as e:
                logger.error(
                    f"Failed to send notification to {chat_id}: {e}",
                    extra={
                        "intel_type": intel_type,
                        "item_id": item_id,
                        "chat_id": chat_id,
                    },
                )

        logger.info(
            f"Sent {success_count}/{len(chat_ids)} rich notifications",
            extra={"intel_type": intel_type, "item_id": item_id},
        )

        return success_count > 0

    def _build_notification_caption(
        self,
        intel_type: Literal["visa", "news"],
        item_id: str,
        item_data: dict[str, Any],
        enriched_data: dict[str, Any] | None,
        team_config: dict[str, Any],
    ) -> str:
        """
        Build HTML formatted caption for Telegram notification.

        Args:
            intel_type: "visa" or "news"
            item_id: Unique item identifier
            item_data: Full item data
            enriched_data: Optional enriched data
            team_config: Team configuration

        Returns:
            HTML formatted caption string
        """
        # Use enriched data if available, otherwise fallback to raw
        if enriched_data:
            title = enriched_data.get("enriched_title", item_data.get("title", "Untitled"))
            summary = enriched_data.get("enriched_summary", "")
            key_points = enriched_data.get("key_points", [])
            keywords = enriched_data.get("seo_keywords", [])
        else:
            title = item_data.get("title", "Untitled")
            summary = item_data.get("content", "")[:200] + "..."
            key_points = []
            keywords = []

        source = item_data.get("source_name", item_data.get("source", "Unknown"))
        source_url = item_data.get("source_url", item_data.get("url", ""))
        detected_at = item_data.get("detected_at", datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M"))

        emoji_map = {"visa": "🛂", "news": "📰"}
        emoji = emoji_map.get(intel_type, "📋")

        # Build HTML formatted caption (Bali Zero style)
        caption = f"""<b>{emoji} BALI ZERO INTELLIGENCE</b>

<b>{title}</b>

{summary}
"""

        # Add key points only if available
        if key_points:
            caption += "\n<b>📌 Key Points:</b>\n"
            for i, point in enumerate(key_points[: self.max_key_points], 1):
                caption += f"  {i}. {point}\n"

        # Add metadata
        caption += f"""
<b>📰 Source:</b> <a href="{source_url}">{source}</a>
<b>📅 Detected:</b> {detected_at}"""

        # Add tags only if available
        if keywords:
            caption += f"\n<b>🏷️ Tags:</b> {', '.join(keywords[:5])}"

        caption += f"""

🗳️ <b>Votazione {team_config["required_votes"]}/{len(team_config["approvers"])}</b> per approvare/rifiutare

<code>ID: {item_id}</code>"""

        return caption

    def _build_approval_keyboard(
        self, intel_type: Literal["visa", "news"], item_id: str
    ) -> dict[str, Any]:
        """
        Build inline keyboard for approval/rejection buttons.

        Args:
            intel_type: "visa" or "news"
            item_id: Unique item identifier

        Returns:
            Keyboard dictionary for Telegram
        """
        return {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ APPROVE",
                        "callback_data": f"intel:approve:{intel_type}:{item_id}",
                    },
                    {
                        "text": "❌ REJECT",
                        "callback_data": f"intel:reject:{intel_type}:{item_id}",
                    },
                ],
            ]
        }

    def _save_voting_status(
        self,
        item_id: str,
        intel_type: Literal["visa", "news"],
        item_data: dict[str, Any],
        enriched_data: dict[str, Any] | None,
        image_path: str | None,
    ) -> None:
        """
        Save voting status to file.

        Args:
            item_id: Unique item identifier
            intel_type: "visa" or "news"
            item_data: Full item data
            enriched_data: Optional enriched data
            image_path: Optional image path
        """
        voting_status = {
            "item_id": item_id,
            "intel_type": intel_type,
            "status": "voting",
            "votes": {"approve": [], "reject": []},
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "item_data": item_data,
            "enriched_data": enriched_data,
            "image_path": image_path,
        }

        status_file = self.pending_intel_path / f"{item_id}.json"

        try:
            status_file.write_text(json.dumps(voting_status, indent=2))

        except Exception as e:
            logger.error(
                f"Failed to save voting status for {item_id}: {e}",
                exc_info=True,
                extra={"item_id": item_id, "intel_type": intel_type},
            )
            raise
