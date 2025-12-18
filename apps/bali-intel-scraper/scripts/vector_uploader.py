"""
BALI INTEL SCRAPER - Stage 3: Vector DB Upload
Uploads generated articles directly to NUZANTARA's Qdrant vector database for semantic search
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import uuid
from loguru import logger
import yaml

# Import from backend-rag
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend-rag" / "backend"))

try:
    from core.qdrant_db import QdrantClient
    from core.embeddings import EmbeddingsGenerator
except ImportError as e:
    logger.error(f"Failed to import from backend-rag: {e}")
    logger.error("Make sure backend-rag is in the parent directory")
    raise


class VectorDBUploader:
    """
    Uploads generated articles directly to Qdrant vector database.

    Integrates with NUZANTARA RAG backend for:
    - Semantic search via vector similarity
    - Context enrichment
    - Knowledge base queries
    - Real-time RAG retrieval
    """

    def __init__(self):
        # Qdrant connection
        self.qdrant_url = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
        self.qdrant_api_key = os.getenv("QDRANT_API_KEY")

        # OpenAI API key for embeddings
        self.openai_api_key = os.getenv("OPENAI_API_KEY")

        if not self.openai_api_key:
            logger.warning("OPENAI_API_KEY not set. Embeddings generation may fail.")

        # Initialize embeddings generator (OpenAI text-embedding-3-small, 1536 dims)
        self.embeddings = EmbeddingsGenerator(
            api_key=self.openai_api_key,
            model="text-embedding-3-small",
            provider="openai",
        )

        logger.info(f"Embeddings: {self.embeddings.get_model_info()}")

        # Category to collection mapping
        self.collection_map = {
            "immigration": "bali_intel_immigration",
            "tax_bkpm": "bali_intel_bkpm_tax",
            "property": "bali_intel_realestate",
            "business": "bali_intel_business",
            "legal": "bali_intel_legal",
            "events": "bali_intel_events",
            "cost_living": "bali_intel_social",
            "healthcare": "bali_intel_healthcare",
            "education": "bali_intel_education",
            "transportation": "bali_intel_transportation",
            "bali_news": "bali_intel_bali_news",
            "competitors": "bali_intel_competitors",
        }

        logger.info(f"Vector uploader initialized (Qdrant: {self.qdrant_url})")

    async def upload_article(
        self,
        article_path: Path,
        category: str,
    ) -> Dict:
        """
        Upload a single article to Qdrant vector database.

        Generates embeddings and stores in Qdrant for semantic search.

        Args:
            article_path: Path to markdown article file
            category: Category key (immigration, tax_bkpm, etc.)

        Returns:
            Dict with upload results
        """
        try:
            # Read article
            with open(article_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Parse frontmatter
            metadata = self._parse_frontmatter(content)

            # Extract title and body
            title, body = self._extract_content(content)

            # Get collection name
            collection = self.collection_map.get(category, "bali_intel_roundup")

            # Create document ID (UUID as required by Qdrant)
            doc_id = str(uuid.uuid4())

            # Generate embedding for the full content (title + body)
            full_text = f"{title}\n\n{body}"
            logger.debug(f"Generating embedding for: {title[:50]}...")

            embedding = self.embeddings.generate_single_embedding(full_text)

            # Prepare metadata for Qdrant (ensure all values are JSON serializable)
            doc_metadata = {
                "title": title,
                "category": category,
                "generated_at": str(metadata.get("generated_at", "")),
                "source_file": str(metadata.get("source_file", "")),
                "ai_model": str(metadata.get("ai_model", "")),
                "file_path": str(article_path),
                "tier": self._extract_tier(metadata),
                "uploaded_at": datetime.utcnow().isoformat(),
            }

            # Upload to Qdrant
            result = await self._upload_to_qdrant(
                doc_id=doc_id,
                text=full_text,
                embedding=embedding,
                metadata=doc_metadata,
                collection=collection,
            )

            if result["success"]:
                logger.success(f"✓ Uploaded to Qdrant: {title[:60]}...")
                return {
                    "success": True,
                    "document_id": doc_id,
                    "collection": collection,
                }
            else:
                raise Exception(result.get("error", "Unknown error"))

        except Exception as e:
            logger.error(f"✗ Failed to upload {article_path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "file": str(article_path),
            }

    async def upload_category(
        self,
        category: str,
        max_articles: Optional[int] = None,
    ) -> Dict:
        """
        Upload all articles in a category.

        Args:
            category: Category key
            max_articles: Maximum articles to upload (None = all)

        Returns:
            Dict with upload statistics
        """
        logger.info(f"Uploading category: {category}")

        articles_dir = Path("data/articles") / category

        if not articles_dir.exists():
            logger.warning(f"No articles directory for {category}")
            return {
                "category": category,
                "uploaded": 0,
                "failed": 0,
                "errors": [],
            }

        # Get all markdown files
        article_files = list(articles_dir.glob("*.md"))

        if max_articles:
            article_files = article_files[:max_articles]

        logger.info(f"Found {len(article_files)} articles")

        uploaded = 0
        failed = 0
        errors = []

        for article_path in article_files:
            result = await self.upload_article(article_path, category)

            if result["success"]:
                uploaded += 1
            else:
                failed += 1
                errors.append(result.get("error"))

        logger.info(f"Uploaded {uploaded}/{len(article_files)} articles")

        return {
            "category": category,
            "total": len(article_files),
            "uploaded": uploaded,
            "failed": failed,
            "errors": errors,
        }

    async def upload_all_categories(
        self,
        categories: Optional[List[str]] = None,
        max_per_category: Optional[int] = None,
    ) -> Dict:
        """
        Upload articles from all categories.

        Args:
            categories: List of category keys (None = all)
            max_per_category: Max articles per category

        Returns:
            Dict with overall statistics
        """
        logger.info("=" * 70)
        logger.info("📤 STAGE 3: VECTOR DB UPLOAD")
        logger.info("=" * 70)

        # Determine categories to process
        if categories:
            cat_list = categories
        else:
            # Get all categories from articles directory
            articles_dir = Path("data/articles")
            cat_list = [d.name for d in articles_dir.iterdir() if d.is_dir()]

        logger.info(f"Categories to upload: {', '.join(cat_list)}")

        total_uploaded = 0
        total_failed = 0
        results_by_category = {}

        for category in cat_list:
            result = await self.upload_category(category, max_per_category)
            results_by_category[category] = result

            total_uploaded += result["uploaded"]
            total_failed += result["failed"]

        logger.success(
            f"✅ Upload complete: {total_uploaded} uploaded, {total_failed} failed"
        )

        return {
            "total_uploaded": total_uploaded,
            "total_failed": total_failed,
            "by_category": results_by_category,
        }

    def _parse_frontmatter(self, content: str) -> Dict:
        """Parse YAML frontmatter robustly using yaml.safe_load"""
        if not content.startswith("---"):
            return {}

        try:
            # Extract frontmatter
            parts = content.split("---", 2)
            if len(parts) < 3:
                return {}

            frontmatter_str = parts[1]

            # Parse YAML safely
            metadata = yaml.safe_load(frontmatter_str) or {}

            return metadata

        except yaml.YAMLError as e:
            logger.warning(f"YAML parsing error: {e}")
            return {}
        except Exception as e:
            logger.warning(f"Failed to parse frontmatter: {e}")
            return {}

    def _extract_content(self, content: str) -> tuple:
        """Extract title and body from markdown."""
        # Remove frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = parts[2]

        content = content.strip()

        # Extract title (first # heading)
        lines = content.split("\n")
        title = "Untitled"
        body_lines = []

        for line in lines:
            if line.startswith("# ") and title == "Untitled":
                title = line.replace("# ", "").strip()
            else:
                body_lines.append(line)

        body = "\n".join(body_lines).strip()

        return title, body

    def _extract_tier(self, metadata: Dict) -> str:
        """Extract source tier from metadata."""
        source_file = metadata.get("source_file", "")

        # Try to extract tier from source filename
        if "T1" in source_file:
            return "T1"
        elif "T2" in source_file:
            return "T2"
        elif "T3" in source_file:
            return "T3"

        return "unknown"

    async def _upload_to_qdrant(
        self,
        doc_id: str,
        text: str,
        embedding: List[float],
        metadata: Dict,
        collection: str,
    ) -> Dict:
        """
        Upload document directly to Qdrant vector database.

        Args:
            doc_id: Unique document ID
            text: Full text content
            embedding: Embedding vector (1536 dims for text-embedding-3-small)
            metadata: Document metadata
            collection: Qdrant collection name

        Returns:
            Dict with upload results
        """
        try:
            # Create Qdrant client
            async with QdrantClient(
                qdrant_url=self.qdrant_url,
                collection_name=collection,
                api_key=self.qdrant_api_key,
            ) as qdrant:
                # Ensure collection exists (create if needed)
                stats = await qdrant.get_collection_stats()
                if "error" in stats:
                    logger.info(f"Creating collection: {collection}")
                    await qdrant.create_collection(vector_size=1536, distance="Cosine")

                # Upsert document
                result = await qdrant.upsert_documents(
                    chunks=[text],
                    embeddings=[embedding],
                    metadatas=[metadata],
                    ids=[doc_id],
                )

                return result

        except Exception as e:
            logger.error(f"Qdrant upload error: {e}")
            return {"success": False, "error": str(e)}


# Standalone function for orchestrator
async def run_stage3_upload(
    categories: Optional[List[str]] = None,
    max_per_category: Optional[int] = None,
) -> Dict:
    """
    Run Stage 3: Vector DB Upload

    Args:
        categories: List of categories to upload (None = all)
        max_per_category: Max articles per category (None = all)

    Returns:
        Dict with upload statistics
    """
    uploader = VectorDBUploader()
    return await uploader.upload_all_categories(categories, max_per_category)


if __name__ == "__main__":
    import asyncio

    # Test upload
    asyncio.run(run_stage3_upload(max_per_category=5))
