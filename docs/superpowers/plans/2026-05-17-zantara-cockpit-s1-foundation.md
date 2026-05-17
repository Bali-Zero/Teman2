# Zantara Cockpit — S1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Foundation of Zantara Cockpit at `localhost:3100/cockpit`: Bloomberg neon-green theme + 12-widget grid skeleton + 2 LIVE widget (GlobalPulse + DecisionsAttesa) + intent-table action skeleton + PIN auth + rate-limit + HMAC audit + start script. Smoke: page opens, 2 widget work, PIN gate enforced, allowlist+reason validated, no DB writes to live tables.

**Architecture:** Extend existing `apps/admin-dashboard-local/` (Next.js 16.1.6). New `/cockpit` route with 4×3 grid. New CSS `cockpit-shell.css`. New `lib/cockpit-*.ts` helpers. 2 PG migrations (180 audit + 181 intents). bcrypt PIN in middleware. NO SSE in S1 (polling only).

**Tech Stack:** Next.js 16.1.6 App Router, React 18, Tailwind 3.4, JetBrains Mono via `next/font/google`, bcryptjs 3.0.3 (root), pg 8, launchctl subprocess, gh CLI subprocess, Node crypto HMAC.

**Spec reference:** `docs/superpowers/specs/2026-05-17-zantara-cockpit-design.md` (committed `a423c98bb`)

---

## File Structure (S1)

| Path                                                                                                                              | Action                |
| --------------------------------------------------------------------------------------------------------------------------------- | --------------------- |
| `apps/backend-rag/backend/db/migrations_v2/180_cockpit_audit_log.sql`                                                             | CREATE                |
| `apps/backend-rag/backend/db/migrations_v2/181_cockpit_intents.sql`                                                               | CREATE                |
| `apps/admin-dashboard-local/package.json`                                                                                         | MODIFY (+bcryptjs)    |
| `apps/admin-dashboard-local/app/cockpit/{layout,page}.tsx`                                                                        | CREATE                |
| `apps/admin-dashboard-local/app/cockpit/cockpit-shell.css`                                                                        | CREATE                |
| `apps/admin-dashboard-local/lib/cockpit-{allowlist,auth,audit,launchctl,pg}.ts`                                                   | CREATE (5 files)      |
| `apps/admin-dashboard-local/middleware.ts`                                                                                        | CREATE                |
| `apps/admin-dashboard-local/app/api/cockpit/{auth,cron/list,cron/run,decisions,intent/create}/route.ts`                           | CREATE (5 endpoints)  |
| `apps/admin-dashboard-local/components/cockpit/{WidgetFrame,StatusDot,WidgetPlaceholder,GlobalPulse,DecisionsAttesa,PinGate}.tsx` | CREATE (6 components) |
| `apps/admin-dashboard-local/scripts/{setup-cockpit-pin,start-cockpit}.sh`                                                         | CREATE                |
| `apps/admin-dashboard-local/tests/cockpit/{allowlist,auth,audit}.test.ts`                                                         | CREATE                |

---

### Task 1: Verify pre-conditions

- [ ] **Step 1**: `ls apps/backend-rag/backend/db/migrations_v2/ | grep -E '^(180|181)_'` → expected empty
- [ ] **Step 2**: `cd ~/Desktop/nuzantara-wt-cockpit && npm ls bcryptjs 2>&1 | head -3` → expected `bcryptjs@3.0.3`
- [ ] **Step 3**: `cd ~/Desktop/nuzantara-wt-cockpit && git status --short` → expected empty (post-spec-commit)
- [ ] **Step 4**: Confirm proceed

---

### Task 2: Migration 180 — cockpit_audit_log

**Files:** Create `apps/backend-rag/backend/db/migrations_v2/180_cockpit_audit_log.sql`

- [ ] **Step 1: Write SQL**

```sql
-- 180_cockpit_audit_log.sql
-- Immutable audit log with HMAC chain integrity
-- === FORWARD ===
CREATE TABLE IF NOT EXISTS cockpit_audit_log (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor TEXT NOT NULL DEFAULT 'antonello',
    action TEXT NOT NULL,
    params_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    result TEXT NOT NULL CHECK (result IN ('success', 'denied', 'error')),
    error_message TEXT,
    hmac_sha256 TEXT NOT NULL,
    prev_hmac TEXT
);

CREATE INDEX IF NOT EXISTS idx_cockpit_audit_log_recent ON cockpit_audit_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cockpit_audit_log_action ON cockpit_audit_log (action, created_at DESC);

COMMENT ON TABLE cockpit_audit_log IS 'Immutable audit log for Zantara Cockpit. hmac_sha256 = HMAC(secret, prev_hmac || row_serialized). Tampering detectable by chain replay.';

-- === ROLLBACK ===
-- DROP INDEX IF EXISTS idx_cockpit_audit_log_action;
-- DROP INDEX IF EXISTS idx_cockpit_audit_log_recent;
-- DROP TABLE IF EXISTS cockpit_audit_log;
```

- [ ] **Step 2**: `grep -E '^(CREATE|DROP|COMMENT)' apps/backend-rag/backend/db/migrations_v2/180_cockpit_audit_log.sql` → 7 lines
- [ ] **Step 3**: `git add ... && git commit -m "feat(cockpit): migration 180 cockpit_audit_log with HMAC chain"`

---

### Task 3: Migration 181 — cockpit_intents

**Files:** Create `apps/backend-rag/backend/db/migrations_v2/181_cockpit_intents.sql`

- [ ] **Step 1: Write SQL**

```sql
-- 181_cockpit_intents.sql
-- Intent queue: cockpit writes here, existing services consume
-- Decouples UI from production state machines
-- === FORWARD ===
CREATE TABLE IF NOT EXISTS cockpit_intents (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    intent_type TEXT NOT NULL,
    params_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'consumed', 'rejected', 'expired')),
    consumer TEXT,
    consumed_at TIMESTAMPTZ,
    error_message TEXT,
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '24 hours')
);

CREATE INDEX IF NOT EXISTS idx_cockpit_intents_pending ON cockpit_intents (intent_type, created_at) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_cockpit_intents_expires ON cockpit_intents (expires_at) WHERE status = 'pending';

COMMENT ON TABLE cockpit_intents IS 'Intent queue from Zantara Cockpit. Consumers: intel-lake-router-cron.sh (intel.skip/rerun), wr2_supervisor.py (wr2.approve/reject), manual review (cron.kill, library.*).';

-- === ROLLBACK ===
-- DROP INDEX IF EXISTS idx_cockpit_intents_expires;
-- DROP INDEX IF EXISTS idx_cockpit_intents_pending;
-- DROP TABLE IF EXISTS cockpit_intents;
```

