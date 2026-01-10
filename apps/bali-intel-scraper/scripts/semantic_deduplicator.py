#!/usr/bin/env python3
"""
SEMANTIC DEDUPLICATOR
=====================
Gestisce la deduplicazione semantica usando Qdrant.
Confronta il SIGNIFICATO delle news, non solo le parole chiave.

Flow:
1. Genera embedding (vettore) del titolo + sommario
2. Cerca in Qdrant nella collezione 'balizero_news_history'
3. Filtra per data (ultimi X giorni)
4. Se similarità > THRESHOLD (es. 0.85) -> è un duplicato
"""

import os
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from loguru import logger
from qdrant_client import QdrantClient, models
from openai import AsyncOpenAI

# Configurazione
COLLECTION_NAME = "balizero_news_history"
SIMILARITY_THRESHOLD = 0.88  # 88% identico = duplicato sicuro
SEARCH_WINDOW_DAYS = 5       # Controlla solo news recenti
EMBEDDING_MODEL = "text-embedding-3-small"

class SemanticDeduplicator:
    def __init__(self):
        # Setup Qdrant
        self.qdrant_url = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
        self.qdrant_key = os.getenv("QDRANT_API_KEY")
        self.qdrant = QdrantClient(url=self.qdrant_url, api_key=self.qdrant_key)
        
        # Setup OpenAI (per embedding)
        self.openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        logger.info(f"🧠 Semantic Deduplicator initialized (Threshold: {SIMILARITY_THRESHOLD})")

    async def _get_embedding(self, text: str) -> list[float]:
        """Genera embedding vettoriale per il testo"""
        try:
            # Pulisci e tronca testo se troppo lungo
            text = text[:8000]
            response = await self.openai.embeddings.create(
                input=text,
                model=EMBEDDING_MODEL
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Errore generazione embedding: {e}")
            return []

    def _generate_id(self, url: str) -> str:
        """Genera ID deterministico basato su URL (UUID format)"""
        import uuid
        hash_val = hashlib.md5(url.encode()).hexdigest()
        return str(uuid.UUID(hash_val))

    async def is_duplicate(self, title: str, summary: str, url: str) -> Tuple[bool, str, float]:
        """
        Verifica se la notizia esiste già semanticamente.
        Returns: (is_duplicate, original_title, similarity_score)
        """
        # 1. Check rapido URL esatto (Deduplicazione tecnica)
        try:
            doc_id = self._generate_id(url)
            points = self.qdrant.retrieve(
                collection_name=COLLECTION_NAME,
                ids=[doc_id]
            )
            if points:
                logger.info(f"🔄 Duplicato ESATTO trovato (URL match): {title[:50]}...")
                return True, points[0].payload.get("title", "Unknown"), 1.0
        except Exception as e:
            logger.warning(f"Errore check URL esatto: {e}")

        # 2. Check Semantico (Deduplicazione concettuale)
        try:
            # Combina titolo e sommario per contesto migliore
            query_text = f"{title}\n{summary}"
            vector = await self._get_embedding(query_text)
            
            if not vector:
                return False, "", 0.0

            # Filtro temporale (solo news recenti)
            cutoff_date = (datetime.utcnow() - timedelta(days=SEARCH_WINDOW_DAYS)).isoformat()
            
            # Cerca vettori simili
            search_result = self.qdrant.search(
                collection_name=COLLECTION_NAME,
                query_vector=vector,
                limit=1,
                query_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="published_at",
                            range=models.DatetimeRange(gte=cutoff_date)
                        )
                    ]
                ),
                with_payload=True
            )

            if search_result:
                best_match = search_result[0]
                if best_match.score >= SIMILARITY_THRESHOLD:
                    existing_title = best_match.payload.get("title", "Unknown")
                    logger.warning(
                        f"🧠 Duplicato SEMANTICO ({best_match.score:.2f}): "
                        f"'{title[:30]}...' ≈ '{existing_title[:30]}...'"
                    )
                    return True, existing_title, best_match.score

            return False, "", 0.0

        except Exception as e:
            logger.error(f"Errore check semantico: {e}")
            return False, "", 0.0

    async def save_article(self, article: Dict):
        """Salva l'articolo nella memoria storica"""
        try:
            title = article.get("title", "")
            summary = article.get("summary", "") or article.get("content", "")[:500]
            url = article.get("sourceUrl") or article.get("url", "")
            
            if not url or not title:
                return

            # Genera ID e Vettore
            doc_id = self._generate_id(url)
            text_to_embed = f"{title}\n{summary}"
            vector = await self._get_embedding(text_to_embed)
            
            if not vector:
                return

            # Prepara Payload
            payload = {
                "title": title,
                "summary": summary,
                "source_url": url,
                "source": article.get("source", "Unknown"),
                "category": article.get("category", "general"),
                "published_at": article.get("publishedAt") or datetime.utcnow().isoformat(),
                "tier": "T2", # Default tier
                "ingested_at": datetime.utcnow().isoformat()
            }

            # Upsert in Qdrant
            self.qdrant.upsert(
                collection_name=COLLECTION_NAME,
                points=[
                    models.PointStruct(
                        id=doc_id,
                        vector=vector,
                        payload=payload
                    )
                ]
            )
            logger.info(f"💾 Salvato in memoria news: {title[:50]}...")

        except Exception as e:
            logger.error(f"Errore salvataggio news: {e}")

# Test rapido
if __name__ == "__main__":
    async def test():
        dedup = SemanticDeduplicator()
        
        # Test Case
        title = "Bali Introduces New Tourist Tax"
        summary = "Foreign visitors must pay IDR 150,000 upon entry starting February."
        url = "https://example.com/bali-tax-test"
        
        # 1. Check
        is_dup, match, score = await dedup.is_duplicate(title, summary, url)
        print(f"Is duplicate? {is_dup} (Score: {score}) - Match: {match}")
        
        # 2. Save
        if not is_dup:
            await dedup.save_article({
                "title": title,
                "summary": summary,
                "sourceUrl": url,
                "source": "TestBot",
                "category": "immigration"
            })
            print("Saved.")
            
            # 3. Re-check (dovrebbe essere True ora)
            is_dup, match, score = await dedup.is_duplicate(title, summary, url)
            print(f"Re-check: Is duplicate? {is_dup} (Score: {score})")

    asyncio.run(test())
