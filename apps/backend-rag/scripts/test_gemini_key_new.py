import os
import asyncio
from google import genai

async def test_key():
    key = "AIzaSyC1cM933ORSdB4CCAx8EYe4mNsYShIoGDI"
    print(f"Testing new key: {key[:10]}...")
    client = genai.Client(api_key=key)
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-001",
            contents="Hello, respond with 'OK' if you can hear me."
        )
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_key())
