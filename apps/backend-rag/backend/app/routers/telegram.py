"""
Telegram Bot Webhook Router for Zantara
Handles incoming Telegram messages and responds using the RAG system.
"""

import logging
import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from pydantic import BaseModel

from app.core.config import settings
from app.core.intel_approvers import get_required_votes, get_team_config
from app.metrics import (
    intel_items_approved,
    intel_items_rejected,
    intel_qdrant_ingestion_duration,
    intel_qdrant_ingestion_total,
    intel_votes_cast,
    intel_voting_duration,
)
from services.integrations.telegram_bot_service import telegram_bot
from services.rag.agentic import AgenticRAGOrchestrator, create_agentic_rag

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/telegram",
    tags=["telegram"],
)

# Lazy-loaded orchestrator
_orchestrator: AgenticRAGOrchestrator | None = None


async def get_orchestrator(request: Request) -> AgenticRAGOrchestrator:
    """Get or create the RAG orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        db_pool = getattr(request.app.state, "db_pool", None)
        search_service = getattr(request.app.state, "search_service", None)
        _orchestrator = create_agentic_rag(retriever=search_service, db_pool=db_pool)
    return _orchestrator


class TelegramUpdate(BaseModel):
    """Telegram update object (simplified)."""

    update_id: int
    message: dict[str, Any] | None = None
    edited_message: dict[str, Any] | None = None
    callback_query: dict[str, Any] | None = None


# Storage for article approval status (in production, use Redis or DB)
import json
from datetime import datetime
from pathlib import Path

PENDING_ARTICLES_PATH = Path("/tmp/pending_articles")
PENDING_ARTICLES_PATH.mkdir(exist_ok=True)

# Majority voting configuration
REQUIRED_VOTES = 2  # Need 2/3 to approve or reject


def get_article_status(article_id: str) -> dict:
    """Get article status from storage."""
    status_file = PENDING_ARTICLES_PATH / f"{article_id}.json"
    if status_file.exists():
        return json.loads(status_file.read_text())
    return {
        "article_id": article_id,
        "status": "voting",
        "votes": {"approve": [], "reject": []},
        "feedback": [],
        "created_at": datetime.utcnow().isoformat(),
    }


def save_article_status(article_id: str, data: dict) -> dict:
    """Save article status to storage."""
    status_file = PENDING_ARTICLES_PATH / f"{article_id}.json"
    data["updated_at"] = datetime.utcnow().isoformat()
    status_file.write_text(json.dumps(data, indent=2))
    return data


def add_vote(article_id: str, vote_type: str, user: dict) -> tuple[dict, str]:
    """
    Add a vote for an article.

    Returns:
        tuple: (article_data, result_message)
        result_message can be: "already_voted", "approved", "rejected", "vote_recorded"
    """
    data = get_article_status(article_id)
    user_id = user.get("id")
    user_name = user.get("first_name", "Unknown")

    # Check if already voted
    all_voters = [v["user_id"] for v in data["votes"]["approve"]] + [
        v["user_id"] for v in data["votes"]["reject"]
    ]
    if user_id in all_voters:
        return data, "already_voted"

    # Check if voting is still open
    if data["status"] in ["approved", "rejected"]:
        return data, "voting_closed"

    # Add vote
    vote_record = {
        "user_id": user_id,
        "user_name": user_name,
        "voted_at": datetime.utcnow().isoformat(),
    }
    data["votes"][vote_type].append(vote_record)

    # Check for majority
    approve_count = len(data["votes"]["approve"])
    reject_count = len(data["votes"]["reject"])

    if approve_count >= REQUIRED_VOTES:
        data["status"] = "approved"
        save_article_status(article_id, data)
        logger.info(f"Article {article_id} APPROVED with {approve_count} votes")
        return data, "approved"

    if reject_count >= REQUIRED_VOTES:
        data["status"] = "rejected"
        save_article_status(article_id, data)
        logger.info(f"Article {article_id} REJECTED with {reject_count} votes")
        return data, "rejected"

    # Vote recorded but not decided yet
    save_article_status(article_id, data)
    logger.info(
        f"Article {article_id}: {user_name} voted {vote_type} (approve:{approve_count}, reject:{reject_count})"
    )
    return data, "vote_recorded"


def format_vote_tally(data: dict, original_text: str = "") -> str:
    """Format the current vote tally for display."""
    approve_votes = data["votes"]["approve"]
    reject_votes = data["votes"]["reject"]

    approve_count = len(approve_votes)
    reject_count = len(reject_votes)

    # Build voter list
    voters_list = []
    for v in approve_votes:
        voters_list.append(f"  {v['user_name']} ✅")
    for v in reject_votes:
        voters_list.append(f"  {v['user_name']} ❌")

    voters_str = "\n".join(voters_list) if voters_list else "  (nessun voto)"

    tally = f"""📊 VOTAZIONE IN CORSO

