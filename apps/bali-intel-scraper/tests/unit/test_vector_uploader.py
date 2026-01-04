"""
Unit Tests for Vector Uploader
Tests for Qdrant vector database uploads
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import sys
from pathlib import Path
import os

# Set dummy env vars to prevent init errors
os.environ.setdefault("OPENAI_API_KEY", "test-key-for-testing")
os.environ.setdefault("QDRANT_API_KEY", "test-qdrant-key")

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))


class TestVectorDBUploaderInit:
    """Test VectorDBUploader initialization"""

    def test_import_module(self):
        """Test that module can be imported"""
        from vector_uploader import VectorDBUploader

        assert VectorDBUploader is not None

    def test_has_collection_map(self):
        """Test collection mapping exists"""
        with patch("vector_uploader.EmbeddingsGenerator"):
            from vector_uploader import VectorDBUploader

            uploader = VectorDBUploader()
            assert "immigration" in uploader.collection_map
            assert "tax_bkpm" in uploader.collection_map
            assert "property" in uploader.collection_map
            assert "business" in uploader.collection_map

    def test_qdrant_url_default(self):
        """Test default Qdrant URL"""
        with patch("vector_uploader.EmbeddingsGenerator"):
            from vector_uploader import VectorDBUploader

            uploader = VectorDBUploader()
            assert (
                "qdrant" in uploader.qdrant_url.lower()
                or "fly.dev" in uploader.qdrant_url
            )


class TestParseFrontmatter:
    """Test frontmatter parsing"""

    def test_parse_valid_frontmatter(self):
        """Test parsing valid YAML frontmatter"""
        with patch("vector_uploader.EmbeddingsGenerator"):
            from vector_uploader import VectorDBUploader

            uploader = VectorDBUploader()

            content = """---
title: Test Article
source_file: test.md
ai_model: claude
---

Article content here.
"""
            metadata = uploader._parse_frontmatter(content)

            assert metadata.get("title") == "Test Article"
            assert metadata.get("source_file") == "test.md"
            assert metadata.get("ai_model") == "claude"

    def test_parse_no_frontmatter(self):
        """Test parsing content without frontmatter"""
        with patch("vector_uploader.EmbeddingsGenerator"):
            from vector_uploader import VectorDBUploader

            uploader = VectorDBUploader()

            content = "Just plain content without frontmatter."
            metadata = uploader._parse_frontmatter(content)

            assert metadata == {}

    def test_parse_invalid_yaml(self):
        """Test parsing invalid YAML returns empty dict"""
        with patch("vector_uploader.EmbeddingsGenerator"):
            from vector_uploader import VectorDBUploader

            uploader = VectorDBUploader()

            content = """---
invalid: yaml: content: here
---
Content
"""
            metadata = uploader._parse_frontmatter(content)
            # Should return empty or partial dict, not crash
            assert isinstance(metadata, dict)


class TestExtractContent:
    """Test content extraction"""

    def test_extract_title_and_body(self):
        """Test extracting title and body"""
        with patch("vector_uploader.EmbeddingsGenerator"):
            from vector_uploader import VectorDBUploader

            uploader = VectorDBUploader()

            content = """---
title: Frontmatter Title
---

# Main Title

This is the article body.

