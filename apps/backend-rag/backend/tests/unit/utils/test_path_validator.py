"""
Tests for path_validator utility module.
"""

import pytest

from backend.app.utils.path_validator import sanitize_filename, validate_path


class TestValidatePath:
    """Tests for validate_path function."""

    def test_valid_relative_path(self, tmp_path):
        """Test validating a valid relative path."""
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        result = validate_path(str(test_dir), allowed_bases=[str(tmp_path)])
        assert result == test_dir.resolve()

    def test_path_outside_allowed_bases(self, tmp_path):
        """Test that paths outside allowed bases are rejected."""
        with pytest.raises(ValueError, match="outside allowed"):
            validate_path("/etc/passwd", allowed_bases=[str(tmp_path)])

    def test_path_traversal_attempt(self, tmp_path):
        """Test that path traversal attempts are blocked."""
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        with pytest.raises(ValueError, match="outside allowed"):
            validate_path(
                str(test_dir / ".." / ".." / "etc" / "passwd"), allowed_bases=[str(tmp_path)],
            )

    def test_must_exist_raises_when_missing(self, tmp_path):
        """Test that must_exist=True raises for non-existent paths."""
        non_existent = tmp_path / "does_not_exist"

        with pytest.raises(FileNotFoundError):
            validate_path(str(non_existent), allowed_bases=[str(tmp_path)], must_exist=True)

    def test_must_exist_false_allows_missing(self, tmp_path):
        """Test that must_exist=False allows non-existent paths."""
        non_existent = tmp_path / "does_not_exist"

        result = validate_path(str(non_existent), allowed_bases=[str(tmp_path)], must_exist=False)
        assert result == non_existent.resolve()


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""

    def test_removes_path_separators(self):
        """Test that path separators are replaced."""
        assert sanitize_filename("path/to/file.txt") == "path_to_file.txt"
        assert sanitize_filename("path\\to\\file.txt") == "path_to_file.txt"

    def test_removes_null_bytes(self):
        """Test that null bytes are removed."""
        assert sanitize_filename("file\x00name.txt") == "filename.txt"

    def test_removes_parent_directory_references(self):
        """Test that parent directory references are removed (.. -> _)."""
        result = sanitize_filename("../../etc/passwd")
        assert ".." not in result
        assert "etc" in result and "passwd" in result

    def test_trims_whitespace_and_dots(self):
        """Test that leading/trailing whitespace and dots are removed."""
        assert sanitize_filename("  .file.txt.  ") == "file.txt"

    def test_limits_length(self):
        """Test that very long filenames are truncated."""
        long_name = "a" * 300 + ".txt"
        result = sanitize_filename(long_name)
        assert len(result) <= 255

    def test_empty_name_fallback(self):
        """Test that empty sanitized names fallback to 'unnamed_file'."""
        assert sanitize_filename("   ") == "unnamed_file"

    def test_normal_filename_unchanged(self):
        """Test that normal filenames are not modified."""
        assert sanitize_filename("document.pdf") == "document.pdf"
        assert sanitize_filename("my-file_name.txt") == "my-file_name.txt"
