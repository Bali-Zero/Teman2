"""
Intel Cover Image Handler

Handles cover image uploads from Damar via Telegram.
Flow: Damar replies to article notification with photo → bot downloads → saves as cover.
"""

import base64
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from backend.app.core.config import settings
from backend.services.integrations.telegram_bot_service import telegram_bot

logger = logging.getLogger(__name__)

# Damar's Telegram chat_id
DAMAR_CHAT_ID = 1813875994
# Owner (Zero) chat_id — first in TELEGRAM_APPROVAL_CHAT_ID
OWNER_CHAT_ID = None  # Will be set from env at runtime

# Notification map persistence
NOTIFICATION_MAP_FILE = Path("/tmp/staging/notification_map.json")
# Max age for notification mappings
MAP_MAX_AGE_DAYS = 7


class IntelCoverHandler:
    """Handles cover image uploads from Damar via Telegram bot."""

    def __init__(self) -> None:
        self._notification_map: dict[str, dict[str, Any]] = {}
        self._load_map()

    def _load_map(self) -> None:
        """Load notification map from disk."""
        try:
            if NOTIFICATION_MAP_FILE.exists():
                data = json.loads(NOTIFICATION_MAP_FILE.read_text())
                # Prune old entries
                cutoff = (datetime.utcnow() - timedelta(days=MAP_MAX_AGE_DAYS)).isoformat()
                self._notification_map = {
                    k: v for k, v in data.items() if v.get("registered_at", "") > cutoff
                }
                logger.info(f"Loaded {len(self._notification_map)} notification mappings")
        except Exception as e:
            logger.warning(f"Failed to load notification map: {e}")
            self._notification_map = {}

    def _save_map(self) -> None:
        """Persist notification map to disk."""
        try:
            NOTIFICATION_MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
            NOTIFICATION_MAP_FILE.write_text(
                json.dumps(self._notification_map, indent=2, ensure_ascii=False)
            )
        except Exception as e:
            logger.warning(f"Failed to save notification map: {e}")

    def register_notification(
        self,
        telegram_message_id: int,
        chat_id: int,
        intel_type: str,
        item_id: str,
        title: str = "",
    ) -> None:
        """Register mapping between Telegram message_id and staging item."""
        key = str(telegram_message_id)
        self._notification_map[key] = {
            "intel_type": intel_type,
            "item_id": item_id,
            "chat_id": chat_id,
            "title": title,
            "registered_at": datetime.utcnow().isoformat(),
        }
        self._save_map()
        logger.info(f"Registered notification mapping: msg_id={telegram_message_id} → {item_id}")

    async def handle_photo_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """
        Process a photo message from Damar, match to article, upload cover.

        Returns result dict if handled, None if not matched.
        """
        chat_id = message.get("chat", {}).get("id", 0)
        from_id = message.get("from", {}).get("id", 0)

        if from_id != DAMAR_CHAT_ID:
            return None

        # Try to match article
        match = self._match_article(message)
        if not match:
            await self._send_help_message(chat_id)
            return {"matched": False, "reason": "no_match"}

        intel_type, item_id, title = match

        try:
            # Download photo from Telegram
            photo_bytes = await self._download_photo(message)
            if len(photo_bytes) < 5000:
                await self._send_message(
                    chat_id,
                    "⚠️ Ukuran gambar terlalu kecil. Kirim gambar dengan resolusi lebih tinggi.",
                )
                return {"matched": True, "error": "photo_too_small"}

            # Save as cover image
            await self._upload_cover(intel_type, item_id, photo_bytes)

            # Confirm to Damar (Indonesian)
            await self._send_message(
                chat_id,
                f"✅ <b>Gambar cover berhasil diunggah!</b>\n\n"
                f"📰 <i>{title}</i>\n\n"
                f"Gambar sudah tersedia di News Room.",
                parse_mode="HTML",
            )

            # Notify owner (Italian)
            await self._notify_owner(title)

            logger.info(f"Cover image uploaded for {item_id} by Damar")
            return {"matched": True, "item_id": item_id, "success": True}

        except Exception as e:
            logger.error(f"Cover upload failed for {item_id}: {e}", exc_info=True)
            await self._send_message(
                chat_id,
                f"❌ Gagal mengunggah gambar untuk: {title}\nError: {e!s:.100}",
            )
            return {"matched": True, "item_id": item_id, "error": str(e)}

    def _match_article(self, message: dict[str, Any]) -> tuple[str, str, str] | None:
        """
        Match photo to article. Returns (intel_type, item_id, title) or None.

        Priority:
        1. Reply to article notification message
        2. Caption with /cover command
        3. None (no match)
        """
        # Priority 1: Reply match
        reply_msg = message.get("reply_to_message", {})
        if reply_msg:
            reply_msg_id = str(reply_msg.get("message_id", ""))
            if reply_msg_id in self._notification_map:
                mapping = self._notification_map[reply_msg_id]
                return (
                    mapping["intel_type"],
                    mapping["item_id"],
                    mapping.get("title", ""),
                )

        # Priority 2: /cover command in caption
        caption = message.get("caption", "") or ""
        if caption.strip().lower().startswith("/cover "):
            item_id = caption.strip().split(maxsplit=1)[1].strip()
            # Find in map by item_id
            for _msg_id, mapping in self._notification_map.items():
                if mapping["item_id"] == item_id:
                    return (
                        mapping["intel_type"],
                        item_id,
                        mapping.get("title", ""),
                    )
            # item_id provided but not in map — try as news type
            return ("news", item_id, item_id)

        return None

    async def _download_photo(self, message: dict[str, Any]) -> bytes:
        """Download largest photo or image document from Telegram."""
        file_id = None

        # Check for photo (compressed by Telegram)
        photos = message.get("photo", [])
        if photos:
            file_id = photos[-1].get("file_id")  # Largest size

        # Check for document (original quality)
        doc = message.get("document", {})
        if doc and doc.get("mime_type", "").startswith("image/"):
            file_id = doc.get("file_id")

        if not file_id:
            raise ValueError("No photo or image document found in message")

        file_info = await telegram_bot.get_file(file_id)
        file_path = file_info.get("file_path", "")
        if not file_path:
            raise ValueError("Telegram returned empty file_path")

        return await telegram_bot.download_file(file_path)

    async def _upload_cover(self, intel_type: str, item_id: str, photo_bytes: bytes) -> None:
        """Save cover image to staging and update staging JSON."""
        base_dir = Path(settings.get_intel_staging_base_dir)
        staging_dir = base_dir / intel_type
        covers_dir = staging_dir / "covers"
        covers_dir.mkdir(parents=True, exist_ok=True)

        # Save image file
        image_path = covers_dir / f"{item_id}.jpg"
        image_path.write_bytes(photo_bytes)
        logger.info(f"Saved cover image: {image_path} ({len(photo_bytes)} bytes)")

        # Update staging item JSON with cover_image field
        item_file = staging_dir / f"{item_id}.json"
        if item_file.exists():
            try:
                item_data = json.loads(item_file.read_text())
                item_data["cover_image"] = f"covers/{item_id}.jpg"
                item_data["cover_image_base64"] = base64.b64encode(photo_bytes).decode()
                item_data["cover_uploaded_by"] = "damar"
                item_data["cover_uploaded_at"] = datetime.utcnow().isoformat()
                item_file.write_text(json.dumps(item_data, indent=2, ensure_ascii=False))
                logger.info(f"Updated staging item {item_id} with cover image")
            except Exception as e:
                logger.warning(f"Could not update staging JSON for {item_id}: {e}")

    async def _send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "HTML",
    ) -> None:
        """Send a Telegram message."""
        try:
            await telegram_bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
            )
        except Exception as e:
            logger.error(f"Failed to send message to {chat_id}: {e}")

    async def _send_help_message(self, chat_id: int) -> None:
        """Send help message when photo cannot be matched to an article."""
        # List articles without covers
        pending = []
        for _msg_id, mapping in self._notification_map.items():
            item_id = mapping["item_id"]
            title = mapping.get("title", item_id)
            # Check if cover already exists
            base_dir = Path(settings.get_intel_staging_base_dir)
            cover_path = base_dir / mapping["intel_type"] / "covers" / f"{item_id}.jpg"
            if not cover_path.exists():
                pending.append(f"• <code>{item_id}</code>\n  {title}")

        pending_text = "\n".join(pending[:10]) if pending else "Semua artikel sudah ada cover."

        await self._send_message(
            chat_id,
            f"⚠️ <b>Tidak bisa mencocokkan foto dengan artikel.</b>\n\n"
            f"Cara mengirim gambar cover:\n"
            f"1️⃣ <b>Reply</b> langsung ke notifikasi artikel\n"
            f"2️⃣ Kirim dengan caption: <code>/cover [kode_artikel]</code>\n\n"
            f"📋 <b>Artikel yang belum ada cover:</b>\n{pending_text}",
        )

    async def _notify_owner(self, title: str) -> None:
        """Notify the owner that Damar uploaded a cover image."""
        import os

        owner_id = os.environ.get("TELEGRAM_APPROVAL_CHAT_ID", "").split(",")[0].strip()
        if not owner_id:
            return
        try:
            await telegram_bot.send_message(
                chat_id=int(owner_id),
                text=(
                    f"🖼️ Damar ha caricato la cover per:\n"
                    f"<i>{title}</i>\n\n"
                    f"Verifica nella News Room."
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Failed to notify owner about cover upload: {e}")


# Singleton instance
intel_cover_handler = IntelCoverHandler()
