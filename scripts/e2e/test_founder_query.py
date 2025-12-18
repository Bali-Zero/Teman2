#!/usr/bin/env python3
"""
Quick test for founder query
"""
import requests
import json

API_URL = "https://zantara.balizero.com"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI3ZGZlNTZiMi1mZjYzLTRkNDAtYjc4Yi05MGMwMTgxMjdhMDIiLCJ1c2VySWQiOiI3ZGZlNTZiMi1mZjYzLTRkNDAtYjc4Yi05MGMwMTgxMjdhMDIiLCJlbWFpbCI6Inplcm9AYmFsaXplcm8uY29tIiwicm9sZSI6IkZvdW5kZXIiLCJkZXBhcnRtZW50IjoibGVhZGVyc2hpcCIsInNlc3Npb25JZCI6InNlc3Npb25fMTc2NDQ2MjEwNjk4NF83ZGZlNTZiMi1mZjYzLTRkNDAtYjc4Yi05MGMwMTgxMjdhMDIiLCJleHAiOjE3NjUwNjY5MDZ9.EbJN1c8_oGNKLarYJQZPNbOH_U9PNZVstchnjTrMq7k"

print("🧪 Testing Founder Query...")
print("=" * 60)

# Test query
query = "Chi è il fondatore di Bali Zero?"

print(f"\n👤 Query: {query}")

try:
    response = requests.post(
        f"{API_URL}/api/chat/stream",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json"
        },
        json={
            "message": query,
            "conversation_history": []
        },
        timeout=30
    )

    if not response.ok:
        print(f"❌ API Error: {response.status_code}")
        print(response.text)
        exit(1)

    # Parse SSE stream
    full_response = ""
    metadata = {}

    for line in response.text.split("\n"):
        if line.startswith("data: "):
            try:
                data = json.loads(line[6:])
                if data.get("type") == "token":
                    full_response += data.get("data", "")
                elif data.get("type") == "metadata":
                    metadata = data.get("data", {})
            except json.JSONDecodeError:
                continue

    print(f"\n🤖 Response: {full_response}")
    print(f"\n📊 Metadata:")
    print(f"   Intent: {metadata.get('intent')}")
    print(f"   RAG used: {metadata.get('used_rag', False)}")
    print(f"   RAG sources: {metadata.get('rag_sources', [])}")
    print(f"   Memory used: {metadata.get('memory_used', False)}")

    # Check if founder (Zero) is mentioned
    if "zero" in full_response.lower() or "fondatore" in full_response.lower():
        print("\n✅ SUCCESS: Founder mentioned in response!")
        exit(0)
    else:
        print("\n❌ FAIL: Founder not mentioned")
        exit(1)

except Exception as e:
    print(f"❌ Exception: {e}")
    exit(1)
