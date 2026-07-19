import type { D1DatabaseLike } from "./publication-repository.ts";
import { normalizeHttpsEvidenceUrl, sha256Hex } from "./security.ts";

export const RESEARCH_MODES = [
  "search",
  "compare",
  "timeline",
  "notebook_insight",
] as const;
export const RESEARCH_TEMPLATES = ["explain", "compare", "timeline"] as const;

export type ResearchMode = (typeof RESEARCH_MODES)[number];
export type ResearchTemplate = (typeof RESEARCH_TEMPLATES)[number];
export type ResearchStatus =
  | "queued"
  | "claimed"
  | "completed"
  | "failed"
  | "cancelled";

export type ResearchCatalog = Readonly<{
  schema_version: "research-catalog.v1";
  topics: readonly Readonly<{ id: string; label: string }>[];
  entities: readonly Readonly<{ id: string; label: string }>[];
  index_tokens: readonly string[];
  source_system_ids: readonly string[];
}>;

export type ResearchFacets = Readonly<{
  domains: readonly (
    | "immigration"
    | "company"
    | "tax"
    | "property"
    | "compliance"
  )[];
  source_system_ids: readonly string[];
  evidence_types: readonly (
    | "official"
    | "journalism"
    | "research"
    | "dataset"
  )[];
  confidence: readonly ("normal" | "cautious" | "abstain")[];
  lifecycle_states: readonly ("published" | "amended" | "superseded")[];
  languages: readonly ("en" | "id")[];
}>;

export type ResearchRequestV1 = Readonly<{
  schema_version: "research-request.v1";
  mode: ResearchMode;
  topic_ids: readonly string[];
  entity_ids: readonly string[];
  index_tokens: readonly string[];
  template: ResearchTemplate | null;
  facets: ResearchFacets;
}>;

export type ResearchEvidenceV1 = Readonly<{
  evidence_id: string;
  publisher: string;
  citation: string;
  canonical_url: string | null;
  source_type: "official" | "journalism" | "research" | "dataset";
  published_at: string | null;
}>;

export type ResearchClaimV1 = Readonly<{
  claim_id: string;
  kind: "fact" | "numeric" | "analysis";
  text: string;
  numeric_value: string | null;
  numeric_unit: string | null;
  as_of: string | null;
  evidence: readonly ResearchEvidenceV1[];
}>;

export type ResearchResultV1 = Readonly<{
  schema_version: "research-result.v1";
  job_id: string;
  request_hash: string;
  mode: ResearchMode;
  status: "completed" | "failed";
  completed_at: string;
  summary: string | null;
  claims: readonly ResearchClaimV1[];
  failure: Readonly<{
    code:
      | "source_unavailable"
      | "dlp_rejected"
      | "evidence_missing"
      | "invalid_result"
      | "internal_error";
  }> | null;
  claim_token: string;
  fencing_token: number;
}>;

export type ResearchJobView = Readonly<{
  job_id: string;
  actor_key: string;
  mode: ResearchMode;
  request: ResearchRequestV1;
  request_hash: string;
  status: ResearchStatus;
  claim_token: string | null;
  fencing_token: number;
  lease_deadline: string | null;
  created_at: string;
  expires_at: string;
  completed_at: string | null;
  result: ResearchResultV1 | null;
}>;

type JobRow = Readonly<{
  job_id: string;
  actor_key: string;
  mode: ResearchMode;
  query_json: string;
  request_hash: string;
  idempotency_key: string;
  status: ResearchStatus;
  claim_token: string | null;
  fencing_token: number;
  lease_deadline: string | null;
  created_at: string;
  expires_at: string;
  completed_at: string | null;
  result_json: string | null;
}>;

type ResultRow = Readonly<{
  result_hash: string;
  receipt_body_hash: string;
  result_json: string;
}>;

type RepositoryOptions = Readonly<{
  now?: () => string;
  randomId?: () => string;
}>;

const encoder = new TextEncoder();
const SHA256 = /^[a-f0-9]{64}$/;
const STABLE_ID = /^(?:topic|entity|token):[a-z0-9]+(?:-[a-z0-9]+)*$/;
const WORKER_ID = /^worker:[a-z0-9]+(?:-[a-z0-9]+)*$/;
const TOKEN = /^[A-Za-z0-9][A-Za-z0-9:_-]{15,127}$/;
const DATE = /^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z)?$/;
const MAX_CATALOG_BYTES = 512_000;
const MAX_REQUEST_BYTES = 32_000;
const MAX_RESULT_BYTES = 128_000;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function exactKeys(
  value: Record<string, unknown>,
  expected: readonly string[],
  label: string,
): void {
  const actual = Object.keys(value).sort();
  if (actual.join("\0") !== [...expected].sort().join("\0")) {
    throw new TypeError(`invalid ${label}`);
  }
}

