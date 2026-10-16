python3 -I -c '
import csv, json
from collections import Counter
prefixes = ("apps/backend-rag/backend/app/routers/", "apps/backend-rag/backend/services/", "apps/bali-intel-scraper/", "packages/cell/", "packages/cell-core/", "packages/research-os-core/")
c = Counter()
with open(".agent-receipts/udb-wave8-inputs/consumer-matrix.csv", newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        ep = r["entry_point"]
        pre = next((x for x in prefixes if ep.startswith(x)), None)
        if pre:
            c[pre + " | " + (r["phase_source_path_evidence"] or "EMPTY") + " | " + (r["phase_source_scope_status"] or "EMPTY") + " | fc=" + (r["phase_factory_candidate_count"] or "EMPTY")] += 1
print(json.dumps({"total_rows_in_prefixes": sum(c.values()), "prefix|phase_source_path_evidence|phase_source_scope_status|factory_count": dict(c.most_common())}, indent=1))
'
