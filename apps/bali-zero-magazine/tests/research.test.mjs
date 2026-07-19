import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import test from "node:test";

import { authorize } from "../lib/server/authorization.ts";
import {
  createResearchRepository,
  parseResearchCatalog,
  parseResearchRequest,
  parseResearchResult,
} from "../lib/server/research-repository.ts";
import { runWithMagazineBindings } from "../lib/server/runtime-bindings.ts";
import { hmacSha256Hex } from "../lib/server/security.ts";
import {
  SqliteD1Database,
  runtimeBindings,
  signedMachineRequest,
} from "./helpers/task-5-fixtures.mjs";

const routePaths = {
  jobs: new URL("../app/api/research/jobs/route.ts", import.meta.url),
  job: new URL("../app/api/research/jobs/[jobId]/route.ts", import.meta.url),
  claim: new URL(
    "../app/api/machine/research/jobs/claim/route.ts",
    import.meta.url,
  ),
  heartbeat: new URL(
    "../app/api/machine/research/jobs/[jobId]/heartbeat/route.ts",
    import.meta.url,
  ),
  result: new URL(
    "../app/api/machine/research/jobs/[jobId]/result/route.ts",
    import.meta.url,
  ),
  page: new URL("../app/research/page.tsx", import.meta.url),
  detail: new URL("../app/research/jobs/[jobId]/page.tsx", import.meta.url),
};

const catalogRaw = JSON.stringify({
  schema_version: "research-catalog.v1",
  topics: [
    { id: "topic:indonesia-investment", label: "Indonesia investment" },
    { id: "topic:visa-policy", label: "Visa policy" },
  ],
  entities: [
    { id: "entity:bkpm", label: "BKPM" },
    { id: "entity:imigrasi", label: "Directorate General of Immigration" },
  ],
  index_tokens: ["token:foreign-investment", "token:visa-change"],
  source_system_ids: [
    "intel-lake",
    "mata-garuda",
    "regulatory-watcher",
    "notebooklm",
  ],
});

function request(overrides = {}) {
  return {
    schema_version: "research-request.v1",
    mode: "search",
    topic_ids: ["topic:visa-policy"],
    entity_ids: [],
    index_tokens: ["token:visa-change"],
    template: null,
    facets: {
      domains: ["immigration"],
      source_system_ids: ["regulatory-watcher"],
      evidence_types: ["official"],
      confidence: ["normal"],
      lifecycle_states: ["published"],
      languages: ["en"],
    },
    ...overrides,
  };
}

function result(jobId, claim, overrides = {}) {
  return {
    schema_version: "research-result.v1",
    job_id: jobId,
    request_hash: claim.request_hash,
    mode: claim.mode,
    status: "completed",
    completed_at: "2026-07-19T04:30:00.000Z",
    summary: "The official source records a material policy change.",
    claims: [
      {
        claim_id: "claim:visa-change-1",
        kind: "fact",
        text: "The policy change is recorded by the issuing authority.",
        numeric_value: null,
        numeric_unit: null,
        as_of: "2026-07-19",
        evidence: [
          {
            evidence_id: "evidence:official-visa-change",
            publisher: "Directorate General of Immigration",
            citation: "Official policy notice, 19 July 2026",
            canonical_url: "https://www.imigrasi.go.id/",
            source_type: "official",
            published_at: "2026-07-19",
          },
        ],
      },
    ],
    failure: null,
    claim_token: claim.claim_token,
    fencing_token: claim.fencing_token,
    ...overrides,
  };
}

function bindings(db, memberships = {}) {
  return {
    ...runtimeBindings(db),
    RESEARCH_CATALOG_JSON: catalogRaw,
    ROLE_ALLOWLIST_JSON: JSON.stringify({
      version: "roles.research.v1",
      analysts: memberships.analysts ?? [],
      operators: memberships.operators ?? [],
    }),
  };
}

test("research room ships the human and machine boundary routes", () => {
  for (const [name, path] of Object.entries(routePaths)) {
    assert.ok(existsSync(path), `missing ${name} research surface`);
  }
});

