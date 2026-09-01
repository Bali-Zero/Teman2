import { isGarudaVoaPublicEnabled } from "./flag";

/**
 * The team-lead flag (2026-08-25): measured on this branch, GARUDA_PUBLIC_ENABLED
 * appeared three times in apps/mouth, all prose (test descriptions + a docblock) —
 * no frontend code read it, so the funnel rendered in full for anyone with the URL
 * despite the mandate's "running in PRODUCTION behind the flag". This file pins the
 * fail-closed parsing (unset/"false"/typo = dark) that the layout gate relies on.
 *
 * Moved out of layout.test.tsx (2026-08-25, second review round): the Vercel build
 * failed with TS2344 because `layout.tsx` exported `isGarudaVoaPublicEnabled`
 * directly, which is outside Next's closed App Router layout export list — a build
 * that `tsc --noEmit` never catches, since the route-type shim it fails against
 * only exists at real `next build` time. See flag.ts's own docblock.
 */

describe("isGarudaVoaPublicEnabled — fail-closed parsing", () => {
  const original = process.env.GARUDA_PUBLIC_ENABLED;
  afterEach(() => {
    if (original === undefined) delete process.env.GARUDA_PUBLIC_ENABLED;
    else process.env.GARUDA_PUBLIC_ENABLED = original;
  });

  it.each([
    [undefined, false],
    ["", false],
    ["false", false],
    ["False", false],
    ["0", false],
    ["typo", false],
    ["true", true],
    ["TRUE", true],
    ["  true  ", true],
  ])("GARUDA_PUBLIC_ENABLED=%p -> %p", (value, expected) => {
    if (value === undefined) delete process.env.GARUDA_PUBLIC_ENABLED;
    else process.env.GARUDA_PUBLIC_ENABLED = value;
    expect(isGarudaVoaPublicEnabled()).toBe(expected);
  });
});
