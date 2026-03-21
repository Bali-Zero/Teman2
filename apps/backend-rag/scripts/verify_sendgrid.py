#!/usr/bin/env python3
"""
SendGrid Configuration Verification Script
==========================================

Verifies that SendGrid is properly configured and can send emails.

Usage:
    python verify_sendgrid.py [test_email]

Example:
    python verify_sendgrid.py test@example.com
"""

import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import aiohttp


async def verify_sendgrid_config(test_email: str | None = None):
    """Verify SendGrid configuration."""
    api_key = os.getenv("SENDGRID_API_KEY")

    print("🔍 Verifying SendGrid configuration...")
    print()

    # Check environment variables
    print("1️⃣ Checking environment variables...")
    if not api_key:
        print("   ❌ SENDGRID_API_KEY not set")
        print("   💡 Run: flyctl secrets set SENDGRID_API_KEY=xxx -a backend-rag")
        return False
    else:
        masked_key = api_key[:10] + "..." + api_key[-4:] if len(api_key) > 14 else "***"
        print(f"   ✅ SENDGRID_API_KEY: {masked_key}")

    email_provider = os.getenv("EMAIL_PROVIDER", "sendgrid")
    print(f"   ✅ EMAIL_PROVIDER: {email_provider}")
    print()

    # Test API connectivity
    print("2️⃣ Testing SendGrid API connectivity...")
    try:
        async with (
            aiohttp.ClientSession() as session,
            session.get(
                "https://api.sendgrid.com/v3/user/profile",
                headers={"Authorization": f"Bearer {api_key}"},
            ) as response,
        ):
            if response.status == 200:
                data = await response.json()
                print("   ✅ API connection successful")
                print(f"   📧 Account: {data.get('email', 'N/A')}")
            else:
                error = await response.text()
                print(f"   ❌ API error (status {response.status}): {error}")
                return False
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        return False

    print()

    # Test email sending (if test email provided)
    if test_email:
        print(f"3️⃣ Sending test email to {test_email}...")
        try:
            payload = {
                "personalizations": [{"to": [{"email": test_email}]}],
                "from": {"email": "notifications@balizero.com", "name": "Bali Zero Test"},
                "subject": "SendGrid Test - Bali Zero Notifications",
                "content": [
                    {
                        "type": "text/html",
                        "value": """
                        <h2>✅ SendGrid Test Successful!</h2>
                        <p>This is a test email from the Bali Zero notification system.</p>
                        <p>If you're receiving this, SendGrid is properly configured.</p>
                        <br>
                        <p><strong>Bali Zero Team</strong></p>
                        """,
                    }
                ],
            }

            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                ) as response,
            ):
                if response.status == 202:
                    print("   ✅ Test email sent successfully!")
                    print(f"   📨 Check your inbox at {test_email}")
                else:
                    error = await response.text()
                    print(f"   ❌ Send failed (status {response.status}): {error}")
                    return False
        except Exception as e:
            print(f"   ❌ Send failed: {e}")
            return False
    else:
        print("3️⃣ Skipping email test (no test email provided)")
        print("   💡 Run with test email: python verify_sendgrid.py test@example.com")

    print()
    print("=" * 50)
    print("✅ SendGrid configuration verified successfully!")
    print("=" * 50)
    return True


if __name__ == "__main__":
    test_email = sys.argv[1] if len(sys.argv) > 1 else None
    result = asyncio.run(verify_sendgrid_config(test_email))
    sys.exit(0 if result else 1)
