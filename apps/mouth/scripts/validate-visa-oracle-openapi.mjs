import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const EVALUATE_PATH = "/api/visa-oracle/evaluate";
const REQUIRED_STATES = new Set([
  "SUPPORTED_CANDIDATES",
  "NEEDS_INPUT",
  "HUMAN_REVIEW_REQUIRED",
  "NO_SUPPORTED_PATH",
  "TEMPORARILY_UNAVAILABLE",
]);
const REQUIRED_RESPONSE_MODES = new Set(["CURATED", "ENGINE"]);
const REQUIRED_ERROR_STATUSES = ["400", "409", "413", "415", "422"];

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const schemaPath = path.resolve(
  scriptDirectory,
  "../../backend-rag/openapi.json",
);

function fail(message) {
  throw new Error(`Visa Oracle OpenAPI contract: ${message}`);
}

function asObject(value, label) {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    fail(`${label} must be an object`);
  }
  return value;
}

function dereference(document, schema, label) {
  const candidate = asObject(schema, label);
  if (typeof candidate.$ref !== "string") return candidate;
  const prefix = "#/components/schemas/";
  if (!candidate.$ref.startsWith(prefix)) {
    fail(`${label} uses unsupported reference ${candidate.$ref}`);
  }
  const name = candidate.$ref.slice(prefix.length);
  return asObject(document.components?.schemas?.[name], `${label} (${name})`);
}

function collectEnums(value, enums = []) {
  if (Array.isArray(value)) {
    for (const item of value) collectEnums(item, enums);
    return enums;
  }
  if (typeof value !== "object" || value === null) return enums;
  if (Array.isArray(value.enum)) enums.push(value.enum);
  for (const child of Object.values(value)) collectEnums(child, enums);
  return enums;
}

function assertRequiredProperties(schema, keys, label) {
  const required = new Set(schema.required ?? []);
  for (const key of keys) {
    if (!required.has(key) || !schema.properties?.[key]) {
      fail(`${label} must require ${key}`);
    }
  }
}

function assertClosedObject(schema, label) {
  if (schema.type !== "object" || schema.additionalProperties !== false) {
    fail(`${label} must be a closed object`);
  }
}

function assertExactEnum(document, schema, values, label) {
  const resolved = dereference(document, schema, label);
  const actual = new Set(resolved.enum ?? []);
  if (
    actual.size !== values.size ||
    [...actual].some((value) => !values.has(value))
  ) {
    fail(`${label} must export exactly ${[...values].join(", ")}`);
  }
}

function assertParameter(parameters, name, location) {
  const found = parameters.find(
    (parameter) =>
      typeof parameter === "object" &&
      parameter !== null &&
      typeof parameter.name === "string" &&
      parameter.name.toLowerCase() === name.toLowerCase() &&
      parameter.in === location,
  );
  if (!found) fail(`POST is missing ${location} parameter ${name}`);
  return found;
}

async function main() {
  const document = JSON.parse(await readFile(schemaPath, "utf8"));
  const pathItem = asObject(document.paths?.[EVALUATE_PATH], EVALUATE_PATH);
  const operation = asObject(pathItem.post, `${EVALUATE_PATH} POST`);
  if (operation.operationId !== "evaluateVisaOracleV2") {
    fail("POST operationId must remain evaluateVisaOracleV2");
  }

  const requestBody = asObject(operation.requestBody, "POST requestBody");
  if (requestBody.required !== true) fail("requestBody must be required");
  const requestSchema = dereference(
    document,
    requestBody.content?.["application/json"]?.schema,
    "POST application/json request schema",
  );
  assertClosedObject(requestSchema, "request schema");
  assertRequiredProperties(
    requestSchema,
    ["schema_version", "assessment_id", "collected_at", "facts"],
    "request schema",
  );
  if (!requestSchema.properties?.disclosed_review_flags) {
    fail("request schema must expose conservative disclosed_review_flags");
  }

  const response = asObject(operation.responses?.["200"], "POST 200 response");
  const responseSchema = dereference(
    document,
    response.content?.["application/json"]?.schema,
    "POST 200 application/json response schema",
  );
  assertClosedObject(responseSchema, "typed response");
  assertRequiredProperties(
    responseSchema,
    ["mode", "decision", "sources", "display"],
    "typed response",
  );
  assertExactEnum(
    document,
    responseSchema.properties.mode,
    REQUIRED_RESPONSE_MODES,
    "response mode",
  );

  const decisionSchema = dereference(
    document,
    responseSchema.properties.decision,
    "response decision",
  );
  assertClosedObject(decisionSchema, "response decision");
  assertRequiredProperties(
    decisionSchema,
    [
      "state",
      "candidates",
      "missing_facts",
      "review_reasons",
      "no_path_reasons",
      "outage",
      "quotes",
      "rule_pack",
      "trace_sha256",
      "decision_integrity",
    ],
    "response decision",
  );
  assertExactEnum(
    document,
    decisionSchema.properties.state,
    REQUIRED_STATES,
    "decision state",
  );

  const displaySchema = dereference(
    document,
    responseSchema.properties.display,
    "response display",
  );
  assertClosedObject(displaySchema, "response display");
  assertRequiredProperties(displaySchema, ["candidates"], "response display");
  if (
    responseSchema.properties.sources?.type !== "array" ||
    !responseSchema.properties.sources?.items?.$ref
  ) {
    fail("response sources must be a typed array");
  }

  const stateEnums = collectEnums(document.components?.schemas).find(
    (values) =>
      values.length === REQUIRED_STATES.size &&
      values.every((value) => REQUIRED_STATES.has(value)),
  );
  if (!stateEnums) fail("the exact five DecisionState values are not exported");

  for (const status of REQUIRED_ERROR_STATUSES) {
    const errorResponse = asObject(
      operation.responses?.[status],
      `POST ${status} response`,
    );
    const errorSchema = dereference(
      document,
      errorResponse.content?.["application/json"]?.schema,
      `POST ${status} application/json response schema`,
    );
    assertClosedObject(errorSchema, `POST ${status} response`);
    assertRequiredProperties(
      errorSchema,
      ["detail"],
      `POST ${status} response`,
    );
  }

  const parameters = [
    ...(pathItem.parameters ?? []),
    ...(operation.parameters ?? []),
  ];
  const trafficSource = assertParameter(parameters, "traffic_source", "query");
  if (trafficSource.required !== true) {
    fail("POST query parameter traffic_source must be required");
  }
  assertParameter(parameters, "request_category", "query");
  assertParameter(parameters, "Idempotency-Key", "header");

  process.stdout.write(
    `Visa Oracle OpenAPI contract valid: ${EVALUATE_PATH} (${REQUIRED_STATES.size} states)\n`,
  );
}

main().catch((error) => {
  process.stderr.write(
    `${error instanceof Error ? error.message : String(error)}\n`,
  );
  process.exitCode = 1;
});
