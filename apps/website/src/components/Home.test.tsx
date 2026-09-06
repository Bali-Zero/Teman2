import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Portal } from "./Portal";
import { Journal } from "./Journal";
import { Services } from "./Services";
import { Evoa } from "./Evoa";
import { SecondHome } from "./SecondHome";
import { contactHref } from "../content/services";

describe("client portal feature preview", () => {
  it("shows one panel and supports all tab keyboard transitions", async () => {
    const user = userEvent.setup();
    render(<Portal />);
    const tabs = screen.getAllByRole("tab");
    expect(screen.getAllByRole("tabpanel")).toHaveLength(1);
    expect(screen.getByRole("tabpanel")).toHaveTextContent(
      "Document organisation.",
    );
    tabs[0].focus();
    await user.keyboard("{ArrowRight}");
    expect(tabs[1]).toHaveFocus();
    expect(tabs[1]).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveTextContent(
      "Application updates.",
    );
    await user.keyboard("{End}");
    expect(tabs[2]).toHaveFocus();
    await user.keyboard("{ArrowRight}");
    expect(tabs[0]).toHaveFocus();
    await user.keyboard("{ArrowLeft}");
    expect(tabs[2]).toHaveFocus();
    await user.keyboard("{Home}");
    expect(tabs[0]).toHaveFocus();
    await user.click(tabs[2]);
    expect(screen.getByRole("tabpanel")).toHaveTextContent(
      "Team conversations.",
    );
    expect(screen.getAllByRole("tabpanel")).toHaveLength(1);
  });
  it("distinguishes the preview from account access", () => {
    render(<Portal />);
    expect(screen.getByText("Feature preview")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Sign in/ })).toHaveAttribute(
      "href",
      "https://my.balizero.com",
    );
  });
});
describe("editorial carousel", () => {
  it("keeps image, heading, date and destination together in both directions", async () => {
    const user = userEvent.setup();
    render(<Journal />);
    const feature = screen.getByRole("article", {
      name: "Featured editorial stories",
    });
    await user.click(
      screen.getByRole("button", { name: "Next editorial story" }),
    );
    expect(within(feature).getByRole("link")).toHaveAttribute(
      "href",
      "https://balizero.com/business/the-villa-dream-has-a-new-wall",
    );
    expect(within(feature).getByRole("img")).toHaveAttribute(
      "src",
      "/assets/villa-wall.png",
    );
    expect(feature).toHaveTextContent("23 June 2026 · 4 min read");
    expect(feature).toHaveTextContent("02 / 02");
    feature.focus();
    await user.keyboard("{ArrowRight}");
    expect(feature).toHaveTextContent("01 / 02");
    await user.click(
      screen.getByRole("button", { name: "Previous editorial story" }),
    );
    expect(feature).toHaveTextContent("02 / 02");
  });
});
describe("service routes", () => {
  it("provides four direct product links and four contextual conversations", () => {
    render(<Services />);
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Find a business code/ }),
    ).toHaveAttribute("href", "https://balizero.com/kbli");
    const contacts = screen.getAllByRole("link", { name: /Talk to our team/ });
    expect(contacts).toHaveLength(4);
    expect(new Set(contacts.map((x) => x.getAttribute("href"))).size).toBe(4);
    for (const id of ["visa", "business", "tax", "property"])
      expect(document.getElementById(id + "-tool")).toBeInTheDocument();
  });
  it("encodes user-facing topics as a single message parameter", () => {
    const url = new URL(contactHref("Tax & accounting"));
    expect(url.searchParams.get("text")).toBe(
      "Hello Bali Zero, I would like to discuss Tax & accounting.",
    );
    expect([...url.searchParams.keys()]).toEqual(["text"]);
  });
  it("preserves the project and host in the conversation link", () => {
    render(
      <>
        <Evoa />
        <SecondHome />
      </>,
    );
    for (const name of ["Surya", "Ari"]) {
      const link = screen.getByRole("link", {
        name: new RegExp("Contact our team about " + name),
      });
      expect(
        new URL(link.getAttribute("href")!).searchParams.get("text"),
      ).toContain(name);
    }
  });
});
