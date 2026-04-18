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
  const { state, upload, reset } = useVaultUpload();

  useEffect(() => {
    if (state.status === "done") {
      onDone?.();
      const t = setTimeout(reset, 3000);
      return () => clearTimeout(t);
    }
  }, [state, onDone, reset]);

  const handleFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    upload(files[0], { practiceId });
  };

  return (
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
        dragOver ? "border-[#d4845a] bg-white/5" : "border-white/20"
      }`}
    >
      <Upload aria-hidden className="w-6 h-6 mx-auto text-[#c9a96e]/60 mb-2" />
      <p className="text-sm text-[#c9a96e]/70 mb-3">Drag & drop here, or</p>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        className="text-xs uppercase tracking-[2px] text-[#d4845a] hover:underline"
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
        <p role="status" className="text-xs text-[#c9a96e]/60 mt-3">
          Uploading… {Math.round(state.progress)}%
        </p>
      )}
      {state.status === "error" && (
        <p role="alert" className="text-xs text-[#c94a4a] mt-3">
          {state.message}
        </p>
      )}
      {state.status === "done" && (
        <p role="status" className="text-xs text-[#4a9c5c] mt-3">
          Uploaded: {state.file.name}
          {!state.processing.virus_clean && " (flagged)"}
        </p>
      )}
    </div>
  );
}
