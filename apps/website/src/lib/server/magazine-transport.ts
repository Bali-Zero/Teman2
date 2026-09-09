import "server-only";

// Node-only factory: credentials never enter a client component or URL. The
// existing loader deliberately does not import/arm this local proof transport.
import { randomUUID } from "node:crypto";
import {
  WEBSITE_READ_CONTRACT, WEBSITE_READ_AUDIENCE, READ_PATH, MEDIA_PATH, WEBSITE_MEDIA_PATH,
  MAX_READ_BYTES, MAX_PUBLIC_MEDIA_BYTES, isRecord, hasKeys, isDigest, isPublicArticle,
  isPublicMedia, localOrigin, mediaPath, responseSignatureInput, type WebsiteRead,
} from "../../../../bali-zero-magazine/lib/contracts/website-read";
import { machineSignatureHeaders, type MachineHmacKey } from "../../../../bali-zero-magazine/lib/server/hmac";
import { constantTimeEqualHex, hmacSha256Hex, sha256Hex, publicMediaSecurityHeaders } from "../../../../bali-zero-magazine/lib/server/security";
import { readMagazineFeed, type EditorialFeed } from "../editorial-feed";

function parseSnapshot(value: unknown, origins: readonly string[]): WebsiteRead {
  if (!isRecord(value) || !hasKeys(value, ["contract", "snapshotId", "canonicalAccess", "feed", "media"]) ||
    value.contract !== WEBSITE_READ_CONTRACT || !isDigest(value.snapshotId) || value.canonicalAccess !== "unverified" ||
    !isRecord(value.feed) || !hasKeys(value.feed, ["version", "publisher", "status", "articles", "provenance"])) throw new TypeError();
  const feed = value.feed;
  if (feed.version !== 2 || feed.publisher !== "bali-zero-magazine" || feed.provenance !== "fixture" || !Array.isArray(feed.articles) || feed.articles.length > 100 ||
    !["ready", "empty", "withdrawn", "unpublished", "unavailable", "malformed"].includes(feed.status as string)) throw new TypeError();
  if ((feed.status === "ready") !== (feed.articles.length > 0) || !feed.articles.every((article) => isPublicArticle(article, origins))) throw new TypeError();
  if (!Array.isArray(value.media) || value.media.length > feed.articles.length) throw new TypeError();
  const seen = new Set<string>();
  for (const media of value.media) {
    if (!isPublicMedia(media) || seen.has(media.slug) || !feed.articles.some((article) => article.slug === media.slug && article.revision === media.version)) throw new TypeError();
    seen.add(media.slug);
  }
  return value as unknown as WebsiteRead;
}

async function boundedBytes(response: Response, limit: number): Promise<Uint8Array> {
  const length = response.headers.get("content-length");
  if (length === null || !/^\d+$/.test(length) || Number(length) > limit || response.headers.has("content-encoding") || !response.body) throw new TypeError();
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const item = await reader.read();
      if (item.done) break;
      size += item.value.length;
      if (size > limit) throw new TypeError();
      chunks.push(item.value);
    }
    if (size !== Number(length)) throw new TypeError();
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
    return bytes;
  } finally { await reader.cancel(); }
}

export type LocalMagazineRead = Readonly<{ snapshotId: string | null; feed: EditorialFeed }>;

