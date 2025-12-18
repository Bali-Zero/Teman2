import asyncio
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO)

# Mock settings if needed or load from env
from app.core.config import settings

print(f"OpenAI Key present: {bool(settings.openai_api_key)}")
print(f"Google Key present: {bool(settings.google_api_key)}")


async def test_intent():
    try:
        print("Importing IntentClassifier...")
        from services.classification.intent_classifier import IntentClassifier

        print("Initializing IntentClassifier...")
        classifier = IntentClassifier()

        query = "Hello, I need a visa for Bali"
        print(f"Classifying intent for: '{query}'...")

        # Set timeout to detect hang
        intent = await asyncio.wait_for(classifier.classify_intent(query), timeout=10)
        print(f"✅ Intent Classified: {intent}")

    except asyncio.TimeoutError:
        print("❌ IntentClassifier TIMED OUT (Hung)")
    except Exception as e:
        print(f"❌ IntentClassifier Failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_intent())