{original_text}

━━━━━━━━━━━━━━━━━━━━━━
Voti: ✅ {approve_count}/{REQUIRED_VOTES} | ❌ {reject_count}/{REQUIRED_VOTES}

Chi ha votato:
{voters_str}
━━━━━━━━━━━━━━━━━━━━━━
Servono {REQUIRED_VOTES} voti per decidere"""

    return tally


# ===================================
# INTELLIGENCE CENTER VOTING
# ===================================

PENDING_INTEL_PATH = Path("/tmp/pending_intel")
PENDING_INTEL_PATH.mkdir(exist_ok=True)


def get_intel_status(item_id: str) -> dict:
    """Get intel item status from storage."""
    status_file = PENDING_INTEL_PATH / f"{item_id}.json"
    if status_file.exists():
        return json.loads(status_file.read_text())
    return {
        "item_id": item_id,
        "intel_type": "unknown",
        "status": "voting",
        "votes": {"approve": [], "reject": []},
        "created_at": datetime.utcnow().isoformat(),
    }


def save_intel_status(item_id: str, data: dict) -> dict:
    """Save intel item status to storage."""
    status_file = PENDING_INTEL_PATH / f"{item_id}.json"
    data["updated_at"] = datetime.utcnow().isoformat()
    status_file.write_text(json.dumps(data, indent=2))
    return data


def add_intel_vote(item_id: str, intel_type: str, vote_type: str, user: dict) -> tuple[dict, str]:
    """
    Add a vote for an intel item.

    Returns:
        tuple: (intel_data, result_message)
        result_message: "already_voted", "approved", "rejected", "vote_recorded"
    """
    data = get_intel_status(item_id)
    data["intel_type"] = intel_type
    user_id = user.get("id")
    user_name = user.get("first_name", "Unknown")

    # Check if already voted
    all_voters = [v["user_id"] for v in data["votes"]["approve"]] + [
        v["user_id"] for v in data["votes"]["reject"]
    ]
    if user_id in all_voters:
        return data, "already_voted"

    # Check if voting is still open
    if data["status"] in ["approved", "rejected"]:
        return data, "voting_closed"

    # Add vote
    vote_record = {
        "user_id": user_id,
        "user_name": user_name,
        "voted_at": datetime.utcnow().isoformat(),
    }
    data["votes"][vote_type].append(vote_record)

    # Metrics: Vote cast
    intel_votes_cast.labels(
        intel_type=intel_type,
        vote_type=vote_type,
        user=user_name
    ).inc()

    # Check for majority
    required_votes = get_required_votes(intel_type)
    approve_count = len(data["votes"]["approve"])
    reject_count = len(data["votes"]["reject"])

    if approve_count >= required_votes:
        data["status"] = "approved"
        save_intel_status(item_id, data)
        logger.info(f"Intel {item_id} ({intel_type}) APPROVED with {approve_count} votes")

        # Metrics: Item approved
        intel_items_approved.labels(intel_type=intel_type).inc()

        # Metrics: Voting duration
        if "created_at" in data:
            try:
                created_dt = datetime.fromisoformat(data["created_at"].replace('Z', '+00:00'))
                duration_seconds = (datetime.utcnow() - created_dt.replace(tzinfo=None)).total_seconds()
                intel_voting_duration.labels(intel_type=intel_type).observe(duration_seconds)
            except Exception:
                pass  # Skip if timestamp parsing fails

        return data, "approved"

    if reject_count >= required_votes:
        data["status"] = "rejected"
        save_intel_status(item_id, data)
        logger.info(f"Intel {item_id} ({intel_type}) REJECTED with {reject_count} votes")

        # Metrics: Item rejected
        intel_items_rejected.labels(intel_type=intel_type).inc()

        # Metrics: Voting duration
        if "created_at" in data:
            try:
                created_dt = datetime.fromisoformat(data["created_at"].replace('Z', '+00:00'))
                duration_seconds = (datetime.utcnow() - created_dt.replace(tzinfo=None)).total_seconds()
                intel_voting_duration.labels(intel_type=intel_type).observe(duration_seconds)
            except Exception:
                pass

        return data, "rejected"

    # Vote recorded but not decided yet
    save_intel_status(item_id, data)
    logger.info(
        f"Intel {item_id} ({intel_type}): {user_name} voted {vote_type} (approve:{approve_count}, reject:{reject_count})"
    )
    return data, "vote_recorded"


def format_intel_vote_tally(data: dict, intel_type: str, original_text: str = "") -> str:
    """Format the current intel vote tally for display."""
    approve_votes = data["votes"]["approve"]
    reject_votes = data["votes"]["reject"]

    approve_count = len(approve_votes)
    reject_count = len(reject_votes)
    required_votes = get_required_votes(intel_type)

    # Build voter list
    voters_list = []
    for v in approve_votes:
        voters_list.append(f"  {v['user_name']} ✅")
    for v in reject_votes:
        voters_list.append(f"  {v['user_name']} ❌")

    voters_str = "\n".join(voters_list) if voters_list else "  (nessun voto)"

    tally = f"""📊 VOTAZIONE IN CORSO

