# 🔮 PARTE 1: Oracle Service (RAG Core)

> Il cuore del sistema RAG di Nuzantara

---

## Overview

**Location:** `backend/services/oracle/`

L'Oracle Service è il cervello di Nuzantara. Riceve query utente, capisce l'intento, recupera contesto rilevante, e genera risposte intelligenti.

---

## Architettura

```
Query Utente
     │
     ▼
┌─────────────────┐
│  OracleService  │ ← Entry point principale
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────────┐ ┌───────────────┐
│  Intent   │ │   Language    │
│Classifier │ │   Detector    │
└─────┬─────┘ └───────┬───────┘
      │               │
      ▼               ▼
┌──────────────────────────────┐
│     Routing Decision         │
│  (GoldenRouterService)       │
└─────────────┬────────────────┘
              │
     ┌────────┴────────┐
     ▼                 ▼
┌─────────┐      ┌──────────┐
│ Search  │      │  Memory  │
│(Qdrant) │      │Orchestr. │
└────┬────┘      └────┬─────┘
     │                │
     └───────┬────────┘
             ▼
┌──────────────────────────────┐
│     ReasoningEngine          │
│      (Gemini LLM)            │
└─────────────┬────────────────┘
              │
              ▼
┌──────────────────────────────┐
│    Response Validator        │
└──────────────────────────────┘
```

---

## Sub-Services

### 1. LanguageDetectionService
**File:** `oracle/language_detector.py`

```python
class LanguageDetectionService:
    """
    Detecta lingua della query:
    - Italian
    - English  
    - Indonesian
    - Mixed
    
    Usa pattern matching + langdetect library
    """
    
    def detect_language(self, query: str) -> str:
        # Pattern per indonesiano
        indonesian_patterns = ["apa", "bagaimana", "mengapa", "saya"]
        # Pattern per italiano
        italian_patterns = ["come", "cosa", "perché", "quanto"]
        # ...
```

### 2. UserContextService
**File:** `oracle/user_context.py`

```python
class UserContextService:
    """
    Recupera contesto utente:
    - Profilo utente
    - Memoria a lungo termine
    - Preferenze comunicazione
    - Storico conversazioni
    """
    
    async def get_user_context(self, user_id: str) -> UserContext:
        memory_facts = await self.memory_service.get_facts(user_id)
        personality = await self.personality_service.get(user_id)
        return UserContext(facts=memory_facts, personality=personality)
```

### 3. ReasoningEngineService
**File:** `oracle/reasoning_engine.py`

```python
class ReasoningEngineService:
    """
    Cuore del reasoning con Gemini:
    
    1. Costruisce prompt con contesto
    2. Chiama Gemini
    3. Valida risposta
    4. Estrae citazioni
    """
    
    async def reason_with_gemini(
        self,
        documents: list[str],
        query: str,
        context: PromptContext,
        user_memory_facts: list[str] | None = None,
        conversation_history: list[dict] | None = None,
    ) -> dict:
        # Build prompt
        prompt = self.prompt_builder.build(
            query=query,
            context=context,
            documents=documents,
            memory_facts=user_memory_facts,
            history=conversation_history
        )
        
        # Call Gemini
        response = await self.gemini_client.generate(prompt)
        
        # Validate
        validated = self.response_validator.validate(response)
        
        return validated
```

### 4. DocumentRetrievalService
**File:** `oracle/document_retrieval.py`

```python
class DocumentRetrievalService:
    """
    Recupera documenti da:
    - Google Drive (PDF, DOCX)
    - Vector store (chunks)
    - Cache locale
    """
    
    def download_pdf_from_drive(self, filename: str) -> str | None:
        # Usa Google Drive API
        pass
    
    async def get_relevant_chunks(self, query_embedding, limit=10):
        # Search in Qdrant
        pass
```

### 5. OracleAnalyticsService
**File:** `oracle/analytics.py`

```python
class OracleAnalyticsService:
    """
    Traccia metriche Oracle:
    - Query hash (deduplication)
    - Response time
    - Token usage
    - User satisfaction
    """
```

---

## OracleService - Main Class

```python
class OracleService:
    def __init__(self):
        self.prompt_builder = ZantaraPromptBuilder(model_adapter=GeminiAdapter())
        self.intent_classifier = IntentClassifier()
        self.response_validator = ZantaraResponseValidator(...)
        
        # Sub-services
        self.language_service = LanguageDetectionService()
        self.user_context_service = UserContextService()
        self.reasoning_engine = ReasoningEngineService(...)
        self.document_service = DocumentRetrievalService()
        self.analytics_service = OracleAnalyticsService()
        
    async def process_query(
        self,
        query: str,
        user_id: str,
        session_id: str,
        history: list[dict] = None
    ) -> OracleResponse:
        """
        Main entry point per query processing.
        """
        # 1. Detect language
        language = self.language_service.detect_language(query)
        
        # 2. Classify intent
        intent = await self.intent_classifier.classify(query)
        
        # 3. Get user context
        user_context = await self.user_context_service.get_user_context(user_id)
        
        # 4. Route query
        route = await self.router.route(query, intent)
        
        # 5. Search relevant documents
        documents = await self.search_service.search(
            query=query,
            collection=route.collection,
            filters=route.filters
        )
        
        # 6. Reason with LLM
        response = await self.reasoning_engine.reason_with_gemini(
            documents=documents,
            query=query,
            context=PromptContext(
                language=language,
                intent=intent,
                user_context=user_context
            ),
            user_memory_facts=user_context.facts,
            conversation_history=history
        )
        
        # 7. Track analytics
        await self.analytics_service.track(query, response)
        
        return response
```

