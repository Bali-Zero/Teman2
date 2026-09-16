// Ward-round 2026-08-07 (kbli-client-facing-content-defects): the `reason`
// behind a Bali verdict reached the client ONLY via the `title` attribute —
// a hover tooltip that never fires on mobile/touch and that most screen
// readers do not reliably announce. For a badge whose whole point is "why
// is this closed", the reason is not decoration — it needs to render as
// visible text, not just live in an attribute nobody on a phone will see.

import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { BaliStatusBadge } from "./BaliStatusBadge";
import { getCode } from "@/lib/kbli-data";
import { toPanelDetail } from "@/lib/kbli-panel-detail";
import type { KBLICode } from "@/lib/kbli-types";

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

describe("BaliStatusBadge — ATTENZIONE_FASCIA_BALI (added 2026-09-15, W-J B1 overlay)", () => {
  it("GUILT: renders the warn label and never a green/ok wording", () => {
    render(<BaliStatusBadge status="ATTENZIONE_FASCIA_BALI" />);
    expect(
      screen.getByText("Not on Bali's PMA closure list — verify on OSS"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/registrable/i)).toBeNull();
    expect(screen.queryByText(/^open in bali$/i)).toBeNull();
  });

  it("INNOCENCE: renders with the pill present (not dropped like an unknown status)", () => {
    const { container } = render(
      <BaliStatusBadge status="ATTENZIONE_FASCIA_BALI" />,
    );
    expect(container.firstChild).not.toBeNull();
  });
});

// =============================================================================
// Review F1(g): the listing/panel badge props are the panel projection's
// job (kbli-panel-detail.ts's `toPanelDetail`), so end-to-end on REAL data —
// a MEDIUM-confidence CHIUSO_BALI code (47211) must show "· medium conf.",
// which never rendered before W-J B1 disclose (only HIGH-confidence Bali
// verdicts ever reached this badge on an unlocated national record).
// =============================================================================
describe("BaliStatusBadge — panel/card props sourced from the real dataset (review F1g)", () => {
  it("47211 (MEDIUM confidence, CHIUSO_BALI) renders the '· medium conf.' marker via the panel projection", () => {
    const kbli = getCode("47211") as KBLICode;
    expect(kbli.baliL4?.confidence).toBe("MEDIUM");
    const detail = toPanelDetail(kbli);

    render(
      <BaliStatusBadge
        status={detail.bali.status}
        confidence={detail.bali.confidence}
        needsReview={detail.bali.needsReview}
      />,
    );

    expect(screen.getByText("· medium conf.")).toBeInTheDocument();
  });

  it("68111 (HIGH confidence, CHIUSO_BALI) renders no confidence marker via the panel projection", () => {
    const kbli = getCode("68111") as KBLICode;
    expect(kbli.baliL4?.confidence).toBe("HIGH");
    const detail = toPanelDetail(kbli);

    render(
      <BaliStatusBadge
        status={detail.bali.status}
        confidence={detail.bali.confidence}
        needsReview={detail.bali.needsReview}
      />,
    );

    expect(screen.queryByText(/conf\./)).toBeNull();
    expect(screen.queryByText("· needs review")).toBeNull();
  });
});
