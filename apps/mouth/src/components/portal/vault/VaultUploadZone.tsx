"use client";
import { useRef, useState, useEffect } from "react";
import { Upload } from "lucide-react";
import { useVaultUpload } from "@/hooks/useVaultUpload";

interface Props {
  practiceId?: number | string | null;
  onDone?: () => void;
}

export function VaultUploadZone({ practiceId, onDone }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [purpose, setPurpose] = useState("");
  const { state, upload, reset } = useVaultUpload();

  useEffect(() => {
    if (state.status === "done") {
      onDone?.();
      const t = setTimeout(() => {
        reset();
        setPurpose("");
      }, 3000);
      return () => clearTimeout(t);
    }
  }, [state, onDone, reset]);

  const handleFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    upload(files[0], { practiceId, purpose });
  };

  return (
    <div className="space-y-2">
      <div>
        <label
          htmlFor="vault-upload-purpose"
          className="block text-[10px] uppercase tracking-[2px] mb-1"
          style={{ color: "var(--bz-copper-text, var(--tx-secondary))" }}
        >
          What is this document for? (optional)
        </label>
        <input
          id="vault-upload-purpose"
          type="text"
          value={purpose}
          maxLength={500}
          onChange={(e) => setPurpose(e.target.value)}
          placeholder="e.g. Passport for KITAS renewal"
          className="w-full rounded-lg border px-3 py-2 text-sm placeholder:text-[var(--text-tertiary,var(--tx-tertiary))] focus:border-[var(--bz-copper)] focus:outline-none"
          style={{
            background: "var(--bz-card)",
            borderColor: "var(--bz-border)",
            color: "var(--bz-text-1)",
          }}
        />
      </div>
      <div
        data-testid="vault-upload-zone"
        data-drag-over={dragOver ? "true" : "false"}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          handleFiles(e.dataTransfer.files);
        }}
        className="rounded-lg border-2 border-dashed p-6 text-center transition"
        style={
          dragOver
            ? {
                borderColor: "var(--bz-copper)",
                background: "var(--glass-rim)",
              }
            : { borderColor: "var(--bz-border-hover)" }
        }
      >
        <Upload
          aria-hidden
          className="w-6 h-6 mx-auto mb-2"
          style={{ color: "var(--bz-copper)" }}
        />
        <p className="text-sm mb-3" style={{ color: "var(--bz-text-2)" }}>
          Drag & drop here, or
        </p>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="text-xs uppercase tracking-[2px] hover:underline"
          style={{ color: "var(--bz-copper-text, var(--tx-secondary))" }}
        >
          Choose file
        </button>
        <input
          ref={inputRef}
          type="file"
          className="sr-only"
          onChange={(e) => handleFiles(e.target.files)}
          aria-label="Choose file to upload"
        />
        {state.status === "uploading" && (
          <p
            role="status"
            className="text-xs mt-3"
            style={{ color: "var(--bz-text-2)" }}
          >
            Uploading… {Math.round(state.progress)}%
          </p>
        )}
        {state.status === "error" && (
          <p
            role="alert"
            className="text-xs mt-3"
            style={{ color: "var(--state-danger)" }}
          >
            {state.message}
          </p>
        )}
        {state.status === "done" && (
          <p
            role="status"
            className="text-xs mt-3"
            style={{ color: "var(--state-success)" }}
          >
            Uploaded: {state.file.name}
            {!state.processing.virus_clean && " (flagged)"}
          </p>
        )}
      </div>
    </div>
  );
}
