import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { useVaultUpload } from "./useVaultUpload";

// ------------------------------------------------------------------
// Mock XMLHttpRequest — surface the instance to the test so we can drive
// progress / onload / onerror synchronously from assertions.
// ------------------------------------------------------------------

type UploadEventHandler = (e: ProgressEvent) => void;

class MockXHR {
  static last: MockXHR | null = null;

  upload = {
    onprogress: null as UploadEventHandler | null,
  };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;

  status = 0;
  responseText = "";
  withCredentials = false;

  openCalledWith: { method: string; url: string } | null = null;
  sentBody: FormData | null = null;

  constructor() {
    MockXHR.last = this;
  }

  open(method: string, url: string) {
    this.openCalledWith = { method, url };
  }
  send(body: FormData) {
    this.sentBody = body;
  }

  // Helpers used by tests
  emitProgress(loaded: number, total: number) {
    this.upload.onprogress?.({
      lengthComputable: true,
      loaded,
      total,
    } as unknown as ProgressEvent);
  }
  resolve(status: number, responseText: string) {
    this.status = status;
    this.responseText = responseText;
    this.onload?.();
  }
  fail() {
    this.onerror?.();
  }
}

// ------------------------------------------------------------------
// Sample payloads
// ------------------------------------------------------------------

const validUploadResp = {
  success: true,
  message: "Uploaded",
  data: {
    id: 99,
    type: "passport",
    name: "passport.pdf",
    status: "received",
    size_kb: 512,
    created_at: "2026-04-18T00:00:00Z",
    expiry_date: null,
    extracted_text_preview: null,
    processing: {
      virus_clean: true,
      ocr_pages: 2,
      drive_uploaded: true,
    },
  },
};

function makeFile(
  name: string,
  size: number,
  type: string = "application/pdf",
): File {
  const blob = new Blob([new Uint8Array(size)], { type });
  // File constructor honors blob size
  return new File([blob], name, { type });
}

// ------------------------------------------------------------------
// Tests
// ------------------------------------------------------------------

describe("useVaultUpload", () => {
  beforeEach(() => {
    MockXHR.last = null;
    vi.stubGlobal("XMLHttpRequest", MockXHR);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("rejects oversize file before opening request", () => {
    const { result } = renderHook(() => useVaultUpload());

    // 30 MB — default cap is 20 MB
    const big = makeFile("huge.pdf", 30 * 1024 * 1024, "application/pdf");

    act(() => result.current.upload(big));

    expect(result.current.state.status).toBe("error");
    if (result.current.state.status === "error") {
      expect(result.current.state.message).toMatch(/exceeds/i);
    }
    // XHR must NOT have been opened — validation short-circuits.
    expect(MockXHR.last).toBeNull();
  });

  it("rejects disallowed MIME", () => {
    const { result } = renderHook(() => useVaultUpload());

    const exe = makeFile("virus.exe", 1024, "application/x-msdownload");

    act(() => result.current.upload(exe));

    expect(result.current.state.status).toBe("error");
    if (result.current.state.status === "error") {
      expect(result.current.state.message).toMatch(/not allowed/i);
    }
    expect(MockXHR.last).toBeNull();
  });

  it("emits uploading state with progress percentage", () => {
    const { result } = renderHook(() => useVaultUpload());
    const file = makeFile("ok.pdf", 4096, "application/pdf");

    act(() => result.current.upload(file));

    expect(MockXHR.last).not.toBeNull();
    const xhr = MockXHR.last!;
    expect(xhr.openCalledWith).toEqual({
      method: "POST",
      url: "/api/portal/documents/upload",
    });
    expect(xhr.withCredentials).toBe(true);

    act(() => xhr.emitProgress(50, 100));

    expect(result.current.state.status).toBe("uploading");
    if (result.current.state.status === "uploading") {
      expect(result.current.state.progress).toBe(50);
    }
  });

  it("transitions to done on successful upload with processing block", async () => {
    const { result } = renderHook(() => useVaultUpload());
    const file = makeFile("ok.pdf", 4096, "application/pdf");

    act(() => result.current.upload(file));
    const xhr = MockXHR.last!;

    act(() => xhr.resolve(200, JSON.stringify(validUploadResp)));

    await waitFor(() => expect(result.current.state.status).toBe("done"));
    if (result.current.state.status === "done") {
      expect(result.current.state.file.id).toBe(99);
      expect(result.current.state.file.name).toBe("passport.pdf");
      expect(result.current.state.processing.virus_clean).toBe(true);
      expect(result.current.state.processing.ocr_pages).toBe(2);
      expect(result.current.state.processing.drive_uploaded).toBe(true);
    }
  });

  it("surfaces schema drift in response as error", async () => {
    const { result } = renderHook(() => useVaultUpload());
    const file = makeFile("ok.pdf", 4096, "application/pdf");

    act(() => result.current.upload(file));
    const xhr = MockXHR.last!;

    // Missing `data.processing` — Zod parse throws.
    const drifted = { success: true, data: { id: 1, type: "x", name: "x" } };
    act(() => xhr.resolve(200, JSON.stringify(drifted)));

    await waitFor(() => expect(result.current.state.status).toBe("error"));
    if (result.current.state.status === "error") {
      expect(result.current.state.message).toMatch(/invalid server response/i);
      expect(result.current.state.httpStatus).toBe(200);
    }
  });

  it("surfaces non-2xx HTTP response as error", async () => {
    const { result } = renderHook(() => useVaultUpload());
    const file = makeFile("ok.pdf", 4096, "application/pdf");

    act(() => result.current.upload(file));
    const xhr = MockXHR.last!;

    act(() => xhr.resolve(413, ""));

    await waitFor(() => expect(result.current.state.status).toBe("error"));
    if (result.current.state.status === "error") {
      expect(result.current.state.message).toMatch(/413/);
      expect(result.current.state.httpStatus).toBe(413);
    }
  });

  it("surfaces network error", async () => {
    const { result } = renderHook(() => useVaultUpload());
    const file = makeFile("ok.pdf", 4096, "application/pdf");

    act(() => result.current.upload(file));
    const xhr = MockXHR.last!;

    act(() => xhr.fail());

    await waitFor(() => expect(result.current.state.status).toBe("error"));
    if (result.current.state.status === "error") {
      expect(result.current.state.message).toMatch(/network error/i);
    }
  });

  it("reset() returns state to idle", async () => {
    const { result } = renderHook(() => useVaultUpload());
    const file = makeFile("ok.pdf", 4096, "application/pdf");

    act(() => result.current.upload(file));
    const xhr = MockXHR.last!;
    act(() => xhr.resolve(200, JSON.stringify(validUploadResp)));

    await waitFor(() => expect(result.current.state.status).toBe("done"));

    act(() => result.current.reset());
    expect(result.current.state.status).toBe("idle");
  });
});
