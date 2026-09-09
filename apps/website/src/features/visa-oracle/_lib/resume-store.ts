const RESUME_SCHEMA_VERSION = 1 as const;

export const VISA_ORACLE_RESUME_KEY = "visa-oracle:v2:resume:v1";
export const VISA_ORACLE_RESUME_TTL_MS = 2 * 60 * 60 * 1_000;

export interface ResumeEnvelope<TSnapshot> {
  schemaVersion: typeof RESUME_SCHEMA_VERSION;
  savedAtIso: string;
  expiresAtIso: string;
  snapshot: TSnapshot;
}

export interface LoadedInterviewResume<TSnapshot> {
  snapshot: TSnapshot;
  expiresAtIso: string;
}

export interface ResumeStoreOptions {
  storage?: Pick<Storage, "getItem" | "setItem" | "removeItem">;
  now?: Date;
  ttlMs?: number;
}

function browserStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

function resolveStorage(
  storage: ResumeStoreOptions["storage"],
): Pick<Storage, "getItem" | "setItem" | "removeItem"> | null {
  return storage ?? browserStorage();
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseEnvelope(value: unknown): ResumeEnvelope<unknown> | null {
  if (!isRecord(value)) return null;
  if (value.schemaVersion !== RESUME_SCHEMA_VERSION) return null;
  if (typeof value.savedAtIso !== "string") return null;
  if (typeof value.expiresAtIso !== "string") return null;
  if (!Object.prototype.hasOwnProperty.call(value, "snapshot")) return null;

  const savedAt = Date.parse(value.savedAtIso);
  const expiresAt = Date.parse(value.expiresAtIso);
  if (!Number.isFinite(savedAt) || !Number.isFinite(expiresAt)) return null;
  if (expiresAt <= savedAt) return null;

  return value as unknown as ResumeEnvelope<unknown>;
}

/**
 * Store only the already-minimized interview snapshot supplied by the flow.
 * The default is sessionStorage: cross-session persistence requires a separate,
 * explicit consented path and must never happen as an incidental default.
 */
export function saveInterviewResume<TSnapshot>(
  snapshot: TSnapshot,
  options: ResumeStoreOptions = {},
): boolean {
  const storage = resolveStorage(options.storage);
  if (!storage) return false;

  const now = options.now ?? new Date();
  const ttlMs = options.ttlMs ?? VISA_ORACLE_RESUME_TTL_MS;
  if (!Number.isFinite(ttlMs) || ttlMs <= 0) return false;

  const envelope: ResumeEnvelope<TSnapshot> = {
    schemaVersion: RESUME_SCHEMA_VERSION,
    savedAtIso: now.toISOString(),
    expiresAtIso: new Date(now.getTime() + ttlMs).toISOString(),
    snapshot,
  };

  try {
    storage.setItem(VISA_ORACLE_RESUME_KEY, JSON.stringify(envelope));
    return true;
  } catch {
    return false;
  }
}

/**
 * Load only a current envelope whose snapshot passes the flow-owned runtime
 * validator. Invalid, stale, or incompatible data is deleted fail-closed.
 */
export function loadInterviewResumeWithExpiry<TSnapshot>(
  validateSnapshot: (value: unknown) => TSnapshot | null,
  options: ResumeStoreOptions = {},
): LoadedInterviewResume<TSnapshot> | null {
  const storage = resolveStorage(options.storage);
  if (!storage) return null;

  try {
    const raw = storage.getItem(VISA_ORACLE_RESUME_KEY);
    if (raw === null) return null;

    const envelope = parseEnvelope(JSON.parse(raw));
    const now = options.now ?? new Date();
    if (
      envelope === null ||
      Date.parse(envelope.expiresAtIso) <= now.getTime()
    ) {
      storage.removeItem(VISA_ORACLE_RESUME_KEY);
      return null;
    }

    const snapshot = validateSnapshot(envelope.snapshot);
    if (snapshot === null) {
      storage.removeItem(VISA_ORACLE_RESUME_KEY);
      return null;
    }
    return { snapshot, expiresAtIso: envelope.expiresAtIso };
  } catch {
    try {
      storage.removeItem(VISA_ORACLE_RESUME_KEY);
    } catch {
      // Storage may be disabled between the read and cleanup attempt.
    }
    return null;
  }
}

export function loadInterviewResume<TSnapshot>(
  validateSnapshot: (value: unknown) => TSnapshot | null,
  options: ResumeStoreOptions = {},
): TSnapshot | null {
  return (
    loadInterviewResumeWithExpiry(validateSnapshot, options)?.snapshot ?? null
  );
}

export interface ResumeCleanupOptions extends ResumeStoreOptions {
  onExpired?: () => void;
}

/**
 * Enforce the persisted expiry while the document stays mounted. Loading is
 * still expiry-checked independently, so background timer throttling cannot
 * revive stale data on the next read.
 */
export function scheduleInterviewResumeCleanup(
  expiresAtIso: string,
  options: ResumeCleanupOptions = {},
): () => void {
  const expiresAt = Date.parse(expiresAtIso);
  const now = options.now?.getTime() ?? Date.now();
  const expire = () => {
    clearInterviewResume(options);
    options.onExpired?.();
  };
  if (!Number.isFinite(expiresAt) || expiresAt <= now) {
    expire();
    return () => undefined;
  }

  const timer = setTimeout(expire, expiresAt - now);
  return () => clearTimeout(timer);
}

export function clearInterviewResume(options: ResumeStoreOptions = {}): void {
  const storage = resolveStorage(options.storage);
  if (!storage) return;
  try {
    storage.removeItem(VISA_ORACLE_RESUME_KEY);
  } catch {
    // Best-effort cleanup when browser storage is unavailable.
  }
}
