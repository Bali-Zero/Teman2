import { parseStoryPacket } from "../../../../../lib/contracts/publication.ts";
import {
  authenticateMachineRequest,
  machineFailure,
  machinePromotionBlocked,
  machineResult,
  parseJsonBody,
} from "../../../../../lib/server/machine-ingress.ts";
import { createPublicationRepository } from "../../../../../lib/server/publication-repository.ts";
import { getMagazineBindings } from "../../../../../lib/server/runtime-bindings.ts";
import {
  consumePromotionPermit,
  ensurePublicationAuditCandidate,
  isPromotionAuthorized,
} from "../../../../../lib/server/audit-chain.ts";

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
    const packet = parseStoryPacket(parseJsonBody(verified.body));
    const repository = createPublicationRepository(db);
    await repository.stageBreaking(packet, verified.bodySha256);
    await ensurePublicationAuditCandidate(
      db,
      "breaking.publish",
      packet.packet_id,
    );
    if (
      !(await isPromotionAuthorized(db, "breaking.publish", packet.packet_id))
    ) {
      return machinePromotionBlocked("breaking.publish", packet.packet_id);
    }
    const finalization = await repository.finalizeBreaking(packet.packet_id);
    if (finalization === "published") {
      await consumePromotionPermit(db, "breaking.publish", packet.packet_id);
    }
    return machineResult(finalization === "replay" ? "replay" : "created");
  } catch (error) {
    return error instanceof TypeError
      ? machineFailure(400)
      : machineFailure(409);
  }
}