- [ ] **Step 2**: grep verify (similar to Task 2)
- [ ] **Step 3**: commit `feat(cockpit): migration 181 cockpit_intents queue`

---

### Task 4: Add bcryptjs to admin-dashboard-local

**Files:** Modify `apps/admin-dashboard-local/package.json`

- [ ] **Step 1**: Add to `dependencies`: `"bcryptjs": "^3.0.3"`
- [ ] **Step 2**: `cd apps/admin-dashboard-local && npm install bcryptjs --silent`
- [ ] **Step 3**: `node -e "console.log(require('bcryptjs').hashSync('test', 10))"` → bcrypt hash output
- [ ] **Step 4**: commit `chore(cockpit): declare bcryptjs dep`

---

### Task 5: Bloomberg theme CSS

**Files:** Create `apps/admin-dashboard-local/app/cockpit/cockpit-shell.css`

- [ ] **Step 1: Write CSS** (full content):

```css
:root[data-cockpit="true"] {
  --bg-deep: #0a0e0a;
  --bg-panel: #0f1411;
  --fg-primary: #00ff41;
  --fg-active: #39ff14;
  --fg-dim: #4a7a4a;
  --fg-amber: #ffb000;
  --fg-red: #ff3838;
  --border: #1f2a1f;
  --border-active: #00ff41;
}

[data-cockpit="true"] body {
  background: var(--bg-deep);
  color: var(--fg-primary);
  font-family: "JetBrains Mono", ui-monospace, monospace;
  font-size: 13px;
  line-height: 1.4;
}

[data-cockpit="true"] .cockpit-widget {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  padding: 8px 12px;
  min-height: 200px;
  font-feature-settings: "tnum" 1;
}

[data-cockpit="true"] .cockpit-widget-title {
  color: var(--fg-active);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 8px;
}

[data-cockpit="true"] .cockpit-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  padding: 8px;
}

[data-cockpit="true"] .status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
}

[data-cockpit="true"] .status-dot.green {
  background: var(--fg-primary);
  box-shadow: 0 0 4px var(--fg-primary);
  animation: pulse 2s infinite;
}
[data-cockpit="true"] .status-dot.amber {
  background: var(--fg-amber);
  box-shadow: 0 0 4px var(--fg-amber);
}
[data-cockpit="true"] .status-dot.red {
  background: var(--fg-red);
  box-shadow: 0 0 4px var(--fg-red);
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

[data-cockpit="true"] .cockpit-action-button {
  background: var(--bg-deep);
  color: var(--fg-active);
  border: 1px solid var(--border-active);
  padding: 4px 10px;
  font-family: inherit;
  font-size: 11px;
  cursor: pointer;
}
[data-cockpit="true"] .cockpit-action-button:hover {
  background: var(--border);
}
[data-cockpit="true"] .cockpit-action-button.danger {
  border-color: var(--fg-red);
  color: var(--fg-red);
}
```

- [ ] **Step 2**: `npx prettier --write app/cockpit/cockpit-shell.css`
- [ ] **Step 3**: commit `feat(cockpit): Bloomberg CSS theme`

---

### Task 6: Cockpit layout — JetBrains Mono

**Files:** Create `apps/admin-dashboard-local/app/cockpit/layout.tsx`

- [ ] **Step 1: Write**

```tsx
import { JetBrains_Mono } from "next/font/google";
import "./cockpit-shell.css";

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
  variable: "--font-jetbrains-mono",
});

export const metadata = { title: "Zantara Cockpit" };

export default function CockpitLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      data-cockpit="true"
      className={`dark ${jetbrains.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}
```

- [ ] **Step 2**: `LOCAL_ONLY=1 npx next build 2>&1 | grep -E "error|Failed"` → no errors related
- [ ] **Step 3**: commit `feat(cockpit): layout shell with JetBrains Mono`

---

### Task 7: WidgetFrame + StatusDot + Placeholder components

**Files:** Create `components/cockpit/{WidgetFrame,StatusDot,WidgetPlaceholder}.tsx`

- [ ] **Step 1: WidgetFrame.tsx**

```tsx
import { ReactNode } from "react";

export interface WidgetFrameProps {
  title: string;
  children: ReactNode;
  status?: "green" | "amber" | "red";
}

export function WidgetFrame({ title, children, status }: WidgetFrameProps) {
  return (
    <div className="cockpit-widget">
      <div className="cockpit-widget-title">
        {status && <span className={`status-dot ${status}`} aria-hidden />}
        {title}
      </div>
      <div className="cockpit-widget-body">{children}</div>
    </div>
  );
}
```

- [ ] **Step 2: StatusDot.tsx**

```tsx
export type StatusColor = "green" | "amber" | "red";

export function StatusDot({
  status,
  label,
}: {
  status: StatusColor;
  label?: string;
}) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center" }}>
      <span className={`status-dot ${status}`} aria-hidden />
      {label && <span style={{ marginLeft: 6 }}>{label}</span>}
    </span>
  );
}
```

- [ ] **Step 3: WidgetPlaceholder.tsx**

```tsx
import { WidgetFrame } from "./WidgetFrame";

export function WidgetPlaceholder({
  title,
  deferTo,
}: {
  title: string;
  deferTo: string;
}) {
  return (
    <WidgetFrame title={title} status="amber">
      <div style={{ color: "var(--fg-dim)", fontSize: 11 }}>
        deferred to {deferTo}
      </div>
    </WidgetFrame>
  );
}
```

- [ ] **Step 4**: commit `feat(cockpit): WidgetFrame + StatusDot + Placeholder`

---

### Task 8: 12-widget grid page

**Files:** Create `apps/admin-dashboard-local/app/cockpit/page.tsx`

- [ ] **Step 1: Write** (GlobalPulse + DecisionsAttesa imports will resolve after Tasks 20-21)

```tsx
import { WidgetPlaceholder } from "@/components/cockpit/WidgetPlaceholder";
import { GlobalPulse } from "@/components/cockpit/GlobalPulse";
import { DecisionsAttesa } from "@/components/cockpit/DecisionsAttesa";

export const dynamic = "force-dynamic";

