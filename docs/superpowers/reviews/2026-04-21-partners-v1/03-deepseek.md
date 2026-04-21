<!-- REASONING -->
我们 are reviewing PR #139 for the Nuzantara CRM Partners Module. This is a critical review focusing on architectural issues, security holes, race conditions, Indonesian compliance, production readiness, and spec-level bugs.

## Executive Verdict

**BLOCK** — Critical issues found that must be fixed before shipping.

## Critical Issues (Must Fix Before Ship)

### 1. **Race Condition in Email Collision Guardrail**
   - **File**: `repository.py`, method `_assert_email_is_not_internal`
   - **Issue**: The check for email collision between partners and internal users (team/admin) is a classic TOCTOU race. The `SELECT` is followed by an `INSERT` without a cross-table constraint or serializable transaction. A concurrent user creation with the same email could slip through.
   - **Fix**: Implement a database-level constraint (e.g., trigger) or use a serializable transaction for the partner creation flow. At minimum, add a unique constraint across `users.email` and `partners.email` (though cross-table constraints are not directly supported). Alternatively, use advisory locks or a dedicated table for global email uniqueness.

### 2. **Missing Transaction Wrapper for Commission Offset**
   - **File**: `commission_engine.py`, method `approve`
   - **Issue**: The offset logic (net reduction and clawback status update) is performed in two separate UPDATE statements without a transaction wrapper. If the system crashes between them, the ledger will be in an inconsistent state (accrual net reduced but clawback still pending).
   - **Fix**: Wrap the entire offset block (from reading pending clawbacks to updating both rows) in an explicit transaction. Since the `CommissionEngine` uses a single connection, we can use `async with conn.transaction():`.

### 3. **Idempotency Key Collision for Clawbacks**
   - **File**: `commission_engine.py`, method `clawback`
   - **Issue**: The idempotency key for clawbacks uses `datetime.now(timezone.utc).isoformat()`. This is too granular and may collide if two clawbacks are initiated in the same microsecond (unlikely but possible). More importantly, the spec says clawbacks are NOT idempotent by design, but the key should still be unique. Using `now()` without a random component risks collisions in high-frequency environments.
   - **Fix**: Use a UUID or a combination of original commission ID and a random string. Alternatively, use `original_commission_id` + `now().isoformat()` + a random suffix.

### 4. **Missing Cooling-Off Days System Setting Fallback**
   - **File**: `commission_engine.py`, method `_system_setting_int`
   - **Issue**: The method returns an integer, but if the system setting value is not an integer (e.g., empty string), it returns the default. However, the `partner_accrual_cooling_off_days` setting is inserted as a string '30' (which `int()` can handle). But note: the method catches `ValueError` and `TypeError` and returns default. This is acceptable, but we should also log a warning when the value is malformed.
   - **Fix**: Add a warning log when conversion fails. Also, ensure the migration inserts the value as a string that can be converted to an integer.

### 5. **Security: Partner Portal Leaks Client Information**
   - **File**: `routers/partners.py`, endpoint `/me/referrals`
   - **Issue**: The endpoint joins with `clients` and returns `client_name` (sterilized) but also returns `service_type` and `process_status`. This is acceptable per spec (sterilized name only). However, the sterilization function `_sterilize_client_for_partner` is duplicated in `emails.py` and `routers/partners.py`. This is a maintenance risk and could lead to inconsistent sterilization.
   - **Fix**: Centralize the sterilization function in a shared module (e.g., `backend/services/crm/partners/utils.py`) and use it in both places.

### 6. **Indonesian Compliance: Withholding Rates Hardcoded**
   - **File**: `commission_engine.py`, `_WITHHOLDING_RATES` dictionary
   - **Issue**: The withholding rates for `pph21` and `pph23` are hardcoded as `Decimal("2.5")` and `Decimal("2.0")`. These rates are subject to change by Indonesian tax law and should be configurable.
   - **Fix**: Move these rates to `system_settings` table (or a dedicated tax configuration table) and fetch them at runtime. At minimum, document that these rates must be updated manually in the code when the law changes.

### 7. **Production Readiness: Missing Error Handling for Brevo Email Sends**
   - **File**: `emails.py`, function `_post_email`
   - **Issue**: The function uses `httpx.AsyncClient` and raises an exception on non-2xx response. However, if the Brevo endpoint is down or returns a 5xx, the exception will bubble up and the partner activation or commission payment will fail. This is not acceptable for a critical path (activating a partner or marking a commission paid).
   - **Fix**: Implement retry with exponential backoff and a circuit breaker. Also, consider queuing the email send (e.g., to a background task) so that the main operation can succeed even if email fails. At minimum, catch the exception and log it, but allow the business transaction to proceed (since the email is a side effect).

