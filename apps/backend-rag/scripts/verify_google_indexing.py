#!/usr/bin/env python3
"""
Verifica configurazione Google Indexing API e riprova re-indexing.
"""

import asyncio
import json
import os
from pathlib import Path

import httpx

BASE_URL = "https://balizero.com"
GOOGLE_INDEXING_ENDPOINT = "https://indexing.googleapis.com/v3/urlNotifications:publish"
ARTICLES_DIR = (
    Path(__file__).parent.parent.parent.parent / "apps/mouth/src/content/articles/business"
)


def get_kbli_articles() -> list[str]:
    """Recupera tutti gli slug degli articoli KBLI."""
    articles = []
    if not ARTICLES_DIR.exists():
        return articles
    for file in ARTICLES_DIR.glob("*kbli*.mdx"):
        slug = file.stem
        url = f"{BASE_URL}/business/{slug}"
        articles.append(url)
    return sorted(articles)


def get_google_token():
    """Ottiene token OAuth2 da service account."""
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    creds_json = os.getenv("GOOGLE_INDEXING_CREDENTIALS")
    if not creds_json:
        raise ValueError("GOOGLE_INDEXING_CREDENTIALS non impostato!")

    credentials = service_account.Credentials.from_service_account_info(
        json.loads(creds_json),
        scopes=["https://www.googleapis.com/auth/indexing"],
    )
    credentials.refresh(Request())
    return credentials.token, credentials.service_account_email


async def submit_to_google(url: str, token: str) -> dict:
    """Invia singola URL a Google Indexing API."""
    payload = {
        "url": url,
        "type": "URL_UPDATED",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            GOOGLE_INDEXING_ENDPOINT,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        return {
            "status_code": response.status_code,
            "url": url,
            "response": response.text,
        }


async def main():
    print("🔍 Recupero articoli KBLI...")
    articles = get_kbli_articles()
    print(f"✅ Trovati {len(articles)} articoli KBLI\n")

    print("🔑 Autenticazione Google...")
    try:
        token, service_email = get_google_token()
        print("   ✅ Token ottenuto")
        print(f"   📧 Service Account: {service_email}")
    except Exception as e:
        print(f"   ❌ Errore: {e}")
        return

    print()
    print("📤 Invio URL a Google Indexing API...")
    print("   (Rate limit: ~200/giorno, attendi tra le chiamate)")
    print()

    success = 0
    failed = 0
    errors = []

    for i, url in enumerate(articles, 1):
        try:
            result = await submit_to_google(url, token)

            if result["status_code"] == 200:
                print(f"   ✅ [{i}/{len(articles)}] {url}")
                success += 1
            elif result["status_code"] == 403:
                print(f"   ⚠️  [{i}/{len(articles)}] 403 - Permesso negato")
                print(f"      Risposta: {result['response'][:200]}")
                errors.append(f"{url}: 403 Forbidden - Verifica Search Console")
                failed += 1
            else:
                print(f"   ⚠️  [{i}/{len(articles)}] {result['status_code']} - {url}")
                errors.append(f"{url}: {result['status_code']}")
                failed += 1

        except Exception as e:
            print(f"   ❌ [{i}/{len(articles)}] Errore: {e}")
            errors.append(f"{url}: {e}")
            failed += 1

        if i < len(articles):
            await asyncio.sleep(2)

    print()
    print("=" * 60)
    print("🎉 RISULTATO:")
    print(f"   ✅ Successo: {success}")
    print(f"   ❌ Falliti: {failed}")

    if errors:
        print()
        print("📝 Errori dettagliati:")
        for err in errors[:5]:
            print(f"   - {err}")

    print()
    print("💡 Se vedi errori 403:")
    print("   1. Vai su https://search.google.com/search-console")
    print("   2. Seleziona proprietà balizero.com")
    print("   3. Settings → Users and Permissions")
    print(f"   4. Aggiungi: {service_email}")
    print("   5. Ruolo: Owner")


if __name__ == "__main__":
    asyncio.run(main())
