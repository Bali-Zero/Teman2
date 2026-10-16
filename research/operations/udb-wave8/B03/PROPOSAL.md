---
adversarial_review: codex
---

# B03 Development Proposal — Deterministic 6,030-Lead Reconciliation & Denominator Engine

## 0. Mandate & Sibling Contract

- **Campaign / Block**: `universal-db-wave8-20261015` / `B03` (Active-consumer denominator)
- **Mission Colour / Gear / Role**: `BLUE` / `GEAR3` / `EXTERNAL PREPARER, NO_DUX`
- **Host / Worktree / Base**: `Mini` / `~/nuzantara/.worktrees/db-udb-b03-census` / `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`
- **Owned Perimeter**: `research/operations/udb-wave8/B03/**` and assigned evidence-pack path; optional coherent census adapter/verifier and tests only (`BATTLE.md:6-7`).
- **Frozen Sibling Contract (`BATTLE.md:9-10`)**:
  - Core fields (unchanged): `consumer_id,operation_id,store_id,source_version,evidence_timestamp,evidence_sha256,status,unknowns`
  - Operation instance extension fields (owned by `B05`): `principal,role,tenant,authorization,transaction,effects,retries,idempotency,failure,retention,recovery`
  - Dependencies: `B04, B07`.

---

## 1. Proposed Deterministic Reconciliation Architecture

This section retains a rejected historical development proposal, superseded by the tested adapter and definitive artifact contracts. The schema values, joins and retirement rules below are not admitted current behavior. It originally proposed to implement a deterministic reconciliation module and test suite under our owned perimeter that ingests `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv` (6,029 rows, SHA-256 `c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118`), `STATE.json` (SHA-256 `caaebbbac9703bf5ebd5f7624b8a2dd6759a2e508703f311cecffebf1c0967d4`), and the pinned `DUX-REQUESTS` outputs to reconcile all **6,030** union leads without guessing.

### 1.1 Rejected Historical Record Schema & Conservation Invariant
Every lead in the 6,030 universe (`6,029` baseline CSV rows + `1` `mini.restore_drill` runtime organ row) emits exactly one canonical record containing the frozen sibling contract fields:
- `consumer_id`: Lead identifier (`src_*`, `runtime_*`, `index_*`, `job_*`, `cron_*`, `engine_*`, `SOURCE-PATH-UNMATCHED-PRO-*`, `SOURCE-TRACE-UNMATCHED-PRO-*`, `CI-REGISTRATION-UNMATCHED-GH-*`, `NOTEBOOK-CONTAINER-REFERENCE-NLM-*`, or `mini.restore_drill`).
- `operation_id`: Proven operation identifier (e.g., `op:db:migrate:cli` for `src_c8f206461cd9bf69`, `op:mini:restore_drill` for `mini.restore_drill`), `NONE_EXCLUDED` for non-consumer rows, `JOINED_TO:<canonical_consumer_id>` for `duplicate` rows, or `UNKNOWN` when awaiting `B05`.
- `store_id`: Proven store identifier (`postgres:pro`, `postgres:mini`, `postgres:M5`, `redis:pro`, `redis:mini`, `NON_CONSUMER_ENTITY`, or `UNKNOWN` when awaiting `B04`/`B07`).
- `source_version`: `d0c67ee668f97c754e8bcec662d0df7dbf30a126` for tracked repository leads, or `OUTSIDE_TRACKED_CODE_INDEX` for untracked host wrappers.
- `evidence_timestamp`: Snapshot ISO-8601 timestamp derived from the row's provenance (`2026-10-12T04:54:00Z`, `2026-10-13T10:18:00Z`, or `2026-10-15T06:06:16Z`).
- `evidence_sha256`: Pinned SHA-256 digest of the backing frozen input artifact from `INPUT-MANIFEST.json` (plus workflow file SHA-256 where present).
- `status`: Candidate disposition in `{active, retired, duplicate, excluded}` with explicit evidence-gate sub-state (`verified` vs. `blocked_evidence` when runtime/store proof is unresolved, ensuring zero unverified promotions).
- `unknowns`: Deterministic list of unresolved evidence gaps (e.g., `["MISSING_B04_STORE_BINDING", "MISSING_B07_RUNTIME_EXECUTION_PROOF", "MISSING_REGISTRATION_HASH_PREIMAGE"]`).

