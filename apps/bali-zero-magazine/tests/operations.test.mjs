import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

import {
  createOperationsRepository,
  parseOperationIntentRequest,
  parseOperationResult,
} from "../lib/server/operations-repository.ts";
import { runWithMagazineBindings } from "../lib/server/runtime-bindings.ts";
import { hmacSha256Hex } from "../lib/server/security.ts";
import {
  SqliteD1Database,
  runtimeBindings,
  signedMachineRequest,
} from "./helpers/task-5-fixtures.mjs";

const routePaths = {
  human: new URL("../app/api/operations/intents/route.ts", import.meta.url),
  detail: new URL(
    "../app/api/operations/intents/[intentId]/route.ts",
    import.meta.url,
  ),
  claim: new URL(
    "../app/api/machine/operations/intents/claim/route.ts",
    import.meta.url,
  ),
  start: new URL(
    "../app/api/machine/operations/intents/[intentId]/start/route.ts",
    import.meta.url,
  ),
  heartbeat: new URL(
    "../app/api/machine/operations/intents/[intentId]/heartbeat/route.ts",
    import.meta.url,
  ),
  attest: new URL(
    "../app/api/machine/operations/intents/[intentId]/pre-effect-attest/route.ts",
    import.meta.url,
  ),
  result: new URL(
    "../app/api/machine/operations/intents/[intentId]/result/route.ts",
    import.meta.url,
  ),
  page: new URL("../app/operations/page.tsx", import.meta.url),
  board: new URL("../components/operations-board.tsx", import.meta.url),
};

const actor = "a".repeat(64);
const policy = "roles.operations.v1";

function request(kind = "rerun_collector", overrides = {}) {
  const params = {
    rerun_collector: {
      collector_id: "regulatory-watcher",
      failed_run_id: "collector-run-0123456789abcdef",
    },
    rebuild_edition: {
      edition_id: "edition-0123456789abcdef",
      expected_revision: 4,
    },
    quarantine_story: {
      story_id: "story-0123456789abcdef",
      story_version: 2,
      expected_visibility_seq: 7,
    },
    release_story: {
      story_id: "story-0123456789abcdef",
      story_version: 2,
      expected_visibility_seq: 7,
    },
    refresh_research_job: {
      research_job_id: "research-job-0123456789abcdef",
    },
  };
  const reasons = {
    rerun_collector: "collector_recovery",
    rebuild_edition: "edition_recovery",
    quarantine_story: "content_safety",
    release_story: "gates_reverified",
    refresh_research_job: "research_recovery",
  };
  return {
    schema_version: "ops-intent-request.v1",
    intent_kind: kind,
    idempotency_key: `ops-idempotency-${kind}-0001`,
    reason_code: reasons[kind],
    expires_at: "2026-07-19T05:00:00.000Z",
    params: params[kind],
    ...overrides,
  };
}

test("operations ships every human and machine boundary", () => {
  for (const [name, path] of Object.entries(routePaths)) {
    assert.ok(existsSync(path), `missing ${name} operations surface`);
  }
});

test("closed intent schemas accept exactly five kinds and reject command carriers", () => {
  for (const kind of [
    "rerun_collector",
    "rebuild_edition",
    "quarantine_story",
    "release_story",
    "refresh_research_job",
  ]) {
    assert.equal(parseOperationIntentRequest(request(kind)).intent_kind, kind);
  }
  for (const injected of [
    { command: "rm -rf /" },
    { shell: "bash" },
    { url: "https://evil.example" },
    { path: "/tmp/payload" },
    { reason: "client passport A1234567" },
  ]) {
    assert.throws(
      () =>
        parseOperationIntentRequest(
          request("rerun_collector", {
            params: { ...request().params, ...injected },
          }),
        ),
      /invalid operation intent/,
    );
  }
  assert.throws(
    () => parseOperationIntentRequest(request("restart_anything")),
    /invalid operation intent/,
  );
});

