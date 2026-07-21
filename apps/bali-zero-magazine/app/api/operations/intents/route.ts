import {
  authorizeOperationsRequest,
  operationsFailure,
  operationsJson,
} from "../../../../lib/server/operations-http.ts";
import {
  createOperationsRepository,
  parseOperationIntentRequest,
} from "../../../../lib/server/operations-repository.ts";
import {
  currentResearchRoleAllowlist,
  readClosedJson,
  requireSameOriginMutation,
} from "../../../../lib/server/research-http.ts";
import { getMagazineBindings } from "../../../../lib/server/runtime-bindings.ts";

export const dynamic = "force-dynamic";

export async function GET(request: Request): Promise<Response> {
  try {
    await authorizeOperationsRequest(request, "magazine:read");
    const db = getMagazineBindings().DB;
    if (db === undefined) throw new Error("database binding is required");
    const repository = createOperationsRepository(db);
    const [health, intents] = await Promise.all([
      repository.healthSnapshot(),
      repository.listIntents(),
    ]);
    return operationsJson({ ok: true, health, intents });
  } catch (error) {
    return operationsFailure(error);
  }
}

export async function POST(request: Request): Promise<Response> {
  try {
    requireSameOriginMutation(request);
    const viewer = await authorizeOperationsRequest(request, "ops:create");
    const bindings = getMagazineBindings();
    if (bindings.DB === undefined)
      throw new Error("database binding is required");
    const parsed = parseOperationIntentRequest(await readClosedJson(request));
    const roles = currentResearchRoleAllowlist();
    const created = await createOperationsRepository(bindings.DB).createIntent({
      actorKey: viewer.actorKey,
      effectiveRole: viewer.role,
      policyVersion: roles.version,
      operatorActorKeys: roles.operators,
      request: parsed,
    });
    return operationsJson(
      { ok: true, status: created.status, intent: created.intent },
      created.status === "created" ? 201 : 200,
    );
  } catch (error) {
    return operationsFailure(error);
  }
}