### 1.2 Rejected Historical Disposition & Reconciliation Rules
1. **`excluded` (Non-Consumer Entities)**:
   - `NOTEBOOK-CONTAINER-REFERENCE-NLM-*` (67 rows): `NOT_DATABASE_CONSUMER_IDENTITY`.
   - `engine_{pro,mini,M5}_*` (5 rows): Target database/cache server engines (`D01_PHYSICAL_SCOPE`), not consumers.
   - `RETAINED_TEST_SOURCE` rows in `src_*`: Test suites explicitly excluded from the active production consumer denominator (`D15`).
2. **`duplicate` (Cross-Phase Multi-Representation Joins)**:
   - `index_<24hex>` rows whose `source_id=<24hex>` prefix matches `src_<16hex>` in `source-index-enhanced.json` are marked `duplicate` of the primary `src_<16hex>` row.
   - `CI-REGISTRATION-UNMATCHED-GH-<12hex>` rows whose `source-path-sha256=<64hex>` matches either `sha256(entry_point)` or the `workflow sha256 <64hex>` recorded on `src_*` workflow rows (`consumer-matrix.csv:3-34`) are marked `duplicate` of the corresponding `src_*` row.
   - `SOURCE-PATH-UNMATCHED-PRO-*` and `SOURCE-TRACE-UNMATCHED-PRO-*` rows (`PATH_NOVELTY_NOT_ACTOR_NOVELTY`) that resolve to an existing `src_*` path hash are marked `duplicate`; unresolved hashes retain explicit `unknowns`.
3. **`retired` (Proven Retired Code / Registrations)**:
   - `.github/workflows/restore-drill.yml` (`src_307bea3dfb94ec31`, removed in `e1b328af52` and absent from active GitHub workflow registrations) is dispositioned `retired` (superseded by `mini.restore_drill`), with any residual host copy explicitly checked via the 5-restore-reference reconciliation table.
   - `.github/workflows/*.yml` rows with `phase_ci_reported_states=disabled_manually` and verified absence of active runtime triggers are dispositioned `retired` (or flagged with `unknowns` if manual `workflow_dispatch` remains reachable).
4. **`active` vs. Evidence-Blocked Candidates**:
   - `mini.restore_drill` (the 6,030th union lead, loaded Mini restore organ) and verified active registrations/CLI tools (`src_c8f206461cd9bf69` `migrate.py` under isolated CLI manual scope) are recorded with their exact verification scope.
   - All remaining `BLOCKED_DISCOVERY` and `BLOCKED_RUNTIME_CONTRACT` leads are preserved with their exact blocker and `unknowns` list rather than fabricated into verified `active` or `retired` claims.

### 1.3 Five Historical Restore References & Manual/Break-Glass Deliverables
- **Five Historical Restore References Table**: Reconciles all 5 restore-related baseline leads (including `src_307bea3dfb94ec31` `.github/workflows/restore-drill.yml`, `src_4aa41913f64f2f8c` `scripts/ci/restore_drill_verify.py` with its stale line-3 docstring, any `index_*` entry marker for `restore_drill_verify.py`, and host `job_*`/`runtime_*`/`cron_*` restore leads) against the 6,030th lead (`mini.restore_drill`).
- **Manual / Break-Glass Consumer Catalog**: Enumerates CLI migration runners (`apps/backend-rag/backend/db/migrate.py`), DR verification tools (`scripts/ci/restore_drill_verify.py`), `PYTHON_SOURCE_WITH_ENTRY_MARKERS` operator scripts, and untracked `runtime_*` host scripts (`OUTSIDE_TRACKED_CODE_INDEX`).

---

## 2. Verification & Test Plan (for Synthesis/Execution Stage)

1. **6,030 Conservation Test**: Asserts `len(reconciled_rows) == 6030` (`6029` CSV rows + `1` `mini.restore_drill`) and exact 1-to-1 `consumer_id` parity.
2. **Contract & Hash Pin Test**: Asserts every output row has all 8 required sibling contract fields and cites valid SHA-256 digests from `INPUT-MANIFEST.json`.
3. **Negative Case 1 (Fail-Closed on Unproven Active Promotion)**: Verifies the classifier rejects promoting any `BLOCKED_DISCOVERY` or `PATH_MATCH_DOES_NOT_PROVE_SAME_DATABASE_CONSUMER` row to verified `active` without runtime + store evidence.
4. **Negative Case 2 (Non-Consumer Leakage Guard)**: Verifies zero `NOTEBOOK-CONTAINER-REFERENCE-NLM-*`, zero `engine_*`, and zero `RETAINED_TEST_SOURCE` rows enter the active consumer denominator.
5. **Negative Case 3 (Premature Retirement Guard)**: Verifies git deletion alone cannot clear a host registration without checking host registration state.

