"""
Zoho Email Integration Router

OAuth flow and email operations endpoints for Zoho Mail integration.

Endpoints:
- OAuth: /auth/url, /callback, /status, /disconnect
- Folders: /folders
- Emails: /emails (list, get, send, reply, forward, mark, flag, delete)
- Attachments: /emails/{id}/attachments/{aid}
"""

import secrets
from typing import Any

import asyncpg
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field

from backend.app.core.config import settings
from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.utils.logging_utils import get_logger
from backend.services.integrations.zoho_email_service import ZohoEmailService
from backend.services.integrations.zoho_oauth_service import ZohoOAuthService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/integrations/zoho", tags=["zoho-email"])


class DeleteEmailsRequest(BaseModel):
    """Request model for deleting emails."""

    message_ids: list[str] = Field(..., min_length=1, description="Message IDs to delete")


class AttachmentObject(BaseModel):
    """Model for attachment details required by Zoho API."""

    attachment_id: str = Field(..., description="Attachment ID")
    store_name: str = Field(..., description="Store Name")
    attachment_path: str = Field(..., description="Attachment Path")
    attachment_name: str = Field(..., description="Attachment Name")


# ================================================
# PYDANTIC MODELS
# ================================================


class SendEmailRequest(BaseModel):
    """Request body for sending a new email."""

    to: list[EmailStr] = Field(..., min_length=1, description="Recipient email addresses")
    subject: str = Field(..., min_length=1, max_length=500, description="Email subject")
    # Accept both 'content' and 'html_content' from frontend
    html_content: str | None = Field(None, description="HTML email body content")
    text_content: str | None = Field(None, description="Plain text email body content")
    content: str | None = Field(None, description="Email body content (legacy)")
    cc: list[EmailStr] | None = Field(None, description="CC recipients")
    bcc: list[EmailStr] | None = Field(None, description="BCC recipients")
    attachment_ids: list[AttachmentObject] | None = Field(None, description="Attachments")
    is_html: bool = Field(True, description="Whether content is HTML")

    def get_content(self) -> str:
        """Get email content from whichever field was provided."""
        return self.html_content or self.text_content or self.content or ""


class ReplyEmailRequest(BaseModel):
    """Request body for replying to an email."""

    content: str = Field(..., description="Reply content")
    reply_all: bool = Field(False, description="Reply to all recipients")


class ForwardEmailRequest(BaseModel):
    """Request body for forwarding an email."""

    to: list[EmailStr] = Field(..., min_length=1, description="Forward to addresses")
    content: str | None = Field(None, description="Optional additional content")


class MarkReadRequest(BaseModel):
    """Request body for marking emails as read/unread."""

    message_ids: list[str] = Field(..., min_length=1, description="Message IDs to update")
    is_read: bool = Field(True, description="Mark as read (True) or unread (False)")


class ConnectionStatusResponse(BaseModel):
    """Response model for connection status."""

    connected: bool
    email: str | None
    account_id: str | None
    expires_at: str | None


class FolderResponse(BaseModel):
    """Response model for a folder."""

    id: str
    name: str
    path: str
    type: str
    unread_count: int
    total_count: int


class EmailSummaryResponse(BaseModel):
    """Response model for email list item."""

    id: str
    folder_id: str
    subject: str
    sender_email: str
    sender_name: str | None
    snippet: str | None
    has_attachments: bool
    is_read: bool
    is_flagged: bool
    received_at: int | None


class AttachmentResponse(BaseModel):
    """Response model for an attachment."""

    id: str
    name: str
    size: int
    content_type: str


# ================================================
# HELPER FUNCTIONS
# ================================================


def _get_oauth_service(db_pool: asyncpg.Pool) -> ZohoOAuthService:
    """Create ZohoOAuthService instance."""
    return ZohoOAuthService(db_pool)


def _get_email_service(db_pool: asyncpg.Pool) -> ZohoEmailService:
    """Create ZohoEmailService instance."""
    return ZohoEmailService(db_pool)


def _get_user_id(current_user: dict) -> str:
    """
    Extract user_id string from current_user dict.

    Args:
        current_user: User dict from get_current_user

    Returns:
        String user ID (matches team_members.id VARCHAR)

    Raises:
        HTTPException: If user_id is invalid
    """
    user_id = current_user.get("user_id")

    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")

    # Return as string (team_members.id is VARCHAR)
    return str(user_id)


# ================================================
# OAUTH ENDPOINTS
# ================================================


