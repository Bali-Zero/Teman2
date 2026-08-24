"use client";

import { useEffect, useId, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { MessageCircle, X } from "lucide-react";
import type { Language } from "../_lib/flow";
import { translate } from "../_lib/i18n";
import type { VisaOracleTelemetryState } from "../_lib/telemetry";
import type {
  ConsultantAssignmentOriginScreen,
  ConsultantAssignmentTier,
} from "../_lib/consultant-assignment-client";
import { ConsentHandoff } from "./ConsentHandoff";

export interface ConsultantAccessProps {
  language: Language;
  /**
   * Undefined on every screen before a verdict has been reached (framing,
   * every question, confirmation) — `ConsentHandoff` receives `"IN_PROGRESS"`
   * in that case rather than a guessed or reused outcome state. Never
   * invented: this component does not run its own evaluation.
   */
  state?: VisaOracleTelemetryState;
  assessmentReference?: string | null;
  guardianConsentRequired?: boolean;
  whatsappNumber?: string;
  /**
   * C3 identity, supplied by `OracleShell` — deliberately NOT generated here.
   * This control and the verdict screen's own handoff can both be on screen at
   * once (this one lives in the topbar, which renders on every `current.kind`),
   * so if each minted its own `evaluationId` one visitor with one intent would
   * produce two uncorrelatable rows in `visa_oracle_consultant_requests`.
   * Same identity, different `origin_screen` — which is what that column is
   * for.
   */
  evaluationId: string;
  tier: ConsultantAssignmentTier;
  /**
   * Required, no default: this control renders on every `current.kind`, so
   * only `OracleShell` — the one place that actually knows which screen is
   * current — can say whether this interaction is "wizard" or "verdict".
   * Deliberately NOT inferred in here from the presence of `state` (verdict
   * screens pass one, every other screen doesn't): that would be a second
   * place guessing something the caller already knows for certain, which is
   * the same shape of defect the shared `evaluationId` above exists to
   * close.
   */
  originScreen: ConsultantAssignmentOriginScreen;
  productVersionId?: string | null;
}

/**
 * The ever-present "Talk to a consultant" control (contract C3, FROZEN.md:
 * "the control that emits this event is present on every screen — wizard,
 * verdict, checkout, portal — and is invokable at any moment, including
 * before buying. A screen without it fails V2's critic gate regardless of
 * how it looks."). Lives in `oracle-topbar__actions`, which already renders
 * unconditionally on every `current.kind` (`OracleShell.tsx`) — so mounting
 * this once there, rather than once per screen type, is what makes
 * "ever-present" true by construction instead of by five separate reminders
 * to add it.
 *
 * This component owns the SURFACE only. It reuses the existing,
 * already-reviewed `ConsentHandoff` WhatsApp-consent mechanism verbatim — it
 * does not call a CRM endpoint, because none exists yet
 * (`consultant_assignment.py` is a validated model with no HTTP route,
 * V3/unit-1 commit bb1cd7142 — "does not wire a frontend caller (V2 owns
 * wizard visuals)"). When that endpoint lands, it is wired from inside
 * `ConsentHandoff`'s existing consent-grant path, not by rebuilding this
 * trigger.
 */
export function ConsultantAccess({
  language,
  state,
  assessmentReference,
  guardianConsentRequired = false,
  whatsappNumber,
  evaluationId,
  tier,
  originScreen,
  productVersionId,
}: ConsultantAccessProps) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const containerRef = useRef<HTMLDivElement>(null);
  const reducedMotion = useReducedMotion();

  useEffect(() => {
    if (!open) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    const onPointerDown = (event: PointerEvent) => {
      if (!containerRef.current) return;
      if (!containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("pointerdown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("pointerdown", onPointerDown);
    };
  }, [open]);

  return (
    <div className="oracle-consultant-access" ref={containerRef}>
      <button
        type="button"
        data-oracle-consultant-trigger
        className="oracle-consultant-access__trigger"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={translate(language, "consultant.trigger.aria")}
        onClick={() => setOpen((value) => !value)}
      >
        <MessageCircle aria-hidden="true" size={18} />
        <span className="oracle-consultant-access__label">
          {translate(language, "consultant.trigger")}
        </span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <>
            <motion.div
              className="oracle-consultant-access__backdrop"
              initial={reducedMotion ? undefined : { opacity: 0 }}
              animate={reducedMotion ? undefined : { opacity: 1 }}
              exit={reducedMotion ? undefined : { opacity: 0 }}
              transition={{ duration: reducedMotion ? 0 : 0.15 }}
              aria-hidden="true"
            />
            <motion.div
              id={panelId}
              className="oracle-consultant-access__panel"
              role="dialog"
              aria-modal="false"
              aria-label={translate(language, "consultant.trigger")}
              initial={reducedMotion ? undefined : { opacity: 0, y: -8 }}
              animate={reducedMotion ? undefined : { opacity: 1, y: 0 }}
              exit={reducedMotion ? undefined : { opacity: 0, y: -8 }}
              transition={{ duration: reducedMotion ? 0 : 0.15 }}
            >
              <button
                type="button"
                className="oracle-consultant-access__close"
                aria-label={translate(language, "consultant.close.aria")}
                onClick={() => setOpen(false)}
              >
                <X aria-hidden="true" size={16} />
              </button>
              <ConsentHandoff
                language={language}
                state={state ?? "IN_PROGRESS"}
                assessmentReference={assessmentReference}
                guardianConsentRequired={guardianConsentRequired}
                whatsappNumber={whatsappNumber}
                evaluationId={evaluationId}
                tier={tier}
                originScreen={originScreen}
                productVersionId={productVersionId}
              />
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
