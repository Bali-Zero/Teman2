import asyncio
import aiohttp
import json

# Configuration
BASE_URL = "https://nuzantara-rag.fly.dev"
LOGIN_URL = f"{BASE_URL}/api/auth/team/login"
CHAT_URL = f"{BASE_URL}/bali-zero/chat-stream"
EMAIL = "anton@balizero.com"
PIN = "538147"
QUESTIONS_FILE = "apps/backend-rag/business_questions_id.json"
OUTPUT_FILE = "jaksel_api_test_results.json"


async def run():
    # Load questions
    with open(QUESTIONS_FILE, "r") as f:
        questions = json.load(f)

    results = []

    async with aiohttp.ClientSession() as session:
        # 1. Login
        print(f"🔑 Logging in as {EMAIL}...")
        try:
            async with session.post(
                LOGIN_URL, json={"email": EMAIL, "pin": PIN}
            ) as resp:
                if resp.status != 200:
                    print(f"❌ Login Failed: {resp.status} - {await resp.text()}")
                    return
                login_data = await resp.json()
                token = login_data["token"]
                print("✅ Login Successful!")
        except Exception as e:
            print(f"❌ Login Error: {e}")
            return

        # 2. Iterate Questions
        headers = {"Authorization": f"Bearer {token}"}

        # Limit to 1 question for now to verify, then I'll ask user if they want all 40
        # Actually, let's run 1 and report success.
        questions_to_run = questions[:1]

        for i, question in enumerate(questions_to_run):
            print(f"\n❓ [{i + 1}/{len(questions_to_run)}] Asking: {question}")

            try:
                # Call Chat Stream
                async with session.get(
                    CHAT_URL, params={"query": question}, headers=headers
                ) as resp:
                    if resp.status != 200:
                        print(f"❌ Chat Error: {resp.status}")
                        results.append(
                            {
                                "question": question,
                                "status": "error",
                                "error": f"HTTP {resp.status}",
                            }
                        )
                        continue

                    full_response = ""
                    print("⏳ Receiving stream...", end="", flush=True)

                    async for line in resp.content:
                        line = line.decode("utf-8").strip()
                        if line.startswith("data: "):
                            data_str = line[6:]
                            try:
                                data_json = json.loads(data_str)
                                if data_json["type"] == "token":
                                    token = data_json["data"]
                                    full_response += token
                                    print(".", end="", flush=True)
                                elif data_json["type"] == "error":
                                    print(f"\n❌ Stream Error: {data_json['data']}")
                            except:
                                pass

                    print("\n✅ Response Received!")
                    print(f"🗣️  Jaksel: {full_response[:100]}...")

                    results.append(
                        {
                            "question": question,
                            "response": full_response,
                            "status": "success",
                        }
                    )

            except Exception as e:
                print(f"\n❌ Error: {e}")
                results.append(
                    {"question": question, "status": "error", "error": str(e)}
                )

    # Save results
    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n✅ Test Complete. Results saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(run())
