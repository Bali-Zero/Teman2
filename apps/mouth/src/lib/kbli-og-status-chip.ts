import { getCode } from "@/lib/kbli-data";
import {
  isBaliL4BlockVerifiedForBareClaim,
  isPmaVerdictVerified,
} from "@/lib/kbli-provenance";
import { isSourcedBaliClosure } from "@/lib/kbli-pma-disclosure";

/**
 * The social-preview status chip's pure label/color logic, extracted out of
 * `app/api/og/kbli/[code]/route.tsx` (review r2 BLOCKER B1): a Next.js route
 * module may only export route handlers/config (`GET`, `runtime`, …) —
 * `next build` fails with TS2344 on any other export from a route file, even
 * though `tsc --noEmit` and `next dev` do not catch it. This module has no
 * such restriction and is the unit under test instead, since next/og's
 * `ImageResponse` cannot be rendered under vitest.
 */
export function statusChip(kbli: NonNullable<ReturnType<typeof getCode>>): {
  label: string;
  color: string;
} {
  const verified = isPmaVerdictVerified(kbli);
  // Added 2026-09-16 (W-J B1 disclose): a Bali applied closure sourced to a
  // public press release is self-sufficient evidence for the SOCIAL PREVIEW
  // too — checked before the neutral "verify" fallback below, which would
  // otherwise say nothing about a closure the code's own page now discloses.
  if (!verified && isSourcedBaliClosure(kbli.baliL4)) {
    // Review F1(f): a scoped closure (the hotel rows) or a below-bare-claim
    // confidence/review flag must not chip the same unqualified "closed" a
    // HIGH-confidence, unscoped, whole-code closure gets — the social
    // preview has no room for the scope text itself, so it says "check
    // scope" instead of asserting a bar the record does not make bare.
    const wholeCodeConfident =
      isBaliL4BlockVerifiedForBareClaim(kbli) &&
      !kbli.baliL4?.closure?.scopeQualifier;
    return wholeCodeConfident
      ? { label: "BALI: CLOSED TO PMA", color: "#e0645a" }
      : { label: "BALI: CLOSED — CHECK SCOPE", color: "#e0645a" };
  }
  if (!verified) {
    return { label: "PMA: VERIFY", color: "#8f96a3" };
  }
  if (kbli.baliL4?.blocked) {
    return { label: "BALI: BLOCKED", color: "#e0645a" };
  }
  // GARUDA-FILIERA Fase-1 cure #4 (2026-07-17): a code whose Bali risk tier
  // was carried over from a different activity (code-number collision) is
  // neither blocked nor confirmed open — a neutral verify chip, not the
  // green "OPEN" the pma.status fallthrough below would otherwise render.
  // Added 2026-09-15 (W-J B1): off Bali's applied PMA closure list, but the
  // risk tier that used to blanket-block it was only ever named in the
  // Governor's own request letter — a "verify" chip, never the green "OPEN"
  // the pma.status fallthrough below would otherwise render.
  if (
    kbli.baliL4?.status === "NON_CLASSIFICABILE" ||
    kbli.baliL4?.status === "ATTENZIONE_FASCIA_BALI"
  ) {
    return { label: "BALI: VERIFY", color: "#c9a227" };
  }
  switch (kbli.pma.status) {
    case "open":
      return { label: "OPEN", color: "#5aab6e" };
    case "restricted":
      return { label: "RESTRICTED", color: "#c9a227" };
    case "closed":
      return { label: "CLOSED", color: "#e0645a" };
    default:
      // A complete provenance tuple does not make an unrecognised vocabulary
      // token mean "open". Keep the social preview neutral rather than turning
      // future/legacy status values into a foreign-ownership permission.
      return { label: "PMA: VERIFY", color: "#8f96a3" };
  }
}
