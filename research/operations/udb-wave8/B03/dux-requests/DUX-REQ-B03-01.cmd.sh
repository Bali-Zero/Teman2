  python3 -c '
  import csv, json, re
  from collections import Counter
  path = ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv"
  prefix_counts = Counter()
  disp_counts = Counter()
  act_counts = Counter()
  prefix_disp = Counter()
  with open(path, newline="", encoding="utf-8") as f:
      r = csv.DictReader(f)
      for row in r:
          cid = row["consumer_id"]
          m = re.match(r"^([A-Za-z0-9-]+?)(?:_[0-9a-f]{12,24}|-[0-9a-f]{12})$", cid)
          pfx = m.group(1) if m else cid.split("_")[0]
          prefix_counts[pfx] += 1
          disp_counts[row["disposition"]] += 1
          act_counts[row["activation_status"]] += 1
          prefix_disp[f"{pfx}::{row[\"disposition\"]}::{row[\"test_coverage\"]}"] += 1
  print(json.dumps({
      "total_rows": sum(prefix_counts.values()),
      "prefix_counts": dict(prefix_counts),
      "disposition_counts": dict(disp_counts),
      "activation_status_counts": dict(act_counts),
      "prefix_disposition_coverage": dict(prefix_disp)
  }, indent=2, sort_keys=True))
  '