test("repository is actor-scoped idempotent and persists policy evidence", async () => {
  const db = new SqliteD1Database();
  const repository = createOperationsRepository(db, {
    now: () => "2026-07-19T04:00:00.000Z",
    randomId: () => "01234567-89ab-4def-8123-456789abcdef",
  });
  const parsed = parseOperationIntentRequest(request());
  const first = await repository.createIntent({
    actorKey: actor,
    effectiveRole: "operator",
    policyVersion: policy,
    operatorActorKeys: [actor],
    request: parsed,
  });
  assert.equal(first.status, "created");
  assert.equal(
    (
      await repository.createIntent({
        actorKey: actor,
        effectiveRole: "operator",
        policyVersion: policy,
        operatorActorKeys: [actor],
        request: parsed,
      })
    ).status,
    "replay",
  );
  await assert.rejects(
    repository.createIntent({
      actorKey: actor,
      effectiveRole: "operator",
      policyVersion: policy,
      operatorActorKeys: [actor],
      request: parseOperationIntentRequest(
        request("rerun_collector", {
          params: {
            collector_id: "intel-lake",
            failed_run_id: "collector-run-0123456789abcdef",
          },
        }),
      ),
    }),
    /idempotency conflict/,
  );
  const row = db.get(
    "SELECT actor_key, effective_role, policy_version, reason_code, params_json FROM ops_intents",
  );
  assert.deepEqual(
    [row.actor_key, row.effective_role, row.policy_version, row.reason_code],
    [actor, "operator", policy, "collector_recovery"],
  );
  assert.doesNotMatch(row.params_json, /command|shell|url|path|passport/i);
});

test("revoked queued intents cancel while claim scan continues", async () => {
  let sequence = 0;
  const db = new SqliteD1Database();
  const repository = createOperationsRepository(db, {
    now: () => "2026-07-19T04:00:00.000Z",
    randomId: () =>
      `01234567-89ab-4def-8123-${String(++sequence).padStart(12, "0")}`,
  });
  await repository.createIntent({
    actorKey: "b".repeat(64),
    effectiveRole: "operator",
    policyVersion: policy,
    operatorActorKeys: ["b".repeat(64)],
    request: parseOperationIntentRequest(request()),
  });
  await repository.createIntent({
    actorKey: actor,
    effectiveRole: "operator",
    policyVersion: policy,
    operatorActorKeys: [actor],
    request: parseOperationIntentRequest(
      request("rebuild_edition", {
        idempotency_key: "ops-idempotency-edition-0002",
      }),
    ),
  });
  const claim = await repository.claimNext({
    workerId: "worker:pro-magazine",
    leaseSeconds: 30,
    operatorActorKeys: [actor],
    policyVersion: "roles.operations.v2",
  });
  assert.equal(claim.intent_kind, "rebuild_edition");
  assert.equal(
    db.get("SELECT status FROM ops_intents WHERE actor_key = ?", "b".repeat(64))
      .status,
    "cancelled_revoked",
  );
});

test("claim start attest result is fenced, terminal, and receipt-only", async () => {
  const db = new SqliteD1Database();
  const repository = createOperationsRepository(db, {
    now: () => "2026-07-19T04:00:00.000Z",
    randomId: () => "01234567-89ab-4def-8123-456789abcdef",
  });
  await repository.createIntent({
    actorKey: actor,
    effectiveRole: "operator",
    policyVersion: policy,
    operatorActorKeys: [actor],
    request: parseOperationIntentRequest(request()),
  });
  const claim = await repository.claimNext({
    workerId: "worker:pro-magazine",
    leaseSeconds: 60,
    operatorActorKeys: [actor],
    policyVersion: policy,
  });
  assert.equal(claim.status, "claimed");
  assert.equal(claim.actor_key, actor);
  assert.equal(claim.target_key, `collector:${claim.target_id}`);
  assert.equal(claim.target_fencing_token, 1);
  assert.equal((await repository.start(claim)).status, "running");
  const attestation = await repository.attestPreEffect(claim, {
    operatorActorKeys: [actor],
    policyVersion: "roles.operations.v2",
  });
  assert.equal(attestation.authorized, true);
  assert.deepEqual(
    {
      schema_version: attestation.schema_version,
      intent_id: attestation.intent_id,
      request_hash: attestation.request_hash,
      actor_key: attestation.actor_key,
      target_id: attestation.target_id,
      target_key: attestation.target_key,
      fencing_token: attestation.fencing_token,
      target_fencing_token: attestation.target_fencing_token,
    },
    {
      schema_version: "ops-effect-attestation.v1",
      intent_id: claim.intent_id,
      request_hash: claim.request_hash,
      actor_key: actor,
      target_id: claim.target_id,
      target_key: claim.target_key,
      fencing_token: claim.fencing_token,
      target_fencing_token: claim.target_fencing_token,
    },
  );
  assert.ok(
    Date.parse(attestation.expires_at) > Date.parse(attestation.attested_at),
  );
  assert.ok(
    Date.parse(attestation.expires_at) - Date.parse(attestation.attested_at) <=
      30_000,
  );
  const envelope = parseOperationResult({
    schema_version: "ops-result.v1",
    intent_id: claim.intent_id,
    request_hash: claim.request_hash,
    status: "succeeded",
    completed_at: "2026-07-19T04:01:00.000Z",
    receipt: { code: "effect_acknowledged", target_id: claim.target_id },
    failure: null,
    claim_token: claim.claim_token,
    fencing_token: claim.fencing_token,
    target_fencing_token: claim.target_fencing_token,
    actor_key: claim.actor_key,
    target_key: claim.target_key,
    target_id: claim.target_id,
    effect_token: attestation.effect_token,
    attested_policy_version: attestation.policy_version,
    attestation_expires_at: attestation.expires_at,
  });
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
  await assert.rejects(repository.start(claim), /lease lost|terminal/);
  const columns = db.sqlite
    .prepare("PRAGMA table_info(ops_receipts)")
    .all()
    .map((row) => row.name);
  assert.equal(columns.includes("payload_json"), false);
  assert.equal(columns.includes("receipt_json"), true);
  assert.doesNotMatch(
    db.get("SELECT receipt_json FROM ops_receipts").receipt_json,
    /actor|idempotency|params|passport/i,
  );
});