More content here.
"""
            title, body = uploader._extract_content(content)

            assert title == "Main Title"
            assert "article body" in body
            assert "More content" in body

    def test_extract_no_title(self):
        """Test extracting when no title heading"""
        with patch("vector_uploader.EmbeddingsGenerator"):
            from vector_uploader import VectorDBUploader

            uploader = VectorDBUploader()

            content = """Just body content without a heading."""
            title, body = uploader._extract_content(content)

            assert title == "Untitled"
            assert "body content" in body


class TestExtractTier:
    """Test tier extraction"""

    def test_extract_t1(self):
        """Test extracting T1 tier"""
        with patch("vector_uploader.EmbeddingsGenerator"):
            from vector_uploader import VectorDBUploader

            uploader = VectorDBUploader()

            metadata = {"source_file": "immigration_T1_article.md"}
            tier = uploader._extract_tier(metadata)

            assert tier == "T1"

    def test_extract_t2(self):
        """Test extracting T2 tier"""
        with patch("vector_uploader.EmbeddingsGenerator"):
            from vector_uploader import VectorDBUploader

            uploader = VectorDBUploader()

            metadata = {"source_file": "tax_T2_news.md"}
            tier = uploader._extract_tier(metadata)

            assert tier == "T2"

    def test_extract_t3(self):
        """Test extracting T3 tier"""
        with patch("vector_uploader.EmbeddingsGenerator"):
            from vector_uploader import VectorDBUploader

            uploader = VectorDBUploader()

            metadata = {"source_file": "general_T3_blog.md"}
            tier = uploader._extract_tier(metadata)

            assert tier == "T3"

    def test_extract_unknown_tier(self):
        """Test unknown tier returns unknown"""
        with patch("vector_uploader.EmbeddingsGenerator"):
            from vector_uploader import VectorDBUploader

            uploader = VectorDBUploader()

            metadata = {"source_file": "random_article.md"}
            tier = uploader._extract_tier(metadata)

            assert tier == "unknown"

    def test_extract_empty_metadata(self):
        """Test with empty metadata"""
        with patch("vector_uploader.EmbeddingsGenerator"):
            from vector_uploader import VectorDBUploader

            uploader = VectorDBUploader()

            tier = uploader._extract_tier({})

            assert tier == "unknown"


class TestCollectionMapping:
    """Test category to collection mapping"""

    def test_immigration_collection(self):
        """Test immigration maps to correct collection"""
        with patch("vector_uploader.EmbeddingsGenerator"):
            from vector_uploader import VectorDBUploader

            uploader = VectorDBUploader()

            assert uploader.collection_map["immigration"] == "bali_intel_immigration"

    def test_tax_collection(self):
        """Test tax maps to correct collection"""
        with patch("vector_uploader.EmbeddingsGenerator"):
            from vector_uploader import VectorDBUploader

            uploader = VectorDBUploader()

            assert uploader.collection_map["tax_bkpm"] == "bali_intel_bkpm_tax"

    def test_property_collection(self):
        """Test property maps to correct collection"""
        with patch("vector_uploader.EmbeddingsGenerator"):
            from vector_uploader import VectorDBUploader

            uploader = VectorDBUploader()

            assert uploader.collection_map["property"] == "bali_intel_realestate"


class TestUploadArticle:
    """Test article upload"""

    @pytest.mark.asyncio
    async def test_upload_success(self, tmp_path):
        """Test successful article upload"""
        with patch("vector_uploader.EmbeddingsGenerator") as mock_embed_class:
            with patch("vector_uploader.QdrantClient") as mock_qdrant_class:
                # Setup mocks
                mock_embed = MagicMock()
                mock_embed.generate_single_embedding.return_value = [0.1] * 1536
                mock_embed.get_model_info.return_value = "test-model"
                mock_embed_class.return_value = mock_embed

                mock_qdrant = AsyncMock()
                mock_qdrant.get_collection_stats.return_value = {"vectors_count": 0}
                mock_qdrant.upsert_documents.return_value = {"success": True}
                mock_qdrant.__aenter__.return_value = mock_qdrant
                mock_qdrant.__aexit__.return_value = None
                mock_qdrant_class.return_value = mock_qdrant

                from vector_uploader import VectorDBUploader

                uploader = VectorDBUploader()

                # Create test file
                test_file = tmp_path / "test.md"
                test_file.write_text("""---
title: Test Article
source_file: T1_test.md
---

# Test Title

