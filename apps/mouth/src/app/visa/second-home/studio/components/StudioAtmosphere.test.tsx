import { render, screen } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { StudioAtmosphere } from "./StudioAtmosphere";

describe("StudioAtmosphere", () => {
  it("renders identical procedural SVG output across two server renders", () => {
    const firstRender = renderToStaticMarkup(<StudioAtmosphere />);
    const secondRender = renderToStaticMarkup(<StudioAtmosphere />);

    expect(secondRender).toBe(firstRender);
    expect(firstRender.match(/data-contour="true"/g)).toHaveLength(32);
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

  it("uses one static desaturated fractal-noise grain layer at 2.8% opacity", () => {
    const { container } = render(<StudioAtmosphere />);
    const turbulence = container.querySelector("feTurbulence");
    const colorMatrix = container.querySelector("feColorMatrix");
    const filter = container.querySelector("filter");
    const pattern = container.querySelector("pattern");
    const style = container.querySelector("style")?.textContent ?? "";

    expect(turbulence).toHaveAttribute("type", "fractalNoise");
    expect(turbulence).toHaveAttribute("seed", "37");
    expect(filter).toHaveAttribute("filterRes", "180 180");
    expect(pattern).toHaveAttribute("width", "180");
    expect(pattern).toHaveAttribute("height", "180");
    expect(pattern).toHaveAttribute("patternUnits", "userSpaceOnUse");
    expect(colorMatrix).toHaveAttribute("type", "saturate");
    expect(colorMatrix).toHaveAttribute("values", "0");
    expect(style).toContain("opacity: 0.028");
    expect(style).toContain("mix-blend-mode: overlay");
  });

  it("removes its scroll-linked movement under reduced motion", () => {
    const { container } = render(<StudioAtmosphere />);
    const style = container.querySelector("style")?.textContent ?? "";

    expect(style).toContain("animation-timeline: scroll(root block)");
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
