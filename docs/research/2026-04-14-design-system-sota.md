# Design System Unificato Cross-App — Research & Architecture

> **Date:** 2026-04-14
> **Author:** Claude Code (Air)
> **Scope:** mouth, admin-dashboard, kbli-navigator, war-room, satellites (drive, mail, calendar, knowledge, web)
> **Status:** Research complete — ready for implementation decisions

---

## 1. Current State Audit

### 1.1 packages/core — The Ghost Library

`packages/core/` is **not a workspace package** (no `package.json`). It contains only 4 utility files:

```
packages/core/
└── utils/
    ├── index.ts        # re-exports 3 modules
    ├── date.ts         # formatDate, formatTime, formatRelative
    ├── currency.ts     # formatIDR, formatUSD, formatCurrency
    └── expiry.ts       # getExpiryStatus, isBirthdayToday
```

**Zero imports across the entire monorepo.** Every app implements its own date/currency formatters. The CLAUDE.md references to `packages/core/styles/bz-tokens.css` and `packages/core/components/BZLogo.tsx` are **stale** — these files don't exist.

### 1.2 Token Scatter — Where Design Lives Today

Design tokens are **distributed across individual app CSS files** with no single source of truth:

| File | Role | Lines | Token count |
|------|------|-------|-------------|
| `apps/kbli-navigator/styles/kbli-theme.css` | **De facto source of truth** — colors, shadows, radii | 136 | 40+ |
| `apps/mouth/src/app/globals.css` | Maps `kbli-theme` + adds legacy `--bz-*`, utility classes | 312 | 60+ |
| `apps/mouth/src/styles/kbli-theme.css` | Copy of kbli-navigator's theme (imported by mouth) | ~136 | 40+ |
| `apps/drive/src/app/globals.css` | Simplified subset | ~40 | 15+ |
| `apps/calendar/src/app/globals.css` | Minimal | 44 | 8 |
| `apps/mail/src/app/globals.css` | Minimal | ~40 | 8 |
| `apps/knowledge/src/app/globals.css` | Minimal | ~40 | 8 |
| `apps/web/src/app/globals.css` | Minimal | ~40 | 8 |

**Three token namespaces coexist in mouth's globals.css:**

1. `--kbli-*` — Current standard (via kbli-theme.css import)
2. `--bz-*` — Legacy Warm Depth tokens (partially overlapping values)
3. Semantic aliases: `--background`, `--foreground`, `--accent`, `--border` (map to `--kbli-*`)

**The semantic aliases are the right pattern** — components consume `var(--accent)` not `var(--kbli-accent)`. But only mouth defines them; other apps use raw values or their own CSS vars.

### 1.3 Token Inventory — Concrete Values

**Color Palette (canonical from kbli-theme.css):**

| Semantic | Token | Value | Usage |
|----------|-------|-------|-------|
| Brand accent | `--kbli-accent` | `#d4845a` | Primary CTA, links, highlights |
| Accent hover | `--kbli-accent-hover` | `#c07348` | Button hover states |
| Secondary accent | `--kbli-accent2` | `#8b9cf7` | Zantara AI, secondary actions |
| Background base | `--kbli-bg-base` | `#2b2b2b` | Page background |
| Background elevated | `--kbli-bg-elevated` | `#343434` | Cards, panels |
| Background surface | `--kbli-bg-surface` | `#3d3d3d` | Nested containers |
| Text primary | `--kbli-text-primary` | `#ececec` | Body text |
| Text secondary | `--kbli-text-secondary` | `#a8a8a8` | Labels, captions |
| Text muted | `--kbli-text-muted` | `#8a8a8a` | Placeholders |
| Border | `--kbli-border` | `rgba(255,255,255,0.08)` | Default borders |
| Success | `--success` / `--kbli-pma-open` | `#4db87a` / `#5ec490` | Status, PMA open |
| Warning | `--warning` / `--kbli-pma-restricted` | `#d4923a` / `#e8a849` | Alerts, PMA restricted |
| Error | `--error` / `--kbli-pma-closed` | `#d95f5a` / `#e8716c` | Errors, PMA closed |

Note: success/warning/error values **don't match exactly** between mouth (`#4db87a`) and kbli-navigator (`#5ec490`). This is a real inconsistency.

**Spacing:** Only `--bz-sidebar-width: 216px` and `--bz-header-height: 48px` are defined. No spacing scale.

**Radii (kbli-theme):** `sm: 6px`, `md: 10px`, `lg: 14px`, `xl: 20px`

**Shadows (kbli-theme):** 3 levels — `card`, `card-hover`, `glow`

