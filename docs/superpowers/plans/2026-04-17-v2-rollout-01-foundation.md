# v2 Rollout — Sub-plan 01: Foundation (Sprint 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Estendere `@balizero/core` con gli 8 componenti di dominio, 2 utility, session-bridge e analytics lib richiesti da tutti i subdomain v2; creare 2 migrations PostgreSQL (funnel_sessions generalizzato + notification_prefs).

**Architecture:** `packages/core` già espone `NavShell`/`ThemeProvider`/`BZLogo`/`WhatsAppFAB` e i token. Aggiungiamo componenti di dominio (MatterCard, FunnelFrame, CTAHandoff, TrustBand, ProgressRing, DeadlineBadge, CommandPalette, ContextPanel) più utility (ical, wa-deeplink, session-bridge, funnel-view analytics). Tutto TDD con Vitest (già configurato: 3 test files esistenti). Generalizziamo `visa_oracle_sessions` (migration 080b) in `funnel_sessions` via nuova migration additiva, senza distruggere la tabella esistente.

**Tech Stack:** TypeScript 5, React 19, Vitest, Tailwind 4, PostgreSQL 17 via asyncpg, Alembic-like `apply()` convention.

**Worktree:** `.worktrees/v2-foundation` on branch `v2-foundation`.

---

## File Structure

### Creare

```
packages/core/
├── components/
│   ├── MatterCard.tsx             + MatterCard.test.tsx
│   ├── ProgressRing.tsx           + ProgressRing.test.tsx
│   ├── DeadlineBadge.tsx          + DeadlineBadge.test.tsx
│   ├── FunnelFrame.tsx            + FunnelFrame.test.tsx
│   ├── TrustBand.tsx              + TrustBand.test.tsx
│   ├── CTAHandoff.tsx             + CTAHandoff.test.tsx
│   ├── CommandPalette.tsx         + CommandPalette.test.tsx
│   └── ContextPanel.tsx           + ContextPanel.test.tsx
├── tokens/themes/
│   ├── operative-light.css        (duplica light.css + extend)
│   └── operative-dark.css         (duplica dark.css + extend)
├── auth/
│   ├── session-bridge.ts          + session-bridge.test.ts
│   └── index.ts
├── analytics/
│   ├── funnel-view.ts             + funnel-view.test.ts
│   └── index.ts
└── utils/
    ├── ical.ts                    + ical.test.ts
    └── wa-deeplink.ts             + wa-deeplink.test.ts
```

### Modificare

- `packages/core/index.ts` — re-export nuovi simboli
- `packages/core/package.json` — aggiungere export paths

### Backend migrations

- `apps/backend-rag/backend/migrations/migration_109_funnel_sessions.py` (new)
- `apps/backend-rag/backend/migrations/migration_110_notification_prefs.py` (new)

---

## Task 1: Worktree setup

- [ ] **Step 1: Create worktree**

```bash
cd ~/Desktop/nuzantara
git worktree add .worktrees/v2-foundation -b v2-foundation main
cd .worktrees/v2-foundation
```

- [ ] **Step 2: Verify environment**

```bash
npm install
cd apps/backend-rag && source .venv/bin/activate && cd ../..
npm run typecheck -w apps/mouth
```

Expected: 0 TS errors.

---

## Task 2: ProgressRing (atomic, zero deps)

**Files:**

- Create: `packages/core/components/ProgressRing.tsx`
- Test: `packages/core/components/ProgressRing.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// packages/core/components/ProgressRing.test.tsx
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { ProgressRing } from "./ProgressRing";

describe("ProgressRing", () => {
  it("renders a circular ring at given percent", () => {
    const { container } = render(<ProgressRing percent={66} />);
    const circle = container.querySelector("circle[data-role='fill']");
    expect(circle).toBeTruthy();
    const dasharray = circle?.getAttribute("stroke-dasharray");
    const dashoffset = circle?.getAttribute("stroke-dashoffset");
    expect(dasharray).toBeTruthy();
    expect(Number(dashoffset)).toBeGreaterThan(0);
  });

  it("clamps to [0, 100]", () => {
    const { container } = render(<ProgressRing percent={150} />);
    const label = container.querySelector("[data-role='label']");
    expect(label?.textContent).toBe("100%");
  });

  it("uses status color tokens", () => {
    const { container } = render(<ProgressRing percent={30} status="danger" />);
    const circle = container.querySelector("circle[data-role='fill']");
    expect(circle?.getAttribute("stroke")).toBe("var(--color-status-danger)");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/core && npx vitest run components/ProgressRing.test.tsx
```

Expected: FAIL — `Cannot find module './ProgressRing'`.

- [ ] **Step 3: Implement minimal component**

```tsx
// packages/core/components/ProgressRing.tsx
import type { FC } from "react";

export interface ProgressRingProps {
  percent: number;
  size?: number;
  strokeWidth?: number;
  status?: "ok" | "warn" | "danger" | "neutral";
  label?: string;
}

const STATUS_TOKEN: Record<NonNullable<ProgressRingProps["status"]>, string> = {
  ok: "var(--color-status-ok)",
  warn: "var(--color-status-warn)",
  danger: "var(--color-status-danger)",
  neutral: "var(--accent-copper)",
};

export const ProgressRing: FC<ProgressRingProps> = ({
  percent,
  size = 48,
  strokeWidth = 4,
  status = "neutral",
  label,
}) => {
  const clamped = Math.max(0, Math.min(100, percent));
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - clamped / 100);

  return (
    <div
      role="img"
      aria-label={`${clamped}% complete`}
      style={{
        width: size,
        height: size,
        display: "inline-block",
        position: "relative",
      }}
    >
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="var(--color-border-subtle)"
          strokeWidth={strokeWidth}
          fill="none"
        />
        <circle
          data-role="fill"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={STATUS_TOKEN[status]}
          strokeWidth={strokeWidth}
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
        />
      </svg>
      <span
        data-role="label"
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: size / 4,
          fontVariantNumeric: "tabular-nums",
          color: "var(--color-text-primary)",
        }}
      >
        {label ?? `${clamped}%`}
      </span>
    </div>
  );
};
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd packages/core && npx vitest run components/ProgressRing.test.tsx
```

Expected: PASS (3 tests).

- [ ] **Step 5: Export + commit**

Add to `packages/core/index.ts`:

```ts
export {
  ProgressRing,
  type ProgressRingProps,
} from "./components/ProgressRing";
```

```bash
git add packages/core/components/ProgressRing.tsx packages/core/components/ProgressRing.test.tsx packages/core/index.ts
git commit -m "feat(core): ProgressRing with status tokens and label"
```

---

## Task 3: DeadlineBadge (depends on ProgressRing)

**Files:**

- Create: `packages/core/components/DeadlineBadge.tsx`
- Test: `packages/core/components/DeadlineBadge.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// packages/core/components/DeadlineBadge.test.tsx
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { DeadlineBadge } from "./DeadlineBadge";

describe("DeadlineBadge", () => {
  it("renders 'in Xd' when deadline is future", () => {
    const future = new Date(Date.now() + 5 * 86400_000);
    const { getByText } = render(<DeadlineBadge date={future} />);
    expect(getByText(/in 5d/)).toBeTruthy();
  });

  it("renders 'overdue' when deadline passed", () => {
    const past = new Date(Date.now() - 3 * 86400_000);
    const { getByText } = render(<DeadlineBadge date={past} />);
    expect(getByText(/overdue/i)).toBeTruthy();
  });

  it("maps days-left to status color", () => {
    const in2d = new Date(Date.now() + 2 * 86400_000);
    const { container } = render(<DeadlineBadge date={in2d} />);
    const fill = container.querySelector("circle[data-role='fill']");
    expect(fill?.getAttribute("stroke")).toBe("var(--color-status-danger)");
  });
});
```

