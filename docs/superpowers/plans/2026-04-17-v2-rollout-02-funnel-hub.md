# v2 Rollout — Sub-plan 02: L1 Funnel Hub (Sprint 2)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development o superpowers:executing-plans.
> **Blocked by:** `2026-04-17-v2-rollout-01-foundation.md` completato + merged in main.

**Goal:** Portare i 4 funnel su `FunnelFrame`, unificare le loro nav via `NavShell` persona=editorial, creare 2 nuovi tool (Tax Calendar, Property), collegare homepage ai tool reali, usare cookie `bz_session` + session-bridge per cross-funnel memory.

**Architecture:** Ogni funnel diventa `<FunnelFrame funnel="…" sessionId={…}><ToolBody /></FunnelFrame>`. Il session_id generato da `getOrCreateSessionId()` (lato client) e `attachToServerSession({funnel})` chiamato al mount. CTAHandoff preconfigurato con canonical WA `+628213107363`.

**Tech Stack:** Next.js 16 route groups, middleware rewrite pattern visa-oracle, Vercel domain per `tax.balizero.com`, `@balizero/core`.

**Worktree:** `.worktrees/v2-funnel-hub` on branch `v2-funnel-hub`.

---

## Task 1: Worktree + verify foundation

- [ ] Create worktree, verify foundation merged

```bash
cd ~/Desktop/nuzantara
git worktree add .worktrees/v2-funnel-hub -b v2-funnel-hub main
cd .worktrees/v2-funnel-hub
grep -q "MatterCard" packages/core/index.ts && echo "✓ foundation merged"
npm install
```

Expected: `✓ foundation merged`.

---

## Task 2: Homepage FunnelFeature link fix

**File:** `apps/mouth/src/app/v2/_components/FunnelFeature.tsx:1-50` (find href)

- [ ] **Step 1:** Search for `href={\`/services`

```bash
grep -n "href={" apps/mouth/src/app/v2/_components/FunnelFeature.tsx
```

- [ ] **Step 2:** Replace link map — open file, find the `href={\`/services/\${funnel === "kbli" ? "company" : funnel}\`}` pattern, substitute with:

```tsx
const FUNNEL_HREF: Record<string, string> = {
  visa: "https://visa.balizero.com/",
  kbli: "/kbli",
  tax: "https://tax.balizero.com/",
  property: "/property",
};
// ... and use FUNNEL_HREF[funnel]
```

- [ ] **Step 3:** Commit

```bash
git add apps/mouth/src/app/v2/_components/FunnelFeature.tsx
git commit -m "feat(mouth): homepage funnel CTAs link to real tools"
```

---

## Task 3: Visa Oracle → FunnelFrame (port v1 → v2)

**Files:**

- Modify: `apps/mouth/src/app/(visa-oracle)/visa-oracle/layout.tsx`
- Modify: `apps/mouth/src/app/(visa-oracle)/visa-oracle/page.tsx`

- [ ] **Step 1:** Wrap layout with FunnelFrame + NavShell persona=editorial

```tsx
// apps/mouth/src/app/(visa-oracle)/visa-oracle/layout.tsx
import { NavShell, BZLogo } from "@balizero/core";
import { SessionInit } from "@/components/funnel/SessionInit";

export default function VisaOracleLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <NavShell
        logo={<BZLogo variant="dark" />}
        items={[
          { label: "Home", href: "https://balizero.com/" },
          { label: "KBLI", href: "/kbli" },
          { label: "Tax", href: "https://tax.balizero.com/" },
        ]}
        actions={
          <a href="https://wa.me/628213107363" className="btn btn-primary">
            WhatsApp
          </a>
        }
      />
      <SessionInit funnel="visa" />
      {children}
    </>
  );
}
```

- [ ] **Step 2:** Create `SessionInit` component

```tsx
// apps/mouth/src/components/funnel/SessionInit.tsx
"use client";
import { useEffect } from "react";
import {
  getOrCreateSessionId,
  attachToServerSession,
} from "@balizero/core/auth";

export function SessionInit({
  funnel,
}: {
  funnel: "visa" | "kbli" | "tax" | "property";
}) {
  useEffect(() => {
    getOrCreateSessionId();
    attachToServerSession({ funnel });
  }, [funnel]);
  return null;
}
```

