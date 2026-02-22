#!/usr/bin/env python3
"""Generate Nano Banana Pro AI style images for Bali Zero articles."""

import urllib.request
import urllib.parse
import time
import os

BASE_URL = "https://image.pollinations.ai/prompt/"
OUTPUT_BASE = "apps/mouth/public/static/insights/business"

STYLE_MODIFIER = ", Nano Banana Pro AI style: hyper-realistic, 8k resolution, cinematic lighting, sharp focus, vibrant Bali colors, professional business photography, Bali Zero brand aesthetic"

ARTICLES = [
    {
        "filename": "beginners-guide-kbli-2025.jpg",
        "prompt": "A modern digital compass overlaid on a traditional Balinese batik pattern, pointing towards a futuristic crystal tower labeled KBLI 2025"
    },
    {
        "filename": "kbli-2020-to-2025-migration-guide.jpg",
        "prompt": "A sleek glowing bridge connecting an old weathered stone pillar marked 2020 to a polished marble pillar marked 2025, tropical jungle background"
    },
    {
        "filename": "kbli-2025-agriculture-agritourism.jpg",
        "prompt": "Close up of a premium Bali coffee bean held by a robotic hand over a lush green rice terrace at sunrise"
    },
    {
        "filename": "kbli-2025-bali-transformation.jpg",
        "prompt": "The Bali shoreline with a digital translucent holographic interface showing growth charts and business icons floating over the water"
    },
    {
        "filename": "kbli-2025-brand-positioning-strategy.jpg",
        "prompt": "A professional desk with a luxury Balinese fountain pen resting on a crisp white document with a gold wax seal of Nuzantara"
    },
    {
        "filename": "kbli-2025-capital-investment-requirements.jpg",
        "prompt": "A stack of golden IDR coins arranged in the shape of a modern architectural building in Denpasar, bright blue sky"
    },
    {
        "filename": "kbli-2025-construction-building.jpg",
        "prompt": "Architectural blueprints of a luxury Bali villa transforming into a 3D holographic model with construction workers silhouettes"
    },
    {
        "filename": "kbli-2025-consulting-professional-services.jpg",
        "prompt": "A group of diverse professionals having a meeting in a high-end open-air bamboo office in Ubud, cinematic depth of field"
    },
    {
        "filename": "kbli-2025-creative-design-industry.jpg",
        "prompt": "A high-tech design studio setup with multiple screens showing colorful Balinese graphic art and 3D models"
    },
    {
        "filename": "kbli-2025-education-training.jpg",
        "prompt": "An open laptop displaying a futuristic virtual classroom with Balinese students and holographic certificates"
    },
    {
        "filename": "kbli-2025-environmental-permits-amdal.jpg",
        "prompt": "A pristine waterfall in Bali with a glowing green shield icon representing environmental protection and compliance"
    },
    {
        "filename": "kbli-2025-food-beverage-fnb.jpg",
        "prompt": "A Michelin-star style presentation of Indonesian Nasi Campur with a luxury cocktail in a sophisticated Seminyak restaurant setting"
    }
]

def generate_image(prompt: str, output_path: str):
    full_prompt = prompt + STYLE_MODIFIER
    encoded = urllib.parse.quote(full_prompt)
    url = f"{BASE_URL}{encoded}?width=1200&height=630&seed=88&nologo=true&model=flux"
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as response:
            data = response.read()
            with open(output_path, "wb") as f:
                f.write(data)
            print(f"✅ Generated: {output_path}")
    except Exception as e:
        print(f"❌ Failed {output_path}: {e}")

def main():
    os.makedirs(OUTPUT_BASE, exist_ok=True)
    for article in ARTICLES:
        path = f"{OUTPUT_BASE}/{article['filename']}"
        print(f"Generating for {article['filename']}...")
        generate_image(article["prompt"], path)
        time.sleep(2) # Prevent rate limiting

if __name__ == "__main__":
    main()
