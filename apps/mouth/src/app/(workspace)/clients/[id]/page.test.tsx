// The server boundary is the thing that decides WHAT the client gets, so it gets
// its own test.
//
// Raised by a refuter seat: renaming the old page test to ClientDetailClient.test
// left the new 22-line server component with no coverage at all. Nothing asserted
// that it calls `taxConsultants()` rather than, say, handing down a literal it
// defined itself — which would put the addresses straight back into a module that
// the client tree imports.
//
// The assertion deliberately does NOT restate the five addresses. They are pinned
// once, in src/lib/workspace/roster-directory.test.ts, against the backend CHECK
// constraint; copying them here would duplicate the source of truth and put staff
// emails in a second file for no added coverage. What this proves is the WIRING:
// the prop is exactly what the server module returns, and it is not empty.
import React from "react";
import { describe, expect, it, vi } from "vitest";

const { clientProps } = vi.hoisted(() => ({
  clientProps: [] as Record<string, unknown>[],
}));

vi.mock("./ClientDetailClient", () => ({
  ClientDetailClient: (props: Record<string, unknown>) => {
    clientProps.push(props);
    return <div data-testid="ClientDetailClient" />;
  },
}));

describe("ClientDetailPage (server boundary)", () => {
  it("hands the client the list the server module resolves, not one of its own", async () => {
    const { default: ClientDetailPage } = await import("./page");
    const { taxConsultants } = await import("@/lib/workspace/roster-directory");

    // A server component here is a plain function returning an element; calling
    // it is enough, and avoids rendering the (mocked) client subtree.
    const element = ClientDetailPage() as React.ReactElement<{
      taxConsultants: unknown;
    }>;

    const expected = taxConsultants();
    expect(expected.length).toBeGreaterThan(0);
    expect(element.props.taxConsultants).toEqual(expected);
  });

  it("passes a copy, so the client cannot mutate the server's table", async () => {
    const { default: ClientDetailPage } = await import("./page");
    const { taxConsultants } = await import("@/lib/workspace/roster-directory");

    const first = (
      ClientDetailPage() as React.ReactElement<{ taxConsultants: unknown[] }>
    ).props.taxConsultants;
    (first as Record<string, unknown>[]).push({
      value: "injected@example.test",
      label: "Injected",
    });

    // A later resolution must be unaffected by that mutation.
    expect(
      taxConsultants().some((c) => c.value === "injected@example.test"),
    ).toBe(false);
  });
});
