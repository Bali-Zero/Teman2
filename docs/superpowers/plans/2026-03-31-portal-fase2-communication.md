# Portal Fase 2 — Communication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve portal communication: self-service profile editing, chat grouped by practice (multi-thread), and a notification center — addressing the top 3 client pain points from the portal strategy brainstorm.

**Architecture:** Profile editing adds a PATCH endpoint via PortalService with field whitelist. Chat multi-thread is a frontend-only change — `portal_messages` already stores `practice_id` and `practice_name`, so we group client-side. Notification center adds a `portal_notifications` table, SSE stream endpoint, and a frontend bell popover (already scaffolded as `PortalNotifications.tsx`).

**Tech Stack:** FastAPI (backend), asyncpg, Next.js App Router (frontend), React Query, SSE (Server-Sent Events), Warm Depth design tokens.

---

## Feature A: Profile Self-Service Editing

### File Structure

| File                                                         | Action | Responsibility                                     |
| ------------------------------------------------------------ | ------ | -------------------------------------------------- |
| `backend/services/portal/portal_service.py`                  | Modify | Add `update_profile()` method with field whitelist |
| `backend/app/routers/portal.py`                              | Modify | Add `PATCH /api/portal/profile` endpoint           |
| `backend/tests/unit/routers/test_portal_profile_update.py`   | Create | Tests for profile update                           |
| `apps/mouth/src/lib/api/portal/portal.api.ts`                | Modify | Add `updateProfile()` method                       |
| `apps/mouth/src/lib/api/portal/portal.types.ts`              | Modify | Add `UpdateProfileRequest` type                    |
| `apps/mouth/src/app/portal/(authenticated)/profile/page.tsx` | Modify | Add edit mode with save button                     |

---

### Task 1: Backend — Profile Update Endpoint

**Files:**

- Modify: `apps/backend-rag/backend/services/portal/portal_service.py`
- Modify: `apps/backend-rag/backend/app/routers/portal.py`
- Create: `apps/backend-rag/backend/tests/unit/routers/test_portal_profile_update.py`

- [ ] **Step 1: Write the failing test**

```python
# apps/backend-rag/backend/tests/unit/routers/test_portal_profile_update.py
"""Tests for portal profile update."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.services.portal.portal_service import PortalService


EDITABLE_FIELDS = {"phone", "whatsapp", "address", "language"}


@pytest.mark.asyncio
async def test_update_profile_updates_allowed_fields():
    """update_profile updates only whitelisted fields."""
    mock_conn = AsyncMock()
    mock_conn.execute.return_value = None
    mock_conn.fetchrow.return_value = {
        "id": 1, "full_name": "John", "email": "john@test.com",
        "phone": "+6281234567890", "whatsapp": "+6281234567890",
        "address": "Jl Raya Seminyak 123", "nationality": "US",
        "passport_number": "AB123", "passport_expiry": None,
        "date_of_birth": None, "gender": "M", "member_since": "2025-01-01",
        "assigned_to_email": None, "assigned_to_name": None, "assigned_to_avatar": None,
    }

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    service = PortalService(mock_pool)
    result = await service.update_profile(
        client_id=1,
        fields={"phone": "+6281234567890", "whatsapp": "+6281234567890", "address": "Jl Raya Seminyak 123"},
    )

    assert result is not None
    mock_conn.execute.assert_called_once()
    call_sql = mock_conn.execute.call_args[0][0]
    assert "phone" in call_sql
    assert "whatsapp" in call_sql
    assert "address" in call_sql


@pytest.mark.asyncio
async def test_update_profile_rejects_sensitive_fields():
    """update_profile ignores non-whitelisted fields like name, passport."""
    mock_conn = AsyncMock()
    mock_conn.execute.return_value = None
    mock_conn.fetchrow.return_value = {
        "id": 1, "full_name": "John", "email": "john@test.com",
        "phone": None, "whatsapp": None, "address": None, "nationality": "US",
        "passport_number": "AB123", "passport_expiry": None,
        "date_of_birth": None, "gender": "M", "member_since": "2025-01-01",
        "assigned_to_email": None, "assigned_to_name": None, "assigned_to_avatar": None,
    }

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    service = PortalService(mock_pool)
    result = await service.update_profile(
        client_id=1,
        fields={"full_name": "HACKED", "passport_number": "STOLEN", "phone": "+62999"},
    )

    assert result is not None
    call_sql = mock_conn.execute.call_args[0][0]
    assert "full_name" not in call_sql
    assert "passport_number" not in call_sql
    assert "phone" in call_sql


@pytest.mark.asyncio
async def test_update_profile_empty_fields_noop():
    """update_profile with no valid fields returns profile without updating."""
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {
        "id": 1, "full_name": "John", "email": "john@test.com",
        "phone": None, "whatsapp": None, "address": None, "nationality": "US",
        "passport_number": None, "passport_expiry": None,
        "date_of_birth": None, "gender": None, "member_since": "2025-01-01",
        "assigned_to_email": None, "assigned_to_name": None, "assigned_to_avatar": None,
    }

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    service = PortalService(mock_pool)
    result = await service.update_profile(
        client_id=1,
        fields={"full_name": "HACKED", "nationality": "RU"},
    )

    assert result is not None
    mock_conn.execute.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/unit/routers/test_portal_profile_update.py -v`
