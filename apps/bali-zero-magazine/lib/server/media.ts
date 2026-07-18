// Node's type-stripping test runner executes the TypeScript source directly.
import type { AssetUploadMetadataV1 } from "../contracts/collector.ts";
import type { D1DatabaseLike } from "./publication-repository.ts";
// @ts-expect-error TypeScript requires allowImportingTsExtensions for this runtime-safe import.
import { sha256Hex } from "./security.ts";

export const MAX_MEDIA_BYTES = 12 * 1024 * 1024;
export const MAX_MEDIA_DIMENSION = 8192;
export const MAX_DECODED_PIXELS = 40_000_000;

type R2Metadata = Readonly<{
  contentType?: string;
}>;

export interface R2ObjectLike {
  readonly key: string;
  readonly size: number;
  readonly httpMetadata?: R2Metadata;
  readonly customMetadata?: Readonly<Record<string, string>>;
  arrayBuffer(): Promise<ArrayBuffer>;
}

export interface R2BucketLike {
  put(
    key: string,
    value: Uint8Array | ArrayBuffer,
    options?: Readonly<{
      httpMetadata?: R2Metadata;
      customMetadata?: Readonly<Record<string, string>>;
    }>,
  ): Promise<unknown>;
  get(key: string): Promise<R2ObjectLike | null>;
  head?(key: string): Promise<Omit<R2ObjectLike, "arrayBuffer"> | null>;
  delete?(key: string): Promise<void>;
}

export type ValidatedImage = Readonly<{
  mimeType: AssetUploadMetadataV1["mime_type"];
  width: number;
  height: number;
  extension: "jpg" | "png" | "webp";
}>;

export type ResolvedMedia = Readonly<{
  bytes: Uint8Array;
  mimeType: AssetUploadMetadataV1["mime_type"];
}>;

const PNG_SIGNATURE = [137, 80, 78, 71, 13, 10, 26, 10] as const;
const MIME_EXTENSION = {
  "image/jpeg": "jpg",
  "image/png": "png",
  "image/webp": "webp",
} as const;
const SHA256 = /^[a-f0-9]{64}$/;

function equalsAt(
  bytes: Uint8Array,
  offset: number,
  expected: readonly number[],
): boolean {
  return expected.every((value, index) => bytes[offset + index] === value);
}

function ascii(bytes: Uint8Array, start: number, length: number): string {
  return String.fromCharCode(...bytes.subarray(start, start + length));
}

function u16be(bytes: Uint8Array, offset: number): number {
  return bytes[offset] * 256 + bytes[offset + 1];
}

function u32be(bytes: Uint8Array, offset: number): number {
  return (
    bytes[offset] * 0x1000000 +
    bytes[offset + 1] * 0x10000 +
    bytes[offset + 2] * 0x100 +
    bytes[offset + 3]
  );
}

function u32le(bytes: Uint8Array, offset: number): number {
  return (
    (bytes[offset] +
      bytes[offset + 1] * 0x100 +
      bytes[offset + 2] * 0x10000 +
      bytes[offset + 3] * 0x1000000) >>>
    0
  );
}

