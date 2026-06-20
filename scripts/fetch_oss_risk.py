"""Fetch the OFFICIAL risk/licensing ground-truth from OSS RBA for all 1559 5-digit KBLI.

Endpoint: GET gw.oss.go.id/v2/portal/kbli/ruang-lingkup/{uuid}
Auth: static app credential (user_key) — ZERO PII (public economic classification).
The response carries KbliResikos[] per scope, each with SkalaUsaha + Resiko (official
Tingkat Resiko) + jangka_waktu + KbliPersyaratans/KbliIzins/KbliKewajibans/Kewenangans.

Phase 1 = raw dump only (separate network from transform). Writes one JSON line per code
to /tmp/oss_risk_raw.jsonl so a parsing bug never forces a re-download.

Usage:
    python scripts/fetch_oss_risk.py [--limit N] [--start N]
"""
import argparse, json, time, urllib.request, urllib.error
from pathlib import Path

OSS_GT = Path("/Users/balizero/Desktop/nuzantara/data/source_documents/KBLI_2025_OSS_GROUND_TRUTH.json")
OUT = Path("/tmp/oss_risk_raw.jsonl")
USER_KEY = "846ee507525c6b00d18733e066bd5686"
BASE = "https://gw.oss.go.id/v2/portal/kbli/ruang-lingkup/"


def fetch(uuid, retries=3):
    req = urllib.request.Request(BASE + uuid, headers={"user_key": USER_KEY, "accept": "application/json"})
    # bypass system proxy explicitly (memory trap: urllib honors it)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for attempt in range(retries):
        try:
            with opener.open(req, timeout=25) as r:
                return json.loads(r.read().decode("utf-8")), r.status
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {"success": False, "code": 404}, 404
            if attempt == retries - 1:
                return {"error": f"HTTP {e.code}"}, e.code
        except Exception as e:
            if attempt == retries - 1:
                return {"error": str(e)}, 0
        time.sleep(1.5 * (attempt + 1))
    return {"error": "exhausted"}, 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--start", type=int, default=0)
    args = ap.parse_args()

    gt = json.loads(OSS_GT.read_text(encoding="utf-8"))
    codes = [(str(x["kode"]), x["uuid"]) for x in gt["data"] if x.get("digits") == 5]
    codes = codes[args.start:]
    if args.limit:
        codes = codes[: args.limit]

    # resume: skip codes already in OUT
    done = set()
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(line)["kode"])
            except Exception:
                pass

    ok = err = skip = notfound = 0
    with OUT.open("a", encoding="utf-8") as f:
        for i, (kode, uuid) in enumerate(codes):
            if kode in done:
                skip += 1
                continue
            data, status = fetch(uuid)
            rec = {"kode": kode, "uuid": uuid, "status": status, "data": data}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            if status == 200 and data.get("success"):
                ok += 1
            elif status == 404:
                notfound += 1
            else:
                err += 1
            if (i + 1) % 100 == 0:
                print(f"  {i+1}/{len(codes)} ok={ok} 404={notfound} err={err} skip={skip}", flush=True)
            time.sleep(0.15)  # be polite

    print(f"DONE ok={ok} 404={notfound} err={err} skip={skip} total_lines={ok+notfound+err+skip}")


if __name__ == "__main__":
    main()
