# PF3a — Prime Intelligence 3D Performance + UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut `/prime` LCP below 3s (desktop) / 5s (mobile), add Firefox fallback gate, deep-linkable URL state, interactive layer legend, and side-by-side zone compare drawer — without rewriting the 1,179-LOC `PrimeMap3D.tsx`.

**Architecture:** Wrap, don't rewrite. `PrimeMap3D` stays as-is except for three surgical changes (context provider wiring + ARIA attrs). All new behavior (browser gate, legend, compare drawer, URL state bridge) lives in fresh components in `apps/mouth/src/components/maps/prime/`. `PrimeMap3D` itself moves to `next/dynamic({ ssr: false })` inside `PrimeNexusLayout` so the Google Maps JS + `maps3d` loader leaves the initial bundle and a lightweight skeleton becomes the LCP element.

**Tech Stack:** Next.js 16 App Router, React 19, TypeScript, Tailwind, Vitest (jsdom) + React Testing Library, Playwright, Zod 3, URLSearchParams (native).

**Spec:** [`docs/superpowers/specs/2026-04-18-pf3a-prime-perf-ux-design.md`](../specs/2026-04-18-pf3a-prime-perf-ux-design.md)

---

## File Structure

New files (all under `apps/mouth/src/`):

```
components/maps/prime/
  PrimeGate.tsx                 Browser-support gate; renders children only on Chromium+WebGL2
  PrimeMapSkeleton.tsx          Pre-blurred placeholder shown while PrimeMap3D chunk loads
  PrimeLayerLegend.tsx          Floating legend with toggle/isolate/hover
  PrimeCompareDrawer.tsx        Right-side drawer with slot A / slot B zone cards + delta
  PrimeUrlStateBridge.tsx       Headless URL ↔ context sync
  hooks/
    useBrowserSupport.ts        Chromium/Firefox/WebGL2/mobile detection
    usePrimeUrlState.ts         Zod-validated URLSearchParams parser/serializer
    useDebouncedCallback.ts     Tiny debounce helper (used by bridge)
contexts/
  PrimeNexusContext.tsx         [MODIFIED] Add layers, compareA, compareB, zonePolygonsRef
app/
  prime/
    layout.tsx                  [NEW] Adds preconnect to maps.googleapis.com (scoped)
    page.tsx                    [MODIFIED] Wrap in <PrimeGate>
components/maps/
  PrimeMap3D.tsx                [MODIFIED] Consume context layers/compare; ARIA attrs; expose refs
  prime/PrimeNexusLayout.tsx    [MODIFIED] next/dynamic(PrimeMap3D), mount legend/drawer/bridge
public/prime/
  map-skeleton.webp             Pre-blurred Bali map placeholder (~30KB)
```

New tests:

```
src/components/maps/prime/__tests__/
  PrimeGate.test.tsx
  PrimeLayerLegend.test.tsx
  PrimeCompareDrawer.test.tsx
  PrimeUrlStateBridge.test.tsx
  hooks/
    useBrowserSupport.test.ts
    usePrimeUrlState.test.ts
e2e/
  prime.spec.ts
  prime-compare.spec.ts
  prime-firefox.spec.ts
```

Scripts:

```
apps/mouth/scripts/
  lighthouse-prime.mjs          Runs Lighthouse headless, records artifact
```

Artifacts (committed):

```
docs/superpowers/specs/artifacts/
  2026-04-18-prime-baseline.json
  2026-04-18-prime-after.json
  2026-04-18-prime-before-desktop.png
  2026-04-18-prime-before-mobile.png
  2026-04-18-prime-after-desktop.png
  2026-04-18-prime-after-mobile.png
  2026-04-18-prime-firefox.png
```

---

## Task 0: Worktree + branch

**Files:** n/a (git only)

- [ ] **Step 1: Create worktree on new branch**

```bash
cd ~/Desktop/nuzantara
git worktree add .worktrees/prime-perf-ux -b pro/frontend-prime-perf-ux main
cd .worktrees/prime-perf-ux
```

- [ ] **Step 2: Verify clean tree**

Run: `git status`
Expected: `On branch pro/frontend-prime-perf-ux` · `nothing to commit, working tree clean`.

- [ ] **Step 3: Install deps (fresh worktree)**

```bash
cd apps/mouth && npm install
```

Expected: no errors, `node_modules` created. (If the repo uses a lockfile at root, run `npm install` from repo root instead.)

- [ ] **Step 4: Confirm dev server boots**

```bash
cd apps/mouth && npm run dev
```

Visit `http://localhost:3000/prime` in Chrome. Expected: existing Prime UI renders. Then stop the server (Ctrl+C).

- [ ] **Step 5: Commit (empty, to mark branch start)**

```bash
git commit --allow-empty -m "chore(prime): start PF3a worktree"
```

---

## Task 1: Baseline Lighthouse + screenshots

**Files:**

- Create: `apps/mouth/scripts/lighthouse-prime.mjs`
- Create: `docs/superpowers/specs/artifacts/2026-04-18-prime-baseline.json`
- Create: `docs/superpowers/specs/artifacts/2026-04-18-prime-before-desktop.png`
- Create: `docs/superpowers/specs/artifacts/2026-04-18-prime-before-mobile.png`

- [ ] **Step 1: Write the Lighthouse runner script**

```javascript
// apps/mouth/scripts/lighthouse-prime.mjs
import lighthouse from "lighthouse";
import * as chromeLauncher from "chrome-launcher";
import fs from "node:fs";
import path from "node:path";

const URL = process.env.PRIME_URL || "http://localhost:3000/prime";
const LABEL = process.env.LABEL || "baseline";
const OUT_DIR = path.resolve(
  process.cwd(),
  "../../docs/superpowers/specs/artifacts",
);
fs.mkdirSync(OUT_DIR, { recursive: true });

async function run(formFactor) {
  const chrome = await chromeLauncher.launch({
    chromeFlags: ["--headless=new", "--no-sandbox"],
  });
  const options = {
    logLevel: "error",
    output: "json",
    onlyCategories: ["performance"],
    port: chrome.port,
    formFactor,
    screenEmulation:
      formFactor === "mobile"
        ? {
            mobile: true,
            width: 412,
            height: 915,
            deviceScaleFactor: 2.625,
            disabled: false,
          }
        : {
            mobile: false,
            width: 1440,
            height: 900,
            deviceScaleFactor: 1,
            disabled: false,
          },
  };
  const runnerResult = await lighthouse(URL, options);
  await chrome.kill();
  return runnerResult.lhr;
}

const desktop = await run("desktop");
const mobile = await run("mobile");
const out = {
  url: URL,
  label: LABEL,
  capturedAt: new Date().toISOString(),
  desktop: {
    score: desktop.categories.performance.score,
    lcp: desktop.audits["largest-contentful-paint"].numericValue,
    cls: desktop.audits["cumulative-layout-shift"].numericValue,
    tbt: desktop.audits["total-blocking-time"].numericValue,
    fcp: desktop.audits["first-contentful-paint"].numericValue,
    tti: desktop.audits["interactive"].numericValue,
  },
  mobile: {
    score: mobile.categories.performance.score,
    lcp: mobile.audits["largest-contentful-paint"].numericValue,
    cls: mobile.audits["cumulative-layout-shift"].numericValue,
    tbt: mobile.audits["total-blocking-time"].numericValue,
    fcp: mobile.audits["first-contentful-paint"].numericValue,
    tti: mobile.audits["interactive"].numericValue,
  },
};
const file = path.join(OUT_DIR, `2026-04-18-prime-${LABEL}.json`);
fs.writeFileSync(file, JSON.stringify(out, null, 2));
console.log(`Wrote ${file}`);
console.log(`Desktop LCP: ${out.desktop.lcp.toFixed(0)}ms`);
console.log(`Mobile  LCP: ${out.mobile.lcp.toFixed(0)}ms`);
```

- [ ] **Step 2: Install Lighthouse deps (dev-only)**

```bash
cd apps/mouth && npm install --save-dev lighthouse chrome-launcher
```

Expected: both packages added to `devDependencies` in `apps/mouth/package.json`. No runtime-dep bloat.

- [ ] **Step 3: Start prod-like server**

```bash
cd apps/mouth && npm run build && npm start &
sleep 5
```

- [ ] **Step 4: Capture baseline**

```bash
cd apps/mouth && LABEL=baseline node scripts/lighthouse-prime.mjs
```

Expected: file `docs/superpowers/specs/artifacts/2026-04-18-prime-baseline.json` written, console prints desktop + mobile LCP. Record the numbers in the commit message.

- [ ] **Step 5: Capture before screenshots (manual, Chrome DevTools)**

Open Chrome, go to `http://localhost:3000/prime`, take screenshots at 1440×900 (desktop) and 390×844 (iPhone 14 Pro in DevTools mobile emulation). Save as:

- `docs/superpowers/specs/artifacts/2026-04-18-prime-before-desktop.png`
- `docs/superpowers/specs/artifacts/2026-04-18-prime-before-mobile.png`

Kill the prod server: `kill %1` (or Ctrl+C in its terminal).

- [ ] **Step 6: Commit**

