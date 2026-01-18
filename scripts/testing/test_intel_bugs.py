#!/usr/bin/env python3
"""
Test script to reproduce potential bugs in Intel services.

This script tests:
- Race conditions in duplicate checking
- File write atomicity
- Archive operations under concurrent access
- Error handling in voting status saving
"""

import sys
import time
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent / "apps" / "backend-rag" / "backend"
sys.path.insert(0, str(backend_path))

from services.intel.intel_staging_service import IntelStagingService
from services.intel.intel_approval_service import IntelApprovalService


def test_concurrent_duplicate_check():
    """Test race condition in duplicate checking."""
    print("=" * 60)
    print("TEST: Concurrent Duplicate Check (Race Condition)")
    print("=" * 60)

    service = IntelStagingService()
    test_url = "https://test-example.com/article-123"

    # Simulate concurrent duplicate checks
    def check_duplicate():
        return service.check_duplicate("visa", test_url)

    # Run multiple checks concurrently
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(check_duplicate) for _ in range(5)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    print(f"Concurrent checks completed: {len(results)}")
    print(f"Results: {[r is not None for r in results]}")
    print()


def test_file_write_atomicity():
    """Test file write atomicity."""
    print("=" * 60)
    print("TEST: File Write Atomicity")
    print("=" * 60)

    service = IntelStagingService()
    test_data = {
        "item_id": "test_atomic_123",
        "title": "Test Article",
        "content": "Test content",
        "source_url": "https://test.com",
    }

    try:
        # Save item
        file_path = service.save_staging_item("visa", "test_atomic_123", test_data)
        print(f"File saved: {file_path}")
        print(f"File exists: {file_path.exists()}")

        # Try to read it back
        loaded = service.load_staging_item("visa", "test_atomic_123")
        print(f"File loaded successfully: {loaded is not None}")
        if loaded:
            print(f"Content matches: {loaded.get('title') == test_data['title']}")

        # Cleanup
        if file_path.exists():
            file_path.unlink()
            print("Test file cleaned up")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
    print()


def test_archive_race_condition():
    """Test race condition in archive operation."""
    print("=" * 60)
    print("TEST: Archive Race Condition")
    print("=" * 60)

    service = IntelStagingService()
    test_data = {
        "item_id": "test_archive_123",
        "title": "Test Article",
        "content": "Test content",
        "source_url": "https://test.com",
    }

    try:
        # Create test item
        file_path = service.save_staging_item("visa", "test_archive_123", test_data)
        print(f"Test item created: {file_path.exists()}")

        # Simulate concurrent read while archiving
        def read_item():
            return service.load_staging_item("visa", "test_archive_123")

        def archive_item():
            time.sleep(0.1)  # Small delay
            return service.archive_item("visa", "test_archive_123", "approved")

        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            read_future = executor.submit(read_item)
            archive_future = executor.submit(archive_item)

            read_result = read_future.result()
            archive_result = archive_future.result()

        print(f"Read result: {read_result is not None}")
        print(f"Archive result: {archive_result}")
        print(
            f"Archive file exists: {archive_result.exists() if archive_result else False}"
        )

        # Cleanup
        if archive_result and archive_result.exists():
            archive_result.unlink()
            archive_result.parent.rmdir()  # Remove archive dir if empty
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
    print()


def test_voting_status_error_handling():
    """Test error handling in voting status saving."""
    print("=" * 60)
    print("TEST: Voting Status Error Handling")
    print("=" * 60)

    service = IntelApprovalService()
    test_data = {
        "item_id": "test_voting_123",
        "title": "Test Article",
        "content": "Test content",
    }

    try:
        # Try to save voting status
        service._save_voting_status(
            "test_voting_123",
            "visa",
            test_data,
            None,
            None,
        )
        print("Voting status saved successfully")

        # Check if file exists
        status_file = service.pending_intel_path / "test_voting_123.json"
        print(f"Status file exists: {status_file.exists()}")

        # Cleanup
        if status_file.exists():
            status_file.unlink()
    except Exception as e:
        print(f"ERROR (expected if path doesn't exist): {e}")
        import traceback

        traceback.print_exc()
    print()


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Intel Services Bug Reproduction Tests")
    print("=" * 60 + "\n")

    test_concurrent_duplicate_check()
    test_file_write_atomicity()
    test_archive_race_condition()
    test_voting_status_error_handling()

    print("=" * 60)
    print("All tests completed. Check debug.log for detailed logs.")
    print("=" * 60)


if __name__ == "__main__":
    main()
