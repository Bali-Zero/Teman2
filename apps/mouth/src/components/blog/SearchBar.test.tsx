import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SearchBar, SearchModal, SearchTrigger } from "./SearchBar";

const loggerMock = vi.hoisted(() => ({
  error: vi.fn(),
}));

vi.mock("@/lib/logger", () => ({
  logger: loggerMock,
}));

describe("SearchBar", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    loggerMock.error.mockReset();
    Object.defineProperty(window, "scrollTo", {
      configurable: true,
      value: vi.fn(),
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("debounces typing, submits immediately, and clears the query", () => {
    const onSearch = vi.fn();
    render(<SearchBar defaultValue="visa" onSearch={onSearch} />);

    const input = screen.getByLabelText("Search articles");
    fireEvent.change(input, { target: { value: "tax" } });
    expect(onSearch).not.toHaveBeenCalled();

    vi.advanceTimersByTime(300);
    expect(onSearch).toHaveBeenCalledWith("tax");

    fireEvent.submit(input.closest("form") as HTMLFormElement);
    expect(onSearch).toHaveBeenLastCalledWith("tax");

    fireEvent.click(screen.getByRole("button"));
    expect(onSearch).toHaveBeenLastCalledWith("");
    expect(input).toHaveFocus();
  });

  it("focuses with command-k and closes filters with escape", () => {
    render(<SearchBar showFilters />);

    fireEvent.keyDown(document, { key: "k", metaKey: true });
    expect(screen.getByLabelText("Search articles")).toHaveFocus();

    fireEvent.click(screen.getAllByRole("button")[0]);
    expect(screen.getByText("Sort by")).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.getByLabelText("Search articles")).not.toHaveFocus();
  });

  it("changes filter sorting state", () => {
    render(<SearchBar showFilters />);

    fireEvent.click(screen.getAllByRole("button")[0]);
    fireEvent.click(screen.getByRole("button", { name: /latest/i }));
    fireEvent.click(screen.getByRole("button", { name: /popular/i }));

    expect(screen.getByRole("button", { name: /popular/i })).toHaveClass(
      "text-violet-400",
    );
  });
});

describe("SearchTrigger", () => {
  it("calls the supplied click handler", () => {
    const onClick = vi.fn();

    render(<SearchTrigger onClick={onClick} />);
    fireEvent.click(screen.getByRole("button"));

    expect(onClick).toHaveBeenCalledTimes(1);
  });
});

describe("SearchModal", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.mocked(fetch).mockReset();
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { href: "" },
    });
  });

  it("does not render when closed", () => {
    const { container } = render(<SearchModal isOpen={false} onClose={vi.fn()} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("fetches debounced results and navigates selected result with enter", async () => {
    vi.useRealTimers();
    Object.defineProperty(window, "scrollTo", {
      configurable: true,
      value: vi.fn(),
    });
    const onClose = vi.fn();
    vi.mocked(fetch).mockResolvedValue({
      json: async () => ({
        articles: [
          {
            id: "a1",
            slug: "visa-clock",
            title: "Visa Clock",
            excerpt: "Track a visa timeline",
            coverImage: "/cover.jpg",
            category: "visa",
            readingTime: 4,
            publishedAt: "2026-05-09",
          },
          {
            id: "a2",
            slug: "tax-calendar",
            title: "Tax Calendar",
            excerpt: "Know the date",
            coverImage: "/tax.jpg",
            category: "tax",
            readingTime: 2,
            publishedAt: "2026-05-08",
          },
        ],
      }),
    } as Response);

    render(<SearchModal isOpen onClose={onClose} />);

    fireEvent.change(screen.getByRole("textbox", { name: "Search articles" }), {
      target: { value: "visa" },
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 320));
    });

    await waitFor(() => {
      expect(screen.getByText("Visa Clock")).toBeInTheDocument();
    });
    expect(fetch).toHaveBeenCalledWith("/api/blog/articles?q=visa&limit=10");

    fireEvent.keyDown(document, { key: "ArrowDown" });
    fireEvent.keyDown(document, { key: "Enter" });

    expect(window.location.href).toBe("/tax/tax-calendar");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("clears results on fetch failure and closes on escape/backdrop", async () => {
    vi.useRealTimers();
    Object.defineProperty(window, "scrollTo", {
      configurable: true,
      value: vi.fn(),
    });
    const onClose = vi.fn();
    vi.mocked(fetch).mockRejectedValue(new Error("network"));

    render(<SearchModal isOpen onClose={onClose} />);

    fireEvent.change(screen.getByRole("textbox", { name: "Search articles" }), {
      target: { value: "broken" },
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 320));
    });

    await waitFor(() => {
      expect(fetch).toHaveBeenCalled();
    });
    expect(screen.getByText(/No results found for/)).toBeInTheDocument();
    expect(loggerMock.error).toHaveBeenCalledWith(
      "Search failed:",
      expect.any(Error),
    );

    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
