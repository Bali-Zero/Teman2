#!/usr/bin/env python3
"""Generate unique branded images for business articles to avoid duplicates."""

import urllib.request
import urllib.parse
import time
import os
import random

BASE_URL = "https://pollinations.ai/p/"
OUTPUT_BASE = "apps/mouth/public/static/insights/business"
STYLE = "Nano Banana Pro style, cinematic hyper-realistic, 8k, professional business photography, Bali Zero branding colors"

ARTICLES = [
    {"slug": "ecommerce-indonesia", "prompt": "Luxury ecommerce delivery box with Balinese pattern, tropical foliage background"},
    {"slug": "pt-pma-registration-guide", "prompt": "Corporate registration certificate with a gold seal on a modern desk in Jakarta"},
    {"slug": "starting-a-business-in-indonesia-complete-guide", "prompt": "A modern business center lobby with a sign saying Welcome to Indonesia, bright sunlight"},
    {"slug": "business-licenses-overview", "prompt": "A digital tablet showing various business permits and icons, modern interface"},
    {"slug": "capital-requirements-guide", "prompt": "A graph showing capital growth next to a stack of IDR banknotes, professional lighting"},
    {"slug": "hiring-indonesian-employees", "prompt": "A diverse team of professionals having a meeting in a tropical modern office"},
    {"slug": "labor-law-guide", "prompt": "Scales of justice on top of an Indonesian labor law book, mahogany desk"},
    {"slug": "minimum-wage-indonesia-2026", "prompt": "Financial chart showing wage trends in Indonesia, 2026 forecast, blue aesthetic"},
    {"slug": "monthly-bookkeeping-indonesia", "prompt": "A neat organized desk with a calculator, notebook and coffee, business bookkeeping theme"},
    {"slug": "audit-requirements-indonesia", "prompt": "A magnifying glass over a pile of financial documents, sharp focus, auditing theme"}
]

def generate(slug, prompt):
    full_prompt = f"{prompt}. {STYLE}"
    encoded = urllib.parse.quote(full_prompt)
    # Using a random seed to ensure uniqueness
    seed = random.randint(1000, 9999)
    url = f"{BASE_URL}{encoded}?width=1200&height=630&seed={seed}&nologo=true"
    
    path = f"{OUTPUT_BASE}/{slug}.jpg"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read()
            if len(data) > 5000:
                with open(path, "wb") as f:
                    f.write(data)
                print(f"✅ Generated unique image for {slug}")
                return True
    except Exception as e:
        print(f"❌ Failed {slug}: {e}")
    return False

def main():
    os.makedirs(OUTPUT_BASE, exist_ok=True)
    for a in ARTICLES:
        generate(a["slug"], a["prompt"])
        time.sleep(1)

if __name__ == "__main__":
    main()
