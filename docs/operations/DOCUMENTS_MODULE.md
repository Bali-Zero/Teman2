# Documents Module - Complete Documentation

**Last Updated:** 2026-01-05
**Module Version:** 2.0 (OAuth + Permission Management)

---

## Overview

The Documents module provides Google Drive integration for the Zantara workspace, enabling team members to browse, manage, and share files within the organization's Shared Drive.

### Key Features

- **File Browsing**: Grid and list views with folder navigation
- **File Operations**: Upload, download, create, rename, move, copy, delete
- **Permission Management**: Add/remove/update user access to files and folders
- **Role-Based Visibility**: Users only see folders they have access to
- **Hidden Admin Pattern**: Admins can have full access without being visible to others

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                          │
├────────────────────────────────────────────────────────────────────┤
│  apps/mouth/src/app/(workspace)/documents/page.tsx                  │
│  ├── ContextMenu.tsx        - Right-click context menu              │
│  └── PermissionDialog.tsx   - Manage access dialog                  │
└────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ /api/team-drive/*
┌────────────────────────────────────────────────────────────────────┐
│                         Backend (FastAPI)                           │
├────────────────────────────────────────────────────────────────────┤
│  backend/app/routers/team_drive.py        - API endpoints           │
│  backend/app/routers/google_drive.py      - OAuth endpoints         │
│  backend/services/integrations/team_drive_service.py - Business     │
└────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
          ┌─────────────────┐             ┌─────────────────┐
          │   Google Drive  │             │   PostgreSQL    │
          │   API (OAuth)   │             │   - team_members│
          │   30TB Quota    │             │   - folder_rules│
          └─────────────────┘             └─────────────────┘
```

---

## Access Control System

### User Visibility Rules

1. **Department-Based Access** (`departments.can_see_all`)
   - If `can_see_all = true`, user sees ALL team folders
   - Example: "founders" department has `can_see_all = true`

2. **Folder Access Rules** (`folder_access_rules` table)
   - `allowed_folders`: Array of folder names user can access
   - `context_folder`: Primary folder for the user
   - Example: Ruslana can see `[Anton, Dea, Rina, Dewa Ayu, Kadek, Angel, Faysha]`

3. **Hidden Admins**
   - Some users are invisible in permission lists
   - Configured in `team_drive.py`: `HIDDEN_ADMINS = ["zero@balizero.com", "antonellosiano@gmail.com"]`
   - Hidden admins can see themselves but others cannot

### Database Schema

```sql
-- folder_access_rules (migration 037)
CREATE TABLE folder_access_rules (
    id SERIAL PRIMARY KEY,
    user_email VARCHAR(255) NOT NULL UNIQUE,
    allowed_folders TEXT[] NOT NULL,
    context_folder VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- departments (for can_see_all)
ALTER TABLE departments ADD COLUMN can_see_all BOOLEAN DEFAULT FALSE;
```

---

## API Endpoints

### File Operations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/team-drive/status` | GET | Connection status + user access info |
| `/api/team-drive/files` | GET | List files in folder (filtered by access) |
| `/api/team-drive/files/{file_id}` | GET | Get single file metadata |
| `/api/team-drive/files/{file_id}/download` | GET | Download file content |
| `/api/team-drive/files/{file_id}/path` | GET | Get folder breadcrumb path |
| `/api/team-drive/search` | GET | Search files by name |
| `/api/team-drive/upload` | POST | Upload file to folder |
| `/api/team-drive/folders` | POST | Create new folder |
| `/api/team-drive/docs` | POST | Create Google Doc/Sheet/Slide |
| `/api/team-drive/files/{file_id}/rename` | PATCH | Rename file |
| `/api/team-drive/files/{file_id}` | DELETE | Delete file (trash or permanent) |
| `/api/team-drive/files/{file_id}/move` | POST | Move file to new parent |
| `/api/team-drive/files/{file_id}/copy` | POST | Copy file |

### Permission Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/team-drive/files/{file_id}/permissions` | GET | List permissions (filters hidden admins) |
| `/api/team-drive/files/{file_id}/permissions` | POST | Add permission for user |
| `/api/team-drive/files/{file_id}/permissions/{perm_id}` | PATCH | Update permission role |
| `/api/team-drive/files/{file_id}/permissions/{perm_id}` | DELETE | Remove permission |

### OAuth Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/integrations/google-drive/system/status` | GET | SYSTEM OAuth status |
| `/api/integrations/google-drive/system/authorize` | GET | Get OAuth URL (admin only) |
| `/api/integrations/google-drive/callback` | GET | OAuth callback |
| `/api/integrations/google-drive/system/disconnect` | POST | Disconnect OAuth (admin only) |

---

## Frontend Components

### DocumentsPage (`page.tsx`)

Main page component with:
- **Header**: Search bar, view toggle (grid/list), new file button
- **Sidebar**: Quick access folders (if access rules defined)
- **Main Area**: File grid or list view
- **Context Menu**: Right-click actions on files
- **Dialogs**: Upload, create folder, create doc, rename, move, permission

### ContextMenu (`ContextMenu.tsx`)

Right-click menu with options:
- Open / Open in Drive
- Rename
- Move to...
- Copy (files only)
- Download (files only)
- **Manage Access** (highlighted in blue)
- Delete (danger, red)

### PermissionDialog (`PermissionDialog.tsx`)

Manage access dialog with:
- Add person form (email + role dropdown)
- Current permissions list
- Role selector (Reader, Commenter, Editor)
- Remove button (Owner cannot be removed)
- Send notification checkbox

---

## Logging

All operations are logged with `[TEAM_DRIVE]` prefix:

```python
# Example log entries
logger.info(f"[TEAM_DRIVE] {user_email} uploaded: {filename}")
logger.info(f"[TEAM_DRIVE] {user_email} created folder: {name}")
logger.info(f"[TEAM_DRIVE] {user_email} added permission: {email} as {role} on {file_id}")
logger.error(f"[TEAM_DRIVE] Error uploading file: {e}")
```

### Log Categories

| Level | Use Case |
|-------|----------|
| `INFO` | Successful operations (upload, create, rename, delete, permission changes) |
| `WARNING` | Non-critical issues (could not get folder path) |
| `ERROR` | Operation failures |

---

## Prometheus Metrics

All metrics have `zantara_` prefix:

### Counters

| Metric | Labels | Description |
|--------|--------|-------------|
| `zantara_drive_operations_total` | operation, user_email, status | Total operations |
| `zantara_drive_oauth_refresh_total` | status | OAuth token refreshes |
| `zantara_drive_errors_total` | error_type, operation | Error count by type |
| `zantara_drive_files_accessed_total` | file_type, action | File access by type |

### Histograms

| Metric | Buckets | Description |
|--------|---------|-------------|
| `zantara_drive_operation_duration_seconds` | 0.1-30s | Operation timing |
| `zantara_drive_file_size_bytes` | 1KB-100MB | File sizes |

### Gauges

| Metric | Description |
|--------|-------------|
| `zantara_drive_oauth_token_expiry_seconds` | Time until OAuth expires |
| `zantara_drive_quota_usage_percent` | Quota usage (0-100) |
| `zantara_drive_active_users` | Users active in last hour |

---

## Testing

### Unit Tests (38 tests)

Location: `backend/tests/unit/services/integrations/test_team_drive_service.py`

Coverage:
- `TestTeamDriveServiceInit` - Initialization with/without DB pool
- `TestOAuthTokenHandling` - Token retrieval and refresh
- `TestFileOperations` - List, search, get metadata, get path
- `TestCRUDOperations` - Upload, create, rename, delete, move, copy
- `TestPermissionManagement` - List, add, update, remove permissions
- `TestAuditLogging` - Audit logger functionality
- `TestMetricsIntegration` - Prometheus metrics recording
- `TestSingletonPattern` - Service singleton behavior

### Integration Tests (21 tests)

Location: `backend/tests/integration/test_team_drive_api.py`

Coverage:
- `TestMetricsIntegration` - Metrics collector methods
- `TestResponseSchemas` - API response structures
- `TestTeamDriveRouterConfig` - Router configuration
- `TestTeamDriveServiceIntegration` - Service imports
- `TestErrorClassification` - Error type handling
- `TestOAuthConfiguration` - OAuth scopes and config

### Running Tests

```bash
# Unit tests
pytest backend/tests/unit/services/integrations/test_team_drive_service.py -v

# Integration tests
pytest backend/tests/integration/test_team_drive_api.py -v

# All Drive tests
pytest -k "drive" -v
```

---

## Configuration

### Environment Variables (Fly.io Secrets)

```bash
# OAuth 2.0
GOOGLE_DRIVE_CLIENT_ID=930328104463-d39fpretk5t0lucunkovu7o0g6id5eu2.apps.googleusercontent.com
GOOGLE_DRIVE_CLIENT_SECRET=GOCSPX-xxxxx

# Shared Drive
GOOGLE_DRIVE_ROOT_FOLDER_ID=1hkOeV03YM5-sHbQhswYz809jsrnwC0At
```

### OAuth Token Storage

```sql
-- google_drive_tokens table
CREATE TABLE google_drive_tokens (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,  -- 'SYSTEM' for shared token
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    scope TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## Troubleshooting

### Common Issues

1. **"storageQuotaExceeded"**
   - OAuth connected to wrong account
   - Re-authorize with 30TB Google One account

2. **"Permission denied"**
   - User not in `folder_access_rules`
   - Check department `can_see_all` flag

3. **"Token refresh failed"**
   - OAuth token revoked in Google account
   - Re-authorize: `/api/integrations/google-drive/system/authorize`

4. **Permissions not showing**
   - API filtering hidden admins
   - Check if requester is in `HIDDEN_ADMINS` list

### Debug Commands

```bash
# Check OAuth status
curl -s https://nuzantara-rag.fly.dev/api/integrations/google-drive/system/status | jq

# Check user folder access
fly ssh console -a nuzantara-rag -C "psql \$DATABASE_URL -c \"
  SELECT user_email, allowed_folders, context_folder
  FROM folder_access_rules
  WHERE user_email = 'user@balizero.com'
\""

# Check logs
fly logs -a nuzantara-rag | grep "TEAM_DRIVE"
```

---

## Recent Changes (2026-01-05)

1. **Removed Board-only restriction** - All users can manage permissions
2. **Hidden admin pattern** - Zero/Anton invisible to other users
3. **Access rules updated**:
   - Zero: Full access (founders department, can_see_all=true)
   - Ruslana: Her folder + Anton, Dea, Rina, Dewa Ayu, Kadek, Angel, Faysha
   - Veronika: Her folder + Dewa Ayu, Kadek, Angel, Faysha
   - Zainal: Deactivated
4. **UI improvements** - Removed hover checkbox, improved PermissionDialog

---

## Files Reference

### Backend

| File | Purpose |
|------|---------|
| `backend/app/routers/team_drive.py` | Main API endpoints |
| `backend/app/routers/google_drive.py` | OAuth endpoints |
| `backend/services/integrations/team_drive_service.py` | Business logic |
| `backend/app/metrics.py` | Prometheus metrics |
| `backend/db/migrations/034_google_drive_tokens.sql` | OAuth storage |
| `backend/db/migrations/037_folder_access_rules.sql` | Access rules |

### Frontend

| File | Purpose |
|------|---------|
| `apps/mouth/src/app/(workspace)/documents/page.tsx` | Main page |
| `apps/mouth/src/components/documents/ContextMenu.tsx` | Context menu |
| `apps/mouth/src/components/documents/PermissionDialog.tsx` | Permission dialog |
| `apps/mouth/src/lib/api/drive/drive.api.ts` | API client |
| `apps/mouth/src/lib/api/drive/drive.types.ts` | TypeScript types |
