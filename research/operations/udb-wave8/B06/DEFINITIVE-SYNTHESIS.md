---
adversarial_review: codex
reviewed_source_sha256: "7c288289468d86ee3d280631c7f9dcdefe212b13b942035bf2b28afea93a9bbd"
review_disposition: PARTIAL_DOCUMENTATION_REQUIRES_RECONCILIATION
---

# DEFINITIVE-SYNTHESIS — Wave 8 Block `B06` (Business-Domain Paths `D04`–`D10`)

## Current package and historical preparation boundary (2026-10-16)

Current package evidence records 27 passing source tests:18 preserved legacy tests and9 inventory tests. The C09 census retains6029 IDs;4231 public source paths yield1566 rows with static anchors,4463 untraced rows and21001 syntax signals accepted by actual B05 schema validation. These are overlapping path candidates, not proven business membership or complete operation semantics. Independent source execution is available; document and final committed-head acceptance remain incomplete. No native DB query or credential provisioning was performed. block_closed:false; production adoption:false.

The preparation sections below preserve the earlier18-test scope and its corrected historical claims. They do not supersede the current inventory evidence or establish operational closure. References to raw untracked inputs, ungranted execution or pending synthesis describe that earlier preparation phase unless explicitly repeated in current RESULT.json. Current source files and their tests are unchanged by this document reconciliation.

## Current package status (2026-10-16)

Current source tests: 27 passed (18 preserved legacy tests plus 9 inventory tests). All 6029 C09 IDs and 4231 public source paths are retained; 1566 rows have static anchors and 4463 have no trace. The 21001 additional syntax signals pass actual B05 schema validation but do not establish operation semantics or business membership. Independent source execution is recorded; document and final commit gates remain incomplete. block_closed:false; production adoption is not claimed. Original deadline elapsed. This package is prepared for review; no final committed-head PASS is asserted.

> **Dux addendum (2026-10-16, supersedes every conflicting statement below, including the 2026-10-15 correction).**
> Authoritative status and evidence: `RESULT.json`. `test_b06_domain_paths.py` runs 18 passed, 0 skipped, offline over committed
> files only (`fixtures/consumer-matrix-metadata.csv`, `fixtures/manifest.json`, `fixtures/receipts/`). Pinned receipts:
> `DUX-REQ-B06-01.out` sha256 `1551433483cb28444c7729aef228a351edc0a644880ec01d8b77546bb20f5cbb` and `DUX-REQ-B06-03.out` sha256 `e30e1c44d8e6ab797e20dc7722eb27854cc1e04a2feab325db2d0a1f3c9d10aa` (earlier text swapped them). The
> 683 B06-prefix rows are 504 `NOT_ENRICHED_THIS_PHASE` + 179 `MATCHED_SOURCE_PATH_ONLY; ACTOR_IDENTITY_UNRESOLVED`; the 527/155/1
> split, the 2,608-row business-label subset of `domain_hint` and a "parent run 3 passed / 8 failed" are withdrawn as
> unsupported. `dux-requests/` and `.agent-receipts/...` paths below are historical, untracked locations; the shipped copies
> live in `fixtures/`. Dispositions marked ACCEPTED for X10 (hash discipline), X12 (offline from committed files) and B06-F4
> (coverage counts) are met only as stated in this addendum. No runtime role, live aggregate or restore measurement is
> claimed; `block_closed` stays `false`.

## Dux correction (2026-10-15) — supersedes the NAGA row below

This addendum takes precedence over any conflicting line further down. The original synthesis text is
retained unchanged as the historical record; it is not rewritten.

- **What changed.** One bounded patch prepared by the parent coordinator in an isolated scratch
  worktree (patch sha256 `94e3c2cf81ba6636aacb100bd7242001bbe6132371a891cc09e2af162341ffb5`) was
  applied to this block's three source files after their pre-image pins matched:
  `b06_domain_paths.py`, `test_b06_domain_paths.py`, `domain-operation-instances.json`. The
  pre/post sha256 pins are recorded in `RESULT.json` under `dux_correction`.