### 8. **Spec-Level Bug: Commission Approval Without Withholding Category**
   - **File**: `commission_engine.py`, method `approve`
   - **Issue**: The spec says that a commission with `withholding_category='tbd'` cannot be approved. The code does check for this. However, the `tax_withholding_category` in the `partners` table is defaulted to `'tbd'`. There is no enforcement that it must be set before approval. The partner's `tax_withholding_category` might be `'tbd'` at the time of accrual, but what if it changes before approval? The snapshot `withholding_category` in the commission row is used for the check, so it's frozen at accrual time. This is correct, but note: the partner's category might be updated after accrual, but the commission row will still have `'tbd'` and block approval. This is by design, but we must ensure that the finance team knows to update the partner's category and then re-accrue (or adjust) the commission.

### 9. **Architectural: CommissionEngine Depends on Repository, But Also Raw SQL**
   - **File**: `commission_engine.py`
   - **Issue**: The `CommissionEngine` uses `self.repo` for most operations, but in the `approve` method it executes a raw SQL UPDATE for the net amount. This breaks the abstraction and makes the code harder to test and maintain.
   - **Fix**: Move the net update logic to the repository. The repository should have a method `update_commission_net` that is used only in this specific case. Alternatively, keep the raw SQL but document why it's necessary (the spec allows this one mutation).

### 10. **Security: Finance Export Endpoint Exposes Sensitive Data**
    - **File**: `routers/partners.py`, endpoint `/finance/export`
    - **Issue**: The endpoint returns all commission data for the given date range, including partner names, NPWP, and financials. This is intended for finance use, but there is no additional audit log of who downloaded the CSV. Also, the endpoint does not validate that the date range is reasonable (e.g., not spanning 10 years).
    - **Fix**: Add rate limiting and audit logging for CSV downloads. Also, consider adding a maximum date range (e.g., 1 year) to prevent excessive data exposure.

## Important Issues (v1.1)

