import {
  authorizeResearchRequest,
  publicResearchJob,
  readClosedJson,
  requireSameOriginMutation,
  researchFailure,
  researchJson,
} from "../../../../lib/server/research-http.ts";
import {
  createResearchRepository,
  parseResearchCatalog,
  parseResearchRequest,
} from "../../../../lib/server/research-repository.ts";
import { getMagazineBindings } from "../../../../lib/server/runtime-bindings.ts";

export const dynamic = "force-dynamic";

function exactSubmission(value: unknown): {
  idempotencyKey: string;
  request: unknown;
} {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new TypeError("invalid research submission");
  }
  const record = value as Record<string, unknown>;
  if (
    Object.keys(record).sort().join(",") !== "idempotency_key,request" ||
    typeof record.idempotency_key !== "string" ||
    !/^[A-Za-z0-9][A-Za-z0-9:_-]{15,95}$/.test(record.idempotency_key)
  ) {
    throw new TypeError("invalid research submission");
  }
  return { idempotencyKey: record.idempotency_key, request: record.request };
}

export async function GET(request: Request): Promise<Response> {
  try {
    await authorizeResearchRequest(request, "magazine:read");
    const db = getMagazineBindings().DB;
    if (db === undefined) throw new Error("database binding is required");
    const repository = createResearchRepository(db);
    const [jobs, evidence] = await Promise.all([
      repository.listJobs(),
      repository.listPublishedEvidence(),
    ]);
    return researchJson({
      ok: true,
      jobs: jobs.map(publicResearchJob),
      published_evidence: evidence,
    });
  } catch (error) {
    return researchFailure(error);
  }
}

export async function POST(request: Request): Promise<Response> {
  try {
    requireSameOriginMutation(request);
    const viewer = await authorizeResearchRequest(request, "research:create");
    const bindings = getMagazineBindings();
    if (bindings.DB === undefined)
      throw new Error("database binding is required");
    const submission = exactSubmission(await readClosedJson(request));
    const catalog = parseResearchCatalog(bindings.RESEARCH_CATALOG_JSON);
    const sanitized = parseResearchRequest(submission.request, catalog);
    const created = await createResearchRepository(bindings.DB).createJob(
      viewer.actorKey,
      sanitized,
      submission.idempotencyKey,
    );
    return researchJson(
      { ok: true, status: created.status, job: publicResearchJob(created.job) },
      created.status === "created" ? 201 : 200,
    );
  } catch (error) {
    return researchFailure(error);
  }
}
