export const VISA_ORACLE_MODES = [
  "OFF",
  "SHADOW",
  "ENGINE",
  "PREVIEW",
] as const;

export type VisaOracleMode = (typeof VISA_ORACLE_MODES)[number];

const MODE_SET = new Set<string>(VISA_ORACLE_MODES);

/**
 * Resolve the v2 strangler mode without allowing an invalid deployment value
 * to silently put the mock back in charge.
 *
 * Browser builds default to ENGINE. Vitest defaults to PREVIEW so isolated UI
 * tests can exercise the curated fixture without a network dependency.
 * Production ignores an explicit PREVIEW value and fails back to ENGINE: a
 * deployment typo can never put the mock catalogue in public authority.
 */
export function resolveVisaOracleMode(
  configuredMode: string | undefined = process.env.NEXT_PUBLIC_VISA_ORACLE_MODE,
  nodeEnvironment: string | undefined = process.env.NODE_ENV,
): VisaOracleMode {
  const normalized = configuredMode?.trim().toUpperCase();
  if (normalized && MODE_SET.has(normalized)) {
    if (normalized === "PREVIEW" && nodeEnvironment === "production") {
      return "ENGINE";
    }
    return normalized as VisaOracleMode;
  }
  return nodeEnvironment === "test" ? "PREVIEW" : "ENGINE";
}

export function modeUsesEngine(mode: VisaOracleMode): boolean {
  return mode === "ENGINE" || mode === "SHADOW";
}

export function modeMayRenderPreview(mode: VisaOracleMode): boolean {
  return mode === "PREVIEW";
}
