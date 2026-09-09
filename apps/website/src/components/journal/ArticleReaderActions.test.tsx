import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ArticleContextHelp, ArticleReaderActions } from "./ArticleReaderActions";
const url = "https://balizero.com/property/leasehold-vs-freehold";
afterEach(() => vi.unstubAllGlobals());
describe("non-sending article actions", () => {
  it("shares the selected authored language while dropping private query and hash context", () => {
    render(<ArticleReaderActions title="Una guida" url={`${url}?lang=it&token=private-reference#private-context`} includeContextHelp={false} />);
    const email = new URL(screen.getByRole("link", { name: /Open an email with this article/ }).getAttribute("href")!);
    expect(email.searchParams.get("body")).toBe(`${url}?lang=it`);
  });
  it("preserves article and selected question in both drafts without any network request", () => {
    const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
    render(<ArticleContextHelp title="Leasehold vs Freehold" url={url} context="Property ownership" questions={["What should I ask about my lease?"]} />);
    fireEvent.click(screen.getByRole("button", { name: "What should I ask about my lease?" }));
    expect(screen.getByRole("button")).toHaveAttribute("aria-pressed", "true");
    const whatsapp = new URL(screen.getByRole("link", { name: /WhatsApp/ }).getAttribute("href")!);
    expect(whatsapp.origin).toBe("https://wa.me"); expect(whatsapp.searchParams.get("text")).toContain(url); expect(whatsapp.searchParams.get("text")).toContain("What should I ask");
    const email = new URL(screen.getByRole("link", { name: /email draft/ }).getAttribute("href")!);
    expect(email.searchParams.get("body")).toContain(url); expect(email.searchParams.get("body")).toContain("What should I ask");
    expect(fetcher).not.toHaveBeenCalled();
    expect(screen.getByText(/chat is unavailable/)).toBeVisible();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });
  it("reports copy success only after clipboard resolves; failure exposes a selectable address", async () => {
    let finishCopy!: () => void;
    const pending = new Promise<void>((resolve) => { finishCopy = resolve; });
    const writeText = vi.fn().mockReturnValue(pending); Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    render(<ArticleReaderActions title="A property guide" url={url} />);
    fireEvent.click(screen.getByRole("button", { name: "Copy article link" }));
    expect(screen.getByRole("button", { name: "Copying…" })).toBeDisabled();
    expect(screen.queryByText("Article link copied.")).not.toBeInTheDocument();
    finishCopy();
    await screen.findByText("Article link copied."); expect(writeText).toHaveBeenCalledWith(url);
    writeText.mockRejectedValue(new Error("Permission unavailable"));
    fireEvent.click(screen.getByRole("button", { name: "Copy article link" }));
    await waitFor(() => expect(screen.getByRole("textbox", { name: "Article address" })).toHaveValue(url));
    expect(screen.getByText(/Newsletter signup is unavailable/)).toBeVisible();
  });
  it("rejects foreign and authenticated destinations as public article context", () => {
    const { container } = render(<ArticleReaderActions title="Invalid" url="https://kita.balizero.com/chat" />);
    expect(container).toBeEmptyDOMElement();
  });
  it("keeps sharing and newsletter when authored context help already exists, including legacy slugs", () => {
    const legacyUrl = "https://balizero.com/property/published---story-";
    render(<ArticleReaderActions title="A published legacy article" url={legacyUrl} includeContextHelp={false} />);
    expect(screen.getByRole("button", { name: "Copy article link" })).toBeVisible();
    const email = new URL(screen.getByRole("link", { name: /Open an email with this article/ }).getAttribute("href")!);
    expect(email.searchParams.get("body")).toBe(legacyUrl);
    expect(screen.getByRole("region", { name: "Journal newsletter" })).toBeVisible();
    expect(screen.getByText(/Newsletter signup is unavailable/)).toBeVisible();
    expect(screen.queryByRole("heading", { name: "A question about this article?" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /WhatsApp/ })).not.toBeInTheDocument();
  });
});