function crc32(bytes: Uint8Array): number {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function rejectActiveText(bytes: Uint8Array): void {
  const sample = new TextDecoder("utf-8", { fatal: false })
    .decode(bytes.subarray(0, Math.min(bytes.length, 1024)))
    .replaceAll("\u0000", "")
    .trimStart()
    .toLowerCase();
  if (
    sample.startsWith("<") ||
    sample.includes("<script") ||
    sample.includes("<?xml") ||
    sample.includes("<svg") ||
    sample.includes("<!doctype html") ||
    sample.includes("<html")
  ) {
    throw new TypeError("active document media is forbidden");
  }
}

function parsePng(
  bytes: Uint8Array,
): Readonly<{ width: number; height: number }> {
  if (!equalsAt(bytes, 0, PNG_SIGNATURE))
    throw new TypeError("invalid PNG magic");
  let offset: number = PNG_SIGNATURE.length;
  let width = 0;
  let height = 0;
  let sawIdat = false;
  let sawIend = false;
  let chunkIndex = 0;
  while (offset < bytes.length) {
    if (offset + 12 > bytes.length) throw new TypeError("truncated PNG chunk");
    const length = u32be(bytes, offset);
    const type = ascii(bytes, offset + 4, 4);
    const dataStart = offset + 8;
    const dataEnd = dataStart + length;
    if (dataEnd + 4 > bytes.length) throw new TypeError("truncated PNG data");
    const expectedCrc = u32be(bytes, dataEnd);
    if (crc32(bytes.subarray(offset + 4, dataEnd)) !== expectedCrc) {
      throw new TypeError("invalid PNG CRC");
    }
    if (chunkIndex === 0 && type !== "IHDR")
      throw new TypeError("PNG IHDR must be first");
    if (type === "IHDR") {
      if (chunkIndex !== 0 || length !== 13)
        throw new TypeError("invalid PNG IHDR");
      width = u32be(bytes, dataStart);
      height = u32be(bytes, dataStart + 4);
    } else if (type === "IDAT") {
      sawIdat = true;
    } else if (type === "acTL" || type === "fcTL" || type === "fdAT") {
      throw new TypeError("animated PNG is forbidden");
    } else if (type === "IEND") {
      if (length !== 0 || dataEnd + 4 !== bytes.length) {
        throw new TypeError("invalid PNG terminator");
      }
      sawIend = true;
      offset = bytes.length;
      break;
    }
    offset = dataEnd + 4;
    chunkIndex += 1;
  }
  if (!sawIdat || !sawIend || width === 0 || height === 0) {
    throw new TypeError("incomplete PNG image");
  }
  return { width, height };
}

const JPEG_SOF_MARKERS = new Set([
  0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf,
]);

function parseJpeg(
  bytes: Uint8Array,
): Readonly<{ width: number; height: number }> {
  if (!equalsAt(bytes, 0, [0xff, 0xd8]))
    throw new TypeError("invalid JPEG magic");
  if (!equalsAt(bytes, bytes.length - 2, [0xff, 0xd9])) {
    throw new TypeError("invalid JPEG terminator");
  }
  let offset = 2;
  let width = 0;
  let height = 0;
  while (offset < bytes.length - 2) {
    if (bytes[offset] !== 0xff) throw new TypeError("invalid JPEG marker");
    while (bytes[offset] === 0xff) offset += 1;
    const marker = bytes[offset++];
    if (marker === 0xd9) break;
    if (marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) continue;
    if (offset + 2 > bytes.length)
      throw new TypeError("truncated JPEG segment");
    const length = u16be(bytes, offset);
    if (length < 2 || offset + length > bytes.length) {
      throw new TypeError("invalid JPEG segment length");
    }
    if (JPEG_SOF_MARKERS.has(marker)) {
      if (length < 7) throw new TypeError("invalid JPEG frame");
      height = u16be(bytes, offset + 3);
      width = u16be(bytes, offset + 5);
    }
    if (marker === 0xda) {
      offset += length;
      while (offset < bytes.length - 1) {
        if (bytes[offset] !== 0xff) {
          offset += 1;
          continue;
        }
        const next = bytes[offset + 1];
        if (next === 0x00 || (next >= 0xd0 && next <= 0xd7)) {
          offset += 2;
          continue;
        }
        break;
      }
    } else {
      offset += length;
    }
  }
  if (width === 0 || height === 0) throw new TypeError("missing JPEG frame");
  return { width, height };
}

function parseWebp(
  bytes: Uint8Array,
): Readonly<{ width: number; height: number }> {
  if (ascii(bytes, 0, 4) !== "RIFF" || ascii(bytes, 8, 4) !== "WEBP") {
    throw new TypeError("invalid WebP magic");
  }
  if (bytes.length < 20 || u32le(bytes, 4) + 8 !== bytes.length) {
    throw new TypeError("invalid WebP container length");
  }
  let offset = 12;
  let width = 0;
  let height = 0;
  let sawImage = false;
  while (offset < bytes.length) {
    if (offset + 8 > bytes.length) throw new TypeError("truncated WebP chunk");
    const type = ascii(bytes, offset, 4);
    const length = u32le(bytes, offset + 4);
    const data = offset + 8;
    const end = data + length;
    if (end > bytes.length) throw new TypeError("truncated WebP data");
    if (type === "ANIM" || type === "ANMF")
      throw new TypeError("animated WebP is forbidden");
    if (type === "VP8X") {
      if (length !== 10) throw new TypeError("invalid WebP extended header");
      if ((bytes[data] & 0x02) !== 0)
        throw new TypeError("animated WebP is forbidden");
      width =
        1 + bytes[data + 4] + bytes[data + 5] * 256 + bytes[data + 6] * 65536;
      height =
        1 + bytes[data + 7] + bytes[data + 8] * 256 + bytes[data + 9] * 65536;
    } else if (type === "VP8L") {
      if (length < 5 || bytes[data] !== 0x2f)
        throw new TypeError("invalid lossless WebP");
      const packed = u32le(bytes, data + 1);
      width = (packed & 0x3fff) + 1;
      height = ((packed >>> 14) & 0x3fff) + 1;
      sawImage = true;
    } else if (type === "VP8 ") {
      if (length < 10 || !equalsAt(bytes, data + 3, [0x9d, 0x01, 0x2a])) {
        throw new TypeError("invalid lossy WebP");
      }
      width =
        u16be(Uint8Array.of(bytes[data + 7], bytes[data + 6]), 0) & 0x3fff;
      height =
        u16be(Uint8Array.of(bytes[data + 9], bytes[data + 8]), 0) & 0x3fff;
      sawImage = true;
    }
    offset = end + (length & 1);
  }
  if (offset !== bytes.length || !sawImage || width === 0 || height === 0) {
    throw new TypeError("incomplete WebP image");
  }
  return { width, height };
}

function requireSafeDimensions(width: number, height: number): void {
  if (
    !Number.isSafeInteger(width) ||
    !Number.isSafeInteger(height) ||
    width < 1 ||
    height < 1 ||
    width > MAX_MEDIA_DIMENSION ||
    height > MAX_MEDIA_DIMENSION ||
    width * height > MAX_DECODED_PIXELS
  ) {
    throw new TypeError("unsafe decoded image dimensions");
  }
}

export async function validateImageAsset(
  bytes: Uint8Array,
  contentType: string,
  metadata: AssetUploadMetadataV1,
): Promise<ValidatedImage> {
  if (bytes.byteLength < 12 || bytes.byteLength > MAX_MEDIA_BYTES) {
    throw new TypeError("asset byte length exceeds limit");
  }
  if (contentType !== metadata.mime_type)
    throw new TypeError("asset MIME mismatch");
  rejectActiveText(bytes);
  let dimensions: Readonly<{ width: number; height: number }>;
  if (contentType === "image/png") dimensions = parsePng(bytes);
  else if (contentType === "image/jpeg") dimensions = parseJpeg(bytes);
  else if (contentType === "image/webp") dimensions = parseWebp(bytes);
  else throw new TypeError("unsupported asset MIME type");
  requireSafeDimensions(dimensions.width, dimensions.height);
  const digest = await sha256Hex(bytes);
  if (
    digest !== metadata.sha256 ||
    bytes.byteLength !== metadata.byte_count ||
    dimensions.width !== metadata.width ||
    dimensions.height !== metadata.height
  ) {
    throw new TypeError("asset digest or metadata mismatch");
  }
  return {
    mimeType: metadata.mime_type,
    width: dimensions.width,
    height: dimensions.height,
    extension: MIME_EXTENSION[metadata.mime_type],
  };
}

function expectedMetadata(
  metadata: AssetUploadMetadataV1,
): Readonly<Record<string, string>> {
  return {
    sha256: metadata.sha256,
    byteCount: String(metadata.byte_count),
    width: String(metadata.width),
    height: String(metadata.height),
  };
}

async function verifiedObjectBytes(
  bucket: R2BucketLike,
  key: string,
  metadata: AssetUploadMetadataV1,
): Promise<Uint8Array> {
  const object = await bucket.get(key);
  if (
    object === null ||
    object.key !== key ||
    object.size !== metadata.byte_count ||
    object.httpMetadata?.contentType !== metadata.mime_type
  ) {
    throw new Error("asset storage verification conflict");
  }
  const expected = expectedMetadata(metadata);
  if (
    Object.entries(expected).some(
      ([name, value]) => object.customMetadata?.[name] !== value,
    )
  ) {
    throw new Error("asset storage verification conflict");
  }
  const bytes = new Uint8Array(await object.arrayBuffer());
  if (
    bytes.byteLength !== metadata.byte_count ||
    (await sha256Hex(bytes)) !== metadata.sha256
  ) {
    throw new Error("asset storage verification conflict");
  }
  return bytes;
}

export async function storeVerifiedAsset(
  bucket: R2BucketLike,
  bytes: Uint8Array,
  metadata: AssetUploadMetadataV1,
  image: ValidatedImage,
): Promise<string> {
  const key = `assets/sha256/${metadata.sha256}.${image.extension}`;
  await bucket.put(key, bytes, {
    httpMetadata: { contentType: metadata.mime_type },
    customMetadata: expectedMetadata(metadata),
  });
  try {
    await verifiedObjectBytes(bucket, key, metadata);
  } catch (error) {
    await bucket.delete?.(key);
    throw error;
  }
  return key;
}

type EligibleAssetRow = Readonly<{
  asset_id: string;
  packet_id: string;
  sha256: string;
  r2_key: string;
  mime_type: AssetUploadMetadataV1["mime_type"];
  byte_count: number;
  width: number;
  height: number;
  captured_at: string;
  rights_status: "approved";
}>;

export async function resolvePublishedMedia(
  db: D1DatabaseLike,
  bucket: R2BucketLike,
  digest: string,
): Promise<ResolvedMedia | null> {
  if (!SHA256.test(digest)) return null;
  const row = await db
    .prepare(
      `SELECT a.asset_id, a.packet_id, a.sha256, a.r2_key, a.mime_type,
              a.byte_count, a.width, a.height, a.captured_at, a.rights_status
       FROM assets a
       JOIN story_asset_references sar ON sar.asset_sha256 = a.sha256
       JOIN story_versions sv
         ON sv.packet_id = sar.packet_id AND sv.story_id = sar.story_id
        AND sv.version = sar.version
       JOIN stories s ON s.story_id = sv.story_id AND s.current_version = sv.version
       WHERE a.sha256 = ?
         AND sar.publication_state = 'published'
         AND sv.publication_state = 'published'
         AND COALESCE((
           SELECT ase.status FROM asset_status_events ase
           WHERE ase.asset_id = a.asset_id
           ORDER BY ase.status_seq DESC LIMIT 1
         ), a.status) = 'verified'
         AND COALESCE((
           SELECT ase.rights_status FROM asset_status_events ase
           WHERE ase.asset_id = a.asset_id
           ORDER BY ase.status_seq DESC LIMIT 1
         ), a.rights_status) = 'approved'
         AND NOT EXISTS (
           SELECT 1 FROM story_visibility_events visibility
           WHERE visibility.story_id = sv.story_id
             AND visibility.visibility_seq = (
               SELECT max(latest.visibility_seq)
               FROM story_visibility_events latest
               WHERE latest.story_id = sv.story_id
             )
             AND visibility.desired_quarantined = 1
         )
       LIMIT 1`,
    )
    .bind(digest)
    .first<EligibleAssetRow>();
  if (row === null || row.sha256 !== digest) return null;
  try {
    const bytes = await verifiedObjectBytes(bucket, row.r2_key, {
      schema_version: "asset-upload.v1",
      packet_id: row.packet_id,
      asset_id: row.asset_id,
      sha256: row.sha256,
      byte_count: row.byte_count,
      mime_type: row.mime_type,
      width: row.width,
      height: row.height,
      captured_at: row.captured_at,
      rights_status: row.rights_status,
    });
    return { bytes, mimeType: row.mime_type };
  } catch {
    return null;
  }
}
