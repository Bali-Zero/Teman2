/**
 * Tests for settings Zod schemas.
 *
 * Verifies schemas match the shapes emitted by:
 *   - GET /api/auth/profile          (UserProfile)
 *   - GET /api/portal/settings       (PortalSettingsResponse)
 *   - GET/PUT /api/portal/notifications/prefs  (NotificationPrefs*)
 */

import { describe, expect, it } from "vitest";

import {
  isMigrationMissingMessage,
  Language,
  MigrationMissingError,
  NotificationChannel,
  NotificationEvent,
  NotificationPrefs,
  NotificationPrefsInput,
  PortalSettings,
  PortalSettingsResponse,
  UserProfile,
} from "./settings";

// ============================================
// UserProfile
// ============================================

describe("UserProfile", () => {
  // Shape mirrors what /api/auth/profile emits after Pydantic
  // `model_post_init` syncs id<->user_id and language<->language_preference.
  const fullProfile = {
    id: "u_123",
    user_id: "u_123",
    email: "zero@balizero.com",
    name: "Zero",
    role: "admin",
    status: "active",
    avatar: "/avatars/zero.png",
    language: "it",
    language_preference: "it",
    tone: "professional",
    complexity: "medium",
    timezone: "Asia/Bali",
    role_level: "owner",
    metadata: { foo: "bar" },
    meta_json: { foo: "bar" },
  };

  it("parses a full profile response", () => {
    const parsed = UserProfile.parse(fullProfile);
    expect(parsed.id).toBe("u_123");
    expect(parsed.user_id).toBe("u_123");
    expect(parsed.language).toBe("it");
    expect(parsed.metadata).toEqual({ foo: "bar" });
  });

  it("accepts only one of id/user_id (BE compat path)", () => {
    // Only `id` — BE normaliser will fill `user_id` before return, but we
    // don't want Zod to choke if a future BE slims the response.
    expect(
      UserProfile.safeParse({ ...fullProfile, user_id: undefined }).success,
    ).toBe(true);
    // Only `user_id` — older call sites.
    expect(
      UserProfile.safeParse({ ...fullProfile, id: undefined }).success,
    ).toBe(true);
  });

  it("rejects a profile missing both id and user_id", () => {
    const noIds = { ...fullProfile, id: undefined, user_id: undefined };
    const result = UserProfile.safeParse(noIds);
    expect(result.success).toBe(false);
  });

  it("rejects a profile missing email/name/role/language", () => {
    for (const missing of ["email", "name", "role", "language"] as const) {
      const bad = { ...fullProfile } as Record<string, unknown>;
      delete bad[missing];
      const result = UserProfile.safeParse(bad);
      expect(result.success).toBe(false);
    }
  });

  it("accepts nullable optional fields as null", () => {
    const parsed = UserProfile.parse({
      ...fullProfile,
      status: null,
      avatar: null,
      tone: null,
      complexity: null,
      timezone: null,
      role_level: null,
      metadata: null,
      language_preference: null,
    });
    expect(parsed.status).toBeNull();
    expect(parsed.metadata).toBeNull();
  });
});

// ============================================
// PortalSettings / PortalSettingsResponse
// ============================================

describe("PortalSettings", () => {
  it("parses BE defaults (no row in client_preferences)", () => {
    const parsed = PortalSettings.parse({
      email_notifications: true,
      whatsapp_notifications: true,
      language: "en",
      timezone: "Asia/Jakarta",
    });
    expect(parsed.email_notifications).toBe(true);
    expect(parsed.language).toBe("en");
  });

  it("rejects missing fields", () => {
    const result = PortalSettings.safeParse({ email_notifications: true });
    expect(result.success).toBe(false);
  });

  it("parses the full envelope { success, data }", () => {
    const parsed = PortalSettingsResponse.parse({
      success: true,
      data: {
        email_notifications: false,
        whatsapp_notifications: true,
        language: "it",
        timezone: "Asia/Bali",
      },
    });
    expect(parsed.success).toBe(true);
    expect(parsed.data.language).toBe("it");
  });
});

