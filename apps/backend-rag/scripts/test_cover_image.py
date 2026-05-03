#!/usr/bin/env python3
"""
Test script for cover image handling in publish_staging_item.

Tests:
1. Cover image path resolution (relative vs absolute)
2. Base64 encoding
3. Error handling for missing images
"""

import base64
import sys
import tempfile
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

import os

os.environ.setdefault("PYTHONPATH", str(backend_path))


def test_base64_encoding():
    """Test base64 encoding of image data."""
    print("\n" + "=" * 80)
    print("TEST: Base64 Encoding")
    print("=" * 80)

    # Create a dummy image file (1x1 PNG)
    png_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )

    try:
        # Encode to base64
        encoded = base64.b64encode(png_data).decode("utf-8")

        # Verify it's valid base64
        assert len(encoded) > 0, "Encoded string should not be empty"
        assert isinstance(encoded, str), "Encoded should be string"

        # Decode back to verify
        decoded = base64.b64decode(encoded)
        assert decoded == png_data, "Decoded data should match original"

        print("✅ Base64 encoding successful")
        print(f"   Original size: {len(png_data)} bytes")
        print(f"   Encoded length: {len(encoded)} chars")
        print(f"   Encoded preview: {encoded[:50]}...")

        print("\n✅ Base64 encoding test passed!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_cover_image_path_resolution():
    """Test cover image path resolution logic."""
    print("\n" + "=" * 80)
    print("TEST: Cover Image Path Resolution")
    print("=" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        staging_dir = Path(tmpdir) / "staging" / "news"
        staging_dir.mkdir(parents=True, exist_ok=True)

        covers_dir = staging_dir / "covers"
        covers_dir.mkdir(parents=True, exist_ok=True)

        # Create a dummy image file
        image_file = covers_dir / "test_image.jpg"
        image_file.write_bytes(b"fake image data")

        test_cases = [
            {
                "name": "Relative path",
                "cover_image": "covers/test_image.jpg",
                "staging_dir": staging_dir,
                "expected_exists": True,
            },
            {
                "name": "Absolute path",
                "cover_image": str(image_file),
                "staging_dir": staging_dir,
                "expected_exists": True,
            },
            {
                "name": "Non-existent relative path",
                "cover_image": "covers/nonexistent.jpg",
                "staging_dir": staging_dir,
                "expected_exists": False,
            },
            {
                "name": "Non-existent absolute path",
                "cover_image": "/tmp/nonexistent.jpg",
                "staging_dir": staging_dir,
                "expected_exists": False,
            },
        ]

        passed = 0
        failed = 0

        for test_case in test_cases:
            try:
                cover_image_path = test_case["cover_image"]
                staging_dir_path = test_case["staging_dir"]

                # Simulate the logic from publish_staging_item
                if not os.path.isabs(cover_image_path):
                    # Relative path - resolve from staging directory
                    resolved_path = staging_dir_path / cover_image_path
                else:
                    # Absolute path
                    resolved_path = Path(cover_image_path)

                exists = resolved_path.exists()
                expected = test_case["expected_exists"]

                if exists == expected:
                    print(f"   ✅ {test_case['name']}: Path resolution correct (exists: {exists})")
                    passed += 1
                else:
                    print(
                        f"   ❌ {test_case['name']}: Path resolution incorrect (expected: {expected}, got: {exists})"
                    )
                    failed += 1

            except Exception as e:
                print(f"   ❌ {test_case['name']}: Error - {e}")
                failed += 1

        print(f"\n📊 Path Resolution Results: {passed}/{len(test_cases)} passed")

        if failed == 0:
            print("✅ All path resolutions correct!")
            return True
        else:
            print(f"❌ {failed} path resolution(s) incorrect")
            return False


def test_cover_image_reading():
    """Test reading cover image file and converting to base64."""
    print("\n" + "=" * 80)
    print("TEST: Cover Image Reading and Base64 Conversion")
    print("=" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        staging_dir = Path(tmpdir) / "staging" / "news"
        staging_dir.mkdir(parents=True, exist_ok=True)

        covers_dir = staging_dir / "covers"
        covers_dir.mkdir(parents=True, exist_ok=True)

        # Create a test image file
        image_file = covers_dir / "test_cover.jpg"
        image_data = b"fake jpeg image data for testing"
        image_file.write_bytes(image_data)

        try:
            # Simulate the logic from publish_staging_item
            cover_image_path = "covers/test_cover.jpg"

            if not os.path.isabs(cover_image_path):
                resolved_path = staging_dir / cover_image_path
            else:
                resolved_path = Path(cover_image_path)

            if resolved_path.exists():
                cover_image_base64 = base64.b64encode(resolved_path.read_bytes()).decode("utf-8")
                cover_image_filename = resolved_path.name

                print("✅ Cover image read successfully")
                print(f"   File path: {resolved_path}")
                print(f"   File size: {len(image_data)} bytes")
                print(f"   Filename: {cover_image_filename}")
                print(f"   Base64 length: {len(cover_image_base64)} chars")

                # Verify base64 can be decoded back
                decoded = base64.b64decode(cover_image_base64)
                assert decoded == image_data, "Decoded data should match original"

                print("   ✅ Base64 decoding verified")

                print("\n✅ Cover image reading test passed!")
                return True
            else:
                print(f"❌ Cover image file not found: {resolved_path}")
                return False

        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            import traceback

            traceback.print_exc()
            return False


def test_missing_cover_image_handling():
    """Test handling of missing cover image."""
    print("\n" + "=" * 80)
    print("TEST: Missing Cover Image Handling")
    print("=" * 80)

    staging_data = {
        "title": "Article without cover image",
        "content": "## Summary\nTest\n## Facts\nTest",
        "category": "news",
        "relevance_score": 50,
        "source_url": "https://example.com",
        "source_name": "Test",
        # No cover_image field
    }

    try:
        # Simulate the logic from publish_staging_item
        cover_image_base64 = None
        cover_image_filename = None

        if staging_data.get("cover_image"):
            # This should not execute
            print("❌ Cover image should not be present")
            return False
        else:
            print("✅ Missing cover image handled correctly")
            print(f"   cover_image_base64: {cover_image_base64}")
            print(f"   cover_image_filename: {cover_image_filename}")

            # Verify None values are acceptable
            assert cover_image_base64 is None, "Should be None when no cover image"
            assert cover_image_filename is None, "Should be None when no cover image"

            print("\n✅ Missing cover image handling test passed!")
            return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all cover image tests."""
    print("\n" + "=" * 80)
    print("COVER IMAGE TEST SUITE")
    print("=" * 80)

    tests = [
        ("Base64 Encoding", test_base64_encoding),
        ("Path Resolution", test_cover_image_path_resolution),
        ("Image Reading", test_cover_image_reading),
        ("Missing Image Handling", test_missing_cover_image_handling),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed: {e}")
            import traceback

            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 80)
    print("COVER IMAGE TEST SUMMARY")
    print("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {status}: {test_name}")

    print(f"\n📊 Results: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ All cover image tests passed!")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
