VERDICT: REWORK

All line references below refer to commit `5f162f8e225721bd5e574cd7702379113f6657e1`.

1. **MEDIUM — Removing the connected-state action leaves no reliable reauthorization path.**

   [settings/integrations/page.tsx:140](</Users/balizero/nuzantara/apps/mouth/src/app/(workspace)/settings/integrations/page.tsx:140>) hides Connect whenever status is `connected` and instructs the user to revoke access through Google. However, [google_drive.py:83](/Users/balizero/nuzantara/apps/backend-rag/backend/app/routers/google_drive.py:83) obtains that status from `is_connected()`, which accepts the stored token without contacting Google while its expiry remains outside the refresh window: [google_drive_service.py:229](/Users/balizero/nuzantara/apps/backend-rag/backend/services/integrations/google_drive_service.py:229), lines 229–235 and 291–294.

   Consequently, revoking a grant externally can leave the page showing Connected with no way to reconnect—even after reloading—until refresh becomes due and fails. The mounted page also checks status only once. The previous local Disconnect toggle, although it did not revoke anything, exposed Connect; removing it also removed that recovery path.

   **Verification:** an in-memory probe executing the target’s exact service methods returned `connected=True` for a synthetic stored token expiring in 30 minutes, with zero refresh or remote-validation calls. Keep an explicit reauthorize/account-switch action available, or provide a confirmed disconnect that clears the stored grant.

2. **LOW — The new status contract exposes `configured`, but the page ignores it and silently fails to connect.**

   [settings/integrations/page.tsx:42](</Users/balizero/nuzantara/apps/mouth/src/app/(workspace)/settings/integrations/page.tsx:42>) reduces the response to `connected` alone at line 45. With `{connected:false, configured:false}`, it displays Disconnected and enables Connect at line 149. Yet [google_drive.py:103](/Users/balizero/nuzantara/apps/backend-rag/backend/app/routers/google_drive.py:103) deterministically rejects authorization with HTTP 503 when OAuth is unconfigured. The page’s catch block, lines 69–71, only logs the error and resets the button.

   **Verification:** executing the target’s router branches with an unconfigured synthetic service produced that status response and the expected 503. This is a conditional configuration defect; production misconfiguration was not established. Honor `configured` and display an actionable error. The silent catch existed previously, but the rewritten page now receives and discards the explicit configuration signal.

3. **LOW — References to deleted modules and routes remain in documentation and test scaffolding.**

   [DOCUMENTATION.md:700](/Users/balizero/nuzantara/apps/mouth/DOCUMENTATION.md:700) still demonstrates the deleted `useWebSocket`, `WebSocketProvider`, and `useWebSocketContext`; lines 508–512 describe deleted chat components, and line 832 advertises the deleted article-views route. [dashboard/**tests**/page.test.tsx:65](</Users/balizero/nuzantara/apps/mouth/src/app/(workspace)/dashboard/__tests__/page.test.tsx:65>) still supplies mock exports for deleted dashboard components, including `StatsCard`, `CasesPreview`, and `DashboardStatCard`.

   These are stale references, not demonstrated runtime import failures. Remove the obsolete examples and mock exports.

The targeted `git grep` searches and dynamic-import, Next configuration, script, e2e, and i18n inspection found **no dangling runtime importer or live navigation reference attributable to the deletions**.

**Coverage limitation:** the requested diff contains 215 changed files, including 97 nondeleted files; its base predates the pruning commit’s direct parent. All 26 nondeleted files changed by #6296 itself, plus 69 other files in the wider interval, were read in full. `.secrets.baseline` was fully parsed structurally; the 3.16 MB `.claude/skills/modus/PENDING-ARMS.md` was structurally scanned but not semantically read in full. Both are unchanged by #6296 itself. The literal full-text-read requirement for the entire supplied interval therefore remains incomplete. No build or browser/e2e run was performed. No repository files were modified.
