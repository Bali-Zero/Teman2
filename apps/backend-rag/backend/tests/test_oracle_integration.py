import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.routers.oracle_universal import hybrid_oracle_query, OracleQueryRequest
from prompts.zantara_prompt_builder import PromptContext

@pytest.mark.asyncio
async def test_hybrid_oracle_query_integration():
    # Mock dependencies
    mock_service = MagicMock()
    mock_service.router.get_routing_stats.return_value = {"selected_collection": "test_collection", "domain_scores": {}}
    mock_service.collections = {"test_collection": AsyncMock()}
    mock_service.collections["test_collection"].search.return_value = {
        "documents": ["Doc 1 content", "Doc 2 content"],
        "metadatas": [{"id": "1", "source": "test.pdf"}, {"id": "2", "source": "test2.pdf"}],
        "distances": [0.1, 0.2]
    }

    # Mock DB Manager
    with patch("backend.app.routers.oracle_universal.db_manager") as mock_db:
        mock_db.get_user_profile = AsyncMock(return_value={
            "id": "user123",
            "email": "test@example.com",
            "language": "en",
            "role": "admin",
            "role_level": "member",
            "name": "Test User"
        })
        mock_db.store_query_analytics = AsyncMock()

        # Mock Intent Classifier
        with patch("backend.app.routers.oracle_universal.intent_classifier") as mock_classifier:
            mock_classifier.classify_intent = AsyncMock(return_value={
                "intent": "legal_inquiry",
                "mode": "legal_brief",
                "confidence": 0.9
            })

            # Mock Google Services (Gemini)
            with patch("backend.app.routers.oracle_universal.google_services") as mock_google:
                mock_model = MagicMock()
                mock_response = MagicMock()
                mock_response.text = "This is a generated response."
                mock_model.generate_content.return_value = mock_response
                mock_google.get_gemini_model.return_value = mock_model

                # Mock Embeddings
                with patch("backend.core.embeddings.create_embeddings_generator") as mock_embedder_factory:
                    mock_embedder = MagicMock()
                    mock_embedder.generate_single_embedding.return_value = [0.1] * 768
                    mock_embedder_factory.return_value = mock_embedder

                    # Create Request
                    request = OracleQueryRequest(
                        query="What are the requirements for PT PMA?",
                        user_email="test@example.com",
                        use_ai=True
                    )

                    # Execute
                    response = await hybrid_oracle_query(request, service=mock_service)

                    # Verify
                    assert response.success is True
                    assert response.answer == "This is a generated response."
                    assert response.model_used == "gemini-2.5-flash"
                    
                    # Verify Intent Classifier was called
                    mock_classifier.classify_intent.assert_called_once_with("What are the requirements for PT PMA?")
                    
                    # Verify Gemini was called with correct config
                    mock_model.generate_content.assert_called_once()
                    call_args = mock_model.generate_content.call_args
                    assert call_args is not None
                    
                    # Check that contents list was passed (system prompt + user message)
                    contents = call_args[1]['contents']
                    assert len(contents) == 2
                    assert "Zantara" in contents[0] # System prompt should contain identity
                    assert "QUERY:" in contents[1] # User message

@pytest.mark.asyncio
async def test_reason_with_gemini_mode_handling():
    from app.routers.oracle_universal import reason_with_gemini
    
    # Mock Google Services
    with patch("backend.app.routers.oracle_universal.google_services") as mock_google:
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Legal response."
        mock_model.generate_content.return_value = mock_response
        mock_google.get_gemini_model.return_value = mock_model

        context = PromptContext(
            query="test",
            language="en",
            mode="legal_brief",
            emotional_state="neutral",
            user_name="Test"
        )

        result = await reason_with_gemini(
            documents=["doc1"],
            query="test",
            context=context
        )

        assert result["success"] is True
        assert result["mode_used"] == "legal_brief"
        
        # Check temperature for legal mode
        call_args = mock_model.generate_content.call_args
        gen_config = call_args[1]['generation_config']
        assert gen_config['temperature'] == 0.3
