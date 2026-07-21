// Node's type-stripping test runner executes the TypeScript source directly.
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
  alt_text: string;
  source: string;
  source_url: string | null;
  rights_basis:
    | "internal-owned"
    | "licensed"
    | "public-domain"
    | "official-use"
    | "generated";
  rights_status: "approved";
  usage_status: "approved";
  dlp_status: "passed";
  sanitization_status: "passed";
  perceptual_dedup_status: "unique" | "intentional-reuse";
}>;

export type AssetUploadMetadataV2 = Readonly<{
  schema_version: "asset-upload.v2";
  packet_id: string;
  asset_id: string;
  source_sha256: string;
  source_byte_count: number;
  source_mime_type: "image/jpeg" | "image/png" | "image/webp";
  source_width: number;
  source_height: number;
  captured_at: string;
  alt_text: string;
  source: string;
  source_url: string | null;
  rights_basis: AssetUploadMetadataV1["rights_basis"];
  rights_status: "approved";
  usage_status: "approved";
  dlp_status: "passed";
  sanitization_status: "passed";
  perceptual_dedup_status: "unique" | "intentional-reuse";
}>;

function requireSourceUrl(value: unknown): string | null {
  if (value === null) return null;
  const sourceUrl = requireString(value, "asset upload metadata.source_url");
  let parsed: URL;
  try {
    parsed = new URL(sourceUrl);
  } catch {
    throw new TypeError("asset upload metadata.source_url must be a URL");
  }
  if (
    !["http:", "https:"].includes(parsed.protocol) ||
    parsed.username !== "" ||
    parsed.password !== "" ||
    parsed.hash !== ""
  ) {
    throw new TypeError(
      "asset upload metadata.source_url must be a public HTTP URL",
    );
  }
  return sourceUrl;
}

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

export function parseAssetUploadMetadata(raw: unknown): AssetUploadMetadataV2 {
  if (
    typeof raw !== "object" ||
    raw === null ||
    Array.isArray(raw) ||
    (raw as Record<string, unknown>).schema_version !== "asset-upload.v2"
  ) {
    throw new TypeError(
      `unsupported schema_version ${String(
        typeof raw === "object" && raw !== null
          ? (raw as Record<string, unknown>).schema_version
          : undefined,
      )}`,
    );
  }
  const asset = requireClosedRecord(raw, "asset upload metadata", [
    "schema_version",
    "packet_id",
    "asset_id",
    "source_sha256",
    "source_byte_count",
    "source_mime_type",
    "source_width",
    "source_height",
    "captured_at",
    "alt_text",
    "source",
    "source_url",
    "rights_basis",
    "rights_status",
    "usage_status",
    "dlp_status",
    "sanitization_status",
    "perceptual_dedup_status",
  ]);
  const byteCount = requireInteger(
    asset.source_byte_count,
    "asset upload metadata.source_byte_count",
    1,
  );
  if (byteCount > 12 * 1024 * 1024)
    throw new TypeError("asset exceeds 12 MiB limit");
  const width = requireInteger(
    asset.source_width,
    "asset upload metadata.source_width",
    1,
  );
  const height = requireInteger(
    asset.source_height,
    "asset upload metadata.source_height",
    1,
  );
  if (width > 8192 || height > 8192)
    throw new TypeError("asset dimension exceeds 8192 pixels");
  if (width * height > 40_000_000)
    throw new TypeError("asset decoded pixel count exceeds limit");
  return {
    schema_version: "asset-upload.v2",
    packet_id: requireString(
      asset.packet_id,
      "asset upload metadata.packet_id",
    ),
    asset_id: requireString(asset.asset_id, "asset upload metadata.asset_id"),
    source_sha256: requireSha256(
      asset.source_sha256,
      "asset upload metadata.source_sha256",
    ),
    source_byte_count: byteCount,
    source_mime_type: requireEnum(
      asset.source_mime_type,
      "asset upload metadata.source_mime_type",
      ["image/jpeg", "image/png", "image/webp"] as const,
    ),
    source_width: width,
    source_height: height,
    captured_at: requireTimestamp(
      asset.captured_at,
      "asset upload metadata.captured_at",
    ),
    alt_text: requireString(asset.alt_text, "asset upload metadata.alt_text"),
    source: requireString(asset.source, "asset upload metadata.source"),
    source_url: requireSourceUrl(asset.source_url),
    rights_basis: requireEnum(
      asset.rights_basis,
      "asset upload metadata.rights_basis",
      [
        "internal-owned",
        "licensed",
        "public-domain",
        "official-use",
        "generated",
      ] as const,
    ),
    rights_status: requireEnum(
      asset.rights_status,
      "asset upload metadata.rights_status",
      ["approved"] as const,
    ),
    usage_status: requireEnum(
      asset.usage_status,
      "asset upload metadata.usage_status",
      ["approved"] as const,
    ),
    dlp_status: requireEnum(
      asset.dlp_status,
      "asset upload metadata.dlp_status",
      ["passed"] as const,
    ),
    sanitization_status: requireEnum(
      asset.sanitization_status,
      "asset upload metadata.sanitization_status",
      ["passed"] as const,
    ),
    perceptual_dedup_status: requireEnum(
      asset.perceptual_dedup_status,
      "asset upload metadata.perceptual_dedup_status",
      ["unique", "intentional-reuse"] as const,
    ),
  };
}