export default function CockpitPage() {
  return (
    <main className="cockpit-grid">
      {/* Global */}
      <GlobalPulse />
      <DecisionsAttesa />
      <WidgetPlaceholder title="Cosa Ha Imparato" deferTo="S5" />
      <WidgetPlaceholder title="Comandi Rapidi" deferTo="S5" />
      {/* Intel-Lake */}
      <WidgetPlaceholder title="Intel Pipeline Live" deferTo="S2" />
      <WidgetPlaceholder title="Source Health" deferTo="S2" />
      <WidgetPlaceholder title="NB Push Log" deferTo="S2" />
      <WidgetPlaceholder title="Intel Manual Override" deferTo="S2" />
      {/* WR2 */}
      <WidgetPlaceholder title="WR2 Drafts Pipeline" deferTo="S3" />
      <WidgetPlaceholder title="WR2 IG Metrics" deferTo="S3" />
      <WidgetPlaceholder title="Canva Status" deferTo="S3" />
      <WidgetPlaceholder title="WR2 Manual Override" deferTo="S3" />
    </main>
  );
}
```

- [ ] **Step 2**: defer build verify until Tasks 20-21 done (imports will resolve)
- [ ] **Step 3**: commit `feat(cockpit): 12-widget grid skeleton`

---

### Task 9: Allowlist 35 agentic cron + test

**Files:** Create `lib/cockpit-allowlist.ts` + `tests/cockpit/allowlist.test.ts`

- [ ] **Step 1: Test first (TDD)**

```ts
// tests/cockpit/allowlist.test.ts
import { describe, it, expect } from "vitest";
import {
  isAgenticCronLabel,
  AGENTIC_CRON_ALLOWLIST,
} from "@/lib/cockpit-allowlist";

describe("cockpit-allowlist", () => {
  it("has exactly 35 entries", () => {
    expect(AGENTIC_CRON_ALLOWLIST.length).toBe(35);
  });
  it("all start with com.balizero. or com.matagaruda.", () => {
    for (const label of AGENTIC_CRON_ALLOWLIST) {
      expect(label).toMatch(/^com\.(balizero|matagaruda)\./);
    }
  });
  it("whitelisted labels return true", () => {
    expect(isAgenticCronLabel("com.balizero.regulatory-watcher")).toBe(true);
  });
  it("non-whitelisted return false", () => {
    expect(isAgenticCronLabel("com.apple.dock")).toBe(false);
    expect(isAgenticCronLabel("")).toBe(false);
  });
  it("rejects null/undefined", () => {
    expect(isAgenticCronLabel(null as any)).toBe(false);
    expect(isAgenticCronLabel(undefined as any)).toBe(false);
  });
});
```

- [ ] **Step 2**: `npx vitest run tests/cockpit/allowlist.test.ts` → FAIL (module missing)
- [ ] **Step 3: Implementation**

```ts
// lib/cockpit-allowlist.ts
export const AGENTIC_CRON_ALLOWLIST: readonly string[] = Object.freeze([
  "com.balizero.regulatory-watcher",
  "com.balizero.intel.nightly",
  "com.balizero.intel-lake-router.5min",
  "com.balizero.intel-lake-nb-pusher.15min",
  "com.balizero.intel-lake.outbox-drain.minute",
  "com.balizero.intel-lake.shadow-validate.6h",
  "com.balizero.intel-radar-daily-digest",
  "com.balizero.intel-dedup-gateway",
  "com.balizero.wr2.draft-generator",
  "com.balizero.wr2.fact-checker",
  "com.balizero.wr2.fact-extractor",
  "com.balizero.wr2.image-generator",
  "com.balizero.wr2.canva-renderer",
  "com.balizero.wr2.canva-apply",
  "com.balizero.wr2.canva-gc.weekly",
  "com.balizero.wr2.connector",
  "com.balizero.wr2.dossier-compiler",
  "com.balizero.wr2.measurer",
  "com.balizero.wr2.daily-metrics",
  "com.balizero.wr2.sla-worker",
  "com.balizero.wr2.trend-hunter",
  "com.balizero.wr2.voyager.weekly",
  "com.balizero.wr2.reflexion.weekly",
  "com.balizero.wr2.external-bench.monthly",
  "com.balizero.wr2.ig-metrics-analyst.weekly",
  "com.balizero.wr2.hardening",
  "com.balizero.wr2.queue-server",
  "com.balizero.bali-intel-scraper.daily",
  "com.balizero.competitor-monitor.monthly",
  "com.balizero.email-template-builder",
  "com.balizero.yield-optimizer.weekly",
  "com.matagaruda.bridge.adaptive",
  "com.matagaruda.gap.consumer",
  "com.matagaruda.invalidation-sweep",
  "com.balizero.meta-dispatcher",
]) as readonly string[];

export function isAgenticCronLabel(label: string | null | undefined): boolean {
  if (!label || typeof label !== "string") return false;
  return (AGENTIC_CRON_ALLOWLIST as readonly string[]).includes(label);
}
```

- [ ] **Step 4**: tests PASS (5/5)
- [ ] **Step 5**: commit `feat(cockpit): 35 agentic cron allowlist + tests`

---

### Task 10: cockpit-auth — PIN bcrypt + rate-limit + tests

**Files:** Create `lib/cockpit-auth.ts` + `tests/cockpit/auth.test.ts`

- [ ] **Step 1: Test first**

```ts
import { describe, it, expect, beforeEach } from "vitest";
import bcrypt from "bcryptjs";
import {
  verifyPin,
  recordFailure,
  isLockedOut,
  resetRateLimit,
} from "@/lib/cockpit-auth";

describe("cockpit-auth", () => {
  beforeEach(() => {
    resetRateLimit("test");
  });
  it("verifyPin correct", async () => {
    const hash = bcrypt.hashSync("123456", 10);
    expect(await verifyPin("123456", hash)).toBe(true);
  });
  it("verifyPin wrong", async () => {
    const hash = bcrypt.hashSync("123456", 10);
    expect(await verifyPin("999999", hash)).toBe(false);
  });
  it("isLockedOut false initially", () => {
    expect(isLockedOut("test")).toBe(false);
  });
  it("5 failures → locked", () => {
    for (let i = 0; i < 5; i++) recordFailure("test");
    expect(isLockedOut("test")).toBe(true);
  });
  it("4 failures → not locked", () => {
    for (let i = 0; i < 4; i++) recordFailure("test");
    expect(isLockedOut("test")).toBe(false);
  });
  it("lockout 5min duration", () => {
    for (let i = 0; i < 5; i++) recordFailure("test");
    const orig = Date.now;
    Date.now = () => orig() + 5 * 60 * 1000 + 1000;
    expect(isLockedOut("test")).toBe(false);
    Date.now = orig;
  });
});
```

- [ ] **Step 2**: FAIL
- [ ] **Step 3: Implementation**

```ts
// lib/cockpit-auth.ts
import bcrypt from "bcryptjs";

const MAX_FAILURES = 5;
const WINDOW_MS = 5 * 60 * 1000;
const LOCKOUT_MS = 5 * 60 * 1000;

