import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  Skeleton,
  MessageBubbleSkeleton,
  ChatMessageListSkeleton,
  StatCardSkeleton,
  PageSkeleton,
} from "./skeleton";

describe("Skeleton", () => {
  it("renders a single skeleton element by default", () => {
    const { container } = render(
      <Skeleton data-testid="skeleton" className="test-class" />,
    );
    // Single div (not wrapped in a space-y container)
    const skeletonEl = container.firstChild as HTMLElement;
    expect(skeletonEl.className).toContain("skeleton");
    expect(skeletonEl.className).toContain("test-class");
  });

  it("applies text variant styles", () => {
    const { container } = render(<Skeleton variant="text" />);
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain("h-4");
    expect(el.className).toContain("rounded");
  });

  it("applies circular variant styles", () => {
    const { container } = render(<Skeleton variant="circular" />);
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain("rounded-full");
  });

  it("applies width and height as inline styles", () => {
    const { container } = render(<Skeleton width={100} height={20} />);
    const el = container.firstChild as HTMLElement;
    expect(el.style.width).toBe("100px");
    expect(el.style.height).toBe("20px");
  });

  it("accepts string dimensions", () => {
    const { container } = render(<Skeleton width="50%" height="2rem" />);
    const el = container.firstChild as HTMLElement;
    expect(el.style.width).toBe("50%");
    expect(el.style.height).toBe("2rem");
  });

  it("renders multiple lines when lines > 1", () => {
    const { container } = render(<Skeleton variant="text" lines={3} />);
    // Should render a wrapper div with 3 children
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.children).toHaveLength(3);
  });

  it("makes last line shorter when multi-line", () => {
    const { container } = render(
      <Skeleton variant="text" lines={3} width={200} />,
    );
    const wrapper = container.firstChild as HTMLElement;
    const lastLine = wrapper.children[2] as HTMLElement;
    expect(lastLine.style.width).toBe("75%");
  });
});

describe("MessageBubbleSkeleton", () => {
  it("renders user variant (right-aligned)", () => {
    const { container } = render(<MessageBubbleSkeleton isUser={true} />);
    const outerDiv = container.firstChild as HTMLElement;
    expect(outerDiv.className).toContain("justify-end");
  });

  it("renders AI variant (left-aligned) by default", () => {
    const { container } = render(<MessageBubbleSkeleton />);
    const outerDiv = container.firstChild as HTMLElement;
    expect(outerDiv.className).toContain("justify-start");
  });
});

describe("ChatMessageListSkeleton", () => {
  it("renders the specified count of message skeletons", () => {
    const { container } = render(<ChatMessageListSkeleton count={4} />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.children).toHaveLength(4);
  });

  it("defaults to 3 messages", () => {
    const { container } = render(<ChatMessageListSkeleton />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.children).toHaveLength(3);
  });
});

describe("StatCardSkeleton", () => {
  it("renders without errors", () => {
    const { container } = render(<StatCardSkeleton />);
    expect(container.firstChild).toBeTruthy();
  });
});

describe("PageSkeleton", () => {
  it("renders header, stats row, and main content", () => {
    const { container } = render(<PageSkeleton />);
    expect(container.firstChild).toBeTruthy();
    // Should have children for header, stats grid, and widget
    const outerDiv = container.firstChild as HTMLElement;
    expect(outerDiv.children.length).toBeGreaterThanOrEqual(3);
  });
});
