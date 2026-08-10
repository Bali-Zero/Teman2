import fs from "node:fs";
import path from "node:path";

const ROUTE = "/portal/login-upgraded/page";
const CLIENT_ENTRY_SUFFIX = "/src/app/portal/login-upgraded/page.tsx";
const MANIFEST_PATH = path.join(
  ".next",
  "server",
  "app",
  "portal",
  "login-upgraded",
  "page_client-reference-manifest.js",
);
const ROUTE_CHUNK_DIRECTORY = path.join(
  ".next",
  "static",
  "chunks",
  "app",
  "portal",
  "login-upgraded",
);

// Public authentication may reveal its own endpoints. Every other API route is
// denied by default so adding a new internal domain cannot silently bypass a
// stale denylist.
const ALLOWED_ROUTE_PREFIXES = ["/api/auth/"];
const API_ROUTE_PATTERN = /\/api\/[A-Za-z0-9_./?&=${}-]*/g;

function fail(message) {
  console.error(`PUBLIC_LOGIN_BUNDLE_FAIL: ${message}`);
  process.exit(1);
}

if (!fs.existsSync(MANIFEST_PATH)) {
  fail(
    `missing production build manifest ${MANIFEST_PATH}; run next build first`,
  );
}

const manifestSource = fs.readFileSync(MANIFEST_PATH, "utf8");
const assignment = `globalThis.__RSC_MANIFEST[${JSON.stringify(ROUTE)}]=`;
const assignmentStart = manifestSource.indexOf(assignment);
if (assignmentStart === -1) {
  fail(`route assignment ${ROUTE} is absent from ${MANIFEST_PATH}`);
}

const jsonStart = assignmentStart + assignment.length;
const jsonEnd = manifestSource.indexOf(";", jsonStart);
if (jsonEnd === -1) {
  fail(`route assignment ${ROUTE} is malformed in ${MANIFEST_PATH}`);
}

let routeManifest;
try {
  routeManifest = JSON.parse(manifestSource.slice(jsonStart, jsonEnd));
} catch (error) {
  fail(`cannot parse route manifest: ${error.message}`);
}

const clientEntry = Object.entries(routeManifest.clientModules ?? {}).find(
  ([modulePath]) => modulePath.endsWith(CLIENT_ENTRY_SUFFIX),
);
if (!clientEntry) {
  fail(`client entry ${CLIENT_ENTRY_SUFFIX} is absent from route manifest`);
}

const clientEntryChunks = clientEntry[1]?.chunks;
if (!Array.isArray(clientEntryChunks)) {
  fail(`client entry ${CLIENT_ENTRY_SUFFIX} has no chunk list`);
}

let chunkPaths = clientEntryChunks.filter(
  (entry) => typeof entry === "string" && entry.endsWith(".js"),
);

// Vercel can deduplicate the page module and leave its manifest chunk list
// empty even though Next.js emitted the route entry. The route-specific entry
// is the narrow fallback; scanning every clientModules entry would include
// chunks from unrelated authenticated routes.
if (chunkPaths.length === 0 && fs.existsSync(ROUTE_CHUNK_DIRECTORY)) {
  chunkPaths = fs
    .readdirSync(ROUTE_CHUNK_DIRECTORY)
    .filter((entry) => /^page-[A-Za-z0-9]+\.js$/.test(entry))
    .map((entry) =>
      path.join("static", "chunks", "app", "portal", "login-upgraded", entry),
    );
}

if (chunkPaths.length === 0) {
  fail(`route ${ROUTE} resolves to no JavaScript chunks`);
}

const violations = [];
for (const chunkPath of chunkPaths) {
  const assetPath = path.join(".next", chunkPath);
  if (!fs.existsSync(assetPath)) {
    fail(`manifest references missing client asset ${assetPath}`);
  }

  const asset = fs.readFileSync(assetPath, "utf8");
  for (const route of asset.match(API_ROUTE_PATTERN) ?? []) {
    if (!ALLOWED_ROUTE_PREFIXES.some((prefix) => route.startsWith(prefix))) {
      violations.push({ chunk: chunkPath, route });
    }
  }
}

if (violations.length > 0) {
  const evidence = [
    ...new Set(violations.map(({ chunk, route }) => `${route} in ${chunk}`)),
  ].join(", ");
  fail(
    `internal API routes reached the unauthenticated login bundle: ${evidence}`,
  );
}

console.log(
  `PUBLIC_LOGIN_BUNDLE_OK: inspected ${chunkPaths.length} assets; no internal API route prefixes found`,
);
