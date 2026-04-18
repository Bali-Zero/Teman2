"use client";

import { useCallback, useState } from "react";
import { sanitizeFilename } from "@/lib/vault/sanitizeFilename";
import { MAX_SIZE_BYTES, isAllowedUploadMime } from "@/lib/vault/uploadLimits";
import {
  VaultUploadResponse,
  type VaultUploadedFile,
  type VaultUploadProcessing,
} from "@/lib/schemas/vault";

export type UploadState =
  | { status: "idle" }
  | { status: "validating" }
  | { status: "uploading"; progress: number }
  | {
      status: "done";
      file: VaultUploadedFile;
      processing: VaultUploadProcessing;
    }
  | { status: "error"; message: string; httpStatus?: number };

export interface UploadOptions {
  practiceId?: number | string | null;
  documentType?: string;
}

/**
 * Uploads a single file to `POST /api/portal/documents/upload` via
 * `XMLHttpRequest` (required for progress events — `fetch` has no upload
 * progress in browsers).
 *
 * Pre-flight validation rejects disallowed MIME types and oversize files
 * before opening the request. The upload response is Zod-validated; the
 * returned `processing` block surfaces `virus_clean`, `ocr_pages`, and
 * `drive_uploaded` for the UI to display.
 */
export function useVaultUpload() {
  const [state, setState] = useState<UploadState>({ status: "idle" });

  const reset = useCallback(() => setState({ status: "idle" }), []);

  const upload = useCallback((file: File, opts: UploadOptions = {}) => {
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

    const fd = new FormData();
    fd.append("file", file, sanitizeFilename(file.name));
    if (opts.practiceId != null && opts.practiceId !== "") {
      fd.append("practice_id", String(opts.practiceId));
    }
    if (opts.documentType) {
      fd.append("document_type", opts.documentType);
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
            setState({
              status: "error",
              message: parsed.message ?? "Upload rejected",
              httpStatus: xhr.status,
            });
            return;
          }
          setState({
            status: "done",
            file: parsed.data,
            processing: parsed.data.processing,
          });
        } catch {
          setState({
            status: "error",
            message: "Invalid server response",
            httpStatus: xhr.status,
          });
        }
      } else {
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

  return { state, upload, reset };
}