interface FailureRecord {
  count: number;
  firstFailureAt: number;
  lockedUntil: number;
}
const failureMap = new Map<string, FailureRecord>();

export async function verifyPin(pin: string, hash: string): Promise<boolean> {
  if (!pin || !hash || typeof pin !== "string") return false;
  try {
    return await bcrypt.compare(pin, hash);
  } catch {
    return false;
  }
}

export function recordFailure(clientId: string): void {
  const now = Date.now();
  const r = failureMap.get(clientId);
  if (!r || now - r.firstFailureAt > WINDOW_MS) {
    failureMap.set(clientId, { count: 1, firstFailureAt: now, lockedUntil: 0 });
    return;
  }
  r.count += 1;
  if (r.count >= MAX_FAILURES) r.lockedUntil = now + LOCKOUT_MS;
}

export function isLockedOut(clientId: string): boolean {
  const r = failureMap.get(clientId);
  if (!r) return false;
  const now = Date.now();
  if (r.lockedUntil > 0 && now < r.lockedUntil) return true;
  if (r.lockedUntil > 0 && now >= r.lockedUntil) {
    failureMap.delete(clientId);
    return false;
  }
  return false;
}

export function resetRateLimit(clientId: string): void {
  failureMap.delete(clientId);
}

export function readPinHash(): string | null {
  const fs = require("node:fs");
  const path = require("node:path");
  const os = require("node:os");
  const p = path.join(os.homedir(), ".config/zantara-cockpit/pin.hash");
  try {
    return fs.readFileSync(p, "utf8").trim();
  } catch {
    return null;
  }
}
```

- [ ] **Step 4**: tests PASS (6/6)
- [ ] **Step 5**: commit `feat(cockpit): bcrypt PIN + rate-limit (5 fail → 5min)`

---

### Task 11: cockpit-audit — HMAC chain + tests

**Files:** Create `lib/cockpit-audit.ts` + `tests/cockpit/audit.test.ts`

- [ ] **Step 1: Test first**

```ts
import { describe, it, expect } from "vitest";
import { computeAuditHmac, verifyAuditChain } from "@/lib/cockpit-audit";

describe("cockpit-audit", () => {
  const SECRET = "test-hmac-key-XXXXX";
  it("deterministic", () => {
    const row = {
      action: "a",
      params_json: {},
      created_at: "t",
      result: "success" as const,
    };
    expect(computeAuditHmac(SECRET, null, row)).toBe(
      computeAuditHmac(SECRET, null, row),
    );
  });
  it("hmac changes with prev", () => {
    const row = {
      action: "a",
      params_json: {},
      created_at: "t",
      result: "success" as const,
    };
    expect(computeAuditHmac(SECRET, null, row)).not.toBe(
      computeAuditHmac(SECRET, "abc", row),
    );
  });
  it("genesis valid", () => {
    const row: any = {
      id: 1n,
      action: "a",
      params_json: {},
      created_at: "t",
      result: "success",
      prev_hmac: null,
    };
    row.hmac_sha256 = computeAuditHmac(SECRET, null, row);
    expect(verifyAuditChain(SECRET, [row])).toEqual({ valid: true });
  });
  it("tamper detect", () => {
    const r: any = {
      id: 1n,
      action: "a",
      params_json: {},
      created_at: "t",
      result: "success",
      prev_hmac: null,
    };
    r.hmac_sha256 = computeAuditHmac(SECRET, null, r);
    const tampered = { ...r, action: "b" };
    expect(verifyAuditChain(SECRET, [tampered])).toEqual({
      valid: false,
      tamperedAt: 1n,
    });
  });
});
```

- [ ] **Step 2**: FAIL
- [ ] **Step 3: Implementation**

```ts
// lib/cockpit-audit.ts
import { createHmac } from "node:crypto";

export interface AuditRow {
  id?: bigint;
  action: string;
  params_json: Record<string, unknown>;
  created_at: string;
  result: "success" | "denied" | "error";
  error_message?: string | null;
  prev_hmac?: string | null;
  hmac_sha256?: string;
}

function serializeForHmac(row: AuditRow): string {
  return JSON.stringify({
    action: row.action,
    params_json: row.params_json,
    created_at: row.created_at,
    result: row.result,
    error_message: row.error_message ?? null,
  });
}

export function computeAuditHmac(
  secret: string,
  prevHmac: string | null,
  row: AuditRow,
): string {
  const payload = (prevHmac ?? "") + serializeForHmac(row);
  return createHmac("sha256", secret).update(payload).digest("hex");
}

export interface ChainVerification {
  valid: boolean;
  tamperedAt?: bigint;
}

export function verifyAuditChain(
  secret: string,
  rows: AuditRow[],
): ChainVerification {
  let prev: string | null = null;
  for (const row of rows) {
    if (computeAuditHmac(secret, prev, row) !== row.hmac_sha256) {
      return { valid: false, tamperedAt: row.id };
    }
    prev = row.hmac_sha256 ?? null;
  }
  return { valid: true };
}

export function readHmacSecret(): string | null {
  return process.env.COCKPIT_HMAC_KEY || null;
}
```

- [ ] **Step 4**: tests PASS (4/4)
- [ ] **Step 5**: commit `feat(cockpit): HMAC SHA-256 audit chain`

---

### Task 12: cockpit-launchctl helper

**Files:** Create `lib/cockpit-launchctl.ts`

- [ ] **Step 1: Implementation**

```ts
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { AGENTIC_CRON_ALLOWLIST } from "./cockpit-allowlist";

const execFileAsync = promisify(execFile);

export interface CronStatus {
  label: string;
  state: "running" | "waiting" | "not_loaded";
  lastExitStatus: number | null;
  pid: number | null;
}

const cache = new Map<string, { value: CronStatus; expiresAt: number }>();
const CACHE_MS = 2000;

async function getCronStatusUncached(label: string): Promise<CronStatus> {
  const uid = process.getuid?.() ?? 501;
  try {
    const { stdout } = await execFileAsync(
      "launchctl",
      ["print", `gui/${uid}/${label}`],
      { timeout: 3000 },
    );
    const stateMatch = stdout.match(/state\s*=\s*(\w+)/);
    const exitMatch = stdout.match(/last exit code\s*=\s*(-?\d+)/);
    const pidMatch = stdout.match(/pid\s*=\s*(\d+)/);
    const state = stateMatch?.[1];
    return {
      label,
      state:
        state === "running"
          ? "running"
          : state === "waiting"
            ? "waiting"
            : "not_loaded",
      lastExitStatus: exitMatch ? parseInt(exitMatch[1], 10) : null,
      pid: pidMatch ? parseInt(pidMatch[1], 10) : null,
    };
  } catch {
    return { label, state: "not_loaded", lastExitStatus: null, pid: null };
  }
}

