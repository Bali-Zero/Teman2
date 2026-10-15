# DEFINITIVE-SYNTHESIS — Wave 8 Block `B06` (Business-Domain Paths `D04`–`D10`)

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

## 1. Consolidated Adversarial & Triage Dispositions (`X1`–`X13` & `B06-F1`–`B06-F4`)

Every cross-cutting finding (`X1`–`X13`) and block-specific finding (`B06-F1`–`B06-F4`) from `.agent-receipts/udb-wave8-dux/ADVERSARY-FINDINGS.md` (`sha256: 29c57f706bcc0dd8e7f492f3ffe5215598798ed173f452f19aa7a086c8faaf54`), `.agent-receipts/udb-wave8-dux/DUX-CONSOLIDATION.md` (`sha256: c39218718f496b643b550abf98ca40bd2755e74d3954caed953005eb5b906e14`), and `.agent-receipts/udb-wave8-dux/DUX-TRIAGE-B01-B06.md` (`sha256: 806837176838f33b3cf7fc284316efe6d2d1a214b363d90aa3adbbf7acbfcc7c`) is disposed below:

| Finding ID | Summary of Challenge | Disposition | Concrete Change in Synthesis & Deliverables |
| :--- | :--- | :--- | :--- |
| **`X1` / `B06-F1`** | Cross-block schema fragmentation: `B06` proposed custom 14-field JSON (`operation_slug`, `domain_line`, `entry_surface`, `store_targets`, etc.) incompatible with `B05` and `CONTRACT-CONVENTIONS.md`. | **ACCEPTED** | Replaced custom schema in `b06_domain_paths.py` and `domain-operation-instances.json` with the exact 19 canonical keys in order (`consumer_id`, `operation_id`, `store_id`, `source_version`, `evidence_timestamp`, `evidence_sha256`, `status`, `unknowns`, `principal`, `role`, `tenant`, `authorization`, `transaction`, `effects`, `retries`, `idempotency`, `failure`, `retention`, `recovery`) plus `x_`-prefixed extension keys only (`x_domain_line`, `x_entry_point`, `x_source_line_span`, `x_evidence_ref`, `x_counterexample_id`, `x_contract_posture`, `x_proposed_operation_slug`). |
| **`X2`** | Premature `EVIDENCED` status despite `ACTOR_IDENTITY_UNRESOLVED`, `NOT_ENRICHED_THIS_PHASE`, or unverified recovery. | **ACCEPTED** | All 21 operation instances in `domain-operation-instances.json` are capped at `status: "PARTIAL"` with explicit `unknowns` arrays; `validate_operation_instance()` rejects `EVIDENCED` whenever `role` contains `UNKNOWN`, `recovery` contains `UNVERIFIED`, or `unknowns` is non-empty. |
| **`X3`** | Unverified live counts and RPO/RTO assumptions (`clients: FAIL` and `conversations: CANNOT-VERIFY` in `scripts/restore_drill_verify.py`). | **ACCEPTED** | Recovery fields for `public.clients` (`src_a7ceb266c9ec6438`) and `public.conversations` (`src_4c49b82438955ab7`) are explicitly marked `UNVERIFIED` citing `scripts/restore_drill_verify.py` (`clients: FAIL`, `conversations: CANNOT-VERIFY`) and routed to `B07`. |
| **`X4`** | Over-scoped execution proposals across blocks. | **ACCEPTED** | Kept deliverables strictly within `research/operations/udb-wave8/B06/` (`b06_domain_paths.py`, `domain-operation-instances.json`, `test_b06_domain_paths.py`, `DEFINITIVE-SYNTHESIS.md`, `RESULT.json`, `PR_BODY.md`), stdlib + `pytest` only. |
| **`X5`** | Unbounded/redundant Dux request queues across seats. | **ACCEPTED** | Consolidated `B06` runtime verification requests into 3 bounded read-only aggregate probes (`DUX-REQ-B06-10`..`12`), avoiding duplicate `pg_roles` / `pg_stat_activity` scans already owned by `B01`/`B04`. |
| **`X6`** | Contract posture ambiguity (`bug` vs `intentional` vs `transitional`). | **ACCEPTED** | Added `x_contract_posture` (`"intentional"`, `"transitional"`, or `"bug"`) on all 21 operation instances and documented each posture in §3. |
| **`X7`** | Store ID naming drift across blocks. | **ACCEPTED** | All `store_id` values conform to `CONTRACT-CONVENTIONS.md` §1.2 (`pg:nuzantara_rag:public.<table>`, `qdrant:kbli_2025_final_hybrid`, `s3:tigris_garuda_artifacts`), enforced by regex `STORE_ID_GRAMMAR_RE`. |
| **`X8`** | Consumer ID linkage drift (`consumer_id` must match `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv`). | **ACCEPTED** | Every `consumer_id` in `domain-operation-instances.json` is an exact `src_<16hex>` key verified against `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv` (`sha256: c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118`). |
| **`X9`** | Operation ID assignment discipline (`B06` must not invent `operation_id` values outside `B05`). | **ACCEPTED** | All 21 records set `"operation_id": "UNASSIGNED_B05"` and carry the candidate slug in `"x_proposed_operation_slug"`. |
| **`X10`** | Evidence hash discipline (`evidence_sha256` must be a real 64-char hex SHA-256 of a pinned receipt/file). | **ACCEPTED** | Every record carries a 64-char lowercase hex `evidence_sha256` matching either the router's pinned content SHA-256 in `consumer-matrix.csv` or `DUX-REQ-B06-03.out` (`1551433483cb28444c7729aef228a351edc0a644880ec01d8b77546bb20f5cbb`). |
| **`X11`** | PII boundary in tests and examples (`CONTRACT-CONVENTIONS.md` §4). | **ACCEPTED** | All tests and code use only synthetic fixtures `+00-000-0000` and `user@example.invalid`; zero client rows or PII appear anywhere. |
| **`X12`** | Test hermeticity (no live DB, no network, no external packages beyond stdlib + `pytest`). | **ACCEPTED** | `b06_domain_paths.py` and `test_b06_domain_paths.py` import only Python stdlib + `pytest` and run offline against committed repo files. |
| **`X13`** | Honest closure posture (`block_closed: false` while runtime proofs remain pending). | **ACCEPTED** | `RESULT.json` sets `"status": "PARTIAL"` and `"block_closed": false`. |
| **`B06-F2`** | Citation drift in `D04`: `ANALYSIS.md` cited `client_core.py:293-305` as email uniqueness instead of normalized phone uniqueness (`REGEXP_REPLACE(phone, '[^0-9]', '', 'g')` with `length >= 7`), and cited `crm_practices.py:720-910` instead of `775-1045` (`create_practice`) and `1590-1745` (`patch_practice`). | **ACCEPTED** | Corrected in §2/§3, `b06_domain_paths.py`, `domain-operation-instances.json`, and `test_b06_domain_paths.py`: `client_core.py:293-309` is the non-atomic normalized phone duplicate gate (`>= 7` digits), and `crm_practices.py:775-1045,1590-1745` are the exact `create_practice` / `patch_practice` spans. |
| **`B06-F3`** | `D06` WhatsApp fail-open dedup characterization: `_claim_wamid_for_reply` (`whatsapp_chat.py:341-374`) fails open (`return True` on DB exception at lines `369–374`), which bypasses inbound `wamid` dedup; outbound `_enqueue_wa_outbox` (`660–762`) is a separate step that falls back to direct `_send_whatsapp_Interactive` if outbox insert fails. | **ACCEPTED** | Separated inbound `wamid` fail-open (`CE-B06-05` in `whatsapp_chat.py:341-374`) from outbound `wa_outbox` enqueue (`660–762`) and worker dispatch (`wa_outbox_worker.py:635-860`) in §3 and `domain-operation-instances.json`. |
| **`B06-F4`** | Coverage gap between 21 deep-traced exemplars and the `683` B06-prefix rows / `2,608` B06 `domain_hint` rows in `consumer-matrix.csv`. | **ACCEPTED** | `b06_domain_paths.py` (`load_consumer_matrix_index` + `verify_all`) scans all `6,029` rows of `consumer-matrix.csv`, verifying all `2,608` B06 `domain_hint` rows (`DUX-REQ-B06-01.out`) and all `683` B06-prefix rows (`DUX-REQ-B06-03.out`: `527` `NOT_ENRICHED_THIS_PHASE`, `155` `PARTIAL`, `1` `ADAPTED_PARTIAL_VERIFIED`) alongside the 21 deep operation instances. |

