#!/usr/bin/env python3
"""Test script to verify OpenAI API key is being read correctly"""

import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend-rag" / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

print("=" * 60)
print("🔍 VERIFICA CONFIGURAZIONE EMBEDDING")
print("=" * 60)

# Check environment variable
env_key = os.getenv("OPENAI_API_KEY")
print("\n1. OPENAI_API_KEY da environment:")
if env_key:
    print(f"   ✅ Presente: {env_key[:20]}...{env_key[-10:]}")
    print(f"   Lunghezza: {len(env_key)} caratteri")
else:
    print("   ❌ NON TROVATA")

# Check settings
try:
    from app.core.config import settings

    print("\n2. Settings da config.py:")
    print(f"   embedding_provider: {settings.embedding_provider}")
    print(
        f"   openai_api_key: {settings.openai_api_key[:20] if settings.openai_api_key else 'None'}..."
    )
    print(f"   embedding_model: {settings.embedding_model}")
except Exception as e:
    print(f"   ❌ Errore caricando settings: {e}")

# Test EmbeddingsGenerator initialization
print("\n3. Test EmbeddingsGenerator:")
try:
    from core.embeddings import EmbeddingsGenerator

    embedder = EmbeddingsGenerator()
    print("   ✅ Inizializzato con successo")
    print(f"   Provider: {embedder.provider}")
    print(f"   Model: {embedder.model}")
    if hasattr(embedder, "api_key"):
        if embedder.api_key:
            print(f"   ✅ API Key presente: {embedder.api_key[:20]}...")
        else:
            print("   ❌ API Key NON presente")
    else:
        print("   ℹ️  Provider locale (sentence-transformers), no API key needed")
except ValueError as e:
    print(f"   ❌ ValueError: {e}")
    print("   → Questo è il problema! API key mancante o non valida")
except Exception as e:
    print(f"   ❌ Errore: {e}")
    import traceback

    traceback.print_exc()

# Test actual embedding generation
print("\n4. Test generazione embedding:")
try:
    from core.embeddings import EmbeddingsGenerator

    embedder = EmbeddingsGenerator()
    test_embedding = embedder.generate_single_embedding("test query")
    print("   ✅ Embedding generato con successo")
    print(f"   Dimensione: {len(test_embedding)}")
except Exception as e:
    print(f"   ❌ Errore generando embedding: {e}")
    import traceback

    traceback.print_exc()

print("\n" + "=" * 60)