- **NAGA instance `src_b3bccbae2cc91a8c` (D10, row 19 below) is superseded.** The record now cites
  `apps/backend-rag/backend/services/naga/persist.py:24-217` (`save_session`): one
  `conn.transaction()` covers inserts into `naga_sessions`, `naga_sources`, `naga_claims` and
  `naga_claim_evidence`; each call allocates fresh session and claim UUIDs; `ON CONFLICT DO NOTHING`
  only deduplicates source URLs within a session and claim-evidence links; a caught exception logs
  and returns `None`. Row 19's `public.research_os_objects` store, its
  `d10.naga.persist_research_os_bundle` operation and its `naga_persistence.py:88-355` citation are
  NOT supported by the source at the pinned base and must not be relied on. No `research_os_objects`
  bridge, deterministic replay or permanent retention is asserted. Claim-expiry metadata is not an
  erasure proof. The record stays `PARTIAL` with eight explicit unknowns, including
  `ACTOR_IDENTITY_UNRESOLVED`, `REPLAY_IDEMPOTENCY_UNPROVED` and `CLAIM_EXPIRY_NOT_ERASURE_PROOF`;
  its `operation_id` stays `UNASSIGNED_B05`.
- **Unchanged.** The 6029-row census, the 683 B06-prefix rows and all 21 `D04`–`D10` instances are
  preserved; no other instance's operation code changed.
- **Test history (every receipt retained, no case removed).**
  - Dux run at base `8061c88`, before the correction: exit 1, 8 passed / 1 failed
    (`test_consumer_matrix_census_parity_with_dux_receipts`), output sha256
    `60fee2bd40d819e3cf6c7811d207269b135091277ad06be3af10a0ac574924d4`.
  - Parent coordinator run, before the correction: 3 passed / 8 failed (parent receipt).
  - Isolated regression on the pre-patch adapter (`-k "naga_instance_is_grounded or
missing_evidence_file"`): exit 1, 1 failed / 1 passed / 11 deselected, the failure naming the
    missing `naga_persistence.py` path; output sha256
    `8832db2535d5205b9c7e55b6592b077a6a85f3af75c3eefc3ff9cbb89332174c`.
  - After the correction: exit 0, 13 passed; output sha256
    `f5801870ba3c5ceaddd5b679e3bc49fcaf5484957ab861eb9e4a296e654ee7e6`. The Dux re-runs the suite
    at the committed HEAD before the final gate.
- **Not done.** No native probe executed, no live Postgres probed, no credential present. The block
  remains `block_closed: false`; the missing items in `RESULT.json` stand.

- **Campaign**: `universal-db-wave8-20261015`
- **Block**: `B06` — Business-domain paths (`D04`, `D05`, `D06`, `D07`, `D08`, `D09`, `D10`)
- **Seat**: `agy` (`gemini-3.1-pro` high, BLUE prepare-only)
- **Host / Worktree**: `[Mini]` `~/nuzantara/.worktrees/db-udb-b06-domains`
- **Base Commit**: `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`
- **Note**: In `domain-operation-instances.json`, record 18 (`src_737479819e0beeb6`) references `apps/bali-intel-scraper/scripts/post_publish_poller.py:1681-1840` via `x_entry_point`.

---

## 1. Corrected frozen adversarial dispositions

IDs follow actual frozen ADVERSARY-FINDINGS headings, SHA256 29c57f706bcc0dd8e7f492f3ffe5215598798ed173f452f19aa7a086c8faaf54. Earlier incorrect X3-X13 labels are withdrawn. This revision is pending fresh review.

