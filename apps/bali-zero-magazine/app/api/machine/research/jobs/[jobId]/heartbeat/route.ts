import {
  authenticateMachineRequest,
  machineFailure,
  parseJsonBody,
} from "../../../../../../../lib/server/machine-ingress.ts";
import {
  createResearchRepository,
  parseResearchHeartbeat,
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
    const heartbeat = parseResearchHeartbeat(parseJsonBody(verified.body));
    const job = await createResearchRepository(db).heartbeat(
      jobId,
      heartbeat.claimToken,
      heartbeat.fencingToken,
      heartbeat.leaseSeconds,
    );
    return Response.json(
      { ok: true, status: job.status, lease_deadline: job.lease_deadline },
      { status: 200, headers: privateNoStoreHeaders() },
    );
  } catch (error) {
    return error instanceof TypeError
      ? machineFailure(400)
      : machineFailure(409);
  }
}
