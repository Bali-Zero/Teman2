import {
  authorizeOperationsRequest,
  OperationsHttpError,
  operationsFailure,
  operationsJson,
} from "../../../../../lib/server/operations-http.ts";
import { createOperationsRepository } from "../../../../../lib/server/operations-repository.ts";
import { getMagazineBindings } from "../../../../../lib/server/runtime-bindings.ts";

type Context = Readonly<{ params: Promise<{ intentId: string }> }>;

export async function GET(
  request: Request,
  context: Context,
): Promise<Response> {
  try {
    await authorizeOperationsRequest(request, "magazine:read");
    const db = getMagazineBindings().DB;
    if (db === undefined) throw new Error("database binding is required");
    const intentId = (await context.params).intentId;
    if (!/^ops-intent-[A-Za-z0-9-]{16,112}$/.test(intentId))
      throw new TypeError("invalid intent id");
    const intent = await createOperationsRepository(db).getIntent(intentId);
    if (intent === null) throw new OperationsHttpError(404, "not_found");
    return operationsJson({ ok: true, intent });
  } catch (error) {
    return operationsFailure(error);
  }
}
