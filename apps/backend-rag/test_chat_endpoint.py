#!/usr/bin/env python3
"""
Test the chat streaming endpoint to verify the create_chat_with_history fix.
"""

import requests
import json
import sys

def test_chat_streaming():
    """Test the chat streaming endpoint."""
    
    print("🧪 Testing chat streaming endpoint...")
    
    url = "https://nuzantara-rag.fly.dev/api/v1/chat/stream"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer development"
    }
    
    payload = {
        "query": "Ciao, come stai?",
        "user_id": "test_user",
        "conversation_history": [
            {"role": "user", "content": "Ciao!"},
            {"role": "model", "content": "Ciao! Come posso aiutarti?"}
        ]
    }
    
    try:
        print(f"📡 Sending request to: {url}")
        print(f"📝 Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(url, json=payload, headers=headers, stream=True, timeout=30)
        
        print(f"📊 Response status: {response.status_code}")
        print(f"📋 Response headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("✅ Streaming started successfully!")
            print("\n📦 Stream content:")
            
            for line in response.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    print(decoded)
                    
                    # Stop after a few lines for testing
                    if "done" in decoded.lower():
                        break
                        
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.Timeout:
        print("⏰ Request timed out after 30 seconds")
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

def test_health_endpoint():
    """Test the health endpoint."""
    
    print("\n🔍 Testing health endpoint...")
    
    try:
        response = requests.get("https://nuzantara-rag.fly.dev/health", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Health endpoint working!")
            print(f"📊 Status: {data.get('status')}")
            print(f"🗄️ Database: {data.get('database', {}).get('status')}")
            print(f"🤖 Embeddings: {data.get('embeddings', {}).get('provider')}")
        else:
            print(f"❌ Health endpoint failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Health endpoint error: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 TESTING CHAT STREAMING AFTER FIX")
    print("=" * 60)
    
    # Test health first
    test_health_endpoint()
    
    # Test chat streaming
    test_chat_streaming()
    
    print("\n" + "=" * 60)
    print("🎯 Test completed!")
    print("=" * 60)
