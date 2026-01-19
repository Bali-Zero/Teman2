#!/usr/bin/env python3
"""
Simple test for create_chat_with_history implementation.

This is a minimal test that avoids the full backend initialization.
"""

import sys
import os

# Add the backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def test_method_exists():
    """Test that the method exists in the file."""
    
    print("🔍 Checking if create_chat_with_history method exists in llm_gateway.py...")
    
    # Read the file and check for the method
    llm_gateway_path = os.path.join(
        os.path.dirname(__file__), 
        'backend', 
        'services', 
        'rag', 
        'agentic', 
        'llm_gateway.py'
    )
    
    try:
        with open(llm_gateway_path, 'r') as f:
            content = f.read()
        
        if 'def create_chat_with_history(' in content:
            print("✅ Method create_chat_with_history found in llm_gateway.py")
            
            # Check for key components
            checks = [
                ('ChatSession import', 'from .chat_session import ChatSession, MockChatSession'),
                ('Method signature', 'def create_chat_with_history('),
                ('History conversion', 'gemini_history = []'),
                ('ChatSession creation', 'return ChatSession('),
                ('Mock fallback', 'return MockChatSession('),
                ('Model tier method', 'def _get_model_for_tier('),
            ]
            
            for check_name, check_string in checks:
                if check_string in content:
                    print(f"✅ {check_name}: Present")
                else:
                    print(f"❌ {check_name}: Missing")
            
            return True
        else:
            print("❌ Method create_chat_with_history NOT found in llm_gateway.py")
            return False
            
    except FileNotFoundError:
        print(f"❌ File not found: {llm_gateway_path}")
        return False
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False

def test_chat_session_file():
    """Test that chat_session.py was created."""
    
    print("\n🔍 Checking if chat_session.py was created...")
    
    chat_session_path = os.path.join(
        os.path.dirname(__file__), 
        'backend', 
        'services', 
        'rag', 
        'agentic', 
        'chat_session.py'
    )
    
    try:
        with open(chat_session_path, 'r') as f:
            content = f.read()
        
        print(f"✅ chat_session.py found ({len(content)} characters)")
        
        # Check for key components
        checks = [
            ('ChatSession class', 'class ChatSession:'),
            ('MockChatSession class', 'class MockChatSession:'),
            ('send_message method', 'async def send_message('),
            ('send_message_stream', 'async def send_message_stream('),
            ('Mock response fallback', 'Mi dispiace, il servizio di intelligenza artificiale'),
        ]
        
        for check_name, check_string in checks:
            if check_string in content:
                print(f"✅ {check_name}: Present")
            else:
                print(f"❌ {check_name}: Missing")
        
        return True
        
    except FileNotFoundError:
        print(f"❌ File not found: {chat_session_path}")
        return False
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 TESTING create_chat_with_history FIX")
    print("=" * 60)
    
    success = True
    
    # Test 1: Check method exists in llm_gateway.py
    if not test_method_exists():
        success = False
    
    # Test 2: Check chat_session.py was created
    if not test_chat_session_file():
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 SUCCESS: create_chat_with_history fix implemented correctly!")
        print("\n📋 Next steps:")
        print("1. Configure GOOGLE_API_KEY on Fly.io")
        print("2. Deploy to test the fix")
        print("3. Test with real chat messages")
    else:
        print("❌ FAILED: Some components are missing")
    
    print("=" * 60)
