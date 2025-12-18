import http.client
import json
import urllib.parse
import sys
import time

# Configuration
BASE_URL = "nuzantara-rag.fly.dev"
LOGIN_EMAIL = "anton@balizero.com"
LOGIN_PIN = "538147"

SCENARIOS = {
    "Company Setup": [
        "Halo, saya ingin buka perusahaan di Bali. Apa langkah pertamanya?",
        "Saya mau buka restoran di Canggu. Apakah harus PT PMA?",
        "Berapa modal minimal untuk PT PMA?",
        "Apakah saya butuh partner lokal?",
        "Berapa lama proses pembuatannya?",
    ],
    "Visa & Stay": [
        "Apa itu KITAS?",
        "Apa bedanya KITAS Investor dan KITAS Working?",
        "Saya mau tinggal lama tapi tidak kerja, pakai visa apa?",
        "Berapa biaya perpanjangan KITAS?",
        "Apakah saya bisa bawa keluarga?",
    ],
    "Real Estate": [
        "Apakah orang asing bisa beli tanah di Bali?",
        "Apa itu Hak Pakai?",
        "Apakah aman beli tanah dengan nominee?",
        "Berapa pajak pembelian properti?",
        "Daerah mana yang bagus untuk investasi villa?",
    ],
}


def login():
    print(f"🔑 Logging in as {LOGIN_EMAIL}...")
    conn = http.client.HTTPSConnection(BASE_URL)
    payload = json.dumps({"email": LOGIN_EMAIL, "pin": LOGIN_PIN})
    headers = {"Content-Type": "application/json"}
    conn.request("POST", "/api/auth/team/login", payload, headers)
    res = conn.getresponse()
    data = res.read()

    if res.status == 200:
        response_json = json.loads(data.decode("utf-8"))
        token = response_json.get("token")
        print("✅ Login Successful!")
        return token
    else:
        print(f"❌ Login Failed: {res.status} - {data.decode('utf-8')}")
        sys.exit(1)


def chat_turn(conn, token, query, history):
    params = {"query": query, "conversation_history": json.dumps(history)}
    query_string = urllib.parse.urlencode(params)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "text/event-stream",  # Although we might just read the raw stream
    }

    print(f"\n❓ User: {query}")
    conn.request("GET", f"/bali-zero/chat-stream?{query_string}", headers=headers)
    res = conn.getresponse()

    if res.status != 200:
        print(f"❌ Chat Error: {res.status}")
        print(res.read().decode("utf-8"))
        return None

    # Read stream
    full_response = ""
    print("🗣️  Jaksel: ", end="", flush=True)

    while True:
        chunk = res.read(1024)  # Read in chunks
        if not chunk:
            break
        decoded_chunk = chunk.decode("utf-8")
        # Simple stream parsing (assuming raw text or SSE)
        # The endpoint returns raw text chunks in the stream based on previous tests
        print(decoded_chunk, end="", flush=True)
        full_response += decoded_chunk

    print("\n")
    return full_response


def run_scenario(scenario_name, questions, token):
    print(f"\n{'=' * 20} SCENARIO: {scenario_name} {'=' * 20}")
    conn = http.client.HTTPSConnection(BASE_URL)
    history = []

    for q in questions:
        response = chat_turn(conn, token, q, history)
        if response:
            # Update history
            history.append({"role": "user", "content": q})
            history.append({"role": "assistant", "content": response})
            # Wait a bit to be polite to the server
            time.sleep(1)
        else:
            print("⚠️ Stopping scenario due to error.")
            break

    conn.close()


def main():
    token = login()

    for name, questions in SCENARIOS.items():
        run_scenario(name, questions, token)
        time.sleep(2)


if __name__ == "__main__":
    main()
