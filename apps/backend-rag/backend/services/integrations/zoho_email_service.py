"""
Zoho Email Service

Core email operations: list, read, send, reply, forward, search, attachments, etc.

Features:
- List emails with pagination and filtering
- Read full email content
- Send new emails with attachments
- Reply / Reply All / Forward
- Mark read/unread, flag/unflag
- Delete (move to trash)
- Folder management
- Search emails
- Attachment upload/download
"""

import logging
import time
from typing import Any

import asyncpg
import httpx

from app.core.config import settings
from app.metrics import metrics_collector
from services.integrations.zoho_oauth_service import ZohoOAuthService

logger = logging.getLogger(__name__)


class ZohoEmailService:
    """
    Handles all Zoho Mail API operations.
    """

    def __init__(self, db_pool: asyncpg.Pool):
        """
        Initialize ZohoEmailService.

        Args:
            db_pool: PostgreSQL connection pool
        """
        self.db_pool = db_pool
        self.oauth_service = ZohoOAuthService(db_pool)
        self.api_domain = settings.zoho_api_domain

    async def _log_activity(
        self,
        user_id: str,
        operation: str,
        email_subject: str | None = None,
        recipient_email: str | None = None,
        has_attachments: bool = False,
        attachment_count: int = 0,
    ) -> None:
        """
        Log email activity for weekly reporting.

        Args:
            user_id: User ID
            operation: Operation type (sent, received, read, deleted, replied, forwarded)
            email_subject: Email subject (optional)
            recipient_email: Recipient email for sent emails (optional)
            has_attachments: Whether email has attachments
            attachment_count: Number of attachments
        """
        try:
            # Get user email from oauth tokens or team_members
            async with self.db_pool.acquire() as conn:
                user_email = await conn.fetchval(
                    """
                    SELECT COALESCE(z.email_address, t.email)
                    FROM team_members t
                    LEFT JOIN zoho_email_tokens z ON z.user_id = t.id
                    WHERE t.id = $1
                    """,
                    user_id,
                )

                if not user_email:
                    user_email = user_id  # Fallback to user_id

                await conn.execute(
                    """
                    INSERT INTO email_activity_log
                    (user_id, user_email, operation, email_subject, recipient_email, has_attachments, attachment_count)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    user_id,
                    user_email,
                    operation,
                    email_subject[:255] if email_subject else None,
                    recipient_email,
                    has_attachments,
                    attachment_count,
                )
                logger.debug(f"[Email Activity] Logged {operation} for user={user_id}")
        except Exception as e:
            # Don't fail the main operation if logging fails
            logger.warning(f"[Email Activity] Failed to log activity: {e}")

    async def _get_headers(self, user_id: str) -> dict[str, str]:
        """
        Get authenticated headers for API requests.

        Args:
            user_id: User ID

        Returns:
            Headers dict with authorization
        """
        token = await self.oauth_service.get_valid_token(user_id)
        return {
            "Authorization": f"Zoho-oauthtoken {token}",
            "Content-Type": "application/json",
        }

    async def _get_account_id(self, user_id: str) -> str:
        """
        Get Zoho account ID for user.

        Args:
            user_id: User ID

        Returns:
            Zoho account ID
        """
        return await self.oauth_service.get_account_id(user_id)

    async def _request(
        self,
        user_id: str,
        method: str,
        endpoint: str,
        json_data: dict | None = None,
        params: dict | None = None,
    ) -> dict[str, Any]:
        """
        Make authenticated request to Zoho Mail API.

        Args:
            user_id: User ID
            method: HTTP method
            endpoint: API endpoint (without /api/accounts/{account_id})
            json_data: JSON body data
            params: Query parameters

        Returns:
            Response JSON data
        """
        account_id = await self._get_account_id(user_id)
        headers = await self._get_headers(user_id)
        url = f"{self.api_domain}/api/accounts/{account_id}{endpoint}"

        logger.debug(f"[Email API] {method} {endpoint} for user={user_id}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=json_data,
                params=params,
            )

            if response.status_code >= 400:
                error_data = response.json() if response.content else {}
                logger.error(
                    f"[Email API] Error: {method} {endpoint} user={user_id} "
                    f"status={response.status_code} error={error_data}"
                )
                raise ValueError(
                    f"API error: {error_data.get('data', {}).get('errorCode', 'unknown')}"
                )

            logger.debug(f"[Email API] Success: {method} {endpoint} status={response.status_code}")
            return response.json()

    # ═══════════════════════════════════════════
    # FOLDER OPERATIONS
    # ═══════════════════════════════════════════

    async def list_folders(self, user_id: str) -> list[dict[str, Any]]:
        """
        List all email folders.

        Args:
            user_id: User ID

        Returns:
            List of folder objects
        """
        logger.info(f"[Email] Listing folders for user={user_id}")
        response = await self._request(user_id, "GET", "/folders")
        folders = response.get("data", [])
        logger.debug(f"[Email] Found {len(folders)} folders for user={user_id}")

        # Transform to format matching frontend EmailFolder
        return [
            {
                "folder_id": f.get("folderId"),
                "folder_name": f.get("folderName"),
                "folder_path": f.get("folderPath", f.get("folderName", "")),
                "folder_type": self._normalize_folder_type(f.get("folderType", "custom")),
                "unread_count": f.get("unreadCount", 0),
                "total_count": f.get("messageCount", 0),
            }
            for f in folders
        ]

    def _normalize_folder_type(self, folder_type: str) -> str:
        """Normalize Zoho folder type to frontend expected values."""
        type_map = {
            "Inbox": "inbox",
            "Sent": "sent",
            "Drafts": "drafts",
            "Trash": "trash",
            "Spam": "spam",
            "Junk": "spam",
        }
        return type_map.get(folder_type, "custom")

    # ═══════════════════════════════════════════
    # EMAIL OPERATIONS
    # ═══════════════════════════════════════════

    async def list_emails(
        self,
        user_id: str,
        folder_id: str = "inbox",
        limit: int = 50,
        start: int = 0,
        search_key: str | None = None,
        is_unread: bool | None = None,
    ) -> dict[str, Any]:
        """
        List emails in a folder with pagination and filtering.

        Args:
            user_id: User ID
            folder_id: Folder ID (default: inbox)
            limit: Max emails to return (max 200)
            start: Offset for pagination
            search_key: Search query
            is_unread: Filter by read status

        Returns:
            Dict with emails, total count, and has_more flag
        """
        logger.info(
            f"[Email] Listing emails user={user_id} folder={folder_id} "
            f"limit={limit} start={start} search={search_key}"
        )
        params: dict[str, Any] = {
            "folderId": folder_id,
            "limit": min(limit, 200),
            "start": start,
        }

        if search_key:
            params["searchKey"] = search_key

        if is_unread is not None:
            params["status"] = "unread" if is_unread else "read"

        response = await self._request(user_id, "GET", "/messages/view", params=params)

        emails = response.get("data", [])
        paging = response.get("paging", {})

        # Transform to consistent format matching frontend EmailSummary
        transformed_emails = []
        for email in emails:
            transformed_emails.append(
                {
                    "message_id": email.get("messageId"),
                    "folder_id": email.get("folderId"),
                    "thread_id": email.get("threadId"),
                    "subject": email.get("subject", "(No subject)"),
                    "from": {
                        "address": email.get("fromAddress", ""),
                        "name": email.get("sender", ""),
                    },
                    "to": self._parse_recipients_to_objects(email.get("toAddress", "")),
                    "cc": self._parse_recipients_to_objects(email.get("ccAddress", "")),
                    "snippet": email.get("summary", ""),
                    "has_attachments": email.get("hasAttachment", False),
                    "is_read": email.get("isRead", True),
                    "is_flagged": email.get("isFlagged", False),
                    "date": email.get("receivedTime") or email.get("sentDateInGMT"),
                }
            )

        result = {
            "emails": transformed_emails,
            "total": paging.get("totalCount", len(emails)),
            "has_more": paging.get("hasMoreData", False),
        }
        logger.debug(
            f"[Email] Listed {len(transformed_emails)} emails, total={result['total']}, "
            f"has_more={result['has_more']}"
        )
        return result

    def _parse_recipients(self, recipients_str: str) -> list[str]:
        """Parse comma-separated recipient string to list."""
        if not recipients_str:
            return []
        return [r.strip() for r in recipients_str.split(",") if r.strip()]

    def _parse_recipients_to_objects(self, recipients_str: str) -> list[dict[str, str]]:
        """Parse comma-separated recipient string to list of {address, name} objects."""
        if not recipients_str:
            return []
        result = []
        for r in recipients_str.split(","):
            r = r.strip()
            if r:
                # Handle format like "Name <email>" or just "email"
                if "<" in r and ">" in r:
                    name = r[: r.index("<")].strip().strip('"')
                    address = r[r.index("<") + 1 : r.index(">")].strip()
                else:
                    name = ""
                    address = r
                result.append({"address": address, "name": name})
        return result

    async def get_email(
        self, user_id: str, message_id: str, folder_id: str | None = None
    ) -> dict[str, Any]:
        """
        Get full email content.

        Args:
            user_id: User ID
            message_id: Message ID
            folder_id: Folder ID (required for Zoho API)

        Returns:
            Full email object with content
        """
        if not folder_id:
            raise ValueError("folder_id is required for Zoho Mail API")

        # Step 1: Get metadata from list endpoint (Zoho doesn't have single message metadata endpoint)
        list_response = await self._request(
            user_id, "GET", "/messages/view", params={"folderId": folder_id, "limit": "50"}
        )
        emails_list = list_response.get("data", [])

        # Find the specific email by messageId
        email = None
        for e in emails_list:
            if str(e.get("messageId")) == str(message_id):
                email = e
                break

        if not email:
            raise ValueError(f"Email {message_id} not found in folder {folder_id}")

        # Step 2: Get content from the /content endpoint (this is the only way in Zoho API)
        content_path = f"/folders/{folder_id}/messages/{message_id}/content"
        content_response = await self._request(user_id, "GET", content_path)
        content = content_response.get("data", {}).get("content", "")

        # Mark as read automatically
        try:
            await self.mark_read(user_id, [message_id], is_read=True)
        except Exception as e:
            logger.warning(f"Failed to mark email as read: {e}")

        # Return in format matching frontend EmailDetail
        is_html = "<" in content and ">" in content
        return {
            "message_id": email.get("messageId"),
            "folder_id": email.get("folderId"),
            "thread_id": email.get("threadId"),
            "subject": email.get("subject", "(No subject)"),
            "from": {
                "address": email.get("fromAddress", ""),
                "name": email.get("sender", ""),
            },
            "to": self._parse_recipients_to_objects(email.get("toAddress", "")),
            "cc": self._parse_recipients_to_objects(email.get("ccAddress", "")),
            "bcc": self._parse_recipients_to_objects(email.get("bccAddress", "")),
            "html_content": content if is_html else "",
            "text_content": content if not is_html else "",
            "snippet": email.get("summary", ""),
            "has_attachments": email.get("hasAttachment", False),
            "is_read": True,  # We just marked it read
            "is_flagged": email.get("isFlagged", False),
            "date": email.get("receivedTime") or email.get("sentDateInGMT"),
            "attachments": self._parse_attachments(email.get("attachments", [])),
        }

    def _parse_attachments(self, attachments: list) -> list[dict]:
        """Parse attachment metadata to match frontend EmailAttachment format."""
        return [
            {
                "attachment_id": a.get("attachmentId"),
                "filename": a.get("attachmentName"),
                "size": a.get("attachmentSize", 0),
                "mime_type": a.get("contentType", "application/octet-stream"),
            }
            for a in attachments
        ]

    async def search_emails(
        self,
        user_id: str,
        query: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Search emails across all folders.

        Args:
            user_id: User ID
            query: Search query
            limit: Max results

        Returns:
            List of matching emails
        """
        response = await self._request(
            user_id,
            "GET",
            "/messages/search",
            params={"searchKey": query, "limit": limit},
        )

        emails = response.get("data", [])
        return [
            {
                "id": email.get("messageId"),
                "folder_id": email.get("folderId"),
                "subject": email.get("subject", "(No subject)"),
                "sender_email": email.get("fromAddress", ""),
                "sender_name": email.get("sender", ""),
                "snippet": email.get("summary", ""),
                "has_attachments": email.get("hasAttachment", False),
                "is_read": email.get("isRead", True),
                "received_at": email.get("receivedTime"),
            }
            for email in emails
        ]

    # ═══════════════════════════════════════════
    # SEND EMAIL
    # ═══════════════════════════════════════════

    async def send_email(
        self,
        user_id: str,
        to: list[str],
        subject: str,
        content: str,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        attachments: list[dict[str, str]] | None = None,
        is_html: bool = True,
    ) -> dict[str, Any]:
        """
        Send a new email.

        Args:
            user_id: User ID
            to: Recipient email addresses
            subject: Email subject
            content: Email body content
            cc: CC recipients
            bcc: BCC recipients
            attachments: List of attachment objects (from upload_attachment)
            is_html: Whether content is HTML

        Returns:
            Send result with message ID
        """
        start_time = time.time()
        logger.info(
            f"[Email] Sending email user={user_id} to={to} subject='{subject[:50]}...' "
            f"cc={cc} bcc={bcc} attachments={len(attachments or [])}"
        )
        try:
            # Get sender email from account
            status = await self.oauth_service.get_connection_status(user_id)
            from_address = status.get("email", "")

            payload: dict[str, Any] = {
                "fromAddress": from_address,
                "toAddress": ",".join(to),
                "subject": subject,
                "content": content,
                "mailFormat": "html" if is_html else "plaintext",
            }

            if cc:
                payload["ccAddress"] = ",".join(cc)
            if bcc:
                payload["bccAddress"] = ",".join(bcc)
            if attachments:
                # payload["attachments"] expects list of objects with storeName, attachmentPath, attachmentName
                formatted_attachments = []
                for att in attachments:
                    formatted_attachments.append(
                        {
                            "storeName": att.get("store_name"),
                            "attachmentPath": att.get("attachment_path"),
                            "attachmentName": att.get("attachment_name"),
                        }
                    )
                payload["attachments"] = formatted_attachments

            response = await self._request(user_id, "POST", "/messages", json_data=payload)

            message_id = response.get("data", {}).get("messageId")
            duration = time.time() - start_time
            logger.info(f"[Email] Email sent successfully user={user_id} message_id={message_id}")
            metrics_collector.record_email_operation(
                operation="send", user_id=user_id, status="success", duration_seconds=duration
            )

            # Log activity for weekly report
            await self._log_activity(
                user_id=user_id,
                operation="sent",
                email_subject=subject,
                recipient_email=to[0] if to else None,
                has_attachments=bool(attachments),
                attachment_count=len(attachments) if attachments else 0,
            )

            return {
                "success": True,
                "message_id": message_id,
            }
        except Exception:
            duration = time.time() - start_time
            metrics_collector.record_email_operation(
                operation="send", user_id=user_id, status="error", duration_seconds=duration
            )
            metrics_collector.record_email_error(error_type="api_error", operation="send")
            raise

    async def reply_email(
        self,
        user_id: str,
        message_id: str,
        content: str,
        reply_all: bool = False,
    ) -> dict[str, Any]:
        """
        Reply to an email.

        Args:
            user_id: User ID
            message_id: Original message ID
            content: Reply content
            reply_all: Whether to reply to all recipients

        Returns:
            Send result
        """
        action = "replyall" if reply_all else "reply"
        logger.info(
            f"[Email] Replying to email user={user_id} message_id={message_id} reply_all={reply_all}"
        )

        response = await self._request(
            user_id,
            "POST",
            f"/messages/{message_id}/{action}",
            json_data={"content": content, "mailFormat": "html"},
        )

        reply_message_id = response.get("data", {}).get("messageId")
        logger.info(
            f"[Email] Reply sent successfully user={user_id} reply_message_id={reply_message_id}"
        )

        # Log activity for weekly report
        await self._log_activity(
            user_id=user_id,
            operation="replied",
        )

        return {
            "success": True,
            "message_id": reply_message_id,
        }

    async def forward_email(
        self,
        user_id: str,
        message_id: str,
        to: list[str],
        content: str | None = None,
    ) -> dict[str, Any]:
        """
        Forward an email.

        Args:
            user_id: User ID
            message_id: Message to forward
            to: Recipient addresses
            content: Optional additional content

        Returns:
            Send result
        """
        logger.info(f"[Email] Forwarding email user={user_id} message_id={message_id} to={to}")
        payload: dict[str, Any] = {
            "toAddress": ",".join(to),
        }
        if content:
            payload["content"] = content
            payload["mailFormat"] = "html"

        response = await self._request(
            user_id,
            "POST",
            f"/messages/{message_id}/forward",
            json_data=payload,
        )

        fwd_message_id = response.get("data", {}).get("messageId")
        logger.info(
            f"[Email] Email forwarded successfully user={user_id} fwd_message_id={fwd_message_id}"
        )

        # Log activity for weekly report
        await self._log_activity(
            user_id=user_id,
            operation="forwarded",
            recipient_email=to[0] if to else None,
        )

        return {
            "success": True,
            "message_id": fwd_message_id,
        }

    # ═══════════════════════════════════════════
    # STATUS OPERATIONS
    # ═══════════════════════════════════════════

    async def mark_read(
        self,
        user_id: str,
        message_ids: list[str],
        is_read: bool = True,
    ) -> bool:
        """
        Mark emails as read/unread.

        Args:
            user_id: User ID
            message_ids: List of message IDs
            is_read: True to mark read, False for unread

        Returns:
            Success status
        """
        mode = "markAsRead" if is_read else "markAsUnread"
        logger.info(f"[Email] Marking {len(message_ids)} emails as {mode} user={user_id}")

        await self._request(
            user_id,
            "PUT",
            "/messages",
            json_data={"messageId": message_ids, "mode": mode},
        )

        return True

    async def toggle_flag(
        self,
        user_id: str,
        message_id: str,
        is_flagged: bool,
    ) -> bool:
        """
        Flag/unflag an email.

        Args:
            user_id: User ID
            message_id: Message ID
            is_flagged: True to flag, False to unflag

        Returns:
            Success status
        """
        logger.info(
            f"[Email] Toggling flag user={user_id} message_id={message_id} flagged={is_flagged}"
        )
        await self._request(
            user_id,
            "PUT",
            f"/messages/{message_id}",
            json_data={"flagid": "1" if is_flagged else "0"},
        )

        return True

    async def move_to_folder(
        self,
        user_id: str,
        message_ids: list[str],
        folder_id: str,
    ) -> bool:
        """
        Move emails to a folder.

        Args:
            user_id: User ID
            message_ids: List of message IDs
            folder_id: Destination folder ID

        Returns:
            Success status
        """
        logger.info(
            f"[Email] Moving {len(message_ids)} emails to folder={folder_id} user={user_id}"
        )
        await self._request(
            user_id,
            "PUT",
            "/updatemessage",
            json_data={
                "messageId": message_ids,
                "destfolderId": folder_id,
                "mode": "moveMessage",
            },
        )

        return True

    async def delete_emails(
        self,
        user_id: str,
        message_ids: list[str],
    ) -> bool:
        """
        Move emails to trash.

        Refactored to find Trash folder and move messages there, as
        PUT /messages with mode=moveToTrash is deprecated/unsupported if expunge is not set.
        Using move_to_folder is safer and more consistent.

        Args:
            user_id: User ID
            message_ids: List of message IDs

        Returns:
            Success status
        """
        start_time = time.time()
        logger.info(
            f"[Email] Deleting {len(message_ids)} emails user={user_id} message_ids={message_ids}"
        )
        try:
            # Step 1: Find Trash Folder
            folders = await self.list_folders(user_id)
            trash_folder_id = None

            # Try to find folder with type 'trash' (normalized) or name 'Trash'
            for f in folders:
                if f.get("folder_type") == "trash":
                    trash_folder_id = f.get("folder_id")
                    break

            if not trash_folder_id:
                # Fallback: check by name
                for f in folders:
                    if f.get("folder_name", "").lower() in ("trash", "bin", "cestino"):
                        trash_folder_id = f.get("folder_id")
                        break

            if not trash_folder_id:
                # Critical failure if we can't find trash
                logger.error(f"[Email] Could not find Trash folder for user={user_id}")
                raise ValueError("Trash folder not found. Cannot delete emails.")

            # Step 2: Move to Trash
            logger.info(f"[Email] Moving messages to Trash folder_id={trash_folder_id}")
            await self.move_to_folder(user_id, message_ids, trash_folder_id)

            duration = time.time() - start_time
            metrics_collector.record_email_operation(
                operation="delete", user_id=user_id, status="success", duration_seconds=duration
            )

            # Log activity for weekly report (one entry per delete operation)
            await self._log_activity(
                user_id=user_id,
                operation="deleted",
            )

            return True
        except Exception:
            duration = time.time() - start_time
            metrics_collector.record_email_operation(
                operation="delete", user_id=user_id, status="error", duration_seconds=duration
            )
            metrics_collector.record_email_error(error_type="api_error", operation="delete")
            raise

    # ═══════════════════════════════════════════
    # ATTACHMENT OPERATIONS
    # ═══════════════════════════════════════════

    async def get_attachment(
        self,
        user_id: str,
        message_id: str,
        attachment_id: str,
    ) -> bytes:
        """
        Download attachment content.

        Args:
            user_id: User ID
            message_id: Message ID
            attachment_id: Attachment ID

        Returns:
            Attachment content as bytes
        """
        logger.info(
            f"[Email] Downloading attachment user={user_id} "
            f"message_id={message_id} attachment_id={attachment_id}"
        )
        account_id = await self._get_account_id(user_id)
        headers = await self._get_headers(user_id)
        del headers["Content-Type"]  # Not needed for download

        url = f"{self.api_domain}/api/accounts/{account_id}/messages/{message_id}/attachments/{attachment_id}"

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(url, headers=headers)

            if response.status_code != 200:
                logger.error(
                    f"[Email] Failed to download attachment: status={response.status_code}"
                )
                raise ValueError(f"Failed to download attachment: {response.status_code}")

            logger.debug(
                f"[Email] Attachment downloaded successfully size={len(response.content)} bytes"
            )
            return response.content

    async def upload_attachment(
        self,
        user_id: str,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> dict[str, str]:
        """
        Upload attachment and get details for use in send.

        Args:
            user_id: User ID
            filename: File name
            content: File content
            content_type: MIME type

        Returns:
            Dictionary with attachment details (id, store_name, path, name)
        """
        logger.info(
            f"[Email] Uploading attachment user={user_id} "
            f"filename={filename} size={len(content)} type={content_type}"
        )
        account_id = await self._get_account_id(user_id)
        token = await self.oauth_service.get_valid_token(user_id)

        url = f"{self.api_domain}/api/accounts/{account_id}/messages/attachments"

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Zoho-oauthtoken {token}"},
                files={"attach": (filename, content, content_type)},
            )

            if response.status_code != 200:
                logger.error(f"[Email] Failed to upload attachment: status={response.status_code}")
                raise ValueError(f"Failed to upload attachment: {response.status_code}")

            data = response.json()
            # Zoho returns these fields in the 'data' object
            attachment_data = data.get("data", {})

            result = {
                "attachment_id": attachment_data.get("attachmentId", ""),
                "store_name": attachment_data.get("storeName", ""),
                "attachment_path": attachment_data.get("attachmentPath", ""),
                "attachment_name": attachment_data.get("attachmentName", filename),
            }

            logger.info(f"[Email] Attachment uploaded successfully id={result['attachment_id']}")
            return result

    # ═══════════════════════════════════════════
    # DRAFT OPERATIONS
    # ═══════════════════════════════════════════

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
        """
        Save email as draft.

        Args:
            user_id: User ID
            to: Recipients
            subject: Subject
            content: Content
            cc: CC recipients
            bcc: BCC recipients

        Returns:
            Draft info with message ID
        """
        status = await self.oauth_service.get_connection_status(user_id)
        from_address = status.get("email", "")

        payload: dict[str, Any] = {
            "fromAddress": from_address,
            "subject": subject,
            "content": content,
            "mode": "draft",
            "mailFormat": "html",
        }

        if to:
            payload["toAddress"] = ",".join(to)
        if cc:
            payload["ccAddress"] = ",".join(cc)
        if bcc:
            payload["bccAddress"] = ",".join(bcc)
        if attachments:
            formatted_attachments = []
            for att in attachments:
                formatted_attachments.append(
                    {
                        "storeName": att.get("store_name"),
                        "attachmentPath": att.get("attachment_path"),
                        "attachmentName": att.get("attachment_name"),
                    }
                )
            payload["attachments"] = formatted_attachments

        response = await self._request(user_id, "POST", "/messages", json_data=payload)

        return {
            "success": True,
            "message_id": response.get("data", {}).get("messageId"),
        }

    # ═══════════════════════════════════════════
    # UNREAD COUNT
    # ═══════════════════════════════════════════

    async def get_unread_count(self, user_id: str) -> int:
        """
        Get total unread email count.

        Args:
            user_id: User ID

        Returns:
            Total unread count
        """
        try:
            folders = await self.list_folders(user_id)
            # Sum unread from all folders
            return sum(f.get("unread_count", 0) for f in folders)
        except Exception as e:
            logger.warning(f"Failed to get unread count: {e}")
            return 0