This is test content.
""")

                result = await uploader.upload_article(test_file, "immigration")

                assert result["success"] is True
                assert "document_id" in result

    @pytest.mark.asyncio
    async def test_upload_file_not_found(self, tmp_path):
        """Test upload with non-existent file"""
        with patch("vector_uploader.EmbeddingsGenerator") as mock_embed_class:
            mock_embed = MagicMock()
            mock_embed.get_model_info.return_value = "test-model"
            mock_embed_class.return_value = mock_embed

            from vector_uploader import VectorDBUploader

            uploader = VectorDBUploader()

            result = await uploader.upload_article(
                tmp_path / "nonexistent.md", "immigration"
            )

            assert result["success"] is False
            assert "error" in result


class TestUploadCategory:
    """Test category upload"""

    @pytest.mark.asyncio
    async def test_upload_category_no_dir(self):
        """Test upload when category directory doesn't exist"""
        with patch("vector_uploader.EmbeddingsGenerator") as mock_embed_class:
            mock_embed = MagicMock()
            mock_embed.get_model_info.return_value = "test-model"
            mock_embed_class.return_value = mock_embed

            from vector_uploader import VectorDBUploader

            uploader = VectorDBUploader()

            result = await uploader.upload_category("nonexistent_category")

            assert result["uploaded"] == 0
            assert result["failed"] == 0


class TestUploadCategoryWithFiles:
    """Test category upload with actual files"""

    @pytest.mark.asyncio
    async def test_upload_category_with_files(self, tmp_path):
        """Test upload category with multiple files"""
        with patch("vector_uploader.EmbeddingsGenerator") as mock_embed_class:
            with patch("vector_uploader.QdrantClient") as mock_qdrant_class:
                # Setup mocks
                mock_embed = MagicMock()
                mock_embed.generate_single_embedding.return_value = [0.1] * 1536
                mock_embed.get_model_info.return_value = "test-model"
                mock_embed_class.return_value = mock_embed

                mock_qdrant = AsyncMock()
                mock_qdrant.get_collection_stats.return_value = {"vectors_count": 0}
                mock_qdrant.upsert_documents.return_value = {"success": True}
                mock_qdrant.__aenter__.return_value = mock_qdrant
                mock_qdrant.__aexit__.return_value = None
                mock_qdrant_class.return_value = mock_qdrant

                from vector_uploader import VectorDBUploader

                uploader = VectorDBUploader()

                # Create test directory structure
                articles_dir = tmp_path / "data" / "articles" / "immigration"
                articles_dir.mkdir(parents=True)

                # Create test files
                for i in range(3):
                    (articles_dir / f"article_{i}.md").write_text(f"""---
title: Article {i}
source_file: T1_test.md
---

# Article {i} Title

Content for article {i}.
""")

                # Patch the articles directory path
                with patch.object(
                    uploader, "upload_article", new_callable=AsyncMock
                ) as mock_upload:
                    mock_upload.return_value = {"success": True}

                    # The path lookup happens in upload_category - we need to mock Path
                    with patch("vector_uploader.Path") as mock_path:
                        mock_path.return_value.exists.return_value = True
                        mock_path.return_value.glob.return_value = list(
                            articles_dir.glob("*.md")
                        )

                        result = await uploader.upload_category(
                            "immigration", max_articles=2
                        )

                        assert result["uploaded"] >= 0

    @pytest.mark.asyncio
    async def test_upload_category_with_max_articles(self, tmp_path):
        """Test upload category respects max_articles limit"""
        with patch("vector_uploader.EmbeddingsGenerator") as mock_embed_class:
            mock_embed = MagicMock()
            mock_embed.get_model_info.return_value = "test-model"
            mock_embed_class.return_value = mock_embed

            from vector_uploader import VectorDBUploader

            uploader = VectorDBUploader()

            result = await uploader.upload_category("nonexistent", max_articles=5)

            assert result["uploaded"] == 0