test("research detail exposes the closed brief and labels Notebook Insight as synthesis", () => {
  const source = readFileSync(routePaths.detail, "utf8");
  assert.match(source, /Controlled brief/);
  assert.match(source, /Synthesis, not verification/);
  assert.match(
    source,
    /displayed separately from the published evidence corpus/,
  );
  assert.match(source, /publicResearchJob\(storedJob\)/);
});

test("research migration archives legacy rows without retaining raw request or result text", () => {
  const sqlite = new DatabaseSync(":memory:");
  sqlite.exec("PRAGMA foreign_keys = ON");
  const migrationDirectory = new URL("../drizzle/", import.meta.url);
  const migrations = readdirSync(migrationDirectory)
    .filter((name) => /^000[0-4].*\.sql$/.test(name))
    .sort();
  for (const filename of migrations) {
    sqlite.exec(
      readFileSync(new URL(filename, migrationDirectory), "utf8").replaceAll(
        "--> statement-breakpoint",
        "",
      ),
    );
  }
  sqlite
    .prepare(
      "INSERT INTO research_jobs(job_id, actor_key, mode, query_json, status, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
    )
    .run(
      "legacy-job-0000000000000001",
      "legacy-email@example.com",
      "freeform",
      JSON.stringify({
        query: "passport A1234567",
        notebook_uuid: "private-notebook",
      }),
      "done",
      "2026-07-18T04:00:00.000Z",
      "2026-07-20T04:00:00.000Z",
    );
  sqlite
    .prepare(
      "INSERT INTO research_results(result_id, job_id, result_json, result_hash, created_at) VALUES (?, ?, ?, ?, ?)",
    )
    .run(
      "legacy-result-000000000001",
      "legacy-job-0000000000000001",
      JSON.stringify({
        raw_notebook_output: "private client passport A1234567",
      }),
      "f".repeat(64),
      "2026-07-18T04:05:00.000Z",
    );
  sqlite.exec(
    readFileSync(
      new URL("0005_wakeful_obadiah_stane.sql", migrationDirectory),
      "utf8",
    ).replaceAll("--> statement-breakpoint", ""),
  );
  const archived = sqlite
    .prepare(
      "SELECT actor_key, mode, query_json, status FROM research_jobs WHERE job_id = ?",
    )
    .get("legacy-job-0000000000000001");
  assert.equal(archived.actor_key, "0".repeat(64));
  assert.equal(archived.mode, "search");
  assert.equal(archived.status, "cancelled");
  assert.match(archived.query_json, /legacy-archived/);
  assert.doesNotMatch(archived.query_json, /passport|notebook/i);
  assert.equal(
    sqlite.prepare("SELECT count(*) AS count FROM research_results").get()
      .count,
    0,
  );
});

test("closed request schema rejects free text, unknown IDs, notebook UUIDs, and extra keys", () => {
  const catalog = parseResearchCatalog(catalogRaw);
  assert.equal(parseResearchRequest(request(), catalog).mode, "search");
  assert.throws(
    () =>
      parseResearchRequest(
        { ...request(), query: "tell me about a client" },
        catalog,
      ),
    /invalid research request/,
  );
  assert.throws(
    () =>
      parseResearchRequest(request({ topic_ids: ["topic:unknown"] }), catalog),
    /unknown topic/,
  );
  assert.throws(
    () =>
      parseResearchRequest(
        request({
          mode: "notebook_insight",
          template: "explain",
          notebook_uuid: "d9438180-0000-0000-0000-000000000000",
        }),
        catalog,
      ),
    /invalid research request/,
  );
  assert.throws(
    () =>
      parseResearchRequest(
        request({ mode: "notebook_insight", template: "custom-question" }),
        catalog,
      ),
    /invalid template/,
  );
  assert.throws(
    () =>
      parseResearchRequest(
        request({
          mode: "notebook_insight",
          index_tokens: [],
          template: "explain",
          facets: {
            ...request().facets,
            source_system_ids: ["regulatory-watcher"],
          },
        }),
        catalog,
      ),
    /NotebookLM only/,
  );
  assert.throws(
    () =>
      parseResearchRequest(
        request({
          mode: "compare",
          topic_ids: ["topic:visa-policy", "topic:indonesia-investment"],
          entity_ids: ["entity:bkpm"],
        }),
        catalog,
      ),
    /exactly two/,
  );
  assert.throws(
    () =>
      parseResearchRequest(
        request({
          mode: "timeline",
          topic_ids: ["topic:visa-policy", "topic:indonesia-investment"],
        }),
        catalog,
      ),
    /exactly one/,
  );
});

