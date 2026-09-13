"""Score a Dux support run against the frozen labels. Reads labels ONLY here, post hoc —
the run itself never saw them (the same discipline B1.4's harness kept)."""
import json, sys, collections
r = json.load(open(sys.argv[1]))
recs = r["records"]
exp = lambda s: "SUPPORTED" if s == "sufficient" else "NOT_SUPPORTED"
for setname in sorted({x["set"] for x in recs}):
    sub = [x for x in recs if x["set"] == setname]
    ok = [x for x in sub if x["verdict"] == exp(x["stratum"])]
    bad = [x for x in sub if x["verdict"] != exp(x["stratum"])]
    print(f"=== set {setname}: {len(ok)}/{len(sub)} agree, {len(bad)} disagree")
    print("   by stratum:", dict(collections.Counter((x['stratum'], x['verdict']) for x in sub)))
    for x in bad:
        print(f"   MISS {x['case_id']} [{x.get('pair_type') or x['stratum']}] expected {exp(x['stratum'])} got {x['verdict']} votes={x['votes']}")
    byp = collections.defaultdict(list)
    for x in sub:
        if x["pair_id"]:
            byp[x["pair_id"]].append(x)
    dist = [p for p, ms in byp.items() if len(ms) == 2 and {m["stratum"]: m["verdict"] for m in ms} == {"sufficient": "SUPPORTED", "relevant_insufficient": "NOT_SUPPORTED"}]
    if byp:
        print(f"   pairs distinguished: {len(dist)}/{len(byp)}")
        for p in sorted(set(byp) - set(dist)):
            print("     lost pair", p, [(m['stratum'], m['verdict'], m.get('pair_type')) for m in byp[p]])
print()
print("judges:", dict(collections.Counter(x["judge"] for x in recs)))
print("fallback_used:", sum(1 for x in recs if x["fallback_used"]))
nonu = [x["case_id"] for x in recs if len(set(x["votes"])) > 1]
print("non-unanimous (majority-of-3 earned its keep here):", len(nonu), nonu)
lat = sorted(x["latency_s"] for x in recs)
print(f"latency s: min {lat[0]} median {lat[len(lat)//2]} max {lat[-1]} | wall {r['elapsed_s']}s for {len(recs)} cases x 3 reps")
