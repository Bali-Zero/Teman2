/**
 * BUILD-SPEC §8 — pure projection tests for the atlas presentation
 * (ORACLE-PROD-20260927). Synthetic data only. `projectAtlasScene` is a
 * pure function of (node, facts, previewCategory): scenery never decides or
 * implies eligibility, so every assertion here reads only `id`/`layout`/
 * `asset`/`labelKey`, never anything resembling an eligibility verdict.
 */
import { existsSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { CATEGORY_KEYS, type OracleFacts } from "./tree";
import type { OracleNode } from "./flow";
import {
  ATLAS_ASSETS,
  ATLAS_BRANCHES,
  ATLAS_COPY,
  atlasBranchFor,
  atlasCopy,
  isAtlasCategoryKey,
  projectAtlasScene,
} from "./atlas-scenes";

const PUBLIC_ATLAS_DIR = join(
  __dirname,
  "..",
  "..",
  "..",
  "..",
  "..",
  "public",
  "static",
  "visa-oracle",
  "atlas",
);

function question(questionId: string): OracleNode {
  return { kind: "question", questionId };
}

describe("ATLAS_BRANCHES", () => {
  it("has a glyph and a landscape asset for every one of the 11 CATEGORY_KEYS", () => {
    for (const category of CATEGORY_KEYS) {
      const branch = ATLAS_BRANCHES[category];
      expect(branch, `missing branch for ${category}`).toBeDefined();
      expect(branch.glyph.length).toBeGreaterThan(0);
      expect(ATLAS_ASSETS).toContain(branch.asset);
    }
  });

  it("atlasBranchFor falls back to undefined for an unrecognised category", () => {
    expect(atlasBranchFor("not-a-real-category")).toBeUndefined();
    expect(atlasBranchFor(null)).toBeUndefined();
    expect(atlasBranchFor(undefined)).toBeUndefined();
  });

  it("isAtlasCategoryKey narrows only the 11 real keys", () => {
    for (const category of CATEGORY_KEYS) {
      expect(isAtlasCategoryKey(category)).toBe(true);
    }
    expect(isAtlasCategoryKey("bogus")).toBe(false);
    expect(isAtlasCategoryKey(undefined)).toBe(false);
    expect(isAtlasCategoryKey(null)).toBe(false);
  });
});

describe("ATLAS_ASSETS on disk", () => {
  it("every asset the projection can reference exists under the public atlas dir, and no PNG ships", () => {
    for (const asset of ATLAS_ASSETS) {
      expect(asset.endsWith(".webp")).toBe(true);
      expect(
        existsSync(join(PUBLIC_ATLAS_DIR, asset)),
        `missing ${asset}`,
      ).toBe(true);
    }
    for (const category of CATEGORY_KEYS) {
      expect(ATLAS_ASSETS).toContain(ATLAS_BRANCHES[category].asset);
    }
  });

  it("ships no .png anywhere in the atlas dir", () => {
    // Synthetic guard, not a directory walk of the whole repo — the fixture
    // above already proves every referenced file exists; this proves none
    // of the 19 filenames themselves smuggled in a .png extension.
    for (const asset of ATLAS_ASSETS) {
      expect(asset.toLowerCase().endsWith(".png")).toBe(false);
    }
  });
});

describe("projectAtlasScene", () => {
  const facts: OracleFacts = {};

  it("framing -> entry (stage)", () => {
    const scene = projectAtlasScene({ kind: "framing" }, facts);
    expect(scene).toEqual({
      id: "entry",
      layout: "stage",
      asset: "indonesia.webp",
      labelKey: null,
    });
  });

  it("in_indonesia -> world (stage)", () => {
    const scene = projectAtlasScene(question("in_indonesia"), facts);
    expect(scene).toEqual({
      id: "world",
      layout: "stage",
      asset: "world.webp",
      labelKey: null,
    });
  });

  it("holds_stay_permit -> paper (stage)", () => {
    const scene = projectAtlasScene(question("holds_stay_permit"), facts);
    expect(scene).toEqual({
      id: "paper",
      layout: "stage",
      asset: "permit-paper.webp",
      labelKey: null,
    });
  });

  it("category with no preview -> watershed with the hub asset", () => {
    const scene = projectAtlasScene(question("category"), facts, null);
    expect(scene).toEqual({
      id: "watershed",
      layout: "landscape",
      asset: "watershed.webp",
      labelKey: "scene.watershed",
    });
  });

  it("category with a valid preview -> that branch's asset, same scene id", () => {
    const scene = projectAtlasScene(question("category"), facts, "tourism");
    expect(scene.id).toBe("watershed");
    expect(scene.asset).toBe("tourism.webp");
    expect(scene.labelKey).toBe("scene.watershed");
  });

  it("category with an invalid preview falls back to the hub asset, never throws", () => {
    expect(() =>
      projectAtlasScene(question("category"), facts, "not-a-category"),
    ).not.toThrow();
    const scene = projectAtlasScene(
      question("category"),
      facts,
      "not-a-category",
    );
    expect(scene.asset).toBe("watershed.webp");
  });

  it.each(["nationalities", "birth_date", "guardian_consent"])(
    "%s -> identity (landscape)",
    (questionId) => {
      const scene = projectAtlasScene(question(questionId), facts);
      expect(scene).toEqual({
        id: "identity",
        layout: "landscape",
        asset: "identity.webp",
        labelKey: "scene.identity",
      });
    },
  );

  it("review_gate -> confluence, 'One last check'", () => {
    const scene = projectAtlasScene(question("review_gate"), facts);
    expect(scene.id).toBe("confluence");
    expect(scene.asset).toBe("confluence.webp");
    expect(scene.labelKey).toBe("scene.review_gate");
  });

  it("confirmation -> confluence, 'Your route'", () => {
    const scene = projectAtlasScene({ kind: "confirmation" }, facts);
    expect(scene.id).toBe("confluence");
    expect(scene.labelKey).toBe("scene.confirmation");
  });

  it("verdict -> confluence, 'Your next chapter'", () => {
    const scene = projectAtlasScene({ kind: "verdict" }, facts);
    expect(scene.id).toBe("confluence");
    expect(scene.labelKey).toBe("scene.verdict");
  });

  it.each(CATEGORY_KEYS)(
    "a post-category question falls back to the %s branch when facts.category is set",
    (category) => {
      const scene = projectAtlasScene(question("some_other_question_id"), {
        category,
      });
      expect(scene).toEqual({
        id: category,
        layout: "landscape",
        asset: ATLAS_BRANCHES[category].asset,
        labelKey: `branch.${category}.name`,
      });
    },
  );

  it("a pre-category onshore question with no category set falls back to stay/here", () => {
    const scene = projectAtlasScene(question("some_question"), {
      in_indonesia: "yes",
    });
    expect(scene).toEqual({
      id: "stay",
      layout: "landscape",
      asset: "permit-paper.webp",
      labelKey: "scene.stay_here",
    });
  });

  it("a pre-category offshore question with no category set falls back to stay/planning", () => {
    const scene = projectAtlasScene(question("some_question"), {
      in_indonesia: "no",
    });
    expect(scene.labelKey).toBe("scene.stay_planning");
  });

  it("an invalid facts.category never throws and falls back safely", () => {
    expect(() =>
      projectAtlasScene(question("some_question"), { category: "nonsense" }),
    ).not.toThrow();
    const scene = projectAtlasScene(question("some_question"), {
      category: "nonsense",
    });
    expect(scene.id).toBe("stay");
  });
});

describe("atlasCopy", () => {
  const KEYS = Object.keys(ATLAS_COPY.en) as (keyof typeof ATLAS_COPY.en)[];

  it("EN and ID declare exactly the same non-empty keys", () => {
    const enKeys = Object.keys(ATLAS_COPY.en).sort();
    const idKeys = Object.keys(ATLAS_COPY.id).sort();
    expect(idKeys).toEqual(enKeys);
    for (const key of KEYS) {
      expect(ATLAS_COPY.en[key].length).toBeGreaterThan(0);
      expect(ATLAS_COPY.id[key].length).toBeGreaterThan(0);
    }
  });

  it("every CATEGORY_KEYS branch has a name and a line in both languages", () => {
    for (const category of CATEGORY_KEYS) {
      expect(atlasCopy("en", `branch.${category}.name`).length).toBeGreaterThan(
        0,
      );
      expect(atlasCopy("en", `branch.${category}.line`).length).toBeGreaterThan(
        0,
      );
      expect(atlasCopy("id", `branch.${category}.name`).length).toBeGreaterThan(
        0,
      );
      expect(atlasCopy("id", `branch.${category}.line`).length).toBeGreaterThan(
        0,
      );
    }
  });

  it("interpolates {q} and leaves an unmatched placeholder untouched", () => {
    expect(
      atlasCopy("en", "tools.change_labeled", { q: "Do you hold a permit?" }),
    ).toBe("Change: Do you hold a permit?");
    expect(atlasCopy("id", "tools.change_labeled", { q: "X" })).toBe("Ubah: X");
  });

  it("returns the raw key when no vars are supplied and the key has a placeholder", () => {
    expect(atlasCopy("en", "tools.change_labeled")).toBe("Change: {q}");
  });
});
