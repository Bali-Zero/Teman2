import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { expect, test, type Page } from "@playwright/test";
import { translate } from "../src/app/(visa-oracle)/visa-oracle/_lib/i18n";

const ENABLED = process.env.VISA_ORACLE_FULLSTACK === "1";
const DATABASE_URL = process.env.VISA_ORACLE_SMOKE_DATABASE_URL ?? "";
const RESUME_KEY = "visa-oracle:v2:resume:v1";
const TEST_RULE_PACK_ID = "8a57d996-c7f2-5abc-9c31-4128a29ed848";
const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const SHA256 = /^[0-9a-f]{64}$/;

const SYNTHETIC_VERDICT_FACTS = {
  in_indonesia: "no",
  overstay_days: "0",
  nationalities: "US",
  birth_date: "1990-01-01",
  category: "tourism",
  trip_scope: "single",
  stay_days: "30",
  entry_pattern: "SINGLE",
  review_gate: "none",
};

const VERDICT_HISTORY = [
  { kind: "framing" },
  { kind: "question", questionId: "in_indonesia" },
  { kind: "question", questionId: "overstay_days" },
  { kind: "question", questionId: "nationalities" },
  { kind: "question", questionId: "birth_date" },
  { kind: "question", questionId: "category" },
  { kind: "question", questionId: "trip_scope" },
  { kind: "question", questionId: "stay_days" },
  { kind: "question", questionId: "entry_pattern" },
  { kind: "question", questionId: "review_gate" },
  { kind: "confirmation" },
  { kind: "verdict" },
];

type PublicDecisionResponse = {
  mode: string;
  decision: {
    decision_id: string | null;
    state: string;
    candidates: Array<{ product_code: string }>;
    review_reasons: Array<{ code: string; source_refs: string[] }>;
    trace_sha256: string | null;
  };
  sources: Array<{
    source_record_id: string;
    canonical_url: string;
    freshness: { status: string };
  }>;
};

type CapturedEvaluation = {
  body: string;
  idempotencyKey: string;
  path: string;
  response: PublicDecisionResponse;
};

type PersistenceEvidence = {
  activation_bound: boolean;
  decision_count: number;
  decision_integrity_bound: boolean;
  engine_mode: string;
  environment: string;
  idempotency_completed: boolean;
  idempotency_count: number;
  idempotency_response_bound: boolean;
  retention_active: boolean;
  retention_policy: string;
  rule_pack_bound: boolean;
  trace_bound: boolean;
  verdict: string;
};

function assertDisposableTestDatabaseUrl(databaseUrl: string): void {
  const parsed = new URL(databaseUrl);
  if (
    !["postgres:", "postgresql:"].includes(parsed.protocol) ||
    !["127.0.0.1", "localhost", "[::1]"].includes(parsed.hostname) ||
    !/^\/visa_oracle_smoke_[a-z0-9_]{8,80}$/.test(parsed.pathname)
  ) {
    throw new Error("refusing non-local or non-disposable smoke database URL");
  }
}

async function seedSyntheticVerdictResume(page: Page): Promise<void> {
  const savedAtIso = new Date().toISOString();
  const expiresAtIso = new Date(Date.now() + 2 * 60 * 60 * 1_000).toISOString();
  await page.addInitScript(
    ({ key, savedAt, expiresAt, history, facts }) => {
      window.sessionStorage.setItem(
        key,
        JSON.stringify({
          schemaVersion: 1,
          savedAtIso: savedAt,
          expiresAtIso: expiresAt,
          snapshot: {
            schemaVersion: 1,
            attempt: 0,
            history,
            facts,
            updatedAtIso: savedAt,
          },
        }),
      );
    },
    {
      key: RESUME_KEY,
      savedAt: savedAtIso,
      expiresAt: expiresAtIso,
      history: VERDICT_HISTORY,
      facts: SYNTHETIC_VERDICT_FACTS,
    },
  );
}

