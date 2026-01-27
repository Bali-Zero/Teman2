#!/usr/bin/env python3
"""
Pubblica articoli pending su GitHub tramite Article Composer API
"""

import json
import os
import sys
import base64
from pathlib import Path
import requests
from typing import Dict, Optional

API_URL = os.getenv("API_URL", "https://nuzantara-rag.fly.dev")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "69ff6340462fd10b")
INTEL_DIR = Path("apps/bali-intel-scraper")
PENDING_DIR = INTEL_DIR / "data" / "pending_articles"
IMAGES_DIR = INTEL_DIR / "data" / "images"


def load_article(article_file: Path) -> Optional[Dict]:
    """Carica articolo da file JSON"""
    try:
        with open(article_file) as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Errore leggendo {article_file}: {e}")
        return None


def load_cover_image(image_path: str) -> Optional[tuple]:
    """Carica cover image e restituisce (base64_data, filename)"""
    if not image_path or image_path == "None":
        return None

    # Prova path relativo e assoluto
    full_path = INTEL_DIR / image_path
    if not full_path.exists():
        full_path = Path(image_path)

    if not full_path.exists():
        print(f"⚠️  Immagine non trovata: {image_path}")
        return None

    try:
        with open(full_path, "rb") as f:
            image_data = f.read()
            base64_data = base64.b64encode(image_data).decode("utf-8")
            filename = full_path.name
            return (base64_data, filename)
    except Exception as e:
        print(f"❌ Errore leggendo immagine {full_path}: {e}")
        return None


def extract_section(content: str, section_name: str) -> str:
    """Estrae una sezione dal contenuto arricchito"""
    import re

    # Pattern per trovare sezione (case insensitive)
    patterns = [
        rf"\*\*{section_name}\*\*:\s*(.+?)(?=\n\n\*\*|\Z)",
        rf"{section_name}:\s*(.+?)(?=\n\n\*\*|\Z)",
        rf"## {section_name}\s*\n(.+?)(?=\n##|\Z)",
    ]

    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()

    return ""


def convert_to_enriched_article(article_data: Dict) -> Dict:
    """Converte articolo pending in formato EnrichedArticle per API"""
    # Estrai contenuto arricchito
    enriched_content = article_data.get("enriched_content", "")

    # Se non c'è enriched_content, usa il contenuto base
    if not enriched_content:
        enriched_content = article_data.get("content", "")

    # Estrai facts (prima parte del contenuto, prima delle sezioni speciali)
    facts = ""
    if enriched_content:
        # Trova dove iniziano le sezioni speciali
        special_sections = [
            "**What They Don't Tell You**",
            "**Our Analysis**",
            "**Our Advice**",
            "##",
        ]
        first_special = len(enriched_content)

        for section in special_sections:
            idx = enriched_content.find(section)
            if idx != -1 and idx < first_special:
                first_special = idx

        if first_special < len(enriched_content):
            facts = enriched_content[:first_special].strip()
        else:
            facts = enriched_content[:1000]

    # Estrai BaliZero Take dal contenuto
    bali_zero_take = {
        "hidden_insight": extract_section(enriched_content, "What They Don't Tell You")[
            :500
        ],
        "our_analysis": extract_section(enriched_content, "Our Analysis")[:1000],
        "our_advice": extract_section(enriched_content, "Our Advice")[:1000],
    }

    # Se non trovato, prova varianti
    if not bali_zero_take["hidden_insight"]:
        bali_zero_take["hidden_insight"] = extract_section(
            enriched_content, "Hidden Insight"
        )

    # Genera AI summary
    ai_summary = article_data.get("seo_metadata", {}).get("meta_description", "")
    if not ai_summary and facts:
        ai_summary = facts[:200]

    # Genera AI tags (usa keywords se disponibili)
    ai_tags = article_data.get("seo_metadata", {}).get("keywords", [])
    if not ai_tags:
        # Genera tags base dalla categoria
        category = article_data.get("category", "business")
        ai_tags = [category, "bali", "indonesia"]

    # Genera TLDR (se non presente, crea da summary)
    headline = article_data.get("title") or article_data.get("headline", "")
    tldr = {
        "should_worry": "No"
        if "not" in ai_summary.lower() or "no" in ai_summary.lower()[:50]
        else "Maybe",
        "what": ai_summary[:100] if ai_summary else facts[:100],
        "who": "Expats and investors in Indonesia",
        "when": "Now",
        "risk_level": "low"
        if article_data.get("relevance_score", 50) < 60
        else "medium",
    }

    # Crea struttura EnrichedArticle (tutti i campi richiesti)
    enriched = {
        "title": headline,
        "headline": headline,
        "tldr": tldr,
        "ai_summary": ai_summary[:500],
        "facts": facts[:2000],  # Limita a 2000 caratteri
        "bali_zero_take": bali_zero_take,
        "next_steps": {"expat": [], "investor": []},
        "category": article_data.get("category", "business"),
        "priority": "medium",
        "relevance_score": article_data.get("relevance_score", 50),
        "source": article_data.get("source", "Intel Scraper"),
        "source_url": article_data.get("source_url", ""),
        "enriched_at": article_data.get("created_at", ""),
        "ai_tags": ai_tags[:10],  # Limita a 10 tags
        "suggested_components": [],  # Componenti suggeriti (vuoto per ora)
    }

    return enriched


