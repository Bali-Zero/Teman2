# CRM↔Portal Auto-Sync Design

**Date:** 2026-04-02
**Status:** Draft
**Scope:** Auto-populate portal profiles, bidirectional OCR, notifications

---

## Problem

1,097 clients in CRM (`/clients`), only 84 have a portal record in `team_members` (role='client'). The portal profile is only created via manual invite flow. Documents uploaded by clients in the portal don't trigger OCR. No notifications flow between CRM and portal on document uploads or status changes.

## Goals

1. Every client created in CRM automatically gets a portal profile
2. Backfill existing 1,013 clients without a portal record
3. Portal document uploads trigger OCR (same as CRM uploads)
4. Team gets notified (CRM badge + email) when client uploads from portal
5. Client gets notified (portal notification) when team uploads a document or changes practice/visa status

---

## 1. Auto-Creation of Portal Profile

### Trigger

After a client is created via `POST /api/crm/clients` in `crm_clients.py:280` (`create_client()`).

### Action

Insert into `team_members`:

```sql
INSERT INTO team_members (email, role, linked_client_id, portal_access)
VALUES ($1, 'client', $2, true)
ON CONFLICT (email) DO UPDATE SET linked_client_id = $2, portal_access = true
```

- `email` = client's email from `clients.email`
- `linked_client_id` = the newly created `clients.id`
- `portal_access` = true
- `pin_hash` = NULL (no PIN yet — client sets it when invited)

### Where

