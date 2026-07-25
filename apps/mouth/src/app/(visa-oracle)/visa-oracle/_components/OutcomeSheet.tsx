"use client";

import { useMemo, useState } from "react";
import {
  ArrowRight,
  CalendarClock,
  Check,
  CircleAlert,
  Copy,
  ListChecks,
  MessageCircle,
  Printer,
} from "lucide-react";
import QRCode from "qrcode";
import type { Assumption, EvaluateResult } from "../_lib/mock-engine";
import {
  QUESTIONS,
  formatIsoDateForDisplay,
  getLane,
  type OracleFacts,
} from "../_lib/tree";
import type { Language } from "../_lib/flow";
import { translate, type I18nKey } from "../_lib/i18n";
import { ELIGIBILITY_ICON } from "./VerdictReveal";
import { DISPLAY_ORDER, reviewGateDisplay } from "./ConfirmationCard";

export interface OutcomeSheetProps {
  language: Language;
  result: EvaluateResult;
  facts: OracleFacts;
  /** Injected for deterministic tests/snapshots; defaults to now. */
  today?: Date;
  /** Finding #15 (adversarial review 2026-07-17): NO_SUPPORTED_PATH's
   * "what instead" alternatives dispatch straight back into the interview
   * at the category question rather than dead-ending the demo. Optional
   * so a snapshot/test render without a live flow still works. */
  onSelectCategory?: (category: string) => void;
}

const WHATSAPP_NUMBER = "628213465159"; // Zantara / Bali Zero, wa.me format (fact_whatsapp_meta_verified_number)

