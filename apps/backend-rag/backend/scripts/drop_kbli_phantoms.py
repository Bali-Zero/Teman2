"""Drop the 4 phantom KBLI codes (26120/60111/82920/85598 — in our old file, NOT in OSS
ground-truth) from the kbli_2025_final_oss twin. Idempotent. Live collection untouched.
"""
import hashlib
import json
import urllib.request
import uuid

ENV="/Users/balizero/nuzantara/apps/backend-rag/.env"
qurl=qkey=None
for line in open(ENV):
    line=line.strip()
    if line.startswith("QDRANT_URL="):
        qurl=line.split("=",1)[1].strip().strip('"')
    if line.startswith("QDRANT_API_KEY="):
        qkey=line.split("=",1)[1].strip().strip('"')
op=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def req(path, body=None, method="GET"):
    data=json.dumps(body).encode() if body is not None else None
    r=urllib.request.Request(f"{qurl}{path}", data=data,
        headers={"Content-Type":"application/json","api-key":qkey}, method=method)
    return json.load(op.open(r, timeout=30))

def det_uuid(code): return str(uuid.UUID(hashlib.md5(f"kbli_2025_bps::{code}".encode()).hexdigest()))
PHANTOMS=["26120","60111","82920","85598"]
ids=[det_uuid(c) for c in PHANTOMS]

before=req("/collections/kbli_2025_final_oss")["result"]["points_count"]
print("twin count BEFORE:", before)

# delete by id (idempotent — deleting absent ids is a no-op)
r=req("/collections/kbli_2025_final_oss/points/delete?wait=true", {"points": ids}, "POST")
print("delete op status:", r.get("status"))

after=req("/collections/kbli_2025_final_oss")["result"]["points_count"]
print("twin count AFTER:", after, "(expected 1559)")

# confirm gone via retrieve-by-id (correct endpoint: POST /points)
chk=req("/collections/kbli_2025_final_oss/points", {"ids": ids, "with_payload": False}, "POST")
remaining=[p["id"] for p in chk.get("result",[])]
print("phantom points still present:", remaining if remaining else "NONE")
print("live kbli_2025_final_hybrid:", req("/collections/kbli_2025_final_hybrid")["result"]["points_count"], "(must be 4624 — untouched)")
