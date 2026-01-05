/**
 * Safe localStorage wrapper with fallback for Safari Private Browsing
 *
 * Safari iOS blocks localStorage in Private Browsing mode, throwing QuotaExceededError.
 * This wrapper gracefully handles those cases without crashing the app.
 *
 * Best Practice: Use httpOnly cookies for auth (primary), localStorage as optional enhancement.
 */

class SafeStorage {
  private isAvailable: boolean;
  private memoryFallback: Map<string, string>;

  constructor() {
    this.memoryFallback = new Map();
    this.isAvailable = this.checkAvailability();
  }

  /**
   * Check if localStorage is available (not blocked by Private Browsing)
   */
  private checkAvailability(): boolean {
    if (typeof window === 'undefined') return false;

    try {
      const testKey = '__storage_test__';
      localStorage.setItem(testKey, 'test');
      localStorage.removeItem(testKey);
      return true;
    } catch (e) {
      console.warn('[SafeStorage] localStorage blocked (Private Browsing or disabled). Using memory fallback.');
      return false;
    }
  }

  /**
   * Safely get item from localStorage with fallback
   */
  getItem(key: string): string | null {
    try {
      if (this.isAvailable) {
        return localStorage.getItem(key);
      }
      return this.memoryFallback.get(key) || null;
    } catch (e) {
      console.warn(`[SafeStorage] getItem failed for key "${key}":`, e);
      return this.memoryFallback.get(key) || null;
    }
  }

  /**
   * Safely set item in localStorage with fallback
   */
  setItem(key: string, value: string): boolean {
    try {
      if (this.isAvailable) {
        localStorage.setItem(key, value);
        return true;
      }
      this.memoryFallback.set(key, value);
      return false; // Indicate fallback was used
    } catch (e) {
      console.warn(`[SafeStorage] setItem failed for key "${key}":`, e);
      this.memoryFallback.set(key, value);
      return false;
    }
  }

  /**
   * Safely remove item from localStorage with fallback
   */
  removeItem(key: string): void {
    try {
      if (this.isAvailable) {
        localStorage.removeItem(key);
      }
      this.memoryFallback.delete(key);
    } catch (e) {
      console.warn(`[SafeStorage] removeItem failed for key "${key}":`, e);
      this.memoryFallback.delete(key);
    }
  }

  /**
   * Clear all items (both localStorage and memory fallback)
   */
  clear(): void {
    try {
      if (this.isAvailable) {
        localStorage.clear();
      }
      this.memoryFallback.clear();
    } catch (e) {
      console.warn('[SafeStorage] clear failed:', e);
      this.memoryFallback.clear();
    }
  }

  /**
   * Check if localStorage is actually available (not using fallback)
   */
  isLocalStorageAvailable(): boolean {
    return this.isAvailable;
  }
}

// Singleton instance
export const safeStorage = new SafeStorage();

/**
 * Backward compatible exports for drop-in replacement
 */
export const storage = {
  getItem: (key: string) => safeStorage.getItem(key),
  setItem: (key: string, value: string) => safeStorage.setItem(key, value),
  removeItem: (key: string) => safeStorage.removeItem(key),
  clear: () => safeStorage.clear(),
  isAvailable: () => safeStorage.isLocalStorageAvailable(),
};