export function createLocalMagazineTransport(options: Readonly<{
  mode: "local-proof";
  authorityOrigin: string;
  websiteOrigin: string;
  key: MachineHmacKey;
  approvedEvidenceOrigins: readonly string[];
  timeoutMs?: number;
}>): Readonly<{
  read(): Promise<LocalMagazineRead>;
  serveMedia(request: Request): Promise<Response>;
}> {
  const origin = localOrigin(options.authorityOrigin), websiteOrigin = localOrigin(options.websiteOrigin);
  const timeoutMs = options.timeoutMs ?? 3000;
  if (options.mode !== "local-proof" || !/^[a-f0-9]{64}$/.test(options.key.secret) ||
    !Number.isSafeInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 10000) throw new TypeError("Local proof configuration required");
  async function get(path: string, limit: number, mime: "application/json" | "image/png"): Promise<Uint8Array> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const nonce = randomUUID();
      const request = new Request(origin + path, {
        method: "GET", headers: { "content-type": "application/json" },
        redirect: "error", cache: "no-store", signal: controller.signal,
      });
      const signature = await machineSignatureHeaders(request, {
        timestamp: String(Math.floor(Date.now() / 1000)), nonce,
        keyId: options.key.id, secret: options.key.secret, audience: WEBSITE_READ_AUDIENCE,
      });
      for (const [name, value] of Object.entries(signature)) request.headers.set(name, value);
      const response = await fetch(request);
      if (response.status !== 200 || response.url !== origin + path || response.headers.get("content-type") !== mime ||
        response.headers.get("cache-control") !== "private, no-store" || response.headers.get("cross-origin-resource-policy") !== "same-origin" ||
        response.headers.get("x-content-type-options") !== "nosniff") throw new TypeError();
      const bytes = await boundedBytes(response, limit);
      const expected = await hmacSha256Hex(options.key.secret, responseSignatureInput(path, nonce, response.status, mime, await sha256Hex(bytes)));
      if (!constantTimeEqualHex(expected, response.headers.get("x-magazine-response-signature") ?? "")) throw new TypeError();
      return bytes;
    } finally { clearTimeout(timeout); }
  }
  const snapshot = async (): Promise<WebsiteRead> => parseSnapshot(
    JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(await get(READ_PATH, MAX_READ_BYTES, "application/json"))), options.approvedEvidenceOrigins,
  );
  return {
    async read() {
      try {
        const result = await snapshot();
        // The same v2 decoder consumed by loadJournalFeed remains authoritative.
        const feed = await readMagazineFeed(async () => result.feed, { allowFixture: true, approvedEvidenceOrigins: options.approvedEvidenceOrigins });
        if (feed.status !== "ready") return { snapshotId: result.snapshotId, feed };
        return { snapshotId: result.snapshotId, feed: { ...feed, articles: feed.articles.map((article) => {
          const media = result.media.find((item) => item.slug === article.slug && item.version === article.editorial?.revision);
          return { ...article, image: media ? { src: mediaPath(WEBSITE_MEDIA_PATH, result.snapshotId, media), alt: media.alt } : null };
        }) } };
      } catch { return { snapshotId: null, feed: { status: "unavailable", articles: [], rejected: 0 } }; }
    },
    async serveMedia(request) {
      const failure = () => new Response(null, { status: 404, headers: publicMediaSecurityHeaders() });
      try {
        const url = new URL(request.url);
        if (request.method !== "GET" || url.origin !== websiteOrigin || !url.pathname.startsWith(`${WEBSITE_MEDIA_PATH}/`)) return failure();
        const result = await snapshot();
        const media = result.media.find((item) => mediaPath(WEBSITE_MEDIA_PATH, result.snapshotId, item) === url.pathname + url.search);
        if (!media) return failure();
        const bytes = await get(mediaPath(MEDIA_PATH, result.snapshotId, media), MAX_PUBLIC_MEDIA_BYTES, "image/png");
        if (bytes.length !== media.byteCount || await sha256Hex(bytes) !== media.sha256 || bytes.length < 33 ||
          ![137, 80, 78, 71, 13, 10, 26, 10, 0, 0, 0, 13, 73, 72, 68, 82].every((byte, index) => bytes[index] === byte)) return failure();
        const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
        if (view.getUint32(16) !== media.width || view.getUint32(20) !== media.height) return failure();
        // Known reviewed canonical PNG bytes, not a URL proxy or a decoder.
        // Original ingress performs full decode/re-encode; no new media writer.
        return new Response(Uint8Array.from(bytes).buffer, { headers: publicMediaSecurityHeaders({
          "Content-Type": "image/png", "Content-Length": String(bytes.length),
        }) });
      } catch { return failure(); }
    },
  };
}
