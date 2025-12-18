"""
Vertex AI Service
Handles interactions with Google Cloud Vertex AI (Gemini Pro).
Used as a fallback for complex extraction tasks.
"""

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

try:
    import vertexai
    from vertexai.preview.generative_models import GenerationConfig, GenerativeModel
except ImportError:
    vertexai = None
    GenerationConfig = None
    GenerativeModel = None
    logger.warning("vertexai module not found. VertexAIService will be disabled.")


class VertexAIService:
    """
    Service for interacting with Vertex AI Gemini models.
    """

    def __init__(self, project_id: str = None, location: str = "us-central1"):
        """
        Initialize Vertex AI service.

        Args:
            project_id: Google Cloud Project ID (defaults to env var GOOGLE_CLOUD_PROJECT)
            location: Vertex AI location (default: us-central1)
        """
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = location
        self._initialized = False
        self.model = None

    def _ensure_initialized(self):
        """Lazy initialization of Vertex AI client."""
        if self._initialized:
            return

        if vertexai is None:
            raise ImportError("vertexai module is not installed.")

        try:
            # Check for credentials
            if not self.project_id:
                logger.warning("GOOGLE_CLOUD_PROJECT not set. Vertex AI may fail.")

            vertexai.init(project=self.project_id, location=self.location)
            self.model = GenerativeModel("gemini-pro")
            self._initialized = True
            logger.info(f"Vertex AI initialized for project {self.project_id}")
        except Exception as e:
            logger.error(f"Failed to initialize Vertex AI: {e}")
            raise

    async def extract_metadata(self, text: str) -> dict[str, Any]:
        """
        Extract legal metadata from text using Gemini Pro.

        Args:
            text: The text content of the document.

        Returns:
            Dictionary containing extracted metadata.
        """
        self._ensure_initialized()

        prompt = f"""
        You are an expert Indonesian Legal Analyst.
        Extract the following metadata from the provided legal document text.
        Return ONLY a JSON object. Do not include markdown formatting.

        Fields to extract:
        - type: The type of regulation (e.g., "UNDANG-UNDANG", "PERATURAN PEMERINTAH").
        - type_abbrev: Abbreviation (e.g., "UU", "PP", "PERPRES").
        - number: The regulation number (e.g., "12", "12 TAHUN 2024").
        - year: The year of enactment.
        - topic: A brief topic or title of the regulation.
        - status: The status if mentioned (e.g., "BERLAKU", "MENCABUT").
        - full_title: The full title of the document.

        Text:
        {text[:10000]}  # Limit context to first 10k chars to fit window/save costs
        """

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=GenerationConfig(
                    temperature=0.1, max_output_tokens=1024, response_mime_type="application/json"
                ),
            )

            result_text = response.text.strip()
            # Clean up potential markdown code blocks if the model ignores the instruction
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]

            return json.loads(result_text)

        except Exception as e:
            logger.error(f"Vertex AI extraction failed: {e}")
            return {}

    async def extract_structure(self, text: str) -> dict[str, Any]:
        """
        Extract document structure (BAB/Pasal) using Gemini Pro.
        Use this only if regex parsing fails completely.
        """
        # This is expensive and complex for full text.
        # For now, we rely on the pattern extractor for structure.
        # This is a placeholder for future implementation.
        pass