@router.get("/auth/url")
async def get_auth_url(
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, str]:
    """
    Get Zoho OAuth authorization URL.

    Returns URL to redirect user to Zoho login page.
    The state parameter includes user_id for CSRF protection.
    """
    oauth_service = _get_oauth_service(db_pool)

    # Generate state token with user_id for CSRF protection
    user_id = _get_user_id(current_user)
    state_token = secrets.token_urlsafe(32)
    state = f"{user_id}:{state_token}"

    try:
        auth_url = oauth_service.get_authorization_url(state)
        return {"auth_url": auth_url, "state": state_token}
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/callback")
async def oauth_callback(
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> RedirectResponse:
    """
    OAuth callback handler.

    Exchanges authorization code for tokens and stores them.
    Redirects to /email page with success or error status.
    """
    # Frontend URL for redirects (from settings)
    frontend_url = settings.frontend_url

    # Handle OAuth errors
    if error:
        logger.warning(f"Zoho OAuth error: {error}")
        return RedirectResponse(url=f"{frontend_url}/email?error=oauth_denied")

    # Validate required parameters
    if not code or not state:
        logger.warning("Missing code or state in OAuth callback")
        return RedirectResponse(url=f"{frontend_url}/email?error=missing_params")

    try:
        # Extract user_id from state (format: user_id:random_token)
        logger.info(f"OAuth callback received - state: {state[:50]}..., code length: {len(code)}")

        parts = state.split(":", 1)
        if len(parts) != 2:
            raise ValueError("Invalid state format")

        user_id = parts[0]  # Keep as string (VARCHAR)
        logger.info(f"Extracted user_id: {user_id}")

        # Exchange code for tokens
        oauth_service = _get_oauth_service(db_pool)
        logger.info(f"Calling exchange_code for user {user_id}")
        await oauth_service.exchange_code(code, user_id)

        logger.info(f"Zoho OAuth successful for user {user_id}")
        return RedirectResponse(url=f"{frontend_url}/email?connected=true")

    except ValueError as e:
        logger.error(f"OAuth callback ValueError: {e}", exc_info=True)
        return RedirectResponse(url=f"{frontend_url}/email?error=invalid_state")
    except Exception as e:
        logger.error(f"OAuth callback exception: {type(e).__name__}: {e}", exc_info=True)
        return RedirectResponse(url=f"{frontend_url}/email?error=connection_failed")


@router.get("/status", response_model=ConnectionStatusResponse)
async def get_connection_status(
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> ConnectionStatusResponse:
    """
    Check if user has connected Zoho account.

    Returns connection status with email and expiry information.
    """
    try:
        user_id = _get_user_id(current_user)
        oauth_service = _get_oauth_service(db_pool)
        status = await oauth_service.get_connection_status(user_id)

        return ConnectionStatusResponse(
            connected=status["connected"],
            email=status.get("email"),
            account_id=status.get("account_id"),
            expires_at=status.get("expires_at"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get connection status: {e}")
        return ConnectionStatusResponse(
            connected=False, email=None, account_id=None, expires_at=None
        )


@router.delete("/disconnect")
async def disconnect_account(
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Disconnect Zoho account and remove tokens.

    Revokes OAuth tokens and clears all stored data.
    """
    try:
        user_id = _get_user_id(current_user)
        oauth_service = _get_oauth_service(db_pool)
        await oauth_service.disconnect(user_id)

        return {"success": True, "message": "Zoho account disconnected"}
    except Exception as e:
        logger.error(f"Failed to disconnect: {e}")
        raise HTTPException(status_code=500, detail="Failed to disconnect account")


# ================================================
# FOLDER ENDPOINTS
# ================================================


@router.get("/folders")
async def list_folders(
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    List all email folders.

    Returns object with folders list and unread counts.
    """
    try:
        user_id = _get_user_id(current_user)
        email_service = _get_email_service(db_pool)
        folders = await email_service.list_folders(user_id)
        return {"folders": folders}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to list folders: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch folders")


# ================================================
# EMAIL ENDPOINTS
# ================================================


@router.get("/emails")
async def list_emails(
    folder_id: str = Query("inbox", description="Folder ID"),
    limit: int = Query(50, ge=1, le=200, description="Max emails to return"),
    start: int = Query(0, ge=0, description="Offset for pagination"),
    search: str | None = Query(None, description="Search query"),
    is_unread: bool | None = Query(None, description="Filter by read status"),
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    List emails in a folder with pagination and filtering.

    Returns emails with pagination info.
    """
    try:
        user_id = _get_user_id(current_user)
        email_service = _get_email_service(db_pool)

        return await email_service.list_emails(
            user_id=user_id,
            folder_id=folder_id,
            limit=limit,
            start=start,
            search_key=search,
            is_unread=is_unread,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to list emails: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch emails")


@router.get("/emails/{message_id}")
async def get_email(
    message_id: str = Path(..., description="Email message ID"),
    folder_id: str | None = Query(None, description="Folder ID (required for Zoho API)"),
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Get full email content.

    Returns complete email with body and attachments.
    Automatically marks the email as read.
    """
    try:
        user_id = _get_user_id(current_user)
        email_service = _get_email_service(db_pool)
        return await email_service.get_email(user_id, message_id, folder_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get email: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch email")


@router.post("/emails")
async def send_email(
    request: SendEmailRequest,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Send a new email.

    Supports HTML content, CC/BCC, and attachments.
    """
    try:
        user_id = _get_user_id(current_user)
        email_service = _get_email_service(db_pool)

        return await email_service.send_email(
            user_id=user_id,
            to=[str(e) for e in request.to],
            subject=request.subject,
            content=request.get_content(),  # Accepts html_content, text_content, or content
            cc=[str(e) for e in request.cc] if request.cc else None,
            bcc=[str(e) for e in request.bcc] if request.bcc else None,
            attachments=[a.model_dump() for a in request.attachment_ids]
            if request.attachment_ids
            else None,
            is_html=request.is_html,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise HTTPException(status_code=500, detail="Failed to send email")


@router.get("/emails/search")
async def search_emails(
    query: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(50, ge=1, le=100, description="Max results"),
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> list[dict[str, Any]]:
    """
    Search emails across all folders.

    Returns matching emails.
    """
    try:
        user_id = _get_user_id(current_user)
        email_service = _get_email_service(db_pool)
        return await email_service.search_emails(user_id, query, limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to search emails: {e}")
        raise HTTPException(status_code=500, detail="Failed to search emails")


@router.post("/emails/{message_id}/reply")
async def reply_email(
    message_id: str = Path(..., description="Original message ID"),
    request: ReplyEmailRequest = ...,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Reply to an email.

    Supports reply to sender only or reply all.
    """
    try:
        user_id = _get_user_id(current_user)
        email_service = _get_email_service(db_pool)

        return await email_service.reply_email(
            user_id=user_id,
            message_id=message_id,
            content=request.content,
            reply_all=request.reply_all,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to reply to email: {e}")
        raise HTTPException(status_code=500, detail="Failed to reply to email")


@router.post("/emails/{message_id}/forward")
async def forward_email(
    message_id: str = Path(..., description="Message ID to forward"),
    request: ForwardEmailRequest = ...,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Forward an email.

    Optionally add additional content to forwarded message.
    """
    try:
        user_id = _get_user_id(current_user)
        email_service = _get_email_service(db_pool)

        return await email_service.forward_email(
            user_id=user_id,
            message_id=message_id,
            to=[str(e) for e in request.to],
            content=request.content,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to forward email: {e}")
        raise HTTPException(status_code=500, detail="Failed to forward email")


@router.patch("/emails/mark-read")
async def mark_emails_read(
    request: MarkReadRequest,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, bool]:
    """
    Mark emails as read or unread.

    Supports bulk operation on multiple messages.
    """
    try:
        user_id = _get_user_id(current_user)
        email_service = _get_email_service(db_pool)

        success = await email_service.mark_read(
            user_id=user_id,
            message_ids=request.message_ids,
            is_read=request.is_read,
        )
        return {"success": success}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to mark emails: {e}")
        raise HTTPException(status_code=500, detail="Failed to update emails")


@router.patch("/emails/{message_id}/flag")
async def toggle_flag(
    message_id: str = Path(..., description="Message ID"),
    is_flagged: bool = Query(..., description="Flag status"),
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, bool]:
    """
    Flag or unflag an email.
    """
    try:
        user_id = _get_user_id(current_user)
        email_service = _get_email_service(db_pool)

        success = await email_service.toggle_flag(
            user_id=user_id,
            message_id=message_id,
            is_flagged=is_flagged,
        )
        return {"success": success}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to toggle flag: {e}")
        raise HTTPException(status_code=500, detail="Failed to update email")


@router.delete("/emails")
async def delete_emails(
    request: DeleteEmailsRequest = Body(...),
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, bool]:
    """
    Move emails to trash.

    Supports bulk deletion of multiple messages.
    """
    try:
        user_id = _get_user_id(current_user)
        email_service = _get_email_service(db_pool)

        success = await email_service.delete_emails(
            user_id=user_id,
            message_ids=request.message_ids,
        )
        return {"success": success}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete emails: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete emails")


@router.post("/emails/delete")
async def delete_emails_post(
    request: DeleteEmailsRequest = Body(...),
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, bool]:
    """
    Move emails to trash (POST variant for better proxy compatibility).

    Supports bulk deletion of multiple messages.
    """
    try:
        user_id = _get_user_id(current_user)
        email_service = _get_email_service(db_pool)

        success = await email_service.delete_emails(
            user_id=user_id,
            message_ids=request.message_ids,
        )
        return {"success": success}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete emails: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete emails")


# ================================================
# DRAFT ENDPOINTS
# ================================================


class SaveDraftRequest(BaseModel):
    """Request body for saving a draft."""

    to: list[EmailStr] | None = Field(None, description="Recipient email addresses")
    subject: str = Field(..., max_length=500, description="Email subject")
    html_content: str = Field(..., description="Email content")
    cc: list[EmailStr] | None = Field(None, description="CC recipients")
    bcc: list[EmailStr] | None = Field(None, description="BCC recipients")
    attachment_ids: list[AttachmentObject] | None = Field(None, description="Attachments")


@router.post("/drafts")
async def save_draft(
    request: SaveDraftRequest,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Save an email as draft.
    """
    try:
        user_id = _get_user_id(current_user)
        email_service = _get_email_service(db_pool)

        return await email_service.save_draft(
            user_id=user_id,
            to=[str(e) for e in request.to] if request.to else None,
            subject=request.subject,
            content=request.html_content,
            cc=[str(e) for e in request.cc] if request.cc else None,
            bcc=[str(e) for e in request.bcc] if request.bcc else None,
            attachments=[a.model_dump() for a in request.attachment_ids]
            if request.attachment_ids
            else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to save draft: {e}")
        raise HTTPException(status_code=500, detail="Failed to save draft")


# ================================================
# ATTACHMENT ENDPOINTS
# ================================================


@router.post("/attachments")
async def upload_attachment(
    file: Any = Body(...),  # Using Any to bypass strict type checking for UploadFile
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Upload an attachment.
    Expects multipart/form-data.
    """
    from fastapi import UploadFile

    # Manual type check/cast
    if not isinstance(file, UploadFile):
        # In case FastAPI passes it differently or for testing
        pass

    try:
        user_id = _get_user_id(current_user)
        email_service = _get_email_service(db_pool)

        content = await file.read()
        attachment_result = await email_service.upload_attachment(
            user_id=user_id,
            filename=file.filename or "unnamed",
            content=content,
            content_type=file.content_type or "application/octet-stream",
        )

        return attachment_result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to upload attachment: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload attachment")


@router.get("/emails/{message_id}/attachments/{attachment_id}")
async def download_attachment(
    message_id: str = Path(..., description="Message ID"),
    attachment_id: str = Path(..., description="Attachment ID"),
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> Response:
    """
    Download email attachment.

    Returns attachment content as binary stream.
    """
    try:
        user_id = _get_user_id(current_user)
        email_service = _get_email_service(db_pool)

        content = await email_service.get_attachment(
            user_id=user_id,
            message_id=message_id,
            attachment_id=attachment_id,
        )

        return Response(
            content=content,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={attachment_id}"},
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to download attachment: {e}")
        raise HTTPException(status_code=500, detail="Failed to download attachment")


# ================================================
# UNREAD COUNT ENDPOINT
# ================================================


@router.get("/unread-count")
async def get_unread_count(
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, int]:
    """
    Get total unread email count.

    Useful for displaying badge in navigation.
    """
    try:
        user_id = _get_user_id(current_user)
        email_service = _get_email_service(db_pool)
        count = await email_service.get_unread_count(user_id)
        return {"unread_count": count}
    except ValueError:
        # Not connected - return 0
        return {"unread_count": 0}
    except Exception as e:
        logger.warning(f"Failed to get unread count: {e}")
        return {"unread_count": 0}


@router.options("/emails")
async def options_emails():
    """Handle OPTIONS requests for DELETE /emails endpoint."""
    return {"detail": "Method allowed"}
