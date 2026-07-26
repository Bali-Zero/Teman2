import { parseAuditAnchorReceipt } from "../../../../lib/contracts/audit-anchor.ts";
import {
  acceptAuditAnchor,
  blockAuditPromotions,
  verifyAuditAnchorReceipt,
} from "../../../../lib/server/audit-chain.ts";
import {
  authenticateMachineRequest,
  machineFailure,
  machineResult,
  parseJsonBody,
} from "../../../../lib/server/machine-ingress.ts";
import { getMagazineBindings } from "../../../../lib/server/runtime-bindings.ts";

export async function POST(request: Request): Promise<Response> {
  let verified;
  try {
    verified = await authenticateMachineRequest(request);
  } catch {
    return machineFailure(401);
  }
  const bindings = getMagazineBindings();
  const db = bindings.DB;
  if (db === undefined) return machineFailure(409);
  if (request.headers.get("content-type") !== "application/json") {
    await blockAuditPromotions(db, "invalid_anchor_content_type");
    return machineFailure(400);
  }
  try {
    const receipt = parseAuditAnchorReceipt(parseJsonBody(verified.body));
    await verifyAuditAnchorReceipt(
      receipt,
      bindings.AUDIT_ANCHOR_KEY_REGISTRY_JSON,
    );
    return machineResult(await acceptAuditAnchor(db, receipt));
  } catch (error) {
    await blockAuditPromotions(db, "invalid_or_conflicting_anchor");
    if (
      error instanceof TypeError &&
      !/registry|anchor key is required|unknown anchor key/i.test(error.message)
    ) {
      return machineFailure(400);
    }
    return machineFailure(409);
  }
}
