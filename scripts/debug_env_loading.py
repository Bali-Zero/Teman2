import os
import json
from dotenv import load_dotenv

# Load .env manually to emulate what pydantic/app does
load_dotenv("apps/backend-rag/.env")


def debug_env():
    print("--- DEBUG ENV LOADING ---")
    raw_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    print(
        f"Raw GOOGLE_SERVICE_ACCOUNT_JSON length: {len(raw_json) if raw_json else 'None'}"
    )

    if raw_json:
        print(f"First 50 chars: {raw_json[:50]}")
        print(f"Last 50 chars: {raw_json[-50:]}")

        try:
            parsed = json.loads(raw_json)
            print("✅ JSON Parsing: SUCCESS")
            print(f"Keys found: {list(parsed.keys())}")
            print(f"Project ID: {parsed.get('project_id')}")

            pk = parsed.get("private_key", "")
            has_escaped = "\\n" in pk
            print(f"Private Key Validation: {has_escaped} (contains escaped newlines)")
            print(f"Private Key Length: {len(pk)}")

        except json.JSONDecodeError as e:
            print(f"❌ JSON Parsing: FAILED - {e}")
    else:
        print("❌ GOOGLE_SERVICE_ACCOUNT_JSON not found in env")

    print(f"GOOGLE_API_KEY: {os.environ.get('GOOGLE_API_KEY')}")


if __name__ == "__main__":
    debug_env()
