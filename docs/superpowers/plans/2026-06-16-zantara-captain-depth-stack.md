# Zantara Captain Depth Stack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the local-only Captain pipeline with five Client Captain depth layers, plus Team Captain and Owner Captain artifacts with progressively deeper aggregate reasoning layers.

**Architecture:** Client Captain remains the per-case shadow runtime and writes five deterministic depth layers per draft. Team Captain reads the local client shadow DB and aggregates operator/team coaching into six layers per specialist lane. Owner Captain reads the local team and client shadow DBs and writes seven owner-level governance layers without raw message text, WhatsApp sends, CRM mutations, or cloud LLM calls.

**Tech Stack:** Python 3, SQLite, pytest, local ignored artifacts under `research/personal/wa-corpus/`.

---

### Task 1: Client Captain Depth Layers

**Files:**

- Modify: `scripts/whatsapp_corpus/build_client_captain_shadow.py`
- Modify: `scripts/tests/test_whatsapp_corpus_client_captain_shadow.py`

- [x] **Step 1: Write the failing test**

Assert that each client shadow draft writes five `shadow_depth_layers` rows with levels 1..5.

- [x] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest -q scripts/tests/test_whatsapp_corpus_client_captain_shadow.py`
Expected: FAIL because `shadow_depth_layers` does not exist.

- [x] **Step 3: Write minimal implementation**

Add deterministic layer generation:

1. signal readout
2. diagnosis
3. decision
4. draft gate
5. operator coaching

- [x] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest -q scripts/tests/test_whatsapp_corpus_client_captain_shadow.py`
Expected: PASS.

### Task 2: Team Captain Shadow Artifact

**Files:**

- Create: `scripts/whatsapp_corpus/build_team_captain_shadow.py`
- Create: `scripts/tests/test_whatsapp_corpus_team_captain_shadow.py`
- Modify: `scripts/whatsapp_corpus/README.md`

- [x] **Step 1: Write the failing test**

Create a small client shadow DB, run Team Captain, and assert one team finding per specialist lane plus six depth layers per finding.

- [x] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest -q scripts/tests/test_whatsapp_corpus_team_captain_shadow.py`
Expected: FAIL because module is missing.

- [x] **Step 3: Write minimal implementation**

Read `client_captain_shadow.local.sqlite`, group by specialist lane, write `team_captain_findings` and `team_captain_depth_layers`.

- [x] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest -q scripts/tests/test_whatsapp_corpus_team_captain_shadow.py`
Expected: PASS.

### Task 3: Owner Captain Shadow Artifact

**Files:**

- Create: `scripts/whatsapp_corpus/build_owner_captain_shadow.py`
- Create: `scripts/tests/test_whatsapp_corpus_owner_captain_shadow.py`
- Modify: `scripts/whatsapp_corpus/README.md`

- [x] **Step 1: Write the failing test**

Create client and team shadow DBs, run Owner Captain, and assert one owner finding plus seven depth layers.

- [x] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest -q scripts/tests/test_whatsapp_corpus_owner_captain_shadow.py`
Expected: FAIL because module is missing.

- [x] **Step 3: Write minimal implementation**

Read aggregate-safe client/team shadow DBs, write `owner_captain_findings` and `owner_captain_depth_layers`.

- [x] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest -q scripts/tests/test_whatsapp_corpus_owner_captain_shadow.py`
Expected: PASS.

### Task 4: Real Generation and Verification

**Files:**

- Runtime outputs under `/Users/nuzantara/Desktop/nuzantara/research/personal/wa-corpus/drive-*`

- [x] **Step 1: Sync code to Pro worktree**

Use rsync for the changed scripts/tests/README into `/Users/nuzantara/Desktop/nuzantara/.worktrees/backend-rag-zantara-client-captain-academy`.

- [x] **Step 2: Run targeted tests on Pro**

Run the Client, Team, Owner, Academy, Drive import, review manifest, and privacy audit tests.

- [x] **Step 3: Generate real Team and Owner artifacts**

Run Team Captain and Owner Captain against the full Drive Client Shadow DB.

- [x] **Step 4: Audit privacy and count outputs**

Run `audit_privacy_outputs.py` on the new summary/output directories and query SQLite counts.
