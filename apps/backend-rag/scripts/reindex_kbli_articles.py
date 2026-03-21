#!/usr/bin/env python3
"""
Re-indexing massivo di tutti gli articoli KBLI.
Invia a IndexNow per Bing/Yandex indexing immediato.
"""

import asyncio
from pathlib import Path

import httpx

# Config
BASE_URL = "https://balizero.com"
INDEXNOW_KEY = "2633309a0003ec408c59ec48c952604f"
INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"
ARTICLES_DIR = (
    Path(__file__).parent.parent.parent.parent / "apps/mouth/src/content/articles/business"
)


def get_kbli_articles() -> list[str]:
    """Recupera tutti gli slug degli articoli KBLI."""
    articles = []

    if not ARTICLES_DIR.exists():
        print(f"❌ Directory non trovata: {ARTICLES_DIR}")
        return articles

    for file in ARTICLES_DIR.glob("*kbli*.mdx"):
        slug = file.stem  # nome file senza estensione
        url = f"{BASE_URL}/business/{slug}"
        articles.append(url)

    return sorted(articles)


async def submit_to_indexnow(urls: list[str]) -> dict:
    """Invia URL a IndexNow API."""

    payload = {
        "host": "balizero.com",
        "key": INDEXNOW_KEY,
        "keyLocation": f"{BASE_URL}/{INDEXNOW_KEY}.txt",
        "urlList": urls,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            INDEXNOW_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        return {
            "status_code": response.status_code,
            "response": response.text,
        }


async def main():
    print("🔍 Recupero articoli KBLI...")

    articles = get_kbli_articles()
    total = len(articles)

    if total == 0:
        print("❌ Nessun articolo KBLI trovato!")
        return

    print(f"✅ Trovati {total} articoli KBLI")
    print()

    # IndexNow supporta max 10,000 URL per chiamata
    # Se abbiamo più di 10k articoli, splittiamo in batch
    BATCH_SIZE = 10000

    for i in range(0, len(articles), BATCH_SIZE):
        batch = articles[i : i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        total_batches = (len(articles) + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"📤 Invio batch {batch_num}/{total_batches} ({len(batch)} URL)...")

        try:
            result = await submit_to_indexnow(batch)

            if result["status_code"] == 200:
                print(f"   ✅ IndexNow: 200 OK - {len(batch)} URL accettati")
            elif result["status_code"] == 202:
                print(f"   ⏳ IndexNow: 202 Accepted - {len(batch)} URL in coda")
            else:
                print(f"   ⚠️ IndexNow: {result['status_code']} - {result['response'][:200]}")

        except Exception as e:
            print(f"   ❌ Errore: {e}")

        # Rate limiting: max 1 richiesta per 10 secondi per IndexNow
        if batch_num < total_batches:
            print("   ⏱️  Attesa 10s per rate limiting...")
            await asyncio.sleep(10)

    print()
    print("=" * 60)
    print(f"🎉 COMPLETATO! {total} articoli KBLI inviati a IndexNow")
    print()
    print("I motori di ricerca (Bing, Yandex, Naver, Seznam)")
    print("processeranno gli URL entro poche ore.")
    print()
    print("Prime 5 URL inviate:")
    for url in articles[:5]:
        print(f"  - {url}")
    if len(articles) > 5:
        print(f"  ... e altri {len(articles) - 5}")


if __name__ == "__main__":
    asyncio.run(main())
