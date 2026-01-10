"""
Oracle Google Services
Manages Google Gemini AI and Drive integration for Oracle endpoints

UPDATED 2025-12-23:
- Migrated to new google-genai SDK via GenAIClient wrapper
"""

import json
import logging
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from backend.llm.genai_client import GENAI_AVAILABLE, GenAIClient

from .oracle_config import oracle_config

logger = logging.getLogger(__name__)


class GoogleServices:
    """Google Cloud services manager for Oracle endpoints"""

    def __init__(self):
        self._gemini_initialized = False
        self._drive_service = None
        self._genai_client: GenAIClient | None = None
        self._initialize_services()

    def _initialize_services(self) -> None:
        """Initialize Google Gemini and Drive services"""
        try:
            # Initialize GenAI client (only if API key is available)
            api_key = oracle_config.google_api_key
            if api_key and GENAI_AVAILABLE:
                self._genai_client = GenAIClient(api_key=api_key)
                self._gemini_initialized = self._genai_client.is_available
                if self._gemini_initialized:
                    logger.info("✅ Google Gemini AI initialized successfully (new SDK)")
            else:
                logger.warning(
                    "⚠️ GOOGLE_API_KEY not set or SDK unavailable - Gemini AI services disabled"
                )
                self._gemini_initialized = False

            # Initialize Drive Service
            self._initialize_drive_service()

        except Exception as e:
            logger.error(f"❌ Failed to initialize Google services: {e}")
            logger.warning(
                "⚠️ Continuing without Google services - some Oracle features may be unavailable"
            )
            self._gemini_initialized = False
            self._drive_service = None

    def _initialize_drive_service(self) -> None:
        """Initialize Google Drive service using service account"""
        try:
            try:
                creds_dict = json.loads(oracle_config.google_credentials_json)
                credentials = service_account.Credentials.from_service_account_info(
                    creds_dict, scopes=["https://www.googleapis.com/auth/drive.readonly"]
                )
            except (json.JSONDecodeError, ValueError) as e:
                # Fallback to file if env var is invalid/missing
                # This fixes the crash where GOOGLE_CREDENTIALS_JSON is partial/invalid
                import os

                if os.path.exists("google_credentials.json"):
                    logger.warning(
                        f"⚠️ Failed to load credentials from env: {e}. Falling back to google_credentials.json file."
                    )
                    credentials = service_account.Credentials.from_service_account_file(
                        "google_credentials.json",
                        scopes=["https://www.googleapis.com/auth/drive.readonly"],
                    )
                else:
                    raise e

            self._drive_service = build("drive", "v3", credentials=credentials)
            logger.info("✅ Google Drive service initialized successfully")

        except Exception as e:
            logger.error(f"❌ Error initializing Google Drive service: {e}")
            self._drive_service = None

    @property
    def gemini_available(self) -> bool:
        """Check if Gemini is available"""
        return self._gemini_initialized

    @property
    def drive_service(self) -> Any:
        """Get Drive service instance"""
        return self._drive_service

    @property
    def genai_client(self) -> GenAIClient | None:
        """Get the GenAI client instance for direct API calls"""
        return self._genai_client

    def get_model_name(self, model_name: str = "gemini-3-flash-preview") -> str:
        """Get a valid model name, stripping 'models/' prefix if present.

        Args:
            model_name: Requested model name

        Returns:
            Normalized model name (without 'models/' prefix)
        """
        # Strip 'models/' prefix for new SDK compatibility
        return model_name.replace("models/", "")

    def get_gemini_model_name(self, model_name: str = "gemini-3-flash-preview") -> str:
        """Get Gemini model name for use with GenAIClient.

        Note: This method now returns a model name string instead of a model instance.
        Use the genai_client property to make API calls with this model name.

        Args:
            model_name: Requested model name

        Returns:
            Normalized model name string
        """
        if not self._gemini_initialized:
            raise RuntimeError("Gemini AI not initialized")

        return self.get_model_name(model_name)

    def get_zantara_model_name(self, use_case: str = "legal_reasoning") -> str:
        """
        Get the best Gemini model name for specific ZANTARA use cases.

        Note: This method now returns a model name string instead of a model instance.
        Use the genai_client property to make API calls with this model name.

        Args:
            use_case: Type of task
                - "legal_reasoning": Complex legal analysis
                - "personality_translation": Fast personality conversion
                - "multilingual": Multi-language support
                - "document_analysis": Deep document understanding

        Returns:
            Model name string for use with GenAIClient
        """
        if not self._gemini_initialized:
            raise RuntimeError("Gemini AI not initialized")

        # Model recommendations by use case (all use Flash for unlimited quota)
        model_mapping = {
            "legal_reasoning": "gemini-3-flash-preview",
            "personality_translation": "gemini-3-flash-preview",
            "multilingual": "gemini-3-flash-preview",
            "document_analysis": "gemini-3-flash-preview",
        }

        model_name = model_mapping.get(use_case, "gemini-3-flash-preview")
        logger.info(f"🧠 Using {model_name} for {use_case}")
        return model_name


# Initialize Google services singleton
google_services = GoogleServices()