test("catalog can be large while every request selection stays bounded", () => {
  const largeCatalog = parseResearchCatalog(
    JSON.stringify({
      ...JSON.parse(catalogRaw),
      index_tokens: Array.from(
        { length: 500 },
        (_, index) => `token:registered-${index}`,
      ),
    }),
  );
  assert.equal(largeCatalog.index_tokens.length, 500);
  assert.throws(
    () =>
      parseResearchRequest(
        request({
          index_tokens: largeCatalog.index_tokens.slice(0, 9),
        }),
        largeCatalog,
      ),
    /invalid index_tokens/,
  );
});

test("result contract enforces strict dates, numeric provenance, evidence, and total bounds", () => {
  const claim = {
    request_hash: "a".repeat(64),
    mode: "search",
    claim_token: "claim-token-0123456789abcdef",
    fencing_token: 1,
  };
  const numeric = {
    ...result("research-job-0123456789abcdef", claim).claims[0],
    kind: "numeric",
    numeric_value: "25",
    numeric_unit: "percent",
    as_of: null,
  };
  assert.throws(
    () =>
      parseResearchResult(
        result("research-job-0123456789abcdef", claim, { claims: [numeric] }),
      ),
    /as-of date/,
  );
  assert.throws(
    () =>
      parseResearchResult(
        result("research-job-0123456789abcdef", claim, {
          completed_at: "2026-02-30T04:30:00.000Z",
        }),
      ),
    /completed at/,
  );
  assert.doesNotThrow(() =>
    parseResearchResult(
      result("research-job-0123456789abcdef", claim, {
        claims: [{ ...numeric, as_of: "2026-07-19" }],
      }),
    ),
  );
  const oversizedEvidence = Array.from({ length: 12 }, (_, index) => ({
    ...result("research-job-0123456789abcdef", claim).claims[0].evidence[0],
    evidence_id: `evidence:item-${index}`,
    citation: "x".repeat(500),
  }));
  const oversizedClaims = Array.from({ length: 50 }, (_, index) => ({
    ...result("research-job-0123456789abcdef", claim).claims[0],
    claim_id: `claim:item-${index}`,
    text: "x".repeat(1200),
    evidence: oversizedEvidence,
  }));
  assert.throws(
    () =>
      parseResearchResult(
        result("research-job-0123456789abcdef", claim, {
          claims: oversizedClaims,
        }),
      ),
    /size limit/,
  );
});

test("role matrix keeps create privilege analyst-only", () => {
  const allowlist = {
    version: "roles.research.v1",
    analysts: ["a".repeat(64)],
    operators: ["b".repeat(64)],
  };
  assert.equal(
    authorize(
      {
        actorKey: "a".repeat(64),
        role: "analyst",
        roleConfigVersion: allowlist.version,
      },
      "research:create",
      allowlist,
    ).allowed,
    true,
  );
  assert.equal(
    authorize(
      {
        actorKey: "b".repeat(64),
        role: "operator",
        roleConfigVersion: allowlist.version,
      },
      "research:create",
      allowlist,
    ).allowed,
    false,
  );
});