- [ ] **Step 2: Run test — fail**

```bash
cd packages/core && npx vitest run components/DeadlineBadge.test.tsx
```

- [ ] **Step 3: Implement**

```tsx
// packages/core/components/DeadlineBadge.tsx
import type { FC } from "react";
import { ProgressRing } from "./ProgressRing";

export interface DeadlineBadgeProps {
  date: Date;
  windowDays?: number; // countdown window that maps to 0-100% ring fill
}

export const DeadlineBadge: FC<DeadlineBadgeProps> = ({
  date,
  windowDays = 30,
}) => {
  const now = Date.now();
  const diffMs = date.getTime() - now;
  const daysLeft = Math.ceil(diffMs / 86400_000);

  let status: "ok" | "warn" | "danger";
  let label: string;
  let percent: number;

  if (daysLeft < 0) {
    status = "danger";
    label = "overdue";
    percent = 0;
  } else if (daysLeft <= 3) {
    status = "danger";
    label = `in ${daysLeft}d`;
    percent = (daysLeft / windowDays) * 100;
  } else if (daysLeft <= 14) {
    status = "warn";
    label = `in ${daysLeft}d`;
    percent = (daysLeft / windowDays) * 100;
  } else {
    status = "ok";
    label = `in ${daysLeft}d`;
    percent = Math.min(100, (daysLeft / windowDays) * 100);
  }

  return (
    <ProgressRing percent={percent} status={status} label={label} size={56} />
  );
};
```

- [ ] **Step 4: Run tests — pass**

```bash
cd packages/core && npx vitest run components/DeadlineBadge.test.tsx
```

- [ ] **Step 5: Export + commit**

```bash
# add export to packages/core/index.ts
git add packages/core/components/DeadlineBadge.tsx packages/core/components/DeadlineBadge.test.tsx packages/core/index.ts
git commit -m "feat(core): DeadlineBadge (uses ProgressRing)"
```

---

## Task 4: TrustBand

**Files:**

- Create: `packages/core/components/TrustBand.tsx` + test

- [ ] **Step 1: Write failing test**

```tsx
// packages/core/components/TrustBand.test.tsx
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { TrustBand } from "./TrustBand";

describe("TrustBand", () => {
  it("renders three stat tiles with labels", () => {
    const { getByText } = render(
      <TrustBand clientCount={5000} rating={4.9} responseMinutes={15} />,
    );
    expect(getByText(/5,?000\+/)).toBeTruthy();
    expect(getByText(/4\.9/)).toBeTruthy();
    expect(getByText(/15 min/)).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Implement**

```tsx
// packages/core/components/TrustBand.tsx
import type { FC } from "react";

export interface TrustBandProps {
  clientCount: number;
  rating: number;
  responseMinutes: number;
}

function formatK(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(0)}k+` : `${n}+`;
}

export const TrustBand: FC<TrustBandProps> = ({
  clientCount,
  rating,
  responseMinutes,
}) => (
  <section
    aria-label="Trust signals"
    style={{
      display: "grid",
      gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
      gap: "var(--space-4)",
      padding: "var(--space-6) var(--space-4)",
      background: "var(--surface-subtle)",
      borderTop: "1px solid var(--color-border-subtle)",
    }}
  >
    <div>
      <strong style={{ fontSize: "var(--font-size-2xl)" }}>
        {formatK(clientCount)}
      </strong>
      <div style={{ color: "var(--color-text-secondary)" }}>Clienti</div>
    </div>
    <div>
      <strong style={{ fontSize: "var(--font-size-2xl)" }}>
        ★ {rating.toFixed(1)}
      </strong>
      <div style={{ color: "var(--color-text-secondary)" }}>Recensioni</div>
    </div>
    <div>
      <strong style={{ fontSize: "var(--font-size-2xl)" }}>
        ~{responseMinutes} min
      </strong>
      <div style={{ color: "var(--color-text-secondary)" }}>Risposta</div>
    </div>
  </section>
);
```

- [ ] **Step 4: Run — pass**

- [ ] **Step 5: Export + commit**

```bash
git add packages/core/components/TrustBand.tsx packages/core/components/TrustBand.test.tsx packages/core/index.ts
git commit -m "feat(core): TrustBand (5000+ clients / rating / response)"
```

---

## Task 5: wa-deeplink utility

**Files:**

- Create: `packages/core/utils/wa-deeplink.ts` + test

- [ ] **Step 1: Write failing test**

```ts
// packages/core/utils/wa-deeplink.test.ts
import { describe, it, expect } from "vitest";
import { buildWaDeeplink, WA_CANONICAL } from "./wa-deeplink";

describe("buildWaDeeplink", () => {
  it("uses canonical number +62 821 3107 363", () => {
    expect(WA_CANONICAL).toBe("628213107363");
  });
  it("url-encodes the context text", () => {
    const url = buildWaDeeplink({ text: "Ciao! sessione abc" });
    expect(url).toBe(
      "https://wa.me/628213107363?text=Ciao%21%20sessione%20abc",
    );
  });
  it("composes from source + session + payload", () => {
    const url = buildWaDeeplink({
      source: "visa-oracle",
      sessionId: "abc-123",
      payload: { visa: "E23" },
    });
    expect(url).toMatch(/wa\.me\/628213107363\?text=/);
    expect(decodeURIComponent(url)).toContain("visa-oracle");
    expect(decodeURIComponent(url)).toContain("abc-123");
    expect(decodeURIComponent(url)).toContain("E23");
  });
});
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Implement**

```ts
// packages/core/utils/wa-deeplink.ts
export const WA_CANONICAL = "628213107363";

export interface WaDeeplinkArgs {
  text?: string;
  source?: string;
  sessionId?: string;
  payload?: Record<string, unknown>;
}

export function buildWaDeeplink(args: WaDeeplinkArgs): string {
  let text = args.text;
  if (!text) {
    const parts: string[] = ["Ciao Bali Zero"];
    if (args.source) parts.push(`[source:${args.source}]`);
    if (args.sessionId) parts.push(`[session:${args.sessionId}]`);
    if (args.payload) parts.push(`[data:${JSON.stringify(args.payload)}]`);
    text = parts.join(" ");
  }
  return `https://wa.me/${WA_CANONICAL}?text=${encodeURIComponent(text)}`;
}
```

- [ ] **Step 4: Run — pass**

- [ ] **Step 5: Export + commit**

```ts
// packages/core/utils/index.ts — add:
export * from "./wa-deeplink";
```

```bash
git add packages/core/utils/wa-deeplink.ts packages/core/utils/wa-deeplink.test.ts packages/core/utils/index.ts
git commit -m "feat(core): wa-deeplink utility with canonical +628213107363"
```

---

## Task 6: ical utility (Tax Calendar + portal deadlines)

**Files:**

- Create: `packages/core/utils/ical.ts` + test

- [ ] **Step 1: Write failing test**

```ts
// packages/core/utils/ical.test.ts
import { describe, it, expect } from "vitest";
import { toIcalString, type IcalEvent } from "./ical";

