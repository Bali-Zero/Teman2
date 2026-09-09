import { VISA_ORACLE_RESUME_TTL_MS } from "./resume-store";

const CONSENT_SCHEMA_VERSION = 3 as const;
const CONSENT_POLICY_VERSION = "visa-oracle-whatsapp-v3" as const;
const RECEIPT_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const PUBLIC_DECISION_ID_PATTERN = /^[a-z0-9]{16,20}$/;
const OUTCOME_STATES = new Set([
  "SUPPORTED_CANDIDATES",
  "NEEDS_INPUT",
  "HUMAN_REVIEW_REQUIRED",
  "NO_SUPPORTED_PATH",
  "TEMPORARILY_UNAVAILABLE",
]);

// Keep the storage key stable so loading prunes prior receipt schemas.
export const VISA_ORACLE_CONSENT_KEY = "visa-oracle:v2:handoff-consent:v2";
export const VISA_ORACLE_CONSENT_TTL_MS = VISA_ORACLE_RESUME_TTL_MS;

export interface LocalConsentReceipt {
  schemaVersion: typeof CONSENT_SCHEMA_VERSION;
  receiptId: string;
  policyVersion: typeof CONSENT_POLICY_VERSION;
  purpose: "WHATSAPP_HANDOFF";
  channel: "WHATSAPP";
  scope: ConsentScope;
  grantedAtIso: string;
  expiresAtIso: string;
}

export type ConsentScope =
  | { context: "CONSULTATION"; state?: never; assessmentReference?: never }
  | {
      context: "ASSESSMENT";
      state:
        | "SUPPORTED_CANDIDATES"
        | "NEEDS_INPUT"
        | "HUMAN_REVIEW_REQUIRED"
        | "NO_SUPPORTED_PATH"
        | "TEMPORARILY_UNAVAILABLE";
      /** Opaque engine public id only. No facts, candidates or applicant data. */
      assessmentReference: string | null;
    };

export interface ConsentStoreOptions {
  storage?: Pick<Storage, "getItem" | "setItem" | "removeItem">;
  now?: Date;
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
  storage: ConsentStoreOptions["storage"],
): Pick<Storage, "getItem" | "setItem" | "removeItem"> | null {
  return storage ?? browserStorage();
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

const RECEIPT_KEYS = [
  "channel",
  "expiresAtIso",
  "grantedAtIso",
  "policyVersion",
  "purpose",
  "receiptId",
  "schemaVersion",
  "scope",
] as const;

function validScope(value: unknown): value is ConsentScope {
  if (!isRecord(value)) return false;
  if (value.context === "CONSULTATION") {
    return Object.keys(value).length === 1;
  }
  if (
    value.context !== "ASSESSMENT" ||
    Object.keys(value).sort().join("|") !==
      ["assessmentReference", "context", "state"].sort().join("|")
  ) {
    return false;
  }
  return (
    typeof value.state === "string" &&
    OUTCOME_STATES.has(value.state) &&
    (value.assessmentReference === null ||
      (typeof value.assessmentReference === "string" &&
        PUBLIC_DECISION_ID_PATTERN.test(value.assessmentReference)))
  );
}

export function sameConsentScope(
  left: ConsentScope,
  right: ConsentScope,
): boolean {
  return (
    left.context === right.context &&
    left.state === right.state &&
    left.assessmentReference === right.assessmentReference
  );
}

function validReceipt(value: unknown): value is LocalConsentReceipt {
  if (!isRecord(value)) return false;
  if (
    Object.keys(value).sort().join("|") !== [...RECEIPT_KEYS].sort().join("|")
  ) {
    return false;
  }
  if (
    value.schemaVersion !== CONSENT_SCHEMA_VERSION ||
    value.policyVersion !== CONSENT_POLICY_VERSION ||
    value.purpose !== "WHATSAPP_HANDOFF" ||
    value.channel !== "WHATSAPP" ||
    !validScope(value.scope) ||
    typeof value.receiptId !== "string" ||
    !RECEIPT_ID_PATTERN.test(value.receiptId) ||
    typeof value.grantedAtIso !== "string" ||
    typeof value.expiresAtIso !== "string"
  ) {
    return false;
  }

  const grantedAt = Date.parse(value.grantedAtIso);
  const expiresAt = Date.parse(value.expiresAtIso);
  return (
    Number.isFinite(grantedAt) &&
    Number.isFinite(expiresAt) &&
    expiresAt > grantedAt &&
    expiresAt - grantedAt <= VISA_ORACLE_CONSENT_TTL_MS
  );
}

export function createLocalConsentReceipt(
  now: Date,
  receiptId: string,
  scope: ConsentScope,
): LocalConsentReceipt {
  if (
    !Number.isFinite(now.getTime()) ||
    !RECEIPT_ID_PATTERN.test(receiptId) ||
    !validScope(scope)
  ) {
    throw new Error("Invalid local consent receipt identity");
  }
  return {
    schemaVersion: CONSENT_SCHEMA_VERSION,
    receiptId,
    policyVersion: CONSENT_POLICY_VERSION,
    purpose: "WHATSAPP_HANDOFF",
    channel: "WHATSAPP",
    scope: { ...scope },
    grantedAtIso: now.toISOString(),
    expiresAtIso: new Date(
      now.getTime() + VISA_ORACLE_CONSENT_TTL_MS,
    ).toISOString(),
  };
}

export function saveLocalConsentReceipt(
  receipt: LocalConsentReceipt,
  options: ConsentStoreOptions = {},
): boolean {
  const storage = resolveStorage(options.storage);
  if (!storage || !validReceipt(receipt)) return false;
  try {
    storage.setItem(VISA_ORACLE_CONSENT_KEY, JSON.stringify(receipt));
    return true;
  } catch {
    return false;
  }
}

/** Invalid, expired, or over-retained consent is removed fail-closed. */
export function loadLocalConsentReceipt(
  expectedScope: ConsentScope,
  options: ConsentStoreOptions = {},
): LocalConsentReceipt | null {
  const storage = resolveStorage(options.storage);
  if (!storage) return null;
  try {
    const raw = storage.getItem(VISA_ORACLE_CONSENT_KEY);
    if (raw === null) return null;
    const receipt = JSON.parse(raw) as unknown;
    const now = options.now ?? new Date();
    if (
      !validReceipt(receipt) ||
      !validScope(expectedScope) ||
      !sameConsentScope(receipt.scope, expectedScope) ||
      Date.parse(receipt.expiresAtIso) <= now.getTime()
    ) {
      storage.removeItem(VISA_ORACLE_CONSENT_KEY);
      return null;
    }
    return receipt;
  } catch {
    try {
      storage.removeItem(VISA_ORACLE_CONSENT_KEY);
    } catch {
      // Storage may become unavailable between read and cleanup.
    }
    return null;
  }
}

export function clearLocalConsentReceipt(
  options: Pick<ConsentStoreOptions, "storage"> = {},
): void {
  const storage = resolveStorage(options.storage);
  if (!storage) return;
  try {
    storage.removeItem(VISA_ORACLE_CONSENT_KEY);
  } catch {
    // Best-effort local cleanup; this screen creates no remote CRM receipt.
  }
}