test("repository provides idempotent create, atomic lease claim, heartbeat, and result CAS", async () => {
  const db = new SqliteD1Database();
  const repository = createResearchRepository(db, {
    now: () => "2026-07-19T04:00:00.000Z",
    randomId: () => "01234567-89ab-4def-8123-456789abcdef",
  });
  const catalog = parseResearchCatalog(catalogRaw);
  const sanitized = parseResearchRequest(request(), catalog);
  const created = await repository.createJob(
    "a".repeat(64),
    sanitized,
    "research-idempotency-0001",
  );
  assert.equal(created.status, "created");
  assert.equal(
    (
      await repository.createJob(
        "a".repeat(64),
        sanitized,
        "research-idempotency-0001",
      )
    ).status,
    "replay",
  );

  const claim = await repository.claimNext({
    workerId: "worker:pro-magazine",
    leaseSeconds: 120,
    analystActorKeys: ["a".repeat(64)],
  });
  assert.ok(claim);
  assert.equal(claim.status, "claimed");
  assert.equal(claim.fencing_token, 1);
  assert.equal(
    await repository.claimNext({
      workerId: "worker:other",
      leaseSeconds: 120,
      analystActorKeys: ["a".repeat(64)],
    }),
    null,
  );
  const heartbeat = await repository.heartbeat(
    claim.job_id,
    claim.claim_token,
    claim.fencing_token,
    120,
  );
  assert.equal(heartbeat.status, "claimed");

  const envelope = parseResearchResult(result(claim.job_id, claim));
  assert.equal(
    (await repository.complete(envelope, "task-5-current", "f".repeat(64)))
      .status,
    "created",
  );
  assert.equal(
    (await repository.complete(envelope, "task-5-current", "f".repeat(64)))
      .status,
    "replay",
  );
  assert.equal((await repository.getJob(claim.job_id))?.status, "completed");
  assert.throws(
    () =>
      parseResearchResult(
        result(claim.job_id, claim, {
          claims: [
            {
              ...result(claim.job_id, claim).claims[0],
              evidence: [],
            },
          ],
        }),
      ),
    /evidence/,
  );
});

test("expired leases are reclaimed with fencing and stale workers fail closed", async () => {
  let clock = "2026-07-19T04:00:00.000Z";
  let sequence = 0;
  const db = new SqliteD1Database();
  const repository = createResearchRepository(db, {
    now: () => clock,
    randomId: () =>
      `01234567-89ab-4def-8123-${String(++sequence).padStart(12, "0")}`,
  });
  const sanitized = parseResearchRequest(
    request(),
    parseResearchCatalog(catalogRaw),
  );
  await repository.createJob(
    "a".repeat(64),
    sanitized,
    "lease-reclaim-create-0001",
  );
  const first = await repository.claimNext({
    workerId: "worker:first",
    leaseSeconds: 30,
    analystActorKeys: ["a".repeat(64)],
  });
  assert.ok(first);
  clock = "2026-07-19T04:00:31.000Z";
  const second = await repository.claimNext({
    workerId: "worker:second",
    leaseSeconds: 30,
    analystActorKeys: ["a".repeat(64)],
  });
  assert.ok(second);
  assert.equal(second.job_id, first.job_id);
  assert.equal(second.fencing_token, 2);
  assert.notEqual(second.claim_token, first.claim_token);
  await assert.rejects(
    repository.heartbeat(
      first.job_id,
      first.claim_token,
      first.fencing_token,
      30,
    ),
    /lease lost/,
  );
  await assert.rejects(
    repository.complete(
      parseResearchResult(result(first.job_id, first)),
      "task-5-current",
      "e".repeat(64),
    ),
    /lease lost/,
  );
  assert.equal(
    (
      await repository.complete(
        parseResearchResult(result(second.job_id, second)),
        "task-5-current",
        "f".repeat(64),
      )
    ).status,
    "created",
  );
});

