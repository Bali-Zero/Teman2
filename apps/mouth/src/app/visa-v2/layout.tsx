import type { Metadata } from "next";

/**
 * Visa Oracle v2 — prototype route (Track C PR C1, foundation only).
 *
 * noindex/nofollow: this is a foundation prototype (design tokens + mock
 * interview model + Q0), not the live public funnel — see
 * docs/plans/2026-07-17-visa-oracle-v2/track-c-experience-spec.md.
 *
 * RELOCATED from `/visa/v2` to `/visa-v2` (Codex sol review F6, 2026-07-17):
 * this route previously lived inside the `/visa` subtree and silently
 * inherited the parent `VisaLayout`'s `<SessionInit funnel="visa" />`
 * (apps/mouth/src/app/visa/layout.tsx), which POSTs /api/funnel/session/touch
 * on every visit — violating this PR's documented "no API calls" invariant
 * (track-c-experience-spec.md §Acceptance criteria). Living as a sibling
 * top-level segment, `/visa-v2` inherits ONLY the root layout
 * (apps/mouth/src/app/layout.tsx), which was verified to mount no
 * SessionInit-equivalent component — see the F6 verification note in the
 * PR body / commit message.
 */
export const metadata: Metadata = {
  title: "Visa Oracle v2 — prototype",
  robots: { index: false, follow: false },
};

export default function VisaOracleV2Layout({
  children,
}: {
  children: React.ReactNode;
}) {
  // F3 (Codex sol review): deliberate local theme pin. The root layout's
  // <ThemeProvider defaultTheme="editorial"> means this route would
  // otherwise inherit the dark "editorial" theme — but this prototype's
  // lane/eligibility colors (visa-oracle-v2.css) are tuned and
  // AA-verified against the LIGHT theme (design doc §3: light is the
  // Jakarta-demo default). Pinning `data-theme="light"` here makes the
  // core semantic tokens (--surface-raised, --text-primary, etc.) resolve
  // through [data-theme="light"] (packages/core/tokens/themes/light.css)
  // under this subtree BY CONSTRUCTION, independent of whatever theme the
  // rest of the app is in. A local light/dark toggle is PR C2 scope; the
  // `[data-theme="dark"] .vo2` override block in visa-oracle-v2.css is
  // kept ready for that (see the css file's DELIBERATE LOCAL THEME PIN
  // comment for the post-pin contrast re-verification numbers).
  return (
    <div className="vo2" data-theme="light">
      {children}
    </div>
  );
}