---

## Prompt Building

**File:** `backend/prompts/zantara_prompt_builder.py`

```python
class ZantaraPromptBuilder:
    """
    Costruisce prompt strutturati per Gemini.
    
    Template sections:
    1. System identity (ZANTARA persona)
    2. User context (memory, preferences)
    3. Retrieved documents
    4. Conversation history
    5. Current query
    6. Output format instructions
    """
    
    def build(self, query, context, documents, memory_facts, history):
        sections = []
        
        # Identity
        sections.append(self._build_identity(context.language))
        
        # Documents
        if documents:
            sections.append(self._build_documents_section(documents))
        
        # Memory
        if memory_facts:
            sections.append(self._build_memory_section(memory_facts))
        
        # History
        if history:
            sections.append(self._build_history_section(history))
        
        # Query
        sections.append(f"USER QUERY: {query}")
        
        return "\n\n".join(sections)
```

---

## Collections (Knowledge Bases)

Il sistema usa diverse collection Qdrant:

| Collection | Contenuto |
|------------|-----------|
| `visa_knowledge` | Info visti, permessi, KITAS |
| `business_knowledge` | PT, CV, company setup |
| `legal_knowledge` | Leggi indonesiane |
| `politics_knowledge` | News politica |
| `pricing_knowledge` | Prezzi servizi |
| `team_knowledge` | Info team interno |
| `client_memory` | Memoria per-client |

---

## Intent Classification

**File:** `services/classification/intent_classifier.py`

```python
class IntentClassifier:
    """
    Classifica intenti:
    - visa_inquiry (domande visti)
    - business_inquiry (domande business)
    - pricing_inquiry (domande prezzi)
    - general_chat (conversazione generica)
    - complaint (lamentele)
    - follow_up (follow-up precedenti)
    """
    
    async def classify(self, query: str) -> Intent:
        # Uses keyword matching + optional LLM classification
        pass
```

---

## Response Validation

**File:** `services/response/validator.py`

```python
class ZantaraResponseValidator:
    """
    Valida risposte LLM:
    - No hallucination (verifica citazioni)
    - Appropriate length
    - Language consistency
    - No sensitive info leakage
    - Format compliance
    """
    
    def validate(self, response: str) -> ValidatedResponse:
        # Check citations exist in documents
        # Check language matches
        # Check length limits
        # Check for PII leakage
        pass
```

---

## Agentic RAG

**File:** `services/rag/agentic/orchestrator.py`

Per query complesse, usa Agentic RAG:

```python
class AgenticRAGOrchestrator:
    """
    Multi-step reasoning per query complesse:
    
    1. Decompose query in sub-queries
    2. Execute each sub-query
    3. Synthesize results
    4. Verify coherence
    """
    
    async def process(self, query: str) -> CoreResult:
        # Step 1: Analyze complexity
        complexity = await self.analyze_complexity(query)
        
        if complexity.needs_decomposition:
            # Step 2: Break down
            sub_queries = await self.decompose(query)
            
            # Step 3: Execute in parallel
            results = await asyncio.gather(*[
                self.execute_subquery(sq) for sq in sub_queries
            ])
            
            # Step 4: Synthesize
            final = await self.synthesize(results, query)
            return final
        else:
            # Simple query - direct execution
            return await self.execute_simple(query)
```

---

## Key Dependencies

```python
# Core
from backend.core.qdrant_db import QdrantDB
from backend.core.embeddings import EmbeddingService

# LLM
from backend.llm.zantara_ai_client import ZantaraAIClient
from backend.llm.adapters.gemini import GeminiAdapter

# Memory
from backend.services.memory import MemoryOrchestrator

# Search
from backend.services.search.search_service import SearchService
from backend.services.search.citation_service import CitationService

# Routing
from backend.services.routing.golden_router_service import GoldenRouterService
```

---

## Config

**File:** `backend/config/communication_modes.yaml`

```yaml
modes:
  professional:
    tone: formal
    emoji_usage: minimal
    response_length: detailed
  
  friendly:
    tone: warm
    emoji_usage: moderate
    response_length: concise
  
  technical:
    tone: precise
    emoji_usage: none
    response_length: comprehensive
```

---

## Usage Example

```python
from backend.services.oracle import OracleService

oracle = OracleService()

response = await oracle.process_query(
    query="How much does a KITAS cost?",
    user_id="user_123",
    session_id="session_456",
    history=[
        {"role": "user", "content": "I want to work in Bali"},
        {"role": "assistant", "content": "Great! What type of work?"}
    ]
)

print(response.answer)
print(response.citations)
print(response.confidence)
```

---

*"The Oracle knows all" 🔮*
