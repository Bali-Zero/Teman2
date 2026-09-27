import { render } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

// Guard for spec C1 PR-A (2026-09-27, legal-only slice): /privacy, /terms
// and /cookies moved under (blog) and the v2 page files were deleted in
// the same PR. A footer link still pointing at /v2/privacy, /v2/terms or
// /v2/cookies would 404-via-redirect forever after — cheaper to catch it
// here than to notice it live. Company (/v2/company/*) is PR-B and is
// deliberately NOT checked here — those links still point at v2 today.
vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

const V2_LEGAL = /\/v2\/(privacy|terms|cookies)(\/|"|$)/;

function hrefs(container: HTMLElement): string[] {
  return Array.from(container.querySelectorAll("a")).map(
    (a) => a.getAttribute("href") ?? "",
  );
}

describe("footers carry no /v2/ legal href", () => {
  it("the v2/_components Footer (also rendered by the (blog) layout)", async () => {
    const { Footer } = await import("./Footer");
    const { container } = render(<Footer />);
    const offenders = hrefs(container).filter((h) => V2_LEGAL.test(h));
    expect(offenders).toEqual([]);
  });

  it("the r19/home Footer (the homepage's own footer)", async () => {
    const { Footer } = await import("@/components/r19/home/Footer");
    const { container } = render(<Footer />);
    const offenders = hrefs(container).filter((h) => V2_LEGAL.test(h));
    expect(offenders).toEqual([]);
  });
});
