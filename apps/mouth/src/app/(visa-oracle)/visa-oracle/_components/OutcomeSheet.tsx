"use client";

import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
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
  questionPromptI18nKey,
  type OracleFacts,
} from "../_lib/tree";
import type { Language } from "../_lib/flow";
import {
  localized,
  type LegalSupportStatus,
  type OperationalAvailabilityStatus,
  type OutcomeCandidate,
  type OutcomeDuration,
  type OutcomePrice,
  type OutcomeReason,
  type OutcomeSource,
  type OutcomeTimeline,
  type OutcomeViewModel,
  type ServiceAvailabilityStatus,
} from "../_lib/outcome-view-model";
import { translate, type I18nKey } from "../_lib/i18n";
import { ACTIVITY_BOUNDARY_DECIDABLE_ANSWERS } from "../_lib/fact-mapper";
import {
  SECOND_HOME_STUDIO_REVIEW_REASON_CODE,
  SECOND_HOME_STUDIO_URL,
  REVIEW_REASON_ELEMENTS,
  UNMAPPED_REASON_COPY,
  isSecondHomeStudioOnly,
} from "../_lib/engine-adapter";
import {
  DISPLAY_ORDER,
  assumptionDisplay,
  formatFactDisplay,
} from "./ConfirmationCard";

export interface OutcomeSheetProps {
  language: Language;
  outcome: OutcomeViewModel;
  facts: OracleFacts;
  onSelectCategory?: (category: string) => void;
  /** Reopen an ALREADY-ASKED question (history truncates back to it). */
  onEditMissingInput?: (questionId: string) => void;
  /** Ask a question this interview never reached (history appends; every
   * answer already given is kept). Distinct slot from
   * `onEditMissingInput` on purpose — the two do opposite things to the
   * interview and must not be wired to the same handler. */
  onAskMissingInput?: (questionId: string) => void;
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
      label: question
        ? translate(language, questionPromptI18nKey(question, facts) as I18nKey)
        : id,
      value: question ? formatFactDisplay(language, id, value) : value,
    };
  });
}

function typicalTimingText(
  language: Language,
  min: number | undefined,
  max: number | undefined,
): string | null {
  if (min === undefined || max === undefined) return null;
  if (min === 0 && max === 1) {
    return translate(language, "outcome.timeline_within_one" as I18nKey);
  }
  if (min === max) {
    return translate(language, "outcome.timeline_typical_exact" as I18nKey, {
      days: String(min),
    });
  }
  return translate(language, "outcome.timeline_typical_range" as I18nKey, {
    min: String(min),
    max: String(max),
  });
}

/** Timing for the shared text: no dates (read later), never for UNKNOWN. */
function shareTimingText(
  language: Language,
  timeline: OutcomeTimeline,
): string | null {
  if (timeline.status !== "AVAILABLE") return null;
  const { workingDaysMin: min, workingDaysMax: max } = timeline;
  if (min === 0 && max === 0) {
    return translate(language, "outcome.timeline_none" as I18nKey);
  }
  const typical = typicalTimingText(language, min, max);
  return typical === null
    ? null
    : translate(language, "outcome.share_timing_indicative" as I18nKey, {
        typical,
      });
}

function buildShareSummary(
  language: Language,
  outcome: OutcomeViewModel,
): string {
  // D23 "OPTION B-STUDIO": the share text must never carry the generic
  // "needs a human, not an algorithm" headline for a Studio-only hold.
  const headlineKey: I18nKey = isSecondHomeStudioOnly(outcome)
    ? ("verdict.headline.SECOND_HOME_STUDIO" as I18nKey)
    : (`verdict.headline.${outcome.state}` as I18nKey);
  const lines = [
    translate(language, "outcome.share_title" as I18nKey),
    translate(language, headlineKey),
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
      const name = `${candidate.code} — ${localized(candidate.name, language)}`;
      const timing = shareTimingText(language, candidate.timeline);
      const parts = [
        candidate.duration && candidate.price.status === "AVAILABLE"
          ? formatIDR(candidate.price.amount, language)
          : null,
        candidate.duration
          ? durationLabel(language, candidate.duration.selectedDays, "permit")
          : null,
        timing,
      ].filter((part): part is string => part !== null);
      lines.push(parts.length > 0 ? `${name}: ${parts.join(" · ")}` : name);
    }
  }
  return lines.join("\n");
}

