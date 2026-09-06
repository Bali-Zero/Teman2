# Website design-system API

Contract: `website-v1`

Owner: lane `01-design-system`

The R19 website uses a deliberately small set of server-compatible React primitives. They import one CSS Module, carry their own scoped semantic tokens, and do not require a global stylesheet or a client boundary.

Use the barrel at `src/components/ui/index.ts` through a relative import. This seed has no `@/*` TypeScript alias.

```tsx
import {
  ButtonLink,
  Card,
  Container,
  SectionHeading,
  TextLink,
} from "../../components/ui";
```

## Public components

- `Container`: `as?: "div" | "section" | "main"`, `width?: "content" | "wide"`, and native HTML/data/ARIA attributes.
- `SectionHeading`: `title`, optional `eyebrow`, `description`, `id`, `level?: 2 | 3`, and `align?: "start" | "split"`. The `id` belongs to the heading, so a surrounding section can use it in `aria-labelledby`.
- `Button`: native button attributes plus `variant?: "primary" | "secondary" | "copper"`. Consumers must choose the native `type` explicitly when form behavior matters.
- `ButtonLink`: native anchor attributes with required `href` and the same variants as `Button`.
- `TextLink`: native anchor attributes with required `href` and `tone?: "copper" | "ink"`.
- `Card`: `as?: "article" | "div"`, `tone?: "paper" | "quiet"`, and native HTML/data/ARIA attributes. A card does not become interactive; put a native link or button inside it.

`Field`, chip, tag, icon-button, dialog, and navigation abstractions are intentionally absent. No second concrete consumer justified those APIs at the time of this contract.

## Token scope

Every primitive root receives the local `.theme` class from `src/styles/design-system.module.css`. Token names use the `--bz-` prefix and cover:

- paper, raised paper, ink, muted ink, green, copper, borders, and white;
- system sans and editorial serif stacks;
- label, body, lead, and fluid heading sizes;
- an eight-step spacing scale, two container widths, control/card radii, and one restrained card shadow.

This local scope prevents collisions with the imported R19 globals while consumers migrate. The coordinator may later promote the same values to the application shell only through a reviewed shared-file patch.

## Accessibility contract

- Components retain native elements and attributes.
- Buttons and links have a minimum 48px block size where they use the button treatment.
- Focus rings remain visible on paper and filled green/copper controls.
- `SectionHeading` preserves the requested heading level rather than inferring hierarchy.
- Responsive behavior changes layout only; reading and keyboard order remain unchanged.
