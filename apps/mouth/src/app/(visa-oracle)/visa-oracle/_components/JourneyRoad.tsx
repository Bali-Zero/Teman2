"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { GitFork } from "lucide-react";
import {
  getProcessModel,
  isEditableTreeStep,
  PROCESS_PHASES,
  type Language,
  type OracleNode,
  type ProcessPhaseKey,
} from "../_lib/flow";
import {
  QUESTIONS,
  questionPromptI18nKey,
  type OracleFacts,
} from "../_lib/tree";
import { translate, type I18nKey } from "../_lib/i18n";
import { formatFactDisplay } from "./ConfirmationCard";
import { roadCopy } from "./road-copy";
import { RoadCanvas, type RoadHeadStatus } from "./RoadCanvas";

/** The five question stages; `outcome` is the arrival, not a stage. */
const STAGES = PROCESS_PHASES.filter(
  (phase): phase is Exclude<ProcessPhaseKey, "outcome"> => phase !== "outcome",
);

export function stageLine(language: Language, group: ProcessPhaseKey): string {
  const index = STAGES.indexOf(group as (typeof STAGES)[number]);
  const name = translate(language, `process.phase.${group}` as I18nKey);
  if (index < 0) return name;
  return `${roadCopy(language, "stage", { n: index + 1, total: STAGES.length })} · ${name}`;
}

interface RoadRecord {
  id: string;
  label: string;
  value: string;
  status: "ink" | "pencil";
  group: ProcessPhaseKey | null;
  editable: boolean;
  pruned: number;
}

const FORK_KINDS = new Set(["branch", "choice", "tiles"]);

export interface JourneyRoadProps {
  language: Language;
  current: OracleNode;
  history: readonly OracleNode[];
  facts: OracleFacts;
  visitedVerdict: boolean;
  headStatus: RoadHeadStatus;
  reducedMotion: boolean;
  onEdit: (questionId: string) => void;
  /** The head of the road: the trailhead, the open question, the
   * confirmation, the checking plaque or the arrival. */
  children: ReactNode;
}

/**
 * «La strada» (BRIEF-v2 §3.1, ROADHEAD): the questions already answered
 * are the road behind you — one `<ol>` of records, each with its answer in
 * ink and a Change that re-opens exactly that question — and the live
 * question is the HEAD of that road, a `<fieldset>` whose legend names the
 * stage. The drawing (RoadCanvas) is measured from this list and hidden
 * from assistive tech; the list is the truth.
 */
