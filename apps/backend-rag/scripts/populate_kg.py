"""
Populate Knowledge Graph Script
===============================

This script populates the Knowledge Graph (kg_entities, kg_relationships)
by processing documents stored in the 'parent_documents' table.

It uses the GraphExtractor service (Gemini) to extract entities and relationships.

Usage:
    python scripts/populate_kg.py --limit 50
"""

import asyncio
import logging
import os
import sys
import argparse
from typing import List

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../backend"))

import asyncpg
from app.core.config import settings
from llm.zantara_ai_client import ZantaraAIClient
from services.graph_extractor import GraphExtractor
from services.graph_service import GraphService, GraphEntity, GraphRelation

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def process_document(row, extractor: GraphExtractor, graph_service: GraphService):
    """Process a single document row from parent_documents"""
    doc_id = row['document_id']
    title = row['title']
    full_text = row['full_text']
    
    logger.info(f"Processing document: {title} ({doc_id})")
    
    # Extract graph
    try:
        graph_data = await extractor.extract_from_text(full_text, context=f"Title: {title}")
        
        # Save entities
        for entity in graph_data.entities:
            # Add source metadata
            entity_props = entity.get('properties', {})
            entity_props['source_document'] = doc_id
            
            graph_entity = GraphEntity(
                id=entity['id'],
                type=entity['type'],
                name=entity['name'],
                description=entity.get('description'),
                properties=entity_props
            )
            await graph_service.add_entity(graph_entity)
            
        # Save relations
        for rel in graph_data.relationships:
            graph_rel = GraphRelation(
                source_id=rel['source'],
                target_id=rel['target'],
                type=rel['type'],
                strength=rel.get('strength', 1.0),
                properties=rel.get('properties', {})
            )
            try:
                await graph_service.add_relation(graph_rel)
            except Exception as e:
                logger.warning(f"Failed to add relation {rel}: {e}")
                
        logger.info(f"✅ Extracted {len(graph_data.entities)} entities and {len(graph_data.relationships)} relations")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to process {doc_id}: {e}")
        return False

async def main():
    parser = argparse.ArgumentParser(description="Populate Knowledge Graph")
    parser.add_argument("--limit", type=int, default=10, help="Number of documents to process")
    args = parser.parse_args()

    if not settings.database_url:
        logger.error("DATABASE_URL not set")
        return

    logger.info("🔌 Connecting to database...")
    pool = await asyncpg.create_pool(settings.database_url)
    
    # Initialize services
    ai_client = ZantaraAIClient()
    extractor = GraphExtractor(ai_client)
    graph_service = GraphService(pool)
    
    try:
        async with pool.acquire() as conn:
            # Fetch documents
            # Prefer 'parent_documents' as source of truth
            rows = await conn.fetch(
                "SELECT document_id, title, full_text FROM parent_documents LIMIT $1",
                args.limit
            )
            
            if not rows:
                logger.warning("⚠️ No documents found in 'parent_documents'. Is the table populated?")
                return

            logger.info(f"📚 Found {len(rows)} documents to process")
            
            # Process in parallel (batches of 5)
            batch_size = 5
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i+batch_size]
                tasks = [process_document(row, extractor, graph_service) for row in batch]
                await asyncio.gather(*tasks)
                logger.info(f"Processed batch {i//batch_size + 1}")

    finally:
        await pool.close()
        logger.info("👋 Done")

if __name__ == "__main__":
    asyncio.run(main())
