import { sha256Hex } from "./security.ts";

/** Read-only part of R2. Shared by existing media delivery and local read proof. */
export interface ReadonlyMediaBucket {
  get(key: string): Promise<Readonly<{
    key: string; size: number;
    httpMetadata?: Readonly<{ contentType?: string }>;
    customMetadata?: Readonly<Record<string, string>>;
    arrayBuffer(): Promise<ArrayBuffer>;
  }> | null>;
}

export type StoredAssetDescriptor = Readonly<{
  sha256: string;
  byteCount: number;
  mimeType: "image/png";
  width: number;
  height: number;
}>;

export function expectedMetadata(asset: StoredAssetDescriptor): Readonly<Record<string, string>> {
  return {
    sha256: asset.sha256,
    mimeType: asset.mimeType,
    byteCount: String(asset.byteCount),
    width: String(asset.width),
    height: String(asset.height),
  };
}

// Unchanged storage checks extracted from media.ts. Canonicalization remains
// the existing ingest responsibility; this function does not encode images.
export async function verifiedObjectBytes(
  bucket: ReadonlyMediaBucket,
  key: string,
  asset: StoredAssetDescriptor,
): Promise<Uint8Array> {
  const object = await bucket.get(key);
  if (object === null || object.key !== key || object.size !== asset.byteCount ||
    object.httpMetadata?.contentType !== asset.mimeType) {
    throw new Error("asset storage verification conflict");
  }
  const expected = expectedMetadata(asset);
  if (Object.keys(object.customMetadata ?? {}).length !== Object.keys(expected).length ||
    Object.entries(expected).some(([name, value]) => object.customMetadata?.[name] !== value)) {
    throw new Error("asset storage verification conflict");
  }
  const bytes = new Uint8Array(await object.arrayBuffer());
  if (bytes.byteLength !== asset.byteCount || (await sha256Hex(bytes)) !== asset.sha256) {
    throw new Error("asset storage verification conflict");
  }
  return bytes;
}