function requiredString(value: unknown, label: string, maximum = 200): string {
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    value.length > maximum ||
    value.trim() !== value ||
    /[\u0000-\u001f\u007f]/.test(value)
  ) {
    throw new TypeError(`invalid ${label}`);
  }
  return value;
}

function enumValue<T extends string>(
  value: unknown,
  allowed: readonly T[],
  label: string,
): T {
  if (typeof value !== "string" || !allowed.includes(value as T)) {
    throw new TypeError(`invalid ${label}`);
  }
  return value as T;
}

function closedArray<T extends string>(
  value: unknown,
  allowed: readonly T[],
  label: string,
  maximum = 8,
): readonly T[] {
  if (!Array.isArray(value) || value.length > maximum) {
    throw new TypeError(`invalid ${label}`);
  }
  const parsed = value.map((item) => enumValue(item, allowed, label));
  if (new Set(parsed).size !== parsed.length) {
    throw new TypeError(`invalid ${label}`);
  }
  return parsed;
}

function stableIdList(
  value: unknown,
  allowed: ReadonlySet<string>,
  label: string,
): readonly string[] {
  if (!Array.isArray(value) || value.length > 8) {
    throw new TypeError(`invalid ${label}`);
  }
  const parsed = value.map((item) => requiredString(item, label, 96));
  if (
    parsed.some((item) => !STABLE_ID.test(item) || !allowed.has(item)) ||
    new Set(parsed).size !== parsed.length
  ) {
    throw new TypeError(`unknown ${label.replace(/_ids$/, "")}`);
  }
  return parsed;
}

function catalogTokenList(value: unknown): readonly string[] {
  if (!Array.isArray(value) || value.length > 5_000) {
    throw new TypeError("invalid index_tokens");
  }
  const parsed = value.map((item) => requiredString(item, "index token", 96));
  if (
    parsed.some(
      (item) => !item.startsWith("token:") || !STABLE_ID.test(item),
    ) ||
    new Set(parsed).size !== parsed.length
  ) {
    throw new TypeError("invalid index_tokens");
  }
  return parsed;
}

function assertJsonSize(value: unknown, maximum: number, label: string): void {
  let serialized: string;
  try {
    serialized = JSON.stringify(value);
  } catch {
    throw new TypeError(`invalid ${label}`);
  }
  if (encoder.encode(serialized).byteLength > maximum) {
    throw new TypeError(`${label} exceeds size limit`);
  }
}

function parseIso(value: unknown, label: string): string {
  const parsed = requiredString(value, label, 32);
  const instant = Date.parse(parsed);
  if (!DATE.test(parsed) || Number.isNaN(instant)) {
    throw new TypeError(`invalid ${label}`);
  }
  const normalized = new Date(instant).toISOString();
  const roundTrips =
    parsed.length === 10
      ? normalized === `${parsed}T00:00:00.000Z`
      : normalized === parsed || normalized.replace(".000Z", "Z") === parsed;
  if (!roundTrips) throw new TypeError(`invalid ${label}`);
  return parsed;
}

export function parseResearchCatalog(raw: string | undefined): ResearchCatalog {
  if (raw === undefined) throw new TypeError("research catalog is required");
  if (encoder.encode(raw).byteLength > MAX_CATALOG_BYTES) {
    throw new TypeError("research catalog exceeds size limit");
  }
  const value: unknown = JSON.parse(raw);
  if (!isRecord(value)) throw new TypeError("invalid research catalog");
  exactKeys(
    value,
    [
      "schema_version",
      "topics",
      "entities",
      "index_tokens",
      "source_system_ids",
    ],
    "research catalog",
  );
  if (value.schema_version !== "research-catalog.v1") {
    throw new TypeError("invalid research catalog");
  }
  const parseEntries = (entries: unknown, prefix: "topic" | "entity") => {
    if (
      !Array.isArray(entries) ||
      entries.length === 0 ||
      entries.length > 500
    ) {
      throw new TypeError("invalid research catalog");
    }
    const parsed = entries.map((entry) => {
      if (!isRecord(entry)) throw new TypeError("invalid research catalog");
      exactKeys(entry, ["id", "label"], "research catalog entry");
      const id = requiredString(entry.id, "catalog id", 96);
      const label = requiredString(entry.label, "catalog label", 120);
      if (!id.startsWith(`${prefix}:`) || !STABLE_ID.test(id)) {
        throw new TypeError("invalid research catalog id");
      }
      return { id, label };
    });
    if (new Set(parsed.map((entry) => entry.id)).size !== parsed.length) {
      throw new TypeError("duplicate research catalog id");
    }
    return parsed;
  };
  const topics = parseEntries(value.topics, "topic");
  const entities = parseEntries(value.entities, "entity");
  const indexTokens = catalogTokenList(value.index_tokens);
  const sourceSystems = closedArray(
    value.source_system_ids,
    ["intel-lake", "mata-garuda", "regulatory-watcher", "notebooklm"] as const,
    "source_system_ids",
  );
  return {
    schema_version: "research-catalog.v1",
    topics,
    entities,
    index_tokens: indexTokens,
    source_system_ids: sourceSystems,
  };
}

