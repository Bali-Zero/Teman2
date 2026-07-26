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
4. Shared components require a Phase 4 waiver to be promoted here. Current count: 21 (`BZLogo`, `NavShell`, `ThemeProvider`, `ProgressRing`, `DeadlineBadge`, `TrustBand`, `CTAHandoff`, `FunnelFrame`, `MatterCard`, `CommandPalette`, `Money`, `ListPageHeader`, `SearchBox`, `FilterBar`, `StatChips`, `SubNav`, `ContextPanel`, `WhatsAppFAB`, `FactBadge`, `SystemPulse`, `ComplianceRadar`). FactBadge (WS1, 2026-07-21): promoted under the Phase 4 waiver — rationale: one verifiable-facts badge (KBLI codes, citations, regulation codes) shared by every surface; semantic tokens only, funnel-agnostic. Granted with the WS1 merge. SystemPulse (WS2, 2026-07-22): promotion requested under Phase 4 (rationale: one live-stack service panel of status/latency rows shared by every workspace surface; semantic state tokens only, funnel-agnostic); waiver effective on operator merge (WS1/FactBadge precedent). ComplianceRadar (WS2, 2026-07-22): promotion requested under Phase 4 (rationale: one severity-ranked compliance alert panel shared by every workspace surface; semantic state tokens only, funnel-agnostic); waiver effective on operator merge (WS1/FactBadge precedent).
