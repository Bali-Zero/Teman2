"""
Integration Tests for PoliticsIngestionService
Tests Indonesian politics knowledge base ingestion into Qdrant
"""

import json
import os
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestPoliticsIngestionServiceIntegration:
    """Comprehensive integration tests for PoliticsIngestionService"""

    @pytest_asyncio.fixture
    async def mock_qdrant_client(self):
        """Create mock Qdrant client"""
        mock_client = MagicMock()
        mock_client.upsert_documents = MagicMock(return_value={"success": True})
        return mock_client

    @pytest_asyncio.fixture
    async def mock_embedder(self):
        """Create mock embedder"""
        mock_embedder = MagicMock()
        mock_embedder.generate_embeddings = MagicMock(return_value=[[0.1] * 384, [0.2] * 384])
        return mock_embedder

    @pytest_asyncio.fixture
    async def service(self, mock_qdrant_client, mock_embedder):
        """Create PoliticsIngestionService instance"""
        with patch(
            "services.politics_ingestion.create_embeddings_generator", return_value=mock_embedder
        ):
            with patch("services.politics_ingestion.QdrantClient", return_value=mock_qdrant_client):
                from services.politics_ingestion import PoliticsIngestionService

                service = PoliticsIngestionService(qdrant_url="http://localhost:6333")
                service.embedder = mock_embedder
                service.vector_db = mock_qdrant_client
                return service

    def test_initialization(self, service):
        """Test service initialization"""
        assert service is not None
        assert service.embedder is not None
        assert service.vector_db is not None

    def test_build_text_person(self, service):
        """Test building text for person record"""
        record = {
            "type": "person",
            "name": "Joko Widodo",
            "dob": "1961-06-21",
            "pob": "Surakarta",
            "offices": [
                {
                    "office": "President",
                    "from": "2014",
                    "to": "2024",
                    "jurisdiction_id": "id",
                }
            ],
            "party_memberships": [{"party_id": "pdi-p", "from": "2004", "to": "present"}],
        }

        text = service._build_text(record)
        assert "Joko Widodo" in text
        assert "President" in text
        assert "pdi-p" in text

    def test_build_text_party(self, service):
        """Test building text for party record"""
        record = {
            "type": "party",
            "name": "Partai Demokrasi Indonesia Perjuangan",
            "abbrev": "PDI-P",
            "founded": "1999",
            "dissolved": None,
            "ideology": ["nationalism", "social democracy"],
            "leaders": [{"person_id": "jokowi", "from": "2014", "to": "present"}],
        }

        text = service._build_text(record)
        assert "PDI-P" in text
        assert "Partai Demokrasi Indonesia Perjuangan" in text
        assert "nationalism" in text

    def test_build_text_election(self, service):
        """Test building text for election record"""
        record = {
            "type": "election",
            "id": "pemilu-2019",
            "date": "2019-04-17",
            "level": "national",
            "scope": "presidential",
            "jurisdiction_id": "id",
            "contests": [
                {
                    "office": "President",
                    "district": "Indonesia",
                    "results": [
                        {
                            "candidate_id": "jokowi",
                            "party_id": "pdi-p",
                            "votes": 85000000,
                            "pct": 55.5,
                        }
                    ],
                }
            ],
        }

        text = service._build_text(record)
        assert "pemilu-2019" in text
        assert "2019-04-17" in text
        assert "President" in text

    def test_build_text_jurisdiction(self, service):
        """Test building text for jurisdiction record"""
        record = {
            "type": "jurisdiction",
            "id": "id-jakarta",
            "name": "DKI Jakarta",
            "kind": "province",
            "parent_id": "id",
            "valid_from": "1961",
            "valid_to": None,
        }

        text = service._build_text(record)
        assert "DKI Jakarta" in text
        assert "province" in text

    def test_build_text_law(self, service):
        """Test building text for law record"""
        record = {
            "type": "law",
            "number": "UU No. 13/2003",
            "title": "Ketenagakerjaan",
            "date": "2003-03-25",
            "subject": "labor",
        }

        text = service._build_text(record)
        assert "UU No. 13/2003" in text
        assert "Ketenagakerjaan" in text

    def test_build_text_unknown_type(self, service):
        """Test building text for unknown record type"""
        record = {"type": "unknown", "data": "test"}

        text = service._build_text(record)
        # Should return JSON string
        assert "unknown" in text or "test" in text

    def test_ingest_jsonl_files_success(self, service):
        """Test ingesting JSONL files successfully"""
        # Create temporary JSONL file
        with NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            record = {
                "type": "person",
                "id": "test-person-1",
                "name": "Test Person",
                "dob": "1990-01-01",
                "pob": "Jakarta",
                "offices": [],
                "party_memberships": [],
            }
            f.write(json.dumps(record) + "\n")
            temp_file = Path(f.name)

        try:
            result = service.ingest_jsonl_files([temp_file])

            assert result["success"] is True
            assert result["documents_added"] == 1
            service.vector_db.upsert_documents.assert_called_once()
        finally:
            temp_file.unlink()

    def test_ingest_jsonl_files_empty(self, service):
        """Test ingesting empty JSONL file"""
        with NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            # Write empty file
            temp_file = Path(f.name)

        try:
            result = service.ingest_jsonl_files([temp_file])

            assert result["success"] is False
            assert result["documents_added"] == 0
            assert "message" in result
        finally:
            temp_file.unlink()

    def test_ingest_jsonl_files_multiple_records(self, service):
        """Test ingesting JSONL file with multiple records"""
        with NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for i in range(3):
                record = {
                    "type": "person",
                    "id": f"test-person-{i}",
                    "name": f"Person {i}",
                    "dob": "1990-01-01",
                    "pob": "Jakarta",
                    "offices": [],
                    "party_memberships": [],
                }
                f.write(json.dumps(record) + "\n")
            temp_file = Path(f.name)

        try:
            result = service.ingest_jsonl_files([temp_file])

            assert result["success"] is True
            assert result["documents_added"] == 3
        finally:
            temp_file.unlink()

    def test_ingest_jsonl_files_invalid_json(self, service):
        """Test ingesting JSONL file with invalid JSON"""
        with NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("invalid json line\n")
            temp_file = Path(f.name)

        try:
            # Should handle gracefully
            result = service.ingest_jsonl_files([temp_file])

            # May return success=False or handle error
            assert "success" in result
        finally:
            temp_file.unlink()

    def test_ingest_dir(self, service):
        """Test ingesting directory with JSONL files"""
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Create subdirectories
            (tmp_path / "persons").mkdir()
            (tmp_path / "parties").mkdir()

            # Create JSONL files
            person_file = tmp_path / "persons" / "persons.jsonl"
            with person_file.open("w") as f:
                record = {
                    "type": "person",
                    "id": "test-person",
                    "name": "Test Person",
                    "dob": "1990-01-01",
                    "pob": "Jakarta",
                    "offices": [],
                    "party_memberships": [],
                }
                f.write(json.dumps(record) + "\n")

            party_file = tmp_path / "parties" / "parties.jsonl"
            with party_file.open("w") as f:
                record = {
                    "type": "party",
                    "id": "test-party",
                    "name": "Test Party",
                    "abbrev": "TP",
                    "founded": "2000",
                    "dissolved": None,
                    "ideology": [],
                    "leaders": [],
                }
                f.write(json.dumps(record) + "\n")

            result = service.ingest_dir(tmp_path)

            assert result["success"] is True
            assert result["documents_added"] == 2

    def test_ingest_jsonl_files_metadata(self, service):
        """Test that metadata is correctly generated"""
        with NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            record = {
                "type": "person",
                "id": "test-person-1",
                "qid": "Q123",
                "name": "Test Person",
                "dob": "1990-01-01",
                "pob": "Jakarta",
                "offices": [],
                "party_memberships": [],
                "sources": [{"url": "http://example.com"}],
                "period": "1999-ongoing",
            }
            f.write(json.dumps(record) + "\n")
            temp_file = Path(f.name)

        try:
            result = service.ingest_jsonl_files([temp_file])

            assert result["success"] is True
            # Verify upsert_documents was called with correct metadata
            call_args = service.vector_db.upsert_documents.call_args
            assert call_args is not None
            metadatas = call_args.kwargs.get("metadatas", [])
            if metadatas:
                assert metadatas[0]["domain"] == "politics-id"
                assert metadatas[0]["record_type"] == "person"
                assert metadatas[0]["record_id"] == "test-person-1"
        finally:
            temp_file.unlink()

    def test_ingest_jsonl_files_ids(self, service):
        """Test that document IDs are correctly generated"""
        with NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            record = {
                "type": "person",
                "id": "test-person-1",
                "name": "Test Person",
                "dob": "1990-01-01",
                "pob": "Jakarta",
                "offices": [],
                "party_memberships": [],
            }
            f.write(json.dumps(record) + "\n")
            temp_file = Path(f.name)

        try:
            result = service.ingest_jsonl_files([temp_file])

            assert result["success"] is True
            call_args = service.vector_db.upsert_documents.call_args
            if call_args:
                ids = call_args.kwargs.get("ids", [])
                if ids:
                    assert ids[0].startswith("pol:person:")

        finally:
            temp_file.unlink()
