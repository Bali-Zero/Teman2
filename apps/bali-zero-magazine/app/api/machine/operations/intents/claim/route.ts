import {
  authenticateMachineRequest,
  machineFailure,
  parseJsonBody,
} from "../../../../../../lib/server/machine-ingress.ts";
import {
  createOperationsRepository,
  parseOperationClaimRequest,
} from "../../../../../../lib/server/operations-repository.ts";
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
    const input = parseOperationClaimRequest(parseJsonBody(verified.body));
    const roles = currentResearchRoleAllowlist();
    const intent = await createOperationsRepository(db).claimNext({
      ...input,
      operatorActorKeys: roles.operators,
      policyVersion: roles.version,
    });
    return Response.json(
      { ok: true, intent },
      { status: 200, headers: privateNoStoreHeaders() },
    );
  } catch (error) {
    return error instanceof TypeError
      ? machineFailure(400)
      : machineFailure(409);
  }
}