test("failed and cancelled jobs are terminal and audit rows stay metadata-only", async () => {
  const db = new SqliteD1Database();
  const repository = createResearchRepository(db);
  const sanitized = parseResearchRequest(
    request(),
    parseResearchCatalog(catalogRaw),
  );
  await repository.createJob(
    "a".repeat(64),
    sanitized,
    "terminal-failure-create-0001",
  );
  const failedClaim = await repository.claimNext({
    workerId: "worker:failure",
    leaseSeconds: 120,
    analystActorKeys: ["a".repeat(64)],
  });
  assert.ok(failedClaim);
  const failed = parseResearchResult(
    result(failedClaim.job_id, failedClaim, {
      status: "failed",
      summary: null,
      claims: [],
      failure: { code: "source_unavailable" },
    }),
  );
  assert.equal(
    (await repository.complete(failed, "task-5-current", "d".repeat(64)))
      .status,
    "created",
  );
  assert.equal(
    await repository.cancelOwn(failedClaim.job_id, "a".repeat(64)),
    false,
  );

  await repository.createJob(
    "a".repeat(64),
    sanitized,
    "terminal-cancel-create-0001",
  );
  const cancelledClaim = await repository.claimNext({
    workerId: "worker:cancel",
    leaseSeconds: 120,
    analystActorKeys: ["a".repeat(64)],
  });
  assert.ok(cancelledClaim);
  assert.equal(
    await repository.cancelOwn(cancelledClaim.job_id, "a".repeat(64)),
    true,
  );
  assert.equal(
    await repository.cancelOwn(cancelledClaim.job_id, "a".repeat(64)),
    false,
  );
  await assert.rejects(
    repository.complete(
      parseResearchResult(result(cancelledClaim.job_id, cancelledClaim)),
      "task-5-current",
      "c".repeat(64),
    ),
    /lease lost/,
  );
  const columns = db.sqlite
    .prepare("PRAGMA table_info(research_audit_events)")
    .all()
    .map((row) => row.name);
  assert.deepEqual(columns.sort(), [
    "actor_key",
    "created_at",
    "event_id",
    "event_type",
    "failure_code",
    "fencing_token",
    "job_id",
    "status",
    "worker_id",
  ]);
  const eventTypes = db.sqlite
    .prepare("SELECT event_type FROM research_audit_events ORDER BY rowid")
    .all()
    .map((row) => row.event_type);
  assert.deepEqual(eventTypes, [
    "created",
    "claimed",
    "failed",
    "created",
    "claimed",
    "cancelled",
  ]);
});

test("human POST rejects reader/operator, cross-origin and free-form payloads", async () => {
  const db = new SqliteD1Database();
  const actorSecret = runtimeBindings(db).ACTOR_KEY_SECRET;
  const analystKey = await hmacSha256Hex(actorSecret, "analyst@balizero.com");
  const operatorKey = await hmacSha256Hex(actorSecret, "operator@balizero.com");
  const { POST } = await import(routePaths.jobs);
  const invoke = (email, body, options = {}) => {
    const requestHeaders = new Headers({
      "content-type": "application/json",
      "oai-authenticated-user-email": email,
      origin: options.origin ?? "https://magazine.example",
      "x-magazine-csrf": "1",
    });
    return runWithMagazineBindings(
      bindings(db, { analysts: [analystKey], operators: [operatorKey] }),
      () =>
        POST(
          new Request("https://magazine.example/api/research/jobs", {
            method: "POST",
            headers: requestHeaders,
            body: JSON.stringify(body),
          }),
        ),
    );
  };
  assert.equal(
    (
      await invoke("reader@balizero.com", {
        idempotency_key: "reader-attempt-0001",
        request: request(),
      })
    ).status,
    403,
  );
  assert.equal(
    (
      await invoke("operator@balizero.com", {
        idempotency_key: "operator-attempt-0001",
        request: request(),
      })
    ).status,
    403,
  );
  assert.equal(
    (
      await invoke(
        "analyst@balizero.com",
        {
          idempotency_key: "origin-attempt-0001",
          request: request(),
        },
        { origin: "https://evil.example" },
      )
    ).status,
    403,
  );
  assert.equal(
    (
      await invoke("analyst@balizero.com", {
        idempotency_key: "free-text-attempt-0001",
        request: { ...request(), query: "client passport details" },
      })
    ).status,
    400,
  );
  const accepted = await invoke("analyst@balizero.com", {
    idempotency_key: "analyst-create-0001",
    request: request(),
  });
  assert.equal(accepted.status, 201);
  assert.equal(
    db.get("SELECT actor_key FROM research_jobs").actor_key,
    analystKey,
  );
  assert.equal(
    JSON.parse(db.get("SELECT query_json FROM research_jobs").query_json).query,
    undefined,
  );
});

