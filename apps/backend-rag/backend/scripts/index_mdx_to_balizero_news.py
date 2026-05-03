"""
Index MDX editorial articles into balizero_news Qdrant collection.

Reads all .mdx files from apps/mouth/src/content/articles/,
parses frontmatter + body, chunks by section (## heading boundaries),
embeds with text-embedding-3-small (1536 dims), and upserts to Qdrant.

Payload schema matches existing balizero_news points:
  - text: str (the embedded content)
  - metadata: dict (title, category, source_url, tier, tags, published_at, etc.)

Usage:
    cd apps/backend-rag
    source .venv/bin/activate
    PYTHONPATH=. python backend/scripts/index_mdx_to_balizero_news.py [--dry-run] [--limit N]
"""

import argparse
import hashlib
import logging
import os
import re
import sys
import uuid
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# --- Config ---
COLLECTION_NAME = "balizero_news"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMS = 1536
MAX_CHUNK_CHARS = 2000  # ~500 tokens — matches RAG retrieval window
MIN_CHUNK_CHARS = 200  # skip tiny fragments
BATCH_SIZE = 50  # points per upsert batch
EMBED_BATCH_SIZE = 20  # texts per embedding API call

ARTICLES_DIR = (
    Path(__file__).resolve().parents[4] / "apps" / "mouth" / "src" / "content" / "articles"
)
CANONICAL_BASE = "https://balizero.com"

# Tier assignment: editorial content is T1 (authoritative, written by us)
ARTICLE_TIER = "T1"

# Source tag to distinguish from scraper-ingested news
SOURCE_TAG = "editorial_mdx"


def parse_mdx(filepath: Path) -> tuple[dict, str]:
    """Parse frontmatter (YAML) and body from an MDX file."""
    raw = filepath.read_text(encoding="utf-8")

    # Split frontmatter
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError:
                frontmatter = {}
            body = parts[2].strip()
        else:
            frontmatter, body = {}, raw
    else:
        frontmatter, body = {}, raw

    return frontmatter, body


def strip_mdx_components(text: str) -> str:
    """Remove JSX/MDX components, imports, and HTML tags — keep plain text."""
    # Remove import statements
    text = re.sub(r"^import\s+.*$", "", text, flags=re.MULTILINE)
    # Remove self-closing JSX: <Component ... />
    text = re.sub(r"<[A-Z]\w+[^>]*/>\s*", "", text)
    # Remove JSX blocks: <Component ...>...</Component>
    text = re.sub(r"<[A-Z]\w+[^>]*>.*?</[A-Z]\w+>", "", text, flags=re.DOTALL)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Remove markdown image syntax
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_by_sections(body: str, max_chars: int = MAX_CHUNK_CHARS) -> list[dict]:
    """
    Split article body into chunks at ## heading boundaries.

    Each chunk carries its section heading for context.
    Long sections are further split at paragraph boundaries.
    """
    # Clean MDX artifacts
    clean = strip_mdx_components(body)

    # Split at ## headings (keep heading with its content)
    sections = re.split(r"(?=^## )", clean, flags=re.MULTILINE)
    sections = [s.strip() for s in sections if s.strip()]

    chunks = []
    for section in sections:
        # Extract heading if present
        heading_match = re.match(r"^(#{1,4}\s+.+?)$", section, re.MULTILINE)
        heading = heading_match.group(1).strip("# ").strip() if heading_match else ""

        if len(section) <= max_chars:
            if len(section) >= MIN_CHUNK_CHARS:
                chunks.append({"heading": heading, "text": section})
        else:
            # Split long sections at paragraph boundaries
            paragraphs = section.split("\n\n")
            current = ""
            for para in paragraphs:
                if len(current) + len(para) + 2 > max_chars and len(current) >= MIN_CHUNK_CHARS:
                    chunks.append({"heading": heading, "text": current.strip()})
                    current = para
                else:
                    current = current + "\n\n" + para if current else para
            if current.strip() and len(current.strip()) >= MIN_CHUNK_CHARS:
                chunks.append({"heading": heading, "text": current.strip()})

    return chunks