export async function getCronStatus(label: string): Promise<CronStatus> {
  const cached = cache.get(label);
  const now = Date.now();
  if (cached && cached.expiresAt > now) return cached.value;
  const value = await getCronStatusUncached(label);
  cache.set(label, { value, expiresAt: now + CACHE_MS });
  return value;
}

export async function getAllAgenticCronStatus(): Promise<CronStatus[]> {
  return Promise.all(AGENTIC_CRON_ALLOWLIST.map(getCronStatus));
}

export async function startCron(
  label: string,
): Promise<{ ok: boolean; stderr?: string }> {
  if (!AGENTIC_CRON_ALLOWLIST.includes(label as never)) {
    return { ok: false, stderr: "not in allowlist" };
  }
  const uid = process.getuid?.() ?? 501;
  try {
    await execFileAsync("launchctl", ["kickstart", `gui/${uid}/${label}`], {
      timeout: 5000,
    });
    cache.delete(label);
    return { ok: true };
  } catch (e: any) {
    return { ok: false, stderr: e.message };
  }
}
```

- [ ] **Step 2**: build verify no error
- [ ] **Step 3**: commit `feat(cockpit): launchctl helper with 2s cache`

---

### Task 13: cockpit-pg — query + audit insert + intent create

**Files:** Create `lib/cockpit-pg.ts`

- [ ] **Step 1: Implementation**

```ts
import { getDb } from "@/app/lib/db";
import { computeAuditHmac } from "./cockpit-audit";

export interface IntelStats {
  unrouted: number;
  routed_recent: number;
  needs_review: number;
  skipped: number;
}

export async function getIntelStats(): Promise<IntelStats> {
  const db = await getDb();
  const { rows } = await db.query<{ routing_status: string; n: string }>(
    `SELECT routing_status, COUNT(*)::text AS n FROM intel_items WHERE first_seen_at > NOW() - INTERVAL '30 days' GROUP BY routing_status`,
  );
  const s: IntelStats = {
    unrouted: 0,
    routed_recent: 0,
    needs_review: 0,
    skipped: 0,
  };
  for (const r of rows) {
    const n = parseInt(r.n, 10);
    if (r.routing_status === "unrouted") s.unrouted = n;
    else if (r.routing_status === "needs_review") s.needs_review = n;
    else if (r.routing_status === "skip") s.skipped = n;
    else s.routed_recent += n;
  }
  return s;
}

export interface AuditInsertParams {
  action: string;
  params: Record<string, unknown>;
  result: "success" | "denied" | "error";
  errorMessage?: string;
}

export async function insertAuditRow(
  hmacSecret: string,
  p: AuditInsertParams,
): Promise<bigint> {
  const db = await getDb();
  const { rows: prev } = await db.query<{ hmac_sha256: string }>(
    `SELECT hmac_sha256 FROM cockpit_audit_log ORDER BY id DESC LIMIT 1`,
  );
  const prevHmac = prev[0]?.hmac_sha256 ?? null;
  const createdAt = new Date().toISOString();
  const hmac = computeAuditHmac(hmacSecret, prevHmac, {
    action: p.action,
    params_json: p.params,
    created_at: createdAt,
    result: p.result,
    error_message: p.errorMessage ?? null,
  });
  const { rows } = await db.query<{ id: string }>(
    `INSERT INTO cockpit_audit_log (action, params_json, result, error_message, hmac_sha256, prev_hmac)
     VALUES ($1, $2::jsonb, $3, $4, $5, $6) RETURNING id::text`,
    [
      p.action,
      JSON.stringify(p.params),
      p.result,
      p.errorMessage ?? null,
      hmac,
      prevHmac,
    ],
  );
  return BigInt(rows[0].id);
}

export async function createIntent(
  intentType: string,
  params: Record<string, unknown>,
  reason: string,
): Promise<bigint> {
  const db = await getDb();
  const { rows } = await db.query<{ id: string }>(
    `INSERT INTO cockpit_intents (intent_type, params_json, reason) VALUES ($1, $2::jsonb, $3) RETURNING id::text`,
    [intentType, JSON.stringify(params), reason],
  );
  return BigInt(rows[0].id);
}
```

- [ ] **Step 2**: build verify
- [ ] **Step 3**: commit `feat(cockpit): PG helpers + audit + intent insert`

---

### Task 14: Middleware — origin + PIN gate

**Files:** Create `apps/admin-dashboard-local/middleware.ts`

- [ ] **Step 1: Write**

```ts
import { NextResponse, type NextRequest } from "next/server";

export const config = { matcher: ["/cockpit/:path*", "/api/cockpit/:path*"] };
const VALID_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

export function middleware(req: NextRequest) {
  const host = req.headers.get("host")?.split(":")[0] ?? "";
  if (!VALID_HOSTS.has(host)) {
    return new NextResponse("Forbidden: localhost-only", { status: 403 });
  }
  const isAuthRoute = req.nextUrl.pathname === "/api/cockpit/auth";
  const pinCookie = req.cookies.get("cockpit-session")?.value;
  if (!isAuthRoute && !pinCookie) {
    if (req.nextUrl.pathname.startsWith("/api/cockpit/")) {
      return new NextResponse(JSON.stringify({ error: "unauthorized" }), {
        status: 401,
        headers: { "content-type": "application/json" },
      });
    }
  }
  return NextResponse.next();
}
```

- [ ] **Step 2**: build verify
- [ ] **Step 3**: commit `feat(cockpit): middleware origin + PIN gate`

---

### Task 15: API /api/cockpit/auth

**Files:** Create `app/api/cockpit/auth/route.ts`

- [ ] **Step 1: Write**

```ts
import { NextRequest, NextResponse } from "next/server";
import {
  verifyPin,
  recordFailure,
  isLockedOut,
  readPinHash,
  resetRateLimit,
} from "@/lib/cockpit-auth";
import { insertAuditRow } from "@/lib/cockpit-pg";
import { readHmacSecret } from "@/lib/cockpit-audit";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const clientId = req.headers.get("x-forwarded-for") ?? "localhost";
  const hmacSecret = readHmacSecret();

  if (isLockedOut(clientId)) {
    if (hmacSecret)
      await insertAuditRow(hmacSecret, {
        action: "auth.pin",
        params: {},
        result: "denied",
        errorMessage: "rate-limited",
      });
    return NextResponse.json({ error: "rate_limited" }, { status: 429 });
  }

  const body = await req.json().catch(() => ({}));
  const pin = typeof body.pin === "string" ? body.pin : "";
  const pinHash = readPinHash();
  if (!pinHash) {
    return NextResponse.json({ error: "pin_not_configured" }, { status: 503 });
  }

  const ok = await verifyPin(pin, pinHash);
  if (hmacSecret)
    await insertAuditRow(hmacSecret, {
      action: "auth.pin",
      params: {},
      result: ok ? "success" : "denied",
    });

  if (!ok) {
    recordFailure(clientId);
    return NextResponse.json({ error: "invalid_pin" }, { status: 401 });
  }

  resetRateLimit(clientId);
  const res = NextResponse.json({ ok: true });
  res.cookies.set("cockpit-session", "1", {
    httpOnly: true,
    sameSite: "strict",
    secure: false,
    maxAge: 60 * 60 * 12,
    path: "/",
  });
  return res;
}
```

- [ ] **Step 2**: build verify
- [ ] **Step 3**: commit `feat(cockpit): POST /api/cockpit/auth`

---

### Task 16: API /api/cockpit/cron/list

**Files:** Create `app/api/cockpit/cron/list/route.ts`

- [ ] **Step 1: Write**

```ts
import { NextResponse } from "next/server";
import { getAllAgenticCronStatus } from "@/lib/cockpit-launchctl";