describe("toIcalString", () => {
  it("emits a valid VCALENDAR with VEVENT entries", () => {
    const events: IcalEvent[] = [
      {
        uid: "deadline-pph-2026-05-15",
        summary: "PPh 25 — Maggio",
        start: new Date("2026-05-15T00:00:00Z"),
        end: new Date("2026-05-15T23:59:00Z"),
        description: "Pagamento PPh 25 mensile",
      },
    ];
    const out = toIcalString(events, { prodId: "BaliZero//TaxCalendar" });
    expect(out).toContain("BEGIN:VCALENDAR");
    expect(out).toContain("PRODID:BaliZero//TaxCalendar");
    expect(out).toContain("BEGIN:VEVENT");
    expect(out).toContain("UID:deadline-pph-2026-05-15");
    expect(out).toContain("SUMMARY:PPh 25 — Maggio");
    expect(out).toContain("DTSTART:20260515T000000Z");
    expect(out).toContain("END:VCALENDAR");
  });
});
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Implement**

```ts
// packages/core/utils/ical.ts
export interface IcalEvent {
  uid: string;
  summary: string;
  start: Date;
  end: Date;
  description?: string;
}

export interface IcalOptions {
  prodId: string;
}

function icalDate(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    d.getUTCFullYear().toString() +
    pad(d.getUTCMonth() + 1) +
    pad(d.getUTCDate()) +
    "T" +
    pad(d.getUTCHours()) +
    pad(d.getUTCMinutes()) +
    pad(d.getUTCSeconds()) +
    "Z"
  );
}

function escape(s: string): string {
  return s.replace(/[\\,;]/g, (c) => `\\${c}`).replace(/\n/g, "\\n");
}

export function toIcalString(events: IcalEvent[], opts: IcalOptions): string {
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    `PRODID:${opts.prodId}`,
    "CALSCALE:GREGORIAN",
  ];
  for (const e of events) {
    lines.push("BEGIN:VEVENT");
    lines.push(`UID:${e.uid}`);
    lines.push(`DTSTAMP:${icalDate(new Date())}`);
    lines.push(`DTSTART:${icalDate(e.start)}`);
    lines.push(`DTEND:${icalDate(e.end)}`);
    lines.push(`SUMMARY:${escape(e.summary)}`);
    if (e.description) lines.push(`DESCRIPTION:${escape(e.description)}`);
    lines.push("END:VEVENT");
  }
  lines.push("END:VCALENDAR");
  return lines.join("\r\n");
}
```

- [ ] **Step 4: Run — pass**

- [ ] **Step 5: Export + commit**

```bash
git add packages/core/utils/ical.ts packages/core/utils/ical.test.ts packages/core/utils/index.ts
git commit -m "feat(core): ical export utility (VCALENDAR/VEVENT)"
```

---

## Task 7: CTAHandoff (depends on wa-deeplink)

**Files:**

- Create: `packages/core/components/CTAHandoff.tsx` + test

- [ ] **Step 1: Write failing test**

```tsx
// packages/core/components/CTAHandoff.test.tsx
import { describe, it, expect } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { CTAHandoff } from "./CTAHandoff";

describe("CTAHandoff", () => {
  it("renders three tiers in order: PDF, Zantara, WA", () => {
    const { getAllByRole } = render(
      <CTAHandoff
        source="visa-oracle"
        sessionId="abc"
        pdfHref="/api/report.pdf"
        onZantaraClick={() => {}}
      />,
    );
    const links = getAllByRole("link");
    expect(links[0].getAttribute("href")).toBe("/api/report.pdf");
    expect(links[1].getAttribute("href")).toMatch(/wa\.me\/628213107363/);
  });

  it("falls back to WA-only when pdf/Zantara missing", () => {
    const { getAllByRole } = render(
      <CTAHandoff source="kbli" sessionId="xyz" />,
    );
    const links = getAllByRole("link");
    expect(links).toHaveLength(1);
    expect(links[0].getAttribute("href")).toMatch(/wa\.me/);
  });
});
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Implement**

```tsx
// packages/core/components/CTAHandoff.tsx
"use client";
import type { FC, MouseEventHandler } from "react";
import { buildWaDeeplink } from "../utils/wa-deeplink";

export interface CTAHandoffProps {
  source: string;
  sessionId: string;
  pdfHref?: string;
  onZantaraClick?: MouseEventHandler<HTMLButtonElement>;
  payload?: Record<string, unknown>;
}

export const CTAHandoff: FC<CTAHandoffProps> = ({
  source,
  sessionId,
  pdfHref,
  onZantaraClick,
  payload,
}) => {
  const waUrl = buildWaDeeplink({ source, sessionId, payload });
  return (
    <div
      role="group"
      aria-label="Next actions"
      style={{
        display: "flex",
        gap: "var(--space-3)",
        padding: "var(--space-4)",
        position: "sticky",
        bottom: 0,
        background: "var(--surface-base)",
        borderTop: "1px solid var(--color-border-subtle)",
      }}
    >
      {pdfHref ? (
        <a href={pdfHref} className="btn btn-tertiary">
          Scarica report
        </a>
      ) : null}
      {onZantaraClick ? (
        <button
          type="button"
          onClick={onZantaraClick}
          className="btn btn-secondary"
        >
          Chatta con Zantara
        </button>
      ) : null}
      <a
        href={waUrl}
        className="btn btn-primary"
        target="_blank"
        rel="noreferrer"
      >
        Parla su WhatsApp
      </a>
    </div>
  );
};
```

- [ ] **Step 4: Run — pass**

- [ ] **Step 5: Export + commit**

```bash
git add packages/core/components/CTAHandoff.tsx packages/core/components/CTAHandoff.test.tsx packages/core/index.ts
git commit -m "feat(core): CTAHandoff 3-tier (PDF/Zantara/WA)"
```

---

## Task 8: FunnelFrame (depends on TrustBand, CTAHandoff)

**Files:**

- Create: `packages/core/components/FunnelFrame.tsx` + test

- [ ] **Step 1: Write failing test**

```tsx
// packages/core/components/FunnelFrame.test.tsx
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { FunnelFrame } from "./FunnelFrame";

describe("FunnelFrame", () => {
  it("renders children, TrustBand, and CTAHandoff", () => {
    const { getByText, getByRole } = render(
      <FunnelFrame
        funnel="visa"
        sessionId="abc"
        step={{ current: 2, total: 5 }}
        trust={{ clientCount: 5000, rating: 4.9, responseMinutes: 15 }}
      >
        <div>QUIZ_BODY</div>
      </FunnelFrame>,
    );
    expect(getByText("QUIZ_BODY")).toBeTruthy();
    expect(getByText(/5k\+/)).toBeTruthy();
    expect(getByRole("group", { name: /next actions/i })).toBeTruthy();
  });

  it("sets data-funnel on the container", () => {
    const { container } = render(
      <FunnelFrame funnel="kbli" sessionId="x">
        <span>body</span>
      </FunnelFrame>,
    );
    expect(container.firstChild).toHaveAttribute("data-funnel", "kbli");
  });
});
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Implement**