| ID | Actual finding | Current disposition |
| --- | --- | --- |
| X1 | Incompatible store_id grammars | B04 catalog membership joined; unresolved stores retain the frozen sentinel. Consumer binding does not prove a particular call target. |
| X2 | Siblings mint operation IDs | UNASSIGNED_B05 and OPERATION_ID_PENDING_B05 retained; B05 owns assignment. |
| X3 | Inconsistent status vocabularies | Frozen PARTIAL/UNKNOWN statuses retained; no complete status inferred. |
| X4 | B05 exact-key rule conflicts with instances | Actual committed B05 validation covers original and additional submissions; see B05-VALIDATION.json. Shape acceptance does not prove runtime semantics. |
| X5 | Inconsistent source_version/evidence_timestamp | New capture pins current source commit, actual capture UTC and per-file SHA256. Historical examples retain dated pins. |
| X6 | Unobserved root causes stated as facts | No new root cause claimed. Historical restore outcomes remain dated; current cause UNKNOWN. |
| X7 | Application credential bypasses observer identity | No credentials loaded or database connection attempted. Concrete parent-observed access blocker recorded in RESULT.json. |
| X8 | Sibling ownership misassigned | B01 restore; B04 physical stores; B05 operation semantics; B07 runtime/maintenance evidence. |
| X9 | Dependency graph cannot close | Block stays PARTIAL/open; S1 and dependent closure stay gated. |
| X10 | Fabricated IDs and mis-cited lines | Exact C09 consumer membership; B04 store membership; actual source SHA and AST anchors. Unknown IDs are never minted. |
| X11 | Prior admissions do not authorize new exercises | No native query or restore exercise performed. |
| X12 | Public repository output boundary | Compressed projection exports canonical IDs, approved tracked public-code paths, digests and syntax categories; no original matrix, SQL literals, client data or private paths. |
| X13 | Tests require actual command/exit receipts | Worktree and clean-copy commands/exits/digests recorded in INVENTORY-VERIFICATION.json; effective model/effort remain unobserved. |
| B06-F1 | Exemplars are insufficient; static AST cannot fill roles | Full 6029-identity inventory added with seven overlapping candidate sets and explicit untraced rows. Business membership, runtime effects, failure/retry semantics remain UNKNOWN. Criterion PARTIAL. |
| B06-F2 | Proposed 25-key schema incompatible | Actual B05 receipt covers all submissions; unresolved values retained. |
| B06-F3 | Wrong routing and duplicate restore request | Duplicate request withdrawn; ownership follows X8. No new restore admission. |
| B06-F4 | Nonexistent domain column; phone fixture safety | Invalid column proposal removed; actual census fields and public-source rules used. Synthetic non-realistic phone fixtures unchanged. |

## 2. Separated Facts, Inference, and Unknowns

### 2.1 Facts (Verified from Pinned Receipts & Source Files at `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`)

1. **Census Parity (`DUX-REQ-B06-01.out` & `DUX-REQ-B06-03.out`)**:
   - `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv` (`sha256: c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118`) contains `6,029` rows.
   - Across the 7 B06 `domain_hint` buckets (`DUX-REQ-B06-01.out`, `sha256: 1551433483cb28444c7729aef228a351edc0a644880ec01d8b77546bb20f5cbb`), there are `2,608` rows: `knowledge_rag_Corpus=1,152`, `comms_channels=399`, `crm_case_practice=313`, `editorial_news_wr2=291`, `ingestion_drive_ocr=267`, `memory_intelligence_naga=110`, `commerce_billing_payments=76`.
   - Across the B06 path prefixes (`DUX-REQ-B06-03.out`, `sha256: e30e1c44d8e6ab797e20dc7722eb27854cc1e04a2feab325db2d0a1f3c9d10aa`), there are `683` rows: `527` `NOT_ENRICHED_THIS_PHASE`, `155` `PARTIAL`, and `1` `ADAPTED_PARTIAL_VERIFIED` (`src_4c49b82438955ab7`, `apps/backend-rag/backend/app/routers/agentic_rag.py`). Zero rows have `status=EVIDENCED`.
2. **Counterexample `CE-B06-01` (`D04` CRM Phone Deduplication)**:
   - In `apps/backend-rag/backend/services/crm/client_core.py:293-309`, `create_client` normalizes `client.phone` by stripping non-digits and, when `len(norm_phone) >= 7`, runs a pre-insert `SELECT id, full_name FROM clients WHERE deleted_at IS NULL AND REGEXP_REPLACE(COALESCE(phone, ''), '[^0-9]', '', 'g') = $1 LIMIT 1` before executing `INSERT INTO clients` inside `conn.transaction()`. Without a database-level `UNIQUE` index on normalized phone digits or `SERIALIZABLE` locking, concurrent requests with equivalent phone numbers (`+00-000-0000` vs `+00 (000) 0000`) both pass the `SELECT` and insert duplicate active rows.
3. **Counterexample `CE-B06-02` (`D05` Invoice Split Commit Boundary)**:
   - In `apps/backend-rag/backend/services/invoicing/invoice_service.py:35-355`, `trigger_on_sending_invoice` acquires three separate pool connections without an enclosing transaction: (1) allocates and writes `practices.invoice_number`, (2) generates a PDF and uploads it to Google Drive via `_upload_pdf_to_drive`, and (3) inserts into `public.payments` and updates `practices.invoice_file_url`. A crash or Drive/DB failure after step 1 leaves `practices.invoice_number` mutated with no `public.payments` row.
