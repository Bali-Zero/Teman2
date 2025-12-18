import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "apps/backend-rag/backend"))

try:
    print("1. Testing VertexAIService import...")
    from services.vertex_ai_service import VertexAIService

    print("✅ VertexAIService imported successfully")
except ImportError as e:
    print(f"❌ Failed to import VertexAIService: {e}")
    sys.exit(1)

try:
    print("\n2. Testing LegalIngestionService import...")
    from services.legal_ingestion_service import LegalIngestionService

    print("✅ LegalIngestionService imported successfully")
except ImportError as e:
    print(f"❌ Failed to import LegalIngestionService: {e}")
    sys.exit(1)

try:
    print("\n3. Testing IntelligentRouter import...")
    from services.intelligent_router import IntelligentRouter

    print("✅ IntelligentRouter imported successfully")
except ImportError as e:
    print(f"❌ Failed to import IntelligentRouter: {e}")
    sys.exit(1)

try:
    print("\n4. Testing RAGManager import...")
    from services.context.rag_manager import RAGManager

    print("✅ RAGManager imported successfully")
except ImportError as e:
    print(f"❌ Failed to import RAGManager: {e}")
    sys.exit(1)

try:
    print("\n5. Testing ContextBuilder import...")
    from services.context.context_builder import ContextBuilder

    cb = ContextBuilder()
    if hasattr(cb, "build_synthetic_context"):
        print("✅ ContextBuilder has build_synthetic_context method")
    else:
        print("❌ ContextBuilder missing build_synthetic_context method")
        sys.exit(1)
except ImportError as e:
    print(f"❌ Failed to import ContextBuilder: {e}")
    sys.exit(1)

print("\n🎉 All checks passed! The Data Strategy infrastructure is ready.")
