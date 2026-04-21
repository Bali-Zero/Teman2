Truncating MCP tool name "mcp_google-maps-platform-code-assist_retrieve-google-maps-platform-docs" to fit within the 64 character limit. This tool may require user approval.
Discarding invalid hook definition for SessionStart from project: {
  type: 'command',
  command: '~/.gemini/hooks/session-context.sh',
  description: 'Inject git/env context at session start'
}
Executive Verdict: **BLOCK**

This PR is structurally sound, well-tested, and adheres closely to a detailed spec. However, it contains several critical-level issues that must be fixed before it can be merged into `main`. The issues range from a simple but fatal copy-paste error in the data models to severe race conditions in financial logic and a foundational assumption about a database table that does not exist in production.

The presence of a comprehensive E2E test is excellent and caught none of these issues, which highlights the value of this critical, architectural review layer. The code is close, but not yet production-ready.

---

### Critical Issues (Must Fix Before Ship)

1.  **Fatal Decorator Error in Data Models**
    - **File:** `apps/backend-rag/backend/services/crm/partners/models.py`
    - **Issue:** All data classes (`Partner`, `PartnerReferral`, etc.) are decorated with `@../../.gemini/extensions/advanced-seo-mcp/.venv/lib/python3.11/site-packages/dns/rdataclass.py`. This is a file path, not a decorator. It appears to be a copy-paste or tool-automation error. The correct decorator is `@dataclasses.dataclass`.
    - **Impact:** This is a syntax error. The Python service will fail to start.
    - **Fix:** Replace the incorrect file path decorator with `@dataclasses.dataclass` for all models in the file.

2.  **Financial Race Condition in Commission Approval (Missing Transaction)**
    - **File:** `apps/backend-rag/backend/services/crm/partners/commission_engine.py`, method `approve()`
    - **Issue:** The logic to offset a pending clawback against an approval involves two separate `UPDATE` statements: one to reduce the `net_amount_idr` of the accrual, and another to change the status of the clawback to `offset_applied`. These are not wrapped in a database transaction.
    - **Impact:** If the system crashes between these two updates, the ledger will be left in an inconsistent state (e.g., an accrual's value is reduced, but the clawback is still marked as pending). This violates the append-only/immutable principles of a financial ledger and can lead to incorrect payouts.
    - **Fix:** Wrap the entire offset logic block within an `async with self.conn.transaction():` block to ensure atomicity.

3.  **Code Written Against Non-Existent Production Table**
    - **File:** `apps/backend-rag/backend/services/crm/partners/commission_engine.py`, method `accrue_from_process()`
    - **Issue:** The docstring explicitly states that the `processes` table, which is fundamental to the entire accrual mechanism, "does not exist in the live Fly.io DB — it is a test stub only." The code queries columns like `status`, `payment_status`, and `total_invoiced_idr` from this non-existent table.
    - **Impact:** The core feature of automatically accruing commissions will fail silently or crash in production. This feature cannot ship as-is.
    - **Fix:** This is a **major spec/implementation gap**. The developer must identify the *actual* production table and columns that represent a completed and paid client service and refactor the `accrue_from_process` method to query that real data source.

4.  **User/Partner Email Collision Race Condition**
    - **File:** `apps/backend-rag/backend/services/crm/partners/repository.py`, method `_assert_email_is_not_internal()`
    - **Issue:** The code and spec correctly identify that a partner's email should not collide with an internal user's email. However, the check is a `SELECT` followed by an `INSERT`, and the docstring explicitly notes this race condition is not handled.
    - **Impact:** While the race window is narrow, a concurrent operation could create a partner with an email that is also an admin, leading to serious authentication and authorization confusion.
    - **Fix:** The check and the subsequent `INSERT` in `insert_partner` must be wrapped in a `SERIALIZABLE` transaction to close the race window.

---

### Important Issues (Recommend for v1.0 or immediate v1.1)

1.  **Fragile Dependency Handling in Router**
    - **File:** `apps/backend-rag/backend/app/routers/partners.py`, methods `activate_partner()` and `mark_paid_commission()`
    - **Issue:** The code uses a `try...except ImportError:` block to conditionally call the email-sending functions. While this allows for partial implementation during development, it's an anti-pattern for production code. It hides dependency issues and makes the control flow less predictable.
    - **Fix:** Now that all modules are present in the PR, remove the `try/except` blocks. The email functions should be treated as a hard dependency for these state transitions.

2.  **Finance Permission Check is a Soft-Gate**
    - **File:** `apps/backend-rag/backend/app/routers/partners.py`, helper `_require_finance()`
    - **Issue:** The permission check correctly looks for `"finance.mark_paid"` in the user's JWT permissions but has a fallback that allows any user with the `admin` role to pass.
    - **Impact:** This weakens the principle of least privilege defined by the new, granular permissions. An admin without explicit finance approval rights can still perform financial operations.
    - **Fix:** The `if user.get("role") == "admin": return` fallback should be removed. Access should be determined solely by the presence of the specific permission in the `permissions` list, aligning with the spec's RBAC goals.

---

### Observations & Future Work

*   **Indonesian Compliance:** The implementation correctly addresses the spec's compliance points. The PPh 21/23 logic is present (though rates are placeholders, as noted), and the UU PDP data minimization principle is correctly implemented and tested in `emails.py` (`_sterilize` function). This is very well done.
*   **Append-Only Enforcement:** The ledger's append-only nature is enforced at the repository layer by raising a `RuntimeError`. This is acceptable for v1. For v2, consider hardening this with database-level `REVOKE DELETE` permissions for the application user on the `partner_commissions` table.
*   **Test Quality:** The E2E test is excellent. However, the test fixtures could be improved. The use of `uuid.UUID(int=partner_id.int)` suggests factories are returning integers or a custom type, not standard UUIDs. Manually updating foreign keys post-creation is also brittle. Refining the test factories to handle relationships would make tests cleaner and more robust.

---

**One Sentence Summary:** A structurally sound and well-tested module with critical-blocking issues related to race conditions, a fundamental syntax error in the data models, and a dangerous dependency on a non-existent production table.
