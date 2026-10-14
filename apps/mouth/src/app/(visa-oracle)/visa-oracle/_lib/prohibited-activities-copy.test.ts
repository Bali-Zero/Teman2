import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { describe, expect, it } from "vitest";
import {
  PROHIBITED_ACTIVITY_COPY,
  PROHIBITED_ACTIVITY_PRODUCT_COPY,
  SUPPORT_REASON_COPY,
  UNRENDERED_PROHIBITED_ACTIVITIES,
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
    const entry = Object.prototype.hasOwnProperty.call(copyTable, id)
      ? copyTable[id]
      : undefined;
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
      missingCopyIdentifiers(
        [...liveIdentifiers].filter(
          (id) => !UNRENDERED_PROHIBITED_ACTIVITIES.has(id),
        ),
        PROHIBITED_ACTIVITY_COPY,
      ),
    ).toEqual([]);
    // An intentionally unrendered identifier is still a live pack identifier
    // and must never also carry copy.
    for (const id of UNRENDERED_PROHIBITED_ACTIVITIES) {
      expect(liveIdentifiers.has(id)).toBe(true);
      expect(Object.keys(PROHIBITED_ACTIVITY_COPY)).not.toContain(id);
    }

    const orphans = Object.keys(PROHIBITED_ACTIVITY_COPY)
      .filter((key) => !liveIdentifiers.has(key))
      .sort();
    expect(orphans).toEqual([]);
  });

  it("guilt: the census helper reports any pack identifier lacking EN/ID copy", () => {
    const live = new Set([
      "overstay",
      "unmapped_future_prohibition",
      "constructor",
    ]);
    expect(missingCopyIdentifiers(live, PROHIBITED_ACTIVITY_COPY)).toEqual([
      "constructor",
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

    expect(allEntries.length).toBeGreaterThanOrEqual(29);

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
      en: "Doing work that does not match your stay permit",
      id: "Melakukan pekerjaan yang tidak sesuai dengan izin tinggal",
    });

    const expectedReporting = {
      en: "Working or studying without reporting it to Immigration as a dual activity",
      id: "Bekerja atau menempuh pendidikan tanpa melaporkannya ke Imigrasi sebagai rangkap kegiatan",
    };

    for (const code of ["E33", "E33E"] as const) {
      const resolved = prohibitedActivitiesFor(code, [
        "work_inconsistent_with_permit",
      ]);
      expect(resolved).toEqual([expectedReporting]);
      expect(resolved[0].en).toContain(
        "reporting it to Immigration as a dual activity",
      );
      expect(resolved[0].id).toContain(
        "melaporkannya ke Imigrasi sebagai rangkap kegiatan",
      );
      expect(resolved[0].en).not.toMatch(/issuing/i);
      expect(resolved[0].id).not.toMatch(/menerbitkan/i);
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

  it("maps operational_work to company operational work with no bridging/peralihan wording on E28B/E28C/E28F", () => {
    expect(PROHIBITED_ACTIVITY_COPY.operational_work).toEqual({
      en: "Performing day-to-day operational work in the company",
      id: "Melakukan pekerjaan operasional sehari-hari di perusahaan",
    });

    const { products } = newestSignedPack();
    const withOperationalWork = products.filter((product) =>
      (product.prohibited_activities ?? []).includes("operational_work"),
    );
    expect(
      withOperationalWork.map((product) => product.product_code).sort(),
    ).toEqual(["E28B", "E28C", "E28F"]);

    for (const product of withOperationalWork) {
      const resolved = prohibitedActivitiesFor(
        product.product_code ?? "",
        product.prohibited_activities,
      );
      expect(resolved.length).toBeGreaterThan(0);
      for (const item of resolved) {
        expect(item.en, `${product.product_code} en`).not.toMatch(
          /bridging|peralihan/i,
        );
        expect(item.id, `${product.product_code} id`).not.toMatch(
          /bridging|peralihan/i,
        );
      }
    }

    const keysWithBridgingTerms = Object.entries(PROHIBITED_ACTIVITY_COPY)
      .filter(
        ([, copy]) =>
          /bridging|peralihan/i.test(copy.en) ||
          /bridging|peralihan/i.test(copy.id),
      )
      .map(([key]) => key);
    for (const key of keysWithBridgingTerms) {
      expect(["employment_relationship", "exit_terminates_permit"]).toContain(
        key,
      );
    }
  });

  it("keeps the work-required exception clause only on sale_of_goods_or_services, keeps selling_goods_services flat, and scopes E33G to remote work without an exception clause", () => {
    expect(PROHIBITED_ACTIVITY_COPY.sale_of_goods_or_services).toEqual({
      en: "Selling goods or services, unless your work requires it",
      id: "Menjual barang atau jasa, kecuali diperlukan dalam pekerjaan Anda",
    });
    expect(PROHIBITED_ACTIVITY_COPY.sale_of_goods_or_services.en).toContain(
      "unless your work requires it",
    );
    expect(PROHIBITED_ACTIVITY_COPY.sale_of_goods_or_services.id).toContain(
      "kecuali diperlukan dalam pekerjaan Anda",
    );

    expect(PROHIBITED_ACTIVITY_COPY.selling_goods_services).toEqual({
      en: "Selling goods or services",
      id: "Menjual barang atau jasa",
    });
    expect(PROHIBITED_ACTIVITY_COPY.selling_goods_services.en).not.toMatch(
      /unless|kecuali/i,
    );
    expect(PROHIBITED_ACTIVITY_COPY.selling_goods_services.id).not.toMatch(
      /unless|kecuali/i,
    );

    expect(
      PROHIBITED_ACTIVITY_COPY.sale_of_goods_or_services_beyond_remote_work,
    ).toEqual({
      en: "Selling goods or services in Indonesia beyond your remote work for an employer outside Indonesia",
      id: "Menjual barang atau jasa di Indonesia di luar pekerjaan jarak jauh untuk pemberi kerja di luar Indonesia",
    });
    expect(
      PROHIBITED_ACTIVITY_COPY.sale_of_goods_or_services_beyond_remote_work.en,
    ).not.toMatch(/unless|kecuali/i);
    expect(
      PROHIBITED_ACTIVITY_COPY.sale_of_goods_or_services_beyond_remote_work.id,
    ).not.toMatch(/unless|kecuali/i);

    const both = prohibitedActivitiesFor("D1", [
      "selling_goods_services",
      "sale_of_goods_or_services",
    ]);
    expect(both).toHaveLength(2);
    expect(new Set(both.map((item) => item.en)).size).toBe(2);
  });

  it("pins guarantee_value_below_commitment, deposit_value_below_commitment, exit_terminates_permit, and wording updates in EN and ID", () => {
    expect(PROHIBITED_ACTIVITY_COPY.guarantee_value_below_commitment).toEqual({
      en: "Letting the immigration guarantee fall below the amount in your commitment letter while the permit is valid",
      id: "Membiarkan nilai Jaminan Keimigrasian turun di bawah nilai dalam surat pernyataan komitmen selama izin tinggal berlaku",
    });
    expect(PROHIBITED_ACTIVITY_COPY.deposit_value_below_commitment).toEqual({
      en: "Letting the immigration guarantee deposit fall below the amount in your commitment letter while the permit is valid",
      id: "Membiarkan nilai deposito Jaminan Keimigrasian turun di bawah nilai dalam surat pernyataan komitmen selama izin tinggal berlaku",
    });
    expect(PROHIBITED_ACTIVITY_COPY.exit_terminates_permit).toEqual({
      en: "Leaving Indonesia ends this permit",
      id: "Izin ini berakhir apabila Anda keluar dari wilayah Indonesia",
    });
    expect(
      PROHIBITED_ACTIVITY_COPY.indonesian_source_compensation_including_in_kind,
    ).toEqual({
      en: "Receiving compensation, wages, or in-kind benefits from an Indonesian source",
      id: "Menerima imbalan atau upah, termasuk dalam bentuk barang, dari sumber di Indonesia",
    });
    // Official pages and the price catalogue allow business meetings on
    // A1/B1/C1/C6, so the pack's business_meetings identifier renders nothing.
    for (const code of ["A1", "B1", "C1", "C6"]) {
      expect(prohibitedActivitiesFor(code, ["business_meetings"])).toEqual([]);
    }
    expect(JSON.stringify(PROHIBITED_ACTIVITY_COPY).toLowerCase()).not.toMatch(
      /business meeting|pertemuan bisnis/,
    );
    expect(PROHIBITED_ACTIVITY_COPY.study).toEqual({
      en: "Studying in Indonesia",
      id: "Menempuh pendidikan di Indonesia",
    });
  });

  it("drops unknown identifiers, Object.prototype keys, and duplicate identifiers without leaking raw codes", () => {
    const resolved = prohibitedActivitiesFor("E33", [
      "overstay",
      "unknown_future_code_xyz",
      "constructor",
      "toString",
      "overstay",
      "sale_of_goods_or_services",
    ]);
    expect(resolved).toEqual([
      PROHIBITED_ACTIVITY_COPY.overstay,
      PROHIBITED_ACTIVITY_COPY.sale_of_goods_or_services,
    ]);
    expect(JSON.stringify(resolved)).not.toContain("unknown_future_code_xyz");
    expect(
      prohibitedActivitiesFor("constructor", ["constructor", "toString"]),
    ).toEqual([]);
  });
});
