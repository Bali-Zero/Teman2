python3 -I -c '
import csv, json, hashlib
from collections import Counter
p = ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv"
sha = hashlib.sha256(open(p, "rb").read()).hexdigest()
by_domain, by_hint, by_dc = Counter(), Counter(), Counter()
with open(p, newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        by_domain[r["domain"] or "EMPTY"] += 1
        by_hint[r["domain_hint"] or "EMPTY"] += 1
        by_dc[(r["disposition"] or "EMPTY") + "|" + (r["contract_coverage_status"] or "EMPTY")] += 1
print(json.dumps({"sha256": sha, "total": sum(by_domain.values()), "by_domain": dict(by_domain.most_common()), "by_domain_hint": dict(by_hint.most_common()), "by_disposition_contract_status": dict(by_dc.most_common())}, indent=1))
'
