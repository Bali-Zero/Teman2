# v2 Rollout — Sub-plan 04: L3 Team Ops + Polish (Sprint 4 + 5)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development o superpowers:executing-plans.
> **Blocked by:** sub-plan 01 (foundation) + 02 (funnel-hub) + 03 (client-app) merged.

**Goal:** Kita da feature-tabs a inbox-first workspace. CommandPalette Cmd+K. ContextPanel dx. Prime come "View as map" toggle in `/kita/clients`. Cleanup 4 app orfane satellite. Analytics funnel-view dashboard `/kita/analytics/funnel`.

**Architecture:** `/kita/inbox` diventa default post-login (middleware già ha pattern, va aggiornato `APP_DOMAIN` root → `/inbox`). Timeline omnichannel riusa `conversations.messages` già popolato. ContextPanel carica lazy su click.

**Worktree:** `.worktrees/v2-team-ops` on branch `v2-team-ops`.

**Note:** Sprint 4 + 5 insieme perché polish è piccolo (2gg). Split S4a/S4b se necessario in esecuzione.

---

## Task 1: Worktree + verify stack

- [ ] Create worktree, verify previous merges

```bash
cd ~/Desktop/nuzantara
git worktree add .worktrees/v2-team-ops -b v2-team-ops main
cd .worktrees/v2-team-ops
grep -q "CommandPalette" packages/core/index.ts && echo "✓ foundation"
test -d apps/mouth/src/app/portal/\(authenticated\)/family && echo "✓ client-app"
```

---

## Task 2: Federation pre-check L3 refactor

L3 tocca 17 route workspace + middleware. **Trigger obbligatorio (CLAUDE.md §2):** gemini explore before refactor.

- [ ] **Step 1:** Run

```bash
./scripts/ai-dispatch.sh gemini-explore "map dependencies of /kita/(workspace)/* routes and which share AppSidebar/Header components; identify which are safe to rename/replace"
```

- [ ] **Step 2:** Review output. If warnings on shared deps → adjust plan.

- [ ] **Step 3:** Commit findings (as .md in `docs/sessions/`)

---

## Task 3: New `/kita/inbox` route — omnichannel timeline

**Files:**

- Create: `apps/mouth/src/app/(workspace)/inbox/layout.tsx`
- Create: `apps/mouth/src/app/(workspace)/inbox/page.tsx`
- Create: `apps/mouth/src/components/workspace/InboxTimeline.tsx`
- Create: `apps/backend-rag/backend/app/routers/workspace_inbox.py`

- [ ] **Step 1:** Backend — query omnichannel messages

```python
# apps/backend-rag/backend/app/routers/workspace_inbox.py
"""Omnichannel unified feed for team workspace (/kita/inbox)."""
from fastapi import APIRouter, Depends, Query
from backend.app.dependencies import get_current_user, get_pg_pool

router = APIRouter(prefix="/api/workspace/inbox", tags=["workspace"])


@router.get("")
async def feed(
    user=Depends(get_current_user),
    pool=Depends(get_pg_pool),
    channel: str | None = Query(None),
    status: str | None = Query(None),
    client_id: str | None = Query(None),
    limit: int = Query(50, le=200),
):
    filters = []
    params: list = []
    if channel:
        filters.append(f"m.channel = ${len(params)+1}"); params.append(channel)
    if status:
        filters.append(f"c.status = ${len(params)+1}"); params.append(status)
    if client_id:
        filters.append(f"c.client_id = ${len(params)+1}"); params.append(client_id)
    # RBAC: team users see only assigned clients
    if user.get("role") != "admin":
        filters.append(f"c.assigned_to = ${len(params)+1}"); params.append(user["email"])
    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    sql = f"""
        SELECT m.id, m.channel, m.direction, m.content, m.created_at,
               c.client_id, c.status, cl.name AS client_name
        FROM messages m
        JOIN conversations c ON c.id = m.conversation_id
        LEFT JOIN clients cl ON cl.id = c.client_id
        {where}
        ORDER BY m.created_at DESC
        LIMIT {limit}
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)
    return {"items": [dict(r) for r in rows]}
```

Register router.

- [ ] **Step 2:** Frontend — timeline with filters

