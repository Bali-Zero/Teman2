import asyncio
import json

import aiohttp


async def test_streaming():
    url = "http://localhost:8000/bali-zero/chat-stream"
    params = {
        "query": "Hello, are you online?",
        "user_email": "test@example.com",
        "user_role": "member",
    }
    headers = {"X-API-Key": "REDACTED-ROTATED-KEY", "Content-Type": "application/json"}

    print(f"Connecting to {url}...")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as response:
                print(f"Status: {response.status}")

                if response.status != 200:
                    print(f"Error: {await response.text()}")
                    return

                async for line in response.content:
                    line = line.decode("utf-8").strip()
                    if not line:
                        continue

                    if line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            event = json.loads(data_str)
                            event_type = event.get("type")
                            event_data = event.get("data")

                            print(f"Received Event: [{event_type}]")
                            if event_type == "token":
                                print(f"  Token: {event_data}", end="", flush=True)
                            else:
                                print(f"  Data: {event_data}")

                        except json.JSONDecodeError:
                            print(f"Failed to parse JSON: {data_str}")

                print("\nStream complete.")

    except Exception as e:
        print(f"Connection failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_streaming())
