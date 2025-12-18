import requests
import json

API_URL = "http://localhost:8080/api/chat/stream"
API_KEY = "dev_api_key_for_testing_only"


def test_chat():
    print(f"Testing Chat API at {API_URL}...")

    payload = {
        "message": "Hello Zantara, are you fully operational?",
        "user_id": "test_cli_user",
        "enable_vision": False,
    }

    headers = {"Content-Type": "application/json", "X-API-Key": API_KEY}

    try:
        with requests.post(
            API_URL, json=payload, headers=headers, stream=True
        ) as response:
            if response.status_code != 200:
                print(f"Error: {response.status_code}")
                print(response.text)
                return

            print("\n--- ZANTARA RESPONSE ---\n")
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode("utf-8")
                    if decoded_line.startswith("data: "):
                        json_str = decoded_line[6:]
                        if json_str == "[DONE]":
                            break
                        try:
                            data = json.loads(json_str)
                            event_type = data.get("type")

                            if event_type == "token":
                                content = data.get("data", "")
                                print(content, end="", flush=True)
                            elif event_type == "error":
                                print(f"\n[ERROR]: {data.get('data')}")
                            elif event_type == "metadata":
                                # print(f"\n[META]: {data.get('data')}")
                                pass
                        except json.JSONDecodeError:
                            pass
            print("\n\n--- END ---")

    except Exception as e:
        print(f"Connection failed: {e}")


if __name__ == "__main__":
    test_chat()
