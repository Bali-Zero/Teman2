import logging
import os

import google.generativeai as genai

logger = logging.getLogger(__name__)


def _get_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY before running this script.")
    return key


def test_key() -> None:
    key = _get_api_key()
    logger.info("Testing key with legacy SDK: %s...", key[:10])
    genai.configure(api_key=key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    try:
        response = model.generate_content("Hello, respond with 'OK' if you can hear me.")
        logger.info("Response: %s", response.text)
    except Exception as exc:
        logger.exception("Legacy Gemini key test failed: %s", exc)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_key()