---

## 2. Separated Facts, Inference, and Unknowns

### 2.1 Facts (Verified from Pinned Receipts & Source Files at `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`)
1. **Census Parity (`DUX-REQ-B06-01.out` & `DUX-REQ-B06-03.out`)**:
   - `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv` (`sha256: c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118`) contains `6,029` rows.
   - Across the 7 B06 `domain_hint` buckets (`DUX-REQ-B06-01.out`, `sha256: e30e1c44d8e6ab797e20dc7722eb27854cc1e04a2feab325db2d0a1f3c9d10aa`), there are `2,608` rows: `knowledge_rag_Corpus=1,152`, `comms_channels=399`, `crm_case_practice=313`, `editorial_news_wr2=291`, `ingestion_drive_ocr=267`, `memory_intelligence_naga=110`, `commerce_billing_payments=76`.
   - Across the B06 path prefixes (`DUX-REQ-B06-03.out`, `sha256: 1551433483cb28444c7729aef228a351edc0a644880ec01d8b77546bb20f5cbb`), there are `683` rows: `527` `NOT_ENRICHED_THIS_PHASE`, `155` `PARTIAL`, and `1` `ADAPTED_PARTIAL_VERIFIED` (`src_4c49b82438955ab7`, `apps/backend-rag/backend/app/routers/agentic_rag.py`). Zero rows have `status=EVIDENCED`.
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
1. Because all `155` `PARTIAL` rows and `1` `ADAPTED_PARTIAL_VERIFIED` row in the B06 path prefix slice of `consumer-matrix.csv` carry `ACTOR_IDENTITY_UNRESOLVED` and share `app.state.db_pool` (`apps/backend-rag/backend/app/setup/database.py`), resolving the runtime Postgres role on `app.state.db_pool` in `B04` will simultaneously resolve `role` for the backend FastAPI portion of `B06`.
2. Standardizing multi-step domain writes onto two patterns already present in `B06`—(a) single-transaction `repeatable_read` + audit row (`intake/writer.py:660-1135`) for in-DB mutations and (b) transactional outbox with `FOR UPDATE SKIP LOCKED` + bounded backoff (`wa_outbox_worker.py:635-860`) for external side effects—eliminates `CE-B06-02`, `CE-B06-03`, `CE-B06-07`, and `CE-B06-08`.

