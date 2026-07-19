import type { D1DatabaseLike } from "./publication-repository.ts";
import { sha256Hex } from "./security.ts";

export const OPERATION_INTENT_KINDS = [
  "rerun_collector",
  "rebuild_edition",
  "quarantine_story",
  "release_story",
  "refresh_research_job",
] as const;
export const OPERATION_REASON_CODES = [
  "collector_recovery",
  "edition_recovery",
  "content_safety",
  "gates_reverified",
  "research_recovery",
] as const;

export type OperationIntentKind = (typeof OPERATION_INTENT_KINDS)[number];
export type OperationReasonCode = (typeof OPERATION_REASON_CODES)[number];
export type OperationStatus =
  | "queued"
  | "claimed"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled_revoked"
  | "outcome_unknown";

type CollectorParams = Readonly<{
  collector_id:
    | "intel-lake"
    | "mata-garuda"
    | "regulatory-watcher"
    | "notebooklm";
  failed_run_id: string;
}>;
type EditionParams = Readonly<{
  edition_id: string;
  expected_revision: number;
}>;
type StoryParams = Readonly<{
  story_id: string;
  story_version: number;
  expected_visibility_seq: number;
}>;
type ResearchParams = Readonly<{ research_job_id: string }>;
export type OperationParams =
  | CollectorParams
  | EditionParams
  | StoryParams
  | ResearchParams;

export type OperationIntentRequest = Readonly<{
  schema_version: "ops-intent-request.v1";
  intent_kind: OperationIntentKind;
  idempotency_key: string;
  reason_code: OperationReasonCode;
  expires_at: string;
  params: OperationParams;
}>;

export type OperationClaim = Readonly<{
  schema_version: "ops-claim-result.v1";
  intent_id: string;
  intent_kind: OperationIntentKind;
  params: OperationParams;
  target_id: string;
  target_key: string;
  actor_key: string;
  request_hash: string;
  reason_code: OperationReasonCode;
  status: "claimed";
  claim_token: string;
  fencing_token: number;
  target_fencing_token: number;
  lease_deadline: string;
  attempt_count: number;
}>;

export type OperationResult = Readonly<{
  schema_version: "ops-result.v1";
  intent_id: string;
  request_hash: string;
  status: "succeeded" | "failed" | "outcome_unknown";
  completed_at: string;
  receipt: Readonly<{
    code: "effect_acknowledged";
    target_id: string;
  }> | null;
  failure: Readonly<{
    code:
      | "capability_unavailable"
      | "invalid_target"
      | "effect_failed"
      | "lease_lost"
      | "intent_expired"
      | "retry_exhausted"
      | "stale_target_fence"
      | "outcome_ambiguous"
      | "internal_error";
  }> | null;
  claim_token: string;
  fencing_token: number;
  target_fencing_token: number;
  actor_key: string;
  target_key: string;
  target_id: string;
  effect_token: string;
  attested_policy_version: string;
  attestation_expires_at: string;
}>;

type IntentRow = Readonly<{
  intent_id: string;
  actor_key: string;
  effective_role: "operator";
  policy_version: string;
  idempotency_key: string;
  intent_kind: OperationIntentKind;
  params_json: string;
  request_hash: string;
  reason_code: OperationReasonCode;
  status: OperationStatus;
  attempt_limit: number;
  attempt_count: number;
  worker_id: string | null;
  claim_token: string | null;
  fencing_token: number;
  target_key: string;
  target_fencing_token: number;
  heartbeat_at: string | null;
  lease_deadline: string | null;
  effect_token: string | null;
  pre_effect_attested_at: string | null;
  attested_policy_version: string | null;
  attestation_expires_at: string | null;
  effect_consumed_at: string | null;
  expires_at: string;
  started_at: string | null;
  completed_at: string | null;
  failure_code: string | null;
  created_at: string;
}>;

const SHA256 = /^[a-f0-9]{64}$/;
const ENCODER = new TextEncoder();
const TOKEN = /^[A-Za-z0-9][A-Za-z0-9:_-]{15,127}$/;
const WORKER = /^worker:[a-z0-9]+(?:-[a-z0-9]+)*$/;
const IDS = {
  collectorRun: /^collector-run-[a-z0-9][a-z0-9-]{15,79}$/,
  edition: /^edition-[a-z0-9][a-z0-9-]{15,79}$/,
  story: /^story-[a-z0-9][a-z0-9-]{15,79}$/,
  research: /^research-job-[a-z0-9][a-z0-9-]{15,79}$/,
};
const COLLECTORS = [
  "intel-lake",
  "mata-garuda",
  "regulatory-watcher",
  "notebooklm",
] as const;
const REASON_BY_KIND: Record<OperationIntentKind, OperationReasonCode> = {
  rerun_collector: "collector_recovery",
  rebuild_edition: "edition_recovery",
  quarantine_story: "content_safety",
  release_story: "gates_reverified",
  refresh_research_job: "research_recovery",
};

function record(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new TypeError("invalid operation intent");
  }
  return value as Record<string, unknown>;
}