def build_embedding_text(title: str, category: str, chunk: dict) -> str:
    """
    Build the text that gets embedded.

    Prefix with [CONTEXT: ...] line matching the pattern used by other collections
    (legal_unified_hybrid, kbli_2025_final, training_conversations_hybrid).
    """
    heading_part = f" - {chunk['heading']}" if chunk["heading"] else ""
    context = f"[CONTEXT: BaliZero Editorial - {category} - {title}{heading_part}]"
    return f"{context}\n\n{chunk['text']}"


def deterministic_uuid(title: str, chunk_index: int) -> str:
    """Generate a deterministic UUID from title + chunk index for idempotent upserts."""
    key = f"{title}::chunk::{chunk_index}"
    return str(uuid.UUID(hashlib.md5(key.encode()).hexdigest()))


def build_payload(
    frontmatter: dict,
    category: str,
    chunk: dict,
    chunk_index: int,
    total_chunks: int,
    filepath: Path,
) -> dict:
    """
    Build Qdrant payload matching existing balizero_news schema.

    Uses the nested metadata pattern already in production.
    """
    slug = frontmatter.get("slug", filepath.stem)
    canonical = f"{CANONICAL_BASE}/{category}/{slug}"
    tags = frontmatter.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]

    return {
        "text": chunk["_embedding_text"],  # the embedded text
        "metadata": {
            "title": frontmatter.get("title", filepath.stem),
            "summary": frontmatter.get("description", frontmatter.get("excerpt", "")),
            "content_preview": chunk["text"][:500],
            "published_at": str(frontmatter.get("publishedAt", "unknown")),
            "source_url": canonical,
            "source_name": "BaliZero Editorial",
            "category": category,
            "tier": ARTICLE_TIER,
            "keywords": tags,
            "status": "published",
            "indexed_at": "",  # filled at upsert time
            "collection_type": "editorial_mdx",
            "chunk_index": chunk_index,
            "total_chunks": total_chunks,
            "section_heading": chunk["heading"],
            "slug": slug,
            "reading_time": frontmatter.get("readingTime", 0),
            "featured": frontmatter.get("featured", False),
        },
    }


async def embed_texts(texts: list[str], client) -> list[list[float]]:
    """Embed a batch of texts using OpenAI."""
    all_embeddings = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i : i + EMBED_BATCH_SIZE]
        response = await client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        all_embeddings.extend([d.embedding for d in response.data])
    return all_embeddings


async def upsert_to_qdrant(points: list[dict], qdrant_url: str, api_key: str | None):
    """Upsert points to Qdrant in batches."""
    import httpx

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["api-key"] = api_key

    async with httpx.AsyncClient(timeout=60) as http:
        for i in range(0, len(points), BATCH_SIZE):
            batch = points[i : i + BATCH_SIZE]
            body = {"points": batch}
            resp = await http.put(
                f"{qdrant_url}/collections/{COLLECTION_NAME}/points",
                json=body,
                headers=headers,
            )
            if resp.status_code != 200:
                logger.error(
                    f"Qdrant upsert failed batch {i}: {resp.status_code} {resp.text[:300]}",
                )
            else:
                logger.info(f"  Upserted batch {i}-{i + len(batch)} ({len(batch)} points)")


