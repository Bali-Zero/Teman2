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


async def test_key() -> None:
    key = _get_api_key()
    logger.info("Testing new key: %s...", key[:10])
    client = genai.Client(api_key=key)
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-001", contents="Hello, respond with 'OK' if you can hear me."
        )
        logger.info("Response: %s", response.text)
    except Exception as exc:
        logger.exception("Gemini key new test failed: %s", exc)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_key())
