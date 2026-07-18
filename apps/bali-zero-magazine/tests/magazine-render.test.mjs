import assert from "node:assert/strict";
import test from "node:test";

const RAW_STORY_ID = "story_01JZX7Z8P9Q2M4N6R8T0V2W4Y6";
const RAW_QUARANTINED_ID = "story_01JZX7Z8P9Q2M4N6R8T0V2W4Z7";
const RAW_CLAIM_ID = "claim_01JZX7Z8P9Q2M4N6R8T0V2W4Y6";
const RAW_EVIDENCE_ID = "evidence_01JZX7Z8P9Q2M4N6R8T0V2W4Y6";
const RAW_RUN_ID = "run_01JZX7Z8P9Q2M4N6R8T0V2W4Y6";
const RAW_NOTEBOOK_ID = "nb-933509f9-internal";
const RAW_DIGEST = "a".repeat(64);

const storyRows = [
  {
    story_id: RAW_STORY_ID,
    version: 2,
    slug: "bali-visa-evidence-standard",
    language: "en",
    domain: "immigration",
    section: "hero",
    editorial_order: 1,
    severity: "high",
    lifecycle_state: "published",
    title: "Bali visa files move to a stricter evidence standard",
    deck: "A verified document trail now matters earlier in the application cycle.",
    summary:
      "The operational change shifts document checks forward and narrows the margin for incomplete submissions.",
    why_it_matters:
      "Teams must identify missing evidence before a client reaches the submission window.",
    curiosity_text:
      "The overlooked detail: translation dates can change the useful life of a supporting document.",
    coverage_state: "complete",
    confidence: "high",
    first_seen_at: "2026-07-18T00:15:00.000Z",
    updated_at: "2026-07-18T01:20:00.000Z",
    published_at: "2026-07-18T01:30:00.000Z",
    contributing_system_ids_json: JSON.stringify([
      "intel-lake-private-id",
      RAW_NOTEBOOK_ID,
    ]),
    desired_quarantined: 0,
    media_alt_text:
      "A reviewed immigration dossier arranged beside a verification checklist",
  },
  {
    story_id: "story_company_internal",
    version: 1,
    slug: "investment-licensing-sequence",
    domain: "company-investment",
    section: "company-investment",
    editorial_order: 1,
    severity: "medium",
    lifecycle_state: "published",
    title: "Investment licensing now rewards the correct filing sequence",
    deck: "Corporate documents and operational permits must tell the same story.",
    summary: "A sequencing mismatch can delay downstream approvals.",
    why_it_matters: "Company setup teams need one shared readiness view.",
    curiosity_text: null,
    coverage_state: "complete",
    confidence: "high",
    published_at: "2026-07-18T01:30:00.000Z",
    contributing_system_ids_json: "[]",
    desired_quarantined: 0,
    media_alt_text: "Company licensing documents reviewed in sequence",
  },
  {
    story_id: "story_tax_internal",
    version: 1,
    slug: "tax-calendar-cross-check",
    domain: "tax",
    section: "tax",
    editorial_order: 1,
    severity: "medium",
    lifecycle_state: "published",
    title: "The tax calendar needs a second operational cross-check",
    deck: "Filing dates and client evidence windows do not always align.",
    summary: "A cross-check protects the filing window.",
    why_it_matters: "Tax teams can surface missing records before deadlines.",
    curiosity_text:
      "A one-day document lag can turn an apparently complete file into a partial filing record.",
    coverage_state: "partial",
    confidence: "medium",
    published_at: "2026-07-18T01:30:00.000Z",
    contributing_system_ids_json: "[]",
    desired_quarantined: 0,
    media_alt_text: "A tax calendar annotated with document checkpoints",
  },
  {
    story_id: "story_property_internal",
    version: 1,
    slug: "property-rights-review",
    domain: "property",
    section: "property",
    editorial_order: 1,
    severity: "medium",
    lifecycle_state: "published",
    title: "Property reviews put usage rights before the sales narrative",
    deck: "The operational file begins with title, zoning, and permitted use.",
    summary: "Rights verification precedes commercial interpretation.",
    why_it_matters: "Advisers need a grounded file before discussing options.",
    curiosity_text: null,
    coverage_state: "complete",
    confidence: "high",
    published_at: "2026-07-18T01:30:00.000Z",
    contributing_system_ids_json: "[]",
    desired_quarantined: 0,
    media_alt_text: "A land title and zoning map under review",
  },
  {
    story_id: "story_regulation_internal",
    version: 1,
    slug: "regulatory-source-refresh",
    domain: "regulation-compliance",
    section: "regulation-compliance",
    editorial_order: 1,
    severity: "critical",
    lifecycle_state: "published",
    title: "Primary-source refresh changes the compliance watchlist",
    deck: "A newly verified source changes which files require attention first.",
    summary: "The watchlist now follows the verified primary source.",
    why_it_matters: "Compliance owners can prioritize affected client files.",
    curiosity_text: null,
    coverage_state: "complete",
    confidence: "high",
    published_at: "2026-07-18T01:30:00.000Z",
    contributing_system_ids_json: "[]",
    desired_quarantined: 0,
    media_alt_text: "A primary regulation source marked for review",
  },
  {
    story_id: RAW_QUARANTINED_ID,
    version: 1,
    slug: "quarantined-draft",
    domain: "tax",
    section: "tax",
    editorial_order: 2,
    severity: "high",
    lifecycle_state: "published",
    title: "This quarantined title must never render",
    deck: "Hidden by the latest visibility overlay.",
    summary: "Hidden.",
    why_it_matters: "Hidden.",
    curiosity_text: null,
    coverage_state: "complete",
    confidence: "high",
    published_at: "2026-07-18T01:30:00.000Z",
    contributing_system_ids_json: "[]",
    desired_quarantined: 1,
    media_alt_text: "A quarantined editorial asset",
  },
];