/**
 * PR-O4 / Δ2 (spec §3, D6 "Δ2: SÌ"): review codes whose hold is about OUR
 * sources or OUR process, never about anything the applicant answered. The
 * spec names the three families — `DECISIVE_*`, `SAFETY_CRITICAL_*`,
 * `MINOR_GUARDIAN_PRIVACY` — and PR-O2 documents `CLIENT_UNABLE_TO_VERIFY_
 * DETAIL` (outcome-fallbacks.ts) as the client-side technical exception of
 * the same kind. They render under their own heading so a reader can tell a
 * hold we owe them from a hold their own answers caused.
 *
 * Every other code — known or not — renders under the neutral "about your
 * case" heading, which is true of any review reason and never says the
 * applicant did something wrong. That is the fail-closed direction: an
 * unclassified new code can at worst be under-specific, never mis-attributed
 * to the visitor. `OutcomeSheet.test.tsx` pins the three families against
 * `REVIEW_REASON_COPY` so a new source/system code cannot ship unclassified.
 */
export const SYSTEM_REVIEW_REASON_CODES: ReadonlySet<string> = new Set([
  "DECISIVE_PRIMARY_SOURCE_NOT_APPLICABLE",
  "DECISIVE_SOURCE_FRESHNESS_UNKNOWN",
  "DECISIVE_SOURCE_STALE",
  "SAFETY_CRITICAL_PRIMARY_SOURCE_NOT_APPLICABLE",
  "SAFETY_CRITICAL_SOURCE_FRESHNESS_UNKNOWN",
  "SAFETY_CRITICAL_SOURCE_STALE",
  "MINOR_GUARDIAN_PRIVACY_REVIEW",
  "CLIENT_UNABLE_TO_VERIFY_DETAIL",
]);

/** One answer of this interview that demonstrably triggered a review code. */
export interface DemonstratedReviewCause {
  questionId: string;
  value: string;
}

/**
 * Review codes raised by a `review_gate` checklist item, keyed by the item
 * the applicant actually ticked. `fact-mapper.ts::mapDisclosedReviewFlags`
 * reads the same CSV fact and `evaluate_path.py::_DISCLOSED_REVIEW_REASON_
 * CODES` turns each flag into the code on the left, so ticking the item IS
 * the demonstrated cause. Mirrored rather than imported because the mapper's
 * own table is module-private; `OutcomeSheet.test.tsx` re-derives every row
 * through `mapDisclosedReviewFlags` so a drift in either file goes red.
 */
const REVIEW_GATE_CAUSE_ITEM: Readonly<Record<string, string>> = {
  DISCLOSED_CRIMINAL_RECORD_REVIEW: "criminal_record",
  DISCLOSED_HEALTH_CONCERN_REVIEW: "health_flag",
  DISCLOSED_PRIOR_VISA_REFUSAL_REVIEW: "prior_refusal",
  DISCLOSED_PEP_OR_SANCTIONS_REVIEW: "pep_or_sanctions",
  DISCLOSED_SOURCE_OF_FUNDS_REVIEW: "source_of_funds_unclear",
  DISCLOSED_DIPLOMATIC_PASSPORT_REVIEW: "diplomatic_passport",
  DISCLOSED_AMBIGUOUS_SPONSOR_REVIEW: "ambiguous_sponsor",
  DISCLOSED_UNCERTAINTY_REVIEW: "not_certain",
  DISCLOSED_ACTIVITY_BOUNDARY_REVIEW: "activity_boundary",
  // Slice A3-M (DRAFT-SPEC-A3-1.v2-M §4.1, M7): three rows for M1's new
  // `REVIEW_FLAG_MAP` keys — each REVIEW code is reachable only under the
  // `VISA_ORACLE_HOLDING_FLAGS` kill switch (its own review-reason copy is
  // a slice of its own the day a flag is held for real), but the mapping
  // back to the ticked item must exist now so the drift test below stays
  // green.
  DISCLOSED_PAST_OVERSTAY_REVIEW: "overstay",
  DISCLOSED_BLACKLIST_ENTRY_REVIEW: "blacklist",
  DISCLOSED_IMMIGRATION_INVESTIGATION_REVIEW: "immigration_investigation",
  // A3'-M (M4): the one NO_PATH code this row set covers. Unlike every row
  // above, no `DisclosedReviewFlag` backs it (it is a NO_SUPPORTED_PATH
  // code, never a review one) — the row exists so ticking "activity
  // boundary" on the review-gate checklist attributes a cause on THIS dead
  // end exactly as it already does on `DISCLOSED_ACTIVITY_BOUNDARY_REVIEW`.
  DISCLOSED_ACTIVITY_BOUNDARY_NO_PATH: "activity_boundary",
};

