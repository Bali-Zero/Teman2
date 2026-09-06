import { existsSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import Home from "./page";

describe("homepage integration", () => {
  it("connects every internal journey to an existing unique destination", () => {
    const { container } = render(<Home />);
    const ids = [...container.querySelectorAll("[id]")].map((el) => el.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const link of container.querySelectorAll('a[href^="#"]')) {
      expect(ids).toContain(link.getAttribute("href")!.slice(1));
    }
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });

  it("ships every referenced portrait and illustration and excludes removed members", () => {
    const { container } = render(<Home />);
    for (const image of container.querySelectorAll("img")) {
      const src = image.getAttribute("src")!;
      expect(src.startsWith("/assets/")).toBe(true);
      expect(existsSync(join(process.cwd(), "public", src))).toBe(true);
    }
    expect(container.textContent).not.toMatch(/Faysha|Fayisha|Sahira/i);
  });
});