```tsx
// apps/mouth/src/components/workspace/InboxTimeline.tsx
"use client";
import { useEffect, useState } from "react";
type Item = {
  id: string;
  channel: string;
  direction: "inbound" | "outbound";
  content: string;
  created_at: string;
  client_name?: string;
};
export function InboxTimeline() {
  const [items, setItems] = useState<Item[]>([]);
  const [channel, setChannel] = useState("");
  useEffect(() => {
    const q = channel ? `?channel=${channel}` : "";
    fetch(`/api/workspace/inbox${q}`)
      .then((r) => r.json())
      .then((d) => setItems(d.items));
  }, [channel]);
  return (
    <div>
      <header>
        <select value={channel} onChange={(e) => setChannel(e.target.value)}>
          <option value="">Tutti i canali</option>
          <option value="whatsapp">WhatsApp</option>
          <option value="telegram">Telegram</option>
          <option value="instagram">Instagram</option>
          <option value="web">Web chat</option>
          <option value="email">Email</option>
        </select>
      </header>
      <ul style={{ listStyle: "none", padding: 0 }}>
        {items.map((it) => (
          <li
            key={it.id}
            style={{
              padding: "var(--space-3)",
              borderBottom: "1px solid var(--color-border-subtle)",
            }}
          >
            <div
              style={{
                display: "flex",
                gap: "var(--space-2)",
                color: "var(--color-text-secondary)",
                fontSize: "var(--font-size-sm)",
              }}
            >
              <span>{it.channel}</span>
              <span>·</span>
              <span>{new Date(it.created_at).toLocaleString()}</span>
              <span>·</span>
              <span>{it.client_name ?? "unknown"}</span>
            </div>
            <p>
              {it.direction === "inbound" ? "→ " : "← "}
              {it.content}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

```tsx
// apps/mouth/src/app/(workspace)/inbox/page.tsx
import { InboxTimeline } from "@/components/workspace/InboxTimeline";
export default function InboxPage() {
  return <InboxTimeline />;
}
```

- [ ] **Step 3:** Update middleware — redirect `/` → `/inbox` on `kita.balizero.com`

In `apps/mouth/src/middleware.ts` (workspace branch, ~line 388), replace:

```tsx
if (pathname === "/") {
  const redirectResponse = NextResponse.redirect(
    new URL("/login", request.url),
  );
  // ...
}
```

with (after login gate):

```tsx
// Authenticated root → /inbox (new default), not /dashboard
if (pathname === "/") {
  const redirectResponse = NextResponse.redirect(
    new URL("/inbox", request.url),
  );
  // …
}
```

- [ ] **Step 4:** Commit

```bash
git commit -m "feat(kita): inbox-first default route + omnichannel feed API"
```

---

## Task 4: Cmd+K palette in kita

**Files:**

- Create: `apps/mouth/src/components/workspace/KitaCommandPalette.tsx`
- Modify: `apps/mouth/src/app/(workspace)/layout.tsx`

- [ ] **Step 1:** Wire CommandPalette with app-specific actions

```tsx
// apps/mouth/src/components/workspace/KitaCommandPalette.tsx
"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CommandPalette, type CommandAction } from "@balizero/core";

export function KitaCommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const actions: CommandAction[] = [
    {
      id: "go-inbox",
      label: "Vai a inbox",
      group: "Navigazione",
      run: () => router.push("/inbox"),
    },
    {
      id: "go-clients",
      label: "Clienti",
      group: "Navigazione",
      run: () => router.push("/clients"),
    },
    {
      id: "go-prime",
      label: "Apri Prime 3D",
      group: "Navigazione",
      run: () => window.open("https://prime.balizero.com/", "_blank"),
    },
    {
      id: "create-kitas",
      label: "Crea pratica KITAS",
      group: "Pratiche",
      run: () => router.push("/process/new?type=kitas"),
    },
    {
      id: "create-pt",
      label: "Crea pratica PT Setup",
      group: "Pratiche",
      run: () => router.push("/process/new?type=pt_setup"),
    },
    {
      id: "export-lkpm",
      label: "Esporta LKPM Q1",
      group: "Tax",
      run: () => router.push("/lkpm"),
    },
    {
      id: "open-ga4",
      label: "Apri analytics funnel",
      group: "Analytics",
      run: () => router.push("/analytics/funnel"),
    },
  ];

  return (
    <CommandPalette
      open={open}
      actions={actions}
      onClose={() => setOpen(false)}
    />
  );
}
```

- [ ] **Step 2:** Add `<KitaCommandPalette />` to `(workspace)/layout.tsx`

- [ ] **Step 3:** Commit

```bash
git commit -m "feat(kita): Cmd+K command palette with 7 actions"
```

---

## Task 5: ContextPanel dx in `/kita/clients`

- [ ] **Step 1:** Add state `selectedClientId`

- [ ] **Step 2:** On row click, set selectedClientId and show `<ContextPanel open tabs={...} />`

```tsx
const tabs = [
  {
    id: "info",
    label: "Info",
    render: () => <ClientInfo id={selectedClientId} />,
  },
  {
    id: "matter",
    label: "Matter",
    render: () => <ClientMatters id={selectedClientId} />,
  },
  {
    id: "visa",
    label: "Visa",
    render: () => <ClientVisa id={selectedClientId} />,
  },
  {
    id: "tax",
    label: "Tax",
    render: () => <ClientTax id={selectedClientId} />,
  },
  {
    id: "docs",
    label: "Docs",
    render: () => <ClientDocs id={selectedClientId} />,
  },
  {
    id: "prime",
    label: "Prime",
    render: () => <ClientPrime id={selectedClientId} />,
  },
];
```

Each sub-component fetches its data lazily.

- [ ] **Step 3:** Commit

```bash
git commit -m "feat(kita): ContextPanel right-side with 6 lazy tabs"
```

---

## Task 6: Prime "View as map" toggle in `/kita/clients`

- [ ] **Step 1:** Add view selector (List | Map | Pipeline) in clients page header

- [ ] **Step 2:** Map mode: mount `<PrimeNexusLayout mode="crm" />` (already implemented per memoria #103/#124) with clients markers

- [ ] **Step 3:** Commit

```bash
git commit -m "feat(kita): Prime map view toggle in /clients"
```

---

## Task 7: Zantara inline suggestions

**Files:**

- Create: `apps/mouth/src/components/workspace/ZantaraSuggestTile.tsx`

- [ ] **Step 1:** For each inbound message in InboxTimeline, fetch `/api/zantara/suggest` with message context

- [ ] **Step 2:** Render 3 reply buttons: Accept / Edit / Reject. Accept sends via channel adapter, Edit opens input prefilled, Reject dismisses.

- [ ] **Step 3:** Commit

---

## Task 8: Analytics funnel-view dashboard

**Files:**

- Create: `apps/mouth/src/app/(workspace)/analytics/funnel/page.tsx`
- Create: `apps/backend-rag/backend/app/routers/workspace_analytics.py`

- [ ] **Step 1:** Backend query for funnel attribution

```python
# apps/backend-rag/backend/app/routers/workspace_analytics.py
@router.get("/funnel")
async def funnel_view(pool=Depends(get_pg_pool), user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "admin only")
    async with pool.acquire() as conn:
        sessions = await conn.fetch("SELECT funnel, COUNT(*) AS n FROM funnel_sessions GROUP BY funnel")
        conversions = await conn.fetch("""
            SELECT first_funnel AS funnel, COUNT(*) AS n
            FROM funnel_attributions GROUP BY first_funnel
        """)
    return {"sessions": [dict(r) for r in sessions], "conversions": [dict(r) for r in conversions]}
