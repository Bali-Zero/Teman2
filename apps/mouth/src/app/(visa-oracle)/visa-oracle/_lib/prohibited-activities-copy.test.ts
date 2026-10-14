import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { describe, expect, it } from "vitest";
import {
  PROHIBITED_ACTIVITY_COPY,
  PROHIBITED_ACTIVITY_PRODUCT_COPY,
  SUPPORT_REASON_COPY,
  prohibitedActivitiesFor,
} from "./engine-adapter";
import type { LocalizedText } from "./outcome-view-model";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PACKS_DIR = path.resolve(
  HERE,
  "../../../../../../..",
  "apps/backend-rag/backend/services/visa_engine/contracts/packs",
);

interface SignedPackProduct {
  product_code?: string;
  prohibited_activities?: string[];
}

interface SignedPackPayload {
  sequence?: number;
  products?: SignedPackProduct[];
}

function newestSignedPack(): {
  sequence: number;
  products: SignedPackProduct[];
} {
  const candidates = fs
    .readdirSync(PACKS_DIR)
    .map((name) => {
      const match = /^rulepack-prod-(\d+)\.signed\.json$/.exec(name);
      return match
        ? { sequence: Number(match[1]), file: path.join(PACKS_DIR, name) }
        : null;
    })
    .filter(
      (entry): entry is { sequence: number; file: string } => entry !== null,
    )
    .sort((a, b) => b.sequence - a.sequence);

  if (candidates.length === 0) {
    throw new Error(`no signed production packs found under ${PACKS_DIR}`);
  }

  const newest = candidates[0];
  const raw = JSON.parse(fs.readFileSync(newest.file, "utf-8")) as {
    payload?: SignedPackPayload;
  };
  const products = raw.payload?.products ?? [];
  return { sequence: newest.sequence, products };
}

function prohibitedIdentifiersInNewestPack(): Set<string> {
  const { products } = newestSignedPack();
  const identifiers = new Set<string>();
  for (const product of products) {
    for (const id of product.prohibited_activities ?? []) {
      identifiers.add(id);
    }
  }
  return identifiers;
}

function missingCopyIdentifiers(
  packIdentifiers: Iterable<string>,
  copyTable: Readonly<Record<string, LocalizedText>>,
): string[] {
  const missing: string[] = [];
  for (const id of packIdentifiers) {
    const entry = copyTable[id];
    if (!entry || !entry.en.trim() || !entry.id.trim()) {
      missing.push(id);
    }
  }
  return missing.sort();
}

