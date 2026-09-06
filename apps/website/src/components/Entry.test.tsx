import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { Hero, SiteHeader } from "./Entry";

afterEach(cleanup);

describe("SiteHeader", () => {
  it("keeps every navigation destination in the mobile disclosure", () => {
    render(<SiteHeader />);
    const button = screen.getByRole("button", { name: "Menu" });
    const navigation = screen.getByRole("navigation", {
      name: "Main navigation",
    });
    expect(button.getAttribute("aria-expanded")).toBe("false");
    expect(button.getAttribute("aria-controls")).toBe(navigation.id);
    expect(navigation.getAttribute("data-open")).toBe("false");
    fireEvent.click(button);
    expect(button.getAttribute("aria-expanded")).toBe("true");
    expect(navigation.getAttribute("data-open")).toBe("true");
    for (const [name, href] of [
      ["Explore", "#tools"],
      ["Services", "/services"],
      ["Journal", "/journal"],
      ["Our team", "#team"],
      ["My account", "https://my.balizero.com/"],
    ]) {
      expect(
        within(navigation).getByRole("link", { name }).getAttribute("href"),
      ).toBe(href);
    }
  });

  it("opens with Enter, allows Tab navigation and restores focus on Escape", async () => {
    const user = userEvent.setup();
    render(<SiteHeader />);
    const button = screen.getByRole("button", { name: "Menu" });
    button.focus();
    await user.keyboard("{Enter}");
    expect(button.getAttribute("aria-expanded")).toBe("true");
    await user.tab();
    expect(document.activeElement).toBe(
      screen.getByRole("link", { name: "Explore" }),
    );
    await user.keyboard("{Escape}");
    expect(button.getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(button);
  });

  it("closes after navigation and when focus leaves the header", async () => {
    const user = userEvent.setup();
    render(
      <>
        <SiteHeader />
        <button type="button">Outside header</button>
      </>,
    );
    const button = screen.getByRole("button", { name: "Menu" });
    await user.click(button);
    await user.click(screen.getByRole("link", { name: "Our team" }));
    expect(button.getAttribute("aria-expanded")).toBe("false");
    await user.click(button);
    await user.click(screen.getByRole("button", { name: "Outside header" }));
    expect(button.getAttribute("aria-expanded")).toBe("false");
  });
});

describe("Hero", () => {
  it("offers explicit category links to the matching local service journeys", () => {
    render(<Hero />);
    const startingPoints = screen.getByRole("list", {
      name: "Choose where to start",
    });
    const destinations = [
      ["Visas & residence", "/services/immigration"],
      ["Business & company", "/services/company-setup"],
      ["Tax", "/services/tax"],
      ["Property", "/services/property"],
    ];
    expect(within(startingPoints).getAllByRole("link")).toHaveLength(
      destinations.length,
    );
    for (const [name, href] of destinations) {
      expect(
        within(startingPoints).getByRole("link", { name }).getAttribute("href"),
      ).toBe(href);
    }
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(
      screen
        .getByRole("link", { name: "Talk to our team" })
        .getAttribute("href"),
    ).toBe("#contact");
  });
});
