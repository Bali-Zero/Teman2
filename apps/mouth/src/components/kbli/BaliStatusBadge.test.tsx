// Ward-round 2026-08-07 (kbli-client-facing-content-defects): the `reason`
// behind a Bali verdict reached the client ONLY via the `title` attribute —
// a hover tooltip that never fires on mobile/touch and that most screen
// readers do not reliably announce. For a badge whose whole point is "why
// is this closed", the reason is not decoration — it needs to render as
// visible text, not just live in an attribute nobody on a phone will see.

import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { BaliStatusBadge } from "./BaliStatusBadge";

describe("BaliStatusBadge — reason visibility (no longer hover-only)", () => {
  it("renders the reason as visible text, not just a title attribute", () => {
    render(
      <BaliStatusBadge
        status="CHIUSO_PMA_NO_BESAR"
        reason="OSS has no Usaha Besar scale row -> reserved for UMKM"
        confidence="HIGH"
      />,
    );
    // Visible in the DOM as text content (findable without simulating hover).
    expect(
      screen.getByText(/OSS has no Usaha Besar scale row/),
    ).toBeInTheDocument();
  });

  it("still carries the reason in `title` too (desktop hover stays a free extra)", () => {
    render(
      <BaliStatusBadge
        status="CHIUSO_MORATORIA_BALI"
        reason="Blocked under the 13 May 2026 provincial moratorium"
      />,
    );
    const pill = screen.getByTitle(
      "Blocked under the 13 May 2026 provincial moratorium",
    );
    expect(pill).toBeInTheDocument();
  });

  it("innocence: no reason given renders the pill with no stray empty caption", () => {
    const { container } = render(
      <BaliStatusBadge status="OK_or_HIGHER_RISK" />,
    );
    expect(screen.getByText("Registrable in Bali")).toBeInTheDocument();
    // No caption span rendered at all when `reason` is absent.
    expect(container.querySelector("[title]")).toBeNull();
  });

  it("innocence: an unknown status still renders nothing (defense-in-depth untouched)", () => {
    const { container } = render(
      <BaliStatusBadge status="SOME_FUTURE_STATUS" reason="whatever" />,
    );
    expect(container.firstChild).toBeNull();
  });
});