/**
 * The answers of THIS interview that demonstrably raised `code` — never a
 * guess, never a plausible-looking cause. Each branch mirrors the exact
 * trigger `fact-mapper.ts::mapDisclosedReviewFlags` uses to raise the flag
 * the backend turns into this code, so a cause shown here is one the
 * applicant can act on. When nothing demonstrates the code (a backend-only
 * trigger, or a relation-driven hold the interview cannot attribute to one
 * answer), this returns `[]` and only the code's own copy is shown — an
 * unexplained hold is better than an invented explanation.
 *
 * Every returned `questionId` is a key of `facts`, and `flow.ts::pruneFacts`
 * keeps `facts` a subset of the questions this walk actually asked — so
 * reopening one is always `EDIT` on a node present in history, which
 * truncates back to it and keeps every prerequisite. `EDIT` on a never-asked
 * question resets the whole interview (flow.ts `EDIT` case): that is why the
 * guard below is `facts[id] !== undefined`, not `QUESTIONS[id] !== undefined`.
 */
export function demonstratedReviewCauses(
  code: string,
  facts: OracleFacts,
): DemonstratedReviewCause[] {
  const causes = new Map<string, string>();
  const add = (questionId: string) => {
    const value = facts[questionId];
    if (value === undefined || !QUESTIONS[questionId]) return;
    causes.set(questionId, value);
  };

  if (code === "DISCLOSED_UNCERTAINTY_REVIEW") {
    for (const [questionId, value] of Object.entries(facts)) {
      if (value === "unsure") add(questionId);
    }
  }
  if (
    code === "DISCLOSED_ACTIVITY_BOUNDARY_REVIEW" ||
    // A3'-M (M4): the sourceless dead end reads the SAME undecidable-answer
    // table as the hold above — same cause, different destination state.
    code === "DISCLOSED_ACTIVITY_BOUNDARY_NO_PATH"
  ) {
    for (const [questionId, decidable] of Object.entries(
      ACTIVITY_BOUNDARY_DECIDABLE_ANSWERS,
    ) as [string, readonly string[]][]) {
      const answer = facts[questionId];
      if (answer !== undefined && !decidable.includes(answer)) add(questionId);
    }
  }
  if (code === "DISCLOSED_MULTI_PURPOSE_TRIP_REVIEW") {
    if (facts.trip_scope === "multiple") add("trip_scope");
  }
  if (code === "DISCLOSED_AMBIGUOUS_SPONSOR_REVIEW") {
    // Only the "unsure" half of the NARROW-1 trigger is attributable: the
    // other half is the STEPCHILD relation itself, which no single answer
    // demonstrates.
    for (const questionId of [
      "family_sponsor_status_code",
      "family_sponsor_confirmed",
    ]) {
      if (facts[questionId] === "unsure") add(questionId);
    }
  }
  const gateItem = REVIEW_GATE_CAUSE_ITEM[code];
  if (gateItem && (facts.review_gate?.split(",") ?? []).includes(gateItem)) {
    add("review_gate");
  }

  return [...causes].map(([questionId, value]) => ({ questionId, value }));
}

