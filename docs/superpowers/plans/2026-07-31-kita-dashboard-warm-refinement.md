# Kita Dashboard Warm Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the redundant Zantara lotus from the useful dashboard portal card and give Kita a warmer near-white default canvas without altering My or Prime.

**Architecture:** Preserve the existing portal-card link and layout, changing only its redundant asset. Scope the palette through the existing `[data-theme="operative-light"][data-product="kita"]` token block so downstream workspace surfaces inherit the warmer background without component-level color overrides.

**Tech Stack:** Next.js 16, React 19, TypeScript, Tailwind CSS 4, Vitest, Testing Library, Playwright.

## Global Constraints

- Keep `https://zantara.balizero.com/chat` as the portal destination.
- Keep the Bali Zero `BZLogo`; remove only `/static/zantara-lotus-v2.png` from this card.
- Kita day mode must remain visually white; use low-chroma warm neutrals, not beige cards.
- Keep My and Prime token scopes unchanged.
- Do not deploy, merge, or publish; update the existing draft PR only.
- Report unrelated broken dashboard behavior instead of expanding scope silently.

---

## File map

- `apps/mouth/src/components/dashboard/ZantaraPortalCard.tsx`: dashboard portal card asset and destination.
- `apps/mouth/src/components/dashboard/__tests__/ZantaraPortalCard.test.tsx`: user-visible portal-card contract.
- `apps/mouth/src/app/globals.css`: product-scoped Kita day palette.
- `apps/mouth/src/app/(workspace)/__tests__/kita-theme.contract.test.ts`: scoped palette regression contract.
- `apps/mouth/e2e/bz-product-family.spec.ts`: authenticated product-family interaction regression.
- `docs/superpowers/specs/2026-07-31-kita-dashboard-warm-refinement-design.md`: approved design record.

### Task 1: Synchronize the existing draft branch

**Files:**

- Resolve only if conflicted: `apps/mouth/src/app/(workspace)/process/[id]/page.tsx`
- Resolve only if conflicted: `apps/mouth/src/app/portal/(authenticated)/chat/page.tsx`
- Resolve only if conflicted: `apps/mouth/src/app/portal/(authenticated)/layout.tsx`
- Resolve only if conflicted: `apps/mouth/src/components/workspace/AppSidebar.tsx`

**Interfaces:**

- Consumes: current `main` and draft branch `agent/air-m5/mouth/bz-ui-restyle`.
- Produces: a conflict-free draft branch containing both current-main behavior and the approved restyle.

- [ ] **Step 1: Commit the approved design and implementation plan**

```bash
git add docs/superpowers/specs/2026-07-31-kita-dashboard-warm-refinement-design.md docs/superpowers/plans/2026-07-31-kita-dashboard-warm-refinement.md
git commit -m "docs(mouth): plan Kita dashboard warm refinement"
```

- [ ] **Step 2: Merge current main without rewriting draft history**

```bash
git fetch origin main
git merge --no-ff origin/main
```

Expected: four localized conflicts at most; no reset, rebase, force-push, or unrelated file deletion.

- [ ] **Step 3: Resolve conflicts by preserving both contracts**

For each conflict, retain the restyle's semantic tokens/accessibility behavior and current main's newer runtime/error-handling behavior. Then prove the index is clean:

```bash
rg -n '^(<<<<<<<|=======|>>>>>>>)' apps/mouth/src
git diff --check
git status --short
```

Expected: no conflict markers; only the merge result is staged.

- [ ] **Step 4: Run the conflict-zone tests**

```bash
cd apps/mouth
npm test -- --run 'src/app/(workspace)/process/[id]/page.test.tsx' 'src/app/portal/(authenticated)/chat/page.test.tsx' 'src/app/portal/(authenticated)/layout.test.tsx'
```

Expected: all discovered conflict-zone tests pass; if a listed path does not exist, run the nearest existing test shown by `rg --files src | rg '(process|portal).*(test|spec)'` and record the substitution.

### Task 2: Preserve the portal action while removing the redundant mark

**Files:**

- Create: `apps/mouth/src/components/dashboard/__tests__/ZantaraPortalCard.test.tsx`
- Modify: `apps/mouth/src/components/dashboard/ZantaraPortalCard.tsx`

**Interfaces:**

- Consumes: `BZLogo` and constant `ZANTARA_URL`.
- Produces: `ZantaraPortalCard(): React.JSX.Element` with one Bali Zero mark and a valid external link.

- [ ] **Step 1: Write the failing user-visible test**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ZantaraPortalCard } from "../ZantaraPortalCard";