test("expired original intent is terminalized before effect attestation", async () => {
  let instant = "2026-07-19T04:00:00.000Z";
  const db = new SqliteD1Database();
  const repository = createOperationsRepository(db, { now: () => instant });
  await repository.createIntent({
    actorKey: actor,
    effectiveRole: "operator",
    policyVersion: policy,
    operatorActorKeys: [actor],
    request: parseOperationIntentRequest(
      request("rerun_collector", { expires_at: "2026-07-19T04:00:30.000Z" }),
    ),
  });
  const claim = await repository.claimNext({
    workerId: "worker:pro-magazine",
    leaseSeconds: 120,
    operatorActorKeys: [actor],
    policyVersion: policy,
  });
  await repository.start(claim);
  instant = "2026-07-19T04:01:00.000Z";
  const attestation = await repository.attestPreEffect(claim, {
    operatorActorKeys: [actor],
    policyVersion: "roles.operations.v2",
  });
  assert.equal(attestation.authorized, false);
  assert.equal(attestation.status, "cancelled_revoked");
  assert.equal(
    (await repository.getIntent(claim.intent_id)).status,
    "cancelled_revoked",
  );
  assert.equal(
    db.get(
      "SELECT status FROM ops_receipts WHERE intent_id = ?",
      claim.intent_id,
    ).status,
    "cancelled_revoked",
  );
});

test("attempt exhaustion atomically produces a failed receipt and audit", async () => {
  let instant = "2026-07-19T04:00:00.000Z";
  const db = new SqliteD1Database();
  const repository = createOperationsRepository(db, { now: () => instant });
  await repository.createIntent({
    actorKey: actor,
    effectiveRole: "operator",
    policyVersion: policy,
    operatorActorKeys: [actor],
    request: parseOperationIntentRequest(request()),
  });
  let claim;
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    claim = await repository.claimNext({
      workerId: "worker:pro-magazine",
      leaseSeconds: 15,
      operatorActorKeys: [actor],
      policyVersion: policy,
    });
    assert.equal(claim.attempt_count, attempt);
    instant = new Date(Date.parse(instant) + 16_000).toISOString();
  }
  assert.equal(
    await repository.claimNext({
      workerId: "worker:pro-magazine",
      leaseSeconds: 15,
      operatorActorKeys: [actor],
      policyVersion: policy,
    }),
    null,
  );
  const stored = await repository.getIntent(claim.intent_id);
  assert.equal(stored.status, "failed");
  assert.equal(stored.failure_code, "retry_exhausted");
  assert.equal(
    db.get(
      "SELECT status FROM ops_receipts WHERE intent_id = ?",
      claim.intent_id,
    ).status,
    "failed",
  );
  assert.equal(
    db.get(
      "SELECT count(*) AS count FROM ops_audit_events WHERE intent_id = ? AND event_type = 'failed'",
      claim.intent_id,
    ).count,
    1,
  );
});

