#!/usr/bin/env python3
"""Generate Nano Banana Pro AI style images using a more robust endpoint."""

import urllib.request
import urllib.parse
import time
import os

# Using a more direct endpoint often more stable
BASE_URL = "https://pollinations.ai/p/"
OUTPUT_BASE = "apps/mouth/public/static/insights/business"

# High-fidelity prompt modifier for "Nano Banana Pro" look
STYLE_MODIFIER = " (Style: Nano Banana Pro AI, cinematic hyper-realism, 8k, sharp detailed textures, Bali Zero corporate branding colors, professional photography lighting)"

ARTICLES = [
    {"filename": "beginners-guide-kbli-2025.jpg", "prompt": "Futuristic digital compass on Balinese batik, 2025 roadmap"},
    {"filename": "kbli-2020-to-2025-migration-guide.jpg", "prompt": "Glowing bridge connecting stone 2020 pillar to crystal 2025 pillar"},
    {"filename": "kbli-2025-agriculture-agritourism.jpg", "prompt": "Premium coffee bean in robotic hand over rice terraces"},
    {"filename": "kbli-2025-bali-transformation.jpg", "prompt": "Uluwatu temple meets holographic business data"},
    {"filename": "kbli-2025-brand-positioning-strategy.jpg", "prompt": "Chess pieces as Balinese statues on a luxury desk"},
    {"filename": "kbli-2025-capital-investment-requirements.jpg", "prompt": "Stack of gold IDR coins forming a skyscraper"},
    {"filename": "kbli-2025-construction-building.jpg", "prompt": "Holographic villa blueprint in a tropical setting"},
    {"filename": "kbli-2025-consulting-professional-services.jpg", "prompt": "Luxury bamboo office in Ubud with professionals"},
    {"filename": "kbli-2025-creative-design-industry.jpg", "prompt": "Creative studio with 3D Balinese art on screens"},
    {"filename": "kbli-2025-education-training.jpg", "prompt": "Virtual classroom with students and holographic certificates"},
    {"filename": "kbli-2025-environmental-permits-amdal.jpg", "prompt": "Glowing green shield over a pristine Bali waterfall"},
    {"filename": "kbli-2025-food-beverage-fnb.jpg", "prompt": "Michelin-star Nasi Campur in a luxury Seminyak bar"}
]

def generate_image(prompt: str, output_path: str):
    full_prompt = prompt + STYLE_MODIFIER
    encoded = urllib.parse.quote(full_prompt)
    # Adding extra params for quality
    url = f"{BASE_URL}{encoded}?width=1200&height=630&seed=123&nologo=true"
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        # Polling strategy
        with urllib.request.urlopen(req, timeout=60) as response:
            data = response.read()
            if len(data) < 5000: # Very small file usually means an error page
                print(f"  ⚠️ Received corrupted file for {output_path}")
                return False
            with open(output_path, "wb") as f:
                f.write(data)
            return True
    except Exception as e:
        print(f"  ❌ Error for {output_path}: {e}")
        return False

def main():
    os.makedirs(OUTPUT_BASE, exist_ok=True)
    success_count = 0
    for article in ARTICLES:
        path = f"{OUTPUT_BASE}/{article['filename']}"
        print(f"Generating: {article['filename']}...", end=" ", flush=True)
        
        if generate_image(article["prompt"], path):
            print("✅")
            success_count += 1
        else:
            print("❌")
        time.sleep(1)

    print(f"\nTotal Success: {success_count}/{len(ARTICLES)}")

if __name__ == "__main__":
    main()