export function parseResearchRequest(
  value: unknown,
  catalog: ResearchCatalog,
): ResearchRequestV1 {
  assertJsonSize(value, MAX_REQUEST_BYTES, "research request");
  if (!isRecord(value)) throw new TypeError("invalid research request");
  exactKeys(
    value,
    [
      "schema_version",
      "mode",
      "topic_ids",
      "entity_ids",
      "index_tokens",
      "template",
      "facets",
    ],
    "research request",
  );
  if (value.schema_version !== "research-request.v1") {
    throw new TypeError("invalid research request");
  }
  const mode = enumValue(value.mode, RESEARCH_MODES, "research mode");
  const topicIds = stableIdList(
    value.topic_ids,
    new Set(catalog.topics.map(({ id }) => id)),
    "topic_ids",
  );
  const entityIds = stableIdList(
    value.entity_ids,
    new Set(catalog.entities.map(({ id }) => id)),
    "entity_ids",
  );
  const indexTokens = stableIdList(
    value.index_tokens,
    new Set(catalog.index_tokens),
    "index_tokens",
  );
  if (topicIds.length + entityIds.length + indexTokens.length === 0) {
    throw new TypeError("research request requires a selected subject");
  }
  let template: ResearchTemplate | null = null;
  if (mode === "notebook_insight") {
    template = enumValue(value.template, RESEARCH_TEMPLATES, "template");
    if (topicIds.length + entityIds.length !== 1 || indexTokens.length !== 0) {
      throw new TypeError("notebook insight requires one public subject");
    }
  } else if (value.template !== null) {
    throw new TypeError("template is reserved for notebook insight");
  }
  const publicSubjectCount = topicIds.length + entityIds.length;
  if (mode === "compare" && publicSubjectCount !== 2) {
    throw new TypeError("compare requires exactly two public subjects");
  }
  if (mode === "timeline" && publicSubjectCount !== 1) {
    throw new TypeError("timeline requires exactly one public subject");
  }
  if (!isRecord(value.facets)) throw new TypeError("invalid research facets");
  exactKeys(
    value.facets,
    [
      "domains",
      "source_system_ids",
      "evidence_types",
      "confidence",
      "lifecycle_states",
      "languages",
    ],
    "research facets",
  );
  const facets: ResearchFacets = {
    domains: closedArray(
      value.facets.domains,
      ["immigration", "company", "tax", "property", "compliance"] as const,
      "domains",
    ),
    source_system_ids: closedArray(
      value.facets.source_system_ids,
      catalog.source_system_ids,
      "source_system_ids",
    ),
    evidence_types: closedArray(
      value.facets.evidence_types,
      ["official", "journalism", "research", "dataset"] as const,
      "evidence_types",
    ),
    confidence: closedArray(
      value.facets.confidence,
      ["normal", "cautious", "abstain"] as const,
      "confidence",
    ),
    lifecycle_states: closedArray(
      value.facets.lifecycle_states,
      ["published", "amended", "superseded"] as const,
      "lifecycle_states",
    ),
    languages: closedArray(
      value.facets.languages,
      ["en", "id"] as const,
      "languages",
    ),
  };
  if (facets.source_system_ids.length === 0) {
    throw new TypeError("research request requires a source system");
  }
  if (
    mode === "notebook_insight" &&
    (facets.source_system_ids.length !== 1 ||
      facets.source_system_ids[0] !== "notebooklm")
  ) {
    throw new TypeError("notebook insight requires NotebookLM only");
  }
  return {
    schema_version: "research-request.v1",
    mode,
    topic_ids: topicIds,
    entity_ids: entityIds,
    index_tokens: indexTokens,
    template,
    facets,
  };
}

