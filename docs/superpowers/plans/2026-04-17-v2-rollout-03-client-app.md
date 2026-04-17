# v2 Rollout — Sub-plan 03: L2 Client App (Sprint 3)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development o superpowers:executing-plans.
> **Blocked by:** sub-plan 01 (foundation) merged.

**Goal:** Trasformare `my.balizero.com/portal/*` da feature-tabs a matter-first dashboard. 3 hero cards sempre visibili. WA push opt-in. Family route. Riallineare theme `prime/proposal/[token]` e `zantara.balizero.com` a `operative-light`.

**Architecture:** Portal home con 3 hero card + lista MatterCard. Dati da 3 endpoint esistenti o nuovi (`api/portal/dashboard-summary`). Notification prefs via migration 110 + endpoint GET/PUT. Cron `portal_deadline_watchdog.py` ogni 6h scansiona `lkpm_reports.due_date`, `clients.visa_expiry_date` e invia WA via template esistente.

**Worktree:** `.worktrees/v2-client-app` on branch `v2-client-app`.

---

## Task 1: Worktree + verify

- [ ] Create worktree, verify foundation+funnel-hub merged

```bash
cd ~/Desktop/nuzantara
git worktree add .worktrees/v2-client-app -b v2-client-app main
cd .worktrees/v2-client-app
grep -q "MatterCard" packages/core/index.ts && echo "✓ foundation merged"
test -d apps/mouth/src/app/\(tax-calendar\)/ && echo "✓ funnel-hub merged"
```

---

## Task 2: Portal dashboard summary endpoint

**Files:**

- Create: `apps/backend-rag/backend/app/routers/portal_dashboard.py`
- Create: `apps/backend-rag/backend/tests/app/routers/test_portal_dashboard.py`

- [ ] **Step 1:** Write test — 3 sections in response

```python
def test_dashboard_summary_returns_three_sections(client, auth_client_token):
    r = client.get("/api/portal/dashboard/summary", headers={"Authorization": f"Bearer {auth_client_token}"})
    assert r.status_code == 200
    body = r.json()
    assert "open_actions" in body      # card A
    assert "upcoming_deadlines" in body # card B
    assert "unread_messages" in body   # card C
    assert isinstance(body["open_actions"], list)
```

- [ ] **Step 2:** Implement

```python
# apps/backend-rag/backend/app/routers/portal_dashboard.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from backend.app.dependencies import get_current_user, get_pg_pool

router = APIRouter(prefix="/api/portal/dashboard", tags=["portal"])


@router.get("/summary")
async def summary(user=Depends(get_current_user), pool=Depends(get_pg_pool)):
    async with pool.acquire() as conn:
        open_actions = await conn.fetch("""
            SELECT m.id, m.title, m.type, m.pending_from_client
            FROM client_matters m
            WHERE m.client_id = $1 AND m.pending_from_client IS NOT NULL
            ORDER BY m.updated_at DESC LIMIT 10
        """, user["client_id"])
        deadlines = await conn.fetch("""
            SELECT id, label, due_date, kind FROM (
                SELECT id, 'Visa expiry' AS label, visa_expiry_date AS due_date, 'visa' AS kind
                FROM clients WHERE id = $1 AND visa_expiry_date IS NOT NULL
                UNION ALL
                SELECT id::text, label, due_date, kind
                FROM lkpm_reports WHERE client_id = $1 AND due_date > NOW() AND due_date < NOW() + INTERVAL '30 days'
            ) t ORDER BY due_date ASC LIMIT 10
        """, user["client_id"])
        unread = await conn.fetchval("""
            SELECT COUNT(*) FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE c.client_id = $1 AND m.read_at IS NULL AND m.direction = 'inbound'
        """, user["client_id"])
    return {
        "open_actions": [dict(r) for r in open_actions],
        "upcoming_deadlines": [dict(r) for r in deadlines],
        "unread_messages": unread or 0,
    }
```

- [ ] **Step 3:** Register router, run test — pass, commit

```bash
git commit -m "feat(api): portal dashboard summary (3 hero cards data)"
```

---

## Task 3: Portal home — 3 hero cards

**Files:**

- Modify: `apps/mouth/src/app/portal/(authenticated)/page.tsx` (or create if root)

- [ ] **Step 1:** Fetch dashboard/summary, render 3 cards