4. **Counterexample `CE-B06-03` (`D05` Unwrapped Reconciliation Writes)**:
   - In `apps/backend-rag/backend/services/accounting/reconcile_service.py:32-119`, `confirm_payment` acquires a connection (`async with self.db_pool.acquire() as conn:`) and runs three sequential autocommit mutations (`UPDATE payments`, `UPDATE practices`, `INSERT INTO audit_logs`) without `async with conn.transaction():`. By contrast, `apps/backend-rag/backend/services/garuda_orders/repository.py:66-160` (`handle_paid_event`) properly wraps `SELECT ... FOR UPDATE`, `UPDATE garuda_orders`, and `INSERT INTO garuda_order_events` inside `async with conn.transaction():`.
5. **Counterexample `CE-B06-04` (`D06` SSE Stream Post-Yield Silent Catch)**:
   - In `apps/backend-rag/backend/app/routers/agentic_rag.py:515-555` and `1480-1525`, `/stream` and `/workspace-stream` yield SSE answer chunks to the client first and then persist the turn to `public.conversations` inside a `try ... except Exception` block that logs and swallows persistence errors after the user has already received the answer.
6. **Counterexample `CE-B06-05` (`D06` WhatsApp Inbound `wamid` Fail-Open)**:
   - In `apps/backend-rag/backend/app/routers/whatsapp_chat.py:341-374`, `_claim_wamid_for_reply` executes `INSERT INTO whatsapp_message_dedup (wamid, phone, created_at) VALUES ($1, $2, NOW()) ON CONFLICT (wamid) DO NOTHING RETURNING wamid`, but its `except Exception` block at lines `369–374` returns `True` (fail-open). If Postgres is unreachable or errors during webhook delivery, inbound `wamid` deduplication is bypassed; if `_enqueue_wa_outbox` (`lines 660–762`) also fails, `_handle_incoming_message` falls back to direct `_send_whatsapp_Interactive`.
7. **Counterexample `CE-B06-06` (`D07` KG Watermark Split from Batch Upsert)**:
   - In `apps/backend-rag/backend/services/knowledge_graph/incremental_builder.py:300-480`, `kg_nodes` and `kg_edges` batch upserts commit prior to the `public.system_settings` watermark update; a failure before the watermark write causes the next builder run to re-scroll the Qdrant window (safe on `kg_nodes`/`kg_edges` via `ON CONFLICT DO UPDATE`, but repeats extraction).
8. **Counterexample `CE-B06-07` (`D08` Intake CRM Delivery Out-of-Tx Window)**:
   - In `apps/backend-rag/backend/services/intake/crm_delivery.py:82-360`, `_resolve_and_push_locked` acquires `pg_try_advisory_xact_lock` inside a transaction to mark `intake_queue` as pushing, releases the transaction to call `push_IntakeItem_to_crm`, and then opens a new transaction to record completion. Conversely, `apps/backend-rag/backend/services/intake/writer.py:660-1135` (`execute_commit`) executes all 5 table writes (`clients`, `documents`, `document_routing_proposal`, `intake_commit_audit`, `intake_queue`) inside one `repeatable_read` transaction.
9. **Counterexample `CE-B06-08` (`D09` Editorial Publish vs Queue & Git Push Split)**:
   - In `apps/backend-rag/backend/app/routers/news.py:415-555`, updating `public.news_items` to `published` and inserting into `public.post_publish_queue` occur in separate autocommit statements. In `apps/bali-intel-scraper/scripts/post_publish_poller.py:1681-1840`, `process_item` pushes the git branch/PR to GitHub before calling `POST /api/intel/post-publish-queue/{id}/done`.
10. **Counterexample `CE-B06-09` (`D10` Volatile In-Memory Fallback in `MemoryServicePostgres`)**:
    - In `apps/backend-rag/backend/services/memory/memory_service_postgres.py:228-315`, when `self.pool` is unavailable or raises an exception during `save_memory`, the service mutates a process-local dictionary (`self.in_memory_storage`) without marking the response non-durable or syncing back to `public.memory_facts` when Postgres recovers.
