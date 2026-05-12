import { describe, expect, it } from "vitest";
import { buildBusinessStorySearchTerms } from "./useClientDetail";
import type { ClientCompanyLink } from "@/lib/api/crm/crm.types";

describe("buildBusinessStorySearchTerms", () => {
  it("starts from the person and deduplicates linked company names", () => {
    const links: ClientCompanyLink[] = [
      {
        link_id: 1,
        company_id: 10,
        company_name: "Bimala Investments Bali PT",
        company_type: "PT PMA",
        role: "Shareholder",
        is_primary: true,
        status: "active",
      },
      {
        link_id: 2,
        company_id: 10,
        company_name: "  Bimala Investments Bali PT  ",
        company_type: "PT PMA",
        role: "Director",
        is_primary: false,
        status: "active",
      },
    ];

    expect(buildBusinessStorySearchTerms("Giulia Del Giudice", links)).toEqual([
      "Giulia Del Giudice",
      "Bimala Investments Bali PT",
    ]);
  });

  it("keeps Ocean and Bimala fallback search terms for unlinked people", () => {
    expect(buildBusinessStorySearchTerms("Natan Kleimonov", [])).toEqual([
      "Natan Kleimonov",
      "ocean",
      "bimala",
    ]);
  });
});