function parseEvidence(value: unknown): ResearchEvidenceV1 {
  if (!isRecord(value)) throw new TypeError("invalid evidence");
  exactKeys(
    value,
    [
      "evidence_id",
      "publisher",
      "citation",
      "canonical_url",
      "source_type",
      "published_at",
    ],
    "evidence",
  );
  const id = requiredString(value.evidence_id, "evidence id", 128);
  if (!/^evidence:[a-z0-9]+(?:-[a-z0-9]+)*$/.test(id)) {
    throw new TypeError("invalid evidence id");
  }
  return {
    evidence_id: id,
    publisher: requiredString(value.publisher, "publisher", 160),
    citation: requiredString(value.citation, "citation", 500),
    canonical_url:
      value.canonical_url === null
        ? null
        : normalizeHttpsEvidenceUrl(
            requiredString(value.canonical_url, "canonical URL", 1000),
          ),
    source_type: enumValue(
      value.source_type,
      ["official", "journalism", "research", "dataset"] as const,
      "source type",
    ),
    published_at:
      value.published_at === null
        ? null
        : parseIso(value.published_at, "published at"),
  };
}

function parseClaim(value: unknown): ResearchClaimV1 {
  if (!isRecord(value)) throw new TypeError("invalid research claim");
  exactKeys(
    value,
    [
      "claim_id",
      "kind",
      "text",
      "numeric_value",
      "numeric_unit",
      "as_of",
      "evidence",
    ],
    "research claim",
  );
  const claimId = requiredString(value.claim_id, "claim id", 128);
  if (!/^claim:[a-z0-9]+(?:-[a-z0-9]+)*$/.test(claimId)) {
    throw new TypeError("invalid claim id");
  }
  const kind = enumValue(
    value.kind,
    ["fact", "numeric", "analysis"] as const,
    "claim kind",
  );
  if (
    !Array.isArray(value.evidence) ||
    value.evidence.length === 0 ||
    value.evidence.length > 12
  ) {
    throw new TypeError("research claim requires evidence");
  }
  const numericValue =
    value.numeric_value === null
      ? null
      : requiredString(value.numeric_value, "numeric value", 64);
  const numericUnit =
    value.numeric_unit === null
      ? null
      : requiredString(value.numeric_unit, "numeric unit", 48);
  const asOf =
    value.as_of === null ? null : parseIso(value.as_of, "claim as of");
  if (
    kind === "numeric" &&
    (numericValue === null || numericUnit === null || asOf === null)
  ) {
    throw new TypeError("numeric claim requires a value, unit, and as-of date");
  }
  if (kind !== "numeric" && (numericValue !== null || numericUnit !== null)) {
    throw new TypeError("non-numeric claim cannot carry numeric fields");
  }
  return {
    claim_id: claimId,
    kind,
    text: requiredString(value.text, "claim text", 1200),
    numeric_value: numericValue,
    numeric_unit: numericUnit,
    as_of: asOf,
    evidence: value.evidence.map(parseEvidence),
  };
}

export function parseResearchResult(value: unknown): ResearchResultV1 {
  assertJsonSize(value, MAX_RESULT_BYTES, "research result");
  if (!isRecord(value)) throw new TypeError("invalid research result");
  exactKeys(
    value,
    [
      "schema_version",
      "job_id",
      "request_hash",
      "mode",
      "status",
      "completed_at",
      "summary",
      "claims",
      "failure",
      "claim_token",
      "fencing_token",
    ],
    "research result",
  );
  if (value.schema_version !== "research-result.v1")
    throw new TypeError("invalid research result");
  const status = enumValue(
    value.status,
    ["completed", "failed"] as const,
    "result status",
  );
  const requestHash = requiredString(value.request_hash, "request hash", 64);
  if (!SHA256.test(requestHash)) throw new TypeError("invalid request hash");
  if (!Array.isArray(value.claims) || value.claims.length > 50)
    throw new TypeError("invalid research claims");
  const claims = value.claims.map(parseClaim);
  let failure: ResearchResultV1["failure"] = null;
  if (status === "completed") {
    if (value.failure !== null || typeof value.summary !== "string")
      throw new TypeError("invalid completed research result");
  } else {
    if (!isRecord(value.failure))
      throw new TypeError("invalid failure receipt");
    exactKeys(value.failure, ["code"], "failure receipt");
    failure = {
      code: enumValue(
        value.failure.code,
        [
          "source_unavailable",
          "dlp_rejected",
          "evidence_missing",
          "invalid_result",
          "internal_error",
        ] as const,
        "failure code",
      ),
    };
    if (value.summary !== null || claims.length !== 0)
      throw new TypeError("failed result must be content free");
  }
  const claimToken = requiredString(value.claim_token, "claim token", 128);
  if (!TOKEN.test(claimToken)) throw new TypeError("invalid claim token");
  if (
    !Number.isSafeInteger(value.fencing_token) ||
    (value.fencing_token as number) < 1
  )
    throw new TypeError("invalid fencing token");
  return {
    schema_version: "research-result.v1",
    job_id: requiredString(value.job_id, "job id", 128),
    request_hash: requestHash,
    mode: enumValue(value.mode, RESEARCH_MODES, "research mode"),
    status,
    completed_at: parseIso(value.completed_at, "completed at"),
    summary:
      value.summary === null
        ? null
        : requiredString(value.summary, "summary", 2000),
    claims,
    failure,
    claim_token: claimToken,
    fencing_token: value.fencing_token as number,
  };
}

