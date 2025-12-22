"""
Oracle Google Services
Manages Google Gemini AI and Drive integration for Oracle endpoints
"""

import json
import logging
from typing import Any

import google.generativeai as genai
from google.oauth2 import service_account
from googleapiclient.discovery import build

from services.oracle_config import oracle_config

logger = logging.getLogger(__name__)


class GoogleServices:
    """Google Cloud services manager for Oracle endpoints"""

    def __init__(self):
        self._gemini_initialized = False
        self._drive_service = None
        self._initialize_services()

    def _initialize_services(self) -> None:
        """Initialize Google Gemini and Drive services"""
        try:
            # Initialize Gemini AI (only if API key is available)
            api_key = oracle_config.google_api_key
            if api_key:
                genai.configure(api_key=api_key)
                self._gemini_initialized = True
                logger.info("✅ Google Gemini AI initialized successfully")
            else:
                logger.warning("⚠️ GOOGLE_API_KEY not set - Gemini AI services disabled")
                self._gemini_initialized = False

            # Initialize Drive Service
            self._initialize_drive_service()

        except Exception as e:
            logger.error(f"❌ Failed to initialize Google services: {e}")
            logger.warning("⚠️ Continuing without Google services - some Oracle features may be unavailable")
            self._gemini_initialized = False
            self._drive_service = None

    def _initialize_drive_service(self) -> None:
        """Initialize Google Drive service using service account"""
        try:
            creds_dict = json.loads(oracle_config.google_credentials_json)
            credentials = service_account.Credentials.from_service_account_info(
                creds_dict, scopes=["https://www.googleapis.com/auth/drive.readonly"]
            )
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

    def get_gemini_model(
        self, model_name: str = "models/gemini-2.5-flash"
    ) -> genai.GenerativeModel:
        """Get Gemini model instance"""
        if not self._gemini_initialized:
            raise RuntimeError("Gemini AI not initialized")

        # Try alternative model names for API compatibility (2025 models)
        # SOLO FLASH MODE - Illimitato e veloce per piano ULTRA
        alternative_names = [
            "models/gemini-2.5-flash",  # Primario: Illimitato!
            "models/gemini-2.0-flash-001",
            "models/gemini-flash-latest",
            "models/gemini-pro-latest",  # Fallback solo se necessario
        ]

        # Try original name first
        try:
            return genai.GenerativeModel(model_name)
        except Exception as e:
            logger.warning(f"⚠️ Failed to load model '{model_name}': {e}")

            # Try alternative names
            for alt_name in alternative_names:
                try:
                    logger.info(f"🔄 Trying alternative model name: {alt_name}")
                    return genai.GenerativeModel(alt_name)
                except Exception as e2:
                    logger.warning(f"⚠️ Failed to load alternative model '{alt_name}': {e2}")
                    continue

            raise RuntimeError(
                f"Could not load Gemini model '{model_name}' or any alternatives"
            ) from None

    def get_zantara_model(self, use_case: str = "legal_reasoning") -> genai.GenerativeModel:
        """
        Get the best Gemini model for specific ZANTARA use cases

        Args:
            use_case: Type of task
                - "legal_reasoning": Complex legal analysis (use PRO)
                - "personality_translation": Fast personality conversion (use Flash)
                - "multilingual": Multi-language support (use 3 Pro)
                - "document_analysis": Deep document understanding (use PRO)
        """
        if not self._gemini_initialized:
            raise RuntimeError("Gemini AI not initialized")

        # SOLO GEMINI 2.5 FLASH - Illimitato e performante per piano ULTRA
        model_mapping = {
            "legal_reasoning": [
                "models/gemini-2.5-flash",  # Flash ce la fa benissimo!
                "models/gemini-2.0-flash-001",
                "models/gemini-flash-latest",
            ],
            "personality_translation": [
                "models/gemini-2.5-flash",  # PERFETTO: Illimitato
                "models/gemini-2.0-flash-001",
                "models/gemini-flash-latest",
            ],
            "multilingual": [
                "models/gemini-2.5-flash",  # Flash per tutto (unlimited)
                "models/gemini-2.0-flash-001",
                "models/gemini-flash-latest",
            ],
            "document_analysis": [
                "models/gemini-2.5-flash",  # Flash per ogni analisi
                "models/gemini-2.0-flash-001",
                "models/gemini-flash-latest",
            ],
        }

        models_to_try = model_mapping.get(use_case, model_mapping["legal_reasoning"])

        for model_name in models_to_try:
            try:
                logger.info(f"🧠 Using {model_name} for {use_case}")
                return genai.GenerativeModel(model_name)
            except Exception as e:
                logger.warning(f"⚠️ Failed to load {model_name}: {e}")
                continue

        # Ultimate fallback
        return self.get_gemini_model()


# Initialize Google services singleton
google_services = GoogleServices()
