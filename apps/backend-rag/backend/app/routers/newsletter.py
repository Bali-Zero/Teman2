"""
Newsletter Router
Handles newsletter subscriptions for Bali Zero Insights blog

Endpoints:
- POST /api/blog/newsletter/subscribe - Subscribe to newsletter
- POST /api/blog/newsletter/confirm - Confirm subscription
- POST /api/blog/newsletter/unsubscribe - Unsubscribe
- PATCH /api/blog/newsletter/preferences - Update preferences
- GET /api/blog/newsletter/subscribers - List subscribers (admin)
"""

import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, field_validator

from app.dependencies import get_database_pool
from app.utils.logging_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/blog/newsletter", tags=["newsletter"])


# ============================================================================
# Pydantic Models
# ============================================================================


class SubscribeRequest(BaseModel):
    """Subscribe request model"""

    email: EmailStr
    name: str | None = None
    categories: list[str] = []
    frequency: str = "weekly"
    language: str = "en"

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, v: str) -> str:
        allowed = ["instant", "daily", "weekly"]
        if v not in allowed:
            raise ValueError(f"frequency must be one of: {allowed}")
        return v


class SubscribeResponse(BaseModel):
    """Subscribe response model"""

    success: bool
    message: str
    subscriberId: str | None = None


class ConfirmRequest(BaseModel):
    """Confirm subscription request"""

    subscriberId: str
    token: str


class UnsubscribeRequest(BaseModel):
    """Unsubscribe request"""

    subscriberId: str | None = None
    email: str | None = None
    token: str | None = None


class PreferencesRequest(BaseModel):
    """Update preferences request"""

    subscriberId: str | None = None
    email: str | None = None
    categories: list[str] | None = None
    frequency: str | None = None
    language: str | None = None


class SubscriberResponse(BaseModel):
    """Subscriber response model"""

    id: str
    email: str
    name: str | None = None
    categories: list[str] = []
    frequency: str = "weekly"
    language: str = "en"
    confirmed: bool = False
    created_at: datetime | None = None


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/subscribe", response_model=SubscribeResponse)
async def subscribe(request: SubscribeRequest, pool=Depends(get_database_pool)):
    """
    Subscribe to the newsletter.
    Creates a new subscriber and sends confirmation email.
    """
    async with pool.acquire() as conn:
        # Check if email already exists
        existing = await conn.fetchrow(
            "SELECT id, confirmed, unsubscribed_at FROM newsletter_subscribers WHERE email = $1",
            request.email,
        )

        if existing:
            if existing["confirmed"] and not existing["unsubscribed_at"]:
                # Already confirmed and active
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": "This email is already subscribed",
                        "code": "ALREADY_SUBSCRIBED",
                    },
                )
            elif existing["unsubscribed_at"]:
                # Resubscribing
                confirmation_token = secrets.token_urlsafe(32)
                await conn.execute(
                    """
                    UPDATE newsletter_subscribers
                    SET confirmed = FALSE,
                        unsubscribed_at = NULL,
                        confirmation_token = $2,
                        confirmation_sent_at = NOW(),
                        categories = $3,
                        frequency = $4,
                        language = $5,
                        name = $6,
                        updated_at = NOW()
                    WHERE email = $1
                    """,
                    request.email,
                    confirmation_token,
                    request.categories,
                    request.frequency,
                    request.language,
                    request.name,
                )
                logger.info(f"Resubscribed: {request.email}")
                return SubscribeResponse(
                    success=True,
                    message="Please check your email to confirm your subscription.",
                    subscriberId=existing["id"],
                )
            else:
                # Exists but not confirmed - resend confirmation
                confirmation_token = secrets.token_urlsafe(32)
                await conn.execute(
                    """
                    UPDATE newsletter_subscribers
                    SET confirmation_token = $2,
                        confirmation_sent_at = NOW(),
                        categories = $3,
                        frequency = $4,
                        language = $5,
                        name = $6,
                        updated_at = NOW()
                    WHERE email = $1
                    """,
                    request.email,
                    confirmation_token,
                    request.categories,
                    request.frequency,
                    request.language,
                    request.name,
                )
                logger.info(f"Resent confirmation: {request.email}")
                return SubscribeResponse(
                    success=True,
                    message="Confirmation email resent. Please check your inbox.",
                    subscriberId=existing["id"],
                )

        # New subscriber
        confirmation_token = secrets.token_urlsafe(32)
        row = await conn.fetchrow(
            """
            INSERT INTO newsletter_subscribers (
                email, name, categories, frequency, language,
                confirmation_token, confirmation_sent_at, source
            ) VALUES ($1, $2, $3, $4, $5, $6, NOW(), 'blog')
            RETURNING id
            """,
            request.email,
            request.name,
            request.categories,
            request.frequency,
            request.language,
            confirmation_token,
        )

        subscriber_id = row["id"]
        logger.info(f"New subscriber: {request.email} (ID: {subscriber_id})")

        # TODO: Send confirmation email via Zoho
        # await send_confirmation_email(request.email, subscriber_id, confirmation_token)

        return SubscribeResponse(
            success=True,
            message="Please check your email to confirm your subscription.",
            subscriberId=subscriber_id,
        )


