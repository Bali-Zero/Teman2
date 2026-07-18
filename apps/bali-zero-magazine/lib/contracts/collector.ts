// Node's type-stripping test runner executes the TypeScript source directly.
// @ts-expect-error TypeScript requires allowImportingTsExtensions for this runtime-safe import.
import {
  requireClosedRecord,
  requireEnum,
  requireInteger,
  requireSha256,
  requireString,
  requireTimestamp,
} from "./publication.ts";

export type CollectorRunProjectionV1 = Readonly<{
  schema_version: "collector-run.v1";
  run_id: string;
  system_id: string;
  collector_id: string;
  started_at: string;
  completed_at: string;
  status: "healthy" | "delayed" | "degraded" | "unavailable" | "unknown";
  freshness: "fresh" | "delayed" | "archived";
  items_seen: number;
  items_eligible: number;
  source_count: number;
  unreachable_source_count: number;
  watermark: string;
  verified_at: string;
}>;

export type AssetUploadMetadataV1 = Readonly<{
  schema_version: "asset-upload.v1";
  packet_id: string;
  asset_id: string;
  sha256: string;
  byte_count: number;
  mime_type: "image/jpeg" | "image/png" | "image/webp";
  width: number;
  height: number;
  captured_at: string;
  rights_status: "approved";
}>;

export function parseCollectorRunProjection(
  raw: unknown,
): CollectorRunProjectionV1 {
  const run = requireClosedRecord(raw, "collector run", [
    "schema_version",
    "run_id",
    "system_id",
    "collector_id",
    "started_at",
    "completed_at",
    "status",
    "freshness",
    "items_seen",
    "items_eligible",
    "source_count",
    "unreachable_source_count",
    "watermark",
    "verified_at",
  ]);
  if (run.schema_version !== "collector-run.v1") {
    throw new TypeError(
      `unsupported schema_version ${String(run.schema_version)}`,
    );
  }
  const startedAt = requireTimestamp(
    run.started_at,
    "collector run.started_at",
  );
  const completedAt = requireTimestamp(
    run.completed_at,
    "collector run.completed_at",
  );
  if (Date.parse(completedAt) < Date.parse(startedAt)) {
    throw new TypeError("collector run completed_at precedes started_at");
  }
  const itemsSeen = requireInteger(run.items_seen, "collector run.items_seen");
  const itemsEligible = requireInteger(
    run.items_eligible,
    "collector run.items_eligible",
  );
  if (itemsEligible > itemsSeen)
    throw new TypeError("items_eligible exceeds items_seen");
  const sourceCount = requireInteger(
    run.source_count,
    "collector run.source_count",
  );
  const unreachableSourceCount = requireInteger(
    run.unreachable_source_count,
    "collector run.unreachable_source_count",
  );
  if (unreachableSourceCount > sourceCount) {
    throw new TypeError("unreachable_source_count exceeds source_count");
  }
  return {
    schema_version: "collector-run.v1",
    run_id: requireString(run.run_id, "collector run.run_id"),
    system_id: requireString(run.system_id, "collector run.system_id"),
    collector_id: requireString(run.collector_id, "collector run.collector_id"),
    started_at: startedAt,
    completed_at: completedAt,
    status: requireEnum(run.status, "collector run.status", [
      "healthy",
      "delayed",
      "degraded",
      "unavailable",
      "unknown",
    ] as const),
    freshness: requireEnum(run.freshness, "collector run.freshness", [
      "fresh",
      "delayed",
      "archived",
    ] as const),
    items_seen: itemsSeen,
    items_eligible: itemsEligible,
    source_count: sourceCount,
    unreachable_source_count: unreachableSourceCount,
    watermark: requireString(run.watermark, "collector run.watermark"),
    verified_at: requireTimestamp(run.verified_at, "collector run.verified_at"),
  };
}

export function parseAssetUploadMetadata(raw: unknown): AssetUploadMetadataV1 {
  const asset = requireClosedRecord(raw, "asset upload metadata", [
    "schema_version",
    "packet_id",
    "asset_id",
    "sha256",
    "byte_count",
    "mime_type",
    "width",
    "height",
    "captured_at",
    "rights_status",
  ]);
  if (asset.schema_version !== "asset-upload.v1") {
    throw new TypeError(
      `unsupported schema_version ${String(asset.schema_version)}`,
    );
  }
  const byteCount = requireInteger(
    asset.byte_count,
    "asset upload metadata.byte_count",
    1,
  );
  if (byteCount > 12 * 1024 * 1024)
    throw new TypeError("asset exceeds 12 MiB limit");
  const width = requireInteger(asset.width, "asset upload metadata.width", 1);
  const height = requireInteger(
    asset.height,
    "asset upload metadata.height",
    1,
  );
  if (width > 8192 || height > 8192)
    throw new TypeError("asset dimension exceeds 8192 pixels");
  if (width * height > 40_000_000)
    throw new TypeError("asset decoded pixel count exceeds limit");
  return {
    schema_version: "asset-upload.v1",
    packet_id: requireString(
      asset.packet_id,
      "asset upload metadata.packet_id",
    ),
    asset_id: requireString(asset.asset_id, "asset upload metadata.asset_id"),
    sha256: requireSha256(asset.sha256, "asset upload metadata.sha256"),
    byte_count: byteCount,
    mime_type: requireEnum(asset.mime_type, "asset upload metadata.mime_type", [
      "image/jpeg",
      "image/png",
      "image/webp",
    ] as const),
    width,
    height,
    captured_at: requireTimestamp(
      asset.captured_at,
      "asset upload metadata.captured_at",
    ),
    rights_status: requireEnum(
      asset.rights_status,
      "asset upload metadata.rights_status",
      ["approved"] as const,
    ),
  };
}
