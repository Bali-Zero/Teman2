#!/usr/bin/env python3
"""
Real CRM Client Matching via API

Queries the production CRM via HTTP API and matches Dropbox folders to real clients.
"""

import sys
import json
import csv
import requests
from datetime import datetime
from pathlib import Path

# Import client matcher
try:
    from client_folder_matcher import fuzzy_match_clients, categorize_folders, DROPBOX_FOLDERS
except ImportError:
    print("❌ Could not import client_folder_matcher. Make sure it's in the same directory.")
    sys.exit(1)


# API Configuration
API_BASE_URL = "https://nuzantara.fly.dev"  # Production API
# API_BASE_URL = "http://localhost:8080"  # Local development

# Authentication token (admin user)
# This is needed to access the CRM API
AUTH_TOKEN = None  # Will prompt if needed


def fetch_crm_clients_via_api(api_url=API_BASE_URL, auth_token=None):
    """Fetch all clients from CRM via HTTP API"""
    print("🔍 Fetching clients from CRM API...")

    try:
        headers = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        # Try to fetch clients
        response = requests.get(
            f"{api_url}/api/crm/clients",
            headers=headers,
            params={"limit": 500},  # Get all clients
            timeout=30
        )

        if response.status_code == 401:
            print("❌ Authentication required. Please provide admin credentials.")
            return None

        if response.status_code != 200:
            print(f"❌ API error: {response.status_code} - {response.text[:200]}")
            return None

        clients_data = response.json()

        # Convert to our expected format
        client_list = [
            {
                "id": client.get("id"),
                "name": client.get("full_name"),
                "type": client.get("client_type", "individual"),
                "email": client.get("email")
            }
            for client in clients_data
        ]

        print(f"✅ Found {len(client_list)} clients in CRM")
        return client_list

    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return None
    except Exception as e:
        print(f"❌ Error fetching clients: {e}")
        return None


def save_matching_csv(matches, output_file="dropbox_crm_matching.csv"):
    """Save matching results to CSV for manual review"""

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'dropbox_folder',
            'crm_client_id',
            'crm_client_name',
            'similarity_score',
            'confidence',
            'needs_review',
            'action',
            'notes'
        ])

        writer.writeheader()

        for match in matches:
            writer.writerow({
                'dropbox_folder': match['dropbox_folder'],
                'crm_client_id': match['crm_client_id'] or '',
                'crm_client_name': match['crm_client_name'] or '',
                'similarity_score': match['similarity_score'],
                'confidence': match['confidence'],
                'needs_review': 'YES' if match['needs_review'] else 'NO',
                'action': 'MIGRATE' if match['crm_client_id'] else 'SKIP',
                'notes': ''
            })

    print(f"💾 Matching CSV saved to: {output_file}")


def main():
    print("\n" + "="*80)
    print("🔍 DROPBOX → CRM CLIENT MATCHING (VIA API)")
    print("="*80 + "\n")

    # Fetch real CRM clients via API
    crm_clients = fetch_crm_clients_via_api(api_url=API_BASE_URL, auth_token=AUTH_TOKEN)

    if not crm_clients:
        print("\n⚠️  Could not fetch CRM clients via API.")
        print("\nOPTIONS:")
        print("1. Make sure the backend is running")
        print("2. Check API_BASE_URL in the script")
        print("3. Provide authentication token if needed")
        return 1

    print(f"\n📊 Analyzing {len(DROPBOX_FOLDERS)} Dropbox folders...")

    # Run fuzzy matching
    results = fuzzy_match_clients(crm_clients, threshold=0.6)

    # Print summary
    print("\n" + "="*80)
    print("📊 MATCHING RESULTS")
    print("="*80)

    print(f"\n📁 Total Dropbox Folders: {results['summary']['total_dropbox_folders']}")
    print(f"   • Potential Clients: {results['summary']['potential_clients']}")
    print(f"   • Process Folders: {results['summary']['process_folders']}")
    print(f"   • Utility Folders: {results['summary']['utility_folders']}")

    print(f"\n🎯 Matching Confidence:")
    print(f"   • High (≥80%): {results['summary']['high_confidence_matches']}")
    print(f"   • Medium (≥60%): {results['summary']['medium_confidence_matches']}")
    print(f"   • Low (<60%): {results['summary']['low_confidence_matches']}")

    print(f"\n✅ HIGH CONFIDENCE MATCHES:")
    high_matches = [m for m in results['matches'] if m['confidence'] == 'high']
    for match in high_matches[:10]:  # Show first 10
        print(f"   📁 {match['dropbox_folder']}")
        print(f"      → CRM: {match['crm_client_name']} (ID: {match['crm_client_id']})")
        print(f"      Score: {match['similarity_score']:.1%}")
    if len(high_matches) > 10:
        print(f"   ... and {len(high_matches) - 10} more")

    print(f"\n⚠️  MEDIUM CONFIDENCE MATCHES (NEED REVIEW):")
    medium_matches = [m for m in results['matches'] if m['confidence'] == 'medium']
    for match in medium_matches:
        print(f"   📁 {match['dropbox_folder']}")
        print(f"      → CRM: {match['crm_client_name']} (ID: {match['crm_client_id']})")
        print(f"      Score: {match['similarity_score']:.1%}")

    print(f"\n❌ NO MATCH / LOW CONFIDENCE:")
    low_matches = [m for m in results['matches'] if m['confidence'] == 'low']
    for match in low_matches[:5]:  # Show first 5
        print(f"   📁 {match['dropbox_folder']}")
        if match['crm_client_name']:
            print(f"      Best guess: {match['crm_client_name']} (Score: {match['similarity_score']:.1%})")
        else:
            print(f"      No match found")
    if len(low_matches) > 5:
        print(f"   ... and {len(low_matches) - 5} more")

    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Save JSON report
    json_file = f"crm_matching_report_{timestamp}.json"
    with open(json_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Full JSON report saved to: {json_file}")

    # Save CSV for manual review
    csv_file = f"dropbox_crm_matching_{timestamp}.csv"
    save_matching_csv(results['matches'], csv_file)

    print("\n" + "="*80)
    print("✅ NEXT STEPS:")
    print("="*80)
    print(f"\n1. Review the CSV file: {csv_file}")
    print(f"   - Check 'needs_review' = YES rows")
    print(f"   - Verify all high confidence matches")
    print(f"   - Manually match low confidence folders")
    print(f"\n2. Update the 'action' column:")
    print(f"   - MIGRATE = Include in migration")
    print(f"   - SKIP = Exclude from migration")
    print(f"   - MANUAL = Needs manual intervention")
    print(f"\n3. Add notes for any special cases")
    print(f"\n4. Save the CSV and proceed with migration planning")
    print("\n" + "="*80 + "\n")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