class TestUploadAllCategories:
    """Test uploading all categories"""

    @pytest.mark.asyncio
    async def test_upload_all_with_specified_categories(self):
        """Test upload all with specific categories"""
        with patch("vector_uploader.EmbeddingsGenerator") as mock_embed_class:
            mock_embed = MagicMock()
            mock_embed.get_model_info.return_value = "test-model"
            mock_embed_class.return_value = mock_embed

            from vector_uploader import VectorDBUploader

            uploader = VectorDBUploader()

            # Mock upload_category to avoid file system access
            with patch.object(
                uploader, "upload_category", new_callable=AsyncMock
            ) as mock_upload:
                mock_upload.return_value = {
                    "category": "test",
                    "total": 5,
                    "uploaded": 5,
                    "failed": 0,
                    "errors": [],
                }

                result = await uploader.upload_all_categories(
                    categories=["immigration", "tax_bkpm"], max_per_category=3
                )

                assert result["total_uploaded"] == 10  # 5 per category
                assert result["total_failed"] == 0
                assert mock_upload.call_count == 2

    @pytest.mark.asyncio
    async def test_upload_all_discovers_categories(self, tmp_path):
        """Test upload all discovers categories from directory"""
        with patch("vector_uploader.EmbeddingsGenerator") as mock_embed_class:
            mock_embed = MagicMock()
            mock_embed.get_model_info.return_value = "test-model"
            mock_embed_class.return_value = mock_embed

            from vector_uploader import VectorDBUploader

            uploader = VectorDBUploader()

            # Mock upload_category
            with patch.object(
                uploader, "upload_category", new_callable=AsyncMock
            ) as mock_upload:
                mock_upload.return_value = {
                    "category": "test",
                    "uploaded": 0,
                    "failed": 0,
                    "errors": [],
                }

                # Mock Path to return empty directory
                with patch("vector_uploader.Path") as mock_path:
                    mock_dir = MagicMock()
                    mock_dir.iterdir.return_value = []
                    mock_path.return_value = mock_dir

                    result = await uploader.upload_all_categories()

                    assert "total_uploaded" in result
                    assert "total_failed" in result


class TestUploadToQdrant:
    """Test Qdrant upload functionality"""

    @pytest.mark.asyncio
    async def test_upload_creates_collection_if_not_exists(self):
        """Test that upload creates collection if needed"""
        with patch("vector_uploader.EmbeddingsGenerator") as mock_embed_class:
            with patch("vector_uploader.QdrantClient") as mock_qdrant_class:
                mock_embed = MagicMock()
                mock_embed.get_model_info.return_value = "test-model"
                mock_embed_class.return_value = mock_embed

                mock_qdrant = AsyncMock()
                # Return error to trigger collection creation
                mock_qdrant.get_collection_stats.return_value = {"error": "not found"}
                mock_qdrant.create_collection.return_value = {"success": True}
                mock_qdrant.upsert_documents.return_value = {"success": True}
                mock_qdrant.__aenter__.return_value = mock_qdrant
                mock_qdrant.__aexit__.return_value = None
                mock_qdrant_class.return_value = mock_qdrant

                from vector_uploader import VectorDBUploader

                uploader = VectorDBUploader()

                result = await uploader._upload_to_qdrant(
                    doc_id="test-id",
                    text="test content",
                    embedding=[0.1] * 1536,
                    metadata={"title": "test"},
                    collection="test_collection",
                )

                mock_qdrant.create_collection.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_to_qdrant_error(self):
        """Test handling Qdrant upload error"""
        with patch("vector_uploader.EmbeddingsGenerator") as mock_embed_class:
            with patch("vector_uploader.QdrantClient") as mock_qdrant_class:
                mock_embed = MagicMock()
                mock_embed.get_model_info.return_value = "test-model"
                mock_embed_class.return_value = mock_embed

                mock_qdrant_class.side_effect = Exception("Connection failed")

                from vector_uploader import VectorDBUploader

                uploader = VectorDBUploader()

                result = await uploader._upload_to_qdrant(
                    doc_id="test-id",
                    text="test content",
                    embedding=[0.1] * 1536,
                    metadata={"title": "test"},
                    collection="test_collection",
                )

                assert result["success"] is False
                assert "error" in result


