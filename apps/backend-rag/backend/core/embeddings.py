"""
ZANTARA RAG - Embeddings Generation
Supports both OpenAI and Sentence Transformers
"""

import logging

logger = logging.getLogger(__name__)

# Import settings - try both absolute paths
try:
    from app.core.config import settings as _default_settings
except ImportError:
    try:
        import sys
        from pathlib import Path

        # Add parent dir to path for imports
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from app.core.config import settings as _default_settings
    except ImportError:
        # Fallback if config not available
        _default_settings = None


class EmbeddingsGenerator:
    """
    Generate embeddings using configured provider (OpenAI or Sentence Transformers).
    Automatically chooses provider based on settings.

    Note: This class no longer uses singleton pattern. Each instance is independent.
    For dependency injection, use create_embeddings_generator() factory function.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        provider: str | None = None,
        settings: object | None = None,
    ):
        """
        Initialize embeddings generator.
        Automatically chooses provider based on settings.

        Args:
            api_key: OpenAI API key (only needed if using OpenAI provider)
            model: Embedding model name (default from settings)
            provider: "openai" or "sentence-transformers" (default from settings)
            settings: Optional settings object (for testing). If None, uses module-level settings.
        """
        self._settings = settings if settings is not None else _default_settings

        # Determine provider from settings or parameter
        if provider:
            self.provider = provider
        elif self._settings:
            self.provider = getattr(self._settings, "embedding_provider", "sentence-transformers")
        else:
            # Default to sentence-transformers for local deployment
            self.provider = "sentence-transformers"

        # Load appropriate provider
        if self.provider == "openai":
            self._init_openai(api_key, model)
        else:
            # Default to sentence-transformers (local, no API key needed)
            self._init_sentence_transformers(model)

    def _init_openai(self, api_key: str | None = None, model: str | None = None):
        """Initialize OpenAI embeddings provider"""
        from openai import OpenAI

        self.provider = "openai"  # Ensure provider is set to openai
        self.model = (
            model
            or (getattr(self._settings, "embedding_model", None) if self._settings else None)
            or "text-embedding-3-small"
        )
        self.dimensions = 1536  # OpenAI text-embedding-3-small is always 1536
        self.api_key = api_key or (
            getattr(self._settings, "openai_api_key", None) if self._settings else None
        )

        if not self.api_key:
            if (
                self._settings
                and getattr(self._settings, "environment", "development") == "production"
            ):
                logger.critical("❌ CRITICAL: No OpenAI API key found in PRODUCTION environment")
                raise ValueError("OpenAI API key is required for OpenAI provider in production")

            raise ValueError("OpenAI API key is required for OpenAI provider")

        self.client = OpenAI(api_key=self.api_key)
        logger.info(
            f"🔌 [EmbeddingsGenerator] Initialized with OpenAI: {self.model} ({self.dimensions} dims)"
        )

    def _init_sentence_transformers(self, model: str | None = None):
        """Initialize Sentence Transformers local embeddings provider"""
        self.model = (
            model
            or (getattr(self._settings, "embedding_model", None) if self._settings else None)
            or "sentence-transformers/all-MiniLM-L6-v2"
        )

        logger.info(
            f"🔌 [EmbeddingsGenerator] Attempting to load Sentence Transformers: {self.model}"
        )

        try:
            from sentence_transformers import SentenceTransformer

            logger.info("   This may take a moment on first run (downloads model)...")
            self.transformer = SentenceTransformer(self.model)
            self.dimensions = self.transformer.get_sentence_embedding_dimension()
            logger.info(
                f"🔌 [EmbeddingsGenerator] Initialized with Sentence Transformers: {self.model} ({self.dimensions} dims)"
            )

        except ImportError:
            # Sentence transformers not available (size constraint on Fly.io)
            # Fallback to OpenAI
            logger.warning(
                "🔌 [EmbeddingsGenerator] Sentence Transformers not available (size constraint)"
            )
            logger.warning("   Falling back to OpenAI (text-embedding-3-small)")
            logger.warning(
                "   ⚠️ NOTE: This may cause dimension mismatch if Qdrant collections expect 384 dims"
            )
            self._init_openai(model=None)

        except Exception as e:
            logger.error(f"🔌 [EmbeddingsGenerator] Failed to load Sentence Transformers: {e}")
            logger.error("   Falling back to OpenAI...")
            try:
                self._init_openai(model=None)
            except Exception as openai_error:
                logger.error(f"🔌 [EmbeddingsGenerator] Both providers failed: {openai_error}")
                raise

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors (each vector is a list of floats)

        Raises:
            Exception: If API call fails
        """
        if not texts:
            logger.warning("Empty text list provided for embedding")
            return []

        try:
            if self.provider == "openai":
                return self._generate_embeddings_openai(texts)
            else:
                return self._generate_embeddings_sentence_transformers(texts)

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise

    def _generate_embeddings_openai(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings using OpenAI API.
        Automatically batches large requests (OpenAI max batch size: 2048).
        """
        logger.info(f"Generating embeddings for {len(texts)} texts using OpenAI")

        MAX_BATCH_SIZE = 2048  # OpenAI API limit
        all_embeddings = []

        # Process in batches if needed
        for i in range(0, len(texts), MAX_BATCH_SIZE):
            batch = texts[i : i + MAX_BATCH_SIZE]
            logger.debug(f"Processing batch {i // MAX_BATCH_SIZE + 1}: {len(batch)} texts")

            # Call OpenAI API
            # Note: dimensions parameter removed - text-embedding-3-small defaults to 1536 dims
            # which matches our Qdrant collections configuration
            response = self.client.embeddings.create(model=self.model, input=batch)

            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

        logger.info(
            f"✅ Generated {len(all_embeddings)} embeddings (OpenAI, {len(all_embeddings[0]) if all_embeddings else 0} dims)"
        )
        return all_embeddings

    def _generate_embeddings_sentence_transformers(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using Sentence Transformers"""
        logger.info(f"Generating embeddings for {len(texts)} texts using Sentence Transformers")

        try:
            embeddings = self.transformer.encode(
                texts, convert_to_numpy=True, show_progress_bar=len(texts) > 10
            )

            # Convert numpy array to list of lists
            embeddings_list = embeddings.tolist()
            logger.info(f"✅ Generated {len(embeddings_list)} embeddings (Sentence Transformers)")
            return embeddings_list

        except Exception as e:
            logger.error(f"Sentence Transformers error: {e}")
            raise

    def generate_single_embedding(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text string to embed

        Returns:
            Embedding vector as list of floats
        """
        embeddings = self.generate_embeddings([text])
        return embeddings[0] if embeddings else []

    def generate_query_embedding(self, query: str) -> list[float]:
        """
        Generate embedding optimized for query/search.

        Args:
            query: Search query text

        Returns:
            Query embedding vector
        """
        # For text-embedding-3-small, same process as document embedding
        return self.generate_single_embedding(query)

    def generate_batch_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a batch of texts.

        Alias for generate_embeddings() for backward compatibility.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors (each vector is a list of floats)
        """
        return self.generate_embeddings(texts)

    def get_model_info(self) -> dict:
        """
        Get information about the embedding model.

        Returns:
            Dictionary with model configuration
        """
        cost_info = "Paid (OpenAI API)" if self.provider == "openai" else "FREE (Local)"
        return {
            "model": self.model,
            "dimensions": self.dimensions,
            "provider": self.provider,
            "cost": cost_info,
        }


# Factory function for dependency injection
def create_embeddings_generator(
    api_key: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    settings: object | None = None,
) -> EmbeddingsGenerator:
    """
    Factory function to create EmbeddingsGenerator instance.
    Use this for dependency injection instead of direct instantiation.

    Args:
        api_key: OpenAI API key (only needed if using OpenAI provider)
        model: Embedding model name (default from settings)
        provider: "openai" or "sentence-transformers" (default from settings)
        settings: Optional settings object (for testing)

    Returns:
        EmbeddingsGenerator instance
    """
    return EmbeddingsGenerator(api_key=api_key, model=model, provider=provider, settings=settings)


# Convenience function
def generate_embeddings(texts: list[str], api_key: str | None = None) -> list[list[float]]:
    """
    Quick function to generate embeddings without instantiating class.

    Args:
        texts: List of texts to embed
        api_key: Optional OpenAI API key

    Returns:
        List of embedding vectors
    """
    generator = EmbeddingsGenerator(api_key=api_key)
    return generator.generate_embeddings(texts)
