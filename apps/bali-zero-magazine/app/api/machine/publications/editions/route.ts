// @ts-expect-error TypeScript requires allowImportingTsExtensions for this runtime-safe import.
import { parseEditionPacket } from "../../../../../lib/contracts/publication.ts";
// @ts-expect-error TypeScript requires allowImportingTsExtensions for this runtime-safe import.
import {
  authenticateMachineRequest,
  machineFailure,
  machineResult,
  parseJsonBody,
} from "../../../../../lib/server/machine-ingress.ts";
// @ts-expect-error TypeScript requires allowImportingTsExtensions for this runtime-safe import.
import { createPublicationRepository } from "../../../../../lib/server/publication-repository.ts";
// @ts-expect-error TypeScript requires allowImportingTsExtensions for this runtime-safe import.
import { getMagazineBindings } from "../../../../../lib/server/runtime-bindings.ts";

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
    const packet = parseEditionPacket(parseJsonBody(verified.body));
    const repository = createPublicationRepository(db);
    const stage = await repository.stageEdition(packet, verified.bodySha256);
    const finalization = await repository.finalizeEdition(packet.packet_id);
    return machineResult(
      stage === "replay" || finalization === "replay" ? "replay" : "created",
    );
  } catch (error) {
    return error instanceof TypeError
      ? machineFailure(400)
      : machineFailure(409);
  }
}
