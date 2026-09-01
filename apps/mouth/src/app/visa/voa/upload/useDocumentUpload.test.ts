import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { useDocumentUpload } from "./useDocumentUpload";

function makeFile(name: string, size: number, type: string): File {
  return new File([new Uint8Array(size)], name, { type });
}

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

describe("useDocumentUpload", () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    global.fetch = mockFetch;
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("rejects an oversized file client-side without calling fetch", () => {
    const { result } = renderHook(() => useDocumentUpload("result-1"));
    const bigFile = makeFile("passport.jpg", 20 * 1024 * 1024, "image/jpeg");

    act(() => {
      result.current.selectFile(bigFile);
    });

    expect(result.current.state.step).toBe("client_rejected");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("rejects an unsupported media type client-side without calling fetch", () => {
    const { result } = renderHook(() => useDocumentUpload("result-1"));
    const pdf = makeFile("passport.pdf", 1024, "application/pdf");

    act(() => {
      result.current.selectFile(pdf);
    });

    expect(result.current.state.step).toBe("client_rejected");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("sends a fresh Idempotency-Key header on a valid upload, and moves to ready on 201", async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse(201, {
        document_id: "doc-1",
        processing_state: "READY_FOR_REVIEW",
        review_fields: [
          {
            field_path: "full_name",
            value: "JANE DOE",
            confirmation_required: true,
          },
        ],
      }),
    );

    const { result } = renderHook(() => useDocumentUpload("result-1"));
    const file = makeFile("passport.jpg", 1024, "image/jpeg");

    act(() => {
      result.current.selectFile(file);
    });

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, init] = mockFetch.mock.calls[0];
    expect(String(url)).toContain(
      "/visa/voa/eligibility-checks/result-1/documents",
    );
    const headers = init.headers as Record<string, string>;
    expect(headers["Idempotency-Key"]).toEqual(expect.any(String));
    expect(headers["Idempotency-Key"].length).toBeGreaterThan(0);

    await waitFor(() => expect(result.current.state.step).toBe("ready"));
    if (result.current.state.step === "ready") {
      expect(result.current.state.fields[0].value).toBe("JANE DOE");
    }
  });

  it("moves to low_confidence on a 202 LOW_CONFIDENCE body, with no leaked value", async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse(202, {
        document_id: "doc-2",
        processing_state: "LOW_CONFIDENCE",
        uncertain_fields: [
          { field_path: "passport_number", confirmation_required: true },
        ],
      }),
    );

    const { result } = renderHook(() => useDocumentUpload("result-1"));
    act(() => {
      result.current.selectFile(makeFile("passport.jpg", 1024, "image/jpeg"));
    });

    await waitFor(() =>
      expect(result.current.state.step).toBe("low_confidence"),
    );
    if (result.current.state.step === "low_confidence") {
      expect(result.current.state.uncertainFields).toEqual([
        { field_path: "passport_number", confirmation_required: true },
      ]);
    }
  });

  it("moves to unreadable on the UNREADABLE_DOCUMENT error code", async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse(422, {
        code: "UNREADABLE_DOCUMENT",
        retryable: false,
        message_key: "garuda_voa.error.unreadable_document",
      }),
    );

    const { result } = renderHook(() => useDocumentUpload("result-1"));
    act(() => {
      result.current.selectFile(makeFile("passport.jpg", 1024, "image/jpeg"));
    });

    await waitFor(() => expect(result.current.state.step).toBe("unreadable"));
  });

  it("surfaces a retryable error for a retryable server error code", async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse(503, {
        code: "DOCUMENT_PROCESSING_UNAVAILABLE",
        retryable: true,
        message_key: "garuda_voa.error.document_processing_unavailable",
      }),
    );

    const { result } = renderHook(() => useDocumentUpload("result-1"));
    act(() => {
      result.current.selectFile(makeFile("passport.jpg", 1024, "image/jpeg"));
    });

    await waitFor(() => expect(result.current.state.step).toBe("error"));
    if (result.current.state.step === "error") {
      expect(result.current.state.retryable).toBe(true);
    }
  });

  it("replays with the SAME idempotency key while the server returns PROCESSING", async () => {
    mockFetch
      .mockResolvedValueOnce(
        jsonResponse(202, {
          document_id: "doc-3",
          processing_state: "PROCESSING",
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse(201, {
          document_id: "doc-3",
          processing_state: "READY_FOR_REVIEW",
          review_fields: [
            {
              field_path: "full_name",
              value: "JANE DOE",
              confirmation_required: true,
            },
          ],
        }),
      );

    const { result } = renderHook(() => useDocumentUpload("result-1"));
    act(() => {
      result.current.selectFile(makeFile("passport.jpg", 1024, "image/jpeg"));
    });

    // Real 2s wait, not faked: mixing fake timers with testing-library's `waitFor` (which
    // itself polls on a timer) deadlocks rather than advancing — not worth the complexity
    // for one poll-interval test.
    await waitFor(() => expect(result.current.state.step).toBe("ready"), {
      timeout: 4000,
    });
    expect(mockFetch).toHaveBeenCalledTimes(2);
    const key1 = (mockFetch.mock.calls[0][1].headers as Record<string, string>)[
      "Idempotency-Key"
    ];
    const key2 = (mockFetch.mock.calls[1][1].headers as Record<string, string>)[
      "Idempotency-Key"
    ];
    expect(key1).toBe(key2); // exact replay identity — the contract's safe-retry guarantee
  }, 10000);

  it("does not let a LATE-arriving stale rejection clobber a newer, already-succeeded upload", async () => {
    // Refuter finding (2026-08-25): selecting file B while file A's request is still
    // pending aborts A's fetch, but A's rejection can still arrive on the microtask queue
    // AFTER B has already succeeded and rendered "ready". The old code unconditionally
    // overwrote state on any catch, so that late arrival flipped a successfully-reviewed
    // upload back to a generic error. Deferred promises here give explicit control over
    // settle ORDER (never left to incidental microtask timing) so the regression this
    // guards is unambiguous: resolve B's success FIRST, only THEN reject A's stale
    // request, and assert state is untouched by the second event.
    let resolveA!: (v: Response) => void;
    let rejectA!: (e: unknown) => void;
    const pendingA = new Promise<Response>((res, rej) => {
      resolveA = res;
      rejectA = rej;
    });
    void resolveA; // unused — A never resolves successfully in this scenario, only rejects

    let callCount = 0;
    mockFetch.mockImplementation(() => {
      callCount += 1;
      if (callCount === 1) return pendingA;
      return Promise.resolve(
        jsonResponse(201, {
          document_id: "doc-b",
          processing_state: "READY_FOR_REVIEW",
          review_fields: [
            {
              field_path: "full_name",
              value: "JANE DOE",
              confirmation_required: true,
            },
          ],
        }),
      );
    });

    const { result } = renderHook(() => useDocumentUpload("result-1"));

    act(() => {
      result.current.selectFile(makeFile("passport-a.jpg", 1024, "image/jpeg"));
    });
    expect(result.current.state.step).toBe("uploading");

    act(() => {
      result.current.selectFile(makeFile("passport-b.jpg", 1024, "image/jpeg"));
    });

    // B (the current attempt) succeeds first.
    await waitFor(() => expect(result.current.state.step).toBe("ready"));

    // Only NOW does A's aborted request's rejection actually land.
    await act(async () => {
      rejectA(new DOMException("Aborted", "AbortError"));
      await pendingA.catch(() => {});
    });

    expect(result.current.state.step).toBe("ready");
  });

  it("uses a NEW idempotency key when a different file is selected (not a replay)", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse(422, {
        code: "UNREADABLE_DOCUMENT",
        retryable: false,
        message_key: "garuda_voa.error.unreadable_document",
      }),
    );

    const { result } = renderHook(() => useDocumentUpload("result-1"));

    act(() => {
      result.current.selectFile(makeFile("passport-1.jpg", 1024, "image/jpeg"));
    });
    await waitFor(() => expect(result.current.state.step).toBe("unreadable"));

    act(() => {
      result.current.selectFile(makeFile("passport-2.jpg", 1024, "image/jpeg"));
    });
    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(2));

    const key1 = (mockFetch.mock.calls[0][1].headers as Record<string, string>)[
      "Idempotency-Key"
    ];
    const key2 = (mockFetch.mock.calls[1][1].headers as Record<string, string>)[
      "Idempotency-Key"
    ];
    expect(key1).not.toBe(key2); // a new photo is a new upload attempt, not a replay
  });
});
