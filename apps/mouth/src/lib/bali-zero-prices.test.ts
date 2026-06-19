import fs from "fs";
import path from "path";
import { describe, expect, it } from "vitest";

import { getCompanyServicePrice, getKbliCtaPrices } from "./bali-zero-prices";

/**
 * Bali Zero prices come from PricingTool, NEVER from a hardcoded literal
 * (CLAUDE.md §8.11). These tests pin that contract:
 *
 *  1. The frontend lib resolves the two KBLI-CTA prices from the synced catalog
 *     (`apps/mouth/data/bali-zero-prices.json`) — not a constant in code.
 *  2. That synced catalog is in PARITY with the PricingTool canonical
 *     (`apps/backend-rag/backend/data/bali_zero_official_prices_2026.json`). If
 *     the canonical changes and the sync script (`scripts/sync_frontend_prices.py`)
 *     was not re-run, this test FAILS — drift cannot ship silently, and a real
 *     catalog change propagates to the frontend.
 *  3. The consuming component (`KBLIConsultationCTA`) reads the source, not a
 *     literal — asserted by grepping the component for `getKbliCtaPrices` and
 *     for the absence of the hardcoded `20.000.000` / `5.000.000` strings.
 */

// Repo root from apps/mouth/src/lib → up 4 levels.
const REPO_ROOT = path.resolve(__dirname, "../../../..");
const CANONICAL = path.join(
  REPO_ROOT,
  "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json",
);
const CTA_COMPONENT = path.join(
  REPO_ROOT,
  "apps/mouth/src/components/kbli/KBLIConsultationCTA.tsx",
);

function canonicalCompanyServices(): Record<
  string,
  { name?: string; price?: string; icon_id?: string }
> {
  const raw = JSON.parse(fs.readFileSync(CANONICAL, "utf-8"));
  return raw.services.company_services;
}

describe("bali-zero-prices (PricingTool source-of-truth)", () => {
  it("resolves the KBLI-CTA prices from the synced catalog, not a literal", () => {
    const { ptPma, virtualOffice } = getKbliCtaPrices();
    // Values are present and come from the catalog (verbatim "… IDR" form).
    expect(ptPma).toBe("20.000.000 IDR");
    expect(virtualOffice).toBe("5.000.000 IDR");
  });

  it("keys company services by stable icon_id", () => {
    expect(getCompanyServicePrice("company-pma")?.name).toBe(
      "New Company (PT PMA)",
    );
    expect(getCompanyServicePrice("company-virtual")?.name).toBe(
      "Virtual Office",
    );
    expect(getCompanyServicePrice("does-not-exist")).toBeUndefined();
  });

  it("is in parity with the PricingTool canonical (no silent drift)", () => {
    const canonical = canonicalCompanyServices();
    const byIcon: Record<string, string> = {};
    for (const svc of Object.values(canonical)) {
      if (svc.icon_id && svc.price) byIcon[svc.icon_id] = svc.price;
    }
    // Every price the frontend serves must equal the canonical value.
    for (const iconId of ["company-pma", "company-virtual"]) {
      expect(getCompanyServicePrice(iconId)?.price).toBe(byIcon[iconId]);
    }
  });
});

describe("KBLIConsultationCTA reads from the pricing source", () => {
  const src = fs.readFileSync(CTA_COMPONENT, "utf-8");

  it("imports the PricingTool-backed price helper", () => {
    expect(src).toMatch(/getKbliCtaPrices/);
    expect(src).toMatch(/from "@\/lib\/bali-zero-prices"/);
  });

  it("does NOT hardcode the price figures in the component", () => {
    // The literals must live only in the catalog, never in the component.
    expect(src).not.toMatch(/20\.000\.000/);
    expect(src).not.toMatch(/5\.000\.000/);
  });
});
