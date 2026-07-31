# Kita Dashboard Warm Refinement

**Date:** 2026-07-31
**Status:** Approved from the operator's explicit conditional brief

## Objective

Refine the Kita dashboard without changing its information architecture:

- remove the redundant Zantara lotus mark beside the `Zantara AI` label;
- retain the portal row because it is an active external link to
  `https://zantara.balizero.com/chat`;
- make Kita's default day-mode canvas warmer while keeping it visibly white;
- keep My and Prime product palettes unchanged;
- verify the dashboard's core navigation and controls before handing back the
  draft PR.

## Visual direction

Kita remains the compact operational member of the Bali Zero product family.
Its canvas moves from cool mineral gray to near-white warm porcelain. Cards
remain white so the hierarchy stays crisp. Borders and hover surfaces inherit
the same low-chroma warm bias; typography, copper accents, radii, density, and
layout do not change.

The `Zantara AI` portal card keeps the Bali Zero logo and external-link cue. The
small overlaid Zantara lotus is removed because the adjacent label already
identifies the destination and the duplicate mark creates visual noise.

## Functional contract

- The full portal card remains keyboard-focusable and opens the existing
  Zantara chat URL in a new tab with `noopener noreferrer`.
- Existing dashboard links, refresh actions, notification controls, theme
  toggle, sidebar navigation, and Zantara assistant toggle remain unchanged.
- The palette override stays under
  `[data-theme="operative-light"][data-product="kita"]`.

## Verification

- Add a user-visible component test proving the portal card retains its link
  while the redundant Zantara image is absent.
- Add a scoped theme-contract test proving Kita receives the warm day palette
  without changing My or operative-dark.
- Run targeted unit tests, TypeScript checks, production build, and the
  dashboard/product-family browser suite.
- Inspect the rendered desktop and mobile dashboard and report any unrelated
  broken behavior instead of silently expanding scope.
