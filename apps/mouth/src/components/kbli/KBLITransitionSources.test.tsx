import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { getCode } from "@/lib/kbli-data";
import { KBLITransitionSources } from "./KBLITransitionSources";

describe("KBLITransitionSources — BPS-authoritative transition disclosure", () => {
  it("guilt: 01138 renders BPS first, PP28 second, with neither called previous codes", () => {
    const code = getCode("01138")!;
    const { container } = render(
      <KBLITransitionSources transition={code.transition} />,
    );

    const bps = screen.getByTestId("bps-transition-source");
    const pp28 = screen.getByTestId("pp28-transition-source");
    expect(
      bps.compareDocumentPosition(pp28) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      within(bps).getByText("Authoritative BPS crosswalk"),
    ).toBeInTheDocument();
    expect(within(bps).getByText("01283")).toBeInTheDocument();
    expect(
      within(pp28).getByText("PP 28/2025 licensing source"),
    ).toBeInTheDocument();
    expect(within(pp28).getByText("01122")).toBeInTheDocument();
    expect(container.textContent).not.toContain("Previous codes");
    expect(container.textContent).toContain(
      "Legacy PP28 source-matching note:",
    );
  });

  it("vintage-link trap: BPS 01283 and PP28 01122 are monospaced plain text, never links", () => {
    const code = getCode("01138")!;
    const { container } = render(
      <KBLITransitionSources transition={code.transition} />,
    );
    for (const token of ["01283", "01122"]) {
      const node = screen.getByText(token);
      expect(node.tagName).toBe("SPAN");
      expect(node.className).toContain("font-mono");
      expect(node.closest("a")).toBeNull();
    }
    expect(container.querySelector('a[href="/kbli/01283"]')).toBeNull();
    expect(container.querySelector('a[href="/kbli/01122"]')).toBeNull();
  });

  it("guilt: PP28-only 01287 renders a BPS gap before its licensing citation", () => {
    const code = getCode("01287")!;
    render(<KBLITransitionSources transition={code.transition} />);
    expect(screen.getByText("BPS crosswalk gap")).toBeInTheDocument();
    expect(
      screen.getByText(
        "No official BPS 2020 → 2025 crosswalk ancestor is recorded for this code. This is an ancestry data gap, not evidence that no KBLI 2020 predecessor existed.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByTestId("pp28-transition-source")).toHaveTextContent(
      "01287",
    );
  });

  it("innocence: BPS-only 01122 keeps the authoritative card and verbatim disclaimer", () => {
    const code = getCode("01122")!;
    render(<KBLITransitionSources transition={code.transition} />);
    expect(screen.getByText("Authoritative BPS crosswalk")).toBeInTheDocument();
    expect(screen.queryByTestId("pp28-transition-source")).toBeNull();
    expect(screen.getByTestId("bps-transition-source")).toHaveTextContent(
      "Source: the BPS 2020↔2025 conversion table, mechanically extracted and acceptance-gate verified. It shows which 2020 codes map to this 2025 code — provenance only, not a licensing claim: the regulatory regime of these predecessor codes has not been adjudicated as transferring.",
    );
  });

  it("innocence: neither-source 64995 renders only the meaningful BPS gap", () => {
    const code = getCode("64995")!;
    render(<KBLITransitionSources transition={code.transition} />);
    expect(screen.getByText("BPS crosswalk gap")).toBeInTheDocument();
    expect(screen.queryByTestId("pp28-transition-source")).toBeNull();
    expect(
      screen.getByRole("region", {
        name: "KBLI 2020 to 2025 transition sources",
      }),
    ).toBeInTheDocument();
  });
});
