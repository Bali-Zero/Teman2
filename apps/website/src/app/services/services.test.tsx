import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import {
  ServiceDetail,
  ServicesOverview,
} from "../../components/services/ServiceJourneys";
import { destinationIntents, getDestination } from "../../content/destinations";
import { servicePages } from "../../content/service-pages";
import { generateMetadata, generateStaticParams } from "./[slug]/page";
import { metadata as overviewMetadata } from "./page";
import NotFound from "../not-found";
import { serviceSectionContent } from "../../content/service-section-content";
import LegacyVisaRoute from "./visa/page";
import LegacyCompanyRoute from "./company/page";

afterEach(cleanup);

describe("service journeys", () => {
  it("keeps legacy visa and company links resolvable", () => {
    for (const [route, target] of [
      [LegacyVisaRoute, "/services/immigration"],
      [LegacyCompanyRoute, "/services/company-setup"],
    ] as const) {
      try {
        route();
        throw new Error("Expected redirect");
      } catch (error) {
        expect((error as { digest: string }).digest).toContain(`;${target};`);
      }
    }
  });
  it("publishes an overview and four resolvable local journeys", () => {
    render(<ServicesOverview />);
    const main = screen.getByRole("main");
    const localRoutes = new Set([
      "/",
      "/services",
      ...servicePages.map(({ slug }) => `/services/${slug}`),
    ]);
    const links = [...main.querySelectorAll('a[href^="/"]')];
    expect(servicePages).toHaveLength(4);
    expect(generateStaticParams()).toEqual(
      servicePages.map(({ slug }) => ({ slug })),
    );
    for (const link of links) {
      const destination = new URL(
        link.getAttribute("href")!,
        "https://example.test",
      );
      expect(localRoutes.has(destination.pathname)).toBe(true);
      if (destination.hash) {
        expect(destination.pathname).toBe("/services/tax");
        expect(
          serviceSectionContent.tax.catalog.map(
            (_, index) => "#catalog-" + (index + 1),
          ),
        ).toContain(destination.hash);
      }
    }
    for (const service of servicePages) {
      expect(
        within(main).getByRole("link", {
          name: `Explore this service: ${service.cardTitle}`,
        }),
      ).toHaveAttribute("href", `/services/${service.slug}`);
    }
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    screen.getByRole("main").focus();
    expect(screen.getByRole("main")).toHaveFocus();
    expect(screen.queryByRole("form")).not.toBeInTheDocument();
  });

  it.each(servicePages)("renders one complete $slug page", (service) => {
    const { container } = render(<ServiceDetail service={service} />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    screen.getByRole("main").focus();
    expect(screen.getByRole("main")).toHaveFocus();
    expect(
      screen.getByRole("navigation", { name: "On this service page" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Find the support you need." }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Prepare for a useful review." }),
    ).toBeInTheDocument();
    expect(screen.getByText("How the next step works")).toBeInTheDocument();
    expect(
      screen.getByRole("navigation", { name: "Breadcrumb" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Back to all services" }),
    ).toHaveAttribute("href", "/services");
    const tool = getDestination(service.toolDestinationId);
    expect(
      screen.getByRole("link", { name: `Open ${tool.label}` }),
    ).toHaveAttribute("href", tool.href);
    expect(container.querySelector("form")).toBeNull();
    const content = serviceSectionContent[service.slug];
    const expectedServices = content.catalog.flatMap((group) => group.services);
    const quoteLinks = [
      ...container.querySelectorAll('a[aria-label^="Request a quote for"]'),
    ];
    expect(quoteLinks).toHaveLength(expectedServices.length);
    expect(container.querySelectorAll("details")).toHaveLength(
      content.catalog.length + expectedServices.length + content.faqs.length,
    );
    for (const anchor of container.querySelectorAll(
      'nav[aria-label="On this service page"] a',
    )) {
      expect(
        container.querySelector(anchor.getAttribute("href")!),
      ).not.toBeNull();
    }
  });

  it("URL-encodes a contextual contact intent", () => {
    for (const service of servicePages) {
      const url = new URL(
        destinationIntents.whatsapp({ topic: service.contactTopic }),
      );
      expect(url.origin + url.pathname).toBe("https://wa.me/628213454721");
      expect(url.searchParams.get("text")).toBe(
        `Hello Bali Zero, I would like to discuss ${service.contactTopic}.`,
      );
      expect([...url.searchParams.keys()]).toEqual(["text"]);
    }
  });

  it("offers reachable home and services recovery from a missing page", () => {
    render(<NotFound />);
    expect(
      screen.getByRole("heading", { level: 1, name: "Page not found." }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to home" })).toHaveAttribute(
      "href",
      "/",
    );
    expect(
      screen.getByRole("link", { name: "Explore services" }),
    ).toHaveAttribute("href", "/services");
    screen.getByRole("main").focus();
    expect(screen.getByRole("main")).toHaveFocus();
  });

  it("keeps native link navigation keyboard reachable", async () => {
    const user = userEvent.setup();
    render(<ServiceDetail service={servicePages[0]} />);
    await user.tab();
    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveFocus();
    await user.tab();
    const main = screen.getByRole("main");
    const siteBanners = screen
      .getAllByRole("banner")
      .filter((banner) => !main.contains(banner));
    expect(siteBanners).toHaveLength(1);
    expect(
      within(siteBanners[0]).getByRole("link", { name: "Bali Zero home" }),
    ).toHaveFocus();
  });

  it("provides descriptive metadata for every route", async () => {
    expect(overviewMetadata.description).toContain("immigration");
    for (const service of servicePages) {
      const metadata = await generateMetadata({
        params: Promise.resolve({ slug: service.slug }),
      });
      expect(metadata.title).toContain(service.title);
      expect(metadata.description).toBe(service.metaDescription);
    }
  });
});
