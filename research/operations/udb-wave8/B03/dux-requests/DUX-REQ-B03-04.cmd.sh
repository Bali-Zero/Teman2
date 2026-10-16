  python3 -c '
  import glob, os, json
  patterns = [
      "**/LEAD-DELTA.json",
      "**/launchd-cron-normalize.json",
      "**/SOURCE-BOUNDARY-PRO.json",
      "**/REGISTERED-INGRESS-SOURCE.json",
      "**/GITHUB-WORKFLOW-METADATA.json"
  ]
  found = {}
  for p in patterns:
      found[p] = [f for f in glob.glob(p, recursive=True) if os.path.isfile(f)]
  print(json.dumps(found, indent=2))
  '
