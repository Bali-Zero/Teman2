#!/usr/bin/env python3
"""
News Pre-Scorer using Ollama (local LLM)
Zero cost, no rate limits, preserves Claude Max for Claude Code
"""

import httpx
import json
import asyncio
from typing import Tuple
from loguru import logger


class OllamaScorer:
    """Score news articles using local Ollama LLM"""

    def __init__(
        self, model: str = "llama3.2:3b", base_url: str = "http://localhost:11434"
    ):
        self.model = model
        self.base_url = base_url
        self.api_url = f"{base_url}/api/generate"

    async def score_article(self, title: str, summary: str) -> Tuple[int, str]:
        """
        Score article relevance for Bali expats.
        Returns (score 0-100, reason).
        """
        prompt = f"""You are the Senior Intelligence Officer at Bali Zero. 
Score this news for Bali expat/investor relevance (0-100). Reply ONLY with valid JSON.

TITLE: {title}
SUMMARY: {summary[:300] if summary else "No summary"}

Criteria (Bali Zero Intelligence):
- 80-100: CRITICAL (Visas, Tax laws, Business regulations, Property law changes, major infrastructure)
- 50-79: STRATEGIC (Tourism policy, significant market shifts, lifestyle changes for high-net-worth expats)
- 20-49: INFORMATIONAL (General Indonesia news, regional developments)
- 0-19: NOISE (Gossip, sports, unrelated regions)

Reply with ONLY this JSON format:
{{"score": <number>, "reason": "<5 words max focusing on business/expat impact>"}}"""

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.api_url,
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.1,  # Low temp for consistent scoring
                            "num_predict": 50,  # Short response
                        },
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    result_text = data.get("response", "").strip()

                    # Extract JSON from response
                    if "{" in result_text and "}" in result_text:
                        json_start = result_text.find("{")
                        json_end = result_text.rfind("}") + 1
                        json_str = result_text[json_start:json_end]

                        result = json.loads(json_str)
                        score = int(result.get("score", 50))
                        reason = result.get("reason", "scored")[:50]

                        return score, reason

        except httpx.TimeoutException:
            logger.warning(f"Ollama timeout for: {title[:50]}")
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}")
        except Exception as e:
            logger.error(f"Ollama error: {e}")

        return 50, "scoring failed"  # Default to medium if fails

    async def health_check(self) -> bool:
        """Check if Ollama is running and model is available"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    model_names = [m.get("name", "") for m in models]
                    return any(self.model in name for name in model_names)
        except Exception:
            pass
        return False

    async def warm_up(self) -> bool:
        """Warm up the model (first call loads it into memory)"""
        logger.info(f"Warming up Ollama model: {self.model}")
        score, reason = await self.score_article(
            "Test article", "This is a test to warm up the model"
        )
        logger.info(f"Warm-up complete. Test score: {score}")
        return score > 0


async def test_scorer():
    """Test the Ollama scorer"""
    scorer = OllamaScorer()

    # Health check
    if not await scorer.health_check():
        print("Ollama not running or model not found!")
        print("Run: ollama pull llama3.2:3b")
        return

    print("Ollama is ready!")

    # Warm up (first call loads model)
    print("\nWarming up model...")
    await scorer.warm_up()

    # Test articles
    test_articles = [
        {
            "title": "Indonesia Extends Digital Nomad Visa to 5 Years",
            "summary": "The Indonesian government announced a new policy extending the digital nomad visa validity from 1 year to 5 years. The visa will cost $500.",
        },
        {
            "title": "Bali Property Prices Rise 15% in 2025",
            "summary": "Real estate prices in Bali have increased significantly, especially in Canggu and Ubud areas popular with expats.",
        },
        {
            "title": "Taylor Swift Announces World Tour",
            "summary": "Pop star Taylor Swift has announced her new world tour dates for 2026, including stops in Asia.",
        },
        {
            "title": "New Tax Rules for Foreign Workers in Indonesia",
            "summary": "The Indonesian tax authority has issued new guidelines for foreign workers regarding income tax obligations and reporting requirements.",
        },
    ]

    print("\nScoring test articles:\n")

    for article in test_articles:
        score, reason = await scorer.score_article(article["title"], article["summary"])

        emoji = "✅" if score >= 50 else "❌"
        print(f"{emoji} [{score:3d}] {article['title'][:50]}...")
        print(f"   Reason: {reason}\n")


if __name__ == "__main__":
    asyncio.run(test_scorer())
