/**
 * Tests for vault (documents) Zod schemas.
 *
 * Verifies that schemas match the actual shape emitted by:
 *   - GET  /api/portal/documents
 *   - POST /api/portal/documents/upload
 *
 * BE sources:
 *   - apps/backend-rag/backend/app/routers/portal.py
 *   - apps/backend-rag/backend/services/portal/_mixins/documents.py
 */

import { describe, expect, it } from "vitest";

import {
  VaultFile,
  VaultListResponse,
  VaultScanStatus,
  VaultUploadedFile,
  VaultUploadResponse,
} from "./vault";

// A minimal valid list response — one document, LEFT-JOIN practice fields
// both null (document not linked to any practice).
const minimalListResponse = {
  success: true,
  data: [
    {
      id: 101,
      type: "passport",
      name: "passport_scan.pdf",
      status: "received",
      expiry_date: null,
      size_kb: 523,
      practice_id: null,
      practice_name: null,
      downloadable: false,
      created_at: "2026-04-18T09:15:42+00:00",
    },
  ],
};

describe("VaultListResponse", () => {
  it("parses a valid minimal response (one file, no practice link)", () => {
    const parsed = VaultListResponse.parse(minimalListResponse);
    expect(parsed.success).toBe(true);
    expect(parsed.data).toHaveLength(1);
    expect(parsed.data[0].id).toBe(101);
    expect(parsed.data[0].type).toBe("passport");
    expect(parsed.data[0].name).toBe("passport_scan.pdf");
    expect(parsed.data[0].downloadable).toBe(false);
    expect(parsed.data[0].practice_id).toBeNull();
  });

  it("parses a multi-file response with mixed downloadability and practice links", () => {
    const multi = {
      success: true,
      data: [
        {
          id: 201,
          type: "kitas",
          name: "KITAS_2026.pdf",
          status: "issued",
          expiry_date: "2027-04-18",
          size_kb: 1024,
          practice_id: 42,
          practice_name: "KITAS Working Visa",
          downloadable: true,
          created_at: "2026-04-18T10:00:00+00:00",
        },
        {
          id: 202,
          type: "akta_pendirian",
          name: "akta_pendirian.pdf",
          status: "verified",
          expiry_date: null,
          size_kb: 2048,
          practice_id: 77,
          practice_name: "PMA Setup",
          downloadable: true,
          created_at: "2026-04-17T14:30:00+00:00",
        },
        {
          id: 203,
          type: "nib",
          name: "nib_cert.pdf",
          status: "received",
          expiry_date: null,
          size_kb: 128,
          practice_id: null,
          practice_name: null,
          downloadable: false,
          created_at: "2026-04-16T08:00:00+00:00",
        },
      ],
    };
    const parsed = VaultListResponse.parse(multi);
    expect(parsed.data).toHaveLength(3);
    expect(parsed.data.filter((f) => f.downloadable)).toHaveLength(2);
    expect(parsed.data[0].practice_name).toBe("KITAS Working Visa");
  });

  it("handles null/undefined for all optional fields on a file", () => {
    // All nullable/optional fields explicitly null.
    const allNull = VaultFile.parse({
      id: 1,
      type: "misc",
      name: "x.pdf",
      status: null,
      expiry_date: null,
      size_kb: null,
      practice_id: null,
      practice_name: null,
      downloadable: false,
      created_at: "2026-04-18T00:00:00+00:00",
    });
    expect(allNull.status).toBeNull();
    expect(allNull.expiry_date).toBeNull();
    expect(allNull.size_kb).toBeNull();

    // Optional fields entirely absent (future-proof: BE may trim nulls).
    const absent = VaultFile.parse({
      id: 2,
      type: "misc",
      name: "y.pdf",
      downloadable: false,
      created_at: "2026-04-18T00:00:00+00:00",
    });
    expect(absent.status).toBeUndefined();
    expect(absent.expiry_date).toBeUndefined();
    expect(absent.practice_id).toBeUndefined();
  });

  it("rejects negative size_kb (would indicate BE regression)", () => {
    const bad = {
      ...minimalListResponse,
      data: [{ ...minimalListResponse.data[0], size_kb: -5 }],
    };
    expect(VaultListResponse.safeParse(bad).success).toBe(false);
  });

  it("rejects negative or non-integer id", () => {
    const neg = {
      ...minimalListResponse,
      data: [{ ...minimalListResponse.data[0], id: -1 }],
    };
    expect(VaultListResponse.safeParse(neg).success).toBe(false);

    const floaty = {
      ...minimalListResponse,
      data: [{ ...minimalListResponse.data[0], id: 3.5 }],
    };
    expect(VaultListResponse.safeParse(floaty).success).toBe(false);
  });

  it("rejects a malformed envelope (wrong top-level shape)", () => {
    // Bare array (missing envelope).
    const bareArray = [
      { id: 1, type: "x", name: "y.pdf", downloadable: false },
    ];
    expect(VaultListResponse.safeParse(bareArray).success).toBe(false);

    // Envelope with object-shaped `data` instead of array.
    const wrongDataShape = {
      success: true,
      data: {
        id: 1,
        type: "x",
        name: "y.pdf",
        downloadable: false,
        created_at: "2026-04-18T00:00:00+00:00",
      },
    };
    expect(VaultListResponse.safeParse(wrongDataShape).success).toBe(false);

    // Missing required `created_at` on a file.
    const noCreatedAt = {
      success: true,
      data: [
        {
          id: 1,
          type: "x",
          name: "y.pdf",
          downloadable: false,
        },
      ],
    };
    expect(VaultListResponse.safeParse(noCreatedAt).success).toBe(false);

    // Missing required `downloadable` boolean on a file.
    const noDownloadable = {
      success: true,
      data: [
        {
          id: 1,
          type: "x",
          name: "y.pdf",
          created_at: "2026-04-18T00:00:00+00:00",
        },
      ],
    };
    expect(VaultListResponse.safeParse(noDownloadable).success).toBe(false);
  });

  it("status is permissive (not a strict enum) — accepts any BE string", () => {
    // The documents table has NO CHECK constraint on status, so we must
    // accept values beyond the known set (received/verified/issued) that
    // workspace/CRM flows may set (e.g. draft, review, archived).
    const exotic = {
      ...minimalListResponse,
      data: [{ ...minimalListResponse.data[0], status: "archived_legacy_q3" }],
    };
    const result = VaultListResponse.safeParse(exotic);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.data[0].status).toBe("archived_legacy_q3");
    }
  });
});