11. **Restore Drill Status (`scripts/restore_drill_verify.py` & `DUX-TRIAGE-B01-B06.md`)**:
    - Latest restore drill verification covers only 6 tables and records `clients: FAIL` (schema drift) and `conversations: CANNOT-VERIFY`, while `practices`, `payments`, `garuda_orders`, `wa_outbox`, `intake_queue`, `news_items`, `war_room_drafts`, `research_os_objects`, and `memory_facts` are outside the verified restore drill set.

### 2.2 Inferences

1. Runtime role inheritance across the 683 prefix rows is unproved. Source-path matches do not establish a shared principal; B04 evidence is required per actual binding.
2. Standardizing multi-step domain writes onto two patterns already present in `B06`—(a) single-transaction `repeatable_read` + audit row (`intake/writer.py:660-1135`) for in-DB mutations and (b) transactional outbox with `FOR UPDATE SKIP LOCKED` + bounded backoff (`wa_outbox_worker.py:635-860`) for external side effects—eliminates `CE-B06-02`, `CE-B06-03`, `CE-B06-07`, and `CE-B06-08`.

### 2.3 Unknowns (Explicitly Preserved)

1. **Live Runtime Database Role (`role`)**: Unresolved in `consumer-matrix.csv` (`ACTOR_IDENTITY_UNRESOLVED`) across all `683` B06 prefix rows; requires live `B04`/Dux execution receipt.
2. **Live Constraint & Outbox Dead-Letter Counts**: Whether production `public.clients` currently holds duplicate normalized phones (`DUX-REQ-B06-10`), whether `public.payments` / `public.practices` have orphaned invoice states (`DUX-REQ-B06-11`), and how many rows sit in `wa_outbox` / `post_publish_queue` dead-letter/failed states (`DUX-REQ-B06-12`).
3. **End-to-End Restore Verification (`recovery`)**: Unverified for `public.clients` (`FAIL`), `public.conversations` (`CANNOT-VERIFY`), and all B06 tables omitted from `scripts/restore_drill_verify.py` (routed to `B07`).

---

## 3. Historical detailed domain examples (`D04`–`D10`, 21 Operation Instances)

All 21 operation instances are materialized in `research/operations/udb-wave8/B06/domain-operation-instances.json` and generated/validated by `research/operations/udb-wave8/B06/b06_domain_paths.py`:

