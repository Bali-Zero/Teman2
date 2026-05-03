# @balizero/core

Bali Zero design system foundation. Tokens + primitives + shared components.

## Zero-to-themed-component in ≤20 lines (success criterion §10.6)

```tsx
import { BZLogo, ThemeProvider, useTheme } from "@balizero/core";

function ExampleCard() {
  const { setTheme } = useTheme();
  return (
    <article
      data-funnel="kbli"
      style={{
        background: "var(--surface-raised)",
        border: "1px solid var(--border-default)",
        color: "var(--text-primary)",
        padding: "var(--space-6)",
        borderRadius: "var(--radius-md)",
      }}
    >
      <BZLogo variant="mark" />
      <h2 style={{ color: "var(--accent-funnel-text)" }}>KBLI Navigator</h2>
      <button onClick={() => setTheme("light")}>Switch to light</button>
    </article>
  );
}
```

## Architecture

```
tokens/primitives.css   → raw values (colors, sizes, fonts)
tokens/semantic.css     → intent-named vars, funnel mapping
tokens/themes/*.css     → theme overrides (dark/light/editorial)
tailwind/theme.css      → Tailwind v4 @theme block
components/             → BZLogo, NavShell, ThemeProvider
effects/                → grain, shimmer
fonts/inter.ts          → next/font Inter loader
```

## Consumer wiring (once, in `app/layout.tsx` + `app/globals.css`)

See the design doc for the full three-coupled-changes procedure:

- `docs/superpowers/specs/2026-04-15-design-system-foundation-design.md` §5
- `docs/superpowers/plans/2026-04-15-design-system-foundation-plan.md` Step 0.3

## Rules

1. Components read **semantic** tokens (`--surface-base`, `--accent-funnel`). Never primitives directly.
2. Funnel-identity elements carry `data-funnel="visa|kbli|tax|property"`. Funnel-agnostic elements do not.
3. Inline text uses `--accent-funnel-text` (contrast-verified); shapes use `--accent-funnel`.
4. Three components only: `BZLogo`, `NavShell`, `ThemeProvider`. Promoting new shared components requires the Phase 4 waiver.
