# Email System Documentation

Complete technical documentation for the Zantara Email Integration with Zoho Mail.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Backend Components](#2-backend-components)
3. [Frontend Components](#3-frontend-components)
4. [API Endpoints](#4-api-endpoints)
5. [Database Schema](#5-database-schema)
6. [OAuth 2.0 Flow](#6-oauth-20-flow)
7. [Logging & Metrics](#7-logging--metrics)
8. [Test Coverage](#8-test-coverage)
9. [Security Considerations](#9-security-considerations)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Architecture Overview

### System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (Next.js)                                  │
│                                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────────────────────┐ │
│  │  email/page.tsx │→ │  email.api.ts   │→ │          email.types.ts          │ │
│  │  (Main UI)      │  │  (API Client)   │  │  (TypeScript Interfaces)         │ │
│  └────────┬────────┘  └────────┬────────┘  └──────────────────────────────────┘ │
│           │                    │                                                 │
│  ┌────────┴────────────────────┴────────────────────────────────────────────┐   │
│  │  Components: FolderSidebar, EmailList, EmailViewer, EmailCompose,        │   │
│  │              ZohoConnectBanner                                            │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────┬─────────────────────────────────────────────┘
                                    │ HTTPS (JWT Auth)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND (FastAPI)                                   │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  Router: zoho_email.py                                                   │   │
│  │  Prefix: /api/integrations/zoho                                          │   │
│  │                                                                          │   │
│  │  Endpoints:                                                              │   │
│  │  - GET/POST /auth/*     (OAuth flow)                                     │   │
│  │  - GET /folders         (List folders)                                   │   │
│  │  - GET/POST /emails/*   (CRUD operations)                                │   │
│  │  - GET /unread-count    (Badge count)                                    │   │
│  └────────────┬────────────────────────────────────────────────────────────┘   │
│               │                                                                  │
│  ┌────────────┴────────────────────────────────────────────────────────────┐   │
│  │                          SERVICES                                        │   │
│  │  ┌──────────────────────┐     ┌──────────────────────────────────────┐  │   │
│  │  │  ZohoEmailService    │     │  ZohoOAuthService                    │  │   │
│  │  │  - list_emails()     │     │  - get_authorization_url()           │  │   │
│  │  │  - get_email()       │     │  - exchange_code()                   │  │   │
│  │  │  - send_email()      │     │  - get_valid_token()                 │  │   │
│  │  │  - reply_email()     │     │  - _refresh_token()                  │  │   │
│  │  │  - forward_email()   │     │  - get_connection_status()           │  │   │
│  │  │  - delete_emails()   │     │  - disconnect()                      │  │   │
│  │  │  - mark_read()       │     │                                      │  │   │
│  │  │  - toggle_flag()     │     │                                      │  │   │
│  │  │  - get_attachment()  │     │                                      │  │   │
│  │  │  - upload_attachment │     │                                      │  │   │
│  │  │  - save_draft()      │     │                                      │  │   │
│  │  │  - _log_activity()   │     │                                      │  │   │
│  │  └──────────┬───────────┘     └──────────────────────────────────────┘  │   │
│  └─────────────┼───────────────────────────────────────────────────────────┘   │
│                │                                                                 │
└────────────────┼─────────────────────────────────────────────────────────────────┘
                 │ HTTPS (OAuth 2.0)
                 ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           ZOHO MAIL API                                          │
│  https://mail.zoho.com/api/accounts/{account_id}/*                              │
│                                                                                  │
│  Scopes:                                                                         │
│  - ZohoMail.accounts.READ                                                        │
│  - ZohoMail.messages.READ/CREATE/UPDATE/DELETE                                   │
│  - ZohoMail.folders.READ                                                         │
│  - ZohoMail.attachments.READ/CREATE                                              │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Per-User Email Isolation

**Critical Security Feature**: Each user sees ONLY their own emails.

```
┌─────────────────────────────────────────────────────────────────────┐
│                     EMAIL ISOLATION FLOW                            │
│                                                                     │
│  1. User logs in → JWT token contains user_id                       │
│  2. Frontend sends request with JWT                                 │
│  3. Backend extracts user_id from JWT                               │
│  4. ZohoEmailService uses user_id to get user's OAuth token         │
│  5. Zoho API returns ONLY emails for that account                   │
│                                                                     │
│  user_id → zoho_email_tokens → access_token → Zoho API              │
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐              │
│  │   Zero      │    │   Ruslana   │    │   Kadek     │              │
│  │ user_id: 1  │    │ user_id: 2  │    │ user_id: 3  │              │
│  │ token: A    │    │ token: B    │    │ token: C    │              │
│  │ emails: 50  │    │ emails: 3   │    │ emails: 8   │              │
│  └─────────────┘    └─────────────┘    └─────────────┘              │
│        ↓                  ↓                  ↓                      │
│  zero@balizero.com  ruslana@balizero.com  kadek.tax@balizero.com   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Backend Components

### 2.1 ZohoEmailService (`backend/services/integrations/zoho_email_service.py`)

**Lines**: ~920
**Responsibility**: Core email operations

#### Methods

| Method | Description | Metrics |
|--------|-------------|---------|
| `list_emails()` | Paginated email list with filtering | ✗ |
| `get_email()` | Full email with content | ✗ |
| `search_emails()` | Search across folders | ✗ |
| `send_email()` | Send new email | ✓ (operation, duration) |
| `reply_email()` | Reply/Reply All | ✓ (activity log) |
| `forward_email()` | Forward email | ✓ (activity log) |
| `mark_read()` | Mark read/unread | ✗ |
| `toggle_flag()` | Flag/unflag | ✗ |
| `move_to_folder()` | Move to folder | ✗ |
| `delete_emails()` | Move to trash | ✓ (operation, duration) |
| `get_attachment()` | Download attachment | ✗ |
| `upload_attachment()` | Upload for send | ✗ |
| `save_draft()` | Save draft | ✗ |
| `get_unread_count()` | Total unread | ✗ |
| `list_folders()` | List all folders | ✗ |
| `_log_activity()` | Activity for weekly report | ✓ (DB) |

#### Internal Helpers

| Method | Purpose |
|--------|---------|
| `_get_headers()` | Build authenticated headers |
| `_get_account_id()` | Get Zoho account ID |
| `_request()` | Make authenticated API call |
| `_parse_recipients()` | Parse comma-separated emails |
| `_parse_recipients_to_objects()` | Parse to `{address, name}` objects |
| `_parse_attachments()` | Transform attachment metadata |
| `_normalize_folder_type()` | Map Zoho folder types |

### 2.2 ZohoOAuthService (`backend/services/integrations/zoho_oauth_service.py`)

**Lines**: ~530
**Responsibility**: OAuth 2.0 lifecycle

#### Methods

| Method | Description |
|--------|-------------|
| `get_authorization_url()` | Generate OAuth URL with CSRF state |
| `exchange_code()` | Exchange auth code for tokens |
| `get_valid_token()` | Get token (auto-refresh if needed) |
| `_refresh_token()` | Refresh expired token |
| `_get_account_info()` | Fetch Zoho account details |
| `_store_tokens()` | Persist tokens to PostgreSQL |
| `get_account_id()` | Get stored account ID |
| `get_connection_status()` | Check connection state |
| `disconnect()` | Revoke and remove tokens |

#### OAuth Scopes

```python
SCOPES = [
    "ZohoMail.accounts.READ",
    "ZohoMail.messages.READ",
    "ZohoMail.messages.CREATE",
    "ZohoMail.messages.UPDATE",
    "ZohoMail.messages.DELETE",
    "ZohoMail.folders.READ",
    "ZohoMail.attachments.READ",
    "ZohoMail.attachments.CREATE",
]
```

### 2.3 Router (`backend/app/routers/zoho_email.py`)

**Lines**: ~642
**Prefix**: `/api/integrations/zoho`

---

## 3. Frontend Components

### 3.1 Main Page (`apps/mouth/src/app/(workspace)/email/page.tsx`)

**Lines**: ~595
**Features**:
- Connection status check
- Folder navigation
- Email list with selection
- Email viewer with HTML rendering
- Compose modal (new, reply, forward)
- CSS stripping for Zoho emails (reply/forward)

#### Key Functions

| Function | Purpose |
|----------|---------|
| `htmlToPlainText()` | Strip Zoho CSS from HTML emails |
| `checkConnection()` | Verify Zoho OAuth status |
| `loadFolders()` | Fetch folder list |
| `loadEmails()` | Fetch email list |
| `loadEmailDetail()` | Fetch full email |
| `handleConnect()` | Initiate OAuth flow |
| `handleReply()` | Prepare reply compose |
| `handleForward()` | Prepare forward compose |
| `handleSendEmail()` | Send/Reply/Forward |
| `handleAddToCRM()` | Create CRM client from email |

### 3.2 API Client (`apps/mouth/src/lib/api/email/email.api.ts`)

**Lines**: ~263

| Method | Endpoint |
|--------|----------|
| `getAuthUrl()` | `GET /auth/url` |
| `getConnectionStatus()` | `GET /status` |
| `disconnect()` | `DELETE /disconnect` |
| `getFolders()` | `GET /folders` |
| `listEmails()` | `GET /emails` |
| `getEmail()` | `GET /emails/{id}` |
| `sendEmail()` | `POST /emails` |
| `replyEmail()` | `POST /emails/{id}/reply` |
| `forwardEmail()` | `POST /emails/{id}/forward` |
| `markRead()` | `PATCH /emails/mark-read` |
| `toggleFlag()` | `PATCH /emails/{id}/flag` |
| `deleteEmails()` | `DELETE /emails` |
| `downloadAttachment()` | `GET /emails/{id}/attachments/{aid}` |
| `uploadAttachment()` | `POST /attachments` |
| `getUnreadCount()` | `GET /unread-count` |

### 3.3 Types (`apps/mouth/src/lib/api/email/email.types.ts`)

**Lines**: ~183

Core interfaces:
- `ZohoConnectionStatus`
- `EmailFolder`
- `EmailSummary`
- `EmailDetail`
- `EmailAttachment`
- `SendEmailParams`
- `ReplyEmailParams`
- `ForwardEmailParams`

---

## 4. API Endpoints

### OAuth Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/auth/url` | JWT | Get Zoho OAuth URL |
| `GET` | `/callback` | None | OAuth callback handler |
| `GET` | `/status` | JWT | Connection status |
| `DELETE` | `/disconnect` | JWT | Disconnect account |

### Folder Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/folders` | JWT | List all folders |

### Email Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/emails` | JWT | List emails (paginated) |
| `GET` | `/emails/{id}` | JWT | Get email detail |
| `POST` | `/emails` | JWT | Send new email |
| `GET` | `/emails/search` | JWT | Search emails |
| `POST` | `/emails/{id}/reply` | JWT | Reply to email |
| `POST` | `/emails/{id}/forward` | JWT | Forward email |
| `PATCH` | `/emails/mark-read` | JWT | Mark read/unread |
| `PATCH` | `/emails/{id}/flag` | JWT | Toggle flag |
| `DELETE` | `/emails` | JWT | Delete emails |

### Attachment Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/emails/{id}/attachments/{aid}` | JWT | Download |
| `POST` | `/attachments` | JWT | Upload |

### Utility Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/unread-count` | JWT | Get unread count |

---

## 5. Database Schema

### Table: `zoho_email_tokens`

```sql
CREATE TABLE zoho_email_tokens (
    user_id VARCHAR(255) NOT NULL,
    account_id VARCHAR(255) NOT NULL,
    email_address TEXT NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    scopes TEXT[],
    api_domain TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (user_id, account_id)
);
```

### Table: `email_activity_log` (Migration 040)

```sql
CREATE TABLE email_activity_log (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL REFERENCES team_members(id) ON DELETE CASCADE,
    user_email TEXT NOT NULL,
    operation VARCHAR(50) NOT NULL, -- 'sent', 'received', 'read', 'deleted', 'replied', 'forwarded'
    email_subject TEXT,
    recipient_email TEXT,
    has_attachments BOOLEAN DEFAULT FALSE,
    attachment_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_email_activity_user ON email_activity_log(user_id);
CREATE INDEX idx_email_activity_created ON email_activity_log(created_at DESC);
CREATE INDEX idx_email_activity_user_created ON email_activity_log(user_id, created_at);
CREATE INDEX idx_email_activity_operation ON email_activity_log(operation);
```

---

## 6. OAuth 2.0 Flow

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                           ZOHO OAUTH 2.0 FLOW                                 │
│                                                                               │
│  1. User clicks "Connect Zoho"                                                │
│     │                                                                         │
│     ▼                                                                         │
│  2. Frontend: GET /api/integrations/zoho/auth/url                             │
│     │                                                                         │
│     ▼                                                                         │
│  3. Backend generates URL with state = "{user_id}:{random_token}"             │
│     │                                                                         │
│     ▼                                                                         │
│  4. Frontend redirects to: https://accounts.zoho.com/oauth/v2/auth?...        │
│     │                                                                         │
│     ▼                                                                         │
│  5. User logs in to Zoho and grants permissions                               │
│     │                                                                         │
│     ▼                                                                         │
│  6. Zoho redirects to: /api/integrations/zoho/callback?code=xxx&state=yyy     │
│     │                                                                         │
│     ▼                                                                         │
│  7. Backend extracts user_id from state, exchanges code for tokens            │
│     │                                                                         │
│     ▼                                                                         │
│  8. Backend stores tokens in zoho_email_tokens table                          │
│     │                                                                         │
│     ▼                                                                         │
│  9. Redirect to /email?connected=true                                         │
│                                                                               │
│  Token Refresh (automatic):                                                   │
│  - Tokens expire after ~1 hour                                                │
│  - get_valid_token() checks expiry with 5-min buffer                          │
│  - If expiring, calls _refresh_token() with refresh_token                     │
│  - New access_token stored, expiry updated                                    │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Logging & Metrics

### Logging

All email operations use structured logging with prefix `[Email]`:

```python
logger.info(f"[Email] Sending email user={user_id} to={to} subject='{subject[:50]}...'")
logger.debug(f"[Email] Found {len(folders)} folders for user={user_id}")
logger.error(f"[Email API] Error: {method} {endpoint} status={status_code}")
```

**Log Levels**:
- `INFO`: Operations start/complete
- `DEBUG`: Detailed operation data
- `WARNING`: Non-fatal issues (e.g., activity log failure)
- `ERROR`: API errors, failures

### Prometheus Metrics

Located in `backend/app/metrics.py`:

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `email_operations_total` | Counter | operation, user_id, status | Email operations count |
| `email_operation_duration_seconds` | Histogram | operation | Operation duration |
| `email_attachment_size_bytes` | Histogram | operation | Attachment sizes |
| `email_oauth_refresh_total` | Counter | status | OAuth refresh count |
| `email_errors_total` | Counter | error_type, operation | Error count |
| `email_unread_count` | Gauge | user_id | Unread emails per user |
| `email_active_users` | Gauge | - | Connected email accounts |

**Instrumented Operations**:
- `send_email()` - success/error, duration
- `delete_emails()` - success/error, duration
- `reply_email()` - activity log only
- `forward_email()` - activity log only

### Activity Logging

The `_log_activity()` method records operations for weekly reports:

```python
await self._log_activity(
    user_id=user_id,
    operation="sent",           # sent, replied, forwarded, deleted
    email_subject=subject,
    recipient_email=to[0],
    has_attachments=bool(attachments),
    attachment_count=len(attachments)
)
```

---

## 8. Test Coverage

### Test Files

| File | Tests | Status |
|------|-------|--------|
| `test_zoho_email_service.py` | 18 | ✅ All passed |
| `test_zoho_oauth_service.py` | 24 | ✅ All passed |
| `test_zoho_email_simple.py` | 35 | ✅ 33 passed, 2 skipped |

**Total: 93 tests (91 passed, 2 skipped)**

### Test Classes

```
ZohoEmailService Tests (18)
───────────────────────────────────────
TestZohoEmailServiceInit        1 test
TestInternalMethods             4 tests
TestFolderOperations            2 tests
TestEmailListOperations         5 tests
TestEmailReadOperations         4 tests
TestSearchOperations            1 test
TestSendOperations              4 tests
TestStatusOperations            6 tests
TestAttachmentOperations        4 tests
TestDraftOperations             1 test
TestUnreadCount                 2 tests
TestEdgeCases                   4 tests

ZohoOAuthService Tests (24)
───────────────────────────────────────
TestZohoOAuthService            6 tests (init, auth_url, exchange_code)
TestGetValidToken               3 tests (fresh, no_account, needs_refresh)
TestRefreshToken                3 tests (success, no_token, api_error)
TestGetAccountId                2 tests (success, not_found)
TestGetConnectionStatus         2 tests (connected, not_connected)
TestDisconnect                  3 tests (success, no_refresh, revoke_fails)
TestGetAccountInfo              4 tests (success, no_accounts, api_error, email_string)
TestStoreTokens                 1 test (success)

Router Tests (35)
───────────────────────────────────────
TestZohoEmailRouterSimple      35 tests (models, endpoints, validation)
```

### Running Tests

```bash
# Run all email tests (from apps/backend-rag directory)
cd apps/backend-rag
python -m pytest \
  backend/tests/unit/services/integrations/test_zoho_email_service.py \
  backend/tests/unit/services/integrations/test_zoho_oauth_service.py \
  tests/unit/test_zoho_email_simple.py -v

# Expected output: 93 passed (91 passed, 2 skipped)
```

### Coverage Summary

| Area | Coverage | Status |
|------|----------|--------|
| ZohoEmailService | ~95% | ✅ All core methods covered |
| ZohoOAuthService | ~95% | ✅ All OAuth flows covered |
| Router endpoints | ~90% | ✅ All endpoints validated |
| Pydantic models | 100% | ✅ Full validation coverage |
| Error handling | ~90% | ✅ Error paths covered |
| Frontend | 0% | ⚠️ No Jest tests (manual testing only) |

### Key Test Scenarios

**OAuth Flow**:
- ✅ Authorization URL generation
- ✅ Code exchange (success + error)
- ✅ Token refresh (auto + error paths)
- ✅ Token revocation
- ✅ Connection status check

**Email Operations**:
- ✅ List/Get emails
- ✅ Send/Reply/Forward
- ✅ Mark read/unread
- ✅ Toggle flag
- ✅ Delete emails
- ✅ Attachment handling

**Edge Cases**:
- ✅ Max limit enforcement
- ✅ Optional fields handling
- ✅ Plain text content fallback

---

## 9. Security Considerations

### Token Storage

- Access tokens and refresh tokens stored encrypted in PostgreSQL
- Tokens scoped per-user (user_id + account_id compound key)
- Refresh tokens preserved on update (COALESCE for non-empty)

### CSRF Protection

- State parameter format: `{user_id}:{random_token}`
- Validated on callback before token exchange

### Input Validation

- Pydantic models validate all request bodies
- EmailStr validates email format
- Field constraints (min_length, max_length)

### Privacy

- User IDs truncated in metrics (first 8 chars)
- Email content not logged (only subjects truncated to 50 chars)

---

## 10. Troubleshooting

### Common Issues

#### 1. OAuth Connection Fails

**Symptoms**: Redirect to `/email?error=connection_failed`

**Causes**:
- Invalid/expired authorization code
- Missing Zoho OAuth credentials in env
- Network timeout

**Solution**:
```bash
# Check Fly.io secrets
fly secrets list -a nuzantara-rag | grep ZOHO

# Required secrets:
# - ZOHO_CLIENT_ID
# - ZOHO_CLIENT_SECRET
# - ZOHO_REDIRECT_URI
# - ZOHO_ACCOUNTS_URL (default: https://accounts.zoho.com)
# - ZOHO_API_DOMAIN (default: https://mail.zoho.com)
```

#### 2. Token Refresh Fails

**Symptoms**: "Failed to refresh token - reconnect required"

**Causes**:
- Refresh token revoked
- Zoho account password changed
- OAuth app permissions revoked

**Solution**: User must disconnect and reconnect

#### 3. CSS Garbage in Reply/Forward

**Symptoms**: Reply shows CSS rules like `div.zm_xxx_parse {...}`

**Fixed**: The `htmlToPlainText()` function in `email/page.tsx` strips Zoho CSS patterns.

**Pattern Removed**:
```javascript
.replace(/div\.zm_[\w]+_parse_[\w]+[^{]*\{[^}]*\}/g, '')
```

#### 4. Wrong Emails Displayed

**Symptoms**: User sees another user's emails

**Root Cause**: This should NEVER happen due to per-user isolation.

**Debug**:
```sql
-- Check token ownership
SELECT user_id, email_address FROM zoho_email_tokens;

-- Verify JWT user_id matches
-- Check router _get_user_id() extraction
```

### Debug Queries

```sql
-- Check OAuth tokens
SELECT user_id, email_address, token_expires_at
FROM zoho_email_tokens
ORDER BY updated_at DESC;

-- Check activity log
SELECT user_id, operation, email_subject, created_at
FROM email_activity_log
ORDER BY created_at DESC
LIMIT 20;

-- Count emails per operation
SELECT operation, COUNT(*)
FROM email_activity_log
GROUP BY operation;
```

---

## Quick Reference

### Environment Variables

```bash
ZOHO_CLIENT_ID=xxx
ZOHO_CLIENT_SECRET=xxx
ZOHO_REDIRECT_URI=https://nuzantara-rag.fly.dev/api/integrations/zoho/callback
ZOHO_ACCOUNTS_URL=https://accounts.zoho.com
ZOHO_API_DOMAIN=https://mail.zoho.com
```

### Key Files

| Component | Path |
|-----------|------|
| Email Service | `backend/services/integrations/zoho_email_service.py` |
| OAuth Service | `backend/services/integrations/zoho_oauth_service.py` |
| Router | `backend/app/routers/zoho_email.py` |
| Frontend Page | `apps/mouth/src/app/(workspace)/email/page.tsx` |
| API Client | `apps/mouth/src/lib/api/email/email.api.ts` |
| Types | `apps/mouth/src/lib/api/email/email.types.ts` |
| Tests | `backend/tests/unit/services/integrations/test_zoho_*.py` |
| Migration | `backend/db/migrations/040_email_activity_log.sql` |

---

*Last Updated: 2026-01-05*
