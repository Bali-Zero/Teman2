import { isPmaVerdictVerified } from "./kbli-provenance";
import type { KBLICode, KBLIGoldContent } from "./kbli-types";

export interface KBLIPublicEditorial {
  gold: KBLIGoldContent | null;
  intel: KBLICode["intel_2026"] | undefined;
  withheld: boolean;
}

/**
 * Disclose generated editorial as one atomic layer.
 *
 * Gold and intel prose predate the per-record PMA provenance contract and can
 * contain ownership claims anywhere in the block.  A substring scrubber would
 * be a second, incomplete verifier, so the entire layer is withheld unless the
 * structured record has located + official locator + vintage.
 */
export function discloseKbliEditorial(
  code: KBLICode,
  gold: KBLIGoldContent | null,
): KBLIPublicEditorial {
  if (!isPmaVerdictVerified(code)) {
    return {
      gold: null,
      intel: undefined,
      withheld: Boolean(gold || code.intel_2026),
    };
  }

  return { gold, intel: code.intel_2026, withheld: false };
}

/**
 * Bali reason prose can repeat national PMA status/cap claims from the same
 * pre-provenance editorial layer. Keep the structured Bali classification,
 * but disclose its free text only when the national verdict has the complete
 * official provenance tuple.
 */
export function discloseKbliBaliReason(code: KBLICode): string | undefined {
  return isPmaVerdictVerified(code) ? code.baliL4?.reason : undefined;
}

export function neutralKbliChatOpener(code: KBLICode): string {
  return `Ask me about KBLI ${code.code} — ${code.titleEn}: its official scope, licensing, risk, or foreign-ownership verification.`;
}
