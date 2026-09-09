import { createServer } from "node:http";
import { randomBytes } from "node:crypto";
import { createMagazineFixture, FIXTURE_DATES } from "../../../src/lib/server/magazine-fixture";
import { createLocalMagazineTransport } from "../../../src/lib/server/magazine-transport";
import { createLocalWebsiteReadAuthority, publicApprovalDigest, type PublicReadApproval } from "../../../../bali-zero-magazine/lib/server/website-read-authority";
import { sha256Hex } from "../../../../bali-zero-magazine/lib/server/security";
import { type PublicArticle, type PublicMedia } from "../../../../bali-zero-magazine/lib/contracts/website-read";
import { type MachineHmacKey } from "../../../../bali-zero-magazine/lib/server/hmac";
import { type ReadonlyMediaBucket } from "../../../../bali-zero-magazine/lib/server/verified-media-bytes";

export async function httpSurface() {
  let handler: (request: Request) => Promise<Response> = async () => new Response(null, { status: 503 });
  let origin = "";
  const server = createServer(async (incoming, outgoing) => {
    try {
      // This read-only HTTP proof accepts only bodyless GETs. Reject framing
      // before adapting IncomingMessage to a Fetch Request (which drops GET bodies).
      if (incoming.method !== "GET" || incoming.headers["transfer-encoding"] !== undefined ||
        (incoming.headers["content-length"] !== undefined && incoming.headers["content-length"] !== "0")) {
        outgoing.writeHead(400, { "connection": "close", "cache-control": "no-store" });
        incoming.resume(); outgoing.end(); return;
      }
      const headers = new Headers();
      for (const [name, value] of Object.entries(incoming.headers)) if (value !== undefined) headers.set(name, Array.isArray(value) ? value.join(",") : value);
      const request = new Request(origin + incoming.url, { method: incoming.method, headers });
      const response = await handler(request);
      outgoing.writeHead(response.status, Object.fromEntries(response.headers.entries()));
      outgoing.end(Buffer.from(await response.arrayBuffer()));
    } catch { outgoing.writeHead(500); outgoing.end(); }
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("Test listener unavailable");
  origin = `http://127.0.0.1:${address.port}`;
  return {
    origin, setHandler(next: typeof handler) { handler = next; },
    async close() {
      server.closeAllConnections();
      await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    },
  };
}

// Existing Magazine 1x1 raster test bytes, not generated news imagery.
export const PNG = Uint8Array.from(Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=", "base64"));

/** Hand-authored public projection. Never derive approval from a DB read. */
export function approvedFixtureArticles(): PublicArticle[] {
  const entries = [
    ["fixture-paper-and-type", "A place for paper and type", "A synthetic design note exploring the Journal’s paper, forest and copper palette."],
    ["fixture-room-to-read", "Room to read", "A synthetic editorial note about clear summaries, quiet spacing and a useful reading order."],
    ["fixture-notes-in-the-margin", "Notes in the margin", "This synthetic note was revised to demonstrate a visible amendment and dated revision history."],
  ];
  return entries.map(([slug, title, summary], index) => ({
    slug, title, summary, category: "general", publicationState: "published", visibility: "visible",
    revision: index === 2 ? 2 : 1, lifecycleState: index === 2 ? "amended" : "verified",
    publishedAt: index === 2 ? FIXTURE_DATES.amendment : FIXTURE_DATES.publication,
    updatedAt: index === 2 ? FIXTURE_DATES.amendment : FIXTURE_DATES.publication,
    canonicalUrl: `https://bali-zero-magazine.antonellosiano.chatgpt.site/stories/${slug}`,
    whyItMatters: "This preview demonstrates the reading experience. It is not news or regulatory advice.", image: null,
    evidence: [{ publisher: "Synthetic editorial fixture", citation: "Local design proof; not a news source", url: `https://example.org/${slug}` }],
    revisions: [{ version: 1, publishedAt: FIXTURE_DATES.publication }, ...(index === 2 ? [{ version: 2, publishedAt: FIXTURE_DATES.amendment }] : [])],
  }));
}

export async function localProof() {
  const db = await createMagazineFixture();
  const authority = await httpSurface(), website = await httpSurface();
  const now = Math.floor(Date.now() / 1000);
  const key: MachineHmacKey = { id: "local-ephemeral", secret: randomBytes(32).toString("hex"), notBefore: now - 60, notAfter: now + 3600 };
  const digest = await sha256Hex(PNG);
  const asset: PublicMedia = { slug: "fixture-paper-and-type", version: 1, sha256: digest,
    mimeType: "image/png", byteCount: PNG.length, width: 1, height: 1,
    alt: "One pixel — synthetic local transport proof" };
  db.sqlite.prepare("INSERT INTO assets(sha256, r2_key, mime_type, byte_count, width, height) VALUES (?, ?, 'image/png', ?, 1, 1)")
    .run(digest, `assets/sha256/${digest}.png`, PNG.length);
  db.sqlite.prepare("UPDATE story_asset_references SET asset_sha256 = ? WHERE asset_sha256 = ?").run(digest, "a".repeat(64));
  db.sqlite.prepare("UPDATE asset_sources SET canonical_sha256 = ?, alt_text = ? WHERE asset_id = 'fixture-artwork'").run(digest, asset.alt);
  const articleDigests = Object.fromEntries(await Promise.all(approvedFixtureArticles().map(async (article) => [`${article.slug}/${article.revision}`, await publicApprovalDigest(article)])));
  let approval: PublicReadApproval = {
    approvedEvidenceOrigins: ["https://example.org"], articleDigests,
    mediaDigests: { [`${asset.slug}/${asset.version}`]: await publicApprovalDigest(asset) },
  };
  let bytes = PNG, contentType = "image/png", storageKey = `assets/sha256/${digest}.png`;
  let storedDigest = digest, storedSize = PNG.length;
  let beforeObject: (() => Promise<void>) | undefined;
  const lookups: string[] = [];
  const bucket: ReadonlyMediaBucket = { get: async (requested) => {
    lookups.push(requested);
    await beforeObject?.();
    return { key: storageKey, size: storedSize, httpMetadata: { contentType },
      customMetadata: { sha256: storedDigest, mimeType: "image/png", byteCount: String(storedSize), width: "1", height: "1" },
      arrayBuffer: async () => Uint8Array.from(bytes).buffer,
    };
  } };
  const handler = createLocalWebsiteReadAuthority({ mode: "local-proof", origin: authority.origin, db, bucket, key, approval: () => approval });
  authority.setHandler(handler);
  const transport = createLocalMagazineTransport({ mode: "local-proof", authorityOrigin: authority.origin, websiteOrigin: website.origin, key, approvedEvidenceOrigins: ["https://example.org"] });
  website.setHandler(transport.serveMedia);
  return { db, authority, website, key, asset, handler, transport, bucket, lookups,
    get approval() { return approval; },
    approve(next: PublicReadApproval) { approval = next; },
    object(next: { bytes?: Uint8Array; contentType?: string; key?: string; digest?: string; size?: number; before?: () => Promise<void> }) {
      if (next.bytes) bytes = next.bytes;
      if (next.contentType) contentType = next.contentType;
      if (next.key) storageKey = next.key;
      if (next.digest) storedDigest = next.digest;
      if (next.size) storedSize = next.size;
      beforeObject = next.before;
    },
    async close() { await Promise.all([authority.close(), website.close()]); db.close(); },
  };
}
