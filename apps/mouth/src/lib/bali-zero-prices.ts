// =============================================================================
// Bali Zero company-service prices — sourced from PricingTool, NEVER hardcoded.
//
// Absolute rule (CLAUDE.md §8.11 "PricingTool Only"): Bali Zero prices live in
// ONE place — `apps/backend-rag/backend/data/bali_zero_official_prices_2026.json`,
// the file `PricingService._load_prices()` reads ("PricingTool"). The Next.js
// frontend is built/deployed separately on Vercel and cannot reach the backend
// at request time for two annual-static company prices, so it reads a COMMITTED,
// GENERATED copy under `apps/mouth/data/bali-zero-prices.json`.
//
//   - The copy is produced by `scripts/sync_frontend_prices.py` FROM the
//     PricingTool canonical (it is NOT a hand-authored re-hardcode).
//   - Drift is CI-blocked: `bali-zero-prices.test.ts` asserts the committed copy
//     equals the canonical catalog, so a stale price cannot ship silently.
//   - A future catalog change therefore propagates: edit the canonical JSON,
//     run the sync script, and this module + the consuming component update.
//
// This module is consumed by server components at BUILD time (the KBLI [code]
// page is statically generated, `revalidate = 604800`), exactly like
// `kbli-gold-codes.ts` / `kbli-data.ts` read their committed `data/*.json`.
// =============================================================================

import fs from "fs";
import path from "path";

export interface CompanyServicePrice {
  /** Display name from the PricingTool catalog. */
  name: string;
  /** Price string verbatim from PricingTool, e.g. "20.000.000 IDR". */
  price: string;
  /** Stable key (matches the catalog `icon_id`). */
  iconId: string;
}

interface RawPricesFile {
  company_services?: Record<
    string,
    { name?: string; price?: string; icon_id?: string }
  >;
}

let _byIconId: Record<string, CompanyServicePrice> | null = null;

function loadCompanyServices(): Record<string, CompanyServicePrice> {
  if (_byIconId) return _byIconId;
  try {
    const jsonPath = path.join(process.cwd(), "data", "bali-zero-prices.json");
    const raw = JSON.parse(fs.readFileSync(jsonPath, "utf-8")) as RawPricesFile;
    const services: Record<string, CompanyServicePrice> = {};
    for (const [iconId, svc] of Object.entries(raw.company_services ?? {})) {
      if (!svc?.price) continue;
      services[iconId] = {
        name: svc.name ?? iconId,
        price: svc.price,
        iconId: svc.icon_id ?? iconId,
      };
    }
    // Only memoize a successful, non-empty read — a transient/cold-start read
    // failure must NOT poison the module cache for the server's lifetime
    // (the next render retries instead of permanently serving no prices).
    if (Object.keys(services).length > 0) {
      _byIconId = services;
      return _byIconId;
    }
    return services;
  } catch {
    return {};
  }
}

/**
 * Look up a company-service price by its stable `icon_id`.
 *
 * Returns `undefined` if the catalog is missing the service (the consuming
 * component must handle that — never substitute a hardcoded literal).
 */
export function getCompanyServicePrice(
  iconId: string,
): CompanyServicePrice | undefined {
  return loadCompanyServices()[iconId];
}

/**
 * Render the PT PMA + Virtual Office prices the KBLI consultation CTA shows.
 * Each value comes straight from PricingTool via the synced catalog; if a
 * service is somehow absent, the field is `null` (the CTA hides that card)
 * rather than falling back to a hardcoded number.
 */
export function getKbliCtaPrices(): {
  ptPma: string | null;
  virtualOffice: string | null;
} {
  return {
    ptPma: getCompanyServicePrice("company-pma")?.price ?? null,
    virtualOffice: getCompanyServicePrice("company-virtual")?.price ?? null,
  };
}
