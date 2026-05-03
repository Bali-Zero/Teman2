#!/usr/bin/env python3
"""
Generate a test JWT token for API testing
"""

import sys
from datetime import datetime, timedelta

import jwt


def generate_token(secret: str, user_email: str = "test@nuzantara.com", expires_hours: int = 24):
    """Generate a JWT token for testing"""

    payload = {
        "sub": user_email,
        "email": user_email,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=expires_hours),
        "type": "access",
    }

    token = jwt.encode(payload, secret, algorithm="HS256")
    return token


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_test_token.py <JWT_SECRET> [email] [hours]")
        print("Example: python generate_test_token.py 'your-secret' 'user@example.com' 24")
        sys.exit(1)

    secret = sys.argv[1]
    email = sys.argv[2] if len(sys.argv) > 2 else "test@nuzantara.com"
    hours = int(sys.argv[3]) if len(sys.argv) > 3 else 24

    token = generate_token(secret, email, hours)

    print("✅ JWT Token generated:")
    print(f"   Email: {email}")
    print(f"   Expires: {hours} hours")
    print()
    print(f"export JWT_TOKEN='{token}'")
    print()
    print("Copy and paste the export command above, then run:")
    print("./scripts/test_production.sh")
