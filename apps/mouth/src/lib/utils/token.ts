/**
 * JWT Token Utilities
 *
 * Provides token expiry validation without a full JWT library.
 * Uses base64 decoding of the JWT payload to check the `exp` claim.
 */

/**
 * Decode a JWT payload without verification.
 * This is safe for expiry checking -- signature verification
 * happens on the backend.
 *
 * @returns Parsed payload or null if decoding fails
 */
function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;

    // Base64url decode the payload (second segment)
    const payload = parts[1]
      .replace(/-/g, "+")
      .replace(/_/g, "/");

    const decoded = atob(payload);
    return JSON.parse(decoded);
  } catch {
    return null;
  }
}

/**
 * Check if a JWT token is expired.
 *
 * @param token - JWT token string
 * @param clockSkewSeconds - Grace period in seconds (default 30s)
 * @returns true if the token has a valid `exp` claim that is in the past,
 *          false if the token is still valid, not a JWT, or has no exp claim.
 *          Non-JWT tokens are treated as valid (backend will reject if invalid).
 */
export function isTokenExpired(
  token: string,
  clockSkewSeconds: number = 30,
): boolean {
  if (!token) return true;

  const payload = decodeJwtPayload(token);
  if (!payload) {
    // Not a decodable JWT -- let backend validate; do not reject client-side
    return false;
  }

  const exp = payload.exp;
  if (typeof exp !== "number") {
    // No `exp` claim -- treat as non-expiring (some internal tokens)
    return false;
  }

  const nowSeconds = Math.floor(Date.now() / 1000);
  return nowSeconds >= exp - clockSkewSeconds;
}

/**
 * Get a token from storage, validating its expiry.
 * If the token is expired, it is removed from storage and null is returned.
 *
 * @param key - Storage key (e.g. "auth_token")
 * @param storage - Storage interface (localStorage or safeStorage)
 * @returns The token if valid, or null if expired/missing
 */
export function getValidToken(
  key: string,
  storage: {
    getItem: (k: string) => string | null;
    removeItem: (k: string) => void;
  },
): string | null {
  const token = storage.getItem(key);
  if (!token) return null;

  if (isTokenExpired(token)) {
    storage.removeItem(key);
    return null;
  }

  return token;
}