**Typography:** Inter font family, hardcoded in CSS. No type scale tokens.

**Motion:** 7 keyframe animations in mouth's globals.css (aurora, pulse-glow, fade-in-up, holographic-spin, lotusPulse, liquidShift, progress-grow). No tokenized durations/easings.

### 1.4 Component Inventory — Duplication Matrix

| Component | mouth | drive | kbli-nav | web | knowledge | admin |
|-----------|-------|-------|----------|-----|-----------|-------|
| Button | CVA+Radix Slot | **Identical copy** | - | Custom | Radix Slot | - |
| Input | CVA+Radix | CVA+Radix | - | - | - | - |
| Dialog | Radix Dialog | Radix Dialog | - | - | - | - |
| Card | CVA | CVA | Custom | - | - | - |
| Badge | CVA | CVA | Custom (PMA) | Custom | - | - |
| Select | Radix Select | - | Custom | - | - | - |
| Table | HTML table | - | - | - | - | - |
| Tabs | Radix Tabs | - | - | - | - | - |
| Progress | Radix Progress | Radix Progress | - | - | - | - |
| ScrollArea | Radix ScrollArea | Radix ScrollArea | - | - | - | - |
| Toast | Sonner | - | - | - | - | - |
| Skeleton | Custom | - | - | - | - | Custom |
| ErrorBoundary | Custom | - | - | - | - | Custom |

**Key finding:** `mouth/src/components/ui/button.tsx` and `drive/src/components/ui/button.tsx` are **byte-for-byte identical** (63 lines). Same for input, card, dialog. This is pure duplication — no divergence, no customization.

### 1.5 Dependency Matrix

| Dep | mouth | drive | calendar | mail | knowledge | kbli-nav | web | admin |
|-----|-------|-------|----------|------|-----------|----------|-----|-------|
| React | 19.2.4 | 19.2.4 | 19.2.4 | 19.2.4 | 19.2.4 | ^19.0.0 | ? | ^18 |
| Tailwind | 4 | 3.4.17 | 4 | 4 | 3.4.14 | 4 | 4 | 3.x |
| Radix UI | 5 pkgs | 4 pkgs | - | - | slot only | - | - | - |
| lucide-react | 0.556.0 | 0.556.0 | latest | latest | latest | 0.475.0 | - | 0.363.0 |
| CVA | yes | yes | - | - | yes | - | - | yes |
| framer-motion | 12.36.0 | 12.23.26 | - | - | - | - | - | - |
| tailwind-merge | yes | yes | yes | yes | yes | yes | - | yes |

