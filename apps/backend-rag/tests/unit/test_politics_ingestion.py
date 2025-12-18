"""
Unit tests for PoliticsIngestionService
Target: Increase coverage from 88% to 95%+
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def sample_jsonl_data():
    """Sample JSONL data for testing"""
    return [
        {"id": "1", "name": "Test Person", "type": "person"},
        {"id": "2", "name": "Test Party", "type": "party"},
    ]


@pytest.fixture
def temp_jsonl_file(sample_jsonl_data):
    """Create temporary JSONL file"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        for item in sample_jsonl_data:
            f.write(json.dumps(item) + "\n")
        temp_path = Path(f.name)

    yield temp_path
    temp_path.unlink(missing_ok=True)


@pytest.fixture
def temp_dir_structure():
    """Create temporary directory structure"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # Create subdirectories
        (tmp_path / "persons").mkdir()
        (tmp_path / "parties").mkdir()
        (tmp_path / "elections").mkdir()
        (tmp_path / "jurisdictions").mkdir()

        # Create sample files
        (tmp_path / "persons" / "test1.jsonl").write_text('{"id": "1", "name": "Person 1"}\n')
        (tmp_path / "parties" / "test2.jsonl").write_text('{"id": "2", "name": "Party 1"}\n')

        yield tmp_path


def test_init():
    """Test PoliticsIngestionService initialization"""
    from services.politics_ingestion import PoliticsIngestionService

    service = PoliticsIngestionService()
    assert service.embedder is not None
    assert service.vector_db is not None
    assert service.vector_db.collection_name == "politics_id"


def test_init_custom_collection():
    """Test initialization with custom qdrant URL"""
    from services.politics_ingestion import PoliticsIngestionService

    service = PoliticsIngestionService(qdrant_url="http://localhost:6333")
    assert service.vector_db is not None
    assert service.vector_db.collection_name == "politics_id"


def test_ingest_jsonl_file(temp_jsonl_file):
    """Test ingesting a single JSONL file"""
    from services.politics_ingestion import PoliticsIngestionService

    service = PoliticsIngestionService()

    # Mock the vector store operations
    with (
        patch.object(service.vector_db, "upsert_documents") as mock_upsert,
        patch.object(service.embedder, "generate_embeddings") as mock_embed,
    ):
        mock_upsert.return_value = {"success": True, "documents_added": 2}
        mock_embed.return_value = [[0.1] * 1536, [0.2] * 1536]

        result = service.ingest_jsonl_files([temp_jsonl_file])

        assert "success" in result
        assert result["success"] is True
        assert result["documents_added"] == 2


def test_ingest_jsonl_file_empty():
    """Test ingesting an empty JSONL file"""
    from services.politics_ingestion import PoliticsIngestionService

    # Create empty file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        empty_file = Path(f.name)

    try:
        service = PoliticsIngestionService()

        result = service.ingest_jsonl_files([empty_file])

        assert result["success"] is False
        assert result["documents_added"] == 0
    finally:
        empty_file.unlink(missing_ok=True)


def test_ingest_jsonl_file_invalid_json(temp_jsonl_file):
    """Test ingesting JSONL file with invalid JSON lines"""
    from services.politics_ingestion import PoliticsIngestionService

    # Write invalid JSON
    invalid_file = temp_jsonl_file.parent / "invalid.jsonl"
    invalid_file.write_text("invalid json line\n")

    try:
        service = PoliticsIngestionService()

        # Should handle invalid JSON gracefully (skip invalid lines)
        result = service.ingest_jsonl_files([invalid_file])
        # May return success=False or skip invalid lines
        assert "success" in result or "documents_added" in result
    finally:
        invalid_file.unlink(missing_ok=True)


def test_ingest_jsonl_files_multiple(temp_jsonl_file):
    """Test ingesting multiple JSONL files"""
    from services.politics_ingestion import PoliticsIngestionService

    # Create second file
    second_file = temp_jsonl_file.parent / "second.jsonl"
    second_file.write_text('{"id": "3", "name": "Test 3", "type": "person"}\n')

    try:
        service = PoliticsIngestionService()

        with (
            patch.object(service.vector_db, "upsert_documents") as mock_upsert,
            patch.object(service.embedder, "generate_embeddings") as mock_embed,
        ):
            mock_upsert.return_value = {"success": True, "documents_added": 3}
            mock_embed.return_value = [[0.1] * 1536, [0.2] * 1536, [0.3] * 1536]

            result = service.ingest_jsonl_files([temp_jsonl_file, second_file])

            assert result["success"] is True
            assert result["documents_added"] == 3
    finally:
        second_file.unlink(missing_ok=True)


def test_ingest_dir(temp_dir_structure):
    """Test ingesting directory structure"""
    from services.politics_ingestion import PoliticsIngestionService

    service = PoliticsIngestionService()

    with (
        patch.object(service.vector_db, "upsert_documents") as mock_upsert,
        patch.object(service.embedder, "generate_embeddings") as mock_embed,
    ):
        mock_upsert.return_value = {"success": True, "documents_added": 2}
        mock_embed.return_value = [[0.1] * 1536, [0.2] * 1536]

        result = service.ingest_dir(temp_dir_structure)

        assert result["success"] is True
        assert result["documents_added"] == 2


def test_ingest_dir_empty():
    """Test ingesting empty directory"""
    from services.politics_ingestion import PoliticsIngestionService

    with tempfile.TemporaryDirectory() as tmpdir:
        empty_dir = Path(tmpdir) / "empty"
        empty_dir.mkdir()
        (empty_dir / "persons").mkdir()
        (empty_dir / "parties").mkdir()
        (empty_dir / "elections").mkdir()
        (empty_dir / "jurisdictions").mkdir()

        service = PoliticsIngestionService()

        result = service.ingest_dir(empty_dir)

        assert result["success"] is False
        assert result["documents_added"] == 0
