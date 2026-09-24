# Portal usage measurement — 2026-09-24

Status: implementation prepared for independent review; not released. Access to the authenticated GA4 reports is pending the operator's Google sign-in.

## Purpose and existing components

Measure authenticated portal navigation and the message-send and document-upload submission funnels. Reuse the existing GA4 browser tag. No backend database, dependency, API key, tracking vendor, or custom client identity is added.

Consumers:

- The authenticated portal layout mounts PortalUsageTracker after its loading/authentication phase.
- PortalApi.sendMessage covers both the messages hook and the direct chat page.
- useVaultUpload covers the actual Vault XHR/progress upload, including preflight rejection; PortalApi.uploadDocument covers the legacy document hook.

## Event contract

| Event                   | Meaning                                                                                      |
| ----------------------- | -------------------------------------------------------------------------------------------- |
| portal_page_view        | Initial authenticated page and subsequent pathname changes                                   |
| portal_action_started   | A message submission or document upload attempt begins, including Vault preflight validation |
| portal_action_completed | The operation resolves successfully                                                          |
| portal_action_failed    | The operation rejects                                                                        |

Closed parameters: portal_section, portal_action (message_send or document_upload), failure_class (validation, request, server, response, network, unknown), duration_ms. URLs are reduced to section paths; title and referrer are fixed safe values. No client IDs, emails, message text, document names, types, practice IDs, query strings, or raw errors are supplied. Only client-role sessions without staff impersonation qualify. Partner/public/auth routes are excluded.

GA4 supplies its existing browser pseudonymous identifiers; these events add no custom user_id. Browser identity is not a verified person and does not link devices or map this history back to the 103-account cohort.

## Report recipe after release and access verification

1. Confirm portal_page_view and all three action stages in GA4 Realtime or DebugView using a synthetic authorized client. Check that staff preview emits none.
2. Register event-scoped dimensions portal_section, portal_action and failure_class if absent; register duration_ms as a custom metric if needed.
3. In an Exploration, filter hostname my.balizero.com and the portal_* event names. Compare section users, navigation sequences, submission completion and failure rates.
4. Compare new and returning browser sessions, not repeated logins. Cookie loss, blockers, consent state and network loss limit coverage.
5. A section visit without submission is not proven abandonment: the user may only be reading. Submission started without an outcome is incomplete observation, not proof of an error.
6. No historical reconstruction is claimed. These new custom events begin only after the release owner deploys the change. Existing GA4 history must be inspected separately.

## Verification and release boundary

Targeted tests cover auth/staff exclusion, URL and payload redaction, API success/error preservation, and route rerender behavior. Existing portal API and layout tests are included. No live client mutation or test message/upload was performed.

The external builder prepares only. A Claude release owner must independently verify, merge and prove the events reach the intended GA4 property. Google sign-in is an operator action; no credentials are requested in chat.

Reference: [Google Analytics event implementation](https://developers.google.com/analytics/devguides/collection/ga4/events).