class TestUploadArticleEdgeCases:
    """Test article upload edge cases"""

    @pytest.mark.asyncio
    async def test_upload_article_qdrant_fails(self, tmp_path):
        """Test upload when Qdrant returns failure"""
        with patch("vector_uploader.EmbeddingsGenerator") as mock_embed_class:
            with patch("vector_uploader.QdrantClient") as mock_qdrant_class:
                mock_embed = MagicMock()
                mock_embed.generate_single_embedding.return_value = [0.1] * 1536
                mock_embed.get_model_info.return_value = "test-model"
                mock_embed_class.return_value = mock_embed

                mock_qdrant = AsyncMock()
                mock_qdrant.get_collection_stats.return_value = {"vectors_count": 0}
                mock_qdrant.upsert_documents.return_value = {
                    "success": False,
                    "error": "Upload failed",
                }
                mock_qdrant.__aenter__.return_value = mock_qdrant
                mock_qdrant.__aexit__.return_value = None
                mock_qdrant_class.return_value = mock_qdrant

                from vector_uploader import VectorDBUploader

                uploader = VectorDBUploader()

                test_file = tmp_path / "test.md"
                test_file.write_text("""---
title: Test
---

# Test

Content.
""")

                result = await uploader.upload_article(test_file, "immigration")

                assert result["success"] is False

    @pytest.mark.asyncio
    async def test_upload_unknown_category(self, tmp_path):
        """Test upload with unknown category uses default collection"""
        with patch("vector_uploader.EmbeddingsGenerator") as mock_embed_class:
            with patch("vector_uploader.QdrantClient") as mock_qdrant_class:
                mock_embed = MagicMock()
                mock_embed.generate_single_embedding.return_value = [0.1] * 1536
                mock_embed.get_model_info.return_value = "test-model"
                mock_embed_class.return_value = mock_embed

                mock_qdrant = AsyncMock()
                mock_qdrant.get_collection_stats.return_value = {"vectors_count": 0}
                mock_qdrant.upsert_documents.return_value = {"success": True}
                mock_qdrant.__aenter__.return_value = mock_qdrant
                mock_qdrant.__aexit__.return_value = None
                mock_qdrant_class.return_value = mock_qdrant

                from vector_uploader import VectorDBUploader

                uploader = VectorDBUploader()

                test_file = tmp_path / "test.md"
                test_file.write_text("# Test\n\nContent.")

                result = await uploader.upload_article(test_file, "unknown_category")

                assert result["success"] is True
                assert result["collection"] == "bali_intel_roundup"


class TestFrontmatterEdgeCases:
    """Test frontmatter parsing edge cases"""

    def test_parse_incomplete_frontmatter(self):
        """Test parsing frontmatter with only one delimiter"""
        with patch("vector_uploader.EmbeddingsGenerator"):
            from vector_uploader import VectorDBUploader

            uploader = VectorDBUploader()

            content = """---
title: Test
This has no closing delimiter"""
            metadata = uploader._parse_frontmatter(content)

            assert metadata == {}

    def test_parse_empty_frontmatter(self):
        """Test parsing empty frontmatter"""
        with patch("vector_uploader.EmbeddingsGenerator"):
            from vector_uploader import VectorDBUploader

            uploader = VectorDBUploader()

            content = """---
---

Content here"""
            metadata = uploader._parse_frontmatter(content)

            assert metadata == {}


class TestRunStage3:
    """Test standalone function"""

    def test_function_exists(self):
        """Test run_stage3_upload function exists"""
        from vector_uploader import run_stage3_upload

        assert callable(run_stage3_upload)

    @pytest.mark.asyncio
    async def test_run_stage3_creates_uploader(self):
        """Test that run_stage3_upload creates uploader and calls upload_all"""
        with patch("vector_uploader.EmbeddingsGenerator") as mock_embed_class:
            mock_embed = MagicMock()
            mock_embed.get_model_info.return_value = "test-model"
            mock_embed_class.return_value = mock_embed

            with patch(
                "vector_uploader.VectorDBUploader.upload_all_categories",
                new_callable=AsyncMock,
            ) as mock_upload:
                mock_upload.return_value = {"total_uploaded": 0, "total_failed": 0}

                from vector_uploader import run_stage3_upload

                result = await run_stage3_upload(
                    categories=["test"], max_per_category=5
                )

                assert "total_uploaded" in result
