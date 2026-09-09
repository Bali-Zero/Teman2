import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Portal } from "./Portal";
import { Journal } from "./Journal";
import { Services } from "./Services";
import { Evoa } from "./Evoa";
import { SecondHome } from "./SecondHome";
import { contactHref } from "../content/services";
import { getPublicJournalArticles } from "../content/journal";

describe("client portal introduction", () => {
  it("explains all three account areas without inventing interactive product views", () => {
    render(<Portal />);
    const portal = screen.getByRole("region", { name: /Your case/ });
    const terms = within(portal).getAllByRole("term");
    const definitions = within(portal).getAllByRole("definition");
    expect(terms).toHaveLength(3);
    expect(definitions).toHaveLength(3);
    for (const [index, title, detail] of [
      [0, "Documents", "records shared with your account"],
      [1, "Applications", "next steps linked to your case"],
      [2, "Conversations", "your Bali Zero team"],
    ] as const) {
      expect(terms[index]).toHaveTextContent(title);
      expect(definitions[index]).toHaveTextContent(detail);
    }
    expect(within(portal).getByText(/depend on your account and permissions/)).toBeVisible();
    expect(within(portal).queryByRole("tab")).not.toBeInTheDocument();
    expect(within(portal).queryByRole("tabpanel")).not.toBeInTheDocument();
  });

  it("provides keyboard access to real sign-in and contextual account help", async () => {
    const user = userEvent.setup();
    render(<Portal />);
    const signIn = screen.getByRole("link", { name: /Sign in/ });
    const help = screen.getByRole("link", { name: /Need access or help/ });
    expect(signIn).toHaveAttribute("href", "https://my.balizero.com/");
    expect(signIn).toHaveAttribute("target", "_blank");
    expect(signIn).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByText(/Opens My Bali Zero in a new tab/)).toBeVisible();
    expect(help).toHaveAttribute("href", "/contact?topic=portal&from=home");
    await user.tab();
    expect(signIn).toHaveFocus();
    await user.tab();
    expect(help).toHaveFocus();
  });
});
describe("editorial carousel", () => {
  it("keeps image, heading, date and destination together in both directions", async () => {
    const user = userEvent.setup();
    render(<Journal articles={getPublicJournalArticles()} />);
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
    expect(feature).toHaveTextContent("23 June 2026");
    expect(feature).not.toHaveTextContent(/min read/);
    expect(
      screen.getByRole("link", { name: /Explore the Journal/ }),
    ).toHaveAttribute("href", "/journal");
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
    ).toHaveAttribute("href", "/kbli");
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
