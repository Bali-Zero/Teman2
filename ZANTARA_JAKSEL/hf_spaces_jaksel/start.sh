#!/bin/bash

echo "🚀 Starting Jaksel AI on Hugging Face Spaces..."

# Imposta environment variables
export OLLAMA_HOST=0.0.0.0
export HF_HOME=/data
export TRANSFORMERS_CACHE=/data/transformers_cache

# Assicura che la directory esista
mkdir -p /root/.ollama

# Avvia Ollama in background
echo "📥 Starting Ollama server..."
ollama serve --host 0.0.0.0 --port 11434 &
OLLAMA_PID=$!

# Attendi che Ollama sia avviato
echo "⏳ Waiting for Ollama to start..."
sleep 15

# Testa se Ollama è attivo
echo "🔍 Testing Ollama connection..."
if curl -s http://127.0.0.1:11434/api/version > /dev/null; then
    echo "✅ Ollama is running!"
else
    echo "❌ Ollama failed to start"
    exit 1
fi

# Pull Jaksel model ( se non già presente )
echo "🤖 Checking for Jaksel model..."
if ! ollama list | grep -q "zantara-jaksel"; then
    echo "📥 Pulling Jaksel model (this may take a few minutes)..."
    ollama pull zantara-jaksel:latest
    if [ $? -eq 0 ]; then
        echo "✅ Jaksel model loaded successfully!"
    else
        echo "⚠️ Model download failed, but continuing..."
    fi
else
    echo "✅ Jaksel model already exists!"
fi

# Script Python per il proxy server
python3 <<PYTHON
import subprocess
import time
import requests
from fastapi import FastAPI, Request, HTTPException
import uvicorn
import json
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Jaksel AI Proxy", version="1.0.0")

@app.get("/")
async def root():
    return {"message": "Jaksel AI is running!", "status": "healthy"}

@app.get("/health")
async def health():
    try:
        response = requests.get("http://127.0.0.1:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            jaksel_found = any("zantara-jaksel" in m.get("name", "") for m in models)
            return {
                "status": "healthy",
                "ollama": "connected",
                "jaksel_loaded": jaksel_found,
                "models": [m.get("name") for m in models]
            }
        else:
            return {"status": "unhealthy", "ollama": "error"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.post("/api/generate")
async def proxy_generate(request: Request):
    """Proxy per richieste generate a Ollama"""
    try:
        body = await request.json()

        # Log richiesta per debug
        logger.info(f"Received /api/generate request: model={body.get('model', 'unknown')}")

        ollama_url = "http://127.0.0.1:11434/api/generate"

        response = requests.post(
            ollama_url,
            json=body,
            timeout=120
        )

        return response.json()

    except Exception as e:
        logger.error(f"Error in /api/generate: {str(e)}")
        return {
            "error": f"Proxy error: {str(e)}",
            "response": "Maaf, Jaksel lagi nggak bisa merespon. Coba lagi ya!"
        }

@app.post("/api/chat")
async def proxy_chat(request: Request):
    """Proxy per richieste chat a Ollama"""
    try:
        body = await request.json()

        logger.info(f"Received /api/chat request: model={body.get('model', 'unknown')}")

        ollama_url = "http://127.0.0.1:11434/api/chat"

        response = requests.post(
            ollama_url,
            json=body,
            timeout=120,
            stream=body.get("stream", False)
        )

        if body.get("stream", False):
            return response.raw
        else:
            return response.json()

    except Exception as e:
        logger.error(f"Error in /api/chat: {str(e)}")
        return {
            "error": f"Proxy error: {str(e)}",
            "message": {"content": "Maaf, Jaksel lagi nggak bisa merespon. Coba lagi ya!"}
        }

logger.info("🌐 Starting proxy server on port 7860...")
uvicorn.run(app, host="0.0.0.0", port=7860)
PYTHON

# Keep the script running
wait $OLLAMA_PID