Expected: FAIL with AttributeError (update_profile doesn't exist)

- [ ] **Step 3: Add update_profile to PortalService**

Append to `PortalService` class in `apps/backend-rag/backend/services/portal/portal_service.py` (after `get_invoice_pdf_url`):

```python
    # ================================================
    # PROFILE UPDATE
    # ================================================

    PROFILE_EDITABLE_FIELDS = {"phone", "whatsapp", "address", "language"}

    async def update_profile(
        self,
        client_id: int,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Update client profile with whitelisted fields only.

        Sensitive fields (full_name, email, passport_number, nationality, etc.)
        are silently ignored — they require team intervention.

        Returns the updated profile in the same format as get_profile().
        """
        # Filter to only allowed fields
        safe_fields = {
            k: v for k, v in fields.items()
            if k in self.PROFILE_EDITABLE_FIELDS and v is not None
        }

        async with self.pool.acquire() as conn:
            if safe_fields:
                # Build dynamic SET clause
                set_parts = []
                params: list[Any] = []
                for i, (key, value) in enumerate(safe_fields.items(), start=1):
                    set_parts.append(f"{key} = ${i}")
                    params.append(value)

                params.append(client_id)
                set_clause = ", ".join(set_parts)

                await conn.execute(
                    f"UPDATE clients SET {set_clause}, updated_at = NOW() WHERE id = ${len(params)} AND deleted_at IS NULL",
                    *params,
                )

                logger.info(f"Portal profile updated for client {client_id}: {list(safe_fields.keys())}")

            # Return updated profile using existing get_profile logic
            return await self._get_profile_data(conn, client_id)

    async def _get_profile_data(self, conn: Any, client_id: int) -> dict[str, Any]:
        """Fetch profile data from DB (shared between get_profile and update_profile)."""
        row = await conn.fetchrow(
            """
            SELECT c.id, c.full_name, c.email, c.phone, c.whatsapp,
                   c.nationality, c.passport_number, c.passport_expiry,
                   c.date_of_birth, c.gender, c.address, c.created_at as member_since,
                   tm.email as assigned_to_email, tm.full_name as assigned_to_name,
                   tm.avatar_url as assigned_to_avatar
            FROM clients c
            LEFT JOIN team_members tm ON tm.email = c.assigned_to AND tm.active = true
            WHERE c.id = $1 AND c.deleted_at IS NULL
            """,
            client_id,
        )

        if not row:
            return {}

        return {
            "id": row["id"],
            "full_name": row["full_name"],
            "email": row["email"],
            "phone": row["phone"],
            "whatsapp": row["whatsapp"],
            "nationality": row["nationality"],
            "passport_number": row["passport_number"],
            "passport_expiry": str(row["passport_expiry"]) if row["passport_expiry"] else None,
            "date_of_birth": str(row["date_of_birth"]) if row["date_of_birth"] else None,
            "gender": row["gender"],
            "address": row["address"],
            "member_since": str(row["member_since"]) if row["member_since"] else None,
            "assigned_to": {
                "email": row["assigned_to_email"],
                "name": row["assigned_to_name"],
                "avatar_url": row["assigned_to_avatar"],
            } if row["assigned_to_email"] else None,
        }
```

- [ ] **Step 4: Add PATCH endpoint to portal.py**

In `apps/backend-rag/backend/app/routers/portal.py`, add after the existing profile GET endpoint:

```python
class UpdateProfileRequest(BaseModel):
    """Request to update client profile (only whitelisted fields)."""
    phone: str | None = None
    whatsapp: str | None = None
    address: str | None = None
    language: str | None = None


@router.patch("/profile")
async def update_profile(
    request: UpdateProfileRequest,
    client: dict = Depends(get_current_client),
    portal_service: PortalService = Depends(get_portal_service),
) -> dict[str, Any]:
    """Update client profile. Only phone, whatsapp, address, and language can be changed."""
    try:
        fields = {k: v for k, v in request.model_dump().items() if v is not None}
        result = await portal_service.update_profile(client["client_id"], fields)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Failed to update profile for client {client['client_id']}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update profile")
```

- [ ] **Step 5: Run tests**

Run: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/unit/routers/test_portal_profile_update.py -v`
Expected: 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add apps/backend-rag/backend/services/portal/portal_service.py apps/backend-rag/backend/app/routers/portal.py apps/backend-rag/backend/tests/unit/routers/test_portal_profile_update.py
git commit -m "feat(portal): add profile self-service editing with field whitelist"
```

---

### Task 2: Frontend — Profile Edit Mode

**Files:**

- Modify: `apps/mouth/src/lib/api/portal/portal.types.ts`
- Modify: `apps/mouth/src/lib/api/portal/portal.api.ts`
- Modify: `apps/mouth/src/app/portal/(authenticated)/profile/page.tsx`

- [ ] **Step 1: Add types and API method**

Append to `apps/mouth/src/lib/api/portal/portal.types.ts`:

```ts
// ============================================================================
// Profile Update Types
// ============================================================================

export interface UpdateProfileRequest {
  phone?: string;
  whatsapp?: string;
  address?: string;
  language?: string;
}
```

Add to `PortalApi` class in `portal.api.ts`:

```ts
  async updateProfile(data: UpdateProfileRequest): Promise<PortalProfile> {
    const response = await this.client.request<PortalApiResponse<any>>(
      "/api/portal/profile",
      { method: "PATCH", body: JSON.stringify(data) },
    );
    const d = response.data!;
    return {
      id: d.id,
      fullName: d.full_name,
      email: d.email,
      phone: d.phone,
      whatsapp: d.whatsapp,
      nationality: d.nationality,
      passportNumber: d.passport_number,
      passportExpiry: d.passport_expiry,
      dateOfBirth: d.date_of_birth,
      gender: d.gender,
      address: d.address,
      memberSince: d.member_since,
      assignedTo: d.assigned_to ? {
        email: d.assigned_to.email,
        name: d.assigned_to.name,
        avatarUrl: d.assigned_to.avatar_url,
      } : undefined,
    };
  }
```

Add `UpdateProfileRequest` to the import in `portal.api.ts`.

- [ ] **Step 2: Add edit mode to profile page**

In `apps/mouth/src/app/portal/(authenticated)/profile/page.tsx`, modify the `ProfilePage` component:

Add these state variables after existing state:

```tsx
const [isEditing, setIsEditing] = useState(false);
const [isSaving, setIsSaving] = useState(false);
const [editData, setEditData] = useState({
  phone: "",
  whatsapp: "",
  address: "",
});
```

Add this function after `loadProfile`:

```tsx
const handleEdit = () => {
  if (!profile) return;
  setEditData({
    phone: profile.phone || "",
    whatsapp: profile.whatsapp || "",
    address: profile.address || "",
  });
  setIsEditing(true);
};

const handleSave = async () => {
  try {
    setIsSaving(true);
    const updated = await api.portal.updateProfile({
      phone: editData.phone || undefined,
      whatsapp: editData.whatsapp || undefined,
      address: editData.address || undefined,
    });
    setProfile(updated);
    setIsEditing(false);
    // Toast success would go here if useToast has success method
  } catch (err) {
    error("Failed to update profile", "Please try again");
    logger.error("Failed to update portal profile", {}, err as Error);
  } finally {
    setIsSaving(false);
  }
};

const handleCancel = () => {
  setIsEditing(false);
};
```

Replace the info notice at the bottom of the page (the section that says "To update your profile information, please contact your account manager") with:

```tsx
{
  !isEditing ? (
    <section className="flex justify-end">
      <Button variant="outline" onClick={handleEdit}>
        Edit Profile
      </Button>
    </section>
  ) : (
    <section
      className="space-y-4 rounded-xl border p-6"
      style={{
        background: "rgba(30,30,35,0.7)",
        borderColor: "rgba(255,255,255,0.05)",
      }}
    >
      <h2 className="text-lg font-semibold">Edit Profile</h2>
      <div className="space-y-3">
        <div>
          <label
            htmlFor="edit-phone"
            className="text-xs mb-1 block"
            style={{ color: "var(--bz-text-2)" }}
          >
            Phone
          </label>
          <input
            id="edit-phone"
            type="tel"
            value={editData.phone}
            onChange={(e) =>
              setEditData((prev) => ({ ...prev, phone: e.target.value }))
            }
            className="w-full px-3 py-2 rounded-lg border text-sm"
            style={{
              background: "rgba(255,255,255,0.03)",
              borderColor: "rgba(255,255,255,0.05)",
              color: "var(--bz-text-1)",
            }}
          />
        </div>
        <div>
          <label
            htmlFor="edit-whatsapp"
            className="text-xs mb-1 block"
            style={{ color: "var(--bz-text-2)" }}
          >
            WhatsApp
          </label>
          <input
            id="edit-whatsapp"
            type="tel"
            value={editData.whatsapp}
            onChange={(e) =>
              setEditData((prev) => ({ ...prev, whatsapp: e.target.value }))
            }
            className="w-full px-3 py-2 rounded-lg border text-sm"
            style={{
              background: "rgba(255,255,255,0.03)",
              borderColor: "rgba(255,255,255,0.05)",
              color: "var(--bz-text-1)",
            }}
          />
        </div>
        <div>
          <label
            htmlFor="edit-address"
            className="text-xs mb-1 block"
            style={{ color: "var(--bz-text-2)" }}
          >
            Address
          </label>
          <textarea
            id="edit-address"
            value={editData.address}
            onChange={(e) =>
              setEditData((prev) => ({ ...prev, address: e.target.value }))
            }
            className="w-full px-3 py-2 rounded-lg border text-sm min-h-[80px]"
            style={{
              background: "rgba(255,255,255,0.03)",
              borderColor: "rgba(255,255,255,0.05)",
              color: "var(--bz-text-1)",
            }}
          />
        </div>
      </div>
      <div className="flex gap-2 justify-end">
        <Button variant="outline" onClick={handleCancel} disabled={isSaving}>
          Cancel
        </Button>
        <Button onClick={handleSave} disabled={isSaving}>
          {isSaving ? "Saving..." : "Save Changes"}
        </Button>
      </div>
    </section>
  );
}
```

Add `import { Button } from '@/components/ui/button';` if not already imported. Add `useState` if not in imports.

- [ ] **Step 3: Commit**

```bash
git add apps/mouth/src/lib/api/portal/portal.types.ts apps/mouth/src/lib/api/portal/portal.api.ts apps/mouth/src/app/portal/\(authenticated\)/profile/page.tsx
git commit -m "feat(portal): add profile self-service editing UI with phone, WhatsApp, address"
```

---

## Feature B: Chat Multi-Thread

### File Structure

| File                                                      | Action | Responsibility                         |
| --------------------------------------------------------- | ------ | -------------------------------------- |
| `apps/mouth/src/lib/api/portal/portal.types.ts`           | Modify | Add `practice_name` to PortalMessage   |
| `apps/mouth/src/app/portal/(authenticated)/chat/page.tsx` | Modify | Add thread tabs grouped by practice_id |

**Note:** The backend already returns `practice_id` and `practice_name` in messages. This is a frontend-only feature.

---

### Task 3: Frontend — Chat Thread Tabs

**Files:**

- Modify: `apps/mouth/src/lib/api/portal/portal.types.ts`
- Modify: `apps/mouth/src/app/portal/(authenticated)/chat/page.tsx`

- [ ] **Step 1: Update PortalMessage type**

In `apps/mouth/src/lib/api/portal/portal.types.ts`, the existing `PortalMessage` interface already has `practiceId?: number`. Add `practiceName`:

```ts
export interface PortalMessage {
  id: string;
  content: string;
  direction: "client_to_team" | "team_to_client";
  sentBy: string;
  subject?: string;
  practiceId?: number;
  practiceName?: string; // ADD THIS
  createdAt: string;
  readAt?: string;
}
```

- [ ] **Step 2: Add thread tabs to chat page**

In `apps/mouth/src/app/portal/(authenticated)/chat/page.tsx`:

Add state for active thread after existing state variables:

```tsx
const [activeThread, setActiveThread] = useState<number | null>(null); // null = "All"
```

After messages are loaded/sorted, compute the thread list:

```tsx
// Compute unique threads from messages
const threads = React.useMemo(() => {
  const threadMap = new Map<
    number | null,
    { id: number | null; name: string; unread: number; lastMessage: string }
  >();

  // "All" thread
  threadMap.set(null, {
    id: null,
    name: "All Messages",
    unread: 0,
    lastMessage: "",
  });

  for (const msg of messages) {
    const pid = msg.practiceId ?? null;
    if (pid !== null && !threadMap.has(pid)) {
      threadMap.set(pid, {
        id: pid,
        name: msg.practiceName || `Practice #${pid}`,
        unread: 0,
        lastMessage: "",
      });
    }
    if (msg.direction === "team_to_client" && !msg.readAt) {
      const t = threadMap.get(pid);
      if (t) t.unread++;
      const allT = threadMap.get(null);
      if (allT) allT.unread++;
    }
  }

  return Array.from(threadMap.values());
}, [messages]);

