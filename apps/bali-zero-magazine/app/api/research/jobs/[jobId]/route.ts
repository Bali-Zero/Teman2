import {
  authorizeResearchRequest,
  publicResearchJob,
  requireSameOriginMutation,
  researchFailure,
  researchJson,
} from "../../../../../lib/server/research-http.ts";
import { createResearchRepository } from "../../../../../lib/server/research-repository.ts";
import { getMagazineBindings } from "../../../../../lib/server/runtime-bindings.ts";

export const dynamic = "force-dynamic";

type Context = Readonly<{ params: Promise<{ jobId: string }> }>;

function safeJobId(value: string): string {
  if (!/^research-job-[A-Za-z0-9-]{16,80}$/.test(value)) {
    throw new TypeError("invalid job id");
  }
  return value;
}

export async function GET(
  request: Request,
  context: Context,
): Promise<Response> {
  try {
    await authorizeResearchRequest(request, "magazine:read");
    const db = getMagazineBindings().DB;
    if (db === undefined) throw new Error("database binding is required");
    const job = await createResearchRepository(db).getJob(
      safeJobId((await context.params).jobId),
    );
    if (job === null)
      return researchJson({ ok: false, error: "not_found" }, 404);
    return researchJson({ ok: true, job: publicResearchJob(job) });
  } catch (error) {
    return researchFailure(error);
  }
}

export async function DELETE(
  request: Request,
  context: Context,
): Promise<Response> {
  try {
    requireSameOriginMutation(request);
    const viewer = await authorizeResearchRequest(
      request,
      "research:cancel-own",
    );
    const db = getMagazineBindings().DB;
    if (db === undefined) throw new Error("database binding is required");
    const jobId = safeJobId((await context.params).jobId);
    const cancelled = await createResearchRepository(db).cancelOwn(
      jobId,
      viewer.actorKey,
    );
    if (!cancelled) return researchJson({ ok: false, error: "conflict" }, 409);
    return researchJson({ ok: true, status: "cancelled", job_id: jobId });
  } catch (error) {
    return researchFailure(error);
  }
}
