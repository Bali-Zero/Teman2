import asyncio
import logging
import os

from google import genai

logger = logging.getLogger(__name__)


def _get_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY before running this script.")
    return key


async def list_models() -> None:
    client = genai.Client(api_key=_get_api_key())
    try:
        logger.info("Available models:")
        for model in client.models.list():
            logger.info("- %s", model.name)
    except Exception as exc:
        logger.exception("Failed to list Gemini models: %s", exc)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(list_models())
