'use client';

import React, { useReducer, useRef, useCallback } from 'react';
import {
  Camera,
  Loader2,
  CheckCircle,
  AlertTriangle,
  ShieldAlert,
  XCircle,
  Upload,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { PassportOcrResult } from '@/lib/api/crm/crm.types';
import { api } from '@/lib/api';
import type { CreateClientInput } from '@/lib/api/crm/crm.schemas';
import { COMMON_NATIONALITIES } from '@/lib/api/crm/crm.types';
import { logger } from '@/lib/logger';

// ============================================
// Props
// ============================================

interface PassportScanSectionProps {
  onFieldsConfirmed: (fields: Partial<CreateClientInput>, file: string) => void;
  onDiscarded: () => void;
}

// ============================================
// State Machine Types
// ============================================

/** OCR-extractable field keys (applied to the form on confirm) */
const OCR_FIELDS = [
  'full_name',
  'nationality',
  'date_of_birth',
  'gender',
  'passport_number',
  'passport_expiry',
] as const;

type OcrFieldKey = (typeof OCR_FIELDS)[number];

/** Read-only name component fields shown for verification (not applied to form) */
const NAME_COMPONENT_FIELDS = ['given_names', 'surname'] as const;
type NameComponentKey = (typeof NAME_COMPONENT_FIELDS)[number];

/** Human-readable labels for each OCR field */
const FIELD_LABELS: Record<OcrFieldKey | NameComponentKey, string> = {
  full_name: 'Full Name',
  given_names: 'Given Names',
  surname: 'Surname',
  nationality: 'Nationality',
  date_of_birth: 'Date of Birth',
  gender: 'Gender',
  passport_number: 'Passport Number',
  passport_expiry: 'Expiry Date',
};

type ScanState =
  | { step: 'idle' }
  | { step: 'consent'; file: string; mimeType: string }
  | { step: 'uploading' }
  | { step: 'processing' }
  | { step: 'preview'; result: PassportOcrResult; file: string; checked: Record<string, boolean> }
  | { step: 'confirmed' }
  | { step: 'discarded' }
  | { step: 'error'; message: string };

type ScanAction =
  | { type: 'FILE_SELECTED'; file: string; mimeType: string }
  | { type: 'CONSENT_ACCEPTED' }
  | { type: 'CONSENT_CANCELLED' }
  | { type: 'PROCESSING' }
  | { type: 'OCR_SUCCESS'; result: PassportOcrResult; file: string }
  | { type: 'OCR_FAIL'; message: string }
  | { type: 'TOGGLE_FIELD'; field: string }
  | { type: 'CONFIRMED' }
  | { type: 'DISCARDED' }
  | { type: 'RESET' };

function scanReducer(state: ScanState, action: ScanAction): ScanState {
  switch (action.type) {
    case 'FILE_SELECTED':
      return { step: 'consent', file: action.file, mimeType: action.mimeType };
    case 'CONSENT_ACCEPTED':
      return { step: 'processing' };
    case 'CONSENT_CANCELLED':
      return { step: 'idle' };
    case 'PROCESSING':
      return { step: 'processing' };
    case 'OCR_SUCCESS': {
      // Initialize all non-null fields as checked
      const checked: Record<string, boolean> = {};
      for (const key of OCR_FIELDS) {
        if (action.result[key] != null) {
          checked[key] = true;
        }
      }
      // Uncheck nationality if not in COMMON_NATIONALITIES dropdown
      const nat = action.result.nationality;
      if (nat && !(COMMON_NATIONALITIES as readonly string[]).includes(nat)) {
        checked['nationality'] = false;
      }
      return { step: 'preview', result: action.result, file: action.file, checked };
    }
    case 'OCR_FAIL':
      return { step: 'error', message: action.message };
    case 'TOGGLE_FIELD':
      if (state.step !== 'preview') return state;
      return {
        ...state,
        checked: {
          ...state.checked,
          [action.field]: !state.checked[action.field],
        },
      };
    case 'CONFIRMED':
      return { step: 'confirmed' };
    case 'DISCARDED':
      return { step: 'discarded' };
    case 'RESET':
      return { step: 'idle' };
    default:
      return state;
  }
}

// ============================================
// Helpers
// ============================================

/** Convert file to base64 data URL, strip the prefix */
function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      // Strip data:image/...;base64, prefix
      const base64 = result.split(',')[1] ?? result;
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

/** Format gender "M"/"F" to human-readable */
function formatGender(value: string | null): string {
  if (value === 'M') return 'Male';
  if (value === 'F') return 'Female';
  return value ?? '';
}

/** Get display value for an OCR field */
function getDisplayValue(key: OcrFieldKey, result: PassportOcrResult): string {
  const raw = result[key];
  if (raw == null) return '';
  if (key === 'gender') return formatGender(raw as string);
  return String(raw);
}

// ============================================
// Component
// ============================================

export function PassportScanSection({ onFieldsConfirmed, onDiscarded }: PassportScanSectionProps) {
  const [state, dispatch] = useReducer(scanReducer, { step: 'idle' });
  const fileInputRef = useRef<HTMLInputElement>(null);
  // Keep consent data in a ref so it survives across reducer transitions
  const consentDataRef = useRef<{ file: string; mimeType: string } | null>(null);

  // ------------------------------------------
  // File selection
  // ------------------------------------------
  const handleFileChange = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate type
    if (!['image/jpeg', 'image/png'].includes(file.type)) {
      dispatch({ type: 'OCR_FAIL', message: 'Only JPG and PNG files are supported.' });
      return;
    }

    // Validate size (10 MB)
    if (file.size > 10 * 1024 * 1024) {
      dispatch({ type: 'OCR_FAIL', message: 'File is too large. Maximum size is 10 MB.' });
      return;
    }

    try {
      const base64 = await fileToBase64(file);
      consentDataRef.current = { file: base64, mimeType: file.type };
      dispatch({ type: 'FILE_SELECTED', file: base64, mimeType: file.type });
    } catch (err) {
      logger.error(
        'Failed to read passport file',
        { component: 'PassportScanSection', action: 'fileToBase64' },
        err instanceof Error ? err : new Error(String(err)),
      );
      dispatch({ type: 'OCR_FAIL', message: 'Failed to read the file. Please try again.' });
    }

    // Reset file input so re-selecting the same file triggers onChange
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, []);

  // ------------------------------------------
  // OCR call
  // ------------------------------------------
  const runOcr = useCallback(async () => {
    const data = consentDataRef.current;
    if (!data) return;

    dispatch({ type: 'PROCESSING' });

    try {
      // Call backend API (Ollama → Gemini fallback, works everywhere)
      const result = await api.crm.extractPassportPreview(data.file, data.mimeType);

      if (result.success && result.confidence >= 0.7) {
        dispatch({ type: 'OCR_SUCCESS', result, file: data.file });
      } else if (result.success && result.confidence < 0.7) {
        dispatch({
          type: 'OCR_FAIL',
          message: 'Photo quality too low — please try a clearer photo with good lighting.',
        });
      } else {
        dispatch({
          type: 'OCR_FAIL',
          message: result.message ?? 'Failed to extract passport data.',
        });
      }
    } catch (err) {
      logger.error(
        'Passport OCR request failed',
        { component: 'PassportScanSection', action: 'extractPassportPreview' },
        err instanceof Error ? err : new Error(String(err)),
      );
      dispatch({
        type: 'OCR_FAIL',
        message: 'Network error — please check your connection and try again.',
      });
    }
  }, []);

  // ------------------------------------------
  // Confirm (Apply selected)
  // ------------------------------------------
  const handleConfirm = useCallback(() => {
    if (state.step !== 'preview') return;

    const { result, file, checked } = state;
    const fields: Partial<CreateClientInput> = {};

    for (const key of OCR_FIELDS) {
      if (!checked[key] || result[key] == null) continue;

      // Nationality validation
      if (key === 'nationality') {
        const nat = result[key] as string;
        if (!(COMMON_NATIONALITIES as readonly string[]).includes(nat)) {
          logger.warn('OCR nationality not in COMMON_NATIONALITIES, skipping', {
            component: 'PassportScanSection',
            action: 'handleConfirm',
            metadata: { nationality: nat },
          });
          continue;
        }
      }

      // Map OCR keys directly — they match CreateClientInput keys
      (fields as Record<string, unknown>)[key] = result[key];
    }

    onFieldsConfirmed(fields, file);
    dispatch({ type: 'CONFIRMED' });
  }, [state, onFieldsConfirmed]);

  // ------------------------------------------
  // Discard
  // ------------------------------------------
  const handleDiscard = useCallback(() => {
    dispatch({ type: 'DISCARDED' });
    onDiscarded();
  }, [onDiscarded]);

  // ------------------------------------------
  // Render helpers
  // ------------------------------------------

  /** Upload zone (idle / discarded) */
  const renderUploadZone = () => (
    <div
      className="rounded-lg border-2 border-dashed border-[var(--border)] bg-[var(--background-elevated)] p-8 text-center cursor-pointer hover:border-[var(--accent)] transition-colors"
      onClick={() => fileInputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        e.stopPropagation();
      }}
      onDrop={(e) => {
        e.preventDefault();
        e.stopPropagation();
        const file = e.dataTransfer.files[0];
        if (file && fileInputRef.current) {
          // Create a synthetic event-like data transfer
          const dt = new DataTransfer();
          dt.items.add(file);
          fileInputRef.current.files = dt.files;
          fileInputRef.current.dispatchEvent(new Event('change', { bubbles: true }));
        }
      }}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          fileInputRef.current?.click();
        }
      }}
      aria-label="Upload passport photo"
    >
      <Camera className="w-10 h-10 mx-auto mb-3 text-[var(--foreground-muted)]" />
      <p className="text-sm font-medium text-[var(--foreground)]">
        Drop passport photo or click to browse
      </p>
      <p className="text-xs text-[var(--foreground-muted)] mt-1">JPG, PNG — max 10 MB</p>
      <p className="text-xs text-[var(--foreground-muted)] mt-3 italic">
        Or skip and fill fields manually below
      </p>
      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png"
        capture="environment"
        className="hidden"
        onChange={handleFileChange}
      />
    </div>
  );

  /** Consent prompt */
  const renderConsent = () => (
    <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-5 space-y-4">
      <div className="flex items-start gap-3">
        <ShieldAlert className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-medium text-[var(--foreground)]">AI Processing Consent</p>
          <p className="text-xs text-[var(--foreground-muted)] mt-1">
            Passport data will be processed by AI to extract information. No data is stored until you
            create the client.
          </p>
        </div>
      </div>
      <div className="flex gap-3 justify-end">
        <Button
          variant="outline"
          size="sm"
          onClick={() => dispatch({ type: 'CONSENT_CANCELLED' })}
        >
          Cancel
        </Button>
        <Button size="sm" onClick={runOcr}>
          Continue
        </Button>
      </div>
    </div>
  );

  /** Processing spinner */
  const renderProcessing = () => (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-8 text-center">
      <Loader2 className="w-8 h-8 mx-auto mb-3 text-[var(--accent)] animate-spin" />
      <p className="text-sm text-[var(--foreground)]">Analyzing passport... this may take a few seconds</p>
    </div>
  );

  /** Preview with per-field checkboxes */
  const renderPreview = () => {
    if (state.step !== 'preview') return null;
    const { result, checked } = state;

    // Only show fields that have a non-null value
    const availableFields = OCR_FIELDS.filter((key) => result[key] != null);
    const hasChecked = availableFields.some((key) => checked[key]);

    return (
      <div className="rounded-lg border border-green-500/30 bg-green-500/5 p-5 space-y-4">
        {/* Header */}
        <div className="flex items-center gap-2">
          <CheckCircle className="w-5 h-5 text-green-400" />
          <p className="text-sm font-medium text-[var(--foreground)]">Passport Data Extracted</p>
        </div>

        {/* Name components (read-only verify) — shown when OCR returned them */}
        {(result.given_names || result.surname) && (
          <div className="rounded-md border border-[var(--border)] bg-[var(--background-elevated)]/50 p-3 space-y-1">
            <p className="text-xs text-[var(--foreground-muted)] mb-1">
              Verify name attribution from passport
            </p>
            {NAME_COMPONENT_FIELDS.map((key) =>
              result[key] ? (
                <div key={key} className="flex items-center gap-3 px-1">
                  <span className="text-xs text-[var(--foreground-muted)] w-28 flex-shrink-0">
                    {FIELD_LABELS[key]}
                  </span>
                  <span className="text-sm text-[var(--foreground)] font-medium">
                    {result[key]}
                  </span>
                </div>
              ) : null,
            )}
          </div>
        )}

        {/* Fields */}
        <div className="space-y-2">
          {availableFields.map((key) => (
            <label
              key={key}
              className="flex items-center gap-3 p-2 rounded-lg hover:bg-[var(--background-elevated)] transition-colors cursor-pointer"
            >
              <input
                type="checkbox"
                checked={checked[key] ?? false}
                onChange={() => dispatch({ type: 'TOGGLE_FIELD', field: key })}
                className="w-4 h-4 rounded border-[var(--border)] text-[var(--accent)] focus:ring-[var(--accent)] accent-[var(--accent)]"
              />
              <span className="text-xs text-[var(--foreground-muted)] w-28 flex-shrink-0">
                {FIELD_LABELS[key]}
              </span>
              <span className="text-sm text-[var(--foreground)] font-medium">
                {getDisplayValue(key, result)}
              </span>
              {key === 'nationality' && !checked[key] && result.nationality && (
                <span className="text-xs text-amber-400 ml-1">(not in dropdown — fill manually)</span>
              )}
            </label>
          ))}
        </div>

        {/* Warnings */}
        {result.warnings && result.warnings.length > 0 && (
          <div className="space-y-1 pt-2">
            {result.warnings.map((warning, i) => (
              <div key={i} className="flex items-start gap-2">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-amber-400">{warning}</p>
              </div>
            ))}
          </div>
        )}

        {/* Hint */}
        <p className="text-xs text-[var(--foreground-muted)] italic">
          Uncheck fields you want to fill manually
        </p>

        {/* Actions */}
        <div className="flex gap-3 justify-end pt-2">
          <Button variant="outline" size="sm" onClick={handleDiscard}>
            Discard all
          </Button>
          <Button size="sm" onClick={handleConfirm} disabled={!hasChecked}>
            Apply selected
          </Button>
        </div>
      </div>
    );
  };

  /** Confirmed state */
  const renderConfirmed = () => (
    <div className="rounded-lg border border-green-500/30 bg-green-500/5 p-4 flex items-center gap-3">
      <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0" />
      <div>
        <p className="text-sm font-medium text-[var(--foreground)]">Passport data applied to form</p>
        <p className="text-xs text-[var(--foreground-muted)]">
          — passport will be saved on submit
        </p>
      </div>
    </div>
  );

  /** Error state */
  const renderError = () => {
    if (state.step !== 'error') return null;
    return (
      <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-5 space-y-4">
        <div className="flex items-start gap-3">
          <XCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-red-400">{state.message}</p>
        </div>
        <div className="flex gap-3 justify-end">
          <Button variant="outline" size="sm" onClick={() => dispatch({ type: 'DISCARDED' })}>
            Fill manually
          </Button>
          <Button
            size="sm"
            onClick={() => {
              dispatch({ type: 'RESET' });
            }}
          >
            Try another photo
          </Button>
        </div>
      </div>
    );
  };

  // ------------------------------------------
  // Main render
  // ------------------------------------------
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-5 mb-5">
      <div className="flex items-center gap-2 mb-4">
        <Upload className="w-4 h-4 text-[var(--accent)]" />
        <h3 className="text-sm font-semibold text-[var(--foreground)]">Passport Scan</h3>
      </div>

      {(state.step === 'idle' || state.step === 'discarded') && renderUploadZone()}
      {state.step === 'consent' && renderConsent()}
      {(state.step === 'uploading' || state.step === 'processing') && renderProcessing()}
      {state.step === 'preview' && renderPreview()}
      {state.step === 'confirmed' && renderConfirmed()}
      {state.step === 'error' && renderError()}
    </div>
  );
}

export default PassportScanSection;
