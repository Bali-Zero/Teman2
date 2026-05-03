import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "./card";

describe("Card", () => {
  it("renders as a div with card classes", () => {
    render(<Card data-testid="card">Content</Card>);
    const el = screen.getByTestId("card");
    expect(el.tagName).toBe("DIV");
    expect(el.className).toContain("rounded-lg");
    expect(el.className).toContain("shadow-sm");
  });

  it("merges custom className", () => {
    render(
      <Card className="my-class" data-testid="card">
        Content
      </Card>,
    );
    expect(screen.getByTestId("card").className).toContain("my-class");
  });

  it("forwards ref", () => {
    const ref = React.createRef<HTMLDivElement>();
    render(<Card ref={ref}>Content</Card>);
    expect(ref.current).toBeInstanceOf(HTMLDivElement);
  });
});

describe("CardHeader", () => {
  it("renders with flex column layout", () => {
    render(<CardHeader data-testid="header">Header</CardHeader>);
    const el = screen.getByTestId("header");
    expect(el.className).toContain("flex");
    expect(el.className).toContain("flex-col");
    expect(el.className).toContain("p-6");
  });
});

describe("CardTitle", () => {
  it("renders as h3", () => {
    render(<CardTitle>My Title</CardTitle>);
    const el = screen.getByText("My Title");
    expect(el.tagName).toBe("H3");
    expect(el.className).toContain("text-2xl");
    expect(el.className).toContain("font-semibold");
  });
});

describe("CardDescription", () => {
  it("renders as p with muted text", () => {
    render(<CardDescription>Some description</CardDescription>);
    const el = screen.getByText("Some description");
    expect(el.tagName).toBe("P");
    expect(el.className).toContain("text-sm");
    expect(el.className).toContain("text-muted-foreground");
  });
});

describe("CardContent", () => {
  it("renders with padding", () => {
    render(<CardContent data-testid="content">Body</CardContent>);
    const el = screen.getByTestId("content");
    expect(el.className).toContain("p-6");
    expect(el.className).toContain("pt-0");
  });
});

describe("CardFooter", () => {
  it("renders with flex layout", () => {
    render(<CardFooter data-testid="footer">Footer</CardFooter>);
    const el = screen.getByTestId("footer");
    expect(el.className).toContain("flex");
    expect(el.className).toContain("items-center");
    expect(el.className).toContain("p-6");
  });
});

describe("Card composition", () => {
  it("renders a complete card with all sub-components", () => {
    render(
      <Card data-testid="card">
        <CardHeader>
          <CardTitle>Title</CardTitle>
          <CardDescription>Description</CardDescription>
        </CardHeader>
        <CardContent>Body content</CardContent>
        <CardFooter>Footer content</CardFooter>
      </Card>,
    );

    expect(screen.getByTestId("card")).toBeInTheDocument();
    expect(screen.getByText("Title")).toBeInTheDocument();
    expect(screen.getByText("Description")).toBeInTheDocument();
    expect(screen.getByText("Body content")).toBeInTheDocument();
    expect(screen.getByText("Footer content")).toBeInTheDocument();
  });
});