```tsx
// apps/mouth/src/app/portal/(authenticated)/page.tsx
import { cookies } from "next/headers";
import { ProgressRing, DeadlineBadge } from "@balizero/core";

async function getSummary() {
  const jwt = cookies().get("nz_access_token")?.value;
  const res = await fetch(
    `${process.env.API_URL}/api/portal/dashboard/summary`,
    {
      headers: { Authorization: `Bearer ${jwt}` },
      cache: "no-store",
    },
  );
  return res.json();
}

export default async function PortalHomePage() {
  const s = await getSummary();
  const empty =
    s.open_actions.length === 0 &&
    s.upcoming_deadlines.length === 0 &&
    (s.unread_messages ?? 0) === 0;

  if (empty) {
    return (
      <div style={{ padding: "var(--space-8)", textAlign: "center" }}>
        <h1>Tutto a posto ✓</h1>
        <p>Nessuna azione aperta, nessuna deadline nei prossimi 30 giorni.</p>
      </div>
    );
  }

  return (
    <section
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(3, 1fr)",
        gap: "var(--space-6)",
        padding: "var(--space-6)",
      }}
    >
      <article className="card">
        <h2>Azioni aperte</h2>
        <ul>
          {s.open_actions.map((a: any) => (
            <li key={a.id}>
              <a href={`/portal/matters/${a.id}`}>{a.title}</a>
            </li>
          ))}
        </ul>
      </article>
      <article className="card">
        <h2>Deadline 30 giorni</h2>
        <ul style={{ display: "grid", gap: "var(--space-3)" }}>
          {s.upcoming_deadlines.map((d: any) => (
            <li
              key={d.id}
              style={{
                display: "flex",
                gap: "var(--space-3)",
                alignItems: "center",
              }}
            >
              <DeadlineBadge date={new Date(d.due_date)} />
              <span>{d.label}</span>
            </li>
          ))}
        </ul>
        <a href="/api/portal/deadlines/ical" download>
          Export iCal
        </a>
      </article>
      <article className="card">
        <h2>Messaggi team</h2>
        <p>
          <strong>{s.unread_messages}</strong> non letti
        </p>
        <a href="/portal/messages" className="btn">
          Apri
        </a>
      </article>
    </section>
  );
}
```

- [ ] **Step 2:** Commit

```bash
git commit -m "feat(portal): 3 hero cards dashboard (matter-first home)"
```

---

## Task 4: Portal deadlines iCal export

- [ ] **Step 1:** Create `apps/mouth/src/app/api/portal/deadlines/ical/route.ts`

```ts
import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { toIcalString } from "@balizero/core/utils";

export async function GET() {
  const jwt = cookies().get("nz_access_token")?.value;
  const res = await fetch(
    `${process.env.API_URL}/api/portal/dashboard/summary`,
    {
      headers: { Authorization: `Bearer ${jwt}` },
      cache: "no-store",
    },
  );
  const { upcoming_deadlines } = await res.json();
  const ics = toIcalString(
    upcoming_deadlines.map((d: any) => ({
      uid: `balizero-portal-${d.id}@balizero.com`,
      summary: d.label,
      start: new Date(d.due_date),
      end: new Date(new Date(d.due_date).getTime() + 86400_000),
      description: d.kind ?? "",
    })),
    { prodId: "BaliZero//Portal//EN" },
  );
  return new NextResponse(ics, {
    headers: {
      "Content-Type": "text/calendar; charset=utf-8",
      "Content-Disposition": 'attachment; filename="balizero-deadlines.ics"',
    },
  });
}
```

- [ ] **Step 2:** Commit

---

## Task 5: MatterCard list route `/portal/matters`

**Files:**

- Create: `apps/mouth/src/app/portal/(authenticated)/matters/page.tsx`

- [ ] **Step 1:** Create endpoint `/api/portal/matters` in `apps/backend-rag/backend/app/routers/portal_matters.py`:

```python
@router.get("/api/portal/matters")
async def list_matters(user=Depends(get_current_user), pool=Depends(get_pg_pool)):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, title, type, progress, pending_docs, next_deadline, next_step
            FROM client_matters WHERE client_id = $1 ORDER BY updated_at DESC
        """, user["client_id"])
    return {"matters": [dict(r) for r in rows]}
```

If `client_matters` table/view doesn't exist yet, create via migration 111 that unions existing `crm_practices` + `lkpm_reports` + visa state into a logical "matter" view.

- [ ] **Step 2:** Render as vertical stack of `<MatterCard>` from `@balizero/core`

```tsx
import { MatterCard } from "@balizero/core";
// ...
{
  matters.map((m) => (
    <MatterCard
      key={m.id}
      title={m.title}
      type={m.type}
      progressPercent={m.progress}
      pendingDocs={m.pending_docs}
      nextDeadline={m.next_deadline ? new Date(m.next_deadline) : undefined}
      nextStep={m.next_step}
      action={
        <a href={`/portal/matters/${m.id}`} className="btn">
          Apri
        </a>
      }
    />
  ));
}
```

- [ ] **Step 3:** Commit

---

## Task 6: Notification prefs endpoints + UI

**Files:**

- Create: `apps/backend-rag/backend/app/routers/portal_notification_prefs.py`
- Create: `apps/mouth/src/app/portal/(authenticated)/settings/notifications/page.tsx`

- [ ] **Step 1:** GET `/api/portal/notifications/prefs` returns current

- [ ] **Step 2:** PUT same accepts `{email_enabled, wa_enabled, wa_phone}`

- [ ] **Step 3:** UI: two toggles + phone input (validation E.164)