export const dynamic = "force-dynamic";

export async function GET() {
  const statuses = await getAllAgenticCronStatus();
  const counts = {
    running: statuses.filter((s) => s.state === "running").length,
    waiting: statuses.filter((s) => s.state === "waiting").length,
    not_loaded: statuses.filter((s) => s.state === "not_loaded").length,
    failed: statuses.filter(
      (s) => s.lastExitStatus !== null && s.lastExitStatus !== 0,
    ).length,
  };
  return NextResponse.json({ statuses, counts });
}
```

- [ ] **Step 2**: commit

---

### Task 17: API /api/cockpit/cron/run

**Files:** Create `app/api/cockpit/cron/run/route.ts`

- [ ] **Step 1: Write**

```ts
import { NextRequest, NextResponse } from "next/server";
import { isAgenticCronLabel } from "@/lib/cockpit-allowlist";
import { startCron } from "@/lib/cockpit-launchctl";
import { insertAuditRow } from "@/lib/cockpit-pg";
import { readHmacSecret } from "@/lib/cockpit-audit";
import { isLockedOut, recordFailure } from "@/lib/cockpit-auth";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const clientId = req.headers.get("x-forwarded-for") ?? "localhost";
  if (isLockedOut(clientId))
    return NextResponse.json({ error: "rate_limited" }, { status: 429 });

  const body = await req.json().catch(() => ({}));
  const label = typeof body.label === "string" ? body.label : "";
  const reason = typeof body.reason === "string" ? body.reason : "";

  if (!isAgenticCronLabel(label)) {
    recordFailure(clientId);
    return NextResponse.json(
      { error: "not_in_allowlist", label },
      { status: 403 },
    );
  }
  if (!reason || reason.length < 5) {
    return NextResponse.json(
      { error: "reason_required_min_5_chars" },
      { status: 400 },
    );
  }

  const hmacSecret = readHmacSecret();
  const result = await startCron(label);
  if (hmacSecret) {
    await insertAuditRow(hmacSecret, {
      action: "cron.run",
      params: { label, reason },
      result: result.ok ? "success" : "error",
      errorMessage: result.stderr,
    });
  }
  if (!result.ok)
    return NextResponse.json(
      { error: "launchctl_failed", stderr: result.stderr },
      { status: 500 },
    );
  return NextResponse.json({ ok: true, label });
}
```

- [ ] **Step 2**: commit

---

### Task 18: API /api/cockpit/decisions

**Files:** Create `app/api/cockpit/decisions/route.ts`

- [ ] **Step 1: Write**

```ts
import { NextResponse } from "next/server";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
export const dynamic = "force-dynamic";

export async function GET() {
  const decisions: Array<{
    type: string;
    title: string;
    url?: string;
    age_minutes?: number;
  }> = [];
  try {
    const { stdout } = await execFileAsync(
      "gh",
      [
        "pr",
        "list",
        "--draft",
        "--json",
        "title,url,createdAt",
        "--limit",
        "20",
      ],
      { timeout: 5000, cwd: process.env.COCKPIT_REPO_ROOT || process.cwd() },
    );
    const list = JSON.parse(stdout) as Array<{
      title: string;
      url: string;
      createdAt: string;
    }>;
    for (const pr of list) {
      decisions.push({
        type: "pr_draft",
        title: pr.title,
        url: pr.url,
        age_minutes: Math.floor(
          (Date.now() - new Date(pr.createdAt).getTime()) / 60000,
        ),
      });
    }
  } catch {
    /* gh CLI unavailable or no PRs */
  }
  return NextResponse.json({ decisions, total: decisions.length });
}
```

- [ ] **Step 2**: commit

---

### Task 19: API /api/cockpit/intent/create

**Files:** Create `app/api/cockpit/intent/create/route.ts`

- [ ] **Step 1: Write**

```ts
import { NextRequest, NextResponse } from "next/server";
import { createIntent, insertAuditRow } from "@/lib/cockpit-pg";
import { readHmacSecret } from "@/lib/cockpit-audit";
import { isLockedOut, recordFailure } from "@/lib/cockpit-auth";

export const dynamic = "force-dynamic";

const ALLOWED = new Set([
  "intel.skip",
  "intel.rerun",
  "wr2.approve",
  "wr2.reject",
  "cron.kill",
  "library.approve-pr",
  "library.reject-pr",
]);

export async function POST(req: NextRequest) {
  const clientId = req.headers.get("x-forwarded-for") ?? "localhost";
  if (isLockedOut(clientId))
    return NextResponse.json({ error: "rate_limited" }, { status: 429 });

  const body = await req.json().catch(() => ({}));
  const intentType =
    typeof body.intent_type === "string" ? body.intent_type : "";
  const params =
    typeof body.params === "object" && body.params !== null ? body.params : {};
  const reason = typeof body.reason === "string" ? body.reason : "";

  if (!ALLOWED.has(intentType)) {
    recordFailure(clientId);
    return NextResponse.json({ error: "invalid_intent_type" }, { status: 400 });
  }
  if (!reason || reason.length < 5)
    return NextResponse.json(
      { error: "reason_required_min_5_chars" },
      { status: 400 },
    );

  const hmacSecret = readHmacSecret();
  try {
    const intentId = await createIntent(intentType, params, reason);
    if (hmacSecret) {
      await insertAuditRow(hmacSecret, {
        action: `intent.${intentType}`,
        params: { ...params, intent_id: intentId.toString() },
        result: "success",
      });
    }
    return NextResponse.json({ ok: true, intent_id: intentId.toString() });
  } catch (e: any) {
    if (hmacSecret)
      await insertAuditRow(hmacSecret, {
        action: `intent.${intentType}`,
        params,
        result: "error",
        errorMessage: e.message,
      });
    return NextResponse.json(
      { error: "intent_create_failed" },
      { status: 500 },
    );
  }
}
```

- [ ] **Step 2**: commit

---

### Task 20: GlobalPulse widget (LIVE)

**Files:** Create `components/cockpit/GlobalPulse.tsx`

- [ ] **Step 1: Write**

```tsx
"use client";
import { useEffect, useState } from "react";
import { WidgetFrame } from "./WidgetFrame";
import { StatusDot } from "./StatusDot";

