#!/usr/bin/env python3
"""Generate article cover images via Pollinations.AI with Nano Banana Pro AI style."""

import urllib.request
import urllib.parse
import time
import os

BASE_URL = "https://image.pollinations.ai/prompt/"
OUTPUT_BASE = "apps/mouth/public/static/insights/business"

# Nano Banana Pro AI Style: 
# "Tropical Cyberpunk, Nano-Banana textures, vibrant yellow and neon green, 
#  integrated with tech/legal metaphors, high-end digital art, 8k, cinematic."

COLLEGA3_IMAGES = [
    {
        "filename": "kbli-2025-multi-code-strategy.jpg",
        "prompt": "Multi-colored Tetris blocks made of holographic banana fibers fitting together, tropical digital workspace, neon yellow and lime green accents, cinematic lighting, 8k.",
    },
    {
        "filename": "kbli-2025-new-codes-spotlight.jpg",
        "prompt": "A spotlight illuminating a futuristic tech-banana with VR headset and digital icons, cyberpunk tropical laboratory, vibrant yellow and purple, high-end digital art.",
    },
    {
        "filename": "kbli-2025-oss-transition-update.jpg",
        "prompt": "A digital portal transitioning from a dusty ledger to a glowing Nano-Banana interface, tropical tech aesthetic, vibrant yellow glowing energy, cinematic.",
    },
    {
        "filename": "kbli-2025-real-estate-property.jpg",
        "prompt": "Futuristic Bali villa architecture with Nano-Banana solar leaf panels, luxury property development meets tropical tech, sunset gold and neon green, 8k.",
    },
    {
        "filename": "kbli-2025-red-flags-audit-risk.jpg",
        "prompt": "A digital warning flag with a neon banana core, storm clouds made of binary data, tropical tech security aesthetic, red and yellow glow, dramatic.",
    },
    {
        "filename": "kbli-2025-retail-ecommerce.jpg",
        "prompt": "A digital shopping cart filled with glowing neon bananas and tech gadgets, tropical e-commerce interface, vibrant yellow and electric blue, 8k.",
    },
    {
        "filename": "kbli-2025-tax-implications-klu.jpg",
        "prompt": "A calculator built into a Balinese offering tray with smoke turning into golden banana currency symbols, mystical tropical tech, yellow and green glow.",
    },
    {
        "filename": "kbli-2025-tourism-travel-services.jpg",
        "prompt": "A futuristic holographic travel map with banana-shaped markers for Bali locations, tropical digital agency, vibrant yellow and turquoise, cinematic.",
    },
    {
        "filename": "kbli-2025-visa-kitas-synergy.jpg",
        "prompt": "A KITAS card merging with a digital business license in a flash of Nano-Banana energy, synergy effect, tropical cyberpunk, yellow and gold sparks.",
    },
    {
        "filename": "kbli-klu-fiscal-control-2025.jpg",
        "prompt": "A digital fiscal eye watching over a field of data-bananas, Coretax surveillance architecture, tropical cyber-surveillance, vibrant yellow and dark navy.",
    },
    {
        "filename": "oss-kbli-2025-fiktif-positif.jpg",
        "prompt": "A golden digital seal of approval with a banana motif appearing from a cloud of silent data, bureaucratic silence as power, yellow glow, 8k.",
    },
    {
        "filename": "upgrading-indonesia-kbli-2025.jpg",
        "prompt": "A massive staircase ascending to a giant glowing Nano-Banana sun, modern Indonesia skyline, regulatory upgrade strategy, vibrant yellow and orange, cinematic.",
    },
]

def generate_image(prompt: str, output_path: str) -> bool:
    """Download image from Pollinations.AI."""
    full_prompt = f"{prompt} tropical tech Bali yellow neon"
    encoded = urllib.parse.quote(full_prompt)
    url = f"{BASE_URL}{encoded}?width=1200&height=630&seed=88&nologo=true"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as response:
            data = response.read()
            if len(data) < 1000:
                return False
            with open(output_path, "wb") as f:
                f.write(data)
            return True
    except Exception as e:
        print(f"  Error generating {output_path}: {e}")
        return False

def main():
    os.makedirs(OUTPUT_BASE, exist_ok=True)
    total = len(COLLEGA3_IMAGES)
    
    print(f"Starting image generation for 12 articles (Nano Banana Pro AI style)...")
    
    for i, img in enumerate(COLLEGA3_IMAGES):
        output_path = f"{OUTPUT_BASE}/{img['filename']}"
        print(f"[{i+1}/{total}] Generating {img['filename']}...", end=" ", flush=True)
        
        if generate_image(img["prompt"], output_path):
            print("OK")
        else:
            print("FAILED")
        
        # Rate limiting
        time.sleep(2)

if __name__ == "__main__":
    main()
