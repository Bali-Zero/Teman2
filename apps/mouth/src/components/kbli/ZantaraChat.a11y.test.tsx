import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ZantaraChat } from "./ZantaraChat";

// next/dynamic pulls react-markdown in lazily; under jsdom we only need a
// passthrough so the component tree mounts.
vi.mock("next/dynamic", () => ({
  default: () =>
    function Markdown({ children }: { children?: React.ReactNode }) {
      return <>{children}</>;
    },
}));
vi.mock("@/lib/analytics", () => ({ trackKBLIChatQuestion: vi.fn() }));

describe("ZantaraChat accessibility surface", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("exposes the message list as a named polite log, before any message", () => {
    render(<ZantaraChat />);

    const log = screen.getByRole("log", {
      name: "Conversation with Zantara AI",
    });
    expect(log).toHaveAttribute("aria-live", "polite");
  });

  // The typing indicator is three bouncing dots and nothing else — zero text.
  // role="status" on a node with no text announces nothing, so the dots are
  // aria-hidden and an sr-only string carries the state.
  it("announces the typing indicator instead of showing silent dots", async () => {
    let release: (v: unknown) => void = () => {};
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockReturnValue(
      new Promise((resolve) => {
        release = resolve;
      }),
    );

    render(<ZantaraChat />);
    const box = screen.getByRole("textbox", { name: "Chat with Zantara AI" });
    fireEvent.change(box, { target: { value: "what is 56101" } });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));

    const status = await screen.findByRole("status");
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status).toHaveTextContent("Zantara is typing");

    release({ ok: true, json: async () => ({ answer: "ok" }) });
    await waitFor(() =>
      expect(screen.queryByRole("status")).not.toBeInTheDocument(),
    );
  });

  it("keeps a programmatic name on the icon-only send control", () => {
    render(<ZantaraChat />);
    expect(
      screen.getByRole("button", { name: "Send message" }),
    ).toBeInTheDocument();
  });

  it("keeps a programmatic name on the chat input", () => {
    render(<ZantaraChat />);
    expect(
      screen.getByRole("textbox", { name: "Chat with Zantara AI" }),
    ).toBeInTheDocument();
  });

  it("names each suggestion chip from its visible text", () => {
    render(<ZantaraChat suggestions={["Capital rules", "Risk level"]} />);
    expect(
      screen.getByRole("button", { name: "Capital rules" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Risk level" }),
    ).toBeInTheDocument();
  });

  it("puts the opener inside the log so it is announced with the thread", () => {
    render(<ZantaraChat opener="Ask me about this code." />);
    const log = screen.getByRole("log", {
      name: "Conversation with Zantara AI",
    });
    expect(log).toHaveTextContent("Ask me about this code.");
  });
});
