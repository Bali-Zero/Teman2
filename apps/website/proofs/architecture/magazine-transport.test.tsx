import { afterEach, describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { request as nodeRequest } from "node:http";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { JsxEmit, ModuleKind, transpileModule } from "typescript";
import * as storageVerifier from "../../../bali-zero-magazine/lib/server/verified-media-bytes";
import * as security from "../../../bali-zero-magazine/lib/server/security";
import * as eligibility from "../../../bali-zero-magazine/lib/server/asset-eligibility";
import { JournalIndex } from "../../src/components/journal/JournalIndex";
import { createLocalMagazineTransport } from "../../src/lib/server/magazine-transport";
import { MagazineFixtureDatabase, quarantineFixtureStory } from "../../src/lib/server/magazine-fixture";
import { createPublicationRepository, type D1DatabaseLike } from "../../../bali-zero-magazine/lib/server/publication-repository";
import { createLocalWebsiteReadAuthority, readWebsiteSnapshot, publicApprovalDigest, WEBSITE_SNAPSHOT_SQL } from "../../../bali-zero-magazine/lib/server/website-read-authority";
import { verifiedObjectBytes } from "../../../bali-zero-magazine/lib/server/verified-media-bytes";
import { machineSignatureHeaders } from "../../../bali-zero-magazine/lib/server/hmac";
import { sha256Hex } from "../../../bali-zero-magazine/lib/server/security";
import { READ_PATH, MEDIA_PATH, MAX_READ_BYTES, WEBSITE_READ_AUDIENCE, mediaPath } from "../../../bali-zero-magazine/lib/contracts/website-read";
import { localProof, PNG, approvedFixtureArticles } from "./magazine/http-fixture";

const proofs: Awaited<ReturnType<typeof localProof>>[] = [];
afterEach(async () => { await Promise.all(proofs.splice(0).map((proof) => proof.close())); });
async function proof() { const value = await localProof(); proofs.push(value); return value; }
async function signedRequest(p: Awaited<ReturnType<typeof localProof>>, path = READ_PATH, secret = p.key.secret, nonce = crypto.randomUUID(), timestamp = String(Math.floor(Date.now() / 1000))) {
  const request = new Request(p.authority.origin + path, { headers: { "content-type": "application/json" } });
  const headers = await machineSignatureHeaders(request, { keyId: p.key.id, secret, audience: WEBSITE_READ_AUDIENCE, nonce, timestamp });
  for (const [name, value] of Object.entries(headers)) request.headers.set(name, value);
  return request;
}
function revoke(p: Awaited<ReturnType<typeof localProof>>) {
  p.db.sqlite.exec("INSERT INTO asset_status_events(asset_id, status_seq, status, rights_status, reason_code) VALUES ('fixture-artwork', 1, 'verified', 'denied', 'local-proof-revocation')");
}

describe("local authority → authenticated HTTP → existing Website v2 consumer", () => {
  it("reads approved current amendments and renders the existing Journal with mediated raster media", async () => {
    const p = await proof();
    const read = await p.transport.read();
    expect(read.feed.status).toBe("ready");
    expect(read.feed.articles).toHaveLength(3);
    expect(read.feed.articles[2].editorial).toMatchObject({ revision: 2, amended: true, revisions: [{ version: 1 }, { version: 2 }] });
    expect(read.feed.articles[1].image).toBeNull();
    const html = renderToStaticMarkup(<JournalIndex articles={read.feed.articles} status={read.feed.status} fixture />);
    expect(html).toContain("Amended · Revision 2");
    expect(html).toContain("/api/journal-media/fixture-paper-and-type/1/");
    expect(html).not.toContain('href="https://bali-zero-magazine');
    expect(JSON.stringify(read)).not.toMatch(/MUST_NOT_LEAK|root_source|evidence_note|packet_id|claim_id|asset_sources/);
    expect(JSON.stringify(read)).not.toContain(p.key.secret);
    const image = await fetch(p.website.origin + read.feed.articles[0].image!.src);
    expect(image.status).toBe(200);
    expect(image.headers.get("content-type")).toBe("image/png");
    expect(image.headers.get("cache-control")).toBe("no-store");
    expect(image.headers.get("cross-origin-resource-policy")).toBe("same-origin");
    expect(image.headers.get("x-content-type-options")).toBe("nosniff");
    expect(image.headers.get("access-control-allow-origin")).toBeNull();
    expect(new Uint8Array(await image.arrayBuffer())).toEqual(PNG);
    expect(p.lookups).toEqual([`assets/sha256/${p.asset.sha256}.png`]);
    for (const article of read.feed.articles) expect(article.verificationStatus).toBe("development-only");
  });

  it("rejects missing/wrong/expired/replayed credentials over HTTP without a database read", async () => {
    const p = await proof();
    let reads = 0;
    p.authority.setHandler(createLocalWebsiteReadAuthority({ mode: "local-proof", origin: p.authority.origin,
      db: { prepare() { reads++; throw new Error("PRIVATE_DB_FAILURE"); } }, bucket: p.bucket, key: p.key, approval: () => p.approval }));
    expect((await fetch(p.authority.origin + READ_PATH)).status).toBe(401);
    expect((await fetch(await signedRequest(p, READ_PATH, "f".repeat(64)))).status).toBe(401);
    expect((await fetch(await signedRequest(p, READ_PATH, p.key.secret, crypto.randomUUID(), String(Math.floor(Date.now() / 1000) - 40)))).status).toBe(401);
    expect(reads).toBe(0);
    const request = await signedRequest(p);
    await fetch(request.clone());
    expect((await fetch(request)).status).toBe(401);
    expect(reads).toBe(1);
  });

  it.each(["content-length", "chunked"])("rejects signed GET bodies with %s framing before HTTP adaptation", async (framing) => {
    const p = await proof();
    let admitted = 0;
    p.authority.setHandler(async (request) => { admitted++; return p.handler(request); });
    const request = await signedRequest(p);
    const headers = Object.fromEntries(request.headers.entries());
    if (framing === "content-length") headers["content-length"] = "1";
    else headers["transfer-encoding"] = "chunked";
    const status = await new Promise<number>((resolve, reject) => {
      const outgoing = nodeRequest(request.url, { method: "GET", headers }, (incoming) => {
        incoming.resume(); incoming.on("end", () => resolve(incoming.statusCode!));
      });
      outgoing.on("error", reject); outgoing.end("x");
    });
    expect(status).toBe(400);
    expect(admitted).toBe(0);
    request.headers.set("content-length", "1");
    expect((await p.handler(request)).status).toBe(401);
  });

  it("binds authentication to the intended audience and exact path", async () => {
    const p = await proof();
    const request = await signedRequest(p);
    const headers = await machineSignatureHeaders(request, {
      keyId: p.key.id, secret: p.key.secret, audience: "different-local-audience",
      nonce: crypto.randomUUID(), timestamp: String(Math.floor(Date.now() / 1000)),
    });
    expect((await fetch(request.url, { headers: { "content-type": "application/json", ...headers } })).status).toBe(401);
    const valid = await signedRequest(p);
    expect((await fetch(p.authority.origin + MEDIA_PATH, { headers: valid.headers })).status).toBe(401);
  });

  it("uses exactly one read-only prepared statement for a coherent snapshot", async () => {
    const p = await proof();
    const queries: string[] = [];
    const db = { prepare(sql: string) {
      queries.push(sql);
      expect(sql).toBe(WEBSITE_SNAPSHOT_SQL);
      return p.db.prepare(sql);
    } };
    const snapshot = await readWebsiteSnapshot(db, p.approval);
    expect(snapshot.feed.articles).toEqual(approvedFixtureArticles());
    expect(queries).toHaveLength(1);
    expect(queries[0]).not.toMatch(/\b(?:INSERT|UPDATE|DELETE|REPLACE)\b/);
    // Same actual authority heads as legacy public article reads; historic
    // edition placement v1 cannot revive an old current story.
    const repository = createPublicationRepository(p.db);
    for (const article of snapshot.feed.articles) {
      const current = await repository.getCurrentStory(article.slug);
      expect(current?.version).toBe(article.revision);
      expect(current?.title).toBe(article.title);
    }
  });

  it("binds one captured statement state, then rejects its media after a later withdrawal", async () => {
    const p = await proof();
    let mutated = false;
    const db = { prepare(sql: string) {
      const statement = p.db.prepare(sql);
      return { ...statement, bind: statement.bind.bind(statement), run: statement.run.bind(statement), all: statement.all.bind(statement),
        first: async <T,>() => {
          const captured = await statement.first<T>();
          if (!mutated) { mutated = true; quarantineFixtureStory(p.db, "fixture-paper-and-type"); }
          return captured;
        },
      };
    } } as Pick<D1DatabaseLike, "prepare">;
    const captured = await readWebsiteSnapshot(db, p.approval);
    expect(captured.feed.articles).toHaveLength(3); // coherent state before withdrawal
    const next = await p.transport.read();
    expect(next.feed.articles).toHaveLength(2);
    expect(next.snapshotId).not.toBe(captured.snapshotId);
    expect((await fetch(await signedRequest(p, mediaPath(MEDIA_PATH, captured.snapshotId, captured.media[0])))).status).toBe(409);
  });

  it.each(["withdrawal", "rights", "public-approval"])("rejects %s during the asynchronous R2 read", async (change) => {
    const p = await proof();
    const read = await p.transport.read();
    p.object({ before: async () => {
      if (change === "withdrawal") quarantineFixtureStory(p.db, "fixture-paper-and-type");
      else if (change === "rights") revoke(p);
      else p.approve({ ...p.approval, mediaDigests: {} });
    } });
    const response = await fetch(p.website.origin + read.feed.articles[0].image!.src);
    expect(response.status).toBe(404);
    expect((await response.arrayBuffer()).byteLength).toBe(0);
  });

  it("new reads remove revoked media and old URLs cannot return stored bytes", async () => {
    const p = await proof();
    const old = await p.transport.read();
    revoke(p);
    const current = await p.transport.read();
    expect(current.feed.status).toBe("ready");
    expect(current.feed.articles[0].image).toBeNull();
    expect(current.snapshotId).not.toBe(old.snapshotId);
    expect((await fetch(p.website.origin + old.feed.articles[0].image!.src)).status).toBe(404);
    expect(p.lookups).toEqual([]);
  });

  it("rejects a pointer to a superseded edition rather than falling back", async () => {
    const p = await proof();
    const read = await p.transport.read();
    // Local corruption simulation: a superseded pointer must not silently
    // fall back to any other published edition or a historical feed.
    p.db.sqlite.exec("UPDATE editions SET publication_state = 'superseded'");
    expect((await p.transport.read()).feed).toMatchObject({ status: "malformed", articles: [] });
    expect((await fetch(p.website.origin + read.feed.articles[0].image!.src)).status).toBe(404);
  });

  it("follows a newly finalized quiet edition and invalidates previous edition media", async () => {
    const p = await proof();
    const old = await p.transport.read();
    const repository = createPublicationRepository(p.db, { now: () => "2026-09-03T08:00:00.000Z" });
    const packet = {
      schema_version: "edition.v1" as const, packet_id: "fixture-next-quiet-edition",
      editor_version: "fixture.v1", ruleset_version: "fixture.v1", edition_date: "2026-09-03",
      edition_revision: 2, expected_current_revision: 1, expected_breaking_revision: 2,
      edition_kind: "quiet" as const, publication_state: "building" as const, coverage_state: "complete" as const,
      readiness_cutoff: "2026-09-03T08:00:00.000Z", verified_at: "2026-09-03T08:00:00.000Z",
      collector_run_ids: [], stories: [], placements: [], breaking_story_ids: [],
      referenced_claim_ids: [], referenced_evidence_ids: [], asset_digests: [], coverage_gaps: [], reader_notices: [],
    };
    await repository.stageEdition(packet, "e".repeat(64));
    // A staged composer output is not the published current edition.
    expect((await p.transport.read()).feed.articles).toHaveLength(3);
    await repository.finalizeEdition(packet.packet_id);
    const current = await p.transport.read();
    expect(current.feed).toMatchObject({ status: "empty", articles: [] });
    expect(current.snapshotId).not.toBe(old.snapshotId);
    expect((await fetch(p.website.origin + old.feed.articles[0].image!.src)).status).toBe(404);
  });

  it.each([
    "UPDATE stories SET current_version = 999 WHERE slug = 'fixture-paper-and-type'",
    "UPDATE story_versions SET published_at = NULL WHERE story_id = 'fixture-paper-and-type'",
    "UPDATE story_versions SET published_at = '2026-02-30T08:00:00Z' WHERE story_id = 'fixture-paper-and-type'",
    "UPDATE story_versions SET lifecycle_state = 'superseded' WHERE story_id = 'fixture-paper-and-type'",
    "UPDATE edition_pointer SET current_edition_id = 'missing-edition'",
    "UPDATE story_evidence SET publication_state = 'building' WHERE story_id = 'fixture-paper-and-type'",
    "UPDATE story_claims SET publication_state = 'building' WHERE story_id = 'fixture-paper-and-type'",
    "DELETE FROM edition_entries WHERE story_id = 'fixture-paper-and-type'",
  ])("fails malformed without raw text or invented dates: %s", async (sql) => {
    const p = await proof(); p.db.sqlite.exec(sql);
    expect((await p.transport.read()).feed).toMatchObject({ status: "malformed", articles: [] });
  });

  it.each([
    "UPDATE evidence_refs SET document_citation = 'PRIVATE_PERSON_CITATION' WHERE evidence_id = 'fixture-paper-and-type-evidence'",
    "UPDATE evidence_refs SET canonical_url = 'https://example.org/private-person' WHERE evidence_id = 'fixture-paper-and-type-evidence'",
    "UPDATE evidence_refs SET publisher = 'PRIVATE_PERSON_NAME' WHERE evidence_id = 'fixture-paper-and-type-evidence'",
    "UPDATE story_versions SET summary = 'PRIVATE_PERSON_SUMMARY' WHERE story_id = 'fixture-paper-and-type'",
  ])("same approved origin never approves changed public prose/path: %s", async (sql) => {
    const p = await proof(); p.db.sqlite.exec(sql);
    const response = await fetch(await signedRequest(p));
    const payload = await response.text();
    expect(payload).not.toContain("PRIVATE_PERSON");
    expect(JSON.parse(payload).feed).toMatchObject({ status: "unavailable", articles: [] });
  });

  it("does not issue public text without explicit exact projection approvals", async () => {
    const p = await proof(); p.approve({ ...p.approval, articleDigests: {} });
    expect((await p.transport.read()).feed).toMatchObject({ status: "unavailable", articles: [] });
  });

  it.each(["https://example.org/path?token=PRIVATE", "https://name:password@example.org/path", "https://example.org/path#PRIVATE", "https://unapproved.example/path"])("rejects unsafe evidence URL %s", async (url) => {
    const p = await proof();
    p.db.sqlite.prepare("UPDATE evidence_refs SET canonical_url = ? WHERE evidence_id = 'fixture-paper-and-type-evidence'").run(url);
    expect((await p.transport.read()).feed.status).toBe("malformed");
  });

  it("distinguishes valid empty, unpublished and withdrawn states", async () => {
    const p = await proof();
    const fresh = new MagazineFixtureDatabase();
    try { expect((await readWebsiteSnapshot(fresh, p.approval)).feed.status).toBe("empty"); } finally { fresh.close(); }
    for (const article of approvedFixtureArticles()) quarantineFixtureStory(p.db, article.slug);
    expect((await p.transport.read()).feed).toMatchObject({ status: "withdrawn", articles: [] });
    for (const article of approvedFixtureArticles()) quarantineFixtureStory(p.db, article.slug, 2, false);
    p.db.sqlite.exec("UPDATE story_versions SET publication_state = 'building' WHERE story_id <> 'fixture-withdrawn'");
    expect((await p.transport.read()).feed).toMatchObject({ status: "withdrawn", articles: [] });
    quarantineFixtureStory(p.db, "fixture-withdrawn", 2, false);
    p.db.sqlite.exec("UPDATE story_versions SET publication_state = 'building'");
    expect((await p.transport.read()).feed).toMatchObject({ status: "unpublished", articles: [] });
  });

  it.each(["bytes", "mime", "key"])("existing extracted storage verification rejects %s drift", async (drift) => {
    const p = await proof();
    expect(await verifiedObjectBytes(p.bucket, `assets/sha256/${p.asset.sha256}.png`, p.asset)).toEqual(PNG);
    if (drift === "bytes") p.object({ bytes: Uint8Array.from(PNG, (byte, index) => index === 40 ? byte ^ 1 : byte) });
    if (drift === "mime") p.object({ contentType: "image/svg+xml" });
    if (drift === "key") p.object({ key: "private/arbitrary-object" });
    await expect(verifiedObjectBytes(p.bucket, `assets/sha256/${p.asset.sha256}.png`, p.asset)).rejects.toThrow();
    const read = await p.transport.read();
    expect((await fetch(p.website.origin + read.feed.articles[0].image!.src)).status).toBe(404);
  });

  it("never fetches arbitrary URLs, digests or unpublished story media", async () => {
    const p = await proof();
    for (const path of ["/api/journal-media/https://example.org/a", "/api/media/" + p.asset.sha256, "/api/journal-media/fixture-building/1/" + p.asset.sha256]) {
      expect((await fetch(p.website.origin + path)).status).toBe(404);
    }
    expect(p.lookups).toEqual([]);
  });

  it("rejects SVG bytes even if mislabelled PNG and their hash was explicitly approved", async () => {
    const p = await proof();
    const bytes = new TextEncoder().encode('<svg xmlns="http://www.w3.org/2000/svg"><script>forbidden()</script></svg>');
    const digest = await sha256Hex(bytes), key = `assets/sha256/${digest}.png`;
    const media = { ...p.asset, sha256: digest, byteCount: bytes.length };
    p.db.sqlite.prepare("INSERT INTO assets(sha256, r2_key, mime_type, byte_count, width, height) VALUES (?, ?, 'image/png', ?, 1, 1)").run(digest, key, bytes.length);
    p.db.sqlite.prepare("UPDATE story_asset_references SET asset_sha256 = ? WHERE asset_sha256 = ?").run(digest, p.asset.sha256);
    p.db.sqlite.prepare("UPDATE asset_sources SET canonical_sha256 = ? WHERE asset_id = 'fixture-artwork'").run(digest);
    p.approve({ ...p.approval, mediaDigests: { [`${media.slug}/${media.version}`]: await publicApprovalDigest(media) } });
    p.object({ bytes, key, digest, size: bytes.length });
    const read = await p.transport.read();
    expect(read.feed.status).toBe("ready");
    expect((await fetch(p.website.origin + read.feed.articles[0].image!.src)).status).toBe(404);
  });

  it("runs the existing story-media resolver against the extracted storage verifier without Photon loading", async () => {
    const p = await proof();
    // Execute the actual legacy module with a narrowly stubbed unused encoder.
    // This tests read delivery unchanged; it does not claim an ingress/WASM test.
    const source = readFileSync(resolve(process.cwd(), "../bali-zero-magazine/lib/server/media.ts"), "utf8");
    const code = transpileModule(source, { compilerOptions: { module: ModuleKind.CommonJS, jsx: JsxEmit.React } }).outputText;
    const exports: Record<string, Function> = {};
    const modules: Record<string, unknown> = {
      "@cf-wasm/photon": { PhotonImage: class { constructor() { throw new Error("Encoder outside read proof"); } } },
      "./asset-eligibility.ts": eligibility, "./security.ts": security, "./verified-media-bytes.ts": storageVerifier,
    };
    new Function("require", "exports", code)((name: string) => {
      if (!(name in modules)) throw new Error("Unexpected legacy dependency");
      return modules[name];
    }, exports);
    const result = await exports.resolvePublishedStoryMedia(p.db, p.bucket, p.asset.slug);
    expect(result.bytes).toEqual(PNG);
    revoke(p);
    expect(await exports.resolvePublishedStoryMedia(p.db, p.bucket, p.asset.slug)).toBeNull();
    expect(await exports.resolvePublishedStoryMedia(p.db, p.bucket, "fixture-building")).toBeNull();
    expect(await exports.resolvePublishedStoryMedia(p.db, p.bucket, "fixture-withdrawn")).toBeNull();
  });

  it("exercises the existing canonical metadata function through a local public-route simulation", async () => {
    const p = await proof();
    // Actual page module/metadata code; the read model is deterministically
    // substituted with its real current-story repository contract. Dispatcher,
    // Next middleware and the production host's admission remain untested.
    const source = readFileSync(resolve(process.cwd(), "../bali-zero-magazine/app/stories/[slug]/page.tsx"), "utf8");
    const code = transpileModule(source, { compilerOptions: { module: ModuleKind.CommonJS, jsx: JsxEmit.React } }).outputText;
    const exports: Record<string, Function> = {};
    const notFound = new Error("not-found");
    const repository = createPublicationRepository(p.db);
    new Function("require", "exports", code)((name: string) => {
      if (name === "next/navigation") return { notFound() { throw notFound; } };
      if (name === "@/lib/server/magazine-read-model") return { readStoryDetail: async (slug: string) => {
        const story = await repository.getCurrentStory(slug);
        return story === null ? null : { story };
      } };
      if (name.startsWith("@/components/")) return {};
      throw new Error("Unexpected page dependency");
    }, exports);
    p.website.setHandler(async (request) => {
      const path = new URL(request.url).pathname;
      const slug = path.slice("/stories/".length), props = { params: Promise.resolve({ slug }) };
      const metadata = await exports.generateMetadata(props);
      if (metadata.title === "Story not found | Bali Zero Magazine") {
        await expect(exports.default(props)).rejects.toBe(notFound);
        return new Response(null, { status: 404 });
      }
      expect(metadata.alternates.canonical).toBe(path);
      return Response.json(metadata);
    });
    const path = `/stories/${p.asset.slug}`;
    const initial = await fetch(p.website.origin + path);
    expect(initial.status).toBe(200);
    expect(await initial.json()).toMatchObject({ title: "A place for paper and type | Bali Zero Magazine", alternates: { canonical: path } });
    quarantineFixtureStory(p.db, p.asset.slug);
    expect((await fetch(p.website.origin + path)).status).toBe(404);
    expect((await fetch(p.website.origin + "/stories/fixture-building")).status).toBe(404);
    expect((await fetch(p.website.origin + "/stories/missing")).status).toBe(404);
    expect((await readWebsiteSnapshot(p.db, p.approval)).canonicalAccess).toBe("unverified");
  });

  it("rejects tampered/replayed response signatures and redirects, with no stale fallback", async () => {
    const p = await proof();
    expect((await p.transport.read()).feed.status).toBe("ready");
    const recorded = await p.handler(await signedRequest(p));
    const body = await recorded.arrayBuffer();
    p.authority.setHandler(async () => new Response(body, { headers: recorded.headers }));
    expect((await p.transport.read()).feed).toMatchObject({ status: "unavailable", articles: [] });
    p.authority.setHandler(async () => Response.redirect("https://example.org/", 302));
    expect((await p.transport.read()).feed.status).toBe("unavailable");
  });

  it("rejects changed response bytes while retaining the current request's original signature", async () => {
    const p = await proof();
    p.authority.setHandler(async (request) => {
      const original = await p.handler(request);
      const text = (await original.text()).replace("A place for paper and type", "A place for paper and hype");
      return new Response(text, { headers: original.headers });
    });
    expect((await p.transport.read()).feed).toMatchObject({ status: "unavailable", articles: [] });
  });

  it.each(["oversize", "truncated", "missing-length"])("rejects %s HTTP read boundaries without a stale feed", async (kind) => {
    const p = await proof();
    expect((await p.transport.read()).feed.status).toBe("ready");
    p.authority.setHandler(async (request) => {
      const original = await p.handler(request);
      const headers = new Headers(original.headers);
      const body = await original.arrayBuffer();
      if (kind === "oversize") headers.set("content-length", String(MAX_READ_BYTES + 1));
      if (kind === "truncated") headers.set("content-length", String(body.byteLength + 1));
      if (kind === "missing-length") headers.delete("content-length");
      headers.set("connection", "close");
      return new Response(body, { headers });
    });
    expect((await p.transport.read()).feed).toMatchObject({ status: "unavailable", articles: [] });
  });

  it("fails closed on DB/storage/network timeout and never exposes exceptions", async () => {
    const p = await proof();
    p.authority.setHandler(createLocalWebsiteReadAuthority({ mode: "local-proof", origin: p.authority.origin,
      db: { prepare() { throw new Error("PRIVATE_DATABASE_CREDENTIAL"); } }, bucket: p.bucket, key: p.key, approval: () => p.approval }));
    const read = await p.transport.read();
    expect(read.feed.status).toBe("unavailable");
    expect(JSON.stringify(read)).not.toContain("PRIVATE");
    p.authority.setHandler(async () => { await new Promise((resolve) => setTimeout(resolve, 40)); return new Response("late"); });
    const fast = createLocalMagazineTransport({ mode: "local-proof", authorityOrigin: p.authority.origin, websiteOrigin: p.website.origin, key: p.key, approvedEvidenceOrigins: ["https://example.org"], timeoutMs: 5 });
    expect((await fast.read()).feed.status).toBe("unavailable");
  });

  it("executes the installed Next client server-only barrier before transport dependencies", () => {
    // A bounded guard-semantics proof, not a full negative Next client build.
    // Transpile the actual transport and route its first import through Next's
    // actual compiler alias. The client error must occur before any dependency.
    const require = createRequire(import.meta.url);
    const { createServerOnlyClientOnlyAliases } = require("next/dist/build/create-compiler-aliases.js");
    const source = readFileSync(resolve(process.cwd(), "src/lib/server/magazine-transport.ts"), "utf8");
    const code = transpileModule(source, { compilerOptions: { module: ModuleKind.CommonJS } }).outputText;
    const aliases = createServerOnlyClientOnlyAliases(false);
    const imports: string[] = [];
    expect(() => new Function("require", "exports", code)((name: string) => {
      imports.push(name);
      if (name !== "server-only") throw new Error("Transport dependency reached before guard");
      return require(aliases["server-only$"]);
    }, {})).toThrow(/cannot be imported from a Client Component/);
    expect(imports).toEqual(["server-only"]);
    expect(() => require(createServerOnlyClientOnlyAliases(true)["server-only$"])).not.toThrow();
  });

  it("only accepts explicitly local unarmed configurations", async () => {
    const p = await proof();
    expect(() => createLocalMagazineTransport({ mode: "local-proof", authorityOrigin: "https://bali-zero-magazine.antonellosiano.chatgpt.site", websiteOrigin: p.website.origin, key: p.key, approvedEvidenceOrigins: [] })).toThrow();
    expect(() => createLocalWebsiteReadAuthority({ mode: "local-proof", origin: "http://localhost:1234", db: p.db, bucket: p.bucket, key: p.key, approval: () => p.approval })).toThrow();
    const loader = readFileSync(resolve(process.cwd(), "src/lib/server/journal-feed.ts"), "utf8");
    expect(loader).not.toContain("magazine-transport");
    expect(loader).toContain("WEBSITE_EDITORIAL_FIXTURE");
  });
});
