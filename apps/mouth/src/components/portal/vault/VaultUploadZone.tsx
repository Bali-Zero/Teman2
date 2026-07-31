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
          className="block text-[10px] uppercase tracking-[2px] text-[var(--bz-text-3)] mb-1"
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
          className="w-full rounded-lg border border-[var(--bz-border)] bg-[var(--bz-card)] px-3 py-2 text-sm text-[var(--bz-text-1)] placeholder:text-[var(--bz-text-3)] focus:border-[var(--bz-focus-ring)] focus:outline-none"
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
        className={`rounded-lg border-2 border-dashed p-6 text-center transition ${
          dragOver
            ? "border-[var(--bz-copper-text)] bg-[var(--surface-raised)]"
            : "border-[var(--bz-border-hover)]"
        }`}
      >
        <Upload
          aria-hidden
          className="w-6 h-6 mx-auto text-[var(--bz-accent-warm)] mb-2"
        />
        <p className="text-sm text-[var(--bz-text-2)] mb-3">
          Drag & drop here, or
        </p>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="text-xs uppercase tracking-[2px] text-[var(--bz-copper-text)] hover:underline"
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
          <p role="status" className="text-xs text-[var(--bz-text-2)] mt-3">
            Uploading… {Math.round(state.progress)}%
          </p>
        )}
        {state.status === "error" && (
          <p role="alert" className="text-xs text-[var(--state-danger)] mt-3">
            {state.message}
          </p>
        )}
        {state.status === "done" && (
          <p role="status" className="text-xs text-[var(--state-success)] mt-3">
            Uploaded: {state.file.name}
            {!state.processing.virus_clean && " (flagged)"}
          </p>
        )}
      </div>
    </div>
  );
}
