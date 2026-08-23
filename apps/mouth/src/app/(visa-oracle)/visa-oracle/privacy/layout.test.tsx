/**
 * The privacy layout is set explicitly (not left to inherit from
 * ../layout.tsx) so it stays correct on its own — see the comment in
 * layout.tsx for why a public privacy policy stays noindex while the tool
 * it describes is SHADOW/unratified.
 */
import { describe, expect, it } from "vitest";

import VisaOraclePrivacyLayout, { metadata } from "./layout";

describe("visa-oracle/privacy layout metadata: noindex is explicit, not inherited", () => {
  it("guilt: robots directive blocks both index and follow", () => {
    expect(metadata.robots).toEqual({ index: false, follow: false });
  });

  it("innocence: children still render through the layout", () => {
    expect(
      VisaOraclePrivacyLayout({
        children: "privacy child" as unknown as React.ReactNode,
      }),
    ).toBe("privacy child");
  });
});