const editionRow = {
  edition_id: "edition_2026-07-18_internal_revision_2",
  edition_date: "2026-07-18",
  edition_revision: 2,
  edition_kind: "standard",
  coverage_state: "partial",
  verified_at: "2026-07-18T01:25:00.000Z",
  published_at: "2026-07-18T01:30:00.000Z",
  coverage_gaps_json: JSON.stringify(["One optional tax source is delayed"]),
  reader_notices_json: JSON.stringify(["Partial input coverage"]),
};

const sourceRows = [
  {
    system_id: "intel-lake-private-id",
    display_name: "Intel Lake",
    health: "healthy",
    verified_at: "2026-07-18T01:20:00.000Z",
    run_id: RAW_RUN_ID,
  },
  {
    system_id: RAW_NOTEBOOK_ID,
    display_name: "Notebook Insight",
    health: "delayed",
    verified_at: "2026-07-18T00:50:00.000Z",
    run_id: "run_notebook_internal",
  },
];

const claimRows = [
  {
    claim_id: RAW_CLAIM_ID,
    claim_kind: "fact",
    normalized_text:
      "The reviewed workflow requires supporting evidence before submission readiness is confirmed.",
    numeric_value: null,
    numeric_unit: null,
    as_of: "2026-07-18",
  },
];

const evidenceRows = [
  {
    claim_id: RAW_CLAIM_ID,
    evidence_id: RAW_EVIDENCE_ID,
    root_source_id: "root_source_private",
    canonical_url: "https://example.go.id/verified-guidance",
    publisher: "Directorate General of Immigration",
    document_citation: "Operational guidance, section 4",
    published_at: "2026-07-17T08:00:00.000Z",
    retrieved_at: "2026-07-18T00:10:00.000Z",
    source_type: "official",
    primary_document_status: "primary",
    root_resolution_status: "resolved",
    evidence_note: "Primary guidance verified against the issuing authority.",
  },
];

class FixtureStatement {
  constructor(sql, fixture) {
    this.sql = sql;
    this.fixture = fixture;
    this.values = [];
  }

  bind(...values) {
    this.values = values;
    return this;
  }

  async first() {
    return this.fixture.answer(this.sql, this.values, "first");
  }

  async all() {
    return {
      success: true,
      results: this.fixture.answer(this.sql, this.values, "all") ?? [],
    };
  }

  async run() {
    return { success: true, meta: { changes: 0 } };
  }
}