test("Reader and Operator can read sanitized findings; only the current owning Analyst can cancel", async () => {
  const db = new SqliteD1Database();
  const actorSecret = runtimeBindings(db).ACTOR_KEY_SECRET;
  const analystKey = await hmacSha256Hex(actorSecret, "analyst@balizero.com");
  const operatorKey = await hmacSha256Hex(actorSecret, "operator@balizero.com");
  const repository = createResearchRepository(db);
  const sanitized = parseResearchRequest(
    request(),
    parseResearchCatalog(catalogRaw),
  );
  const completedCreated = await repository.createJob(
    analystKey,
    sanitized,
    "human-read-completed-0001",
  );
  const claim = await repository.claimNext({
    workerId: "worker:human-read",
    leaseSeconds: 120,
    analystActorKeys: [analystKey],
  });
  assert.ok(claim);
  await repository.complete(
    parseResearchResult(result(claim.job_id, claim)),
    "task-5-current",
    "b".repeat(64),
  );
  const queued = await repository.createJob(
    analystKey,
    sanitized,
    "human-cancel-queued-0001",
  );
  const [jobsRoute, jobRoute] = await Promise.all([
    import(routePaths.jobs),
    import(routePaths.job),
  ]);
  const runtime = bindings(db, {
    analysts: [analystKey],
    operators: [operatorKey],
  });
  const humanRequest = (email, path, method = "GET") =>
    new Request(`https://magazine.example${path}`, {
      method,
      headers: {
        "oai-authenticated-user-email": email,
        ...(method === "DELETE"
          ? { origin: "https://magazine.example", "x-magazine-csrf": "1" }
          : {}),
      },
    });
  for (const email of ["reader@balizero.com", "operator@balizero.com"]) {
    const response = await runWithMagazineBindings(runtime, () =>
      jobsRoute.GET(humanRequest(email, "/api/research/jobs")),
    );
    assert.equal(response.status, 200);
    assert.match(response.headers.get("cache-control"), /no-store/);
    const payload = await response.json();
    const completed = payload.jobs.find(
      (job) => job.job_id === completedCreated.job.job_id,
    );
    assert.equal(
      completed.result.claims[0].evidence[0].source_type,
      "official",
    );
    assert.equal(completed.actor_key, undefined);
    assert.equal(completed.request_hash, undefined);
    assert.equal(completed.result.claim_token, undefined);
    assert.equal(completed.result.fencing_token, undefined);
    assert.equal(completed.result.request_hash, undefined);
  }
  const deleteJob = (email, currentRuntime = runtime) =>
    runWithMagazineBindings(currentRuntime, () =>
      jobRoute.DELETE(
        humanRequest(
          email,
          `/api/research/jobs/${queued.job.job_id}`,
          "DELETE",
        ),
        { params: Promise.resolve({ jobId: queued.job.job_id }) },
      ),
    );
  assert.equal((await deleteJob("reader@balizero.com")).status, 403);
  assert.equal((await deleteJob("operator@balizero.com")).status, 403);
  assert.equal(
    (
      await deleteJob(
        "analyst@balizero.com",
        bindings(db, { analysts: [], operators: [operatorKey] }),
      )
    ).status,
    403,
  );
  assert.equal((await deleteJob("analyst@balizero.com")).status, 200);
  assert.equal((await deleteJob("analyst@balizero.com")).status, 409);
});