function addSeconds(iso: string, seconds: number): string {
  const instant = Date.parse(iso);
  if (Number.isNaN(instant))
    throw new TypeError("repository clock returned invalid time");
  return new Date(instant + seconds * 1000).toISOString();
}

function rowToView(row: JobRow): ResearchJobView {
  return {
    job_id: row.job_id,
    actor_key: row.actor_key,
    mode: row.mode,
    request: JSON.parse(row.query_json) as ResearchRequestV1,
    request_hash: row.request_hash,
    status: row.status,
    claim_token: row.claim_token,
    fencing_token: row.fencing_token,
    lease_deadline: row.lease_deadline,
    created_at: row.created_at,
    expires_at: row.expires_at,
    completed_at: row.completed_at,
    result:
      row.result_json === null
        ? null
        : parseResearchResult(JSON.parse(row.result_json)),
  };
}

const JOB_SELECT = `SELECT job.job_id, job.actor_key, job.mode, job.query_json,
  job.request_hash, job.idempotency_key, job.status, job.claim_token,
  job.fencing_token, job.lease_deadline, job.created_at, job.expires_at,
  job.completed_at, result.result_json
  FROM research_jobs job
  LEFT JOIN research_results result ON result.job_id = job.job_id`;

const MAX_CLAIM_SCAN = 100;

type ClaimCandidate = Readonly<{
  job_id: string;
  actor_key: string;
}>;

