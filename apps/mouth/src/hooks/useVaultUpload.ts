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
          message: `Upload failed (${xhr.status})`,
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
