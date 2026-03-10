#!/usr/bin/env python3
"""
Phase 1 Files Verification - Check that all code is deployed

Verifies:
1. All Phase 1 files exist
2. Categorization service works
3. Key functions are present
"""

import os
import sys

# Color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def check_file(filepath, description):
    """Check if file exists and return size"""
    if os.path.exists(filepath):
        size = os.path.getsize(filepath)
        print(f"{GREEN}✓{RESET} {description}")
        print(f"  Path: {filepath}")
        print(f"  Size: {size:,} bytes")
        return True
    else:
        print(f"{RED}✗{RESET} {description}")
        print(f"  Path: {filepath} (NOT FOUND)")
        return False


def test_categorization():
    """Test categorization service directly"""
    print(f"\n{BLUE}🧪 Testing Auto-Categorization Service...{RESET}")

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../apps/backend-rag"))

    try:
        from backend.services.crm.document_categorizer import (
            auto_categorize_document,
            extract_expiry_date,
        )

        test_cases = [
            ("Passport_JOHN_DOE_2028-12-31.pdf", "immigration", "Passport"),
            ("KITAS_2025-06-15.jpg", "immigration", "Kitas"),
            ("Akta_PT_ABC.pdf", "pma", "Akta"),
            ("NPWP_Company_123.pdf", "pma", "Npwp Company"),
            ("SPT_2023.pdf", "tax", "Spt"),
            ("Invoice_December.pdf", "tax", "Invoice"),
            ("Photo_3x4.jpg", "personal", "Photo"),
            ("CV_Resume.pdf", "personal", "Cv"),
        ]

        passed = 0
        failed = 0

        for filename, expected_cat, expected_type in test_cases:
            result = auto_categorize_document(filename)
            actual_cat = result["document_category"]
            actual_type = result["document_type"]
            confidence = result["confidence"]

            if actual_cat == expected_cat and actual_type == expected_type:
                print(f"{GREEN}✓{RESET} {filename}")
                print(f"  → {actual_cat}/{actual_type} (confidence: {confidence:.2f})")
                passed += 1
            else:
                print(f"{RED}✗{RESET} {filename}")
                print(f"  Expected: {expected_cat}/{expected_type}")
                print(f"  Got: {actual_cat}/{actual_type}")
                failed += 1

        # Test date extraction
        print(f"\n{BLUE}📅 Testing Date Extraction...{RESET}")
        date_tests = [
            ("Passport_2028-12-31.pdf", "2028-12-31"),
            ("KITAS_20251215.jpg", "2025-12-15"),
            ("Document_2025/06/30.pdf", "2025-06-30"),
        ]

        for filename, expected_date in date_tests:
            extracted = extract_expiry_date(filename)
            if extracted == expected_date:
                print(f"{GREEN}✓{RESET} {filename} → {extracted}")
                passed += 1
            else:
                print(
                    f"{RED}✗{RESET} {filename} → Expected {expected_date}, got {extracted}"
                )
                failed += 1

        print(f"\n{BLUE}📊 Categorization Test Results:{RESET}")
        print(f"  Passed: {GREEN}{passed}{RESET}")
        print(f"  Failed: {RED}{failed}{RESET}")
        print(f"  Success Rate: {passed / (passed + failed) * 100:.1f}%")

        return failed == 0

    except ImportError as e:
        print(f"{RED}✗ Cannot import categorization service: {e}{RESET}")
        return False
    except Exception as e:
        print(f"{RED}✗ Categorization test failed: {e}{RESET}")
        return False


def main():
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{BLUE}PHASE 1 FILES VERIFICATION{RESET}")
    print(f"{BLUE}{'=' * 60}{RESET}\n")

    base_path = os.path.join(os.path.dirname(__file__), "../apps/backend-rag")

    # Files to check
    files_to_check = [
        (
            f"{base_path}/backend/app/routers/crm_drive_folders.py",
            "CRM Drive Folders Router (NEW)",
        ),
        (
            f"{base_path}/backend/app/routers/crm_enhanced.py",
            "CRM Enhanced Router (MODIFIED)",
        ),
        (
            f"{base_path}/backend/app/routers/crm_migration.py",
            "CRM Migration Router (NEW)",
        ),
        (
            f"{base_path}/backend/services/crm/document_categorizer.py",
            "Document Categorizer Service (NEW)",
        ),
        (
            f"{base_path}/backend/services/integrations/google_drive_service.py",
            "Google Drive Service (MODIFIED)",
        ),
        (f"{base_path}/backend/app/core/config.py", "Config (MODIFIED)"),
        (
            f"{base_path}/backend/app/setup/router_registration.py",
            "Router Registration (MODIFIED)",
        ),
    ]

    print(f"{BLUE}📁 Checking Phase 1 Files...{RESET}\n")

    files_exist = 0
    files_missing = 0

    for filepath, description in files_to_check:
        if check_file(filepath, description):
            files_exist += 1
        else:
            files_missing += 1
        print()

    # Test categorization
    categorization_ok = test_categorization()

    # Summary
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{BLUE}VERIFICATION SUMMARY{RESET}")
    print(f"{BLUE}{'=' * 60}{RESET}\n")

    print(f"Files Found: {GREEN}{files_exist}/{len(files_to_check)}{RESET}")
    print(f"Files Missing: {RED}{files_missing}/{len(files_to_check)}{RESET}")
    print(
        f"Categorization: {GREEN + '✓ PASS' if categorization_ok else RED + '✗ FAIL'}{RESET}"
    )

    if files_missing == 0 and categorization_ok:
        print(
            f"\n{GREEN}🎉 ALL CHECKS PASSED! Phase 1 code is complete and working!{RESET}"
        )
        return 0
    else:
        print(f"\n{YELLOW}⚠️  Some checks failed. Review errors above.{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