### 2.3 Unknowns (Explicitly Preserved)
1. **Live Runtime Database Role (`role`)**: Unresolved in `consumer-matrix.csv` (`ACTOR_IDENTITY_UNRESOLVED`) across all `683` B06 prefix rows; requires live `B04`/Dux execution receipt.
2. **Live Constraint & Outbox Dead-Letter Counts**: Whether production `public.clients` currently holds duplicate normalized phones (`DUX-REQ-B06-10`), whether `public.payments` / `public.practices` have orphaned invoice states (`DUX-REQ-B06-11`), and how many rows sit in `wa_outbox` / `post_publish_queue` dead-letter/failed states (`DUX-REQ-B06-12`).
3. **End-to-End Restore Verification (`recovery`)**: Unverified for `public.clients` (`FAIL`), `public.conversations` (`CANNOT-VERIFY`), and all B06 tables omitted from `scripts/restore_drill_verify.py` (routed to `B07`).

---

## 3. Definitive Domain Path Inventory (`D04`–`D10`, 21 Operation Instances)

All 21 operation instances are materialized in `research/operations/udb-wave8/B06/domain-operation-instances.json` and generated/validated by `research/operations/udb-wave8/B06/b06_domain_paths.py`:

| # | Line | `consumer_id` | `store_id` | `x_proposed_operation_slug` | `status` | `x_contract_posture` | Counterexample / Invariant |
| :- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `D04` | `src_a7ceb266c9ec6438` | `pg:nuzantara_rag:public.clients` | `d04.crm.client_core.lifecycle_write` | `PARTIAL` | `transitional` | `CE-B06-01`: non-atomic phone digit dedup (`client_core.py:293-309`); `clients: FAIL` in restore drill |
| 2 | `D04` | `src_36852546767b6d1b` | `pg:nuzantara_rag:public.practices` | `d04.crm.practices.mutate_and_transition` | `PARTIAL` | `transitional` | `CE-B06-02`: fire-and-forget invoice trigger on `status='sending_invoice'` (`crm_practices.py:775-1745`) |
| 3 | `D04` | `src_3cfe047e6c2ec7f8` | `pg:nuzantara_rag:public.visa_oracle_sessions` | `d04.visa_oracle.evaluate_and_persist_session` | `PARTIAL` | `bug` | Swallowed session persistence error (`evaluate_path.py:137-285`) |
| 4 | `D05` | `src_55053b267fa8ea4a` | `pg:nuzantara_rag:public.payments` | `d05.invoicing.trigger_on_sending_invoice` | `PARTIAL` | `bug` | `CE-B06-02`: 3 separate `pool.acquire()` blocks + Drive upload (`invoice_service.py:35-355`) |
| 5 | `D05` | `src_fe7d40f6ffa95a8b` | `pg:nuzantara_rag:public.garuda_orders` | `d05.payments.xendit_checkout_and_webhook` | `PARTIAL` | `intentional` | `SELECT ... FOR UPDATE` state guard in `garuda_orders/repository.py:66-160` |
| 6 | `D05` | `src_a3385c4f03c66ace` | `pg:nuzantara_rag:public.garuda_order_events` | `d05.accounting.reconcile_and_garuda_ledger` | `PARTIAL` | `bug` | `CE-B06-03`: unwrapped 3-statement `confirm_payment` (`reconcile_service.py:32-119`) |
| 7 | `D06` | `src_4c49b82438955ab7` | `pg:nuzantara_rag:public.conversations` | `d06.rag.stream_conversation_persistence` | `PARTIAL` | `bug` | `CE-B06-04`: post-SSE silent catch (`agentic_rag.py:515-555`); `conversations: CANNOT-VERIFY` |
| 8 | `D06` | `src_d88734f39509787b` | `pg:nuzantara_rag:public.whatsapp_message_dedup` | `d06.whatsapp.claim_wamid_and_enqueue_outbox` | `PARTIAL` | `bug` | `CE-B06-05`: fail-open `return True` on DB exception (`whatsapp_chat.py:341-374`) |
| 9 | `D06` | `src_54faf2d6d680ab0d` | `pg:nuzantara_rag:public.wa_outbox` | `d06.whatsapp.outbox_claim_and_dispatch` | `PARTIAL` | `intentional` | `FOR UPDATE SKIP LOCKED` + 6-step backoff (`wa_outbox_worker.py:635-860`) |
| 10 | `D07` | `src_c0f6810d71583357` | `qdrant:kbli_2025_final_hybrid` | `d07.kbli.hybrid_notebook_lookup` | `PARTIAL` | `intentional` | Read-only PG + Qdrant + KG fan-out (`kbli_notebook.py:60-735`) |
| 11 | `D07` | `src_68fe091af1bf456a` | `pg:nuzantara_rag:public.kg_nodes` | `d07.kg.incremental_builder_upsert` | `PARTIAL` | `transitional` | `CE-B06-06`: `system_settings` watermark updated outside batch tx (`incremental_builder.py:300-480`) |
| 12 | `D07` | `src_990f416b23c04a69` | `pg:nuzantara_rag:public.kbli_documents` | `d07.kbli.catalogue_membership_and_kg_staging` | `PARTIAL` | `intentional` | Catalogue parity check + `kg_nodes_staging` quarantine (`kbli_catalogue_membership.py:39-125`) |
| 13 | `D08` | `src_fbda17e1dfb27de7` | `pg:nuzantara_rag:public.intake_commit_audit` | `d08.intake.atomic_review_commit` | `PARTIAL` | `intentional` | Reference 5-table `repeatable_read` atomic tx (`intake/writer.py:660-1135`) |
| 14 | `D08` | `src_56b35953c85895b6` | `pg:nuzantara_rag:public.intake_queue` | `d08.intake.crm_delivery_resolve_and_push` | `PARTIAL` | `transitional` | `CE-B06-07`: out-of-tx `push_IntakeItem_to_crm` after advisory lock release (`crm_delivery.py:82-360`) |
| 15 | `D08` | `src_d3e3b6647a4d9614` | `s3:tigris_garuda_artifacts` | `d08.artifacts.tigris_write_once_put` | `PARTIAL` | `intentional` | Content-addressed `IfNoneMatch="*"` + ETag verify (`tigris_store.py:210-355`) |
| 16 | `D09` | `src_0634ad7a081c6d3f` | `pg:nuzantara_rag:public.news_items` | `d09.editorial.news_publish_and_enqueue` | `PARTIAL` | `transitional` | `CE-B06-08`: separate autocommit writes to `news_items` and `post_publish_queue` (`news.py:415-555`) |
| 17 | `D09` | `src_59070a3d3043fb26` | `pg:nuzantara_rag:public.war_room_drafts` | `d09.wr2.draft_render_and_post_registry` | `PARTIAL` | `intentional` | WR2 draft/post persistence + Legge 5 approval gate (`war_room/repository.py:72-355`) |
| 18 | `D09` | `src_737479819e0beeb6` | `pg:nuzantara_rag:public.post_publish_queue` | `d09.editorial.post_publish_poller_sync` | `PARTIAL` | `transitional` | `CE-B06-08`: git push before `/done` callback (`post_publish_poller.py:1681-1840`) |
| 19 | `D10` | `src_b3bccbae2cc91a8c` | `pg:nuzantara_rag:public.research_os_objects` | `d10.naga.persist_research_os_bundle` | `PARTIAL` | `intentional` | Atomic `conn.transaction()` + SHA-256 `object_id` (`naga_persistence.py:88-355`) |
| 20 | `D10` | `src_e2cc71af6590d0d0` | `pg:nuzantara_rag:public.memory_facts` | `d10.memory.user_memory_facts_upsert` | `PARTIAL` | `bug` | `CE-B06-09`: silent fallback to volatile `self.in_memory_storage` (`memory_service_postgres.py:228-315`) |
| 21 | `D10` | `src_d9f387b7f19b73dd` | `pg:nuzantara_rag:public.collective_memories` | `d10.memory.collective_and_cell_episodic_store` | `PARTIAL` | `intentional` | PG `collective_memories` tx + cell-core SQLite WAL `stm`/`episodes` (`collective_memory_service.py:70-265`) |

