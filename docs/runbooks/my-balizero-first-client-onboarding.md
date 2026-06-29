# My Bali Zero First-Client Onboarding Runbook

## Purpose

Prepare the first client account for `my.balizero.com` so the portal feels like a useful client cockpit from the first login:

- Clear view of bureaucracy and active practices.
- Smart next actions and deadlines.
- Safe document visibility.
- Approved Bali Zero information and entertainment content.
- No raw OSINT, internal notes, credentials, or unreviewed intelligence.

## Operating Rules

- Use `zantara@balizero.com` as the sender identity for client-facing email.
- Do not put real client PII into test artifacts, screenshots, prompt logs, or reusable fixtures.
- Do not expose internal CRM notes, internal WhatsApp wording, raw research, or admin-only intelligence in the client portal.
- When a field is uncertain, show a conservative empty state or "Bali Zero is reviewing this" status instead of inventing facts.
- The portal is a client view, not the operational database. Only publish data that is approved for client consumption.

## 1. Client Record Readiness

Before sending the portal invite, confirm the client record has:

- Full client display name.
- Client email used for portal login.
- WhatsApp or phone number.
- Nationality.
- Passport expiry when relevant to the active practice.
- Assigned Bali Zero team owner.
- Preferred communication language.
- No duplicate client records that could route documents or messages to the wrong account.

Acceptance:

- The portal profile shows the same client identity that Ops expects.
- Client-visible profile fields do not include internal-only metadata.

## 2. Active Matter Readiness

For the first login, the client should see either one active matter or a deliberately clean empty state.

For each active matter, confirm:

- Matter title is client-readable.
- Matter category is correct: visa, company, tax, property, or operations.
- Status label matches the operational state.
- Next step is actionable and written for the client.
- Deadline is real and sourced from the matter or compliance system.
- Assigned team member is correct.
- Matter-specific recap is approved for client view.

Acceptance:

- The dashboard explains what is happening now.
- The client can answer: "What does Bali Zero need from me next?"

## 3. Process Timeline Readiness

Confirm the process page shows:

- Active process name.
- Current status.
- Completed steps.
- Current step.
- Required documents.
- Expiry or compliance date when relevant.

Each required document should have:

- Clear document label.
- Required or optional status.
- Uploaded, pending, verified, or rejected status.
- Client-safe notes only.

Acceptance:

- The process page makes the next document action explicit.
- No internal team notes are visible to the client unless deliberately rewritten for client use.

## 4. Document Vault Readiness

For every visible file, confirm:

- File belongs to the authenticated client.
- File name is understandable.
- Purpose is client-safe.
- Practice linkage is correct.
- Expiry date is shown only when relevant and accurate.
- Download permission is intentional.

Acceptance:

- The client can find key documents by search.
- The vault does not expose staff files, raw intake evidence, credentials, or unrelated client records.

## 5. Company And Tax Readiness

If the client has a company, confirm:

- Primary company is set.
- Company name is accurate.
- Entity type is accurate.
- NIB, NPWP, and KBLI are shown only if approved for client display.
- Compliance items have real due dates.

If tax status is shown, confirm:

- Next deadline is real.
- Status is conservative when data is incomplete.
- No tax advice is framed as legal or accounting advice without review.

Acceptance:

- Company card opens the Companies section.
- Tax and compliance surfaces show useful deadlines without overclaiming.

## 6. Messages And Notifications

Before invite:

- Create or verify one welcome/next-action message if the client has an active matter.
- Confirm unread count matches visible messages.
- Confirm notification body is client-safe.
- Remove or rewrite any raw CRM, WhatsApp, OSINT, or internal debugging language.

Acceptance:

- The first visible message tells the client what to do next or how Bali Zero will proceed.

## 7. Bali Zero Dispatch Readiness

The portal can include Bali Zero editorial content, but only approved content should appear.

Confirm:

- Articles are published and approved.
- Titles are useful for the client's context.
- Links route to public article pages.
- No draft research, raw intelligence, or private client material is exposed.

Acceptance:

- Dispatch content adds confidence and engagement without confusing the operational next step.

## 8. Invitation Flow

Before sending:

- Run the latest portal smoke tests.
- Check the deployed `my.balizero.com` portal with a pilot account.
- Confirm the client email is correct.
- Confirm the account is linked to the correct client id.
- Confirm role is `client`, not admin or team.

Invite email should include:

- Portal URL: `https://my.balizero.com`.
- Short explanation of what the client can see: bureaucracy, next actions, documents, deadlines, and Bali Zero updates.
- Login instructions.
- Support channel for access issues.

Sender:

- `Zantara <zantara@balizero.com>`.

## 9. Final Production Smoke

Run this checklist on `my.balizero.com` before the client receives the invite:

- Login works on desktop.
- Login works on mobile viewport or real mobile browser.
- Dashboard shows client name and matter context.
- Company card opens Companies when a company exists.
- Process page shows active practice and required documents.
- Vault search works.
- Messages load.
- Notifications load.
- Profile is client-safe.
- Dispatch links open public article pages.
- Browser console has no runtime errors.
- No API request returns 401, 403, or 500 after authenticated login.

## 10. Support And Rollback

If the client reports a problem:

- Confirm account email and role.
- Reset invite or PIN if login fails.
- Revoke portal access if data linkage looks wrong.
- Correct the CRM/client linkage before restoring access.
- If a document or message leak is suspected, pause the account first and investigate second.

Rollback acceptance:

- Client access can be paused without deleting the underlying CRM record.
- The team can restore access after correcting the visible data.
