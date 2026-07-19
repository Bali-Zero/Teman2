import {
  authenticateMachineRequest,
  machineFailure,
  parseJsonBody,
} from "../../../../../../../lib/server/machine-ingress.ts";
import {
  createOperationsRepository,
  parseOperationResult,
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
    const result = parseOperationResult(parseJsonBody(verified.body));
    if (result.intent_id !== intentId) return machineFailure(400);
    const persisted = await createOperationsRepository(db).complete(
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