// ============================================
// NotificationPrefs (GET response) + Input (PUT payload)
// ============================================

describe("NotificationPrefs (GET)", () => {
  it("parses prefs with wa_phone = null (channel disabled)", () => {
    const parsed = NotificationPrefs.parse({
      email_enabled: true,
      wa_enabled: false,
      wa_phone: null,
    });
    expect(parsed.wa_phone).toBeNull();
  });

  it("parses prefs with a valid-looking E.164 phone", () => {
    const parsed = NotificationPrefs.parse({
      email_enabled: true,
      wa_enabled: true,
      wa_phone: "628123456789",
    });
    expect(parsed.wa_enabled).toBe(true);
    expect(parsed.wa_phone).toBe("628123456789");
  });

  it("rejects non-boolean email/wa flags", () => {
    const bad = {
      email_enabled: "yes",
      wa_enabled: 1,
      wa_phone: null,
    };
    expect(NotificationPrefs.safeParse(bad).success).toBe(false);
  });
});

describe("NotificationPrefsInput (PUT)", () => {
  it("accepts valid input with phone and wa_enabled=true", () => {
    const parsed = NotificationPrefsInput.parse({
      email_enabled: true,
      wa_enabled: true,
      wa_phone: "628123456789",
    });
    expect(parsed.wa_enabled).toBe(true);
  });

  it("accepts valid input with wa_enabled=false and no phone", () => {
    const parsed = NotificationPrefsInput.parse({
      email_enabled: true,
      wa_enabled: false,
    });
    expect(parsed.wa_phone).toBeUndefined();
  });

  it("rejects wa_enabled=true with missing phone", () => {
    const result = NotificationPrefsInput.safeParse({
      email_enabled: true,
      wa_enabled: true,
    });
    expect(result.success).toBe(false);
  });

  it("rejects wa_phone starting with + (BE wants digits only)", () => {
    const result = NotificationPrefsInput.safeParse({
      email_enabled: true,
      wa_enabled: true,
      wa_phone: "+628123456789",
    });
    expect(result.success).toBe(false);
  });

  it("rejects wa_phone with alpha characters", () => {
    const result = NotificationPrefsInput.safeParse({
      email_enabled: true,
      wa_enabled: true,
      wa_phone: "62notaphone",
    });
    expect(result.success).toBe(false);
  });
});

// ============================================
// Enums + migration-missing helpers
// ============================================

describe("Language enum", () => {
  it("accepts exactly the 3 supported locales", () => {
    expect(Language.options).toEqual(["it", "en", "id"]);
  });

  it("rejects an unknown locale", () => {
    expect(Language.safeParse("fr").success).toBe(false);
  });
});

describe("NotificationChannel / NotificationEvent enums", () => {
  it("NotificationChannel only has email + wa today", () => {
    expect(NotificationChannel.options).toEqual(["email", "wa"]);
  });

  it("NotificationEvent lists the 3 current event families", () => {
    expect([...NotificationEvent.options].sort()).toEqual(
      ["deadline_reminder", "document_request", "practice_update"].sort(),
    );
  });
});

describe("MigrationMissingError + isMigrationMissingMessage", () => {
  it("parses the FastAPI 503 shape { detail }", () => {
    const parsed = MigrationMissingError.parse({
      detail: "notification_prefs unavailable — run migration 110",
    });
    expect(parsed.detail).toMatch(/migration 110/);
  });

  it("isMigrationMissingMessage recognises the BE message variants", () => {
    expect(
      isMigrationMissingMessage(
        "notification_prefs unavailable — run migration 110",
      ),
    ).toBe(true);
    expect(isMigrationMissingMessage("please run Migration 110")).toBe(true);
    expect(isMigrationMissingMessage("something else went wrong")).toBe(false);
    expect(isMigrationMissingMessage(undefined)).toBe(false);
  });
});