export function createResearchRepository(
  db: D1DatabaseLike,
  options: RepositoryOptions = {},
) {
  const now = options.now ?? (() => new Date().toISOString());
  const randomId = options.randomId ?? (() => crypto.randomUUID());

  return {
    async createJob(
      actorKey: string,
      request: ResearchRequestV1,
      idempotencyKey: string,
    ) {
      if (!SHA256.test(actorKey)) throw new TypeError("invalid actor key");
      if (!TOKEN.test(idempotencyKey))
        throw new TypeError("invalid idempotency key");
      const queryJson = JSON.stringify(request);
      const requestHash = await sha256Hex(encoder.encode(queryJson));
      const jobId = `research-job-${randomId()}`;
      const createdAt = now();
      const expiresAt = addSeconds(createdAt, 86_400);
      const inserted = await db.batch([
        db
          .prepare(
            `INSERT OR IGNORE INTO research_jobs(
             job_id, actor_key, mode, query_json, request_hash,
             idempotency_key, status, attempt_limit, attempt_count,
             fencing_token, created_at, expires_at
           ) VALUES (?, ?, ?, ?, ?, ?, 'queued', 3, 0, 0, ?, ?)`,
          )
          .bind(
            jobId,
            actorKey,
            request.mode,
            queryJson,
            requestHash,
            idempotencyKey,
            createdAt,
            expiresAt,
          ),
        db
          .prepare(
            `INSERT OR IGNORE INTO research_audit_events(
             event_id, job_id, event_type, actor_key, status, created_at
           ) SELECT job_id || ':created', job_id, 'created', actor_key,
                    'queued', ? FROM research_jobs
             WHERE idempotency_key = ? AND actor_key = ? AND request_hash = ?`,
          )
          .bind(createdAt, idempotencyKey, actorKey, requestHash),
      ]);
      const row = await db
        .prepare(`${JOB_SELECT} WHERE job.idempotency_key = ?`)
        .bind(idempotencyKey)
        .first<JobRow>();
      if (row === null) throw new Error("research job insert did not persist");
      if (row.actor_key !== actorKey || row.request_hash !== requestHash)
        throw new Error("CAS conflict: research idempotency key reused");
      return {
        status: (inserted[0]?.meta?.changes ?? 0) === 1 ? "created" : "replay",
        job: rowToView(row),
      } as const;
    },

    async claimNext(
      input: Readonly<{
        workerId: string;
        leaseSeconds: number;
        analystActorKeys: readonly string[];
      }>,
    ): Promise<ResearchJobView | null> {
      if (!WORKER_ID.test(input.workerId))
        throw new TypeError("invalid worker id");
      if (
        !Number.isSafeInteger(input.leaseSeconds) ||
        input.leaseSeconds < 30 ||
        input.leaseSeconds > 300
      )
        throw new TypeError("invalid lease seconds");
      if (!Array.isArray(input.analystActorKeys))
        throw new TypeError("current Analyst allowlist is required");
      const analystActorKeys = new Set(input.analystActorKeys);
      if (
        analystActorKeys.size !== input.analystActorKeys.length ||
        [...analystActorKeys].some((actorKey) => !SHA256.test(actorKey))
      )
        throw new TypeError("invalid current Analyst allowlist");
      const claimedAt = now();
      const leaseDeadline = addSeconds(claimedAt, input.leaseSeconds);
      for (let scanned = 0; scanned < MAX_CLAIM_SCAN; scanned += 1) {
        const candidate = await db
          .prepare(
            `SELECT job_id, actor_key FROM research_jobs
             WHERE expires_at > ? AND attempt_count < attempt_limit
               AND (status = 'queued' OR (status = 'claimed' AND lease_deadline <= ?))
             ORDER BY created_at, job_id LIMIT 1`,
          )
          .bind(claimedAt, claimedAt)
          .first<ClaimCandidate>();
        if (candidate === null) return null;

        if (!analystActorKeys.has(candidate.actor_key)) {
          const cancelled = await db.batch([
            db
              .prepare(
                `UPDATE research_jobs
                 SET status = 'cancelled', cancelled_at = ?, worker_id = NULL,
                     claim_token = NULL, heartbeat_at = NULL, lease_deadline = NULL
                 WHERE job_id = ? AND actor_key = ? AND expires_at > ?
                   AND attempt_count < attempt_limit
                   AND (status = 'queued' OR (status = 'claimed' AND lease_deadline <= ?))`,
              )
              .bind(
                claimedAt,
                candidate.job_id,
                candidate.actor_key,
                claimedAt,
                claimedAt,
              ),
            db
              .prepare(
                `INSERT OR IGNORE INTO research_audit_events(
                   event_id, job_id, event_type, actor_key, status, created_at
                 ) SELECT job_id || ':cancelled', job_id, 'cancelled', actor_key,
                          'cancelled', ? FROM research_jobs
                   WHERE job_id = ? AND actor_key = ? AND status = 'cancelled'
                     AND cancelled_at = ?`,
              )
              .bind(
                claimedAt,
                candidate.job_id,
                candidate.actor_key,
                claimedAt,
              ),
          ]);
          if ((cancelled[0]?.meta?.changes ?? 0) === 0) continue;
          if ((cancelled[1]?.meta?.changes ?? 0) !== 1)
            throw new Error("research revocation audit did not persist");
          continue;
        }

        const claimToken = `claim-${randomId()}`;
        const claimed = await db.batch([
          db
            .prepare(
              `UPDATE research_jobs
               SET status = 'claimed', worker_id = ?, claim_token = ?,
                   fencing_token = fencing_token + 1,
                   attempt_count = attempt_count + 1,
                   heartbeat_at = ?, lease_deadline = ?
               WHERE job_id = ? AND actor_key = ? AND expires_at > ?
                 AND attempt_count < attempt_limit
                 AND (status = 'queued' OR (status = 'claimed' AND lease_deadline <= ?))`,
            )
            .bind(
              input.workerId,
              claimToken,
              claimedAt,
              leaseDeadline,
              candidate.job_id,
              candidate.actor_key,
              claimedAt,
              claimedAt,
            ),
          db
            .prepare(
              `INSERT INTO research_audit_events(
                 event_id, job_id, event_type, worker_id, status,
                 fencing_token, created_at
               ) SELECT job_id || ':claimed:' || fencing_token, job_id, 'claimed',
                        worker_id, 'claimed', fencing_token, ?
                   FROM research_jobs
                  WHERE claim_token = ? AND worker_id = ? AND status = 'claimed'
                    AND heartbeat_at = ?`,
            )
            .bind(claimedAt, claimToken, input.workerId, claimedAt),
        ]);
        if ((claimed[0]?.meta?.changes ?? 0) === 0) continue;
        if ((claimed[1]?.meta?.changes ?? 0) !== 1)
          throw new Error("research claim audit did not persist");
        const row = await db
          .prepare(
            `${JOB_SELECT} WHERE job.claim_token = ? AND job.worker_id = ?`,
          )
          .bind(claimToken, input.workerId)
          .first<JobRow>();
        if (row === null) throw new Error("claimed research job disappeared");
        return rowToView(row);
      }
      return null;
    },

    async heartbeat(
      jobId: string,
      claimToken: string,
      fencingToken: number,
      leaseSeconds: number,
    ): Promise<ResearchJobView> {
      if (
        !TOKEN.test(claimToken) ||
        !Number.isSafeInteger(fencingToken) ||
        fencingToken < 1 ||
        !Number.isSafeInteger(leaseSeconds) ||
        leaseSeconds < 30 ||
        leaseSeconds > 300
      )
        throw new TypeError("invalid heartbeat");
      const heartbeatAt = now();
      const leaseDeadline = addSeconds(heartbeatAt, leaseSeconds);
      const row = await db
        .prepare(
          `UPDATE research_jobs
         SET heartbeat_at = ?, lease_deadline = ?
         WHERE job_id = ? AND status = 'claimed' AND claim_token = ?
           AND fencing_token = ? AND expires_at > ? AND lease_deadline > ?
         RETURNING job_id`,
        )
        .bind(
          heartbeatAt,
          leaseDeadline,
          jobId,
          claimToken,
          fencingToken,
          heartbeatAt,
          heartbeatAt,
        )
        .first<{ job_id: string }>();
      if (row === null)
        throw new Error("CAS conflict: research heartbeat lease lost");
      const job = await this.getJob(row.job_id);
      if (job === null) throw new Error("research heartbeat job disappeared");
      return job;
    },

    async complete(
      result: ResearchResultV1,
      receiptKeyId: string,
      receiptBodyHash: string,
    ) {
      requiredString(receiptKeyId, "receipt key id", 128);
      if (!SHA256.test(receiptBodyHash))
        throw new TypeError("invalid receipt body hash");
      const resultJson = JSON.stringify(result);
      const resultHash = await sha256Hex(encoder.encode(resultJson));
      const existing = await db
        .prepare(
          "SELECT result_hash, receipt_body_hash, result_json FROM research_results WHERE job_id = ?",
        )
        .bind(result.job_id)
        .first<ResultRow>();
      if (existing !== null) {
        if (
          existing.result_hash === resultHash &&
          existing.receipt_body_hash === receiptBodyHash
        )
          return { status: "replay" } as const;
        throw new Error("CAS conflict: research result already exists");
      }
      const resultId = `research-result-${result.job_id}`;
      const completedAt = now();
      const statements = [
        db
          .prepare(
            `UPDATE research_jobs
           SET status = ?, completed_at = ?, heartbeat_at = ?, lease_deadline = NULL
           WHERE job_id = ? AND mode = ? AND request_hash = ?
             AND status = 'claimed' AND claim_token = ? AND fencing_token = ?
             AND expires_at > ? AND lease_deadline > ?
             AND NOT EXISTS (SELECT 1 FROM research_results WHERE job_id = research_jobs.job_id)`,
          )
          .bind(
            result.status,
            completedAt,
            completedAt,
            result.job_id,
            result.mode,
            result.request_hash,
            result.claim_token,
            result.fencing_token,
            completedAt,
            completedAt,
          ),
        db
          .prepare(
            `INSERT INTO research_results(
             result_id, job_id, status, result_json, result_hash, request_hash,
             fencing_token, receipt_key_id, receipt_body_hash, created_at
           ) SELECT ?, job_id, ?, ?, ?, ?, ?, ?, ?, ?
             FROM research_jobs
             WHERE job_id = ? AND status = ? AND request_hash = ?
               AND fencing_token = ? AND completed_at = ?
               AND NOT EXISTS (SELECT 1 FROM research_results WHERE job_id = research_jobs.job_id)`,
          )
          .bind(
            resultId,
            result.status,
            resultJson,
            resultHash,
            result.request_hash,
            result.fencing_token,
            receiptKeyId,
            receiptBodyHash,
            completedAt,
            result.job_id,
            result.status,
            result.request_hash,
            result.fencing_token,
            completedAt,
          ),
        db
          .prepare(
            `INSERT INTO research_audit_events(
             event_id, job_id, event_type, worker_id, status,
             failure_code, fencing_token, created_at
           ) SELECT ?, job_id, ?, worker_id, ?, ?, fencing_token, ?
             FROM research_jobs
             WHERE job_id = ? AND status = ? AND request_hash = ?
               AND fencing_token = ? AND completed_at = ?`,
          )
          .bind(
            `${result.job_id}:${result.status}:${result.fencing_token}`,
            result.status,
            result.status,
            result.failure?.code ?? null,
            completedAt,
            result.job_id,
            result.status,
            result.request_hash,
            result.fencing_token,
            completedAt,
          ),
      ];
      const applied = await db.batch(statements);
      if (
        (applied[0]?.meta?.changes ?? 0) !== 1 ||
        (applied[1]?.meta?.changes ?? 0) !== 1 ||
        (applied[2]?.meta?.changes ?? 0) !== 1
      ) {
        const replay = await db
          .prepare(
            "SELECT result_hash, receipt_body_hash, result_json FROM research_results WHERE job_id = ?",
          )
          .bind(result.job_id)
          .first<ResultRow>();
        if (
          replay?.result_hash === resultHash &&
          replay.receipt_body_hash === receiptBodyHash
        )
          return { status: "replay" } as const;
        throw new Error("CAS conflict: research result lease lost");
      }
      return { status: "created" } as const;
    },

    async cancelOwn(jobId: string, actorKey: string): Promise<boolean> {
      const cancelledAt = now();
      const result = await db.batch([
        db
          .prepare(
            `UPDATE research_jobs SET status = 'cancelled', cancelled_at = ?,
             claim_token = NULL, lease_deadline = NULL
           WHERE job_id = ? AND actor_key = ? AND status IN ('queued', 'claimed')`,
          )
          .bind(cancelledAt, jobId, actorKey),
        db
          .prepare(
            `INSERT OR IGNORE INTO research_audit_events(
             event_id, job_id, event_type, actor_key, status, created_at
           ) SELECT job_id || ':cancelled', job_id, 'cancelled', actor_key,
                    'cancelled', ? FROM research_jobs
             WHERE job_id = ? AND actor_key = ? AND status = 'cancelled'
               AND cancelled_at = ?`,
          )
          .bind(cancelledAt, jobId, actorKey, cancelledAt),
      ]);
      return (
        (result[0]?.meta?.changes ?? 0) === 1 &&
        (result[1]?.meta?.changes ?? 0) === 1
      );
    },

    async getJob(jobId: string): Promise<ResearchJobView | null> {
      const row = await db
        .prepare(`${JOB_SELECT} WHERE job.job_id = ?`)
        .bind(jobId)
        .first<JobRow>();
      return row === null ? null : rowToView(row);
    },

    async listJobs(limit = 50): Promise<readonly ResearchJobView[]> {
      const bounded = Math.max(1, Math.min(limit, 100));
      const rows = await db
        .prepare(
          `${JOB_SELECT} ORDER BY job.created_at DESC, job.job_id DESC LIMIT ?`,
        )
        .bind(bounded)
        .all<JobRow>();
      return (rows.results ?? []).map(rowToView);
    },

    async listPublishedEvidence(
      limit = 50,
    ): Promise<readonly ResearchEvidenceV1[]> {
      const bounded = Math.max(1, Math.min(limit, 100));
      const rows = await db
        .prepare(
          `SELECT DISTINCT evidence.evidence_id, evidence.publisher,
                evidence.document_citation AS citation,
                evidence.canonical_url, evidence.source_type, evidence.published_at
         FROM evidence_refs evidence
         JOIN story_evidence link ON link.evidence_id = evidence.evidence_id
         JOIN story_versions version ON version.story_id = link.story_id
           AND version.version = link.version
         WHERE link.publication_state = 'published'
           AND version.publication_state = 'published'
         ORDER BY COALESCE(evidence.published_at, evidence.retrieved_at) DESC,
                  evidence.evidence_id
         LIMIT ?`,
        )
        .bind(bounded)
        .all<ResearchEvidenceV1>();
      return (rows.results ?? []).map((row) => ({
        ...row,
        citation: row.citation ?? "Published source",
      }));
    },
  };
}