interface Resp {
  statuses: any[];
  counts: {
    running: number;
    waiting: number;
    not_loaded: number;
    failed: number;
  };
}

export function GlobalPulse() {
  const [data, setData] = useState<Resp | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancel = false;
    async function fetchD() {
      try {
        const r = await fetch("/api/cockpit/cron/list");
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const j = await r.json();
        if (!cancel) {
          setData(j);
          setErr(null);
        }
      } catch (e: any) {
        if (!cancel) setErr(e.message);
      }
    }
    fetchD();
    const i = setInterval(fetchD, 10_000);
    return () => {
      cancel = true;
      clearInterval(i);
    };
  }, []);

  if (err)
    return (
      <WidgetFrame title="Global Pulse" status="red">
        error: {err}
      </WidgetFrame>
    );
  if (!data)
    return (
      <WidgetFrame title="Global Pulse" status="amber">
        loading...
      </WidgetFrame>
    );

  const dominant: "green" | "amber" | "red" =
    data.counts.failed > 0
      ? "red"
      : data.counts.not_loaded > 0
        ? "amber"
        : "green";
  return (
    <WidgetFrame title="Global Pulse" status={dominant}>
      <div style={{ fontSize: 24, marginBottom: 8 }}>
        {data.counts.running}/{data.statuses.length}
      </div>
      <div style={{ fontSize: 11, color: "var(--fg-dim)" }}>
        <div>
          <StatusDot status="green" /> running: {data.counts.running}
        </div>
        <div>
          <StatusDot status="amber" /> waiting: {data.counts.waiting}
        </div>
        <div style={{ color: "var(--fg-red)" }}>
          <StatusDot status="red" /> failed (24h): {data.counts.failed}
        </div>
      </div>
    </WidgetFrame>
  );
}
```

- [ ] **Step 2**: commit

---

### Task 21: DecisionsAttesa widget (LIVE)

**Files:** Create `components/cockpit/DecisionsAttesa.tsx`

- [ ] **Step 1: Write**

```tsx
"use client";
import { useEffect, useState } from "react";
import { WidgetFrame } from "./WidgetFrame";

interface Decision {
  type: string;
  title: string;
  url?: string;
  age_minutes?: number;
}
interface Resp {
  decisions: Decision[];
  total: number;
}

export function DecisionsAttesa() {
  const [data, setData] = useState<Resp | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancel = false;
    async function fetchD() {
      try {
        const r = await fetch("/api/cockpit/decisions");
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const j = await r.json();
        if (!cancel) {
          setData(j);
          setErr(null);
        }
      } catch (e: any) {
        if (!cancel) setErr(e.message);
      }
    }
    fetchD();
    const i = setInterval(fetchD, 30_000);
    return () => {
      cancel = true;
      clearInterval(i);
    };
  }, []);

  if (err)
    return (
      <WidgetFrame title="Decisions Attesa" status="red">
        error: {err}
      </WidgetFrame>
    );
  if (!data)
    return (
      <WidgetFrame title="Decisions Attesa" status="amber">
        loading...
      </WidgetFrame>
    );

  const status: "green" | "amber" | "red" =
    data.total === 0 ? "green" : data.total > 5 ? "red" : "amber";
  return (
    <WidgetFrame title="Decisions Attesa" status={status}>
      <div style={{ fontSize: 24, marginBottom: 8 }}>{data.total}</div>
      <div style={{ fontSize: 11, maxHeight: 140, overflow: "auto" }}>
        {data.decisions.length === 0 ? (
          <div style={{ color: "var(--fg-dim)" }}>nothing pending</div>
        ) : (
          data.decisions.map((d, i) => (
            <div key={i} style={{ marginBottom: 4 }}>
              <a
                href={d.url ?? "#"}
                target="_blank"
                rel="noreferrer"
                style={{ color: "var(--fg-active)", textDecoration: "none" }}
              >
                {d.title.slice(0, 50)}
              </a>
              {typeof d.age_minutes === "number" && (
                <span style={{ color: "var(--fg-dim)", marginLeft: 4 }}>
                  ({d.age_minutes}m)
                </span>
              )}
            </div>
          ))
        )}
      </div>
    </WidgetFrame>
  );
}
```

- [ ] **Step 2**: commit

---

### Task 22: PinGate component + page wrap

**Files:** Create `components/cockpit/PinGate.tsx` + Modify `app/cockpit/page.tsx`

- [ ] **Step 1: PinGate.tsx**

```tsx
"use client";
import { useState, useEffect } from "react";

export function PinGate({ children }: { children: React.ReactNode }) {
  const [authed, setAuthed] = useState(false);
  const [pin, setPin] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetch("/api/cockpit/cron/list").then((r) => {
      if (r.ok) setAuthed(true);
    });
  }, []);

  if (authed) return <>{children}</>;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const r = await fetch("/api/cockpit/auth", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ pin }),
      });
      if (r.status === 429) {
        setErr("rate-limited: try again in 5 minutes");
        return;
      }
      if (!r.ok) {
        setErr("invalid PIN");
        return;
      }
      setAuthed(true);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        background: "var(--bg-deep)",
      }}
    >
      <form
        onSubmit={submit}
        style={{
          background: "var(--bg-panel)",
          border: "1px solid var(--border)",
          padding: 32,
          minWidth: 320,
        }}
      >
        <div className="cockpit-widget-title">ZANTARA COCKPIT — PIN</div>
        <input
          type="password"
          value={pin}
          onChange={(e) => setPin(e.target.value)}
          autoFocus
          maxLength={20}
          style={{
            display: "block",
            width: "100%",
            background: "var(--bg-deep)",
            border: "1px solid var(--border-active)",
            color: "var(--fg-primary)",
            padding: 8,
            fontFamily: "inherit",
            fontSize: 14,
            marginTop: 16,
          }}
        />
        {err && (
          <div style={{ color: "var(--fg-red)", fontSize: 11, marginTop: 8 }}>
            {err}
          </div>
        )}
        <button
          type="submit"
          disabled={busy || !pin}
          className="cockpit-action-button"
          style={{ marginTop: 16, width: "100%" }}
        >
          {busy ? "verifying..." : "unlock"}
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 2**: Wrap `app/cockpit/page.tsx` content in `<PinGate>...</PinGate>`
- [ ] **Step 3**: build verify
- [ ] **Step 4**: commit `feat(cockpit): PinGate component + page integration`

