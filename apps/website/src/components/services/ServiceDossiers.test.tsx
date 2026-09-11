import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import inventory from "./__fixtures__/legacy-service-inventory.json";
import pricing from "./__fixtures__/legacy-pricing-identities.json";
import {
  getServiceDossier,
  serviceDossiers,
} from "../../content/service-dossiers";
import { servicePriceIdentities } from "../../content/service-price-identities";
import { servicePages } from "../../content/service-pages";
import { serviceSectionContent } from "../../content/service-section-content";
import { ServiceSections } from "./ServiceSections";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("editorial service restoration", () => {
  it("preserves the independently pinned legacy identities and exact pricing keys", () => {
    expect(inventory).toHaveLength(108);
    expect(inventory.flatMap((item) => item.features)).toHaveLength(142);
    expect(
      serviceDossiers.map(({ id, name, domain }) => ({ id, name, domain })),
    ).toEqual(
      inventory.map(({ id, currentName: name, domain }) => ({
        id,
        name,
        domain,
      })),
    );
    expect(servicePriceIdentities).toEqual(
      Object.fromEntries(
        pricing.map(({ name, key, category }) => [name, { key, category }]),
      ),
    );
    expect(pricing).toHaveLength(91);
    const visaGroups = serviceSectionContent.immigration.catalog;
    expect(visaGroups.map(({ title }) => title)).toEqual([
      "Single-entry visits",
      "Multiple-entry visits",
      "KITAS residence services",
      "KITAP services",
      "Documents & permit administration",
      "Urgent processing enquiries",
    ]);
    const visaPricing = pricing.filter(
      ({ category }) => category !== "compliance_retainers",
    );
    expect(visaGroups.flatMap(({ services }) => services)).toEqual(
      visaPricing.map(({ name }) => name),
    );
    expect(
      visaGroups.map(
        ({ services }) =>
          new Set(services.map((name) => servicePriceIdentities[name].category))
            .size,
      ),
    ).toEqual([1, 1, 1, 1, 1, 1]);
    for (const page of servicePages) {
      expect(
        serviceSectionContent[page.slug].catalog
          .flatMap((group) => group.services)
          .toSorted(),
      ).toEqual(
        inventory
          .filter(({ domain }) => domain === page.slug)
          .map(({ currentName }) => currentName)
          .toSorted(),
      );
    }
    expect(() => getServiceDossier("Uninventoried offering")).toThrow(
      "Missing editorial dossier",
    );
  });

  it("gives every pinned record substantive purpose, distinctions, preparation and limits", () => {
    for (const { currentName } of inventory) {
      const dossier = getServiceDossier(currentName);
      for (const text of [
        dossier.purpose,
        dossier.explanation,
        dossier.distinction,
        dossier.limit,
        dossier.next,
      ]) {
        expect(text.trim(), currentName).not.toBe("");
        expect(text, currentName).not.toMatch(
          /^(contact us|coming soon|details available on request)[.!]?$/i,
        );
      }
      expect(dossier.scope.length, currentName).toBeGreaterThanOrEqual(2);
      expect(dossier.preparation.length, currentName).toBeGreaterThanOrEqual(2);
      expect(JSON.stringify(dossier)).not.toMatch(
        /\d[\d.,]*\s*IDR|Rp\s*[\d.,]+/,
      );
      if (dossier.reference) {
        expect(dossier.reference.url).toMatch(/^https:\/\//);
        expect(dossier.reference.checkedOn).toBe("2026-09-08");
      }
    }
    expect(
      new Set(serviceDossiers.map(({ explanation }) => explanation)).size,
    ).toBe(108);
  });

  it("keeps consequential neighboring choices and corrected legacy assumptions explicit", () => {
    expect(getServiceDossier("B1 Visa on Arrival (VOA)").distinction).toContain(
      "one extension",
    );
    expect(
      getServiceDossier("B1 Visa on Arrival — Extension (+30 days)")
        .distinction,
    ).toContain("does not issue a new arrival visa");
    expect(getServiceDossier("D1 Tourism (5 Years)").variantNote).toContain(
      "not a continuous stay",
    );
    expect(
      getServiceDossier("Working KITAS (Altus/Onshore)").routeNote,
    ).toContain("change of status inside Indonesia");
    expect(getServiceDossier("Working KITAS (Offshore)").routeNote).toContain(
      "before entry",
    );
    expect(getServiceDossier("Working KITAS (Extend)").routeNote).toContain(
      "existing permit",
    );
    expect(getServiceDossier("C10 Speaker Visa").distinction).toMatch(
      /remuneration|compensat/,
    );
    expect(
      getServiceDossier("Electronic Passport 10 Years").variantNote,
    ).toContain("electronic");
    expect(getServiceDossier("E33 Second Home (5 Years)").guide?.href).toBe(
      "/visa/second-home",
    );
    const regional = serviceDossiers.find(({ family }) => family === "npwpd")!;
    expect(regional.distinction).toContain("regional tax registration");
    expect(regional.distinction).toContain("not a replacement");
    expect(
      serviceDossiers.find(({ family }) => family === "zero-return")!.limit,
    ).toContain("personal return is not automatically included");
    expect(
      serviceDossiers.find(({ family }) => family === "lease")!.limit,
    ).toMatch(/25|automatic/);
    expect(
      serviceDossiers.find(({ family }) => family === "building")!.distinction,
    ).toMatch(/PBG/);
  });

  it.each(servicePages)(
    "renders real dossier content and contextual actions throughout $slug",
    async (service) => {
      const { container } = render(<ServiceSections service={service} />);
      for (const expected of inventory.filter(
        ({ domain }) => domain === service.slug,
      )) {
        const dossier = getServiceDossier(expected.currentName);
        const row = container.querySelector(`#${expected.id}`)!;
        expect(
          within(row as HTMLElement).getByRole("heading", {
            name: expected.currentName,
            level: 4,
          }),
        ).toBeInTheDocument();
        expect(
          within(row as HTMLElement).getByText(dossier.explanation),
        ).toBeVisible();
        const details = row.querySelector("details")!;
        expect(details.open).toBe(false);
        await userEvent.click(
          within(row as HTMLElement).getByText("Scope & preparation"),
        );
        expect(details.open).toBe(true);
        expect(
          within(row as HTMLElement).getByText(dossier.distinction),
        ).toBeVisible();
        for (const text of [
          ...dossier.scope,
          ...dossier.preparation,
          dossier.limit,
          dossier.next,
        ]) {
          expect(within(row as HTMLElement).getByText(text)).toBeVisible();
        }
        const quote = within(row as HTMLElement).getByRole("link", {
          name: `Request a quote for ${expected.currentName}`,
        });
        const text = new URL(quote.getAttribute("href")!).searchParams.get(
          "text",
        );
        expect(text).toContain(expected.id);
        expect(text).toContain(expected.currentName);
        if (!["immigration", "compliance"].includes(service.slug)) {
          expect(
            within(row as HTMLElement).queryByRole("button", {
              name: /price/i,
            }),
          ).not.toBeInTheDocument();
          expect(
            within(row as HTMLElement).getByText("Scope-based quotation"),
          ).toBeVisible();
        } else {
          expect(
            within(row as HTMLElement).getByRole("button", {
              name: /Check current price/,
            }),
          ).toBeInTheDocument();
        }
      }
    },
    30000,
  );

  it("isolates multiple runtime prices, retries a failure and retains the selected quote context", async () => {
    const first = pricing.find(
      ({ name }) => name === "B1 Visa on Arrival (VOA)",
    )!;
    const second = pricing.find(
      ({ name }) => name === "B1 Visa on Arrival — Extension (+30 days)",
    )!;
    const attempts = new Map<string, number>();
    const fetch = vi.fn(async (input: string) => {
      const key = new URL(input, "https://example.test").searchParams.get(
        "key",
      )!;
      attempts.set(key, (attempts.get(key) ?? 0) + 1);
      if (key === second.key && attempts.get(key) === 1)
        return Response.json({ available: false }, { status: 503 });
      return Response.json({
        available: true,
        price: key === first.key ? "123.456 IDR" : "234.567 IDR",
        verifiedOn: "2026-09-08",
      });
    });
    vi.stubGlobal("fetch", fetch);
    const { container } = render(
      <ServiceSections
        service={servicePages.find(({ slug }) => slug === "immigration")!}
      />,
    );
    expect(fetch).not.toHaveBeenCalled();
    const firstRow = within(
      container.querySelector("#svc-visa-002") as HTMLElement,
    );
    const secondRow = within(
      container.querySelector("#svc-visa-003") as HTMLElement,
    );
    const quoteBefore = secondRow
      .getByRole("link", { name: `Request a quote for ${second.name}` })
      .getAttribute("href");
    await userEvent.click(
      firstRow.getByRole("button", { name: /Check current price/ }),
    );
    expect(await firstRow.findByRole("status")).toHaveTextContent(
      "123.456 IDR",
    );
    await userEvent.click(secondRow.getByText("Scope & preparation"));
    await userEvent.click(
      secondRow.getByRole("button", { name: /Check current price/ }),
    );
    expect(await secondRow.findByRole("status")).toHaveTextContent(
      "Price unavailable",
    );
    expect(firstRow.getByRole("status")).toHaveTextContent("123.456 IDR");
    await userEvent.click(
      secondRow.getByRole("button", { name: /Check current price/ }),
    );
    expect(await secondRow.findByRole("status")).toHaveTextContent(
      "234.567 IDR",
    );
    expect(
      within(secondRow.getByRole("status")).getByText("2026-09-08"),
    ).toHaveAttribute("dateTime", "2026-09-08");
    expect(
      secondRow.getByRole("link", {
        name: `Request a quote for ${second.name}`,
      }),
    ).toHaveAttribute("href", quoteBefore);
    expect(attempts.get(first.key)).toBe(1);
    expect(attempts.get(second.key)).toBe(2);
    for (const [, options] of fetch.mock.calls as unknown as [
      string,
      RequestInit,
    ][]) {
      expect(options.cache).toBe("no-store");
      expect(options.credentials).toBe("omit");
    }
    expect(screen.queryByRole("form")).not.toBeInTheDocument();
  });
});
