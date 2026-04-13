import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "./badge";

describe("Badge", () => {
  it("renders children text", () => {
    render(<Badge>Active</Badge>);
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("applies default variant classes", () => {
    render(<Badge data-testid="badge">Default</Badge>);
    const el = screen.getByTestId("badge");
    expect(el.className).toContain("inline-flex");
    expect(el.className).toContain("rounded-full");
  });

  it("applies destructive variant", () => {
    render(
      <Badge variant="destructive" data-testid="badge">
        Error
      </Badge>,
    );
    const el = screen.getByTestId("badge");
    expect(el.className).toContain("bg-red-500");
  });

  it("applies outline variant", () => {
    render(
      <Badge variant="outline" data-testid="badge">
        Outline
      </Badge>,
    );
    const el = screen.getByTestId("badge");
    expect(el.className).toContain("border-[var(--border)]");
  });

  it("merges custom className", () => {
    render(
      <Badge className="my-custom" data-testid="badge">
        Custom
      </Badge>,
    );
    const el = screen.getByTestId("badge");
    expect(el.className).toContain("my-custom");
  });

  it("passes through HTML attributes", () => {
    render(
      <Badge role="status" aria-label="Status badge">
        Active
      </Badge>,
    );
    const el = screen.getByRole("status");
    expect(el).toHaveAttribute("aria-label", "Status badge");
  });
});
