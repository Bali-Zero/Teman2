#!/bin/bash
# Fix remaining wildcard imports in test files

cd "$(dirname "$0")/.."

# Fix test_vertex.py
sed -i '' 's/from llm.providers.vertex import \*/from llm.providers.vertex import VertexProvider/g' apps/backend-rag/backend/tests/unit/llm/providers/test_vertex.py

# Fix test_deepseek.py  
sed -i '' 's/from llm.providers.deepseek import \*/from llm.providers.deepseek import DeepSeekProvider/g' apps/backend-rag/backend/tests/unit/llm/providers/test_deepseek.py

# Fix test_gemini.py
sed -i '' 's/from llm.adapters.gemini import \*/from llm.adapters.gemini import GeminiAdapter/g' apps/backend-rag/backend/tests/unit/llm/adapters/test_gemini.py

# Fix test_base.py (adapters)
sed -i '' 's/from llm.adapters.base import \*/from llm.adapters.base import BaseAdapter/g' apps/backend-rag/backend/tests/unit/llm/adapters/test_base.py

echo "✅ Fixed wildcard imports in test files"
