# Piano Test Coverage >95%

**Stato Attuale:** 68.03% (19,874 linee coperte / 29,214 totali)
**Obiettivo:** 95% (27,753 linee coperte)
**Linee da Coprire:** ~7,879 linee aggiuntive

---

## Priorita 1: Alta Impatto (>100 linee mancanti)

### 1.1 RAG Agentic System (~900 linee)

| File | Linee Mancanti | Test da Creare |
|------|----------------|----------------|
| `services/rag/agentic/orchestrator.py` | 419 | `test_orchestrator_comprehensive.py` |
| `services/rag/agentic/tools.py` | 167 | `test_agentic_tools_comprehensive.py` |
| `services/rag/agentic/prompt_builder.py` | 131 | `test_prompt_builder_comprehensive.py` |
| `services/rag/agentic/pipeline.py` | 87 | `test_pipeline_comprehensive.py` |
| `services/rag/agentic/reasoning.py` | 62 | `test_reasoning_comprehensive.py` |
| `services/rag/agentic/llm_gateway.py` | 57 | `test_llm_gateway_comprehensive.py` |

**Test necessari per orchestrator.py:**
```python
# tests/unit/services/rag/agentic/test_orchestrator_comprehensive.py
class TestAgenticOrchestrator:
    - test_init_with_all_services
    - test_init_without_optional_services
    - test_stream_response_success
    - test_stream_response_with_history
    - test_stream_response_with_context
    - test_stream_response_error_handling
    - test_non_stream_response
    - test_tool_execution_flow
    - test_early_exit_optimization
    - test_intent_based_routing
    - test_followup_generation
    - test_metadata_emission
    - test_quota_exceeded_fallback
    - test_service_unavailable_handling
```

### 1.2 Knowledge Graph (~700 linee)

| File | Linee Mancanti | Test da Creare |
|------|----------------|----------------|
| `services/knowledge_graph/pipeline.py` | 214 | `test_kg_pipeline.py` |
| `services/knowledge_graph/extractor.py` | 178 | `test_kg_extractor.py` |
| `services/knowledge_graph/ontology.py` | 167 | `test_kg_ontology.py` |
| `services/knowledge_graph/coreference.py` | 145 | `test_kg_coreference.py` |

**Test necessari per pipeline.py:**
```python
# tests/unit/services/knowledge_graph/test_kg_pipeline.py
class TestKGPipeline:
    - test_init_with_db_pool
    - test_extract_entities_from_chunk
    - test_extract_relationships
    - test_persist_to_database
    - test_build_graph_from_chunks
    - test_incremental_extraction
    - test_batch_processing
    - test_error_handling_on_extraction
    - test_rate_limiting
```

### 1.3 App Routers (~1,200 linee)

| File | Linee Mancanti | Test da Creare |
|------|----------------|----------------|
| `app/routers/zoho_email.py` | 173 | `test_zoho_email_router.py` |
| `app/routers/debug.py` | 144 | `test_debug_router.py` |
| `app/routers/agentic_rag.py` | 137 | `test_agentic_rag_router.py` |
| `app/routers/autonomous_agents.py` | 129 | `test_autonomous_agents_router.py` |
| `app/routers/portal.py` | 126 | `test_portal_router.py` |
| `app/routers/conversations.py` | 106 | `test_conversations_router.py` |
| `app/routers/newsletter.py` | 100 | `test_newsletter_router.py` |
| `app/routers/analytics.py` | 81 | `test_analytics_router.py` |
| `app/routers/legal_ingest.py` | 71 | `test_legal_ingest_router.py` |
| `app/routers/portal_invite.py` | 71 | `test_portal_invite_router.py` |
| `app/routers/crm_portal_integration.py` | 68 | `test_crm_portal_integration_router.py` |
| `app/routers/feedback.py` | 63 | `test_feedback_router.py` |

### 1.4 Services Core (~800 linee)

| File | Linee Mancanti | Test da Creare |
|------|----------------|----------------|
| `app/streaming.py` | 175 | `test_streaming.py` |
| `services/integrations/zoho_oauth_service.py` | 148 | `test_zoho_oauth.py` |
| `services/monitoring/unified_health_service.py` | 148 | `test_unified_health.py` |
| `services/search/search_service.py` | 142 | `test_search_service_comprehensive.py` |
| `core/qdrant_db.py` | 140 | `test_qdrant_db_comprehensive.py` |
| `services/integrations/zoho_email_service.py` | 137 | `test_zoho_email_service.py` |
| `app/setup/service_initializer.py` | 132 | `test_service_initializer.py` |
| `services/portal/portal_service.py` | 131 | `test_portal_service.py` |

---

## Priorita 2: Media Impatto (50-100 linee mancanti)

### 2.1 Services Misc (~400 linee)

