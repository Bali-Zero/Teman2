"use client";

import { useEffect, useRef, type ReactNode } from "react";
import type { Language } from "../_lib/flow";
import type { OutcomeViewModel } from "../_lib/outcome-view-model";
import { BODY_FIRST, translate, type I18nKey } from "../_lib/i18n";
import {
  LEGAL_STATUS_CHIP_STATE,
  LEGAL_STATUS_ICON,
  VerdictReveal,
} from "./VerdictReveal";
import { roadCopy, type RoadCopyKey } from "./road-copy";

/**
 * The road pauses on a paper plaque until the engine answers. Nothing that
 * looks like a result is drawn before then (red team: "reveal before the
 * engine answered").
 */
export function CheckingPlaque({
  language,
  children,
}: {
  language: Language;
  children: ReactNode;
}) {
  return (
    <div
      className="oracle-plaque oracle-plaque--checking oracle-verdict-card"
      role="status"
      aria-live="polite"
    >
      <p className="oracle-plaque__title">
        {roadCopy(language, "checkingTitle")}
      </p>
      {children}
    </div>
  );
}

/**
 * SUPPORTED: the paths the engine returned, in ITS order, as plain paper
 * plaques — no rank words, no seal, no stamp, no date. The qualifier sits
 * inside the heading so the result never reads as approval. Names come from
 * the engine's own display payload; this component never names a visa.
 */
export function ArrivalLanes({
  language,
  outcome,
}: {
  language: Language;
  outcome: OutcomeViewModel;
}) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    headingRef.current?.focus();
  }, []);
  const lanes = [...outcome.candidates].sort((a, b) => a.rank - b.rank);
  const description = (
    <p className="oracle-subhead oracle-arrival__body">
      {translate(
        language,
        "verdict.state_description.SUPPORTED_CANDIDATES" as I18nKey,
      )}
    </p>
  );
  const heading = (
    <h1
      className="oracle-headline oracle-arrival__title"
      tabIndex={-1}
      ref={headingRef}
    >
      <span className="oracle-arrival__kicker">
        {roadCopy(language, "lanesKicker")}
      </span>
      <span>{roadCopy(language, "lanesTitle")}</span>
    </h1>
  );
  return (
    <section
      className="oracle-arrival oracle-arrival--lanes oracle-verdict-card"
      data-arrival="SUPPORTED_CANDIDATES"
    >
      {BODY_FIRST[language] ? (
        <>
          {description}
          {heading}
        </>
      ) : (
        <>
          {heading}
          {description}
        </>
      )}
      <ol className="oracle-lanes">
        {lanes.map((candidate) => {
          const status = candidate.legal.status;
          const Icon = LEGAL_STATUS_ICON[status];
          return (
            <li
              key={candidate.code}
              className="oracle-lane"
              data-lane-code={candidate.code}
            >
              <span className="oracle-lane__name">
                {candidate.name[language] ?? candidate.name.en}
              </span>
              <span
                className="oracle-verdict-chip oracle-lane__chip"
                data-state={LEGAL_STATUS_CHIP_STATE[status]}
              >
                <Icon aria-hidden="true" size={16} />
                {translate(language, `outcome.status.${status}` as I18nKey)}
              </span>
            </li>
          );
        })}
      </ol>
      <p className="oracle-arrival__line">{roadCopy(language, "lanesOrder")}</p>
    </section>
  );
}

function ArrivalFrame({
  kind,
  language,
  outcome,
  isSecondHomeStudioOnly,
  lines,
}: {
  kind: "edge" | "pencil" | "specialist" | "outage";
  language: Language;
  outcome: OutcomeViewModel;
  isSecondHomeStudioOnly: boolean;
  lines: RoadCopyKey[];
}) {
  return (
    <section
      className={`oracle-arrival oracle-arrival--${kind}`}
      data-arrival={outcome.state}
    >
      <VerdictReveal
        language={language}
        state={outcome.state}
        provenance={outcome.provenance}
        legalStatus={outcome.candidates[0]?.legal.status}
        isSecondHomeStudioOnly={isSecondHomeStudioOnly}
      />
      <p className="oracle-arrival__line">
        {lines.map((key) => roadCopy(language, key)).join(" ")}
      </p>
    </section>
  );
}

/** NO_PATH: the edge of the map. The alternatives OutcomeSheet renders
 * below are drawn as the roads back (RoadCanvas measures them). */
export function EdgeOfMap(props: ArrivalProps) {
  const back =
    props.outcome.state === "NO_SUPPORTED_PATH" &&
    props.outcome.alternatives.length > 0;
  return (
    <ArrivalFrame
      kind="edge"
      {...props}
      lines={back ? ["edgeLine", "edgeBack"] : ["edgeLine"]}
    />
  );
}

/** NEEDS_INPUT: a pencil ring — the missing answer is asked below. */
export function PencilRing(props: ArrivalProps) {
  return <ArrivalFrame kind="pencil" {...props} lines={["pencilLine"]} />;
}

/** HUMAN_REVIEW: the road continues with a person, through the existing
 * consultant contact — no promise of a review is made here. */
export function SpecialistEnd(props: ArrivalProps) {
  return (
    <ArrivalFrame kind="specialist" {...props} lines={["specialistLine"]} />
  );
}

/** TEMPORARILY_UNAVAILABLE: the answers stay; the retry is the action. */
export function Outage(props: ArrivalProps) {
  return <ArrivalFrame kind="outage" {...props} lines={["outageLine"]} />;
}

interface ArrivalProps {
  language: Language;
  outcome: OutcomeViewModel;
  isSecondHomeStudioOnly: boolean;
}

export function Arrival(props: ArrivalProps) {
  switch (props.outcome.state) {
    case "SUPPORTED_CANDIDATES":
      return <ArrivalLanes language={props.language} outcome={props.outcome} />;
    case "NO_SUPPORTED_PATH":
      return <EdgeOfMap {...props} />;
    case "NEEDS_INPUT":
      return <PencilRing {...props} />;
    case "HUMAN_REVIEW_REQUIRED":
      return <SpecialistEnd {...props} />;
    default:
      return <Outage {...props} />;
  }
}
