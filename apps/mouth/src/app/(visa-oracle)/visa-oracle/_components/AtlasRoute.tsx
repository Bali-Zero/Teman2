"use client";

import {
  forwardRef,
  useCallback,
  useId,
  useImperativeHandle,
  useMemo,
  useRef,
} from "react";
import type { Language, OracleNode } from "../_lib/flow";
import {
  CATEGORY_KEYS,
  QUESTIONS,
  questionPromptI18nKey,
  type OracleFacts,
} from "../_lib/tree";
import { translate, type I18nKey } from "../_lib/i18n";
import { atlasCopy, isAtlasCategoryKey } from "../_lib/atlas-scenes";
import { formatFactDisplay } from "./ConfirmationCard";

export interface AtlasRouteHandle {
  /** Opens the dialog. `opener` is the element focus returns to on close —
   * defaults to `document.activeElement` (the button that was clicked). */
  open: (opener?: HTMLElement | null) => void;
}

export interface AtlasRouteProps {
  language: Language;
  history: readonly OracleNode[];
  facts: OracleFacts;
  onEdit: (questionId: string) => void;
  onSelectCategory: (category: string) => void;
}

/**
 * "Your route" — a native `<dialog>` recap of every question actually
 * answered so far, in the order the interview visited them, each editable.
 * Presentation only: `onEdit`/`onSelectCategory` are the same reducer
 * actions `OracleShell` already wires to Back/Edit/category tiles — this
 * component never mutates state itself.
 */
export const AtlasRoute = forwardRef<AtlasRouteHandle, AtlasRouteProps>(
  function AtlasRoute(
    { language, history, facts, onEdit, onSelectCategory },
    ref,
  ) {
    const dialogRef = useRef<HTMLDialogElement>(null);
    const openerRef = useRef<HTMLElement | null>(null);
    // Set just before a "Change"/alternative-direction close so the async
    // `close` event (fired by `dialog.close()`) knows NOT to steal focus back
    // to the opener — the new question heading QuestionScreen focuses on
    // mount must keep it instead. Plain closes (×, backdrop, Escape) never
    // set this, so they still restore focus to the opener as before.
    const skipRestoreRef = useRef(false);
    const headingId = useId();

    const requestClose = useCallback(() => {
      const dialog = dialogRef.current;
      if (!dialog) return;
      if (typeof dialog.close === "function") {
        dialog.close();
      } else {
        dialog.removeAttribute("open");
        dialog.dispatchEvent(new Event("close"));
      }
    }, []);

    // Close first (flagged so `onClose` skips focus restoration), THEN run
    // the reducer action — mirrors the order BUILD-SPEC's required fix calls
    // for, since the native `close` event fires asynchronously relative to
    // `dialog.close()` and must not race the action's own focus management.
    const closeAndNavigate = useCallback(
      (action: () => void) => {
        skipRestoreRef.current = true;
        requestClose();
        action();
      },
      [requestClose],
    );

    useImperativeHandle(
      ref,
      () => ({
        open: (opener) => {
          openerRef.current =
            opener ??
            (typeof document !== "undefined"
              ? (document.activeElement as HTMLElement)
              : null);
          const dialog = dialogRef.current;
          if (!dialog) return;
          // jsdom (BUILD-SPEC §4) has no `showModal` — degrade to a plain
          // `open` attribute rather than throwing, so the ledger and its
          // affordances are still reachable in tests.
          if (typeof dialog.showModal === "function") {
            dialog.showModal();
          } else {
            dialog.setAttribute("open", "");
          }
        },
      }),
      [],
    );

    // HISTORY order, deduplicated to the first visit — mirrors the
    // prototype's `AnswerLedger` (`[...new Set(...)]` preserves insertion
    // order) — and only questions the interview actually recorded a fact for
    // (a follow-up question can be in history before it is answered).
    const answeredIds = useMemo(() => {
      const seen = new Set<string>();
      const ids: string[] = [];
      for (const node of history) {
        if (node.kind !== "question") continue;
        if (facts[node.questionId] === undefined) continue;
        if (seen.has(node.questionId)) continue;
        seen.add(node.questionId);
        ids.push(node.questionId);
      }
      return ids;
    }, [history, facts]);

    const selectedCategory = isAtlasCategoryKey(facts.category)
      ? facts.category
      : null;

    return (
      <dialog
        ref={dialogRef}
        className="oracle-atlas-route"
        aria-labelledby={headingId}
        onClose={() => {
          const skipRestore = skipRestoreRef.current;
          skipRestoreRef.current = false;
          if (skipRestore) return;
          // The opener sits in the header, which has scrolled off-screen on a
          // long verdict — scrolling it back into view would jump the page
          // to the top under the reader.
          const opener = openerRef.current;
          if (opener?.isConnected) opener.focus({ preventScroll: true });
        }}
        onCancel={(event) => {
          // FIX-ROUND-2 K5: the native `<dialog>` already fires `cancel` on
          // Escape — preventing its default (which would skip straight to
          // `close` without our own `requestClose` bookkeeping) and routing
          // through the same close path keeps focus-return behaviour uniform
          // across ×, backdrop, and Escape.
          event.preventDefault();
          requestClose();
        }}
        onClick={(event) => {
          // Clicking the native `::backdrop` dispatches a click whose target
          // is the `<dialog>` element itself (there is no other way to reach
          // it) — clicking any real content inside targets that content
          // instead, so this only fires for a genuine backdrop click.
          if (event.target === dialogRef.current) requestClose();
        }}
      >
        <button
          type="button"
          className="oracle-atlas-route__close"
          aria-label={atlasCopy(language, "tools.route_close")}
          onClick={requestClose}
        >
          <span aria-hidden="true">×</span>
        </button>
        <p className="oracle-eyebrow">{atlasCopy(language, "tools.route")}</p>
        <h2 id={headingId}>{atlasCopy(language, "tools.route_heading")}</h2>
        {answeredIds.length === 0 ? (
          <p className="oracle-atlas-route__empty">
            {atlasCopy(language, "tools.empty_ledger")}
          </p>
        ) : (
          <ol className="oracle-atlas-route__ledger">
            {answeredIds.map((questionId) => {
              const question = QUESTIONS[questionId];
              const prompt = translate(
                language,
                questionPromptI18nKey(question, facts) as I18nKey,
              );
              return (
                <li key={questionId}>
                  <div>
                    <span>{prompt}</span>
                    <strong>
                      {formatFactDisplay(
                        language,
                        questionId,
                        facts[questionId],
                      )}
                    </strong>
                  </div>
                  <button
                    type="button"
                    aria-label={atlasCopy(language, "tools.change_labeled", {
                      q: prompt,
                    })}
                    onClick={() => closeAndNavigate(() => onEdit(questionId))}
                  >
                    {atlasCopy(language, "tools.change")}
                  </button>
                </li>
              );
            })}
          </ol>
        )}
        {selectedCategory && (
          <details className="oracle-atlas-route__alternatives oracle-no-print">
            <summary>{atlasCopy(language, "tools.explore")}</summary>
            <div>
              {CATEGORY_KEYS.filter(
                (category) => category !== selectedCategory,
              ).map((category) => (
                <button
                  type="button"
                  key={category}
                  onClick={() =>
                    closeAndNavigate(() => onSelectCategory(category))
                  }
                >
                  {translate(language, `q.category.opt.${category}` as I18nKey)}
                  <span aria-hidden="true"> ↗</span>
                </button>
              ))}
            </div>
          </details>
        )}
      </dialog>
    );
  },
);
