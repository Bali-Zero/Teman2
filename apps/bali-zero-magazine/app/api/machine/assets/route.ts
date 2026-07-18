import { parseAssetUploadMetadata } from "../../../../lib/contracts/collector.ts";
import {
  authenticateMachineRequest,
  machineFailure,
  machineResult,
} from "../../../../lib/server/machine-ingress.ts";
import {
  storeVerifiedAsset,
  validateImageAsset,
} from "../../../../lib/server/media.ts";
import { createPublicationRepository } from "../../../../lib/server/publication-repository.ts";
import { getMagazineBindings } from "../../../../lib/server/runtime-bindings.ts";

const METADATA_HEADER = "x-magazine-asset-metadata";

export async function POST(request: Request): Promise<Response> {
  let verified;
  try {
    verified = await authenticateMachineRequest(request, {
      signedHeaderNames: [METADATA_HEADER],
    });
  } catch {
    return machineFailure(401);
  }
  try {
    const rawMetadata = request.headers.get(METADATA_HEADER);
    if (rawMetadata === null) return machineFailure(400);
    const metadata = parseAssetUploadMetadata(
      JSON.parse(rawMetadata) as unknown,
    );
    const contentType = request.headers.get("content-type") ?? "";
    const image = await validateImageAsset(
      verified.body,
      contentType,
      metadata,
    );
    const bindings = getMagazineBindings();
    if (bindings.DB === undefined || bindings.MEDIA === undefined)
      return machineFailure(409);
    const key = await storeVerifiedAsset(
      bindings.MEDIA,
      verified.body,
      metadata,
      image,
    );
    const result = await createPublicationRepository(
      bindings.DB,
    ).ingestVerifiedAsset(metadata, key);
    return machineResult(result);
  } catch (error) {
    if (error instanceof TypeError) {
      return error.message.includes("12 MiB") ||
        error.message.includes("byte length exceeds")
        ? machineFailure(413)
        : machineFailure(400);
    }
    return machineFailure(409);
  }
}
