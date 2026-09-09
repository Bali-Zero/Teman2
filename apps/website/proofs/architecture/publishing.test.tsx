import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "node:http";
import { once } from "node:events";
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import matter from "gray-matter";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { Journal } from "../../src/components/Journal";
import { destinations } from "../../src/content/destinations";
import { readEditorialFeed, type EditorialFeed } from "../../src/lib/editorial-feed";

const realFetch = globalThis.fetch;
const temporaryRoot = mkdtempSync(join(tmpdir(), "website-architecture-"));
const sourcePath = fileURLToPath(new URL("../../../mouth/src/content/articles/tech/fintech-payments-indonesia.mdx", import.meta.url));
const raw = readFileSync(sourcePath, "utf8");
const metadata = matter(raw).data;
let legacy: Awaited<ReturnType<typeof import("../../../mouth/src/lib/blog/articles")["getAllArticles"]>>;

beforeAll(async () => {
  mkdirSync(join(temporaryRoot, "src/content/articles/tech"), { recursive: true });
  const folder = join(temporaryRoot, "src/content/articles/tech");
  writeFileSync(join(folder, "fintech-payments-indonesia.mdx"), raw);
  for (const [slug, extra] of [
    ["fixture-draft", 'status: "draft"\npublishedAt: "2026-09-01"'],
    ["fixture-undated", 'status: "published"'],
    ["fixture-hidden", 'status: "published"\nnoIndex: true'],
  ]) {
    writeFileSync(join(folder, `${slug}.mdx`), `---\nslug: "${slug}"\ntitle: "${slug}"\n${extra}\n---\nSynthetic test content.`);
  }
  // The legacy module captures cwd at import. No main content is modified.
  const cwd = vi.spyOn(process, "cwd").mockReturnValue(temporaryRoot);
  vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 503 })));
  try {
    const { getAllArticles } = await import("../../../mouth/src/lib/blog/articles");
    legacy = await getAllArticles();
  } finally {
    cwd.mockRestore();
    vi.unstubAllGlobals();
  }
});

afterAll(() => rmSync(temporaryRoot, { recursive: true, force: true }));

function envelope() {
  const loaded = legacy.articles.find((article) => article.slug === metadata.slug)!;
  // Restore evidence from RAW publishing metadata, not the status-less listing.
  // This is a one-record proof adapter, not a shipped publishing endpoint.
  return { version: 1, articles: [{
    ...loaded,
    publicationState: metadata.status,
    noIndex: metadata.noIndex === undefined ? false : metadata.noIndex,
    publishedAt: metadata.publishedAt,
    coverImage: metadata.coverImage,
  }] };
}

function page(feed: EditorialFeed): string {
  return renderToStaticMarkup(<main>
    <h1>Your next step in Indonesia</h1>
    <a href={destinations.evoa.href}>Explore E-VOA</a>
    <Journal articles={feed.articles} status={feed.status} indexHref={destinations.journal.href} />
  </main>);
}

describe("architecture proof: real publisher, two delivery boundaries", () => {
  it("executes the real MDX reader against an unchanged repository article", () => {
    expect(legacy.articles.find((row) => row.slug === metadata.slug)).toMatchObject({
      title: metadata.title, category: "trends",
    });
    expect(metadata.status).toBe("published");
  });

  it("characterizes the legacy draft leak and missing-date substitution (not approved behavior)", () => {
    expect(legacy.articles.some((row) => row.slug === "fixture-draft")).toBe(true);
    const undated = legacy.articles.find((row) => row.slug === "fixture-undated")!;
    expect(Number.isFinite(new Date(undated.publishedAt).getTime())).toBe(true);
    expect(legacy.articles.some((row) => row.slug === "fixture-hidden")).toBe(false);
  });

  it("refuses the legacy list as an implicitly approved feed", async () => {
    const result = await readEditorialFeed(async () => ({ version: 1, articles: legacy.articles }));
    expect(result.articles).toEqual([]);
    expect(result.rejected).toBe(legacy.articles.length);
  });

  it("renders identical provider-free marketing HTML from direct and real loopback HTTP delivery", async () => {
    const direct = await readEditorialFeed(async () => envelope());
    const server = createServer((_request, response) => {
      response.writeHead(200, { "Content-Type": "application/json" });
      response.end(JSON.stringify(envelope()));
    });
    server.listen(0, "127.0.0.1");
    await once(server, "listening");
    try {
      const address = server.address();
      if (!address || typeof address === "string") throw new Error("Missing proof port");
      const remote = await readEditorialFeed(async () => {
        const response = await realFetch(`http://127.0.0.1:${address.port}/editorial`, { signal: AbortSignal.timeout(3000) });
        if (!response.ok) throw new Error("Publisher unavailable");
        return response.json();
      });
      expect(remote.status).toBe("ready");
      expect(remote).toEqual(direct);
      expect(page(remote)).toBe(page(direct));
      expect(page(remote)).toContain(`https://balizero.com/trends/${metadata.slug}`);
      expect(page(remote)).toContain(`/legacy${metadata.coverImage}`);
      expect(page(remote)).toContain('href="/visa/voa"');
      expect(page(remote)).toContain('href="/journal"');
      expect(page(remote)).not.toContain("Next editorial story");
    } finally {
      server.closeAllConnections();
      await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    }
  });

  it("keeps useful navigation on publisher failure without fake article cards", async () => {
    const empty = await readEditorialFeed(async () => { throw new Error("Publisher down"); });
    const markup = page(empty);
    expect(markup).toContain("The Journal is temporarily unavailable. Please try again later.");
    expect(markup).toContain('href="/journal"');
    expect(markup).toContain('href="/visa/voa"');
    expect(markup).not.toContain('id="feature-image"');
  });
});
