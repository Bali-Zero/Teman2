#!/usr/bin/env python3
"""
Add Service Account to Google Workspace Shared Drive

This script uses OAuth2 to authenticate as a user with access to the Shared Drive,
then uses the Drive API to add the Service Account as a member.

Usage:
    python3 scripts/add_service_account_to_shared_drive.py

Requirements:
    pip install google-auth google-auth-oauthlib google-api-python-client
"""

import sys
from pathlib import Path

# Add backend to path for config access
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "backend-rag"))

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle

# Configuration
SERVICE_ACCOUNT_EMAIL = "nuzantara-drive-bot@nuzantara.iam.gserviceaccount.com"
SHARED_DRIVE_ID = "0AJC3-SJL03OOUk9PVA"  # AMBARADAM Shared Drive
SCOPES = [
    "https://www.googleapis.com/auth/drive",
]

# OAuth credentials file path (you need to download this from Google Cloud Console)
OAUTH_CREDENTIALS_PATH = Path(__file__).parent / "oauth_client_secret.json"
TOKEN_PATH = Path(__file__).parent / "user_token.pickle"


def get_oauth_credentials():
    """Get OAuth2 credentials for an authorized user."""
    creds = None

    # Check for cached token
    if TOKEN_PATH.exists():
        with open(TOKEN_PATH, "rb") as token:
            creds = pickle.load(token)

    # If no valid credentials, run OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not OAUTH_CREDENTIALS_PATH.exists():
                print(f"""
❌ OAuth credentials file not found at: {OAUTH_CREDENTIALS_PATH}

To create OAuth credentials:
1. Go to Google Cloud Console: https://console.cloud.google.com/apis/credentials
2. Select project 'nuzantara'
3. Click "Create Credentials" → "OAuth client ID"
4. Choose "Desktop app"
5. Download the JSON file
6. Save it as: {OAUTH_CREDENTIALS_PATH}

Then run this script again.
""")
                sys.exit(1)

            flow = InstalledAppFlow.from_client_secrets_file(
                str(OAUTH_CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=8080)

        # Save credentials for future runs
        with open(TOKEN_PATH, "wb") as token:
            pickle.dump(creds, token)

    return creds


def add_service_account_to_shared_drive(creds):
    """Add the Service Account as a member of the Shared Drive."""
    service = build("drive", "v3", credentials=creds)

    # First, check if Service Account is already a member
    print("🔍 Checking existing members of Shared Drive...")

    try:
        # List permissions on the Shared Drive
        permissions = (
            service.permissions()
            .list(
                fileId=SHARED_DRIVE_ID,
                supportsAllDrives=True,
                useDomainAdminAccess=False,
                fields="permissions(id, emailAddress, role, type)",
            )
            .execute()
        )

        existing_emails = [
            p.get("emailAddress", "").lower()
            for p in permissions.get("permissions", [])
        ]

        if SERVICE_ACCOUNT_EMAIL.lower() in existing_emails:
            print(f"✅ Service Account {SERVICE_ACCOUNT_EMAIL} is already a member!")
            return True

        print(f"📋 Current members: {len(existing_emails)}")
        for p in permissions.get("permissions", []):
            print(f"   - {p.get('emailAddress', 'unknown')} ({p.get('role')})")

    except Exception as e:
        print(f"⚠️ Could not list existing permissions: {e}")

    # Add the Service Account as organizer (full access)
    print("\n📤 Adding Service Account to Shared Drive...")
    print(f"   Email: {SERVICE_ACCOUNT_EMAIL}")
    print(f"   Drive ID: {SHARED_DRIVE_ID}")
    print("   Role: organizer (full access)")

    try:
        permission = {
            "type": "user",
            "role": "organizer",  # Full access to manage files
            "emailAddress": SERVICE_ACCOUNT_EMAIL,
        }

        result = (
            service.permissions()
            .create(
                fileId=SHARED_DRIVE_ID,
                body=permission,
                supportsAllDrives=True,
                useDomainAdminAccess=False,
                sendNotificationEmail=False,  # Don't send email to service account
                fields="id, emailAddress, role",
            )
            .execute()
        )

        print(f"""
✅ SUCCESS! Service Account added to Shared Drive

   Permission ID: {result.get("id")}
   Email: {result.get("emailAddress")}
   Role: {result.get("role")}

The Service Account now has access to AMBARADAM Shared Drive.
Department folders should now appear on kita.balizero.com/documents
""")
        return True

    except Exception as e:
        print(f"""
❌ Failed to add Service Account: {e}

Possible reasons:
1. You don't have permission to manage Shared Drive members
2. The Shared Drive doesn't allow external members
3. The Service Account email is invalid

Try running as a Workspace admin (zer0@balizero.com).
""")
        return False


def main():
    print(
        """
╔══════════════════════════════════════════════════════════════╗
║  Add Service Account to Google Workspace Shared Drive        ║
╚══════════════════════════════════════════════════════════════╝

This script will:
1. Open a browser for OAuth2 authentication
2. Authenticate as a user with Shared Drive access
3. Add the Service Account as a member via Drive API

Service Account: {sa}
Shared Drive ID: {sd}
""".format(sa=SERVICE_ACCOUNT_EMAIL, sd=SHARED_DRIVE_ID)
    )

    input("Press Enter to continue (this will open a browser for authentication)...")

    # Get OAuth credentials
    print("\n🔐 Getting OAuth2 credentials...")
    creds = get_oauth_credentials()
    print("✅ Authenticated successfully!")

    # Add Service Account to Shared Drive
    success = add_service_account_to_shared_drive(creds)

    if success:
        print("""
╔══════════════════════════════════════════════════════════════╗
║  Next Steps                                                  ║
╚══════════════════════════════════════════════════════════════╝

1. Wait 1-2 minutes for permissions to propagate
2. Visit https://kita.balizero.com/documents
3. You should see the department folders:
   - BOARD
   - CRM
   - MARKETING
   - TAX DEPARTMENT
   - PERATURAN
""")
    else:
        print("\n❌ Failed. Try the alternative method below.")


if __name__ == "__main__":
    main()
