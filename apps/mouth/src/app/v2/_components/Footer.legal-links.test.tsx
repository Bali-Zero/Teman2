import { render } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

// Guard for spec C1 (2026-09-27): PR-A moved /privacy, /terms and /cookies
// under (blog); PR-B (this one) moves /about, /careers and /press too, and
// the v2 page files are deleted in the same PR each time. A footer link
// still pointing at /v2/privacy, /v2/terms, /v2/cookies or /v2/company/*
// would 404-via-redirect forever after — cheaper to catch it here than to
// notice it live.
vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

const V2_LEGAL_COMPANY = /\/v2\/(privacy|terms|cookies|company)(\/|"|$)/;

function hrefs(container: HTMLElement): string[] {
  return Array.from(container.querySelectorAll("a")).map(
    (a) => a.getAttribute("href") ?? "",
  );
}

describe("footers carry no /v2/ legal or company href", () => {
  it("the v2/_components Footer (also rendered by the (blog) layout)", async () => {
    const { Footer } = await import("./Footer");
    const { container } = render(<Footer />);
    const offenders = hrefs(container).filter((h) => V2_LEGAL_COMPANY.test(h));
    expect(offenders).toEqual([]);
  });

  it("the r19/home Footer (the homepage's own footer)", async () => {
    const { Footer } = await import("@/components/r19/home/Footer");
    const { container } = render(<Footer />);
    const offenders = hrefs(container).filter((h) => V2_LEGAL_COMPANY.test(h));
    expect(offenders).toEqual([]);
  });
});