```

- [ ] **Step 2:** Frontend — bar chart (use `@nivo/bar` already in deps)

- [ ] **Step 3:** Commit

```bash
git commit -m "feat(kita): /analytics/funnel — sessions→conversions dashboard"
```

---

## Task 9: Cleanup 4 satellite apps

Verificato: mail/calendar/drive/knowledge subdomain redirect via middleware → kita interne. Apps in `apps/{mail,calendar,drive,knowledge}/` non hanno uso di `@balizero/core` (0 ref) e non ricevono traffic in prod.

- [ ] **Step 1:** Federation check — gemini explore

```bash
./scripts/ai-dispatch.sh gemini-explore "grep for any import or reference to apps/mail, apps/calendar, apps/drive, apps/knowledge anywhere in the monorepo outside their own directories; list findings"
```

- [ ] **Step 2:** If findings empty → proceed. If findings exist → document in `docs/sessions/` and skip cleanup.

- [ ] **Step 3:** Delete app directories + Vercel project unlinks (manual dashboard step)

```bash
rm -rf apps/mail apps/calendar apps/drive apps/knowledge
```

Update root `package.json` workspaces list if explicitly lists them.

- [ ] **Step 4:** Commit

```bash
git commit -m "chore: remove 4 orphan satellite apps (unreachable in prod, middleware redirect to kita)"
```

---

## Task 10: Polish — remove hardcoded theme references

Ricerca residui `className="dark"` o import diretti di `globals.css`/`kbli-theme.css`.

- [ ] **Step 1:** Grep

```bash
grep -rn 'className="dark"' apps/mouth/src/
grep -rn 'kbli-theme.css' apps/mouth/src/
grep -rn 'import.*globals.css' apps/mouth/src/
```

- [ ] **Step 2:** Per ogni match: sostituisci con `ThemeScope`/`ThemeProvider` o rimuovi se obsoleto

- [ ] **Step 3:** Commit

---

## Task 11: Lighthouse final audit

- [ ] Run Lighthouse su tutti i target:
  - balizero.com, visa., /kbli, tax., /property (target 95+)
  - my., prime/proposal/demo-token, zantara. (target 85+)
  - kita./inbox, kita./analytics/funnel (target 85+)

- [ ] Document in `docs/sessions/2026-04-17-v2-rollout-lighthouse.md`

---

## Task 12: Final merge

- [ ] All tests green, typecheck clean, lighthouse targets met

- [ ] Merge

```bash
git checkout main && git merge --no-ff v2-team-ops
git push origin main  # solo con autorizzazione user
```

- [ ] Save MOS memory:

```bash
~/.claude/scripts/mem save decision "v2 Rollout 3-Layer completato: L1 Funnel Hub (5 tool), L2 Client App (portal matter-first + WA push), L3 Team Ops (inbox + Cmd+K + Prime toggle + analytics funnel). 4 satellite orfane rimosse. $(git log --oneline main~$(git log --oneline v2-foundation..main|wc -l) -1)" 10
```

---

## Exit criteria

- ✅ `/kita/inbox` = default post-login, omnichannel timeline funzionante
- ✅ Cmd+K palette operativa
- ✅ ContextPanel dx su /clients
- ✅ Prime "View as map" toggle live
- ✅ /analytics/funnel live (admin only)
- ✅ 4 app orfane rimosse
- ✅ Zero `className="dark"` hardcoded residuo
- ✅ Lighthouse targets met
- ✅ Roll-out 3-layer completato, MOS saved