- [ ] **Step 4:** Commit

```bash
git commit -m "feat(portal): notification prefs (email/WA opt-in)"
```

---

## Task 7: WA push cron — portal_deadline_watchdog

**Files:**

- Create: `apps/backend-rag/scripts/portal_deadline_watchdog.py`
- Modify: OpenClaw cron catalog (Pro) or `scripts/automation_catalog.json`

- [ ] **Step 1:** Implementation

```python
# apps/backend-rag/scripts/portal_deadline_watchdog.py
"""Every 6h: scan deadlines within 30 days, for users with wa_enabled send WA."""
from __future__ import annotations
import asyncio, asyncpg, os, httpx, logging

logger = logging.getLogger(__name__)
API_URL = os.environ["API_URL"]
API_KEY = os.environ["ZANTARA_API_KEY"]

async def main():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    rows = await conn.fetch("""
        SELECT u.id, u.email, np.wa_phone, d.label, d.due_date
        FROM notification_prefs np
        JOIN users u ON u.id = np.user_id
        JOIN lkpm_reports d ON d.client_id = u.client_id
        WHERE np.wa_enabled = TRUE AND np.wa_phone IS NOT NULL
        AND d.due_date BETWEEN NOW() AND NOW() + INTERVAL '30 days'
        AND NOT EXISTS (
            SELECT 1 FROM notification_log l
            WHERE l.user_id = u.id AND l.ref = d.id::text AND l.sent_at > NOW() - INTERVAL '7 days'
        )
    """)
    async with httpx.AsyncClient(timeout=10) as http:
        for r in rows:
            await http.post(f"{API_URL}/api/whatsapp/send",
                headers={"X-API-Key": API_KEY},
                json={"phone": r["wa_phone"], "template": "deadline_reminder",
                      "params": {"label": r["label"], "date": r["due_date"].isoformat()}})
            await conn.execute(
                "INSERT INTO notification_log (user_id, channel, ref, sent_at) VALUES ($1,'wa',$2,NOW())",
                r["id"], str(r["due_date"]),
            )
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2:** Add to automation catalog (Pro cron, every 6h)

- [ ] **Step 3:** Commit

```bash
git commit -m "feat(portal): WA push cron portal_deadline_watchdog (6h)"
```

---

## Task 8: Family profile route

**Files:**

- Create: `apps/mouth/src/app/portal/(authenticated)/family/page.tsx`

- [ ] **Step 1:** Query `crm_clients` where `family_parent_id = current_user.client_id`

- [ ] **Step 2:** Show list of family members, separated by `is_adult` boolean

- [ ] **Step 3:** Per minor: inline edit nome, data nascita, passport upload
      Per adult: link to their own profile

- [ ] **Step 4:** Commit

---

## Task 9: Prime proposal theme riallineato

**Files:**

- Modify: `apps/mouth/src/app/prime/proposal/[token]/page.tsx` (and/or layout)

- [ ] **Step 1:** Add `ThemeScope theme="operative-light"` wrapper (already exported from core)

- [ ] **Step 2:** Add `CTAHandoff` sticky bottom with WA deeplink pre-compiled with proposal token

- [ ] **Step 3:** Commit

---

## Task 10: Zantara. matter-context pane

**Files:**

- Modify: `apps/mouth/src/app/chat/layout.tsx`

- [ ] **Step 1:** Wrap in `ThemeScope theme="operative-light"` (for auth users) or `editorial` (anon)

- [ ] **Step 2:** Add right-side `ContextPanel` collassabile, tabs: Info / Active matters

- [ ] **Step 3:** Commit

---

## Task 11: Bundle audit portal

- [ ] **Step 1:** Run bundle analyzer

```bash
cd apps/mouth && ANALYZE=true npm run build -- --analyze
```

- [ ] **Step 2:** Identify top 5 contributors to `/portal/(authenticated)/clients` bundle

- [ ] **Step 3:** Wrap heavy panels in `dynamic(() => import(), { ssr: false })`

Target: initial bundle < 300KB.

- [ ] **Step 4:** Verify with Lighthouse that `/portal` first-load is < 300KB

- [ ] **Step 5:** Commit

```bash
git commit -m "perf(portal): dynamic imports to fix ERR_INSUFFICIENT_RESOURCES"
```

---

## Task 12: QA + merge

- [ ] **Step 1:** Browser QA via `mcp__claude-in-chrome__*` — 3 screenshots (portal home, matters, prime/proposal)
- [ ] **Step 2:** Run all tests green
- [ ] **Step 3:** Merge

```bash
git checkout main && git merge --no-ff v2-client-app
```

---

## Exit criteria

- ✅ Portal home = 3 hero cards
- ✅ `/portal/matters` = MatterCard list
- ✅ WA push opt-in funzionante (cron live)
- ✅ `/portal/family` operativo
- ✅ Prime proposal + zantara. su operative-light theme
- ✅ Portal bundle < 300KB, no più ERR_INSUFFICIENT_RESOURCES
