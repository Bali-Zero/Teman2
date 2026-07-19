// Node's type-stripping test runner executes the TypeScript source directly.
import { verifyMachineRequest } from "./hmac.ts";
import type {
  MachineHmacKey,
  MachineNonceStore,
  VerifiedMachineRequest,
} from "./hmac.ts";
import { getMagazineBindings } from "./runtime-bindings.ts";
import { privateNoStoreHeaders } from "./security.ts";

function requireAdmissionContext(headers: Headers): void {
  const value = headers.get("oai-sites-authorization");
  if (
    value === null ||
    !/^Bearer [\x21-\x7e]+$/.test(value) ||
    value.length > 4096
  ) {
    throw new TypeError("dispatcher admission is required");
  }
}

function parseMachineKey(
  raw: string | undefined,
  label: string,
): MachineHmacKey {
  if (raw === undefined)
    throw new TypeError(`${label} machine key is required`);
  const parsed: unknown = JSON.parse(raw);
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    throw new TypeError(`invalid ${label} machine key`);
  }
  const record = parsed as Record<string, unknown>;
  const keys = Object.keys(record).sort();
  if (keys.join(",") !== "id,notAfter,notBefore,secret") {
    throw new TypeError(`invalid ${label} machine key`);
  }
  return {
    id: typeof record.id === "string" ? record.id : "",
    secret: typeof record.secret === "string" ? record.secret : "",
    notBefore: typeof record.notBefore === "number" ? record.notBefore : -1,
    notAfter: typeof record.notAfter === "number" ? record.notAfter : -1,
  };
}

class D1NonceStore implements MachineNonceStore {
  private readonly db: NonNullable<
    ReturnType<typeof getMagazineBindings>["DB"]
  >;

  constructor(db: NonNullable<ReturnType<typeof getMagazineBindings>["DB"]>) {
    this.db = db;
  }

  async insertUnique(
    keyId: string,
    nonce: string,
    expiresAt: number,
    bodySha256 = "",
  ): Promise<boolean> {
    const results = await this.db.batch([
      this.db
        .prepare("DELETE FROM ingest_nonces WHERE expires_at <= ?")
        .bind(new Date().toISOString()),
      this.db
        .prepare(
          `INSERT OR IGNORE INTO ingest_nonces(
             key_id, nonce, body_hash, expires_at
           ) VALUES (?, ?, ?, ?)`,
        )
        .bind(keyId, nonce, bodySha256, new Date(expiresAt).toISOString()),
    ]);
    return (results[1]?.meta?.changes ?? 0) === 1;
  }
}

export async function authenticateMachineRequest(
  request: Request,
  options: Readonly<{ signedHeaderNames?: readonly string[] }> = {},
): Promise<VerifiedMachineRequest> {
  requireAdmissionContext(request.headers);
  const bindings = getMagazineBindings();
  if (bindings.DB === undefined)
    throw new TypeError("database binding is required");
  const nextKey =
    bindings.MACHINE_HMAC_NEXT_KEY_JSON === undefined
      ? undefined
      : parseMachineKey(bindings.MACHINE_HMAC_NEXT_KEY_JSON, "next");
  return verifyMachineRequest(
    request,
    {
      audience: bindings.MACHINE_HMAC_AUDIENCE ?? "",
      currentKey: parseMachineKey(
        bindings.MACHINE_HMAC_CURRENT_KEY_JSON,
        "current",
      ),
      nextKey,
      maxBodyBytes: 13 * 1024 * 1024,
      nonceStore: new D1NonceStore(bindings.DB),
    },
    options,
  );
}

export function parseJsonBody(body: Uint8Array): unknown {
  const text = new TextDecoder("utf-8", { fatal: true }).decode(body);
  return JSON.parse(text) as unknown;
}

export function machineResult(status: "created" | "replay"): Response {
  return Response.json(
    { ok: true, status },
    {
      status: status === "created" ? 201 : 200,
      headers: privateNoStoreHeaders(),
    },
  );
}

export function machineAssetResult(
  status: "created" | "replay",
  asset: Readonly<{
    assetId: string;
    sourceSha256: string;
    canonicalSha256: string;
    canonicalByteCount: number;
    width: number;
    height: number;
  }>,
): Response {
  return Response.json(
    {
      ok: true,
      status,
      asset_id: asset.assetId,
      source_sha256: asset.sourceSha256,
      canonical_sha256: asset.canonicalSha256,
      canonical_mime_type: "image/png",
      canonical_byte_count: asset.canonicalByteCount,
      width: asset.width,
      height: asset.height,
    },
    {
      status: status === "created" ? 201 : 200,
      headers: privateNoStoreHeaders(),
    },
  );
}

export function machineFailure(status: 400 | 401 | 409 | 413): Response {
  const error =
    status === 401
      ? "unauthorized"
      : status === 409
        ? "conflict"
        : status === 413
          ? "payload_too_large"
          : "invalid_request";
  return Response.json(
    { ok: false, error },
    { status, headers: privateNoStoreHeaders() },
  );
}

export function machinePromotionBlocked(
  operation: "edition.publish" | "breaking.publish",
  packetId: string,
): Response {
  return Response.json(
    {
      ok: false,
      error: "promotion_blocked",
      operation,
      packet_id: packetId,
    },
    { status: 409, headers: privateNoStoreHeaders() },
  );
}
