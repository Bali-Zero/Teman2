const IDENTITY_SCHEMA_VERSION = 1 as const;
const IDENTITY_TTL_MS = 2 * 60 * 60 * 1_000;
const MAX_IDENTITIES = 16;
const SHA256_HEX = /^[a-f0-9]{64}$/;
const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export const VISA_ORACLE_IDENTITY_KEY =
  "visa-oracle:v2:evaluation-identities:v1";

export interface EvaluationIdentity {
  assessmentId: string;
  idempotencyKey: string;
  createdAtIso: string;
}

export type EvaluationIdentityStorage = Pick<
  Storage,
  "getItem" | "setItem" | "removeItem"
>;

interface IdentityEnvelope {
  schemaVersion: typeof IDENTITY_SCHEMA_VERSION;
  expiresAtIso: string;
  entries: Record<string, EvaluationIdentity>;
}

export interface EvaluationIdentityOptions {
  attempt: number;
  evaluationHash: string;
  storage?: EvaluationIdentityStorage | null;
  now?: Date;
  createId?: () => string;
}

export function browserEvaluationIdentityStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export function createMemoryEvaluationIdentityStorage(): EvaluationIdentityStorage {
  const entries = new Map<string, string>();
  return {
    getItem: (key) => entries.get(key) ?? null,
    setItem: (key, value) => {
      entries.set(key, value);
    },
    removeItem: (key) => {
      entries.delete(key);
    },
  };
}

function entryKey(attempt: number, evaluationHash: string): string {
  return `${attempt}:${evaluationHash}`;
}

function validIdentity(value: unknown): value is EvaluationIdentity {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }
  const identity = value as Partial<EvaluationIdentity>;
  return (
    typeof identity.assessmentId === "string" &&
    UUID.test(identity.assessmentId) &&
    typeof identity.idempotencyKey === "string" &&
    UUID.test(identity.idempotencyKey) &&
    typeof identity.createdAtIso === "string" &&
    Number.isFinite(Date.parse(identity.createdAtIso))
  );
}

function readEnvelope(
  storage: Pick<Storage, "getItem" | "setItem" | "removeItem">,
  now: Date,
): IdentityEnvelope | null {
  try {
    const raw = storage.getItem(VISA_ORACLE_IDENTITY_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as unknown;
    if (
      typeof parsed !== "object" ||
      parsed === null ||
      Array.isArray(parsed)
    ) {
      storage.removeItem(VISA_ORACLE_IDENTITY_KEY);
      return null;
    }
    const envelope = parsed as Partial<IdentityEnvelope>;
    if (
      envelope.schemaVersion !== IDENTITY_SCHEMA_VERSION ||
      typeof envelope.expiresAtIso !== "string" ||
      Date.parse(envelope.expiresAtIso) <= now.getTime() ||
      typeof envelope.entries !== "object" ||
      envelope.entries === null ||
      Array.isArray(envelope.entries) ||
      Object.keys(envelope.entries).length > MAX_IDENTITIES ||
      !Object.values(envelope.entries).every(validIdentity)
    ) {
      storage.removeItem(VISA_ORACLE_IDENTITY_KEY);
      return null;
    }
    const currentEntries = Object.fromEntries(
      Object.entries(envelope.entries).filter(([, identity]) => {
        const createdAt = Date.parse(identity.createdAtIso);
        return (
          createdAt <= now.getTime() &&
          createdAt + IDENTITY_TTL_MS > now.getTime()
        );
      }),
    );
    if (Object.keys(currentEntries).length === 0) {
      storage.removeItem(VISA_ORACLE_IDENTITY_KEY);
      return null;
    }
    return { ...(envelope as IdentityEnvelope), entries: currentEntries };
  } catch {
    try {
      storage.removeItem(VISA_ORACLE_IDENTITY_KEY);
    } catch {
      // Browser storage can become unavailable between operations.
    }
    return null;
  }
}

function freshIdentity(now: Date, createId: () => string): EvaluationIdentity {
  const assessmentId = createId();
  const idempotencyKey = createId();
  if (!UUID.test(assessmentId) || !UUID.test(idempotencyKey)) {
    throw new Error("Evaluation identity generator must return UUID values");
  }
  return { assessmentId, idempotencyKey, createdAtIso: now.toISOString() };
}

/**
 * Reuses one request identity for the same attempt + non-reversible hash of
 * the complete semantic request (facts, review flags and request category),
 * including after a reload when the caller explicitly provides sessionStorage.
 * No response body or raw interview fact is cached. Storage is opt-in so a
 * caller cannot persist a fact-derived lookup key without an explicit policy.
 */
export function getOrCreateEvaluationIdentity(
  options: EvaluationIdentityOptions,
): EvaluationIdentity {
  if (
    !Number.isSafeInteger(options.attempt) ||
    options.attempt < 0 ||
    !SHA256_HEX.test(options.evaluationHash)
  ) {
    throw new Error("Invalid evaluation identity key");
  }

  const now = options.now ?? new Date();
  const createId = options.createId ?? (() => crypto.randomUUID());
  const storage = options.storage ?? null;
  if (!storage) return freshIdentity(now, createId);

  const key = entryKey(options.attempt, options.evaluationHash);
  const envelope = readEnvelope(storage, now);
  const existing = envelope?.entries[key];
  if (existing) return existing;

  const identity = freshIdentity(now, createId);
  const entries = { ...(envelope?.entries ?? {}), [key]: identity };
  const orderedEntries = Object.fromEntries(
    Object.entries(entries)
      .sort(([, left], [, right]) =>
        left.createdAtIso.localeCompare(right.createdAtIso),
      )
      .slice(-MAX_IDENTITIES),
  );
  const nextEnvelope: IdentityEnvelope = {
    schemaVersion: IDENTITY_SCHEMA_VERSION,
    expiresAtIso: new Date(now.getTime() + IDENTITY_TTL_MS).toISOString(),
    entries: orderedEntries,
  };
  try {
    storage.setItem(VISA_ORACLE_IDENTITY_KEY, JSON.stringify(nextEnvelope));
  } catch {
    // The in-memory caller still reuses the returned identity for this mount.
  }
  return identity;
}

export function clearEvaluationIdentities(
  storage?: Pick<Storage, "removeItem">,
): void {
  const target = storage ?? browserEvaluationIdentityStorage();
  try {
    target?.removeItem(VISA_ORACLE_IDENTITY_KEY);
  } catch {
    // Best-effort privacy cleanup.
  }
}
