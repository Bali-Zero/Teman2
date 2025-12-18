"""
💰 CLIENT LIFETIME VALUE PREDICTOR
Predicts high-value clients and automatically nurtures them

Refactored to use modular services:
- ClientScoringService: Calculate LTV scores
- ClientSegmentationService: Segment clients and calculate risk
- NurturingMessageService: Generate personalized messages
- WhatsAppNotificationService: Send messages via Twilio
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

import asyncpg
from agents.services.client_scoring import ClientScoringService
from agents.services.client_segmentation import ClientSegmentationService
from agents.services.nurturing_message import NurturingMessageService
from agents.services.whatsapp_notification import WhatsAppNotificationService

try:
    from llm.zantara_ai_client import ZantaraAIClient

    ZANTARA_AVAILABLE = True
except ImportError:
    ZantaraAIClient = None
    ZANTARA_AVAILABLE = False

logger = logging.getLogger(__name__)

# Constants for nurturing thresholds
VIP_INACTIVE_DAYS = 14
HIGH_VALUE_INACTIVE_DAYS = 60


class ClientValuePredictor:
    """
    Autonomous agent that orchestrates client value prediction and nurturing.

    Uses modular services for:
    - Scoring clients
    - Segmenting clients
    - Generating nurturing messages
    - Sending notifications
    """

    def __init__(
        self,
        db_pool: asyncpg.Pool | None = None,
        ai_client: ZantaraAIClient | None = None,
    ):
        """
        Initialize ClientValuePredictor with dependencies.

        Args:
            db_pool: AsyncPG connection pool (if None, will try to get from app.state)
            ai_client: ZantaraAIClient instance (if None, will create new)
        """
        from app.core.config import settings

        # Get db_pool
        self.db_pool = db_pool
        if not self.db_pool:
            try:
                from app.main_cloud import app

                self.db_pool = getattr(app.state, "db_pool", None)
            except Exception:
                pass

        if not self.db_pool:
            raise RuntimeError(
                "Database pool not available. Provide db_pool in __init__ or ensure app.state.db_pool is set."
            )

        # Initialize services
        self.scoring_service = ClientScoringService(self.db_pool)
        self.segmentation_service = ClientSegmentationService()
        self.message_service = NurturingMessageService(ai_client)
        self.whatsapp_service = WhatsAppNotificationService(
            twilio_sid=settings.twilio_account_sid,
            twilio_token=settings.twilio_auth_token,
            whatsapp_number=settings.twilio_whatsapp_number,
        )

    async def _get_db_pool(self) -> asyncpg.Pool:
        """Get database pool"""
        return self.db_pool

    async def calculate_client_score(self, client_id: str) -> dict[str, Any] | None:
        """
        Calculate comprehensive client value score.

        Args:
            client_id: Client ID to score

        Returns:
            Dictionary with score data or None if client not found
        """
        score_data = await self.scoring_service.calculate_client_score(client_id)
        if score_data:
            return self.segmentation_service.enrich_client_data(score_data)
        return None

    async def calculate_scores_batch(self, client_ids: list[str]) -> dict[str, dict[str, Any]]:
        """
        Calculate scores for multiple clients in batch.

        Args:
            client_ids: List of client IDs to score

        Returns:
            Dictionary mapping client_id -> score data
        """
        scores = await self.scoring_service.calculate_scores_batch(client_ids)

        # Enrich with segmentation
        enriched = {}
        for client_id, score_data in scores.items():
            enriched[client_id] = self.segmentation_service.enrich_client_data(score_data)

        return enriched

    async def generate_nurturing_message(
        self, client_data: dict[str, Any], timeout: float = 30.0
    ) -> str:
        """
        Generate personalized nurturing message.

        Args:
            client_data: Client data with segment, risk_level, etc.
            timeout: Maximum time to wait for message generation

        Returns:
            Generated message text
        """
        return await self.message_service.generate_message(client_data, timeout)

    async def send_whatsapp_message(
        self, phone: str, message: str, max_retries: int = 3
    ) -> str | None:
        """
        Send WhatsApp message via Twilio.

        Args:
            phone: Phone number
            message: Message text
            max_retries: Maximum retry attempts

        Returns:
            Message SID if successful, None otherwise
        """
        return await self.whatsapp_service.send_message(phone, message, max_retries)

    async def run_daily_nurturing(self, timeout: float = 300.0) -> dict[str, Any]:
        """
        Daily job to identify and nurture clients.

        Uses batch processing to fix N+1 queries.

        Args:
            timeout: Maximum time for entire operation (default: 5 minutes)

        Returns:
            Dictionary with results
        """

        async def _run():
            async with self.db_pool.acquire() as conn:
                # Get all active clients
                rows = await conn.fetch("SELECT id::text FROM crm_clients WHERE status = 'active'")
                client_ids = [row["id"] for row in rows]

            if not client_ids:
                logger.info("No active clients found for nurturing")
                return {
                    "vip_nurtured": 0,
                    "high_risk_contacted": 0,
                    "total_messages_sent": 0,
                    "errors": [],
                }

            # Batch calculate all scores (fixes N+1 query problem)
            logger.info(f"Calculating scores for {len(client_ids)} clients in batch...")
            client_scores = await self.calculate_scores_batch(client_ids)

            results = {
                "vip_nurtured": 0,
                "high_risk_contacted": 0,
                "total_messages_sent": 0,
                "errors": [],
            }

            # Process each client
            async with self.db_pool.acquire() as conn, conn.transaction():
                for client_id in client_ids:
                    try:
                        client_data = client_scores.get(client_id)
                        if not client_data:
                            logger.warning(f"No score data for client {client_id}")
                            continue

                        # Update client score in DB
                        await conn.execute(
                            """
                            UPDATE crm_clients
                            SET
                                metadata = metadata || $1::jsonb,
                                updated_at = NOW()
                            WHERE id = $2
                            """,
                            json.dumps(
                                {
                                    "ltv_score": client_data["ltv_score"],
                                    "segment": client_data["segment"],
                                    "risk_level": client_data["risk_level"],
                                    "last_score_update": datetime.now().isoformat(),
                                }
                            ),
                            int(client_id),
                        )

                        # Decide if we should reach out
                        should_nurture, reason = self.segmentation_service.should_nurture(
                            client_data
                        )

                        if should_nurture and client_data.get("phone"):
                            # Generate personalized message
                            message = await self.generate_nurturing_message(client_data)

                            # Send WhatsApp
                            message_sid = await self.send_whatsapp_message(
                                client_data["phone"], message
                            )

                            if message_sid:
                                # Log interaction
                                await conn.execute(
                                    """
                                    INSERT INTO crm_interactions (client_id, type, notes, created_at)
                                    VALUES ($1, 'whatsapp_nurture', $2, NOW())
                                    """,
                                    int(client_id),
                                    f"Auto-nurture: {reason}\nMessage: {message}",
                                )
                                results["total_messages_sent"] += 1

                                if client_data["segment"] == "VIP":
                                    results["vip_nurtured"] += 1
                                if client_data["risk_level"] == "HIGH_RISK":
                                    results["high_risk_contacted"] += 1

                                logger.info(f"✅ Nurtured {client_data['name']} ({reason})")

                    except Exception as e:
                        error_msg = f"Client {client_id}: {str(e)}"
                        results["errors"].append(error_msg)
                        logger.error(f"❌ Error processing client {client_id}: {e}", exc_info=True)

            # Send summary to team
            from app.core.config import settings

            if settings.slack_webhook_url:
                try:
                    import httpx

                    async with httpx.AsyncClient(timeout=10.0) as client:
                        await client.post(
                            settings.slack_webhook_url,
                            json={
                                "text": f"""💰 Daily Client Nurturing Report

