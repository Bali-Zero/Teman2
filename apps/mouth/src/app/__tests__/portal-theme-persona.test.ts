import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * The pre-paint persona script is a STRING inside layout.tsx, so nothing type-
 * checks it and no render test reaches it — it runs before React exists. This
 * suite extracts the real string and EXECUTES it against a stubbed document,
 * location and localStorage, so the assertions are about behaviour rather than
 * about the source text happening to contain a substring.
 *
 * Guarded defect (measured live 2026-09-10): persona was derived from the
 * hostname alone, so `/portal/login-upgraded` served from anything that is not
 * literally `my.` rendered with the editorial NIGHT palette — dark on
 * 127.0.0.1, cream on production, for byte-identical code. The authenticated
 * portal pinned operative-light in its own CSS and so looked correct, which is
 * what kept the split hidden: only the unauthenticated screens diverged.
 */

const layoutSource = readFileSync(join(__dirname, "..", "layout.tsx"), "utf8");

function extractThemeInitScript(): string {
  const match = layoutSource.match(/const themeInitScript = `([\s\S]*?)`;/);
  if (!match) {
    throw new Error(
      "themeInitScript not found in layout.tsx — the persona script was renamed or reshaped; update this test rather than deleting it.",
    );
  }
  return match[1];
}

function runPersonaScript(options: {
  host: string;
  path: string;
  stored?: string | null;
}): { product?: string; theme?: string } {
  const dataset: Record<string, string> = {};
  const localStorage = {
    getItem: (key: string) =>
      key === "bz-theme" ? (options.stored ?? null) : null,
  };
  const location = { hostname: options.host, pathname: options.path };
  const document = { documentElement: { dataset } };

  // eslint-disable-next-line @typescript-eslint/no-implied-eval, no-new-func
  new Function(
    "localStorage",
    "location",
    "document",
    extractThemeInitScript(),
  )(localStorage, location, document);

  return { product: dataset.product, theme: dataset.theme };
}

describe("pre-paint persona script", () => {
  describe("GUILT — the portal is the client persona on ANY host", () => {
    it.each([
      ["127.0.0.1", "/portal"],
      ["127.0.0.1", "/portal/login-upgraded"],
      ["localhost", "/portal/magic-link"],
      ["localhost", "/portal/register"],
      ["mouth-git-main-nuzantara-2026.vercel.app", "/portal/vault"],
    ])(
      "serves operative-light for %s%s (this failed before the path check)",
      (host, path) => {
        expect(runPersonaScript({ host, path })).toEqual({
          product: "my",
          theme: "operative-light",
        });
      },
    );
  });

  describe("INNOCENCE — every other persona is untouched", () => {
    it("keeps production my.balizero.com on operative-light", () => {
      expect(
        runPersonaScript({ host: "my.balizero.com", path: "/portal" }),
      ).toEqual({ product: "my", theme: "operative-light" });
    });

    it("keeps the public editorial site dark-by-design", () => {
      expect(
        runPersonaScript({ host: "balizero.com", path: "/blog/anything" }),
      ).toEqual({ product: "editorial", theme: "editorial" });
    });

    it("does not turn a non-portal path on a plain host into the portal", () => {
      expect(
        runPersonaScript({ host: "127.0.0.1", path: "/portal-news" }),
      ).toEqual({ product: "editorial", theme: "editorial" });
    });

    it("keeps kita on its day mode", () => {
      expect(
        runPersonaScript({ host: "kita.balizero.com", path: "/clients" }),
      ).toEqual({ product: "kita", theme: "operative-light" });
    });

    it("keeps prime on operative-dark — the 3D maps are designed for it", () => {
      expect(
        runPersonaScript({ host: "prime.balizero.com", path: "/" }),
      ).toEqual({ product: "kita", theme: "operative-dark" });
    });
  });

  describe("the client's own choice still wins over the default", () => {
    it("honours a stored dark preference inside the portal", () => {
      expect(
        runPersonaScript({
          host: "my.balizero.com",
          path: "/portal",
          stored: "dark",
        }),
      ).toEqual({ product: "my", theme: "operative-dark" });
    });

    it("honours a stored light preference inside the portal", () => {
      expect(
        runPersonaScript({
          host: "127.0.0.1",
          path: "/portal",
          stored: "light",
        }),
      ).toEqual({ product: "my", theme: "operative-light" });
    });
  });

  it("falls back to editorial when the environment throws", () => {
    const dataset: Record<string, string> = {};
    const throwingStorage = {
      getItem: () => {
        throw new Error("localStorage blocked");
      },
    };
    // eslint-disable-next-line @typescript-eslint/no-implied-eval, no-new-func
    new Function(
      "localStorage",
      "location",
      "document",
      extractThemeInitScript(),
    )(
      throwingStorage,
      { hostname: "my.balizero.com", pathname: "/portal" },
      { documentElement: { dataset } },
    );
    expect(dataset).toEqual({ product: "editorial", theme: "editorial" });
  });
});
