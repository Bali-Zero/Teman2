"""Census replay seq-20 vs seq-21 at AS_OF inside seq-21 validity (read-only).

Re-run from apps/backend-rag (no DB, no network, no signing key):
  export VISA_ENGINE_TRUST_STORE_KEYS_JSON=<the PUBLIC prod key JSON, see test_seq21_pack.PROD_TRUST_STORE_JSON>
  JWT_SECRET_KEY=<any 32+ chars> API_KEYS=<any> PYTHONPATH=. .venv/bin/python <this file>
Output of the 2026-09-14 run: census-replay-seq20-vs-seq21.txt (same directory).
"""
import json
from collections import Counter
from pathlib import Path
import backend.tests.services.visa_engine.test_seq21_pack as t
from backend.scripts.visa_engine.compile_pack import load_rule_pack_payload, wrap_as_unsigned_pack
from backend.services.visa_engine import compiler
from backend.services.visa_engine.compiler import DEFAULT_FACT_REGISTRY

def comp(p):
    return compiler.build_compiled_pack(wrap_as_unsigned_pack(load_rule_pack_payload(p)), fact_registry=DEFAULT_FACT_REGISTRY)

walks = {}
for path in sorted(t._CORPUS_DIR.glob("*.json")):
    spec = json.loads(path.read_text(encoding="utf-8")); walks[str(spec["label"])] = spec
p20, p21 = comp(t._SEQ20_SOURCE_PATH), comp(t._SEQ21_SOURCE_PATH)
r20, r21 = t._replay(p20, walks), t._replay(p21, walks)
print("as_of", t.AS_OF.isoformat(), "walks", len(walks))
def keys(d): return sorted(d.keys())
sample = next(iter(r20.values())); print("actual keys", keys(sample))
def st(r): return Counter(v.get("state") for v in r.values())
print("seq20 states", dict(st(r20))); print("seq21 states", dict(st(r21)))
def named(r):
    s=set()
    for v in r.values():
        for c in v.get("candidates") or v.get("candidate_product_codes") or []:
            s.add(c if isinstance(c,str) else json.dumps(c))
    return s
n20, n21 = named(r20), named(r21)
print("distinct named seq20", len(n20), sorted(n20)); print("distinct named seq21", len(n21), sorted(n21))
changed = [l for l in walks if r20[l] != r21[l]]
print("walks whose outcome differs", len(changed))
for l in changed:
    print(" ", l, "|", json.dumps(r20[l], sort_keys=True)[:300], "->", json.dumps(r21[l], sort_keys=True)[:300])
base = dict(walks["offshore/work/sponsor_government"]["overrides"])
for code, ov in t._gold_overrides().items():
    d21 = t._decide(p21, {**base, **ov}, f"gold/{code}")
    d20 = t._decide(p20, {**base, **ov}, f"gold/{code}")
    print("gold", code, "seq20:", d20.get("state"), d20.get("candidates"), "| seq21:", d21.get("state"), d21.get("candidates"))
