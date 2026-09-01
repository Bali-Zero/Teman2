"use client";

import { FormEvent, useMemo, useState } from "react";
import { useCockpitSession } from "@/lib/cockpit-session-context";

type CaseType = "issuance" | "extension";
type Purpose = "tourism" | "family" | "transit" | "business-meeting";

interface PreviewFormState {
  case_type: CaseType;
  nationality: string;
  entry_date: string;
  passport_expiry_date: string;
  purpose: Purpose;
  travellers: number;
  self_pay: boolean;
  voa_expiry_date: string;
  extension_already_used: boolean;
}

interface InternalCheckpoint {
  label: string;
  at: string;
  kind: string;
  note: null;
}

interface PreviewResult {
  decision: "ACCEPT" | "DECLINE";
  reason_codes: string[];
  case_type: CaseType;
  entry_date: string;
  expiry_date: string;
  computed_stay_end: string;
  expiry_is_estimated: boolean;
  published_filing_deadline: string | null;
  submit_by_date: string | null;
  internal_checkpoints: InternalCheckpoint[];
  price_idr: number | null;
  price_source: string | null;
  price_status: "confirmed" | "unavailable";
  price_warning: string | null;
  calendar_coverage_start: string;
  calendar_coverage_end: string;
  calendar_status: "confirmed" | "uncovered" | "not_applicable";
  calendar_warning: string | null;
  warnings: string[];
}

const VISIBLE_INTERNAL_CHECKPOINTS = new Set(["D-10", "D-3", "D-1"]);

function isoDateOffset(days: number): string {
  const value = new Date();
  value.setUTCHours(12, 0, 0, 0);
  value.setUTCDate(value.getUTCDate() + days);
  return value.toISOString().slice(0, 10);
}

function extensionPreset(travellers: number): PreviewFormState {
  return {
    case_type: "extension",
    nationality: "USA",
    entry_date: isoDateOffset(-14),
    passport_expiry_date: isoDateOffset(400),
    purpose: "tourism",
    travellers,
    self_pay: true,
    voa_expiry_date: isoDateOffset(14),
    extension_already_used: false,
  };
}

function issuancePreset(): PreviewFormState {
  return {
    case_type: "issuance",
    nationality: "USA",
    entry_date: isoDateOffset(10),
    passport_expiry_date: isoDateOffset(400),
    purpose: "tourism",
    travellers: 1,
    self_pay: true,
    voa_expiry_date: "",
    extension_already_used: false,
  };
}

