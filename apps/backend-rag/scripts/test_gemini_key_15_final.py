import os
import asyncio
from google import genai

async def test_key():
    key = "AIzaSyBJaqMN8Wi8p5aA2sWBDlWXwu-FGv0Yj5Q"
    print(f"Testing key with 1.5-flash: {key[:10]}...")
    client = genai.Client(api_key=key)
    try:
        # Try different model ID formats
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents="Hello, respond with 'OK' if you can hear me."
        )
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_key())
