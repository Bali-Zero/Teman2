"""Census replay seq-20 vs seq-21 at AS_OF inside seq-21 validity (read-only).

Re-run from apps/backend-rag (no DB, no network, no signing key):
  export VISA_ENGINE_TRUST_STORE_KEYS_JSON=<the PUBLIC prod key JSON, see test_seq21_pack.PROD_TRUST_STORE_JSON>
  JWT_SECRET_KEY=<any 32+ chars> API_KEYS=<any> PYTHONPATH=. .venv/bin/python <this file>
Output of the 2026-09-14 WITA run (AS_OF 2026-09-13T21:30Z): census-replay-seq20-vs-seq21.txt (same directory).
"""

import json
from collections import Counter

import backend.tests.services.visa_engine.test_seq21_pack as t
from backend.scripts.visa_engine.compile_pack import load_rule_pack_payload, wrap_as_unsigned_pack
from backend.services.visa_engine import compiler
from backend.services.visa_engine.compiler import DEFAULT_FACT_REGISTRY


def comp(path):
    payload = load_rule_pack_payload(path)
    return compiler.build_compiled_pack(
        wrap_as_unsigned_pack(payload), fact_registry=DEFAULT_FACT_REGISTRY
    )


def states(replay):
    return dict(Counter(outcome.get("state") for outcome in replay.values()))


def named(replay):
    return {code for outcome in replay.values() for code in outcome.get("candidates") or []}


walks = {}
for path in sorted(t._CORPUS_DIR.glob("*.json")):
    spec = json.loads(path.read_text(encoding="utf-8"))
    walks[str(spec["label"])] = spec
p20 = comp(t._SEQ20_SOURCE_PATH)
p21 = comp(t._SEQ21_SOURCE_PATH)
r20 = t._replay(p20, walks)
r21 = t._replay(p21, walks)
print("as_of", t.AS_OF.isoformat(), "walks", len(walks))
print("actual keys", sorted(next(iter(r20.values())).keys()))
print("seq20 states", states(r20))
print("seq21 states", states(r21))
n20, n21 = named(r20), named(r21)
print("distinct named seq20", len(n20), sorted(n20))
print("distinct named seq21", len(n21), sorted(n21))
changed = [label for label in walks if r20[label] != r21[label]]
print("walks whose outcome differs", len(changed))
for label in changed:
    before = json.dumps(r20[label], sort_keys=True)[:300]
    after = json.dumps(r21[label], sort_keys=True)[:300]
    print(" ", label, "|", before, "->", after)
base = dict(walks["offshore/work/sponsor_government"]["overrides"])
for code, overrides in t._gold_overrides().items():
    d21 = t._decide(p21, {**base, **overrides}, f"gold/{code}")
    d20 = t._decide(p20, {**base, **overrides}, f"gold/{code}")
    print(
        "gold", code,
        "seq20:", d20.get("state"), d20.get("candidates"),
        "| seq21:", d21.get("state"), d21.get("candidates"),
    )