function exact(value: Record<string, unknown>, keys: readonly string[]): void {
  if (Object.keys(value).sort().join("\0") !== [...keys].sort().join("\0")) {
    throw new TypeError("invalid operation intent");
  }
}

function text(value: unknown, pattern: RegExp, maximum = 128): string {
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    value.length > maximum ||
    value.trim() !== value ||
    !pattern.test(value)
  ) {
    throw new TypeError("invalid operation intent");
  }
  return value;
}

function integer(value: unknown, minimum = 0): number {
  if (!Number.isSafeInteger(value) || (value as number) < minimum) {
    throw new TypeError("invalid operation intent");
  }
  return value as number;
}

function iso(value: unknown): string {
  if (typeof value !== "string" || value.length > 32) {
    throw new TypeError("invalid operation intent");
  }
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp) || new Date(timestamp).toISOString() !== value) {
    throw new TypeError("invalid operation intent");
  }
  return value;
}

function enumValue<T extends string>(value: unknown, values: readonly T[]): T {
  if (typeof value !== "string" || !values.includes(value as T)) {
    throw new TypeError("invalid operation intent");
  }
  return value as T;
}

function paramsFor(kind: OperationIntentKind, raw: unknown): OperationParams {
  const value = record(raw);
  if (kind === "rerun_collector") {
    exact(value, ["collector_id", "failed_run_id"]);
    return {
      collector_id: enumValue(value.collector_id, COLLECTORS),
      failed_run_id: text(value.failed_run_id, IDS.collectorRun, 96),
    };
  }
  if (kind === "rebuild_edition") {
    exact(value, ["edition_id", "expected_revision"]);
    return {
      edition_id: text(value.edition_id, IDS.edition, 96),
      expected_revision: integer(value.expected_revision),
    };
  }
  if (kind === "quarantine_story" || kind === "release_story") {
    exact(value, ["story_id", "story_version", "expected_visibility_seq"]);
    return {
      story_id: text(value.story_id, IDS.story, 96),
      story_version: integer(value.story_version, 1),
      expected_visibility_seq: integer(value.expected_visibility_seq),
    };
  }
  exact(value, ["research_job_id"]);
  return {
    research_job_id: text(value.research_job_id, IDS.research, 96),
  };
}

export function parseOperationIntentRequest(
  raw: unknown,
): OperationIntentRequest {
  const value = record(raw);
  exact(value, [
    "schema_version",
    "intent_kind",
    "idempotency_key",
    "reason_code",
    "expires_at",
    "params",
  ]);
  if (value.schema_version !== "ops-intent-request.v1") {
    throw new TypeError("invalid operation intent");
  }
  const intentKind = enumValue(value.intent_kind, OPERATION_INTENT_KINDS);
  const reasonCode = enumValue(value.reason_code, OPERATION_REASON_CODES);
  if (REASON_BY_KIND[intentKind] !== reasonCode) {
    throw new TypeError("invalid operation intent");
  }
  return {
    schema_version: "ops-intent-request.v1",
    intent_kind: intentKind,
    idempotency_key: text(
      value.idempotency_key,
      /^[a-z0-9][a-z0-9_-]{15,95}$/,
      96,
    ),
    reason_code: reasonCode,
    expires_at: iso(value.expires_at),
    params: paramsFor(intentKind, value.params),
  };
}

export function parseOperationResult(raw: unknown): OperationResult {
  const value = record(raw);
  exact(value, [
    "schema_version",
    "intent_id",
    "request_hash",
    "status",
    "completed_at",
    "receipt",
    "failure",
    "claim_token",
    "fencing_token",
    "target_fencing_token",
    "actor_key",
    "target_key",
    "target_id",
    "effect_token",
    "attested_policy_version",
    "attestation_expires_at",
  ]);
  if (value.schema_version !== "ops-result.v1") {
    throw new TypeError("invalid operation result");
  }
  const status = enumValue(value.status, [
    "succeeded",
    "failed",
    "outcome_unknown",
  ] as const);
  let receipt: OperationResult["receipt"] = null;
  let failure: OperationResult["failure"] = null;
  if (status === "succeeded") {
    const item = record(value.receipt);
    exact(item, ["code", "target_id"]);
    if (item.code !== "effect_acknowledged" || value.failure !== null) {
      throw new TypeError("invalid operation result");
    }
    receipt = {
      code: "effect_acknowledged",
      target_id: text(item.target_id, /^[a-z][a-z0-9-]{15,95}$/, 96),
    };
  } else {
    if (value.receipt !== null) throw new TypeError("invalid operation result");
    const item = record(value.failure);
    exact(item, ["code"]);
    failure = {
      code: enumValue(item.code, [
        "capability_unavailable",
        "invalid_target",
        "effect_failed",
        "lease_lost",
        "intent_expired",
        "retry_exhausted",
        "stale_target_fence",
        "outcome_ambiguous",
        "internal_error",
      ] as const),
    };
  }
  return {
    schema_version: "ops-result.v1",
    intent_id: text(value.intent_id, /^ops-intent-[A-Za-z0-9-]{16,96}$/, 112),
    request_hash: text(value.request_hash, SHA256, 64),
    status,
    completed_at: iso(value.completed_at),
    receipt,
    failure,
    claim_token: text(value.claim_token, TOKEN),
    fencing_token: integer(value.fencing_token, 1),
    target_fencing_token: integer(value.target_fencing_token, 1),
    actor_key: text(value.actor_key, SHA256, 64),
    target_key: text(value.target_key, /^[a-z]+:[a-z][a-z0-9-]{15,95}$/, 112),
    target_id: text(value.target_id, /^[a-z][a-z0-9-]{15,95}$/, 96),
    effect_token: text(value.effect_token, TOKEN),
    attested_policy_version: text(
      value.attested_policy_version,
      /^[A-Za-z0-9][A-Za-z0-9._:-]{2,95}$/,
      96,
    ),
    attestation_expires_at: iso(value.attestation_expires_at),
  };
}

