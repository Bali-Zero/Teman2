import {
  authenticateMachineRequest,
  machineFailure,
  parseJsonBody,
} from "../../../../../../../lib/server/machine-ingress.ts";
import {
  createOperationsRepository,
  parseOperationLeaseRequest,
} from "../../../../../../../lib/server/operations-repository.ts";
import { currentResearchRoleAllowlist } from "../../../../../../../lib/server/research-http.ts";
import { getMagazineBindings } from "../../../../../../../lib/server/runtime-bindings.ts";
import { privateNoStoreHeaders } from "../../../../../../../lib/server/security.ts";

type Context = Readonly<{ params: Promise<{ intentId: string }> }>;
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
    const intentId = (await context.params).intentId;
    if (!/^ops-intent-[A-Za-z0-9-]{16,112}$/.test(intentId))
      return machineFailure(400);
    const input = parseOperationLeaseRequest(
      parseJsonBody(verified.body),
      "ops-pre-effect-attest.v1",
    );
    const roles = currentResearchRoleAllowlist();
    const attestation = await createOperationsRepository(db).attestPreEffect(
      {
        intent_id: intentId,
        claim_token: input.claimToken,
        fencing_token: input.fencingToken,
      },
      { operatorActorKeys: roles.operators, policyVersion: roles.version },
    );
    return Response.json(
      { ok: true, attestation },
      { headers: privateNoStoreHeaders() },
    );
  } catch (error) {
    return error instanceof TypeError
      ? machineFailure(400)
      : machineFailure(409);
  }
}