| File | Linee Mancanti | Test da Creare |
|------|----------------|----------------|
| `services/misc/migration_runner.py` | 123 | `test_migration_runner.py` |
| `self_healing/backend_agent.py` | 122 | `test_backend_agent.py` |
| `services/autonomous_agents/knowledge_graph_builder.py` | 114 | `test_kg_builder.py` |
| `services/misc/autonomous_scheduler.py` | 110 | `test_autonomous_scheduler.py` |
| `services/rag/kg_enhanced_retrieval.py` | 108 | `test_kg_enhanced_retrieval.py` |
| `services/rag/agent/tools.py` | 102 | `test_agent_tools.py` |

### 2.2 Memory & Analytics (~300 linee)

| File | Linee Mancanti | Test da Creare |
|------|----------------|----------------|
| `middleware/hybrid_auth.py` | 94 | `test_hybrid_auth.py` |
| `services/misc/personality_service.py` | 91 | `test_personality_service.py` |
| `agents/agents/conversation_trainer.py` | 91 | `test_conversation_trainer.py` |
| `services/memory/orchestrator.py` | 88 | `test_memory_orchestrator.py` |
| `core/legal/hierarchical_indexer.py` | 88 | `test_hierarchical_indexer.py` |
| `services/oracle/oracle_service.py` | 86 | `test_oracle_service.py` |
| `db/migration_base.py` | 86 | `test_migration_base.py` |

### 2.3 LLM & Client (~250 linee)

| File | Linee Mancanti | Test da Creare |
|------|----------------|----------------|
| `services/rag/agent/mcp_tool.py` | 82 | `test_mcp_tool.py` |
| `services/misc/work_session_service.py` | 80 | `test_work_session.py` |
| `services/oracle/oracle_database.py` | 78 | `test_oracle_database.py` |
| `llm/genai_client.py` | 77 | `test_genai_client.py` |
| `agents/services/kg_repository.py` | 73 | `test_kg_repository.py` |
| `llm/zantara_ai_client.py` | 64 | `test_zantara_ai_client.py` |

---

## Priorita 3: Bassa Impatto (20-50 linee mancanti)

### 3.1 CLI & Scripts (~200 linee)

| File | Linee Mancanti | Test da Creare |
|------|----------------|----------------|
| `cli/ingestion_cli.py` | 175 | `test_ingestion_cli.py` |
| `verify_*.py` (7 files) | ~150 | Skip (scripts di debug) |

### 3.2 Utilities (~150 linee)

| File | Linee Mancanti | Test da Creare |
|------|----------------|----------------|
| `services/misc/proactive_compliance_monitor.py` | 59 | `test_proactive_compliance.py` |
| `services/rag/agent/diagnostics_tool.py` | 57 | `test_diagnostics_tool.py` |
| `core/legal/quality_validators.py` | 56 | `test_quality_validators.py` |
| `services/portal/invite_service.py` | 55 | `test_invite_service.py` |
| `services/memory/collective_memory_service.py` | 53 | `test_collective_memory_comprehensive.py` |
| `services/misc/graph_service.py` | 51 | `test_graph_service.py` |

---

## Template Test File

```python
"""
Unit tests for {ModuleName}
Target: 100% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from {module_path} import {ClassName}


@pytest.fixture
def mock_dependencies():
    """Mock all external dependencies"""
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.database_url = "postgresql://test"
        yield mock_settings


class Test{ClassName}:
    """Tests for {ClassName}"""

    def test_init(self, mock_dependencies):
        """Test initialization"""
        instance = {ClassName}()
        assert instance is not None

    @pytest.mark.asyncio
    async def test_main_method(self, mock_dependencies):
        """Test main functionality"""
        instance = {ClassName}()
        result = await instance.main_method()
        assert result is not None

    def test_error_handling(self, mock_dependencies):
        """Test error scenarios"""
        with pytest.raises(ValueError):
            {ClassName}(invalid_param=True)
```

---

## Stima Effort

| Priorita | Linee da Coprire | File Test | Ore Stimate |
|----------|------------------|-----------|-------------|
| P1 - Alta | ~3,600 | 25 files | 50-60 ore |
| P2 - Media | ~1,500 | 15 files | 25-30 ore |
| P3 - Bassa | ~800 | 10 files | 15-20 ore |
| **Totale** | **~5,900** | **50 files** | **90-110 ore** |

---

## Ordine di Esecuzione Consigliato

1. **Settimana 1:** RAG Agentic (orchestrator, tools, pipeline)
2. **Settimana 2:** Knowledge Graph (pipeline, extractor, ontology)
3. **Settimana 3:** App Routers (agentic_rag, conversations, portal)
4. **Settimana 4:** Core Services (search, qdrant_db, streaming)
5. **Settimana 5:** Memory & Analytics (orchestrator, collective_memory)
6. **Settimana 6:** LLM Clients (genai_client, zantara_ai_client)
7. **Settimana 7:** Integrations (zoho, portal, newsletter)
8. **Settimana 8:** Utilities & Cleanup

---

## Note

- I file `verify_*.py` sono script di debug e possono essere esclusi dalla coverage
- I file `test_*_comprehensive.py` esistenti vanno aggiornati per nuove API
- Usare `@pytest.mark.skip` per test che richiedono servizi esterni
- Mock tutti i servizi esterni (Qdrant, PostgreSQL, Redis, OpenAI, Gemini)
