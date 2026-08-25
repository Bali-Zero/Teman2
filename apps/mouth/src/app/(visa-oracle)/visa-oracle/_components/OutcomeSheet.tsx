"use client";

import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import {
  ArrowRight,
  CalendarClock,
  Check,
  CircleAlert,
  CircleCheck,
  CircleHelp,
  Copy,
  ExternalLink,
  FileCheck,
  Printer,
  Share2,
  ShieldCheck,
} from "lucide-react";
import {
  QUESTIONS,
  formatIsoDateForDisplay,
  type OracleFacts,
} from "../_lib/tree";
import type { Language } from "../_lib/flow";
import {
  localized,
  type LegalSupportStatus,
  type OperationalAvailabilityStatus,
  type OutcomeCandidate,
  type OutcomePrice,
  type OutcomeReason,
  type OutcomeSource,
  type OutcomeTimeline,
  type OutcomeViewModel,
  type ServiceAvailabilityStatus,
} from "../_lib/outcome-view-model";
import { translate, type I18nKey } from "../_lib/i18n";
import {
  T2_CONSULTANT_TERMS,
  T2_CONSULTANT_TERMS_TITLE,
} from "../_lib/engine-adapter";
import { DISPLAY_ORDER, formatFactDisplay } from "./ConfirmationCard";

export interface OutcomeSheetProps {
  language: Language;
  outcome: OutcomeViewModel;
  facts: OracleFacts;
  onSelectCategory?: (category: string) => void;
  onEditMissingInput?: (questionId: string) => void;
  /** Integration-owned, consent-gated handoff. No WhatsApp/CRM destination
   * is rendered unless the caller supplies this slot explicitly. */
  handoffSlot?: ReactNode;
}

type AxisStatus =
  | LegalSupportStatus
  | OperationalAvailabilityStatus
  | ServiceAvailabilityStatus;

const STATUS_ICON: Record<AxisStatus, typeof CircleCheck> = {
  SUPPORTED: CircleCheck,
  CONDITIONAL: CircleHelp,
  NOT_SUPPORTED: CircleAlert,
  UNKNOWN: CircleHelp,
  AVAILABLE: CircleCheck,
  TEMPORARILY_UNAVAILABLE: CircleAlert,
  CONTACT_REQUIRED: CircleHelp,
  NOT_OFFERED: CircleAlert,
};

function localeFor(language: Language): string {
  return language === "id" ? "id-ID" : "en-GB";
}

function formatIDR(amount: number, language: Language): string {
  return new Intl.NumberFormat(language === "id" ? "id-ID" : "en-US", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatAssessmentDate(value: string, language: Language): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) return value;
  return new Intl.DateTimeFormat(localeFor(language), {
    dateStyle: "long",
    timeStyle: "short",
  }).format(parsed);
}

function answerRows(language: Language, facts: OracleFacts) {
  return DISPLAY_ORDER.filter(
    (id) => facts[id] !== undefined && facts[id] !== "unsure",
  ).map((id) => {
    const question = QUESTIONS[id];
    const value = facts[id];
    return {
      id,
      label: question ? translate(language, question.i18nKey as I18nKey) : id,
      value: question ? formatFactDisplay(language, id, value) : value,
    };
  });
}

function buildShareSummary(
  language: Language,
  outcome: OutcomeViewModel,
): string {
  const lines = [
    translate(language, "outcome.share_title" as I18nKey),
    translate(language, `verdict.headline.${outcome.state}` as I18nKey),
  ];
  if (outcome.assessment?.publicId) {
    lines.push(
      translate(language, "outcome.decision_reference" as I18nKey, {
        id: outcome.assessment.publicId,
      }),
    );
  }
  if (outcome.state === "SUPPORTED_CANDIDATES") {
    for (const candidate of outcome.candidates) {
      lines.push(`${candidate.code} — ${localized(candidate.name, language)}`);
    }
  }
  return lines.join("\n");
}