// Filter messages by active thread
const filteredMessages = React.useMemo(() => {
  if (activeThread === null) return messages;
  return messages.filter((m) => (m.practiceId ?? null) === activeThread);
}, [messages, activeThread]);
```

Add thread tab bar after the header section (after `{unreadCount > 0 && (...)}` block), before the Messages Container:

```tsx
{
  /* Thread Tabs */
}
{
  threads.length > 1 && (
    <div
      className="flex-shrink-0 flex gap-1 py-2 overflow-x-auto scrollbar-hide border-b"
      style={{ borderColor: "var(--bz-border)" }}
    >
      {threads.map((thread) => (
        <button
          key={thread.id ?? "all"}
          onClick={() => setActiveThread(thread.id)}
          className="px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors flex items-center gap-1.5"
          style={
            activeThread === thread.id
              ? {
                  background: "rgba(201,169,110,0.15)",
                  color: "var(--bz-accent-warm)",
                }
              : {
                  color: "var(--bz-text-2)",
                }
          }
        >
          {thread.name}
          {thread.unread > 0 && (
            <span
              className="px-1.5 py-0.5 rounded-full text-[10px] font-bold"
              style={{
                background: "rgba(201,169,110,0.2)",
                color: "var(--bz-accent-warm)",
              }}
            >
              {thread.unread}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
```

Replace `messages` with `filteredMessages` in the groupedMessages computation and in the rendering.

In the message input area, when sending a message and `activeThread` is a practice ID, pass it:

```tsx
const sentMessage = await api.portal.sendMessage({
  content: trimmedMessage,
  practiceId: activeThread ?? undefined,
});
```

- [ ] **Step 3: Commit**

```bash
git add apps/mouth/src/lib/api/portal/portal.types.ts apps/mouth/src/app/portal/\(authenticated\)/chat/page.tsx
git commit -m "feat(portal): add chat multi-thread tabs grouped by practice"
```

---

## Feature C: Notification Center

### File Structure

| File                                                       | Action | Responsibility                                                               |
| ---------------------------------------------------------- | ------ | ---------------------------------------------------------------------------- |
| `backend/app/routers/portal_notifications.py`              | Create | `GET /api/portal/notifications` + `POST /api/portal/notifications/{id}/read` |
| `backend/tests/unit/routers/test_portal_notifications.py`  | Create | Tests                                                                        |
| `backend/app/setup/router_registration.py`                 | Modify | Register router                                                              |
| `apps/mouth/src/lib/api/portal/portal.types.ts`            | Modify | Add `PortalNotification` type                                                |
| `apps/mouth/src/lib/api/portal/portal.api.ts`              | Modify | Add notification methods                                                     |
| `apps/mouth/src/hooks/usePortalNotifications.ts`           | Create | React Query hook with polling                                                |
| `apps/mouth/src/components/portal/PortalNotifications.tsx` | Modify | Populate existing scaffolded component                                       |

---

### Task 4: Backend — Notifications Endpoint

**Files:**

- Create: `apps/backend-rag/backend/app/routers/portal_notifications.py`
- Create: `apps/backend-rag/backend/tests/unit/routers/test_portal_notifications.py`
- Modify: `apps/backend-rag/backend/app/setup/router_registration.py`

- [ ] **Step 1: Write the failing test**

```python
# apps/backend-rag/backend/tests/unit/routers/test_portal_notifications.py
"""Tests for portal notifications endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.app.routers.portal_notifications import _get_notifications, _mark_read


@pytest.mark.asyncio
async def test_get_notifications_returns_list():
    """Notifications endpoint returns ordered list."""
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [
        {"id": 1, "type": "document_verified", "title": "Passport verified", "body": "Your passport has been verified", "data": "{}", "read_at": None, "created_at": "2026-03-30T10:00:00+00:00"},
        {"id": 2, "type": "status_changed", "title": "KITAS approved", "body": "Your visa application was approved", "data": "{}", "read_at": "2026-03-30T11:00:00+00:00", "created_at": "2026-03-29T10:00:00+00:00"},
    ]
    mock_conn.fetchval.return_value = 1  # unread count

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await _get_notifications(mock_pool, client_id=1, limit=50)

    assert len(result["notifications"]) == 2
    assert result["unread_count"] == 1
    assert result["notifications"][0]["title"] == "Passport verified"


@pytest.mark.asyncio
async def test_mark_read_updates_notification():
    """Mark read endpoint updates read_at timestamp."""
    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = 1  # rows affected

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await _mark_read(mock_pool, client_id=1, notification_id=1)
    assert result is True


@pytest.mark.asyncio
async def test_mark_read_returns_false_for_wrong_client():
    """Mark read returns False if notification doesn't belong to client."""
    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = 0  # no rows affected

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await _mark_read(mock_pool, client_id=999, notification_id=1)
    assert result is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/unit/routers/test_portal_notifications.py -v`

- [ ] **Step 3: Create the router**

```python
# apps/backend-rag/backend/app/routers/portal_notifications.py
"""
Portal Notifications Router.

Client notification center. Reads from portal_notifications table.
Gracefully returns empty if table doesn't exist.
"""

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.dependencies import get_database_pool
from backend.app.routers.portal import get_current_client
from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/portal/notifications", tags=["portal-notifications"])


async def _get_notifications(
    pool: asyncpg.Pool,
    client_id: int,
    limit: int = 50,
) -> dict[str, Any]:
    """Get notifications for a client. Returns empty if table doesn't exist."""
    async with pool.acquire() as conn:
        try:
            rows = await conn.fetch(
                """
                SELECT id, type, title, body, data, read_at, created_at
                FROM portal_notifications
                WHERE client_id = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                client_id,
                limit,
            )
            unread = await conn.fetchval(
                "SELECT COUNT(*) FROM portal_notifications WHERE client_id = $1 AND read_at IS NULL",
                client_id,
            )
        except Exception:
            return {"notifications": [], "unread_count": 0}

    return {
        "notifications": [
            {
                "id": r["id"],
                "type": r["type"],
                "title": r["title"],
                "body": r["body"],
                "data": r["data"],
                "read": r["read_at"] is not None,
                "created_at": str(r["created_at"]) if r["created_at"] else None,
            }
            for r in rows
        ],
        "unread_count": unread or 0,
    }


async def _mark_read(
    pool: asyncpg.Pool,
    client_id: int,
    notification_id: int,
) -> bool:
    """Mark a notification as read. Returns False if not found."""
    async with pool.acquire() as conn:
        try:
            affected = await conn.fetchval(
                "UPDATE portal_notifications SET read_at = NOW() WHERE id = $1 AND client_id = $2 AND read_at IS NULL RETURNING id",
                notification_id,
                client_id,
            )
            return affected is not None
        except Exception:
            return False


@router.get("")
async def get_notifications(
    client: dict = Depends(get_current_client),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    limit: int = Query(default=50, le=100),
) -> dict[str, Any]:
    """Get notifications for the authenticated client."""
    result = await _get_notifications(db_pool, client["client_id"], limit)
    return {"success": True, "data": result}


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    client: dict = Depends(get_current_client),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Mark a notification as read."""
    success = await _mark_read(db_pool, client["client_id"], notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"success": True}


@router.post("/read-all")
async def mark_all_read(
    client: dict = Depends(get_current_client),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Mark all notifications as read."""
    async with db_pool.acquire() as conn:
        try:
            await conn.execute(
                "UPDATE portal_notifications SET read_at = NOW() WHERE client_id = $1 AND read_at IS NULL",
                client["client_id"],
            )
        except Exception:
            pass
    return {"success": True}
```

- [ ] **Step 4: Run tests**

Run: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/unit/routers/test_portal_notifications.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Register the router**

Add to `apps/backend-rag/backend/app/setup/router_registration.py`:

```python
from backend.app.routers.portal_notifications import router as portal_notifications_router
app.include_router(portal_notifications_router)
```

- [ ] **Step 6: Commit**

```bash
git add apps/backend-rag/backend/app/routers/portal_notifications.py apps/backend-rag/backend/tests/unit/routers/test_portal_notifications.py apps/backend-rag/backend/app/setup/router_registration.py
git commit -m "feat(portal): add notifications endpoint with read/mark-all-read"
```

---

### Task 5: Frontend — Notification Hook + Popover

**Files:**

- Modify: `apps/mouth/src/lib/api/portal/portal.types.ts`
- Modify: `apps/mouth/src/lib/api/portal/portal.api.ts`
- Create: `apps/mouth/src/hooks/usePortalNotifications.ts`
- Modify: `apps/mouth/src/components/portal/PortalNotifications.tsx`

- [ ] **Step 1: Add types and API methods**

Append to `portal.types.ts`:

```ts
// ============================================================================
// Notification Types
// ============================================================================

export interface PortalNotification {
  id: number;
  type: string;
  title: string;
  body: string | null;
  data: string | null;
  read: boolean;
  created_at: string | null;
}

export interface NotificationsResponse {
  notifications: PortalNotification[];
  unread_count: number;
}
```

Add to `PortalApi` class in `portal.api.ts`:

```ts
  // ============================================================================
  // Notifications
  // ============================================================================

  async getNotifications(limit = 50): Promise<NotificationsResponse> {
    const response = await this.client.request<PortalApiResponse<NotificationsResponse>>(
      `/api/portal/notifications?limit=${limit}`,
      { method: "GET" },
    );
    return response.data!;
  }

  async markNotificationRead(notificationId: number): Promise<void> {
    await this.client.request<PortalApiResponse<void>>(
      `/api/portal/notifications/${notificationId}/read`,
      { method: "POST" },
    );
  }

  async markAllNotificationsRead(): Promise<void> {
    await this.client.request<PortalApiResponse<void>>(
      "/api/portal/notifications/read-all",
      { method: "POST" },
    );
  }
```

Add `NotificationsResponse` to the import.

- [ ] **Step 2: Create notification hook**

```ts
// apps/mouth/src/hooks/usePortalNotifications.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { NotificationsResponse } from "@/lib/api/portal/portal.types";

export function usePortalNotifications() {
  const queryClient = useQueryClient();

  const query = useQuery<NotificationsResponse>({
    queryKey: ["portal", "notifications"],
    queryFn: () => api.portal.getNotifications(50),
    refetchInterval: 60_000, // Poll every 60s
    staleTime: 30_000,
  });

  const markRead = useMutation({
    mutationFn: (id: number) => api.portal.markNotificationRead(id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["portal", "notifications"] }),
  });

  const markAllRead = useMutation({
    mutationFn: () => api.portal.markAllNotificationsRead(),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["portal", "notifications"] }),
  });

  return {
    notifications: query.data?.notifications ?? [],
    unreadCount: query.data?.unread_count ?? 0,
    isLoading: query.isLoading,
    markRead: markRead.mutate,
    markAllRead: markAllRead.mutate,
  };
}
```

- [ ] **Step 3: Populate PortalNotifications component**

Read `apps/mouth/src/components/portal/PortalNotifications.tsx`. It's already scaffolded with exports for `PortalNotificationsPopover`, `PortalNotificationsList`, `PortalNotificationBadge`. Replace the entire file content with a working implementation that uses `usePortalNotifications` hook, showing a bell icon with unread badge, and a popover dropdown with notification list.

The popover should show each notification with title, body, time ago, and a "Mark as read" action. Include a "Mark all as read" button at the top.

Use Warm Depth tokens and match existing portal card styling (`rgba(30,30,35,0.7)`, `rgba(255,255,255,0.05)` borders).

- [ ] **Step 4: Commit**

```bash
git add apps/mouth/src/lib/api/portal/portal.types.ts apps/mouth/src/lib/api/portal/portal.api.ts apps/mouth/src/hooks/usePortalNotifications.ts apps/mouth/src/components/portal/PortalNotifications.tsx
git commit -m "feat(portal): add notification center with polling, mark read, and popover"
```

---

## Summary

| Task | Feature       | Description                    | Backend | Frontend | Est.   |
| ---- | ------------- | ------------------------------ | ------- | -------- | ------ |
| 1    | Profile       | PATCH endpoint + PortalService | ✅      |          | 15 min |
| 2    | Profile       | Edit mode UI                   |         | ✅       | 15 min |
| 3    | Chat          | Multi-thread tabs by practice  |         | ✅       | 15 min |
| 4    | Notifications | Notifications endpoint + tests | ✅      |          | 15 min |
| 5    | Notifications | Hook + popover component       |         | ✅       | 15 min |

**Total: 5 tasks, ~75 minutes, 5 commits**

**Dependencies:**

- Task 2 depends on Task 1 (backend endpoint)
- Task 5 depends on Task 4 (backend endpoint)
- Task 3 is independent (frontend-only)
- `portal_notifications` table needs to be created in prod (endpoint gracefully returns empty if missing)

**Not in scope (Fase 3):**

- SSE real-time streaming (deferred — polling every 60s is sufficient MVP)
- Push notifications (service worker)
- Email digest
- Knowledge base page (/portal/help)