**Problems:**
- **React 18 vs 19**: admin-dashboard is on React 18 (can't consume React 19 components)
- **Tailwind 3 vs 4**: drive, knowledge, admin still on Tailwind 3 (incompatible config format)
- **lucide-react versions**: 4 different versions across apps (0.363 to 0.556)

### 1.6 Tailwind Config Patterns

**Two incompatible patterns exist:**

Pattern A — **HSL-based** (admin-dashboard, shadcn default):
```ts
colors: { primary: "hsl(var(--primary))" }
```

Pattern B — **Direct CSS vars** (mouth, drive, satellites):
```ts
colors: { background: "var(--background)" }
```

Neither extends a shared preset. Each app has its own minimal `tailwind.config.ts`.

### 1.7 What Doesn't Exist

- No Storybook
- No visual regression testing (manual screenshot audit via `audit-*.png` files)
- No a11y CI (no axe-core, no jest-axe)
- No shared Tailwind preset
- No shared component package
- No icon registry/wrapper
- No type scale tokens
- No spacing scale tokens
- No motion tokens
- No design documentation site

---

## 2. Target Architecture

### 2.1 Package Structure

```
packages/
  tokens/                    # NEW — Design token source of truth
    ├── package.json         # @nuzantara/tokens
    ├── src/
    │   ├── primitive/       # Raw values (colors, spacing, radii, shadows, motion)
    │   │   ├── colors.json
    │   │   ├── spacing.json
    │   │   ├── radii.json
    │   │   ├── shadows.json
    │   │   ├── typography.json
    │   │   └── motion.json
    │   └── semantic/        # Mapped tokens (background, foreground, accent, status)
    │       ├── light.json   # Future light theme
    │       └── dark.json    # Current default (dark-first)
    ├── sd.config.mjs        # Style Dictionary build config
    └── dist/                # Generated outputs
        ├── tokens.css       # CSS custom properties
        ├── tailwind-preset.js  # Tailwind v4 @theme compatible
        └── tokens.ts        # TypeScript constants

  ui/                        # NEW — Shared component library
    ├── package.json         # @nuzantara/ui
    ├── components.json      # shadcn CLI config
    ├── src/
    │   ├── primitives/      # Radix-based (button, input, dialog, select, badge, card, table, tabs, progress, scroll-area, skeleton, toast, label, popover, textarea)
    │   ├── patterns/        # Composed (form-field, data-table, status-badge, search-input)
    │   ├── styles/
    │   │   └── globals.css  # Imports @nuzantara/tokens/dist/tokens.css + Tailwind
    │   ├── lib/
    │   │   └── utils.ts     # cn() helper
    │   └── index.ts         # Barrel export
    └── tsconfig.json

  core/                      # EXISTING — Keep as utility library
    ├── package.json         # @nuzantara/core (NEW — add this)
    └── utils/               # Existing: date, currency, expiry
```

### 2.2 Dependency Graph

```
@nuzantara/tokens (no deps)
       │
       ▼
@nuzantara/ui (depends on tokens + radix + cva + tailwind-merge + lucide-react)
       │
       ▼
apps/* (depends on ui, may also import tokens directly for custom components)
```

### 2.3 Why NOT Merge Tokens into UI

Tokens are consumed by:
- `@nuzantara/ui` components (via CSS vars)
- App-level custom components (via CSS vars)
- Potential future: React Native, email templates, Figma sync

Keeping tokens separate allows non-React consumers and avoids coupling token changes to component releases.

---

## 3. Token Specification

### 3.1 Primitive Tokens (JSON, Style Dictionary format)

```json
{
  "bz": {
    "color": {
      "copper": { "$value": "#d4845a", "$type": "color" },
      "copper-hover": { "$value": "#c07348", "$type": "color" },
      "periwinkle": { "$value": "#8b9cf7", "$type": "color" },
      "amber": { "$value": "#e8a849", "$type": "color" },
      "green": { "$value": "#5ec490", "$type": "color" },
      "red": { "$value": "#e8716c", "$type": "color" },
      "blue": { "$value": "#6ba3e8", "$type": "color" },
      "gray": {
        "50": { "$value": "#ececec", "$type": "color" },
        "100": { "$value": "#d0d0d0", "$type": "color" },
        "300": { "$value": "#a8a8a8", "$type": "color" },
        "500": { "$value": "#8a8a8a", "$type": "color" },
        "700": { "$value": "#474747", "$type": "color" },
        "800": { "$value": "#3d3d3d", "$type": "color" },
        "850": { "$value": "#343434", "$type": "color" },
        "900": { "$value": "#2b2b2b", "$type": "color" },
        "950": { "$value": "#1a1a1a", "$type": "color" }
      }
    },
    "spacing": {
      "1": { "$value": "4px", "$type": "dimension" },
      "2": { "$value": "8px", "$type": "dimension" },
      "3": { "$value": "12px", "$type": "dimension" },
      "4": { "$value": "16px", "$type": "dimension" },
      "5": { "$value": "20px", "$type": "dimension" },
      "6": { "$value": "24px", "$type": "dimension" },
      "8": { "$value": "32px", "$type": "dimension" },
      "10": { "$value": "40px", "$type": "dimension" },
      "12": { "$value": "48px", "$type": "dimension" },
      "16": { "$value": "64px", "$type": "dimension" }
    },
    "radius": {
      "sm": { "$value": "6px", "$type": "dimension" },
      "md": { "$value": "10px", "$type": "dimension" },
      "lg": { "$value": "14px", "$type": "dimension" },
      "xl": { "$value": "20px", "$type": "dimension" },
      "full": { "$value": "9999px", "$type": "dimension" }
    },
    "shadow": {
      "card": { "$value": "0 1px 2px rgba(0,0,0,0.2), 0 4px 16px rgba(0,0,0,0.12)", "$type": "shadow" },
      "card-hover": { "$value": "0 4px 12px rgba(0,0,0,0.2), 0 16px 40px rgba(0,0,0,0.15)", "$type": "shadow" },
      "glow": { "$value": "0 0 20px rgba(212,132,90,0.15), 0 0 60px rgba(212,132,90,0.05)", "$type": "shadow" }
    },
    "font": {
      "family": { "$value": "'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif", "$type": "fontFamily" },
      "size": {
        "xs": { "$value": "0.75rem", "$type": "dimension" },
        "sm": { "$value": "0.875rem", "$type": "dimension" },
        "base": { "$value": "1rem", "$type": "dimension" },
        "lg": { "$value": "1.125rem", "$type": "dimension" },
        "xl": { "$value": "1.25rem", "$type": "dimension" },
        "2xl": { "$value": "1.5rem", "$type": "dimension" },
        "3xl": { "$value": "1.875rem", "$type": "dimension" }
      },
      "weight": {
        "normal": { "$value": "400", "$type": "fontWeight" },
        "medium": { "$value": "500", "$type": "fontWeight" },
        "semibold": { "$value": "600", "$type": "fontWeight" },
        "bold": { "$value": "700", "$type": "fontWeight" }
      }
    },
    "motion": {
      "duration": {
        "fast": { "$value": "150ms", "$type": "duration" },
        "normal": { "$value": "300ms", "$type": "duration" },
        "slow": { "$value": "500ms", "$type": "duration" }
      },
      "easing": {
        "default": { "$value": "cubic-bezier(0.4, 0, 0.2, 1)", "$type": "cubicBezier" },
        "out": { "$value": "cubic-bezier(0.16, 1, 0.3, 1)", "$type": "cubicBezier" },
        "in-out": { "$value": "cubic-bezier(0.4, 0, 0.6, 1)", "$type": "cubicBezier" }
      }
    }
  }
}
```

### 3.2 Semantic Tokens (dark theme — current default)

```json
{
  "sem": {
    "background": { "$value": "{bz.color.gray.900}", "$type": "color" },
    "background-elevated": { "$value": "{bz.color.gray.850}", "$type": "color" },
    "background-surface": { "$value": "{bz.color.gray.800}", "$type": "color" },
    "background-hover": { "$value": "{bz.color.gray.700}", "$type": "color" },
    "foreground": { "$value": "{bz.color.gray.50}", "$type": "color" },
    "foreground-secondary": { "$value": "{bz.color.gray.300}", "$type": "color" },
    "foreground-muted": { "$value": "{bz.color.gray.500}", "$type": "color" },
    "accent": { "$value": "{bz.color.copper}", "$type": "color" },
    "accent-hover": { "$value": "{bz.color.copper-hover}", "$type": "color" },
    "accent-foreground": { "$value": "#ffffff", "$type": "color" },
    "border": { "$value": "rgba(255,255,255,0.08)", "$type": "color" },
    "border-hover": { "$value": "rgba(255,255,255,0.15)", "$type": "color" },
    "success": { "$value": "{bz.color.green}", "$type": "color" },
    "warning": { "$value": "{bz.color.amber}", "$type": "color" },
    "error": { "$value": "{bz.color.red}", "$type": "color" }
  }
}
```

### 3.3 Output Examples

**CSS Custom Properties (generated):**
```css
:root {
  --bz-color-copper: #d4845a;
  --bz-radius-md: 10px;
  --bz-shadow-card: 0 1px 2px rgba(0,0,0,0.2), 0 4px 16px rgba(0,0,0,0.12);
  --bz-motion-duration-normal: 300ms;
  --sem-background: var(--bz-color-gray-900);
  --sem-accent: var(--bz-color-copper);
  /* ... */
}
```

**Tailwind v4 @theme (generated or manual):**
```css
@theme {
  --color-accent: var(--sem-accent);
  --color-accent-hover: var(--sem-accent-hover);
  --color-background: var(--sem-background);
  --color-foreground: var(--sem-foreground);
  --color-success: var(--sem-success);
  --color-warning: var(--sem-warning);
  --color-error: var(--sem-error);
  --radius-sm: var(--bz-radius-sm);
  --radius-md: var(--bz-radius-md);
  --radius-lg: var(--bz-radius-lg);
  --shadow-card: var(--bz-shadow-card);
}
```

**TypeScript (generated):**
```typescript
export const tokens = {
  color: {
    copper: '#d4845a',
    copperHover: '#c07348',
    // ...
  },
  radius: { sm: '6px', md: '10px', lg: '14px', xl: '20px' },
  // ...
} as const;
```

---

## 4. Component Roadmap — Prioritized by ROI

### Tier 1 — Immediate (Week 1-2)
Move from mouth to @nuzantara/ui. These are already shadcn/ui pattern, zero customization needed:

| # | Component | Consumers | Why first |
|---|-----------|-----------|-----------|
| 1 | Button | mouth, drive (identical), knowledge | Byte-for-byte duplicate exists |
| 2 | Input | mouth, drive (identical) | Same — pure duplicate |
| 3 | Card | mouth, drive | Same pattern |
| 4 | Badge | mouth, drive, kbli-nav (needs variant merge) | 3 implementations |
| 5 | Dialog | mouth, drive (identical) | Same — pure duplicate |

### Tier 2 — High value (Week 2-3)

| # | Component | Why |
|---|-----------|-----|
| 6 | Select | Used in all form-heavy apps (CRM, admin, portal) |
| 7 | Table | CRM clients, KBLI listing, admin — needs TanStack Table wrapper |
| 8 | Skeleton | 2 implementations (mouth, admin) |
| 9 | Label | Form primitive |
| 10 | Textarea + AutoResize | Chat, forms |

### Tier 3 — Complete primitive set (Week 3-4)

| # | Component | Why |
|---|-----------|-----|
| 11 | Tabs | Dashboard sections |
| 12 | Progress | Upload, processing states |
| 13 | ScrollArea | Scrollable panels |
| 14 | Popover | Context menus, tooltips |
| 15 | Toast (Sonner wrapper) | Notification system |
| 16 | Alert | Status messages |
| 17 | ErrorBoundary | 2 implementations |

### Tier 4 — Composed patterns (Week 4+)

| # | Pattern | Composition |
|---|---------|-------------|
| 18 | FormField | Label + Input/Select/Textarea + error message (React Hook Form + Zod) |
| 19 | StatusBadge | Badge + semantic color from tokens (PMA, risk, status) |
| 20 | DataTable | Table + TanStack Table + sort/filter/pagination |
| 21 | SearchInput | Input + Search icon + clear button + debounce |
| 22 | ConfirmDialog | Dialog + title + message + cancel/confirm buttons |
| 23 | EmptyState | Icon + title + description + optional action |
| 24 | LoadingState | Skeleton variants for cards, tables, text |
| 25 | StatCard | Card with label + value + trend indicator |

---

## 5. Migration Plan Per-App

### 5.1 Strategy: Strangler Fig

Each app migrates component-by-component. Old local component is **deleted**, not kept alongside.

**Order (least risk first):**

### Phase 1: drive (lowest risk, highest duplication)

Components are byte-for-byte copies of mouth. Migration is mechanical:
1. Add `@nuzantara/ui` dependency
2. Replace imports: `@/components/ui/button` -> `@nuzantara/ui/button`
3. Delete `apps/drive/src/components/ui/` (7 files)
4. Update `@/lib/utils.ts` to re-export from `@nuzantara/ui/lib/utils`
5. Verify: `pnpm build` in drive app

**Risk:** Near zero. Components are identical.

### Phase 2: knowledge (minimal surface)

Only 2 components (AuthGateClient, Button):
1. Replace Button import
2. Keep AuthGateClient as app-specific

### Phase 3: admin-dashboard

**Blocker:** React 18. Must upgrade to React 19 first.
1. Upgrade React 18 -> 19, Next.js to latest
2. Upgrade Tailwind 3 -> 4
3. Replace local primitives.tsx with @nuzantara/ui imports
4. Migrate ErrorBoundary, LoadingSkeleton

### Phase 4: kbli-navigator

Custom components (KBLISearch, PMABadge, RiskBadge) stay app-specific but consume @nuzantara/ui primitives internally:
1. PMABadge wraps `<Badge variant="pma-open|restricted|closed">`
2. KBLICard wraps `<Card>` with KBLI-specific layout
3. Import semantic tokens from @nuzantara/tokens for status colors

### Phase 5: mouth (largest, last)

1. Move `apps/mouth/src/components/ui/` to `packages/ui/src/primitives/` (this IS the source)
2. Update all 255 component imports
3. Keep domain components (chat/, dashboard/, maps/) in mouth
4. Utility classes (glass-panel-deep, crystal-stat-card) move to `@nuzantara/ui/styles/utilities.css`

### Phase 6: satellites (mail, calendar, web)

These have no shared components — they just need the token CSS import for consistent theming:
1. Replace app-specific `globals.css` token definitions with `@import '@nuzantara/tokens/dist/tokens.css'`
2. Map semantic vars if needed

---

## 6. Storybook Setup

### 6.1 Configuration

Install in `packages/ui/`:

```bash
cd packages/ui
npx storybook@latest init --framework @storybook/nextjs-vite
```

```typescript
// packages/ui/.storybook/main.ts
import type { StorybookConfig } from '@storybook/nextjs-vite';

const config: StorybookConfig = {
  stories: ['../src/**/*.stories.@(ts|tsx)'],
  framework: '@storybook/nextjs-vite',
  addons: [
    '@storybook/addon-a11y',
    '@storybook/addon-interactions',
    '@storybook/addon-docs',
  ],
  staticDirs: ['../public'],
};
export default config;
```

```typescript
// packages/ui/.storybook/preview.ts
import type { Preview } from '@storybook/react';
import '../src/styles/globals.css';

const preview: Preview = {
  parameters: {
    backgrounds: {
      default: 'dark',
      values: [
        { name: 'dark', value: '#2b2b2b' },
        { name: 'elevated', value: '#343434' },
      ],
    },
    a11y: {
      config: {
        rules: [{ id: 'color-contrast', enabled: true }],
      },
    },
  },
};
export default preview;
```

### 6.2 First 5 Stories

**Button.stories.tsx:**
```tsx
import type { Meta, StoryObj } from '@storybook/react';
import { Button } from '../primitives/button';
import { Search, Plus, Trash2 } from 'lucide-react';

const meta: Meta<typeof Button> = {
  title: 'Primitives/Button',
  component: Button,
  tags: ['autodocs'],
  argTypes: {
    variant: { control: 'select', options: ['default', 'destructive', 'outline', 'secondary', 'ghost', 'link'] },
    size: { control: 'select', options: ['default', 'sm', 'lg', 'icon'] },
    disabled: { control: 'boolean' },
  },
};
export default meta;

type Story = StoryObj<typeof Button>;

export const Default: Story = { args: { children: 'Button' } };
export const Destructive: Story = { args: { variant: 'destructive', children: 'Delete' } };
export const WithIcon: Story = { args: { children: <><Plus /> New Client</> } };
export const IconOnly: Story = { args: { variant: 'outline', size: 'icon', children: <Search />, 'aria-label': 'Search' } };
export const AllVariants: Story = {
  render: () => (
    <div className="flex gap-3 flex-wrap">
      <Button>Default</Button>
      <Button variant="destructive">Destructive</Button>
      <Button variant="outline">Outline</Button>
      <Button variant="secondary">Secondary</Button>
      <Button variant="ghost">Ghost</Button>
      <Button variant="link">Link</Button>
    </div>
  ),
};
```

**Badge, Input, Card, Dialog** — same pattern with variant exploration and a11y testing.

### 6.3 Hosting

Add to `pnpm scripts` in packages/ui:
```json
"storybook": "storybook dev -p 6006",
"build-storybook": "storybook build"
```

**Option A:** Local only (`pnpm storybook` during dev). Zero cost.
**Option B:** Deploy to Vercel as `design.balizero.com`. Adds a subdomain but provides team visibility.

Recommendation: Start with Option A. Add Vercel deploy when team needs it.

---

## 7. Visual Regression Strategy

### 7.1 Recommendation: Playwright Screenshots (Free Tier)

The team already does manual screenshot audits. Automate the same workflow:

```typescript
// packages/ui/tests/visual/button.spec.ts
import { test, expect } from '@playwright/test';

test('button variants', async ({ page }) => {
  await page.goto('http://localhost:6006/iframe.html?id=primitives-button--all-variants');
  await expect(page).toHaveScreenshot('button-variants.png', {
    maxDiffPixelRatio: 0.01,
  });
});
```

**Baseline management:** Screenshots stored in `packages/ui/tests/visual/__screenshots__/`, committed to git. CI compares against baseline.

### 7.2 Cost Analysis

| Tool | Monthly cost | Setup effort | Review UX |
|------|-------------|--------------|-----------|
| Playwright screenshots | $0 | Low (already in stack) | Git diff (no UI) |
| Lost Pixel OSS | $0 | Medium | Web dashboard (self-hosted) |
| Chromatic free | $0 (5K snapshots) | Low (zero-config) | Excellent web UI |
| Chromatic Starter | $149/mo | Zero | Excellent |

**Recommendation:** Start with Playwright screenshots. If the 5K/month free tier of Chromatic fits (roughly 25 components x 6 variants x ~30 PRs/month = 4,500 snapshots), use Chromatic for the review UX.

---

## 8. Accessibility Baseline

### 8.1 WCAG 2.2 AA Checklist — Top 10 Components

| Component | Focus visible | Keyboard nav | ARIA roles | Touch target | Contrast |
|-----------|--------------|--------------|------------|--------------|----------|
| Button | `focus-visible:outline` (exists) | Native `<button>` | Implicit | Add `min-h-11 min-w-11` for 44px | Verify copper on dark |
| Input | Missing visible ring | Native | Needs `aria-invalid`, `aria-describedby` | OK (full width) | Border contrast low (0.08 alpha) |
| Dialog | Radix handles | Radix: Escape, Tab trap | Radix: `role=dialog`, `aria-modal` | N/A | OK |
| Select | Radix handles | Radix: Arrow/Enter/Escape | Radix: `listbox`, `option` | Check trigger height | OK |
| Badge | N/A (non-interactive) | N/A | Add `role="status"` for dynamic | N/A | Verify per variant |
| Card | If clickable: needs focus | If clickable: Enter/Space | If clickable: `role="link"` or `role="button"` | Min 44px if clickable | OK |
| Table | N/A | Tab through cells | `<th scope>`, `<caption>` | N/A | Check row borders |
| Tabs | Radix handles | Radix: Arrow keys | Radix: `tablist`, `tab`, `tabpanel` | Min 44px tab height | OK |
| Toast | Auto-dismiss concern | Escape to dismiss | `role="status"`, `aria-live="polite"` | Close button 44px | OK |
| Skeleton | N/A | N/A | `aria-busy="true"` on parent, `aria-hidden` on skeleton | N/A | N/A |

### 8.2 Automated Testing Setup

```typescript
// packages/ui/tests/a11y/primitives.spec.ts
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const components = ['button', 'input', 'card', 'badge', 'dialog'];

for (const component of components) {
  test(`${component} has no a11y violations`, async ({ page }) => {
    await page.goto(`http://localhost:6006/iframe.html?id=primitives-${component}--default`);
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag22aa'])
      .analyze();
    expect(results.violations).toEqual([]);
  });
}
```

### 8.3 Immediate Fixes Required

1. **Button icon-only:** Add mandatory `aria-label` prop when `size="icon"` (currently not enforced)
2. **Input border contrast:** `rgba(255,255,255,0.08)` is ~1.3:1 ratio — below 3:1 minimum. Increase to `rgba(255,255,255,0.15)` minimum
3. **Badge status:** PMA badges should have `role="status"` for screen readers
4. **Touch targets:** Button `icon` variant is 36x36px — below WCAG 2.2's 44x44px target. Change to `h-11 w-11`

---

## 9. Anti-Patterns to Avoid

### 9.1 Token Anti-Patterns

| Anti-pattern | Why it's bad | What to do instead |
|-------------|-------------|-------------------|
| Hardcoded hex in components | Theme changes require grep-and-replace | Always use `var(--sem-*)` |
| Multiple token namespaces (`--bz-*`, `--kbli-*`, `--anthracite-*`) | Confusion about which is canonical | Single namespace: `--bz-*` (primitive) + `--sem-*` (semantic) |
| Tailwind `hsl(var(--primary))` alongside `var(--accent)` | Two competing patterns | Standardize on direct CSS vars with Tailwind v4 `@theme` |
| Inline `rgba()` with hardcoded values | Not theme-aware | Use token with opacity: `color: rgb(from var(--accent) r g b / 0.3)` |

### 9.2 Component Anti-Patterns

| Anti-pattern | Why it's bad | What to do instead |
|-------------|-------------|-------------------|
| Copy-pasting shadcn components per app | Maintenance n-squared, drift over time | Single source in `@nuzantara/ui` |
| Button with 20+ props | Untestable, unusable | Max 6-8 props. Use composition for complex cases |
| `className` string concatenation | Merge conflicts, specificity issues | Always `cn()` (tailwind-merge) |
| Importing full lucide-react barrel | Bundle bloat | Named imports: `import { Search } from 'lucide-react'` (tree-shakes) |
| Wrapping Radix in custom state management | Fighting the library | Use Radix's controlled/uncontrolled patterns |

### 9.3 Architecture Anti-Patterns

| Anti-pattern | Why it's bad | What to do instead |
|-------------|-------------|-------------------|
| Big-bang rewrite of all apps | Risk, downtime, regression | Strangler fig, one app at a time |
| Design system without consumers | Over-engineering | Extract from mouth (proven), not from scratch |
| Storybook with 200 stories day 1 | Unmaintained after initial push | Start with 5 primitives, grow with usage |
| Mandating Chromatic before product-market fit | $149+/mo for uncertain ROI | Start with Playwright screenshots (free) |

---

## 10. Appendix: Scaffold — packages/ui/button

### File Structure

```
packages/ui/
├── package.json
├── tsconfig.json
├── src/
│   ├── primitives/
│   │   └── button.tsx
│   ├── lib/
│   │   └── utils.ts
│   ├── styles/
│   │   └── globals.css
│   └── index.ts
```

### package.json

```json
{
  "name": "@nuzantara/ui",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "exports": {
    ".": "./src/index.ts",
    "./button": "./src/primitives/button.tsx",
    "./styles": "./src/styles/globals.css",
    "./lib/utils": "./src/lib/utils.ts"
  },
  "sideEffects": ["**/*.css"],
  "peerDependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "dependencies": {
    "@radix-ui/react-slot": "^1.2.3",
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.1",
    "tailwind-merge": "^3.0.2"
  }
}
```

### src/primitives/button.tsx

```tsx
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--sem-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--sem-background)] disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-[var(--sem-accent)] text-[var(--sem-accent-foreground)] shadow hover:bg-[var(--sem-accent-hover)]",
        destructive:
          "bg-[var(--sem-error)] text-[var(--sem-foreground)] shadow-sm hover:bg-[var(--sem-error)]/90",
        outline:
          "border border-[var(--sem-border)] bg-transparent shadow-sm hover:bg-[var(--sem-background-elevated)] hover:text-[var(--sem-foreground)]",
        secondary:
          "bg-[var(--sem-background-elevated)] text-[var(--sem-foreground)] shadow-sm hover:bg-[var(--sem-background-surface)]",
        ghost:
          "hover:bg-[var(--sem-background-elevated)] hover:text-[var(--sem-foreground)]",
        link: "text-[var(--sem-accent)] underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-10 rounded-md px-8",
        icon: "h-11 w-11",  // 44px touch target (WCAG 2.2)
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, type = "button", ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        type={asChild ? undefined : type}
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
```

### src/lib/utils.ts

```typescript
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