function formatDate(value: string | null): string {
  if (!value) return "Not applicable";
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

function formatIdr(value: number | null): string {
  if (value === null) return "Price unavailable — verify with PricingTool";
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(value);
}

export function GarudaPreviewClient() {
  const { authorization, relock } = useCockpitSession();
  const [form, setForm] = useState<PreviewFormState>(() => extensionPreset(1));
  const [result, setResult] = useState<PreviewResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const visibleInternalCheckpoints = useMemo(
    () =>
      (result?.internal_checkpoints ?? []).filter((checkpoint) =>
        VISIBLE_INTERNAL_CHECKPOINTS.has(checkpoint.label),
      ),
    [result],
  );

  function patchForm(patch: Partial<PreviewFormState>): void {
    setForm((current) => ({ ...current, ...patch }));
    setResult(null);
    setError(null);
  }

  function applyPreset(next: PreviewFormState): void {
    setForm(next);
    setResult(null);
    setError(null);
  }

  async function evaluate(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setResult(null);

    const payload: Record<string, unknown> = {
      case_type: form.case_type,
      nationality: form.nationality.trim().toUpperCase(),
      entry_date: form.entry_date,
      passport_expiry_date: form.passport_expiry_date,
      purpose: form.purpose,
      travellers: form.travellers,
      self_pay: form.self_pay,
      extension_already_used: form.extension_already_used,
    };
    if (form.case_type === "extension") {
      payload.voa_expiry_date = form.voa_expiry_date;
    }

    try {
      const response = await fetch("/api/garuda-voa/evaluate", {
        method: "POST",
        headers: {
          authorization,
          "content-type": "application/json",
        },
        cache: "no-store",
        body: JSON.stringify(payload),
      });
      if (response.status === 401) {
        relock();
        return;
      }
      const json = (await response.json().catch(() => ({}))) as
        PreviewResult | { error?: string };
      if (!response.ok || !("decision" in json)) {
        const code = "error" in json ? json.error : undefined;
        throw new Error(code || `preview_failed_${response.status}`);
      }
      setResult(json);
    } catch (requestError) {
      const code =
        requestError instanceof Error
          ? requestError.message
          : "preview_unavailable";
      setError(`The internal preview could not run (${code}).`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="garuda-shell">
      <header className="garuda-masthead">
        <div className="garuda-boundary">INTERNAL / SYNTHETIC DATA ONLY</div>
        <p className="garuda-eyebrow">Bali Zero operator workbench</p>
        <h1>GARUDA VOA pre-screen</h1>
        <p className="garuda-lede">
          This is a deterministic planning preview, not a client decision and
          not an immigration approval. Use fabricated dates only. Every real
          case still requires document, nationality, entry-point and legal
          verification by the team.
        </p>
      </header>

      <section className="garuda-presets" aria-label="Synthetic presets">
        <span>Synthetic presets</span>
        <button type="button" onClick={() => applyPreset(extensionPreset(1))}>
          Accepted extension
        </button>
        <button type="button" onClick={() => applyPreset(extensionPreset(2))}>
          Declined group
        </button>
        <button type="button" onClick={() => applyPreset(issuancePreset())}>
          Issuance sample
        </button>
      </section>

      <div className="garuda-columns">
        <form className="garuda-card garuda-form" onSubmit={evaluate}>
          <div className="garuda-card-heading">
            <span>01</span>
            <h2>Fabricated intake</h2>
          </div>

          <label>
            Case type
            <select
              value={form.case_type}
              onChange={(event) =>
                patchForm({ case_type: event.target.value as CaseType })
              }
            >
              <option value="issuance">Issuance</option>
              <option value="extension">Extension</option>
            </select>
          </label>

          <label>
            Nationality code (synthetic ISO-3)
            <input
              value={form.nationality}
              onChange={(event) =>
                patchForm({ nationality: event.target.value })
              }
              minLength={3}
              maxLength={3}
              pattern="[A-Za-z]{3}"
              required
            />
          </label>

          <div className="garuda-field-pair">
            <label>
              Fabricated entry date
              <input
                type="date"
                value={form.entry_date}
                onChange={(event) =>
                  patchForm({ entry_date: event.target.value })
                }
                required
              />
            </label>
            <label>
              Fabricated passport expiry
              <input
                type="date"
                value={form.passport_expiry_date}
                onChange={(event) =>
                  patchForm({ passport_expiry_date: event.target.value })
                }
                required
              />
            </label>
          </div>

          {form.case_type === "extension" ? (
            <label>
              Fabricated printed VOA expiry
              <input
                type="date"
                value={form.voa_expiry_date}
                onChange={(event) =>
                  patchForm({ voa_expiry_date: event.target.value })
                }
                required
              />
            </label>
          ) : null}

          <div className="garuda-field-pair">
            <label>
              Purpose
              <select
                value={form.purpose}
                onChange={(event) =>
                  patchForm({ purpose: event.target.value as Purpose })
                }
              >
                <option value="tourism">Tourism</option>
                <option value="family">Family visit</option>
                <option value="transit">Transit</option>
                <option value="business-meeting">Business meeting</option>
              </select>
            </label>
            <label>
              Travellers
              <input
                type="number"
                min={1}
                max={10}
                value={form.travellers}
                onChange={(event) =>
                  patchForm({ travellers: Number(event.target.value) })
                }
                required
              />
            </label>
          </div>

          <label className="garuda-check">
            <input
              type="checkbox"
              checked={form.self_pay}
              onChange={(event) =>
                patchForm({ self_pay: event.target.checked })
              }
            />
            Self-pay synthetic case
          </label>

          {form.case_type === "extension" ? (
            <label className="garuda-check">
              <input
                type="checkbox"
                checked={form.extension_already_used}
                onChange={(event) =>
                  patchForm({ extension_already_used: event.target.checked })
                }
              />
              Extension already used
            </label>
          ) : null}

          <button className="garuda-run" type="submit" disabled={busy}>
            {busy ? "Running real engine..." : "Run internal pre-screen"}
          </button>
          <p className="garuda-privacy-note">
            No GARUDA case payload is persisted. No authentication audit row is
            persisted. The synthetic request exists only for this local process
            invocation.
          </p>
        </form>

        <section className="garuda-card garuda-result" aria-live="polite">
          <div className="garuda-card-heading">
            <span>02</span>
            <h2>Engine result</h2>
          </div>

          {!result && !error ? (
            <div className="garuda-empty">
              Choose a synthetic preset or edit the fabricated fields, then run
              the real Python engine.
            </div>
          ) : null}

          {error ? <div className="garuda-error">{error}</div> : null}

          {result ? (
            <div className="garuda-result-stack">
              <div
                className={`garuda-decision ${result.decision.toLowerCase()}`}
              >
                <span>PRELIMINARY</span>
                <strong>{result.decision}</strong>
              </div>

              <p className="garuda-verification-warning">
                Pre-screen only. A positive result is never approval and never
                replaces inspection of the real passport, visa record or office
                procedure.
              </p>

              {result.reason_codes.length > 0 ? (
                <div>
                  <h3>Neutral reason codes</h3>
                  <ul className="garuda-code-list">
                    {result.reason_codes.map((code) => (
                      <li key={code}>{code}</li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <dl className="garuda-facts">
                <div>
                  <dt>Entry</dt>
                  <dd>{formatDate(result.entry_date)}</dd>
                </div>
                <div>
                  <dt>
                    {result.expiry_is_estimated
                      ? "Computed stay end (estimate)"
                      : "Printed stay end"}
                  </dt>
                  <dd>{formatDate(result.computed_stay_end)}</dd>
                </div>
                {result.case_type === "extension" ? (
                  <div>
                    <dt>Published D-7 filing deadline</dt>
                    <dd>{formatDate(result.published_filing_deadline)}</dd>
                  </div>
                ) : (
                  <div>
                    <dt>Bali Zero submit-by</dt>
                    <dd>{formatDate(result.submit_by_date)}</dd>
                  </div>
                )}
                <div>
                  <dt>Expiry basis</dt>
                  <dd>
                    {result.expiry_is_estimated ? "Estimated" : "Printed"}
                  </dd>
                </div>
              </dl>

              {visibleInternalCheckpoints.length > 0 ? (
                <div>
                  <h3>INTERNAL checkpoints</h3>
                  <div className="garuda-checkpoints">
                    {visibleInternalCheckpoints.map((checkpoint) => (
                      <article key={`${checkpoint.label}-${checkpoint.at}`}>
                        <span>{checkpoint.label}</span>
                        <strong>{formatDate(checkpoint.at)}</strong>
                      </article>
                    ))}
                  </div>
                  <p className="garuda-withheld">
                    The disputed earliest-filing marker is deliberately
                    withheld: the official page gives contradictory
                    formulations, so this workbench does not present a date as
                    settled fact.
                  </p>
                </div>
              ) : null}

              <div className="garuda-price">
                <span>PricingTool result</span>
                <strong>{formatIdr(result.price_idr)}</strong>
                <small>
                  Price status: {result.price_status}
                  {result.price_source ? ` · ${result.price_source}` : null}
                </small>
                {result.price_warning ? (
                  <div className="garuda-warning">{result.price_warning}</div>
                ) : null}
              </div>

              <div className="garuda-calendar">
                <h3>Operating-calendar boundary</h3>
                <p>
                  Verified coverage:{" "}
                  {formatDate(result.calendar_coverage_start)}
                  {" through "}
                  {formatDate(result.calendar_coverage_end)}.
                </p>
                <p>
                  Calendar status: {result.calendar_status.replace("_", " ")}.
                </p>
                {result.calendar_warning ? (
                  <div className="garuda-warning">
                    {result.calendar_warning}
                  </div>
                ) : null}
              </div>

              {result.warnings.length > 0 ? (
                <ul className="garuda-warnings">
                  {result.warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
        </section>
      </div>
    </main>
  );
}