test("machine claim cancels revoked creators and continues to the next current Analyst job", async () => {
  const db = new SqliteD1Database();
  const revokedActorKey = "a".repeat(64);
  const analystActorKey = "b".repeat(64);
  const repository = createResearchRepository(db);
  const sanitized = parseResearchRequest(
    request(),
    parseResearchCatalog(catalogRaw),
  );
  const revoked = await repository.createJob(
    revokedActorKey,
    sanitized,
    "revoked-creator-job-0001",
  );
  const eligible = await repository.createJob(
    analystActorKey,
    sanitized,
    "current-analyst-job-0001",
  );
  db.sqlite
    .prepare("UPDATE research_jobs SET created_at = ? WHERE job_id = ?")
    .run("2026-07-19T00:00:00.000Z", revoked.job.job_id);
  db.sqlite
    .prepare("UPDATE research_jobs SET created_at = ? WHERE job_id = ?")
    .run("2026-07-19T00:00:01.000Z", eligible.job.job_id);

  const claimRoute = await import(routePaths.claim);
  const claimRequest = await signedMachineRequest({
    path: "/api/machine/research/jobs/claim",
    body: JSON.stringify({
      schema_version: "research-claim.v1",
      worker_id: "worker:role-revalidation",
      lease_seconds: 120,
    }),
  });
  const response = await runWithMagazineBindings(
    bindings(db, {
      analysts: [analystActorKey],
      operators: [revokedActorKey],
    }),
    () => claimRoute.POST(claimRequest),
  );
  assert.equal(response.status, 200);
  const payload = await response.json();
  assert.equal(payload.job.job_id, eligible.job.job_id);

  const revokedRow = db.sqlite
    .prepare(
      "SELECT status, claim_token, worker_id FROM research_jobs WHERE job_id = ?",
    )
    .get(revoked.job.job_id);
  assert.deepEqual(
    { ...revokedRow },
    {
      status: "cancelled",
      claim_token: null,
      worker_id: null,
    },
  );
  const audit = db.sqlite
    .prepare(
      `SELECT event_type, actor_key, worker_id, status, failure_code
       FROM research_audit_events
       WHERE job_id = ? AND event_type = 'cancelled'`,
    )
    .get(revoked.job.job_id);
  assert.deepEqual(
    { ...audit },
    {
      event_type: "cancelled",
      actor_key: revokedActorKey,
      worker_id: null,
      status: "cancelled",
      failure_code: null,
    },
  );
});

test("expired machine lease rejects heartbeat plus completed and failed results", async () => {
  const db = new SqliteD1Database();
  const analystActorKey = "a".repeat(64);
  const repository = createResearchRepository(db);
  const sanitized = parseResearchRequest(
    request(),
    parseResearchCatalog(catalogRaw),
  );
  await repository.createJob(
    analystActorKey,
    sanitized,
    "expired-machine-lease-job-0001",
  );
  const [claimRoute, heartbeatRoute, resultRoute] = await Promise.all([
    import(routePaths.claim),
    import(routePaths.heartbeat),
    import(routePaths.result),
  ]);
  const runtime = bindings(db, { analysts: [analystActorKey] });
  const claimRequest = await signedMachineRequest({
    path: "/api/machine/research/jobs/claim",
    body: JSON.stringify({
      schema_version: "research-claim.v1",
      worker_id: "worker:expired-lease",
      lease_seconds: 120,
    }),
  });
  const claimResponse = await runWithMagazineBindings(runtime, () =>
    claimRoute.POST(claimRequest),
  );
  assert.equal(claimResponse.status, 200);
  const claimed = (await claimResponse.json()).job;
  db.sqlite
    .prepare("UPDATE research_jobs SET lease_deadline = ? WHERE job_id = ?")
    .run("2000-01-01T00:00:00.000Z", claimed.job_id);

  const heartbeatPath = `/api/machine/research/jobs/${claimed.job_id}/heartbeat`;
  const heartbeatRequest = await signedMachineRequest({
    path: heartbeatPath,
    body: JSON.stringify({
      schema_version: "research-heartbeat.v1",
      claim_token: claimed.claim_token,
      fencing_token: claimed.fencing_token,
      lease_seconds: 120,
    }),
  });
  assert.equal(
    (
      await runWithMagazineBindings(runtime, () =>
        heartbeatRoute.POST(heartbeatRequest, {
          params: Promise.resolve({ jobId: claimed.job_id }),
        }),
      )
    ).status,
    409,
  );

  const resultPath = `/api/machine/research/jobs/${claimed.job_id}/result`;
  const submitResult = async (payload) => {
    const signed = await signedMachineRequest({
      path: resultPath,
      body: JSON.stringify(payload),
    });
    return runWithMagazineBindings(runtime, () =>
      resultRoute.POST(signed, {
        params: Promise.resolve({ jobId: claimed.job_id }),
      }),
    );
  };
  assert.equal(
    (await submitResult(result(claimed.job_id, claimed))).status,
    409,
  );
  assert.equal(
    (
      await submitResult(
        result(claimed.job_id, claimed, {
          status: "failed",
          summary: null,
          claims: [],
          failure: { code: "source_unavailable" },
        }),
      )
    ).status,
    409,
  );
  assert.equal(
    db.sqlite
      .prepare("SELECT status FROM research_jobs WHERE job_id = ?")
      .get(claimed.job_id).status,
    "claimed",
  );
  assert.equal(
    db.sqlite.prepare("SELECT count(*) AS count FROM research_results").get()
      .count,
    0,
  );
});