---

## DUX-REQUESTS

Per `DUX-NOTE-ANALYSIS.md:18-24`, the following read-only computations over local worktree files are requested so the synthesis run can cite exact, un-guessed counts and join tables (aggregate/hashed shapes and repository metadata only; zero client rows, values, credentials, or OSINT):

### `DUX-REQ-B03-01`: Exact Partition & Disposition Histogram of `consumer-matrix.csv` (6,029 rows)
- **Read-only command**:
  ```bash
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
  ```
- **Inputs**: `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv`
- **Expected output shape**: JSON object with exact row counts by `consumer_id` prefix (`src`, `runtime`, `index`, `job_pro`, `cron_pro`, `job_mini`, `cron_mini`, `job_M5`, `engine_pro`, `engine_mini`, `engine_M5`, `SOURCE-PATH-UNMATCHED-PRO`, `SOURCE-TRACE-UNMATCHED-PRO`, `CI-REGISTRATION-UNMATCHED-GH`, `NOTEBOOK-CONTAINER-REFERENCE-NLM`), `disposition`, `activation_status`, and `(prefix, disposition, test_coverage)`.
- **Why it matters**: Eliminates any estimation on the `runtime_*` vs. `index_*` split and the exact count of `RETAINED_TEST_SOURCE` rows across all 6,029 baseline rows.

### `DUX-REQ-B03-02`: Deterministic Join Verification (`index_*` ↔ `src_*` and `CI-REGISTRATION-UNMATCHED-GH-*` ↔ `.github/workflows/*`)
- **Read-only command**:
  ```bash
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
  ```
- **Inputs**: `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv`
- **Expected output shape**: JSON summary of exact match counts between `index_*` and `src_*`, and between `CI-REGISTRATION-UNMATCHED-GH-*` and `.github/workflows/*.yml`.
- **Why it matters**: Proves the exact `duplicate` reduction count from cross-phase identity joins.

### `DUX-REQ-B03-03`: Complete Enumeration of Restore-Related Rows & Manual Entry-Marker Leads in `consumer-matrix.csv`
- **Read-only command**:
  ```bash
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
  ```
- **Inputs**: `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv`
- **Expected output shape**: JSON list of all rows matching `restore`/`pg_restore` (with line number, `consumer_id`, `entry_point`, `disposition`, `activation_status`) and aggregate summary of `PYTHON_SOURCE_WITH_ENTRY_MARKERS` manual/CLI leads.
- **Why it matters**: Pinpoints all five historical restore source references in `consumer-matrix.csv` and quantifies the manual/CLI entry-marker consumer cohort.

### `DUX-REQ-B03-04`: Locate Upstream Pre-Image Artifacts (`LEAD-DELTA.json`, `launchd-cron-normalize.json`, `SOURCE-BOUNDARY-PRO.json`) if Present on Host
- **Read-only command**:
  ```bash
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
  ```
- **Inputs**: Current worktree filesystem metadata (filenames only).
- **Expected output shape**: JSON map of artifact filenames to relative paths if present in the worktree, or empty lists if absent.
- **Why it matters**: Determines whether pre-images for hashed `job_*`, `cron_*`, and `SOURCE-PATH-UNMATCHED-PRO-*` leads are available locally or must remain documented as an explicit upstream input boundary in `RESULT.json`.

## Adversarial review

Fresh independent Codex review by `/root/b03_available_final_gate` inspected pre-attribution lines 1-62, as pinned in `R1-DOCUMENT-REVIEW.json`. This is a scoped document review, not a complete document endorsement, implementation approval, native observation or final exact-head gate. Surviving objections DOC2 are retained in that receipt; the parent reconciled the current synthesis facts and labels the rejected historical schema/join/retirement hypotheses as superseded. Historical command/runtime statements are retained as recorded instructions and receipts, not newly observed events. Operational acceptance and the active denominator remain unproved.
