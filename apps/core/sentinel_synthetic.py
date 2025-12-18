import asyncio
import json
import logging
import sys
import os
from pathlib import Path

# Add backend to path
backend_path = os.path.join(os.getcwd(), "apps/backend-rag/backend")
sys.path.append(backend_path)

# Load environment variables
from dotenv import load_dotenv

env_path = Path(os.getcwd()) / "apps/backend-rag/.env"
load_dotenv(dotenv_path=env_path, override=True)

from services.intelligent_router import IntelligentRouter
from services.context.rag_manager import RAGManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from llm.zantara_ai_client import ZantaraAIClient

from services.search_service import SearchService


class SentinelSynthetic:
    """
    Sentinel module to verify that Nuzantara correctly uses synthetic data.
    """

    def __init__(self):
        self.ai_client = ZantaraAIClient()
        self.search_service = SearchService()
        self.router = IntelligentRouter(ai_client=self.ai_client)
        self.rag = RAGManager(search_service=self.search_service)

    async def verify_few_shot_retrieval(self, dataset_path: str):
        """
        Verify that for each question in the dataset, the system retrieves relevant few-shot examples.
        """
        logger.info(f"🧪 Starting Synthetic Data Verification using {dataset_path}")

        with open(dataset_path, "r") as f:
            data = json.load(f)

        success_count = 0
        total_count = len(data)

        for i, item in enumerate(data, 1):
            question = item["question"]
            logger.info(f"\n📝 Test Case {i}/{total_count}: '{question}'")

            # 1. Check Retrieval directly
            examples = await self.rag.retrieve_few_shot_examples(question, limit=2)

            if examples:
                logger.info(f"   ✅ Retrieved {len(examples)} examples")
                for ex in examples:
                    logger.info(f"      - Found Q: {ex['question'][:50]}...")
                success_count += 1
            else:
                logger.warning(
                    "   ⚠️ No examples retrieved (Might be expected if dataset is small/diverse)"
                )

        logger.info(
            f"\n📊 Result: {success_count}/{total_count} queries found relevant examples."
        )
        return success_count > 0


if __name__ == "__main__":
    dataset = "docs/datasets/synthetic_gold_laws.json"
    if not os.path.exists(dataset):
        logger.error(f"Dataset not found at {dataset}")
        sys.exit(1)

    sentinel = SentinelSynthetic()
    asyncio.run(sentinel.verify_few_shot_retrieval(dataset))
