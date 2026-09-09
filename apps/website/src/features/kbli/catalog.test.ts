// @vitest-environment node
import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  catalogSearch,
  getAllCodes,
  getCode,
  getSections,
  isPmaVerdictVerified,
  publicEditorial,
  publicItem,
} from "./catalog.server";
import { GET } from "../../app/api/kbli/search/route";

describe("native KBLI uses the canonical guarded corpus", () => {
  it("resolves every runtime dataset to the immutable Mouth source", () => {
    for (const name of [
      "KBLI_2025_FINAL_CLEAN.json",
      "kbli-gold-all.json",
      "kbli-risk-disputes.json",
      "kbli-perpres-slice-disclosures.json",
      "perpres-locators.json",
    ]) {
      expect(fs.lstatSync(path.resolve("data", name)).isSymbolicLink()).toBe(
        true,
      );
      expect(fs.realpathSync(path.resolve("data", name))).toBe(
        fs.realpathSync(path.resolve("../mouth/data", name)),
      );
    }
    const raw = JSON.parse(
      fs.readFileSync("data/KBLI_2025_FINAL_CLEAN.json", "utf8"),
    );
    expect(getAllCodes().length).toBe(raw.data.length);
    expect(new Set(getAllCodes().map((code) => code.code)).size).toBe(
      raw.data.length,
    );
  });
  it("finds exact codes and paginates the real catalog", () => {
    const code = getAllCodes()[30];
    expect(catalogSearch({ q: code.code }).items[0].code).toBe(code.code);
    const first = catalogSearch({});
    const second = catalogSearch({ page: "2" });
    expect(first.items).toHaveLength(24);
    expect(
      second.items.some((item) =>
        first.items.some((previous) => previous.code === item.code),
      ),
    ).toBe(false);
    expect(catalogSearch({ page: "99999" }).page).toBe(first.pages);
  });
  it("keeps section results inside the requested sector", () => {
    for (const section of getSections()) {
      const result = catalogSearch({}, section.id);
      expect(result.count).toBe(section.codeCount);
      expect(result.items.every((item) => item.section === section.id)).toBe(
        true,
      );
    }
  });
  it("never promotes an unverified ownership record into a verified filter", () => {
    const unknown = getAllCodes().find((code) => !isPmaVerdictVerified(code));
    expect(unknown).toBeDefined();
    expect(publicItem(unknown!).ownershipVerified).toBe(false);
    expect(publicEditorial(unknown!).withheld).toBe(true);
    for (const status of ["open", "restricted", "closed"]) {
      const result = catalogSearch({ pma: status });
      expect(
        result.items.every((item) => isPmaVerdictVerified(getCode(item.code)!)),
      ).toBe(true);
      expect(
        catalogSearch({ q: unknown!.code, pma: status }).items.some(
          (item) => item.code === unknown!.code,
        ),
      ).toBe(false);
    }
  });
  it("retains inherited licensing and pending verification in the comparison projection", () => {
    const rows = getAllCodes().map(publicItem);
    expect(rows.some((row) => row.licensingPending)).toBe(true);
    expect(rows.some((row) => row.licensingInherited.length > 0)).toBe(true);
  });
  it("returns only requested real codes and rejects malformed or oversized comparisons", async () => {
    const selected = getAllCodes().slice(0, 2);
    const response = GET(
      new Request(
        `http://localhost/api/kbli/search?codes=${selected.map((code) => code.code).join(",")}`,
      ),
    );
    expect(response.status).toBe(200);
    expect(
      (await response.json()).items.map((item: { code: string }) => item.code),
    ).toEqual(selected.map((code) => code.code));
    expect(
      GET(new Request("http://localhost/api/kbli/search?codes=../../private"))
        .status,
    ).toBe(400);
    expect(
      GET(
        new Request(
          "http://localhost/api/kbli/search?codes=11111,11112,11113,11114,11115,11116,11117",
        ),
      ).status,
    ).toBe(400);
    expect(
      (
        await GET(
          new Request("http://localhost/api/kbli/search?codes=00000"),
        ).json()
      ).items,
    ).toEqual([]);
  });
});