function createFixtureDb({ quiet = false, empty = false } = {}) {
  const currentEdition = empty
    ? null
    : {
        ...editionRow,
        edition_kind: quiet ? "quiet" : editionRow.edition_kind,
      };
  const fixture = {
    answer(sql, values, mode) {
      if (sql.includes("magazine:current-edition")) return currentEdition;
      if (sql.includes("magazine:edition-by-id")) {
        return values[0] === "2026-07-18" && values[1] === 2
          ? currentEdition
          : null;
      }
      if (sql.includes("magazine:edition-stories")) {
        return quiet ? [] : storyRows;
      }
      if (sql.includes("magazine:active-breaking")) {
        return quiet
          ? []
          : storyRows.filter(
              (story) => story.slug === "regulatory-source-refresh",
            );
      }
      if (sql.includes("magazine:source-status")) return sourceRows;
      if (sql.includes("magazine:story-by-slug")) {
        return values[0] === "bali-visa-evidence-standard"
          ? storyRows[0]
          : null;
      }
      if (sql.includes("magazine:story-contributors")) return sourceRows;
      if (sql.includes("magazine:story-claims")) return claimRows;
      if (sql.includes("magazine:story-evidence")) return evidenceRows;
      if (sql.includes("magazine:story-history")) {
        return [
          {
            version: 2,
            lifecycle_state: "published",
            published_at: "2026-07-18T01:30:00.000Z",
          },
          {
            version: 1,
            lifecycle_state: "superseded",
            published_at: "2026-07-17T01:30:00.000Z",
          },
        ];
      }
      if (sql.includes("magazine:story-assets")) {
        return [
          {
            asset_sha256: RAW_DIGEST,
            alt_text:
              "A reviewed immigration dossier arranged beside a verification checklist",
            status: "verified",
            rights_status: "approved",
          },
        ];
      }
      throw new Error(`Unexpected fixture query (${mode}): ${sql}`);
    },
  };
  return {
    prepare(sql) {
      return new FixtureStatement(sql, fixture);
    },
    async batch() {
      throw new Error("read-only fixture must not batch");
    },
  };
}

function appEnv(db) {
  return {
    ACTOR_KEY_SECRET: "test-actor-key-secret-with-enough-entropy",
    ROLE_ALLOWLIST_JSON: JSON.stringify({
      version: "roles.test.v1",
      analysts: [],
      operators: [],
    }),
    DB: db,
    ASSETS: {
      fetch: async () => new Response("Not found", { status: 404 }),
    },
  };
}

const magazineWorkerPromise = import(
  new URL("../dist/server/index.js", import.meta.url).href
);

