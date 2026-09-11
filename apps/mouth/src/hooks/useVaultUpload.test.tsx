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

    // 30 MB — safely above the backend-aligned 10 MB default cap.
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

  it("transitions to done on a client-safe successful upload", async () => {
    const { result } = renderHook(() => useVaultUpload());
    const file = makeFile("ok.pdf", 4096, "application/pdf");

    act(() => result.current.upload(file));
    const xhr = MockXHR.last!;

    act(() => xhr.resolve(200, JSON.stringify(validUploadResp)));

    await waitFor(() => expect(result.current.state.status).toBe("done"));
    if (result.current.state.status === "done") {
      expect(result.current.state.file.id).toBe(99);
      expect(result.current.state.file.name).toBe("passport.pdf");
    }
  });

  it("rejects leaked processing internals in a successful response", async () => {
    const { result } = renderHook(() => useVaultUpload());
    const file = makeFile("ok.pdf", 4096, "application/pdf");

    act(() => result.current.upload(file));
    const xhr = MockXHR.last!;

    const leaked = {
      ...validUploadResp,
      data: {
        ...validUploadResp.data,
        processing: {
          virus_clean: true,
          ocr_pages: 2,
          drive_uploaded: true,
        },
      },
    };
    act(() => xhr.resolve(200, JSON.stringify(leaked)));

    await waitFor(() => expect(result.current.state.status).toBe("error"));
    if (result.current.state.status === "error") {
      expect(result.current.state.message).toMatch(/invalid server response/i);
      expect(result.current.state.httpStatus).toBe(200);
    }
    expect(result.current.canRetry).toBe(false);
  });

  it("surfaces an incomplete response as schema drift", async () => {
    const { result } = renderHook(() => useVaultUpload());
    const file = makeFile("ok.pdf", 4096, "application/pdf");

    act(() => result.current.upload(file));
    const xhr = MockXHR.last!;
    act(() =>
      xhr.resolve(
        200,
        JSON.stringify({ success: true, data: { id: 1, name: "x.pdf" } }),
      ),
    );

    await waitFor(() => expect(result.current.state.status).toBe("error"));
    if (result.current.state.status === "error") {
      expect(result.current.state.message).toMatch(/invalid server response/i);
      expect(result.current.state.httpStatus).toBe(200);
    }
    expect(result.current.canRetry).toBe(false);
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
    expect(result.current.canRetry).toBe(false);
  });

  // Portal audit ux F1 (2026-09-11): the failure branch rendered
  // `Upload failed (${status})` and threw the response body away, even
  // though the success branch parses it two lines above. A client hitting
  // the hour-long duplicate guard saw "Upload failed (409)" instead of the
  // sentence the backend had already written for them.
  it("shows the reason the server gave, not just its status code", async () => {
    const { result } = renderHook(() => useVaultUpload());
    const file = makeFile("ok.pdf", 4096, "application/pdf");

    act(() => result.current.upload(file));
    const xhr = MockXHR.last!;

    // The live 409 from the duplicate guard, verbatim.
    const detail =
      "A file with this name was uploaded less than an hour ago. " +
      "Please rename it or wait.";
    act(() => xhr.resolve(409, JSON.stringify({ detail })));

    await waitFor(() => expect(result.current.state.status).toBe("error"));
    if (result.current.state.status === "error") {
      expect(result.current.state.message).toBe(detail);
      expect(result.current.state.httpStatus).toBe(409);
    }
  });

  it("prefers `message` when the envelope uses it instead of `detail`", async () => {
    const { result } = renderHook(() => useVaultUpload());
    const file = makeFile("ok.pdf", 4096, "application/pdf");

    act(() => result.current.upload(file));
    const xhr = MockXHR.last!;
    act(() => xhr.resolve(422, JSON.stringify({ message: "Wrong doc type" })));

    await waitFor(() => expect(result.current.state.status).toBe("error"));
    if (result.current.state.status === "error") {
      expect(result.current.state.message).toBe("Wrong doc type");
    }
  });

  it.each([
    ["an empty body", ""],
    ["HTML from a proxy", "<html><body>502</body></html>"],
    [
      "a non-string detail (FastAPI validation errors are a LIST)",
      JSON.stringify({ detail: [{ loc: ["body"], msg: "x", type: "y" }] }),
    ],
    ["a blank detail", JSON.stringify({ detail: "   " })],
  ])("falls back to the status code for %s", async (_label, body) => {
    const { result } = renderHook(() => useVaultUpload());
    const file = makeFile("ok.pdf", 4096, "application/pdf");

    act(() => result.current.upload(file));
    const xhr = MockXHR.last!;
    act(() => xhr.resolve(500, body));

    await waitFor(() => expect(result.current.state.status).toBe("error"));
    if (result.current.state.status === "error") {
      expect(result.current.state.message).toBe("Upload failed (500)");
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
    expect(result.current.canRetry).toBe(true);
  });

  it("retries the same validated file and options after transport failure", async () => {
    const { result } = renderHook(() => useVaultUpload());
    const file = makeFile("retry.pdf", 4096, "application/pdf");

    act(() =>
      result.current.upload(file, {
        practiceId: 42,
        documentType: "other",
        purpose: "Synthetic retry proof",
      }),
    );
    const failedRequest = MockXHR.last!;
    act(() => failedRequest.resolve(503, ""));

    await waitFor(() => expect(result.current.canRetry).toBe(true));
    act(() => result.current.retry());

    const retryRequest = MockXHR.last!;
    expect(retryRequest).not.toBe(failedRequest);
    const retriedFile = retryRequest.sentBody?.get("file");
    expect(retriedFile).toBeInstanceOf(File);
    expect(retriedFile).toMatchObject({
      name: file.name,
      size: file.size,
      type: file.type,
    });
    expect(retryRequest.sentBody?.get("practice_id")).toBe("42");
    expect(retryRequest.sentBody?.get("document_type")).toBe("other");
    expect(retryRequest.sentBody?.get("document_purpose")).toBe(
      "Synthetic retry proof",
    );

    act(() => retryRequest.resolve(200, JSON.stringify(validUploadResp)));
    await waitFor(() => expect(result.current.state.status).toBe("done"));
    expect(result.current.canRetry).toBe(false);
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