def publish_article(article_id: str, article_data: Dict) -> bool:
    """Pubblica articolo tramite Article Composer API"""
    print(f"\n📰 Pubblicazione: {article_data.get('title', article_id)[:60]}...")

    # Converti in formato EnrichedArticle
    enriched = convert_to_enriched_article(article_data)

    # Carica cover image
    cover_image_path = article_data.get("cover_image") or article_data.get(
        "image_url", ""
    )
    cover_image_data = None
    cover_image_filename = None

    if cover_image_path:
        image_result = load_cover_image(cover_image_path)
        if image_result:
            cover_image_data, cover_image_filename = image_result

    # Prepara payload
    payload = {
        "article": enriched,
        "slug": None,  # Auto-generato
        "position": None,  # Nessuna posizione specifica
        "cover_image_base64": cover_image_data,
        "cover_image_filename": cover_image_filename,
    }

    # Rimuovi None values
    payload = {k: v for k, v in payload.items() if v is not None}

    # Chiama API
    try:
        response = requests.post(
            f"{API_URL}/api/articles/publish",
            json=payload,
            headers={"X-API-Key": ADMIN_API_KEY, "Content-Type": "application/json"},
            timeout=30,
        )

        if response.status_code in [200, 201]:
            result = response.json()
            if result.get("success"):
                print("✅ Pubblicato con successo!")
                print(f"   URL: {result.get('article_url', 'N/A')}")
                print(f"   Commit: {result.get('commit_sha', 'N/A')[:7]}")
                return True
            else:
                print(f"❌ Errore: {result.get('error', 'Unknown error')}")
                return False
        else:
            print(f"❌ HTTP {response.status_code}: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"❌ Errore API: {e}")
        return False


def main():
    print("🚀 Pubblicazione Articoli Pending")
    print("=" * 70)
    print()

    if not PENDING_DIR.exists():
        print(f"❌ Directory non trovata: {PENDING_DIR}")
        sys.exit(1)

    # Trova tutti gli articoli pending
    article_files = list(PENDING_DIR.glob("*.json"))

    if not article_files:
        print("❌ Nessun articolo pending trovato")
        sys.exit(1)

    print(f"📋 Trovati {len(article_files)} articoli pending")
    print()

    # Chiedi conferma
    print("⚠️  Questi articoli verranno pubblicati su GitHub:")
    for article_file in article_files[:5]:
        article_data = load_article(article_file)
        if article_data:
            print(f"   - {article_data.get('title', 'Unknown')[:60]}")
    if len(article_files) > 5:
        print(f"   ... e altri {len(article_files) - 5} articoli")
    print()

    response = input("Continuare? (s/n): ").strip().lower()
    if response != "s":
        print("❌ Operazione annullata")
        sys.exit(0)

    # Pubblica articoli
    published = 0
    failed = 0

    for article_file in article_files:
        article_data = load_article(article_file)
        if not article_data:
            failed += 1
            continue

        article_id = article_file.stem

        if publish_article(article_id, article_data):
            published += 1
        else:
            failed += 1

        # Rate limiting
        import time

        time.sleep(2)

    # Riepilogo
    print()
    print("=" * 70)
    print("📊 Riepilogo:")
    print(f"   Pubblicati: {published}")
    print(f"   Falliti: {failed}")
    print()
    print("🔗 Verifica pubblicazioni:")
    print(
        "   GitHub: https://github.com/Balizero1987/Teman2/tree/main/apps/mouth/src/content/articles"
    )
    print("   URL: https://balizero.com/{category}/{slug}")


if __name__ == "__main__":
    main()