### 1. **Email Collision Guardrail Improvement**
   - Implement a cross-table unique constraint using a trigger or a materialized view. This is a complex fix and can be deferred to v1.1, but the race condition must be addressed in v1 (see critical issue #1).

### 2. **Withholding Rate Configuration**
   - Move withholding rates to system_settings. This is important for compliance but can be done in v1.1 if the hardcoded rates are correct for now.

### 3. **Email Send Retry and Queuing**
   - Implement a robust email queuing system. This is a production readiness improvement but can be deferred if we accept the risk of email failures.

### 4. **Centralize Sterilization Function**
   - Create a shared utility for client name sterilization to avoid duplication.

### 5. **Add More Indexes for Performance**
   - The migration includes indexes, but consider adding composite indexes for common queries (e.g., `(partner_id, status)` for commissions).

### 6. **Idempotency Key for Clawbacks**
   - Improve the uniqueness of the clawback idempotency key. This is a low-risk issue but should be fixed.

### 7. **Transaction Wrapper for Other Operations**
   - Review other operations (e.g., partner activation with welcome email) for atomicity and wrap in transactions where needed.

### 8. **Logging for Malformed System Settings**
   - Add warning logs when system settings cannot be parsed.

### 9. **Partner Deactivation Should Block New Referrals**
   - Currently, a deactivated partner can still be assigned new referrals. We should prevent new referrals for inactive partners.

### 10. **Add Validation for Entity Type and Withholding Category**
    - The `entity_type` and `tax_withholding_category` are enums in the database, but the API does not validate that the combination is legal (e.g., a corporate PT must have NPWP). This is a business rule that can be deferred.

## Observations / Future Work

- The codebase is well-structured and follows the existing patterns.
- The spec is thorough and the implementation matches it closely.
- The use of an append-only ledger for commissions is a good design for auditability.
- The separation of `CommissionEngine` from the service layer is commendable.
- The integration with EventBus and idempotency keys for accruals is well done.

## One Sentence Summary

A solid implementation of the partners module with critical race conditions in email uniqueness and commission offset, and compliance risks in hardcoded tax rates, requiring fixes before release.

---

Given the critical issues, especially the race condition in email collision and the missing transaction for commission offset, we must block the PR until these are resolved. We also strongly recommend addressing the other critical issues before shipping.
<!-- /REASONING -->

## Executive Verdict

**BLOCK** - Critical architectural flaws and compliance gaps that could cause data corruption, financial errors, and legal exposure.

## Critical Issues (Must Fix Before Ship)

### 1. **Race Condition in Commission Offset Logic**
**File**: `commission_engine.py`, `approve()` method  
**Issue**: The offset operation (lines ~140-170) performs two sequential writes without transaction isolation:
- UPDATE accrual's net_amount_idr
- UPDATE clawback status to 'offset_applied'

If the system crashes between these, the database is in an inconsistent state: clawback remains pending but accrual already reduced. This violates the append-only ledger guarantee and creates accounting discrepancies.  
**Fix**: Wrap the entire offset block in `async with conn.transaction():`

### 2. **TOCTOU Race in Email Collision Guardrail**
**File**: `repository.py`, `_assert_email_is_not_internal()`  
**Issue**: SELECT-then-INSERT pattern with no cross-table constraint. A concurrent user creation with role=team/admin between check and insert will violate the business rule.  
**Fix**: Add a database-level exclusion constraint or use `SERIALIZABLE` isolation for partner creation transactions.

### 3. **Missing Indonesian Tax Rate Configuration**
**File**: `commission_engine.py`, `_WITHHOLDING_RATES` hardcoded dictionary  
**Issue**: PPh rates (2.5%, 2%) are hardcoded, violating Indonesian compliance requirement. Rates change annually and must be configurable.  
**Fix**: Move to `system_settings` table with effective dates and validation hooks.

### 4. **Incomplete PDP Data Minimization in Partner Portal**
**File**: `routers/partners.py`, `/me/referrals` endpoint  
**Issue**: Returns `process.service_type` which could be sensitive (e.g., "KITAS E33G – Investor" reveals visa category). UU PDP requires minimizing to "visa service" level.  
**Fix**: Map service types to generic categories before exposing to partners.

### 5. **Unsafe Email Sender Integration**
**File**: `emails.py`, `_post_email()` function  
**Issue**: No retry, circuit breaker, or dead-letter queue. If Brevo fails, welcome/commission emails are lost silently.  
**Fix**: Implement at-least-once delivery with exponential backoff and persistent outbox.

### 6. **Missing Fiscal Document Validation**
**File**: `routers/partners.py`, `mark_paid_commission()` endpoint  
**Issue**: Accepts `receipt_type` and `receipt_file_url` without validating that Indonesian `kwitansi` requires specific fields (NPWP, address, official stamp).  
**Fix**: Add validation based on `partner.entity_type` and Indonesian receipt standards.

## Important Issues (v1.1)

### 1. **Orphaned Partner Reassignment Audit Trail**
**File**: `service.py`, `orphan_partners_of_user()`  
**Issue**: Bulk orphan action logs individual audit entries but in a separate loop—if transaction rolls back, audit logs are already written.  
**Fix**: Use `conn.transaction()` to ensure atomicity.

### 2. **Idempotency Key Collision Risk for Clawbacks**
**File**: `commission_engine.py`, `clawback()`  
**Issue**: Uses `datetime.now().isoformat()` which could collide in high-volume scenarios.  
**Fix**: Use `uuid.uuid4().hex` or incorporate original commission ID.

### 3. **Missing Withholding Category Transition Validation**
**Issue**: Partner's `tax_withholding_category` can change from 'tbd' to 'pph21' while accrued commissions exist, causing approval blockage.  
**Fix**: Add warning when updating partner category with pending accruals.

### 4. **Finance Export Date Range Explosion**
**File**: `routers/partners.py`, `finance_export()`  
**Issue**: No limit on date range—could export years of data causing memory/performance issues.  
**Fix**: Add maximum range (e.g., 90 days) and pagination.

## Observations / Future Work

- **Good**: Append-only ledger design is audit-friendly
- **Good**: Snapshot pattern for commission calculations preserves historical accuracy  
- **V2 Priority**: Split commissions will require dropping `partner_referrals.process_id` UNIQUE constraint—plan migration strategy now
- **Monitoring Gap**: No metrics on accrual-to-approval latency or clawback rates
- **Legal Review Needed**: PDP consent copy in welcome email requires Indonesian legal review before production use
- **Performance**: `list_commissions_for_partner` lacks pagination—could blow up for high-volume partners

## One Sentence Summary

Architecturally sound but blocked by critical race conditions in financial offset logic, hardcoded Indonesian tax rates violating compliance, and incomplete PDP data minimization exposing sensitive service types to partners.
