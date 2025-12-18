"""
Response Handler Module
Applies response sanitization and quality enforcement
"""

import logging
import sys
from pathlib import Path

# Add utils to path for response_sanitizer import
sys.path.append(str(Path(__file__).parent.parent.parent))
from utils.response_sanitizer import classify_query_type as classify_query_for_rag
from utils.response_sanitizer import process_zantara_response

logger = logging.getLogger(__name__)


class ResponseHandler:
    """
    Response Handler for sanitization and quality enforcement

    Applies:
    - PHASE 1: Response sanitization (removes training data artifacts)
    - PHASE 2: Length enforcement (SANTAI mode max 30 words)
    - Conditional contact info (not for greetings)
    """

    def __init__(self):
        """Initialize response handler"""
        logger.info("✨ [ResponseHandler] Initialized (PHASE 1 & 2 fixes)")

    def classify_query(self, message: str) -> str:
        """
        Classify query type for RAG and sanitization

        Args:
            message: User message

        Returns:
            Query type: "greeting", "casual", "business", or "emergency"
        """
        return classify_query_for_rag(message)

    def sanitize_response(
        self, response: str, query_type: str, apply_santai: bool = True, add_contact: bool = True
    ) -> str:
        """
        Sanitize and enforce quality standards on response

        Args:
            response: Raw AI response
            query_type: Query classification (greeting, casual, business, emergency)
            apply_santai: Whether to enforce SANTAI mode length limits
            add_contact: Whether to conditionally add contact info

        Returns:
            Sanitized response
        """
        if not response:
            return response

        try:
            sanitized = process_zantara_response(
                response, query_type, apply_santai=apply_santai, add_contact=add_contact
            )

            logger.info(f"✨ [ResponseHandler] Sanitized response (type: {query_type})")

            return sanitized

        except Exception as e:
            logger.error(f"✨ [ResponseHandler] Error: {e}")
            return response  # Return original if sanitization fails
