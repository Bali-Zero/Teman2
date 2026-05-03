#!/usr/bin/env python3
"""
Re-indexing massivo articoli KBLI su Google Indexing API.
Da eseguire DIRETTAMENTE sul server Fly.io via SSH.
"""

import asyncio
import json
import os

import httpx

# Lista completa articoli KBLI
ARTICLES = [
    "beginners-guide-kbli-2025",
    "kbli-2020-to-2025-migration-guide",
    "kbli-2025-agriculture-agritourism",
    "kbli-2025-bali-transformation",
    "kbli-2025-brand-positioning-strategy",
    "kbli-2025-capital-investment-requirements",
    "kbli-2025-construction-building",
    "kbli-2025-consulting-professional-services",
    "kbli-2025-creative-design-industry",
    "kbli-2025-education-training",
    "kbli-2025-environmental-permits-amdal",
    "kbli-2025-food-beverage-fnb",
    "kbli-2025-foreign-ownership-pma-guide",
    "kbli-2025-future-proofing-flexibility",
    "kbli-2025-gold-rush-migration",
    "kbli-2025-great-transition",
    "kbli-2025-green-economy-waste",
    "kbli-2025-halal-certification-fnb",
    "kbli-2025-healthcare-wellness",
    "kbli-2025-hospitality-accommodation",
    "kbli-2025-import-export-licenses",
    "kbli-2025-it-services-software",
    "kbli-2025-license-permit-requirements",
    "kbli-2025-location-restrictions-bali",
    "kbli-2025-manufacturing-production",
    "kbli-2025-multi-code-strategy",
    "kbli-2025-new-codes-spotlight",
    "kbli-2025-oss-transition-update",
    "kbli-2025-real-estate-property",
    "kbli-2025-red-flags-audit-risk",
    "kbli-2025-regulatory-convergence",
    "kbli-2025-retail-ecommerce",
    "kbli-2025-streaming-digital-media",
    "kbli-2025-tax-implications-klu",
    "kbli-2025-tourism-travel-services",
    "kbli-2025-visa-kitas-synergy",
    "kbli-klu-fiscal-control-2025",
    "oss-kbli-2025-fiktif-positif",
    "upgrading-indonesia-kbli-2025",
]


async def main():
    print("🔑 Autenticazione Google...")

    creds_json = os.getenv("GOOGLE_INDEXING_CREDENTIALS")
    if not creds_json:
        print("❌ GOOGLE_INDEXING_CREDENTIALS non trovato!")
        return

    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    creds_data = json.loads(creds_json)
    credentials = service_account.Credentials.from_service_account_info(
        creds_data,
        scopes=["https://www.googleapis.com/auth/indexing"],
    )
    credentials.refresh(Request())

    print("✅ Token ottenuto!")
    print(f"📧 Service Account: {creds_data.get('client_email')}")
    print()
    print(f"📤 Invio {len(ARTICLES)} URL a Google Indexing API...")
    print("   (Rate limit: ~200/giorno, attendi 2s tra chiamate)")
    print()

    success = 0
    failed = 0

    for i, slug in enumerate(ARTICLES, 1):
        url = f"https://balizero.com/business/{slug}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://indexing.googleapis.com/v3/urlNotifications:publish",
                    json={"url": url, "type": "URL_UPDATED"},
                    headers={
                        "Authorization": f"Bearer {credentials.token}",
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code == 200:
                    print(f"✅ [{i:2d}/{len(ARTICLES)}] {slug}")
                    success += 1
                else:
                    print(f"⚠️  [{i:2d}/{len(ARTICLES)}] HTTP {resp.status_code} - {slug}")
                    failed += 1
        except Exception as e:
            print(f"❌ [{i:2d}/{len(ARTICLES)}] Errore: {str(e)[:50]} - {slug}")
            failed += 1

        # Rate limiting
        if i < len(ARTICLES):
            await asyncio.sleep(2)

    print()
    print("=" * 60)
    print("🎉 RE-INDEXING GOOGLE COMPLETATO!")
    print(f"   ✅ Successo: {success}/{len(ARTICLES)}")
    print(f"   ❌ Falliti: {failed}/{len(ARTICLES)}")
    print()
    print("Google processerà gli URL entro 24-48 ore.")
    print("Monitora la Search Console per lo stato.")


if __name__ == "__main__":
    asyncio.run(main())
