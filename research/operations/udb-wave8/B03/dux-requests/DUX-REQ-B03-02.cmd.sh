  python3 -c '
  import csv, hashlib, json, re
  path = ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv"
  src_ids = {}
  wf_by_path_sha = {}
  wf_by_content_sha = {}
  index_rows = []
  ci_unmatched = []
  with open(path, newline="", encoding="utf-8") as f:
      for row in csv.DictReader(f):
          cid = row["consumer_id"]
          if cid.startswith("src_"):
              hex16 = cid[4:]
              src_ids[hex16] = cid
              ep = row["entry_point"]
              if ep.startswith(".github/workflows/"):
                  wf_by_path_sha[hashlib.sha256(ep.encode()).hexdigest()] = cid
                  m = re.search(r"workflow sha256 ([0-9a-f]{64})", row["phase_ci_registration_evidence"] or "")
                  if m:
                      wf_by_content_sha[m.group(1)] = cid
          elif cid.startswith("index_"):
              index_rows.append((cid, row["evidence"]))
          elif cid.startswith("CI-REGISTRATION-UNMATCHED-GH-"):
              ci_unmatched.append((cid, row["evidence"], row["phase_ci_reported_states"]))
  idx_matched = 0
  idx_unmatched = []
  for cid, ev in index_rows:
      m = re.search(r"source_id=([0-9a-f]{24})", ev)
      sid16 = m.group(1)[:16] if m else cid[6:22]
      if sid16 in src_ids:
          idx_matched += 1
      else:
          idx_unmatched.append(cid)
  ci_matched_path = 0
  ci_matched_content = 0
  ci_still_unmatched = []
  for cid, ev, st in ci_unmatched:
      m = re.search(r"source-path-sha256=([0-9a-f]{64})", ev)
      sha = m.group(1) if m else ""
      if sha in wf_by_path_sha:
          ci_matched_path += 1
      elif sha in wf_by_content_sha:
          ci_matched_content += 1
      else:
          ci_still_unmatched.append({"cid": cid, "sha": sha, "state": st})
  print(json.dumps({
      "index_total": len(index_rows),
      "index_matched_to_src": idx_matched,
      "index_unmatched_ids": idx_unmatched[:20],
      "ci_unmatched_total": len(ci_unmatched),
      "ci_matched_by_path_sha256": ci_matched_path,
      "ci_matched_by_workflow_sha256": ci_matched_content,
      "ci_still_unmatched_count": len(ci_still_unmatched),
      "ci_still_unmatched_sample": ci_still_unmatched[:15]
  }, indent=2))
  '