- [ ] **Step 3:** Update page.tsx to wrap content in `FunnelFrame`

```tsx
// apps/mouth/src/app/(visa-oracle)/visa-oracle/page.tsx (pseudo-diff)
import { FunnelFrame, getOrCreateSessionId } from "@balizero/core";
// ... existing imports
// wrap the main body:
return (
  <FunnelFrame
    funnel="visa"
    sessionId={getOrCreateSessionId()}
    trust={{ clientCount: 5000, rating: 4.9, responseMinutes: 15 }}
  >
    {/* existing quiz + chat + result body */}
  </FunnelFrame>
);
```

- [ ] **Step 4:** Typecheck + build

```bash
npm run typecheck -w apps/mouth
```

- [ ] **Step 5:** Commit

```bash
git add apps/mouth/src/app/\(visa-oracle\)/ apps/mouth/src/components/funnel/
git commit -m "feat(visa): migrate Visa Oracle to FunnelFrame + NavShell editorial"
```

---

## Task 4: KBLI → FunnelFrame

**Files:**

- Modify: `apps/mouth/src/app/kbli/layout.tsx`
- Modify: `apps/mouth/src/app/kbli/page.tsx`
- Modify: `apps/mouth/src/app/kbli/[code]/page.tsx`

- [ ] **Step 1:** Same NavShell+SessionInit pattern as Task 3, funnel="kbli"

- [ ] **Step 2:** Rimuovi `kbli-theme.css` import dal layout (se presente), usa solo `@balizero/core` tokens

- [ ] **Step 3:** In `page.tsx` (listing) + `[code]/page.tsx` avvolgi il contenuto in `<FunnelFrame funnel="kbli" …>`

- [ ] **Step 4:** Fix gap visivo pre-existing (memoria #480) — in `[code]/page.tsx` ispeziona classe layout tra description e licensing section, rimuovi margin inspiegabili.

- [ ] **Step 5:** Aggiungi compare-2-codici modal (stretch) OR skip

- [ ] **Step 6:** Commit

```bash
git add apps/mouth/src/app/kbli/
git commit -m "feat(kbli): FunnelFrame + remove kbli-theme.css, fix layout gap"
```

---

## Task 5: Tax Calendar — nuovo dominio + route group

**Files:**

- Create: `apps/mouth/src/app/(tax-calendar)/tax-calendar/layout.tsx`
- Create: `apps/mouth/src/app/(tax-calendar)/tax-calendar/page.tsx`
- Create: `apps/mouth/src/components/funnel/TaxCalendarBody.tsx`
- Create: `apps/mouth/src/app/api/tax-calendar/deadlines/route.ts`
- Create: `apps/mouth/src/app/api/tax-calendar/ical/route.ts`
- Modify: `apps/mouth/src/middleware.ts` (add TAX_DOMAIN rewrite)

- [ ] **Step 1:** Add middleware rewrite

In `apps/mouth/src/middleware.ts`, after `ZANTARA_DOMAIN` block (line ~264):

```tsx
const TAX_DOMAIN = "tax.balizero.com";

if (hostname === TAX_DOMAIN || hostname === `www.${TAX_DOMAIN}`) {
  const rewriteUrl = request.nextUrl.clone();
  if (pathname === "/" || pathname === "") {
    rewriteUrl.pathname = "/tax-calendar";
  } else if (!pathname.startsWith("/tax-calendar")) {
    rewriteUrl.pathname = `/tax-calendar${pathname}`;
  }
  return NextResponse.rewrite(rewriteUrl);
}
```

- [ ] **Step 2:** Create layout + page in route group `(tax-calendar)`

```tsx
// apps/mouth/src/app/(tax-calendar)/tax-calendar/layout.tsx
import { NavShell, BZLogo } from "@balizero/core";
import { SessionInit } from "@/components/funnel/SessionInit";

export const metadata = {
  title: "Tax Compliance Calendar · Bali Zero",
  description: "Deadlines, reminder e compliance fiscale per business in Bali.",
};

export default function TaxCalendarLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <NavShell
        logo={<BZLogo variant="dark" />}
        items={[
          { label: "Home", href: "https://balizero.com/" },
          { label: "Visa", href: "https://visa.balizero.com/" },
          { label: "KBLI", href: "/kbli" },
        ]}
        actions={
          <a href="https://wa.me/628213107363" className="btn btn-primary">
            WhatsApp
          </a>
        }
      />
      <SessionInit funnel="tax" />
      {children}
    </>
  );
}
```

```tsx
// apps/mouth/src/app/(tax-calendar)/tax-calendar/page.tsx
import { FunnelFrame } from "@balizero/core";
import { TaxCalendarBody } from "@/components/funnel/TaxCalendarBody";

export default async function TaxCalendarPage() {
  const res = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL}/api/tax-calendar/deadlines`,
    { next: { revalidate: 3600 } },
  );
  const { deadlines, regencies } = await res.json();
  return (
    <FunnelFrame
      funnel="tax"
      sessionId="SSR" // client-side will overwrite via SessionInit + hook
      trust={{ clientCount: 5000, rating: 4.9, responseMinutes: 15 }}
    >
      <TaxCalendarBody deadlines={deadlines} regencies={regencies} />
    </FunnelFrame>
  );
}
```

- [ ] **Step 3:** Create TaxCalendarBody with segmented tabs + iCal button

```tsx
// apps/mouth/src/components/funnel/TaxCalendarBody.tsx
"use client";
import { useMemo, useState } from "react";
import { DeadlineBadge } from "@balizero/core";

