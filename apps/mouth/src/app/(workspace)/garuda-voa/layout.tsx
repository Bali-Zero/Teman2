/**
 * GARUDA VOA staff console — R19 typographic scope.
 *
 * SAETTA-VOA W-VOA-V3 (2026-09-13). The console is served on the kita host,
 * whose theme block points --font-serif/--font-sans at the workspace stack.
 * R19 asks for Fraunces headlines and Manrope body HERE without changing that
 * for the rest of the workspace, so the two variables are re-pointed on this
 * subtree's root element only.
 *
 * The faces themselves are NOT re-declared: app/portal/r19-fonts.css already
 * owns the two @font-face rules (self-hosted variable binaries, OFL 1.1) and
 * is imported, not copied — a second copy is exactly the drift class the
 * cicatrix record calls "the documented cure never reaches the twin file".
 */

import React from "react";
import "../../portal/r19-fonts.css";

const R19_TYPE = {
  "--font-serif": '"Fraunces", ui-serif, Georgia, serif',
  fontFamily:
    '"Manrope", var(--font-sans), ui-sans-serif, system-ui, sans-serif',
} as React.CSSProperties;

export default function GarudaVoaConsoleLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div data-r19-console="garuda-voa" style={R19_TYPE}>
      {children}
    </div>
  );
}
