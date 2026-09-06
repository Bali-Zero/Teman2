import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { ServiceDetail, ServicesOverview } from "../../components/services/ServiceJourneys";
import { destinationIntents, getDestination } from "../../content/destinations";
import { servicePages } from "../../content/service-pages";
import { generateMetadata, generateStaticParams } from "./[slug]/page";
import { metadata as overviewMetadata } from "./page";

afterEach(cleanup);

describe("service journeys", () => {
  it("publishes an overview and four resolvable local journeys", () => {
    const { container } = render(<ServicesOverview />);
    const localRoutes = new Set([
      "/",
      "/services",
      ...servicePages.map(({ slug }) => `/services/${slug}`),
    ]);
    const links = [...container.querySelectorAll('a[href^="/"]')];
    expect(servicePages).toHaveLength(4);
    expect(generateStaticParams()).toEqual(
      servicePages.map(({ slug }) => ({ slug })),
    );
    for (const link of links) {
      expect(localRoutes.has(link.getAttribute("href")!)).toBe(true);
    }
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.queryByRole("form")).not.toBeInTheDocument();
  });

  it.each(servicePages)("renders one complete $slug page", (service) => {
    const { container } = render(<ServiceDetail service={service} />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByText("Who this helps")).toBeInTheDocument();
    expect(screen.getByText("Questions to discuss")).toBeInTheDocument();
    expect(screen.getByText("How the next step works")).toBeInTheDocument();
    expect(
      screen.getByRole("navigation", { name: "Breadcrumb" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Back to all services" }),
    ).toHaveAttribute("href", "/services");
    const tool = getDestination(service.toolDestinationId);
    expect(screen.getByRole("link", { name: `Open ${tool.label}` })).toHaveAttribute(
      "href",
      tool.href,
    );
    expect(container.querySelector("form")).toBeNull();
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

  it("keeps native link navigation keyboard reachable", async () => {
    const user = userEvent.setup();
    render(<ServiceDetail service={servicePages[0]} />);
    await user.tab();
    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("link", { name: "Bali Zero home" })).toHaveFocus();
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