function formatIDR(amount: number, language: Language): string {
  // Finding #17: "Free" was a hardcoded ternary invisible to the i18n
  // parity test — now a dict entry like every other rendered string.
  if (amount === 0) return translate(language, "outcome.price_free" as I18nKey);
  return new Intl.NumberFormat(language === "id" ? "id-ID" : "en-US", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(amount);
}

function buildWhatsAppSummary(language: Language, facts: OracleFacts): string {
  const order = [
    "in_indonesia",
    "category",
    "work_payer",
    "remote_clients",
    "remote_income",
    "tourism_duration",
  ];
  const lines = order
    .filter((id) => facts[id] !== undefined && facts[id] !== "unsure")
    .map((id) => {
      const question = QUESTIONS[id];
      const label = translate(language, question.i18nKey as I18nKey);
      const value = translate(
        language,
        `${question.i18nKey}.opt.${facts[id]}` as I18nKey,
      );
      return `${label}: ${value}`;
    });
  // Finding #17: same treatment for the WhatsApp summary header.
  const header = translate(
    language,
    "outcome.whatsapp_summary_header" as I18nKey,
  );
  return [header, ...lines].join("\n");
}

function localeFor(language: Language): string {
  return language === "id" ? "id-ID" : "en-GB";
}

/**
 * Real QR handoff (design doc §3 interaction #8 — the decorative lucide
 * `QrCode` glyph this replaced never encoded anything). `QRCode.create()`
 * (the `qrcode` npm package, MIT, already a monorepo dependency via
 * `apps/wa-mirror` — reuse-first) is a PURE, SYNCHRONOUS bitmap builder —
 * no canvas, no async I/O, so it's identical on the server-rendered pass
 * and the client hydration pass (no hydration mismatch) and needs no
 * network. The bitmap is hand-rendered as a single `<path>` of unit
 * squares — a handful of DOM nodes, crisp at any size. Colors are fixed
 * black-on-white regardless of the oracle light/dark theme: a themed QR
 * code risks falling under the contrast ratio scanners need.
 */
function useQrPath(value: string): { size: number; path: string } {
  return useMemo(() => {
    const qr = QRCode.create(value, { errorCorrectionLevel: "M" });
    const { size, data } = qr.modules;
    let path = "";
    for (let row = 0; row < size; row++) {
      for (let col = 0; col < size; col++) {
        if (data[row * size + col]) {
          path += `M${col},${row}h1v1h-1z`;
        }
      }
    }
    return { size, path };
  }, [value]);
}

function OracleQrCode({ value, label }: { value: string; label: string }) {
  const { size, path } = useQrPath(value);
  return (
    <div className="oracle-qr-wrap oracle-no-print">
      <svg
        className="oracle-qr"
        viewBox={`0 0 ${size} ${size}`}
        role="img"
        aria-label={label}
        // P1 (Codex GPT-5.6-terra xhigh adversarial review 2026-07-18):
        // exposes the exact string encoded into the QR bitmap so e2e can
        // assert it is byte-identical to the visible WhatsApp link's href
        // — the invariant is now also structural (OutcomeSheet computes
        // `whatsappUrl` ONCE and passes it to both), this attribute is the
        // regression guard against that ever drifting back apart.
        data-qr-value={value}
        shapeRendering="crispEdges"
      >
        <rect width={size} height={size} fill="#ffffff" />
        <path d={path} fill="#000000" />
      </svg>
    </div>
  );
}

/**
 * Outcome-page anatomy, top to bottom (design doc §3): comparison table
 * (≥2 candidates), timeline anchored to today, the single all-inclusive
 * price, a checkable document checklist, next 3 steps, WhatsApp handoff +
 * a real QR, share/print/PDF + copy-summary, and a dated assumptions/
 * caveats receipt with the Ditjen-decides disclaimer. Never a fee
 * breakdown — one number.
 */
export function OutcomeSheet({
  language,
  result,
  facts,
  today = new Date(),
  onSelectCategory,
}: OutcomeSheetProps) {
  const lane = getLane(facts, today);
  const freshnessDate = new Intl.DateTimeFormat(
    language === "id" ? "id-ID" : "en-GB",
    {
      dateStyle: "long",
    },
  ).format(today);

  // Item 4 (checklist + share/print): local-to-this-visit checkbox state —
  // never persisted, never fed back into `facts`/the mock engine, purely a
  // "what have I gathered" scratchpad for the person reading this page.
  const [checkedDocs, setCheckedDocs] = useState<Set<string>>(new Set());
  const toggleDoc = (key: string) => {
    setCheckedDocs((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const summaryText = buildWhatsAppSummary(language, facts);
  // P1 (Codex GPT-5.6-terra xhigh adversarial review 2026-07-18): computed
  // ONCE and reused for both the visible WhatsApp link's href and the QR's
  // encoded value — previously each built its own copy of this template
  // literal, a duplication the QR's `data-qr-value` regression test below
  // now guards against ever drifting back apart.
  const whatsappUrl = `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(summaryText)}`;

  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">(
    "idle",
  );
  const handleCopySummary = async () => {
    // Local flag, not `copyState` — the state setters below are async/
    // batched, so the enclosing closure would still see this render's
    // stale value if read directly.
    let failed = false;
    try {
      await navigator.clipboard.writeText(summaryText);
      setCopyState("copied");
    } catch {
      // Clipboard permission denied, insecure context, or API unavailable
      // (older browsers) — real failure modes, not hypothetical (Codex
      // GPT-5.6-terra xhigh adversarial review 2026-07-18, minor finding):
      // surfaced visibly + announced, same as the success path, instead of
      // silently doing nothing while the button looks like it worked.
      failed = true;
      setCopyState("failed");
    } finally {
      // A failure needs enough time to actually be read and acted on
      // (manually select the text) — a fleeting success toast doesn't.
      setTimeout(() => setCopyState("idle"), failed ? 6000 : 2000);
    }
  };

  // Print-only "your answers" recap (design doc §3 print anatomy: "clean
  // verdict + answers + checklist + assumptions + disclaimer"). Nothing
  // else on the verdict screen shows the raw facts — reuses
  // ConfirmationCard's exact row-building logic so the printed page never
  // drifts from what the confirmation screen showed earlier in the visit.
  const answerRows = DISPLAY_ORDER.filter(
    (id) => facts[id] !== undefined && facts[id] !== "unsure",
  ).map((id) => {
    const question = QUESTIONS[id];
    const value = facts[id];
    const display =
      id === "permit_expiry"
        ? formatIsoDateForDisplay(value, localeFor(language))
        : id === "review_gate"
          ? reviewGateDisplay(language, value)
          : translate(language, `${question.i18nKey}.opt.${value}` as I18nKey);
    return {
      id,
      label: translate(language, question.i18nKey as I18nKey),
      value: display,
    };
  });

  return (
    <div className="oracle-outcome">
      {answerRows.length > 0 && (
        <section className="oracle-print-only">
          <h2 className="oracle-outcome__section-title">
            {translate(language, "confirmation.your_answers")}
          </h2>
          <div className="oracle-confirmation__group">
            {answerRows.map((row) => (
              <div key={row.id} className="oracle-confirmation__row">
                <span className="oracle-confirmation__label">{row.label}</span>
                <span className="oracle-confirmation__value">{row.value}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {result.state === "HUMAN_REVIEW_REQUIRED" && (
        <section>
          <p style={{ margin: 0, color: "var(--oracle-ink)" }}>
            {translate(language, "outcome.human_review_body")}
          </p>
          {lane === "expired" && (
            <p
              style={{
                marginTop: "var(--space-2)",
                color: "var(--oracle-ink-muted)",
              }}
            >
              {translate(language, "outcome.overstay_reassurance")}
            </p>
          )}
        </section>
      )}

      {result.state === "NO_SUPPORTED_PATH" && (
        <section>
          <p style={{ margin: 0, color: "var(--oracle-ink)" }}>
            {translate(language, "outcome.no_path_body")}
          </p>
          <h2
            className="oracle-outcome__section-title"
            style={{ marginTop: "var(--space-6)" }}
          >
            {translate(language, "outcome.alternatives_title")}
          </h2>
          <p className="oracle-question__hint">
            {translate(language, "outcome.alternatives_intro")}
          </p>
          {/* Finding #15: alternatives are live re-entry points into the
              interview (SELECT_CATEGORY), never a bare dead-end list.
              oracle-no-print (P1, Codex GPT-5.6-terra xhigh adversarial
              review 2026-07-18): these are category-changing navigation
              controls, not print content — the print stylesheet already
              hides every other interactive control on this page, this
              list was the one left uncovered. */}
          <ul className="oracle-checklist-doc oracle-checklist-doc--actionable oracle-no-print">
            {(result.alternativeCategories ?? []).map((key) => (
              <li key={key}>
                <button
                  type="button"
                  className="oracle-option-card"
                  onClick={() => onSelectCategory?.(key)}
                >
                  <span>
                    {translate(language, `q.category.opt.${key}` as I18nKey)}
                  </span>
                  <ArrowRight aria-hidden="true" size={18} />
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {result.state === "TEMPORARILY_UNAVAILABLE" && (
        <section>
          <p style={{ margin: 0, color: "var(--oracle-ink)" }}>
            {translate(language, "outcome.temporarily_unavailable_body")}
          </p>
        </section>
      )}

      {result.state === "SUPPORTED_CANDIDATES" && (
        <>
          {result.candidates.length >= 2 && (
            <section>
              <h2 className="oracle-outcome__section-title">
                {translate(language, "outcome.comparison_title")}
              </h2>
              <div className="oracle-table-scroll">
                <table className="oracle-table">
                  <thead>
                    <tr>
                      <th scope="col">
                        {translate(language, "outcome.comparison_col.visa")}
                      </th>
                      <th scope="col">
                        {translate(
                          language,
                          "outcome.comparison_col.eligibility",
                        )}
                      </th>
                      <th scope="col">
                        {translate(language, "outcome.comparison_col.timeline")}
                      </th>
                      <th scope="col">
                        {translate(language, "outcome.comparison_col.price")}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.candidates.map((c) => (
                      <tr key={c.code}>
                        <td>{translate(language, c.nameI18nKey as I18nKey)}</td>
                        <td>
                          <span
                            className="oracle-verdict-chip"
                            data-state={c.eligibility}
                          >
                            {(() => {
                              // Finding #14: reuse VerdictReveal's icon set
                              // — eligibility was color+text-only here,
                              // a spec hard-constraint-4 violation (never
                              // color-alone) already solved once, locally.
                              const Icon = ELIGIBILITY_ICON[c.eligibility];
                              return <Icon aria-hidden="true" size={16} />;
                            })()}
                            {translate(
                              language,
                              `verdict.eligibility.${c.eligibility}` as I18nKey,
                            )}
                          </span>
                        </td>
                        <td className="oracle-tabular-nums">
                          {translate(language, "outcome.timeline_range", {
                            min: c.timelineDays[0],
                            max: c.timelineDays[1],
                          })}
                        </td>
                        <td className="oracle-tabular-nums">
                          {formatIDR(c.allInclusivePriceIDR, language)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          <section>
            <h2 className="oracle-outcome__section-title">
              <CalendarClock
                aria-hidden="true"
                size={18}
                style={{ verticalAlign: "-3px", marginRight: "0.4rem" }}
              />
              {translate(language, "outcome.timeline_title")}
            </h2>
            <p className="oracle-tabular-nums" style={{ margin: 0 }}>
              {translate(language, "outcome.timeline_range", {
                min: result.candidates[0].timelineDays[0],
                max: result.candidates[0].timelineDays[1],
              })}
            </p>
          </section>

          <section className="oracle-price">
            <h2
              className="oracle-outcome__section-title"
              style={{ marginBottom: 0 }}
            >
              {translate(language, "outcome.price_label")}
            </h2>
            <span className="oracle-price__value oracle-tabular-nums">
              {formatIDR(result.candidates[0].allInclusivePriceIDR, language)}
            </span>
            <span className="oracle-price__note">
              {translate(language, "outcome.price_all_inclusive")}
            </span>
          </section>

          <section>
            <h2 className="oracle-outcome__section-title">
              <ListChecks
                aria-hidden="true"
                size={18}
                style={{ verticalAlign: "-3px", marginRight: "0.4rem" }}
              />
              {translate(language, "outcome.checklist_title")}
            </h2>
            {/* Item 4: checkable — mirrors the review-gate checklist
                pattern (`.oracle-checklist`/`.oracle-checklist__item`,
                QuestionScreen.tsx's `ReviewGateChecklist`) rather than
                inventing a new one. State is local to this visit only —
                never written back to `facts`/the mock engine. */}
            <fieldset
              className="oracle-checklist oracle-checklist-doc--checkable"
              style={{ border: "none", padding: 0, margin: 0 }}
            >
              <legend className="oracle-sr-only">
                {translate(language, "outcome.checklist_title")}
              </legend>
              {Array.from(
                new Set(
                  result.candidates.flatMap((c) => c.requirementI18nKeys),
                ),
              ).map((key) => (
                <label key={key} className="oracle-checklist__item">
                  <input
                    type="checkbox"
                    checked={checkedDocs.has(key)}
                    onChange={() => toggleDoc(key)}
                  />
                  {translate(language, key as I18nKey)}
                </label>
              ))}
            </fieldset>
          </section>
        </>
      )}

      {/* W0b (legal-disclaimer fix, 2026-07-23): the footer below renders
          on ALL FIVE terminal states — disclaimer/receipt/handoff are the
          legal floor under every verdict, NEEDS_INPUT included (spec
          §A.3.2/§A.9). The next-3-steps section is instead gated on
          SUPPORTED_CANDIDATES only (owner call 2026-07-23, Fable MEDIUM):
          its step-2 copy ("Gather the documents listed above") references
          the candidate checklist, which exists only when candidates exist
          (visas is [] on every other state) — on HUMAN_REVIEW_REQUIRED /
          NO_SUPPORTED_PATH / TEMPORARILY_UNAVAILABLE / NEEDS_INPUT the
          section dangled. */}
      {result.state === "SUPPORTED_CANDIDATES" && (
        <section>
          <h2 className="oracle-outcome__section-title">
            {translate(language, "outcome.next_steps_title")}
          </h2>
          <ol className="oracle-next-steps">
            {[1, 2, 3].map((n) => (
              <li key={n}>
                <span className="oracle-next-steps__index oracle-tabular-nums">
                  {n}
                </span>
                <span>
                  {translate(
                    language,
                    `outcome.next_steps.default.${n}` as I18nKey,
                  )}
                </span>
              </li>
            ))}
          </ol>
        </section>
      )}

      <section
        className="oracle-no-print"
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "var(--space-4)",
          alignItems: "center",
        }}
      >
        <a
          className="oracle-whatsapp-cta"
          href={whatsappUrl}
          target="_blank"
          rel="noopener noreferrer"
        >
          <MessageCircle aria-hidden="true" size={18} />
          {translate(language, "outcome.whatsapp_cta")}
        </a>
        {/* Item 3: a real, scannable QR encoding the exact same
            pre-loaded wa.me URL as the link beside it — the link
            itself is the text alternative (never aria-hidden). */}
        <OracleQrCode
          value={whatsappUrl}
          label={translate(language, "outcome.qr_aria" as I18nKey)}
        />
      </section>

      <section className="oracle-outcome-actions oracle-no-print">
        <button
          type="button"
          className="oracle-print-cta"
          onClick={() => window.print()}
        >
          <Printer aria-hidden="true" size={18} />
          {translate(language, "outcome.print_cta" as I18nKey)}
        </button>
        <button
          type="button"
          className="oracle-copy-cta"
          data-copy-state={copyState}
          onClick={handleCopySummary}
        >
          {copyState === "copied" ? (
            <Check aria-hidden="true" size={18} />
          ) : copyState === "failed" ? (
            <CircleAlert aria-hidden="true" size={18} />
          ) : (
            <Copy aria-hidden="true" size={18} />
          )}
          {translate(
            language,
            copyState === "copied"
              ? ("outcome.copy_confirmed" as I18nKey)
              : copyState === "failed"
                ? ("outcome.copy_failed" as I18nKey)
                : ("outcome.copy_cta" as I18nKey),
          )}
        </button>
        <span role="status" aria-live="polite" className="oracle-sr-only">
          {copyState === "copied"
            ? translate(language, "outcome.copy_confirmed" as I18nKey)
            : copyState === "failed"
              ? translate(language, "outcome.copy_failed" as I18nKey)
              : ""}
        </span>
      </section>

      <section className="oracle-receipt">
        <h2
          className="oracle-outcome__section-title"
          style={{ marginBottom: 0 }}
        >
          {translate(language, "outcome.assumptions_receipt_title")}
        </h2>
        {result.assumptions.length === 0 ? (
          <p style={{ margin: 0 }}>
            {translate(language, "outcome.assumptions_receipt_empty")}
          </p>
        ) : (
          <ul style={{ margin: 0, paddingLeft: "1.1rem" }}>
            {result.assumptions.map((a: Assumption) => (
              <li key={a.questionId}>
                {translate(language, `assumption.${a.questionId}` as I18nKey)}
              </li>
            ))}
          </ul>
        )}
        <p className="oracle-tabular-nums" style={{ margin: 0 }}>
          {translate(language, "outcome.freshness_stamp", {
            date: freshnessDate,
          })}
        </p>
      </section>

      <section className="oracle-disclaimer">
        <p>{translate(language, "outcome.disclaimer.not_government")}</p>
        <p>{translate(language, "outcome.disclaimer.based_on_facts")}</p>
        <p>{translate(language, "outcome.disclaimer.not_approval")}</p>
        <p>{translate(language, "outcome.disclaimer.complex_to_human")}</p>
      </section>
    </div>
  );
}
