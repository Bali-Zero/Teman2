import sys
import time

import requests

BASE_URL = "http://127.0.0.1:8080"
API_KEY = "dev_api_key_for_testing_only"


def test_crm_integration():
    print(f"🚀 Starting Integration Test: CRM Clients Enhanced on {BASE_URL}")

    headers = {"X-API-Key": API_KEY}

    # 1. List Clients (Verify Sentiment & Structure)
    print("\n📡 Fetching client list...")
    try:
        response = requests.get(f"{BASE_URL}/api/crm/clients", headers=headers)
        response.raise_for_status()
        clients = response.json()
        print(f"✅ Client list fetched. Found {len(clients)} clients.")

        if len(clients) == 0:
            print("⚠️ No clients found. Creating a test client...")
            new_client = {
                "full_name": "Test Client Integration",
                "email": f"test.integration.{int(time.time())}@example.com",
                "status": "LEAD",
                "nationality": "Italian",
                "phone": "+391234567890",
                "client_type": "individual",
                "assigned_to": "user@zantara.dev",
                "notes": "Created by integration test",
            }
            create_resp = requests.post(
                f"{BASE_URL}/api/crm/clients?created_by=test_script",
                json=new_client,
                headers=headers,
            )
            create_resp.raise_for_status()
            print("✅ Test client created.")
            # Fetch list again
            response = requests.get(f"{BASE_URL}/api/crm/clients", headers=headers)
            clients = response.json()

        if len(clients) > 0:
            first_client = clients[0]
            # Check for new fields
            if "last_sentiment" in first_client:
                print(f"✅ 'last_sentiment' field present: {first_client.get('last_sentiment')}")
            else:
                print("❌ 'last_sentiment' field MISSING")

            if "last_interaction_summary" in first_client:
                print("✅ 'last_interaction_summary' field present")
            else:
                print("❌ 'last_interaction_summary' field MISSING")

            if "avatar_url" in first_client:
                print("✅ 'avatar_url' field present")

            # Check Kanban status
            print(f"ℹ️ First client status: {first_client.get('status')}")

            # 2. Update Status (Kanban Move)
            client_id = first_client["id"]
            new_status = "active" if first_client["status"] != "active" else "prospect"
            print(
                f"\n🔄 Testing Kanban Drag & Drop (Status Update) for Client {client_id} -> {new_status}"
            )

            patch_payload = {"status": new_status}
            patch_resp = requests.patch(
                f"{BASE_URL}/api/crm/clients/{client_id}?updated_by=test_script",
                json=patch_payload,
                headers=headers,
            )

            if patch_resp.status_code == 200:
                print("✅ Status update successful")
                updated_client = patch_resp.json()
                if updated_client["status"] == new_status:
                    print(f"✅ Status verification passed: {updated_client['status']}")
                else:
                    print(
                        f"❌ Status mismatch: expected {new_status}, got {updated_client['status']}"
                    )
            else:
                print(f"❌ Status update failed: {patch_resp.status_code} - {patch_resp.text}")

        else:
            print("⚠️ No clients found to test details/updates.")

    except requests.exceptions.ConnectionError:
        print("❌ Connection error: Could not connect to backend.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Wait a bit for server to be fully ready if running immediately after start
    # time.sleep(2)
    test_crm_integration()
