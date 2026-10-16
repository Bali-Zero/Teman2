  python3 -c '
  import csv, json
  path = ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv"
  restore_hits = []
  entry_marker_counts = {"total": 0, "by_domain_class": {}, "verified_or_non_blocked": []}
  with open(path, newline="", encoding="utf-8") as f:
      for idx, row in enumerate(csv.DictReader(f), start=2):
          blob = " ".join(row.values()).lower()
          if "restore" in blob or "pg_restore" in blob:
              restore_hits.append({
                  "line": idx,
                  "consumer_id": row["consumer_id"],
                  "domain": row["domain"],
                  "entry_point": row["entry_point"],
                  "disposition": row["disposition"],
                  "activation_status": row["activation_status"],
                  "evidence": row["evidence"][:160]
              })
          if "PYTHON_SOURCE_WITH_ENTRY_MARKERS" in (row["phase_source_path_evidence"] or "") or row["disposition"] == "ADAPTED_ISOLATED_VERIFIED":
              entry_marker_counts["total"] += 1
              dc = row["domain_classification"] or "NONE"
              entry_marker_counts["by_domain_class"][dc] = entry_marker_counts["by_domain_class"].get(dc, 0) + 1
              if row["disposition"] != "BLOCKED_DISCOVERY":
                  entry_marker_counts["verified_or_non_blocked"].append({
                      "line": idx,
                      "consumer_id": row["consumer_id"],
                      "entry_point": row["entry_point"],
                      "disposition": row["disposition"]
                  })
  print(json.dumps({
      "restore_hits_count": len(restore_hits),
      "restore_hits": restore_hits,
      "entry_marker_summary": entry_marker_counts
  }, indent=2))
  '