function ReviewCauseList({
  language,
  facts,
  causes,
  onEditMissingInput,
}: {
  language: Language;
  facts: OracleFacts;
  causes: readonly DemonstratedReviewCause[];
  onEditMissingInput?: (questionId: string) => void;
}) {
  if (causes.length === 0) return null;
  return (
    <ul className="oracle-action-list">
      {causes.map((cause) => {
        const question = QUESTIONS[cause.questionId];
        const prompt = translate(
          language,
          questionPromptI18nKey(question, facts) as I18nKey,
        );
        return (
          <li key={cause.questionId} data-review-cause={cause.questionId}>
            <span>
              {cause.value === "unsure"
                ? translate(language, "outcome.review_cause_unsure", {
                    question: prompt,
                  })
                : translate(language, "outcome.review_cause_answer", {
                    question: prompt,
                    answer: formatFactDisplay(
                      language,
                      cause.questionId,
                      cause.value,
                    ),
                  })}
            </span>
            {onEditMissingInput && (
              <button
                type="button"
                className="oracle-confirmation__edit"
                aria-label={translate(
                  language,
                  "outcome.review_cause_edit_aria",
                  { question: prompt },
                )}
                onClick={() => onEditMissingInput(cause.questionId)}
              >
                {translate(language, "confirmation.edit")}
              </button>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function ReviewReasonGroup({
  language,
  titleKey,
  reasons,
  facts,
  onEditMissingInput,
}: {
  language: Language;
  titleKey: I18nKey;
  reasons: readonly OutcomeReason[];
  facts: OracleFacts;
  onEditMissingInput?: (questionId: string) => void;
}) {
  if (reasons.length === 0) return null;
  return (
    <>
      <h2 className="oracle-outcome__section-title">
        {translate(language, titleKey)}
      </h2>
      <ReasonList
        language={language}
        reasons={reasons}
        causeFacts={facts}
        onEditMissingInput={onEditMissingInput}
      />
    </>
  );
}

// ENDING-ROUND E5 regex: matches the legacy engine-adapter.ts `reasonMessage()`
// fallback ("Verified reason: CODE" / "Alasan terverifikasi: CODE") — never
// a mapped SUPPORT_REASON_COPY sentence, which always reads as prose.
const GENERIC_SUPPORT_REASON_RE =
  /^(Verified reason|Alasan terverifikasi): [A-Z0-9_]+$/;

function ReasonList({
  language,
  reasons,
  causeFacts,
  onEditMissingInput,
  variant,
}: {
  language: Language;
  reasons: readonly OutcomeReason[];
  /** Supplied under HUMAN_REVIEW and, since A3'-M (M4), under
   * NO_SUPPORTED_PATH too: the interview whose answers may be shown as the
   * demonstrated cause of each reason. Absent elsewhere — a candidate's
   * support reason is not something the applicant "caused". */
  causeFacts?: OracleFacts;
  onEditMissingInput?: (questionId: string) => void;
  /** ENDING-ROUND E5 (+extension): "support" and "no_path" are the only
   * variants whose reasons are built by `reason()`/`reasonMessage()`
   * (engine-adapter.ts) and can therefore surface the raw fallback —
   * review/condition reasons always have their own mapped, already-neutral
   * copy. Collapses every such fallback into ONE generic sentence — a
   * DIFFERENT sentence per variant, because "the assessment supports this
   * option" would assert support inside a NO_SUPPORTED_PATH result. */
  variant?: "support" | "no_path" | "review";
}) {
  if (reasons.length === 0) return null;
  const genericKey: I18nKey | undefined =
    variant === "support"
      ? ("outcome.reason_generic" as I18nKey)
      : variant === "no_path"
        ? ("outcome.reason_generic_no_path" as I18nKey)
        : undefined;
  let genericShown = false;
  const rows = reasons.flatMap((reason) => {
    const localizedText = localized(reason.message, language);
    if (
      genericKey &&
      (GENERIC_SUPPORT_REASON_RE.test(localizedText) ||
        localizedText === UNMAPPED_REASON_COPY[language])
    ) {
      if (genericShown) return [];
      genericShown = true;
      return [{ reason, text: translate(language, genericKey) }];
    }
    return [{ reason, text: localizedText }];
  });
  return (
    <ul className="oracle-reason-list">
      {rows.map(({ reason, text }) => (
        <li key={reason.code}>
          <span>{text}</span>
          {REVIEW_REASON_ELEMENTS[reason.code] && (
            <dl className="oracle-review-elements">
              {(
                [
                  ["rule", "outcome.review.element.rule"],
                  ["checked", "outcome.review.element.checked"],
                  ["prepare", "outcome.review.element.prepare"],
                  ["handling", "outcome.review.element.handling"],
                ] as const
              ).map(([field, labelKey]) => (
                <div key={field} className="oracle-review-elements__row">
                  <dt>{translate(language, labelKey as I18nKey)}</dt>
                  <dd>
                    {localized(
                      REVIEW_REASON_ELEMENTS[reason.code]![field],
                      language,
                    )}
                  </dd>
                </div>
              ))}
            </dl>
          )}
          {causeFacts && (
            <ReviewCauseList
              language={language}
              facts={causeFacts}
              causes={demonstratedReviewCauses(reason.code, causeFacts)}
              onEditMissingInput={onEditMissingInput}
            />
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
      <p className="oracle-question__hint oracle-timeline__pending">
        {translate(language, "outcome.timeline_pending" as I18nKey)}
      </p>
    );
  }
  const { workingDaysMin: min, workingDaysMax: max } = timeline;
  if (min === 0 && max === 0) {
    return (
      <div className="oracle-timeline">
        <p>{translate(language, "outcome.timeline_none" as I18nKey)}</p>
      </div>
    );
  }
  const locale = localeFor(language);
  const from = formatIsoDateForDisplay(timeline.earliestDateIso, locale);
  const to = formatIsoDateForDisplay(timeline.latestDateIso, locale);
  const typical = typicalTimingText(language, min, max);
  return (
    <div className="oracle-timeline">
      {typical && <p>{typical}</p>}
      <p className="oracle-tabular-nums">
        {from === to
          ? translate(language, "outcome.timeline_if_today_single" as I18nKey, {
              date: from,
            })
          : translate(language, "outcome.timeline_if_today" as I18nKey, {
              from,
              to,
            })}
      </p>
      <p className="oracle-question__hint">
        {translate(language, "outcome.timeline_indicative" as I18nKey)}
      </p>
    </div>
  );
}

function durationLabel(
  language: Language,
  days: number,
  style: "permit" | "short",
): string {
  const years = days % 365 === 0;
  const count = years ? days / 365 : days;
  const key = years
    ? style === "permit"
      ? "outcome.duration_years"
      : "outcome.duration_label_years"
    : style === "permit"
      ? "outcome.duration_days"
      : "outcome.duration_label_days";
  return translate(language, key as I18nKey, { count });
}

function Price({
  language,
  price,
  duration,
}: {
  language: Language;
  price: OutcomePrice;
  duration?: OutcomeDuration;
}) {
  if (price.status !== "AVAILABLE") {
    return <p>{localized(price.message, language)}</p>;
  }
  return (
    <div className="oracle-price">
      <span className="oracle-price__value oracle-tabular-nums">
        {formatIDR(price.amount, language)}
      </span>
      {duration && (
        <span className="oracle-price__duration">
          {durationLabel(language, duration.selectedDays, "permit")}
        </span>
      )}
      <span className="oracle-price__note">
        {translate(language, "outcome.price_all_inclusive")}
      </span>
      {duration?.options
        .filter((option) => !option.selected && option.amountIdr !== null)
        .map((option) => (
          <span key={option.days} className="oracle-price__note">
            {translate(language, "outcome.duration_alternative" as I18nKey, {
              label: durationLabel(language, option.days, "short"),
              price: formatIDR(option.amountIdr as number, language),
            })}
          </span>
        ))}
      {duration?.extensionRequired && (
        <span className="oracle-question__hint">
          {translate(language, "outcome.duration_extension" as I18nKey)}
        </span>
      )}
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
  index,
  total,
  checkedDocs,
  onToggleDoc,
}: {
  language: Language;
  candidate: OutcomeCandidate;
  /** ENDING-ROUND E4: zero-based position among the candidates shown —
   * renders as the "01/02…" index, replacing the removed "Rank N" chip. */
  index: number;
  total: number;
  checkedDocs: ReadonlySet<string>;
  onToggleDoc: (key: string) => void;
}) {
  return (
    <article className="oracle-candidate-card">
      <header className="oracle-candidate-card__header">
        <div className="oracle-candidate-card__row">
          <p className="oracle-eyebrow">{candidate.code}</p>
          {total > 1 && (
            <span className="oracle-candidate-card__index oracle-tabular-nums">
              {translate(language, "outcome.path_counter" as I18nKey, {
                index: index + 1,
                total,
              })}
            </span>
          )}
        </div>
        <h2 className="oracle-candidate-card__title">
          {localized(candidate.name, language)}
        </h2>
        {candidate.tagline && (
          <p className="oracle-question__hint">
            {localized(candidate.tagline, language)}
          </p>
        )}
      </header>

      {/* ENDING-ROUND E4: axis badges + support reasons behind ONE closed
          disclosure — the prototype ending never showed a provenance wall
          by default; a visitor who wants the mechanics opens it. */}
      <details className="oracle-candidate__why">
        <summary>{translate(language, "outcome.why_fits" as I18nKey)}</summary>
        <div className="oracle-axis-grid">
          <AxisBadge
            language={language}
            labelKey={"outcome.axis.legal" as I18nKey}
            status={candidate.legal.status}
          />
          {candidate.operational.status !== "UNKNOWN" && (
            <AxisBadge
              language={language}
              labelKey={"outcome.axis.operational" as I18nKey}
              status={candidate.operational.status}
            />
          )}
          {candidate.service.status !== "UNKNOWN" && (
            <AxisBadge
              language={language}
              labelKey={"outcome.axis.service" as I18nKey}
              status={candidate.service.status}
            />
          )}
        </div>
        <ReasonList
          language={language}
          reasons={candidate.decisionReasons}
          variant="support"
        />
      </details>

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
          <Price
            language={language}
            price={candidate.price}
            duration={candidate.duration}
          />
        </section>
      </div>

      {candidate.documents.length > 0 && (
        <section>
          <h3 className="oracle-outcome__section-title">
            <FileCheck aria-hidden="true" size={18} />
            {translate(language, "outcome.checklist_title")}
          </h3>
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
        </section>
      )}
    </article>
  );
}

export function OutcomeSheet({
  language,
  outcome,
  facts,
  onSelectCategory,
  onEditMissingInput,
  onAskMissingInput,
  handoffSlot,
}: OutcomeSheetProps) {
  const rows = answerRows(language, facts);
  // Collapse repeated fallback copy only in this view. The adapter retains
  // every missing fact code for SHADOW parity; each editable row stays distinct.
  const fallbackMessages = new Set<string>();
  const visibleMissingInputs =
    outcome.state === "NEEDS_INPUT"
      ? outcome.missingInputs.filter((input) => {
          if (input.questionId) return true;
          const message = localized(input.message, language);
          if (fallbackMessages.has(message)) return false;
          fallbackMessages.add(message);
          return true;
        })
      : [];
  const reviewReasons =
    outcome.state === "HUMAN_REVIEW_REQUIRED" ? outcome.reviewReasons : [];
  const systemReviewReasons = reviewReasons.filter((reason) =>
    SYSTEM_REVIEW_REASON_CODES.has(reason.code),
  );
  const caseReviewReasons = reviewReasons.filter(
    (reason) => !SYSTEM_REVIEW_REASON_CODES.has(reason.code),
  );
  // D23 "OPTION B-STUDIO": this hold is never introduced as needing a
  // person's judgment — it routes to a self-serve calculator. Scoped to the
  // case where this is the ONLY review reason: a case that ALSO carries a
  // different hold still needs the generic body and the normal groups for
  // that other reason. Delegates to `engine-adapter.ts`'s
  // `isSecondHomeStudioOnly` so this component and `VerdictReveal` (via
  // `OracleShell`) agree on the SAME outcome rather than two computations
  // drifting apart.
  const studioOnly = isSecondHomeStudioOnly(outcome);
  const carriesSecondHomeStudio = reviewReasons.some(
    (reason) => reason.code === SECOND_HOME_STUDIO_REVIEW_REASON_CODE,
  );
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

  // F1 fix (ORACLE-PROD-20260927 delta, gate finding 1): a closed
  // `<details>` hides its content through the browser's own UA "details
  // content" slot, not through each child's `display` — the print CSS
  // alone (`> *:not(summary) { display:block !important }`) can never
  // reveal it, confirmed empirically in Chromium (both screenshot and PDF
  // text). This listens for the REAL `window.print()` path (the "Print /
  // save as PDF" button below fires `beforeprint`/`afterprint` like any
  // browser print) and opens every closed disclosure inside THIS sheet
  // right before printing, closing again afterward — but only the ones it
  // opened itself, so a disclosure the visitor already had open stays
  // open. React never controls `open` here (no `open` prop on either
  // `<details>`), so mutating the DOM property directly is safe.
  const outcomeRootRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const root = outcomeRootRef.current;
    if (!root) return;
    let openedByPrint: HTMLDetailsElement[] = [];

    const handleBeforePrint = () => {
      const details = root.querySelectorAll<HTMLDetailsElement>(
        "details.oracle-candidate__why, details.oracle-outcome__legal",
      );
      openedByPrint = [];
      details.forEach((node) => {
        if (!node.open) {
          node.open = true;
          openedByPrint.push(node);
        }
      });
    };
    const handleAfterPrint = () => {
      for (const node of openedByPrint) {
        if (node.isConnected) node.open = false;
      }
      openedByPrint = [];
    };

    window.addEventListener("beforeprint", handleBeforePrint);
    window.addEventListener("afterprint", handleAfterPrint);
    return () => {
      window.removeEventListener("beforeprint", handleBeforePrint);
      window.removeEventListener("afterprint", handleAfterPrint);
    };
  }, []);

  return (
    <div className="oracle-outcome" ref={outcomeRootRef}>
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

      {/* Slice A2 (PLAN VISA-ORACLE-DW-20260919 §1.6, R-SEQ): `notices[]`
          rendered with the verdict, never behind a disclosure glyph — one
          section shared by every state that can carry a condition, since
          the backend places no state constraint on this channel. */}
      {outcome.conditions.length > 0 && (
        // S6 (GATE-A2-REPORT-6849 LOW-4): `aria-labelledby` names this
        // region, matching the `oracle-supported-paths-title` pattern below
        // — `oracle-outcome__conditions` itself carries no CSS rule by
        // design (Track C owns `oracle.css`; this class is a query hook
        // for tests only).
        <section
          className="oracle-outcome__conditions"
          aria-labelledby="oracle-conditions-title"
        >
          <h2
            id="oracle-conditions-title"
            className="oracle-outcome__section-title"
          >
            {translate(language, "outcome.conditions.title")}
          </h2>
          <p>{translate(language, "outcome.conditions.intro")}</p>
          <ReasonList language={language} reasons={outcome.conditions} />
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
            {visibleMissingInputs.map((input) => (
              <li key={input.code}>
                <span>{localized(input.message, language)}</span>
                {/* A never-asked question is ANSWERED, not edited: the
                    interview appends it and keeps everything already
                    given. An already-asked one keeps the pre-existing
                    Edit, which truncates back to it. Never both. */}
                {input.questionId &&
                  (input.followUp
                    ? onAskMissingInput && (
                        <button
                          type="button"
                          className="oracle-confirmation__edit"
                          onClick={() => onAskMissingInput(input.questionId!)}
                        >
                          {translate(language, "outcome.answer_missing_input")}
                        </button>
                      )
                    : onEditMissingInput && (
                        <button
                          type="button"
                          className="oracle-confirmation__edit"
                          onClick={() => onEditMissingInput(input.questionId!)}
                        >
                          {translate(language, "confirmation.edit")}
                        </button>
                      ))}
              </li>
            ))}
          </ul>
        </section>
      )}

      {outcome.state === "HUMAN_REVIEW_REQUIRED" && (
        <section>
          {/* D23 "OPTION B-STUDIO": SECOND_HOME_BELOW_THRESHOLD_STUDIO is
              never introduced as "a person will check" — it routes to a
              self-serve calculator, not a person. The generic body and the
              two ReviewReasonGroup headings ("What a person will check...")
              are both about a HUMAN reviewing, so both are skipped when this
              is the only review reason; the reason's own copy (from
              REVIEW_REASON_COPY) still renders via ReasonList below, plus an
              explicit link to the Studio. A case that ALSO carries a
              different hold keeps the generic body and normal groups, and
              still gets the Studio link. */}
          {studioOnly ? (
            <>
              <ReasonList
                language={language}
                reasons={caseReviewReasons}
                causeFacts={facts}
                onEditMissingInput={onEditMissingInput}
              />
              {/* `oracle.css` is READ-ONLY by ruling (see the comment on the
                  NO_SUPPORTED_PATH door-tile alternatives below) — this
                  reuses the SAME `.oracle-option-card` class those "door"
                  tiles use rather than a bare link in a paragraph: it is a
                  primary next-action tile (44px target, visible hover/focus
                  via the global `:focus-visible` rule), and the Studio link
                  is exactly that — a door onward, not a footnote. */}
              <a
                href={SECOND_HOME_STUDIO_URL}
                className="oracle-option-card"
                style={{ width: "fit-content", marginTop: "var(--space-4)" }}
              >
                {translate(language, "outcome.second_home_studio_link")}
                <ArrowRight aria-hidden="true" size={18} />
              </a>
            </>
          ) : (
            <>
              <p>{translate(language, "outcome.human_review_body")}</p>
              <ReviewReasonGroup
                language={language}
                titleKey={"outcome.review_group_case.title" as I18nKey}
                reasons={caseReviewReasons}
                facts={facts}
                onEditMissingInput={onEditMissingInput}
              />
              <ReviewReasonGroup
                language={language}
                titleKey={"outcome.review_group_system.title" as I18nKey}
                reasons={systemReviewReasons}
                facts={facts}
                onEditMissingInput={onEditMissingInput}
              />
              {carriesSecondHomeStudio && (
                <a
                  href={SECOND_HOME_STUDIO_URL}
                  className="oracle-option-card"
                  style={{
                    width: "fit-content",
                    marginTop: "var(--space-4)",
                  }}
                >
                  {translate(language, "outcome.second_home_studio_link")}
                  <ArrowRight aria-hidden="true" size={18} />
                </a>
              )}
            </>
          )}
        </section>
      )}

      {outcome.state === "NO_SUPPORTED_PATH" && (
        <section>
          <p>{translate(language, "outcome.no_path_body")}</p>
          {/* ENDING-ROUND E5 (extended): `noPathReasons` is built by the SAME
              `reason()`/`reasonMessage()` pipeline as a candidate's support
              reasons (engine-adapter.ts) and falls back to the identical raw
              "Verified reason: CODE" text for an unmapped code — verified on
              screen (a live NO_SUPPORTED_PATH render showed "Verified
              reason: NO_SUPPORTED_PATH"). Same filter, same reason. */}
          <ReasonList
            language={language}
            reasons={outcome.noPathReasons}
            causeFacts={facts}
            onEditMissingInput={onEditMissingInput}
            variant="no_path"
          />
          {outcome.alternatives.length > 0 && (
            <>
              <h2 className="oracle-outcome__section-title">
                {translate(language, "outcome.alternatives_title")}
              </h2>
              <p>{translate(language, "outcome.alternatives_intro")}</p>
              <ul className="oracle-action-list oracle-no-print">
                {outcome.alternatives.map((alternative) => {
                  // The product code is the headline when the door names one:
                  // "Tourist Visit Visa (C1)" is the answer a dead end owes
                  // the visitor, and the tile name alone never was.
                  const title = alternative.productName
                    ? localized(alternative.productName, language)
                    : translate(
                        language,
                        `q.category.opt.${alternative.category}` as I18nKey,
                      );
                  const body = alternative.message
                    ? localized(alternative.message, language)
                    : undefined;
                  const key = `${alternative.category}:${alternative.productCode ?? ""}`;
                  // A door nothing answerable opens is a SENTENCE, never a
                  // button: the button would restart an interview that ends
                  // in exactly the same place.
                  // `oracle.css` is READ-ONLY by ruling, so the two-line
                  // shape (product name, then why that door is open) is set
                  // inline here rather than by a new class.
                  const lines = (
                    <span>
                      <strong>{title}</strong>
                      {body && (
                        <span
                          style={{ display: "block", marginTop: "0.35rem" }}
                        >
                          {body}
                        </span>
                      )}
                    </span>
                  );
                  if (alternative.actionable === false) {
                    return (
                      <li key={key} style={{ padding: "0.5rem 0" }}>
                        {lines}
                      </li>
                    );
                  }
                  return (
                    <li key={key}>
                      <button
                        type="button"
                        className="oracle-option-card"
                        onClick={() => onSelectCategory?.(alternative.category)}
                      >
                        {lines}
                        <ArrowRight aria-hidden="true" size={18} />
                      </button>
                    </li>
                  );
                })}
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
            {outcome.candidates.map((candidate, index) => (
              <CandidateCard
                key={candidate.id}
                language={language}
                candidate={candidate}
                index={index}
                total={outcome.candidates.length}
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

      {/* ENDING-ROUND E7: the previous "Sources used for this decision" wall
          (title + link + publisher + effective/observed dates + freshness
          badge on screen for every row) reads as provenance machinery.
          Closed by default; effective/observed/freshness stay only in
          `.oracle-print-only`. F1 fix (gate finding 1): this `<details>`
          is opened for real printing by the beforeprint/afterprint effect
          above — both the "Print / save as PDF" button below
          (`window.print()`) and Chromium's headless `page.pdf()` fire
          `beforeprint`/`afterprint` (verified empirically), so that effect
          alone covers both paths; oracle.css's `::details-content` print
          rule on this class is a defensive fallback only. */}
      {outcome.sources.length > 0 && (
        <details className="oracle-outcome__legal">
          <summary>
            {translate(language, "outcome.legal_references" as I18nKey)}
          </summary>
          <ol className="oracle-source-list">
            {outcome.sources.map((source) => (
              <li key={source.id}>
                <a href={source.url} target="_blank" rel="noopener noreferrer">
                  {source.title}
                  <ExternalLink aria-hidden="true" size={14} />
                </a>
                <span>{source.publisher}</span>
                <span className="oracle-print-only oracle-tabular-nums">
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
                  className="oracle-print-only oracle-source-freshness"
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
        </details>
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
                {/* Never the raw `assumption.<id>` key: an unsure answer
                    whose question has no dedicated copy still gets the
                    generic sentence, with the question named in it. */}
                {assumption.message
                  ? localized(assumption.message, language)
                  : assumptionDisplay(language, assumption.questionId)}
              </li>
            ))}
          </ul>
        )}
        {outcome.assessment && (
          <p className="oracle-print-only oracle-tabular-nums">
            {translate(
              language,
              (outcome.sources.length > 0
                ? "outcome.checked_on"
                : "outcome.checked_on_plain") as I18nKey,
              {
                date: formatAssessmentDate(
                  outcome.assessment.evaluatedAtIso,
                  language,
                ),
              },
            )}
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
        {/* D23 "OPTION B-STUDIO": the "always go to a human" line is false
            for the one hold that routes to a self-serve calculator instead —
            swapped for Studio-specific copy that names the same guarantee
            hold without ever mentioning a person or consultant. */}
        <p>
          {translate(
            language,
            studioOnly
              ? "outcome.disclaimer.second_home_studio"
              : "outcome.disclaimer.complex_to_human",
          )}
        </p>
      </section>
    </div>
  );
}