### src/styles/globals.css

```css
@import 'tailwindcss';
@import '@nuzantara/tokens/dist/tokens.css';

@theme {
  --color-accent: var(--sem-accent);
  --color-accent-hover: var(--sem-accent-hover);
  --color-background: var(--sem-background);
  --color-foreground: var(--sem-foreground);
  --color-success: var(--sem-success);
  --color-warning: var(--sem-warning);
  --color-error: var(--sem-error);
  --radius-sm: var(--bz-radius-sm);
  --radius-md: var(--bz-radius-md);
  --radius-lg: var(--bz-radius-lg);
}
```

### src/index.ts

```typescript
export { Button, buttonVariants, type ButtonProps } from './primitives/button';
```

### Key Changes from mouth's Current Button

1. **Focus ring**: Added `focus-visible:ring-2` + `ring-offset` (missing in current)
2. **Semantic tokens**: `var(--sem-*)` instead of `var(--accent)` (explicit namespace)
3. **Icon size**: `h-11 w-11` (44px) instead of `h-9 w-9` (36px) for WCAG 2.2 touch target
4. **Secondary variant**: Uses `background-elevated`/`background-surface` (more predictable than `background-secondary`)

---

## 11. Implementation Priorities — Decision Matrix

| Action | Effort | Impact | Dependencies | Recommended |
|--------|--------|--------|--------------|-------------|
| Create @nuzantara/tokens package | S | Foundation for everything | None | **Do first** |
| Move mouth UI to @nuzantara/ui | M | Eliminates all duplication | tokens | **Do second** |
| Migrate drive (delete duplicates) | XS | Immediate dedup win | ui package | **Do with ui** |
| Setup Storybook (5 stories) | S | Component discovery | ui package | Week 2 |
| Playwright a11y tests | S | Catch violations in CI | Storybook | Week 2 |
| Migrate admin-dashboard | M | React 18->19 upgrade needed | ui package | Week 3-4 |
| Migrate kbli-navigator | S | Custom components stay | tokens | Week 3 |
| Migrate satellites | XS | Just CSS import | tokens | Week 3 |
| Visual regression (Playwright) | S | Automated screenshot diff | Storybook | Week 4 |
| Style Dictionary build pipeline | M | Formal token management | tokens defined | Week 4+ |

**Sizing:** XS = hours, S = 1-2 days, M = 3-5 days

---

## 12. Tools & Versions Reference

| Tool | Version (April 2026) | Role |
|------|---------------------|------|
| Style Dictionary | 5.4.0 | Token build pipeline |
| Tailwind CSS | 4.2.2 | CSS framework (keep) |
| Storybook | 10.3.5 | Component workshop |
| @storybook/nextjs-vite | 10.x | Storybook framework adapter |
| @storybook/addon-a11y | 10.x | Accessibility testing |
| @axe-core/playwright | latest | E2E a11y testing |
| Radix UI | latest | Headless primitives (keep) |
| shadcn/ui CLI | latest | Component scaffolding |
| CVA (class-variance-authority) | 0.7.x | Variant management (keep) |
| lucide-react | 0.562+ | Icons (keep, standardize version) |
| motion (ex framer-motion) | 12.38.0 | Animation (keep in mouth) |
| React Hook Form + Zod | 7.72 + 3.x | Form validation |
| Lost Pixel | OSS | Visual regression (future) |

---

*Research complete. Ready for Zero's decision on implementation order and scope.*