---

### Task 23: setup-cockpit-pin.sh

**Files:** Create `apps/admin-dashboard-local/scripts/setup-cockpit-pin.sh`

- [ ] **Step 1: Write**

```bash
#!/bin/bash
# Interactive PIN init for Zantara Cockpit
set -euo pipefail
CONFIG_DIR="$HOME/.config/zantara-cockpit"
PIN_FILE="$CONFIG_DIR/pin.hash"
HMAC_FILE="$CONFIG_DIR/hmac.key"

mkdir -p "$CONFIG_DIR"; chmod 0700 "$CONFIG_DIR"

if [ -f "$PIN_FILE" ]; then
  read -r -p "PIN exists. Overwrite? (y/N) " ans
  [ "$ans" != "y" ] && exit 0
fi

read -rs -p "PIN (6-12 chars): " PIN; echo
read -rs -p "Confirm: " PIN2; echo
[ "$PIN" != "$PIN2" ] && { echo "ERROR: PINs don't match" >&2; exit 1; }
[ ${#PIN} -lt 6 ] && { echo "ERROR: min 6 chars" >&2; exit 1; }

HASH=$(cd "$(dirname "$0")/.." && node -e "console.log(require('bcryptjs').hashSync(process.argv[1], 12))" "$PIN")
echo "$HASH" > "$PIN_FILE"; chmod 0600 "$PIN_FILE"

if [ ! -f "$HMAC_FILE" ]; then
  head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n' > "$HMAC_FILE"
  chmod 0600 "$HMAC_FILE"
  echo "Generated HMAC key at $HMAC_FILE"
fi

echo "OK: PIN saved (mode 0600). Now: bash scripts/start-cockpit.sh"
```

- [ ] **Step 2**: `chmod +x` + commit

---

### Task 24: start-cockpit.sh

**Files:** Create `apps/admin-dashboard-local/scripts/start-cockpit.sh`

- [ ] **Step 1: Write**

```bash
#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
CONFIG_DIR="$HOME/.config/zantara-cockpit"
[ ! -f "$CONFIG_DIR/pin.hash" ] && { echo "ERROR: run setup-cockpit-pin.sh" >&2; exit 1; }
[ ! -f "$CONFIG_DIR/hmac.key" ] && { echo "ERROR: HMAC missing" >&2; exit 1; }

export LOCAL_ONLY=1
export COCKPIT_HMAC_KEY=$(cat "$CONFIG_DIR/hmac.key")
export COCKPIT_REPO_ROOT="${COCKPIT_REPO_ROOT:-/Users/nuzantara/Desktop/nuzantara}"

[ -f .env ] && { set -a; source .env; set +a; }
[ -z "${DATABASE_URL_LOCAL:-}" ] && [ -z "${FLY_TUNNEL_URL:-}" ] && echo "WARN: DB url unset" >&2

echo "Starting Zantara Cockpit http://localhost:3100/cockpit"
npx next dev -p 3100
```

- [ ] **Step 2**: `chmod +x` + commit

---

### Task 25: E2E smoke test

- [ ] **Step 1**: `bash scripts/setup-cockpit-pin.sh` (interactive, PIN test1234)
- [ ] **Step 2**: `bash scripts/start-cockpit.sh &` + sleep 8
- [ ] **Step 3**: Unauth → `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3100/api/cockpit/cron/list` → 401
- [ ] **Step 4**: Auth → `curl -s -c /tmp/jar.txt -H 'content-type: application/json' -d '{"pin":"test1234"}' http://localhost:3100/api/cockpit/auth` → `{"ok":true}`
- [ ] **Step 5**: With cookie → `curl -s -b /tmp/jar.txt http://localhost:3100/api/cockpit/cron/list | head -c 200` → JSON statuses
- [ ] **Step 6**: Allowlist reject → `curl -s -b /tmp/jar.txt -H 'content-type: application/json' -d '{"label":"com.apple.dock","reason":"test"}' http://localhost:3100/api/cockpit/cron/run` → `not_in_allowlist` 403
- [ ] **Step 7**: Reason validation → `curl -s -b /tmp/jar.txt -H 'content-type: application/json' -d '{"label":"com.balizero.regulatory-watcher","reason":""}' http://localhost:3100/api/cockpit/cron/run` → `reason_required` 400
- [ ] **Step 8**: Browser open `http://localhost:3100/cockpit` → PIN gate → 12 panel grid, 2 live
- [ ] **Step 9**: Audit log query: `psql -d nuzantara_rag -c "SELECT id, action, result FROM cockpit_audit_log ORDER BY id DESC LIMIT 5;"` → rows
- [ ] **Step 10**: `kill %1; rm /tmp/jar.txt`

---

### Task 26: Push + PR draft

- [ ] **Step 1**: `git log --oneline origin/main..HEAD` → ~24 commits
- [ ] **Step 2**: `git push` (branch already pushed in spec commit phase)
- [ ] **Step 3**: `gh pr create --draft --title "feat(cockpit): S1 Foundation" --body "..."`
- [ ] **Step 4**: Output PR URL

---

## Self-Review

**1. Spec coverage:**

- Migrations 180+181: Tasks 2, 3 ✓
- Bloomberg theme: Tasks 5, 6 ✓
- 12-widget grid: Task 8 ✓
- Live widgets: Tasks 20, 21 ✓
- Intent-table action: Tasks 13, 19 ✓
- PIN + rate-limit S1: Tasks 10, 14, 15 ✓
- HMAC audit: Tasks 11, 13 ✓
- 35 cron allowlist: Task 9 ✓
- Reason ≥5 chars: Tasks 17, 19 ✓
- LOCAL_ONLY=1: Task 24 ✓
- Origin localhost: Task 14 ✓
- launchctl print (not list): Task 12 ✓
- Setup + start scripts: Tasks 23, 24 ✓
- E2E smoke: Task 25 ✓

**2. Placeholder scan:** none found

**3. Type consistency:** CronStatus (T12, T20), AuditRow (T11, T13), AGENTIC_CRON_ALLOWLIST (T9, T17), WidgetFrame (T7, T20, T21) — all consistent

Plan complete.