| #   | Line  | `consumer_id`          | `store_id`                                       | `x_proposed_operation_slug`                     | `status`  | `x_contract_posture` | Counterexample / Invariant                                                                                  |
| :-- | :---- | :--------------------- | :----------------------------------------------- | :---------------------------------------------- | :-------- | :------------------- | :---------------------------------------------------------------------------------------------------------- |
| 1   | `D04` | `src_a7ceb266c9ec6438` | `pg:nuzantara_rag:public.clients`                | `d04.crm.client_core.lifecycle_write`           | `PARTIAL` | `transitional`       | `CE-B06-01`: non-atomic phone digit dedup (`client_core.py:293-309`); `clients: FAIL` in restore drill      |
| 2   | `D04` | `src_36852546767b6d1b` | `pg:nuzantara_rag:public.practices`              | `d04.crm.practices.mutate_and_transition`       | `PARTIAL` | `transitional`       | `CE-B06-02`: fire-and-forget invoice trigger on `status='sending_invoice'` (`crm_practices.py:775-1745`)    |
| 3   | `D04` | `src_3cfe047e6c2ec7f8` | `pg:nuzantara_rag:public.visa_oracle_sessions`   | `d04.visa_oracle.evaluate_and_persist_session`  | `PARTIAL` | `bug`                | Swallowed session persistence error (`evaluate_path.py:137-285`)                                            |
| 4   | `D05` | `src_55053b267fa8ea4a` | `pg:nuzantara_rag:public.payments`               | `d05.invoicing.trigger_on_sending_invoice`      | `PARTIAL` | `bug`                | `CE-B06-02`: 3 separate `pool.acquire()` blocks + Drive upload (`invoice_service.py:35-355`)                |
| 5   | `D05` | `src_fe7d40f6ffa95a8b` | `pg:nuzantara_rag:public.garuda_orders`          | `d05.payments.xendit_checkout_and_webhook`      | `PARTIAL` | `intentional`        | `SELECT ... FOR UPDATE` state guard in `garuda_orders/repository.py:66-160`                                 |
| 6   | `D05` | `src_a3385c4f03c66ace` | `pg:nuzantara_rag:public.garuda_order_events`    | `d05.accounting.reconcile_and_garuda_ledger`    | `PARTIAL` | `bug`                | `CE-B06-03`: unwrapped 3-statement `confirm_payment` (`reconcile_service.py:32-119`)                        |
| 7   | `D06` | `src_4c49b82438955ab7` | `pg:nuzantara_rag:public.conversations`          | `d06.rag.stream_conversation_persistence`       | `PARTIAL` | `bug`                | `CE-B06-04`: post-SSE silent catch (`agentic_rag.py:515-555`); `conversations: CANNOT-VERIFY`               |
| 8   | `D06` | `src_d88734f39509787b` | `pg:nuzantara_rag:public.whatsapp_message_dedup` | `d06.whatsapp.claim_wamid_and_enqueue_outbox`   | `PARTIAL` | `bug`                | `CE-B06-05`: fail-open `return True` on DB exception (`whatsapp_chat.py:341-374`)                           |
| 9   | `D06` | `src_54faf2d6d680ab0d` | `pg:nuzantara_rag:public.wa_outbox`              | `d06.whatsapp.outbox_claim_and_dispatch`        | `PARTIAL` | `intentional`        | `FOR UPDATE SKIP LOCKED` + 6-step backoff (`wa_outbox_worker.py:635-860`)                                   |
| 10  | `D07` | `src_c0f6810d71583357` | `qdrant:kbli_2025_final_hybrid`                  | `d07.kbli.hybrid_notebook_lookup`               | `PARTIAL` | `intentional`        | Read-only PG + Qdrant + KG fan-out (`kbli_notebook.py:60-735`)                                              |
| 11  | `D07` | `src_68fe091af1bf456a` | `pg:nuzantara_rag:public.kg_nodes`               | `d07.kg.incremental_builder_upsert`             | `PARTIAL` | `transitional`       | `CE-B06-06`: `system_settings` watermark updated outside batch tx (`incremental_builder.py:300-480`)        |
| 12  | `D07` | `src_990f416b23c04a69` | `pg:nuzantara_rag:public.kbli_documents`         | `d07.kbli.catalogue_membership_and_kg_staging`  | `PARTIAL` | `intentional`        | Catalogue parity check + `kg_nodes_staging` quarantine (`kbli_catalogue_membership.py:39-125`)              |
| 13  | `D08` | `src_fbda17e1dfb27de7` | `pg:nuzantara_rag:public.intake_commit_audit`    | `d08.intake.atomic_review_commit`               | `PARTIAL` | `intentional`        | Reference 5-table `repeatable_read` atomic tx (`intake/writer.py:660-1135`)                                 |
| 14  | `D08` | `src_56b35953c85895b6` | `pg:nuzantara_rag:public.intake_queue`           | `d08.intake.crm_delivery_resolve_and_push`      | `PARTIAL` | `transitional`       | `CE-B06-07`: out-of-tx `push_IntakeItem_to_crm` after advisory lock release (`crm_delivery.py:82-360`)      |
| 15  | `D08` | `src_d3e3b6647a4d9614` | `s3:tigris_garuda_artifacts`                     | `d08.artifacts.tigris_write_once_put`           | `PARTIAL` | `intentional`        | Content-addressed `IfNoneMatch="*"` + ETag verify (`tigris_store.py:210-355`)                               |
| 16  | `D09` | `src_0634ad7a081c6d3f` | `pg:nuzantara_rag:public.news_items`             | `d09.editorial.news_publish_and_enqueue`        | `PARTIAL` | `transitional`       | `CE-B06-08`: separate autocommit writes to `news_items` and `post_publish_queue` (`news.py:415-555`)        |
| 17  | `D09` | `src_59070a3d3043fb26` | `pg:nuzantara_rag:public.war_room_drafts`        | `d09.wr2.draft_render_and_post_registry`        | `PARTIAL` | `intentional`        | WR2 draft/post persistence + Legge 5 approval gate (`war_room/repository.py:72-355`)                        |
| 18  | `D09` | `src_737479819e0beeb6` | `pg:nuzantara_rag:public.post_publish_queue`     | `d09.editorial.post_publish_poller_sync`        | `PARTIAL` | `transitional`       | `CE-B06-08`: git push before `/done` callback (`post_publish_poller.py:1681-1840`)                          |
| 19  | `D10` | `src_b3bccbae2cc91a8c` | `pg:nuzantara_rag:public.research_os_objects`    | `d10.naga.persist_research_os_bundle`           | `PARTIAL` | `intentional`        | Atomic `conn.transaction()` + SHA-256 `object_id` (`naga_persistence.py:88-355`)                            |
| 20  | `D10` | `src_e2cc71af6590d0d0` | `pg:nuzantara_rag:public.memory_facts`           | `d10.memory.user_memory_facts_upsert`           | `PARTIAL` | `bug`                | `CE-B06-09`: silent fallback to volatile `self.in_memory_storage` (`memory_service_postgres.py:228-315`)    |
| 21  | `D10` | `src_d9f387b7f19b73dd` | `pg:nuzantara_rag:public.collective_memories`    | `d10.memory.collective_and_cell_episodic_store` | `PARTIAL` | `intentional`        | PG `collective_memories` tx + cell-core SQLite WAL `stm`/`episodes` (`collective_memory_service.py:70-265`) |