export function parseResearchClaimRequest(
  value: unknown,
): Readonly<{ workerId: string; leaseSeconds: number }> {
  if (!isRecord(value)) throw new TypeError("invalid research claim request");
  exactKeys(
    value,
    ["schema_version", "worker_id", "lease_seconds"],
    "research claim request",
  );
  if (value.schema_version !== "research-claim.v1")
    throw new TypeError("invalid research claim request");
  const workerId = requiredString(value.worker_id, "worker id", 96);
  if (
    !WORKER_ID.test(workerId) ||
    !Number.isSafeInteger(value.lease_seconds) ||
    (value.lease_seconds as number) < 30 ||
    (value.lease_seconds as number) > 300
  )
    throw new TypeError("invalid research claim request");
  return { workerId, leaseSeconds: value.lease_seconds as number };
}

export function parseResearchHeartbeat(value: unknown): Readonly<{
  claimToken: string;
  fencingToken: number;
  leaseSeconds: number;
}> {
  if (!isRecord(value)) throw new TypeError("invalid research heartbeat");
  exactKeys(
    value,
    ["schema_version", "claim_token", "fencing_token", "lease_seconds"],
    "research heartbeat",
  );
  if (value.schema_version !== "research-heartbeat.v1")
    throw new TypeError("invalid research heartbeat");
  const claimToken = requiredString(value.claim_token, "claim token", 128);
  if (
    !TOKEN.test(claimToken) ||
    !Number.isSafeInteger(value.fencing_token) ||
    (value.fencing_token as number) < 1 ||
    !Number.isSafeInteger(value.lease_seconds) ||
    (value.lease_seconds as number) < 30 ||
    (value.lease_seconds as number) > 300
  )
    throw new TypeError("invalid research heartbeat");
  return {
    claimToken,
    fencingToken: value.fencing_token as number,
    leaseSeconds: value.lease_seconds as number,
  };
}
