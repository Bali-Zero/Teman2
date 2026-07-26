import {
  authenticateOperationsMachineRequest,
  isMachinePayloadTooLarge,
  machineFailure,
  parseJsonBody,
} from "../../../../../lib/server/machine-ingress.ts";
import {
  createOperationsRepository,
  parseOperationEffect,
} from "../../../../../lib/server/operations-repository.ts";
import { getMagazineBindings } from "../../../../../lib/server/runtime-bindings.ts";
import { privateNoStoreHeaders } from "../../../../../lib/server/security.ts";

export async function POST(request: Request): Promise<Response> {
  let verified;
  try {
    verified = await authenticateOperationsMachineRequest(request);
  } catch (error) {
    return machineFailure(isMachinePayloadTooLarge(error) ? 413 : 401);
  }
  try {
    if (request.headers.get("content-type") !== "application/json") {
      return machineFailure(400);
    }
    const bindings = getMagazineBindings();
    if (bindings.DB === undefined) return machineFailure(409);
    const effect = parseOperationEffect(parseJsonBody(verified.body));
    const receipt = await createOperationsRepository(
      bindings.DB,
    ).applyStoryEffect(effect, bindings.RELEASE_ATTESTATION_KEY_REGISTRY_JSON);
    return Response.json(
      { ok: true, receipt },
      { status: 200, headers: privateNoStoreHeaders() },
    );
  } catch (error) {
    return error instanceof TypeError
      ? machineFailure(400)
      : machineFailure(409);
  }
}
