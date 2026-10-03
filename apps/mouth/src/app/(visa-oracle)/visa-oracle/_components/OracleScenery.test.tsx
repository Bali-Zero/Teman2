/**
 * BUILD-SPEC §8 — decoration-only contract for `OracleScenery`/`AtlasGlyph`/
 * `AtlasBranchCaption` (ORACLE-PROD-20260927). Scenery never decides or
 * implies eligibility and must never itself be reachable by keyboard —
 * every affordance a visitor can act on lives in QuestionScreen/OracleShell.
 * Synthetic scenes only.
 */
import { act, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AtlasScene } from "../_lib/atlas-scenes";
import { AtlasBranchCaption, AtlasGlyph, OracleScenery } from "./OracleScenery";

const STAGE_SCENE: AtlasScene = {
  id: "entry",
  layout: "stage",
  asset: "indonesia.webp",
  labelKey: null,
};

const LANDSCAPE_SCENE: AtlasScene = {
  id: "tourism",
  layout: "landscape",
  asset: "tourism.webp",
  labelKey: "branch.tourism.name",
};

/**
 * `new Image()` never actually loads in jsdom (no real network stack), so
 * `LandscapeArt`'s preload effect would otherwise never resolve either way
 * — this fake resolves deterministically via a microtask so both the
 * success and the error path are reachable without a real asset fetch.
 * A `src` containing "__error__" resolves `onerror`; everything else
 * resolves `onload`, matching how a real `Image` behaves for a bad vs. good
 * URL.
 */
class FakeImage {
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  private _src = "";
  get src(): string {
    return this._src;
  }
  set src(value: string) {
    this._src = value;
    if (value.includes("__error__")) {
      queueMicrotask(() => this.onerror?.());
    } else {
      queueMicrotask(() => this.onload?.());
    }
  }
}