describe("VaultScanStatus (future-proof enum, not on list endpoint today)", () => {
  it("accepts the four canonical values", () => {
    for (const s of ["pending", "clean", "infected", "error"] as const) {
      expect(VaultScanStatus.parse(s)).toBe(s);
    }
  });

  it("rejects an unknown scan status", () => {
    expect(VaultScanStatus.safeParse("quarantined").success).toBe(false);
    expect(VaultScanStatus.safeParse("").success).toBe(false);
    expect(VaultScanStatus.safeParse(null).success).toBe(false);
  });
});

describe("VaultUploadResponse", () => {
  // Mirrors the dict returned by `PortalDocumentsMixin.upload_document`
  // at documents.py:478-496.
  const validUpload = {
    success: true,
    message: "Document uploaded successfully",
    data: {
      id: 501,
      type: "passport",
      name: "passport.pdf",
      status: "received",
      size_kb: 412,
      created_at: "2026-04-18T12:00:00+00:00",
      expiry_date: "2030-01-15",
      extracted_text_preview: "Republic of Indonesia / Passport / ...",
      processing: {
        virus_clean: true,
        ocr_pages: 2,
        drive_uploaded: true,
      },
    },
  };

  it("parses a valid upload response", () => {
    const parsed = VaultUploadResponse.parse(validUpload);
    expect(parsed.data.id).toBe(501);
    expect(parsed.data.processing.virus_clean).toBe(true);
    expect(parsed.data.processing.ocr_pages).toBe(2);
  });

  it("handles null ocr_pages and empty extracted_text_preview", () => {
    const parsed = VaultUploadedFile.parse({
      id: 502,
      type: "misc",
      name: "unreadable.pdf",
      status: "received",
      size_kb: 50,
      created_at: "2026-04-18T12:00:00+00:00",
      expiry_date: null,
      extracted_text_preview: "",
      processing: {
        virus_clean: true,
        ocr_pages: null,
        drive_uploaded: false,
      },
    });
    expect(parsed.processing.ocr_pages).toBeNull();
    expect(parsed.extracted_text_preview).toBe("");
  });

  it("rejects missing required processing block", () => {
    const bad = {
      ...validUpload,
      data: { ...validUpload.data, processing: undefined },
    };
    expect(VaultUploadResponse.safeParse(bad).success).toBe(false);
  });
});
