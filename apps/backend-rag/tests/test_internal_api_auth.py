"""
Test Internal API Authentication
Verifies that protected endpoints require API key
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.main_cloud import app

client = TestClient(app)


class TestInternalAPIEndpoints:
    """Test that internal endpoints require API key authentication"""

    def test_intel_scraper_submit_without_api_key(self):
        """Test /api/intel/scraper/submit requires API key"""
        response = client.post(
            "/api/intel/scraper/submit",
            json={
                "title": "Test Article",
                "content": "Test content",
                "source_url": "https://example.com/test",
                "source_name": "test",
                "category": "news",
                "relevance_score": 50,
            },
        )
        assert response.status_code == 401
        assert "API key required" in response.json()["detail"]

    def test_intel_scraper_submit_with_invalid_api_key(self):
        """Test /api/intel/scraper/submit rejects invalid API key"""
        response = client.post(
            "/api/intel/scraper/submit",
            json={
                "title": "Test Article",
                "content": "Test content",
                "source_url": "https://example.com/test",
                "source_name": "test",
                "category": "news",
                "relevance_score": 50,
            },
            headers={"X-API-Key": "invalid-key-12345"},
        )
        assert response.status_code == 401
        assert "Invalid API key" in response.json()["detail"]

    def test_audio_transcribe_without_api_key(self):
        """Test /api/audio/transcribe requires API key"""
        # Create a dummy file
        files = {"file": ("test.wav", b"fake audio data", "audio/wav")}
        response = client.post("/audio/transcribe", files=files)
        assert response.status_code == 401
        assert "API key required" in response.json()["detail"]

    def test_audio_speech_without_api_key(self):
        """Test /api/audio/speech requires API key"""
        response = client.post(
            "/audio/speech",
            json={"text": "Hello world", "voice": "alloy"},
        )
        assert response.status_code == 401
        assert "API key required" in response.json()["detail"]

    def test_preview_upload_without_api_key(self):
        """Test /preview/upload requires API key"""
        response = client.post(
            "/preview/upload",
            json={"article_id": "test123", "html_content": "<html>Test</html>"},
        )
        assert response.status_code == 401
        assert "API key required" in response.json()["detail"]

    def test_legal_parent_documents_without_api_key(self):
        """Test /api/legal/parent-documents requires API key"""
        response = client.post(
            "/api/legal/parent-documents",
            json={
                "document_id": "test-doc",
                "type": "peraturan",
                "title": "Test Document",
                "full_text": "Test content",
                "char_count": 12,
                "pasal_count": 1,
            },
        )
        assert response.status_code == 401
        assert "API key required" in response.json()["detail"]

    @pytest.mark.skip(reason="Requires valid API key from environment")
    def test_intel_scraper_submit_with_valid_api_key(self):
        """Test /api/intel/scraper/submit accepts valid API key"""
        import os

        api_key = os.getenv("API_KEYS", "").split(",")[0] if os.getenv("API_KEYS") else None
        if not api_key:
            pytest.skip("No API key available in environment")

        response = client.post(
            "/api/intel/scraper/submit",
            json={
                "title": "Test Article",
                "content": "Test content",
                "source_url": "https://example.com/test",
                "source_name": "test",
                "category": "news",
                "relevance_score": 50,
            },
            headers={"X-API-Key": api_key.strip()},
        )
        # Should not be 401 (may be 500 or 200 depending on service availability)
        assert response.status_code != 401
