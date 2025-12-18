#!/usr/bin/env python3
"""
Test script to verify Zantara recognizes zero@balizero.com
"""
import os
import sys
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("BACKEND_URL", "https://nuzantara-rag.fly.dev")
EMAIL = "zero@balizero.com"
PIN = "010719"

async def test_recognition():
    """Test if Zantara recognizes zero@balizero.com"""
    
    # Step 1: Login
    print(f"🔐 Logging in as {EMAIL}...")
    async with httpx.AsyncClient(timeout=30.0) as client:
        login_response = await client.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": EMAIL, "pin": PIN}
        )
        
        if login_response.status_code != 200:
            print(f"❌ Login failed: {login_response.status_code}")
            print(login_response.text)
            return
        
        login_data = login_response.json()
        token = login_data.get("data", {}).get("token")
        
        if not token:
            print("❌ No token in login response")
            print(login_data)
            return
        
        print(f"✅ Login successful, token: {token[:20]}...")
        
        # Step 2: Test chat endpoint
        print(f"\n💬 Testing chat endpoint...")
        chat_response = await client.post(
            f"{BASE_URL}/api/chat/stream",
            json={
                "message": "Ciao, mi riconosci?",
                "user_id": EMAIL,
                "conversation_history": []
            },
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            timeout=60.0
        )
        
        if chat_response.status_code != 200:
            print(f"❌ Chat failed: {chat_response.status_code}")
            print(chat_response.text)
            return
        
        print(f"✅ Chat response received (status: {chat_response.status_code})")
        
        # Parse SSE stream
        full_response = ""
        async for line in chat_response.aiter_lines():
            if line.startswith("data: "):
                data_str = line[6:]  # Remove "data: " prefix
                try:
                    import json
                    data = json.loads(data_str)
                    if data.get("type") == "token":
                        full_response += data.get("data", "")
                    elif data.get("type") == "metadata":
                        metadata = data.get("data", {})
                        print(f"\n📊 Metadata:")
                        print(f"   - User ID: {metadata.get('user')}")
                        print(f"   - Identified: {metadata.get('identified')}")
                        print(f"   - Memory used: {metadata.get('memory_used')}")
                        print(f"   - RAG used: {metadata.get('rag_used')}")
                except json.JSONDecodeError:
                    pass
        
        print(f"\n💭 Zantara response:")
        print(f"   {full_response[:200]}...")
        
        # Check if response mentions Zero or recognizes the user
        response_lower = full_response.lower()
        if "zero" in response_lower or "ricordo" in response_lower or "riconosci" in response_lower:
            print("\n✅ Zantara seems to recognize the user!")
        else:
            print("\n⚠️ Zantara response doesn't show clear recognition")

if __name__ == "__main__":
    asyncio.run(test_recognition())