function readPersistenceEvidence(
  decisionId: string,
  idempotencyKey: string,
  traceSha256: string,
): PersistenceEvidence {
  if (
    !UUID.test(decisionId) ||
    !UUID.test(idempotencyKey) ||
    !SHA256.test(traceSha256)
  ) {
    throw new Error(
      "smoke response returned invalid technical integrity identifiers",
    );
  }
  assertDisposableTestDatabaseUrl(DATABASE_URL);
  const parsedDatabaseUrl = new URL(DATABASE_URL);
  const keySha256 = createHash("sha256").update(idempotencyKey).digest("hex");
  const sql = `
    SELECT json_build_object(
      'decision_count', (SELECT count(*)::int FROM public.visa_decisions),
      'environment', d.environment,
      'engine_mode', d.engine_mode,
      'verdict', d.verdict,
      'rule_pack_bound', d.rule_pack_id = '${TEST_RULE_PACK_ID}'::uuid,
      'activation_bound', d.ruleset_activation_id IS NOT NULL,
      'trace_bound', encode(d.trace_sha256, 'hex') = '${traceSha256}',
      'decision_integrity_bound', d.decision_hmac IS NOT NULL
        AND d.decision_hmac_key_id IS NOT NULL,
      'retention_policy', p.policy_version,
      'retention_active', d.retention_until > clock_timestamp(),
      'idempotency_count', (
        SELECT count(*)::int FROM public.visa_evaluate_idempotency
        WHERE key_sha256 = decode('${keySha256}', 'hex')
      ),
      'idempotency_completed', COALESCE((
        SELECT completed_at IS NOT NULL AND response_hmac IS NOT NULL
        FROM public.visa_evaluate_idempotency
        WHERE key_sha256 = decode('${keySha256}', 'hex')
      ), false),
      'idempotency_response_bound', COALESCE((
        SELECT response_body->'decision'->>'decision_id' = '${decisionId}'
        FROM public.visa_evaluate_idempotency
        WHERE key_sha256 = decode('${keySha256}', 'hex')
      ), false)
    )::text
    FROM public.visa_decisions d
    JOIN public.visa_decision_retention_policies p ON p.id = d.retention_policy_id
    WHERE d.decision_id = '${decisionId}'::uuid
  `;
  const raw = execFileSync(
    "psql",
    ["-X", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-c", sql],
    {
      encoding: "utf8",
      env: {
        ...process.env,
        PGHOST: parsedDatabaseUrl.hostname,
        PGPORT: parsedDatabaseUrl.port || "5432",
        PGUSER: decodeURIComponent(parsedDatabaseUrl.username),
        PGPASSWORD: decodeURIComponent(parsedDatabaseUrl.password),
        PGDATABASE: parsedDatabaseUrl.pathname.slice(1),
      },
    },
  ).trim();
  if (!raw) throw new Error("PII-free persistence evidence row is missing");
  return JSON.parse(raw) as PersistenceEvidence;
}

test.describe("Visa Oracle real full-stack smoke", () => {
  test.skip(
    !ENABLED,
    "set VISA_ORACLE_FULLSTACK=1 via the disposable DB runner",
  );

  test("browser → Next → FastAPI → signed TEST RulePack → PostgreSQL", async ({
    page,
  }) => {
    assertDisposableTestDatabaseUrl(DATABASE_URL);
    await seedSyntheticVerdictResume(page);

    const evaluateRequestPromise = page.waitForRequest(
      (request) =>
        request.method() === "POST" &&
        new URL(request.url()).pathname === "/api/visa-oracle/evaluate",
    );
    await page.goto("/visa-oracle");
    const evaluateRequest = await evaluateRequestPromise;
    const evaluateUrl = new URL(evaluateRequest.url());
    await expect(
      page.getByRole("heading", {
        name: translate("en", "verdict.headline.HUMAN_REVIEW_REQUIRED"),
      }),
    ).toBeVisible({ timeout: 30_000 });
    // DECISIVE_SOURCE_FRESHNESS_UNKNOWN has no curated copy yet (QW-4b): it is
    // listed in engine-adapter.test.ts's own KNOWN_UNMAPPED_REVIEW_REASON_CODES,
    // so reviewReason() deliberately renders GENERIC_REVIEW_REASON for it, never
    // a raw "Verified reason: <code>" dump (that fallback belongs to a different
    // function, reasonMessage(), for candidate-eligibility reasons — review
    // reasons never go through it). Assert the real current copy. When QW-4b
    // lands curated text for this code, tighten this assertion to that text.
    await expect(
      page.getByText(
        "Some of your answers need a person's judgment before we can confirm a path.",
      ),
    ).toBeVisible({ timeout: 30_000 });
    const initialRequest = {
      body: evaluateRequest.postData() ?? "",
      idempotencyKey: evaluateRequest.headers()["idempotency-key"] ?? "",
      path: `${evaluateUrl.pathname}${evaluateUrl.search}`,
    };
    expect(initialRequest.body).not.toBe("");
    expect(initialRequest.idempotencyKey).toMatch(UUID);
    expect(initialRequest.path).toBe(
      "/api/visa-oracle/evaluate?traffic_source=real",
    );

    // Chromium can evict a navigation response body before Playwright reads
    // it. Re-read the already-completed durable result through the product's
    // exact idempotent endpoint instead of racing CDP Network.getResponseBody.
    const firstReplay = await page.evaluate(
      async ({ path, body, key }) => {
        const response = await fetch(path, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": key,
          },
          body,
        });
        return {
          status: response.status,
          body: (await response.json()) as PublicDecisionResponse,
        };
      },
      {
        path: initialRequest.path,
        body: initialRequest.body,
        key: initialRequest.idempotencyKey,
      },
    );
    expect(firstReplay.status).toBe(200);
    const captured: CapturedEvaluation = {
      ...initialRequest,
      response: firstReplay.body,
    };
    expect(captured.response.mode).toBe("ENGINE");
    expect(captured.response.decision.state).toBe("HUMAN_REVIEW_REQUIRED");
    expect(captured.response.decision.candidates).toEqual([]);
    expect(captured.response.decision.trace_sha256).toMatch(SHA256);
    expect(captured.response.decision.review_reasons).toHaveLength(1);
    expect(captured.response.decision.review_reasons[0]?.code).toBe(
      "DECISIVE_SOURCE_FRESHNESS_UNKNOWN",
    );
    expect(captured.response.sources).toHaveLength(1);
    expect(captured.response.sources[0]?.freshness.status).toBe("UNKNOWN");
    expect(captured.response.sources[0]?.canonical_url).toBe(
      "https://www.imigrasi.go.id/id/visa-kunjungan/",
    );

    const replay = await page.evaluate(
      async ({ path, body, key }) => {
        const response = await fetch(path, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": key,
          },
          body,
        });
        return {
          status: response.status,
          body: (await response.json()) as PublicDecisionResponse,
        };
      },
      {
        path: initialRequest.path,
        body: initialRequest.body,
        key: initialRequest.idempotencyKey,
      },
    );
    expect(replay.status).toBe(200);
    expect(replay.body).toEqual(captured.response);

    const decisionId = captured.response.decision.decision_id;
    expect(decisionId).toMatch(UUID);
    const evidence = readPersistenceEvidence(
      decisionId ?? "",
      captured.idempotencyKey,
      captured.response.decision.trace_sha256 ?? "",
    );
    expect(evidence).toEqual({
      activation_bound: true,
      decision_count: 1,
      decision_integrity_bound: true,
      engine_mode: "ENFORCE",
      environment: "TEST",
      idempotency_completed: true,
      idempotency_count: 1,
      idempotency_response_bound: true,
      retention_active: true,
      retention_policy: "zero-test-v1",
      rule_pack_bound: true,
      trace_bound: true,
      verdict: "HUMAN_REVIEW_REQUIRED",
    });
  });
});
