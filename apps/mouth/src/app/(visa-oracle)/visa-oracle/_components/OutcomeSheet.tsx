"use client";

import {
  ArrowRight,
  CalendarClock,
  ListChecks,
  MessageCircle,
  QrCode,
} from "lucide-react";
import type { Assumption, EvaluateResult } from "../_lib/mock-engine";
import { QUESTIONS, getLane, type OracleFacts } from "../_lib/tree";
import type { Language } from "../_lib/flow";
import { translate, type I18nKey } from "../_lib/i18n";
import { ELIGIBILITY_ICON } from "./VerdictReveal";

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

/**
 * Outcome-page anatomy, top to bottom (design doc §3): comparison table
 * (≥2 candidates), timeline anchored to today, the single all-inclusive
 * price, document checklist, next 3 steps, WhatsApp handoff + QR
 * placeholder, and a dated assumptions/caveats receipt with the
 * Ditjen-decides disclaimer. Never a fee breakdown — one number.
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

  return (
    <div className="oracle-outcome">
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
              interview (SELECT_CATEGORY), never a bare dead-end list. */}
          <ul className="oracle-checklist-doc oracle-checklist-doc--actionable">
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
            <ul className="oracle-checklist-doc">
              {Array.from(
                new Set(
                  result.candidates.flatMap((c) => c.requirementI18nKeys),
                ),
              ).map((key) => (
                <li key={key}>{translate(language, key as I18nKey)}</li>
              ))}
            </ul>
          </section>
        </>
      )}

      {result.state !== "NEEDS_INPUT" && (
        <>
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

          <section
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "var(--space-4)",
              alignItems: "center",
            }}
          >
            <a
              className="oracle-whatsapp-cta"
              href={`https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(
                buildWhatsAppSummary(language, facts),
              )}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              <MessageCircle aria-hidden="true" size={18} />
              {translate(language, "outcome.whatsapp_cta")}
            </a>
            <div
              aria-hidden="true"
              style={{
                width: 64,
                height: 64,
                borderRadius: "var(--radius-md)",
                border: "1px dashed var(--oracle-border-strong)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--oracle-ink-faint)",
              }}
            >
              <QrCode size={28} />
            </div>
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
                    {translate(
                      language,
                      `assumption.${a.questionId}` as I18nKey,
                    )}
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
        </>
      )}
    </div>
  );
}
