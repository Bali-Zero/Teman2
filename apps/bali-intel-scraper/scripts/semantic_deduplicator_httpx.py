#!/usr/bin/env python3
"""
SEMANTIC DEDUPLICATOR usando httpx direttamente
Workaround per problema TLS con qdrant-client
"""
import os
import hashlib
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from loguru import logger
import httpx
from openai import AsyncOpenAI

# Configurazione
COLLECTION_NAME = "balizero_news_history"
SIMILARITY_THRESHOLD = 0.88
SEARCH_WINDOW_DAYS = 5
EMBEDDING_MODEL = "text-embedding-3-small"

class SemanticDeduplicator:
    def __init__(self):
        self.qdrant_url = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev").rstrip("/")
        self.qdrant_key = os.getenv("QDRANT_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")
        
        if not openai_key:
            logger.warning("⚠️ OPENAI_API_KEY not set - embedding generation will fail")
        
        self.openai = AsyncOpenAI(api_key=openai_key) if openai_key else None
        
        # HTTP client con configurazione ottimizzata
        # Usa context manager pattern per garantire cleanup
        self._http_client = None
        self._client_headers = {"api-key": self.qdrant_key} if self.qdrant_key else {}
        
        logger.info(f"🧠 Semantic Deduplicator initialized (Threshold: {SIMILARITY_THRESHOLD})")
    
    def _get_client(self) -> httpx.Client:
        """Get or create HTTP client (lazy initialization)"""
        if self._http_client is None:
            self._http_client = httpx.Client(
                timeout=30.0,
                headers=self._client_headers,
                http2=False  # Disabilita HTTP/2 per evitare problemi TLS
            )
        return self._http_client

    def _generate_id(self, url: str) -> str:
        """Genera ID deterministico basato su URL"""
        hash_val = hashlib.md5(url.encode()).hexdigest()
        return str(uuid.UUID(hash_val))

    async def _get_embedding(self, text: str) -> list[float]:
        """Genera embedding vettoriale per il testo"""
        if not self.openai:
            logger.error("OpenAI client not initialized - check OPENAI_API_KEY")
            return []
        
        try:
            text = text[:8000]
            response = await self.openai.embeddings.create(
                input=text,
                model=EMBEDDING_MODEL
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Errore generazione embedding: {e}")
            return []

    async def is_duplicate(self, title: str, summary: str, url: str) -> Tuple[bool, str, float]:
        """Verifica se la notizia esiste già semanticamente"""
        # 1. Check URL esatto
        try:
            doc_id = self._generate_id(url)
            client = self._get_client()
            response = client.get(
                f"{self.qdrant_url}/collections/{COLLECTION_NAME}/points/{doc_id}"
            )
            if response.status_code == 200:
                point = response.json()["result"]
                logger.info(f"🔄 Duplicato ESATTO trovato (URL match): {title[:50]}...")
                return True, point.get("payload", {}).get("title", "Unknown"), 1.0
        except httpx.HTTPStatusError:
            pass  # Point non trovato, continua
        except Exception as e:
            logger.warning(f"Errore check URL esatto: {e}")

        # 2. Check Semantico
        try:
            query_text = f"{title}\n{summary}"
            vector = await self._get_embedding(query_text)
            
            if not vector:
                return False, "", 0.0

            cutoff_date = (datetime.utcnow() - timedelta(days=SEARCH_WINDOW_DAYS)).isoformat()
            
            # Search usando API REST (specifica nome vettore per collezioni ibride)
            # Formato filtro corretto per Qdrant
            search_payload = {
                "vector": {
                    "name": "default",  # Nome del vettore denso nella collezione ibrida
                    "vector": vector
                },
                "limit": 1,
                "filter": {
                    "must": [
                        {
                            "key": "published_at",
                            "range": {
                                "gte": cutoff_date
                            }
                        }
                    ]
                },
                "with_payload": True,
                "score_threshold": SIMILARITY_THRESHOLD  # Filtra risultati sotto threshold
            }
            
            client = self._get_client()
            response = client.post(
                f"{self.qdrant_url}/collections/{COLLECTION_NAME}/points/search",
                json=search_payload
            )
            response.raise_for_status()
            
            results = response.json().get("result", [])
            if results:
                best_match = results[0]
                score = best_match.get("score", 0.0)
                if score >= SIMILARITY_THRESHOLD:
                    existing_title = best_match.get("payload", {}).get("title", "Unknown")
                    logger.warning(
                        f"🧠 Duplicato SEMANTICO ({score:.2f}): "
                        f"'{title[:30]}...' ≈ '{existing_title[:30]}...'"
                    )
                    return True, existing_title, score

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

            doc_id = self._generate_id(url)
            text_to_embed = f"{title}\n{summary}"
            vector = await self._get_embedding(text_to_embed)
            
            if not vector:
                return

            payload = {
                "title": title,
                "summary": summary,
                "source_url": url,
                "source": article.get("source", "Unknown"),
                "category": article.get("category", "general"),
                "published_at": article.get("publishedAt") or datetime.utcnow().isoformat(),
                "tier": "T2",
                "ingested_at": datetime.utcnow().isoformat()
            }

            # Upsert usando API REST
            # La collezione è ibrida con vettore "default", quindi specifica il nome
            upsert_payload = {
                "points": [
                    {
                        "id": doc_id,
                        "vector": {
                            "default": vector  # Specifica nome vettore per collezione ibrida
                        },
                        "payload": payload
                    }
                ]
            }
            
            # Upsert con wait=true per assicurare che sia completato
            client = self._get_client()
            response = client.put(
                f"{self.qdrant_url}/collections/{COLLECTION_NAME}/points",
                json=upsert_payload,
                params={"wait": "true"}  # Attendi completamento indicizzazione
            )
            
            if response.status_code != 200:
                error_text = response.text[:200] if hasattr(response, 'text') else str(response)
                logger.error(f"Errore upsert Qdrant {response.status_code}: {error_text}")
                # Non sollevare eccezione, permette alla pipeline di continuare
                return
            
            response.raise_for_status()
            logger.info(f"💾 Salvato in memoria news: {title[:50]}...")

        except Exception as e:
            logger.error(f"Errore salvataggio news: {e}")

    def close(self):
        """Explicitly close HTTP client"""
        if self._http_client:
            self._http_client.close()
            self._http_client = None
    
    def __del__(self):
        """Cleanup HTTP client (fallback)"""
        self.close()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