test("machine routes enforce HMAC, then claim, heartbeat, and idempotent signed result", async () => {
  const db = new SqliteD1Database();
  const repository = createResearchRepository(db);
  const sanitized = parseResearchRequest(
    request(),
    parseResearchCatalog(catalogRaw),
  );
  const created = await repository.createJob(
    "a".repeat(64),
    sanitized,
    "machine-flow-create-0001",
  );
  const [claimRoute, heartbeatRoute, resultRoute] = await Promise.all([
    import(routePaths.claim),
    import(routePaths.heartbeat),
    import(routePaths.result),
  ]);
  const runtime = bindings(db, { analysts: ["a".repeat(64)] });
  const claimRequest = await signedMachineRequest({
    path: "/api/machine/research/jobs/claim",
    body: JSON.stringify({
      schema_version: "research-claim.v1",
      worker_id: "worker:pro-magazine",
      lease_seconds: 120,
    }),
  });
  const claimedResponse = await runWithMagazineBindings(runtime, () =>
    claimRoute.POST(claimRequest),
  );
  assert.equal(claimedResponse.status, 200);
  const claimed = await claimedResponse.json();
  assert.equal(claimed.job.job_id, created.job.job_id);
  assert.deepEqual(Object.keys(claimed.job.request).sort(), [
    "entity_ids",
    "facets",
    "index_tokens",
    "mode",
    "schema_version",
    "template",
    "topic_ids",
  ]);

  const heartbeatPath = `/api/machine/research/jobs/${claimed.job.job_id}/heartbeat`;
  const heartbeatRequest = await signedMachineRequest({
    path: heartbeatPath,
    body: JSON.stringify({
      schema_version: "research-heartbeat.v1",
      claim_token: claimed.job.claim_token,
      fencing_token: claimed.job.fencing_token,
      lease_seconds: 120,
    }),
  });
  assert.equal(
    (
      await runWithMagazineBindings(runtime, () =>
        heartbeatRoute.POST(heartbeatRequest, {
          params: Promise.resolve({ jobId: claimed.job.job_id }),
        }),
      )
    ).status,
    200,
  );

  const resultPath = `/api/machine/research/jobs/${claimed.job.job_id}/result`;
  const body = JSON.stringify(result(claimed.job.job_id, claimed.job));
  const submit = async () => {
    const signed = await signedMachineRequest({ path: resultPath, body });
    return runWithMagazineBindings(runtime, () =>
      resultRoute.POST(signed, {
        params: Promise.resolve({ jobId: claimed.job.job_id }),
      }),
    );
  };
  assert.equal((await submit()).status, 201);
  assert.equal((await submit()).status, 200);
  assert.equal(
    db.get("SELECT receipt_key_id FROM research_results").receipt_key_id,
    "task-5-current",
  );
});
