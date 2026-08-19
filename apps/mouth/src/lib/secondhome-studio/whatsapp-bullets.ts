/**
 * Second Home Studio — WhatsApp handoff bullet builder (fix-mandate round 1,
 * P0-C3 + P0-C4, backend contract verified in-worktree).
 *
 * Mirrors `apps/backend-rag/backend/app/routers/lead_capture.py:38-47`
 * (`ContextLine` / `LeadCaptureRequest.whatsapp_context`) EXACTLY: at most
 * 6 rows, label <=64 chars, value <=160 chars, every row non-empty. The
 * previous implementation sent 10 rows plus a ~441-char plan-URL value —
 * guaranteed 422, silently degrading the CTA to the bare wa.me fallback.
 *
 * NO plan URL, NO readiness row (P0-C3(b)): the `cta_handoff` LeadSource
 * maps to `result_url_path = "/"`, so a `resultHash` would build a garbage
 * "Reference: https://balizero.com//<band>" line
 * (`whatsapp_deeplink.py:88-89`) — this module never emits one. The plan
 * link's ONLY carrier is SavePlanBar's "Copy plan link" (P0-C3(e)).
 *
 * The funding line is branch-aware (P1-C8): a plain under-55 deposit user
 * used to see "Funding position: —" because the old code always read
 * `seniorFunding`, which is null outside the 55+ paths.
 *
 * Sanitizes through `relevantPlan` first (P2-6) so a stale answer left over
 * from an abandoned branch (e.g. `capital` after switching to the property
 * route) never leaks into the sent bullets.
 */

import { getCopy } from "./copy";
import { relevantPlan } from "./sequence";
import type { PlanState, Verdict } from "./types";

// Mirrors lead_capture.py:38-47 ContextLine (label max_length=64,
// value max_length=160) and LeadCaptureRequest.whatsapp_context
// (max_length=6).
export const MAX_BULLET_ROWS = 6;
export const MAX_LABEL_LENGTH = 64;
export const MAX_VALUE_LENGTH = 160;

export interface WhatsAppBullet {
  label: string;
  value: string;
}

/** Resolves a wizard option's copy label. Returns null (never a "—"
 *  placeholder) for an unanswered/not-applicable value so the caller can
 *  skip the row entirely rather than send an uninformative one. */
function optionLabel(base: string, value: string | null): string | null {
  if (value === null) return null;
  if (value === "not_applicable") return "Not applicable";
  return getCopy(`${base}.options.${value}`);
}

function familySummary(plan: PlanState): string {
  const parts: string[] = [];
  if (plan.family.spouse) parts.push("spouse");
  if (plan.family.children > 0) parts.push("children");
  if (plan.family.parents > 0) parts.push("parents");
  return parts.length > 0 ? parts.join(", ") : "none";
}

/** Branch-aware funding line (P1-C8): the decisive answer differs by
 *  route/age — never blindly reads seniorFunding for a deposit/property
 *  applicant, and never blindly reads capital for a 55+ senior applicant.
 *
 *  55-59 (rules.ts row 5) is ALWAYS seniorFunding-driven — computeSequence
 *  never even asks `capital` at that age band, so there is no fallback
 *  value to show; the seniorFunding label ("Neither of these" included) IS
 *  the decisive answer. 60+ (row 6) is different: once seniorFunding is
 *  "neither"/"not_applicable"/unanswered, the rules engine falls through
 *  to the base deposit route, and `capital` (which computeSequence DOES
 *  ask for at that point) becomes the real decisive answer — reading
 *  seniorFunding there would show a value the rules engine itself no
 *  longer treats as decisive. */
function fundingLine(plan: PlanState): string | null {
  if (plan.route === "property") {
    return optionLabel("wizard.property", plan.property);
  }
  if (plan.age === "55_59") {
    return optionLabel("wizard.seniorFunding", plan.seniorFunding);
  }
  if (plan.age === "60_plus") {
    const isSeniorProductMatch =
      plan.seniorFunding === "deposit_50k_income" ||
      plan.seniorFunding === "income_only_3k";
    return isSeniorProductMatch
      ? optionLabel("wizard.seniorFunding", plan.seniorFunding)
      : optionLabel("wizard.capital", plan.capital);
  }
  return optionLabel("wizard.capital", plan.capital);
}

/**
 * Builds the <=6 WhatsApp handoff bullets for the current plan + verdict.
 * A candidate with no real answer is SKIPPED (never sent as an empty or
 * placeholder value) — the backend's `ContextLine.value` requires
 * `min_length=1`.
 */
export function buildWhatsAppBullets(
  plan: PlanState,
  verdict: Verdict,
): WhatsAppBullet[] {
  const p = relevantPlan(plan);
  const bandLabel = getCopy(`verdict.bands.${verdict.band}.heading`);

  const candidates: Array<{ label: string; value: string | null }> = [
    { label: "Route", value: optionLabel("wizard.route", p.route) },
    { label: "Age band", value: optionLabel("wizard.age", p.age) },
    { label: "Funding position", value: fundingLine(p) },
    { label: "Family", value: familySummary(p) },
    { label: "Timing", value: optionLabel("wizard.horizon", p.horizon) },
    { label: "Fit-check result", value: bandLabel },
  ];

  const bullets: WhatsAppBullet[] = [];
  for (const candidate of candidates) {
    if (bullets.length >= MAX_BULLET_ROWS) break;
    if (candidate.value === null || candidate.value.length === 0) continue;
    bullets.push({
      label: candidate.label.slice(0, MAX_LABEL_LENGTH),
      value: candidate.value.slice(0, MAX_VALUE_LENGTH),
    });
  }
  return bullets;
}
