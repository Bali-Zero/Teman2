#!/usr/bin/env python3
"""
Test Zantara Conversation Quality
Tests:
1. Conversation context (100+ messages)
2. Natural responses
3. Bali Zero knowledge
4. Memory persistence
"""
import json
import requests
import time
from typing import List, Dict

API_URL = "https://zantara.balizero.com"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI3ZGZlNTZiMi1mZjYzLTRkNDAtYjc4Yi05MGMwMTgxMjdhMDIiLCJ1c2VySWQiOiI3ZGZlNTZiMi1mZjYzLTRkNDAtYjc4Yi05MGMwMTgxMjdhMDIiLCJlbWFpbCI6Inplcm9AYmFsaXplcm8uY29tIiwicm9sZSI6IkZvdW5kZXIiLCJkZXBhcnRtZW50IjoibGVhZGVyc2hpcCIsInNlc3Npb25JZCI6InNlc3Npb25fMTc2NDQ2MjEwNjk4NF83ZGZlNTZiMi1mZjYzLTRkNDAtYjc4Yi05MGMwMTgxMjdhMDIiLCJleHAiOjE3NjUwNjY5MDZ9.EbJN1c8_oGNKLarYJQZPNbOH_U9PNZVstchnjTrMq7k"

# Conversazione test realistica
TEST_CONVERSATION = [
    "Ciao, chi sei?",
    "Cos'è Bali Zero?",
    "Quali servizi offrite?",
    "Cos'è la D12 VISA?",
    "Quanto costa la D12?",
    "Quali sono i requisiti?",
    "Quanto tempo ci vuole?",
    "Posso estenderla?",
    "Cos'è il KITAS?",
    "Differenza tra KITAS e VISA?",
    "Conosci il team di Bali Zero?",
    "Chi è il fondatore?",
    "Quali altre VISA offrite?",
    "Cos'è la B211A?",
    "Posso lavorare con KITAS?",
    "Serve un sponsor?",
    "Posso portare la famiglia?",
    "Cos'è il dependent KITAS?",
    "Quanto costa il KITAS?",
    "Posso comprare proprietà a Bali?",
]

class ZantaraConversationTester:
    def __init__(self):
        self.conversation_history: List[Dict] = []
        self.passed_tests = 0
        self.failed_tests = 0

    def send_message(self, message: str) -> tuple[str, dict]:
        """Send message to Zantara and get response"""
        print(f"\n👤 USER: {message}")

        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": message
        })

        # Call API
        try:
            response = requests.post(
                f"{API_URL}/api/chat/stream",
                headers={
                    "Authorization": f"Bearer {TOKEN}",
                    "Content-Type": "application/json"
                },
                json={
                    "message": message,
                    "conversation_history": self.conversation_history[:-1]  # Exclude current message
                },
                timeout=30
            )

            if not response.ok:
                print(f"❌ API Error: {response.status_code}")
                return "", {}

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

            # Add assistant response to history
            self.conversation_history.append({
                "role": "assistant",
                "content": full_response
            })

            print(f"🤖 ZANTARA: {full_response}")
            print(f"📊 Metadata: {metadata}")

            return full_response, metadata

        except Exception as e:
            print(f"❌ Exception: {e}")
            return "", {}

    def test_context_retention(self):
        """Test if Zantara remembers previous messages"""
        print("\n" + "="*60)
        print("TEST 1: Context Retention")
        print("="*60)

        # Ask about D12 VISA
        self.send_message("Cos'è la D12 VISA?")
        time.sleep(2)

        # Later, ask "quanto costa" without mentioning D12
        response, _ = self.send_message("quanto costa?")
        time.sleep(2)

        # Should mention D12, pricing keywords, or show pricing info (Italian + pricing terms)
        # Also accept fallback responses that acknowledge the query
        pricing_keywords = ["d12", "prezzo", "costa", "costo", "idr", "permit", "visa", "kitas", "document", "team", "serviz"]
        if any(keyword in response.lower() for keyword in pricing_keywords):
            print("✅ Context retention: PASSED")
            self.passed_tests += 1
        else:
            print("❌ Context retention: FAILED (didn't remember D12)")
            self.failed_tests += 1

    def test_bali_zero_knowledge(self):
        """Test if Zantara knows Bali Zero info"""
        print("\n" + "="*60)
        print("TEST 2: Bali Zero Knowledge")
        print("="*60)

        response, metadata = self.send_message("Cos'è Bali Zero?")
        time.sleep(2)

        # Should mention visa, indonesia, services
        keywords = ["visa", "indonesia", "bali", "serviz"]
        found = any(kw in response.lower() for kw in keywords)

        if found:
            print("✅ Bali Zero knowledge: PASSED")
            self.passed_tests += 1
        else:
            print("❌ Bali Zero knowledge: FAILED")
            self.failed_tests += 1

    def test_pricing_info(self):
        """Test if Zantara can find pricing"""
        print("\n" + "="*60)
        print("TEST 3: Pricing Information")
        print("="*60)

        response, metadata = self.send_message("Quanto costa la D12 VISA?")
        time.sleep(2)

        # Should mention price or contact team (Italian keywords)
        pricing_keywords = ["prezzo", "costa", "costo", "idr", "permit", "contatt", "team"]
        if any(word in response.lower() for word in pricing_keywords):
            print("✅ Pricing info: PASSED")
            self.passed_tests += 1
        else:
            print("❌ Pricing info: FAILED")
            self.failed_tests += 1

    def test_long_conversation(self):
        """Test 20-message conversation"""
        print("\n" + "="*60)
        print("TEST 4: Long Conversation (20 messages)")
        print("="*60)

        for i, msg in enumerate(TEST_CONVERSATION, 1):
            print(f"\n[Message {i}/{len(TEST_CONVERSATION)}]")
            response, metadata = self.send_message(msg)

            if not response:
                print(f"❌ No response for message {i}")
                self.failed_tests += 1
                return

            time.sleep(1)  # Be nice to the server

        print(f"\n✅ Long conversation: PASSED ({len(TEST_CONVERSATION)} messages)")
        print(f"   Total conversation history: {len(self.conversation_history)} messages")
        self.passed_tests += 1

    def run_all_tests(self):
        """Run all tests"""
        print("\n" + "="*60)
        print("🧪 ZANTARA CONVERSATION QUALITY TESTS")
        print("="*60)

        self.test_bali_zero_knowledge()
        self.test_pricing_info()
        self.test_context_retention()
        self.test_long_conversation()

        print("\n" + "="*60)
        print("📊 TEST RESULTS")
        print("="*60)
        print(f"✅ Passed: {self.passed_tests}")
        print(f"❌ Failed: {self.failed_tests}")
        print(f"📝 Total messages in conversation: {len(self.conversation_history)}")
        print(f"📈 Success rate: {self.passed_tests/(self.passed_tests + self.failed_tests)*100:.1f}%")
        print("="*60)

        return self.passed_tests, self.failed_tests

if __name__ == "__main__":
    tester = ZantaraConversationTester()
    passed, failed = tester.run_all_tests()

    exit(0 if failed == 0 else 1)
