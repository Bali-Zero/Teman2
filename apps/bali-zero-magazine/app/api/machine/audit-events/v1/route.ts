import { parseAuditFeedQuery } from "../../../../../lib/contracts/audit-anchor.ts";
import { readPublicationAuditFeed } from "../../../../../lib/server/audit-chain.ts";
import {
  authenticateMachineRequest,
  machineFailure,
} from "../../../../../lib/server/machine-ingress.ts";
import { getMagazineBindings } from "../../../../../lib/server/runtime-bindings.ts";
import { privateNoStoreHeaders } from "../../../../../lib/server/security.ts";

export async function GET(request: Request): Promise<Response> {
  try {
    await authenticateMachineRequest(request);
  } catch {
    return machineFailure(401);
  }
  try {
    if (request.headers.get("content-type") !== "application/json") {
      return machineFailure(400);
    }
    const db = getMagazineBindings().DB;
    if (db === undefined) return machineFailure(409);
    const feed = await readPublicationAuditFeed(
      db,
      parseAuditFeedQuery(new URL(request.url)),
    );
    return Response.json(feed, { headers: privateNoStoreHeaders() });
  } catch (error) {
    return error instanceof TypeError
      ? machineFailure(400)
      : machineFailure(409);
  }
}