{original_text}

━━━━━━━━━━━━━━━━━━━━━━
Voti: ✅ {approve_count}/{required_votes} | ❌ {reject_count}/{required_votes}

Chi ha votato:
{voters_str}
━━━━━━━━━━━━━━━━━━━━━━
Servono {required_votes} voti per decidere"""

    return tally


async def ingest_intel_to_qdrant(item_id: str, intel_type: str) -> bool:
    """
    Ingest approved intel item to Qdrant.

    This function is called when an intel item receives majority approval.
    It triggers the actual ingestion process.
    """
    ingestion_start = time.time()
    collection_name = "visa_oracle" if intel_type == "visa" else "bali_intel_bali_news"

    try:
        # Import here to avoid circular dependency
        from pathlib import Path as P
        import json as j
        import hashlib
        from datetime import datetime as dt

        # Read staged file
        staging_base = P("data/staging")
        type_dir = "visa" if intel_type == "visa" else "news"
        staging_file = staging_base / type_dir / f"{item_id}.json"

        if not staging_file.exists():
            logger.error(f"Staging file not found: {staging_file}")
            # Metrics: Ingestion failed
            intel_qdrant_ingestion_total.labels(
                collection=collection_name,
                status="error_file_not_found"
            ).inc()
            return False

        data = j.loads(staging_file.read_text())

        # Import ingestion services
        from core.qdrant_db import qdrant_client
        from core.embeddings import embedding_service

        # Extract content
        title = data.get("title", "Untitled")
        content = data.get("content", "")
        source_url = data.get("source_url", "")
        detection_type = data.get("detection_type", "unknown")

        # Create full text for embedding
        full_text = f"{title}\n\n{content}"

        # Generate embedding
        logger.info(f"Generating embedding for {intel_type} item {item_id}")
        embedding = await embedding_service.get_embedding(full_text)

        # Create metadata
        metadata = {
            "title": title,
            "content": content,
            "source_url": source_url,
            "detection_type": detection_type,
            "intel_type": intel_type,
            "ingested_at": dt.utcnow().isoformat(),
            "ingested_via": "telegram_voting",
            "item_id": item_id,
        }

        # Add any additional metadata from staging file
        for key in ["detected_at", "relevance_score", "category"]:
            if key in data:
                metadata[key] = data[key]

        # Generate document ID
        doc_id = hashlib.sha256(f"{intel_type}:{item_id}:{title}".encode()).hexdigest()

        # Upsert to Qdrant
        logger.info(f"Upserting to Qdrant: {collection_name}")
        await qdrant_client.upsert_documents(
            chunks=[full_text],
            embeddings=[embedding],
            metadatas=[metadata],
            ids=[doc_id],
        )

        logger.info(f"✅ Successfully ingested {intel_type} item {item_id} to {collection_name}")

        # Metrics: Ingestion success
        intel_qdrant_ingestion_total.labels(
            collection=collection_name,
            status="success"
        ).inc()

        intel_qdrant_ingestion_duration.labels(
            collection=collection_name
        ).observe(time.time() - ingestion_start)

        # Update staging file with ingestion timestamp
        data["ingested_at"] = dt.utcnow().isoformat()
        data["ingested_to_collection"] = collection_name
        data["qdrant_id"] = doc_id

        # Move to archived/approved
        archive_dir = staging_base / type_dir / "archived" / "approved"
        archive_dir.mkdir(parents=True, exist_ok=True)
        approved_file = archive_dir / f"{item_id}.json"
        approved_file.write_text(j.dumps(data, indent=2))
        staging_file.unlink()  # Remove from staging

        logger.info(f"Archived approved item to {approved_file}")

        return True

    except Exception as e:
        logger.exception(f"Failed to ingest intel {item_id}: {e}")

        # Metrics: Ingestion error
        intel_qdrant_ingestion_total.labels(
            collection=collection_name,
            status="error_exception"
        ).inc()

        return False


class WebhookSetupRequest(BaseModel):
    """Request to set up webhook."""

    webhook_url: str | None = None


async def process_telegram_message(
    chat_id: int,
    message_text: str,
    user_name: str,
    message_id: int,
    request: Request,
):
    """
    Background task to process a Telegram message and respond.

    Args:
        chat_id: Telegram chat ID
        message_text: User's message text
        user_name: User's display name
        message_id: Original message ID for reply
        request: FastAPI request for app state access
    """
    try:
        # Send typing indicator
        await telegram_bot.send_chat_action(chat_id, "typing")

        # Get orchestrator
        orchestrator = await get_orchestrator(request)

        # Create unique user_id for Telegram users
        telegram_user_id = f"telegram_{chat_id}"

        # Process query through RAG
        logger.info(
            f"Processing Telegram message from {user_name} ({chat_id}): {message_text[:50]}..."
        )

        result = await orchestrator.process_query(
            query=message_text,
            user_id=telegram_user_id,
            session_id=f"telegram_session_{chat_id}",
        )

        # Format response
        response_text = result.answer

        # Truncate if too long (Telegram limit: 4096 chars)
        if len(response_text) > 4000:
            response_text = response_text[:3950] + "\n\n_...risposta troncata_"

        # Send response
        await telegram_bot.send_message(
            chat_id=chat_id,
            text=response_text,
            reply_to_message_id=message_id,
            parse_mode="Markdown",
        )

        logger.info(f"Telegram response sent to {chat_id}")

    except Exception as e:
        logger.exception(f"Error processing Telegram message: {e}")

        # Send error message
        error_text = "⚠️ Sorry, something went wrong.\nPlease try again in a few seconds."
        try:
            await telegram_bot.send_message(
                chat_id=chat_id,
                text=error_text,
                reply_to_message_id=message_id,
            )
        except Exception:
            logger.error("Failed to send error message to Telegram")


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: str | None = Header(None),
):
    """
    Telegram webhook endpoint.

    Receives updates from Telegram and processes messages using RAG.
    """
    # Verify secret token if configured
    expected_secret = settings.telegram_webhook_secret
    if expected_secret:
        if x_telegram_bot_api_secret_token != expected_secret:
            logger.warning("Invalid Telegram webhook secret token")
            raise HTTPException(status_code=403, detail="Invalid secret token")

    # Parse update
    try:
        body = await request.json()
        update = TelegramUpdate(**body)
    except Exception as e:
        logger.error(f"Failed to parse Telegram update: {e}")
        raise HTTPException(status_code=400, detail="Invalid update format")

    # Handle callback query (button clicks for article approval)
    if update.callback_query:
        callback = update.callback_query
        callback_id = callback.get("id")
        data = callback.get("data", "")
        user = callback.get("from", {})
        message = callback.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        message_id = message.get("message_id")
        user_name = user.get("first_name", "Unknown")
        user_id = user.get("id")

        logger.info(f"Callback query: {data} from {user_name} ({user_id})")

        # Parse callback data
        if ":" not in data:
            await telegram_bot.answer_callback_query(callback_id, "Invalid action", show_alert=True)
            return {"ok": True}

        parts = data.split(":")

        # =====================
        # INTELLIGENCE CENTER HANDLERS
        # =====================
        if parts[0] == "intel" and len(parts) == 4:
            # Format: intel:approve/reject:type:item_id
            _, action, intel_type, item_id = parts

            # Get original message text
            original_text = message.get("text", "")
            if "━━━━" in original_text:
                original_text = original_text.split("━━━━")[0].strip()
            if original_text.startswith("📊"):
                lines = original_text.split("\n")
                original_text = "\n".join(lines[1:]).strip()

            # Handle APPROVE
            if action == "approve":
                intel_data, result = add_intel_vote(item_id, intel_type, "approve", user)

                if result == "already_voted":
                    await telegram_bot.answer_callback_query(
                        callback_id, "⚠️ Hai già votato!", show_alert=True
                    )

                elif result == "voting_closed":
                    await telegram_bot.answer_callback_query(
                        callback_id, "⚠️ Votazione già chiusa", show_alert=True
                    )

                elif result == "approved":
                    # Majority reached - APPROVED!
                    voters = ", ".join([v["user_name"] for v in intel_data["votes"]["approve"]])
                    required_votes = get_required_votes(intel_type)
                    total_approvers = len(get_team_config(intel_type)["approvers"])

                    await telegram_bot.answer_callback_query(
                        callback_id, "✅ APPROVATO! Maggioranza raggiunta!", show_alert=True
                    )
                    await telegram_bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=f"✅ APPROVATO ({required_votes}/{total_approvers})\n\n{intel_type.upper()} Item {item_id}\n\nApprovato da: {voters}\n\n🔄 Ingestion a Qdrant in corso...",
                        parse_mode=None,
                    )
                    # Trigger ingestion
                    ingestion_success = await ingest_intel_to_qdrant(item_id, intel_type)
                    if ingestion_success:
                        logger.info(f"✅ Intel {item_id} ingested successfully")
                    else:
                        logger.error(f"❌ Intel {item_id} ingestion failed")

                else:
                    # Vote recorded, update tally
                    approve_count = len(intel_data["votes"]["approve"])
                    required_votes = get_required_votes(intel_type)
                    await telegram_bot.answer_callback_query(
                        callback_id,
                        f"✅ Voto registrato ({approve_count}/{required_votes})",
                        show_alert=False,
                    )
                    # Update message with new tally, keep buttons
                    tally_text = format_intel_vote_tally(intel_data, intel_type, original_text)
                    await telegram_bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=tally_text,
                        parse_mode=None,
                        reply_markup={
                            "inline_keyboard": [
                                [
                                    {"text": "✅ APPROVE", "callback_data": f"intel:approve:{intel_type}:{item_id}"},
                                    {"text": "❌ REJECT", "callback_data": f"intel:reject:{intel_type}:{item_id}"},
                                ]
                            ]
                        },
                    )

            # Handle REJECT
            elif action == "reject":
                intel_data, result = add_intel_vote(item_id, intel_type, "reject", user)

                if result == "already_voted":
                    await telegram_bot.answer_callback_query(
                        callback_id, "⚠️ Hai già votato!", show_alert=True
                    )

                elif result == "voting_closed":
                    await telegram_bot.answer_callback_query(
                        callback_id, "⚠️ Votazione già chiusa", show_alert=True
                    )

                elif result == "rejected":
                    # Majority reached - REJECTED!
                    voters = ", ".join([v["user_name"] for v in intel_data["votes"]["reject"]])
                    required_votes = get_required_votes(intel_type)
                    total_approvers = len(get_team_config(intel_type)["approvers"])

                    await telegram_bot.answer_callback_query(
                        callback_id, "❌ RIFIUTATO! Maggioranza raggiunta!", show_alert=True
                    )
                    await telegram_bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=f"❌ RIFIUTATO ({required_votes}/{total_approvers})\n\n{intel_type.upper()} Item {item_id}\n\nRifiutato da: {voters}\n\nL'item è stato scartato.",
                        parse_mode=None,
                    )

                else:
                    # Vote recorded, update tally
                    reject_count = len(intel_data["votes"]["reject"])
                    required_votes = get_required_votes(intel_type)
                    await telegram_bot.answer_callback_query(
                        callback_id,
                        f"❌ Voto registrato ({reject_count}/{required_votes})",
                        show_alert=False,
                    )
                    # Update message with new tally, keep buttons
                    tally_text = format_intel_vote_tally(intel_data, intel_type, original_text)
                    await telegram_bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=tally_text,
                        parse_mode=None,
                        reply_markup={
                            "inline_keyboard": [
                                [
                                    {"text": "✅ APPROVE", "callback_data": f"intel:approve:{intel_type}:{item_id}"},
                                    {"text": "❌ REJECT", "callback_data": f"intel:reject:{intel_type}:{item_id}"},
                                ]
                            ]
                        },
                    )

            return {"ok": True}

        # =====================
        # ARTICLE APPROVAL HANDLERS (existing)
        # =====================
        # Parse callback data (format: "action:article_id")
        action, article_id = data.split(":", 1)

        # Get original message text (without buttons) for context
        original_text = message.get("text", "")
        # Extract just the article description part (before vote tally if present)
        if "━━━━" in original_text:
            original_text = original_text.split("━━━━")[0].strip()
        if original_text.startswith("📊"):
            # Remove voting header
            lines = original_text.split("\n")
            original_text = "\n".join(lines[1:]).strip()

        # Handle APPROVE vote
        if action == "approve":
            data, result = add_vote(article_id, "approve", user)

            if result == "already_voted":
                await telegram_bot.answer_callback_query(
                    callback_id, "⚠️ Hai già votato!", show_alert=True
                )

            elif result == "voting_closed":
                await telegram_bot.answer_callback_query(
                    callback_id, "⚠️ Votazione già chiusa", show_alert=True
                )

            elif result == "approved":
                # Majority reached - APPROVED!
                voters = ", ".join([v["user_name"] for v in data["votes"]["approve"]])
                await telegram_bot.answer_callback_query(
                    callback_id, "✅ APPROVATO! Maggioranza raggiunta!", show_alert=True
                )
                await telegram_bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"✅ APPROVATO (2/3)\n\nArticolo {article_id}\n\nApprovato da: {voters}\n\nL'articolo sarà pubblicato a breve.",
                    parse_mode=None,
                )
                # TODO: Trigger publish to BaliZero API

            else:
                # Vote recorded, update tally
                approve_count = len(data["votes"]["approve"])
                await telegram_bot.answer_callback_query(
                    callback_id,
                    f"✅ Voto registrato ({approve_count}/{REQUIRED_VOTES})",
                    show_alert=False,
                )
                # Update message with new tally, keep buttons
                tally_text = format_vote_tally(data, original_text)
                await telegram_bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=tally_text,
                    parse_mode=None,
                    reply_markup={
                        "inline_keyboard": [
                            [
                                {"text": "✅ APPROVE", "callback_data": f"approve:{article_id}"},
                                {"text": "❌ REJECT", "callback_data": f"reject:{article_id}"},
                            ],
                            [
                                {
                                    "text": "✏️ REQUEST CHANGES",
                                    "callback_data": f"changes:{article_id}",
                                }
                            ],
                        ]
                    },
                )

        # Handle REJECT vote
        elif action == "reject":
            data, result = add_vote(article_id, "reject", user)

            if result == "already_voted":
                await telegram_bot.answer_callback_query(
                    callback_id, "⚠️ Hai già votato!", show_alert=True
                )

            elif result == "voting_closed":
                await telegram_bot.answer_callback_query(
                    callback_id, "⚠️ Votazione già chiusa", show_alert=True
                )

            elif result == "rejected":
                # Majority reached - REJECTED!
                voters = ", ".join([v["user_name"] for v in data["votes"]["reject"]])
                await telegram_bot.answer_callback_query(
                    callback_id, "❌ RIFIUTATO! Maggioranza raggiunta!", show_alert=True
                )
                await telegram_bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"❌ RIFIUTATO (2/3)\n\nArticolo {article_id}\n\nRifiutato da: {voters}\n\nL'articolo è stato scartato.",
                    parse_mode=None,
                )

            else:
                # Vote recorded, update tally
                reject_count = len(data["votes"]["reject"])
                await telegram_bot.answer_callback_query(
                    callback_id,
                    f"❌ Voto registrato ({reject_count}/{REQUIRED_VOTES})",
                    show_alert=False,
                )
                # Update message with new tally, keep buttons
                tally_text = format_vote_tally(data, original_text)
                await telegram_bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=tally_text,
                    parse_mode=None,
                    reply_markup={
                        "inline_keyboard": [
                            [
                                {"text": "✅ APPROVE", "callback_data": f"approve:{article_id}"},
                                {"text": "❌ REJECT", "callback_data": f"reject:{article_id}"},
                            ],
                            [
                                {
                                    "text": "✏️ REQUEST CHANGES",
                                    "callback_data": f"changes:{article_id}",
                                }
                            ],
                        ]
                    },
                )

        # Handle REQUEST CHANGES
        elif action == "changes":
            data = get_article_status(article_id)
            if "feedback" not in data:
                data["feedback"] = []
            data["feedback"].append(
                {
                    "user_id": user.get("id"),
                    "user_name": user_name,
                    "requested_at": datetime.utcnow().isoformat(),
                }
            )
            save_article_status(article_id, data)

            await telegram_bot.answer_callback_query(
                callback_id, "✏️ Rispondi con il tuo feedback", show_alert=True
            )
            await telegram_bot.send_message(
                chat_id=chat_id,
                text=f"✏️ {user_name} richiede modifiche\n\nRispondi a questo messaggio con le modifiche desiderate per l'articolo {article_id}.\n\nEsempio: Aggiungi più dettagli sulla procedura",
                parse_mode=None,
            )

        else:
            await telegram_bot.answer_callback_query(
                callback_id, f"Azione sconosciuta: {action}", show_alert=True
            )

        return {"ok": True}

    # Handle message
    message = update.message or update.edited_message
    if message:
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")
        message_id = message.get("message_id")
        user = message.get("from", {})
        user_name = user.get("first_name", "User")

        if chat_id and text:
            # Handle /start command
            if text.strip() == "/start":
                welcome_text = (
                    "👋 Hi! I'm *Zantara*, your AI assistant for visas, "
                    "business setup, and legal matters in Indonesia.\n\n"
                    "Ask me anything - I'll respond in your language! 🇮🇩\n\n"
                    "_Powered by Bali Zero_"
                )
                await telegram_bot.send_message(
                    chat_id=chat_id,
                    text=welcome_text,
                    parse_mode="Markdown",
                )
                return {"ok": True}

            # Handle /help command
            if text.strip() == "/help":
                help_text = (
                    "🆘 *How can I help you:*\n\n"
                    "• Visa questions (KITAS, KITAP, VOA, B211)\n"
                    "• PT PMA / company setup\n"
                    "• Indonesia tax matters\n"
                    "• Work permits (IMTA)\n"
                    "• Bali Zero pricing & procedures\n\n"
                    "_Ask in any language - I'll adapt!_"
                )
                await telegram_bot.send_message(
                    chat_id=chat_id,
                    text=help_text,
                    parse_mode="Markdown",
                )
                return {"ok": True}

            # Process normal message in background
            background_tasks.add_task(
                process_telegram_message,
                chat_id=chat_id,
                message_text=text,
                user_name=user_name,
                message_id=message_id,
                request=request,
            )

    return {"ok": True}


@router.post("/setup-webhook")
async def setup_webhook(req: WebhookSetupRequest):
    """
    Set up Telegram webhook.

    If webhook_url is not provided, uses default Fly.io URL.
    """
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=400, detail="Telegram bot token not configured")

    # Default webhook URL
    webhook_url = req.webhook_url or "https://nuzantara-rag.fly.dev/api/telegram/webhook"

    try:
        result = await telegram_bot.set_webhook(
            url=webhook_url,
            secret_token=settings.telegram_webhook_secret,
            allowed_updates=["message", "edited_message", "callback_query"],
        )
        return {
            "success": True,
            "webhook_url": webhook_url,
            "telegram_response": result,
        }
    except Exception as e:
        logger.error(f"Failed to set up webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/webhook")
async def delete_webhook():
    """Remove Telegram webhook."""
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=400, detail="Telegram bot token not configured")

    try:
        result = await telegram_bot.delete_webhook()
        return {"success": True, "telegram_response": result}
    except Exception as e:
        logger.error(f"Failed to delete webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/webhook-info")
async def get_webhook_info():
    """Get current webhook configuration."""
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=400, detail="Telegram bot token not configured")

    try:
        result = await telegram_bot.get_webhook_info()
        return result
    except Exception as e:
        logger.error(f"Failed to get webhook info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bot-info")
async def get_bot_info():
    """Get bot information."""
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=400, detail="Telegram bot token not configured")

    try:
        result = await telegram_bot.get_me()
        return result
    except Exception as e:
        logger.error(f"Failed to get bot info: {e}")
        raise HTTPException(status_code=500, detail=str(e))
