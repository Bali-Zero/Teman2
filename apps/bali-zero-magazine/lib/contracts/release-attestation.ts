import { decodeBase64Url } from "./audit-anchor.ts";

export type ReleaseAttestationBodyV1 = Readonly<{
  schema_version: "release-attestation.v1";
  attestation_id: string;
  story_id: string;
  story_version: number;
  evidence_bundle_hash: string;
  asset_set_hash: string;
  key_id: string;
  expires_at: string;
}>;

type ReleaseAttestationKey = Readonly<{
  key_id: string;
  public_key: string;
  not_before: string;
  not_after: string;
  status: "active" | "retained";
}>;

const SIGNATURE_DOMAIN = new TextEncoder().encode(
  "BZM-RELEASE-ATTESTATION-V1\0",
);
const IDENTIFIER = /^[A-Za-z0-9._~-]{1,128}$/;

function concatenate(left: Uint8Array, right: Uint8Array): Uint8Array {
  const value = new Uint8Array(left.byteLength + right.byteLength);
  value.set(left);
  value.set(right, left.byteLength);
  return value;
}

function ownedBytes(value: Uint8Array): Uint8Array<ArrayBuffer> {
  const copy = new Uint8Array(new ArrayBuffer(value.byteLength));
  copy.set(value);
  return copy;
}

export function canonicalizeReleaseAttestationBody(
  body: ReleaseAttestationBodyV1,
): Uint8Array {
  return new TextEncoder().encode(
    JSON.stringify({
      schema_version: body.schema_version,
      attestation_id: body.attestation_id,
      story_id: body.story_id,
      story_version: body.story_version,
      evidence_bundle_hash: body.evidence_bundle_hash,
      asset_set_hash: body.asset_set_hash,
      key_id: body.key_id,
      expires_at: body.expires_at,
    }),
  );
}

export function buildReleaseAttestationSignaturePreimage(
  canonicalBody: Uint8Array,
): Uint8Array {
  return concatenate(SIGNATURE_DOMAIN, canonicalBody);
}

function parseRegistry(
  raw: string | undefined,
): readonly ReleaseAttestationKey[] {
  let value: unknown;
  try {
    value = JSON.parse(raw ?? "");
  } catch {
    throw new TypeError("invalid release attestation registry");
  }
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new TypeError("invalid release attestation registry");
  }
  const record = value as Record<string, unknown>;
  if (
    Object.keys(record).sort().join(",") !== "keys,registry_version" ||
    typeof record.registry_version !== "string" ||
    !Array.isArray(record.keys) ||
    record.keys.length === 0 ||
    record.keys.length > 16
  ) {
    throw new TypeError("invalid release attestation registry");
  }
  const keys = record.keys.map((item): ReleaseAttestationKey => {
    if (typeof item !== "object" || item === null || Array.isArray(item)) {
      throw new TypeError("invalid release attestation registry");
    }
    const key = item as Record<string, unknown>;
    if (
      Object.keys(key).sort().join(",") !==
        "key_id,not_after,not_before,public_key,status" ||
      typeof key.key_id !== "string" ||
      !IDENTIFIER.test(key.key_id) ||
      typeof key.public_key !== "string" ||
      typeof key.not_before !== "string" ||
      typeof key.not_after !== "string" ||
      (key.status !== "active" && key.status !== "retained") ||
      !Number.isFinite(Date.parse(key.not_before)) ||
      !Number.isFinite(Date.parse(key.not_after)) ||
      Date.parse(key.not_after) <= Date.parse(key.not_before)
    ) {
      throw new TypeError("invalid release attestation registry");
    }
    decodeBase64Url(key.public_key, 32);
    return key as ReleaseAttestationKey;
  });
  if (new Set(keys.map((key) => key.key_id)).size !== keys.length) {
    throw new TypeError("invalid release attestation registry");
  }
  return keys;
}

export async function verifyReleaseAttestation(
  body: ReleaseAttestationBodyV1,
  signatureText: string,
  registryRaw: string | undefined,
  now: string,
): Promise<void> {
  if (
    body.schema_version !== "release-attestation.v1" ||
    Date.parse(body.expires_at) <= Date.parse(now)
  ) {
    throw new TypeError("invalid release attestation");
  }
  const key = parseRegistry(registryRaw).find(
    (candidate) => candidate.key_id === body.key_id,
  );
  if (
    key === undefined ||
    Date.parse(now) < Date.parse(key.not_before) ||
    Date.parse(now) >= Date.parse(key.not_after)
  ) {
    throw new TypeError("invalid release attestation key");
  }
  const publicKey = await crypto.subtle.importKey(
    "raw",
    new Uint8Array(decodeBase64Url(key.public_key, 32)),
    { name: "Ed25519" },
    false,
    ["verify"],
  );
  const valid = await crypto.subtle.verify(
    "Ed25519",
    publicKey,
    new Uint8Array(decodeBase64Url(signatureText, 64)),
    ownedBytes(
      buildReleaseAttestationSignaturePreimage(
        canonicalizeReleaseAttestationBody(body),
      ),
    ),
  );
  if (!valid) throw new TypeError("invalid release attestation signature");
}
