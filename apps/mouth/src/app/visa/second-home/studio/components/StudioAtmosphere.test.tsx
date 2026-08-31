import { render, screen } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { StudioAtmosphere } from "./StudioAtmosphere";

describe("StudioAtmosphere", () => {
  it("renders identical procedural SVG output across fresh module loads", async () => {
    vi.resetModules();
    const { StudioAtmosphere: FirstModuleAtmosphere } =
      await import("./StudioAtmosphere");
    const firstRender = renderToStaticMarkup(<FirstModuleAtmosphere />);

    vi.resetModules();
    const { StudioAtmosphere: SecondModuleAtmosphere } =
      await import("./StudioAtmosphere");
    const secondRender = renderToStaticMarkup(<SecondModuleAtmosphere />);

    expect(secondRender).toBe(firstRender);
    expect(firstRender.match(/data-contour="true"/g)).toHaveLength(30);
  });

  it("is one aria-hidden decorative layer with no announced nodes", () => {
    const { container } = render(<StudioAtmosphere />);
    const atmosphere = screen.getByTestId("studio-atmosphere");

    expect(atmosphere).toHaveAttribute("aria-hidden", "true");
    expect(atmosphere).toBe(container.firstElementChild);
    expect(screen.queryByRole("img")).toBeNull();
    expect(
      atmosphere.querySelector(
        "a, button, input, select, textarea, [tabindex], [role]",
      ),
    ).toBeNull();
  });

  it("keeps the grain above the measured perceptibility floor", () => {
    const { container } = render(<StudioAtmosphere />);
    const turbulence = container.querySelector("feTurbulence");
    const colorMatrix = container.querySelector("feColorMatrix");
    const filter = container.querySelector("filter");
    const pattern = container.querySelector("pattern");
    const style = container.querySelector("style")?.textContent ?? "";

    expect(turbulence).toHaveAttribute("type", "fractalNoise");
    expect(turbulence).toHaveAttribute("seed", "37");
    // `filterRes` was removed from the SVG spec and has no rendering effect
    // in current browsers; leaving it in the server-rendered markup makes
    // React report a hydration attribute mismatch (measured live on
    // localhost:3717 — 1 hydration-mismatch console message with it,
    // 0 without). Do not re-add it.
    expect(filter).not.toHaveAttribute("filterRes");
    expect(pattern).toHaveAttribute("width", "180");
    expect(pattern).toHaveAttribute("height", "180");
    expect(pattern).toHaveAttribute("patternUnits", "userSpaceOnUse");
    expect(colorMatrix).toHaveAttribute("type", "saturate");
    expect(colorMatrix).toHaveAttribute("values", "0");
    const grainRule = [...style.matchAll(/\.bz-shs-grain\s*\{([^}]*)\}/g)]
      .map((match) => match[1])
      .find((rule) => rule.includes("opacity:"));
    const grainOpacity = grainRule?.match(/opacity:\s*([0-9.]+);/)?.[1];

    expect(grainOpacity).toBeDefined();
    expect(Number(grainOpacity)).toBeGreaterThanOrEqual(0.05);
    expect(style).toContain("mix-blend-mode: soft-light");
  });

  it("places both contour-family centres inside the viewport side bands", () => {
    const { container } = render(<StudioAtmosphere />);
    const bathymetry = container.querySelector(".bz-shs-bathymetry");
    const contours = [...container.querySelectorAll("[data-contour='true']")];
    const centres = new Set(
      contours.map(
        (contour) =>
          `${contour.getAttribute("data-center-x")}:${contour.getAttribute("data-center-y")}`,
      ),
    );

    expect(bathymetry).toHaveAttribute("viewBox", "0 0 1440 900");
    expect(bathymetry).toHaveAttribute("preserveAspectRatio", "none");
    expect(centres).toEqual(new Set(["118:720", "1295:180"]));
    for (const centre of centres) {
      const [x, y] = centre.split(":").map(Number);
      expect(x <= 160 || x >= 1200).toBe(true);
      expect(y).toBeGreaterThanOrEqual(0);
      expect(y).toBeLessThanOrEqual(900);
    }
  });

  it("leaves the existing page atmosphere uncovered", () => {
    const { container } = render(<StudioAtmosphere />);
    const style = container.querySelector("style")?.textContent ?? "";
    const atmosphereRule = style.match(
      /\.bz-shs-atmosphere\s*\{([\s\S]*?)\}/,
    )?.[1];

    expect(atmosphereRule).toBeDefined();
    expect(atmosphereRule).not.toContain("background:");
    expect(style).not.toContain(".bz-shs-atmosphere::before");
  });

  it("does not override the scenario trigger's neutral resting colors", () => {
    const { container } = render(<StudioAtmosphere />);
    const style = container.querySelector("style")?.textContent ?? "";

    expect(style).not.toMatch(
      /\.bz-shs-scenario-toggle-trigger\s*\{[^}]*(?:--accent-funnel|--accent-funnel-text)/s,
    );
  });

  it("removes its scroll-linked movement under reduced motion", () => {
    const { container } = render(<StudioAtmosphere />);
    const style = container.querySelector("style")?.textContent ?? "";

    expect(style).toContain("animation-timeline: scroll(root block)");
    expect(style).toContain("translate3d(0, -5%, 0)");
    expect(style).toMatch(
      /@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)/,
    );
    expect(style).toMatch(
      /@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)[\s\S]*?\.bz-shs-bathymetry\s*\{[\s\S]*?animation:\s*none\s*!important;[\s\S]*?transform:\s*none\s*!important;/,
    );
  });

  it("keeps the viewport-fixed full-bleed layer out of print", () => {
    const { container } = render(<StudioAtmosphere />);
    const style = container.querySelector("style")?.textContent ?? "";

    expect(style).toMatch(
      /\.bz-shs-atmosphere\s*\{[\s\S]*?position:\s*fixed;[\s\S]*?inset:\s*0;/,
    );
    expect(style).toContain("overflow: clip");
    expect(style).toMatch(
      /@media\s+print[\s\S]*?\.bz-shs-atmosphere\s*\{[\s\S]*?display:\s*none\s*!important;/,
    );
  });
});
