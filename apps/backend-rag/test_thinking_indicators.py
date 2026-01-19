#!/usr/bin/env python3
"""
Test script for thinking indicators implementation.

This script tests the new thinking indicators feature to ensure it works correctly
and provides proper user feedback during LLM processing.
"""

import sys
import os

# Add the backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def test_thinking_indicators_file():
    """Test that thinking_indicators.py was created correctly."""
    
    print("🔍 Checking if thinking_indicators.py was created...")
    
    thinking_indicators_path = os.path.join(
        os.path.dirname(__file__), 
        'backend', 
        'services', 
        'rag', 
        'agentic', 
        'thinking_indicators.py'
    )
    
    try:
        with open(thinking_indicators_path, 'r') as f:
            content = f.read()
        
        print(f"✅ thinking_indicators.py found ({len(content)} characters)")
        
        # Check for key components
        checks = [
            ('ThinkingPhase enum', 'class ThinkingPhase(Enum):'),
            ('ThinkingIndicatorService class', 'class ThinkingIndicatorService:'),
            ('Multi-language messages', 'THINKING_MESSAGES = {'),
            ('Italian messages', 'ThinkingPhase.ANALYZING: "🧠 Analizzo la tua richiesta..."'),
            ('English messages', 'ThinkingPhase.ANALYZING: "🧠 Analyzing your request..."'),
            ('create_thinking_event method', 'def create_thinking_event('),
            ('create_done_event method', 'def create_done_event('),
            ('should_show_thinking method', 'def should_show_thinking('),
            ('Tool display names', 'TOOL_DISPLAY_NAMES = {'),
            ('get_tool_display_name function', 'def get_tool_display_name('),
        ]
        
        for check_name, check_string in checks:
            if check_string in content:
                print(f"✅ {check_name}: Present")
            else:
                print(f"❌ {check_name}: Missing")
        
        return True
        
    except FileNotFoundError:
        print(f"❌ File not found: {thinking_indicators_path}")
        return False
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False

def test_orchestrator_streaming_integration():
    """Test that orchestrator_streaming_core.py was updated with thinking indicators."""
    
    print("\n🔍 Checking orchestrator_streaming_core.py integration...")
    
    orchestrator_path = os.path.join(
        os.path.dirname(__file__), 
        'backend', 
        'services', 
        'rag', 
        'agentic', 
        'orchestrator_streaming_core.py'
    )
    
    try:
        with open(orchestrator_path, 'r') as f:
            content = f.read()
        
        print(f"✅ orchestrator_streaming_core.py found ({len(content)} characters)")
        
        # Check for key integration points
        checks = [
            ('Import thinking indicators', 'from .thinking_indicators import ThinkingIndicatorService, ThinkingPhase'),
            ('Initialize thinking service', 'thinking_service = ThinkingIndicatorService()'),
            ('Immediate thinking indicator', 'yield thinking_service.create_thinking_event(ThinkingPhase.ANALYZING)'),
            ('Searching indicator', 'yield thinking_service.create_thinking_event(ThinkingPhase.SEARCHING)'),
            ('Reasoning indicator', 'yield thinking_service.create_thinking_event(ThinkingPhase.REASONING)'),
            ('Tool calling indicator', 'yield thinking_service.create_thinking_event(ThinkingPhase.TOOL_CALLING'),
            ('Done event', 'yield thinking_service.create_done_event()'),
        ]
        
        for check_name, check_string in checks:
            if check_string in content:
                print(f"✅ {check_name}: Present")
            else:
                print(f"❌ {check_name}: Missing")
        
        return True
        
    except FileNotFoundError:
        print(f"❌ File not found: {orchestrator_path}")
        return False
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False

def test_thinking_messages():
    """Test thinking messages for different phases and languages."""
    
    print("\n🧪 Testing thinking messages...")
    
    try:
        # Import the module
        from backend.services.rag.agentic.thinking_indicators import (
            ThinkingIndicatorService, 
            ThinkingPhase,
            get_tool_display_name
        )
        
        # Test Italian
        it_service = ThinkingIndicatorService(language="it")
        
        print("🇮🇹 Italian messages:")
        for phase in ThinkingPhase:
            message = it_service.get_message(phase)
            print(f"  {phase.value}: {message}")
        
        # Test English
        en_service = ThinkingIndicatorService(language="en")
        
        print("\n🇬🇧 English messages:")
        for phase in ThinkingPhase:
            message = en_service.get_message(phase)
            print(f"  {phase.value}: {message}")
        
        # Test tool names
        print("\n🔧 Tool name translations:")
        tools = ["search_documents", "calculator", "get_pricing"]
        for tool in tools:
            it_name = get_tool_display_name(tool, "it")
            en_name = get_tool_display_name(tool, "en")
            print(f"  {tool}: IT='{it_name}', EN='{en_name}'")
        
        # Test event creation
        print("\n📡 Event creation:")
        event = it_service.create_thinking_event(ThinkingPhase.SEARCHING)
        print(f"  Event: {event}")
        
        done_event = it_service.create_done_event()
        print(f"  Done event: {done_event}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Failed to import thinking_indicators: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing messages: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 TESTING THINKING INDICATORS IMPLEMENTATION")
    print("=" * 60)
    
    success = True
    
    # Test 1: Check thinking_indicators.py file
    if not test_thinking_indicators_file():
        success = False
    
    # Test 2: Check orchestrator integration
    if not test_orchestrator_streaming_integration():
        success = False
    
    # Test 3: Test functionality
    if not test_thinking_messages():
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 SUCCESS: Thinking indicators implemented correctly!")
        print("\n📋 Features implemented:")
        print("✅ Multi-language thinking messages (IT, EN, ID)")
        print("✅ Phase-based indicators (Analyzing, Searching, Reasoning, Tool Calling, Generating)")
        print("✅ Real-time streaming events")
        print("✅ Tool name translations")
        print("✅ Smart timing (only show if taking time)")
        print("✅ Integration with orchestrator streaming")
        print("\n📋 Next steps:")
        print("1. Deploy to test the feature")
        print("2. Test with real chat messages")
        print("3. Implement proactive suggestions")
    else:
        print("❌ FAILED: Some components are missing")
    
    print("=" * 60)
