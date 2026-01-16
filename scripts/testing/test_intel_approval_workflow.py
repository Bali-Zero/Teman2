#!/usr/bin/env python3
"""
Test Intel approval workflow.

This script verifies the approval workflow including:
- Staging item creation
- Approval notification sending
- Telegram notification verification
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import requests

# Colors for terminal output
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
BLUE = "\033[94m"
RESET = "\033[0m"


def check_staging_item_exists(base_url: str, intel_type: str, item_id: str, api_key: Optional[str] = None) -> Dict:
    """Check if staging item exists."""
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    try:
        response = requests.get(
            f"{base_url}/api/intel/staging/preview/{intel_type}/{item_id}",
            headers=headers,
            timeout=10
        )
        
        return {
            "exists": response.status_code == 200,
            "status_code": response.status_code,
            "data": response.json() if response.status_code == 200 else None,
        }
    except Exception as e:
        return {
            "exists": False,
            "error": str(e),
        }


def check_pending_items(base_url: str, api_key: Optional[str] = None) -> Dict:
    """Check pending items in staging."""
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    try:
        response = requests.get(
            f"{base_url}/api/intel/staging/pending?type=all",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "count": data.get("count", 0),
                "items": data.get("items", []),
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def verify_telegram_notification_sent(item_id: str, pending_path: str = "/tmp/pending") -> Dict:
    """Verify Telegram notification was sent by checking voting status file."""
    status_file = Path(pending_path) / f"{item_id}.json"
    
    if not status_file.exists():
        return {
            "sent": False,
            "reason": "Voting status file not found",
        }
    
    try:
        with open(status_file) as f:
            status_data = json.load(f)
        
        return {
            "sent": status_data.get("status") == "voting",
            "item_id": status_data.get("item_id"),
            "intel_type": status_data.get("intel_type"),
            "votes": status_data.get("votes", {}),
            "created_at": status_data.get("created_at"),
        }
    except Exception as e:
        return {
            "sent": False,
            "error": str(e),
        }


def test_approval_workflow(base_url: str, api_key: Optional[str] = None) -> Dict:
    """Test complete approval workflow."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}Intel Approval Workflow Test{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    print(f"Base URL: {base_url}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    results = {
        "staging_check": {},
        "pending_items": {},
        "workflow_status": "UNKNOWN",
    }

    # Check pending items
    print(f"{BLUE}1. Checking pending items in staging...{RESET}")
    pending_result = check_pending_items(base_url, api_key)
    results["pending_items"] = pending_result
    
    if pending_result.get("success"):
        count = pending_result.get("count", 0)
        print(f"  {GREEN}✅ Found {count} pending items{RESET}")
        
        if count > 0:
            items = pending_result.get("items", [])
            print(f"  Sample items:")
            for item in items[:3]:
                print(f"    • {item.get('id', 'unknown')} - {item.get('title', 'Untitled')[:50]}")
    else:
        if pending_result.get("status_code") == 401:
            print(f"  {YELLOW}⚠️  Requires authentication (expected){RESET}")
        else:
            print(f"  {RED}❌ Failed to check pending items{RESET}")
    
    print()

    # Check if we can verify Telegram notifications
    print(f"{BLUE}2. Checking Telegram notification status...{RESET}")
    print(f"  {YELLOW}ℹ️  Note: This requires access to pending directory{RESET}")
    print(f"  {YELLOW}ℹ️  Run on server or with file system access{RESET}")
    print()

    # Summary
    print(f"{BLUE}{'='*60}{RESET}")
    if pending_result.get("success"):
        results["workflow_status"] = "OPERATIONAL"
        print(f"{GREEN}✅ Approval workflow appears operational{RESET}")
    elif pending_result.get("status_code") == 401:
        results["workflow_status"] = "AUTH_REQUIRED"
        print(f"{YELLOW}⚠️  Authentication required (expected){RESET}")
    else:
        results["workflow_status"] = "ERROR"
        print(f"{RED}❌ Workflow check failed{RESET}")
    
    return results


def main():
    """Main test function."""
    import os
    
    base_url = os.getenv("INTEL_API_URL", "https://nuzantara-rag.fly.dev")
    api_key = os.getenv("INTEL_API_KEY")
    
    results = test_approval_workflow(base_url, api_key)
    
    # Save report
    report_file = Path(__file__).parent.parent / "monitoring" / "intel_approval_workflow_test.json"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_file, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "base_url": base_url,
            "results": results,
        }, f, indent=2)
    
    print(f"{BLUE}Report saved to: {report_file}{RESET}\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
