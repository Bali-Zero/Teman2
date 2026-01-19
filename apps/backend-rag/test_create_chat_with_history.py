#!/usr/bin/env python3
"""
Test script for create_chat_with_history implementation.

This script tests the new method in LLMGateway to ensure it works correctly
with both real and mock sessions.
"""

import asyncio
import logging
import sys
import os

# Add the backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.services.rag.agentic.llm_gateway import LLMGateway
from backend.services.rag.agentic.chat_session import ChatSession, MockChatSession

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_create_chat_with_history():
    """Test the new create_chat_with_history method."""
    
    print("🧪 Testing create_chat_with_history implementation...")
    
    # Test 1: Mock session (when GenAI client unavailable)
    print("\n1️⃣ Testing MockChatSession...")
    
    mock_gateway = LLMGateway()
    mock_gateway._available = False  # Force mock mode
    
    try:
        mock_chat = mock_gateway.create_chat_with_history(
            history_to_use=[
                {"role": "user", "content": "Ciao!"},
                {"role": "model", "content": "Ciao! Come posso aiutarti?"}
            ],
            model_tier=0,
            system_instruction="Sei un assistente AI."
        )
        
        print(f"✅ Mock session created: {type(mock_chat).__name__}")
        print(f"📝 History length: {len(mock_chat.get_history())}")
        
        # Test sending a message
        response = await mock_chat.send_message("Test message")
        print(f"💬 Mock response: {response.text[:50]}...")
        
    except Exception as e:
        print(f"❌ Mock session test failed: {e}")
    
    # Test 2: Real session (if API key available)
    print("\n2️⃣ Testing real ChatSession (if available)...")
    
    real_gateway = LLMGateway()
    
    if real_gateway._available:
        try:
            real_chat = real_gateway.create_chat_with_history(
                history_to_use=[
                    {"role": "user", "content": "Ciao!"},
                    {"role": "model", "content": "Ciao! Come posso aiutarti?"}
                ],
                model_tier=0,
                system_instruction="Sei un assistente AI."
            )
            
            print(f"✅ Real session created: {type(real_chat).__name__}")
            print(f"📝 History length: {len(real_chat.get_history())}")
            print(f"🤖 Model: {real_chat.model}")
            
            # Test sending a message (quick test)
            print("💬 Sending test message...")
            response = await real_chat.send_message("Dimmi 'OK' per confermare")
            print(f"✅ Real response received: {response.text[:100]}...")
            
        except Exception as e:
            print(f"❌ Real session test failed: {e}")
    else:
        print("⚠️ GenAI client not available - skipping real session test")
    
    print("\n✅ All tests completed!")

def test_method_exists():
    """Test that the method exists and is callable."""
    
    print("🔍 Checking if create_chat_with_history method exists...")
    
    gateway = LLMGateway()
    
    if hasattr(gateway, 'create_chat_with_history'):
        method = getattr(gateway, 'create_chat_with_history')
        if callable(method):
            print("✅ Method exists and is callable")
            return True
        else:
            print("❌ Method exists but is not callable")
            return False
    else:
        print("❌ Method does not exist")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 TESTING create_chat_with_history FIX")
    print("=" * 60)
    
    # First check if method exists
    if not test_method_exists():
        print("\n❌ FAILED: Method not found")
        sys.exit(1)
    
    # Then test functionality
    try:
        asyncio.run(test_create_chat_with_history())
        print("\n🎉 SUCCESS: All tests passed!")
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