---

## 4. Sibling Block Routing Table (`B01`, `B03`, `B04`, `B05`, `B07`, `B08`)

| Sibling Block                                    | Routed B06 Finding / Artifact                                                                                                                                                                                           | Action Required by Sibling Block                                                                                                                                                                   |
| :----------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`B01` (Store & Schema Inventory)**             | `CE-B06-01` (`public.clients` missing normalized phone `UNIQUE` index) and `D10` local SQLite WAL stores (`stm`, `episodes` in `packages/cell-core/cell_core/memory_sqlite.py:30-120`)                                  | Verify live DDL constraints on `public.clients`, `public.practices`, `public.payments`, `public.wa_outbox`, `public.post_publish_queue`; register cell-core SQLite WAL stores in store inventory.  |
| **`B03` (Migrations & Schema Drift)**            | `clients: FAIL` schema drift in `scripts/restore_drill_verify.py` (`X3`)                                                                                                                                                | Reconcile migration lineage for `public.clients` so restore drill schema validation passes.                                                                                                        |
| **`B04` (Principals, Roles, Auth & RLS)**        | `ACTOR_IDENTITY_UNRESOLVED` across all `683` B06 prefix rows (`role: "UNKNOWN_RUNTIME_DB_ROLE"`) and SQL tables lacking RLS                                                                                             | Map runtime Postgres role of `app.state.db_pool` and Pro LaunchAgent API key principals; evaluate RLS requirements on `public.clients`, `public.practices`, `public.payments`, `public.documents`. |
| **`B05` (Universal Operation Contract Catalog)** | `research/operations/udb-wave8/B06/domain-operation-instances.json` (`21` instances with `"operation_id": "UNASSIGNED_B05"` and `"x_proposed_operation_slug"`)                                                          | Assign canonical `operation_id` entries in the `B05` catalog for all 21 `x_proposed_operation_slug` values and bind the `683` B06 prefix rows.                                                     |
| **`B07` (Backup, Restore, Retention & DR)**      | `clients: FAIL`, `conversations: CANNOT-VERIFY`, and omitted B06 tables (`practices`, `payments`, `garuda_orders`, `wa_outbox`, `intake_queue`, `news_items`, `war_room_drafts`, `research_os_objects`, `memory_facts`) | Expand `scripts/restore_drill_verify.py` beyond 6 tables and verify RPO/RTO for all critical `D04`–`D10` stores.                                                                                   |
| **`B08` (Observability, Verification & Gates)**  | `CE-B06-02`..`CE-B06-05`, `CE-B06-09` silent failure/fallback paths and `research/operations/udb-wave8/B06/b06_domain_paths.py`                                                                                         | Wire `b06_domain_paths.py` into CI contract verification and add health/alert probes for `wa_outbox` dead letters, `post_publish_queue` failures, and `MemoryServicePostgres` fallback rate.       |

---

## DUX-REQUESTS

To upgrade the 21 B06 operation instances from `status: "PARTIAL"` to `status: "EVIDENCED"` (alongside `B04` role resolution and `B07` restore drill repair), `B06` requests the following 3 bounded, read-only, aggregate-only SQL probes (zero client PII, zero row payloads):

