#!/usr/bin/env python3
import requests
import json

url = "https://nuzantara-rag.fly.dev/api/legal/upload"
headers = {"X-API-Key": "REDACTED-ROTATED-KEY"}
files = {"file": open("/Users/antonellosiano/desktop/nuzantara/apps/kb/data/01_immigrazione/PP Nomor 31 Tahun 2013_20251122_163034_f60006.pdf", "rb")}
data = {"title": "PP_31_2013_FINAL"}

print("📤 Uploading PDF...")
response = requests.post(url, headers=headers, files=files, data=data, timeout=300)

print(f"\n📊 Status: {response.status_code}")
print(f"\n📄 Response:")
print(json.dumps(response.json(), indent=2, ensure_ascii=False))
