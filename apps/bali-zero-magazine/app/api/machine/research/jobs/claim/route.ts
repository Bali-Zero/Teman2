import {
  authenticateMachineRequest,
  machineFailure,
  parseJsonBody,
} from "../../../../../../lib/server/machine-ingress.ts";
import {
  createResearchRepository,
  parseResearchClaimRequest,
} from "../../../../../../lib/server/research-repository.ts";
import { currentResearchRoleAllowlist } from "../../../../../../lib/server/research-http.ts";
import { getMagazineBindings } from "../../../../../../lib/server/runtime-bindings.ts";
import { privateNoStoreHeaders } from "../../../../../../lib/server/security.ts";

export async function POST(request: Request): Promise<Response> {
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
    const input = parseResearchClaimRequest(parseJsonBody(verified.body));
    const currentRoles = currentResearchRoleAllowlist();
    const job = await createResearchRepository(db).claimNext({
      ...input,
      analystActorKeys: currentRoles.analysts,
    });
    return Response.json(
      {
        ok: true,
        job:
          job === null
            ? null
            : {
                schema_version: "research-job.v1",
                job_id: job.job_id,
                request_hash: job.request_hash,
                mode: job.mode,
                request: job.request,
                status: job.status,
                claim_token: job.claim_token,
                fencing_token: job.fencing_token,
                lease_deadline: job.lease_deadline,
              },
      },
      { status: 200, headers: privateNoStoreHeaders() },
    );
  } catch (error) {
    return error instanceof TypeError
      ? machineFailure(400)
      : machineFailure(409);
  }
}
