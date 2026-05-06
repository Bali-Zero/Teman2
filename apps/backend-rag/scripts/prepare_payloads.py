#!/usr/bin/env python3
"""
Prepare Payloads for Qdrant REST API Upload
-------------------------------------------
Reads bali_zero_official_prices_2026.json, generates embeddings,
and formats data for Qdrant REST API upsert endpoint.

The 2026 schema has one extra nesting level for ``tax_accounting``
(sub-blocks: ``monthly_tax_basic`` / ``monthly_tax_bundled`` /
``annual_basic_packages`` / ``annual_standalone``). ``flatten_services``
descends into those sub-blocks so each tier becomes its own embedding.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATA_PATH = (
    Path(__file__).parent.parent / "backend" / "data" / "bali_zero_official_prices_2026.json"
)
OUTPUT_PATH = Path(__file__).parent / "ready_to_curl.json"
COLLECTION_NAME = "bali_zero_pricing"

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not set in environment")


def generate_semantic_text(
    item_name: str, category: str, item_data: dict[str, Any], contact_info: dict[str, Any]
) -> str:
    """
    Generate rich markdown semantic text for a pricing item.

    Args:
        item_name: Name of the service/item
        category: Category (e.g., "single_entry_visas", "kitas_permits")
        item_data: Item data dict with price, notes, duration, validity
        contact_info: Contact information dict

    Returns:
        Rich markdown formatted text
    """
    # 2026: use ``tier_range`` when ``price`` is empty.
    price = (item_data.get("price") or "").strip()
    if not price:
        tier_range = item_data.get("tier_range")
        if isinstance(tier_range, (list, tuple)) and len(tier_range) == 2:
            low = (tier_range[0] or "").strip().replace("IDR", "").strip()
            high = (tier_range[1] or "").strip().replace("IDR", "").strip()
            if low and high:
                price = f"Rp {low} – {high}"
    if not price:
        price = "Contact for quote"

    parts = [
        f"# {item_name}",
        f"**Category**: {category.replace('_', ' ').title()}",
        f"**Price**: {price}",
    ]

    if item_data.get("description_en"):
        parts.append(f"**Description**: {item_data['description_en']}")

    if item_data.get("duration"):
        parts.append(f"**Duration**: {item_data['duration']}")

    if item_data.get("validity"):
        parts.append(f"**Validity**: {item_data['validity']}")

    if item_data.get("notes"):
        parts.append(f"**Notes**: {item_data['notes']}")

    parts.append("")
    parts.append("---")
    parts.append("")
    parts.append(f"**Contact**: {contact_info.get('email', 'zero@balizero.com')}")
    parts.append(f"**WhatsApp**: {contact_info.get('whatsapp', '')}")
    parts.append(f"**Location**: {contact_info.get('location', 'Kerobokan, Bali, Indonesia')}")

    return "\n".join(parts)


def generate_point_id(item_name: str, category: str) -> int:
    """Generate a deterministic integer ID for a point."""
    unique_string = f"{category}:{item_name}"
    hash_obj = hashlib.md5(unique_string.encode())
    hex_hash = hash_obj.hexdigest()[:16]
    # Convert to integer (Qdrant accepts int64)
    return int(hex_hash, 16) % (2**63)


def flatten_services(data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Flatten nested services structure into individual items.

    The 2026 schema introduces ``tax_accounting`` whose value is a dict of
    sub-blocks (``monthly_tax_basic`` / ``monthly_tax_bundled`` / ...),
    each of which is itself a ``{name: entry}`` map. Descend one level
    deeper for those — and detect them generically by checking whether the
    inner dict's values look like service entries (have ``price`` or
    ``tier_range``) instead of being entries themselves.

    Returns:
        List of dicts with: name, category, data
    """
    items: list[dict[str, Any]] = []
    services = data.get("services", {})
    # 2026 contact lives under ``metadata.contact``.
    contact_info = data.get("contact_info") or data.get("metadata", {}).get("contact", {})

    def _is_service_entry(d: dict[str, Any]) -> bool:
        return isinstance(d, dict) and ("price" in d or "tier_range" in d)

    for category, category_items in services.items():
        if not isinstance(category_items, dict):
            continue

        for item_name, item_data in category_items.items():
            if not isinstance(item_data, dict):
                continue

            # Sub-block detection: dict of dicts where the inner values
            # ARE service entries (this matches ``tax_accounting`` in 2026).
            if (
                not _is_service_entry(item_data)
                and item_data
                and all(_is_service_entry(v) for v in item_data.values())
            ):
                for sub_name, sub_entry in item_data.items():
                    items.append(
                        {
                            "name": sub_name,
                            "category": f"{category}/{item_name}",
                            "data": sub_entry,
                            "contact_info": contact_info,
                        }
                    )
                continue

            items.append(
                {
                    "name": item_name,
                    "category": category,
                    "data": item_data,
                    "contact_info": contact_info,
                }
            )

    return items