In the `create_client()` function in `crm_clients.py`, after the client INSERT succeeds. Same transaction if possible, otherwise immediately after with error logging (non-blocking — a failed portal record shouldn't block client creation).

### Edge Cases

- Client without email: skip portal record creation, log warning. Portal requires email for login.
- Duplicate email in `team_members`: ON CONFLICT updates `linked_client_id` and `portal_access`.
- Client soft-deleted then re-created: same email conflict handling.

### Backfill Script

One-shot script for existing clients:

```sql
INSERT INTO team_members (email, role, linked_client_id, portal_access)
SELECT c.email, 'client', c.id, true
FROM clients c
WHERE c.deleted_at IS NULL
  AND c.email IS NOT NULL
  AND TRIM(c.email) != ''
  AND NOT EXISTS (
    SELECT 1 FROM team_members tm
    WHERE tm.linked_client_id = c.id AND tm.role = 'client'
  )
ON CONFLICT (email) DO UPDATE
  SET linked_client_id = EXCLUDED.linked_client_id,
      portal_access = true
  WHERE team_members.role = 'client';
```

Run via psql on production DB through tunnel. Log count before/after.

---

## 2. OCR on Portal Document Upload

### Current State

- CRM upload (`crm_enhanced.py:748`): `_dispatch_ocr_by_folder()` auto-detects document type by filename keywords (passport, kitas, npwp, nib, company profile) and dispatches to the appropriate OCR handler.
- Portal upload (`portal_service.py:1395`): `upload_document()` does virus scan only, no OCR.

### Change

After successful portal document upload, call `_dispatch_ocr_by_folder()` with the uploaded document's filename and metadata.

### Implementation

In `portal_service.py:upload_document()`, after the document record is created and file uploaded to Drive:

1. Import the OCR dispatcher function (or extract it to a shared service if currently router-bound)
2. Call `await dispatch_ocr(filename, document_id, client_id, db_pool)` as a background task
3. Same keyword detection logic as CRM: passport, kitas, visa, npwp, nib, company profile

### Refactor Note

`_dispatch_ocr_by_folder()` currently lives in the router (`crm_enhanced.py:748`). Extract to a shared service `backend/services/documents/ocr_dispatcher_service.py` so both CRM and portal can call it without circular imports.

---

## 3. Notify Team on Client Portal Upload

### Trigger

Client uploads a document from `my.balizero.com` via `POST /api/portal/documents/upload`.

### Recipients

The `assigned_to` team member from the `clients` table for this client.

### Channel A: CRM Alert (Badge)

The `notification_alerts` table exists but has no CRM frontend rendering (used only by cron jobs for expiry alerts). Two options:

**Option A (recommended):** Add a new API endpoint `GET /api/crm/notifications` that queries `notification_alerts` filtered by `assigned_to` team member, and add a notification bell component to the CRM frontend header. This makes `notification_alerts` reusable for all CRM alert types.

**Option B:** Use `activity_log` table and surface recent entries in the CRM dashboard. Less structured but requires no new frontend component.

Insert into `notification_alerts`:

```sql
INSERT INTO notification_alerts (client_id, alert_type, status, message)
VALUES ($1, 'portal_document_upload', 'pending', $2)
```

- `alert_type` = `'portal_document_upload'`
- `message` = `"{client_name} uploaded {document_type} via portal"`

**Frontend work needed:** Notification bell in CRM header + `GET /api/crm/notifications` endpoint.

### Channel B: Email

Send email to `assigned_to` via Brevo:

- **From:** `zantara@balizero.com`
- **Subject:** `"[Portal] {client_name} uploaded {document_type}"`
- **Body:** Client name, document type, filename, direct CRM link to client profile

### Where

In `portal_service.upload_document()`, after successful upload. Non-blocking background task — upload response shouldn't wait for email delivery.

---

## 4. Notify Client on CRM Document Upload

### Trigger

Team member uploads a document for a client via `POST /api/crm/clients/{client_id}/documents` in `crm_enhanced_documents.py`.

### Channel: Portal Notification

Insert into `portal_messages`:

```sql
INSERT INTO portal_messages (client_id, subject, direction, content, sent_by)
VALUES ($1, $2, 'team_to_client', $3, $4)
```

- `subject` = `"New document: {document_type}"`
- `content` = `"A new {document_type} document has been added to your profile."`
- `sent_by` = team member email
- `direction` = `'team_to_client'`

### Where

In `crm_enhanced_documents.py`, after successful document creation. Non-blocking.

### Frontend

Already handled — `usePortalNotifications.ts` fetches from `GET /api/portal/notifications` and displays unread count.

---

## 5. Notify Client on Status Changes

### Triggers

**Practice status change:** In `crm_practices.py:943` (`update_practice()`), when `status` field changes.

**Client data update:** In `crm_clients.py`, when significant fields change:

- `passport_number`, `passport_expiry`
- `visa_type`, `visa_expiry`
- `address`, `city`, `province`

### Significant vs Noise

**Notify on:** status, priority, payment*status, passport*\_, visa\_\_, address fields
**Skip:** `assigned_to`, `notes` (internal), `updated_at`, `last_contacted_at`

### Channel: Portal Notification

```sql
INSERT INTO portal_messages (client_id, practice_id, subject, direction, content, sent_by)
VALUES ($1, $2, $3, 'team_to_client', $4, $5)
```

Messages by type:

- Practice status → `"Your {practice_type} status updated to {new_status}"`
- Visa status → `"Visa status update: {new_status}"`
- Personal data → `"Your profile has been updated"`

### Where

In `update_practice()` after the UPDATE succeeds, check if `status` was in the changed fields. If yes, insert portal notification. Same pattern for client update endpoint.

---

## Files to Modify

| File                                                   | Change                                                   |
| ------------------------------------------------------ | -------------------------------------------------------- |
| `backend/app/routers/crm_clients.py`                   | Add portal record creation after client INSERT           |
| `backend/app/routers/crm_enhanced_documents.py`        | Add portal notification after doc upload                 |
| `backend/app/routers/crm_practices.py`                 | Add portal notification on status change                 |
| `backend/app/routers/crm_notifications.py`             | **NEW** — `GET /api/crm/notifications` for team alerts   |
| `backend/services/portal/portal_service.py`            | Add OCR dispatch + team notification after portal upload |
| `backend/services/documents/ocr_dispatcher_service.py` | **NEW** — extracted from `crm_enhanced.py:748`           |
| `apps/mouth/src/components/crm/NotificationBell.tsx`   | **NEW** — CRM header notification bell                   |
| `scripts/backfill_portal_profiles.py`                  | **NEW** — one-shot backfill script                       |

## Tables Used (All Existing)

| Table                 | Role                                                            |
| --------------------- | --------------------------------------------------------------- |
| `team_members`        | Portal profile (role='client', linked_client_id, portal_access) |
| `notification_alerts` | CRM badge alerts for team                                       |
| `portal_messages`     | Client-facing notifications in portal                           |
| `documents`           | Shared document store (CRM + portal)                            |

No schema changes needed. All tables already exist with the required columns.

---

## Non-Goals

- Changing the invite/PIN flow (stays as-is for sending credentials)
- Real-time WebSocket push (existing polling is sufficient)
- Email notifications to clients on every change (portal notification only — no spam)
- Document-level RBAC or sensitivity levels
- Retroactive notifications for existing documents
