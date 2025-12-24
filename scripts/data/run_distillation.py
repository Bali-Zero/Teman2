import os
import sys
import json
import requests
from google import genai

# KEY PARTS
k = [
"-----BEGIN PRIVATE KEY-----",
"MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDZziPmowj2kuXH",
"rpEzrdeIY10pObfB7PBr9u126X9B3ehoW2aDzRk8hl7YRsUD6pjtRBwwxSFZZk6t",
"c+Pkzdwhs10n8m9DhatmAQMli4iHH0EHpY0n6P1EzpC3Op9HFMVzjp0nZYaXRCNQ",
"yeeajU59sB/nCT6EDD8j9E+ar/Oyt/cgTaieSbgyJnbI1rkaoWB1WyOy4ZhngDEw",
"6kcvuTCNMv99R7e7ls3OVK8zamDpbMAfp/gRN28SefYx6204CIeHbGrWMPtJwiqP",
"rG/9hPmwvE7gQDj0A/3zatJrpRdu9XRNWnquKGmh1l09Nc9cWTMkTNwamMxC3EUf",
"MRkSfNcpAgMBAAECggEAA3WFrMqBagLi+8j+IbU0wp2H+ILD+pELL/HERQxRouYi",
"irHx6e1NnznhYxUVP0bNAZtzonaNA5AV0L7x9OH4/IvuUn2dwZnx79aobVxLqxBM",
"+0SIZLFlJuzsNjOL6khBiwbOE7BsdhxLfpalGZ3XJZtqZEqDEXwmznW/tzMs0mik",
"5GdUPAkidleIOKPBK5bQT6vd+tD2NAKSzSuCHVQGSpcesLlevMETHIVmIT81rA13",
"YbN2V0KfN8Tvwic3bBN6ZEiePRn8g5QCP0bpiaXrQo16AKi9sUrcH6sxlhLUkU97",
"/D25hzjsAP+uKIavqzPRN6x9mec76TnDx/pYvm3UAQKBgQDvaNQZVEcF8LPT+MGh",
"eZy4sVZGXOaheT+jF99m3bQHc3Msg6mT8Q/RkmSyoGStsJuMaeVSUkeik8+WhkLb",
"4PGhyI11+HthXd7FABYH0rvpgek52aOaFH+oHZ+VMfExcz3/v+t1Wf1v00tOxAAm",
"ixB1qG/Igsp4AkpVLXLNhrjUAQKBgQDo5gxNNv5DbrMONJGRz377mrpVKjbNMstY",
"xPpA1O8yoLj5CFLRezC62NgicM/eClPjz+tnoSwsvZfNnEeo74QiuNYb2hG1gIvY",
"/il/uKWIUO4WTVt1pfr+foq6p2opgE5tAF4jG+R6QoRBCOy1l3srS1iiSAOy2gq+",
"kFGCIubjKQKBgCarzibRQC+rc8C3m79Tf4ctzfvLoc1PYoIbpxBcm2ngsifslIW7",
"GI0HkpBv7BNKRbXmnQ4xEDUonw13XnFZ4m35kTAPFQ7jNMqpeuWEmqnbPCsGBrEq",
"wnwLXO2ihY0xSkB3Zbcs9A0OGkn8yvFu4RfAP14qEj5UUGF11+du7YgBAoGBAJbR",
"otW97xor7bgdQsdx34F/yXqtQ5/ObPCnXoftXJkki6R5R2hwpjXZht2GwJXBimHU",
"nm1UYgkrW3B9CPQWhVahGmiCfLyiife2fabBUGp4UCppWrguZ2NhFigEluRH3DNJ5",
"knyZ63Ng79RNuzw9RH3c5SDyEbMYkCynuKDViT9BAoGACPX6apWRjcrCZ5Y5Scme",
"JUUPaucvEAlCYZkWesANZNOcD+SpXXqibE90d3TajC9cMOYVYFCtcjREZjjDFVqW",
"YOzIx+hCsVTuw2FYdaVDAZ2FcAsJH6expRwROx7d7Zaz5OlLG4pu+a1mB0v/5Mkw",
"UbQPc1iMJdHXlFTuFpjQvmE=",
"-----END PRIVATE KEY-----"
]
KEY_STR = "\n".join(k)

creds_dict = {
  "type": "service_account",
  "project_id": "nuzantara",
  "private_key_id": "27bd2c546a52252c07c006df9da95bddf375e3ed",
  "private_key": KEY_STR,
  "client_email": "nuzantara-bot@nuzantara.iam.gserviceaccount.com",
  "client_id": "108084477435262178822",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/nuzantara-bot%40nuzantara.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}

# SALVA CREDENZIALI
TEMP_CREDS = "/tmp/clean_sa.json"
with open(TEMP_CREDS, "w") as f:
    json.dump(creds_dict, f)

# IMPOSIZIONE AMBIENTE
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = TEMP_CREDS
# Rimuovo altre variabili conflittuali
for key in ["GOOGLE_CREDENTIALS_JSON", "GOOGLE_API_KEY"]:
    if key in os.environ: del os.environ[key]

QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

print("🚀 RUNNING FINAL DISTILLATION...")

# Init Client (standard env loading)
try:
    client = genai.Client(vertexai=True, project="nuzantara", location="us-central1")
    print("✅ Auth OK.")
except Exception as e:
    print(f"❌ Auth Error: {e}")
    sys.exit(1)

# Fetch Data
headers = {"api-key": QDRANT_API_KEY}
resp = requests.post(f"{QDRANT_URL}/collections/training_conversations/points/scroll",
                    json={"limit": 10, "with_payload": True}, headers=headers)
items = [p.get("payload", {}) for p in resp.json().get("result", {}).get("points", [])]
print(f"📚 Processing {len(items)} items...")

results = []
for i, item in enumerate(items):
    topic = item.get("topic", "Unknown")
    text = item.get("text", "")[:3000]
    print(f"   ⚡ [{i+1}/10] {topic}...")
    try:
        r = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=f"Extract legal facts in JSON:\n\n{text}",
            config={"response_mime_type": "application/json"}
        )
        results.append({"topic": topic, "distilled": json.loads(r.text)})
        print("      ✅ Done.")
    except Exception as e:
        print(f"      ❌ Failed: {e}")

with open("data/datasets/gold/final_distilled_10.json", "w") as f:
    json.dump(results, f, indent=2)
print("✨ DONE.")
