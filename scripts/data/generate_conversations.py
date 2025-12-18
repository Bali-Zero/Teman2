"""
ZANTARA - Conversation Generator

Generates WhatsApp-style consultation conversations using:
1. KB facts from Qdrant
2. Existing conversation templates as few-shot examples
3. Claude/OpenAI for generation

Usage:
    python scripts/generate_conversations.py --topic "E33G Digital Nomad Visa"
    python scripts/generate_conversations.py --batch visa  # Generate all visa types
    python scripts/generate_conversations.py --batch all   # Generate everything
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# Configuration
RAG_API_URL = "https://nuzantara-rag.fly.dev/api/search/"
RAG_API_KEY = os.getenv("API_KEYS", "").split(",")[0] if os.getenv("API_KEYS") else ""
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OUTPUT_DIR = Path.home() / "Desktop" / "conv" / "generated"

# Topics to generate
VISA_TOPICS = [
    {"topic": "E33G Digital Nomad Visa", "collection": "visa_oracle", "code": "E33G"},
    {"topic": "C2 Business Visit Visa", "collection": "visa_oracle", "code": "C2"},
    {
        "topic": "D1 Tourism Multiple Entry Visa",
        "collection": "visa_oracle",
        "code": "D1",
    },
    {
        "topic": "D2 Business Multiple Entry Visa",
        "collection": "visa_oracle",
        "code": "D2",
    },
    {"topic": "Golden Visa Indonesia", "collection": "visa_oracle", "code": "GOLDEN"},
    {"topic": "E31A Spouse KITAS", "collection": "visa_oracle", "code": "E31A"},
    {
        "topic": "E31B Dependent Child KITAS",
        "collection": "visa_oracle",
        "code": "E31B",
    },
    {"topic": "E33F Retirement KITAS", "collection": "visa_oracle", "code": "E33F"},
    {
        "topic": "KITAP Permanent Residence",
        "collection": "visa_oracle",
        "code": "KITAP",
    },
]

TAX_TOPICS = [
    {
        "topic": "PPh 21 Employee Withholding Tax",
        "collection": "tax_genius",
        "code": "PPH21",
    },
    {"topic": "VAT PPN 11% Registration", "collection": "tax_genius", "code": "PPN"},
    {"topic": "Corporate Income Tax 22%", "collection": "tax_genius", "code": "CIT"},
    {
        "topic": "Expatriate Tax Obligations",
        "collection": "tax_genius",
        "code": "EXPAT_TAX",
    },
    {"topic": "Transfer Pricing Rules", "collection": "tax_genius", "code": "TP"},
]

KBLI_TOPICS = [
    {
        "topic": "KBLI for Restaurant Business",
        "collection": "kbli_unified",
        "code": "KBLI_REST",
    },
    {
        "topic": "KBLI for Villa Rental Business",
        "collection": "kbli_unified",
        "code": "KBLI_VILLA",
    },
    {
        "topic": "KBLI for IT Consulting",
        "collection": "kbli_unified",
        "code": "KBLI_IT",
    },
    {
        "topic": "PT PMA Company Setup",
        "collection": "kbli_unified",
        "code": "PMA_SETUP",
    },
    {
        "topic": "OSS NIB Registration Process",
        "collection": "kbli_unified",
        "code": "OSS_NIB",
    },
]

# Few-shot examples from existing conversations
FEW_SHOT_EXAMPLES = """
## Example 1: Freelance KITAS Conversation (Indonesian)

**Client:** Halo, mau tanya soal KITAS Freelance yang 180 hari itu. Bisa jelasin ke saya bagaimana prosesnya?

**Consultant:** Tentu bisa. KITAS Freelance ini berlaku **maksimal 180 hari** untuk **satu jenis pekerjaan** dan bisa digunakan bekerja fleksibel di seluruh Bali.

**Client:** Oke, berarti setengah tahun ya? Itu nanti bisa diperpanjang kalau saya mau lanjut?

**Consultant:** Nah, untuk tipe KITAS ini **tidak bisa diperpanjang**. Kalau masa berlakunya habis, kamu harus **menutup KITAS lama**, keluar dari Indonesia sebentar, dan **apply baru lagi** dari offshore.

---

## Example 2: C7 Visa Conversation (English)

**Client:** Hey, I saw something about a C7 Performing Visa. What does it mean?

**Consultant:** The C7 Visa allows you to perform in Indonesia for 30 days, *without earning money*. You can only perform at the venue we register for you.

**Client:** So it's for hobby/performance only, not actual work?

**Consultant:** Exactly. No IMTA, no income allowed.

**Client:** How long does the process take?

**Consultant:** Around 7 working days. Once approved, I'll send your visa in PDF format.

---

## Example 3: Investor KITAS Conversation (Javanese)

**Client:** Mas, aku arep takon… nek aku kepengin manggon neng Bali bareng buka usaha cilik-cilikan, kuwi perlu Investor KITAS yo?

**Konsultan:** Iyo tenan. Nek pengin nduwé perusahaan dewe neng Indonesia lan manggon legal, Investor KITAS kuwi dalane. Rencanané piye?

**Client:** Rencanané aku pengin nggawe PT PMA kanggo usaha properti cilik. Ribet ora prosesé?

**Konsultan:** Nek dewean yo mumet, tapi nek karo kito yo santai wae mas. 😄
"""

GENERATION_PROMPT = """You are creating WhatsApp conversation templates for Bali Zero visa consultants.