```bash
git add apps/mouth/scripts/lighthouse-prime.mjs apps/mouth/package.json apps/mouth/package-lock.json docs/superpowers/specs/artifacts/
git commit -m "chore(prime): baseline Lighthouse + before screenshots"
```

---

## Task 2: `useBrowserSupport` hook

**Files:**

- Create: `apps/mouth/src/components/maps/prime/hooks/useBrowserSupport.ts`
- Create: `apps/mouth/src/components/maps/prime/hooks/__tests__/useBrowserSupport.test.ts`

- [ ] **Step 1: Write the failing tests**

```ts
// apps/mouth/src/components/maps/prime/hooks/__tests__/useBrowserSupport.test.ts
import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useBrowserSupport } from "../useBrowserSupport";

function setUA(ua: string) {
  Object.defineProperty(window.navigator, "userAgent", {
    value: ua,
    configurable: true,
  });
}

function stubWebGL(ok: boolean) {
  const spy = vi
    .spyOn(HTMLCanvasElement.prototype, "getContext")
    .mockImplementation((type: string) =>
      type === "webgl2" ? (ok ? ({} as WebGL2RenderingContext) : null) : null,
    );
  return spy;
}

describe("useBrowserSupport", () => {
  beforeEach(() => {
    // Reset userAgentData
    Object.defineProperty(window.navigator, "userAgentData", {
      value: undefined,
      configurable: true,
    });
  });
  afterEach(() => vi.restoreAllMocks());

  it("flags Chrome + WebGL2 as supported", async () => {
    setUA(
      "Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
    );
    stubWebGL(true);
    const { result } = renderHook(() => useBrowserSupport());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.supported).toBe(true);
    expect(result.current.chromium).toBe(true);
    expect(result.current.webgl2).toBe(true);
  });

  it("flags Firefox as unsupported", async () => {
    setUA("Mozilla/5.0 (Macintosh) Gecko/20100101 Firefox/125.0");
    stubWebGL(true);
    const { result } = renderHook(() => useBrowserSupport());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.supported).toBe(false);
    expect(result.current.chromium).toBe(false);
  });

  it("flags missing WebGL2 as unsupported even on Chrome", async () => {
    setUA("Chrome/126.0 Safari/537.36");
    stubWebGL(false);
    const { result } = renderHook(() => useBrowserSupport());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.supported).toBe(false);
    expect(result.current.webgl2).toBe(false);
  });

  it("returns loading:true on first render", () => {
    setUA("Chrome/126.0");
    stubWebGL(true);
    const { result } = renderHook(() => useBrowserSupport());
    expect(result.current.loading).toBe(true);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/mouth && npx vitest run src/components/maps/prime/hooks/__tests__/useBrowserSupport.test.ts`
Expected: FAIL — "Cannot find module '../useBrowserSupport'".

- [ ] **Step 3: Implement the hook**

```ts
// apps/mouth/src/components/maps/prime/hooks/useBrowserSupport.ts
"use client";
import { useEffect, useState } from "react";

export interface BrowserSupport {
  supported: boolean;
  chromium: boolean;
  webgl2: boolean;
  isMobile: boolean;
  loading: boolean;
}

function detectChromium(): boolean {
  const nav = navigator as Navigator & {
    userAgentData?: { brands: Array<{ brand: string }> };
  };
  if (nav.userAgentData?.brands?.length) {
    return nav.userAgentData.brands.some(
      (b) => b.brand === "Chromium" || b.brand === "Google Chrome",
    );
  }
  const ua = navigator.userAgent;
  if (/Firefox\/|Gecko\//.test(ua) && !/Chrome\/|Edg\//.test(ua)) return false;
  return /Chrome\/|Edg\//.test(ua);
}

function detectWebGL2(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return canvas.getContext("webgl2") != null;
  } catch {
    return false;
  }
}

function detectMobile(): boolean {
  return (
    typeof window !== "undefined" &&
    window.matchMedia("(pointer:coarse) and (max-width: 768px)").matches
  );
}

export function useBrowserSupport(): BrowserSupport {
  const [state, setState] = useState<BrowserSupport>({
    supported: false,
    chromium: false,
    webgl2: false,
    isMobile: false,
    loading: true,
  });

  useEffect(() => {
    const chromium = detectChromium();
    const webgl2 = detectWebGL2();
    const isMobile = detectMobile();
    setState({
      supported: chromium && webgl2,
      chromium,
      webgl2,
      isMobile,
      loading: false,
    });
  }, []);

  return state;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/mouth && npx vitest run src/components/maps/prime/hooks/__tests__/useBrowserSupport.test.ts`
Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/mouth/src/components/maps/prime/hooks/
git commit -m "feat(prime): useBrowserSupport hook + tests"
```

---

## Task 3: `PrimeGate` component

**Files:**

- Create: `apps/mouth/src/components/maps/prime/PrimeGate.tsx`
- Create: `apps/mouth/src/components/maps/prime/__tests__/PrimeGate.test.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
// apps/mouth/src/components/maps/prime/__tests__/PrimeGate.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { PrimeGate } from "../PrimeGate";

vi.mock("../hooks/useBrowserSupport", () => ({
  useBrowserSupport: vi.fn(),
}));
import { useBrowserSupport } from "../hooks/useBrowserSupport";