describe("prohibited_activities copy census (PR-20)", () => {
  it("covers every prohibited_activities identifier in the newest signed pack, with no orphan keys", () => {
    const { sequence, products } = newestSignedPack();
    expect(sequence).toBeGreaterThanOrEqual(29);
    expect(products.length).toBeGreaterThan(0);

    const liveIdentifiers = prohibitedIdentifiersInNewestPack();
    // Guard the guard: seq-29 carries 28 distinct identifiers.
    expect(liveIdentifiers.size).toBeGreaterThanOrEqual(28);

    expect(
      missingCopyIdentifiers(liveIdentifiers, PROHIBITED_ACTIVITY_COPY),
    ).toEqual([]);

    const orphans = Object.keys(PROHIBITED_ACTIVITY_COPY)
      .filter((key) => !liveIdentifiers.has(key))
      .sort();
    expect(orphans).toEqual([]);
  });

  it("guilt: the census helper reports any pack identifier lacking EN/ID copy", () => {
    const live = new Set(["overstay", "unmapped_future_prohibition"]);
    expect(missingCopyIdentifiers(live, PROHIBITED_ACTIVITY_COPY)).toEqual([
      "unmapped_future_prohibition",
    ]);
  });

  it("enforces EN/ID parity, no raw snake_case identifiers, and no digits in any prohibition line", () => {
    const allEntries: Array<{ label: string; copy: LocalizedText }> = [
      ...Object.entries(PROHIBITED_ACTIVITY_COPY).map(([key, copy]) => ({
        label: key,
        copy,
      })),
      ...Object.entries(PROHIBITED_ACTIVITY_PRODUCT_COPY).flatMap(
        ([productCode, map]) =>
          Object.entries(map).map(([key, copy]) => ({
            label: `${productCode}.${key}`,
            copy,
          })),
      ),
    ];

    expect(allEntries.length).toBeGreaterThanOrEqual(30);

    for (const { label, copy } of allEntries) {
      expect(copy.en.trim().length, `${label}: empty en`).toBeGreaterThan(0);
      expect(copy.id.trim().length, `${label}: empty id`).toBeGreaterThan(0);
      expect(copy.en, `${label}: en === id`).not.toBe(copy.id);
      // Never leak a snake_case or screaming-snake identifier into prose.
      expect(copy.en, `${label}: snake_case in en`).not.toMatch(
        /\b[a-z0-9]+_[a-z0-9_]+\b/i,
      );
      expect(copy.id, `${label}: snake_case in id`).not.toMatch(
        /\b[a-z0-9]+_[a-z0-9_]+\b/i,
      );
      // Prohibition lines must never state numeric figures/thresholds.
      expect(copy.en, `${label}: digit in en`).not.toMatch(/\d/);
      expect(copy.id, `${label}: digit in id`).not.toMatch(/\d/);
    }
  });

  it("keeps work_inconsistent_with_permit base copy generic for E33A/B/C/F and applies dual-activity reporting only to E33 and E33E", () => {
    expect(PROHIBITED_ACTIVITY_COPY.work_inconsistent_with_permit).toEqual({
      en: "Work that does not match your stay permit",
      id: "Melakukan pekerjaan yang tidak sesuai dengan izin tinggal",
    });

    const expectedReporting = {
      en: "Working or studying without reporting it as a dual activity to the immigration office that issued your permit",
      id: "Bekerja atau menempuh pendidikan tanpa melaporkan rangkap kegiatan ke kantor imigrasi yang menerbitkan izin tinggal Anda",
    };

    for (const code of ["E33", "E33E"] as const) {
      const resolved = prohibitedActivitiesFor(code, [
        "work_inconsistent_with_permit",
      ]);
      expect(resolved).toEqual([expectedReporting]);
      expect(resolved[0].en).toContain("reporting it as a dual activity");
      expect(resolved[0].id).toContain("melaporkan rangkap kegiatan");
    }

    for (const code of ["E33A", "E33B", "E33C", "E33F"] as const) {
      const resolved = prohibitedActivitiesFor(code, [
        "work_inconsistent_with_permit",
      ]);
      expect(resolved).toEqual([
        PROHIBITED_ACTIVITY_COPY.work_inconsistent_with_permit,
      ]);
      expect(resolved[0].en).not.toMatch(/dual activity|rangkap/i);
      expect(resolved[0].id).not.toMatch(/rangkap kegiatan|melaporkan/i);
    }

    // Consistent with E33_EMPLOYMENT_NOT_COVERED (reporting/pelaporan, not permission/izin).
    expect(SUPPORT_REASON_COPY.E33_EMPLOYMENT_NOT_COVERED.en).toContain(
      "dual-activity reporting (rangkap kegiatan)",
    );
    expect(SUPPORT_REASON_COPY.E33_EMPLOYMENT_NOT_COVERED.id).toContain(
      "pelaporan rangkap kegiatan",
    );
  });

  it("includes the official work-required exception clause on selling prohibitions and remote-work scoping on E33G", () => {
    expect(PROHIBITED_ACTIVITY_COPY.sale_of_goods_or_services).toEqual({
      en: "Selling goods or services, unless your work requires it",
      id: "Menjual barang atau jasa, kecuali diperlukan dalam pekerjaan Anda",
    });
    expect(PROHIBITED_ACTIVITY_COPY.selling_goods_services).toEqual({
      en: "Selling goods or services, unless your work requires it",
      id: "Menjual barang atau jasa, kecuali diperlukan dalam pekerjaan Anda",
    });

    const e33gSale =
      PROHIBITED_ACTIVITY_COPY.sale_of_goods_or_services_beyond_remote_work;
    expect(e33gSale.en).toContain("Selling goods or services");
    expect(e33gSale.en).toContain("beyond remote work");
    expect(e33gSale.en).toContain("unless your work requires it");
    expect(e33gSale.id).toContain("Menjual barang atau jasa");
    expect(e33gSale.id).toContain("di luar pekerjaan jarak jauh");
    expect(e33gSale.id).toContain("kecuali diperlukan dalam pekerjaan Anda");
  });

  it("pins guarantee_value_below_commitment, deposit_value_below_commitment, and exit_terminates_permit in EN and ID", () => {
    expect(PROHIBITED_ACTIVITY_COPY.guarantee_value_below_commitment).toEqual({
      en: "Letting the immigration guarantee fall below the amount in your commitment letter while the permit is valid",
      id: "Membiarkan nilai Jaminan Keimigrasian turun di bawah nilai dalam surat pernyataan komitmen selama izin tinggal berlaku",
    });
    expect(PROHIBITED_ACTIVITY_COPY.deposit_value_below_commitment).toEqual({
      en: "Letting the immigration guarantee deposit fall below the amount in your commitment letter while the permit is valid",
      id: "Membiarkan nilai deposito Jaminan Keimigrasian turun di bawah nilai dalam surat pernyataan komitmen selama izin tinggal berlaku",
    });
    expect(PROHIBITED_ACTIVITY_COPY.exit_terminates_permit).toEqual({
      en: "Leaving Indonesia — leaving ends this permit",
      id: "Keluar dari Indonesia — keluar mengakhiri izin ini",
    });
  });

  it("drops unknown identifiers silently without leaking raw codes", () => {
    const resolved = prohibitedActivitiesFor("E33", [
      "overstay",
      "unknown_future_code_xyz",
      "sale_of_goods_or_services",
    ]);
    expect(resolved).toEqual([
      PROHIBITED_ACTIVITY_COPY.overstay,
      PROHIBITED_ACTIVITY_COPY.sale_of_goods_or_services,
    ]);
    expect(JSON.stringify(resolved)).not.toContain("unknown_future_code_xyz");
  });
});