- **`DUX-REQ-B06-10`** (`D04` active normalized phone duplicate count on `public.clients`):
  - **Target**: Fly Postgres `nuzantara-postgres` (`nuzantara_readonly`)
  - **Query**:
    ```sql
    SELECT COUNT(*) AS duplicate_phone_groups
    FROM (
      SELECT REGEXP_REPLACE(COALESCE(phone, ''), '[^0-9]', '', 'g') AS norm_phone
      FROM public.clients
      WHERE deleted_at IS NULL
        AND LENGTH(REGEXP_REPLACE(COALESCE(phone, ''), '[^0-9]', '', 'g')) >= 7
      GROUP BY 1
      HAVING COUNT(*) > 1
    ) t;
    ```
  - **Unblocks**: Quantifies live exposure of `CE-B06-01` before adding a partial unique index in `B01`/`B03`.

- **`DUX-REQ-B06-11`** (`D05` split invoice / payment reconciliation aggregate check):
  - **Target**: Fly Postgres `nuzantara-postgres` (`nuzantara_readonly`)
  - **Query**:
    ```sql
    SELECT
      COUNT(*) FILTER (WHERE p.invoice_number IS NOT NULL AND pay.id IS NULL) AS practices_with_invoice_no_payment_row,
      COUNT(*) FILTER (WHERE pay.status = 'completed' AND p.payment_status IS DISTINCT FROM 'paid') AS completed_payments_with_unpaid_practice
    FROM public.practices p
    LEFT JOIN public.payments pay ON pay.practice_id = p.id;
    ```
  - **Unblocks**: Quantifies live drift from `CE-B06-02` (`invoice_service.py`) and `CE-B06-03` (`reconcile_service.py`).

- **`DUX-REQ-B06-12`** (`D06` / `D08` / `D09` queue & outbox health aggregate check):
  - **Target**: Fly Postgres `nuzantara-postgres` (`nuzantara_readonly`)
  - **Query**:
    ```sql
    SELECT
      (SELECT COUNT(*) FROM public.wa_outbox WHERE status = 'dead_letter') AS wa_outbox_dead_letters,
      (SELECT COUNT(*) FROM public.intake_queue WHERE status = 'pushing') AS intake_stuck_pushing,
      (SELECT COUNT(*) FROM public.post_publish_queue WHERE status = 'failed') AS editorial_post_publish_failed;
    ```
  - **Unblocks**: Quantifies live stuck/dead-letter states across `D06` (`wa_outbox`), `D08` (`intake_queue`), and `D09` (`post_publish_queue`).

## Adversarial review

Scoped Codex document review, parent receipt [`R1-DOCUMENT-REVIEW.json`](R1-DOCUMENT-REVIEW.json) (observed 2026-10-15T16:54:26Z): `PARTIAL_DOCUMENTATION_REQUIRES_RECONCILIATION` for this file's bytes with SHA256 `7c288289468d86ee3d280631c7f9dcdefe212b13b942035bf2b28afea93a9bbd` at base `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`. Bounded excerpts only: not a full document or code review, not implementation approval, not the final BLUE gate. Requested seat Astra 6/xhigh; effective runtime identity not observed. Edits after the reviewed bytes (corrections, addendum) apply its findings and were not re-reviewed.

## 2026-10-16 bounded inventory completion

`b06_inventory.py` captures and consumes `fixtures/source-inventory.json.gz` with pinned provenance. Original C09 bytes are processed locally; only the minimal projection is published. All 6029 canonical IDs are retained: 4231 public-code paths, 1566 rows with static call anchors, 4463 rows without an operation trace, and 21001 syntax call signals.

Seven families are overlapping public-path candidate sets, not business-domain denominators. Generic calls, loops, exception handlers and consumer-level store bindings do not establish persistence, retries, failure behavior or effective targets. Those semantics remain UNKNOWN. The original 21 detailed examples remain separate historical evidence and do not establish full coverage.

Actual committed B05 validation is recorded in B05-VALIDATION.json. Principal, role, recovery and operation IDs remain unresolved. The parent reported at 2026-10-16T07:39Z that a secure owner-only credential file exists but zero canonical nuzantara_readonly DSN candidates are present and both observer DSN variables are unset. This is an access blocker, not a B06 native query.

`block_closed:false` remains binding. Required follow-up: establish business-family membership, inspect untraced and dynamic paths, prove effective call targets/effects/failure/retry behavior, obtain admitted observer access and satisfy dependent recovery evidence. No operational closure is claimed.