test("target fences increase across intents and stale authority cannot attest", async () => {
  let sequence = 0;
  const db = new SqliteD1Database();
  const repository = createOperationsRepository(db, {
    now: () => "2026-07-19T04:00:00.000Z",
    randomId: () =>
      `01234567-89ab-4def-8123-${String(++sequence).padStart(12, "0")}`,
  });
  const create = (kind, idempotencyKey) =>
    repository.createIntent({
      actorKey: actor,
      effectiveRole: "operator",
      policyVersion: policy,
      operatorActorKeys: [actor],
      request: parseOperationIntentRequest(
        request(kind, { idempotency_key: idempotencyKey }),
      ),
    });
  await create("quarantine_story", "ops-target-fence-first-0001");
  const first = await repository.claimNext({
    workerId: "worker:pro-magazine",
    leaseSeconds: 60,
    operatorActorKeys: [actor],
    policyVersion: policy,
  });
  assert.equal(first.target_fencing_token, 1);
  await repository.start(first);
  db.execute(
    "UPDATE ops_target_fences SET next_fencing_token = 2 WHERE target_key = ?",
    first.target_key,
  );
  await assert.rejects(
    repository.attestPreEffect(first, {
      operatorActorKeys: [actor],
      policyVersion: policy,
    }),
    /stale target fence/,
  );
  db.execute(
    "UPDATE ops_intents SET status = 'failed', completed_at = ? WHERE intent_id = ?",
    "2026-07-19T04:00:01.000Z",
    first.intent_id,
  );
  await create("release_story", "ops-target-fence-second-0002");
  const second = await repository.claimNext({
    workerId: "worker:pro-magazine",
    leaseSeconds: 60,
    operatorActorKeys: [actor],
    policyVersion: policy,
  });
  assert.equal(second.target_key, first.target_key);
  assert.ok(second.target_fencing_token > first.target_fencing_token);
});

test("state and audit transition roll back together on audit failure", async () => {
  const db = new SqliteD1Database();
  const repository = createOperationsRepository(db, {
    now: () => "2026-07-19T04:00:00.000Z",
  });
  await repository.createIntent({
    actorKey: actor,
    effectiveRole: "operator",
    policyVersion: policy,
    operatorActorKeys: [actor],
    request: parseOperationIntentRequest(request()),
  });
  const claim = await repository.claimNext({
    workerId: "worker:pro-magazine",
    leaseSeconds: 60,
    operatorActorKeys: [actor],
    policyVersion: policy,
  });
  db.sqlite.exec(
    "CREATE TRIGGER fail_started_audit BEFORE INSERT ON ops_audit_events WHEN NEW.event_type = 'started' BEGIN SELECT RAISE(ABORT, 'audit failure'); END",
  );
  await assert.rejects(repository.start(claim), /audit failure/);
  assert.equal((await repository.getIntent(claim.intent_id)).status, "claimed");
  db.sqlite.exec("DROP TRIGGER fail_started_audit");
  assert.equal((await repository.start(claim)).status, "running");
  assert.equal(
    db.get(
      "SELECT count(*) AS count FROM ops_audit_events WHERE intent_id = ? AND event_type = 'started'",
      claim.intent_id,
    ).count,
    1,
  );
});

test("revocation at final attestation prevents the effect", async () => {
  const db = new SqliteD1Database();
  const repository = createOperationsRepository(db, {
    now: () => "2026-07-19T04:00:00.000Z",
  });
  await repository.createIntent({
    actorKey: actor,
    effectiveRole: "operator",
    policyVersion: policy,
    operatorActorKeys: [actor],
    request: parseOperationIntentRequest(request()),
  });
  const claim = await repository.claimNext({
    workerId: "worker:pro-magazine",
    leaseSeconds: 60,
    operatorActorKeys: [actor],
    policyVersion: policy,
  });
  await repository.start(claim);
  const attestation = await repository.attestPreEffect(claim, {
    operatorActorKeys: [],
    policyVersion: "roles.operations.v2",
  });
  assert.equal(attestation.authorized, false);
  assert.equal(
    (await repository.getIntent(claim.intent_id)).status,
    "cancelled_revoked",
  );
});