type Deadline = {
  id: string;
  kind: "PPh" | "PPN" | "LKPM" | "PB1";
  title: string;
  date: string; // ISO
  regency?: string;
  description: string;
};

export function TaxCalendarBody({
  deadlines,
  regencies,
}: {
  deadlines: Deadline[];
  regencies: string[];
}) {
  const [kind, setKind] = useState<Deadline["kind"] | "ALL">("ALL");
  const [regency, setRegency] = useState("");

  const filtered = useMemo(() => {
    return deadlines.filter(
      (d) =>
        (kind === "ALL" || d.kind === kind) &&
        (!regency || d.regency === regency || !d.regency),
    );
  }, [deadlines, kind, regency]);

  return (
    <section>
      <header
        style={{
          display: "flex",
          gap: "var(--space-3)",
          marginBottom: "var(--space-6)",
        }}
      >
        {(["ALL", "PPh", "PPN", "LKPM", "PB1"] as const).map((k) => (
          <button
            key={k}
            onClick={() => setKind(k)}
            className={k === kind ? "pill pill-active" : "pill"}
          >
            {k}
          </button>
        ))}
        <select value={regency} onChange={(e) => setRegency(e.target.value)}>
          <option value="">Tutte le reggenze</option>
          {regencies.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        <a
          href="/api/tax-calendar/ical"
          download="bali-tax-deadlines.ics"
          className="btn"
        >
          Export iCal
        </a>
      </header>
      <ul
        style={{
          display: "grid",
          gap: "var(--space-4)",
          listStyle: "none",
          padding: 0,
        }}
      >
        {filtered.map((d) => (
          <li
            key={d.id}
            style={{
              display: "grid",
              gridTemplateColumns: "auto 1fr auto",
              gap: "var(--space-4)",
              padding: "var(--space-4)",
              background: "var(--surface-raised)",
              borderRadius: "var(--radius-lg)",
            }}
          >
            <DeadlineBadge date={new Date(d.date)} />
            <div>
              <strong>{d.title}</strong>
              <div style={{ color: "var(--color-text-secondary)" }}>
                {d.kind}
                {d.regency ? ` · ${d.regency}` : ""}
              </div>
              <p>{d.description}</p>
            </div>
            <a
              href="https://wa.me/628213107363?text=Delega%20Bali%20Zero%20SPT"
              className="btn btn-primary"
            >
              Delega a noi
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}
```

- [ ] **Step 4:** Create API routes — deadlines (static data) + ical

```ts
// apps/mouth/src/app/api/tax-calendar/deadlines/route.ts
import { NextResponse } from "next/server";

const DEADLINES = [
  {
    id: "pph25-monthly",
    kind: "PPh",
    title: "PPh 25 mensile",
    date: "2026-05-15T00:00:00Z",
    description:
      "Pagamento entro il 15 del mese seguente (JCSS 2025 cambio da 10 a 15).",
  },
  {
    id: "ppn-monthly",
    kind: "PPN",
    title: "PPN SPT Masa",
    date: "2026-05-31T00:00:00Z",
    description: "SPT Masa PPN entro fine mese successivo.",
  },
  {
    id: "lkpm-q1",
    kind: "LKPM",
    title: "LKPM Q1 2026",
    date: "2026-07-10T00:00:00Z",
    description: "Laporan Kegiatan Penanaman Modal, trimestrale.",
  },
  {
    id: "pb1-badung",
    kind: "PB1",
    title: "PB1 Badung",
    date: "2026-05-10T00:00:00Z",
    regency: "Badung",
    description: "Pajak Hotel/Restoran 10%.",
  },
  {
    id: "pb1-gianyar",
    kind: "PB1",
    title: "PB1 Gianyar",
    date: "2026-05-15T00:00:00Z",
    regency: "Gianyar",
    description: "PB1 reggenza Gianyar.",
  },
  {
    id: "spt-individual-2026",
    kind: "PPh",
    title: "SPT Tahunan Individuale 2025",
    date: "2026-04-30T00:00:00Z",
    description: "Estesa a 30 aprile (era 31 marzo).",
  },
];

export async function GET() {
  const regencies = Array.from(
    new Set(DEADLINES.filter((d) => d.regency).map((d) => d.regency!)),
  );
  return NextResponse.json({ deadlines: DEADLINES, regencies });
}
```

```ts
// apps/mouth/src/app/api/tax-calendar/ical/route.ts
import { NextResponse } from "next/server";
import { toIcalString } from "@balizero/core/utils";

const DEADLINES = [
  // ... (same list as above, factor to a shared file in production)
];

export async function GET() {
  const ics = toIcalString(
    DEADLINES.map((d) => ({
      uid: `balizero-tax-${d.id}@balizero.com`,
      summary: d.title,
      start: new Date(d.date),
      end: new Date(new Date(d.date).getTime() + 86400_000),
      description: d.description,
    })),
    { prodId: "BaliZero//TaxCalendar//EN" },
  );
  return new NextResponse(ics, {
    headers: {
      "Content-Type": "text/calendar; charset=utf-8",
      "Content-Disposition": 'attachment; filename="bali-tax-deadlines.ics"',
    },
  });
}
```

- [ ] **Step 5:** Add Vercel domain via dashboard (manual): link `tax.balizero.com` to `mouth` project. DNS CNAME already handled by Cloudflare (same pattern as `visa.balizero.com`, memoria #97).

- [ ] **Step 6:** Commit

```bash
git add apps/mouth/src/app/\(tax-calendar\)/ apps/mouth/src/components/funnel/TaxCalendarBody.tsx apps/mouth/src/app/api/tax-calendar/ apps/mouth/src/middleware.ts
git commit -m "feat(tax-calendar): new funnel tax.balizero.com with iCal export"
```

---

## Task 6: Property Eligibility — nuovo tool

**Files:**

- Create: `apps/mouth/src/app/property/layout.tsx`
- Create: `apps/mouth/src/app/property/page.tsx`
- Create: `apps/mouth/src/components/funnel/PropertyEligibilityBody.tsx`
- Create: `apps/mouth/src/app/api/property/analyze/route.ts`

- [ ] **Step 1:** Route at `/property` on `balizero.com` (public domain). Layout = NavShell editorial + SessionInit funnel="property".

- [ ] **Step 2:** Body chiede indirizzo/lat+lng, chiama API che proxy Prime

```tsx
// apps/mouth/src/components/funnel/PropertyEligibilityBody.tsx
"use client";
import { useState } from "react";

export function PropertyEligibilityBody() {
  const [coord, setCoord] = useState("");
  const [result, setResult] = useState<any>(null);

  async function analyze() {
    const [lat, lng] = coord.split(",").map((s) => s.trim());
    const res = await fetch(`/api/property/analyze?lat=${lat}&lng=${lng}`);
    setResult(await res.json());
  }

  return (
    <section>
      <input
        placeholder="Lat, Lng (es. -8.65, 115.13)"
        value={coord}
        onChange={(e) => setCoord(e.target.value)}
        style={{ padding: "var(--space-3)", width: "100%" }}
      />
      <button onClick={analyze} className="btn btn-primary">
        Analizza
      </button>
      {result ? (
        <div style={{ marginTop: "var(--space-6)" }}>
          <h2>Struttura eligible: {result.eligibility?.join(", ") ?? "n/d"}</h2>
          <p>
            PBB: {result.tax?.pbb_rate}% · BPHTB: {result.tax?.bphtb_rate}%
          </p>
          <p>Risk score: {result.risk?.total}/100</p>
          <a
            href={`https://prime.balizero.com/proposal/${result.token}`}
            className="btn"
          >
            Vedi zona 3D
          </a>
        </div>
      ) : null}
    </section>
  );
}
```

- [ ] **Step 3:** API proxy to Prime

```ts
// apps/mouth/src/app/api/property/analyze/route.ts
import { NextRequest, NextResponse } from "next/server";

export async function GET(req: NextRequest) {
  const lat = req.nextUrl.searchParams.get("lat");
  const lng = req.nextUrl.searchParams.get("lng");
  if (!lat || !lng)
    return NextResponse.json({ error: "lat/lng required" }, { status: 400 });

  const res = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL}/api/prime/v2/analyze?lat=${lat}&lng=${lng}`,
    { headers: { "Content-Type": "application/json" }, cache: "no-store" },
  );
  if (!res.ok) return NextResponse.json({ error: "upstream" }, { status: 502 });
  return NextResponse.json(await res.json());
}
```

- [ ] **Step 4:** Commit

```bash
git add apps/mouth/src/app/property/ apps/mouth/src/components/funnel/PropertyEligibilityBody.tsx apps/mouth/src/app/api/property/
git commit -m "feat(property): eligibility tool wrapping Prime /v2/analyze"
```

---

## Task 7: Event tracking in 4 funnels

Add `trackFunnelEvent` calls:

- Visa: on quiz_completed, result_viewed, chat_question, whatsapp_cta, calling_block
- KBLI: on code_viewed ([code]/page.tsx), search (SearchBar), chat_question
- Tax: on dashboard_viewed (page mount)
- Property: on cta_clicked (analyze button), chat_question

- [ ] **Step 1-5:** For each funnel, import `trackFunnelEvent` from `@balizero/core/analytics` and wire the 11 events. Commit once per funnel.

```bash
git commit -m "feat(funnels): analytics funnel-view event tracking (11 events)"
```

---

## Task 8: Homepage session bridge + QA

- [ ] **Step 1:** In `apps/mouth/src/app/v2/page.tsx` add `<SessionInit funnel="home" />`

- [ ] **Step 2:** Browser QA — use `mcp__claude-in-chrome__*` 4 screenshots (homepage, visa, kbli, tax)

```bash
# via the agent's chrome tools — document in browser QA log
```

- [ ] **Step 3:** Lighthouse on L1 targets (homepage, visa, kbli, tax, property)

Expected: 95+ performance each.

- [ ] **Step 4:** Commit + final merge

```bash
git commit --allow-empty -m "chore(v2-funnel-hub): QA passed, ready for merge"
git checkout main && git merge --no-ff v2-funnel-hub
```

---

## Exit criteria

- ✅ 4 funnel tutti su FunnelFrame + NavShell persona=editorial
- ✅ `tax.balizero.com` live, iCal export funzionante
- ✅ `/property` live, integra Prime API
- ✅ Homepage linka tool reali
- ✅ session_id cross-funnel persistente (cookie `bz_session`)
- ✅ Tracking 11 eventi GA4+backend
- ✅ Lighthouse 95+ su 5 tool L1
