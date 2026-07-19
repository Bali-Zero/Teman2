import {
  authenticateMachineRequest,
  machineFailure,
  parseJsonBody,
} from "../../../../../../../lib/server/machine-ingress.ts";
import {
  createOperationsRepository,
  parseOperationLeaseRequest,
} from "../../../../../../../lib/server/operations-repository.ts";
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
      "ops-heartbeat.v1",
    );
    const intent = await createOperationsRepository(db).heartbeat(
      {
        intent_id: intentId,
        claim_token: input.claimToken,
        fencing_token: input.fencingToken,
      },
      input.leaseSeconds!,
    );
    return Response.json(
      {
        ok: true,
        status: intent.status,
        lease_deadline: intent.lease_deadline,
      },
      { headers: privateNoStoreHeaders() },
    );
  } catch (error) {
    return error instanceof TypeError
      ? machineFailure(400)
      : machineFailure(409);
  }
}
