import { describe, expect, it } from "vitest";
import {
  getServicePage,
  servicePages,
  type ServicePage,
} from "./service-pages";
import { serviceSectionContent } from "./service-section-content";
import { servicePriceIdentities } from "./service-price-identities";

const COMPLIANCE_KEYS = [
  "compliance_takeover",
  "compliance_core_retainer_monthly",
  "compliance_employer_retainer_monthly",
  "pse_registration_fixed",
  "pmse_vat_assessment",
] as const;

describe("service pages content contract", () => {
  it("publishes exactly five pillars with unique slugs", () => {
    expect(servicePages).toHaveLength(5);
    expect(new Set(servicePages.map(({ slug }) => slug)).size).toBe(5);
    expect(servicePages.map(({ slug }) => slug)).toEqual([
      "immigration",
      "company-setup",
      "tax",
      "property",
      "compliance",
    ]);
  });

  it("gives every pillar substantive, non-empty required fields", () => {
    for (const service of servicePages) {
      for (const field of [
        service.title,
        service.cardTitle,
        service.eyebrow,
        service.summary,
        service.metaDescription,
        service.whoItHelps,
        service.contactTopic,
      ] as const) {
        expect(field.trim(), service.slug).not.toBe("");
      }
      expect(service.questions.length, service.slug).toBeGreaterThanOrEqual(2);
      expect(service.image.src, service.slug).toMatch(/^\/assets\//);
      expect(service.image.alt.trim(), service.slug).not.toBe("");
    }
  });

  it("resolves the compliance entry by slug with the expected shape", () => {
    const compliance = getServicePage("compliance") as ServicePage;
    expect(compliance).toBeDefined();
    expect(compliance.title).toBe("Compliance and obligations");
    expect(compliance.cardTitle).toBe("Compliance");
    // No independent public tool exists yet for this pillar; the field stays absent
    // rather than pointing at an invented destination.
    expect(compliance.toolDestinationId).toBeUndefined();
    expect(getServicePage("not-a-real-slug")).toBeUndefined();
  });

  it("wires the compliance catalog to the five live pricing identities", () => {
    const content = serviceSectionContent.compliance;
    const names = content.catalog.flatMap((group) => group.services);
    expect(names.toSorted()).toEqual(
      [
        "Compliance Takeover",
        "Core Compliance Retainer (Monthly)",
        "Employer Compliance Retainer (Monthly)",
        "PMSE VAT Assessment",
        "PSE Registration",
      ].toSorted(),
    );
    for (const name of names) {
      expect(servicePriceIdentities[name], name).toBeDefined();
      expect(servicePriceIdentities[name].category).toBe(
        "compliance_retainers",
      );
    }
    expect(
      names.map((name) => servicePriceIdentities[name].key).toSorted(),
    ).toEqual([...COMPLIANCE_KEYS].toSorted());
  });

  it("keeps the compliance FAQ and why-now facts sourced and specific", () => {
    const content = serviceSectionContent.compliance;
    expect(content.whyNow).toBeDefined();
    expect(content.whyNow).toHaveLength(3);
    expect(content.whyNow!.join(" ")).toContain("28 June 2025");
    expect(content.whyNow!.join(" ")).toContain("26 June 2026");
    expect(content.whyNow!.join(" ")).toContain("9446");
    expect(content.whyNow!.join(" ")).toContain("10354");
    expect(content.whyNow!.join(" ")).toContain("31 May");
    expect(content.whyNow!.join(" ")).toContain("BKPM Regulation 5/2025");
    expect(content.whyNow!.join(" ")).not.toMatch(/PP 28\/2025/);
    const questions = content.faqs.map((faq) => faq.question);
    expect(questions).toEqual([
      "Do you sign filings for us?",
      "Do foreign operators without an Indonesian office need to register as a PSE?",
      "Can you get us appointed as a PMSE VAT collector?",
    ]);
    expect(content.faqs[0]!.answer).toContain(
      "Your director approves and signs",
    );
    expect(content.faqs[1]!.answer).toMatch(/Permenkominfo 5\/2020/);
    expect(content.faqs[2]!.answer).toContain("DJP appoints");
    // Never a numeric price literal in editorial content.
    for (const service of servicePages) {
      expect(JSON.stringify(service)).not.toMatch(
        /[0-9]{3},[0-9]{3}|USD [0-9]|[0-9]{1,3}\.[0-9]{3}\.[0-9]{3}/,
      );
    }
    expect(JSON.stringify(serviceSectionContent.compliance)).not.toMatch(
      /[0-9]{3},[0-9]{3}|USD [0-9]|[0-9]{1,3}\.[0-9]{3}\.[0-9]{3}/,
    );
  });
});
