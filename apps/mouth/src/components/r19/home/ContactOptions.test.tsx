import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { ContactOptions } from "./ContactOptions";

vi.mock("@/components/lead/WhatsAppLeadButton", () => ({
  FALLBACK_WA_URL: "https://wa.me/628213454721",
  WhatsAppLeadButton: ({
    children,
    fallbackHref,
    source,
    context,
  }: {
    children: React.ReactNode;
    fallbackHref: string;
    source: string;
    context: object;
  }) => (
    <a
      href={fallbackHref}
      data-source={source}
      data-context={JSON.stringify(context)}
    >
      {children}
    </a>
  ),
}));
afterEach(cleanup);
describe("R19 topic-aware contact adapter", () => {
  it("uses the existing capture source and carries a changed topic into both destinations", () => {
    render(<ContactOptions />);
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "property" },
    });
    const whatsapp = screen.getByRole("link", { name: /Continue on WhatsApp/ });
    expect(whatsapp.getAttribute("data-source")).toBe("cta_handoff");
    expect(JSON.parse(whatsapp.getAttribute("data-context")!)).toEqual({
      topic: "property",
      source_page: "/",
      section: "contact",
    });
    expect(decodeURIComponent(whatsapp.getAttribute("href")!)).toContain(
      "Property due diligence",
    );
    expect(
      decodeURIComponent(
        screen
          .getByRole("link", { name: /Write an email/ })
          .getAttribute("href")!,
      ),
    ).toContain("Property due diligence");
  });
});