VIP Clients Nurtured: {results["vip_nurtured"]}
High-Risk Contacted: {results["high_risk_contacted"]}
Total Messages Sent: {results["total_messages_sent"]}
Errors: {len(results["errors"])}

All clients scored and segmented automatically!"""
                            },
                        )
                except Exception as e:
                    logger.error(f"Failed to send Slack notification: {e}", exc_info=True)

            return results

        try:
            return await asyncio.wait_for(_run(), timeout=timeout)

        except asyncio.TimeoutError:
            logger.error(f"Timeout in run_daily_nurturing after {timeout}s")
            return {
                "vip_nurtured": 0,
                "high_risk_contacted": 0,
                "total_messages_sent": 0,
                "errors": [f"Operation timed out after {timeout}s"],
            }
        except asyncpg.PostgresError as e:
            logger.error(f"Database error in run_daily_nurturing: {e}", exc_info=True)
            return {
                "vip_nurtured": 0,
                "high_risk_contacted": 0,
                "total_messages_sent": 0,
                "errors": [f"Database error: {str(e)}"],
            }
        except Exception as e:
            logger.error(f"Unexpected error in run_daily_nurturing: {e}", exc_info=True)
            return {
                "vip_nurtured": 0,
                "high_risk_contacted": 0,
                "total_messages_sent": 0,
                "errors": [f"Unexpected error: {str(e)}"],
            }
