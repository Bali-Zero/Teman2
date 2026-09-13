"use client";

/**
 * Client compliance profile panel (U2).
 *
 * Backend: `GET`/`PATCH /api/compliance/obligations/profile/{client_id}` (M3,
 * `compliance_obligations.py`). The engine proposes from the attributes it can
 * read out of `companies.custom_fields`; no client carried them, so every
 * profile collapsed to the defaults and `applies()` proposed the minimum. This
 * panel is where the reviewer fills them in before asking for proposals.
 *
 * Two rules shape the implementation:
 *
 * 1. A save PATCHes ONLY the fields the reviewer touched. The endpoint merges
 *    into the existing JSONB and never removes a key, so sending the whole
 *    computed profile back would write every DEFAULT as if a human had asserted
 *    it — `missing_keys` would come back empty and the "nothing is known about
 *    this client" signal would be destroyed on the first save.
 * 2. Values are validated here against the same domains the endpoint enforces,
 *    so the common mistake costs no round-trip; the server stays the authority
 *    and its 422 detail is shown verbatim when the two disagree.
 *
 * PII: the attributes are client data. They live in component state for the life
 * of the tab, are never logged and are never sent anywhere but the PATCH.
 */

import { useCallback, useMemo, useState } from "react";

import { api } from "@/lib/api";
import { logger } from "@/lib/logger";

import { describeError } from "./describe-error";
import {
  CARD,
  COMPANY_TYPE_OPTIONS,
  INPUT_STYLE,
  INVESTMENT_STAGE_OPTIONS,
  PROFILE_BOOLEAN_FIELDS,
  type ClientProfileAttributes,
  type ProfileOut,
  type ProfilePatch,
} from "./types";
import { useClientProfile } from "./useClientProfile";

/** A 409 here is not the register's "already decided" conflict. */
const SAVE_ERROR_OVERRIDES: Readonly<Record<number, string>> = {
  409: "No company on file for this client. Link a company first — this panel creates nothing.",
};

const INTEGER_RE = /^\d+$/;
const FYE_RE = /^\d{2}-\d{2}$/;

type DraftValue = string | boolean;
type Draft = Record<string, DraftValue>;

function buildPatch(draft: Draft): { patch?: ProfilePatch; error?: string } {
  const patch: Record<string, string | number | boolean> = {};
  for (const [name, raw] of Object.entries(draft)) {
    if (typeof raw === "boolean") {
      patch[name] = raw;
      continue;
    }
    const value = raw.trim();
    if (name === "employee_count" || name === "annual_turnover_idr") {
      if (!INTEGER_RE.test(value)) {
        return { error: `${name} must be a whole number, zero or more.` };
      }
      // JSON carries a double: past 2^53 the number that reaches the endpoint is
      // not the number that was typed, so refuse rather than store a silent
      // rounding of a turnover figure.
      if (!Number.isSafeInteger(Number(value))) {
        return { error: `${name} is too large to store exactly.` };
      }
      patch[name] = Number(value);
      continue;
    }
    if (name === "fiscal_year_end") {
      if (!FYE_RE.test(value)) {
        return { error: "Fiscal year end must be MM-DD, for example 12-31." };
      }
      patch[name] = value;
      continue;
    }
    if (name === "company_type") {
      if (!(COMPANY_TYPE_OPTIONS as readonly string[]).includes(value)) {
        return { error: "Choose one of the listed company types." };
      }
      patch[name] = value;
      continue;
    }
    if (name === "investment_stage") {
      if (value === "") {
        // PATCH only ever SETS a key, so there is no way to go back to "none"
        // from this panel — saying so beats a 422 on an empty string.
        return {
          error:
            "Investment stage cannot be cleared here. Choose construction or commercial.",
        };
      }
      if (!(INVESTMENT_STAGE_OPTIONS as readonly string[]).includes(value)) {
        return { error: "Choose one of the listed investment stages." };
      }
      patch[name] = value;
      continue;
    }
    return { error: `${name} is not an attribute this panel can write.` };
  }
  return { patch };
}

function textValue(
  name: keyof ClientProfileAttributes,
  draft: Draft,
  profile: ClientProfileAttributes,
): string {
  const touched = draft[name];
  if (typeof touched === "string") return touched;
  const current = profile[name];
  return current === null || current === undefined ? "" : String(current);
}

function boolValue(
  name: keyof ClientProfileAttributes,
  draft: Draft,
  profile: ClientProfileAttributes,
): boolean {
  const touched = draft[name];
  return typeof touched === "boolean" ? touched : Boolean(profile[name]);
}

interface FieldProps {
  name: string;
  label: string;
  missing: boolean;
  children: React.ReactNode;
}

