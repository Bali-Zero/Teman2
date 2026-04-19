import { describe, it, expect } from "vitest";
import {
  buildFunnelSchema,
  buildCombinedHomepageSchema,
} from "./funnel-schema";

describe("buildFunnelSchema", () => {
  it("generates Service schema for visa funnel", () => {
    const schema = buildFunnelSchema("visa");
    expect(schema["@type"]).toBe("Service");
    expect((schema.serviceType as string).toLowerCase()).toContain("visa");
    expect((schema.provider as Record<string, unknown>)["@type"]).toBe(
      "LegalService",
    );
    expect((schema.provider as Record<string, unknown>).name).toBe("Bali Zero");
    expect(schema.areaServed).toBe("Indonesia");
  });

  it("includes 3 FAQ entries for visa funnel", () => {
    const schema = buildFunnelSchema("visa");
    const faq = schema.mainEntity as Array<Record<string, unknown>>;
    expect(faq.length).toBe(3);
    expect(faq[0]["@type"]).toBe("Question");
    expect((faq[0].acceptedAnswer as Record<string, unknown>)["@type"]).toBe(
      "Answer",
    );
  });

  it("differentiates schema by funnel", () => {
    const visa = buildFunnelSchema("visa");
    const kbli = buildFunnelSchema("kbli");
    expect(visa.serviceType).not.toBe(kbli.serviceType);
    const visaFaq = visa.mainEntity as Array<Record<string, unknown>>;
    const kbliFaq = kbli.mainEntity as Array<Record<string, unknown>>;
    expect(visaFaq[0].name).not.toBe(kbliFaq[0].name);
  });

  it("schema is serializable JSON-LD", () => {
    const schema = buildFunnelSchema("property");
    expect(() => JSON.stringify(schema)).not.toThrow();
    const parsed = JSON.parse(JSON.stringify(schema));
    expect(parsed["@context"]).toBe("https://schema.org");
  });

  it("supports all 4 funnels", () => {
    for (const funnel of ["visa", "kbli", "tax", "property"] as const) {
      const schema = buildFunnelSchema(funnel);
      expect(schema["@type"]).toBe("Service");
      expect(schema.url).toContain("balizero.com");
    }
  });
});

describe("buildCombinedHomepageSchema", () => {
  it("returns @graph with 4 Service nodes", () => {
    const combined = buildCombinedHomepageSchema();
    expect(combined["@context"]).toBe("https://schema.org");
    const graph = combined["@graph"] as Array<Record<string, unknown>>;
    expect(graph.length).toBe(4);
    expect(graph.every((s) => s["@type"] === "Service")).toBe(true);
  });
});
