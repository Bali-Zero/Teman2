import {
  authenticateMachineRequest,
  machineFailure,
  parseJsonBody,
} from "../../../../../../../lib/server/machine-ingress.ts";
import {
  createResearchRepository,
  parseResearchResult,
} from "../../../../../../../lib/server/research-repository.ts";
import { getMagazineBindings } from "../../../../../../../lib/server/runtime-bindings.ts";
import { privateNoStoreHeaders } from "../../../../../../../lib/server/security.ts";

type Context = Readonly<{ params: Promise<{ jobId: string }> }>;

export async function POST(
  request: Request,
  context: Context,
): Promise<Response> {
  let verified;
  try {
    verified = await authenticateMachineRequest(request);
  } catch {
    return machineFailure(401);
  }
  try {
    if (request.headers.get("content-type") !== "application/json")
      return machineFailure(400);
    const db = getMagazineBindings().DB;
    if (db === undefined) return machineFailure(409);
    const jobId = (await context.params).jobId;
    if (!/^research-job-[A-Za-z0-9-]{16,80}$/.test(jobId))
      return machineFailure(400);
    const result = parseResearchResult(parseJsonBody(verified.body));
    if (result.job_id !== jobId) return machineFailure(400);
    const persisted = await createResearchRepository(db).complete(
      result,
      verified.keyId,
      verified.bodySha256,
    );
    return Response.json(
      { ok: true, status: persisted.status },
      {
        status: persisted.status === "created" ? 201 : 200,
        headers: privateNoStoreHeaders(),
      },
    );
  } catch (error) {
    return error instanceof TypeError
      ? machineFailure(400)
      : machineFailure(409);
  }
}