def main():
    """Main function to prepare payloads."""
    print("🚀 Starting Payload Preparation...")
    print(f"📂 Reading: {DATA_PATH}")

    # Load data
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Data file not found: {DATA_PATH}")

    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)

    # Flatten services
    items = flatten_services(data)
    print(f"📊 Found {len(items)} pricing items")

    # Initialize OpenAI client
    openai_client = OpenAI(api_key=OPENAI_API_KEY)

    # Prepare points
    points = []
    texts = []

    for idx, item in enumerate(items, 1):
        item_name = item["name"]
        category = item["category"]
        item_data = item["data"]
        contact_info = item["contact_info"]

        # Generate semantic text
        semantic_text = generate_semantic_text(item_name, category, item_data, contact_info)
        texts.append(semantic_text)

        print(f"  [{idx}/{len(items)}] Prepared: {item_name}")

    # Generate embeddings in batches
    print(f"\n🔮 Generating embeddings for {len(texts)} texts...")
    all_embeddings = []
    batch_size = 100  # OpenAI can handle up to 2048, but let's be conservative

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(texts) + batch_size - 1) // batch_size

        print(f"  Processing batch {batch_num}/{total_batches} ({len(batch)} texts)...")

        try:
            response = openai_client.embeddings.create(model="text-embedding-3-small", input=batch)
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)
            print(f"    ✅ Generated {len(batch_embeddings)} embeddings")
        except Exception as e:
            print(f"    ❌ Error generating embeddings: {e}")
            raise

    print(f"\n✅ Generated {len(all_embeddings)} embeddings total")

    # Build points array
    print("\n📦 Building Qdrant points...")
    for idx, (item, text, embedding) in enumerate(zip(items, texts, all_embeddings, strict=False)):
        item_name = item["name"]
        category = item["category"]
        item_data = item["data"]

        point_id = generate_point_id(item_name, category)

        point = {
            "id": point_id,
            "vector": embedding,
            "payload": {
                "text": text,
                "name": item_name,
                "category": category,
                "price": item_data.get("price", ""),
                "duration": item_data.get("duration", ""),
                "validity": item_data.get("validity", ""),
                "notes": item_data.get("notes", ""),
                "source_type": "bali_zero_pricing",
                "last_updated": data.get("last_updated", ""),
                "currency": data.get("currency", "IDR"),
            },
        }

        points.append(point)
        print(f"  [{idx + 1}/{len(items)}] Built point: {item_name} (ID: {point_id})")

    # Save to JSON file
    output_data = {
        "collection": COLLECTION_NAME,
        "points": points,
        "total_points": len(points),
        "metadata": {
            "source_file": str(DATA_PATH),
            "last_updated": data.get("last_updated", ""),
            "currency": data.get("currency", "IDR"),
        },
    }

    print(f"\n💾 Saving to: {OUTPUT_PATH}")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Success! Prepared {len(points)} points ready for curl upload")
    print(f"📄 Output file: {OUTPUT_PATH}")
    print("\nNext step: Run force_upload.sh to upload to Qdrant")


if __name__ == "__main__":
    main()