export function parseOperationClaimRequest(raw: unknown): Readonly<{
  workerId: string;
  leaseSeconds: number;
}> {
  const value = record(raw);
  exact(value, ["schema_version", "worker_id", "lease_seconds"]);
  if (value.schema_version !== "ops-claim.v1")
    throw new TypeError("invalid operation intent");
  return {
    workerId: text(value.worker_id, WORKER, 96),
    leaseSeconds: integer(value.lease_seconds, 15),
  };
}

export function parseOperationLeaseRequest(
  raw: unknown,
  schemaVersion:
    | "ops-start.v1"
    | "ops-heartbeat.v1"
    | "ops-pre-effect-attest.v1",
): Readonly<{
  claimToken: string;
  fencingToken: number;
  leaseSeconds: number | null;
}> {
  const value = record(raw);
  const heartbeat = schemaVersion === "ops-heartbeat.v1";
  exact(
    value,
    heartbeat
      ? ["schema_version", "claim_token", "fencing_token", "lease_seconds"]
      : ["schema_version", "claim_token", "fencing_token"],
  );
  if (value.schema_version !== schemaVersion)
    throw new TypeError("invalid operation intent");
  const leaseSeconds = heartbeat ? integer(value.lease_seconds, 15) : null;
  if (leaseSeconds !== null && leaseSeconds > 300)
    throw new TypeError("invalid operation intent");
  return {
    claimToken: text(value.claim_token, TOKEN),
    fencingToken: integer(value.fencing_token, 1),
    leaseSeconds,
  };
}

function targetId(kind: OperationIntentKind, params: OperationParams): string {
  if (kind === "rerun_collector")
    return (params as CollectorParams).failed_run_id;
  if (kind === "rebuild_edition") return (params as EditionParams).edition_id;
  if (kind === "refresh_research_job")
    return (params as ResearchParams).research_job_id;
  return (params as StoryParams).story_id;
}

function targetKey(kind: OperationIntentKind, params: OperationParams): string {
  const id = targetId(kind, params);
  if (kind === "rerun_collector") return `collector:${id}`;
  if (kind === "rebuild_edition") return `edition:${id}`;
  if (kind === "refresh_research_job") return `research:${id}`;
  return `story:${id}`;
}

function changes(result: { meta?: Readonly<{ changes?: number }> }): number {
  return result.meta?.changes ?? 0;
}

function intentView(row: IntentRow) {
  return {
    intent_id: row.intent_id,
    intent_kind: row.intent_kind,
    params: JSON.parse(row.params_json) as OperationParams,
    target_id: targetId(
      row.intent_kind,
      JSON.parse(row.params_json) as OperationParams,
    ),
    target_key: row.target_key,
    target_fencing_token: row.target_fencing_token,
    request_hash: row.request_hash,
    reason_code: row.reason_code,
    status: row.status,
    attempt_count: row.attempt_count,
    fencing_token: row.fencing_token,
    lease_deadline: row.lease_deadline,
    created_at: row.created_at,
    expires_at: row.expires_at,
    completed_at: row.completed_at,
    failure_code: row.failure_code,
  };
}