/** One attribute row, flagged when the engine read it as a default. */
function Field({ name, label, missing, children }: FieldProps) {
  return (
    <div
      role="group"
      // The "not set" marker is visible text next to the control, which a
      // screen reader moving between fields does not pick up. Naming the GROUP
      // carries it without touching the control's own accessible name (which
      // stays the bare label, so a query for it still resolves to one element).
      aria-label={missing ? `${label}, not set` : `${label}, on file`}
      className="rounded-lg border px-3 py-2"
      data-testid={`profile-field-${name}`}
      data-missing={missing ? "true" : "false"}
      style={{
        borderColor: missing ? "var(--state-warning)" : "var(--bz-border)",
      }}
    >
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <span className="text-xs" style={{ color: "var(--bz-text-3)" }}>
          {label}
        </span>
        {missing && (
          <span className="text-xs" style={{ color: "var(--state-warning)" }}>
            not set
          </span>
        )}
      </div>
      {children}
    </div>
  );
}

interface Props {
  /** Trimmed client filter. The panel is only rendered when it is non-empty. */
  clientId: string;
  /** The page's generate path, offered again once a save lands. */
  onGenerate: (clientId: string) => void;
  generating: boolean;
}

export function ClientProfilePanel({
  clientId,
  onGenerate,
  generating,
}: Props) {
  const { data, loading, error, reload } = useClientProfile(clientId);
  const [draft, setDraft] = useState<Draft>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const missing = useMemo(
    () => new Set(data?.missing_keys ?? []),
    [data?.missing_keys],
  );
  const touchedKeys = Object.keys(draft);

  const set = useCallback((name: string, value: DraftValue) => {
    setSaveError(null);
    setSaved(false);
    setDraft((prev) => ({ ...prev, [name]: value }));
  }, []);

  const handleSave = useCallback(async () => {
    // The snapshot this save is built from. The fields stay editable while the
    // request is open, so on success only the keys that are still AT the value
    // we sent are cleared — an attribute edited again mid-flight stays in the
    // draft instead of vanishing under a "Profile saved" banner.
    const sent = draft;
    const { patch, error: invalid } = buildPatch(sent);
    if (invalid || !patch) {
      setSaveError(invalid ?? "Nothing to save.");
      return;
    }
    setSaving(true);
    setSaveError(null);
    try {
      await api.patch<ProfileOut>(
        `/api/compliance/obligations/profile/${clientId}`,
        patch,
      );
      // Keys only, never values: the values are client data.
      logger.info("obligations client profile saved", {
        component: "ObligationsPage",
        action: "saveClientProfile",
        metadata: { client_id: clientId, keys: Object.keys(patch).sort() },
      });
      setDraft((prev) => {
        const next: Draft = {};
        for (const [name, value] of Object.entries(prev)) {
          if (!(name in sent) || !Object.is(sent[name], value))
            next[name] = value;
        }
        return next;
      });
      setSaved(true);
      await reload();
    } catch (e) {
      logger.warn("obligations client profile save failed", {
        component: "ObligationsPage",
        action: "saveClientProfile",
        metadata: { client_id: clientId, keys: Object.keys(patch).sort() },
      });
      setSaveError(
        describeError(
          e,
          "Could not save the client profile.",
          SAVE_ERROR_OVERRIDES,
        ),
      );
    } finally {
      setSaving(false);
    }
  }, [clientId, draft, reload]);

  const profile = data?.profile;

  return (
    <section
      className="mb-6 rounded-xl border p-4"
      style={CARD}
      aria-label="Client profile"
    >
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2
          className="text-lg font-medium"
          style={{ color: "var(--bz-text-1)" }}
        >
          Client profile — client {clientId}
        </h2>
        {data && (
          <span className="text-xs" style={{ color: "var(--bz-text-3)" }}>
            {data.missing_keys.length} of{" "}
            {data.missing_keys.length + data.present_keys.length} attributes not
            set
          </span>
        )}
      </div>

      <p className="mb-3 text-xs" style={{ color: "var(--bz-text-3)" }}>
        These attributes decide which rules apply. An attribute marked “not set”
        is sitting at its default, so the register proposes the minimum for it.
      </p>

      {loading && !profile && (
        <p style={{ color: "var(--bz-text-3)" }}>Loading the profile…</p>
      )}

      {error && (
        <p
          className="text-sm"
          role="alert"
          style={{ color: "var(--state-danger)" }}
        >
          {error}
        </p>
      )}

      {profile && data && (
        <>
          {data.company_type_raw && (
            <p className="mb-2 text-xs" style={{ color: "var(--bz-text-3)" }}>
              Company type on file: <strong>{data.company_type_raw}</strong>
            </p>
          )}
          {data.needs_manual_classification && (
            <div
              className="mb-3 rounded-md border px-3 py-2 text-sm"
              role="alert"
              style={{
                borderColor: "var(--state-warning)",
                color: "var(--bz-text-1)",
              }}
            >
              Company type reads as OTHER, so LKPM, PPh 25, SPT Tahunan Badan
              and RUPS are skipped. Set the company type below before
              generating.
            </div>
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            <Field
              name="company_type"
              label="Company type"
              missing={missing.has("company_type")}
            >
              <select
                aria-label="Company type"
                className="block w-full rounded border px-2 py-1.5 text-sm"
                style={INPUT_STYLE}
                value={textValue("company_type", draft, profile)}
                onChange={(e) => set("company_type", e.target.value)}
              >
                {COMPANY_TYPE_OPTIONS.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </Field>

            <Field
              name="investment_stage"
              label="Investment stage"
              missing={missing.has("investment_stage")}
            >
              <select
                aria-label="Investment stage"
                className="block w-full rounded border px-2 py-1.5 text-sm"
                style={INPUT_STYLE}
                value={textValue("investment_stage", draft, profile)}
                onChange={(e) => set("investment_stage", e.target.value)}
              >
                <option value="">none</option>
                {INVESTMENT_STAGE_OPTIONS.map((stage) => (
                  <option key={stage} value={stage}>
                    {stage}
                  </option>
                ))}
              </select>
            </Field>

            <Field
              name="employee_count"
              label="Employee count"
              missing={missing.has("employee_count")}
            >
              <input
                type="number"
                min={0}
                aria-label="Employee count"
                className="block w-full rounded border px-2 py-1.5 text-sm"
                style={INPUT_STYLE}
                value={textValue("employee_count", draft, profile)}
                onChange={(e) => set("employee_count", e.target.value)}
              />
            </Field>

            <Field
              name="annual_turnover_idr"
              label="Annual turnover (IDR)"
              missing={missing.has("annual_turnover_idr")}
            >
              <input
                type="number"
                min={0}
                aria-label="Annual turnover (IDR)"
                className="block w-full rounded border px-2 py-1.5 text-sm"
                style={INPUT_STYLE}
                value={textValue("annual_turnover_idr", draft, profile)}
                onChange={(e) => set("annual_turnover_idr", e.target.value)}
              />
            </Field>

            <Field
              name="fiscal_year_end"
              label="Fiscal year end (MM-DD)"
              missing={missing.has("fiscal_year_end")}
            >
              <input
                type="text"
                aria-label="Fiscal year end (MM-DD)"
                placeholder="12-31"
                className="block w-full rounded border px-2 py-1.5 text-sm"
                style={INPUT_STYLE}
                value={textValue("fiscal_year_end", draft, profile)}
                onChange={(e) => set("fiscal_year_end", e.target.value)}
              />
            </Field>
          </div>

          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {PROFILE_BOOLEAN_FIELDS.map(([name, label]) => (
              <Field
                key={name}
                name={name}
                label={label}
                missing={missing.has(name)}
              >
                <label
                  className="flex items-center gap-2 text-sm"
                  style={{ color: "var(--bz-text-2)" }}
                >
                  <input
                    type="checkbox"
                    aria-label={label}
                    checked={boolValue(name, draft, profile)}
                    onChange={(e) => set(name, e.target.checked)}
                  />
                  {boolValue(name, draft, profile) ? "yes" : "no"}
                </label>
              </Field>
            ))}
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button
              type="button"
              disabled={saving || touchedKeys.length === 0}
              onClick={() => void handleSave()}
              className="rounded-md px-4 py-2 text-sm font-medium text-white"
              style={{
                background: "var(--bz-accent)",
                opacity: saving || touchedKeys.length === 0 ? 0.6 : 1,
              }}
            >
              {saving ? "Saving…" : "Save profile"}
            </button>
            <span className="text-xs" style={{ color: "var(--bz-text-3)" }}>
              {touchedKeys.length === 0
                ? "No change to save."
                : `Saving ${touchedKeys.length} changed attribute${
                    touchedKeys.length === 1 ? "" : "s"
                  }.`}
            </span>
          </div>

          {saveError && (
            <p
              className="mt-2 text-sm"
              role="alert"
              style={{ color: "var(--state-danger)" }}
            >
              {saveError}
            </p>
          )}

          {saved && (
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <span
                className="text-sm"
                role="status"
                style={{ color: "var(--bz-text-2)" }}
              >
                Profile saved. Generate proposals to apply it.
              </span>
              <button
                type="button"
                disabled={generating}
                onClick={() => onGenerate(clientId)}
                className="rounded-md border px-3 py-1.5 text-sm"
                style={{
                  borderColor: "var(--bz-border)",
                  color: "var(--bz-text-2)",
                }}
              >
                {generating
                  ? "Generating…"
                  : `Generate proposals for client ${clientId}`}
              </button>
            </div>
          )}
        </>
      )}
    </section>
  );
}
