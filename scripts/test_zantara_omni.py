import requests
import time
from jose import jwt

# User provided Configuration
BASE_URL = "http://localhost:8080"
CHAT_URL = f"{BASE_URL}/api/agentic-rag/query"
JWT_SECRET = "07XoX6Eu24amEuUye7MhTFO62jzaYJ48myn04DvECN0="  # Provided by User
ALGORITHM = "HS256"
EMAIL = "zero@balizero.com"


def mint_token():
    print(f"Minting Admin Token for {EMAIL}...")
    payload = {
        "sub": "1",  # Admin ID
        "email": EMAIL,
        "role": "admin",
        "exp": int(time.time()) + 3600,  # 1 hour expiry
        "iat": int(time.time()),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)
    print("✅ Token Minted")
    return token


TOKEN = mint_token()
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}",
    "X-Correlation-ID": "test-omni-live-final",
}


def print_banner(text):
    print(f"\n{'=' * 50}\n {text} \n{'=' * 50}")


def test_query(language, query, expected_vibe):
    print_banner(f"TEST: {language} ({expected_vibe})")
    print(f"User: {query}")

    payload = {
        "query": query,
        "session_id": f"test_session_{int(time.time())}",
        "user_id": EMAIL,
    }

    try:
        start = time.time()
        # Using longer timeout for RAG processing
        response = requests.post(CHAT_URL, json=payload, headers=HEADERS, timeout=90)
        duration = time.time() - start

        if response.status_code == 200:
            data = response.json()
            answer = (
                data.get("answer") or data.get("response") or "No answer field found"
            )
            print(f"Zantara ({duration:.2f}s):\n{answer}")

            # Print Tool Usage if available
            if "debug_info" in data:
                print(
                    f"[Debug] Tools: {data.get('tools_called')} | Model: {data.get('debug_info', {}).get('model')}"
                )
        else:
            print(f"ERROR {response.status_code}: {response.text}")

    except Exception as e:
        print(f"EXCEPTION: {e}")


# 1. Italian Test (User's Native Language)
test_query("Italian", "Chi sei e qual è la tua missione?", "Strategic Consultant")

# 2. English Test (Global Client)
test_query(
    "English",
    "Briefly explain the risk of Nominee agreements in Bali.",
    "Professional Warning",
)

# 3. Bahasa Indonesia Test (Local Team)
test_query(
    "Bahasa",
    "Mas, tolong jelasin syarat bikin PT PMA dong secara singkat.",
    "Local/Formal/Jaksel",
)

# 4. Logic/Tool Test
test_query(
    "Logic",
    "Se il revenue è 2 Miliardi IDR, quanto è l'11% di PPN? Rispondi in italiano.",
    "Calculation",
)
