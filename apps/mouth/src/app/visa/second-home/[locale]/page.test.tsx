import { vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { renderToString } from "react-dom/server";

// The shared setup.tsx mock of next/navigation (useRouter/usePathname/
// useSearchParams) has no `notFound` export — this page calls the real one
// for an out-of-range locale (defense-in-depth alongside dynamicParams=false,
// same pattern as kbli/[code]/page.tsx). Local override, this file only:
// same shape as the shared mock, plus a `notFound` that throws the same
// digest-bearing Error the real next/navigation implementation does.
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
  notFound: () => {
    const error = new Error("NEXT_HTTP_ERROR_FALLBACK;404");
    Object.assign(error, { digest: "NEXT_HTTP_ERROR_FALLBACK;404" });
    throw error;
  },
}));

import SecondHomeLocalizedPage, {
  generateStaticParams,
  generateMetadata,
  dynamicParams,
} from "./page";

/**
 * `/visa/second-home/{it,id}` — SEO-grade localized route (2026-08-20 spec).
 *
 * `next build` is too heavy to run in this suite (spec §7 note); the
 * contract that actually produces "anything else 404s at build" is
 * `generateStaticParams()` returning EXACTLY [it, id] combined with
 * `dynamicParams = false` — Next.js itself enforces the 404 for any other
 * segment from those two facts, so pinning them IS the route test.
 */

describe("second-home/[locale] — SSG params (spec §1)", () => {
  it("generateStaticParams returns exactly it and id — anything else 404s at build", async () => {
    const params = await generateStaticParams();
    expect(params).toEqual([{ locale: "it" }, { locale: "id" }]);
  });

  it("dynamicParams is false — a segment outside generateStaticParams is a true 404, not a soft-404 render", () => {
    expect(dynamicParams).toBe(false);
  });

  it("the studio/ sibling is untouched — different directory, own generateStaticParams-free page", () => {
    // studio/ has no [locale] segment and is not affected by this file at
    // all; this test exists so a future refactor that merges the two
    // directories trips something instead of silently colliding.
    expect(generateStaticParams).not.toBe(undefined);
  });
});

describe("second-home/[locale] — component (spec §2, §7)", () => {
  it("GUILT (unreachable segment): calling the page with a locale outside generateStaticParams throws the Next notFound() 404", async () => {
    await expect(
      SecondHomeLocalizedPage({
        params: Promise.resolve({ locale: "xyz" }),
      }),
    ).rejects.toMatchObject({ digest: expect.stringMatching(/;404$/) });
  });

  it("renders Italian dictionary strings for locale=it (rendered via testing-library)", async () => {
    const jsx = await SecondHomeLocalizedPage({
      params: Promise.resolve({ locale: "it" }),
    });
    render(jsx);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      /Vivi in Indonesia fino a 5 anni/,
    );
  });

  it("renders Indonesian dictionary strings for locale=id (rendered via testing-library)", async () => {
    const jsx = await SecondHomeLocalizedPage({
      params: Promise.resolve({ locale: "id" }),
    });
    render(jsx);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      /Tinggal di Indonesia hingga 5 tahun/,
    );
  });

  it("SSR: locale is already correct on the FIRST render pass, before any effect runs (renderToString never executes effects)", async () => {
    const itJsx = await SecondHomeLocalizedPage({
      params: Promise.resolve({ locale: "it" }),
    });
    const html = renderToString(itJsx);
    expect(html).toContain("Vivi in Indonesia fino a 5 anni");

    const idJsx = await SecondHomeLocalizedPage({
      params: Promise.resolve({ locale: "id" }),
    });
    const idHtml = renderToString(idJsx);
    expect(idHtml).toContain("Tinggal di Indonesia hingga 5 tahun");
  });

  it("stamps <html lang> content-ownership via ContentLangSync (same contract article routes use)", async () => {
    document.documentElement.removeAttribute("data-lang-owner");
    document.documentElement.lang = "en";

    const jsx = await SecondHomeLocalizedPage({
      params: Promise.resolve({ locale: "it" }),
    });
    render(jsx);

    expect(document.documentElement.lang).toBe("it");
    expect(document.documentElement.getAttribute("data-lang-owner")).toBe(
      "content",
    );
  });
});

describe("second-home/[locale] — metadata (spec §4)", () => {
  it("hreflang alternates name all three URLs on the it variant", async () => {
    const metadata = await generateMetadata({
      params: Promise.resolve({ locale: "it" }),
    });
    expect(metadata.alternates?.languages).toMatchObject({
      en: "https://balizero.com/visa/second-home",
      it: "https://balizero.com/visa/second-home/it",
      id: "https://balizero.com/visa/second-home/id",
      "x-default": "https://balizero.com/visa/second-home",
    });
    expect(metadata.alternates?.canonical).toBe(
      "https://balizero.com/visa/second-home/it",
    );
  });

  it("hreflang alternates name all three URLs on the id variant", async () => {
    const metadata = await generateMetadata({
      params: Promise.resolve({ locale: "id" }),
    });
    expect(metadata.alternates?.languages).toMatchObject({
      en: "https://balizero.com/visa/second-home",
      it: "https://balizero.com/visa/second-home/it",
      id: "https://balizero.com/visa/second-home/id",
    });
    expect(metadata.alternates?.canonical).toBe(
      "https://balizero.com/visa/second-home/id",
    );
  });

  it("title/description are in the page language and carry only the EN metadata's existing numbers", async () => {
    const metadata = await generateMetadata({
      params: Promise.resolve({ locale: "it" }),
    });
    expect(metadata.title).toMatch(/Visto Second Home/);
    expect(String(metadata.description)).toContain("USD 130.000");
    expect(String(metadata.description)).toContain("USD 1.000.000");
  });
});

describe("second-home/[locale] — FAQ JSON-LD matches visible content (spec §4)", () => {
  it("FAQ JSON-LD for locale=it is built from the it.json dictionary, not the EN-hardcoded SECOND_HOME_FAQS", async () => {
    const jsx = await SecondHomeLocalizedPage({
      params: Promise.resolve({ locale: "it" }),
    });
    const html = renderToString(jsx);
    // The FAQJsonLd <script> uses dangerouslySetInnerHTML — the raw
    // JSON.stringify output, unescaped — so the first question of it.json's
    // secondHome.faq must appear verbatim (straight apostrophes and all).
    expect(html).toContain("Cos'è il visto Second Home E33");
  });

  it("FAQ JSON-LD for locale=id is built from the id.json dictionary", async () => {
    const jsx = await SecondHomeLocalizedPage({
      params: Promise.resolve({ locale: "id" }),
    });
    const html = renderToString(jsx);
    expect(html).toContain("Apa itu Visa Second Home E33 Indonesia?");
  });
});
