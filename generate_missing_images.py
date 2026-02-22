#!/usr/bin/env python3
"""
Generate missing article images using Nano Banana Pro AI style prompts.
Automatically scans MDX files and generates images for missing covers.
"""

import os
import re
import time
import urllib.parse
import urllib.request
import random

# Configuration
CONTENT_DIR = "apps/mouth/src/content/articles"
IMAGE_DIR_BASE = "apps/mouth/public/static/insights"
STYLE_MODIFIER = " (Style: Nano Banana Pro AI, cinematic hyper-realism, 8k, sharp detailed textures, Bali Zero corporate branding colors, professional photography lighting, minimalist luxury)"

# Categories to scan
CATEGORIES = ["business", "immigration", "tax-legal"]

# Fallback prompts based on keywords if title parsing fails
KEYWORD_PROMPTS = {
    "visa": "Elegant holographic visa card floating above a map of Indonesia, gold and navy blue aesthetic",
    "kitas": "Detailed KITAS permit document on a mahogany desk with a passport and Balinese artifacts",
    "tax": "Golden calculator and tax documents with a digital compliance shield overlay, professional financial setting",
    "business": "Modern glass office building in Jakarta with digital growth charts ascending into the sky",
    "bali": "Stunning aerial view of Bali coastline merging with digital network nodes, nature meets technology",
    "property": "Luxury villa architectural model on a drafting table with golden keys",
    "law": "Bronze scales of justice balanced on a pile of legal documents, dramatic lighting",
    "pma": "Handshake between international business partners with a holographic globe between them",
    "invest": "Stack of gold coins and investment charts on a tablet screen, blurry tropical background"
}

def get_articles_without_images():
    missing = []
    print(f"Scanning {CONTENT_DIR} for missing images...")
    
    for root, dirs, files in os.walk(CONTENT_DIR):
        for file in files:
            if file.endswith(".mdx"):
                full_path = os.path.join(root, file)
                category = os.path.basename(root) # e.g., 'business'
                slug = file.replace(".mdx", "")
                
                # Check expected image path
                image_filename = f"{slug}.jpg"
                image_path = os.path.join(IMAGE_DIR_BASE, category, image_filename)
                
                if not os.path.exists(image_path) or os.path.getsize(image_path) < 1000:
                    # Extract title for prompt generation
                    with open(full_path, "r") as f:
                        content = f.read()
                        title_match = re.search(r'title:\s*"(.*?)"', content)
                        title = title_match.group(1) if title_match else slug.replace("-", " ")
                        
                    missing.append({
                        "slug": slug,
                        "category": category,
                        "title": title,
                        "output_path": image_path
                    })
    
    return missing

def generate_prompt(title):
    # Simple logic to create a prompt from title + keywords
    title_lower = title.lower()
    base_prompt = f"Editorial illustration for an article titled '{title}'"
    
    # Enrich with keyword context
    for key, prompt in KEYWORD_PROMPTS.items():
        if key in title_lower:
            base_prompt = f"{prompt}, representing '{title}'"
            break
            
    return base_prompt + STYLE_MODIFIER

def download_image(prompt, output_path):
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    encoded = urllib.parse.quote(prompt)
    # Using Pollinations.AI endpoint (robust fallback)
    url = f"https://pollinations.ai/p/{encoded}?width=1200&height=630&seed={random.randint(1, 1000)}&nologo=true&model=flux"
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as response:
            data = response.read()
            if len(data) < 5000:
                print(f"  ⚠️  Corrupted/Small file received")
                return False
            with open(output_path, "wb") as f:
                f.write(data)
            return True
    except Exception as e:
        print(f"  ❌ Download failed: {e}")
        return False

def main():
    missing_articles = get_articles_without_images()
    print(f"Found {len(missing_articles)} articles needing images.")
    
    success_count = 0
    
    for i, item in enumerate(missing_articles):
        print(f"[{i+1}/{len(missing_articles)}] Generating for: {item['slug']} ({item['category']})")
        prompt = generate_prompt(item['title'])
        # print(f"  Prompt: {prompt[:50]}...")
        
        if download_image(prompt, item['output_path']):
            print(f"  ✅ Saved to {item['output_path']}")
            success_count += 1
        else:
            print(f"  ❌ Failed")
        
        # Polite rate limiting
        time.sleep(1.5)

    print(f"\nCompleted. Generated {success_count}/{len(missing_articles)} images.")

if __name__ == "__main__":
    main()
