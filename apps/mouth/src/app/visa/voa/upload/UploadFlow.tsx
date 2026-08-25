"use client";

import { useRef, useState } from "react";
import { useDocumentUpload } from "./useDocumentUpload";
import {
  CHECKLIST_ITEMS,
  COPY_LOW_CONFIDENCE_INSTRUCTION,
  COPY_UNREADABLE_INSTRUCTION,
  FIELD_LABELS,
} from "./messages";
import type { ReviewField, UncertainReviewField } from "./types";

/**
 * Deliberately minimal, functional styling — plain Tailwind, no custom theme. Visual
 * identity for `/visa/voa/**` is L6's territory (blocked on owner decision 5); this lane
 * is scoped to `upload/` and to the UX/functional correctness of the upload step, not
 * final branding. L6 restyles this page without needing to touch its logic.
 */
export interface UploadFlowProps {
  resultId: string;
  /** Fires when the customer confirms a resolved set of fields (from either the
   * high-confidence or the corrected low-confidence path), carrying the final
   * customer-edited values keyed by field name. This lane stops here — moving to
   * checkout is `POST /api/visa/voa/orders`, owned by L3 (checkout+orders); a parent
   * component wires that call so this one never has to know about order/payment state.
   */
  onConfirmed?: (values: Record<string, string>) => void;
}