export function JourneyRoad({
  language,
  current,
  history,
  facts,
  visitedVerdict,
  headStatus,
  reducedMotion,
  onEdit,
  children,
}: JourneyRoadProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const headRef = useRef<HTMLElement | null>(null);
  const model = useMemo(
    () => getProcessModel(current, facts, visitedVerdict),
    [current, facts, visitedVerdict],
  );
  const headQuestionId =
    current.kind === "question" ? current.questionId : null;

  const records = useMemo<RoadRecord[]>(() => {
    const steps = new Map(model.trunk.map((step) => [step.id, step]));
    return history
      .flatMap((node) =>
        node.kind === "question" && node.questionId !== headQuestionId
          ? [node.questionId]
          : [],
      )
      .filter((id, index, ids) => ids.indexOf(id) === index)
      .map((id) => {
        const question = QUESTIONS[id];
        const step = steps.get(id);
        const stepKey = step?.labelI18nKey as I18nKey | undefined;
        const stepLabel = stepKey ? translate(language, stepKey) : "";
        const label =
          stepLabel && stepLabel !== stepKey
            ? stepLabel
            : question
              ? translate(
                  language,
                  questionPromptI18nKey(question, facts) as I18nKey,
                )
              : id;
        const raw = facts[id];
        const unsure = raw === undefined || raw === "unsure";
        return {
          id,
          label,
          value:
            raw === undefined
              ? roadCopy(language, "notAnswered")
              : raw === "unsure"
                ? roadCopy(language, "notSure")
                : formatFactDisplay(language, id, raw),
          status: unsure ? "pencil" : "ink",
          group: question?.group ?? null,
          editable: step ? isEditableTreeStep(step) : Boolean(question),
          pruned:
            question && FORK_KINDS.has(question.kind)
              ? Math.max(0, question.options.length - 1)
              : 0,
        };
      });
  }, [facts, headQuestionId, history, language, model.trunk]);

  // Answers given downstream of an edited one: EDIT truncates history and
  // prunes their facts, so the shell keeps their DISPLAY text in memory
  // only (never stored) and shows them in pencil until they are answered
  // again, the road reaches its review, or the interview restarts.
  const [ghosts, setGhosts] = useState<RoadRecord[]>([]);
  const previousRef = useRef<RoadRecord[]>(records);
  useEffect(() => {
    const previous = previousRef.current;
    previousRef.current = records;
    const kept = new Set(records.map((record) => record.id));
    if (current.kind !== "question") {
      setGhosts((value) => (value.length === 0 ? value : []));
      return;
    }
    const dropped =
      records.length < previous.length - 1
        ? previous.filter(
            (record) => !kept.has(record.id) && record.id !== headQuestionId,
          )
        : [];
    setGhosts((value) => {
      const merged = [
        ...dropped.map((record) => ({ ...record, status: "pencil" as const })),
        ...value.filter(
          (ghost) => !dropped.some((record) => record.id === ghost.id),
        ),
      ].filter((ghost) => !kept.has(ghost.id) && ghost.id !== headQuestionId);
      return merged.length === value.length &&
        merged.every((ghost, index) => ghost.id === value[index]?.id)
        ? value
        : merged;
    });
  }, [current.kind, headQuestionId, records]);

  // Native scroll is the walk: after each step forward the new head settles
  // ~150px from the top (the review settles on the start of the road it
  // reviews). Instant under reduced motion; never on the first paint.
  const stepKey =
    current.kind === "question" ? `q:${current.questionId}` : current.kind;
  const lengthRef = useRef(history.length);
  useEffect(() => {
    const grew = history.length > lengthRef.current;
    lengthRef.current = history.length;
    const target =
      current.kind === "confirmation" ? containerRef.current : headRef.current;
    if (!grew || !target || typeof target.scrollIntoView !== "function") {
      return;
    }
    const top = target.getBoundingClientRect().top + window.scrollY - 150;
    window.scrollTo({
      top: Math.max(0, top),
      behavior:
        reducedMotion || current.kind === "confirmation" ? "auto" : "smooth",
    });
  }, [current.kind, history.length, reducedMotion, stepKey]);

  const layoutKey = [
    stepKey,
    history.length,
    language,
    headStatus,
    records.map((record) => `${record.id}:${record.status}`).join(","),
    ghosts.length,
  ].join("|");

  const headGroup: ProcessPhaseKey | null =
    current.kind === "question"
      ? (QUESTIONS[current.questionId]?.group ?? null)
      : current.kind === "confirmation"
        ? "review"
        : null;
  const prunedText =
    model.prunedCount === 1
      ? roadCopy(language, "prunedOne")
      : roadCopy(language, "prunedMany", { count: model.prunedCount });

  let lastGroup: ProcessPhaseKey | null = null;
  const head =
    current.kind === "question" ? (
      <fieldset
        ref={(element) => {
          headRef.current = element;
        }}
        className="oracle-roadhead"
        data-road-head={current.kind}
      >
        {headGroup && (
          <legend className="oracle-road__stage oracle-roadhead__stage">
            {stageLine(language, headGroup)}
          </legend>
        )}
        {children}
      </fieldset>
    ) : (
      <div
        ref={(element) => {
          headRef.current = element;
        }}
        className="oracle-roadhead"
        data-road-head={current.kind}
      >
        {headGroup && (
          <p className="oracle-road__stage oracle-roadhead__stage">
            {stageLine(language, headGroup)}
          </p>
        )}
        {children}
      </div>
    );

  return (
    <div
      ref={containerRef}
      className="oracle-road"
      data-road-at={current.kind}
      data-road-reduced-motion={reducedMotion ? "true" : undefined}
    >
      <RoadCanvas
        containerRef={containerRef}
        headStatus={headStatus}
        layoutKey={layoutKey}
        reducedMotion={reducedMotion}
      />
      {records.length > 0 && (
        <ol
          className="oracle-road__records"
          aria-label={roadCopy(language, "roadLabel")}
        >
          {records.map((record) => {
            const newStage =
              record.group !== null && record.group !== lastGroup;
            if (record.group !== null) lastGroup = record.group;
            return (
              <li
                key={record.id}
                className="oracle-road__record"
                data-road-record={record.id}
                data-road-status={record.status}
              >
                {newStage && record.group && (
                  <p className="oracle-road__stage">
                    {stageLine(language, record.group)}
                  </p>
                )}
                <div className="oracle-road__row">
                  <span
                    className="oracle-road__node"
                    data-road-node={record.status}
                    data-road-pruned={record.pruned}
                    aria-hidden="true"
                  />
                  <span className="oracle-road__text">
                    <span className="oracle-road__label">{record.label}</span>
                    <span className="oracle-road__answer">{record.value}</span>
                  </span>
                  {record.editable && (
                    <button
                      type="button"
                      className="oracle-road__change"
                      aria-label={roadCopy(language, "changeAria", {
                        question: record.label,
                      })}
                      onClick={() => onEdit(record.id)}
                    >
                      {roadCopy(language, "change")}
                    </button>
                  )}
                </div>
                {record.id === "category" && model.prunedCount > 0 && (
                  <p className="oracle-road__pruned">
                    <GitFork aria-hidden="true" size={14} />
                    {prunedText}
                  </p>
                )}
              </li>
            );
          })}
        </ol>
      )}
      {head}
      {ghosts.length > 0 && (
        <div className="oracle-road__earlier">
          <p className="oracle-road__earlier-title">
            {roadCopy(language, "earlierTitle")}
          </p>
          <ul className="oracle-road__earlier-list">
            {ghosts.map((ghost) => (
              <li key={ghost.id} className="oracle-road__earlier-item">
                <span
                  className="oracle-road__node"
                  data-road-node="ghost"
                  aria-hidden="true"
                />
                <span className="oracle-road__label">{ghost.label}</span>
                <span className="oracle-road__answer">{ghost.value}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