## TASK
Generate a realistic 10-bubble WhatsApp conversation between a Client and Consultant about: {topic}

## KNOWLEDGE BASE FACTS (use these as source of truth):
{kb_facts}

## STYLE EXAMPLES (follow this conversation style):
{few_shot}

## REQUIREMENTS
1. Create exactly 10 exchanges (client question → consultant answer)
2. Cover these aspects:
   - What is it / purpose
   - Requirements/documents
   - Process duration
   - Costs/fees
   - Important restrictions
   - Common misconceptions

3. Generate in 3 languages:
   - **Indonesian** (formal but friendly)
   - **English** (professional)
   - **Javanese Timuran** (casual, medok)

4. Use markdown formatting:
   - **Bold** for important info
   - Bullet points for lists
   - Emojis sparingly (1-2 max)

5. Make it feel REAL:
   - Client asks follow-up questions
   - Client sometimes misunderstands
   - Consultant corrects gently
   - Natural conversation flow

## OUTPUT FORMAT
```markdown
# {topic} — 10 Bubble Conversation

---

## 🇮🇩 Indonesian Version

**1 — Client:**
[question]

**Consultant:**
[answer]

**2 — Client:**
[question]

**Consultant:**
[answer]

[... continue to 10]

---

## 🇬🇧 English Version

[same structure]

---

## 🟫 Javanese Version

[same structure]
```

Generate the conversation now:
"""


async def search_kb(query: str, collection: str, limit: int = 5) -> list[dict]:
    """Search the RAG knowledge base for relevant facts."""
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(
                RAG_API_URL,
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": RAG_API_KEY,
                },
                json={
                    "query": query,
                    "collection": collection,
                    "limit": limit,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])
        except Exception as e:
            print(f"⚠️ KB search failed: {e}")
            return []


def format_kb_facts(results: list[dict]) -> str:
    """Format KB search results for the prompt."""
    if not results:
        return "No specific facts found. Use general knowledge."

    facts = []
    for i, r in enumerate(results, 1):
        text = r.get("text", "")[:1500]  # Limit each fact
        facts.append(f"**Fact {i}:**\n{text}")

    return "\n\n".join(facts)


async def generate_conversation(topic: str, collection: str, code: str) -> str:
    """Generate a conversation using Claude."""
    print(f"📚 Searching KB for: {topic}")
    kb_results = await search_kb(topic, collection, limit=5)
    kb_facts = format_kb_facts(kb_results)

    print("🧠 Generating conversation with Claude...")

    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = GENERATION_PROMPT.format(
        topic=topic,
        kb_facts=kb_facts,
        few_shot=FEW_SHOT_EXAMPLES,
    )

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text


async def save_conversation(content: str, code: str, topic: str):
    """Save generated conversation to file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    filename = f"{code.lower()}_conversation_{datetime.now().strftime('%Y%m%d')}.md"
    filepath = OUTPUT_DIR / filename

    header = f"""# Generated Conversation: {topic}

> **Generated**: {datetime.now().isoformat()}
> **Source**: Nuzantara KB + Claude
> **Status**: Review required before use

---

"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(header + content)

    print(f"✅ Saved: {filepath}")
    return filepath


async def generate_single(topic: str, collection: str, code: str):
    """Generate a single conversation."""
    print(f"\n{'=' * 60}")
    print(f"🎯 Topic: {topic}")
    print(f"{'=' * 60}")

    content = await generate_conversation(topic, collection, code)
    await save_conversation(content, code, topic)


async def generate_batch(category: str):
    """Generate batch of conversations."""
    if category == "visa":
        topics = VISA_TOPICS
    elif category == "tax":
        topics = TAX_TOPICS
    elif category == "kbli":
        topics = KBLI_TOPICS
    elif category == "all":
        topics = VISA_TOPICS + TAX_TOPICS + KBLI_TOPICS
    else:
        print(f"❌ Unknown category: {category}")
        return

    print(f"\n🚀 Generating {len(topics)} conversations...")

    for item in topics:
        try:
            await generate_single(item["topic"], item["collection"], item["code"])
        except Exception as e:
            print(f"❌ Failed {item['topic']}: {e}")

        # Small delay to avoid rate limits
        await asyncio.sleep(2)

    print(f"\n✅ Batch complete! Check: {OUTPUT_DIR}")


async def main():
    parser = argparse.ArgumentParser(description="Generate consultation conversations")
    parser.add_argument("--topic", type=str, help="Single topic to generate")
    parser.add_argument(
        "--collection", type=str, default="visa_oracle", help="KB collection"
    )
    parser.add_argument("--code", type=str, default="CUSTOM", help="Output code")
    parser.add_argument(
        "--batch",
        type=str,
        choices=["visa", "tax", "kbli", "all"],
        help="Batch generation",
    )

    args = parser.parse_args()

    if not ANTHROPIC_API_KEY:
        print("❌ ANTHROPIC_API_KEY not found in environment")
        sys.exit(1)

    if args.batch:
        await generate_batch(args.batch)
    elif args.topic:
        await generate_single(args.topic, args.collection, args.code)
    else:
        # Default: generate one example
        await generate_single("E33G Digital Nomad Visa", "visa_oracle", "E33G")


if __name__ == "__main__":
    asyncio.run(main())
