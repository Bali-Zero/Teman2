#!/usr/bin/env python3
"""
Fallback strategy: Clone existing high-quality images to cover missing visuals.
Maps keywords in filenames to existing 'best-in-class' images.
"""

import os
import shutil

CONTENT_DIR = "apps/mouth/src/content/articles"
IMAGE_DIR_BASE = "apps/mouth/public/static/insights"

# Source images (Best-in-class existing images)
# We assume these exist based on previous 'ls' output
SOURCES = {
    "business": "apps/mouth/public/static/insights/business/starting-business-indonesia.jpg",
    "visa": "apps/mouth/public/static/insights/immigration/e28a-investor-kitas-guide.jpg",
    "property": "apps/mouth/public/static/insights/property/villa-purchase-bali.jpg",
    "tax": "apps/mouth/public/static/insights/tax-legal/tax-planning-expats.jpg", # Assuming this exists or similar
    "lifestyle": "apps/mouth/public/static/insights/lifestyle/cost-of-living-bali.jpg", # Assuming this exists
    "tech": "apps/mouth/public/static/insights/business/kbli-2025-it-services-software.jpg"
}

# Specific mappings for keywords -> source image key
KEYWORD_MAPPING = {
    "kitas": "visa",
    "visa": "visa",
    "immigration": "visa",
    "passport": "visa",
    "property": "property",
    "land": "property",
    "villa": "property",
    "tax": "tax",
    "pajak": "tax",
    "pph": "tax",
    "business": "business",
    "company": "business",
    "pt-pma": "business",
    "investment": "business",
    "digital-nomad": "lifestyle",
    "bali": "lifestyle",
    "lifestyle": "lifestyle",
    "tech": "tech",
    "digital": "tech",
    "software": "tech"
}

def get_best_source(filename):
    for keyword, source_key in KEYWORD_MAPPING.items():
        if keyword in filename:
            return SOURCES.get(source_key)
    return SOURCES["business"] # Default fallback

def main():
    missing_count = 0
    copied_count = 0
    
    # 1. First, verify sources exist. If not, find *any* jpg in that dir to use as source.
    # This makes the script robust if specific files are missing.
    verified_sources = {}
    for key, path in SOURCES.items():
        if os.path.exists(path):
            verified_sources[key] = path
        else:
            # Try to find a fallback in the same directory
            dir_path = os.path.dirname(path)
            if os.path.exists(dir_path):
                files = [f for f in os.listdir(dir_path) if f.endswith(".jpg")]
                if files:
                    fallback_path = os.path.join(dir_path, files[0])
                    verified_sources[key] = fallback_path
                    print(f"⚠️ Source for {key} missing, using fallback: {files[0]}")
    
    if not verified_sources:
        print("❌ Critical: No source images found to clone!")
        return

    # Update SOURCES map with verified paths
    SOURCES.update(verified_sources)

    # 2. Scan and Clone
    for root, dirs, files in os.walk(CONTENT_DIR):
        for file in files:
            if file.endswith(".mdx"):
                category = os.path.basename(root)
                slug = file.replace(".mdx", "")
                target_image_filename = f"{slug}.jpg"
                
                # Determine target directory (mirroring content structure or flat structure)
                # The image dir structure in public/static/insights seems to mirror content categories
                target_dir = os.path.join(IMAGE_DIR_BASE, category)
                target_path = os.path.join(target_dir, target_image_filename)
                
                if not os.path.exists(target_path):
                    missing_count += 1
                    
                    # Determine source
                    source_path = get_best_source(slug)
                    
                    if source_path and os.path.exists(source_path):
                        os.makedirs(target_dir, exist_ok=True)
                        shutil.copy2(source_path, target_path)
                        print(f"✅ Created: {target_image_filename} (from {os.path.basename(source_path)})")
                        copied_count += 1
                    else:
                        print(f"❌ Could not find source for {slug}")

    print(f"\nSummary: {copied_count}/{missing_count} images created via cloning.")

if __name__ == "__main__":
    main()