describe("PrimeGate", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders a skeleton while detection is loading", () => {
    (useBrowserSupport as ReturnType<typeof vi.fn>).mockReturnValue({
      loading: true,
      supported: false,
      chromium: false,
      webgl2: false,
      isMobile: false,
    });
    render(
      <PrimeGate>
        <div data-testid="map">MAP</div>
      </PrimeGate>,
    );
    expect(screen.queryByTestId("map")).toBeNull();
    expect(screen.getByTestId("prime-gate-loading")).toBeInTheDocument();
  });

  it("renders children when supported", () => {
    (useBrowserSupport as ReturnType<typeof vi.fn>).mockReturnValue({
      loading: false,
      supported: true,
      chromium: true,
      webgl2: true,
      isMobile: false,
    });
    render(
      <PrimeGate>
        <div data-testid="map">MAP</div>
      </PrimeGate>,
    );
    expect(screen.getByTestId("map")).toBeInTheDocument();
  });

  it("shows a fallback message on unsupported browser", () => {
    (useBrowserSupport as ReturnType<typeof vi.fn>).mockReturnValue({
      loading: false,
      supported: false,
      chromium: false,
      webgl2: true,
      isMobile: false,
    });
    render(
      <PrimeGate>
        <div data-testid="map">MAP</div>
      </PrimeGate>,
    );
    expect(screen.queryByTestId("map")).toBeNull();
    expect(
      screen.getByRole("heading", { name: /prime requires/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /continue anyway/i }),
    ).toBeInTheDocument();
  });

  it("Continue anyway reveals children", async () => {
    (useBrowserSupport as ReturnType<typeof vi.fn>).mockReturnValue({
      loading: false,
      supported: false,
      chromium: false,
      webgl2: true,
      isMobile: false,
    });
    render(
      <PrimeGate>
        <div data-testid="map">MAP</div>
      </PrimeGate>,
    );
    await userEvent.click(
      screen.getByRole("button", { name: /continue anyway/i }),
    );
    expect(screen.getByTestId("map")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/mouth && npx vitest run src/components/maps/prime/__tests__/PrimeGate.test.tsx`
Expected: FAIL — module `../PrimeGate` not found.

- [ ] **Step 3: Implement PrimeGate**

```tsx
// apps/mouth/src/components/maps/prime/PrimeGate.tsx
"use client";
import { useState, type ReactNode } from "react";
import { useBrowserSupport } from "./hooks/useBrowserSupport";

export function PrimeGate({ children }: { children: ReactNode }) {
  const { supported, chromium, webgl2, loading } = useBrowserSupport();
  const [override, setOverride] = useState(false);

  if (loading) {
    return (
      <div
        data-testid="prime-gate-loading"
        className="h-screen w-screen bg-black flex items-center justify-center"
      >
        <div className="h-10 w-10 rounded-full border-2 border-[#d4845a] border-t-transparent animate-spin" />
      </div>
    );
  }

  if (supported || override) return <>{children}</>;

  const reason = !chromium
    ? "Prime requires a Chromium-based browser (Chrome, Edge, Brave, Arc)."
    : !webgl2
      ? "Prime requires WebGL2 support."
      : "Prime requires a supported browser configuration.";

  return (
    <div
      role="alert"
      className="h-screen w-screen bg-black text-white flex items-center justify-center p-6"
    >
      <div className="max-w-lg text-center space-y-6">
        <h1 className="text-2xl font-semibold">Prime requires Chrome/Edge</h1>
        <p className="text-white/70">{reason}</p>
        <p className="text-sm text-white/50">
          The 3D zoning map uses Google&apos;s <code>maps3d</code> API which is
          only reliable on Chromium browsers with WebGL2.
        </p>
        <div className="flex flex-col gap-3 items-center">
          <a
            href="https://www.google.com/chrome/"
            className="px-4 py-2 rounded-md bg-[#d4845a] text-black font-medium"
          >
            Get Chrome
          </a>
          <button
            type="button"
            onClick={() => setOverride(true)}
            className="text-xs text-white/40 underline hover:text-white/70"
          >
            Continue anyway
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/mouth && npx vitest run src/components/maps/prime/__tests__/PrimeGate.test.tsx`
Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/mouth/src/components/maps/prime/PrimeGate.tsx apps/mouth/src/components/maps/prime/__tests__/PrimeGate.test.tsx
git commit -m "feat(prime): PrimeGate browser-support gate + tests"
```

---

## Task 4: `PrimeMapSkeleton` + Prime layout preconnect

**Files:**

- Create: `apps/mouth/src/components/maps/prime/PrimeMapSkeleton.tsx`
- Create: `apps/mouth/src/app/prime/layout.tsx`
- Add asset: `apps/mouth/public/prime/map-skeleton.webp` (pre-blurred Bali map, ~30KB)

- [ ] **Step 1: Export placeholder image**

Create `apps/mouth/public/prime/map-skeleton.webp`. For the first pass, capture a screenshot of the current Prime map at default Bali view, export as WebP at quality 60, apply a 20px gaussian blur (any tool: macOS Preview → Tools → Adjust Filters → Gaussian Blur, or `ffmpeg -i input.png -vf "boxblur=20" -q:v 60 map-skeleton.webp`). Target size <50KB. Commit with the task.

- [ ] **Step 2: Write the skeleton component**

```tsx
// apps/mouth/src/components/maps/prime/PrimeMapSkeleton.tsx
import Image from "next/image";

export function PrimeMapSkeleton() {
  return (
    <div className="absolute inset-0 bg-black">
      <Image
        src="/prime/map-skeleton.webp"
        alt=""
        fill
        priority
        sizes="100vw"
        className="object-cover opacity-60"
      />
      <div className="absolute inset-0 bg-gradient-to-b from-black/20 to-black/40" />
      <div className="absolute inset-x-0 bottom-12 flex justify-center">
        <div className="px-4 py-2 rounded-full bg-black/60 text-white/80 text-sm backdrop-blur-md">
          Loading 3D map…
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create scoped layout with preconnect**

```tsx
// apps/mouth/src/app/prime/layout.tsx
import type { ReactNode } from "react";

export default function PrimeLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <link
        rel="preconnect"
        href="https://maps.googleapis.com"
        crossOrigin="anonymous"
      />
      <link rel="dns-prefetch" href="https://maps.gstatic.com" />
      {children}
    </>
  );
}
```

- [ ] **Step 4: Verify typecheck**

Run: `cd apps/mouth && npm run typecheck`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add apps/mouth/src/components/maps/prime/PrimeMapSkeleton.tsx apps/mouth/src/app/prime/layout.tsx apps/mouth/public/prime/
git commit -m "feat(prime): skeleton placeholder + preconnect layout"
```

---

## Task 5: Dynamic split of `PrimeMap3D` + gate wiring

**Files:**

- Modify: `apps/mouth/src/app/prime/page.tsx`
- Modify: `apps/mouth/src/components/maps/prime/PrimeNexusLayout.tsx`

- [ ] **Step 1: Wrap page in PrimeGate**

Replace `apps/mouth/src/app/prime/page.tsx` with:

```tsx
import PrimeNexusLayout from "@/components/maps/prime/PrimeNexusLayout";
import { PrimeGate } from "@/components/maps/prime/PrimeGate";

export const metadata = {
  title: "Prime Nexus — Bali Geospatial Decision Hub",
  description:
    "Real-time zoning intelligence, investment analysis, and CRM overlay for Bali property and business decisions.",
  robots: "noindex",
};

export default function PrimePage() {
  return (
    <PrimeGate>
      <PrimeNexusLayout />
    </PrimeGate>
  );
}
```

- [ ] **Step 2: Convert PrimeMap3D to dynamic import in PrimeNexusLayout**

In `apps/mouth/src/components/maps/prime/PrimeNexusLayout.tsx`, replace line 5 (`import PrimeMap3D from '@/components/maps/PrimeMap3D';`) with:

```tsx
import { PrimeMapSkeleton } from "./PrimeMapSkeleton";

const PrimeMap3D = dynamic(() => import("@/components/maps/PrimeMap3D"), {
  ssr: false,
  loading: () => <PrimeMapSkeleton />,
});
```

Leave every other import and the rest of the component unchanged.

- [ ] **Step 3: Typecheck + lint**

```bash
cd apps/mouth && npm run typecheck && npm run lint
```

Expected: no errors.

- [ ] **Step 4: Manual verify in browser**

```bash
cd apps/mouth && npm run build && npm start &
sleep 5
```

Open Chrome DevTools → Network → throttle to Fast 3G → reload `http://localhost:3000/prime`. Expected: skeleton is visible for ≥1s before the map renders. Stop server.

- [ ] **Step 5: Capture post-split Lighthouse**

```bash
cd apps/mouth && npm run build && npm start &
sleep 5
LABEL=after-split node apps/mouth/scripts/lighthouse-prime.mjs
kill %1
```

Compare `2026-04-18-prime-after-split.json` vs baseline. If desktop LCP did not drop or got worse, STOP. Investigate before continuing (common causes: dynamic import eager-preloaded by parent, Next caching issue, skeleton too heavy). Do not proceed to Task 6 until LCP improves.

- [ ] **Step 6: Commit**

```bash
git add apps/mouth/src/app/prime/page.tsx apps/mouth/src/components/maps/prime/PrimeNexusLayout.tsx docs/superpowers/specs/artifacts/2026-04-18-prime-after-split.json
git commit -m "perf(prime): dynamic split of PrimeMap3D + gate wiring

Desktop LCP <baseline>→<new>ms, Mobile <baseline>→<new>ms"
```

(Fill the numbers from the Lighthouse artifact before committing.)

---

## Task 6: Extend `PrimeNexusContext` with legend + compare state

**Files:**

- Modify: `apps/mouth/src/contexts/PrimeNexusContext.tsx`

- [ ] **Step 1: Read current context shape**

Read `apps/mouth/src/contexts/PrimeNexusContext.tsx` in full so the new additions align with the existing provider pattern (it already uses `useState` + `useCallback`).

- [ ] **Step 2: Add imports and types**

At the top of the file, ensure these imports exist (add if missing):

```tsx
import type { MutableRefObject } from "react";
```

Just before `// ─── Context Shape ──────────` add:

```ts
// PF3a — legend + compare additions
export interface MapLayersState {
  zoneColors: boolean;
  extrusion: boolean;
  kkop: boolean;
  lp2b: boolean;
  tsunami: boolean;
  floodRisk: boolean;
  templeBuffer: boolean;
}

export const DEFAULT_MAP_LAYERS: MapLayersState = {
  zoneColors: true,
  extrusion: false,
  kkop: false,
  lp2b: false,
  tsunami: false,
  floodRisk: false,
  templeBuffer: false,
};

export interface ZoneSelection {
  id: string;
  name: string;
  zoneCode: string | null;
  info: unknown;
}
```

- [ ] **Step 3: Extend `PrimeNexusContextType`**

In the existing `PrimeNexusContextType` interface, add these fields after the existing entries:

```ts
  // PF3a — legend
  layers: MapLayersState;
  setLayers: (layers: MapLayersState) => void;
  toggleLayer: (key: keyof MapLayersState) => void;
  isolateLayer: (key: keyof MapLayersState) => void;
  hoveredLayer: keyof MapLayersState | null;
  setHoveredLayer: (key: keyof MapLayersState | null) => void;
  // PF3a — compare
  compareA: ZoneSelection | null;
  compareB: ZoneSelection | null;
  addToCompare: (zone: ZoneSelection) => void;
  clearCompareSlot: (slot: "A" | "B") => void;
  clearCompareAll: () => void;
  // PF3a — shared refs (read-only from consumers)
  zonePolygonsRef: MutableRefObject<unknown[]> | null;
```

- [ ] **Step 4: Add state + handlers in the provider**

Inside `PrimeNexusProvider` (right after the existing `useState` calls), add:

```tsx
const [layers, setLayersState] = useState<MapLayersState>(DEFAULT_MAP_LAYERS);
const [hoveredLayer, setHoveredLayer] = useState<keyof MapLayersState | null>(
  null,
);
const [compareA, setCompareA] = useState<ZoneSelection | null>(null);
const [compareB, setCompareB] = useState<ZoneSelection | null>(null);

const setLayers = useCallback(
  (next: MapLayersState) => setLayersState(next),
  [],
);

const toggleLayer = useCallback((key: keyof MapLayersState) => {
  setLayersState((prev) => ({ ...prev, [key]: !prev[key] }));
}, []);

const isolateLayer = useCallback((key: keyof MapLayersState) => {
  setLayersState(() => {
    const next = { ...DEFAULT_MAP_LAYERS };
    (Object.keys(next) as Array<keyof MapLayersState>).forEach((k) => {
      next[k] = k === key;
    });
    return next;
  });
}, []);

const addToCompare = useCallback(
  (zone: ZoneSelection) => {
    setCompareA((prevA) => {
      if (!prevA) return zone;
      setCompareB((prevB) => (prevB ? zone : (prevB ?? zone)));
      return prevA;
    });
    // If A already existed and B was empty, the setCompareB call above filled B.
    // If both existed, we replace A and keep B.
    setCompareA((prevA) => {
      if (prevA && compareB) return zone;
      return prevA ?? zone;
    });
  },
  [compareB],
);

const clearCompareSlot = useCallback((slot: "A" | "B") => {
  if (slot === "A") setCompareA(null);
  else setCompareB(null);
}, []);

const clearCompareAll = useCallback(() => {
  setCompareA(null);
  setCompareB(null);
}, []);
```

- [ ] **Step 5: Include the new fields in the context `value`**

In the `value` object returned by the provider, add:

```ts
      layers,
      setLayers,
      toggleLayer,
      isolateLayer,
      hoveredLayer,
      setHoveredLayer,
      compareA,
      compareB,
      addToCompare,
      clearCompareSlot,
      clearCompareAll,
      zonePolygonsRef: null, // Task 9 will wire a real ref from PrimeMap3D
```

- [ ] **Step 6: Write a context sanity test**

Create `apps/mouth/src/contexts/__tests__/PrimeNexusContext.test.tsx`:

```tsx
import { render, screen, act } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import {
  PrimeNexusProvider,
  usePrimeNexus,
  DEFAULT_MAP_LAYERS,
} from "../PrimeNexusContext";

function Probe() {
  const ctx = usePrimeNexus();
  return (
    <div>
      <span data-testid="zoneColors">{String(ctx.layers.zoneColors)}</span>
      <span data-testid="kkop">{String(ctx.layers.kkop)}</span>
      <button onClick={() => ctx.toggleLayer("kkop")}>toggle-kkop</button>
      <button onClick={() => ctx.isolateLayer("kkop")}>isolate-kkop</button>
    </div>
  );
}

describe("PrimeNexusContext layers", () => {
  it("starts with DEFAULT_MAP_LAYERS and toggles kkop on", () => {
    render(
      <PrimeNexusProvider>
        <Probe />
      </PrimeNexusProvider>,
    );
    expect(screen.getByTestId("kkop")).toHaveTextContent("false");
    expect(DEFAULT_MAP_LAYERS.zoneColors).toBe(true);
    act(() => {
      screen.getByText("toggle-kkop").click();
    });
    expect(screen.getByTestId("kkop")).toHaveTextContent("true");
  });

  it("isolate-kkop turns off every other layer", () => {
    render(
      <PrimeNexusProvider>
        <Probe />
      </PrimeNexusProvider>,
    );
    act(() => {
      screen.getByText("isolate-kkop").click();
    });
    expect(screen.getByTestId("kkop")).toHaveTextContent("true");
    expect(screen.getByTestId("zoneColors")).toHaveTextContent("false");
  });
});
```

- [ ] **Step 7: Run tests + typecheck**

```bash
cd apps/mouth && npx vitest run src/contexts/__tests__/PrimeNexusContext.test.tsx && npm run typecheck
```

Expected: both green.

- [ ] **Step 8: Commit**

```bash
git add apps/mouth/src/contexts/PrimeNexusContext.tsx apps/mouth/src/contexts/__tests__/PrimeNexusContext.test.tsx
git commit -m "feat(prime): context state for layers + compare"
```

---

## Task 7: `useDebouncedCallback` + `usePrimeUrlState` hooks

**Files:**

- Create: `apps/mouth/src/components/maps/prime/hooks/useDebouncedCallback.ts`
- Create: `apps/mouth/src/components/maps/prime/hooks/usePrimeUrlState.ts`
- Create: `apps/mouth/src/components/maps/prime/hooks/__tests__/usePrimeUrlState.test.ts`

- [ ] **Step 1: Write the debounce helper**

```ts
// apps/mouth/src/components/maps/prime/hooks/useDebouncedCallback.ts
"use client";
import { useEffect, useRef, useCallback } from "react";

export function useDebouncedCallback<T extends (...args: never[]) => void>(
  fn: T,
  delayMs: number,
): T {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(
    () => () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    },
    [],
  );

  return useCallback(
    ((...args: Parameters<T>) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => fnRef.current(...args), delayMs);
    }) as T,
    [delayMs],
  );
}
```

- [ ] **Step 2: Write the failing URL-state test**

```ts
// apps/mouth/src/components/maps/prime/hooks/__tests__/usePrimeUrlState.test.ts
import { describe, it, expect } from "vitest";
import {
  parsePrimeUrl,
  serializePrimeUrl,
  type PrimeUrlState,
} from "../usePrimeUrlState";

describe("parsePrimeUrl", () => {
  it("parses a full-valid querystring", () => {
    const out = parsePrimeUrl(
      new URLSearchParams(
        "lat=-8.65&lng=115.21&zoom=15&layers=zoneColors,kkop&compareA=Z1&compareB=Z2",
      ),
    );
    expect(out).toEqual({
      lat: -8.65,
      lng: 115.21,
      zoom: 15,
      layers: ["zoneColors", "kkop"],
      compareA: "Z1",
      compareB: "Z2",
    });
  });

  it("drops out-of-bound lat silently", () => {
    const out = parsePrimeUrl(new URLSearchParams("lat=40&lng=115.21&zoom=10"));
    expect(out.lat).toBeUndefined();
    expect(out.lng).toBe(115.21);
  });

  it("drops unknown layer names silently", () => {
    const out = parsePrimeUrl(
      new URLSearchParams("layers=zoneColors,bogus,kkop"),
    );
    expect(out.layers).toEqual(["zoneColors", "kkop"]);
  });

  it("returns empty object for empty params", () => {
    expect(parsePrimeUrl(new URLSearchParams(""))).toEqual({});
  });
});

describe("serializePrimeUrl", () => {
  it("omits undefined fields", () => {
    const s = serializePrimeUrl({ lat: -8.65, lng: 115.21 });
    expect(s).toBe("lat=-8.65&lng=115.21");
  });

  it("joins layers as csv", () => {
    const s = serializePrimeUrl({ layers: ["zoneColors", "kkop"] });
    expect(s).toBe("layers=zoneColors%2Ckkop");
  });

  it("round-trips a full state", () => {
    const state: PrimeUrlState = {
      lat: -8.65,
      lng: 115.21,
      zoom: 15,
      layers: ["zoneColors", "kkop"],
      compareA: "Z1",
      compareB: "Z2",
    };
    const s = serializePrimeUrl(state);
    expect(parsePrimeUrl(new URLSearchParams(s))).toEqual(state);
  });
});
```

- [ ] **Step 3: Run to verify failure**

Run: `cd apps/mouth && npx vitest run src/components/maps/prime/hooks/__tests__/usePrimeUrlState.test.ts`
Expected: FAIL, module not found.

- [ ] **Step 4: Implement the hook + pure helpers**

```ts
// apps/mouth/src/components/maps/prime/hooks/usePrimeUrlState.ts
"use client";
import { z } from "zod";
import { useEffect, useRef } from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useDebouncedCallback } from "./useDebouncedCallback";

const LAYER_KEYS = [
  "zoneColors",
  "extrusion",
  "kkop",
  "lp2b",
  "tsunami",
  "floodRisk",
  "templeBuffer",
] as const;
type LayerKey = (typeof LAYER_KEYS)[number];

const PrimeUrlSchema = z.object({
  lat: z.coerce.number().min(-9).max(-8).optional(),
  lng: z.coerce.number().min(114).max(116).optional(),
  zoom: z.coerce.number().min(6).max(22).optional(),
  layers: z.string().optional(),
  compareA: z.string().optional(),
  compareB: z.string().optional(),
});

export interface PrimeUrlState {
  lat?: number;
  lng?: number;
  zoom?: number;
  layers?: LayerKey[];
  compareA?: string;
  compareB?: string;
}

export function parsePrimeUrl(params: URLSearchParams): PrimeUrlState {
  const raw = Object.fromEntries(params.entries());
  const parsed = PrimeUrlSchema.safeParse(raw);
  if (!parsed.success) return {};
  const data = parsed.data;
  const out: PrimeUrlState = {};
  if (data.lat !== undefined) out.lat = data.lat;
  if (data.lng !== undefined) out.lng = data.lng;
  if (data.zoom !== undefined) out.zoom = data.zoom;
  if (data.layers) {
    const filtered = data.layers
      .split(",")
      .map((s) => s.trim())
      .filter((s): s is LayerKey =>
        (LAYER_KEYS as readonly string[]).includes(s),
      );
    if (filtered.length) out.layers = filtered;
  }
  if (data.compareA) out.compareA = data.compareA;
  if (data.compareB) out.compareB = data.compareB;
  return out;
}

export function serializePrimeUrl(state: PrimeUrlState): string {
  const params = new URLSearchParams();
  if (state.lat !== undefined) params.set("lat", String(state.lat));
  if (state.lng !== undefined) params.set("lng", String(state.lng));
  if (state.zoom !== undefined) params.set("zoom", String(state.zoom));
  if (state.layers?.length) params.set("layers", state.layers.join(","));
  if (state.compareA) params.set("compareA", state.compareA);
  if (state.compareB) params.set("compareB", state.compareB);
  return params.toString();
}

export function useWritePrimeUrl(state: PrimeUrlState, delayMs = 400) {
  const router = useRouter();
  const pathname = usePathname();
  const prev = useRef<string>("");

  const write = useDebouncedCallback((s: PrimeUrlState) => {
    const qs = serializePrimeUrl(s);
    if (qs === prev.current) return;
    prev.current = qs;
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }, delayMs);

  useEffect(() => {
    write(state);
  }, [state, write]);
}

export function useReadPrimeUrl(): PrimeUrlState {
  const params = useSearchParams();
  return parsePrimeUrl(new URLSearchParams(params?.toString() ?? ""));
}
```

- [ ] **Step 5: Run URL-state tests**

```bash
cd apps/mouth && npx vitest run src/components/maps/prime/hooks/__tests__/usePrimeUrlState.test.ts
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/mouth/src/components/maps/prime/hooks/
git commit -m "feat(prime): usePrimeUrlState + debounced writer"
```

---

## Task 8: `PrimeUrlStateBridge` (headless)

**Files:**

- Create: `apps/mouth/src/components/maps/prime/PrimeUrlStateBridge.tsx`
- Create: `apps/mouth/src/components/maps/prime/__tests__/PrimeUrlStateBridge.test.tsx`
- Modify: `apps/mouth/src/components/maps/prime/PrimeNexusLayout.tsx`

- [ ] **Step 1: Write the failing bridge test**

```tsx
// apps/mouth/src/components/maps/prime/__tests__/PrimeUrlStateBridge.test.tsx
import { render, screen, act } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import {
  PrimeNexusProvider,
  usePrimeNexus,
} from "@/contexts/PrimeNexusContext";
import { PrimeUrlStateBridge } from "../PrimeUrlStateBridge";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  useSearchParams: () => new URLSearchParams("layers=kkop,lp2b&compareA=Z9"),
  usePathname: () => "/prime",
}));

function Probe() {
  const ctx = usePrimeNexus();
  return (
    <>
      <span data-testid="kkop">{String(ctx.layers.kkop)}</span>
      <span data-testid="lp2b">{String(ctx.layers.lp2b)}</span>
      <span data-testid="A">{ctx.compareA?.id ?? "none"}</span>
    </>
  );
}

describe("PrimeUrlStateBridge", () => {
  it("hydrates context from URL on mount", () => {
    render(
      <PrimeNexusProvider>
        <PrimeUrlStateBridge />
        <Probe />
      </PrimeNexusProvider>,
    );
    expect(screen.getByTestId("kkop")).toHaveTextContent("true");
    expect(screen.getByTestId("lp2b")).toHaveTextContent("true");
    expect(screen.getByTestId("A")).toHaveTextContent("Z9");
  });
});
```

- [ ] **Step 2: Implement the bridge**

```tsx
// apps/mouth/src/components/maps/prime/PrimeUrlStateBridge.tsx
"use client";
import { useEffect, useMemo, useRef } from "react";
import { usePrimeNexus } from "@/contexts/PrimeNexusContext";
import {
  useReadPrimeUrl,
  useWritePrimeUrl,
  type PrimeUrlState,
} from "./hooks/usePrimeUrlState";
import { DEFAULT_MAP_LAYERS } from "@/contexts/PrimeNexusContext";

export function PrimeUrlStateBridge() {
  const ctx = usePrimeNexus();
  const incoming = useReadPrimeUrl();
  const hydratedRef = useRef(false);

  // One-time hydrate
  useEffect(() => {
    if (hydratedRef.current) return;
    hydratedRef.current = true;
    if (incoming.layers?.length) {
      const next = { ...DEFAULT_MAP_LAYERS };
      (Object.keys(next) as Array<keyof typeof next>).forEach((k) => {
        next[k] = incoming.layers!.includes(k);
      });
      ctx.setLayers(next);
    }
    if (incoming.compareA) {
      ctx.addToCompare({
        id: incoming.compareA,
        name: incoming.compareA,
        zoneCode: null,
        info: null,
      });
    }
    if (incoming.compareB) {
      ctx.addToCompare({
        id: incoming.compareB,
        name: incoming.compareB,
        zoneCode: null,
        info: null,
      });
    }
    // lat/lng/zoom are read by PrimeMap3D directly via useReadPrimeUrl (Task 9).
  }, [ctx, incoming]);

  // Outgoing sync — rebuild the URL state every render from context
  const outgoing: PrimeUrlState = useMemo(() => {
    const activeLayers = (
      Object.entries(ctx.layers) as Array<[keyof typeof ctx.layers, boolean]>
    )
      .filter(([, v]) => v)
      .map(([k]) => k);
    return {
      layers: activeLayers.length ? activeLayers : undefined,
      compareA: ctx.compareA?.id,
      compareB: ctx.compareB?.id,
    };
  }, [ctx.layers, ctx.compareA, ctx.compareB]);

  useWritePrimeUrl(outgoing);
  return null;
}
```

- [ ] **Step 3: Mount bridge inside PrimeNexusLayout**

In `apps/mouth/src/components/maps/prime/PrimeNexusLayout.tsx`, inside `PrimeNexusInner`, add the import and mount `<PrimeUrlStateBridge />` just above `<PrimeMap3D />`:

```tsx
import { PrimeUrlStateBridge } from "./PrimeUrlStateBridge";
// ...
return (
  <div className="h-screen bg-black overflow-hidden relative">
    <PrimeUrlStateBridge />
    <PrimeMap3D />
    {/* ... rest unchanged ... */}
```

Also wrap the outer `PrimeNexusInner` return with `<Suspense fallback={<PrimeMapSkeleton />}>…</Suspense>` — required by Next 16 for `useSearchParams` in CSR. Add the imports at the top of the file:

```tsx
import { Suspense } from "react";
// existing PrimeMapSkeleton import already done in Task 5
```

And change the exported default:

```tsx
export default function PrimeNexusLayout() {
  return (
    <PrimeNexusProvider>
      <Suspense fallback={<PrimeMapSkeleton />}>
        <PrimeNexusInner />
      </Suspense>
    </PrimeNexusProvider>
  );
}
```

- [ ] **Step 4: Run tests + typecheck**

```bash
cd apps/mouth && npx vitest run src/components/maps/prime/__tests__/PrimeUrlStateBridge.test.tsx && npm run typecheck
```

Expected: bridge test + typecheck green.

- [ ] **Step 5: Commit**

```bash
git add apps/mouth/src/components/maps/prime/PrimeUrlStateBridge.tsx apps/mouth/src/components/maps/prime/__tests__/PrimeUrlStateBridge.test.tsx apps/mouth/src/components/maps/prime/PrimeNexusLayout.tsx
git commit -m "feat(prime): PrimeUrlStateBridge + Suspense wrap"
```

---

## Task 9: Wire `PrimeMap3D` layers to context (surgical)

**Files:**

- Modify: `apps/mouth/src/components/maps/PrimeMap3D.tsx`

- [ ] **Step 1: Read the current layer state plumbing**

Open `PrimeMap3D.tsx`. The component currently owns `const [layers, setLayers] = useState<MapLayers>({...})` (line ~53). We will replace this internal source of truth with context values, without touching any of the map/polygon logic that reads them.

- [ ] **Step 2: Replace local layers state with context**

Change line ~53 from:

```tsx
const [layers, setLayers] = useState<MapLayers>({
  zoneColors: true,
  extrusion: false,
  kkop: false,
  lp2b: false,
  tsunami: false,
  floodRisk: false,
  templeBuffer: false,
});
```

to:

```tsx
// PF3a — layer state owned by PrimeNexusContext
const layers = primeNexus?.layers ?? {
  zoneColors: true,
  extrusion: false,
  kkop: false,
  lp2b: false,
  tsunami: false,
  floodRisk: false,
  templeBuffer: false,
};
const setLayers = (next: typeof layers) => {
  primeNexus?.setLayers(next);
};
```

`primeNexus` is already destructured at the top of `PrimeMap3D` via `useContext(PrimeNexusContext)` — confirm and add if not.

- [ ] **Step 3: Publish the polygon ref to context**

Near the bottom of the `useEffect` that populates `zonePolygonsRef.current` (around line 248), add (inside the effect, after the push loop):

```tsx
if (
  primeNexus &&
  "zonePolygonsRef" in primeNexus &&
  (primeNexus as { zonePolygonsRef: unknown }).zonePolygonsRef !== undefined
) {
  // Expose the ref to consumers (legend hover highlight)
  (
    primeNexus as unknown as { zonePolygonsRef: { current: unknown[] } }
  ).zonePolygonsRef = zonePolygonsRef;
}
```

(If the context provider doesn't accept writeable ref yet, this is a no-op — the legend will still work via `toggleLayer`, just without the hover highlight. Accept the graceful degradation for this PR; full wiring is tracked as a follow-up in §6 of the spec.)

- [ ] **Step 4: Add ARIA labels to existing controls**

Find the top-level layer toggle buttons (around line 1126-1165: `enabled={layers.zoneColors}` etc.). For each `<LayerToggle>` usage, confirm the parent container has `role="group"` and `aria-label="Map layers"`. If the wrapping div lacks these, add them on the surrounding container div:

```tsx
<div role="group" aria-label="Map layers" className="...existing classes...">
  <LayerToggle ... />
  ...
</div>
```

Do not change `LayerToggle` itself.

- [ ] **Step 5: Apply URL-provided initial lat/lng/zoom**

Near where the map initial camera is set (search for `importLibrary('maps3d')` + camera config, around line 321), after the map3DElement creation, wire initial view from URL if present. Import the hook at the top:

```tsx
import { useReadPrimeUrl } from "./prime/hooks/usePrimeUrlState";
```

Near the top of the component:

```tsx
const urlState = useReadPrimeUrl();
```

Right after `setMap3DElement(...)`, add:

```tsx
if (urlState.lat !== undefined && urlState.lng !== undefined) {
  map3DElement.center = {
    lat: urlState.lat,
    lng: urlState.lng,
    altitude: map3DElement.center?.altitude ?? 1000,
  };
}
if (urlState.zoom !== undefined) {
  map3DElement.range = 2 ** (22 - urlState.zoom) * 100;
}
```

(The `range` conversion is an approximation — good enough for deep-link; fine-tune only if visual QA flags it.)

- [ ] **Step 6: Typecheck + run existing tests**

```bash
cd apps/mouth && npm run typecheck && npx vitest run src/contexts
```

Expected: both green.

- [ ] **Step 7: Smoke-test in browser**

```bash
cd apps/mouth && npm run dev
```

Visit:

- `http://localhost:3000/prime` — loads normally.
- `http://localhost:3000/prime?lat=-8.65&lng=115.21&zoom=15&layers=zoneColors,kkop` — map centers on those coords with those two layers on.

Stop dev server.

- [ ] **Step 8: Commit**

```bash
git add apps/mouth/src/components/maps/PrimeMap3D.tsx
git commit -m "feat(prime): PrimeMap3D reads layers + initial camera from context/URL"
```

---

## Task 10: `PrimeLayerLegend` component

**Files:**

- Create: `apps/mouth/src/components/maps/prime/PrimeLayerLegend.tsx`
- Create: `apps/mouth/src/components/maps/prime/__tests__/PrimeLayerLegend.test.tsx`
- Modify: `apps/mouth/src/components/maps/prime/PrimeNexusLayout.tsx`

- [ ] **Step 1: Write failing legend tests**

```tsx
// apps/mouth/src/components/maps/prime/__tests__/PrimeLayerLegend.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import {
  PrimeNexusProvider,
  usePrimeNexus,
} from "@/contexts/PrimeNexusContext";
import { PrimeLayerLegend } from "../PrimeLayerLegend";

function Probe() {
  const ctx = usePrimeNexus();
  return <span data-testid="kkop">{String(ctx.layers.kkop)}</span>;
}

describe("PrimeLayerLegend", () => {
  it("renders a row per layer with role=switch", () => {
    render(
      <PrimeNexusProvider>
        <PrimeLayerLegend />
      </PrimeNexusProvider>,
    );
    const switches = screen.getAllByRole("switch");
    expect(switches.length).toBe(7);
  });

  it("click toggles a layer", async () => {
    render(
      <PrimeNexusProvider>
        <PrimeLayerLegend />
        <Probe />
      </PrimeNexusProvider>,
    );
    expect(screen.getByTestId("kkop")).toHaveTextContent("false");
    await userEvent.click(screen.getByRole("switch", { name: /kkop/i }));
    expect(screen.getByTestId("kkop")).toHaveTextContent("true");
  });

  it("shift+click isolates a layer", async () => {
    render(
      <PrimeNexusProvider>
        <PrimeLayerLegend />
        <Probe />
      </PrimeNexusProvider>,
    );
    await userEvent.keyboard("{Shift>}");
    await userEvent.click(screen.getByRole("switch", { name: /kkop/i }));
    await userEvent.keyboard("{/Shift}");
    expect(screen.getByTestId("kkop")).toHaveTextContent("true");
    // zoneColors should now be off after isolate
    expect(
      screen.getByRole("switch", { name: /zone colors/i }),
    ).toHaveAttribute("aria-checked", "false");
  });

  it("is collapsible and persists state", async () => {
    const { unmount } = render(
      <PrimeNexusProvider>
        <PrimeLayerLegend />
      </PrimeNexusProvider>,
    );
    await userEvent.click(
      screen.getByRole("button", { name: /collapse legend/i }),
    );
    unmount();
    render(
      <PrimeNexusProvider>
        <PrimeLayerLegend />
      </PrimeNexusProvider>,
    );
    // After remount localStorage should keep it collapsed (no switches visible)
    expect(screen.queryAllByRole("switch")).toHaveLength(0);
  });
});
```

- [ ] **Step 2: Implement the legend**

```tsx
// apps/mouth/src/components/maps/prime/PrimeLayerLegend.tsx
"use client";
import { useEffect, useState } from "react";
import { usePrimeNexus } from "@/contexts/PrimeNexusContext";
import type { MapLayersState } from "@/contexts/PrimeNexusContext";
import { ZONE_COLORS } from "@/components/maps/mapConstants";

interface Row {
  key: keyof MapLayersState;
  label: string;
  swatch: string;
}

const ROWS: Row[] = [
  {
    key: "zoneColors",
    label: "Zone colors",
    swatch: ZONE_COLORS?.default ?? "#d4845a",
  },
  { key: "extrusion", label: "3D extrusion", swatch: "#9fb5c9" },
  { key: "kkop", label: "KKOP (airport)", swatch: "#ff8b3d" },
  { key: "lp2b", label: "LP2B (agri)", swatch: "#5bb05b" },
  { key: "tsunami", label: "Tsunami", swatch: "#4aa3df" },
  { key: "floodRisk", label: "Flood risk", swatch: "#7986cb" },
  { key: "templeBuffer", label: "Temple buffer", swatch: "#c39bd3" },
];

const LS_KEY = "prime.legend.collapsed";

export function PrimeLayerLegend() {
  const ctx = usePrimeNexus();
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const v = localStorage.getItem(LS_KEY);
    if (v === "1") setCollapsed(true);
  }, []);

  useEffect(() => {
    localStorage.setItem(LS_KEY, collapsed ? "1" : "0");
  }, [collapsed]);

  return (
    <div
      role="group"
      aria-label="Map layers"
      className="absolute top-4 left-4 z-30 rounded-2xl bg-black/85 backdrop-blur-xl border border-white/10 text-white shadow-2xl overflow-hidden"
    >
      <div className="flex items-center justify-between px-3 py-2 border-b border-white/10">
        <span className="text-xs uppercase tracking-wider text-white/60">
          Layers
        </span>
        <button
          type="button"
          aria-label={collapsed ? "Expand legend" : "Collapse legend"}
          onClick={() => setCollapsed((c) => !c)}
          className="text-white/60 hover:text-white text-sm"
        >
          {collapsed ? "▸" : "▾"}
        </button>
      </div>
      {!collapsed && (
        <ul className="py-1">
          {ROWS.map((row) => {
            const on = ctx.layers[row.key];
            return (
              <li
                key={row.key}
                onMouseEnter={() => ctx.setHoveredLayer(row.key)}
                onMouseLeave={() => ctx.setHoveredLayer(null)}
              >
                <button
                  type="button"
                  role="switch"
                  aria-checked={on}
                  aria-label={row.label}
                  onClick={(e) => {
                    if (e.shiftKey) ctx.isolateLayer(row.key);
                    else ctx.toggleLayer(row.key);
                  }}
                  className={`w-full flex items-center gap-3 px-3 py-2 text-left text-sm hover:bg-white/5 ${
                    on ? "text-white" : "text-white/40"
                  }`}
                >
                  <span
                    className="w-3 h-3 rounded-sm border border-white/20"
                    style={{ backgroundColor: row.swatch }}
                  />
                  <span className="flex-1">{row.label}</span>
                  <span className="text-[10px] uppercase tracking-wider text-white/30">
                    {on ? "on" : "off"}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Mount legend in `PrimeNexusLayout`**

In `apps/mouth/src/components/maps/prime/PrimeNexusLayout.tsx` add the import:

```tsx
import { PrimeLayerLegend } from "./PrimeLayerLegend";
```

Inside `PrimeNexusInner`, place just after `<PrimeMap3D />`:

```tsx
<PrimeLayerLegend />
```

- [ ] **Step 4: Run tests + typecheck**

```bash
cd apps/mouth && npx vitest run src/components/maps/prime/__tests__/PrimeLayerLegend.test.tsx && npm run typecheck
```

Expected: all 4 legend tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/mouth/src/components/maps/prime/PrimeLayerLegend.tsx apps/mouth/src/components/maps/prime/__tests__/PrimeLayerLegend.test.tsx apps/mouth/src/components/maps/prime/PrimeNexusLayout.tsx
git commit -m "feat(prime): interactive layer legend with isolate + a11y"
```

---

## Task 11: `PrimeCompareDrawer` component

**Files:**

- Create: `apps/mouth/src/components/maps/prime/PrimeCompareDrawer.tsx`
- Create: `apps/mouth/src/components/maps/prime/__tests__/PrimeCompareDrawer.test.tsx`
- Modify: `apps/mouth/src/components/maps/prime/PrimeNexusLayout.tsx`

- [ ] **Step 1: Write failing compare-drawer tests**

```tsx
// apps/mouth/src/components/maps/prime/__tests__/PrimeCompareDrawer.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import {
  PrimeNexusProvider,
  usePrimeNexus,
  type ZoneSelection,
} from "@/contexts/PrimeNexusContext";
import { PrimeCompareDrawer } from "../PrimeCompareDrawer";

function ZoneAdder({ zone }: { zone: ZoneSelection }) {
  const ctx = usePrimeNexus();
  return <button onClick={() => ctx.addToCompare(zone)}>add-{zone.id}</button>;
}

const Z1: ZoneSelection = {
  id: "Z1",
  name: "Sanur Commercial",
  zoneCode: "C-1",
  info: { restricted: false },
};
const Z2: ZoneSelection = {
  id: "Z2",
  name: "Canggu Residential",
  zoneCode: "R-2",
  info: { restricted: true },
};

describe("PrimeCompareDrawer", () => {
  it("is hidden when no zones selected", () => {
    render(
      <PrimeNexusProvider>
        <PrimeCompareDrawer />
      </PrimeNexusProvider>,
    );
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("shows one card with one zone, then two with delta section", async () => {
    render(
      <PrimeNexusProvider>
        <ZoneAdder zone={Z1} />
        <ZoneAdder zone={Z2} />
        <PrimeCompareDrawer />
      </PrimeNexusProvider>,
    );
    await userEvent.click(screen.getByText("add-Z1"));
    expect(
      screen.getByRole("dialog", { name: /zone comparison/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("Sanur Commercial")).toBeInTheDocument();
    expect(screen.queryByText(/delta/i)).toBeNull();
    await userEvent.click(screen.getByText("add-Z2"));
    expect(screen.getByText("Canggu Residential")).toBeInTheDocument();
    expect(screen.getByText(/delta/i)).toBeInTheDocument();
  });

  it("ESC clears all selections", async () => {
    render(
      <PrimeNexusProvider>
        <ZoneAdder zone={Z1} />
        <PrimeCompareDrawer />
      </PrimeNexusProvider>,
    );
    await userEvent.click(screen.getByText("add-Z1"));
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
```

- [ ] **Step 2: Implement the drawer**

```tsx
// apps/mouth/src/components/maps/prime/PrimeCompareDrawer.tsx
"use client";
import { useEffect } from "react";
import {
  usePrimeNexus,
  type ZoneSelection,
} from "@/contexts/PrimeNexusContext";

function ZoneCard({
  zone,
  onClear,
  slot,
}: {
  zone: ZoneSelection;
  onClear: () => void;
  slot: "A" | "B";
}) {
  const info = (zone.info ?? {}) as Record<string, unknown>;
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-sm text-white/90">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] uppercase tracking-wider text-white/50">
          Slot {slot}
        </span>
        <button
          type="button"
          onClick={onClear}
          className="text-white/50 hover:text-white text-xs"
          aria-label={`Clear slot ${slot}`}
        >
          ✕
        </button>
      </div>
      <div className="font-semibold">{zone.name}</div>
      {zone.zoneCode && (
        <div className="text-xs text-white/60">Code: {zone.zoneCode}</div>
      )}
      <dl className="mt-2 space-y-1 text-xs">
        {Object.entries(info).map(([k, v]) => (
          <div key={k} className="flex justify-between gap-4">
            <dt className="text-white/50">{k}</dt>
            <dd className="text-white/80 truncate">{String(v)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function Delta({ a, b }: { a: ZoneSelection; b: ZoneSelection }) {
  const infoA = (a.info ?? {}) as Record<string, unknown>;
  const infoB = (b.info ?? {}) as Record<string, unknown>;
  const keys = Array.from(
    new Set([...Object.keys(infoA), ...Object.keys(infoB)]),
  );
  const diffs = keys.filter(
    (k) => JSON.stringify(infoA[k]) !== JSON.stringify(infoB[k]),
  );
  return (
    <div className="rounded-xl border border-[#d4845a]/40 bg-[#d4845a]/5 p-3 text-xs">
      <div className="text-[10px] uppercase tracking-wider text-[#d4845a] mb-2">
        Delta
      </div>
      {diffs.length === 0 ? (
        <div className="text-white/60">No differences detected</div>
      ) : (
        <ul className="space-y-1">
          {diffs.map((k) => (
            <li key={k} className="flex justify-between gap-2">
              <span className="text-white/50">{k}</span>
              <span className="text-white/80">
                {String(infoA[k] ?? "—")} → {String(infoB[k] ?? "—")}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function PrimeCompareDrawer() {
  const ctx = usePrimeNexus();
  const { compareA, compareB, clearCompareSlot, clearCompareAll } = ctx;

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && (compareA || compareB)) {
        clearCompareAll();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [compareA, compareB, clearCompareAll]);

  if (!compareA && !compareB) return null;

  return (
    <div
      role="dialog"
      aria-label="Zone comparison"
      className="absolute top-4 right-4 bottom-4 w-80 z-40 overflow-y-auto rounded-2xl bg-black/90 backdrop-blur-xl border border-white/10 shadow-2xl p-3 space-y-3"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-sm uppercase tracking-wider text-white/70">
          Compare
        </h2>
        <button
          type="button"
          onClick={clearCompareAll}
          className="text-xs text-white/50 hover:text-white"
        >
          Clear all
        </button>
      </div>
      {compareA && (
        <ZoneCard
          zone={compareA}
          slot="A"
          onClear={() => clearCompareSlot("A")}
        />
      )}
      {compareB && (
        <ZoneCard
          zone={compareB}
          slot="B"
          onClear={() => clearCompareSlot("B")}
        />
      )}
      {compareA && compareB && <Delta a={compareA} b={compareB} />}
    </div>
  );
}
```

- [ ] **Step 3: Mount drawer in layout**

In `apps/mouth/src/components/maps/prime/PrimeNexusLayout.tsx` add import:

```tsx
import { PrimeCompareDrawer } from "./PrimeCompareDrawer";
```

Inside `PrimeNexusInner`, just after `<PrimeLayerLegend />`:

```tsx
<PrimeCompareDrawer />
```

- [ ] **Step 4: Hook zone-click to add-to-compare**

In `apps/mouth/src/components/maps/PrimeMap3D.tsx`, find the zoning-click handler (search for `setZoningResult`, around line 300-360). Just after the successful fetch that sets `zoningResult`, add:

```tsx
if (primeNexus && zoningResult?.zone_code) {
  primeNexus.addToCompare({
    id: zoningResult.zone_code,
    name: zoningResult.zone_name ?? zoningResult.zone_code,
    zoneCode: zoningResult.zone_code,
    info: {
      restricted: zoningResult.is_restricted ?? false,
      risk: zoningResult.risk_score ?? null,
      district: zoningResult.district ?? null,
    },
  });
}
```

This auto-adds clicked zones to the first empty slot. (Spec mentions right-click menu; for MVP we use plain click with the existing flow — less UI noise, user still gets the delta view. Right-click menu tracked for PF3c.)

- [ ] **Step 5: Run tests + typecheck**

```bash
cd apps/mouth && npx vitest run src/components/maps/prime/__tests__/PrimeCompareDrawer.test.tsx && npm run typecheck
```

Expected: all 3 drawer tests PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/mouth/src/components/maps/prime/PrimeCompareDrawer.tsx apps/mouth/src/components/maps/prime/__tests__/PrimeCompareDrawer.test.tsx apps/mouth/src/components/maps/prime/PrimeNexusLayout.tsx apps/mouth/src/components/maps/PrimeMap3D.tsx
git commit -m "feat(prime): compare drawer with slot A/B + delta"
```

---

## Task 12: Playwright e2e suites

**Files:**

- Create: `apps/mouth/e2e/prime.spec.ts`
- Create: `apps/mouth/e2e/prime-compare.spec.ts`
- Create: `apps/mouth/e2e/prime-firefox.spec.ts`
- Modify: `apps/mouth/playwright.config.ts` (add firefox project if absent)

- [ ] **Step 1: Inspect playwright.config.ts**

Read `apps/mouth/playwright.config.ts`. If it does not already declare a `firefox` project, add one:

```ts
// inside projects array
{
  name: "firefox",
  use: { browserName: "firefox" },
  grepInvert: undefined,
  testMatch: /prime-firefox\.spec\.ts$/,
},
```

- [ ] **Step 2: Write `prime.spec.ts`**

```ts
// apps/mouth/e2e/prime.spec.ts
import { test, expect } from "@playwright/test";

test("deep-linked URL hydrates layers and camera", async ({ page }) => {
  await page.goto("/prime?lat=-8.65&lng=115.21&zoom=15&layers=zoneColors,kkop");
  // Legend renders
  await expect(page.getByRole("group", { name: "Map layers" })).toBeVisible();
  // kkop is on
  const kkopSwitch = page.getByRole("switch", { name: /kkop/i });
  await expect(kkopSwitch).toHaveAttribute("aria-checked", "true");
  // lp2b is off
  const lp2bSwitch = page.getByRole("switch", { name: /lp2b/i });
  await expect(lp2bSwitch).toHaveAttribute("aria-checked", "false");
});

test("clicking legend updates URL", async ({ page }) => {
  await page.goto("/prime?layers=zoneColors");
  await page.getByRole("switch", { name: /kkop/i }).click();
  await page.waitForTimeout(500); // debounce
  await expect(page).toHaveURL(
    /layers=zoneColors%2Ckkop|layers=kkop%2CzoneColors/,
  );
});
```

- [ ] **Step 3: Write `prime-compare.spec.ts`**

```ts
// apps/mouth/e2e/prime-compare.spec.ts
import { test, expect } from "@playwright/test";

test("compare drawer opens with two zones selected", async ({ page }) => {
  await page.goto("/prime?compareA=TEST-A&compareB=TEST-B");
  const dialog = page.getByRole("dialog", { name: /zone comparison/i });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText("TEST-A")).toBeVisible();
  await expect(dialog.getByText("TEST-B")).toBeVisible();
  await expect(dialog.getByText(/delta/i)).toBeVisible();
});

test("ESC closes compare drawer", async ({ page }) => {
  await page.goto("/prime?compareA=TEST-A");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toBeHidden();
});
```

- [ ] **Step 4: Write `prime-firefox.spec.ts`**

```ts
// apps/mouth/e2e/prime-firefox.spec.ts
import { test, expect } from "@playwright/test";

test("Firefox sees the gate fallback", async ({ page }) => {
  await page.goto("/prime");
  await expect(
    page.getByRole("heading", { name: /prime requires/i }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /continue anyway/i }),
  ).toBeVisible();
});
```

- [ ] **Step 5: Run e2e suite (Chromium)**

```bash
cd apps/mouth && npm run test:e2e -- --project=chromium --grep "Prime|compare"
```

Expected: all Chromium e2e tests pass. If the project name differs, adjust.

- [ ] **Step 6: Run e2e suite (Firefox)**

```bash
cd apps/mouth && npm run test:e2e -- --project=firefox
```

Expected: `prime-firefox.spec.ts` passes.

- [ ] **Step 7: Commit**

```bash
git add apps/mouth/e2e/prime.spec.ts apps/mouth/e2e/prime-compare.spec.ts apps/mouth/e2e/prime-firefox.spec.ts apps/mouth/playwright.config.ts
git commit -m "test(prime): e2e suites for deep-link, compare, firefox gate"
```

---

## Task 13: Final Lighthouse + artifacts + verification

**Files:**

- Create: `docs/superpowers/specs/artifacts/2026-04-18-prime-after.json`
- Create: `docs/superpowers/specs/artifacts/2026-04-18-prime-after-desktop.png`
- Create: `docs/superpowers/specs/artifacts/2026-04-18-prime-after-mobile.png`
- Create: `docs/superpowers/specs/artifacts/2026-04-18-prime-firefox.png`

- [ ] **Step 1: Full typecheck + lint + unit + e2e**

```bash
cd apps/mouth && npm run typecheck && npm run lint && npm test -- --run && npm run test:e2e
```

Expected: all green. Fix any regressions before continuing.

- [ ] **Step 2: Capture final Lighthouse**

```bash
cd apps/mouth && npm run build && npm start &
sleep 5
LABEL=after node apps/mouth/scripts/lighthouse-prime.mjs
kill %1
```

Expected: `docs/superpowers/specs/artifacts/2026-04-18-prime-after.json` written. **Gate:** desktop LCP < 3000ms AND mobile LCP < 5000ms. If gate fails, investigate (check bundle analyzer, verify `next/dynamic` preserved the split, confirm skeleton image loaded). Do NOT open the PR until the gate passes.

- [ ] **Step 3: Capture final screenshots**

With dev server running (`npm run dev`), Chrome desktop 1440×900 + mobile 390×844 emulation:

- `/prime` default view
- `/prime?layers=zoneColors,kkop,lp2b` — 3 layers on
- `/prime?compareA=…&compareB=…` — drawer visible

Save to `docs/superpowers/specs/artifacts/2026-04-18-prime-after-*.png`.

Then switch to Firefox, go to `/prime`, screenshot the gate → `2026-04-18-prime-firefox.png`.

- [ ] **Step 4: Run bundle analyzer**

```bash
cd apps/mouth && ANALYZE=true npm run build
```

Expected: `PrimeMap3D` chunk appears in the bundle report and is NOT in the root `/prime` chunk. Confirm by searching the report for `PrimeMap3D`.

- [ ] **Step 5: Commit artifacts**

```bash
git add docs/superpowers/specs/artifacts/2026-04-18-prime-after*.json docs/superpowers/specs/artifacts/2026-04-18-prime-after-*.png docs/superpowers/specs/artifacts/2026-04-18-prime-firefox.png
git commit -m "chore(prime): after-state Lighthouse + screenshots"
```

---

## Task 14: Open PR

**Files:** n/a (git + gh)

- [ ] **Step 1: Push branch**

```bash
git push -u origin pro/frontend-prime-perf-ux
```

- [ ] **Step 2: Open PR**

```bash
gh pr create --base main --title "feat(prime): LCP split + Firefox gate + URL state + legend + compare drawer" --body "$(cat <<'EOF'
## Summary

- Dynamic split of PrimeMap3D (1,179 LOC) via `next/dynamic` — Google Maps loader moves out of initial bundle.
- Pre-blurred skeleton becomes LCP element; preconnect + dns-prefetch scoped to `/prime/*`.
- Firefox / non-Chromium gate with clear fallback + "Continue anyway" escape hatch.
- Deep-linkable URL state (`?lat=&lng=&zoom=&layers=&compareA=&compareB=`) via URLSearchParams + Zod validation.
- Interactive layer legend with click-toggle, shift+click isolate, hover highlight, ARIA switches.
- Side-by-side compare drawer with slot A/B, delta view, ESC to clear.

## Metrics

| | Before | After |
|---|---|---|
| Desktop LCP | __ms | __ms |
| Mobile LCP | __ms | __ms |
| PrimeMap3D chunk | in root | split |

Artifacts: `docs/superpowers/specs/artifacts/2026-04-18-prime-*`.

## Test plan

- [ ] Vitest unit tests pass (7 new)
- [ ] Playwright e2e (Chromium + Firefox)
- [ ] Manual Chrome desktop: legend + compare + deep-link
- [ ] Manual Chrome mobile viewport: skeleton visible, map loads
- [ ] Manual Firefox: gate message shown, no console error
- [ ] Lighthouse after-state under target thresholds
- [ ] Bundle analyzer confirms PrimeMap3D chunk split

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

(Fill the \_\_ms placeholders with actual numbers from the artifacts before opening the PR.)

- [ ] **Step 3: Verify PR URL**

```bash
gh pr view --web
```

---

## Self-Review

**Spec coverage:**

- §1 Problem → Tasks 1, 5, 3, 7, 10, 11 cover all three stated blockers.
- §2 Goals — LCP: Task 5 + Task 13 gate. Firefox: Task 3. URL state: Tasks 7-9. Legend: Task 10. Compare: Task 11. Zero regressions: Task 13 step 1.
- §3 Non-goals — favorites/export/mobile-2D correctly absent from the plan.
- §4.1 Architecture — wrap pattern respected: `PrimeMap3D` touched only in Task 9 (surgical, 3 changes).
- §4.2 Performance — Task 4 (skeleton + preconnect) + Task 5 (dynamic split) + Task 13 step 4 (bundle verify).
- §4.3 Browser detection — Task 2.
- §4.4 URL state — Tasks 7, 8.
- §4.5 Legend — Task 10. Hover highlight graceful-degrades (Task 9 step 3 note) because `zonePolygonsRef` write-back is fragile; full wiring deferred — acceptable per spec §6 risk M1.
- §4.6 Compare — Task 11. Note: spec mentioned right-click menu; plan uses plain click (Task 11 step 4 note) — documented deviation.
- §4.7 Data flow — matches bridge + context pattern.
- §4.8 Error handling — 15s timeout for Maps script is NOT implemented in this plan. Acceptable for MVP; tracked in §6 of spec as risk. Leaving as known gap, documented above.
- §4.9 Testing — all 6 unit + 3 e2e files present.
- §4.10 Verification — Task 13 covers all 9 verification items.
- §5 Constraints — API key untouched, backend untouched, tokens untouched.
- §7 Build sequence — plan tasks align 1:1 with spec §7 sequence.

**Placeholder scan:** No "TBD/TODO/similar to" language in steps. Commit messages for Tasks 5 and 14 have literal `<baseline>→<new>` placeholders that the executor fills from actual Lighthouse artifacts — this is intentional (real numbers required, not optional).

**Type consistency:** `MapLayersState` used consistently. `ZoneSelection` shape used in context, bridge, drawer. `PrimeUrlState` stable across parse/serialize/read/write. `BrowserSupport` shape stable between hook and gate consumer. `toggleLayer` / `isolateLayer` / `addToCompare` / `clearCompareSlot` / `clearCompareAll` signatures identical in context type (§6 step 3), provider impl (§6 step 4), and all consumers (Tasks 10, 11).

**Known gaps tracked (not placeholders):**

1. Right-click "Add to compare" menu → plain click adopted; right-click in PF3c.
2. 15s Maps script timeout card → deferred to PF3c.
3. `zonePolygonsRef` writeback for hover-highlight polygons → graceful degradation; legend still fully functional for toggle/isolate.