```tsx
// packages/core/components/FunnelFrame.tsx
import type { FC, ReactNode } from "react";
import { TrustBand, type TrustBandProps } from "./TrustBand";
import { CTAHandoff, type CTAHandoffProps } from "./CTAHandoff";
import type { Funnel } from "./ThemeProvider";

export interface FunnelFrameProps {
  funnel: NonNullable<Funnel>;
  sessionId: string;
  step?: { current: number; total: number };
  trust?: TrustBandProps;
  handoff?: Partial<Omit<CTAHandoffProps, "source" | "sessionId">>;
  children: ReactNode;
}

export const FunnelFrame: FC<FunnelFrameProps> = ({
  funnel,
  sessionId,
  step,
  trust,
  handoff,
  children,
}) => (
  <div
    data-funnel={funnel}
    style={{ minHeight: "100dvh", display: "flex", flexDirection: "column" }}
  >
    {step ? (
      <div
        role="progressbar"
        aria-valuenow={step.current}
        aria-valuemax={step.total}
        style={{
          height: 4,
          background: "var(--color-border-subtle)",
        }}
      >
        <div
          style={{
            width: `${(step.current / step.total) * 100}%`,
            height: "100%",
            background: "var(--accent-funnel)",
          }}
        />
      </div>
    ) : null}
    <main style={{ flex: 1, padding: "var(--space-6)" }}>{children}</main>
    {trust ? <TrustBand {...trust} /> : null}
    <CTAHandoff
      source={`funnel-${funnel}`}
      sessionId={sessionId}
      {...handoff}
    />
  </div>
);
```

- [ ] **Step 4: Run — pass**

- [ ] **Step 5: Export + commit**

```bash
git add packages/core/components/FunnelFrame.tsx packages/core/components/FunnelFrame.test.tsx packages/core/index.ts
git commit -m "feat(core): FunnelFrame layout (step bar + TrustBand + CTAHandoff)"
```

---

## Task 9: MatterCard (depends on ProgressRing + DeadlineBadge)

**Files:**

- Create: `packages/core/components/MatterCard.tsx` + test

- [ ] **Step 1: Write failing test**

```tsx
// packages/core/components/MatterCard.test.tsx
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { MatterCard } from "./MatterCard";

describe("MatterCard", () => {
  it("shows title, progress ring, pending docs, deadline", () => {
    const { getByText, container } = render(
      <MatterCard
        title="KITAS Marco"
        type="visa"
        progressPercent={70}
        pendingDocs={["passport scan", "photo"]}
        nextDeadline={new Date(Date.now() + 10 * 86400_000)}
      />,
    );
    expect(getByText("KITAS Marco")).toBeTruthy();
    expect(container.querySelector("[data-role='fill']")).toBeTruthy();
    expect(getByText(/2 document/i)).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Implement**

```tsx
// packages/core/components/MatterCard.tsx
import type { FC, ReactNode } from "react";
import { ProgressRing } from "./ProgressRing";
import { DeadlineBadge } from "./DeadlineBadge";

export type MatterType = "visa" | "company" | "tax" | "property" | "other";

export interface MatterCardProps {
  title: string;
  type: MatterType;
  progressPercent: number;
  pendingDocs?: string[];
  nextDeadline?: Date;
  nextStep?: string;
  action?: ReactNode;
}

const TYPE_LABEL: Record<MatterType, string> = {
  visa: "Visa",
  company: "Company",
  tax: "Tax",
  property: "Property",
  other: "Other",
};

export const MatterCard: FC<MatterCardProps> = ({
  title,
  type,
  progressPercent,
  pendingDocs = [],
  nextDeadline,
  nextStep,
  action,
}) => (
  <article
    style={{
      display: "grid",
      gridTemplateColumns: "auto 1fr auto",
      gap: "var(--space-4)",
      alignItems: "center",
      padding: "var(--space-4)",
      borderRadius: "var(--radius-lg)",
      background: "var(--surface-raised)",
      border: "1px solid var(--color-border-subtle)",
    }}
  >
    <ProgressRing percent={progressPercent} size={64} />
    <div>
      <header
        style={{
          display: "flex",
          gap: "var(--space-2)",
          alignItems: "baseline",
        }}
      >
        <h3 style={{ margin: 0, fontSize: "var(--font-size-lg)" }}>{title}</h3>
        <span
          style={{
            color: "var(--color-text-secondary)",
            fontSize: "var(--font-size-sm)",
          }}
        >
          {TYPE_LABEL[type]}
        </span>
      </header>
      {pendingDocs.length > 0 ? (
        <p
          style={{
            margin: "var(--space-1) 0 0",
            color: "var(--color-status-warn)",
          }}
        >
          {pendingDocs.length} document{pendingDocs.length === 1 ? "" : "s"}{" "}
          pending
        </p>
      ) : null}
      {nextStep ? (
        <p
          style={{
            margin: "var(--space-1) 0 0",
            color: "var(--color-text-secondary)",
          }}
        >
          Prossimo: {nextStep}
        </p>
      ) : null}
    </div>
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "flex-end",
        gap: "var(--space-2)",
      }}
    >
      {nextDeadline ? <DeadlineBadge date={nextDeadline} /> : null}
      {action}
    </div>
  </article>
);
```

- [ ] **Step 4: Run — pass**

- [ ] **Step 5: Export + commit**

```bash
git add packages/core/components/MatterCard.tsx packages/core/components/MatterCard.test.tsx packages/core/index.ts
git commit -m "feat(core): MatterCard matter-first dashboard card"
```

---

## Task 10: CommandPalette (kbd-driven)

**Files:**

- Create: `packages/core/components/CommandPalette.tsx` + test

- [ ] **Step 1: Write failing test**

```tsx
// packages/core/components/CommandPalette.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { CommandPalette, type CommandAction } from "./CommandPalette";

