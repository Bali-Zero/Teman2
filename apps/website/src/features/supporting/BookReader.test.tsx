import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BookReader } from "./BookReader";
import { LegalReader } from "./LegalReader";
import { BookKeys } from "./BookKeys";

const push = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("../../components/SiteShell", () => ({
  SiteShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));
beforeEach(() => {
  vi.unstubAllGlobals();
  push.mockClear();
});

describe("native book and legal reading", () => {
  it("keeps deep chapter links and language choice together", () => {
    render(<BookReader chapter="origin" locale="it" />);
    expect(
      screen.getByRole("heading", { level: 1, name: "Origine" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Pak Zainal Abidin aveva già visto tutto/),
    ).toBeInTheDocument();
    const languages = screen.getByRole("navigation", { name: "Book language" });
    expect(
      within(languages).getByRole("link", { name: "中文" }),
    ).toHaveAttribute("href", "/book/origin?lang=zh");
    expect(
      within(languages).getByRole("link", { name: "Italiano" }),
    ).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("main")).toHaveAttribute("lang", "it");
  });
  it("filters the actual service choices, expands scope and leaves pricing unavailable on upstream failure", async () => {
    const user = userEvent.setup();
    const fetcher = vi
      .fn()
      .mockResolvedValue({
        ok: false,
        json: async () => ({ available: false }),
      });
    vi.stubGlobal("fetch", fetcher);
    render(<BookReader chapter="services" />);
    expect(fetcher).not.toHaveBeenCalled();
    expect(
      screen.getByRole("heading", { name: "C1 Tourism" }),
    ).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", {
        name: "Check current price for C1 Tourism",
      }),
    );
    expect(
      await screen.findByText("Price unavailable. Request a quote."),
    ).toBeInTheDocument();
    expect(fetcher).toHaveBeenCalledWith(
      "/api/service-price?key=C1%20Tourism",
      expect.objectContaining({ credentials: "omit", cache: "no-store" }),
    );
    await user.click(screen.getByRole("button", { name: "Property" }));
    expect(
      screen.queryByRole("heading", { name: "C1 Tourism" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Property Advisory" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Lease Agreement" }),
    ).toBeInTheDocument();
    const details = screen
      .getAllByText("Scope & preparation")[0]
      .closest("details")!;
    await user.click(within(details).getByText("Scope & preparation"));
    expect(details.open).toBe(true);
    expect(
      within(details).getByRole("link", { name: "Read the service dossier ↗" }),
    ).toHaveAttribute("href", "/services/property#svc-property-001");
    expect(screen.queryByText("Nominee structure")).not.toBeInTheDocument();
  });
  it("supplies ordinary navigation and arrow shortcuts without capturing form controls", () => {
    render(
      <>
        <BookKeys previous="/book?lang=en" next="/book/origin?lang=en" />
        <input aria-label="Your notes" />
      </>,
    );
    fireEvent.keyDown(document.body, { key: "ArrowRight" });
    expect(push).toHaveBeenCalledWith("/book/origin?lang=en");
    push.mockClear();
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "ArrowLeft" });
    fireEvent.keyDown(document.body, { key: "ArrowLeft", altKey: true });
    expect(push).not.toHaveBeenCalled();
  });
  it("provides legal contents linked to the actual rendered headings", () => {
    render(<LegalReader documentKey="v2-terms" />);
    const navigation = screen.getByRole("navigation", { name: "On this page" });
    expect(
      within(navigation).getByRole("link", { name: "7. Governing law" }),
    ).toHaveAttribute("href", "#section-7");
    expect(
      screen.getByRole("heading", { name: "7. Governing law" }),
    ).toHaveAttribute("id", "section-7");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Terms of Service",
    );
  });
});
