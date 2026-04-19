/**
 * Stable per-browser identifier for anonymous chat sessions.
 *
 * Generated lazily on first call, persisted in localStorage. Used as the
 * key suffix for `bz_chat_anon_<deviceId>` snapshots when the user is not
 * authenticated. Does NOT identify a person — surviving a browser data
 * wipe is by design (a fresh ID is fine).
 */

const DEVICE_ID_KEY = 'bz_device_id';

function makeRandomId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  // Fallback for very old browsers / SSR-time accidental calls.
  return `dev-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * Returns the stable device ID, creating one if missing.
 * Returns an in-memory ID when localStorage is unavailable (private mode,
 * SSR) — safe to call but the ID won't survive the page.
 */
export function getDeviceId(): string {
  if (typeof window === 'undefined') {
    return makeRandomId();
  }

  try {
    const existing = window.localStorage.getItem(DEVICE_ID_KEY);
    if (existing) return existing;
    const fresh = makeRandomId();
    window.localStorage.setItem(DEVICE_ID_KEY, fresh);
    return fresh;
  } catch {
    return makeRandomId();
  }
}
