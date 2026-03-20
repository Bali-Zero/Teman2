import json
import asyncio
import httpx
from loguru import logger
import os

BACKEND_URL = "https://nuzantara-rag.fly.dev"
API_KEY = os.environ.get("SCRAPER_API_KEY", "")
RUN_FILE = "../data/pipeline/run_20260313_010005.json"

async def main():
    if not API_KEY:
        logger.error("SCRAPER_API_KEY env var not set — aborting")
        return

    with open(RUN_FILE, "r") as f:
        data = json.load(f)

    articles = data.get("articles", [])
    enriched_articles = [a for a in articles if "enrichment" in a and a["enrichment"]]

    logger.info(f"Trovati {len(enriched_articles)} articoli arricchiti da pubblicare.")

    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        for idx, article in enumerate(enriched_articles):
            # First submit to staging
            enr = article.get("enrichment", {})
            content = enr.get("the_facts", "") + "\n\n" + enr.get("bali_zero_take", "")
            if not content.strip():
                content = enr.get("executive_brief", article.get("text", ""))[:8000]
                
            payload = {
                "title": enr.get("headline", article.get("title", "")),
                "content": content,
                "category": article.get("category", "news"),
                "source_name": article.get("source_name", "Unknown"),
                "source_url": article.get("source_url", article.get("url", "")),
                "relevance_score": article.get("quality_score", 50),
            }
            if idx < 3:
                payload["main_news_position"] = idx + 1
            
            logger.info(f"Publishing {idx+1}/{len(enriched_articles)}: {payload['title'][:50]}...")
            
            r = await client.post(f"{BACKEND_URL}/api/intel/scraper/submit", json=payload, headers=headers)
            if r.status_code in (200, 201):
                res_data = r.json()
                item_id = res_data.get("item_id")
                intel_type = res_data.get("intel_type", "news")
                
                if item_id:
                    # Then force publish
                    pub_r = await client.post(f"{BACKEND_URL}/api/intel/staging/publish/{intel_type}/{item_id}", json={}, headers=headers)
                    if pub_r.status_code in (200, 201):
                        logger.success(f"✅ Published to News Room: {item_id}")
                    else:
                        logger.error(f"❌ Failed to publish {item_id}: {pub_r.text}")
            else:
                logger.error(f"❌ Failed to submit: {r.text}")
            
            await asyncio.sleep(7) # Rate limit

if __name__ == "__main__":
    asyncio.run(main())