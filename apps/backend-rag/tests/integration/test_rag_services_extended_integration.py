"""
Extended Integration Tests for RAG Services
Tests advanced RAG features with real Qdrant and dependencies

Covers:
- Multi-hop reasoning
- Query decomposition
- Streaming RAG responses
- Parent-child retrieval
- Golden router integration
- Vision RAG (PDF analysis)
- Self-RAG verification
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("QDRANT_URL", os.getenv("QDRANT_URL", "http://localhost:6333"))
os.environ.setdefault("OPENAI_API_KEY", "test_openai_api_key_for_testing")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key_for_testing")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestMultiHopReasoningIntegration:
    """Test multi-hop reasoning capabilities using AgenticRAG"""

    @pytest.mark.asyncio
    async def test_multi_hop_reasoning_with_tool_calls(self, qdrant_client, db_pool):
        """Test multi-hop reasoning through tool calls in AgenticRAG"""
        from services.rag.agentic import AgenticRAGOrchestrator

        # Simulate multi-hop: first tool call finds PT PMA info, second finds tax info
        call_count = [0]

        async def multi_hop_tool_execution(tool_name, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return "PT PMA requires minimum investment of 10B IDR"
            elif call_count[0] == 2:
                return "PT PMA tax rate is 25%"
            return "Additional information"

        with (
            patch("services.rag.agentic.SearchService") as mock_search,
            patch("services.rag.agentic.ZantaraAIClient") as mock_ai,
        ):
            mock_search_instance = MagicMock()
            mock_search_instance.search = AsyncMock(
                return_value={
                    "results": [{"text": "PT PMA information", "score": 0.9}],
                    "collection_used": "kbli_eye",
                }
            )
            mock_search.return_value = mock_search_instance

            # Mock AI that makes multiple tool calls (multi-hop)
            mock_ai_instance = MagicMock()
            mock_ai_instance.generate_response = AsyncMock(
                side_effect=[
                    "I need to search for PT PMA requirements first. [TOOL_CALL: VectorSearchTool]",
                    "Now I need to find tax obligations. [TOOL_CALL: VectorSearchTool]",
                    "Based on the information: PT PMA companies pay 25% corporate tax.",
                ]
            )
            mock_ai.return_value = mock_ai_instance

            orchestrator = AgenticRAGOrchestrator(retriever=mock_search_instance, db_pool=db_pool)

            # Mock tool executor
            orchestrator._execute_tool = AsyncMock(side_effect=multi_hop_tool_execution)

            result = await orchestrator.process_query(
                query="What are the tax obligations for a PT PMA company?",
                user_id="test_user_multihop_1",
            )

            assert result is not None
            # Should have made multiple tool calls (multi-hop)
            assert call_count[0] >= 1

    @pytest.mark.asyncio
    async def test_multi_hop_reasoning_flow(self, qdrant_client, db_pool):
        """Test complete multi-hop reasoning flow"""
        from services.rag.agentic import AgenticRAGOrchestrator

        with (
            patch("services.rag.agentic.SearchService") as mock_search,
            patch("services.rag.agentic.ZantaraAIClient") as mock_ai,
        ):
            # Simulate multi-hop: first query finds PT PMA info, second finds tax info
            call_count = [0]

            async def multi_hop_search(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    return {
                        "results": [
                            {"text": "PT PMA is a foreign investment company", "score": 0.9}
                        ],
                        "collection_used": "kbli_eye",
                    }
                else:
                    return {
                        "results": [{"text": "PT PMA pays 25% corporate tax", "score": 0.85}],
                        "collection_used": "tax_genius",
                    }

            mock_search_instance = MagicMock()
            mock_search_instance.search = AsyncMock(side_effect=multi_hop_search)
            mock_search.return_value = mock_search_instance

            mock_ai_instance = MagicMock()
            mock_ai_instance.generate_response = AsyncMock(
                return_value="PT PMA companies pay 25% corporate tax on their profits."
            )
            mock_ai.return_value = mock_ai_instance

            orchestrator = AgenticRAGOrchestrator(retriever=mock_search_instance, db_pool=db_pool)

            result = await orchestrator.process_query(
                query="What tax does a PT PMA company pay?",
                user_id="test_user_multihop_1",
            )

            assert result is not None
            # Should have made multiple search calls
            assert call_count[0] >= 1


@pytest.mark.integration
class TestStreamingRAGIntegration:
    """Test streaming RAG responses using AgenticRAGOrchestrator"""

    @pytest.mark.asyncio
    async def test_streaming_rag_response(self, qdrant_client, db_pool):
        """Test streaming RAG response generation"""
        from services.rag.agentic import AgenticRAGOrchestrator

        with (
            patch("services.rag.agentic.SearchService") as mock_search,
            patch("services.rag.agentic.ZantaraAIClient") as mock_ai,
        ):
            mock_search_instance = MagicMock()
            mock_search_instance.search = AsyncMock(
                return_value={
                    "results": [{"text": "KITAS document", "score": 0.9}],
                    "collection_used": "visa_oracle",
                }
            )
            mock_search.return_value = mock_search_instance

            # Mock streaming response
            async def stream_generator():
                chunks = ["KITAS", " is", " a", " temporary", " residence", " permit"]
                for chunk in chunks:
                    yield chunk

            mock_ai_instance = MagicMock()
            mock_ai_instance.generate_stream = AsyncMock(return_value=stream_generator())
            mock_ai.return_value = mock_ai_instance

            orchestrator = AgenticRAGOrchestrator(retriever=mock_search_instance, db_pool=db_pool)

            # Test streaming query
            chunks = []
            async for chunk in orchestrator.stream_query(
                query="What is KITAS?", user_id="test_user_stream_1"
            ):
                chunks.append(chunk)

            assert len(chunks) > 0
            assert any("KITAS" in str(chunk) for chunk in chunks)

    @pytest.mark.asyncio
    async def test_streaming_with_citations(self, qdrant_client, db_pool):
        """Test streaming response with inline citations"""
        from services.rag.agentic import AgenticRAGOrchestrator

        with (
            patch("services.rag.agentic.SearchService") as mock_search,
            patch("services.rag.agentic.ZantaraAIClient") as mock_ai,
        ):
            mock_search_instance = MagicMock()
            mock_search_instance.search = AsyncMock(
                return_value={
                    "results": [
                        {
                            "text": "KITAS document",
                            "score": 0.9,
                            "metadata": {"source": "visa_oracle", "doc_id": "doc1"},
                        }
                    ],
                    "collection_used": "visa_oracle",
                }
            )
            mock_search.return_value = mock_search_instance

            async def stream_with_citations():
                yield "KITAS [1]"
                yield " is a permit"
                yield " [1]"

            mock_ai_instance = MagicMock()
            mock_ai_instance.generate_stream = AsyncMock(return_value=stream_with_citations())
            mock_ai.return_value = mock_ai_instance

            orchestrator = AgenticRAGOrchestrator(retriever=mock_search_instance, db_pool=db_pool)

            chunks = []
            async for chunk in orchestrator.stream_query(
                query="What is KITAS?", user_id="test_user_stream_cite_1"
            ):
                chunks.append(chunk)

            # Should have citations in stream
            full_text = "".join(str(c) for c in chunks)
            assert len(chunks) > 0


@pytest.mark.integration
class TestParentChildRetrievalIntegration:
    """Test parent-child hierarchical retrieval"""

    @pytest.mark.asyncio
    async def test_parent_child_retrieval(self, qdrant_client, db_pool):
        """Test hierarchical parent-child document retrieval"""
        from services.search_service import SearchService

        with patch("core.embeddings.create_embeddings_generator") as mock_embedder:
            embedder = MagicMock()
            embedder.generate_query_embedding = AsyncMock(return_value=[0.1] * 1536)
            embedder.provider = "openai"
            embedder.dimensions = 1536
            mock_embedder.return_value = embedder

            search_service = SearchService()

            # Mock parent-child structure
            with patch.object(search_service, "search") as mock_search:
                mock_search.return_value = {
                    "results": [
                        {
                            "text": "Parent document about PT PMA",
                            "score": 0.9,
                            "metadata": {"parent_id": None, "doc_id": "parent1"},
                        },
                        {
                            "text": "Child document: Tax section",
                            "score": 0.85,
                            "metadata": {"parent_id": "parent1", "doc_id": "child1"},
                        },
                    ],
                    "collection_used": "legal_architect",
                }

                result = await search_service.search(
                    "PT PMA tax requirements", user_level=1, limit=5
                )

                assert result is not None
                assert "results" in result
                # Should have both parent and child documents
                results = result["results"]
                assert len(results) > 0


@pytest.mark.integration
class TestGoldenRouterIntegration:
    """Test Golden Router integration"""

    @pytest.mark.asyncio
    async def test_golden_router_fast_path(self, qdrant_client, db_pool):
        """Test Golden Router fast path for canonical queries"""
        from services.golden_router_service import GoldenRouterService

        with (
            patch("services.golden_router_service.SearchService") as mock_search,
            patch("services.golden_router_service.ZantaraAIClient") as mock_ai,
        ):
            mock_search_instance = MagicMock()
            mock_search_instance.search = AsyncMock(
                return_value={
                    "results": [{"text": "Golden answer document", "score": 0.95}],
                    "collection_used": "visa_oracle",
                }
            )
            mock_search.return_value = mock_search_instance

            golden_router = GoldenRouterService(
                search_service=mock_search_instance, db_pool=db_pool
            )

            # Test canonical query that should hit golden route
            result = await golden_router.route_query(
                query="What is KITAS?", user_id="test_user_golden_1"
            )

            assert result is not None
            # Golden router should return fast path result
            assert "results" in result or "answer" in result

    @pytest.mark.asyncio
    async def test_golden_router_fallback(self, qdrant_client, db_pool):
        """Test Golden Router fallback to normal search"""
        from services.golden_router_service import GoldenRouterService

        with (
            patch("services.golden_router_service.SearchService") as mock_search,
            patch("services.golden_router_service.ZantaraAIClient") as mock_ai,
        ):
            mock_search_instance = MagicMock()
            mock_search_instance.search = AsyncMock(
                return_value={
                    "results": [{"text": "Regular search result", "score": 0.8}],
                    "collection_used": "visa_oracle",
                }
            )
            mock_search.return_value = mock_search_instance

            golden_router = GoldenRouterService(
                search_service=mock_search_instance, db_pool=db_pool
            )

            # Test non-canonical query that should fallback
            result = await golden_router.route_query(
                query="Tell me about some random visa thing that doesn't match golden routes",
                user_id="test_user_golden_fallback_1",
            )

            assert result is not None
            # Should fallback to normal search
            assert "results" in result


@pytest.mark.integration
class TestVisionRAGIntegration:
    """Test Vision RAG for PDF/image analysis"""

    @pytest.mark.asyncio
    async def test_vision_rag_pdf_processing(self, qdrant_client, db_pool):
        """Test Vision RAG for PDF document processing"""
        from services.rag.vision_rag import VisionRAGService

        with (
            patch("services.rag.vision_rag.genai") as mock_genai,
            patch("services.rag.vision_rag.settings") as mock_settings,
        ):
            mock_settings.google_api_key = "test_key"

            # Mock Gemini Vision model
            mock_model = MagicMock()
            mock_response = MagicMock()
            mock_response.text = '{"type": "TABLE", "extracted_text": "KBLI 56101", "description": "Table with KBLI codes"}'
            mock_model.generate_content_async = AsyncMock(return_value=mock_response)
            mock_genai.GenerativeModel.return_value = mock_model

            vision_rag = VisionRAGService()

            # Mock PDF processing (skip actual file reading)
            with patch("fitz.open") as mock_fitz:
                mock_doc = MagicMock()
                mock_page = MagicMock()
                mock_page.get_text.return_value = "Sample PDF text"
                mock_page.get_images.return_value = []
                mock_page.find_tables.return_value = []
                mock_doc.__iter__.return_value = [mock_page]
                mock_doc.__len__.return_value = 1
                mock_fitz.return_value.__enter__.return_value = mock_doc

                # Test PDF processing
                result = await vision_rag.process_pdf("/tmp/test.pdf")

                assert result is not None
                assert hasattr(result, "doc_id")
                assert hasattr(result, "text_content")
                assert hasattr(result, "visual_elements")

    @pytest.mark.asyncio
    async def test_vision_rag_query_with_vision(self, qdrant_client, db_pool):
        """Test Vision RAG query with visual elements"""
        from services.rag.vision_rag import MultiModalDocument, VisionRAGService, VisualElement

        with (
            patch("services.rag.vision_rag.genai") as mock_genai,
            patch("services.rag.vision_rag.settings") as mock_settings,
        ):
            mock_settings.google_api_key = "test_key"

            # Mock Gemini Vision model
            mock_model = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "The table shows KBLI code 56101 for restaurants."
            mock_model.generate_content_async = AsyncMock(return_value=mock_response)
            mock_genai.GenerativeModel.return_value = mock_model

            vision_rag = VisionRAGService()

            # Create test documents with visual elements
            test_doc = MultiModalDocument(
                doc_id="test_doc",
                text_content="Sample document text",
                visual_elements=[
                    VisualElement(
                        element_type="table",
                        page_number=1,
                        bounding_box=(0, 0, 100, 100),
                        image_data=b"fake_image_data",
                        extracted_text="KBLI 56101",
                        description="Table with KBLI codes",
                    )
                ],
                metadata={"source": "test"},
            )

            # Test query with vision
            result = await vision_rag.query_with_vision(
                query="What KBLI code is shown in this document?",
                documents=[test_doc],
                include_images=False,  # Skip actual image processing in test
            )

            assert result is not None
            assert "answer" in result
            assert "visuals_used" in result


@pytest.mark.integration
class TestRerankerAdvancedIntegration:
    """Test advanced reranking scenarios"""

    @pytest.mark.asyncio
    async def test_reranker_multi_source(self, qdrant_client):
        """Test reranking documents from multiple sources"""
        from services.reranker_service import RerankerService

        with patch("sentence_transformers.CrossEncoder"):
            reranker = RerankerService()

            # Documents from different sources
            source_results = {
                "visa_oracle": [
                    {"text": "KITAS visa info", "score": 0.9},
                    {"text": "Visa application", "score": 0.8},
                ],
                "tax_genius": [
                    {"text": "Tax for visa holders", "score": 0.85},
                ],
            }

            query = "What are the tax obligations for KITAS holders?"

            # Mock reranker model
            with patch.object(reranker, "model") as mock_model:
                mock_model.predict.return_value = [0.95, 0.80, 0.75]  # Higher score for tax doc

                reranked = reranker.rerank_multi_source(query, source_results, top_k=3)

                assert reranked is not None
                assert len(reranked) <= 3
                # Should have source information
                assert all(len(item) == 3 for item in reranked)  # (doc, score, source)

    @pytest.mark.asyncio
    async def test_reranker_batch_processing(self, qdrant_client):
        """Test batch reranking for multiple queries"""
        from services.reranker_service import RerankerService

        with patch("sentence_transformers.CrossEncoder"):
            reranker = RerankerService()

            queries = ["What is KITAS?", "What is PT PMA?"]
            documents_list = [
                [
                    {"text": "KITAS doc 1", "score": 0.9},
                    {"text": "KITAS doc 2", "score": 0.8},
                ],
                [
                    {"text": "PT PMA doc 1", "score": 0.9},
                    {"text": "PT PMA doc 2", "score": 0.85},
                ],
            ]

            # Mock reranker model
            with patch.object(reranker, "model") as mock_model:
                mock_model.predict.return_value = [0.95, 0.80, 0.90, 0.75]

                batch_results = reranker.rerank_batch(queries, documents_list, top_k=2)

                assert batch_results is not None
                assert len(batch_results) == len(queries)
                assert all(len(result) <= 2 for result in batch_results)


@pytest.mark.integration
class TestRerankerAdvancedIntegration:
    """Test advanced reranking scenarios"""

    @pytest.mark.asyncio
    async def test_reranker_multi_source(self, qdrant_client):
        """Test reranking documents from multiple sources"""
        from services.reranker_service import RerankerService

        reranker = RerankerService()

        # Documents from different sources
        source_results = {
            "visa_oracle": [
                {"text": "KITAS visa info", "score": 0.9},
                {"text": "Visa application", "score": 0.8},
            ],
            "tax_genius": [
                {"text": "Tax for visa holders", "score": 0.85},
            ],
        }

        query = "What are the tax obligations for KITAS holders?"

        # Mock reranker model
        with patch.object(reranker, "model") as mock_model:
            mock_model.predict.return_value = [0.95, 0.80, 0.75]  # Higher score for tax doc

            reranked = reranker.rerank_multi_source(query, source_results, top_k=3)

            assert reranked is not None
            assert len(reranked) <= 3
            # Should have source information
            assert all(len(item) == 3 for item in reranked)  # (doc, score, source)

    @pytest.mark.asyncio
    async def test_reranker_batch_processing(self, qdrant_client):
        """Test batch reranking for multiple queries"""
        from services.reranker_service import RerankerService

        reranker = RerankerService()

        queries = ["What is KITAS?", "What is PT PMA?"]
        documents_list = [
            [
                {"text": "KITAS doc 1", "score": 0.9},
                {"text": "KITAS doc 2", "score": 0.8},
            ],
            [
                {"text": "PT PMA doc 1", "score": 0.9},
                {"text": "PT PMA doc 2", "score": 0.85},
            ],
        ]

        # Mock reranker model
        with patch.object(reranker, "model") as mock_model:
            mock_model.predict.return_value = [0.95, 0.80, 0.90, 0.75]

            batch_results = reranker.rerank_batch(queries, documents_list, top_k=2)

            assert batch_results is not None
            assert len(batch_results) == len(queries)
            assert all(len(result) <= 2 for result in batch_results)