export function UploadFlow({ resultId, onConfirmed }: UploadFlowProps) {
  const { state, selectFile, retryUpload, reset } = useDocumentUpload(resultId);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (fileInputRef.current) fileInputRef.current.value = "";
    if (!file) return;
    setPreviewUrl((old) => {
      if (old) URL.revokeObjectURL(old);
      return URL.createObjectURL(file);
    });
    selectFile(file);
  }

  function handleRetake() {
    setPreviewUrl((old) => {
      if (old) URL.revokeObjectURL(old);
      return null;
    });
    reset();
    fileInputRef.current?.click();
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col gap-6 p-6">
      <h1 className="text-xl font-semibold text-gray-900">
        Upload your passport
      </h1>

      <Checklist />

      {previewUrl && (
        // eslint-disable-next-line @next/next/no-img-element -- transient local object URL, not a remote/optimizable asset
        <img
          src={previewUrl}
          alt="Selected passport photo preview"
          className="w-full rounded-lg border border-gray-200 object-contain"
        />
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        capture="environment"
        className="hidden"
        onChange={handleFileChange}
        aria-label="Upload passport photo"
      />

      <StateView
        state={state}
        onPickFile={() => fileInputRef.current?.click()}
        onRetake={handleRetake}
        onRetry={retryUpload}
        onConfirmed={onConfirmed}
      />
    </main>
  );
}

function Checklist() {
  return (
    <ul className="flex flex-col gap-2 rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-700">
      {CHECKLIST_ITEMS.map((item) => (
        <li key={item} className="flex gap-2">
          <span aria-hidden="true">•</span>
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

function StateView({
  state,
  onPickFile,
  onRetake,
  onRetry,
  onConfirmed,
}: {
  state: ReturnType<typeof useDocumentUpload>["state"];
  onPickFile: () => void;
  onRetake: () => void;
  onRetry: () => void;
  onConfirmed?: (values: Record<string, string>) => void;
}) {
  switch (state.step) {
    case "idle":
      return <PickButton label="Take or choose a photo" onClick={onPickFile} />;

    case "client_rejected":
      return (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-red-600">{state.message}</p>
          <PickButton label="Choose a different photo" onClick={onPickFile} />
        </div>
      );

    case "uploading":
      return (
        <p aria-live="polite" className="text-sm text-gray-600">
          Reading your passport…
        </p>
      );

    case "ready":
      return <ReadyReview fields={state.fields} onConfirmed={onConfirmed} />;

    case "low_confidence":
      return (
        <LowConfidenceReview
          uncertainFields={state.uncertainFields}
          onRetake={onRetake}
          onConfirmed={onConfirmed}
        />
      );

    case "unreadable":
      return (
        <div className="flex flex-col gap-3" aria-live="polite">
          <p className="text-sm text-red-600">{COPY_UNREADABLE_INSTRUCTION}</p>
          <PickButton label="Retake photo" onClick={onRetake} />
        </div>
      );

    case "error":
      return (
        <div className="flex flex-col gap-3" aria-live="polite">
          <p className="text-sm text-red-600">{state.message}</p>
          {state.retryable && (
            <button
              type="button"
              onClick={onRetry}
              className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white"
            >
              Try again
            </button>
          )}
        </div>
      );

    default:
      return null;
  }
}

function PickButton({
  label,
  onClick,
}: {
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-md bg-gray-900 px-4 py-3 text-sm font-medium text-white"
    >
      {label}
    </button>
  );
}

function ReadyReview({
  fields,
  onConfirmed,
}: {
  fields: ReviewField[];
  onConfirmed?: (values: Record<string, string>) => void;
}) {
  // Contract note: these values ARE what local OCR read with high confidence — but
  // `confirmation_required` is true for every field the server sends (service.py never
  // marks a field as not needing confirmation), so this is always presented as editable,
  // never auto-accepted. "review + pay" per the product framing — the customer always
  // sees and can correct what was read before it goes anywhere else.
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(fields.map((f) => [f.field_path, f.value])),
  );

  return (
    <form
      className="flex flex-col gap-4"
      aria-live="polite"
      onSubmit={(e) => {
        e.preventDefault();
        onConfirmed?.(values);
      }}
    >
      <p className="text-sm text-gray-700">
        Please confirm these details match your passport:
      </p>
      {fields.map((field) => (
        <label key={field.field_path} className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-gray-900">
            {FIELD_LABELS[field.field_path]}
          </span>
          <input
            type="text"
            value={values[field.field_path] ?? ""}
            onChange={(e) =>
              setValues((v) => ({ ...v, [field.field_path]: e.target.value }))
            }
            className="rounded-md border border-gray-300 px-3 py-2"
          />
        </label>
      ))}
      <button
        type="submit"
        className="rounded-md bg-gray-900 px-4 py-3 text-sm font-medium text-white"
      >
        Confirm and continue
      </button>
    </form>
  );
}

function LowConfidenceReview({
  uncertainFields,
  onRetake,
  onConfirmed,
}: {
  uncertainFields: UncertainReviewField[];
  onRetake: () => void;
  onConfirmed?: (values: Record<string, string>) => void;
}) {
  // Contract note: `UncertainReviewField` carries NO extracted value — the server never
  // sends a low-confidence guess to the client (uncertain-ocr.feature: "no uncertain
  // value is silently accepted as verified"). Every field here starts genuinely empty;
  // the customer types it or retakes the photo.
  const [values, setValues] = useState<Record<string, string>>({});
  const allFilled = uncertainFields.every(
    (f) => (values[f.field_path] ?? "").trim().length > 0,
  );

  return (
    <form
      className="flex flex-col gap-4"
      aria-live="polite"
      onSubmit={(e) => {
        e.preventDefault();
        if (allFilled) onConfirmed?.(values);
      }}
    >
      <p className="text-sm text-amber-700">
        {COPY_LOW_CONFIDENCE_INSTRUCTION}
      </p>
      {uncertainFields.map((field) => (
        <label key={field.field_path} className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-gray-900">
            {FIELD_LABELS[field.field_path]}
          </span>
          <input
            type="text"
            placeholder="Enter this field"
            value={values[field.field_path] ?? ""}
            onChange={(e) =>
              setValues((v) => ({ ...v, [field.field_path]: e.target.value }))
            }
            className="rounded-md border border-amber-400 px-3 py-2"
          />
        </label>
      ))}
      <div className="flex gap-3">
        <button
          type="submit"
          disabled={!allFilled}
          className="rounded-md bg-gray-900 px-4 py-3 text-sm font-medium text-white disabled:opacity-50"
        >
          Confirm and continue
        </button>
        <button
          type="button"
          onClick={onRetake}
          className="rounded-md border border-gray-300 px-4 py-3 text-sm font-medium text-gray-700"
        >
          Retake photo instead
        </button>
      </div>
    </form>
  );
}
