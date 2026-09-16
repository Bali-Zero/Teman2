// Review r2 m4: the badge tests elsewhere in this suite render
// `BaliStatusBadge` directly, so removing the `scope=`/`confidence=` props at
// KBLICard's own call site would stay green there. This renders the real
// `KBLICard` (same discipline as `LicensingSection.bali-sourced-closure.test.tsx`
// — real codes via `getCode`) to catch exactly that regression.

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { getCode } from "@/lib/kbli-data";
import type { KBLICode } from "@/lib/kbli-types";
import { KBLICard } from "./KBLICard";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    className,
  }: {
    children: React.ReactNode;
    href: string;
    className?: string;
  }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}));

describe("KBLICard — the Bali badge carries the scope/confidence marker forwarded from the code", () => {
  it("55101 (Five-Star Hotel, scoped: building area under 6,000 m²) shows the scope marker", () => {
    const code = getCode("55101") as KBLICode;
    expect(code.baliL4?.closure?.scopeQualifier).toBe(
      "building area under 6,000 m²",
    );

    render(<KBLICard code={code} />);

    expect(screen.getByText(/under 6,000 m²/)).toBeInTheDocument();
  });

  it("47211 (MEDIUM confidence, unscoped) shows the medium-confidence marker", () => {
    const code = getCode("47211") as KBLICode;
    expect(code.baliL4?.confidence).toBe("MEDIUM");
    expect(code.baliL4?.closure?.scopeQualifier).toBeFalsy();

    render(<KBLICard code={code} />);

    expect(screen.getByText(/medium conf\./)).toBeInTheDocument();
  });

  it("innocence: 68111 (HIGH confidence, unscoped) shows neither marker", () => {
    const code = getCode("68111") as KBLICode;
    expect(code.baliL4?.confidence).toBe("HIGH");
    expect(code.baliL4?.closure?.scopeQualifier).toBeFalsy();

    render(<KBLICard code={code} />);

    expect(screen.queryByText(/only$/)).toBeNull();
    expect(screen.queryByText(/conf\./)).toBeNull();
  });
});