async def main():
    parser = argparse.ArgumentParser(description="Index MDX articles into balizero_news")
    parser.add_argument(
        "--dry-run", action="store_true", help="Parse and chunk but don't embed or upsert",
    )
    parser.add_argument("--limit", type=int, default=0, help="Limit number of articles (0=all)")
    parser.add_argument(
        "--category", type=str, default="", help="Only index articles in this category",
    )
    parser.add_argument(
        "--qdrant-url", type=str, default="", help="Qdrant URL (default: from env or localhost)",
    )
    args = parser.parse_args()

    # Resolve Qdrant connection
    qdrant_url = args.qdrant_url or os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key = os.getenv("QDRANT_API_KEY", "")

    logger.info(f"Articles dir: {ARTICLES_DIR}")
    logger.info(f"Qdrant: {qdrant_url}")
    logger.info(f"Collection: {COLLECTION_NAME}")
    logger.info(f"Dry run: {args.dry_run}")

    if not ARTICLES_DIR.exists():
        logger.error(f"Articles directory not found: {ARTICLES_DIR}")
        sys.exit(1)

    # Discover all MDX files
    mdx_files = sorted(ARTICLES_DIR.rglob("*.mdx"))
    logger.info(f"Found {len(mdx_files)} MDX files")

    if args.category:
        mdx_files = [f for f in mdx_files if f.parent.name == args.category]
        logger.info(f"Filtered to {len(mdx_files)} files in category '{args.category}'")

    if args.limit > 0:
        mdx_files = mdx_files[: args.limit]
        logger.info(f"Limited to {args.limit} files")

    # Skip .id.mdx duplicates (Indonesian translations — same content, different lang)
    mdx_files = [f for f in mdx_files if not f.stem.endswith(".id")]
    logger.info(f"After filtering .id translations: {len(mdx_files)} files")

    # Parse and chunk all articles
    all_points = []
    from datetime import datetime, timezone

    indexed_at = datetime.now(timezone.utc).isoformat()

    stats = {"articles": 0, "chunks": 0, "skipped_small": 0}

    for filepath in mdx_files:
        category = filepath.parent.name
        frontmatter, body = parse_mdx(filepath)

        if not body or len(body) < 100:
            logger.warning(f"Skipping empty article: {filepath.name}")
            continue

        title = frontmatter.get("title", filepath.stem)
        chunks = chunk_by_sections(body)

        if not chunks:
            logger.warning(f"No chunks from {filepath.name}")
            continue

        for idx, chunk in enumerate(chunks):
            embedding_text = build_embedding_text(title, category, chunk)
            chunk["_embedding_text"] = embedding_text

            payload = build_payload(frontmatter, category, chunk, idx, len(chunks), filepath)
            payload["metadata"]["indexed_at"] = indexed_at

            point_id = deterministic_uuid(title, idx)

            all_points.append(
                {
                    "id": point_id,
                    "payload": payload,
                    "_text_to_embed": embedding_text,  # temporary, removed before upsert
                },
            )

        stats["articles"] += 1
        stats["chunks"] += len(chunks)

    logger.info(f"Parsed {stats['articles']} articles -> {stats['chunks']} chunks")

    if args.dry_run:
        logger.info("DRY RUN — showing sample chunks:")
        for p in all_points[:3]:
            logger.info(f"  ID: {p['id']}")
            logger.info(f"  Title: {p['payload']['metadata']['title'][:80]}")
            logger.info(f"  Category: {p['payload']['metadata']['category']}")
            logger.info(
                f"  Chunk: {p['payload']['metadata']['chunk_index']}/{p['payload']['metadata']['total_chunks']}",
            )
            logger.info(f"  Text preview: {p['_text_to_embed'][:150]}...")
            logger.info("")
        logger.info(f"Would upsert {len(all_points)} points to {COLLECTION_NAME}")
        return

    # Embed all texts
    from openai import AsyncOpenAI

    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        logger.error("OPENAI_API_KEY not set")
        sys.exit(1)

    client = AsyncOpenAI(api_key=openai_key)

    texts_to_embed = [p["_text_to_embed"] for p in all_points]
    logger.info(f"Embedding {len(texts_to_embed)} chunks with {EMBEDDING_MODEL}...")

    embeddings = await embed_texts(texts_to_embed, client)
    logger.info(f"Got {len(embeddings)} embeddings (dims={len(embeddings[0])})")

    # Build final Qdrant points
    qdrant_points = []
    for point, embedding in zip(all_points, embeddings, strict=False):
        qdrant_points.append(
            {
                "id": point["id"],
                "vector": embedding,
                "payload": point["payload"],
            },
        )

    logger.info(f"Upserting {len(qdrant_points)} points to {COLLECTION_NAME}...")
    await upsert_to_qdrant(qdrant_points, qdrant_url, qdrant_api_key)

    logger.info(f"Done. {stats['articles']} articles, {stats['chunks']} chunks indexed.")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
