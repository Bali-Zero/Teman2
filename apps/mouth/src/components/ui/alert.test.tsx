import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Alert, AlertTitle, AlertDescription } from "./alert";

describe("Alert", () => {
  it("renders with role='alert'", () => {
    render(<Alert>Alert content</Alert>);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("applies default variant classes", () => {
    render(<Alert>Default</Alert>);
    const el = screen.getByRole("alert");
    expect(el.className).toContain("rounded-lg");
    expect(el.className).toContain("border");
    expect(el.className).toContain("p-4");
  });

  it("applies destructive variant", () => {
    render(<Alert variant="destructive">Error!</Alert>);
    const el = screen.getByRole("alert");
    expect(el.className).toContain("border-red-500/50");
    expect(el.className).toContain("text-red-500");
  });

  it("merges custom className", () => {
    render(<Alert className="my-alert">Custom</Alert>);
    expect(screen.getByRole("alert").className).toContain("my-alert");
  });

  it("forwards ref", () => {
    const ref = React.createRef<HTMLDivElement>();
    render(<Alert ref={ref}>Ref test</Alert>);
    expect(ref.current).toBeInstanceOf(HTMLDivElement);
  });
});

describe("AlertTitle", () => {
  it("renders as h5 with styling", () => {
    render(<AlertTitle>Warning</AlertTitle>);
    const el = screen.getByText("Warning");
    expect(el.tagName).toBe("H5");
    expect(el.className).toContain("font-medium");
  });
});

describe("AlertDescription", () => {
  it("renders as div with text styling", () => {
    render(<AlertDescription>Some details here</AlertDescription>);
    const el = screen.getByText("Some details here");
    expect(el.tagName).toBe("DIV");
    expect(el.className).toContain("text-sm");
  });
});

describe("Alert composition", () => {
  it("renders title and description together", () => {
    render(
      <Alert>
        <AlertTitle>Heads up!</AlertTitle>
        <AlertDescription>
          You can add components to your app using the cli.
        </AlertDescription>
      </Alert>,
    );

    expect(screen.getByText("Heads up!")).toBeInTheDocument();
    expect(
      screen.getByText(
        "You can add components to your app using the cli.",
      ),
    ).toBeInTheDocument();
  });
});