describe("ZantaraPortalCard", () => {
  it("keeps the working chat link without a duplicate Zantara mark", () => {
    render(<ZantaraPortalCard />);

    expect(screen.getByRole("link", { name: /Zantara AI/i })).toHaveAttribute(
      "href",
      "https://zantara.balizero.com/chat",
    );
    expect(screen.queryByAltText("Zantara")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the focused test and observe RED**

```bash
cd apps/mouth
npm test -- --run src/components/dashboard/__tests__/ZantaraPortalCard.test.tsx
```

Expected: FAIL because the current card still renders an image with `alt="Zantara"`.

- [ ] **Step 3: Remove only the redundant Zantara image**

Delete the `next/image` import and the overlaid lotus container. Keep the `BZLogo`, label, copy, `ExternalLink`, `href`, `target`, and `rel` unchanged. Collapse the logo wrapper to one 52px Bali Zero container so spacing stays stable.

- [ ] **Step 4: Run the focused test and observe GREEN**

```bash
cd apps/mouth
npm test -- --run src/components/dashboard/__tests__/ZantaraPortalCard.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit the portal-card slice**

```bash
git add apps/mouth/src/components/dashboard/ZantaraPortalCard.tsx apps/mouth/src/components/dashboard/__tests__/ZantaraPortalCard.test.tsx
git commit -m "fix(mouth): simplify Kita Zantara portal card"
```

### Task 3: Warm the Kita-only day canvas

**Files:**

- Create: `apps/mouth/src/app/(workspace)/__tests__/kita-theme.contract.test.ts`
- Modify: `apps/mouth/src/app/globals.css`

**Interfaces:**

- Consumes: the existing product/theme selector and semantic surface aliases.
- Produces: Kita-scoped warm-white tokens inherited by the workspace shell and dashboard.

- [ ] **Step 1: Write the failing theme contract**

The test reads `globals.css`, extracts the exact Kita light block, and pins the approved warm-neutral values while proving the My block still exists independently:

```ts
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(join(__dirname, "..", "..", "globals.css"), "utf8");
const kita =
  css.match(
    /\[data-theme="operative-light"\]\[data-product="kita"\]\s*\{([\s\S]*?)\n\}/,
  )?.[1] ?? "";

describe("Kita day palette", () => {
  it("uses warm near-white canvas tokens inside the Kita scope", () => {
    expect(kita).toContain("--bz-base: #f8f6f2");
    expect(kita).toContain("--bz-card: #ffffff");
    expect(kita).toContain("--bz-card-hover: #fbf8f3");
    expect(kita).toContain("--nav-bg: rgba(255, 253, 249, 0.92)");
  });

  it("does not move the My palette into the Kita selector", () => {
    expect(css).toContain('[data-theme="operative-light"][data-product="my"]');
    expect(kita).not.toContain("--bz-product-heading-font: var(--font-serif)");
  });
});
```

- [ ] **Step 2: Run the theme contract and observe RED**

```bash
cd apps/mouth
npm test -- --run 'src/app/(workspace)/__tests__/kita-theme.contract.test.ts'
```

Expected: FAIL on the old cool values `#f5f6f8`, `#f8f9fb`, and white navigation background.

- [ ] **Step 3: Apply the minimal scoped palette**

Inside `[data-theme="operative-light"][data-product="kita"]`, set the canvas aliases to `#f8f6f2`, hover aliases to `#fbf8f3`, navigation to `rgba(255, 253, 249, 0.92)`, and Kita borders/shadows to low-alpha warm ink. Keep cards `#ffffff`, text colors, product density, My scope, and all dark themes unchanged.

- [ ] **Step 4: Run the theme contract and observe GREEN**

```bash
cd apps/mouth
npm test -- --run 'src/app/(workspace)/__tests__/kita-theme.contract.test.ts'
```

Expected: PASS.

- [ ] **Step 5: Commit the palette slice**

```bash
git add apps/mouth/src/app/globals.css 'apps/mouth/src/app/(workspace)/__tests__/kita-theme.contract.test.ts'
git commit -m "fix(mouth): warm Kita day-mode canvas"
```

### Task 4: Verify the definitive draft

**Files:**

- Modify only if an assertion needs the approved contract: `apps/mouth/e2e/bz-product-family.spec.ts`

**Interfaces:**

- Consumes: conflict-free branch and Tasks 2-3.
- Produces: current evidence for function, layout, accessibility, and PR readiness.

- [ ] **Step 1: Run focused and dashboard unit tests**

```bash
cd apps/mouth
npm test -- --run src/components/dashboard/__tests__/ZantaraPortalCard.test.tsx 'src/app/(workspace)/__tests__/kita-theme.contract.test.ts' 'src/app/(workspace)/dashboard/__tests__/page.test.tsx'
```

Expected: PASS.

- [ ] **Step 2: Run static gates**

```bash
cd apps/mouth
npm run typecheck
npm run lint
npm run build
```

Expected: all exit 0. Any pre-existing unrelated failure is compared against current main and reported explicitly.

- [ ] **Step 3: Run the authenticated dashboard/product-family browser suite**

```bash
cd apps/mouth
npm run test:e2e -- e2e/bz-product-family.spec.ts e2e/theme-toggle.spec.ts
```

Expected: the dashboard loads, sidebar navigation and theme control work, the Zantara portal link has the correct target, and no uncaught console/page errors occur.

- [ ] **Step 4: Capture and inspect desktop and mobile screenshots**

Use the user's established browser session at the same dashboard state and compare against the supplied reference state. Inspect spacing, overflow, contrast, focus, card hierarchy, and the absence of the duplicate lotus.

- [ ] **Step 5: Push the draft branch and verify the PR**

```bash
git push origin agent/air-m5/mouth/bz-ui-restyle
gh pr view 3460 --repo Bali-Zero/Teman2 --json state,isDraft,mergeable,statusCheckRollup,url
```

Expected: PR remains `OPEN` and `isDraft: true`; no merge or deployment is initiated.
