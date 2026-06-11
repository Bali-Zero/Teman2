import { test, expect, type APIRequestContext } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

/**
 * D12 soft-404 guard (MYTHOS B1).
 *
 * Before the fix, /[category]/[slug] rendered a phantom article page for ANY
 * garbage slug — the slug title-cased into <title>, indexable, an infinite
 * crawlable thin-content surface.
 *
 * After the fix the page (and its generateMetadata) call notFound().
 *
 * NOTE on status codes: this route streams (loading.tsx boundaries exist in
 * the (blog), [category] and [slug] segments), so the HTTP status is
 * committed as 200 BEFORE any page code runs — a true 404 status is
 * architecturally unavailable here. Verified empirically 2026-06-10: even the
 * long-standing isStaticFilePath notFound() returns 200 on this route. What
 * Next.js guarantees instead: the streamed payload carries
 * <meta name="robots" content="noindex"> plus the 404 boundary UI, which
 * keeps phantom URLs out of search indexes. These tests pin that contract,
 * and also accept a true 404 status (if the streaming topology ever changes,
 * they must not break).
 *
 * The describe title contains "page Page" so the CI E2E job
 * (--grep "page Page" in .github/workflows/tests.yml) actually runs it.
 */

const ARTICLES_DIR = path.join(__dirname, "..", "src", "content", "articles");

function firstMdxSlug(folder: string): string | null {
  const dir = path.join(ARTICLES_DIR, folder);
  if (!fs.existsSync(dir)) return null;
  // Real article files only: non-empty kebab slug + ".mdx". Excludes locale
  // variants (slug.id.mdx) and degenerate strays (a literal ".mdx" exists).
  const file = fs
    .readdirSync(dir)
    .sort()
    .find((f) => /^[a-z0-9][a-z0-9-]*\.mdx$/i.test(f));
  return file ? file.replace(/\.mdx$/, "") : null;
}

/**
 * A nonexistent article URL must never be an indexable phantom page:
 * either a true HTTP 404, or a streamed 200 carrying a noindex robots meta
 * and no fabricated title derived from the slug.
 */
async function expectNotIndexablePhantom(
  request: APIRequestContext,
  url: string,
  phantomTitleFragment: string,
): Promise<void> {
  const response = await request.get(url, { timeout: 90_000 });
  const status = response.status();

  if (status === 404) return; // true 404 — strictly better, accept

  expect(status).toBe(200);
  const body = await response.text();
  expect(body).toContain('name="robots" content="noindex"');
  expect(body).not.toContain(phantomTitleFragment);
}

test.describe("article 404 page Page", () => {
  test.describe.configure({ timeout: 120_000 });

  test("unknown slug under a real category is not an indexable phantom", async ({
    request,
  }) => {
    await expectNotIndexablePhantom(
      request,
      "/taxes/totally-nonexistent-slug-xyz-9999",
      // the old soft-404 fabricated this via title-casing the slug
      "Totally Nonexistent",
    );
  });

  test("unknown slug under an unknown category is not an indexable phantom", async ({
    request,
  }) => {
    await expectNotIndexablePhantom(
      request,
      "/foobar/this-page-does-not-exist-42",
      "This Page Does Not Exist",
    );
  });

  test("real article still renders with 200 and no noindex", async ({
    request,
  }) => {
    const slug = firstMdxSlug("immigration");
    test.skip(!slug, "no immigration MDX articles on disk");

    const response = await request.get(`/visas/${slug}`, { timeout: 90_000 });
    expect(response.status()).toBe(200);

    const body = await response.text();
    expect(body).not.toContain('name="robots" content="noindex"');
  });
});
