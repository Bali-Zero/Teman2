"use client";

import { useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ChevronDown, TreePine } from "lucide-react";
import {
  getTreeSteps,
  isEditableTreeStep,
  type OracleNode,
} from "../_lib/flow";
import type { Language } from "../_lib/flow";
import type { OracleFacts } from "../_lib/tree";
import { translate, type I18nKey } from "../_lib/i18n";

export interface LivingTreeProps {
  language: Language;
  current: OracleNode;
  facts: OracleFacts;
  /** Tree tap-to-edit (design doc §3 interaction #6): dispatches the
   * existing `EDIT` action (flow.ts) to jump back to a completed
   * question — same history-truncation + fact-pruning mechanism the
   * confirmation card's own Edit buttons already use. Only ever called
   * for a step `isEditableTreeStep` accepts. */
  onEditQuestion: (questionId: string) => void;
}

/**
 * THE centerpiece (design doc §3): the product's data structure, rendered
 * honestly — not decoration. Vertical trunk of the interview so far;
 * ineligible category leaves fade+curl away the moment the category is
 * answered (FLIP via AnimatePresence exit); the surviving leaf thickens.
 * Idle "breathe" on the current step is pure CSS, gated by the
 * `prefers-reduced-motion` media query in oracle.css — this component
 * additionally gates its own JS-driven prune animation via
 * `useReducedMotion()` so both paths honor the setting.
 */
export function LivingTree({
  language,
  current,
  facts,
  onEditQuestion,
}: LivingTreeProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const reducedMotion = useReducedMotion();
  const { trunk, categoryLeaves } = getTreeSteps(current, facts);

  const srPath = trunk
    .filter((s) => s.status !== "pending")
    .map(
      (s) =>
        `${translate(language, s.labelI18nKey as I18nKey)}: ${translate(
          language,
          `tree.sr_status.${s.status}` as I18nKey,
        )}`,
    );

  return (
    <>
      {/* Non-visual equivalent — always present, independent of viewport. */}
      <nav
        aria-label={translate(language, "tree.sr_path_label")}
        className="oracle-sr-only"
      >
        <ol>
          {srPath.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ol>
      </nav>

      <button
        type="button"
        className="oracle-tree-minimap-trigger"
        aria-expanded={mobileOpen}
        onClick={() => setMobileOpen((v) => !v)}
      >
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "0.4rem",
          }}
        >
          <TreePine aria-hidden="true" size={16} />
          {translate(language, "tree.sr_path_label")}
        </span>
        <ChevronDown
          aria-hidden="true"
          size={16}
          style={{
            transform: mobileOpen ? "rotate(180deg)" : "none",
            transition:
              "transform var(--motion-duration-fast) var(--motion-ease-standard)",
          }}
        />
      </button>
      <AnimatePresence initial={false}>
        {mobileOpen && (
          <motion.div
            initial={reducedMotion ? undefined : { height: 0, opacity: 0 }}
            animate={reducedMotion ? undefined : { height: "auto", opacity: 1 }}
            exit={reducedMotion ? undefined : { height: 0, opacity: 0 }}
            transition={{ duration: reducedMotion ? 0 : 0.2 }}
            style={{ overflow: "hidden" }}
          >
            <TreePanel
              language={language}
              trunk={trunk}
              categoryLeaves={categoryLeaves}
              reducedMotion={!!reducedMotion}
              onEditQuestion={onEditQuestion}
            />
          </motion.div>
        )}
      </AnimatePresence>

      <div className="oracle-tree--desktop">
        <TreePanel
          language={language}
          trunk={trunk}
          categoryLeaves={categoryLeaves}
          reducedMotion={!!reducedMotion}
          onEditQuestion={onEditQuestion}
        />
      </div>
    </>
  );
}

function TreePanel({
  language,
  trunk,
  categoryLeaves,
  reducedMotion,
  onEditQuestion,
}: {
  language: Language;
  trunk: ReturnType<typeof getTreeSteps>["trunk"];
  categoryLeaves: ReturnType<typeof getTreeSteps>["categoryLeaves"];
  reducedMotion: boolean;
  onEditQuestion: (questionId: string) => void;
}) {
  return (
    <div className="oracle-tree">
      <div className="oracle-tree__trunk">
        {trunk.map((step) => {
          const label = translate(language, step.labelI18nKey as I18nKey);
          // "Oracle deals your card" morph (design doc §3 interaction #4):
          // the "verdict" trunk row carries the shared view-transition-name
          // right up until it becomes the current step — at that point the
          // hero card in VerdictReveal takes over the name instead (never
          // both at once, since the two conditions are mutually exclusive
          // on the same `current` state). Harmless no-op CSS property in
          // browsers without View Transitions support or when
          // `prefers-reduced-motion` disables the JS-driven transition call
          // (OracleShell never invokes `document.startViewTransition` in
          // that case, so this name never gets used for anything).
          const morphStyle =
            step.id === "verdict" && step.status !== "current"
              ? ({ viewTransitionName: "oracle-verdict-morph" } as const)
              : undefined;

          if (isEditableTreeStep(step)) {
            return (
              <button
                key={step.id}
                type="button"
                className="oracle-tree__step oracle-tree__step--editable"
                data-status={step.status}
                onClick={() => onEditQuestion(step.id)}
                aria-label={translate(language, "tree.edit_aria" as I18nKey, {
                  question: label,
                })}
              >
                <span className="oracle-tree__dot" aria-hidden="true" />
                <span aria-hidden="true">{label}</span>
              </button>
            );
          }

          return (
            <div
              key={step.id}
              className="oracle-tree__step"
              data-status={step.status}
              aria-hidden="true"
              style={morphStyle}
            >
              <span className="oracle-tree__dot" />
              <span>{label}</span>
            </div>
          );
        })}
      </div>

      {categoryLeaves && (
        <div className="oracle-tree__leaves" aria-hidden="true">
          <AnimatePresence initial={false}>
            {categoryLeaves
              .filter(
                (leaf) =>
                  leaf.status !== "pruned" ||
                  !categoryLeaves.some((l) => l.status === "done"),
              )
              .map((leaf) => (
                <motion.span
                  key={leaf.key}
                  className="oracle-tree__leaf"
                  data-status={leaf.status}
                  layout={!reducedMotion}
                  initial={
                    reducedMotion ? undefined : { opacity: 0, scale: 0.8 }
                  }
                  animate={reducedMotion ? undefined : { opacity: 1, scale: 1 }}
                  exit={
                    reducedMotion
                      ? undefined
                      : {
                          opacity: 0,
                          scale: 0.6,
                          rotate: -8,
                          transition: { duration: 0.25 },
                        }
                  }
                  transition={{
                    duration: reducedMotion ? 0 : 0.3,
                    ease: [0.4, 0, 0.2, 1],
                  }}
                >
                  {translate(language, `q.category.opt.${leaf.key}` as I18nKey)}
                </motion.span>
              ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