async function render(
  pathname,
  { authenticated = true, db = createFixtureDb() } = {},
) {
  const { default: worker } = await magazineWorkerPromise;
  const headers = new Headers({ accept: "text/html" });
  if (authenticated) {
    headers.set("oai-authenticated-user-email", "reader@example.com");
  }
  return worker.fetch(
    new Request(`http://localhost${pathname}`, { headers }),
    appEnv(db),
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

function assertProtectedHtml(response) {
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  assert.equal(response.headers.get("cache-control"), "private, no-store");
  assert.match(
    response.headers.get("content-security-policy") ?? "",
    /default-src 'self'/,
  );
  assert.equal(response.headers.get("x-content-type-options"), "nosniff");
}

function assertNoInternalIdentifiers(html) {
  for (const identifier of [
    RAW_STORY_ID,
    RAW_QUARANTINED_ID,
    RAW_CLAIM_ID,
    RAW_EVIDENCE_ID,
    RAW_RUN_ID,
    RAW_NOTEBOOK_ID,
    RAW_DIGEST,
    "intel-lake-private-id",
    "root_source_private",
  ]) {
    assert.doesNotMatch(html, new RegExp(identifier, "i"));
  }
}

test("magazine front page renders editorial priority, five domains, coverage, and sanitized source status", async () => {
  const response = await render("/");
  assertProtectedHtml(response);
  const html = await response.text();

  assert.match(html, /Bali Zero Magazine/);
  assert.match(html, /18 July 2026/i);
  assert.match(html, /The Morning File/);
  assert.match(html, /Bali visa files move to a stricter evidence standard/);
  assert.match(html, /Breaking/);
  assert.match(html, /Primary-source refresh changes the compliance watchlist/);
  for (const section of [
    "Immigration",
    "Company & Investment",
    "Tax",
    "Property",
    "Regulation & Compliance",
  ]) {
    const encodedSection = section.replaceAll("&", "(?:&|&amp;)");
    assert.match(html, new RegExp(`>${encodedSection}<`, "i"));
  }
  assert.match(html, /The Detail Everyone Missed/);
  assert.match(html, /Source systems/);
  assert.match(html, /Intel Lake/);
  assert.match(html, /Notebook Insight/);
  assert.match(html, /Partial coverage/);
  assert.match(html, /Delayed/);
  assert.ok(
    html.indexOf("The Morning File") < html.indexOf("Source systems"),
    "editorial issue must precede system controls",
  );
  assert.doesNotMatch(html, /This quarantined title must never render/);
  assertNoInternalIdentifiers(html);
});

test("magazine front page omits Breaking and explains quiet and empty publication modes", async () => {
  const quietResponse = await render("/", {
    db: createFixtureDb({ quiet: true }),
  });
  assertProtectedHtml(quietResponse);
  const quietHtml = await quietResponse.text();
  assert.match(quietHtml, /Quiet edition/);
  assert.match(
    quietHtml,
    /No verified developments cleared the publication threshold/i,
  );
  assert.doesNotMatch(quietHtml, /class="breaking-strip"/);

  const emptyResponse = await render("/", {
    db: createFixtureDb({ empty: true }),
  });
  assertProtectedHtml(emptyResponse);
  const emptyHtml = await emptyResponse.text();
  assert.match(emptyHtml, /No published edition yet/i);
  assert.match(emptyHtml, /Source systems/);
  assertNoInternalIdentifiers(emptyHtml);
});

test("story page separates analysis from claim evidence and exposes current revision state without IDs", async () => {
  const response = await render("/stories/bali-visa-evidence-standard");
  assertProtectedHtml(response);
  const html = await response.text();

  assert.match(html, /Bali visa files move to a stricter evidence standard/);
  assert.match(html, /Why it matters/);
  assert.match(html, /Contributing systems/);
  assert.match(html, /Intel Lake/);
  assert.match(html, /Notebook Insight/);
  assert.match(html, /Claims and evidence/);
  assert.match(html, /The reviewed workflow requires supporting evidence/);
  assert.match(html, /Directorate General of Immigration/);
  assert.match(html, /Operational guidance, section 4/);
  assert.match(html, /Supersedes an earlier revision/);
  assert.match(html, /Visible now/);
  assertNoInternalIdentifiers(html);
});

test("edition archive identifies its immutable revision and applies current visibility overlays", async () => {
  const response = await render("/editions/2026-07-18-r2");
  assertProtectedHtml(response);
  const html = await response.text();

  assert.match(html, /Edition archive/);
  assert.match(html, /Immutable revision 2/i);
  assert.match(html, /Current visibility and rights overlays apply/i);
  assert.match(html, /Bali visa files move to a stricter evidence standard/);
  assert.doesNotMatch(html, /This quarantined title must never render/);
  assertNoInternalIdentifiers(html);
});

test("anonymous readers receive a protected shell without editorial data", async () => {
  const response = await render("/", { authenticated: false });
  assertProtectedHtml(response);
  const html = await response.text();
  assert.match(html, /Workspace access required/i);
  assert.doesNotMatch(html, /The Morning File/);
  assert.doesNotMatch(
    html,
    /Bali visa files move to a stricter evidence standard/,
  );
});

test("worker security wrapper mutates protected HTML only", async () => {
  const workerSourceUrl = new URL(
    "../worker/response-security.ts",
    import.meta.url,
  );
  workerSourceUrl.searchParams.set(
    "security-test",
    `${process.pid}-${Date.now()}`,
  );
  const { secureProtectedHtmlResponse } = await import(workerSourceUrl.href);
  const request = new Request("https://magazine.example/", {
    headers: { accept: "text/html" },
  });
  const htmlResponse = secureProtectedHtmlResponse(
    request,
    new Response("<main>Magazine</main>", {
      headers: { "content-type": "text/html; charset=utf-8", etag: "issue-2" },
    }),
  );
  assert.equal(htmlResponse.headers.get("cache-control"), "private, no-store");
  assert.match(
    htmlResponse.headers.get("content-security-policy") ?? "",
    /frame-ancestors 'none'/,
  );
  assert.equal(htmlResponse.headers.get("etag"), "issue-2");

  const jsonResponse = new Response('{"ok":true}', {
    headers: {
      "content-type": "application/json",
      "cache-control": "max-age=60",
    },
  });
  assert.equal(
    secureProtectedHtmlResponse(
      new Request("https://magazine.example/api/machine/collector-runs"),
      jsonResponse,
    ),
    jsonResponse,
  );
  const mediaResponse = new Response("image", {
    headers: {
      "content-type": "image/webp",
      "cross-origin-resource-policy": "same-origin",
    },
  });
  assert.equal(
    secureProtectedHtmlResponse(
      new Request("https://magazine.example/api/media/public-slug"),
      mediaResponse,
    ),
    mediaResponse,
  );
});
