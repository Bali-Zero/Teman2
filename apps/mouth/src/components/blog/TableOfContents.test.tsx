import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  FloatingToc,
  ReadingProgress,
  TableOfContents,
  extractHeadings,
} from "./TableOfContents";

class MockIntersectionObserver implements IntersectionObserver {
  readonly root: Element | Document | null = null;
  readonly rootMargin = "";
  readonly thresholds: ReadonlyArray<number> = [];
  private readonly callback: IntersectionObserverCallback;

  constructor(callback: IntersectionObserverCallback) {
    this.callback = callback;
    MockIntersectionObserver.instances.push(this);
  }

  static instances: MockIntersectionObserver[] = [];
  observed: Element[] = [];
  disconnected = false;

  observe = (target: Element): void => {
    this.observed.push(target);
  };

  unobserve = (target: Element): void => {
    this.observed = this.observed.filter((item) => item !== target);
  };

  disconnect = (): void => {
    this.disconnected = true;
  };

  takeRecords = (): IntersectionObserverEntry[] => [];

  intersect(target: Element): void {
    this.callback(
      [
        {
          isIntersecting: true,
          target,
        } as IntersectionObserverEntry,
      ],
      this,
    );
  }
}

const content = `
# Ignored H1
## Visa Clock
### Required Documents!
#### Final Review
##### Ignored H5
`;

describe("TableOfContents", () => {
  beforeEach(() => {
    MockIntersectionObserver.instances = [];
    vi.stubGlobal("IntersectionObserver", MockIntersectionObserver);
    window.scrollTo = vi.fn();
    document.body.innerHTML = "";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("extracts only level two through four headings and normalizes ids", () => {
    expect(extractHeadings(content)).toEqual([
      { id: "visa-clock", text: "Visa Clock", level: 2 },
      {
        id: "required-documents",
        text: "Required Documents!",
        level: 3,
      },
      { id: "final-review", text: "Final Review", level: 4 },
    ]);
  });

  it("renders nothing when content has no supported headings", () => {
    const { container } = render(<TableOfContents content="# Title only" />);

    expect(container).toBeEmptyDOMElement();
  });

  it("observes heading elements, tracks active heading, and scrolls with offset", async () => {
    const heading = document.createElement("h2");
    heading.id = "visa-clock";
    document.body.appendChild(heading);

    vi.spyOn(document.body, "getBoundingClientRect").mockReturnValue({
      top: 10,
    } as DOMRect);
    vi.spyOn(heading, "getBoundingClientRect").mockReturnValue({
      top: 310,
    } as DOMRect);

    render(<TableOfContents content={content} />);

    const observer = MockIntersectionObserver.instances[0];
    expect(observer.observed).toContain(heading);

    act(() => {
      observer.intersect(heading);
    });
    fireEvent.click(screen.getByRole("button", { name: "Visa Clock" }));

    expect(window.scrollTo).toHaveBeenCalledWith({
      top: 200,
      behavior: "smooth",
    });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Visa Clock" })).toHaveClass(
        "text-violet-400",
      );
    });
  });

  it("opens floating toc, closes on selection, and closes on escape", () => {
    const heading = document.createElement("h2");
    heading.id = "visa-clock";
    document.body.appendChild(heading);
    window.scrollTo = vi.fn();

    render(<FloatingToc content={content} />);

    fireEvent.click(
      screen.getByRole("button", { name: "Open table of contents" }),
    );
    expect(screen.getByText("Table of Contents")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Visa Clock" }));
    expect(window.scrollTo).toHaveBeenCalled();
    expect(screen.queryByText("Table of Contents")).not.toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "Open table of contents" }),
    );
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByText("Table of Contents")).not.toBeInTheDocument();
  });

  it("updates reading progress from scroll position", () => {
    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: 500,
    });
    Object.defineProperty(window, "scrollY", {
      configurable: true,
      value: 250,
    });
    Object.defineProperty(document.documentElement, "scrollHeight", {
      configurable: true,
      value: 1000,
    });

    const { container } = render(<ReadingProgress />);

    fireEvent.scroll(window);

    expect(container.querySelector(".bg-gradient-to-r")).toBeInTheDocument();
  });
});