test("human POST allows only a current Operator and rejects open payloads", async () => {
  const db = new SqliteD1Database();
  const baseBindings = runtimeBindings(db);
  const readerKey = await hmacSha256Hex(
    baseBindings.ACTOR_KEY_SECRET,
    "reader@balizero.com",
  );
  const analystKey = await hmacSha256Hex(
    baseBindings.ACTOR_KEY_SECRET,
    "analyst@balizero.com",
  );
  const operatorKey = await hmacSha256Hex(
    baseBindings.ACTOR_KEY_SECRET,
    "operator@balizero.com",
  );
  const bindings = {
    ...baseBindings,
    ROLE_ALLOWLIST_JSON: JSON.stringify({
      version: "roles.operations.http.v1",
      analysts: [analystKey],
      operators: [operatorKey],
    }),
  };
  const { POST } = await import(routePaths.human);
  const body = request("refresh_research_job", {
    expires_at: new Date(Date.now() + 60 * 60 * 1_000).toISOString(),
  });
  const invoke = (email, value) =>
    runWithMagazineBindings(bindings, () =>
      POST(
        new Request("https://magazine.example/api/operations/intents", {
          method: "POST",
          headers: {
            "content-type": "application/json",
            "oai-authenticated-user-email": email,
            origin: "https://magazine.example",
            "x-magazine-csrf": "1",
          },
          body: JSON.stringify(value),
        }),
      ),
    );
  assert.equal(
    await invoke("reader@balizero.com", body).then((r) => r.status),
    403,
  );
  assert.equal(
    await invoke("analyst@balizero.com", body).then((r) => r.status),
    403,
  );
  assert.equal(
    await invoke("operator@balizero.com", { ...body, command: "restart" }).then(
      (r) => r.status,
    ),
    400,
  );
  assert.equal(
    await invoke("operator@balizero.com", body).then((r) => r.status),
    201,
  );
  const stored = db.get(
    "SELECT actor_key, effective_role, policy_version FROM ops_intents",
  );
  assert.deepEqual(
    { ...stored },
    {
      actor_key: operatorKey,
      effective_role: "operator",
      policy_version: "roles.operations.http.v1",
    },
  );
  assert.notEqual(stored.actor_key, readerKey);
});

test("machine claim requires SIWC admission plus a valid HMAC envelope", async () => {
  const db = new SqliteD1Database();
  const baseBindings = runtimeBindings(db);
  const operatorKey = await hmacSha256Hex(
    baseBindings.ACTOR_KEY_SECRET,
    "operator@balizero.com",
  );
  const bindings = {
    ...baseBindings,
    ROLE_ALLOWLIST_JSON: JSON.stringify({
      version: "roles.operations.machine.v1",
      analysts: [],
      operators: [operatorKey],
    }),
  };
  await createOperationsRepository(db).createIntent({
    actorKey: operatorKey,
    effectiveRole: "operator",
    policyVersion: "roles.operations.machine.v1",
    operatorActorKeys: [operatorKey],
    request: parseOperationIntentRequest(
      request("rerun_collector", {
        expires_at: new Date(Date.now() + 60 * 60 * 1_000).toISOString(),
      }),
    ),
  });
  const { POST } = await import(routePaths.claim);
  const body = JSON.stringify({
    schema_version: "ops-claim.v1",
    worker_id: "worker:pro-magazine",
    lease_seconds: 60,
  });
  const unsigned = new Request(
    "https://magazine.example/api/machine/operations/intents/claim",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body,
    },
  );
  assert.equal(
    await runWithMagazineBindings(bindings, () => POST(unsigned)).then(
      (response) => response.status,
    ),
    401,
  );
  const signed = await signedMachineRequest({
    path: "/api/machine/operations/intents/claim",
    body,
  });
  const accepted = await runWithMagazineBindings(bindings, () => POST(signed));
  assert.equal(accepted.status, 200);
  assert.equal((await accepted.json()).intent.status, "claimed");
  assert.match(accepted.headers.get("cache-control") ?? "", /no-store/);
});

test("operations machine routes reject oversized signed JSON while assets keep their cap", async () => {
  const db = new SqliteD1Database();
  const bindings = runtimeBindings(db);
  const { POST } = await import(routePaths.claim);
  const body = JSON.stringify({
    schema_version: "ops-claim.v1",
    worker_id: "worker:pro-magazine",
    lease_seconds: 60,
    padding: "x".repeat(5_000),
  });
  const signed = await signedMachineRequest({
    path: "/api/machine/operations/intents/claim",
    body,
  });
  const response = await runWithMagazineBindings(bindings, () => POST(signed));
  assert.equal(response.status, 413);
});

test("operations page labels health and keeps actions operator-only", () => {
  const source = `${readFileSync(routePaths.page, "utf8")}\n${readFileSync(routePaths.board, "utf8")}`;
  assert.match(source, /Collector freshness/);
  assert.match(source, /Edition state/);
  assert.match(source, /Breaking queue/);
  assert.match(source, /Research queue/);
  assert.match(source, /Failed intents/);
  assert.match(source, /Audit anchor freshness/);
  assert.match(source, /viewer\.role === "operator"/);
  assert.doesNotMatch(source, /const numeric = 0|story_version: 1/);
  assert.match(source, /action_targets/);
  assert.match(source, /disabled=.*precondition|precondition.*disabled/s);
});
