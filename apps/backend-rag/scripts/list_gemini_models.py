import os
import asyncio
from google import genai

async def list_models():
    key = "AIzaSyBJaqMN8Wi8p5aA2sWBDlWXwu-FGv0Yj5Q"
    client = genai.Client(api_key=key)
    try:
        print("Available models:")
        for model in client.models.list():
            print(f"- {model.name}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(list_models())
