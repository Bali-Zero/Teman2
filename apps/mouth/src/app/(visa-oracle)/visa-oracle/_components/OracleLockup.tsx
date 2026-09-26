import { BZLogo } from "@balizero/core";
import type { Language } from "../_lib/flow";
import { translate } from "../_lib/i18n";

/**
 * Product identity for the top bar: the Bali Zero roundel, the product name
 * and the existing one-line descriptor. Deliberately not a link — a stray tap
 * on a logo mid-interview would drop answers the visitor chose not to save.
 */
export function OracleLockup({ language }: { language: Language }) {
  return (
    <div className="oracle-lockup">
      <BZLogo variant="full" size={36} priority />
      <span className="oracle-lockup__text">
        <span className="oracle-lockup__brand">
          <span className="oracle-lockup__wordmark">Bali Zero</span>
          <span className="oracle-lockup__name">Visa Oracle</span>
        </span>
        <span
          className="oracle-lockup__tag"
          title={translate(language, "prototype.badge.detail")}
        >
          {translate(language, "prototype.badge")}
        </span>
      </span>
    </div>
  );
}
