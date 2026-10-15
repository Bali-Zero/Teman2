# Dux-authored execution of B03 synthesis requests (synthesis listed them as inline bullets, not fenced blocks)

Commands are from `DEFINITIVE-SYNTHESIS.md` §DUX-REQUESTS; the Dux added only the fence, `-I`
(isolated interpreter), `-B` (no `__pycache__` written into the perimeter; added after a first `-I`
run left a `.pyc`) and `2>&1` (unittest reports on stderr).
DUX-REQ-B03-13 (cross-host LaunchAgents/crontab hashing on Pro/Mini/M5) is NOT admitted: no admitted
host-metadata adapter covers it; it is deferred.

### `DUX-REQ-B03-10`
```bash
python3 -I -B -m unittest discover -s research/operations/udb-wave8/B03 -p "test_*.py" -v 2>&1
```

### `DUX-REQ-B03-11`
```bash
python3 -I -B research/operations/udb-wave8/B03/b03_census_adapter.py --output-dir research/operations/udb-wave8/B03/artifacts 2>&1
```

### `DUX-REQ-B03-12`
```bash
python3 -I -B -c 'import hashlib, json, subprocess; files = subprocess.check_output(["git", "ls-files"], text=True).splitlines(); idx = json.load(open(".agent-receipts/udb-wave8-inputs-dux/prior/census-20261012-0454/source-index-enhanced.json")); idx_set = {n["source_id"] for n in idx["nodes"]}; m = {hashlib.sha256(f.encode()).hexdigest()[:24]: f for f in files}; matched = sorted((sid, m[sid]) for sid in idx_set if sid in m); print("matched_index_nodes:", len(matched), "of", len(idx_set)); print("pg_sh_match:", [x for x in matched if "pg" in x[1] or "restore" in x[1] or "migrate" in x[1]][:30])'
```
