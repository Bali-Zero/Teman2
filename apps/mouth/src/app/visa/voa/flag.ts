/**
 * GARUDA VOA public-funnel feature flag — kept OUT of layout.tsx on purpose.
 *
 * Next's App Router allows only a closed set of exports from a layout.tsx
 * (`default`, `metadata`, `dynamic`, `generateStaticParams`,
 * `generateViewport`, ...); a route-type shim generated at `next build`
 * time (`.next/types/app/**\/layout.ts`) reduces anything else to
 * `{ [x: string]: never }` and fails the build with a TS2344 that `tsc
 * --noEmit` alone never sees, because that shim doesn't exist until a real
 * `next build` runs. Measured: `export function isGarudaVoaPublicEnabled()`
 * inside `layout.tsx` passed `tsc --noEmit` clean and failed the Vercel
 * build. Living here, this file has no export-list restriction.
 *
 * Reads `process.env.GARUDA_PUBLIC_ENABLED` at CALL time, not at module
 * load — do not hoist this to a module-level `const`. Doing so would
 * capture the value once per server process and quietly reintroduce the
 * build-time-baking problem that `export const dynamic = "force-dynamic"`
 * on the layout exists to prevent.
 *
 * Fails CLOSED: only the literal string "true" (case-insensitively) opens
 * the route — unset, empty, "false", or a typo all mean dark. A bare
 * truthiness check would get this backwards (`Boolean("false")` is `true`),
 * and an unset Vercel env var must never be the thing that opens a funnel
 * by accident.
 */
export function isGarudaVoaPublicEnabled(): boolean {
  return (
    (process.env.GARUDA_PUBLIC_ENABLED ?? "").trim().toLowerCase() === "true"
  );
}

/**
 * GARUDA VOA payment switch. Card payment (Xendit) is awaiting provider approval;
 * production still runs a sandbox key. Unset or anything but "true" means payments are
 * NOT live — the checkout step must show the "payment activating" panel instead of
 * creating a real order. Flip this together with the backend's own
 * `GARUDA_PAYMENTS_LIVE` on Fly and a Xendit production key — a Vercel env change needs a
 * redeploy to take effect (same call-time-read, fail-closed rule as
 * `isGarudaVoaPublicEnabled` above; see that function's docblock for why).
 */
export function isGarudaPaymentsLive(): boolean {
  return (
    (process.env.GARUDA_PAYMENTS_LIVE ?? "").trim().toLowerCase() === "true"
  );
}
