import os
import sys
import uuid

import requests

BASE_URL = "http://127.0.0.1:8080"
API_KEY = os.getenv("API_KEY")

if not API_KEY:
    print("❌ ERROR: API_KEY environment variable is required")
    print("   Set it with: export API_KEY=your_api_key")
    sys.exit(1)

HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}


def print_step(message):
    print(f"\n🔹 {message}")


def print_success(message):
    print(f"✅ {message}")


def print_error(message):
    print(f"❌ {message}")


def test_user_journey():
    print(f"🚀 Starting User Journey Simulation on {BASE_URL}")

    # Generate unique test data
    run_id = str(uuid.uuid4())[:8]
    client_name = f"Test User {run_id}"
    client_email = f"test.{run_id}@zantara.example.com"

    # ==============================================================================
    # 1. SCENARIO: CLICK "ADD CLIENT" BUTTON
    # ==============================================================================
    print_step("SCENARIO 1: User clicks 'Add Client' and fills full form")

    new_client_data = {
        "full_name": client_name,
        "email": client_email,
        "phone": "+628123456789",
        "whatsapp": "+628123456789",
        "nationality": "Italian",
        "passport_number": f"E{run_id.upper()}",
        "client_type": "individual",
        "assigned_to": "user@zantara.dev",  # Assign to self to ensure visibility
        "avatar_url": "https://ui-avatars.com/api/?name=Test+User",
        "address": "Jalan Sunset Road No. 88, Bali",
        "notes": "Interested in KITAS and PMA setup.",
        "tags": ["vip", "urgent", "referral"],
        "custom_fields": {"referral_source": "Google", "budget": "High"},
    }

    try:
        resp = requests.post(
            f"{BASE_URL}/api/crm/clients/?created_by=test_script",
            json=new_client_data,
            headers=HEADERS,
        )
        resp.raise_for_status()
        client = resp.json()
        client_id = client["id"]
        print_success(f"Client created successfully with ID: {client_id}")

        # Verify fields
        assert client["full_name"] == client_name
        assert "vip" in client["tags"]
        assert client["status"] == "active"  # Default status
        print_success("Client data verified matches form input")

    except Exception as e:
        print_error(f"Failed to create client: {e}")
        if "resp" in locals():
            print(resp.text)
        sys.exit(1)

    # ==============================================================================
    # 2. SCENARIO: CLICK "EDIT" BUTTON
    # ==============================================================================
    print_step("SCENARIO 2: User clicks 'Edit', changes phone and adds tag")

    update_data = {
        "phone": "+628999999999",
        "tags": ["vip", "urgent", "referral", "paid"],  # Adding 'paid'
        "notes": "Updated: Client has paid deposit.",
    }

    try:
        resp = requests.patch(
            f"{BASE_URL}/api/crm/clients/{client_id}?updated_by=test_script",
            json=update_data,
            headers=HEADERS,
        )
        resp.raise_for_status()
        updated_client = resp.json()

        assert updated_client["phone"] == "+628999999999"
        assert "paid" in updated_client["tags"]
        print_success("Client updated successfully")

    except Exception as e:
        print_error(f"Failed to update client: {e}")
        sys.exit(1)

    # ==============================================================================
    # 3. SCENARIO: KANBAN DRAG & DROP (STATUS CHANGE)
    # ==============================================================================
    print_step("SCENARIO 3: User drags client from 'Active' to 'Prospect' (Kanban)")

    try:
        # Move to Prospect
        resp = requests.patch(
            f"{BASE_URL}/api/crm/clients/{client_id}?updated_by=test_script",
            json={"status": "prospect"},
            headers=HEADERS,
        )
        resp.raise_for_status()
        assert resp.json()["status"] == "prospect"
        print_success("Status changed to 'prospect'")

        # Move back to Active
        resp = requests.patch(
            f"{BASE_URL}/api/crm/clients/{client_id}?updated_by=test_script",
            json={"status": "active"},
            headers=HEADERS,
        )
        resp.raise_for_status()
        assert resp.json()["status"] == "active"
        print_success("Status changed back to 'active'")

    except Exception as e:
        print_error(f"Failed to change status: {e}")
        sys.exit(1)

    # ==============================================================================
    # 4. SCENARIO: SEARCH BAR
    # ==============================================================================
    print_step(f"SCENARIO 4: User types '{run_id}' in search bar")

    try:
        resp = requests.get(
            f"{BASE_URL}/api/crm/clients/?search={run_id}&limit=10", headers=HEADERS
        )
        resp.raise_for_status()
        results = resp.json()

        found = False
        for c in results:
            if c["id"] == client_id:
                found = True
                break

        if found:
            print_success(f"Search found client among {len(results)} results")
        else:
            print_error("Search failed to find the client")
            sys.exit(1)

    except Exception as e:
        print_error(f"Search failed: {e}")
        sys.exit(1)

    # ==============================================================================
    # 5. SCENARIO: CLICK "DELETE" BUTTON
    # ==============================================================================
    print_step("SCENARIO 5: User clicks 'Delete' (Soft Delete)")

    try:
        resp = requests.delete(
            f"{BASE_URL}/api/crm/clients/{client_id}?deleted_by=test_script", headers=HEADERS
        )
        resp.raise_for_status()
        print_success("Client deleted successfully")

        # Verify it's inactive
        resp = requests.get(f"{BASE_URL}/api/crm/clients/{client_id}", headers=HEADERS)
        if resp.status_code == 200:
            final_status = resp.json()["status"]
            if final_status == "inactive":
                print_success("Client status verified as 'inactive' (Soft Delete)")
            else:
                print_error(f"Client status is {final_status}, expected 'inactive'")
        else:
            print_error("Could not fetch deleted client to verify status")

    except Exception as e:
        print_error(f"Delete failed: {e}")
        sys.exit(1)

    print("\n🎉 ALL SCENARIOS PASSED. The 'buttons' work!")


if __name__ == "__main__":
    test_user_journey()