describe("OracleScenery", () => {
  const originalImage = global.Image;

  beforeEach(() => {
    // @ts-expect-error — deliberately a partial test double, not a full DOM Image
    global.Image = FakeImage;
  });

  afterEach(() => {
    global.Image = originalImage;
  });

  it("root is aria-hidden with no focusable descendant (stage)", () => {
    const { container } = render(
      <OracleScenery scene={STAGE_SCENE} motion={true} language="en" />,
    );
    const root = container.querySelector(".oracle-atlas-scenery");
    expect(root).not.toBeNull();
    expect(root).toHaveAttribute("aria-hidden", "true");
    expect(
      container.querySelectorAll(
        "a[href], button, input, select, textarea, [tabindex]",
      ).length,
    ).toBe(0);
  });

  it("root is aria-hidden with no focusable descendant (landscape)", async () => {
    const { container } = render(
      <OracleScenery scene={LANDSCAPE_SCENE} motion={true} language="en" />,
    );
    await act(async () => {});
    const root = container.querySelector(".oracle-atlas-scenery");
    expect(root).toHaveAttribute("aria-hidden", "true");
    expect(
      container.querySelectorAll(
        "a[href], button, input, select, textarea, [tabindex]",
      ).length,
    ).toBe(0);
  });

  it("renders the stage map markup for a stage scene, not the landscape scene-art", () => {
    const { container } = render(
      <OracleScenery scene={STAGE_SCENE} motion={false} language="en" />,
    );
    expect(container.querySelector(".oracle-atlas-map-stage")).not.toBeNull();
    expect(container.querySelector(".oracle-atlas-scene-art")).toBeNull();
  });

  it("the entry scene never mounts the permit art (FIX-ROUND-2 K1/Q2)", () => {
    const { container } = render(
      <OracleScenery scene={STAGE_SCENE} motion={false} language="en" />,
    );
    const permitSrcs = Array.from(
      container.querySelectorAll<HTMLImageElement>("img"),
    ).map((img) => img.getAttribute("src") ?? "");
    expect(permitSrcs.some((src) => src.includes("permit-"))).toBe(false);
  });

  it("the world scene mounts the permit art ahead of arriving at paper (FIX-ROUND-2 K1/Q2)", () => {
    const worldScene: AtlasScene = {
      ...STAGE_SCENE,
      id: "world",
      asset: "world.webp",
    };
    const { container } = render(
      <OracleScenery scene={worldScene} motion={false} language="en" />,
    );
    const permitSrcs = Array.from(
      container.querySelectorAll<HTMLImageElement>("img"),
    ).map((img) => img.getAttribute("src") ?? "");
    expect(permitSrcs.some((src) => src.includes("permit-paper.webp"))).toBe(
      true,
    );
  });

  it("renders the landscape scene-art markup for a landscape scene, not the stage map", async () => {
    const { container } = render(
      <OracleScenery scene={LANDSCAPE_SCENE} motion={false} language="en" />,
    );
    await act(async () => {});
    expect(container.querySelector(".oracle-atlas-scene-art")).not.toBeNull();
    expect(container.querySelector(".oracle-atlas-map-stage")).toBeNull();
  });

  it("an image load error leaves no <img> in the landscape art", async () => {
    const errorScene: AtlasScene = {
      ...LANDSCAPE_SCENE,
      asset: "__error__.webp",
    };
    const { container } = render(
      <OracleScenery scene={errorScene} motion={false} language="en" />,
    );
    await act(async () => {});
    expect(
      container.querySelector(".oracle-atlas-scene-art-inner img"),
    ).toBeNull();
  });

  it("a successful load renders the <img>", async () => {
    const { container } = render(
      <OracleScenery scene={LANDSCAPE_SCENE} motion={false} language="en" />,
    );
    await act(async () => {});
    expect(
      container.querySelector(".oracle-atlas-scene-art-inner img"),
    ).not.toBeNull();
  });

  it("a failed load AFTER a success keeps showing the previous image (FIX-ROUND-2 K3)", async () => {
    const { container, rerender } = render(
      <OracleScenery scene={LANDSCAPE_SCENE} motion={false} language="en" />,
    );
    await act(async () => {});
    const img = container.querySelector<HTMLImageElement>(
      ".oracle-atlas-scene-art-inner img",
    );
    expect(img).not.toBeNull();
    expect(img?.src).toContain("tourism.webp");

    const nextErrorScene: AtlasScene = {
      ...LANDSCAPE_SCENE,
      asset: "__error__.webp",
    };
    rerender(
      <OracleScenery scene={nextErrorScene} motion={false} language="en" />,
    );
    await act(async () => {});
    const stillImg = container.querySelector<HTMLImageElement>(
      ".oracle-atlas-scene-art-inner img",
    );
    expect(stillImg).not.toBeNull();
    expect(stillImg?.src).toContain("tourism.webp");
  });

  it("motion off never calls Element.animate, even after the image loads", async () => {
    const animateSpy = vi.fn();
    const originalAnimate = HTMLElement.prototype.animate;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (HTMLElement.prototype as any).animate = animateSpy;
    try {
      render(
        <OracleScenery scene={LANDSCAPE_SCENE} motion={false} language="en" />,
      );
      await act(async () => {});
      expect(animateSpy).not.toHaveBeenCalled();
    } finally {
      HTMLElement.prototype.animate = originalAnimate;
    }
  });
});

describe("AtlasGlyph", () => {
  it("is aria-hidden, not focusable, and always renders a path", () => {
    const { container } = render(<AtlasGlyph category="tourism" />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg).toHaveAttribute("focusable", "false");
    expect(svg?.querySelector("path")).not.toBeNull();
  });

  it("falls back to the 'other' glyph for an unrecognised category", () => {
    const known = render(<AtlasGlyph category="other" />);
    const unknown = render(<AtlasGlyph category="not-a-real-category" />);
    expect(unknown.container.querySelector("path")?.getAttribute("d")).toBe(
      known.container.querySelector("path")?.getAttribute("d"),
    );
  });
});

describe("AtlasBranchCaption", () => {
  it("is aria-hidden and shows the hub line when nothing is previewed", () => {
    const { container, getByText } = render(
      <AtlasBranchCaption category={null} language="en" hub />,
    );
    expect(container.querySelector("aside")).toHaveAttribute(
      "aria-hidden",
      "true",
    );
    expect(getByText("Many directions. One beginning.")).toBeInTheDocument();
  });

  it("shows the chosen branch's line outside the hub variant", () => {
    const { getByText } = render(
      <AtlasBranchCaption category="tourism" language="en" />,
    );
    expect(getByText("Across islands. Into possibility.")).toBeInTheDocument();
  });

  it("renders in Indonesian too", () => {
    const { getByText } = render(
      <AtlasBranchCaption category="work" language="id" />,
    );
    expect(
      getByText("Cakrawala baru bagi kehidupan kerja Anda."),
    ).toBeInTheDocument();
  });
});