describe("CommandPalette", () => {
  it("filters actions by query and invokes handler on Enter", () => {
    const run = vi.fn();
    const actions: CommandAction[] = [
      {
        id: "create-kitas",
        label: "Crea pratica KITAS",
        group: "Pratiche",
        run,
      },
      { id: "export-lkpm", label: "Esporta LKPM", group: "Tax", run: () => {} },
    ];
    const { getByRole, getByText } = render(
      <CommandPalette open actions={actions} onClose={() => {}} />,
    );
    const input = getByRole("combobox");
    fireEvent.change(input, { target: { value: "kit" } });
    expect(getByText("Crea pratica KITAS")).toBeTruthy();
    fireEvent.keyDown(input, { key: "Enter" });
    expect(run).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Implement**

```tsx
// packages/core/components/CommandPalette.tsx
"use client";
import { useEffect, useMemo, useState } from "react";

export interface CommandAction {
  id: string;
  label: string;
  group?: string;
  run: () => void | Promise<void>;
}

interface CommandPaletteProps {
  open: boolean;
  actions: CommandAction[];
  onClose: () => void;
}

export function CommandPalette({
  open,
  actions,
  onClose,
}: CommandPaletteProps) {
  const [q, setQ] = useState("");
  const [idx, setIdx] = useState(0);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return actions;
    return actions.filter((a) => a.label.toLowerCase().includes(needle));
  }, [q, actions]);

  useEffect(() => {
    if (open) {
      setQ("");
      setIdx(0);
    }
  }, [open]);

  if (!open) return null;

  function run(a: CommandAction) {
    Promise.resolve(a.run()).finally(onClose);
  }

  return (
    <div
      role="dialog"
      aria-label="Command palette"
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.5)",
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        paddingTop: "15vh",
        zIndex: 400,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "min(560px, 90vw)",
          background: "var(--surface-raised)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow-xl)",
        }}
      >
        <input
          role="combobox"
          aria-expanded
          autoFocus
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setIdx(0);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown")
              setIdx((i) => Math.min(i + 1, filtered.length - 1));
            if (e.key === "ArrowUp") setIdx((i) => Math.max(i - 1, 0));
            if (e.key === "Enter" && filtered[idx]) run(filtered[idx]);
            if (e.key === "Escape") onClose();
          }}
          placeholder="Digita un'azione…"
          style={{
            width: "100%",
            padding: "var(--space-4)",
            border: "none",
            background: "transparent",
            color: "var(--color-text-primary)",
            fontSize: "var(--font-size-lg)",
          }}
        />
        <ul
          style={{
            listStyle: "none",
            margin: 0,
            padding: 0,
            maxHeight: "50vh",
            overflow: "auto",
          }}
        >
          {filtered.map((a, i) => (
            <li
              key={a.id}
              aria-selected={i === idx}
              onClick={() => run(a)}
              style={{
                padding: "var(--space-3) var(--space-4)",
                cursor: "pointer",
                background:
                  i === idx ? "var(--surface-selected)" : "transparent",
              }}
            >
              {a.group ? (
                <span
                  style={{
                    color: "var(--color-text-secondary)",
                    marginRight: "var(--space-2)",
                  }}
                >
                  {a.group}
                </span>
              ) : null}
              {a.label}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run — pass**

- [ ] **Step 5: Export + commit**

```bash
git add packages/core/components/CommandPalette.tsx packages/core/components/CommandPalette.test.tsx packages/core/index.ts
git commit -m "feat(core): CommandPalette fuzzy+kbd-driven"
```

---

## Task 11: ContextPanel

**Files:**

- Create: `packages/core/components/ContextPanel.tsx` + test

- [ ] **Step 1: Write failing test**

```tsx
// packages/core/components/ContextPanel.test.tsx
import { describe, it, expect } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { ContextPanel } from "./ContextPanel";

describe("ContextPanel", () => {
  it("lazy-renders active tab only", () => {
    const renderInfo = () => <div>INFO_BODY</div>;
    const renderMatter = () => <div>MATTER_BODY</div>;
    const { queryByText, getByRole, getByText } = render(
      <ContextPanel
        open
        tabs={[
          { id: "info", label: "Info", render: renderInfo },
          { id: "matter", label: "Matter", render: renderMatter },
        ]}
      />,
    );
    expect(getByText("INFO_BODY")).toBeTruthy();
    expect(queryByText("MATTER_BODY")).toBeNull();
    fireEvent.click(getByRole("tab", { name: /matter/i }));
    expect(getByText("MATTER_BODY")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Implement**

```tsx
// packages/core/components/ContextPanel.tsx
"use client";
import { useState, type ReactNode } from "react";

export interface ContextTab {
  id: string;
  label: string;
  render: () => ReactNode;
}

interface ContextPanelProps {
  open: boolean;
  tabs: ContextTab[];
  width?: number;
}

export function ContextPanel({ open, tabs, width = 360 }: ContextPanelProps) {
  const [active, setActive] = useState(tabs[0]?.id);
  if (!open || tabs.length === 0) return null;
  const current = tabs.find((t) => t.id === active) ?? tabs[0];
  return (
    <aside
      aria-label="Context panel"
      style={{
        width,
        borderLeft: "1px solid var(--color-border-subtle)",
        background: "var(--surface-raised)",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        role="tablist"
        style={{
          display: "flex",
          borderBottom: "1px solid var(--color-border-subtle)",
        }}
      >
        {tabs.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={t.id === current.id}
            onClick={() => setActive(t.id)}
            style={{
              flex: 1,
              padding: "var(--space-3)",
              background: "transparent",
              border: "none",
              color: "var(--color-text-primary)",
              cursor: "pointer",
              borderBottom:
                t.id === current.id
                  ? "2px solid var(--accent-copper)"
                  : "2px solid transparent",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        style={{ flex: 1, padding: "var(--space-4)", overflow: "auto" }}
      >
        {current.render()}
      </div>
    </aside>
  );
}
```

- [ ] **Step 4: Run — pass**

- [ ] **Step 5: Export + commit**

```bash
git add packages/core/components/ContextPanel.tsx packages/core/components/ContextPanel.test.tsx packages/core/index.ts
git commit -m "feat(core): ContextPanel right-side lazy-tabbed panel"
```

---

## Task 12: session-bridge (cookie bz_session ↔ funnel_sessions)

**Files:**

- Create: `packages/core/auth/session-bridge.ts` + test + `index.ts`

- [ ] **Step 1: Write failing test**

```ts
// packages/core/auth/session-bridge.test.ts
import { describe, it, expect, beforeEach } from "vitest";
import { getOrCreateSessionId, BZ_SESSION_COOKIE } from "./session-bridge";

describe("session-bridge", () => {
  beforeEach(() => {
    document.cookie = `${BZ_SESSION_COOKIE}=; Max-Age=0; path=/`;
  });

  it("creates a UUID v4 cookie on first call", () => {
    const id = getOrCreateSessionId();
    expect(id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
    );
    expect(document.cookie).toContain(BZ_SESSION_COOKIE);
  });

  it("reuses existing cookie on subsequent calls", () => {
    const a = getOrCreateSessionId();
    const b = getOrCreateSessionId();
    expect(a).toBe(b);
  });
});
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Implement**

```ts
// packages/core/auth/session-bridge.ts
export const BZ_SESSION_COOKIE = "bz_session";
const MAX_AGE_SECONDS = 60 * 60 * 24 * 30; // 30 days

function uuidV4(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID)
    return crypto.randomUUID();
  // fallback (rare on modern browsers)
  const b = new Uint8Array(16);
  (globalThis.crypto ?? require("node:crypto").webcrypto).getRandomValues(b);
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = Array.from(b, (n) => n.toString(16).padStart(2, "0"));
  return `${h.slice(0, 4).join("")}-${h.slice(4, 6).join("")}-${h.slice(6, 8).join("")}-${h.slice(8, 10).join("")}-${h.slice(10, 16).join("")}`;
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const prefix = `${name}=`;
  for (const part of document.cookie.split(";")) {
    const trimmed = part.trim();
    if (trimmed.startsWith(prefix)) return trimmed.slice(prefix.length);
  }
  return null;
}

function writeCookie(name: string, value: string): void {
  if (typeof document === "undefined") return;
  const isSecure =
    typeof location !== "undefined" && location.protocol === "https:";
  const parts = [
    `${name}=${value}`,
    "path=/",
    "SameSite=Lax",
    `Max-Age=${MAX_AGE_SECONDS}`,
  ];
  // Only set Domain when not on localhost (would reject)
  if (
    typeof location !== "undefined" &&
    location.hostname.endsWith("balizero.com")
  ) {
    parts.push("Domain=.balizero.com");
  }
  if (isSecure) parts.push("Secure");
  document.cookie = parts.join("; ");
}

export function getOrCreateSessionId(): string {
  const existing = readCookie(BZ_SESSION_COOKIE);
  if (existing) return existing;
  const fresh = uuidV4();
  writeCookie(BZ_SESSION_COOKIE, fresh);
  return fresh;
}

export async function attachToServerSession(payload: {
  funnel: "visa" | "kbli" | "tax" | "property" | "home";
  step_state?: Record<string, unknown>;
}): Promise<void> {
  const sessionId = getOrCreateSessionId();
  await fetch("/api/funnel/session/touch", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, ...payload }),
  });
}
```

- [ ] **Step 4: Run — pass**

- [ ] **Step 5: Export + commit**

```ts
// packages/core/auth/index.ts
export * from "./session-bridge";
```

Add to `packages/core/index.ts`:

```ts
export * from "./auth";
```

```bash
git add packages/core/auth packages/core/index.ts
git commit -m "feat(core): session-bridge with bz_session cookie"
```

---

## Task 13: funnel-view analytics

**Files:**

- Create: `packages/core/analytics/funnel-view.ts` + test + `index.ts`

- [ ] **Step 1: Write failing test**

```ts
// packages/core/analytics/funnel-view.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { trackFunnelEvent, FUNNEL_EVENTS } from "./funnel-view";

describe("funnel-view", () => {
  beforeEach(() => {
    vi.stubGlobal("gtag", vi.fn());
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
  });

  it("emits gtag + backend dual-track", async () => {
    await trackFunnelEvent("visa_quiz_completed", {
      sessionId: "abc",
      payload: { score: 7 },
    });
    const gtag = globalThis.gtag as unknown as ReturnType<typeof vi.fn>;
    expect(gtag).toHaveBeenCalledWith(
      "event",
      "visa_quiz_completed",
      expect.any(Object),
    );
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/analytics/funnel-event",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("whitelist of events matches the 11 known from CLAUDE.md §473", () => {
    expect(FUNNEL_EVENTS).toContain("visa_quiz_completed");
    expect(FUNNEL_EVENTS).toContain("kbli_code_viewed");
    expect(FUNNEL_EVENTS).toContain("tax_dashboard_viewed");
    expect(FUNNEL_EVENTS).toContain("property_cta_clicked");
    expect(FUNNEL_EVENTS.length).toBe(11);
  });
});
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Implement**

```ts
// packages/core/analytics/funnel-view.ts
export const FUNNEL_EVENTS = [
  "visa_quiz_completed",
  "visa_result_viewed",
  "visa_chat_question",
  "visa_whatsapp_cta",
  "visa_calling_block",
  "kbli_code_viewed",
  "kbli_search",
  "kbli_chat_question",
  "tax_dashboard_viewed",
  "property_cta_clicked",
  "property_chat_question",
] as const;

export type FunnelEventName = (typeof FUNNEL_EVENTS)[number];

interface TrackArgs {
  sessionId: string;
  payload?: Record<string, unknown>;
}

declare global {
  // eslint-disable-next-line no-var
  var gtag: ((...args: unknown[]) => void) | undefined;
}

export async function trackFunnelEvent(
  name: FunnelEventName,
  args: TrackArgs,
): Promise<void> {
  const body = {
    session_id: args.sessionId,
    event: name,
    payload: args.payload ?? {},
  };
  if (typeof globalThis.gtag === "function") {
    globalThis.gtag("event", name, body);
  }
  try {
    await fetch("/api/analytics/funnel-event", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    /* silent — analytics never blocks UX */
  }
}
```

- [ ] **Step 4: Run — pass**

- [ ] **Step 5: Export + commit**

```bash
git add packages/core/analytics packages/core/index.ts
git commit -m "feat(core): funnel-view analytics dual-track (GA4+backend)"
```

---

## Task 14: Theme tokens (operative-light, operative-dark)

**Files:**

- Create: `packages/core/tokens/themes/operative-light.css`
- Create: `packages/core/tokens/themes/operative-dark.css`

- [ ] **Step 1: Duplicate + extend**

```bash
cp packages/core/tokens/themes/light.css packages/core/tokens/themes/operative-light.css
cp packages/core/tokens/themes/dark.css packages/core/tokens/themes/operative-dark.css
```

- [ ] **Step 2: Add persona selector attribute**

Edit `operative-light.css` header:

```css
[data-theme="operative-light"] {
  /* all vars from light.css body here — paste from light.css */
  /* plus persona-specific extensions: */
  --surface-matter: #faf9f7;
  --surface-selected: rgba(212, 132, 90, 0.08);
}
```

Idem for `operative-dark.css`:

```css
[data-theme="operative-dark"] {
  /* all vars from dark.css body */
  --surface-matter: #14161b;
  --surface-selected: rgba(212, 132, 90, 0.15);
}
```

- [ ] **Step 3: Register in `tokens/index.css`**

```css
/* Append after existing @imports */
@import "./themes/operative-light.css";
@import "./themes/operative-dark.css";
```

- [ ] **Step 4: Extend ThemeProvider Theme type**

Edit `packages/core/components/ThemeProvider.tsx` line ~12:

```tsx
export type Theme =
  | "dark"
  | "light"
  | "editorial"
  | "operative-light"
  | "operative-dark";
```

- [ ] **Step 5: Run typecheck + commit**

```bash
cd ~/Desktop/nuzantara && npm run typecheck -w apps/mouth
git add packages/core/tokens packages/core/components/ThemeProvider.tsx
git commit -m "feat(core): operative-light/dark persona themes"
```

---

## Task 15: Update package exports

**Files:**

- Modify: `packages/core/package.json`

- [ ] **Step 1: Add exports map**

Edit `packages/core/package.json` `exports` field:

```json
{
  "exports": {
    ".": "./index.ts",
    "./tokens/index.css": "./tokens/index.css",
    "./tailwind/theme.css": "./tailwind/theme.css",
    "./effects/grain.css": "./effects/grain.css",
    "./effects/shimmer.css": "./effects/shimmer.css",
    "./fonts/inter": "./fonts/inter.ts",
    "./components/BZLogo": "./components/BZLogo.tsx",
    "./components/NavShell": "./components/NavShell.tsx",
    "./components/ThemeProvider": "./components/ThemeProvider.tsx",
    "./components/ProgressRing": "./components/ProgressRing.tsx",
    "./components/DeadlineBadge": "./components/DeadlineBadge.tsx",
    "./components/TrustBand": "./components/TrustBand.tsx",
    "./components/CTAHandoff": "./components/CTAHandoff.tsx",
    "./components/FunnelFrame": "./components/FunnelFrame.tsx",
    "./components/MatterCard": "./components/MatterCard.tsx",
    "./components/CommandPalette": "./components/CommandPalette.tsx",
    "./components/ContextPanel": "./components/ContextPanel.tsx",
    "./auth": "./auth/index.ts",
    "./analytics": "./analytics/index.ts",
    "./utils": "./utils/index.ts"
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add packages/core/package.json
git commit -m "chore(core): export new components and utils"
```

---

## Task 16: Migration 109 — funnel_sessions (generalizzazione)

**Files:**

- Create: `apps/backend-rag/backend/migrations/migration_109_funnel_sessions.py`

- [ ] **Step 1: Implement migration (additive, non-distruttiva)**

```python
# apps/backend-rag/backend/migrations/migration_109_funnel_sessions.py
"""
Migration 109: funnel_sessions — generalizzazione cross-funnel.

Crea la tabella `funnel_sessions` per tracciare sessioni anonime (pre-auth)
su tutti e 4 i funnel: visa, kbli, tax, property. Estende il pattern già
in prod per `visa_oracle_sessions` (migration 080b).

Rapporto con visa_oracle_sessions:
- visa_oracle_sessions resta in uso per quiz/chat dettagli specifici del visa
- funnel_sessions è la tabella di lead-tracking cross-funnel, indicizzata per
  `bz_session` cookie
- Bridge: quando user converte (SSO login), `converted_to_client_id` viene popolato

Schema:
- session_id VARCHAR(64) PK: UUID v4 dal cookie `bz_session`
- funnel ENUM: visa, kbli, tax, property, home
- step_state JSONB: stato corrente (quali step fatti)
- lead_profile JSONB: dati estratti dal quiz/tool (nationality, visa_recommended, ...)
- first_touched_at, last_touched_at: timestamp
- converted_to_client_id UUID NULL: FK a clients.id quando SSO login completato
- ip_hash VARCHAR(64): SHA-256 per abuse/rate-limit (no PII)
- expires_at: 90-day TTL

Reference: design 2026-04-17-v2-subdomain-rollout-design.md §3.1
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    await conn.execute("""
        CREATE TYPE IF NOT EXISTS funnel_type_enum AS ENUM (
            'visa', 'kbli', 'tax', 'property', 'home'
        );
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS funnel_sessions (
            session_id              VARCHAR(64) PRIMARY KEY,
            funnel                  funnel_type_enum NOT NULL,
            step_state              JSONB DEFAULT '{}'::jsonb,
            lead_profile            JSONB DEFAULT '{}'::jsonb,
            first_touched_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            last_touched_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            converted_to_client_id  UUID NULL,
            ip_hash                 VARCHAR(64),
            expires_at              TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '90 days')
        );
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_funnel_sessions_funnel_last_touched
        ON funnel_sessions (funnel, last_touched_at DESC);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_funnel_sessions_converted
        ON funnel_sessions (converted_to_client_id)
        WHERE converted_to_client_id IS NOT NULL;
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_funnel_sessions_expires_at
        ON funnel_sessions (expires_at);
    """)

    # Attribution table — permette query "da quale funnel è arrivato cliente X"
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS funnel_attributions (
            id                      BIGSERIAL PRIMARY KEY,
            client_id               UUID NOT NULL,
            session_id              VARCHAR(64) NOT NULL,
            first_funnel            funnel_type_enum NOT NULL,
            touchpoints             JSONB DEFAULT '[]'::jsonb,
            first_touch_at          TIMESTAMP WITH TIME ZONE NOT NULL,
            converted_at            TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_funnel_attributions_client
        ON funnel_attributions (client_id);
    """)

    logger.info("migration 109: funnel_sessions + funnel_attributions created")


async def rollback(conn: Any) -> None:
    await conn.execute("DROP TABLE IF EXISTS funnel_attributions;")
    await conn.execute("DROP TABLE IF EXISTS funnel_sessions;")
    await conn.execute("DROP TYPE IF EXISTS funnel_type_enum;")
    logger.info("migration 109: rolled back")
```

- [ ] **Step 2: Test migration apply + rollback (local postgres)**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. python -c "
import asyncio, asyncpg, os
from backend.migrations.migration_109_funnel_sessions import apply, rollback
async def main():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])
    await apply(conn)
    row = await conn.fetchrow(\"SELECT to_regclass('public.funnel_sessions')\")
    assert row[0] == 'funnel_sessions'
    await rollback(conn)
    row = await conn.fetchrow(\"SELECT to_regclass('public.funnel_sessions')\")
    assert row[0] is None
    await conn.close()
    print('✓ migration 109 apply+rollback OK')
asyncio.run(main())
"
```

Expected: `✓ migration 109 apply+rollback OK`.

- [ ] **Step 3: Apply to local dev DB for real**

```bash
PYTHONPATH=. python -c "
import asyncio, asyncpg, os
from backend.migrations.migration_109_funnel_sessions import apply
async def main():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])
    await apply(conn)
    await conn.close()
asyncio.run(main())
"
```

- [ ] **Step 4: Commit**

```bash
git add apps/backend-rag/backend/migrations/migration_109_funnel_sessions.py
git commit -m "feat(db): migration 109 — funnel_sessions + funnel_attributions"
```

---

## Task 17: Migration 110 — notification_prefs

**Files:**

- Create: `apps/backend-rag/backend/migrations/migration_110_notification_prefs.py`

- [ ] **Step 1: Implement migration**

```python
# apps/backend-rag/backend/migrations/migration_110_notification_prefs.py
"""
Migration 110: notification_prefs — preferenze notifica cliente.

Permette al cliente portal di scegliere canale: email, whatsapp, entrambi.
Usato da portal_deadline_watchdog (cron ogni 6h) e da qualsiasi servizio
che genera reminder utente.

Schema:
- user_id UUID PK (FK implicito a users.id)
- email_enabled BOOLEAN default TRUE
- wa_enabled BOOLEAN default FALSE
- wa_phone VARCHAR(20) NULL  (formato E.164, no +)
- updated_at TIMESTAMP

Reference: design 2026-04-17-v2-subdomain-rollout-design.md §4.3
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS notification_prefs (
            user_id         UUID PRIMARY KEY,
            email_enabled   BOOLEAN NOT NULL DEFAULT TRUE,
            wa_enabled      BOOLEAN NOT NULL DEFAULT FALSE,
            wa_phone        VARCHAR(20),
            updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)
    logger.info("migration 110: notification_prefs created")


async def rollback(conn: Any) -> None:
    await conn.execute("DROP TABLE IF EXISTS notification_prefs;")
    logger.info("migration 110: rolled back")
```

- [ ] **Step 2: Verify apply+rollback**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. python -c "
import asyncio, asyncpg, os
from backend.migrations.migration_110_notification_prefs import apply, rollback
async def main():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])
    await apply(conn)
    row = await conn.fetchrow(\"SELECT to_regclass('public.notification_prefs')\")
    assert row[0] == 'notification_prefs'
    await rollback(conn)
    await conn.close()
    print('✓ migration 110 OK')
asyncio.run(main())
"
```

- [ ] **Step 3: Commit**

```bash
git add apps/backend-rag/backend/migrations/migration_110_notification_prefs.py
git commit -m "feat(db): migration 110 — notification_prefs"
```

---

## Task 18: Backend endpoint — funnel session touch

**Files:**

- Create: `apps/backend-rag/backend/app/routers/funnel.py`
- Modify: `apps/backend-rag/backend/app/setup/router_registration.py` (add include)

- [ ] **Step 1: Write test**

```python
# apps/backend-rag/backend/tests/app/routers/test_funnel.py
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client(app):
    return TestClient(app)

def test_touch_creates_session(client):
    r = client.post("/api/funnel/session/touch", json={
        "session_id": "11111111-1111-4111-8111-111111111111",
        "funnel": "visa",
        "step_state": {"step": 1}
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True

def test_touch_rejects_bad_funnel(client):
    r = client.post("/api/funnel/session/touch", json={
        "session_id": "22222222-2222-4222-8222-222222222222",
        "funnel": "invalid"
    })
    assert r.status_code == 422
```

- [ ] **Step 2: Run — fail**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/app/routers/test_funnel.py -v
```

- [ ] **Step 3: Implement router**

```python
# apps/backend-rag/backend/app/routers/funnel.py
"""
Funnel session tracking — cross-funnel lead capture before auth.

Endpoint:
- POST /api/funnel/session/touch   upsert session + update last_touched_at
- POST /api/funnel/session/convert  set converted_to_client_id (called at login SSO)
"""

from __future__ import annotations

import hashlib
import logging
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from backend.app.dependencies import get_pg_pool

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/funnel", tags=["funnel"])


class FunnelType(str, Enum):
    VISA = "visa"
    KBLI = "kbli"
    TAX = "tax"
    PROPERTY = "property"
    HOME = "home"


class TouchRequest(BaseModel):
    session_id: str = Field(min_length=32, max_length=64)
    funnel: FunnelType
    step_state: dict[str, Any] = Field(default_factory=dict)
    lead_profile: dict[str, Any] = Field(default_factory=dict)


def _ip_hash(request: Request) -> str:
    ip = (request.headers.get("x-forwarded-for") or request.client.host or "").split(",")[0].strip()
    return hashlib.sha256(ip.encode()).hexdigest()[:64] if ip else ""


@router.post("/session/touch")
async def touch_session(req: TouchRequest, request: Request, pool=Depends(get_pg_pool)):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO funnel_sessions (session_id, funnel, step_state, lead_profile, ip_hash)
            VALUES ($1, $2, $3::jsonb, $4::jsonb, $5)
            ON CONFLICT (session_id) DO UPDATE SET
                funnel = EXCLUDED.funnel,
                step_state = funnel_sessions.step_state || EXCLUDED.step_state,
                lead_profile = funnel_sessions.lead_profile || EXCLUDED.lead_profile,
                last_touched_at = NOW()
            """,
            req.session_id,
            req.funnel.value,
            req.step_state,
            req.lead_profile,
            _ip_hash(request),
        )
    return {"ok": True}


class ConvertRequest(BaseModel):
    session_id: str
    client_id: str


@router.post("/session/convert")
async def convert_session(req: ConvertRequest, pool=Depends(get_pg_pool)):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE funnel_sessions
            SET converted_to_client_id = $2
            WHERE session_id = $1
            RETURNING funnel, first_touched_at
            """,
            req.session_id,
            req.client_id,
        )
        if row:
            await conn.execute(
                """
                INSERT INTO funnel_attributions (client_id, session_id, first_funnel, first_touch_at)
                VALUES ($1, $2, $3, $4)
                """,
                req.client_id,
                req.session_id,
                row["funnel"],
                row["first_touched_at"],
            )
    return {"ok": True}
```

- [ ] **Step 4: Register router**

Edit `apps/backend-rag/backend/app/setup/router_registration.py` (in `include_light_routers`):

```python
from backend.app.routers import funnel as funnel_router
# ... inside include_light_routers:
app.include_router(funnel_router.router)
```

- [ ] **Step 5: Run tests — pass**

```bash
PYTHONPATH=. pytest backend/tests/app/routers/test_funnel.py -v
```

- [ ] **Step 6: Commit**

```bash
git add apps/backend-rag/backend/app/routers/funnel.py apps/backend-rag/backend/app/setup/router_registration.py apps/backend-rag/backend/tests/app/routers/test_funnel.py
git commit -m "feat(api): funnel session touch+convert endpoints"
```

---

## Task 19: Backend endpoint — funnel analytics event

**Files:**

- Modify: `apps/backend-rag/backend/app/routers/funnel.py` (add event endpoint)

- [ ] **Step 1: Write test**

```python
# append to backend/tests/app/routers/test_funnel.py

def test_event_tracking(client):
    # first touch to create session
    client.post("/api/funnel/session/touch", json={
        "session_id": "33333333-3333-4333-8333-333333333333",
        "funnel": "kbli"
    })
    r = client.post("/api/analytics/funnel-event", json={
        "session_id": "33333333-3333-4333-8333-333333333333",
        "event": "kbli_code_viewed",
        "payload": {"code": "47111"}
    })
    assert r.status_code == 200
```

- [ ] **Step 2: Run — fail (404)**

- [ ] **Step 3: Create analytics router**

```python
# apps/backend-rag/backend/app/routers/analytics.py (new or extend existing)
"""Analytics funnel-event — dual-track with GA4 (client) + Postgres (here)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.dependencies import get_pg_pool

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["analytics"])

ALLOWED_EVENTS = {
    "visa_quiz_completed", "visa_result_viewed", "visa_chat_question",
    "visa_whatsapp_cta", "visa_calling_block",
    "kbli_code_viewed", "kbli_search", "kbli_chat_question",
    "tax_dashboard_viewed",
    "property_cta_clicked", "property_chat_question",
}


class FunnelEvent(BaseModel):
    session_id: str = Field(min_length=32, max_length=64)
    event: str
    payload: dict = Field(default_factory=dict)


@router.post("/funnel-event")
async def ingest_event(req: FunnelEvent, pool=Depends(get_pg_pool)):
    if req.event not in ALLOWED_EVENTS:
        return {"ok": False, "reason": "unknown_event"}
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE funnel_sessions
            SET step_state = step_state || jsonb_build_object('last_event', $2, 'last_event_at', to_jsonb(NOW())),
                last_touched_at = NOW()
            WHERE session_id = $1
            """,
            req.session_id, req.event,
        )
    return {"ok": True}
```

Register in `router_registration.py`:

```python
from backend.app.routers import analytics as analytics_router
app.include_router(analytics_router.router)
```

- [ ] **Step 4: Run test — pass**

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/app/routers/analytics.py apps/backend-rag/backend/app/setup/router_registration.py apps/backend-rag/backend/tests/app/routers/test_funnel.py
git commit -m "feat(api): analytics funnel-event ingest (11 whitelisted events)"
```

---

## Task 20: Wire mouth root layout to use ThemeProvider

**Files:**

- Modify: `apps/mouth/src/app/layout.tsx`

- [ ] **Step 1: Read current**

```bash
sed -n '160,200p' apps/mouth/src/app/layout.tsx
```

- [ ] **Step 2: Replace hardcoded `className="dark"` with ThemeProvider**

Find `<html lang="it" className="dark">` → replace with:

```tsx
<html lang="it" suppressHydrationWarning>
  <head>
    {/* Inline FOUC-prevention script — before any React hydration */}
    <script
      dangerouslySetInnerHTML={{
        __html: `
(function(){
  try {
    var stored = localStorage.getItem('bz-theme');
    var host = location.hostname;
    var def = stored;
    if (!def) {
      if (host.startsWith('kita.') || host.startsWith('prime.')) def = 'operative-dark';
      else if (host.startsWith('my.') || host.startsWith('zantara.')) def = 'operative-light';
      else def = 'editorial';
    }
    document.documentElement.setAttribute('data-theme', def);
  } catch(e) {}
})();
        `.trim(),
      }}
    />
  </head>
  <body>
    <ThemeProvider>{children}</ThemeProvider>
  </body>
</html>
```

- [ ] **Step 3: Typecheck + build**

```bash
cd ~/Desktop/nuzantara && npm run typecheck -w apps/mouth
npm run build -w apps/mouth 2>&1 | tail -20
```

Expected: build OK.

- [ ] **Step 4: Commit**

```bash
git add apps/mouth/src/app/layout.tsx
git commit -m "feat(mouth): ThemeProvider + FOUC-prevention, remove hardcoded dark class"
```

---

## Task 21: Final gate — all tests + typecheck + lint

- [ ] **Step 1: Run all core tests**

```bash
cd ~/Desktop/nuzantara/packages/core && npx vitest run
```

Expected: all PASS.

- [ ] **Step 2: Run backend tests**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/app/routers/test_funnel.py backend/tests/services/rag/test_confidence.py -q
```

Expected: all PASS.

- [ ] **Step 3: Typecheck mouth**

```bash
cd ~/Desktop/nuzantara && npm run typecheck -w apps/mouth
```

- [ ] **Step 4: Review diff on branch**

```bash
git log --oneline main..v2-foundation
```

Expected: ~20 commit messages, one per task.

- [ ] **Step 5: Federation review (optional but recommended)**

```bash
./scripts/ai-dispatch.sh codex-review --diff main..v2-foundation
```

- [ ] **Step 6: Merge to main (after user approval)**

```bash
git checkout main
git merge --no-ff v2-foundation -m "Merge v2-foundation: packages/core extended + migrations 109/110"
```

---

## Exit criteria

- ✅ 8 nuovi componenti in `@balizero/core` esportati + testati
- ✅ 2 utility (ical, wa-deeplink) + session-bridge + funnel-view analytics
- ✅ Migrations 109, 110 applicate + rollback testati
- ✅ 2 backend endpoint (funnel session + analytics event) + tests green
- ✅ `apps/mouth/src/app/layout.tsx` senza `className="dark"` hardcoded, FOUC-prevention inline
- ✅ Tutti i test verdi, typecheck clean, 0 lint error
- ✅ Pronti per sub-plan 02 (L1 Funnel Hub) che **usa** questi componenti
