import { isPmaVerdictVerified } from "./kbli-provenance";
import { hasPublishablePmaCap } from "./kbli-pma-disclosure";
import { neutralKbliChatOpenerText } from "./kbli-editorial-certification";
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
 * contain ownership claims anywhere in the block. The data loaders admit only
 * exact, hash-certified editorial bound to the current PMA fingerprint; this
 * final boundary also requires the complete structured provenance tuple and a
 * publishable cap. A substring scrubber would be a second, incomplete verifier.
 */
export function discloseKbliEditorial(
  code: KBLICode,
  gold: KBLIGoldContent | null,
): KBLIPublicEditorial {
  if (!isPmaVerdictVerified(code) || !hasPublishablePmaCap(code.pma)) {
    return {
      gold: null,
      intel: undefined,
      withheld: true,
    };
  }

  const intel = code.intel_2026;
  return {
    gold,
    intel,
    withheld: gold === null && intel === undefined,
  };
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
  return neutralKbliChatOpenerText(code.code);
}
