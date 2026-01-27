#!/usr/bin/env python3
"""
Trova articoli completi pubblicati con cover image
e mostra dove sono stati collocati
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Optional
import requests

# Configurazione
INTEL_DIR = Path("apps/bali-intel-scraper")
PENDING_DIR = INTEL_DIR / "data" / "pending_articles"
IMAGES_DIR = INTEL_DIR / "data" / "images"
PREVIEWS_DIR = INTEL_DIR / "data" / "previews"
API_URL = os.getenv("API_URL", "https://nuzantara-rag.fly.dev")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")


def find_complete_articles() -> List[Dict]:
    """Trova articoli completi con cover image"""
    articles = []

    if not PENDING_DIR.exists():
        print(f"❌ Directory non trovata: {PENDING_DIR}")
        return articles

    for article_file in PENDING_DIR.glob("*.json"):
        try:
            with open(article_file) as f:
                data = json.load(f)

            article_id = article_file.stem
            cover_image = data.get("cover_image") or data.get("image_url") or ""
            title = data.get("title") or data.get("headline", "Unknown")
            category = data.get("category", "unknown")

            # Verifica che abbia cover image
            if cover_image and cover_image != "None":
                # Verifica che l'immagine esista
                image_path = (
                    INTEL_DIR / cover_image
                    if not Path(cover_image).is_absolute()
                    else Path(cover_image)
                )
                has_image = image_path.exists()

                # Verifica preview
                preview_path = PREVIEWS_DIR / f"{article_id}.html"
                has_preview = preview_path.exists()

                articles.append(
                    {
                        "id": article_id,
                        "title": title,
                        "category": category,
                        "cover_image": str(cover_image),
                        "has_image": has_image,
                        "has_preview": has_preview,
                        "article_file": str(article_file),
                        "preview_file": str(preview_path) if has_preview else None,
                        "data": data,
                    }
                )
        except Exception as e:
            print(f"⚠️  Errore leggendo {article_file}: {e}")

    return articles


def check_github_published(article_id: str) -> Optional[Dict]:
    """Verifica se l'articolo è stato pubblicato su GitHub"""
    # Questo è un esempio - adatta alla tua API
    if not ADMIN_API_KEY:
        return None

    try:
        # Chiama API per verificare pubblicazione
        # Adatta questo endpoint alla tua API
        response = requests.get(
            f"{API_URL}/api/articles/publish/status",
            headers={"X-API-Key": ADMIN_API_KEY},
            timeout=5,
        )

        if response.status_code == 200:
            # Cerca l'articolo nella risposta
            # Adatta questo alla struttura della tua API
            return {"published": True, "api_response": response.json()}
    except Exception as e:
        print(f"⚠️  Errore verificando pubblicazione: {e}")

    return None


def main():
    print("🔍 Ricerca Articoli Completi con Cover Image")
    print("=" * 70)
    print()

    # Trova articoli completi
    articles = find_complete_articles()

    if not articles:
        print("❌ Nessun articolo completo trovato")
        return

    print(f"✅ Trovati {len(articles)} articoli completi con cover image")
    print()

    # Mostra dettagli
    for i, article in enumerate(articles, 1):
        print(f"{i}. 📰 {article['title']}")
        print(f"   ID: {article['id']}")
        print(f"   Categoria: {article['category']}")
        print(f"   📷 Cover Image: {article['cover_image']}")
        print(f"      Esiste: {'✅' if article['has_image'] else '❌'}")
        print(f"   📄 Preview HTML: {'✅' if article['has_preview'] else '❌'}")
        if article["has_preview"]:
            print(f"      Path: {article['preview_file']}")

        # Verifica pubblicazione GitHub
        github_status = check_github_published(article["id"])
        if github_status:
            print("   🚀 Pubblicato su GitHub: ✅")
            if "api_response" in github_status:
                print(f"      Dettagli: {github_status['api_response']}")
        else:
            print("   🚀 Pubblicato su GitHub: ❓ (verifica manuale)")

        print()

    # Riepilogo
    print("=" * 70)
    print("📊 Riepilogo:")
    print(f"   Articoli completi: {len(articles)}")
    print(f"   Con cover image: {sum(1 for a in articles if a['has_image'])}")
    print(f"   Con preview HTML: {sum(1 for a in articles if a['has_preview'])}")
    print()
    print("📁 Directory:")
    print(f"   Articoli: {PENDING_DIR}")
    print(f"   Immagini: {IMAGES_DIR}")
    print(f"   Preview: {PREVIEWS_DIR}")
    print()
    print("🔗 Per pubblicare:")
    print(f"   API: {API_URL}/api/articles/publish")
    print(f"   Usa: ADMIN_API_KEY={ADMIN_API_KEY}")


if __name__ == "__main__":
    main()
