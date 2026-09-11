"use client";

import { useCallback, useRef, useState } from "react";
import { sanitizeFilename } from "@/lib/vault/sanitizeFilename";
import { MAX_SIZE_BYTES, isAllowedUploadMime } from "@/lib/vault/uploadLimits";
import {
  VaultUploadResponse,
  type VaultUploadedFile,
} from "@/lib/schemas/vault";

export type UploadState =
  | { status: "idle" }
  | { status: "validating" }
  | { status: "uploading"; progress: number }
  | {
      status: "done";
      file: VaultUploadedFile;
    }
  | { status: "error"; message: string; httpStatus?: number };

export interface UploadOptions {
  practiceId?: number | string | null;
  documentType?: string;
  /**
   * FASE 5 — client-facing note on why this document is being provided.
   * Sent as the `document_purpose` form field; trimmed/capped server-side.
   */
  purpose?: string | null;
}

interface RetryableUpload {
  readonly file: File;
  readonly options: UploadOptions;
}

function isRetryableHttpStatus(status: number): boolean {
  return (
    status === 0 ||
    status === 408 ||
    status === 425 ||
    status === 429 ||
    status >= 500
  );
}

/**
 * Uploads a single file to `POST /api/portal/documents/upload` via
 * `XMLHttpRequest` (required for progress events — `fetch` has no upload
 * progress in browsers).
 *
 * Pre-flight validation rejects disallowed MIME types and oversize files
 * before opening the request. The upload response is Zod-validated against
 * the backend's client-safe document projection; scan, OCR, and storage
 * internals are intentionally unavailable to the UI.
 */
/**
 * The reason the server gave, not just the number it gave it with.
 *
 * The failure branch used to render `Upload failed (${status})` and throw
 * `xhr.responseText` away — even though the success branch two lines above
 * already parses it. A client hitting the hour-long duplicate guard saw
 * "Upload failed (409)" instead of "A file with this name was uploaded less
 * than an hour ago", and a client hitting a document-type rule saw
 * "Upload failed (422)" instead of the rule (portal audit ux F1).
 *
 * FastAPI puts the reason in `detail`; this app's own envelopes use
 * `message`. Anything else — HTML from a proxy, an empty body, a non-string
 * `detail` (FastAPI's validation errors are a LIST of objects, which is
 * exactly the shape that must not be stringified at a client) — falls back
 * to the status code, which is still more honest than a wrong sentence.
 */
function serverRejectionMessage(responseText: string, status: number): string {
  const fallback = `Upload failed (${status})`;
  try {
    const body: unknown = JSON.parse(responseText);
    if (typeof body !== "object" || body === null) return fallback;
    const { detail, message } = body as {
      detail?: unknown;
      message?: unknown;
    };
    for (const candidate of [detail, message]) {
      if (typeof candidate === "string" && candidate.trim().length > 0) {
        return candidate.trim();
      }
    }
    return fallback;
  } catch {
    return fallback;
  }
}

export function useVaultUpload() {
  const [state, setState] = useState<UploadState>({ status: "idle" });
  const retryableUploadRef = useRef<RetryableUpload | null>(null);

  const reset = useCallback(() => {
    retryableUploadRef.current = null;
    setState({ status: "idle" });
  }, []);

  const upload = useCallback((file: File, opts: UploadOptions = {}) => {
    retryableUploadRef.current = null;
    setState({ status: "validating" });

    if (!isAllowedUploadMime(file.type)) {
      setState({
        status: "error",
        message: `File type not allowed: ${file.type || "unknown"}`,
      });
      return;
    }
    if (file.size > MAX_SIZE_BYTES) {
      setState({
        status: "error",
        message: `File exceeds ${Math.floor(
          MAX_SIZE_BYTES / 1024 / 1024,
        )} MB limit`,
      });
      return;
    }

    retryableUploadRef.current = {
      file,
      options: { ...opts },
    };
    const fd = new FormData();
    fd.append("file", file, sanitizeFilename(file.name));
    if (opts.practiceId != null && opts.practiceId !== "") {
      fd.append("practice_id", String(opts.practiceId));
    }
    fd.append("document_type", opts.documentType?.trim() || "other");
    if (opts.purpose != null && opts.purpose.trim() !== "") {
      fd.append("document_purpose", opts.purpose.trim());
    }

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/portal/documents/upload");
    xhr.withCredentials = true;

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        setState({
          status: "uploading",
          progress: (e.loaded / e.total) * 100,
        });
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const json = JSON.parse(xhr.responseText);
          const parsed = VaultUploadResponse.parse(json);
          if (!parsed.success) {
            retryableUploadRef.current = null;
            setState({
              status: "error",
              message: parsed.message ?? "Upload rejected",
              httpStatus: xhr.status,
            });
            return;
          }
          retryableUploadRef.current = null;
          setState({
            status: "done",
            file: parsed.data,
          });
        } catch {
          retryableUploadRef.current = null;
          setState({
            status: "error",
            message: "Invalid server response",
            httpStatus: xhr.status,
          });
        }
      } else {
        if (!isRetryableHttpStatus(xhr.status)) {
          retryableUploadRef.current = null;
        }
        setState({
          status: "error",
          message: serverRejectionMessage(xhr.responseText, xhr.status),
          httpStatus: xhr.status,
        });
      }
    };

    xhr.onerror = () => setState({ status: "error", message: "Network error" });

    xhr.send(fd);
  }, []);

  const retry = useCallback(() => {
    const retryableUpload = retryableUploadRef.current;
    if (!retryableUpload) return;
    upload(retryableUpload.file, retryableUpload.options);
  }, [upload]);

  return {
    state,
    upload,
    reset,
    retry,
    canRetry: state.status === "error" && retryableUploadRef.current !== null,
  };
}