@router.post("/confirm")
async def confirm_subscription(request: ConfirmRequest, pool=Depends(get_database_pool)):
    """
    Confirm a newsletter subscription using the token from email.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, email, confirmed FROM newsletter_subscribers
            WHERE id = $1 AND confirmation_token = $2
            """,
            request.subscriberId,
            request.token,
        )

        if not row:
            raise HTTPException(status_code=404, detail="Invalid confirmation link")

        if row["confirmed"]:
            return {"success": True, "message": "Subscription already confirmed"}

        await conn.execute(
            """
            UPDATE newsletter_subscribers
            SET confirmed = TRUE,
                confirmed_at = NOW(),
                confirmation_token = NULL,
                updated_at = NOW()
            WHERE id = $1
            """,
            request.subscriberId,
        )

        logger.info(f"Confirmed subscription: {row['email']}")
        return {"success": True, "message": "Subscription confirmed successfully"}


@router.post("/unsubscribe")
async def unsubscribe(request: UnsubscribeRequest, pool=Depends(get_database_pool)):
    """
    Unsubscribe from the newsletter.
    """
    async with pool.acquire() as conn:
        # Find subscriber by ID, email, or token
        if request.subscriberId:
            row = await conn.fetchrow(
                "SELECT id, email FROM newsletter_subscribers WHERE id = $1", request.subscriberId
            )
        elif request.email:
            row = await conn.fetchrow(
                "SELECT id, email FROM newsletter_subscribers WHERE email = $1", request.email
            )
        else:
            raise HTTPException(status_code=400, detail="Email or subscriberId required")

        if not row:
            raise HTTPException(status_code=404, detail="Subscriber not found")

        await conn.execute(
            """
            UPDATE newsletter_subscribers
            SET unsubscribed_at = NOW(), updated_at = NOW()
            WHERE id = $1
            """,
            row["id"],
        )

        logger.info(f"Unsubscribed: {row['email']}")
        return {"success": True, "message": "Successfully unsubscribed"}


@router.patch("/preferences")
async def update_preferences(request: PreferencesRequest, pool=Depends(get_database_pool)):
    """
    Update newsletter preferences.
    """
    async with pool.acquire() as conn:
        # Find subscriber
        if request.subscriberId:
            row = await conn.fetchrow(
                "SELECT id FROM newsletter_subscribers WHERE id = $1", request.subscriberId
            )
        elif request.email:
            row = await conn.fetchrow(
                "SELECT id FROM newsletter_subscribers WHERE email = $1", request.email
            )
        else:
            raise HTTPException(status_code=400, detail="Email or subscriberId required")

        if not row:
            raise HTTPException(status_code=404, detail="Subscriber not found")

        # Build dynamic update
        updates = []
        params = [row["id"]]
        param_idx = 2

        if request.categories is not None:
            updates.append(f"categories = ${param_idx}")
            params.append(request.categories)
            param_idx += 1

        if request.frequency is not None:
            updates.append(f"frequency = ${param_idx}")
            params.append(request.frequency)
            param_idx += 1

        if request.language is not None:
            updates.append(f"language = ${param_idx}")
            params.append(request.language)
            param_idx += 1

        if not updates:
            return {"success": True, "message": "No changes"}

        updates.append("updated_at = NOW()")
        query = f"UPDATE newsletter_subscribers SET {', '.join(updates)} WHERE id = $1"
        await conn.execute(query, *params)

        logger.info(f"Updated preferences for subscriber: {row['id']}")
        return {"success": True, "message": "Preferences updated"}


@router.get("/subscribers")
async def list_subscribers(
    category: str | None = Query(None),
    frequency: str | None = Query(None),
    confirmed: bool | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    pool=Depends(get_database_pool),
):
    """
    List newsletter subscribers (admin endpoint).
    """
    async with pool.acquire() as conn:
        # Build query with filters
        conditions = ["unsubscribed_at IS NULL"]
        params = []
        param_idx = 1

        if category:
            conditions.append(f"${param_idx} = ANY(categories)")
            params.append(category)
            param_idx += 1

        if frequency:
            conditions.append(f"frequency = ${param_idx}")
            params.append(frequency)
            param_idx += 1

        if confirmed is not None:
            conditions.append(f"confirmed = ${param_idx}")
            params.append(confirmed)
            param_idx += 1

        where_clause = " AND ".join(conditions)
        params.extend([limit, offset])

        query = f"""
            SELECT id, email, name, categories, frequency, language, confirmed, created_at
            FROM newsletter_subscribers
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """

        rows = await conn.fetch(query, *params)

        # Get total count
        count_query = f"SELECT COUNT(*) FROM newsletter_subscribers WHERE {where_clause}"
        total = await conn.fetchval(count_query, *params[:-2])

        subscribers = [
            SubscriberResponse(
                id=row["id"],
                email=row["email"],
                name=row["name"],
                categories=row["categories"] or [],
                frequency=row["frequency"] or "weekly",
                language=row["language"] or "en",
                confirmed=row["confirmed"] or False,
                created_at=row["created_at"],
            )
            for row in rows
        ]

        return {
            "subscribers": [s.model_dump() for s in subscribers],
            "total": total,
            "limit": limit,
            "offset": offset,
        }


@router.post("/log")
async def log_newsletter_send(
    article_id: str,
    recipient_count: int,
    sent_count: int,
    failed_count: int,
    pool=Depends(get_database_pool),
):
    """
    Log a newsletter send event (admin endpoint).
    """
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO newsletter_send_log (article_id, recipient_count, sent_count, failed_count)
            VALUES ($1, $2, $3, $4)
            """,
            article_id,
            recipient_count,
            sent_count,
            failed_count,
        )

        return {"success": True}
