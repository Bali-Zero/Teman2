import type { CSSProperties } from "react";

/**
 * The one ground a primary purchase action may take on the GARUDA VOA
 * public funnel — checkout, verdict and tracker. It mirrors the sanctioned
 * action ground the workspace staff console already declares
 * (`GateScreen.tsx`'s `GATE_ACTION_STYLE`, `--state-success` fill with
 * `--bz-base` text) rather than importing across the `(workspace)` /
 * `visa/voa` route-group boundary, so the public funnel keeps its own
 * dependency surface.
 *
 * It replaces `background: "var(--accent-funnel, #ff3344)"`, whose fallback
 * is a RED LITERAL: `semantic.css` resolves `--accent-funnel` to red for
 * `[data-funnel="visa"]`, and only `voa-r19.css`'s selector specificity has
 * ever held that red off this surface. A token that RESOLVES to red one CSS
 * rule away from the surface it colours is not a safe action ground — this
 * constant never resolves to red, on this surface or any other.
 */
export const VOA_PRIMARY_ACTION_STYLE: CSSProperties = {
  background: "var(--state-success)",
  color: "var(--bz-base)",
};