---

## 4. Sibling Block Routing Table (`B01`, `B03`, `B04`, `B05`, `B07`, `B08`)

| Sibling Block | Routed B06 Finding / Artifact | Action Required by Sibling Block |
| :--- | :--- | :--- |
| **`B01` (Store & Schema Inventory)** | `CE-B06-01` (`public.clients` missing normalized phone `UNIQUE` index) and `D10` local SQLite WAL stores (`stm`, `episodes` in `packages/cell-core/cell_core/memory_sqlite.py:30-120`) | Verify live DDL constraints on `public.clients`, `public.practices`, `public.payments`, `public.wa_outbox`, `public.post_publish_queue`; register cell-core SQLite WAL stores in store inventory. |
| **`B03` (Migrations & Schema Drift)** | `clients: FAIL` schema drift in `scripts/restore_drill_verify.py` (`X3`) | Reconcile migration lineage for `public.clients` so restore drill schema validation passes. |
| **`B04` (Principals, Roles, Auth & RLS)** | `ACTOR_IDENTITY_UNRESOLVED` across all `683` B06 prefix rows (`role: "UNKNOWN_RUNTIME_DB_ROLE"`) and SQL tables lacking RLS | Map runtime Postgres role of `app.state.db_pool` and Pro LaunchAgent API key principals; evaluate RLS requirements on `public.clients`, `public.practices`, `public.payments`, `public.documents`. |
| **`B05` (Universal Operation Contract Catalog)** | `research/operations/udb-wave8/B06/domain-operation-instances.json` (`21` instances with `"operation_id": "UNASSIGNED_B05"` and `"x_proposed_operation_slug"`) | Assign canonical `operation_id` entries in the `B05` catalog for all 21 `x_proposed_operation_slug` values and bind the `683` B06 prefix rows. |
| **`B07` (Backup, Restore, Retention & DR)** | `clients: FAIL`, `conversations: CANNOT-VERIFY`, and omitted B06 tables (`practices`, `payments`, `garuda_orders`, `wa_outbox`, `intake_queue`, `news_items`, `war_room_drafts`, `research_os_objects`, `memory_facts`) | Expand `scripts/restore_drill_verify.py` beyond 6 tables and verify RPO/RTO for all critical `D04`–`D10` stores. |
| **`B08` (Observability, Verification & Gates)** | `CE-B06-02`..`CE-B06-05`, `CE-B06-09` silent failure/fallback paths and `research/operations/udb-wave8/B06/b06_domain_paths.py` | Wire `b06_domain_paths.py` into CI contract verification and add health/alert probes for `wa_outbox` dead letters, `post_publish_queue` failures, and `MemoryServicePostgres` fallback rate. |

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
