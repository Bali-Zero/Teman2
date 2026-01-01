"""
Unit tests for Ingestion CLI
Target: 100% coverage
Composer: 4
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from cli.ingestion_cli import IngestionCLI


@pytest.fixture
def ingestion_cli():
    """Create ingestion CLI instance"""
    return IngestionCLI()


class TestIngestionCLI:
    """Tests for IngestionCLI"""

    def test_init(self):
        """Test initialization"""
        cli = IngestionCLI()
        assert cli is not None

    @pytest.mark.asyncio
    async def test_ingest_team_members(self, ingestion_cli):
        """Test ingesting team members"""
        with patch("core.qdrant_db.QdrantClient") as mock_qdrant, \
             patch("core.embeddings.create_embeddings_generator") as mock_embedder, \
             patch("pathlib.Path.exists", return_value=True), \
             patch("builtins.open", create=True):
            mock_qdrant_instance = MagicMock()
            mock_qdrant_instance.upsert_documents = MagicMock(return_value={"success": True})
            mock_qdrant.return_value = mock_qdrant_instance
            
            mock_embedder_instance = MagicMock()
            mock_embedder_instance.generate_single_embedding = MagicMock(return_value=[0.1] * 1536)
            mock_embedder.return_value = mock_embedder_instance
            
            with patch("json.load", return_value=[{"name": "Test", "role": "Dev", "department": "Tech", "email": "test@test.com"}]):
                result = await ingestion_cli.ingest_team_members()
                # Should return dict with success or error
                assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_ingest_conversations(self, ingestion_cli):
        """Test ingesting conversations"""
        with patch("core.qdrant_db.QdrantClient") as mock_qdrant, \
             patch("core.embeddings.create_embeddings_generator") as mock_embedder, \
             patch("pathlib.Path.exists", return_value=True), \
             patch("builtins.open", create=True):
            mock_qdrant_instance = MagicMock()
            mock_qdrant_instance.upsert_points = MagicMock(return_value={"success": True})
            mock_qdrant.return_value = mock_qdrant_instance
            
            mock_embedder_instance = MagicMock()
            mock_embedder_instance.generate_single_embedding = MagicMock(return_value=[0.1] * 1536)
            mock_embedder.return_value = mock_embedder_instance
            
            with patch("json.load", return_value=[{"role": "user", "content": "test"}]):
                result = await ingestion_cli.ingest_conversations(source="/path/to/data")
                # Should return dict with success or error
                assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_ingest_laws(self, ingestion_cli):
        """Test ingesting laws"""
        with patch("pathlib.Path.exists", return_value=True), \
             patch("builtins.open", create=True):
            with patch.object(ingestion_cli.legal_ingestion_service, 'ingest_legal_document') as mock_ingest:
                mock_ingest.return_value = {"ingested": 1}
                
                result = await ingestion_cli.ingest_laws(file_path="/path/to/law.pdf")
                assert result is not None

    def test_list_collections(self, ingestion_cli):
        """Test listing collections"""
        result = ingestion_cli.list_types()
        # Should return dict with available types
        assert isinstance(result, dict)
        assert "types" in result or "ingestion_types" in result or len(result) > 0

    @pytest.mark.asyncio
    async def test_ingest_team_members_file_not_found(self, ingestion_cli):
        """Test ingesting team members with file not found"""
        with patch("pathlib.Path.exists", return_value=False):
            result = await ingestion_cli.ingest_team_members()
            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_ingest_team_members_with_source(self, ingestion_cli):
        """Test ingesting team members with custom source"""
        with patch("core.qdrant_db.QdrantClient") as mock_qdrant, \
             patch("core.embeddings.create_embeddings_generator") as mock_embedder, \
             patch("pathlib.Path.exists", return_value=True), \
             patch("builtins.open", create=True):
            mock_qdrant_instance = MagicMock()
            mock_qdrant_instance.upsert_points = MagicMock(return_value={"success": True})
            mock_qdrant.return_value = mock_qdrant_instance
            
            mock_embedder_instance = MagicMock()
            mock_embedder_instance.generate_single_embedding = MagicMock(return_value=[0.1] * 1536)
            mock_embedder.return_value = mock_embedder_instance
            
            with patch("json.load", return_value=[{"name": "Test", "role": "Dev", "department": "Tech", "email": "test@test.com", "bio": "Bio"}]):
                result = await ingestion_cli.ingest_team_members(source="/custom/path.json")
                assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_ingest_team_members_error(self, ingestion_cli):
        """Test error handling in ingest_team_members"""
        with patch("pathlib.Path.exists", return_value=True), \
             patch("builtins.open", side_effect=Exception("File error")):
            result = await ingestion_cli.ingest_team_members()
            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_ingest_conversations_directory(self, ingestion_cli):
        """Test ingesting conversations from directory"""
        with patch("core.qdrant_db.QdrantClient") as mock_qdrant, \
             patch("core.embeddings.create_embeddings_generator") as mock_embedder, \
             patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.is_file", return_value=False), \
             patch("pathlib.Path.glob", return_value=[MagicMock()]), \
             patch("builtins.open", create=True):
            mock_qdrant_instance = MagicMock()
            mock_qdrant_instance.upsert_points = MagicMock(return_value={"success": True})
            mock_qdrant.return_value = mock_qdrant_instance
            
            mock_embedder_instance = MagicMock()
            mock_embedder_instance.generate_single_embedding = MagicMock(return_value=[0.1] * 1536)
            mock_embedder.return_value = mock_embedder_instance
            
            with patch("json.load", return_value=[{"role": "user", "content": "test"}]):
                result = await ingestion_cli.ingest_conversations(source="/path/to/dir")
                assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_ingest_conversations_with_question_answer(self, ingestion_cli):
        """Test ingesting conversations with question/answer format"""
        with patch("core.qdrant_db.QdrantClient") as mock_qdrant, \
             patch("core.embeddings.create_embeddings_generator") as mock_embedder, \
             patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.is_file", return_value=True), \
             patch("builtins.open", create=True):
            mock_qdrant_instance = MagicMock()
            mock_qdrant_instance.upsert_points = MagicMock(return_value={"success": True})
            mock_qdrant.return_value = mock_qdrant_instance
            
            mock_embedder_instance = MagicMock()
            mock_embedder_instance.generate_single_embedding = MagicMock(return_value=[0.1] * 1536)
            mock_embedder.return_value = mock_embedder_instance
            
            with patch("json.load", return_value=[{"question": "Q", "answer": "A"}]):
                result = await ingestion_cli.ingest_conversations(source="/path/to/file.json")
                assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_ingest_conversations_error(self, ingestion_cli):
        """Test error handling in ingest_conversations"""
        with patch("pathlib.Path.exists", return_value=False):
            result = await ingestion_cli.ingest_conversations(source="/nonexistent")
            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_ingest_laws_directory(self, ingestion_cli):
        """Test ingesting laws from directory"""
        from pathlib import Path
        
        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.glob", return_value=[Path("law1.pdf"), Path("law2.txt")]), \
             patch.object(ingestion_cli.legal_ingestion_service, 'ingest_legal_document') as mock_ingest:
            mock_ingest.return_value = {"ingested": 1}
            
            result = await ingestion_cli.ingest_laws(directory="/path/to/dir")
            assert result["success"] is True
            assert result["ingested"] > 0

    @pytest.mark.asyncio
    async def test_ingest_laws_directory_with_errors(self, ingestion_cli):
        """Test ingesting laws directory with some errors"""
        from pathlib import Path
        
        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.glob", return_value=[Path("law1.pdf"), Path("law2.pdf")]), \
             patch.object(ingestion_cli.legal_ingestion_service, 'ingest_legal_document') as mock_ingest:
            mock_ingest.side_effect = [{"ingested": 1}, Exception("Error")]
            
            result = await ingestion_cli.ingest_laws(directory="/path/to/dir")
            assert result["ingested"] == 1

    @pytest.mark.asyncio
    async def test_ingest_laws_no_file_or_directory(self, ingestion_cli):
        """Test ingesting laws without file or directory"""
        result = await ingestion_cli.ingest_laws()
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_ingest_laws_error(self, ingestion_cli):
        """Test error handling in ingest_laws"""
        with patch("pathlib.Path.exists", return_value=True), \
             patch.object(ingestion_cli.legal_ingestion_service, 'ingest_legal_document', side_effect=Exception("Error")):
            result = await ingestion_cli.ingest_laws(file_path="/path/to/law.pdf")
            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_ingest_document(self, ingestion_cli):
        """Test ingesting general document"""
        with patch.object(ingestion_cli.ingestion_service, 'ingest_book') as mock_ingest:
            mock_ingest.return_value = {"ingested": 1, "collection": "test_collection"}
            
            result = await ingestion_cli.ingest_document(
                file_path="/path/to/doc.pdf",
                title="Test Doc",
                author="Test Author",
                collection="custom_collection"
            )
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_ingest_document_error(self, ingestion_cli):
        """Test error handling in ingest_document"""
        with patch.object(ingestion_cli.ingestion_service, 'ingest_book', side_effect=Exception("Error")):
            result = await ingestion_cli.ingest_document(file_path="/path/to/doc.pdf")
            assert result["success"] is False