function ReasonList({
  language,
  reasons,
  sources,
}: {
  language: Language;
  reasons: readonly OutcomeReason[];
  sources: ReadonlyMap<string, OutcomeSource>;
}) {
  if (reasons.length === 0) return null;
  return (
    <ul className="oracle-reason-list">
      {reasons.map((reason) => (
        <li key={reason.code}>
          <span>{localized(reason.message, language)}</span>
          {reason.sourceIds.length > 0 && (
            <span className="oracle-reason-list__sources">
              {reason.sourceIds.map((sourceId) => {
                const source = sources.get(sourceId);
                if (!source) return null;
                return (
                  <a
                    key={sourceId}
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {source.title}
                    <ExternalLink aria-hidden="true" size={13} />
                  </a>
                );
              })}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

function AxisBadge({
  language,
  labelKey,
  status,
}: {
  language: Language;
  labelKey: I18nKey;
  status: AxisStatus;
}) {
  const Icon = STATUS_ICON[status];
  return (
    <div className="oracle-axis" data-status={status.toLowerCase()}>
      <span className="oracle-axis__label">
        {translate(language, labelKey)}
      </span>
      <span className="oracle-axis__value">
        <Icon aria-hidden="true" size={16} />
        {translate(language, `outcome.status.${status}` as I18nKey)}
      </span>
    </div>
  );
}

function Timeline({
  language,
  timeline,
}: {
  language: Language;
  timeline: OutcomeTimeline;
}) {
  if (timeline.status !== "AVAILABLE") {
    return (
      <div className="oracle-unverified" role="status">
        <strong>
          {translate(
            language,
            timeline.status === "CONTACT_REQUIRED"
              ? "outcome.timeline_contact_required"
              : "outcome.timeline_unavailable",
          )}
        </strong>
        <p>{localized(timeline.message, language)}</p>
      </div>
    );
  }
  return (
    <div className="oracle-timeline">
      <p className="oracle-tabular-nums">
        {translate(language, "outcome.timeline_dates" as I18nKey, {
          from: formatIsoDateForDisplay(
            timeline.earliestDateIso,
            localeFor(language),
          ),
          to: formatIsoDateForDisplay(
            timeline.latestDateIso,
            localeFor(language),
          ),
        })}
      </p>
      <p className="oracle-question__hint">
        {translate(language, "outcome.timeline_basis" as I18nKey, {
          date: formatIsoDateForDisplay(
            timeline.basisDateIso,
            localeFor(language),
          ),
        })}
      </p>
      {timeline.note && <p>{localized(timeline.note, language)}</p>}
    </div>
  );
}

function Price({
  language,
  price,
}: {
  language: Language;
  price: OutcomePrice;
}) {
  if (price.status !== "AVAILABLE") {
    return <p>{localized(price.message, language)}</p>;
  }
  return (
    <div className="oracle-price">
      <span className="oracle-price__value oracle-tabular-nums">
        {formatIDR(price.amount, language)}
      </span>
      <span className="oracle-price__note">
        {translate(language, "outcome.price_all_inclusive")}
      </span>
      {price.validUntilIso && (
        <span className="oracle-question__hint">
          {translate(language, "outcome.price_valid_until" as I18nKey, {
            date: formatAssessmentDate(price.validUntilIso, language),
          })}
        </span>
      )}
    </div>
  );
}

function CandidateCard({
  language,
  candidate,
  sourceIndex,
  checkedDocs,
  onToggleDoc,
}: {
  language: Language;
  candidate: OutcomeCandidate;
  sourceIndex: ReadonlyMap<string, OutcomeSource>;
  checkedDocs: ReadonlySet<string>;
  onToggleDoc: (key: string) => void;
}) {
  return (
    <article className="oracle-candidate-card">
      <header className="oracle-candidate-card__header">
        <div>
          <p className="oracle-eyebrow">{candidate.code}</p>
          <h2 className="oracle-candidate-card__title">
            {localized(candidate.name, language)}
          </h2>
          {candidate.tagline && (
            <p className="oracle-question__hint">
              {localized(candidate.tagline, language)}
            </p>
          )}
        </div>
        <span className="oracle-candidate-card__rank oracle-tabular-nums">
          {translate(language, "outcome.rank" as I18nKey, {
            rank: candidate.rank,
          })}
        </span>
      </header>

      <div className="oracle-axis-grid">
        <AxisBadge
          language={language}
          labelKey={"outcome.axis.legal" as I18nKey}
          status={candidate.legal.status}
        />
        <AxisBadge
          language={language}
          labelKey={"outcome.axis.operational" as I18nKey}
          status={candidate.operational.status}
        />
        <AxisBadge
          language={language}
          labelKey={"outcome.axis.service" as I18nKey}
          status={candidate.service.status}
        />
      </div>

      <section>
        <h3 className="oracle-outcome__section-title">
          {translate(language, "outcome.why_supported" as I18nKey)}
        </h3>
        <ReasonList
          language={language}
          reasons={candidate.decisionReasons}
          sources={sourceIndex}
        />
      </section>

      <div className="oracle-candidate-card__details">
        <section>
          <h3 className="oracle-outcome__section-title">
            <CalendarClock aria-hidden="true" size={18} />
            {translate(language, "outcome.timeline_title")}
          </h3>
          <Timeline language={language} timeline={candidate.timeline} />
        </section>
        <section>
          <h3 className="oracle-outcome__section-title">
            {translate(language, "outcome.price_label")}
          </h3>
          <Price language={language} price={candidate.price} />
        </section>
      </div>

      {/* Owner ruling #2 (OWNER-RULINGS-2026-08-25.md §2): this candidate's
       * own "product page" surface — one of the two places the T2 terms
       * text must appear (the other is the post-purchase email, which does
       * not exist yet in this repo — see engine-adapter.ts's doc comment on
       * `T2_CONSULTANT_TERMS`). Rendered per-candidate off THIS candidate's
       * own `tier`, not the outcome's top-ranked one, so a mixed-tier
       * candidate list never mislabels a card. */}
      {candidate.tier === "T2" && (
        <section
          className="oracle-candidate-card__consultant-terms"
          role="note"
        >
          <h3 className="oracle-outcome__section-title">
            {localized(T2_CONSULTANT_TERMS_TITLE, language)}
          </h3>
          <p>{localized(T2_CONSULTANT_TERMS, language)}</p>
        </section>
      )}

      <section>
        <h3 className="oracle-outcome__section-title">
          <FileCheck aria-hidden="true" size={18} />
          {translate(language, "outcome.checklist_title")}
        </h3>
        {candidate.documents.length === 0 ? (
          <div className="oracle-unverified" role="status">
            <strong>
              {translate(language, "outcome.documents_unknown" as I18nKey)}
            </strong>
            <p>{translate(language, "outcome.documents_contact" as I18nKey)}</p>
          </div>
        ) : (
          <fieldset className="oracle-checklist oracle-checklist-doc--checkable">
            <legend className="oracle-sr-only">
              {translate(language, "outcome.checklist_title")}
            </legend>
            {candidate.documents.map((document) => {
              const key = `${candidate.id}:${document.id}`;
              return (
                <label key={document.id} className="oracle-checklist__item">
                  <input
                    type="checkbox"
                    checked={checkedDocs.has(key)}
                    onChange={() => onToggleDoc(key)}
                  />
                  <span>
                    {localized(document.label, language)}
                    {document.status !== "REQUIRED" && (
                      <small>
                        {translate(
                          language,
                          `outcome.document_status.${document.status}` as I18nKey,
                        )}
                      </small>
                    )}
                  </span>
                </label>
              );
            })}
          </fieldset>
        )}
      </section>
    </article>
  );
}

export function OutcomeSheet({
  language,
  outcome,
  facts,
  onSelectCategory,
  onEditMissingInput,
  handoffSlot,
}: OutcomeSheetProps) {
  const sourceIndex = useMemo(
    () => new Map(outcome.sources.map((source) => [source.id, source])),
    [outcome.sources],
  );
  const rows = answerRows(language, facts);
  const [checkedDocs, setCheckedDocs] = useState<Set<string>>(new Set());
  const [shareState, setShareState] = useState<
    "idle" | "copied" | "shared" | "failed"
  >("idle");
  const summary = buildShareSummary(language, outcome);

  const copySummary = async () => {
    try {
      await navigator.clipboard.writeText(summary);
      setShareState("copied");
    } catch {
      setShareState("failed");
    }
  };

  const shareSummary = async () => {
    try {
      if (navigator.share) {
        await navigator.share({
          title: translate(language, "outcome.share_title" as I18nKey),
          text: summary,
        });
        setShareState("shared");
        return;
      }
      await copySummary();
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setShareState("failed");
    }
  };

  const toggleDoc = (key: string) => {
    setCheckedDocs((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <div className="oracle-outcome">
      {/* A HUMAN_REVIEW_REQUIRED state already gets its own honest,
          complete explanation below (outcome.human_review_body + the
          review reasons) regardless of provenance — a generic non-ENGINE
          origin notice on top of it would repeat "this is a hold, not a
          decision" next to a section explaining a decision genuinely was
          made and flagged for review. Skip it only for that state. */}
      {outcome.provenance !== "ENGINE" &&
        outcome.state !== "HUMAN_REVIEW_REQUIRED" && (
          <section
            className="oracle-origin-notice"
            data-provenance={outcome.provenance.toLowerCase()}
            role="status"
          >
            <ShieldCheck aria-hidden="true" size={20} />
            <div>
              <h2 className="oracle-outcome__section-title">
                {translate(
                  language,
                  `outcome.provenance.${outcome.provenance}.title` as I18nKey,
                )}
              </h2>
              <p>
                {translate(
                  language,
                  `outcome.provenance.${outcome.provenance}.body` as I18nKey,
                )}
              </p>
            </div>
          </section>
        )}

      {rows.length > 0 && (
        <section className="oracle-print-only">
          <h2 className="oracle-outcome__section-title">
            {translate(language, "confirmation.your_answers")}
          </h2>
          <div className="oracle-confirmation__group">
            {rows.map((row) => (
              <div key={row.id} className="oracle-confirmation__row">
                <span className="oracle-confirmation__label">{row.label}</span>
                <span className="oracle-confirmation__value">{row.value}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {outcome.state === "NEEDS_INPUT" && (
        <section>
          <p>{translate(language, "outcome.needs_input_body" as I18nKey)}</p>
          <ul className="oracle-action-list">
            {outcome.missingInputs.map((input) => (
              <li key={input.code}>
                <span>{localized(input.message, language)}</span>
                {input.questionId && onEditMissingInput && (
                  <button
                    type="button"
                    className="oracle-confirmation__edit"
                    onClick={() => onEditMissingInput(input.questionId!)}
                  >
                    {translate(language, "confirmation.edit")}
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {outcome.state === "HUMAN_REVIEW_REQUIRED" && (
        <section>
          <p>{translate(language, "outcome.human_review_body")}</p>
          <ReasonList
            language={language}
            reasons={outcome.reviewReasons}
            sources={sourceIndex}
          />
        </section>
      )}

      {outcome.state === "NO_SUPPORTED_PATH" && (
        <section>
          <p>{translate(language, "outcome.no_path_body")}</p>
          <ReasonList
            language={language}
            reasons={outcome.noPathReasons}
            sources={sourceIndex}
          />
          {outcome.alternatives.length > 0 && (
            <>
              <h2 className="oracle-outcome__section-title">
                {translate(language, "outcome.alternatives_title")}
              </h2>
              <ul className="oracle-action-list oracle-no-print">
                {outcome.alternatives.map((alternative) => (
                  <li key={alternative.category}>
                    <button
                      type="button"
                      className="oracle-option-card"
                      onClick={() => onSelectCategory?.(alternative.category)}
                    >
                      <span>
                        {translate(
                          language,
                          `q.category.opt.${alternative.category}` as I18nKey,
                        )}
                      </span>
                      <ArrowRight aria-hidden="true" size={18} />
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}

      {outcome.state === "TEMPORARILY_UNAVAILABLE" && (
        <section>
          <p>{localized(outcome.outage.message, language)}</p>
          <p className="oracle-question__hint">
            {translate(
              language,
              outcome.outage.retryable
                ? ("outcome.retryable" as I18nKey)
                : ("outcome.not_retryable" as I18nKey),
            )}
          </p>
        </section>
      )}

      {outcome.state === "SUPPORTED_CANDIDATES" && (
        <section aria-labelledby="oracle-supported-paths-title">
          <h2
            id="oracle-supported-paths-title"
            className="oracle-outcome__section-title"
          >
            {translate(language, "outcome.supported_paths" as I18nKey)}
          </h2>
          <div className="oracle-candidate-list">
            {outcome.candidates.map((candidate) => (
              <CandidateCard
                key={candidate.id}
                language={language}
                candidate={candidate}
                sourceIndex={sourceIndex}
                checkedDocs={checkedDocs}
                onToggleDoc={toggleDoc}
              />
            ))}
          </div>
        </section>
      )}

      <section>
        <h2 className="oracle-outcome__section-title">
          {translate(language, "outcome.next_steps_title")}
        </h2>
        <ol className="oracle-next-steps">
          {outcome.nextSteps.map((step, index) => (
            <li key={step.id}>
              <span className="oracle-next-steps__index oracle-tabular-nums">
                {index + 1}
              </span>
              <span>
                <strong>{localized(step.title, language)}</strong>
                {step.body && <small>{localized(step.body, language)}</small>}
              </span>
            </li>
          ))}
        </ol>
      </section>

      {handoffSlot && (
        <div className="oracle-handoff-slot oracle-no-print">{handoffSlot}</div>
      )}

      {outcome.sources.length > 0 && (
        <section>
          <h2 className="oracle-outcome__section-title">
            {translate(language, "outcome.sources_title" as I18nKey)}
          </h2>
          <ol className="oracle-source-list">
            {outcome.sources.map((source) => (
              <li key={source.id}>
                <a href={source.url} target="_blank" rel="noopener noreferrer">
                  {source.title}
                  <ExternalLink aria-hidden="true" size={14} />
                </a>
                <span>{source.publisher}</span>
                <span className="oracle-tabular-nums">
                  {translate(language, "outcome.source_dates" as I18nKey, {
                    effective: formatAssessmentDate(
                      source.effectiveAtIso,
                      language,
                    ),
                    observed: formatAssessmentDate(
                      source.observedAtIso,
                      language,
                    ),
                  })}
                </span>
                <span
                  className="oracle-source-freshness"
                  data-freshness={source.freshness.toLowerCase()}
                >
                  {translate(
                    language,
                    `outcome.freshness.${source.freshness}` as I18nKey,
                  )}
                </span>
              </li>
            ))}
          </ol>
        </section>
      )}

      <section className="oracle-receipt">
        <h2 className="oracle-outcome__section-title">
          {translate(language, "outcome.assumptions_receipt_title")}
        </h2>
        {outcome.assumptions.length === 0 ? (
          <p>{translate(language, "outcome.assumptions_receipt_empty")}</p>
        ) : (
          <ul>
            {outcome.assumptions.map((assumption) => (
              <li key={assumption.id}>
                {assumption.message
                  ? localized(assumption.message, language)
                  : translate(
                      language,
                      `assumption.${assumption.questionId}` as I18nKey,
                    )}
              </li>
            ))}
          </ul>
        )}
        {outcome.assessment && (
          <p className="oracle-tabular-nums">
            {translate(language, "outcome.assessment_dates" as I18nKey, {
              effective: formatAssessmentDate(
                outcome.assessment.effectiveAtIso,
                language,
              ),
              observed: formatAssessmentDate(
                outcome.assessment.observedAtIso,
                language,
              ),
              evaluated: formatAssessmentDate(
                outcome.assessment.evaluatedAtIso,
                language,
              ),
            })}
          </p>
        )}
      </section>

      <section className="oracle-outcome-actions oracle-no-print">
        <button
          type="button"
          className="oracle-print-cta"
          onClick={() => window.print()}
        >
          <Printer aria-hidden="true" size={18} />
          {translate(language, "outcome.print_cta")}
        </button>
        <button
          type="button"
          className="oracle-copy-cta"
          onClick={() => void shareSummary()}
        >
          <Share2 aria-hidden="true" size={18} />
          {translate(language, "outcome.share_cta" as I18nKey)}
        </button>
        <button
          type="button"
          className="oracle-copy-cta"
          onClick={() => void copySummary()}
        >
          {shareState === "copied" ? (
            <Check aria-hidden="true" size={18} />
          ) : (
            <Copy aria-hidden="true" size={18} />
          )}
          {translate(language, "outcome.copy_cta")}
        </button>
        <span role="status" aria-live="polite" className="oracle-sr-only">
          {shareState === "copied"
            ? translate(language, "outcome.copy_confirmed")
            : shareState === "shared"
              ? translate(language, "outcome.share_confirmed" as I18nKey)
              : shareState === "failed"
                ? translate(language, "outcome.copy_failed")
                : ""}
        </span>
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
