import { describe, expect, it } from "vitest";

import {
  categoriesForGroup,
  driveFolderLabel,
  formatOperator,
  formatPracticeOption,
  inferDestinationFromDocType,
} from "./destination";

const categories = [
  {
    code: "passport",
    name: "Passport",
    category_group: "immigration",
    has_expiry: true,
  },
  {
    code: "npwp",
    name: "NPWP",
    category_group: "tax",
    has_expiry: false,
  },
  {
    code: "nib",
    name: "NIB",
    category_group: "pma",
    has_expiry: false,
  },
  {
    code: "akta_pendirian",
    name: "Akta Pendirian",
    category_group: "pma",
    has_expiry: false,
  },
];

describe("intake review destination helpers", () => {
  it("preselects known document types into their profile group and category", () => {
    expect(inferDestinationFromDocType("passport", categories)).toEqual({
      group: "immigration",
      categoryCode: "passport",
    });
    expect(inferDestinationFromDocType("npwp", categories)).toEqual({
      group: "tax",
      categoryCode: "npwp",
    });
    expect(inferDestinationFromDocType("nib", categories)).toEqual({
      group: "pma",
      categoryCode: "nib",
    });
  });

  it("falls back to the group only when the mapped category code is absent", () => {
    expect(inferDestinationFromDocType("kitas", categories)).toEqual({
      group: "immigration",
      categoryCode: "",
    });
  });

  it("filters category options by profile group", () => {
    expect(categoriesForGroup(categories, "pma").map((c) => c.code)).toEqual([
      "nib",
      "akta_pendirian",
    ]);
  });

  it("formats operator and practice labels for the review queue", () => {
    expect(formatOperator("adit@balizero.com")).toBe("adit@balizero.com");
    expect(formatOperator(null)).toBe("unassigned");
    expect(
      formatPracticeOption({
        practice_id: 365,
        practice_type_code: "d12_visa",
        title: "D12 Visa 2yr",
        status: "sending_invoice",
      }),
    ).toBe("#365 — d12_visa · D12 Visa 2yr (sending_invoice)");
  });

  it("shows known Drive folder hints and leaves personal/other to the backend default", () => {
    expect(driveFolderLabel("immigration")).toBe("01_Immigration");
    expect(driveFolderLabel("pma")).toBe("02_Company");
    expect(driveFolderLabel("tax")).toBe("03_Tax");
    expect(driveFolderLabel("personal")).toBe("backend default");
  });
});