export function createOperationsRepository(
  db: D1DatabaseLike,
  options: Readonly<{ now?: () => string; randomId?: () => string }> = {},
) {
  const now = options.now ?? (() => new Date().toISOString());
  const randomId = options.randomId ?? (() => crypto.randomUUID());
  let sequence = 0;
  const id = (prefix: string) => `${prefix}-${randomId()}-${++sequence}`;
  const load = (intentId: string) =>
    db
      .prepare("SELECT * FROM ops_intents WHERE intent_id = ?")
      .bind(intentId)
      .first<IntentRow>();
  const audit = (
    row: IntentRow,
    eventType: string,
    status: OperationStatus,
    failureCode: string | null = null,
  ) =>
    db
      .prepare(
        "INSERT INTO ops_audit_events(event_id, intent_id, event_type, actor_key, worker_id, status, failure_code, fencing_token, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
      )
      .bind(
        id("ops-audit"),
        row.intent_id,
        eventType,
        row.actor_key,
        row.worker_id,
        status,
        failureCode,
        row.fencing_token,
        now(),
      );

  const terminalize = async (
    row: IntentRow,
    status: "failed" | "cancelled_revoked" | "outcome_unknown",
    failureCode: string,
    eventType: "failed" | "cancelled_revoked" | "outcome_unknown",
  ): Promise<boolean> => {
    const completedAt = now();
    const receiptJson = JSON.stringify({
      schema_version: "ops-terminal-receipt.v1",
      status,
      completed_at: completedAt,
      failure: { code: failureCode },
    });
    const receiptHash = await sha256Hex(ENCODER.encode(receiptJson));
    const terminal = { ...row, status, failure_code: failureCode };
    const results = await db.batch([
      db
        .prepare(
          "UPDATE ops_intents SET status = ?, completed_at = ?, failure_code = ? WHERE intent_id = ? AND status IN ('queued', 'claimed', 'running')",
        )
        .bind(status, completedAt, failureCode, row.intent_id),
      db
        .prepare(
          "INSERT INTO ops_receipts(receipt_id, intent_id, status, receipt_json, receipt_hash, request_hash, key_id, body_hash, fencing_token, attested_policy_version, created_at) VALUES (?, ?, ?, ?, ?, ?, 'server-terminal', ?, ?, ?, ?)",
        )
        .bind(
          id("ops-receipt"),
          row.intent_id,
          status,
          receiptJson,
          receiptHash,
          row.request_hash,
          receiptHash,
          row.fencing_token,
          row.attested_policy_version,
          completedAt,
        ),
      audit(terminal, eventType, status, failureCode),
    ]);
    return changes(results[0] ?? {}) === 1;
  };

  return {
    async createIntent(
      input: Readonly<{
        actorKey: string;
        effectiveRole: string;
        policyVersion: string;
        operatorActorKeys: readonly string[];
        request: OperationIntentRequest;
      }>,
    ) {
      if (
        input.effectiveRole !== "operator" ||
        !input.operatorActorKeys.includes(input.actorKey)
      ) {
        throw new Error("operator authorization revoked");
      }
      const current = now();
      const expiryMs = Date.parse(input.request.expires_at);
      const delta = expiryMs - Date.parse(current);
      if (delta <= 0 || delta > 86_400_000) {
        throw new TypeError("invalid operation intent expiry");
      }
      const paramsJson = JSON.stringify(input.request.params);
      const operationTargetKey = targetKey(
        input.request.intent_kind,
        input.request.params,
      );
      const requestHash = await sha256Hex(
        ENCODER.encode(
          JSON.stringify({
            schema_version: input.request.schema_version,
            intent_kind: input.request.intent_kind,
            reason_code: input.request.reason_code,
            expires_at: input.request.expires_at,
            params: input.request.params,
          }),
        ),
      );
      const existing = await db
        .prepare(
          "SELECT * FROM ops_intents WHERE actor_key = ? AND idempotency_key = ?",
        )
        .bind(input.actorKey, input.request.idempotency_key)
        .first<IntentRow>();
      if (existing) {
        if (existing.request_hash !== requestHash) {
          throw new Error("idempotency conflict");
        }
        return { status: "replay" as const, intent: intentView(existing) };
      }
      const intentId = id("ops-intent");
      const provisional = {
        intent_id: intentId,
        actor_key: input.actorKey,
        effective_role: "operator" as const,
        policy_version: input.policyVersion,
        idempotency_key: input.request.idempotency_key,
        intent_kind: input.request.intent_kind,
        params_json: paramsJson,
        request_hash: requestHash,
        reason_code: input.request.reason_code,
        status: "queued" as const,
        attempt_limit: 3,
        attempt_count: 0,
        worker_id: null,
        claim_token: null,
        fencing_token: 0,
        target_key: operationTargetKey,
        target_fencing_token: 0,
        heartbeat_at: null,
        lease_deadline: null,
        effect_token: null,
        pre_effect_attested_at: null,
        attested_policy_version: null,
        attestation_expires_at: null,
        effect_consumed_at: null,
        expires_at: input.request.expires_at,
        started_at: null,
        completed_at: null,
        failure_code: null,
        created_at: current,
      } satisfies IntentRow;
      await db.batch([
        db
          .prepare(
            "INSERT INTO ops_intents(intent_id, actor_key, effective_role, policy_version, idempotency_key, intent_kind, params_json, request_hash, reason_code, status, attempt_limit, attempt_count, fencing_token, target_key, target_fencing_token, expires_at, created_at) VALUES (?, ?, 'operator', ?, ?, ?, ?, ?, ?, 'queued', 3, 0, 0, ?, 0, ?, ?)",
          )
          .bind(
            intentId,
            input.actorKey,
            input.policyVersion,
            input.request.idempotency_key,
            input.request.intent_kind,
            paramsJson,
            requestHash,
            input.request.reason_code,
            operationTargetKey,
            input.request.expires_at,
            current,
          ),
        audit(provisional, "created", "queued"),
      ]);
      return { status: "created" as const, intent: intentView(provisional) };
    },

    async getIntent(intentId: string) {
      const row = await load(intentId);
      return row ? intentView(row) : null;
    },

    async listIntents(limit = 50) {
      const rows = await db
        .prepare("SELECT * FROM ops_intents ORDER BY created_at DESC LIMIT ?")
        .bind(Math.max(1, Math.min(limit, 100)))
        .all<IntentRow>();
      return (rows.results ?? []).map(intentView);
    },

    async healthSnapshot() {
      const [collectors, edition, breaking, research, failed, anchor] =
        await Promise.all([
          db
            .prepare(
              "SELECT s.system_id, s.health, s.expected_cadence_seconds, s.updated_at, (SELECT max(c.completed_at) FROM collector_runs c WHERE c.system_id = s.system_id AND c.status = 'healthy') AS latest_success_at FROM source_systems s ORDER BY s.system_id",
            )
            .all<{
              system_id: string;
              health: string;
              expected_cadence_seconds: number;
              updated_at: string;
              latest_success_at: string | null;
            }>(),
          db
            .prepare(
              "SELECT current_edition_id, current_revision FROM edition_pointer WHERE singleton_id = 1",
            )
            .first<{
              current_edition_id: string | null;
              current_revision: number;
            }>(),
          db
            .prepare(
              "SELECT active_revision, updated_at, (SELECT count(*) FROM breaking_entries b WHERE b.breaking_revision = breaking_pointer.active_revision AND b.publication_state = 'published') AS queued_count FROM breaking_pointer WHERE singleton_id = 1",
            )
            .first<{
              active_revision: number;
              updated_at: string | null;
              queued_count: number;
            }>(),
          db
            .prepare(
              "SELECT status, count(*) AS count FROM research_jobs WHERE status IN ('queued', 'claimed', 'failed') GROUP BY status",
            )
            .all<{ status: string; count: number }>(),
          db
            .prepare(
              "SELECT status, count(*) AS count FROM ops_intents WHERE status IN ('failed', 'outcome_unknown') GROUP BY status",
            )
            .all<{ status: string; count: number }>(),
          db
            .prepare(
              "SELECT stream_seq, updated_at FROM audit_anchor_heads ORDER BY updated_at DESC LIMIT 1",
            )
            .first<{ stream_seq: number; updated_at: string }>(),
        ]);
      const counts = (rows: readonly { status: string; count: number }[]) =>
        Object.fromEntries(rows.map((row) => [row.status, Number(row.count)]));
      return {
        schema_version: "ops-health.v1" as const,
        observed_at: now(),
        collectors: (collectors.results ?? []).map((row) => ({
          collector_id: row.system_id,
          health: [
            "healthy",
            "delayed",
            "degraded",
            "unavailable",
            "unknown",
          ].includes(row.health)
            ? row.health
            : "unknown",
          expected_cadence_seconds: row.expected_cadence_seconds,
          latest_success_at: row.latest_success_at,
          observed_at: row.updated_at,
        })),
        edition: edition ?? { current_edition_id: null, current_revision: 0 },
        breaking: breaking ?? {
          active_revision: 0,
          updated_at: null,
          queued_count: 0,
        },
        research_queue: counts(research.results ?? []),
        failed_intents: counts(failed.results ?? []),
        audit_anchor:
          anchor === null
            ? { stream_seq: 0, updated_at: null }
            : { stream_seq: anchor.stream_seq, updated_at: anchor.updated_at },
      };
    },

    async actionTargets() {
      const [collectorRuns, edition, stories, researchJobs] = await Promise.all(
        [
          db
            .prepare(
              "SELECT run_id, system_id FROM collector_runs WHERE status IN ('delayed', 'degraded', 'unavailable', 'unknown') ORDER BY completed_at DESC LIMIT 25",
            )
            .all<{
              run_id: string;
              system_id: CollectorParams["collector_id"];
            }>(),
          db
            .prepare(
              "SELECT current_edition_id, current_revision FROM edition_pointer WHERE singleton_id = 1",
            )
            .first<{
              current_edition_id: string | null;
              current_revision: number;
            }>(),
          db
            .prepare(
              "SELECT s.story_id, s.current_version, COALESCE((SELECT max(v.visibility_seq) FROM story_visibility_events v WHERE v.story_id = s.story_id), 0) AS visibility_seq FROM stories s WHERE s.current_version > 0 ORDER BY s.updated_at DESC LIMIT 50",
            )
            .all<{
              story_id: string;
              current_version: number;
              visibility_seq: number;
            }>(),
          db
            .prepare(
              "SELECT job_id FROM research_jobs WHERE status = 'failed' ORDER BY completed_at DESC LIMIT 25",
            )
            .all<{ job_id: string }>(),
        ],
      );
      const storyTargets = (stories.results ?? []).map((row) => ({
        target_id: row.story_id,
        label: `${row.story_id} · version ${row.current_version} · visibility ${row.visibility_seq}`,
        params: {
          story_id: row.story_id,
          story_version: row.current_version,
          expected_visibility_seq: row.visibility_seq,
        },
      }));
      return {
        rerun_collector: (collectorRuns.results ?? []).map((row) => ({
          target_id: row.run_id,
          label: `${row.system_id} · ${row.run_id}`,
          params: { collector_id: row.system_id, failed_run_id: row.run_id },
        })),
        rebuild_edition:
          edition?.current_edition_id === null || edition === null
            ? []
            : [
                {
                  target_id: edition.current_edition_id,
                  label: `${edition.current_edition_id} · revision ${edition.current_revision}`,
                  params: {
                    edition_id: edition.current_edition_id,
                    expected_revision: edition.current_revision,
                  },
                },
              ],
        quarantine_story: storyTargets,
        release_story: storyTargets,
        refresh_research_job: (researchJobs.results ?? []).map((row) => ({
          target_id: row.job_id,
          label: row.job_id,
          params: { research_job_id: row.job_id },
        })),
      } satisfies Record<
        OperationIntentKind,
        readonly Readonly<{
          target_id: string;
          label: string;
          params: OperationParams;
        }>[]
      >;
    },

    async claimNext(
      input: Readonly<{
        workerId: string;
        leaseSeconds: number;
        operatorActorKeys: readonly string[];
        policyVersion: string;
      }>,
    ): Promise<OperationClaim | null> {
      if (!WORKER.test(input.workerId))
        throw new TypeError("invalid worker id");
      if (
        !Number.isInteger(input.leaseSeconds) ||
        input.leaseSeconds < 15 ||
        input.leaseSeconds > 300
      ) {
        throw new TypeError("invalid lease seconds");
      }
      const instant = now();
      const candidates = await db
        .prepare(
          "SELECT * FROM ops_intents WHERE status IN ('queued', 'claimed', 'running') ORDER BY created_at LIMIT 50",
        )
        .all<IntentRow>();
      for (const candidate of candidates.results ?? []) {
        if (
          candidate.status === "running" &&
          candidate.lease_deadline !== null &&
          candidate.lease_deadline <= instant
        ) {
          await terminalize(
            candidate,
            "outcome_unknown",
            "outcome_ambiguous",
            "outcome_unknown",
          );
          continue;
        }
        const revoked =
          candidate.expires_at <= instant ||
          !input.operatorActorKeys.includes(candidate.actor_key);
        if (revoked) {
          await terminalize(
            candidate,
            "cancelled_revoked",
            candidate.expires_at <= instant
              ? "intent_expired"
              : "authorization_revoked",
            "cancelled_revoked",
          );
          continue;
        }
        if (
          candidate.status === "claimed" &&
          (candidate.lease_deadline === null ||
            candidate.lease_deadline > instant)
        )
          continue;
        if (candidate.attempt_count >= candidate.attempt_limit) {
          await terminalize(candidate, "failed", "retry_exhausted", "failed");
          continue;
        }
        const leaseDeadline = new Date(
          Date.parse(instant) + input.leaseSeconds * 1000,
        ).toISOString();
        const claimToken = id("ops-claim-token");
        await db
          .prepare(
            "INSERT OR IGNORE INTO ops_target_fences(target_key, next_fencing_token, effect_fencing_token, updated_at) VALUES (?, 0, 0, ?)",
          )
          .bind(candidate.target_key, instant)
          .run();
        const fence = await db
          .prepare(
            "SELECT next_fencing_token FROM ops_target_fences WHERE target_key = ?",
          )
          .bind(candidate.target_key)
          .first<{ next_fencing_token: number }>();
        if (!fence) throw new Error("target fence unavailable");
        const nextTargetFence = fence.next_fencing_token + 1;
        const predicted = {
          ...candidate,
          worker_id: input.workerId,
          claim_token: claimToken,
          fencing_token: candidate.fencing_token + 1,
          target_fencing_token: nextTargetFence,
          status: "claimed" as const,
        };
        const results = await db.batch([
          db
            .prepare(
              "UPDATE ops_target_fences SET next_fencing_token = next_fencing_token + 1, updated_at = ? WHERE target_key = ? AND next_fencing_token = ?",
            )
            .bind(instant, candidate.target_key, fence.next_fencing_token),
          db
            .prepare(
              "UPDATE ops_intents SET status = 'claimed', worker_id = ?, claim_token = ?, fencing_token = fencing_token + 1, target_fencing_token = ?, attempt_count = attempt_count + 1, heartbeat_at = ?, lease_deadline = ?, effect_token = NULL, pre_effect_attested_at = NULL, attested_policy_version = NULL, attestation_expires_at = NULL, effect_consumed_at = NULL WHERE intent_id = ? AND ((status = 'queued') OR (status = 'claimed' AND lease_deadline <= ?)) AND attempt_count < attempt_limit AND (SELECT next_fencing_token FROM ops_target_fences WHERE target_key = ?) = ?",
            )
            .bind(
              input.workerId,
              claimToken,
              nextTargetFence,
              instant,
              leaseDeadline,
              candidate.intent_id,
              instant,
              candidate.target_key,
              nextTargetFence,
            ),
          audit(
            predicted,
            candidate.status === "claimed" ? "reclaimed" : "claimed",
            "claimed",
          ),
        ]);
        if (changes(results[0] ?? {}) !== 1 || changes(results[1] ?? {}) !== 1)
          continue;
        const claimed = (await load(candidate.intent_id))!;
        return {
          schema_version: "ops-claim-result.v1",
          intent_id: claimed.intent_id,
          intent_kind: claimed.intent_kind,
          params: JSON.parse(claimed.params_json) as OperationParams,
          target_id: targetId(
            claimed.intent_kind,
            JSON.parse(claimed.params_json) as OperationParams,
          ),
          target_key: claimed.target_key,
          actor_key: claimed.actor_key,
          request_hash: claimed.request_hash,
          reason_code: claimed.reason_code,
          status: "claimed",
          claim_token: claimed.claim_token!,
          fencing_token: claimed.fencing_token,
          target_fencing_token: claimed.target_fencing_token,
          lease_deadline: claimed.lease_deadline!,
          attempt_count: claimed.attempt_count,
        };
      }
      return null;
    },

    async start(
      claim: Pick<
        OperationClaim,
        "intent_id" | "claim_token" | "fencing_token"
      >,
    ) {
      const instant = now();
      const before = await load(claim.intent_id);
      if (!before) throw new Error("lease lost or terminal intent");
      const results = await db.batch([
        db
          .prepare(
            "UPDATE ops_intents SET status = 'running', started_at = COALESCE(started_at, ?) WHERE intent_id = ? AND status = 'claimed' AND claim_token = ? AND fencing_token = ? AND lease_deadline > ?",
          )
          .bind(
            instant,
            claim.intent_id,
            claim.claim_token,
            claim.fencing_token,
            instant,
          ),
        audit({ ...before, status: "running" }, "started", "running"),
      ]);
      if (changes(results[0] ?? {}) !== 1)
        throw new Error("lease lost or terminal intent");
      const row = (await load(claim.intent_id))!;
      return intentView(row);
    },

    async heartbeat(
      claim: Pick<
        OperationClaim,
        "intent_id" | "claim_token" | "fencing_token"
      >,
      leaseSeconds: number,
    ) {
      const instant = now();
      const lease = new Date(
        Date.parse(instant) + leaseSeconds * 1000,
      ).toISOString();
      const result = await db
        .prepare(
          "UPDATE ops_intents SET heartbeat_at = ?, lease_deadline = ? WHERE intent_id = ? AND status IN ('claimed', 'running') AND claim_token = ? AND fencing_token = ? AND lease_deadline > ?",
        )
        .bind(
          instant,
          lease,
          claim.intent_id,
          claim.claim_token,
          claim.fencing_token,
          instant,
        )
        .run();
      if (changes(result) !== 1)
        throw new Error("lease lost or terminal intent");
      return intentView((await load(claim.intent_id))!);
    },

    async attestPreEffect(
      claim: Pick<
        OperationClaim,
        "intent_id" | "claim_token" | "fencing_token"
      >,
      authorization: Readonly<{
        operatorActorKeys: readonly string[];
        policyVersion: string;
      }>,
    ) {
      const row = await load(claim.intent_id);
      const instant = now();
      if (
        !row ||
        row.status !== "running" ||
        row.claim_token !== claim.claim_token ||
        row.fencing_token !== claim.fencing_token ||
        row.lease_deadline === null ||
        row.lease_deadline <= instant
      ) {
        throw new Error("lease lost or terminal intent");
      }
      const targetFence = await db
        .prepare(
          "SELECT next_fencing_token FROM ops_target_fences WHERE target_key = ?",
        )
        .bind(row.target_key)
        .first<{ next_fencing_token: number }>();
      if (
        !targetFence ||
        targetFence.next_fencing_token !== row.target_fencing_token
      ) {
        throw new Error("stale target fence");
      }
      const expired = row.expires_at <= instant;
      if (expired || !authorization.operatorActorKeys.includes(row.actor_key)) {
        const failureCode = expired
          ? "intent_expired"
          : "authorization_revoked";
        if (
          !(await terminalize(
            row,
            "cancelled_revoked",
            failureCode,
            "cancelled_revoked",
          ))
        ) {
          throw new Error("lease lost or terminal intent");
        }
        return {
          authorized: false as const,
          status: "cancelled_revoked" as const,
          policy_version: authorization.policyVersion,
          effect_token: null,
        };
      }
      const effectToken = id("ops-effect-token");
      const attestationExpiresAt = new Date(
        Math.min(
          Date.parse(instant) + 30_000,
          Date.parse(row.lease_deadline),
          Date.parse(row.expires_at),
        ),
      ).toISOString();
      const results = await db.batch([
        db
          .prepare(
            "UPDATE ops_target_fences SET effect_fencing_token = ?, updated_at = ? WHERE target_key = ? AND next_fencing_token = ? AND effect_fencing_token < ?",
          )
          .bind(
            row.target_fencing_token,
            instant,
            row.target_key,
            row.target_fencing_token,
            row.target_fencing_token,
          ),
        db
          .prepare(
            "UPDATE ops_intents SET effect_token = ?, pre_effect_attested_at = ?, attested_policy_version = ?, attestation_expires_at = ? WHERE intent_id = ? AND status = 'running' AND claim_token = ? AND fencing_token = ? AND target_fencing_token = ? AND lease_deadline > ? AND expires_at > ? AND effect_token IS NULL",
          )
          .bind(
            effectToken,
            instant,
            authorization.policyVersion,
            attestationExpiresAt,
            row.intent_id,
            claim.claim_token,
            claim.fencing_token,
            row.target_fencing_token,
            instant,
            instant,
          ),
        audit(
          {
            ...row,
            effect_token: effectToken,
            attested_policy_version: authorization.policyVersion,
            attestation_expires_at: attestationExpiresAt,
          },
          "pre_effect_attested",
          "running",
        ),
      ]);
      if (changes(results[0] ?? {}) !== 1 || changes(results[1] ?? {}) !== 1)
        throw new Error("lease lost or terminal intent");
      return {
        schema_version: "ops-effect-attestation.v1" as const,
        authorized: true as const,
        status: "running" as const,
        intent_id: row.intent_id,
        request_hash: row.request_hash,
        actor_key: row.actor_key,
        target_id: targetId(
          row.intent_kind,
          JSON.parse(row.params_json) as OperationParams,
        ),
        target_key: row.target_key,
        fencing_token: row.fencing_token,
        target_fencing_token: row.target_fencing_token,
        policy_version: authorization.policyVersion,
        effect_token: effectToken,
        attested_at: instant,
        expires_at: attestationExpiresAt,
      };
    },

    async complete(envelope: OperationResult, keyId: string, bodyHash: string) {
      const receiptJson = JSON.stringify({
        schema_version: envelope.schema_version,
        status: envelope.status,
        completed_at: envelope.completed_at,
        receipt: envelope.receipt,
        failure: envelope.failure,
      });
      const receiptHash = await sha256Hex(ENCODER.encode(receiptJson));
      const existing = await db
        .prepare(
          "SELECT receipt_hash, body_hash FROM ops_receipts WHERE intent_id = ?",
        )
        .bind(envelope.intent_id)
        .first<{ receipt_hash: string; body_hash: string }>();
      if (existing) {
        if (
          existing.receipt_hash !== receiptHash ||
          existing.body_hash !== bodyHash
        ) {
          throw new Error("terminal receipt conflict");
        }
        return { status: "replay" as const };
      }
      const row = await load(envelope.intent_id);
      const expectedTargetId = row
        ? targetId(
            row.intent_kind,
            JSON.parse(row.params_json) as OperationParams,
          )
        : null;
      const targetFence = row
        ? await db
            .prepare(
              "SELECT next_fencing_token, effect_fencing_token FROM ops_target_fences WHERE target_key = ?",
            )
            .bind(row.target_key)
            .first<{
              next_fencing_token: number;
              effect_fencing_token: number;
            }>()
        : null;
      if (
        !row ||
        row.status !== "running" ||
        row.request_hash !== envelope.request_hash ||
        row.actor_key !== envelope.actor_key ||
        row.target_key !== envelope.target_key ||
        expectedTargetId !== envelope.target_id ||
        row.claim_token !== envelope.claim_token ||
        row.fencing_token !== envelope.fencing_token ||
        row.target_fencing_token !== envelope.target_fencing_token ||
        row.effect_token !== envelope.effect_token ||
        row.attested_policy_version !== envelope.attested_policy_version ||
        row.attestation_expires_at !== envelope.attestation_expires_at ||
        row.effect_consumed_at !== null ||
        targetFence?.next_fencing_token !== envelope.target_fencing_token ||
        targetFence?.effect_fencing_token !== envelope.target_fencing_token
      ) {
        throw new Error("lease lost or terminal intent");
      }
      const failureCode = envelope.failure?.code ?? null;
      const update = db
        .prepare(
          "UPDATE ops_intents SET status = ?, completed_at = ?, failure_code = ?, effect_consumed_at = ? WHERE intent_id = ? AND status = 'running' AND claim_token = ? AND fencing_token = ? AND target_fencing_token = ? AND effect_token = ? AND effect_consumed_at IS NULL",
        )
        .bind(
          envelope.status,
          envelope.completed_at,
          failureCode,
          now(),
          row.intent_id,
          envelope.claim_token,
          envelope.fencing_token,
          envelope.target_fencing_token,
          envelope.effect_token,
        );
      const insert = db
        .prepare(
          "INSERT INTO ops_receipts(receipt_id, intent_id, status, receipt_json, receipt_hash, request_hash, key_id, body_hash, fencing_token, attested_policy_version, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        )
        .bind(
          id("ops-receipt"),
          row.intent_id,
          envelope.status,
          receiptJson,
          receiptHash,
          envelope.request_hash,
          keyId,
          text(bodyHash, SHA256, 64),
          envelope.fencing_token,
          envelope.attested_policy_version,
          now(),
        );
      const results = await db.batch([
        update,
        insert,
        audit(
          { ...row, status: envelope.status, failure_code: failureCode },
          envelope.status,
          envelope.status,
          failureCode,
        ),
      ]);
      if (changes(results[0] ?? {}) !== 1)
        throw new Error("lease lost or terminal intent");
      return { status: "created" as const };
    },
  };
}
